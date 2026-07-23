using CsApi.Interfaces;
using CsApi.Models;
using Microsoft.Azure.Cosmos;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace CsApi.Repositories;

/// <summary>
/// Cosmos DB conversation repository for history storage.
/// Uses partition key = userId.
/// </summary>
public class CosmosConversationRepository : IConversationRepository, IAsyncDisposable
{
    private readonly CosmosClient _cosmosClient;
    private readonly Container _container;
    private readonly ILogger<CosmosConversationRepository> _logger;
    private readonly bool _enableFeedback;

    public CosmosConversationRepository(IConfiguration config, ILogger<CosmosConversationRepository> logger, CsApi.Auth.IAzureCredentialFactory credentialFactory)
    {
        _logger = logger;
        _enableFeedback = string.Equals(config["AZURE_COSMOSDB_ENABLE_FEEDBACK"], "true", StringComparison.OrdinalIgnoreCase);

        var account = config["AZURE_COSMOSDB_ACCOUNT"]
            ?? throw new InvalidOperationException("AZURE_COSMOSDB_ACCOUNT is required");
        var database = config["AZURE_COSMOSDB_DATABASE"]
            ?? throw new InvalidOperationException("AZURE_COSMOSDB_DATABASE is required");
        var container = config["AZURE_COSMOSDB_CONVERSATIONS_CONTAINER"]
            ?? throw new InvalidOperationException("AZURE_COSMOSDB_CONVERSATIONS_CONTAINER is required");

        var endpoint = $"https://{account}.documents.azure.com:443/";
        var credential = credentialFactory.Create(config["AZURE_CLIENT_ID"]);

        _cosmosClient = new CosmosClient(endpoint, credential);

        _container = _cosmosClient.GetContainer(database, container);
    }

    public async Task<bool> EnsureConfiguredAsync()
    {
        try
        {
            await _container.ReadContainerAsync();
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "CosmosDB container not accessible");
            return false;
        }
    }

    public async Task<ConversationSummary?> CreateConversationAsync(string userId, string? conversationId, string title, CancellationToken ct)
    {
        var id = conversationId ?? Guid.NewGuid().ToString();
        var now = DateTime.UtcNow.ToString("o");

        var doc = new JsonObject
        {
            ["id"] = id,
            ["type"] = "conversation",
            ["createdAt"] = now,
            ["updatedAt"] = now,
            ["userId"] = userId,
            ["title"] = title,
            ["conversation_id"] = id
        };

        try
        {
            await UpsertJsonNodeAsync(doc, userId, ct);
            return new ConversationSummary
            {
                ConversationId = id,
                Title = title,
                CreatedAt = DateTime.Parse(now),
                UpdatedAt = DateTime.Parse(now)
            };
        }
        catch (CosmosException ex)
        {
            _logger.LogError(ex, "Failed to create conversation {Id}", id);
            return null;
        }
    }

    public async Task<ConversationSummary?> GetConversationAsync(string userId, string conversationId, CancellationToken ct)
    {
        var query = new QueryDefinition(
            "SELECT * FROM c WHERE c.id = @id AND c.type = 'conversation' AND c.userId = @userId")
            .WithParameter("@id", conversationId)
            .WithParameter("@userId", userId);

        await foreach (var item in QueryItemsAsync(query, ct))
        {
            return MapToConversationSummary(item);
        }

        return null;
    }

    public async Task<IReadOnlyList<ConversationSummary>> GetConversationsAsync(string userId, int offset, int limit, string sortOrder, CancellationToken ct)
    {
        // OFFSET and LIMIT must be integer literals in Cosmos DB SQL (cannot be parameterized)
        var order = sortOrder.Equals("ASC", StringComparison.OrdinalIgnoreCase) ? "ASC" : "DESC";
        var sql = $"SELECT * FROM c WHERE c.userId = @userId AND c.type = 'conversation' ORDER BY c.updatedAt {order} OFFSET {offset} LIMIT {limit}";

        var query = new QueryDefinition(sql)
            .WithParameter("@userId", userId);

        var results = new List<ConversationSummary>();
        await foreach (var item in QueryItemsAsync(query, ct))
        {
            var summary = MapToConversationSummary(item);
            if (summary != null) results.Add(summary);
        }

        return results;
    }

    public async Task<bool> UpsertConversationAsync(string userId, ConversationSummary conversation, CancellationToken ct)
    {
        try
        {
            var rawDoc = await ReadItemAsJsonAsync(conversation.ConversationId, userId, ct);
            if (rawDoc == null) return false;

            var node = JsonNode.Parse(rawDoc.Value.GetRawText());
            if (node == null) return false;

            node["title"] = conversation.Title;
            node["updatedAt"] = DateTime.UtcNow.ToString("o");

            await UpsertJsonNodeAsync(node, userId, ct);
            return true;
        }
        catch (CosmosException ex)
        {
            _logger.LogError(ex, "Failed to upsert conversation {Id}", conversation.ConversationId);
            return false;
        }
    }

    public async Task CreateMessageAsync(string userId, string conversationId, ChatMessage message, CancellationToken ct)
    {
        var now = DateTime.UtcNow.ToString("o");
        var messageId = string.IsNullOrEmpty(message.Id) ? Guid.NewGuid().ToString() : message.Id;

        var doc = new JsonObject
        {
            ["id"] = messageId,
            ["type"] = "message",
            ["userId"] = userId,
            ["createdAt"] = now,
            ["updatedAt"] = now,
            ["conversationId"] = conversationId,
            ["role"] = message.Role,
            ["content"] = BuildContentPayloadNode(message)
        };

        if (_enableFeedback)
        {
            doc["feedback"] = message.Feedback ?? "";
        }

        await UpsertJsonNodeAsync(doc, userId, ct);

        // Update parent conversation's updatedAt
        var conversation = await GetConversationAsync(userId, conversationId, ct);
        if (conversation != null)
        {
            await UpdateConversationTimestamp(userId, conversationId, now, ct);
        }
    }

    public async Task<IReadOnlyList<ChatMessage>> GetMessagesAsync(string userId, string conversationId, CancellationToken ct)
    {
        var query = new QueryDefinition(
            "SELECT * FROM c WHERE c.conversationId = @conversationId AND c.type = 'message' AND c.userId = @userId ORDER BY c.createdAt ASC")
            .WithParameter("@conversationId", conversationId)
            .WithParameter("@userId", userId);

        var results = new List<ChatMessage>();
        await foreach (var item in QueryItemsAsync(query, ct))
        {
            var msg = MapToChatMessage(item);
            if (msg != null) results.Add(msg);
        }

        return results;
    }

    public async Task<bool> UpdateMessageFeedbackAsync(string userId, string messageId, string feedback, CancellationToken ct)
    {
        try
        {
            var rawDoc = await ReadItemAsJsonAsync(messageId, userId, ct);
            if (rawDoc == null) return false;

            var node = JsonNode.Parse(rawDoc.Value.GetRawText());
            if (node == null) return false;

            node["feedback"] = feedback;

            await UpsertJsonNodeAsync(node, userId, ct);
            return true;
        }
        catch (CosmosException ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
        {
            return false;
        }
    }

    public async Task<bool> DeleteConversationAsync(string userId, string conversationId, CancellationToken ct)
    {
        try
        {
            // Verify conversation belongs to user
            var conversation = await GetConversationAsync(userId, conversationId, ct);
            if (conversation == null) return false;

            // Delete all messages first
            await DeleteMessagesAsync(userId, conversationId, ct);

            // Delete the conversation
            await _container.DeleteItemAsync<object>(conversationId, new PartitionKey(userId), cancellationToken: ct);
            return true;
        }
        catch (CosmosException ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
        {
            return false;
        }
    }

    public async Task<bool> DeleteAllConversationsAsync(string userId, CancellationToken ct)
    {
        var conversations = await GetConversationsAsync(userId, 0, 10000, "DESC", ct);
        if (conversations.Count == 0) return false;

        foreach (var conv in conversations)
        {
            await DeleteConversationAsync(userId, conv.ConversationId, ct);
        }

        return true;
    }

    public async Task<bool> ClearMessagesAsync(string userId, string conversationId, CancellationToken ct)
    {
        try
        {
            var conversation = await GetConversationAsync(userId, conversationId, ct);
            if (conversation == null) return false;

            await DeleteMessagesAsync(userId, conversationId, ct);
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to clear messages for conversation {Id}", conversationId);
            return false;
        }
    }

    private async Task DeleteMessagesAsync(string userId, string conversationId, CancellationToken ct)
    {
        var messages = await GetMessagesAsync(userId, conversationId, ct);
        foreach (var msg in messages)
        {
            try
            {
                await _container.DeleteItemAsync<object>(msg.Id, new PartitionKey(userId), cancellationToken: ct);
            }
            catch (CosmosException ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
            {
                // Already deleted
            }
        }
    }

    private async Task UpdateConversationTimestamp(string userId, string conversationId, string timestamp, CancellationToken ct)
    {
        try
        {
            var rawDoc = await ReadItemAsJsonAsync(conversationId, userId, ct);
            if (rawDoc == null) return;

            // Use JsonNode for safe in-place modification (avoids JsonElement serialization issues)
            var node = JsonNode.Parse(rawDoc.Value.GetRawText());
            if (node == null) return;

            node["updatedAt"] = timestamp;

            await UpsertJsonNodeAsync(node, userId, ct);
        }
        catch (CosmosException ex)
        {
            _logger.LogWarning(ex, "Failed to update conversation timestamp for {Id}", conversationId);
        }
    }

    private static JsonNode BuildContentPayloadNode(ChatMessage message)
    {
        // Store content as structured payload: {"role": "...", "content": "...", "citations": [...]}
        var contentStr = message.GetContentAsString();
        var citations = message.GetCitationsAsJsonString();

        var payload = new JsonObject
        {
            ["role"] = message.Role,
            ["content"] = contentStr
        };

        if (!string.IsNullOrEmpty(citations))
        {
            try
            {
                payload["citations"] = JsonNode.Parse(citations);
            }
            catch (JsonException)
            {
                payload["citations"] = citations;
            }
        }

        return payload;
    }

    private static ConversationSummary? MapToConversationSummary(JsonElement item)
    {
        try
        {
            var id = item.GetProperty("id").GetString() ?? "";
            var title = item.TryGetProperty("title", out var t) ? t.GetString() ?? "" : "";
            var createdAt = item.TryGetProperty("createdAt", out var ca) ? ParseDateTime(ca) : DateTime.UtcNow;
            var updatedAt = item.TryGetProperty("updatedAt", out var ua) ? ParseDateTime(ua) : DateTime.UtcNow;

            return new ConversationSummary
            {
                ConversationId = id,
                Title = title,
                CreatedAt = createdAt,
                UpdatedAt = updatedAt
            };
        }
        catch
        {
            return null;
        }
    }

    private static ChatMessage? MapToChatMessage(JsonElement item)
    {
        try
        {
            var msg = new ChatMessage
            {
                Id = item.GetProperty("id").GetString() ?? Guid.NewGuid().ToString(),
                Role = item.TryGetProperty("role", out var r) ? r.GetString() ?? "user" : "user"
            };

            // Content can be string or object {content, citations}
            if (item.TryGetProperty("content", out var content))
            {
                if (content.ValueKind == JsonValueKind.Object)
                {
                    var contentText = content.TryGetProperty("content", out var ct)
                        ? ct.GetString() ?? ""
                        : "";
                    msg.SetContentFromString(contentText);

                    if (content.TryGetProperty("citations", out var cit))
                    {
                        msg.Citations = cit.Clone();
                    }
                }
                else if (content.ValueKind == JsonValueKind.String)
                {
                    msg.SetContentFromString(content.GetString() ?? "");
                }
            }

            if (item.TryGetProperty("feedback", out var fb))
            {
                msg.Feedback = fb.GetString() ?? "";
            }

            if (item.TryGetProperty("createdAt", out var createdAtProp))
            {
                msg.CreatedAt = ParseDateTime(createdAtProp);
            }

            return msg;
        }
        catch
        {
            return null;
        }
    }

    private static DateTime ParseDateTime(JsonElement element)
    {
        if (element.ValueKind == JsonValueKind.String)
        {
            return DateTime.TryParse(element.GetString(), out var dt) ? dt : DateTime.UtcNow;
        }
        return DateTime.UtcNow;
    }

    /// <summary>
    /// Stream-based query that bypasses the Cosmos SDK serializer.
    /// Reads raw JSON from Cosmos and parses with System.Text.Json directly.
    /// </summary>
    private async IAsyncEnumerable<JsonElement> QueryItemsAsync(QueryDefinition query, [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct)
    {
        using var iterator = _container.GetItemQueryStreamIterator(query);
        while (iterator.HasMoreResults)
        {
            using var response = await iterator.ReadNextAsync(ct);
            response.EnsureSuccessStatusCode();

            using var doc = await JsonDocument.ParseAsync(response.Content, cancellationToken: ct);
            if (doc.RootElement.TryGetProperty("Documents", out var documents))
            {
                foreach (var item in documents.EnumerateArray())
                {
                    yield return item.Clone();
                }
            }
        }
    }

    /// <summary>
    /// Read a single item by id and partition key, returning parsed JsonElement.
    /// </summary>
    private async Task<JsonElement?> ReadItemAsJsonAsync(string id, string partitionKey, CancellationToken ct)
    {
        try
        {
            using var response = await _container.ReadItemStreamAsync(id, new PartitionKey(partitionKey), cancellationToken: ct);
            if (!response.IsSuccessStatusCode) return null;

            using var doc = await JsonDocument.ParseAsync(response.Content, cancellationToken: ct);
            return doc.RootElement.Clone();
        }
        catch (CosmosException)
        {
            return null;
        }
    }

    /// <summary>
    /// Upsert a JsonNode document using stream API (bypasses SDK serializer).
    /// </summary>
    private async Task UpsertJsonNodeAsync(JsonNode node, string partitionKey, CancellationToken ct)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
        {
            node.WriteTo(writer);
        }
        stream.Position = 0;

        using var response = await _container.UpsertItemStreamAsync(stream, new PartitionKey(partitionKey), cancellationToken: ct);
        response.EnsureSuccessStatusCode();
    }

    public ValueTask DisposeAsync()
    {
        _cosmosClient?.Dispose();
        return ValueTask.CompletedTask;
    }
}
