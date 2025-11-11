using Azure.AI.Agents.Persistent;
using CsApi.Interfaces;
using CsApi.Auth;
using Microsoft.Extensions.AI;

namespace CsApi.Services;

public class TitleGenerationService : ITitleGenerationService
{
    private readonly IConfiguration _configuration;
    private readonly ILogger<TitleGenerationService> _logger;
    private readonly string? _endpoint;
    private readonly string? _titleAgentId;

    public TitleGenerationService(IConfiguration configuration, ILogger<TitleGenerationService> logger)
    {
        _configuration = configuration;
        _logger = logger;
        _endpoint = _configuration["AZURE_AI_AGENT_ENDPOINT"];
        _titleAgentId = _configuration["AGENT_ID_TITLE"];
    }

    public async Task<string> GenerateTitleAsync(List<Models.ChatMessage> messages, CancellationToken cancellationToken = default)
    {
        string? dynamicAgentId = null;
        
        try
        {
            var userMessages = messages.Where(m => m.Role == "user").ToList();

            if (userMessages.Count == 0)
            {
                return "New Conversation";
            }

            if (string.IsNullOrEmpty(_endpoint))
            {
                return GenerateFallbackTitle(messages);
            }

            if (string.IsNullOrEmpty(_titleAgentId))
            {
                _logger.LogInformation("No AGENT_ID_TITLE configured, creating temporary title generation agent");
                
                dynamicAgentId = await CreateTemporaryTitleAgentAsync(cancellationToken);
                _logger.LogDebug("Created temporary agent with ID: {AgentId}", dynamicAgentId);
                
                var title = await GenerateTitleWithAgentAsync(dynamicAgentId, messages, cancellationToken);
                
                await CleanupTemporaryAgentAsync(dynamicAgentId);
                _logger.LogDebug("Successfully cleaned up temporary agent: {AgentId}", dynamicAgentId);
                
                return title;
            }
            else
            {
                _logger.LogDebug("Using configured title agent: {AgentId}", _titleAgentId);
                return await GenerateTitleWithAgentAsync(_titleAgentId, messages, cancellationToken);
            }
        }
        catch (Exception ex)
        {
            // Ensure cleanup of temporary agent if an exception occurred during processing
            if (!string.IsNullOrEmpty(dynamicAgentId))
            {
                try
                {
                    await CleanupTemporaryAgentAsync(dynamicAgentId);
                    _logger.LogDebug("Cleaned up temporary agent {AgentId} after exception", dynamicAgentId);
                }
                catch (Exception cleanupEx)
                {
                    _logger.LogWarning(cleanupEx, "Failed to cleanup temporary agent {AgentId} during exception handling: {ErrorMessage}", 
                        dynamicAgentId, cleanupEx.Message);
                }
            }
            
            _logger.LogWarning(ex, "Error generating title with Azure AI Foundry agent: {ErrorMessage}", ex.Message);
            return GenerateFallbackTitle(messages);
        }
    }

    private string GenerateFallbackTitle(List<Models.ChatMessage> messages)
    {
        var userMessages = messages.Where(m => m.Role == "user").ToList();
        if (userMessages.Count > 0)
        {
            var lastUserMessage = userMessages.Last();
            var content = lastUserMessage.GetContentAsString();
            
            if (!string.IsNullOrEmpty(content))
            {
                // Take first 4 words like the prompt asks for
                var words = content.Split(new char[] { ' ', '\n', '\r', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                var title = string.Join(" ", words.Take(4));
                return !string.IsNullOrEmpty(title) ? title : "New Conversation";
            }
        }

        return "New Conversation";
    }

    /// <summary>
    /// Creates a temporary Azure AI Foundry agent specifically for title generation using the Azure AI project client.
    /// This agent is configured with specialized instructions for creating concise conversation titles.
    /// Uses the Azure AI Foundry agent framework for proper agent lifecycle management.
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>The temporary agent ID</returns>
    private async Task<string> CreateTemporaryTitleAgentAsync(CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrEmpty(_endpoint))
        {
            throw new InvalidOperationException("Azure AI Agent endpoint is not configured");
        }

        var modelDeploymentName = _configuration["AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"] ?? "gpt-4o-mini";
        var credentialFactory = new AzureCredentialFactory(_configuration);
        var credential = credentialFactory.Create();        
        var persistentAgentsClient = new PersistentAgentsClient(_endpoint, credential);
        var guidPart = Guid.NewGuid().ToString("N")[..8];
        var agentName = $"TempTitleAgent-{guidPart}";

        try
        {
            var instructions = "You are a specialized agent for generating concise conversation titles. " +  
                                "Create 4-word or less titles that capture the main action or data request. " +
                                "Focus on key nouns and actions (e.g., 'Revenue Line Chart', 'Sales Report', 'Data Analysis'). " +
                                "Never use quotation marks or punctuation. " +
                                "Be descriptive but concise. " +
                                "Respond only with the title, no additional commentary.";

            var persistentAgentResponse = await persistentAgentsClient.Administration.CreateAgentAsync(
                model: modelDeploymentName,
                name: agentName,
                description: "Temporary agent for generating conversation titles",
                instructions: instructions,
                cancellationToken: cancellationToken);

            var persistentAgent = persistentAgentResponse.Value;

            _logger.LogInformation("Successfully created temporary title generation agent: {AgentId} with name: {AgentName}", 
                persistentAgent.Id, agentName);
            
            return persistentAgent.Id;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create temporary title generation agent: {ErrorMessage}", ex.Message);
            throw;
        }
    }

    /// <summary>
    /// Generates a title using the specified Azure AI Foundry agent and the last user message from the conversation.
    /// </summary>
    /// <param name="agentId">The agent ID to use for title generation</param>
    /// <param name="messages">The conversation messages</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Generated title or fallback title if generation fails</returns>
    private async Task<string> GenerateTitleWithAgentAsync(string agentId, List<Models.ChatMessage> messages, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrEmpty(_endpoint))
        {
            throw new InvalidOperationException("Azure AI Agent endpoint is not configured");
        }

        if (string.IsNullOrEmpty(agentId))
        {
            throw new InvalidOperationException("Agent ID is required for title generation");
        }

        try
        {
            var credentialFactory = new AzureCredentialFactory(_configuration);
            var credential = credentialFactory.Create();
            var persistentAgentsClient = new PersistentAgentsClient(_endpoint, credential);
            var chatClient = persistentAgentsClient.AsIChatClient(agentId);

            var userMessages = messages.Where(m => m.Role == "user").ToList();
            if (userMessages.Count == 0)
            {
                _logger.LogWarning("No user messages found for title generation with agent {AgentId}", agentId);
                return GenerateFallbackTitle(messages);
            }

            var lastUserMessage = userMessages.Last();
            var content = lastUserMessage.GetContentAsString();            
            if (string.IsNullOrEmpty(content))
            {
                _logger.LogWarning("Last user message is empty for title generation with agent {AgentId}", agentId);
                return GenerateFallbackTitle(messages);
            }

            // Create prompt for title generation using the last user message
            var promptMessages = new List<ChatMessage>
            {
                new ChatMessage(ChatRole.User, $"Generate a 4-word or less title for this request: {content}")
            };

            var chatOptions = new ChatOptions()
            {
                Temperature = 1.0f,
                MaxOutputTokens = 64
            };

            _logger.LogDebug("Requesting title generation from agent {AgentId} for content: {Content}", 
                agentId, content.Length > 100 ? content[..100] + "..." : content);

            var response = await chatClient.GetResponseAsync(promptMessages, chatOptions, cancellationToken);

            if (response?.Messages?.Count > 0 && response.Messages.Last()?.Text != null)
            {
                var generatedTitle = response.Messages.Last().Text.Trim();
                if (!string.IsNullOrEmpty(generatedTitle))
                {
                    _logger.LogInformation("Successfully generated title with agent {AgentId}: {Title}", agentId, generatedTitle);
                    return generatedTitle;
                }
            }

            _logger.LogWarning("Agent {AgentId} returned empty or null title, using fallback", agentId);
            return GenerateFallbackTitle(messages);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error generating title with agent {AgentId}: {ErrorMessage}", agentId, ex.Message);
            return GenerateFallbackTitle(messages);
        }
    }

    /// <summary>
    /// Properly cleans up and deletes a temporary Azure AI Foundry agent.
    /// This ensures proper resource management and prevents agent accumulation.
    /// Uses the Azure AI Foundry agent framework for proper agent deletion.
    /// </summary>
    /// <param name="agentId">The temporary agent ID to cleanup</param>
    private async Task CleanupTemporaryAgentAsync(string agentId)
    {
        if (string.IsNullOrEmpty(_endpoint) || string.IsNullOrEmpty(agentId))
        {
            _logger.LogWarning("Cannot cleanup agent - endpoint or agentId is null/empty");
            return;
        }

        try
        {
            var credentialFactory = new AzureCredentialFactory(_configuration);
            var credential = credentialFactory.Create();
            var persistentAgentsClient = new PersistentAgentsClient(_endpoint, credential);
            await persistentAgentsClient.Administration.DeleteAgentAsync(agentId);

            _logger.LogInformation("Successfully deleted temporary title generation agent: {AgentId}", agentId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to delete temporary agent {AgentId}: {ErrorMessage}", agentId, ex.Message);
            throw;
        }
    }
}