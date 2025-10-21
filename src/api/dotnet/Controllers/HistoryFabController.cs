using CsApi.Models;
using CsApi.Repositories;
using CsApi.Interfaces;
using Microsoft.AspNetCore.Mvc;
using System.Text.Json.Serialization;
using System.Text.Json;

namespace CsApi.Controllers;

[ApiController]
[Route("historyfab")] // SQL-backed history endpoints
public class HistoryFabController : ControllerBase
{
    private readonly ISqlConversationRepository _repo;
    private readonly ITitleGenerationService _titleService;
    private readonly ILogger<HistoryFabController> _logger;
    private readonly IUserContextAccessor _userContext;

    public HistoryFabController(ISqlConversationRepository repo, ITitleGenerationService titleService, ILogger<HistoryFabController> logger, IUserContextAccessor userContext)
    { 
        _repo = repo; 
        _titleService = titleService;
        _logger = logger;
        _userContext = userContext;
    }

    private string? GetUserId() 
    {
        var user = _userContext.GetCurrentUser();
        var userId = user.UserPrincipalId;
        _logger.LogInformation("GetUserId returned: '{UserId}' (from user context)", userId ?? "NULL");
        return userId;
    }
    
    private static bool NeedsTitle(ConversationSummary? conversation)
    {
        if (conversation == null) return true;
        
        // Check if title is null, empty, or the default "New Conversation"
        return string.IsNullOrWhiteSpace(conversation.Title) || 
               conversation.Title.Equals("New Conversation", StringComparison.OrdinalIgnoreCase);
    }

    private static bool ShouldUpdateTitle(ConversationSummary? conversation, List<ChatMessage> messages)
    {
        if (conversation == null) return true;
        
        // Always update if no title or default title
        if (NeedsTitle(conversation)) return true;
        
        // Count user messages to see if conversation has evolved
        var userMessages = messages.Where(m => m.Role == "user").ToList();
        
        // If there are multiple user messages, check if we should update based on content
        if (userMessages.Count >= 2)
        {
            var latestMessage = userMessages.LastOrDefault()?.GetContentAsString()?.ToLowerInvariant() ?? "";
            
            // Check if the latest message contains substantive data analysis terms
            var dataAnalysisTerms = new[] { 
                "revenue", "sales", "chart", "graph", "report", "data", "analysis", "show", "display", 
                "total", "sum", "count", "average", "trend", "year", "month", "dashboard", "metric",
                "line chart", "bar chart", "pie chart", "table", "list", "breakdown", "summary"
            };
            
            // If latest message is about data analysis, always update the title to reflect it
            if (dataAnalysisTerms.Any(term => latestMessage.Contains(term)))
            {
                return true;
            }
        }
        
        return false;
    }

    [HttpGet("list")]
    public async Task<IActionResult> List([FromQuery] int offset = 0, [FromQuery] int limit = 25, [FromQuery(Name="sort")] string sort = "DESC", CancellationToken ct = default)
    {
        var user = GetUserId();
        _logger.LogInformation("List endpoint called for user: {UserId}, offset: {Offset}, limit: {Limit}", user, offset, limit);
        var items = await _repo.ListAsync(user, offset, limit, sort, ct);
        _logger.LogInformation("Retrieved {Count} conversations for user: {UserId}", items.Count, user);
        
        // Return conversations directly as array (matches Python behavior)
        return Ok(items);
    }

    [HttpGet("read")]
    public async Task<IActionResult> Read(
        [FromQuery(Name="id")] string id,
        [FromQuery] string sort = "ASC",
        CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(id))
            return Problem(statusCode:400, title:"Bad Request", detail:"conversation_id or id is required");
        var user = GetUserId();
        _logger.LogInformation("Read endpoint called for user: {UserId}, conversation_id: {ConversationId}", user, id);
        var allMessages = await _repo.ReadAsync(user, id, sort, ct);
        _logger.LogInformation("Retrieved {Count} raw messages for conversation: {ConversationId}", allMessages.Count, id);
        if (allMessages.Count == 0) return NotFound(new { error = $"Conversation {id} not found" });
        
        // Filter messages to show only complete question-answer pairs
        var finalMessages = new List<ChatMessage>();
        
        // First, remove messages with empty or null content
        var validMessages = allMessages.Where(m => !string.IsNullOrWhiteSpace(m.GetContentAsString())).ToList();
        
        // Group messages by conversation flow and identify complete pairs
        var processedMessages = new HashSet<string>(); // Track processed message IDs
        
        for (int i = 0; i < validMessages.Count; i++)
        {
            var currentMessage = validMessages[i];
            
            // Skip if already processed
            if (processedMessages.Contains(currentMessage.Id))
                continue;
            
            if (currentMessage.Role == "user")
            {
                // Look for the IMMEDIATE next assistant message (not just any assistant message)
                ChatMessage? pairedAssistant = null;
                
                // Check the next few messages for an assistant response
                for (int j = i + 1; j < validMessages.Count; j++)
                {
                    var nextMessage = validMessages[j];
                    
                    if (nextMessage.Role == "assistant")
                    {
                        pairedAssistant = nextMessage;
                        break;
                    }
                    // If we encounter another user message before finding an assistant, stop looking
                    if (nextMessage.Role == "user")
                    {
                        break;
                    }
                }
                
                // Only add the user message if it has a paired assistant response
                if (pairedAssistant != null)
                {
                    finalMessages.Add(currentMessage);
                    finalMessages.Add(pairedAssistant);
                    
                    // Mark both messages as processed
                    processedMessages.Add(currentMessage.Id);
                    processedMessages.Add(pairedAssistant.Id);
                }
                // Otherwise, skip this orphaned user message
            }
            else if (currentMessage.Role == "assistant")
            {
                // Standalone assistant messages (edge case) - only add if not already processed
                if (!processedMessages.Contains(currentMessage.Id))
                {
                    finalMessages.Add(currentMessage);
                    processedMessages.Add(currentMessage.Id);
                }
            }
            // Handle other roles (tool, system, etc.) by adding them as-is
            else if (currentMessage.Role != "user" && currentMessage.Role != "assistant")
            {
                finalMessages.Add(currentMessage);
                processedMessages.Add(currentMessage.Id);
            }
        }
        
        _logger.LogInformation("Filtered to {Count} final messages for conversation: {ConversationId}", finalMessages.Count, id);
        return Ok(new { conversation_id = id, messages = finalMessages });
    }

    [HttpDelete("delete")]
    public async Task<IActionResult> Delete([FromQuery(Name="id")] string id, CancellationToken ct = default)
    {
        // _logger.LogInformation($"[DEBUG] Entered Delete endpoint with id={id}"); // Debug logging removed
        if (string.IsNullOrWhiteSpace(id)) return Problem(statusCode:400, title:"Bad Request", detail:"conversation_id is required");
        // REDUNDANT: Test debug return commented out
        // return Ok(new { debug = "Delete endpoint reached", id });
        var user = GetUserId();
        var result = await _repo.DeleteAsync(user, id, ct);
        if (result == null)
            return NotFound(new { error = $"Conversation {id} not found" });
        if (result == false)
            return Forbid();
        return Ok(new { message = "Successfully deleted conversation and messages", conversation_id = id });
    }

    [HttpDelete("delete_all")]
    public async Task<IActionResult> DeleteAll(CancellationToken ct = default)
    {
        var user = GetUserId();
        var count = await _repo.DeleteAllAsync(user, ct);
        
        if (count == null)
            return Problem(statusCode: 500, title: "Internal Server Error", detail: "Failed to delete conversations");
        
        if (!string.IsNullOrEmpty(user))
            return Ok(new { message = $"Deleted all conversations for user {user}", affected = count });
        else
            return Ok(new { message = "Deleted all conversations for all users (admin operation)", affected = count });
    }

    public sealed class RenameRequest { public string Conversation_Id { get; set; } = string.Empty; public string Title { get; set; } = string.Empty; }
    [HttpPost("rename")]
    public async Task<IActionResult> Rename([FromBody] RenameRequest req, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(req.Conversation_Id) || string.IsNullOrWhiteSpace(req.Title))
            return Problem(statusCode:400, title:"Bad Request", detail:"conversation_id and title are required");
        var user = GetUserId();
        var result = await _repo.RenameAsync(user, req.Conversation_Id, req.Title, ct);
        if (result == null)
            return NotFound(new { error = "Conversation not found" });
        if (result == false)
            return Forbid();
        return Ok(new { message = $"Renamed conversation {req.Conversation_Id}" });
    }

    public sealed class UpdateRequest 
    { 
        [JsonPropertyName("conversation_id")]
        public string Conversation_Id { get; set; } = string.Empty; 
        
        [JsonPropertyName("messages")]
        public List<ChatMessage> Messages { get; set; } = new(); 
    }
    
    [HttpPost("update")]
    public async Task<IActionResult> Update([FromBody] UpdateRequest req, CancellationToken ct = default)
    {
        if (req == null)
            return Problem(statusCode:400, title:"Bad Request", detail:"req field is required");
        if (string.IsNullOrWhiteSpace(req.Conversation_Id))
            return Problem(statusCode:400, title:"Bad Request", detail:"conversation_id is required");
        if (req.Messages == null || req.Messages.Count == 0)
            return Problem(statusCode:400, title:"Bad Request", detail:"messages are required");
        
        var user = GetUserId();
        
        try
        {
            _logger.LogInformation("UPDATE ENDPOINT CALLED - ConversationId: {ConversationId}, MessageCount: {MessageCount}", 
                req.Conversation_Id, req.Messages?.Count ?? 0);
            
            // Ensure conversation exists and user has permission
            var (convId, isNewConversation) = await _repo.EnsureConversationAsync(user, req.Conversation_Id, title:"", ct);
            
            _logger.LogInformation(" Conversation Status - ID: {ConversationId}, IsNew: {IsNew}, OriginalId: {OriginalId}", 
                convId, isNewConversation, req.Conversation_Id);
            
            // Get conversation details early to check if it needs a title
            var conversations = await _repo.ListAsync(user, 0, 1000, "DESC", ct);
            var updatedConversation = conversations.FirstOrDefault(c => c.ConversationId == convId);
            
            if (updatedConversation == null)
            {
                _logger.LogError("Could not find conversation {ConversationId} after ensure", convId);
                return Problem(statusCode:500, title:"Internal Server Error", detail:"Failed to retrieve conversation");
            }
            
            // Generate title for new conversations OR existing conversations that should be updated
            if ((isNewConversation || ShouldUpdateTitle(updatedConversation, req.Messages)) && req.Messages.Count > 0)
            {
                try
                {
                    if (isNewConversation)
                    {
                        _logger.LogInformation(" NEW CONVERSATION DETECTED! Generating title for conversation {ConversationId} with {MessageCount} messages", 
                            convId, req.Messages.Count);
                    }
                    else if (NeedsTitle(updatedConversation))
                    {
                        _logger.LogInformation(" EXISTING CONVERSATION with default title! Generating title for conversation {ConversationId} with {MessageCount} messages", 
                            convId, req.Messages.Count);
                    }
                    else
                    {
                        _logger.LogInformation(" UPDATING TITLE for substantive query! Old title: '{OldTitle}', conversation {ConversationId} with {MessageCount} messages", 
                            updatedConversation.Title, convId, req.Messages.Count);
                    }
                    
                    // Log the messages being sent for title generation (focus on latest message)
                    var latestUserMessage = req.Messages.Where(m => m.Role == "user").LastOrDefault();
                    if (latestUserMessage != null)
                    {
                        var content = latestUserMessage.GetContentAsString();
                        _logger.LogInformation(" Latest message for title generation: '{Content}'", 
                            content?.Substring(0, Math.Min(100, content?.Length ?? 0)) ?? "EMPTY");
                    }
                    
                    var generatedTitle = await _titleService.GenerateTitleAsync(req.Messages, ct);
                    _logger.LogInformation(" Generated title: '{Title}' for conversation {ConversationId}", 
                        generatedTitle, convId);
                    await _repo.UpdateConversationTitleAsync(user, convId, generatedTitle, ct);
                    _logger.LogInformation(" Title updated in database for conversation {ConversationId}", convId);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, " Failed to generate title for conversation {ConversationId}", convId);
                    await _repo.UpdateConversationTitleAsync(user, convId, "New Conversation", ct);
                }
            }
            else
            {
                if (!isNewConversation)
                {
                    _logger.LogInformation(" EXISTING CONVERSATION with proper title - No title generation needed for {ConversationId}", convId);
                }
                else
                {
                    _logger.LogWarning(" NEW CONVERSATION but no messages - Cannot generate title for {ConversationId}", convId);
                }
            }
            
            _logger.LogInformation("Update endpoint - ConversationId: {ConversationId}, IsNew: {IsNew}", 
                convId, isNewConversation);
            
            // Add messages (store last user+assistant like Python logic)
            // But first check if they already exist to avoid duplicates
            var messagesToStore = req.Messages.TakeLast(2).ToList();
            var existingMessages = await _repo.ReadAsync(user, convId, "ASC", ct);
            var existingMessageIds = existingMessages.Select(m => m.Id).ToHashSet();
            
            int newMessagesAdded = 0;
            foreach (var message in messagesToStore)
            {
                if (string.IsNullOrEmpty(message.Id))
                    message.Id = Guid.NewGuid().ToString();
                    
                // Only add if this message doesn't already exist
                if (!existingMessageIds.Contains(message.Id))
                {
                    await _repo.AddMessageAsync(user, convId, message, ct);
                    newMessagesAdded++;
                }
            }
            
            // Get the final conversation details from database (refresh after potential title update)
            conversations = await _repo.ListAsync(user, 0, 1000, "DESC", ct);
            updatedConversation = conversations.FirstOrDefault(c => c.ConversationId == convId);
            
            if (updatedConversation == null)
            {
                _logger.LogError(" Could not find updated conversation {ConversationId}", convId);
                return Problem(statusCode:500, title:"Internal Server Error", detail:"Failed to retrieve updated conversation");
            }

            _logger.LogInformation(" Final conversation data - ID: {ConversationId}, Title: '{Title}', UpdatedAt: {UpdatedAt}", 
                updatedConversation.ConversationId, updatedConversation.Title, updatedConversation.UpdatedAt);

            // Return detailed response matching Python format exactly
            var response = new { 
                success = true,
                data = new {
                    title = updatedConversation.Title ?? "New Conversation",
                    date = updatedConversation.UpdatedAt.ToString("yyyy-MM-ddTHH:mm:ss.ffffff"),
                    conversation_id = updatedConversation.ConversationId
                }
            };
            
            _logger.LogInformation(" RESPONSE BEING SENT: {Response}", JsonSerializer.Serialize(response));
            return Ok(response);
        }
        catch (UnauthorizedAccessException)
        {
            return Forbid();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error updating conversation {ConversationId}", req.Conversation_Id);
            return Problem(statusCode:500, title:"Internal Server Error", detail:"Failed to update conversation");
        }
    }
}
