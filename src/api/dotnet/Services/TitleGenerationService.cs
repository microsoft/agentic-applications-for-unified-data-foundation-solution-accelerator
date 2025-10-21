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
        
        // Log configuration for debugging
        _logger.LogInformation(" TitleGenerationService initialized with endpoint: {Endpoint}, model: {Model}, version: {Version}", 
            _endpoint ?? "NULL", _deploymentModel ?? "NULL", _apiVersion ?? "NULL");
            
        // Test simple title generation
        _ = Task.Run(async () => {
            try
            {
                var testMessages = new List<Models.ChatMessage>
                {
                    new Models.ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Show me revenue by region") }
                };
                var testTitle = await GenerateTitleAsync(testMessages);
                _logger.LogInformation("TEST TITLE GENERATION: '{TestTitle}'", testTitle);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "TEST TITLE GENERATION FAILED: {Error}", ex.Message);
            }
        });
    }

    public async Task<string> GenerateTitleAsync(List<Models.ChatMessage> messages, CancellationToken cancellationToken = default)
    {
        try
        {
            _logger.LogInformation("Title generation started for {MessageCount} messages", messages.Count);
            
            // Filter to get only user messages like Python does
            var userMessages = messages.Where(m => m.Role == "user").ToList();
            _logger.LogInformation("Found {UserMessageCount} user messages out of {TotalMessages}", 
                userMessages.Count, messages.Count);

            if (userMessages.Count == 0)
            {
                _logger.LogWarning(" No user messages found for title generation");
                return "New Conversation";
            }

            // Log the actual user message content for debugging
            foreach (var userMsg in userMessages.Take(3)) // Log first 3 user messages
            {
                var content = userMsg.GetContentAsString();
                _logger.LogInformation("📄 User message: '{Content}'", 
                    content?.Substring(0, Math.Min(100, content?.Length ?? 0)) ?? "EMPTY");
            }

            if (string.IsNullOrEmpty(_endpoint) || string.IsNullOrEmpty(_deploymentModel))
            {
                _logger.LogWarning(" Azure OpenAI configuration missing - Endpoint: {Endpoint}, Model: {Model}", 
                    _endpoint ?? "null", _deploymentModel ?? "null");
                return GenerateFallbackTitle(messages);
            }

            _logger.LogInformation(" Azure OpenAI configuration found - Endpoint: {Endpoint}, Model: {Model}", 
                _endpoint, _deploymentModel);

            var client = CreateOpenAIClient();
            
            // Create prompt messages exactly like Python version
            var promptMessages = new List<OpenAI.Chat.ChatMessage>();
            
            // Add user messages from the conversation (extract content as string)
            // Prioritize the most recent message for title generation
            var messagesToUse = userMessages.TakeLast(1).ToList(); // Focus on the latest message
            
            foreach (var msg in messagesToUse)
            {
                var content = msg.GetContentAsString();
                if (!string.IsNullOrEmpty(content))
                {
                    _logger.LogDebug("Adding user message content: {Content}", content.Substring(0, Math.Min(50, content.Length)));
                    promptMessages.Add(OpenAI.Chat.ChatMessage.CreateUserMessage(content));
                }
            }
            
            // Add title generation prompt focused on the most recent request
            var titlePrompt = "Create a 4-word or less title that describes what the user is asking for. " +
                             "Focus on the main action or data they want (e.g., 'Revenue Line Chart', 'Sales Report', 'Data Analysis'). " +
                             "Do not use quotation marks or punctuation. " +
                             "Do not include any other commentary or description.";
            promptMessages.Add(OpenAI.Chat.ChatMessage.CreateUserMessage(titlePrompt));

            _logger.LogInformation(" Sending {PromptMessageCount} messages to Azure OpenAI for title generation", promptMessages.Count);

            var chatClient = client.GetChatClient(_deploymentModel);
            var chatCompletionOptions = new ChatCompletionOptions()
            {
                Temperature = 1.0f,
                MaxOutputTokenCount = 64
            };

            var response = await chatClient.CompleteChatAsync(promptMessages, chatCompletionOptions, cancellationToken);
            
            if (response?.Value != null && response.Value.Content?.Count > 0)
            {
                var generatedTitle = response.Value.Content[0].Text?.Trim();
                _logger.LogInformation(" Azure OpenAI generated title: '{Title}'", generatedTitle);
                if (!string.IsNullOrEmpty(generatedTitle))
                {
                    return generatedTitle;
                }
            }

            _logger.LogWarning(" Azure OpenAI returned empty title, using fallback");
            return GenerateFallbackTitle(messages);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, " Error generating title with Azure OpenAI: {ErrorMessage}", ex.Message);
            
            // Python-style fallback: return the last user message content
            var userMessages = messages.Where(m => m.Role == "user").ToList();
            if (userMessages.Count > 0)
            {
                var lastUserContent = userMessages.Last().GetContentAsString();
                if (!string.IsNullOrEmpty(lastUserContent))
                {
                    // Take first 4 words like Python does
                    var words = lastUserContent.Split(new char[] { ' ', '\n', '\r', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                    var title = string.Join(" ", words.Take(4));
                    _logger.LogInformation(" Using Python-style fallback title: '{Title}'", title);
                    return !string.IsNullOrEmpty(title) ? title : "New Conversation";
                }
            }
            
            return "New Conversation";
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
            _logger.LogInformation(" Using last user message for fallback title: '{Content}'", 
                content?.Substring(0, Math.Min(50, content?.Length ?? 0)) ?? "EMPTY");
            
            if (!string.IsNullOrEmpty(content))
            {
                // Take first 4 words like the prompt asks for
                var words = content.Split(new char[] { ' ', '\n', '\r', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                var title = string.Join(" ", words.Take(4));
                var finalTitle = !string.IsNullOrEmpty(title) ? title : "New Conversation";
                _logger.LogInformation(" Generated fallback title: '{Title}'", finalTitle);
                return finalTitle;
            }
        }

        _logger.LogWarning(" No user messages found, using default title");
        return "New Conversation";
    }
}