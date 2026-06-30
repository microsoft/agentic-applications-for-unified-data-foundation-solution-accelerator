using CsApi.Models;
using System.Text.Json;
using Xunit;

namespace CsApi.Tests.Models;

public class ChatMessageTests
{
    [Fact]
    public void Constructor_SetsDefaultValues()
    {
        // Act
        var message = new ChatMessage();

        // Assert
        Assert.NotNull(message.Id);
        Assert.NotEmpty(message.Id);
        Assert.Equal("user", message.Role);
        Assert.Equal(string.Empty, message.Feedback);
    }

    [Fact]
    public void Id_IsGuidString()
    {
        // Act
        var message = new ChatMessage();

        // Assert
        Assert.True(Guid.TryParse(message.Id, out _));
    }

    [Fact]
    public void GetContentAsString_StringContent_ReturnsString()
    {
        // Arrange
        var message = new ChatMessage
        {
            Content = JsonSerializer.SerializeToElement("Hello World")
        };

        // Act
        var result = message.GetContentAsString();

        // Assert
        Assert.Equal("Hello World", result);
    }

    [Fact]
    public void GetContentAsString_ObjectContent_ReturnsJsonString()
    {
        // Arrange
        var message = new ChatMessage
        {
            Content = JsonSerializer.SerializeToElement(new { text = "Hello", value = 42 })
        };

        // Act
        var result = message.GetContentAsString();

        // Assert
        Assert.Contains("text", result);
        Assert.Contains("Hello", result);
        Assert.Contains("42", result);
    }

    [Fact]
    public void GetContentAsString_EmptyContent_ReturnsEmpty()
    {
        // Arrange
        var message = new ChatMessage
        {
            Content = JsonSerializer.SerializeToElement(string.Empty)
        };

        // Act
        var result = message.GetContentAsString();

        // Assert
        Assert.Equal(string.Empty, result);
    }

    [Fact]
    public void SetContentFromString_SimpleString_SetsContent()
    {
        // Arrange
        var message = new ChatMessage();

        // Act
        message.SetContentFromString("Test content");

        // Assert
        Assert.Equal("Test content", message.GetContentAsString());
    }

    [Fact]
    public void SetContentFromString_JsonString_PreservesStructure()
    {
        // Arrange
        var message = new ChatMessage();
        var json = "{\"key\":\"value\",\"number\":123}";

        // Act
        message.SetContentFromString(json);

        // Assert
        var content = message.GetContentAsString();
        Assert.Contains("key", content);
        Assert.Contains("value", content);
    }

    [Fact]
    public void GetContentAsJsonString_StringContent_ReturnsQuotedString()
    {
        // Arrange
        var message = new ChatMessage
        {
            Content = JsonSerializer.SerializeToElement("Hello")
        };

        // Act
        var result = message.GetContentAsJsonString();

        // Assert
        Assert.Equal("\"Hello\"", result);
    }

    [Fact]
    public void GetContentAsJsonString_ObjectContent_ReturnsRawJson()
    {
        // Arrange
        var message = new ChatMessage
        {
            Content = JsonSerializer.SerializeToElement(new { name = "Test" })
        };

        // Act
        var result = message.GetContentAsJsonString();

        // Assert
        Assert.Contains("name", result);
        Assert.Contains("Test", result);
    }

    [Fact]
    public void GetCitationsAsStringList_NullCitations_ReturnsEmptyList()
    {
        // Arrange
        var message = new ChatMessage { Citations = null };

        // Act
        var result = message.GetCitationsAsStringList();

        // Assert
        Assert.Empty(result);
    }

    [Fact]
    public void GetCitationsAsStringList_ArrayCitations_ReturnsList()
    {
        // Arrange
        var citations = new[] { "citation1", "citation2" };
        var message = new ChatMessage
        {
            Citations = JsonSerializer.SerializeToElement(citations)
        };

        // Act
        var result = message.GetCitationsAsStringList();

        // Assert
        Assert.Equal(2, result.Count);
        Assert.Contains("citation1", result);
        Assert.Contains("citation2", result);
    }

    [Fact]
    public void GetCitationsAsStringList_StringCitation_ReturnsListWithOneItem()
    {
        // Arrange
        var message = new ChatMessage
        {
            Citations = JsonSerializer.SerializeToElement("single citation")
        };

        // Act
        var result = message.GetCitationsAsStringList();

        // Assert
        Assert.Single(result);
        Assert.Equal("single citation", result[0]);
    }

    [Fact]
    public void GetCitationsAsJsonString_NullCitations_ReturnsEmptyString()
    {
        // Arrange
        var message = new ChatMessage { Citations = null };

        // Act
        var result = message.GetCitationsAsJsonString();

        // Assert
        Assert.Equal(string.Empty, result);
    }

    [Fact]
    public void GetCitationsAsJsonString_ArrayCitations_ReturnsJsonArray()
    {
        // Arrange
        var citations = new[] { "cite1", "cite2" };
        var message = new ChatMessage
        {
            Citations = JsonSerializer.SerializeToElement(citations)
        };

        // Act
        var result = message.GetCitationsAsJsonString();

        // Assert
        Assert.StartsWith("[", result);
        Assert.EndsWith("]", result);
    }

    [Fact]
    public void Role_CanBeSetToAssistant()
    {
        // Arrange
        var message = new ChatMessage { Role = "assistant" };

        // Assert
        Assert.Equal("assistant", message.Role);
    }

    [Fact]
    public void Feedback_CanBeSet()
    {
        // Arrange
        var message = new ChatMessage { Feedback = "positive" };

        // Assert
        Assert.Equal("positive", message.Feedback);
    }
}

public class ChatRequestTests
{
    [Fact]
    public void Properties_CanBeSetAndGet()
    {
        // Arrange & Act
        var request = new ChatRequest
        {
            ConversationId = "conv-123",
            Query = "What is the weather?"
        };

        // Assert
        Assert.Equal("conv-123", request.ConversationId);
        Assert.Equal("What is the weather?", request.Query);
    }

    [Fact]
    public void ConversationId_CanBeNull()
    {
        // Arrange & Act
        var request = new ChatRequest { ConversationId = null };

        // Assert
        Assert.Null(request.ConversationId);
    }

    [Fact]
    public void Query_CanBeNull()
    {
        // Arrange & Act
        var request = new ChatRequest { Query = null };

        // Assert
        Assert.Null(request.Query);
    }
}

public class ConversationSummaryTests
{
    [Fact]
    public void Constructor_SetsDefaultValues()
    {
        // Act
        var summary = new ConversationSummary();

        // Assert
        Assert.Equal(string.Empty, summary.ConversationId);
        Assert.Equal(string.Empty, summary.Title);
    }

    [Fact]
    public void CreatedAt_DefaultsToUtcNow()
    {
        // Arrange
        var before = DateTime.UtcNow.AddSeconds(-1);

        // Act
        var summary = new ConversationSummary();

        // Assert
        var after = DateTime.UtcNow.AddSeconds(1);
        Assert.InRange(summary.CreatedAt, before, after);
    }

    [Fact]
    public void UpdatedAt_DefaultsToUtcNow()
    {
        // Arrange
        var before = DateTime.UtcNow.AddSeconds(-1);

        // Act
        var summary = new ConversationSummary();

        // Assert
        var after = DateTime.UtcNow.AddSeconds(1);
        Assert.InRange(summary.UpdatedAt, before, after);
    }

    [Fact]
    public void Properties_CanBeSet()
    {
        // Arrange
        var createdAt = new DateTime(2024, 1, 1, 12, 0, 0, DateTimeKind.Utc);
        var updatedAt = new DateTime(2024, 1, 2, 12, 0, 0, DateTimeKind.Utc);

        // Act
        var summary = new ConversationSummary
        {
            ConversationId = "conv-123",
            Title = "Test Conversation",
            CreatedAt = createdAt,
            UpdatedAt = updatedAt
        };

        // Assert
        Assert.Equal("conv-123", summary.ConversationId);
        Assert.Equal("Test Conversation", summary.Title);
        Assert.Equal(createdAt, summary.CreatedAt);
        Assert.Equal(updatedAt, summary.UpdatedAt);
    }
}

public class ConversationListResponseTests
{
    [Fact]
    public void Constructor_SetsEmptyList()
    {
        // Act
        var response = new ConversationListResponse();

        // Assert
        Assert.NotNull(response.Conversations);
        Assert.Empty(response.Conversations);
    }

    [Fact]
    public void Conversations_CanBeSet()
    {
        // Arrange
        var conversations = new List<ConversationSummary>
        {
            new ConversationSummary { ConversationId = "1", Title = "First" },
            new ConversationSummary { ConversationId = "2", Title = "Second" }
        };

        // Act
        var response = new ConversationListResponse { Conversations = conversations };

        // Assert
        Assert.Equal(2, response.Conversations.Count);
    }
}

public class ConversationMessagesResponseTests
{
    [Fact]
    public void Constructor_SetsEmptyList()
    {
        // Act
        var response = new ConversationMessagesResponse();

        // Assert
        Assert.NotNull(response.Messages);
        Assert.Empty(response.Messages);
    }

    [Fact]
    public void Messages_CanBeSet()
    {
        // Arrange
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "user" },
            new ChatMessage { Role = "assistant" }
        };

        // Act
        var response = new ConversationMessagesResponse { Messages = messages };

        // Assert
        Assert.Equal(2, response.Messages.Count);
    }
}

public class UpdateConversationRequestTests
{
    [Fact]
    public void Constructor_SetsDefaultValues()
    {
        // Act
        var request = new UpdateConversationRequest();

        // Assert
        Assert.Equal(string.Empty, request.ConversationId);
        Assert.Null(request.Title);
        Assert.Null(request.Messages);
    }

    [Fact]
    public void Properties_CanBeSet()
    {
        // Arrange
        var messages = new List<ChatMessage> { new ChatMessage() };

        // Act
        var request = new UpdateConversationRequest
        {
            ConversationId = "conv-123",
            Title = "Updated Title",
            Messages = messages
        };

        // Assert
        Assert.Equal("conv-123", request.ConversationId);
        Assert.Equal("Updated Title", request.Title);
        Assert.Single(request.Messages!);
    }
}

public class UpdateConversationResponseTests
{
    [Fact]
    public void Success_DefaultsFalse()
    {
        // Act
        var response = new UpdateConversationResponse();

        // Assert
        Assert.False(response.Success);
    }

    [Fact]
    public void Success_CanBeSetToTrue()
    {
        // Act
        var response = new UpdateConversationResponse { Success = true };

        // Assert
        Assert.True(response.Success);
    }
}
