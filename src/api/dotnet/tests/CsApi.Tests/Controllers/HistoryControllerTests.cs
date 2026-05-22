using CsApi.Controllers;
using CsApi.Interfaces;
using CsApi.Models;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using Moq;
using System.Text.Json;
using Xunit;

namespace CsApi.Tests.Controllers;

/// <summary>
/// Tests for HistoryController (Cosmos-only, mirrors Python history.py).
/// </summary>
public class HistoryControllerTests
{
    private readonly Mock<IConversationRepository> _mockRepo;
    private readonly Mock<ITitleGenerationService> _mockTitleService;
    private readonly Mock<ILogger<HistoryController>> _mockLogger;
    private readonly Mock<IUserContextAccessor> _mockUserContext;
    private readonly HistoryController _controller;

    public HistoryControllerTests()
    {
        _mockRepo = new Mock<IConversationRepository>();
        _mockTitleService = new Mock<ITitleGenerationService>();
        _mockLogger = new Mock<ILogger<HistoryController>>();
        _mockUserContext = new Mock<IUserContextAccessor>();

        _mockUserContext.Setup(u => u.GetCurrentUser())
            .Returns(new UserContext { UserPrincipalId = "test-user-123" });

        _controller = new HistoryController(
            _mockRepo.Object,
            _mockTitleService.Object,
            _mockLogger.Object,
            _mockUserContext.Object);
    }

    #region List Tests

    [Fact]
    public async Task List_ReturnsOkWithConversations()
    {
        var conversations = new List<ConversationSummary>
        {
            new() { ConversationId = "conv1", Title = "Test 1" },
            new() { ConversationId = "conv2", Title = "Test 2" }
        };
        _mockRepo.Setup(r => r.GetConversationsAsync("test-user-123", 0, 25, "DESC", It.IsAny<CancellationToken>()))
            .ReturnsAsync(conversations);

        var result = await _controller.List();

        var okResult = Assert.IsType<OkObjectResult>(result);
        var returnedList = Assert.IsAssignableFrom<IEnumerable<ConversationSummary>>(okResult.Value);
        Assert.Equal(2, returnedList.Count());
    }

    [Fact]
    public async Task List_WithOffset_UsesProvidedOffset()
    {
        _mockRepo.Setup(r => r.GetConversationsAsync("test-user-123", 10, 25, "DESC", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary> { new() { ConversationId = "c1", Title = "T" } });

        await _controller.List(offset: 10);

        _mockRepo.Verify(r => r.GetConversationsAsync("test-user-123", 10, 25, "DESC", It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task List_WithLimit_UsesProvidedLimit()
    {
        _mockRepo.Setup(r => r.GetConversationsAsync("test-user-123", 0, 50, "DESC", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary> { new() { ConversationId = "c1", Title = "T" } });

        await _controller.List(limit: 50);

        _mockRepo.Verify(r => r.GetConversationsAsync("test-user-123", 0, 50, "DESC", It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task List_EmptyConversations_ReturnsOkWithEmptyList()
    {
        _mockRepo.Setup(r => r.GetConversationsAsync(It.IsAny<string>(), It.IsAny<int>(), It.IsAny<int>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>());

        var result = await _controller.List();

        var okResult = Assert.IsType<OkObjectResult>(result);
        var list = Assert.IsAssignableFrom<IEnumerable<ConversationSummary>>(okResult.Value);
        Assert.Empty(list);
    }

    #endregion

    #region Read Tests

    [Fact]
    public async Task Read_ValidId_ReturnsOkWithMessages()
    {
        var msg = new ChatMessage { Id = "m1", Role = "user" };
        msg.SetContentFromString("Hello");
        _mockRepo.Setup(r => r.GetConversationAsync("test-user-123", "conv1", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new ConversationSummary { ConversationId = "conv1", Title = "Test" });
        _mockRepo.Setup(r => r.GetMessagesAsync("test-user-123", "conv1", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ChatMessage> { msg });

        var result = await _controller.Read("conv1");

        Assert.IsType<OkObjectResult>(result);
    }

    [Fact]
    public async Task Read_EmptyId_ReturnsBadRequest()
    {
        var result = await _controller.Read("");

        var objectResult = Assert.IsType<ObjectResult>(result);
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Read_NotFound_ReturnsNotFound()
    {
        _mockRepo.Setup(r => r.GetConversationAsync("test-user-123", "conv1", It.IsAny<CancellationToken>()))
            .ReturnsAsync((ConversationSummary?)null);

        var result = await _controller.Read("conv1");

        Assert.IsType<NotFoundObjectResult>(result);
    }

    #endregion

    #region Generate Tests

    [Fact]
    public async Task Generate_NewConversation_CreatesAndReturnsOk()
    {
        var userMsg = new ChatMessage { Role = "user" };
        userMsg.SetContentFromString("Hello");

        _mockTitleService.Setup(t => t.GenerateTitleAsync(It.IsAny<List<ChatMessage>>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync("Test Title");
        _mockRepo.Setup(r => r.CreateConversationAsync("test-user-123", null, "Test Title", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new ConversationSummary { ConversationId = "new-id", Title = "Test Title" });
        _mockRepo.Setup(r => r.CreateMessageAsync(It.IsAny<string>(), It.IsAny<string>(), It.IsAny<ChatMessage>(), It.IsAny<CancellationToken>()))
            .Returns(Task.CompletedTask);

        var req = new HistoryController.GenerateRequest
        {
            Messages = new List<ChatMessage> { userMsg }
        };

        var result = await _controller.Generate(req);

        Assert.IsType<OkObjectResult>(result);
    }

    [Fact]
    public async Task Generate_NoUserMessage_ReturnsBadRequest()
    {
        var assistantMsg = new ChatMessage { Role = "assistant" };
        assistantMsg.SetContentFromString("Hi");

        var req = new HistoryController.GenerateRequest
        {
            ConversationId = "conv1",
            Messages = new List<ChatMessage> { assistantMsg }
        };

        var result = await _controller.Generate(req);

        var objectResult = Assert.IsType<ObjectResult>(result);
        Assert.Equal(400, objectResult.StatusCode);
    }

    #endregion

    #region Update Tests

    [Fact]
    public async Task Update_ValidRequest_ReturnsOk()
    {
        var userMsg = new ChatMessage { Role = "user" };
        userMsg.SetContentFromString("Test");
        var assistantMsg = new ChatMessage { Role = "assistant" };
        assistantMsg.SetContentFromString("Response");

        _mockRepo.Setup(r => r.GetConversationAsync("test-user-123", "conv-123", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new ConversationSummary { ConversationId = "conv-123", Title = "Existing" });
        _mockRepo.Setup(r => r.CreateMessageAsync(It.IsAny<string>(), It.IsAny<string>(), It.IsAny<ChatMessage>(), It.IsAny<CancellationToken>()))
            .Returns(Task.CompletedTask);

        var req = new HistoryController.UpdateRequest
        {
            ConversationId = "conv-123",
            Messages = new List<ChatMessage> { userMsg, assistantMsg }
        };

        var result = await _controller.Update(req);

        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    [Fact]
    public async Task Update_EmptyConversationId_ReturnsBadRequest()
    {
        var req = new HistoryController.UpdateRequest
        {
            ConversationId = "",
            Messages = new List<ChatMessage> { new() { Role = "user" } }
        };

        var result = await _controller.Update(req);

        var objectResult = Assert.IsType<ObjectResult>(result);
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Update_NewConversation_CreatesWithTitle()
    {
        var userMsg = new ChatMessage { Role = "user" };
        userMsg.SetContentFromString("Hello world");

        _mockRepo.Setup(r => r.GetConversationAsync("test-user-123", "new-conv", It.IsAny<CancellationToken>()))
            .ReturnsAsync((ConversationSummary?)null);
        _mockTitleService.Setup(t => t.GenerateTitleAsync(It.IsAny<List<ChatMessage>>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync("Hello world");
        _mockRepo.Setup(r => r.CreateConversationAsync("test-user-123", "new-conv", "Hello world", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new ConversationSummary { ConversationId = "new-conv", Title = "Hello world" });
        _mockRepo.Setup(r => r.CreateMessageAsync(It.IsAny<string>(), It.IsAny<string>(), It.IsAny<ChatMessage>(), It.IsAny<CancellationToken>()))
            .Returns(Task.CompletedTask);

        var req = new HistoryController.UpdateRequest
        {
            ConversationId = "new-conv",
            Messages = new List<ChatMessage> { userMsg }
        };

        var result = await _controller.Update(req);

        Assert.IsType<OkObjectResult>(result);
        _mockRepo.Verify(r => r.CreateConversationAsync("test-user-123", "new-conv", "Hello world", It.IsAny<CancellationToken>()), Times.Once);
    }

    #endregion

    #region Delete Tests

    [Fact]
    public async Task Delete_ValidId_ReturnsOk()
    {
        _mockRepo.Setup(r => r.DeleteConversationAsync("test-user-123", "conv1", It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);

        var result = await _controller.Delete("conv1");

        Assert.IsType<OkObjectResult>(result);
    }

    [Fact]
    public async Task Delete_EmptyId_ReturnsBadRequest()
    {
        var result = await _controller.Delete("");

        var objectResult = Assert.IsType<ObjectResult>(result);
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Delete_NotFound_ReturnsNotFound()
    {
        _mockRepo.Setup(r => r.DeleteConversationAsync("test-user-123", "conv1", It.IsAny<CancellationToken>()))
            .ReturnsAsync(false);

        var result = await _controller.Delete("conv1");

        Assert.IsType<NotFoundObjectResult>(result);
    }

    #endregion

    #region DeleteAll Tests

    [Fact]
    public async Task DeleteAll_WithConversations_ReturnsOk()
    {
        _mockRepo.Setup(r => r.GetConversationsAsync("test-user-123", 0, 10000, "DESC", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>
            {
                new() { ConversationId = "c1" },
                new() { ConversationId = "c2" }
            });
        _mockRepo.Setup(r => r.DeleteConversationAsync("test-user-123", It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);

        var result = await _controller.DeleteAll();

        Assert.IsType<OkObjectResult>(result);
    }

    [Fact]
    public async Task DeleteAll_NoConversations_ReturnsNotFound()
    {
        _mockRepo.Setup(r => r.GetConversationsAsync("test-user-123", 0, 10000, "DESC", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new List<ConversationSummary>());

        var result = await _controller.DeleteAll();

        Assert.IsType<NotFoundObjectResult>(result);
    }

    #endregion

    #region Rename Tests

    [Fact]
    public async Task Rename_ValidRequest_ReturnsOk()
    {
        _mockRepo.Setup(r => r.GetConversationAsync("test-user-123", "conv-123", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new ConversationSummary { ConversationId = "conv-123", Title = "Old" });
        _mockRepo.Setup(r => r.UpsertConversationAsync(It.IsAny<string>(), It.IsAny<ConversationSummary>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);

        var req = new HistoryController.RenameRequest
        {
            ConversationId = "conv-123",
            Title = "New Title"
        };

        var result = await _controller.Rename(req);

        Assert.IsType<OkObjectResult>(result);
    }

    [Fact]
    public async Task Rename_EmptyConversationId_ReturnsBadRequest()
    {
        var req = new HistoryController.RenameRequest
        {
            ConversationId = "",
            Title = "New Title"
        };

        var result = await _controller.Rename(req);

        var objectResult = Assert.IsType<ObjectResult>(result);
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Rename_EmptyTitle_ReturnsBadRequest()
    {
        var req = new HistoryController.RenameRequest
        {
            ConversationId = "conv-123",
            Title = ""
        };

        var result = await _controller.Rename(req);

        var objectResult = Assert.IsType<ObjectResult>(result);
        Assert.Equal(400, objectResult.StatusCode);
    }

    [Fact]
    public async Task Rename_NotFound_ReturnsNotFound()
    {
        _mockRepo.Setup(r => r.GetConversationAsync("test-user-123", "conv-123", It.IsAny<CancellationToken>()))
            .ReturnsAsync((ConversationSummary?)null);

        var req = new HistoryController.RenameRequest
        {
            ConversationId = "conv-123",
            Title = "New Title"
        };

        var result = await _controller.Rename(req);

        Assert.IsType<NotFoundObjectResult>(result);
    }

    #endregion

    #region MessageFeedback Tests

    [Fact]
    public async Task MessageFeedback_ValidRequest_ReturnsOk()
    {
        _mockRepo.Setup(r => r.UpdateMessageFeedbackAsync("test-user-123", "msg-1", "positive", It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);

        var req = new HistoryController.MessageFeedbackRequest
        {
            MessageId = "msg-1",
            MessageFeedback = "positive"
        };

        var result = await _controller.MessageFeedback(req);

        Assert.IsType<OkObjectResult>(result);
    }

    [Fact]
    public async Task MessageFeedback_NotFound_ReturnsNotFound()
    {
        _mockRepo.Setup(r => r.UpdateMessageFeedbackAsync("test-user-123", "msg-1", "positive", It.IsAny<CancellationToken>()))
            .ReturnsAsync(false);

        var req = new HistoryController.MessageFeedbackRequest
        {
            MessageId = "msg-1",
            MessageFeedback = "positive"
        };

        var result = await _controller.MessageFeedback(req);

        Assert.IsType<NotFoundObjectResult>(result);
    }

    [Fact]
    public async Task MessageFeedback_EmptyMessageId_ReturnsBadRequest()
    {
        var req = new HistoryController.MessageFeedbackRequest
        {
            MessageId = "",
            MessageFeedback = "positive"
        };

        var result = await _controller.MessageFeedback(req);

        var objectResult = Assert.IsType<ObjectResult>(result);
        Assert.Equal(400, objectResult.StatusCode);
    }

    #endregion

    #region Clear Tests

    [Fact]
    public async Task Clear_ValidRequest_ReturnsOk()
    {
        _mockRepo.Setup(r => r.GetConversationAsync("test-user-123", "conv-123", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new ConversationSummary { ConversationId = "conv-123", Title = "Test" });
        _mockRepo.Setup(r => r.ClearMessagesAsync("test-user-123", "conv-123", It.IsAny<CancellationToken>()))
            .ReturnsAsync(true);

        var req = new HistoryController.ClearRequest { ConversationId = "conv-123" };

        var result = await _controller.Clear(req);

        Assert.IsType<OkObjectResult>(result);
    }

    [Fact]
    public async Task Clear_NotFound_ReturnsNotFound()
    {
        _mockRepo.Setup(r => r.GetConversationAsync("test-user-123", "conv-123", It.IsAny<CancellationToken>()))
            .ReturnsAsync((ConversationSummary?)null);

        var req = new HistoryController.ClearRequest { ConversationId = "conv-123" };

        var result = await _controller.Clear(req);

        Assert.IsType<NotFoundObjectResult>(result);
    }

    #endregion

    #region Ensure Tests

    [Fact]
    public async Task Ensure_Configured_ReturnsOkWithTrue()
    {
        _mockRepo.Setup(r => r.EnsureConfiguredAsync()).ReturnsAsync(true);

        var result = await _controller.Ensure();

        var okResult = Assert.IsType<OkObjectResult>(result);
        Assert.NotNull(okResult.Value);
    }

    [Fact]
    public async Task Ensure_NotConfigured_ReturnsOkWithFalse()
    {
        _mockRepo.Setup(r => r.EnsureConfiguredAsync()).ReturnsAsync(false);

        var result = await _controller.Ensure();

        Assert.IsType<OkObjectResult>(result);
    }

    #endregion
}
