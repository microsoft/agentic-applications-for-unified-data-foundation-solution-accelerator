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
        try
        {
            var userMessages = messages.Where(m => m.Role == "user").ToList();

            if (userMessages.Count == 0)
            {
                return "New Conversation";
            }

            if (string.IsNullOrEmpty(_endpoint) || string.IsNullOrEmpty(_titleAgentId))
            {
                return GenerateFallbackTitle(messages);
            }

            // Use the existing title generation agent
            var chatClient = CreateFoundryChatClient(_titleAgentId);
            
            // Create prompt messages exactly
            var promptMessages = new List<ChatMessage>();
            
            var messagesToUse = userMessages.TakeLast(1).ToList(); 
            
            foreach (var msg in messagesToUse)
            {
                var content = msg.GetContentAsString();
                if (!string.IsNullOrEmpty(content))
                {
                    promptMessages.Add(new ChatMessage(ChatRole.User, content));
                }
            }            
            
            var chatOptions = new ChatOptions()
            {
                Temperature = 1.0f,
                MaxOutputTokens = 64
            };

            var response = await chatClient.GetResponseAsync(promptMessages, chatOptions, cancellationToken);
            
            if (response?.Messages?.Count > 0 && response.Messages.Last()?.Text != null)
            {
                var generatedTitle = response.Messages.Last().Text.Trim();
                if (!string.IsNullOrEmpty(generatedTitle))
                {
                    return generatedTitle;
                }
            }

            return GenerateFallbackTitle(messages);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error generating title with Azure AI Foundry title agent {AgentId}: {ErrorMessage}", _titleAgentId, ex.Message);
            
            var userMessages = messages.Where(m => m.Role == "user").ToList();
            if (userMessages.Count > 0)
            {
                var lastUserContent = userMessages.Last().GetContentAsString();
                if (!string.IsNullOrEmpty(lastUserContent))
                {
                    var words = lastUserContent.Split(new char[] { ' ', '\n', '\r', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                    var title = string.Join(" ", words.Take(4));
                    return !string.IsNullOrEmpty(title) ? title : "New Conversation";
                }
            }
            
            return "New Conversation";
        }
    }

    /// <summary>
    /// Creates an IChatClient using the Foundry project endpoint with the specified agent ID.
    /// This provides a standardized chat interface for interacting with Azure AI Foundry agents.
    /// </summary>
    /// <param name="agentId">The ID of the agent to use for chat operations</param>
    /// <returns>An IChatClient configured for the specified agent</returns>
    private IChatClient CreateFoundryChatClient(string agentId)
    {
        if (string.IsNullOrEmpty(_endpoint))
        {
            throw new InvalidOperationException("Azure AI Agent endpoint is not configured");
        }

        if (string.IsNullOrEmpty(agentId))
        {
            throw new InvalidOperationException("Agent ID is not configured");
        }

        var credentialFactory = new AzureCredentialFactory(_configuration);
        var credential = credentialFactory.Create();
        
        var persistentAgentsClient = new PersistentAgentsClient(_endpoint, credential);
        
        var chatClient = persistentAgentsClient.AsIChatClient(agentId);
        
        return chatClient;
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
}