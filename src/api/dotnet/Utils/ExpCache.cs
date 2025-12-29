using System.Collections.Concurrent;
using Microsoft.Agents.AI;
using CsApi.Auth;
using Azure.AI.Projects;
using Azure.AI.Projects.OpenAI;

namespace CsApi.Utils
{
    /// <summary>
    /// TTL-based cache with automatic cleanup functionality
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

        public ExpCache(int maxSize, double ttlSeconds, IConfiguration configuration, string azureAIEndpoint = "")
        {
            _cache = new ConcurrentDictionary<TKey, CacheItem>();
            _maxSize = maxSize;
            _ttlSeconds = ttlSeconds;
            _azureAIEndpoint = azureAIEndpoint;
            _configuration = configuration;
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
                    // Item expired, remove it and delete thread immediately
                    if (_cache.TryRemove(key, out var removedItem))
                    {
                        // Delete thread immediately when expired
                        Task.Run(() => DeleteThreadAsync(removedItem.Value));
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
            
            // If we exceed max size, remove oldest items immediately and delete their threads
            if (_cache.Count > _maxSize)
            {
                var now = DateTime.UtcNow;
                
                // First, try to remove expired items
                var expiredItems = _cache
                    .Where(kvp => kvp.Value.ExpiresAt <= now)
                    .ToList();
                
                foreach (var kvp in expiredItems)
                {
                    if (_cache.TryRemove(kvp.Key, out var removedItem))
                    {
                        Task.Run(() => DeleteThreadAsync(removedItem.Value));
                    }
                }
                
                // If still over max size after removing expired items, remove oldest non-expired items
                if (_cache.Count > _maxSize)
                {
                    var excessCount = _cache.Count - _maxSize;
                    var oldestItems = _cache
                        .OrderBy(kvp => kvp.Value.CreatedAt)
                        .Take(excessCount)
                        .ToList();

                    foreach (var kvp in oldestItems)
                    {
                        if (_cache.TryRemove(kvp.Key, out var removedItem))
                        {
                            // Delete thread immediately when LRU evicted
                            Task.Run(() => DeleteThreadAsync(removedItem.Value));
                        }
                    }
                }
            }
        }

        public bool Remove(TKey key)
        {
            if (_cache.TryRemove(key, out var removedItem))
            {
                // Delete thread immediately when manually removed
                Task.Run(() => DeleteThreadAsync(removedItem.Value));
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
            var expiredItems = _cache
                .Where(kvp => kvp.Value.ExpiresAt <= now)
                .ToList();

            foreach (var kvp in expiredItems)
            {
                if (_cache.TryRemove(kvp.Key, out var removedItem))
                {
                    // Delete thread immediately like other cleanup operations
                    await DeleteThreadAsync(removedItem.Value);
                }
            }
        }

        /// <summary>
        /// Delete thread from Azure AI Foundry when removed from cache
        /// </summary>
        private async Task DeleteThreadAsync(TValue value)
        {
            if (value is AgentThread agentThread && !string.IsNullOrEmpty(_azureAIEndpoint))
            {
                try
                {
                    // Clean up using Agent Framework pattern: thread is ChatClientAgentThread
                    if (agentThread is ChatClientAgentThread chatThread)
                    {
                        var endpoint = _configuration["AZURE_AI_AGENT_ENDPOINT"]
                                ?? throw new InvalidOperationException("AZURE_AI_AGENT_ENDPOINT is required");
                        var credentialFactory = new AzureCredentialFactory(_configuration);
                        var credential = credentialFactory.Create();
                        AIProjectClient projectClient = new AIProjectClient(new Uri(endpoint), credential);

                        await projectClient.GetProjectOpenAIClient()
                            .GetProjectConversationsClient()
                            .DeleteConversationAsync(chatThread.ConversationId);
                    }
                    else
                    {
                        Console.WriteLine($"ExpCache: AgentThread is not ChatClientAgentThread, actual type: {agentThread.GetType().Name}");
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"ExpCache: Failed to delete thread: {ex.Message}");
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