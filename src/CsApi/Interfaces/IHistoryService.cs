using CsApi.Models;

namespace CsApi.Interfaces;

public interface IHistoryService
{
    Task<ConversationListResponse> GetConversationsAsync(string userId, int limit, string sortOrder, int offset, CancellationToken ct);
    Task<ConversationMessagesResponse> GetConversationMessagesAsync(string userId, string conversationId, string sortOrder, CancellationToken ct);
    Task<bool> DeleteConversationAsync(string userId, string conversationId, CancellationToken ct);
    Task<bool> DeleteAllConversationsAsync(string userId, CancellationToken ct);
    Task<bool> RenameConversationAsync(string userId, string conversationId, string title, CancellationToken ct);
    Task<UpdateConversationResponse> UpdateConversationAsync(string userId, UpdateConversationRequest request, CancellationToken ct);
}

public interface IHistoryRepository
{
    Task<IReadOnlyList<ConversationSummary>> GetConversationsAsync(string userId, int limit, string sortOrder, int offset, CancellationToken ct);
    Task<IReadOnlyList<ChatMessage>> GetConversationMessagesAsync(string userId, string conversationId, string sortOrder, CancellationToken ct);
    Task<bool> DeleteConversationAsync(string userId, string conversationId, CancellationToken ct);
    Task<bool> DeleteAllConversationsAsync(string userId, CancellationToken ct);
    Task<bool> RenameConversationAsync(string userId, string conversationId, string title, CancellationToken ct);
    Task<bool> UpdateConversationAsync(string userId, UpdateConversationRequest request, CancellationToken ct);
}
