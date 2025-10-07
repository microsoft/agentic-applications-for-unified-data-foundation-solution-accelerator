using CsApi.Interfaces;
using CsApi.Models;

namespace CsApi.Repositories;

public class ChatRepository : IChatRepository
{
    private static readonly Dictionary<string, List<ChatMessage>> _store = new();
    private static readonly object _lock = new();

    public Task SaveMessageAsync(string conversationId, ChatMessage message, CancellationToken ct)
    {
        lock (_lock)
        {
            if (!_store.TryGetValue(conversationId, out var list))
            {
                list = new List<ChatMessage>();
                _store[conversationId] = list;
            }
            list.Add(message);
        }
        return Task.CompletedTask;
    }

    public Task<IReadOnlyList<ChatMessage>> GetMessagesAsync(string conversationId, CancellationToken ct)
    {
        lock (_lock)
        {
            if (_store.TryGetValue(conversationId, out var list))
            {
                return Task.FromResult((IReadOnlyList<ChatMessage>)list.ToList());
            }
            return Task.FromResult((IReadOnlyList<ChatMessage>)Array.Empty<ChatMessage>());
        }
    }
}
