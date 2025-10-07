using System.Text.Json.Serialization;
using System.Text.Json;

namespace CsApi.Models;

public class ChatRequest
{
    [JsonPropertyName("conversation_id")] public string? ConversationId { get; set; }
    [JsonPropertyName("messages")] public List<ChatMessage>? Messages { get; set; }
}

public class ChatMessage
{
    [JsonPropertyName("id")] public string Id { get; set; } = Guid.NewGuid().ToString();
    [JsonPropertyName("role")] public string Role { get; set; } = "user";
    
    // Content can be either string or structured JSON (like chart data) - matches Python flexibility
    [JsonPropertyName("content")] public JsonElement Content { get; set; } = JsonSerializer.SerializeToElement(string.Empty);
    
    [JsonPropertyName("created_at")] public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    
    // Citations can be any JSON structure (array, object, etc.) - matches Python flexibility
    [JsonPropertyName("citations")] public JsonElement? Citations { get; set; }
    
    [JsonPropertyName("feedback")] public string Feedback { get; set; } = string.Empty;
    
    // Helper method to get content as string
    public string GetContentAsString()
    {
        try
        {
            if (Content.ValueKind == JsonValueKind.String)
                return Content.GetString() ?? string.Empty;
            else
                return Content.GetRawText();
        }
        catch
        {
            return string.Empty;
        }
    }
    
    // Helper method to set content from string
    public void SetContentFromString(string content)
    {
        try
        {
            // First try to parse as JSON to preserve structure
            Content = JsonSerializer.Deserialize<JsonElement>(content);
        }
        catch
        {
            // If not JSON, store as string
            Content = JsonSerializer.SerializeToElement(content);
        }
    }
    
    // Helper method to get content as JSON string for database storage
    public string GetContentAsJsonString()
    {
        try
        {
            if (Content.ValueKind == JsonValueKind.String)
            {
                // If it's already a string, we might need to serialize it as JSON
                var stringValue = Content.GetString() ?? string.Empty;
                return JsonSerializer.Serialize(stringValue);
            }
            else
            {
                // For objects or arrays, return the raw JSON
                return Content.GetRawText();
            }
        }
        catch
        {
            return JsonSerializer.Serialize(string.Empty);
        }
    }
    
    // Helper method to get citations as a list of strings (for backward compatibility)
    public List<string> GetCitationsAsStringList()
    {
        if (Citations == null || Citations.Value.ValueKind == JsonValueKind.Null)
            return new List<string>();
            
        try
        {
            if (Citations.Value.ValueKind == JsonValueKind.Array)
            {
                return Citations.Value.EnumerateArray()
                    .Select(x => x.ValueKind == JsonValueKind.String ? x.GetString() : x.GetRawText())
                    .Where(x => x != null)
                    .Cast<string>()
                    .ToList();
            }
            else if (Citations.Value.ValueKind == JsonValueKind.String)
            {
                return new List<string> { Citations.Value.GetString()! };
            }
            else
            {
                // For objects or other types, serialize to JSON string
                return new List<string> { Citations.Value.GetRawText() };
            }
        }
        catch
        {
            return new List<string>();
        }
    }
    
    // Helper method to get citations as JSON string for database storage
    public string GetCitationsAsJsonString()
    {
        if (Citations == null || Citations.Value.ValueKind == JsonValueKind.Null)
            return "";
            
        try
        {
            return Citations.Value.GetRawText();
        }
        catch
        {
            return "";
        }
    }
}

public class ConversationSummary
{
    [JsonPropertyName("conversation_id")] public string ConversationId { get; set; } = string.Empty;
    [JsonPropertyName("user_id")] public string UserId { get; set; } = string.Empty;
    [JsonPropertyName("title")] public string Title { get; set; } = string.Empty;
    [JsonPropertyName("created_at")] public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    [JsonPropertyName("updated_at")] public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
}

public class ConversationListResponse
{
    [JsonPropertyName("conversations")] public List<ConversationSummary> Conversations { get; set; } = new();
}

public class ConversationMessagesResponse
{
    [JsonPropertyName("messages")] public List<ChatMessage> Messages { get; set; } = new();
}

public class UpdateConversationRequest
{
    [JsonPropertyName("conversation_id")] public string ConversationId { get; set; } = string.Empty;
    [JsonPropertyName("title")] public string? Title { get; set; }
    [JsonPropertyName("messages")] public List<ChatMessage>? Messages { get; set; }
}

public class UpdateConversationResponse
{
    [JsonPropertyName("success")] public bool Success { get; set; }
}
