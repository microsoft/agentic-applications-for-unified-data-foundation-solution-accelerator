using CsApi.Models;

namespace CsApi.Interfaces;

public interface IChatService
{
    Task<Stream> StreamChatAsync(ChatRequest request, CancellationToken cancellationToken);
}

public interface IChatRepository
{
    // Placeholder for persistence implementation (thread cache / conversation store)
    Task SaveMessageAsync(string conversationId, ChatMessage message, CancellationToken ct);
    Task<IReadOnlyList<ChatMessage>> GetMessagesAsync(string conversationId, CancellationToken ct);
}
