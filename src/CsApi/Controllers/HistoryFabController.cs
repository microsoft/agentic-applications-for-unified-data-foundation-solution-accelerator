using CsApi.Models;
using CsApi.Repositories;
using Microsoft.AspNetCore.Mvc;

namespace CsApi.Controllers;

[ApiController]
[Route("historyfab")] // SQL-backed history endpoints
public class HistoryFabController : ControllerBase
{
    private readonly ISqlConversationRepository _repo;
    private readonly ILogger<HistoryFabController> _logger;

    public HistoryFabController(ISqlConversationRepository repo, ILogger<HistoryFabController> logger)
    { _repo = repo; _logger = logger; }

    private string GetUserId() => Request.Headers["x-ms-client-principal-id"].FirstOrDefault();

    [HttpGet("list")]
    public async Task<IActionResult> List([FromQuery] int offset = 0, [FromQuery] int limit = 25, [FromQuery(Name="sort")] string sort = "DESC", CancellationToken ct = default)
    {
        var user = GetUserId();
        var items = await _repo.ListAsync(user, offset, limit, sort, ct);
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
        var messages = await _repo.ReadAsync(user, id, sort, ct);
        if (messages.Count == 0) return NotFound(new { error = $"Conversation {id} not found" });
        return Ok(new { conversation_id = id, messages });
    }

    [HttpDelete("delete")]
    public async Task<IActionResult> Delete([FromQuery(Name="id")] string id, CancellationToken ct = default)
    {
        _logger.LogInformation($"[DEBUG] Entered Delete endpoint with id={id}");
        if (string.IsNullOrWhiteSpace(id)) return Problem(statusCode:400, title:"Bad Request", detail:"conversation_id is required");
        // TEMP: Test if controller is hit
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

    public sealed class UpdateRequest { public string Conversation_Id { get; set; } = string.Empty; public List<ChatMessage> Messages { get; set; } = new(); }
    [HttpPost("update")]
    public async Task<IActionResult> Update([FromBody] UpdateRequest req, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(req.Conversation_Id))
            return Problem(statusCode:400, title:"Bad Request", detail:"conversation_id is required");
        if (req.Messages == null || req.Messages.Count == 0)
            return Problem(statusCode:400, title:"Bad Request", detail:"messages are required");
        
        var user = GetUserId();
        
        try
        {
            // Ensure conversation exists and user has permission
            var convId = await _repo.EnsureConversationAsync(user, req.Conversation_Id, title:"", ct);
            
            // Add messages (store last user+assistant like Python logic)
            var messagesToStore = req.Messages.TakeLast(2).ToList();
            foreach (var message in messagesToStore)
            {
                if (string.IsNullOrEmpty(message.Id))
                    message.Id = Guid.NewGuid().ToString();
                await _repo.AddMessageAsync(user, convId, message, ct);
            }
            
            // Return detailed response like Python
            return Ok(new { 
                success = true, 
                conversation_id = convId,
                message = "Conversation updated successfully",
                messages_added = messagesToStore.Count,
                updatedAt = DateTime.UtcNow.ToString("o")
            });
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
