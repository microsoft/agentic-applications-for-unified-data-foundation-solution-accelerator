using System.Text.Json;
using CsApi.Interfaces;
using CsApi.Models;
using CsApi.Services;
using CsApi.Repositories;
using Microsoft.AspNetCore.Mvc;
using System.Collections.Concurrent;

namespace CsApi.Controllers;

[ApiController]
[Route("api")] // matches /api prefix
public class ChatController : ControllerBase
{
    // REDUNDANT: _chatService is never used - the controller uses AzureAIAgentOrchestrator directly
    // private readonly IChatService _chatService;
    private readonly IUserContextAccessor _userContextAccessor;
    private readonly ISqlConversationRepository _sqlRepo;
    
    // Thread cache to maintain conversation context like Python backend
    private static readonly ConcurrentDictionary<string, (string ThreadId, DateTime LastAccess)> _threadCache = new();
    private static readonly Timer _cleanupTimer = new Timer(CleanupExpiredThreads, null, TimeSpan.FromMinutes(10), TimeSpan.FromMinutes(10));
    private static readonly TimeSpan THREAD_TTL = TimeSpan.FromHours(1); // Match Python 3600 seconds

    public ChatController(IUserContextAccessor userContextAccessor, ISqlConversationRepository sqlRepo)
    { _userContextAccessor = userContextAccessor; _sqlRepo = sqlRepo; }

    /// <summary>
    /// Streaming chat endpoint. Invokes the AzureAIAgent with plugin support (e.g., ChatWithDataPlugin).
    /// If the LLM determines a function call is needed (e.g., SQL or chart), it will call the plugin automatically.
    /// The response is streamed as JSON lines, matching the FastAPI /chat endpoint.
    /// Maintains conversation context using thread caching like Python backend.
    /// </summary>
    [HttpPost("chat")]
    public async Task Chat([FromBody] ChatRequest request, [FromServices] AzureAIAgentOrchestrator orchestrator, CancellationToken ct)
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
        
        // Note: Messages are NOT saved here during streaming
        // They will be saved later when the frontend calls the update endpoint
        
        // Use orchestrator agent for RAG/AI response with plugin support
        var agent = orchestrator.Agent;
        
        // Get or create thread for this conversation to maintain context like Python backend
        Microsoft.SemanticKernel.Agents.AzureAI.AzureAIAgentThread thread;
        var cacheKey = convId ?? "default";
        
        if (_threadCache.TryGetValue(cacheKey, out var cachedThread))
        {
            if (!string.IsNullOrEmpty(cachedThread.ThreadId) && cachedThread.ThreadId != "unknown")
            {
                // Reuse existing thread to maintain conversation context
                try
                {
                    thread = new Microsoft.SemanticKernel.Agents.AzureAI.AzureAIAgentThread(agent.Client, cachedThread.ThreadId);
                    _threadCache[cacheKey] = (cachedThread.ThreadId, DateTime.UtcNow); // Update access time
                    Console.WriteLine($"Reusing existing thread {cachedThread.ThreadId} for conversation {cacheKey}");
                }
                catch (Exception)
                {
                    // Thread might be invalid, create new one and add recent conversation history
                    thread = new Microsoft.SemanticKernel.Agents.AzureAI.AzureAIAgentThread(agent.Client);
                    if (!string.IsNullOrEmpty(thread.Id))
                    {
                        _threadCache[cacheKey] = (thread.Id, DateTime.UtcNow);
                        Console.WriteLine($"Created new thread {thread.Id} for conversation {cacheKey} (old thread invalid)");
                    }
                    else
                    {
                        Console.WriteLine($"Created new thread with null ID for conversation {cacheKey} (old thread invalid) - not caching");
                    }
                    
                    // Note: We'll rely on context enhancement in the message instead of thread history
                    // because AzureAIAgentThread doesn't support direct message addition
                }
            }
            else
            {
                // Invalid cached thread ID, remove from cache and create new thread
                _threadCache.TryRemove(cacheKey, out _);
                Console.WriteLine($"Removing invalid cached thread ID '{cachedThread.ThreadId}' for conversation {cacheKey}");
                thread = new Microsoft.SemanticKernel.Agents.AzureAI.AzureAIAgentThread(agent.Client);
                if (!string.IsNullOrEmpty(thread.Id))
                {
                    _threadCache[cacheKey] = (thread.Id, DateTime.UtcNow);
                    Console.WriteLine($"Created new thread {thread.Id} for conversation {cacheKey} (after removing invalid cache)");
                }
                else
                {
                    Console.WriteLine($"Created new thread with null ID for conversation {cacheKey} (after removing invalid cache) - not caching");
                }
            }
        }
        else
        {
            // Create new thread for new conversation
            thread = new Microsoft.SemanticKernel.Agents.AzureAI.AzureAIAgentThread(agent.Client);
            if (!string.IsNullOrEmpty(thread.Id))
            {
                _threadCache[cacheKey] = (thread.Id, DateTime.UtcNow);
                Console.WriteLine($"Created new thread {thread.Id} for conversation {cacheKey}");
            }
            else
            {
                Console.WriteLine($"Created new thread with null ID for conversation {cacheKey} - not caching");
            }
        }
        
        var message = new Microsoft.SemanticKernel.ChatMessageContent(Microsoft.SemanticKernel.ChatCompletion.AuthorRole.User, query);
        var acc = "";
        try
        {
            // If this looks like a chart request and we have a conversation, try to add context
            if (IsChartRequest(query) && !string.IsNullOrEmpty(convId))
            {
                var contextualQuery = await EnhanceChartQueryWithContext(query, convId, userId ?? string.Empty);
                message = new Microsoft.SemanticKernel.ChatMessageContent(Microsoft.SemanticKernel.ChatCompletion.AuthorRole.User, contextualQuery);
                Console.WriteLine($"Enhanced chart query with context: {contextualQuery}");
            }
            
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
            Console.WriteLine($"Error during agent invocation: {ex.Message}");
            
            // Enhanced detection for thread-related errors
            var isThreadError = ex.Message.Contains("thread") || 
                               ex.Message.Contains("message could not be added") || 
                               ex.Message.Contains("error response from the service") ||
                               ex.GetType().Name.Contains("RequestFailed");
            
            // For any thread-related error, try with a fresh thread
            if (isThreadError)
            {
                try
                {
                    Console.WriteLine("Attempting request with fresh thread due to thread service error");
                    
                    // Remove bad thread from cache
                    _threadCache.TryRemove(cacheKey, out _);
                    
                    // Create fresh thread and try again with original message
                    var freshThread = new Microsoft.SemanticKernel.Agents.AzureAI.AzureAIAgentThread(agent.Client);
                    var fallbackMessage = message; // Use the original message (might be enhanced with context)
                    
                    await foreach (var response in agent.InvokeStreamingAsync(fallbackMessage, freshThread))
                    {
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
                    
                    await freshThread.DeleteAsync();
                    return; // Success with fresh thread
                }
                catch (Exception fallbackEx)
                {
                    Console.WriteLine($"Fallback with fresh thread also failed: {fallbackEx.Message}");
                }
            }
            
            // Stream error as JSON line
            var errorEnvelope = new { error = ex.Message };
            await Response.WriteAsync(JsonSerializer.Serialize(errorEnvelope) + "\n\n", ct);
        }
        
        // Note: Assistant response is NOT saved here during streaming
        // It will be saved later when the frontend calls the update endpoint
        
        // DON'T delete thread immediately - keep it cached for context like Python backend
        // await thread.DeleteAsync(); // Removed - threads are cached and cleaned up by timer
    }

    /// <summary>
    /// Check if a query is requesting chart/visualization
    /// </summary>
    private static bool IsChartRequest(string query)
    {
        var chartKeywords = new[] { "chart", "graph", "plot", "visualiz", "donut", "pie", "bar", "line", "show as" };
        return chartKeywords.Any(keyword => query.ToLowerInvariant().Contains(keyword));
    }

    /// <summary>
    /// Enhance chart query with recent conversation context containing data
    /// </summary>
    private async Task<string> EnhanceChartQueryWithContext(string originalQuery, string conversationId, string userId)
    {
        try
        {
            // Get recent messages to find data context
            var recentMessages = await _sqlRepo.ReadAsync(userId, conversationId, "desc", CancellationToken.None);
            var lastDataMessage = recentMessages
                .Where(m => m.Role == "assistant" && m.GetContentAsString()?.Contains("Region") == true && m.GetContentAsString()?.Contains("Revenue") == true)
                .FirstOrDefault();

            if (lastDataMessage != null)
            {
                var dataContent = lastDataMessage.GetContentAsString();
                // Keep the enhancement concise to avoid message length issues
                return $@"{originalQuery}

Previous data: {dataContent}

Please use GenerateChartData function to create a donut chart with this revenue data.";
            }
            else
            {
                // If no data found, make the request more explicit but brief
                return $@"{originalQuery}

Please use GenerateChartData function to create a donut chart from the recent revenue data in our conversation.";
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Failed to enhance chart query with context: {ex.Message}");
        }
        
        return originalQuery;
    }

    /// <summary>
    /// Clean up expired threads from cache to prevent memory leak
    /// </summary>
    private static void CleanupExpiredThreads(object? state)
    {
        var cutoff = DateTime.UtcNow - THREAD_TTL;
        var expiredKeys = _threadCache
            .Where(kvp => kvp.Value.LastAccess < cutoff)
            .Select(kvp => kvp.Key)
            .ToList();

        foreach (var key in expiredKeys)
        {
            if (_threadCache.TryRemove(key, out var expiredThread))
            {
                Console.WriteLine($"Expired thread {expiredThread.ThreadId} for conversation {key}");
                // Note: We could attempt to delete the thread here, but it might already be deleted
                // The Azure AI service will handle cleanup of unused threads
            }
        }
        
        if (expiredKeys.Count > 0)
        {
            Console.WriteLine($"Cleaned up {expiredKeys.Count} expired thread(s) from cache");
        }
    }

    /// <summary>
    /// Helper method to clear thread cache for a specific conversation (useful for testing)
    /// </summary>
    [HttpPost("clear-thread-cache")]
    public IActionResult ClearThreadCache([FromBody] ClearThreadCacheRequest request)
    {
        if (!string.IsNullOrEmpty(request.ConversationId))
        {
            if (_threadCache.TryRemove(request.ConversationId, out var removedThread))
            {
                Console.WriteLine($"Manually cleared thread {removedThread.ThreadId} for conversation {request.ConversationId}");
                return Ok(new { message = $"Thread cache cleared for conversation {request.ConversationId}" });
            }
            return NotFound(new { message = $"No cached thread found for conversation {request.ConversationId}" });
        }
        
        var clearedCount = _threadCache.Count;
        _threadCache.Clear();
        Console.WriteLine($"Manually cleared all {clearedCount} threads from cache");
        return Ok(new { message = $"Cleared {clearedCount} threads from cache" });
    }

    public class ClearThreadCacheRequest 
    { 
        public string? ConversationId { get; set; } 
    }

    /// <summary>
    /// Test endpoint to directly test chart generation function
    /// </summary>
    [HttpPost("test-chart")]
    public async Task<IActionResult> TestChart([FromBody] TestChartRequest request, [FromServices] CsApi.Plugins.ChatWithDataPlugin plugin)
    {
        try
        {
            var testInput = $@"Create a donut chart for this revenue data:
[{{""Region"":""South"",""TotalRevenue"":2995457.25}},{{""Region"":""Midwest"",""TotalRevenue"":2747475.05}},{{""Region"":""West Coast"",""TotalRevenue"":2505108.98}},{{""Region"":""Northeast"",""TotalRevenue"":2261476.12}},{{""Region"":""Mountain West"",""TotalRevenue"":865463.59}}]

Please generate Chart.js v4.4.4 compatible JSON configuration for a donut chart showing revenue by region.";
            
            var result = await plugin.GetChartDataAsync(testInput);
            return Ok(new { result });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { error = ex.Message });
        }
    }

    public class TestChartRequest 
    { 
        public string? Input { get; set; } 
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
