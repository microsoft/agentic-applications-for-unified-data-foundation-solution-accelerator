using Azure.AI.Projects;
using CsApi.Auth;
using CsApi.Interfaces;
using CsApi.Models;
using CsApi.Repositories;
using CsApi.Services;
using CsApi.Utils;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Foundry;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.AI;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Web;
using Azure;

namespace CsApi.Controllers;

[ApiController]
[Route("api")] // matches /api prefix
public class ChatController : ControllerBase
{
    private readonly IUserContextAccessor _userContextAccessor;
    private readonly ISqlConversationRepository _sqlRepo;
    private readonly IConfiguration _configuration;
    private readonly ILogger<ChatController> _logger;
    private readonly IAzureCredentialFactory _credentialFactory;

    // Conversation ID cache: maps app-level conversation ID → Foundry server-side conversation ID
    private readonly ExpCache<string, string> _conversationCache;

    // Citation marker regex matching Python _MARKER_RE: 【\d+:(\d+)†([^】]*)】
    private static readonly Regex MarkerRegex = new(@"【\d+:(\d+)†([^】]*)】", RegexOptions.Compiled);

    public ChatController(
        IUserContextAccessor userContextAccessor,
        ISqlConversationRepository sqlRepo,
        IConfiguration configuration,
        ILogger<ChatController> logger,
        ExpCache<string, string> conversationCache,
        IAzureCredentialFactory credentialFactory)
    { 
        _userContextAccessor = userContextAccessor; 
        _sqlRepo = sqlRepo;
        _configuration = configuration;
        _logger = logger;
        _conversationCache = conversationCache;
        _credentialFactory = credentialFactory;
    }

    /// <summary>
    /// Streaming chat endpoint mirroring Python stream_openai_text_workshop + stream_chat_request.
    /// Streams JSON-lines with choices[0].delta {role, content} per line.
    /// Citation markers are replaced with [N] references and a final tool-role chunk emits citations.
    /// </summary>
    [HttpPost("chat")]
    public async Task Chat([FromBody] ChatRequest request, [FromServices] IAgentFrameworkService agentService, CancellationToken ct)
    {
        Response.ContentType = "application/json-lines";
        
        if (string.IsNullOrWhiteSpace(request.Query))
        {
            await WriteDeltaAsync("assistant", string.Empty, ct);
            await WriteErrorAsync("query is required", ct);
            return;
        }
        
        var user = _userContextAccessor.GetCurrentUser();
        var userId = user.UserPrincipalId;

        // Use the conversation_id from the request (or generate one).
        // When AZURE_ENV_ONLY=true, conversations are managed by Cosmos via /history routes.
        // When false, they're managed by Fabric SQL.
        var azureEnvOnly = string.Equals(_configuration["AZURE_ENV_ONLY"], "true", StringComparison.OrdinalIgnoreCase);
        string convId;
        if (azureEnvOnly)
        {
            // Cosmos manages conversations — just use the provided ID or generate a new one
            convId = string.IsNullOrWhiteSpace(request.ConversationId)
                ? Guid.NewGuid().ToString()
                : request.ConversationId;
        }
        else
        {
            // Fabric SQL manages conversations
            var (id, _) = await _sqlRepo.EnsureConversationAsync(userId ?? string.Empty, request.ConversationId, title: string.Empty, ct);
            convId = id;
        }

        // Sanitize user input to prevent log forging attacks
        var sanitizedQuery = request.Query.Replace(Environment.NewLine, "").Replace("\r", "").Replace("\n", "");
        var sanitizedConvId = convId.Replace(Environment.NewLine, "").Replace("\r", "").Replace("\n", "");
        _logger.LogInformation("Chat request received - query: {Query}, conversation_id: {ConversationId}", sanitizedQuery, sanitizedConvId);

        var agent = agentService.Agent;
        var completeResponseBuilder = new StringBuilder();

        try
        {
            // Retrieve or create server-side conversation
            string? serverConvId = null;
            if (_conversationCache.TryGet(convId, out var cachedConvId))
            {
                serverConvId = cachedConvId;
            }

            if (string.IsNullOrEmpty(serverConvId))
            {
                // Create a new server-side conversation
                var convSession = await agent.CreateConversationSessionAsync(ct);
                serverConvId = convSession.ConversationId ?? string.Empty;
                _conversationCache.Set(convId, serverConvId);
            }

            // Citation tracking
            var mcpDocs = new Dictionary<string, McpDocInfo>();
            var markerBuf = new StringBuilder();
            int citationIdx = 0;
            var originalMarkers = new List<(string SecIdx, string MarkerSource)>();

            // Stream response with conversation_id
            var runOptions = new ChatClientAgentRunOptions(new ChatOptions { ConversationId = serverConvId });
            await foreach (var update in agent.RunStreamingAsync(request.Query, session: null, options: runOptions).WithCancellation(ct))
            {
                // Extract MCP docs from raw representations
                ExtractMcpFromUpdate(update, mcpDocs);

                var chunkText = update?.Text ?? string.Empty;
                if (string.IsNullOrEmpty(chunkText)) continue;

                completeResponseBuilder.Append(chunkText);
                markerBuf.Append(chunkText);

                // Process complete markers in buffer, keep trailing incomplete fragment
                while (true)
                {
                    var match = MarkerRegex.Match(markerBuf.ToString());
                    if (!match.Success)
                    {
                        int openPos = markerBuf.ToString().LastIndexOf('【');
                        if (openPos == -1)
                        {
                            if (markerBuf.Length > 0)
                            {
                                await WriteDeltaAsync("assistant", markerBuf.ToString(), ct);
                            }
                            markerBuf.Clear();
                        }
                        else if (openPos > 0)
                        {
                            await WriteDeltaAsync("assistant", markerBuf.ToString(0, openPos), ct);
                            var remaining = markerBuf.ToString(openPos, markerBuf.Length - openPos);
                            markerBuf.Clear();
                            markerBuf.Append(remaining);
                        }
                        break;
                    }

                    // Flush text before this marker
                    if (match.Index > 0)
                    {
                        await WriteDeltaAsync("assistant", markerBuf.ToString(0, match.Index), ct);
                    }

                    // Replace marker: drop section 0, renumber rest
                    var secIdx = match.Groups[1].Value;
                    var markerSource = match.Groups[2].Value;
                    if (secIdx != "0")
                    {
                        citationIdx++;
                        await WriteDeltaAsync("assistant", $"[{citationIdx}]", ct);
                        originalMarkers.Add((secIdx, markerSource));
                    }

                    var afterMatch = markerBuf.ToString(match.Index + match.Length, markerBuf.Length - match.Index - match.Length);
                    markerBuf.Clear();
                    markerBuf.Append(afterMatch);
                }
            }

            // Flush any remaining buffer
            if (markerBuf.Length > 0)
            {
                await WriteDeltaAsync("assistant", markerBuf.ToString(), ct);
            }

            // Update cache with conversation ID
            _conversationCache.Set(convId, serverConvId);

            _logger.LogInformation("Streaming complete for conversation {ConversationId}: response_length={ResponseLength}, mcp_doc_count={McpDocCount}",
                convId, completeResponseBuilder.Length, mcpDocs.Count);

            // Build and emit citations as a tool message
            var citationList = BuildCitationList(originalMarkers, mcpDocs);
            await WriteDeltaAsync("tool", JsonSerializer.Serialize(citationList), ct);

            // Fallback response when no data is received
            if (completeResponseBuilder.Length == 0)
            {
                await WriteDeltaAsync("assistant", "I cannot answer this question with the current data. Please rephrase or add more details.", ct);
            }
        }
        catch (RequestFailedException ex)
        {
            _logger.LogError(ex, "Azure API error in chat streaming");
            HandleCorruptConversation(convId);
            await WriteErrorAsync(ex.Message, ct);
        }
        catch (OperationCanceledException)
        {
            // Client disconnected - no response needed
        }
        catch (IOException ex)
        {
            _logger.LogError(ex, "IO error in chat streaming");
            await WriteErrorAsync(ex.Message, ct);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            _logger.LogError(ex, "Unexpected error in chat streaming");
            HandleCorruptConversation(convId);
            await WriteErrorAsync("An error occurred while processing the request.", ct);
        }
    }

    /// <summary>
    /// Write a single delta JSON-line chunk matching the Python stream format:
    /// {"choices":[{"delta":{"role":"...","content":"..."}}]}
    /// </summary>
    private async Task WriteDeltaAsync(string role, string content, CancellationToken ct)
    {
        var response = new
        {
            choices = new[] { new { delta = new { role, content } } }
        };
        await Response.WriteAsync(JsonSerializer.Serialize(response) + "\n", ct);
        await Response.Body.FlushAsync(ct);
    }

    /// <summary>Write an error JSON-line.</summary>
    private async Task WriteErrorAsync(string error, CancellationToken ct)
    {
        await Response.WriteAsync(JsonSerializer.Serialize(new { error }) + "\n\n", ct);
        await Response.Body.FlushAsync(ct);
    }

    /// <summary>
    /// Move a corrupted conversation to a corrupt key in cache.
    /// </summary>
    private void HandleCorruptConversation(string convId)
    {
        if (_conversationCache.TryGet(convId, out var serverConvId))
        {
            _conversationCache.Remove(convId);
            var corruptKey = $"{convId}_corrupt_{Random.Shared.Next(1000, 9999)}";
            _conversationCache.Set(corruptKey, serverConvId);
        }
    }

    /// <summary>
    /// Extract MCP document info from AgentResponseUpdate contents.
    /// MCP tool results appear as content items with Outputs[].Text containing doc metadata.
    /// </summary>
    private static void ExtractMcpFromUpdate(AgentResponseUpdate? update, Dictionary<string, McpDocInfo> mcpDocs)
    {
        if (update?.Contents == null) return;

        foreach (var content in update.Contents)
        {
            // MCP results have an "Outputs" property containing items with "Text"
            var outputsProp = content.GetType().GetProperty("Outputs");
            if (outputsProp != null)
            {
                if (outputsProp.GetValue(content) is System.Collections.IEnumerable outputs)
                {
                    foreach (var output in outputs)
                    {
                        var textProp = output.GetType().GetProperty("Text");
                        if (textProp != null)
                        {
                            var text = textProp.GetValue(output) as string;
                            if (!string.IsNullOrEmpty(text))
                            {
                                ParseMcpDocs(text, mcpDocs);
                            }
                        }
                    }
                }
            }
        }
    }

    /// <summary>
    /// Parse JSON document blocks from MCP output text keyed by section index.
    /// </summary>
    private static void ParseMcpDocs(string mcpText, Dictionary<string, McpDocInfo> mcpDocs)
    {
        // Split by marker pattern to extract section content
        var sections = Regex.Split(mcpText, @"【\d+:(\d+)†[^】]*】");
        // sections alternates: [preamble, idx0, content0, idx1, content1, ...]
        for (int i = 1; i < sections.Length - 1; i += 2)
        {
            var secIdx = sections[i];
            var secContent = sections[i + 1];
            var jsonMatch = Regex.Match(secContent, @"\{[^{}]*""id""\s*:\s*""[^""]*""[^{}]*\}");
            if (jsonMatch.Success)
            {
                try
                {
                    var doc = JsonSerializer.Deserialize<McpDocInfo>(jsonMatch.Value);
                    if (doc != null && !string.IsNullOrEmpty(doc.Id))
                    {
                        mcpDocs[secIdx] = doc;
                    }
                }
                catch (JsonException)
                {
                    // Skip malformed JSON fragments
                }
            }
        }
    }

    /// <summary>
    /// Build citation list from original markers and MCP docs.
    /// </summary>
    private List<object> BuildCitationList(List<(string SecIdx, string MarkerSource)> originalMarkers, Dictionary<string, McpDocInfo> mcpDocs)
    {
        var citationList = new List<object>();
        var searchEndpoint = _configuration["AZURE_AI_SEARCH_ENDPOINT"] ?? "";
        var searchIndex = _configuration["AZURE_AI_SEARCH_INDEX"] ?? "";

        foreach (var (secIdx, markerSource) in originalMarkers)
        {
            mcpDocs.TryGetValue(secIdx, out var mcpDoc);
            var docSource = mcpDoc?.Source ?? markerSource;
            if (string.IsNullOrEmpty(docSource))
                docSource = $"source_{secIdx}";
            var docId = mcpDoc?.Id ?? "";

            string docUrl = "";
            if (!string.IsNullOrEmpty(searchEndpoint) && !string.IsNullOrEmpty(searchIndex) && !string.IsNullOrEmpty(docId))
            {
                var encodedId = HttpUtility.UrlEncode(docId);
                docUrl = $"{searchEndpoint.TrimEnd('/')}/indexes/{searchIndex}/docs/{encodedId}?api-version=2024-07-01&$select=id,chunk_id,content,source";
            }

            citationList.Add(new { url = docUrl, source = docSource, id = docId });
        }

        return citationList;
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

    /// <summary>
    /// Fetch document content from Azure AI Search by citation URL.
    /// </summary>
    [HttpPost("fetch-azure-search-content")]
    public async Task<IActionResult> FetchAzureSearchContent([FromBody] JsonElement body)
    {
        try
        {
            var citationUrl = body.TryGetProperty("url", out var urlProp) ? urlProp.GetString() : null;
            var fallbackLabel = body.TryGetProperty("source", out var srcProp) ? srcProp.GetString() : "";
            if (string.IsNullOrEmpty(fallbackLabel) && body.TryGetProperty("title", out var titleProp))
                fallbackLabel = titleProp.GetString() ?? "";

            _logger.LogInformation("POST /fetch-azure-search-content called: url={Url}", citationUrl);

            if (string.IsNullOrWhiteSpace(citationUrl))
                return BadRequest(new { error = "URL is required" });

            // SSRF protection: only allow requests to the configured search endpoint
            var searchEndpoint = _configuration["AZURE_AI_SEARCH_ENDPOINT"] ?? "";
            if (string.IsNullOrEmpty(searchEndpoint))
                return StatusCode(500, new { error = "Search endpoint not configured" });

            var allowedHost = new Uri(searchEndpoint).Host.ToLowerInvariant();
            var parsedUrl = new Uri(citationUrl);
            if (!string.Equals(parsedUrl.Host, allowedHost, StringComparison.OrdinalIgnoreCase))
            {
                _logger.LogWarning("Blocked fetch to non-allowed host: {Host} (allowed: {Allowed})", parsedUrl.Host, allowedHost);
                return StatusCode(403, new { error = "URL host not allowed" });
            }

            // Parse the doc id from the URL: .../docs/{doc_id}?api-version=...
            var pathParts = parsedUrl.AbsolutePath.TrimEnd('/').Split('/');
            string? docId = null;
            for (int i = 0; i < pathParts.Length; i++)
            {
                if (pathParts[i] == "docs" && i + 1 < pathParts.Length)
                {
                    docId = pathParts[i + 1];
                    break;
                }
            }

            if (string.IsNullOrEmpty(docId))
                return BadRequest(new { error = "Could not parse document ID from URL" });

            // Reconstruct URL using OData key lookup
            var idxDocs = parsedUrl.AbsolutePath.IndexOf("/docs/", StringComparison.Ordinal);
            var basePath = parsedUrl.AbsolutePath[..idxDocs];
            var queryParams = HttpUtility.ParseQueryString(parsedUrl.Query);
            var apiVersion = queryParams["api-version"] ?? "2024-07-01";

            var decodedDocId = HttpUtility.UrlDecode(docId);
            var encodedKey = HttpUtility.UrlEncode(decodedDocId);
            var lookupUrl = $"{parsedUrl.Scheme}://{parsedUrl.Host}{basePath}/docs('{encodedKey}')?api-version={apiVersion}";

            // Get access token
            var credential = _credentialFactory.Create();
            var tokenResult = await credential.GetTokenAsync(
                new Azure.Core.TokenRequestContext(new[] { "https://search.azure.com/.default" }), default);

            using var httpClient = new HttpClient();
            httpClient.DefaultRequestHeaders.Authorization =
                new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", tokenResult.Token);
            httpClient.Timeout = TimeSpan.FromSeconds(10);

            var response = await httpClient.GetAsync(lookupUrl);
            _logger.LogInformation("Azure Search lookup: status={Status}, url={LookupUrl}", (int)response.StatusCode, lookupUrl);

            if (response.IsSuccessStatusCode)
            {
                var responseBody = await response.Content.ReadAsStringAsync();
                using var doc = JsonDocument.Parse(responseBody);
                var content = doc.RootElement.TryGetProperty("content", out var contentProp) ? contentProp.GetString() ?? "" : "";
                var source = doc.RootElement.TryGetProperty("source", out var sourceProp) ? sourceProp.GetString() ?? fallbackLabel : fallbackLabel;
                return Ok(new { content, title = source });
            }

            var errorBody = await response.Content.ReadAsStringAsync();
            _logger.LogWarning("Azure Search fetch failed: status={Status}, body={Body}", (int)response.StatusCode, errorBody[..Math.Min(500, errorBody.Length)]);
            return Ok(new { error = $"HTTP {(int)response.StatusCode}" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error in fetch-azure-search-content");
            return StatusCode(500, new { error = "Internal server error" });
        }
    }

    /// <summary>MCP document info matching Python mcp_docs structure.</summary>
    private class McpDocInfo
    {
        [System.Text.Json.Serialization.JsonPropertyName("id")]
        public string Id { get; set; } = "";
        [System.Text.Json.Serialization.JsonPropertyName("title")]
        public string Title { get; set; } = "";
        [System.Text.Json.Serialization.JsonPropertyName("source")]
        public string Source { get; set; } = "";
    }
}
