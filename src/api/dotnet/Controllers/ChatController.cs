using Azure.AI.Projects;
using Azure.AI.Projects.OpenAI;
using CsApi.Auth;
using CsApi.Interfaces;
using CsApi.Models;
using CsApi.Repositories;
using CsApi.Services;
using CsApi.Utils;
using Microsoft.Agents.AI;
using Microsoft.AspNetCore.Mvc;
using System.Text.Json;
using Azure;

namespace CsApi.Controllers;

[ApiController]
[Route("api")] // matches /api prefix
public class ChatController : ControllerBase
{
    private readonly IUserContextAccessor _userContextAccessor;
    private readonly ISqlConversationRepository _sqlRepo;
    private readonly IConfiguration _configuration;

    // Thread cache to maintain conversation context like Python ExpCache  
    private static ExpCache<string, AgentThread>? _threadCache;

    public ChatController(IUserContextAccessor userContextAccessor, ISqlConversationRepository sqlRepo, IConfiguration configuration)
    { 
        _userContextAccessor = userContextAccessor; 
        _sqlRepo = sqlRepo;
        _configuration = configuration;
        
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
        
        if (string.IsNullOrWhiteSpace(request.Query))
        {
            await Response.WriteAsync(JsonSerializer.Serialize(new { error = "query is required" }) + "\n\n", ct);
            return;
        }
        
        var user = _userContextAccessor.GetCurrentUser();
        var userId = user.UserPrincipalId;
        
        var (convId, _) = await _sqlRepo.EnsureConversationAsync(userId ?? string.Empty, request.ConversationId, title: string.Empty, ct);
        
        // Use Agent Framework AIAgent for RAG/AI response with function tools  
        AIAgent agent = agentService.Agent;

        AgentThread? thread = null;
        if (_threadCache?.TryGet(convId, out var cachedThread) == true)
        {
            thread = cachedThread;
        }
        else
        {
            var chatClientAgent = agent as ChatClientAgent 
                ?? throw new InvalidOperationException("Agent must be a ChatClientAgent to create conversation threads.");
            
            var endpoint = _configuration["AZURE_AI_AGENT_ENDPOINT"] 
                ?? throw new InvalidOperationException("AZURE_AI_AGENT_ENDPOINT is not configured.");
            
            var credentialFactory = new AzureCredentialFactory(_configuration);
            var credential = credentialFactory.Create();
            var projectClient = new AIProjectClient(new Uri(endpoint), credential);

            ProjectConversation conversationResponse = await projectClient
                .GetProjectOpenAIClient()
                .GetProjectConversationsClient()
                .CreateProjectConversationAsync()
                .ConfigureAwait(false);

            thread = chatClientAgent.GetNewThread(conversationResponse.Id);
            _threadCache?.Set(convId, thread);
        }

        try
        {
            var accumulatedResponse = new System.Text.StringBuilder();
            
            await foreach (var update in agent.RunStreamingAsync(request.Query, thread).WithCancellation(ct))
            {
                var content = update?.ToString();
                if (string.IsNullOrEmpty(content)) continue;
                
                accumulatedResponse.Append(content);
                
                var envelope = new
                {
                    choices = new[] { new { messages = new[] { new { role = "assistant", content = accumulatedResponse.ToString() } } } }
                };
                await Response.WriteAsync(JsonSerializer.Serialize(envelope) + "\n\n", ct);
                await Response.Body.FlushAsync(ct);
            }
        }
        catch (RequestFailedException ex)
        {
            var errorEnvelope = new { error = ex.Message };
            await Response.WriteAsync(JsonSerializer.Serialize(errorEnvelope) + "\n\n", ct);
        }
        catch (Exception ex)
        {
            var errorEnvelope = new { error = ex.Message };
            await Response.WriteAsync(JsonSerializer.Serialize(errorEnvelope) + "\n\n", ct);
        }
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
