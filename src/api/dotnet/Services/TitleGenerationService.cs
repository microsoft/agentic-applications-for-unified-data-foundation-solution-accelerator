using Azure.AI.OpenAI;
using Azure.Identity;
using CsApi.Interfaces;
using CsApi.Models;
using CsApi.Auth;
using System.Text.Json;
using OpenAI.Chat;

namespace CsApi.Services;

public class TitleGenerationService : ITitleGenerationService
{
    private readonly IConfiguration _configuration;
    private readonly ILogger<TitleGenerationService> _logger;
    private readonly string? _endpoint;
    private readonly string? _deploymentModel;
    private readonly string? _apiVersion;

    public TitleGenerationService(IConfiguration configuration, ILogger<TitleGenerationService> logger)
    {
        _configuration = configuration;
        _logger = logger;
        _endpoint = _configuration["AZURE_OPENAI_ENDPOINT"];
        _deploymentModel = _configuration["AZURE_OPENAI_DEPLOYMENT_MODEL"];
        _apiVersion = _configuration["AZURE_OPENAI_API_VERSION"];
    }

    public async Task<string> GenerateTitleAsync(List<Models.ChatMessage> messages, CancellationToken cancellationToken = default)
    {
        try
        {
            _logger.LogInformation("Starting title generation for {MessageCount} messages", messages.Count);
            
            if (string.IsNullOrEmpty(_endpoint) || string.IsNullOrEmpty(_deploymentModel))
            {
                _logger.LogWarning("Azure OpenAI configuration missing - Endpoint: {Endpoint}, Model: {Model}", 
                    _endpoint ?? "null", _deploymentModel ?? "null");
                return GenerateFallbackTitle(messages);
            }

            // Filter to get only user messages like Python does
            var userMessages = messages.Where(m => m.Role == "user").ToList();
            _logger.LogInformation("Found {UserMessageCount} user messages out of {TotalMessages}", 
                userMessages.Count, messages.Count);

            if (userMessages.Count == 0)
            {
                _logger.LogWarning("No user messages found for title generation");
                return "New Conversation";
            }

            var client = CreateOpenAIClient();
            
            // Create prompt messages exactly like Python version
            var promptMessages = new List<OpenAI.Chat.ChatMessage>();
            
            // Add user messages from the conversation (extract content as string)
            foreach (var msg in userMessages)
            {
                var content = msg.GetContentAsString();
                _logger.LogDebug("Adding user message content: {Content}", content?.Substring(0, Math.Min(50, content?.Length ?? 0)));
                promptMessages.Add(OpenAI.Chat.ChatMessage.CreateUserMessage(content ?? ""));
            }
            
            // Add title generation prompt (exact same as Python)
            var titlePrompt = "Summarize the conversation so far into a 4-word or less title. " +
                             "Do not use any quotation marks or punctuation. " +
                             "Do not include any other commentary or description.";
            promptMessages.Add(OpenAI.Chat.ChatMessage.CreateUserMessage(titlePrompt));

            _logger.LogInformation("Sending {PromptMessageCount} messages to Azure OpenAI for title generation", promptMessages.Count);

            var chatClient = client.GetChatClient(_deploymentModel);
            var chatCompletionOptions = new ChatCompletionOptions()
            {
                Temperature = 1.0f,
                MaxOutputTokenCount = 64
            };

            var response = await chatClient.CompleteChatAsync(promptMessages, chatCompletionOptions, cancellationToken);
            
            if (response?.Value != null)
            {
                var generatedTitle = response.Value.Content[0].Text?.Trim();
                _logger.LogInformation("Azure OpenAI generated title: '{Title}'", generatedTitle);
                if (!string.IsNullOrEmpty(generatedTitle))
                {
                    return generatedTitle;
                }
            }

            _logger.LogWarning("Azure OpenAI returned empty title, using fallback");
            return GenerateFallbackTitle(messages);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error generating title with Azure OpenAI");
            return GenerateFallbackTitle(messages);
        }
    }

    private AzureOpenAIClient CreateOpenAIClient()
    {
        if (string.IsNullOrEmpty(_endpoint))
        {
            throw new InvalidOperationException("Azure OpenAI endpoint is not configured");
        }

        var credentialFactory = new AzureCredentialFactory();
        var credential = credentialFactory.Create();
        return new AzureOpenAIClient(new Uri(_endpoint), credential);
    }

    private string GenerateFallbackTitle(List<Models.ChatMessage> messages)
    {
        _logger.LogInformation("Using fallback title generation");
        
        // Python fallback: return messages[-2]["content"] (the last user message before the prompt)
        var userMessages = messages.Where(m => m.Role == "user").ToList();
        if (userMessages.Count > 0)
        {
            var lastUserMessage = userMessages.Last();
            var content = lastUserMessage.GetContentAsString();
            _logger.LogInformation("Using last user message for fallback title: '{Content}'", content?.Substring(0, Math.Min(50, content?.Length ?? 0)));
            
            if (!string.IsNullOrEmpty(content))
            {
                // Take first 4 words like the prompt asks for
                var words = content.Split(new char[] { ' ', '\n', '\r', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                var title = string.Join(" ", words.Take(4));
                return !string.IsNullOrEmpty(title) ? title : "New Conversation";
            }
        }

        _logger.LogWarning("No user messages found, using default title");
        return "New Conversation";
    }
}