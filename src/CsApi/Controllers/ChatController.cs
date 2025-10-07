using System.Text.Json;
using CsApi.Interfaces;
using CsApi.Models;
using CsApi.Services;
using CsApi.Repositories;
using Microsoft.AspNetCore.Mvc;

namespace CsApi.Controllers;

[ApiController]
[Route("api")] // matches /api prefix
public class ChatController : ControllerBase
{
    private readonly IChatService _chatService;
    private readonly IUserContextAccessor _userContextAccessor;
    private readonly ISqlConversationRepository _sqlRepo;

    public ChatController(IChatService chatService, IUserContextAccessor userContextAccessor, ISqlConversationRepository sqlRepo)
    { _chatService = chatService; _userContextAccessor = userContextAccessor; _sqlRepo = sqlRepo; }

    /// <summary>
    /// Streaming chat endpoint. Invokes the AzureAIAgent with plugin support (e.g., ChatWithDataPlugin).
    /// If the LLM determines a function call is needed (e.g., SQL or chart), it will call the plugin automatically.
    /// The response is streamed as JSON lines, matching the FastAPI /chat endpoint.
    /// </summary>
    [HttpPost("chat")]
    public async Task Chat([FromBody] ChatRequest request, [FromServices] AzureAIAgentOrchestrator orchestrator, CancellationToken ct)
    {
        Response.ContentType = "application/json-lines";
        Console.WriteLine("Processing chat request...");
        Console.WriteLine("Request Body: " + JsonSerializer.Serialize(request));
        var query = request.Messages?.LastOrDefault()?.Content;
        if (string.IsNullOrWhiteSpace(query))
        {
            await Response.WriteAsync(JsonSerializer.Serialize(new { error = "query is required" }) + "\n\n", ct);
            return;
        }
        Console.WriteLine($"Received chat request: {query}");
        var userId = Request.Headers["x-ms-client-principal-id"].FirstOrDefault();
        //if (string.IsNullOrWhiteSpace(userId))
        //{
        //    await Response.WriteAsync(JsonSerializer.Serialize(new { error = "Missing user id header" }) + "\n\n", ct);
        //    return;
        //}
        var convId = await _sqlRepo.EnsureConversationAsync(userId, request.ConversationId, title: string.Empty, ct);
        var userMessage = new ChatMessage { Id = Guid.NewGuid().ToString(), Role = "user", Content = query, CreatedAt = DateTime.UtcNow };
        await _sqlRepo.AddMessageAsync(userId, convId, userMessage, ct);

        // Use orchestrator agent for RAG/AI response with plugin support
        var agent = orchestrator.Agent;
        var thread = new Microsoft.SemanticKernel.Agents.AzureAI.AzureAIAgentThread(agent.Client);
        var message = new Microsoft.SemanticKernel.ChatMessageContent(Microsoft.SemanticKernel.ChatCompletion.AuthorRole.User, query);
        var acc = "";
        try
        {
            await foreach (var response in agent.InvokeStreamingAsync(message, thread))
            {   
                // If the LLM chooses to call a plugin function (e.g., ChatWithSQLDatabase),
                // the plugin will be invoked automatically and the result included in the stream.
                // Extract the actual content from the streaming response (using .Message.Content)
                var content = (response?.Message as Microsoft.SemanticKernel.StreamingChatMessageContent)?.Content ?? string.Empty;
                acc += content;
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
        catch (Exception ex)
        {
            // Stream error as JSON line
            var errorEnvelope = new { error = ex.Message };
            await Response.WriteAsync(JsonSerializer.Serialize(errorEnvelope) + "\n\n", ct);
        }
        var assistant = new ChatMessage { Id = Guid.NewGuid().ToString(), Role = "assistant", Content = acc, CreatedAt = DateTime.UtcNow };
        await _sqlRepo.AddMessageAsync(userId, convId, assistant, ct);
        await thread.DeleteAsync();
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
