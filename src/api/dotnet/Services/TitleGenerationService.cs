using Azure;
using CsApi.Interfaces;
using CsApi.Auth;
using Azure.AI.Projects;
using Microsoft.Agents.AI;

namespace CsApi.Services;

public class TitleGenerationService : ITitleGenerationService
{
    private readonly IConfiguration _configuration;
    private readonly ILogger<TitleGenerationService> _logger;
    private readonly string? _endpoint;
    private readonly string? _titleAgentName;

    public TitleGenerationService(IConfiguration configuration, ILogger<TitleGenerationService> logger)
    {
        _configuration = configuration;
        _logger = logger;
        _endpoint = _configuration["AZURE_AI_AGENT_ENDPOINT"];
        _titleAgentName = _configuration["AGENT_NAME_TITLE"];
    }

    public async Task<string> GenerateTitleAsync(List<Models.ChatMessage> messages, CancellationToken cancellationToken = default)
    {
        
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

            if (string.IsNullOrEmpty(_titleAgentName))
            {
                return GenerateFallbackTitle(messages);
            }
            else
            {
                _logger.LogDebug("Using configured title agent: {titleAgentName}", _titleAgentName);
                return await GenerateTitleWithAgentAsync(_titleAgentName, messages, cancellationToken);
            }
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
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
    /// Generates a title using the specified Azure AI Foundry agent and the last user message from the conversation.
    /// </summary>
    /// <param name="titleAgentName">The agent ID to use for title generation</param>
    /// <param name="messages">The conversation messages</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Generated title or fallback title if generation fails</returns>
    private async Task<string> GenerateTitleWithAgentAsync(string titleAgentName, List<Models.ChatMessage> messages, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrEmpty(_endpoint))
        {
            throw new InvalidOperationException("Azure AI Agent endpoint is not configured");
        }

        if (string.IsNullOrEmpty(titleAgentName))
        {
            throw new InvalidOperationException("Agent Name is required for title generation");
        }

        try
        {
            var credentialFactory = new AzureCredentialFactory(_configuration);
            var credential = credentialFactory.Create();
           
            var projectClient = new AIProjectClient(new Uri(_endpoint), credential);
            AIAgent titleAgent = projectClient.GetAIAgent(titleAgentName);

            var userMessages = messages.Where(m => m.Role == "user").ToList();
            if (userMessages.Count == 0)
            {
                _logger.LogWarning("No user messages found for title generation with agent {titleAgentName}", titleAgentName);
                return GenerateFallbackTitle(messages);
            }

            var lastUserMessage = userMessages.Last();
            var content = lastUserMessage.GetContentAsString();            
            if (string.IsNullOrEmpty(content))
            {
                _logger.LogWarning("Last user message is empty for title generation with agent {titleAgentName}", titleAgentName);
                return GenerateFallbackTitle(messages);
            }

            _logger.LogDebug("Requesting title generation from agent {titleAgentName} for content: {Content}",
                titleAgentName, content.Length > 100 ? content[..100] + "..." : content);

            var response = await titleAgent.RunAsync(content);

            if (response?.Messages?.Count > 0 && response.Messages.Last()?.Text != null)
            {
                var generatedTitle = response.Messages.Last().Text.Trim();
                if (!string.IsNullOrEmpty(generatedTitle))
                {
                    _logger.LogInformation("Successfully generated title with agent {titleAgentName}: {Title}", titleAgentName, generatedTitle);
                    return generatedTitle;
                }
            }

            _logger.LogWarning("Agent {titleAgentName} returned empty or null title, using fallback", titleAgentName);
            return GenerateFallbackTitle(messages);
        }
        catch (RequestFailedException ex)
        {
            _logger.LogError(ex, "Azure API error generating title with agent {titleAgentName}: {ErrorMessage}", titleAgentName, ex.Message);
            return GenerateFallbackTitle(messages);
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unexpected error generating title with agent {titleAgentName}: {ErrorMessage}", titleAgentName, ex.Message);
            return GenerateFallbackTitle(messages);
        }
    }

}