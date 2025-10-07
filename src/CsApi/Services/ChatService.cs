using CsApi.Interfaces;
using CsApi.Models;
using System.Text;

namespace CsApi.Services;

public class ChatService : IChatService
{
    private readonly IChatRepository _repo;

    public ChatService(IChatRepository repo)
    {
        _repo = repo;
    }

    public async Task<Stream> StreamChatAsync(ChatRequest request, CancellationToken cancellationToken)
    {
        // Placeholder to mirror streaming from Python agent; returns a simple textual stream
        var ms = new MemoryStream();
        var writer = new StreamWriter(ms, Encoding.UTF8, leaveOpen: true);
        var message = new ChatMessage
        {
            Content = $"Echo: {request.Messages?.LastOrDefault()?.Content}",
            Role = "assistant",
            CreatedAt = DateTime.UtcNow
        };
        await _repo.SaveMessageAsync(request.ConversationId ?? "default", message, cancellationToken);
        await writer.WriteAsync(message.Content?.ToString());
        await writer.FlushAsync();
        ms.Position = 0;
        return ms;
    }
}
