using CsApi.Models;

namespace CsApi.Interfaces;

/// <summary>
/// Common interface for conversation history storage (Cosmos DB or SQL).
/// </summary>
public interface IConversationRepository
{
    Task<ConversationSummary?> CreateConversationAsync(string userId, string? conversationId, string title, CancellationToken ct);
    Task<ConversationSummary?> GetConversationAsync(string userId, string conversationId, CancellationToken ct);
    Task<IReadOnlyList<ConversationSummary>> GetConversationsAsync(string userId, int offset, int limit, string sortOrder, CancellationToken ct);
    Task<bool> UpsertConversationAsync(ConversationSummary conversation, CancellationToken ct);
    Task CreateMessageAsync(string userId, string conversationId, ChatMessage message, CancellationToken ct);
    Task<IReadOnlyList<ChatMessage>> GetMessagesAsync(string userId, string conversationId, CancellationToken ct);
    Task<bool> UpdateMessageFeedbackAsync(string userId, string messageId, string feedback, CancellationToken ct);
    Task<bool> DeleteConversationAsync(string userId, string conversationId, CancellationToken ct);
    Task<bool> DeleteAllConversationsAsync(string userId, CancellationToken ct);
    Task<bool> ClearMessagesAsync(string userId, string conversationId, CancellationToken ct);
    Task<bool> EnsureConfiguredAsync();
}
