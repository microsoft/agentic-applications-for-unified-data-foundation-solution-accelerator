using CsApi.Models;
using CsApi.Interfaces;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Generic;

namespace CsApi.Repositories
{
    public class HistoryRepository : IHistoryRepository
    {
        public Task<IReadOnlyList<ConversationSummary>> GetConversationsAsync(string userId, int limit, string sortOrder, int offset, CancellationToken ct) => Task.FromResult((IReadOnlyList<ConversationSummary>)new List<ConversationSummary>());
        public Task<IReadOnlyList<ChatMessage>> GetConversationMessagesAsync(string userId, string conversationId, string sortOrder, CancellationToken ct) => Task.FromResult((IReadOnlyList<ChatMessage>)new List<ChatMessage>());
        public Task<bool> DeleteConversationAsync(string userId, string conversationId, CancellationToken ct) => Task.FromResult(true);
        public Task<bool> DeleteAllConversationsAsync(string userId, CancellationToken ct) => Task.FromResult(true);
        public Task<bool> RenameConversationAsync(string userId, string conversationId, string title, CancellationToken ct) => Task.FromResult(true);
        public Task<bool> UpdateConversationAsync(string userId, UpdateConversationRequest request, CancellationToken ct) => Task.FromResult(true);
    }
}
