using System.Text.Json;
using CsApi.Interfaces;
using CsApi.Models;
using CsApi.Services;
using CsApi.Repositories;
using Microsoft.AspNetCore.Mvc;
using System.Collections.Concurrent;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace CsApi.Controllers;

[ApiController]
[Route("api")] // matches /api prefix
public class ChatController : ControllerBase
{
    // REDUNDANT: _chatService is never used - the controller uses AzureAIAgentOrchestrator directly
    // private readonly IChatService _chatService;
    private readonly IUserContextAccessor _userContextAccessor;
    private readonly ISqlConversationRepository _sqlRepo;

    public ChatController(IUserContextAccessor userContextAccessor, ISqlConversationRepository sqlRepo)
    { _userContextAccessor = userContextAccessor; _sqlRepo = sqlRepo; }

    /// <summary>
    /// Streaming chat endpoint. Uses Agent Framework ChatClientAgent with function tools.
    /// The response is streamed as JSON lines, matching the FastAPI /chat endpoint.
    /// Maintains conversation context using thread caching like Python backend.
    /// </summary>
    [HttpPost("chat")]
    public async Task Chat([FromBody] ChatRequest request, [FromServices] IAgentFrameworkService agentService, CancellationToken ct)
    {
        Response.ContentType = "application/json-lines";
        // REDUNDANT: Excessive console logging can be reduced in production
        // Console.WriteLine("Processing chat request...");
        // Console.WriteLine("Request Body: " + JsonSerializer.Serialize(request));
        var query = request.Messages?.LastOrDefault()?.GetContentAsString();
        if (string.IsNullOrWhiteSpace(query))
        {
            await Response.WriteAsync(JsonSerializer.Serialize(new { error = "query is required" }) + "\n\n", ct);
            return;
        }
        Console.WriteLine($"Received chat request: {query}"); // Keep this for basic logging
        
        var user = _userContextAccessor.GetCurrentUser();
        var userId = user.UserPrincipalId;
        
        //if (string.IsNullOrWhiteSpace(userId))
        //{
        //    await Response.WriteAsync(JsonSerializer.Serialize(new { error = "Missing user id header" }) + "\n\n", ct);
        //    return;
        //}
        var (convId, _) = await _sqlRepo.EnsureConversationAsync(userId ?? string.Empty, request.ConversationId, title: string.Empty, ct);
        
        // Use Agent Framework AIAgent for RAG/AI response with function tools  
        var agent = agentService.Agent;
        
        try
        {
            var messageContent = query;
            var acc = "";
            
            // Stream response from Agent Framework with thread context
            await foreach (var update in agent.RunStreamingAsync(messageContent))
            {
                // Agent Framework returns string updates directly
                var content = update?.ToString() ?? string.Empty;
                acc += content;
                
                if (!string.IsNullOrEmpty(content))
                {
                    var envelope = new
                    {
                        id = convId,
                        model = "rag-model",
                        created = DateTimeOffset.UtcNow.ToUnixTimeSeconds(),
                        @object = "extensions.chat.completion.chunk",
                        choices = new[] { new { messages = new[] { new { role = "assistant", content = acc } } } }
                    };
                    await Response.WriteAsync(JsonSerializer.Serialize(envelope) + "\n\n", ct);
                    await Response.Body.FlushAsync(ct);
                }
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error during agent invocation: {ex.Message}");
            
            // Stream error as JSON line
            var errorEnvelope = new { error = ex.Message };
            await Response.WriteAsync(JsonSerializer.Serialize(errorEnvelope) + "\n\n", ct);
        }
        
        // Note: Assistant response is NOT saved here during streaming
        // It will be saved later when the frontend calls the update endpoint
    }





    /// <summary>
    /// Helper method to clear thread cache for a specific conversation (useful for testing)
    /// </summary>
    // [HttpPost("clear-thread-cache")]
    // public async Task<IActionResult> ClearThreadCache([FromBody] ClearThreadCacheRequest request)
    // {
    //     if (!string.IsNullOrEmpty(request.ConversationId))
    //     {
    //         if (_threadCache.TryGet(request.ConversationId, out var thread))
    //         {
    //             _threadCache.Remove(request.ConversationId);
                
    //             // Clean up thread like your example: if (thread is ChatClientAgentThread chatThread)
    //             // Note: Thread cleanup implementation may depend on specific AgentThread type
    //             // For now, just remove from cache
    //             Console.WriteLine($"Manually cleared thread cache for conversation {request.ConversationId}");
    //             return Ok(new { message = $"Thread cache cleared for conversation {request.ConversationId}" });
    //         }
    //         return NotFound(new { message = $"No cached thread found for conversation {request.ConversationId}" });
    //     }
        
    //     var clearedCount = _threadCache.Count;
    //     _threadCache.Clear();
    //     Console.WriteLine($"Manually cleared all {clearedCount} threads from cache");
    //     return Ok(new { message = $"Cleared {clearedCount} threads from cache" });
    // }

    public class ClearThreadCacheRequest 
    { 
        public string? ConversationId { get; set; } 
    }


    [HttpGet("layout-config")]
    public IActionResult LayoutConfig([FromServices] IConfiguration config)
    {
        var layoutConfigStr = config["REACT_APP_LAYOUT_CONFIG"] ?? string.Empty;
        if (!string.IsNullOrWhiteSpace(layoutConfigStr))
        {
            try
            {
                using var doc = JsonDocument.Parse(layoutConfigStr);
                return new JsonResult(doc.RootElement.Clone());
            }
            catch (JsonException)
            {
                return BadRequest(new { error = "Invalid layout configuration format." });
            }
        }
        return BadRequest(new { error = "Layout config not found in environment variables" });
    }

    [HttpGet("display-chart-default")]
    public IActionResult DisplayChartDefault([FromServices] IConfiguration config)
    {
        var val = config["DISPLAY_CHART_DEFAULT"] ?? string.Empty;
        if (!string.IsNullOrWhiteSpace(val))
        {
            return new JsonResult(new { isChartDisplayDefault = val });
        }
        return BadRequest(new { error = "DISPLAY_CHART_DEFAULT flag not found in environment variables" });
    }

    [HttpPost("fetch-azure-search-content")]
    public async Task<IActionResult> FetchAzureSearchContent([FromBody] FetchAzureSearchContentRequest req)
    {
        if (string.IsNullOrWhiteSpace(req?.Url))
            return BadRequest(new { error = "URL is required" });
        try
        {
            using var httpClient = new HttpClient();
            var requestMsg = new HttpRequestMessage(HttpMethod.Get, req.Url);
            requestMsg.Headers.Add("Content-Type", "application/json");
            var response = await httpClient.SendAsync(requestMsg);
            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync();
                return Ok(new { content = json });
            }
            return StatusCode((int)response.StatusCode, new { error = $"Error: HTTP {response.StatusCode}" });
        }
        catch (Exception)
        {
            return StatusCode(500, new { error = "Internal server error" });
        }
    }

    public class FetchAzureSearchContentRequest { public string? Url { get; set; } }
}
