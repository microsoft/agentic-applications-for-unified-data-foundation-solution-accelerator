using System.Text.Json.Serialization;

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
    [JsonPropertyName("content")] public string Content { get; set; } = string.Empty;
    [JsonPropertyName("created_at")] public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    [JsonPropertyName("citations")] public List<string> Citations { get; set; } = new();
    [JsonPropertyName("feedback")] public string Feedback { get; set; } = string.Empty;
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
