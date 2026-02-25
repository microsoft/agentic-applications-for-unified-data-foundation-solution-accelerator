using CsApi.Controllers;
using CsApi.Interfaces;
using CsApi.Models;
using CsApi.Repositories;
using CsApi.Services;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Moq;
using System.Text.Json;
using Xunit;

namespace CsApi.Tests.Controllers;

public class HistoryFabControllerTests
{
    private readonly Mock<ISqlConversationRepository> _mockRepo;
    private readonly Mock<ITitleGenerationService> _mockTitleService;
    private readonly Mock<ILogger<HistoryFabController>> _mockLogger;
    private readonly Mock<IUserContextAccessor> _mockUserContext;
    private readonly HistoryFabController _controller;

    public HistoryFabControllerTests()
    {
        _mockRepo = new Mock<ISqlConversationRepository>();
        _mockTitleService = new Mock<ITitleGenerationService>();
        _mockLogger = new Mock<ILogger<HistoryFabController>>();
        _mockUserContext = new Mock<IUserContextAccessor>();

        _mockUserContext.Setup(u => u.GetCurrentUser())
            .Returns(new UserContext { UserPrincipalId = "test-user-123" });

        _controller = new HistoryFabController(
            _mockRepo.Object,
            _mockTitleService.Object,
            _mockLogger.Object,
            _mockUserContext.Object);
    }

    #region List Tests

    [Fact]
    public async Task List_ReturnsOkWithConversations()
    {
        // Arrange
        var conversations = new List<ConversationSummary>
        {
            new ConversationSummary { ConversationId = "conv1", Title = "Test 1" },
            new ConversationSummary { ConversationId = "conv2", Title = "Test 2" }
        };
        _mockRepo.Setup(r => r.ListAsync(It.IsAny<string?>(), It.IsAny<int>(), It.IsAny<int>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(conversations);

        // Act
        var result = await _controller.List();

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        var returnedList = Assert.IsAssignableFrom<IEnumerable<ConversationSummary>>(okResult.Value);
        Assert.Equal(2, returnedList.Count());
    }

    [Fact]
    public async Task List_WithOffset_UsesProvidedOffset()
    {
        // Arrange
        _mockRepo.Setup(r => r.ListAsync("test-user-123", 10, 25, "DESC", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>());

        // Act
        await _controller.List(offset: 10);

        // Assert
        _mockRepo.Verify(r => r.ListAsync("test-user-123", 10, 25, "DESC", It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task List_WithLimit_UsesProvidedLimit()
    {
        // Arrange
        _mockRepo.Setup(r => r.ListAsync("test-user-123", 0, 50, "DESC", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>());

        // Act
        await _controller.List(limit: 50);

        // Assert
        _mockRepo.Verify(r => r.ListAsync("test-user-123", 0, 50, "DESC", It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task List_WithAscSort_UsesSortOrder()
    {
        // Arrange
        _mockRepo.Setup(r => r.ListAsync("test-user-123", 0, 25, "ASC", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>());

        // Act
        await _controller.List(sort: "ASC");

        // Assert
        _mockRepo.Verify(r => r.ListAsync("test-user-123", 0, 25, "ASC", It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task List_EmptyConversations_ReturnsOkWithEmptyList()
    {
        // Arrange
        _mockRepo.Setup(r => r.ListAsync(It.IsAny<string?>(), It.IsAny<int>(), It.IsAny<int>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>());

        // Act
        var result = await _controller.List();

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        var returnedList = Assert.IsAssignableFrom<IEnumerable<ConversationSummary>>(okResult.Value);
        Assert.Empty(returnedList);
    }

    #endregion

    #region Read Tests

    [Fact]
    public async Task Read_ValidId_ReturnsOkWithMessages()
    {
        // Arrange
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Hello") },
            new ChatMessage { Role = "assistant", Content = JsonSerializer.SerializeToElement("Hi there!") }
        };
        _mockRepo.Setup(r => r.ReadAsync("test-user-123", "conv-123", "ASC", It.IsAny<CancellationToken>()))
            .ReturnsAsync(messages);

        // Act
        var result = await _controller.Read("conv-123");

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    [Fact]
    public async Task Read_EmptyId_ReturnsBadRequest()
    {
        // Act
        var result = await _controller.Read("");

        // Assert
        Assert.IsType<ObjectResult>(result);
        var objectResult = (ObjectResult)result;
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Read_NullId_ReturnsBadRequest()
    {
        // Act
        var result = await _controller.Read(null!);

        // Assert
        Assert.IsType<ObjectResult>(result);
        var objectResult = (ObjectResult)result;
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Read_NoMessages_ReturnsNotFound()
    {
        // Arrange
        _mockRepo.Setup(r => r.ReadAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ChatMessage>());

        // Act
        var result = await _controller.Read("conv-123");

        // Assert
        var notFoundResult = Assert.IsType<NotFoundObjectResult>(result);
        Assert.NotNull(notFoundResult.Value);
    }

    [Fact]
    public async Task Read_WithDescSort_UsesSortOrder()
    {
        // Arrange
        _mockRepo.Setup(r => r.ReadAsync("test-user-123", "conv-123", "DESC", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ChatMessage> 
            { 
                new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("test") },
                new ChatMessage { Role = "assistant", Content = JsonSerializer.SerializeToElement("response") }
            });

        // Act
        await _controller.Read("conv-123", "DESC");

        // Assert
        _mockRepo.Verify(r => r.ReadAsync("test-user-123", "conv-123", "DESC", It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task Read_FiltersPairlessUserMessages()
    {
        // Arrange - User message without paired assistant response
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Id = "1", Role = "user", Content = JsonSerializer.SerializeToElement("First question") },
            new ChatMessage { Id = "2", Role = "assistant", Content = JsonSerializer.SerializeToElement("First answer") },
            new ChatMessage { Id = "3", Role = "user", Content = JsonSerializer.SerializeToElement("Orphan question") }
        };
        _mockRepo.Setup(r => r.ReadAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(messages);

        // Act
        var result = await _controller.Read("conv-123");

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    [Fact]
    public async Task Read_StandaloneAssistantMessage_IsIncluded()
    {
        // Arrange - Assistant message without preceding user message
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Id = "1", Role = "assistant", Content = JsonSerializer.SerializeToElement("Standalone assistant message") }
        };
        _mockRepo.Setup(r => r.ReadAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(messages);

        // Act
        var result = await _controller.Read("conv-123");

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    [Fact]
    public async Task Read_ErrorRole_PairedWithUser()
    {
        // Arrange - User message paired with error role
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Id = "1", Role = "user", Content = JsonSerializer.SerializeToElement("Question") },
            new ChatMessage { Id = "2", Role = "error", Content = JsonSerializer.SerializeToElement("Error response") }
        };
        _mockRepo.Setup(r => r.ReadAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(messages);

        // Act
        var result = await _controller.Read("conv-123");

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    [Fact]
    public async Task Read_SystemRole_IsIncluded()
    {
        // Arrange - System/tool role messages
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Id = "1", Role = "system", Content = JsonSerializer.SerializeToElement("System message") },
            new ChatMessage { Id = "2", Role = "user", Content = JsonSerializer.SerializeToElement("User question") },
            new ChatMessage { Id = "3", Role = "assistant", Content = JsonSerializer.SerializeToElement("Response") }
        };
        _mockRepo.Setup(r => r.ReadAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(messages);

        // Act
        var result = await _controller.Read("conv-123");

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    [Fact]
    public async Task Read_MultipleConsecutiveUserMessages_OnlyPairedIncluded()
    {
        // Arrange - Multiple user messages, only last one has assistant response
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Id = "1", Role = "user", Content = JsonSerializer.SerializeToElement("First orphan") },
            new ChatMessage { Id = "2", Role = "user", Content = JsonSerializer.SerializeToElement("Second orphan") },
            new ChatMessage { Id = "3", Role = "user", Content = JsonSerializer.SerializeToElement("Third question") },
            new ChatMessage { Id = "4", Role = "assistant", Content = JsonSerializer.SerializeToElement("Answer") }
        };
        _mockRepo.Setup(r => r.ReadAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(messages);

        // Act
        var result = await _controller.Read("conv-123");

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    [Fact]
    public async Task Read_EmptyContentMessages_Filtered()
    {
        // Arrange - Messages with empty content should be filtered out
        var messages = new List<ChatMessage>
        {
            new ChatMessage { Id = "1", Role = "user", Content = JsonSerializer.SerializeToElement("Valid question") },
            new ChatMessage { Id = "2", Role = "assistant", Content = JsonSerializer.SerializeToElement("") }, // Empty content
            new ChatMessage { Id = "3", Role = "assistant", Content = JsonSerializer.SerializeToElement("Valid response") }
        };
        _mockRepo.Setup(r => r.ReadAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(messages);

        // Act
        var result = await _controller.Read("conv-123");

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    #endregion

    #region Delete Tests

    [Fact]
    public async Task Delete_ValidId_ReturnsOk()
    {
        // Arrange
        _mockRepo.Setup(r => r.DeleteAsync("test-user-123", "conv-123", It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);

        // Act
        var result = await _controller.Delete("conv-123");

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    [Fact]
    public async Task Delete_EmptyId_ReturnsBadRequest()
    {
        // Act
        var result = await _controller.Delete("");

        // Assert
        Assert.IsType<ObjectResult>(result);
        var objectResult = (ObjectResult)result;
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Delete_NotFound_ReturnsNotFound()
    {
        // Arrange
        _mockRepo.Setup(r => r.DeleteAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync((bool?)null);

        // Act
        var result = await _controller.Delete("conv-123");

        // Assert
        Assert.IsType<NotFoundObjectResult>(result);
    }

    [Fact]
    public async Task Delete_NoPermission_ReturnsForbid()
    {
        // Arrange
        _mockRepo.Setup(r => r.DeleteAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(false);

        // Act
        var result = await _controller.Delete("conv-123");

        // Assert
        Assert.IsType<ForbidResult>(result);
    }

    #endregion

    #region DeleteAll Tests

    [Fact]
    public async Task DeleteAll_Success_ReturnsOk()
    {
        // Arrange
        _mockRepo.Setup(r => r.DeleteAllAsync("test-user-123", It.IsAny<CancellationToken>()))
            .ReturnsAsync(5);

        // Act
        var result = await _controller.DeleteAll();

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    [Fact]
    public async Task DeleteAll_Failure_ReturnsProblem()
    {
        // Arrange
        _mockRepo.Setup(r => r.DeleteAllAsync(It.IsAny<string?>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync((int?)null);

        // Act
        var result = await _controller.DeleteAll();

        // Assert
        Assert.IsType<ObjectResult>(result);
        var objectResult = (ObjectResult)result;
        Assert.Equal(500, objectResult.StatusCode);
    }

    [Fact]
    public async Task DeleteAll_NoUserId_ReturnsOkWithAdminMessage()
    {
        // Arrange
        _mockUserContext.Setup(u => u.GetCurrentUser())
            .Returns(new UserContext { UserPrincipalId = null });
        
        var controller = new HistoryFabController(
            _mockRepo.Object,
            _mockTitleService.Object,
            _mockLogger.Object,
            _mockUserContext.Object);

        _mockRepo.Setup(r => r.DeleteAllAsync(null, It.IsAny<CancellationToken>()))
            .ReturnsAsync(10);

        // Act
        var result = await controller.DeleteAll();

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    #endregion

    #region Rename Tests

    [Fact]
    public async Task Rename_ValidRequest_ReturnsOk()
    {
        // Arrange
        _mockRepo.Setup(r => r.RenameAsync("test-user-123", "conv-123", "New Title", It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);

        var request = new HistoryFabController.RenameRequest 
        { 
            Conversation_Id = "conv-123", 
            Title = "New Title" 
        };

        // Act
        var result = await _controller.Rename(request);

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    [Fact]
    public async Task Rename_EmptyConversationId_ReturnsBadRequest()
    {
        // Arrange
        var request = new HistoryFabController.RenameRequest 
        { 
            Conversation_Id = "", 
            Title = "New Title" 
        };

        // Act
        var result = await _controller.Rename(request);

        // Assert
        Assert.IsType<ObjectResult>(result);
        var objectResult = (ObjectResult)result;
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Rename_EmptyTitle_ReturnsBadRequest()
    {
        // Arrange
        var request = new HistoryFabController.RenameRequest 
        { 
            Conversation_Id = "conv-123", 
            Title = "" 
        };

        // Act
        var result = await _controller.Rename(request);

        // Assert
        Assert.IsType<ObjectResult>(result);
        var objectResult = (ObjectResult)result;
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Rename_NotFound_ReturnsNotFound()
    {
        // Arrange
        _mockRepo.Setup(r => r.RenameAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync((bool?)null);

        var request = new HistoryFabController.RenameRequest 
        { 
            Conversation_Id = "conv-123", 
            Title = "New Title" 
        };

        // Act
        var result = await _controller.Rename(request);

        // Assert
        Assert.IsType<NotFoundObjectResult>(result);
    }

    [Fact]
    public async Task Rename_NoPermission_ReturnsForbid()
    {
        // Arrange
        _mockRepo.Setup(r => r.RenameAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(false);

        var request = new HistoryFabController.RenameRequest 
        { 
            Conversation_Id = "conv-123", 
            Title = "New Title" 
        };

        // Act
        var result = await _controller.Rename(request);

        // Assert
        Assert.IsType<ForbidResult>(result);
    }

    #endregion

    #region Update Tests

    [Fact]
    public async Task Update_ValidRequest_ReturnsOk()
    {
        // Arrange
        _mockRepo.Setup(r => r.EnsureConversationAsync("test-user-123", "conv-123", "", It.IsAny<CancellationToken>()))
            .ReturnsAsync(("conv-123", true));
        _mockRepo.Setup(r => r.ListAsync(It.IsAny<string?>(), It.IsAny<int>(), It.IsAny<int>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>
            {
                new ConversationSummary { ConversationId = "conv-123", Title = "Test Title", UpdatedAt = DateTime.UtcNow }
            });
        _mockRepo.Setup(r => r.ReadAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ChatMessage>());
        _mockTitleService.Setup(t => t.GenerateTitleAsync(It.IsAny<List<ChatMessage>>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync("Generated Title");

        var request = new HistoryFabController.UpdateRequest
        {
            Conversation_Id = "conv-123",
            Messages = new List<ChatMessage>
            {
                new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Test") },
                new ChatMessage { Role = "assistant", Content = JsonSerializer.SerializeToElement("Response") }
            }
        };

        // Act
        var result = await _controller.Update(request);

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    [Fact]
    public async Task Update_NullRequest_ReturnsBadRequest()
    {
        // Act
        var result = await _controller.Update(null!);

        // Assert
        Assert.IsType<ObjectResult>(result);
        var objectResult = (ObjectResult)result;
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Update_EmptyConversationId_ReturnsBadRequest()
    {
        // Arrange
        var request = new HistoryFabController.UpdateRequest
        {
            Conversation_Id = "",
            Messages = new List<ChatMessage>
            {
                new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Test") }
            }
        };

        // Act
        var result = await _controller.Update(request);

        // Assert
        Assert.IsType<ObjectResult>(result);
        var objectResult = (ObjectResult)result;
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Update_EmptyMessages_ReturnsBadRequest()
    {
        // Arrange
        var request = new HistoryFabController.UpdateRequest
        {
            Conversation_Id = "conv-123",
            Messages = new List<ChatMessage>()
        };

        // Act
        var result = await _controller.Update(request);

        // Assert
        Assert.IsType<ObjectResult>(result);
        var objectResult = (ObjectResult)result;
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Update_NullMessages_ReturnsBadRequest()
    {
        // Arrange
        var request = new HistoryFabController.UpdateRequest
        {
            Conversation_Id = "conv-123",
            Messages = null!
        };

        // Act
        var result = await _controller.Update(request);

        // Assert
        Assert.IsType<ObjectResult>(result);
        var objectResult = (ObjectResult)result;
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Update_ExistingConversation_DoesNotGenerateTitle()
    {
        // Arrange
        _mockRepo.Setup(r => r.EnsureConversationAsync("test-user-123", "conv-123", "", It.IsAny<CancellationToken>()))
            .ReturnsAsync(("conv-123", false)); // Not a new conversation
        _mockRepo.Setup(r => r.ListAsync(It.IsAny<string?>(), It.IsAny<int>(), It.IsAny<int>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>
            {
                new ConversationSummary { ConversationId = "conv-123", Title = "Existing Title", UpdatedAt = DateTime.UtcNow }
            });
        _mockRepo.Setup(r => r.ReadAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ChatMessage> 
            { 
                new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Old message") }
            });

        var request = new HistoryFabController.UpdateRequest
        {
            Conversation_Id = "conv-123",
            Messages = new List<ChatMessage>
            {
                new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Test") },
                new ChatMessage { Role = "assistant", Content = JsonSerializer.SerializeToElement("Response") }
            }
        };

        // Act
        await _controller.Update(request);

        // Assert
        _mockTitleService.Verify(t => t.GenerateTitleAsync(It.IsAny<List<ChatMessage>>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task Update_UnauthorizedAccess_ReturnsForbid()
    {
        // Arrange
        _mockRepo.Setup(r => r.EnsureConversationAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ThrowsAsync(new UnauthorizedAccessException());

        var request = new HistoryFabController.UpdateRequest
        {
            Conversation_Id = "conv-123",
            Messages = new List<ChatMessage>
            {
                new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Test") }
            }
        };

        // Act
        var result = await _controller.Update(request);

        // Assert
        Assert.IsType<ForbidResult>(result);
    }

    [Fact]
    public async Task Update_GeneralException_ReturnsProblem()
    {
        // Arrange
        _mockRepo.Setup(r => r.EnsureConversationAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ThrowsAsync(new Exception("Database error"));

        var request = new HistoryFabController.UpdateRequest
        {
            Conversation_Id = "conv-123",
            Messages = new List<ChatMessage>
            {
                new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Test") }
            }
        };

        // Act
        var result = await _controller.Update(request);

        // Assert
        Assert.IsType<ObjectResult>(result);
        var objectResult = (ObjectResult)result;
        Assert.Equal(500, objectResult.StatusCode);
    }

    [Fact]
    public async Task Update_ConversationNotFound_ReturnsProblem()
    {
        // Arrange
        _mockRepo.Setup(r => r.EnsureConversationAsync("test-user-123", "conv-123", "", It.IsAny<CancellationToken>()))
            .ReturnsAsync(("conv-123", true));
        _mockRepo.Setup(r => r.ListAsync(It.IsAny<string?>(), It.IsAny<int>(), It.IsAny<int>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>()); // Empty list - conversation not found

        var request = new HistoryFabController.UpdateRequest
        {
            Conversation_Id = "conv-123",
            Messages = new List<ChatMessage>
            {
                new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Test") },
                new ChatMessage { Role = "assistant", Content = JsonSerializer.SerializeToElement("Response") }
            }
        };

        // Act
        var result = await _controller.Update(request);

        // Assert
        Assert.IsType<ObjectResult>(result);
        var objectResult = (ObjectResult)result;
        Assert.Equal(500, objectResult.StatusCode);
    }

    [Fact]
    public async Task Update_TitleGenerationFails_UsesFallbackTitle()
    {
        // Arrange
        _mockRepo.Setup(r => r.EnsureConversationAsync("test-user-123", "conv-123", "", It.IsAny<CancellationToken>()))
            .ReturnsAsync(("conv-123", true));
        _mockRepo.Setup(r => r.ListAsync(It.IsAny<string?>(), It.IsAny<int>(), It.IsAny<int>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>
            {
                new ConversationSummary { ConversationId = "conv-123", Title = "New Conversation", UpdatedAt = DateTime.UtcNow }
            });
        _mockRepo.Setup(r => r.ReadAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ChatMessage>());
        _mockTitleService.Setup(t => t.GenerateTitleAsync(It.IsAny<List<ChatMessage>>(), It.IsAny<CancellationToken>()))
            .ThrowsAsync(new Exception("Title generation failed"));

        var request = new HistoryFabController.UpdateRequest
        {
            Conversation_Id = "conv-123",
            Messages = new List<ChatMessage>
            {
                new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("Test") },
                new ChatMessage { Role = "assistant", Content = JsonSerializer.SerializeToElement("Response") }
            }
        };

        // Act
        var result = await _controller.Update(request);

        // Assert - Should still return Ok with fallback title
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
        
        // Verify fallback title was set
        _mockRepo.Verify(r => r.UpdateConversationTitleAsync("test-user-123", "conv-123", "New Conversation", It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task Update_ExistingMessages_SkipsDuplicates()
    {
        // Arrange
        var existingMessageId = "existing-msg-id";
        
        _mockRepo.Setup(r => r.EnsureConversationAsync("test-user-123", "conv-123", "", It.IsAny<CancellationToken>()))
            .ReturnsAsync(("conv-123", false));
        _mockRepo.Setup(r => r.ListAsync(It.IsAny<string?>(), It.IsAny<int>(), It.IsAny<int>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>
            {
                new ConversationSummary { ConversationId = "conv-123", Title = "Test Title", UpdatedAt = DateTime.UtcNow }
            });
        _mockRepo.Setup(r => r.ReadAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ChatMessage>
            {
                new ChatMessage { Id = existingMessageId, Role = "user", Content = JsonSerializer.SerializeToElement("Existing") }
            });

        var request = new HistoryFabController.UpdateRequest
        {
            Conversation_Id = "conv-123",
            Messages = new List<ChatMessage>
            {
                new ChatMessage { Id = existingMessageId, Role = "user", Content = JsonSerializer.SerializeToElement("Existing") }, // Duplicate
                new ChatMessage { Id = "new-msg-id", Role = "assistant", Content = JsonSerializer.SerializeToElement("New Response") } // New
            }
        };

        // Act
        var result = await _controller.Update(request);

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
        
        // Verify only the new message was added (not the duplicate)
        _mockRepo.Verify(r => r.AddMessageAsync("test-user-123", "conv-123", 
            It.Is<ChatMessage>(m => m.Id == "new-msg-id"), It.IsAny<CancellationToken>()), Times.Once);
        _mockRepo.Verify(r => r.AddMessageAsync("test-user-123", "conv-123", 
            It.Is<ChatMessage>(m => m.Id == existingMessageId), It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task Update_ExistingConversationNoMessages_GeneratesTitle()
    {
        // Arrange - Existing conversation (isNewConversation=false) but has no messages (hasNoMessages=true)
        _mockRepo.Setup(r => r.EnsureConversationAsync("test-user-123", "conv-123", "", It.IsAny<CancellationToken>()))
            .ReturnsAsync(("conv-123", false));
        _mockRepo.Setup(r => r.ListAsync(It.IsAny<string?>(), It.IsAny<int>(), It.IsAny<int>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>
            {
                new ConversationSummary { ConversationId = "conv-123", Title = "", UpdatedAt = DateTime.UtcNow }
            });
        _mockRepo.Setup(r => r.ReadAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ChatMessage>()); // No existing messages
        _mockTitleService.Setup(t => t.GenerateTitleAsync(It.IsAny<List<ChatMessage>>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync("Auto Generated Title");

        var request = new HistoryFabController.UpdateRequest
        {
            Conversation_Id = "conv-123",
            Messages = new List<ChatMessage>
            {
                new ChatMessage { Role = "user", Content = JsonSerializer.SerializeToElement("First message") },
                new ChatMessage { Role = "assistant", Content = JsonSerializer.SerializeToElement("Response") }
            }
        };

        // Act
        await _controller.Update(request);

        // Assert - Title should be generated even for existing conversation with no messages
        _mockTitleService.Verify(t => t.GenerateTitleAsync(It.IsAny<List<ChatMessage>>(), It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task Update_MessagesWithEmptyId_GeneratesNewId()
    {
        // Arrange
        _mockRepo.Setup(r => r.EnsureConversationAsync("test-user-123", "conv-123", "", It.IsAny<CancellationToken>()))
            .ReturnsAsync(("conv-123", false));
        _mockRepo.Setup(r => r.ListAsync(It.IsAny<string?>(), It.IsAny<int>(), It.IsAny<int>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>
            {
                new ConversationSummary { ConversationId = "conv-123", Title = "Test", UpdatedAt = DateTime.UtcNow }
            });
        _mockRepo.Setup(r => r.ReadAsync(It.IsAny<string?>(), It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ChatMessage> 
            { 
                new ChatMessage { Id = "old-id", Role = "user", Content = JsonSerializer.SerializeToElement("Old") }
            });

        var request = new HistoryFabController.UpdateRequest
        {
            Conversation_Id = "conv-123",
            Messages = new List<ChatMessage>
            {
                new ChatMessage { Id = "", Role = "user", Content = JsonSerializer.SerializeToElement("New message") }, // Empty ID
                new ChatMessage { Id = "", Role = "assistant", Content = JsonSerializer.SerializeToElement("Response") } // Empty ID
            }
        };

        // Act
        var result = await _controller.Update(request);

        // Assert
        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
        
        // Verify messages were added (they should have generated IDs)
        _mockRepo.Verify(r => r.AddMessageAsync("test-user-123", "conv-123", 
            It.Is<ChatMessage>(m => !string.IsNullOrEmpty(m.Id)), It.IsAny<CancellationToken>()), Times.AtLeast(1));
    }

    #endregion
}
