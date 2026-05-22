using CsApi.Interfaces;
using CsApi.Models;
using Microsoft.AspNetCore.Mvc;
using System.Text.Json.Serialization;

namespace CsApi.Controllers;

/// <summary>
/// History controller at /history — Cosmos DB only.
/// All routes use CosmosConversationClient (no SQL fallback).
/// </summary>
[ApiController]
[Route("history")]
public class HistoryController : ControllerBase
{
    private readonly IConversationRepository _cosmosRepo;
    private readonly ITitleGenerationService _titleService;
    private readonly ILogger<HistoryController> _logger;
    private readonly IUserContextAccessor _userContext;

    public HistoryController(
        IConversationRepository cosmosRepo,
        ITitleGenerationService titleService,
        ILogger<HistoryController> logger,
        IUserContextAccessor userContext)
    {
        _cosmosRepo = cosmosRepo;
        _titleService = titleService;
        _logger = logger;
        _userContext = userContext;
    }

    private string GetUserId()
    {
        var user = _userContext.GetCurrentUser();
        return user.UserPrincipalId ?? "";
    }

    // ─── GET /history/list ───────────────────────────────────────────────────────

    [HttpGet("list")]
    public async Task<IActionResult> List(
        [FromQuery] int offset = 0,
        [FromQuery] int limit = 25,
        [FromQuery(Name = "sort")] string sort = "DESC",
        CancellationToken ct = default)
    {
        try
        {
            var userId = GetUserId();
            _logger.LogInformation("user_id: {UserId}, offset: {Offset}, limit: {Limit}", userId, offset, limit);

            var conversations = await _cosmosRepo.GetConversationsAsync(userId, offset, limit, sort, ct);

            // Python returns empty list (200) when no conversations — never 404
            return Ok(conversations ?? new List<ConversationSummary>());
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Exception in /history/list");
            return Problem(statusCode: 500, detail: "An internal error has occurred!");
        }
    }

    // ─── GET /history/read ───────────────────────────────────────────────────────

    [HttpGet("read")]
    public async Task<IActionResult> Read(
        [FromQuery(Name = "id")] string id,
        CancellationToken ct = default)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(id))
                return Problem(statusCode: 400, detail: "conversation_id is required");

            var userId = GetUserId();

            var conversation = await _cosmosRepo.GetConversationAsync(userId, id, ct);
            if (conversation == null)
                return NotFound(new { error = $"Conversation {id} was not found. It either does not exist or the user does not have access to it." });

            var messages = await _cosmosRepo.GetMessagesAsync(userId, id, ct);

            // Format messages for response
            var formattedMessages = messages.Select(m => new
            {
                id = m.Id,
                role = m.Role,
                content = m.GetContentAsString(),
                createdAt = m.CreatedAt.ToString("o"),
                feedback = m.Feedback,
                citations = m.GetCitationsAsJsonString()
            }).ToList();

            return Ok(new { conversation_id = id, messages = formattedMessages });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Exception in /history/read");
            return Problem(statusCode: 500, detail: "An internal error has occurred!");
        }
    }

    // ─── POST /history/generate ──────────────────────────────────────────────────

    [HttpPost("generate")]
    public async Task<IActionResult> Generate([FromBody] GenerateRequest req, CancellationToken ct = default)
    {
        if (req == null)
            return Problem(statusCode: 400, detail: "Request body is required");

        try
        {
            var userId = GetUserId();
            var conversationId = req.ConversationId;
            var messages = req.Messages ?? new List<ChatMessage>();

            if (string.IsNullOrWhiteSpace(conversationId))
            {
                // Create new conversation with generated title
                var title = await GenerateTitle(messages, ct);
                var conversation = await _cosmosRepo.CreateConversationAsync(userId, null, title, ct);
                if (conversation == null)
                    return Problem(statusCode: 500, detail: "CosmosDB is not configured or unavailable");
                conversationId = conversation.ConversationId;
            }

            // Store user message (last user message)
            var userMsg = messages.LastOrDefault(m => m.Role == "user");
            if (userMsg == null)
                return Problem(statusCode: 400, detail: "No user message found");

            await _cosmosRepo.CreateMessageAsync(userId, conversationId, userMsg, ct);

            return Ok(true);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Exception in /history/generate");
            return Problem(statusCode: 500, detail: "An internal error has occurred!");
        }
    }

    // ─── POST /history/update ────────────────────────────────────────────────────

    [HttpPost("update")]
    public async Task<IActionResult> Update([FromBody] UpdateRequest req, CancellationToken ct = default)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(req?.ConversationId))
                return Problem(statusCode: 400, detail: "No conversation_id found");

            var userId = GetUserId();
            var conversationId = req.ConversationId;
            var messages = req.Messages ?? new List<ChatMessage>();

            // Ensure conversation exists (create if not)
            var conversation = await _cosmosRepo.GetConversationAsync(userId, conversationId, ct);
            if (conversation == null)
            {
                var title = await GenerateTitle(messages, ct);
                conversation = await _cosmosRepo.CreateConversationAsync(userId, conversationId, title, ct);
                if (conversation == null)
                    return Problem(statusCode: 500, detail: "Failed to create conversation");
            }

            // Store user message (last user message)
            var lastUser = messages.LastOrDefault(m => m.Role == "user");
            if (lastUser != null)
            {
                await _cosmosRepo.CreateMessageAsync(userId, conversationId, lastUser, ct);
            }

            // Store tool message if present before assistant (matches Python)
            if (messages.Count > 1 && messages[^1].Role is "assistant" or "error")
            {
                if (messages.Count >= 2 && messages[^2].Role == "tool")
                {
                    await _cosmosRepo.CreateMessageAsync(userId, conversationId, messages[^2], ct);
                }
                // Store assistant/error message
                await _cosmosRepo.CreateMessageAsync(userId, conversationId, messages[^1], ct);
            }
            else if (messages.Count > 0 && messages[^1].Role is "assistant" or "error")
            {
                await _cosmosRepo.CreateMessageAsync(userId, conversationId, messages[^1], ct);
            }

            // Return conversation info using in-memory object (matches Python — no re-fetch needed)
            return Ok(new
            {
                success = true,
                data = new
                {
                    title = conversation.Title,
                    date = conversation.UpdatedAt.ToString("o"),
                    conversation_id = conversationId
                }
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Exception in /history/update");
            return Problem(statusCode: 500, detail: "An internal error has occurred!");
        }
    }

    // ─── POST /history/message_feedback ──────────────────────────────────────────

    [HttpPost("message_feedback")]
    public async Task<IActionResult> MessageFeedback([FromBody] MessageFeedbackRequest req, CancellationToken ct = default)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(req?.MessageId))
                return Problem(statusCode: 400, detail: "message_id is required");
            if (string.IsNullOrWhiteSpace(req.MessageFeedback))
                return Problem(statusCode: 400, detail: "message_feedback is required");

            var userId = GetUserId();

            var updated = await _cosmosRepo.UpdateMessageFeedbackAsync(userId, req.MessageId, req.MessageFeedback, ct);
            if (!updated)
                return NotFound(new { error = $"Unable to update message {req.MessageId}. It either does not exist or the user does not have access to it." });

            return Ok(new { message = $"Successfully updated message with feedback {req.MessageFeedback}", message_id = req.MessageId });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Exception in /history/message_feedback");
            return Problem(statusCode: 500, detail: "An internal error has occurred!");
        }
    }

    // ─── DELETE /history/delete ───────────────────────────────────────────────────

    [HttpDelete("delete")]
    public async Task<IActionResult> Delete([FromQuery(Name = "id")] string id, CancellationToken ct = default)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(id))
                return Problem(statusCode: 400, detail: "conversation_id is required");

            var userId = GetUserId();

            var deleted = await _cosmosRepo.DeleteConversationAsync(userId, id, ct);
            if (!deleted)
                return NotFound(new { error = $"Conversation {id} not found or user does not have permission." });

            return Ok(new { message = "Successfully deleted conversation and messages", conversation_id = id });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Exception in /history/delete");
            return Problem(statusCode: 500, detail: "An internal error has occurred!");
        }
    }

    // ─── DELETE /history/delete_all ───────────────────────────────────────────────

    [HttpDelete("delete_all")]
    public async Task<IActionResult> DeleteAll(CancellationToken ct = default)
    {
        try
        {
            var userId = GetUserId();

            var conversations = await _cosmosRepo.GetConversationsAsync(userId, 0, 10000, "DESC", ct);
            if (conversations == null || conversations.Count == 0)
                return NotFound(new { error = $"No conversations for {userId} were found" });

            foreach (var conv in conversations)
            {
                await _cosmosRepo.DeleteConversationAsync(userId, conv.ConversationId, ct);
            }

            return Ok(new { message = $"Successfully deleted all conversations for user {userId}" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Exception in /history/delete_all");
            return Problem(statusCode: 500, detail: "An internal error has occurred!");
        }
    }

    // ─── POST /history/rename ────────────────────────────────────────────────────

    [HttpPost("rename")]
    public async Task<IActionResult> Rename([FromBody] RenameRequest req, CancellationToken ct = default)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(req?.ConversationId))
                return Problem(statusCode: 400, detail: "conversation_id is required");
            if (string.IsNullOrWhiteSpace(req.Title))
                return Problem(statusCode: 400, detail: "title is required");

            var userId = GetUserId();

            var conversation = await _cosmosRepo.GetConversationAsync(userId, req.ConversationId, ct);
            if (conversation == null)
                return NotFound(new { error = $"Conversation {req.ConversationId} was not found. It either does not exist or the logged-in user does not have access to it." });

            conversation.Title = req.Title;
            conversation.UpdatedAt = DateTime.UtcNow;
            var success = await _cosmosRepo.UpsertConversationAsync(userId, conversation, ct);
            if (!success)
                return Problem(statusCode: 500, detail: "Failed to rename conversation");

            return Ok(conversation);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Exception in /history/rename");
            return Problem(statusCode: 500, detail: "An internal error has occurred!");
        }
    }

    // ─── POST /history/clear ─────────────────────────────────────────────────────

    [HttpPost("clear")]
    public async Task<IActionResult> Clear([FromBody] ClearRequest req, CancellationToken ct = default)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(req?.ConversationId))
                return Problem(statusCode: 400, detail: "conversation_id is required");

            var userId = GetUserId();

            var conversation = await _cosmosRepo.GetConversationAsync(userId, req.ConversationId, ct);
            if (conversation == null)
                return NotFound(new { error = $"Conversation {req.ConversationId} not found." });

            var cleared = await _cosmosRepo.ClearMessagesAsync(userId, req.ConversationId, ct);
            if (!cleared)
                return Problem(statusCode: 500, detail: "Failed to clear messages");

            return Ok(new { message = $"Successfully cleared messages in conversation {req.ConversationId}" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Exception in /history/clear");
            return Problem(statusCode: 500, detail: "An internal error has occurred!");
        }
    }

    // ─── GET /history/ensure ─────────────────────────────────────────────────────

    [HttpGet("ensure")]
    public async Task<IActionResult> Ensure(CancellationToken ct = default)
    {
        try
        {
            var configured = await _cosmosRepo.EnsureConfiguredAsync();
            return Ok(new { configured });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Exception in /history/ensure");
            return Ok(new { configured = false, error = ex.Message });
        }
    }

    // ─── HELPERS ─────────────────────────────────────────────────────────────────

    private async Task<string> GenerateTitle(List<ChatMessage> messages, CancellationToken ct)
    {
        try
        {
            return await _titleService.GenerateTitleAsync(messages, ct);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to generate title, using fallback");
            return GenerateFallbackTitle(messages);
        }
    }

    private static string GenerateFallbackTitle(List<ChatMessage> messages)
    {
        var userMsg = messages.FirstOrDefault(m => m.Role == "user");
        if (userMsg != null)
        {
            var content = userMsg.GetContentAsString();
            var words = content.Split(' ', StringSplitOptions.RemoveEmptyEntries).Take(4);
            var title = string.Join(" ", words);
            return string.IsNullOrWhiteSpace(title) ? "New Conversation" : title;
        }
        return "New Conversation";
    }

    // ─── REQUEST MODELS ──────────────────────────────────────────────────────────

    public sealed class GenerateRequest
    {
        [JsonPropertyName("conversation_id")] public string? ConversationId { get; set; }
        [JsonPropertyName("messages")] public List<ChatMessage>? Messages { get; set; }
    }

    public sealed class UpdateRequest
    {
        [JsonPropertyName("conversation_id")] public string ConversationId { get; set; } = string.Empty;
        [JsonPropertyName("messages")] public List<ChatMessage> Messages { get; set; } = new();
    }

    public sealed class RenameRequest
    {
        [JsonPropertyName("conversation_id")] public string ConversationId { get; set; } = string.Empty;
        [JsonPropertyName("title")] public string Title { get; set; } = string.Empty;
    }

    public sealed class MessageFeedbackRequest
    {
        [JsonPropertyName("message_id")] public string MessageId { get; set; } = string.Empty;
        [JsonPropertyName("message_feedback")] public string MessageFeedback { get; set; } = string.Empty;
    }

    public sealed class ClearRequest
    {
        [JsonPropertyName("conversation_id")] public string ConversationId { get; set; } = string.Empty;
    }
}
