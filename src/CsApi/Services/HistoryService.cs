using CsApi.Models;
using CsApi.Interfaces;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Generic;

namespace CsApi.Services
{
    public class HistoryService : IHistoryService
    {
        public Task<ConversationListResponse> GetConversationsAsync(string userId, int limit, string sortOrder, int offset, CancellationToken ct) => Task.FromResult(new ConversationListResponse());
        public Task<ConversationMessagesResponse> GetConversationMessagesAsync(string userId, string conversationId, string sortOrder, CancellationToken ct) => Task.FromResult(new ConversationMessagesResponse());
        public Task<bool> DeleteConversationAsync(string userId, string conversationId, CancellationToken ct) => Task.FromResult(true);
        public Task<bool> DeleteAllConversationsAsync(string userId, CancellationToken ct) => Task.FromResult(true);
        public Task<bool> RenameConversationAsync(string userId, string conversationId, string title, CancellationToken ct) => Task.FromResult(true);
        public Task<UpdateConversationResponse> UpdateConversationAsync(string userId, UpdateConversationRequest request, CancellationToken ct) => Task.FromResult(new UpdateConversationResponse { Success = true });
    }
}
