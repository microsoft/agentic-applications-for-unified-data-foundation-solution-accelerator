using CsApi.Models;

namespace CsApi.Interfaces;

public interface ITitleGenerationService
{
    Task<string> GenerateTitleAsync(List<ChatMessage> messages, CancellationToken cancellationToken = default);
}