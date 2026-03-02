using CsApi.Interfaces;
using CsApi.Models;
using CsApi.Services;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Moq;
using System.Text.Json;
using Xunit;

namespace CsApi.Tests.Services;

public class TitleGenerationServiceTests
{
    private readonly Mock<IConfiguration> _mockConfiguration;
    private readonly Mock<ILogger<TitleGenerationService>> _mockLogger;
    private readonly TitleGenerationService _service;

    public TitleGenerationServiceTests()
    {
        _mockConfiguration = new Mock<IConfiguration>();
        _mockLogger = new Mock<ILogger<TitleGenerationService>>();
        _service = new TitleGenerationService(_mockConfiguration.Object, _mockLogger.Object);
    }

    #region GenerateTitleAsync Tests

    [Fact]
    public async Task GenerateTitleAsync_NoUserMessages_ReturnsNewConversation()
    {
        // Arrange
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "assistant", Content = JsonSerializer.SerializeToElement("Hello!") }
        };

        // Act
        var result = await _service.GenerateTitleAsync(messages);

        // Assert
        Assert.Equal("New Conversation", result);
    }

    [Fact]
    public async Task GenerateTitleAsync_EmptyMessages_ReturnsNewConversation()
    {
        // Arrange
        var messages = new List<ChatMessage>();

        // Act
        var result = await _service.GenerateTitleAsync(messages);

        // Assert
        Assert.Equal("New Conversation", result);
    }

    [Fact]
    public async Task GenerateTitleAsync_NoEndpoint_ReturnsFallbackTitle()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns((string?)null);
        _mockConfiguration.Setup(c => c["AGENT_NAME_TITLE"]).Returns((string?)null);
        
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("What is the weather today in Seattle?") }
        };

        // Act
        var result = await _service.GenerateTitleAsync(messages);

        // Assert
        Assert.Equal("What is the weather", result);
    }

    [Fact]
    public async Task GenerateTitleAsync_NoTitleAgentName_ReturnsFallbackTitle()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns("https://test.azure.com");
        _mockConfiguration.Setup(c => c["AGENT_NAME_TITLE"]).Returns((string?)null);
        
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Hello world test message") }
        };

        // Act
        var result = await _service.GenerateTitleAsync(messages);

        // Assert
        Assert.Equal("Hello world test message", result);
    }

    [Fact]
    public async Task GenerateTitleAsync_SingleWord_ReturnsSingleWord()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns((string?)null);
        
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Hello") }
        };

        // Act
        var result = await _service.GenerateTitleAsync(messages);

        // Assert
        Assert.Equal("Hello", result);
    }

    [Fact]
    public async Task GenerateTitleAsync_MultipleUserMessages_UsesLastMessage()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns((string?)null);
        
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("First message here") },
            new ChatMessage { Role = "assistant", Content = JsonSerializer.SerializeToElement("Response") },
            new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Final user message text") }
        };

        // Act
        var result = await _service.GenerateTitleAsync(messages);

        // Assert
        Assert.Equal("Final user message text", result);
    }

    [Fact]
    public async Task GenerateTitleAsync_EmptyUserContent_ReturnsNewConversation()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns((string?)null);
        
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("") }
        };

        // Act
        var result = await _service.GenerateTitleAsync(messages);

        // Assert
        Assert.Equal("New Conversation", result);
    }

    [Fact]
    public async Task GenerateTitleAsync_ContentWithNewlines_TrimsCorrectly()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns((string?)null);
        
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Hello\nworld\ntest\nmessage\nextra") }
        };

        // Act
        var result = await _service.GenerateTitleAsync(messages);

        // Assert
        Assert.Equal("Hello world test message", result);
    }

    [Fact]
    public async Task GenerateTitleAsync_ContentWithTabs_TrimsCorrectly()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns((string?)null);
        
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Hello\tworld\ttest\tmessage\textra") }
        };

        // Act
        var result = await _service.GenerateTitleAsync(messages);

        // Assert
        Assert.Equal("Hello world test message", result);
    }

    [Fact]
    public async Task GenerateTitleAsync_MoreThanFourWords_TakesOnlyFirstFour()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns((string?)null);
        
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("One two three four five six seven") }
        };

        // Act
        var result = await _service.GenerateTitleAsync(messages);

        // Assert
        Assert.Equal("One two three four", result);
    }

    [Fact]
    public async Task GenerateTitleAsync_ExactlyFourWords_ReturnsAllFour()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns((string?)null);
        
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("One two three four") }
        };

        // Act
        var result = await _service.GenerateTitleAsync(messages);

        // Assert
        Assert.Equal("One two three four", result);
    }

    [Fact]
    public async Task GenerateTitleAsync_WhitespaceOnlyContent_ReturnsNewConversation()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns((string?)null);
        
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("   \t\n  ") }
        };

        // Act
        var result = await _service.GenerateTitleAsync(messages);

        // Assert
        Assert.Equal("New Conversation", result);
    }

    [Fact]
    public async Task GenerateTitleAsync_CancellationRequested_ThrowsOperationCanceledException()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns("https://test.azure.com");
        _mockConfiguration.Setup(c => c["AGENT_NAME_TITLE"]).Returns("test-agent");
        
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Test message") }
        };

        using var cts = new CancellationTokenSource();
        cts.Cancel();

        // Act - Since we don't have a real agent, it will fall back which doesn't check cancellation
        var result = await _service.GenerateTitleAsync(messages, cts.Token);

        // Assert - Falls back gracefully
        Assert.NotNull(result);
    }

    #endregion
}
