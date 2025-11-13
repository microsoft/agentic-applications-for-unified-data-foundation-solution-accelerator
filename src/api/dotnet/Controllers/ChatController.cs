using System.Text.Json;
using CsApi.Interfaces;
using CsApi.Models;
using CsApi.Services;
using CsApi.Repositories;
using CsApi.Utils;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Agents.AI;

namespace CsApi.Controllers;

[ApiController]
[Route("api")] // matches /api prefix
public class ChatController : ControllerBase
{
    private readonly IUserContextAccessor _userContextAccessor;
    private readonly ISqlConversationRepository _sqlRepo;
    
    // Thread cache to maintain conversation context like Python ExpCache  
    private static ExpCache<string, AgentThread>? _threadCache;

    public ChatController(IUserContextAccessor userContextAccessor, ISqlConversationRepository sqlRepo, IConfiguration configuration)
    { 
        _userContextAccessor = userContextAccessor; 
        _sqlRepo = sqlRepo;
        
        // Initialize thread cache with Azure AI endpoint if not already initialized
        if (_threadCache == null)
        {
            var endpoint = configuration["AZURE_AI_AGENT_ENDPOINT"] ?? string.Empty;
            _threadCache = new ExpCache<string, AgentThread>(maxSize: 1000, ttlSeconds: 3600.0, configuration, azureAIEndpoint: endpoint);
        }
    }

    /// <summary>
    /// Streaming chat endpoint. Uses Agent Framework ChatClientAgent with function tools.
    /// The response is streamed as JSON lines, matching the FastAPI /chat endpoint.
    /// Maintains conversation context using thread caching like Python backend.
    /// </summary>
    [HttpPost("chat")]
    public async Task Chat([FromBody] ChatRequest request, [FromServices] IAgentFrameworkService agentService, CancellationToken ct)
    {
        Response.ContentType = "application/json-lines";
        var query = request.Messages?.LastOrDefault()?.GetContentAsString();
        if (string.IsNullOrWhiteSpace(query))
        {
            await Response.WriteAsync(JsonSerializer.Serialize(new { error = "query is required" }) + "\n\n", ct);
            return;
        }
        
        var user = _userContextAccessor.GetCurrentUser();
        var userId = user.UserPrincipalId;
        
        var (convId, _) = await _sqlRepo.EnsureConversationAsync(userId ?? string.Empty, request.ConversationId, title: string.Empty, ct);
        
        // Use Agent Framework AIAgent for RAG/AI response with function tools  
        var agent = agentService.Agent;
        
        AgentThread? thread = null;
        if (_threadCache?.TryGet(convId, out var cachedThread) == true)
        {
            thread = cachedThread;
        }
        else
        {
           thread = agent.GetNewThread();
            _threadCache?.Set(convId, thread);
        }
        try
        {
            var messageContent = query;
            var acc = "";
            
            // Stream response from Agent Framework with thread context
            await foreach (var update in agent.RunStreamingAsync(messageContent, thread))
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
            // Stream error as JSON line
            var errorEnvelope = new { error = ex.Message };
            await Response.WriteAsync(JsonSerializer.Serialize(errorEnvelope) + "\n\n", ct);
        }
        
        // Note: Assistant response is NOT saved here during streaming
        // It will be saved later when the frontend calls the update endpoint
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

}
