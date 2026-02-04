using CsApi.Controllers;
using CsApi.Interfaces;
using CsApi.Models;
using CsApi.Repositories;
using CsApi.Services;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Configuration;
using Moq;
using System.Text.Json;
using Xunit;

namespace CsApi.Tests.Controllers;

public class ChatControllerTests
{
    private readonly Mock<IUserContextAccessor> _mockUserContext;
    private readonly Mock<ISqlConversationRepository> _mockRepo;
    private readonly Mock<IConfiguration> _mockConfiguration;
    private readonly ChatController _controller;

    public ChatControllerTests()
    {
        _mockUserContext = new Mock<IUserContextAccessor>();
        _mockRepo = new Mock<ISqlConversationRepository>();
        _mockConfiguration = new Mock<IConfiguration>();

        _mockUserContext.Setup(u => u.GetCurrentUser())
            .Returns(new UserContext { UserPrincipalId = "test-user-123" });

        _mockConfiguration.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"])
            .Returns("https://test.azure.com");

        _controller = new ChatController(
            _mockUserContext.Object,
            _mockRepo.Object,
            _mockConfiguration.Object);

        // Setup default HttpContext
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();
        _controller.ControllerContext = new ControllerContext
        {
            HttpContext = httpContext
        };
    }

    #region LayoutConfig Tests

    [Fact]
    public void LayoutConfig_ValidJson_ReturnsJsonResult()
    {
        // Arrange
        var mockConfig = new Mock<IConfiguration>();
        mockConfig.Setup(c => c["REACT_APP_LAYOUT_CONFIG"])
            .Returns("{\"header\":\"test\",\"footer\":\"footer\"}");

        // Act
        var result = _controller.LayoutConfig(mockConfig.Object);

        // Assert
        Assert.IsType<JsonResult>(result);
    }

    [Fact]
    public void LayoutConfig_EmptyConfig_ReturnsBadRequest()
    {
        // Arrange
        var mockConfig = new Mock<IConfiguration>();
        mockConfig.Setup(c => c["REACT_APP_LAYOUT_CONFIG"])
            .Returns(string.Empty);

        // Act
        var result = _controller.LayoutConfig(mockConfig.Object);

        // Assert
        var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
        Assert.NotNull(badRequestResult.Value);
    }

    [Fact]
    public void LayoutConfig_NullConfig_ReturnsBadRequest()
    {
        // Arrange
        var mockConfig = new Mock<IConfiguration>();
        mockConfig.Setup(c => c["REACT_APP_LAYOUT_CONFIG"])
            .Returns((string?)null);

        // Act
        var result = _controller.LayoutConfig(mockConfig.Object);

        // Assert
        var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
        Assert.NotNull(badRequestResult.Value);
    }

    [Fact]
    public void LayoutConfig_InvalidJson_ReturnsBadRequest()
    {
        // Arrange
        var mockConfig = new Mock<IConfiguration>();
        mockConfig.Setup(c => c["REACT_APP_LAYOUT_CONFIG"])
            .Returns("not valid json {");

        // Act
        var result = _controller.LayoutConfig(mockConfig.Object);

        // Assert
        var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
        Assert.NotNull(badRequestResult.Value);
    }

    [Fact]
    public void LayoutConfig_NestedJson_ReturnsJsonResult()
    {
        // Arrange
        var mockConfig = new Mock<IConfiguration>();
        mockConfig.Setup(c => c["REACT_APP_LAYOUT_CONFIG"])
            .Returns("{\"header\":{\"title\":\"My App\",\"logo\":\"logo.png\"},\"sidebar\":{\"width\":200}}");

        // Act
        var result = _controller.LayoutConfig(mockConfig.Object);

        // Assert
        Assert.IsType<JsonResult>(result);
    }

    [Fact]
    public void LayoutConfig_ArrayJson_ReturnsJsonResult()
    {
        // Arrange
        var mockConfig = new Mock<IConfiguration>();
        mockConfig.Setup(c => c["REACT_APP_LAYOUT_CONFIG"])
            .Returns("[{\"name\":\"item1\"},{\"name\":\"item2\"}]");

        // Act
        var result = _controller.LayoutConfig(mockConfig.Object);

        // Assert
        Assert.IsType<JsonResult>(result);
    }

    #endregion

    #region DisplayChartDefault Tests

    [Fact]
    public void DisplayChartDefault_ValidValue_ReturnsJsonResult()
    {
        // Arrange
        var mockConfig = new Mock<IConfiguration>();
        mockConfig.Setup(c => c["DISPLAY_CHART_DEFAULT"])
            .Returns("true");

        // Act
        var result = _controller.DisplayChartDefault(mockConfig.Object);

        // Assert
        Assert.IsType<JsonResult>(result);
    }

    [Fact]
    public void DisplayChartDefault_FalseValue_ReturnsJsonResult()
    {
        // Arrange
        var mockConfig = new Mock<IConfiguration>();
        mockConfig.Setup(c => c["DISPLAY_CHART_DEFAULT"])
            .Returns("false");

        // Act
        var result = _controller.DisplayChartDefault(mockConfig.Object);

        // Assert
        Assert.IsType<JsonResult>(result);
    }

    [Fact]
    public void DisplayChartDefault_EmptyValue_ReturnsBadRequest()
    {
        // Arrange
        var mockConfig = new Mock<IConfiguration>();
        mockConfig.Setup(c => c["DISPLAY_CHART_DEFAULT"])
            .Returns(string.Empty);

        // Act
        var result = _controller.DisplayChartDefault(mockConfig.Object);

        // Assert
        var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
        Assert.NotNull(badRequestResult.Value);
    }

    [Fact]
    public void DisplayChartDefault_NullValue_ReturnsBadRequest()
    {
        // Arrange
        var mockConfig = new Mock<IConfiguration>();
        mockConfig.Setup(c => c["DISPLAY_CHART_DEFAULT"])
            .Returns((string?)null);

        // Act
        var result = _controller.DisplayChartDefault(mockConfig.Object);

        // Assert
        var badRequestResult = Assert.IsType<BadRequestObjectResult>(result);
        Assert.NotNull(badRequestResult.Value);
    }

    [Fact]
    public void DisplayChartDefault_CustomValue_ReturnsValueInResponse()
    {
        // Arrange
        var mockConfig = new Mock<IConfiguration>();
        mockConfig.Setup(c => c["DISPLAY_CHART_DEFAULT"])
            .Returns("custom_value");

        // Act
        var result = _controller.DisplayChartDefault(mockConfig.Object);

        // Assert
        var jsonResult = Assert.IsType<JsonResult>(result);
        Assert.NotNull(jsonResult.Value);
    }

    #endregion
}
