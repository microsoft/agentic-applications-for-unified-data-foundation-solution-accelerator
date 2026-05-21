using System.Collections.Concurrent;
using Azure;
using Microsoft.Extensions.Logging;
using CsApi.Auth;
using Azure.AI.Projects;

namespace CsApi.Utils
{
    /// <summary>
    /// TTL-based cache with automatic cleanup functionality.
    /// Stores conversation IDs (strings) keyed by application conversation ID,
    /// mirroring the Python ExpCache pattern.
    /// </summary>
    /// <typeparam name="TKey">Cache key type</typeparam>
    /// <typeparam name="TValue">Cache value type</typeparam>
    public class ExpCache<TKey, TValue> : IDisposable
        where TKey : notnull
    {
        private readonly ConcurrentDictionary<TKey, CacheItem> _cache;
        private readonly int _maxSize;
        private readonly double _ttlSeconds;
        private readonly string _azureAIEndpoint;
        private readonly IConfiguration _configuration;
        private readonly ILogger _logger;

        public ExpCache(int maxSize, double ttlSeconds, IConfiguration configuration, ILogger logger, string azureAIEndpoint = "")
        {
            _cache = new ConcurrentDictionary<TKey, CacheItem>();
            _maxSize = maxSize;
            _ttlSeconds = ttlSeconds;
            _azureAIEndpoint = azureAIEndpoint;
            _configuration = configuration;
            _logger = logger;
        }

        public bool TryGet(TKey key, out TValue value)
        {
            if (_cache.TryGetValue(key, out var item))
            {
                if (DateTime.UtcNow <= item.ExpiresAt)
                {
                    value = item.Value;
                    return true;
                }
                else
                {
                    // Item expired, remove it and delete conversation immediately
                    if (_cache.TryRemove(key, out var removedItem))
                    {
                        Task.Run(() => DeleteConversationAsync(removedItem.Value));
                    }
                }
            }

            value = default(TValue)!;
            return false;
        }

        public void Set(TKey key, TValue value)
        {
            var expiresAt = DateTime.UtcNow.AddSeconds(_ttlSeconds);
            var item = new CacheItem(value, expiresAt);
            
            _cache.AddOrUpdate(key, item, (k, v) => item);
            
            // If we exceed max size, remove oldest items immediately and delete their conversations
            if (_cache.Count > _maxSize)
            {
                var now = DateTime.UtcNow;
                
                // First, try to remove expired items
                foreach (var kvp in _cache.Where(kvp => kvp.Value.ExpiresAt <= now))
                {
                    if (_cache.TryRemove(kvp.Key, out var removedItem))
                    {
                        Task.Run(() => DeleteConversationAsync(removedItem.Value));
                    }
                }
                
                // If still over max size after removing expired items, remove oldest non-expired items
                if (_cache.Count > _maxSize)
                {
                    var excessCount = _cache.Count - _maxSize;
                    var oldestItems = _cache
                        .OrderBy(kvp => kvp.Value.CreatedAt)
                        .Take(excessCount);

                    foreach (var kvp in oldestItems)
                    {
                        if (_cache.TryRemove(kvp.Key, out var removedItem))
                        {
                            Task.Run(() => DeleteConversationAsync(removedItem.Value));
                        }
                    }
                }
            }
        }

        public bool Remove(TKey key)
        {
            if (_cache.TryRemove(key, out var removedItem))
            {
                Task.Run(() => DeleteConversationAsync(removedItem.Value));
                return true;
            }
            return false;
        }

        public void Clear()
        {
            _cache.Clear();
        }

        public int Count => _cache.Count;

        /// <summary>
        /// Force cleanup of expired items for testing - manually triggers cleanup
        /// </summary>
        public async Task ForceCleanupAsync()
        {
            var now = DateTime.UtcNow;
            foreach (var kvp in _cache.Where(kvp => kvp.Value.ExpiresAt <= now))
            {
                if (_cache.TryRemove(kvp.Key, out var removedItem))
                {
                    await DeleteConversationAsync(removedItem.Value);
                }
            }
        }

        /// <summary>
        /// Delete conversation from Azure AI Foundry when removed from cache.
        /// Mirrors Python ExpCache._delete_thread_async behavior.
        /// </summary>
        private async Task DeleteConversationAsync(TValue value)
        {
            if (value is string conversationId && !string.IsNullOrEmpty(_azureAIEndpoint))
            {
                try
                {
                    // Response IDs (resp_xxx) don't need explicit deletion
                    if (conversationId.StartsWith("resp_"))
                    {
                        _logger.LogInformation("ExpCache: Skipping deletion for response ID: {ConversationId}", conversationId);
                        return;
                    }

                    var endpoint = _configuration["AZURE_AI_AGENT_ENDPOINT"]
                            ?? throw new InvalidOperationException("AZURE_AI_AGENT_ENDPOINT is required");
                    var credentialFactory = new AzureCredentialFactory(_configuration);
                    var credential = credentialFactory.Create();
                    AIProjectClient projectClient = new AIProjectClient(new Uri(endpoint), credential);

                    await projectClient.GetProjectOpenAIClient()
                        .GetProjectConversationsClient()
                        .DeleteConversationAsync(conversationId);

                    _logger.LogInformation("ExpCache: Conversation deleted successfully: {ConversationId}", conversationId);
                }
                catch (InvalidOperationException ex)
                {
                    _logger.LogWarning(ex, "ExpCache: Configuration error deleting conversation");
                }
                catch (RequestFailedException ex)
                {
                    _logger.LogWarning(ex, "ExpCache: Azure API error deleting conversation");
                }
                catch (UriFormatException ex)
                {
                    _logger.LogError(ex, "ExpCache: Invalid endpoint URI while deleting conversation");
                }
                catch (ArgumentException ex)
                {
                    _logger.LogError(ex, "ExpCache: Invalid argument while deleting conversation");
                }
                catch (Exception ex) when (ex is not InvalidOperationException && ex is not RequestFailedException && ex is not UriFormatException && ex is not ArgumentException)
                {
                    _logger.LogError(ex, "ExpCache: Unexpected error deleting conversation");
                }
            }
        }

        public void Dispose()
        {
            // No resources to dispose since we do immediate cleanup
        }

        private class CacheItem
        {
            public TValue Value { get; }
            public DateTime CreatedAt { get; }
            public DateTime ExpiresAt { get; }

            public CacheItem(TValue value, DateTime expiresAt)
            {
                Value = value;
                CreatedAt = DateTime.UtcNow;
                ExpiresAt = expiresAt;
            }
        }
    }
}