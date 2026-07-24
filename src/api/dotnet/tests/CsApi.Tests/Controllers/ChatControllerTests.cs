using CsApi.Auth;
using CsApi.Controllers;
using CsApi.Interfaces;
using CsApi.Models;
using CsApi.Repositories;
using CsApi.Services;
using CsApi.Utils;
using Azure.Core;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
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

        var conversationCache = new ExpCache<string, string>(
            maxSize: 1000,
            ttlSeconds: 3600.0,
            _mockConfiguration.Object,
            NullLogger<ExpCache<string, string>>.Instance,
            azureAIEndpoint: "https://test.azure.com");

        _controller = new ChatController(
            _mockUserContext.Object,
            _mockRepo.Object,
            _mockConfiguration.Object,
            NullLogger<ChatController>.Instance,
            conversationCache,
            Mock.Of<IAzureCredentialFactory>(),
            Mock.Of<IHttpClientFactory>());

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

    #region Chat Endpoint Guard Tests

    [Fact]
    public async Task Chat_EmptyQuery_WritesValidationError()
    {
        var request = new ChatRequest
        {
            Query = "",
            ConversationId = "conv-1"
        };

        await _controller.Chat(request, Mock.Of<IAgentFrameworkService>(), CancellationToken.None);

        _controller.HttpContext.Response.Body.Position = 0;
        using var reader = new StreamReader(_controller.HttpContext.Response.Body);
        var output = await reader.ReadToEndAsync();

        Assert.Contains("query is required", output, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Chat_EmptyConversationId_WritesValidationError()
    {
        var request = new ChatRequest
        {
            Query = "hello",
            ConversationId = ""
        };

        await _controller.Chat(request, Mock.Of<IAgentFrameworkService>(), CancellationToken.None);

        _controller.HttpContext.Response.Body.Position = 0;
        using var reader = new StreamReader(_controller.HttpContext.Response.Body);
        var output = await reader.ReadToEndAsync();

        Assert.Contains("Conversation ID is required", output, StringComparison.OrdinalIgnoreCase);
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

    #region FetchAzureSearchContent Tests

    [Fact]
    public async Task FetchAzureSearchContent_UrlMissing_ReturnsBadRequest()
    {
        // Arrange
        var body = JsonDocument.Parse("{\"source\":\"fallback\"}").RootElement.Clone();

        // Act
        var result = await _controller.FetchAzureSearchContent(body, CancellationToken.None);

        // Assert
        Assert.IsType<BadRequestObjectResult>(result);
    }

    [Fact]
    public async Task FetchAzureSearchContent_InvalidUrl_ReturnsBadRequest()
    {
        // Arrange
        var body = JsonDocument.Parse("{\"url\":\"not-a-url\"}").RootElement.Clone();

        // Act
        var result = await _controller.FetchAzureSearchContent(body, CancellationToken.None);

        // Assert
        Assert.IsType<BadRequestObjectResult>(result);
    }

    [Fact]
    public async Task FetchAzureSearchContent_NonAllowedHost_ReturnsForbidden()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_SEARCH_ENDPOINT"]).Returns("https://allowed.search.windows.net");
        var body = JsonDocument.Parse("{\"url\":\"https://evil.example.com/indexes/i/docs/d1?api-version=2024-07-01\"}").RootElement.Clone();

        // Act
        var result = await _controller.FetchAzureSearchContent(body, CancellationToken.None);

        // Assert
        var objectResult = Assert.IsType<ObjectResult>(result);
        Assert.Equal(403, objectResult.StatusCode);
    }

    [Fact]
    public async Task FetchAzureSearchContent_HttpScheme_ReturnsBadRequest()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_SEARCH_ENDPOINT"]).Returns("https://allowed.search.windows.net");
        var body = JsonDocument.Parse("{\"url\":\"http://allowed.search.windows.net/indexes/i/docs/d1?api-version=2024-07-01\"}").RootElement.Clone();

        // Act
        var result = await _controller.FetchAzureSearchContent(body, CancellationToken.None);

        // Assert
        Assert.IsType<BadRequestObjectResult>(result);
    }

    [Fact]
    public async Task FetchAzureSearchContent_MissingDocId_ReturnsBadRequest()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["AZURE_AI_SEARCH_ENDPOINT"]).Returns("https://allowed.search.windows.net");
        var body = JsonDocument.Parse("{\"url\":\"https://allowed.search.windows.net/indexes/i?api-version=2024-07-01\"}").RootElement.Clone();

        // Act
        var result = await _controller.FetchAzureSearchContent(body, CancellationToken.None);

        // Assert
        Assert.IsType<BadRequestObjectResult>(result);
    }

    [Fact]
    public async Task FetchAzureSearchContent_Success_ReturnsContentAndTitle()
    {
        // Arrange
        var mockConfig = new Mock<IConfiguration>();
        mockConfig.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns("https://test.azure.com");
        mockConfig.Setup(c => c["AZURE_AI_SEARCH_ENDPOINT"]).Returns("https://allowed.search.windows.net");

        var mockCredentialFactory = new Mock<IAzureCredentialFactory>();
        mockCredentialFactory
            .Setup(f => f.Create(It.IsAny<string?>(), It.IsAny<string?>()))
            .Returns(new StaticTokenCredential());

        using var handler = new StubHttpMessageHandler(_ =>
            new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent("{\"content\":\"doc body\",\"source\":\"doc-source\"}")
            });
        using var httpClient = new HttpClient(handler);
        var mockHttpFactory = new Mock<IHttpClientFactory>();
        mockHttpFactory.Setup(f => f.CreateClient(It.IsAny<string>())).Returns(httpClient);

        var cache = new ExpCache<string, string>(
            maxSize: 1000,
            ttlSeconds: 3600.0,
            mockConfig.Object,
            NullLogger<ExpCache<string, string>>.Instance,
            azureAIEndpoint: "https://test.azure.com");

        var controller = new ChatController(
            _mockUserContext.Object,
            _mockRepo.Object,
            mockConfig.Object,
            NullLogger<ChatController>.Instance,
            cache,
            mockCredentialFactory.Object,
            mockHttpFactory.Object);

        var body = JsonDocument.Parse("{\"url\":\"https://allowed.search.windows.net/indexes/my-index/docs/my-doc?api-version=2024-07-01\",\"source\":\"fallback\"}").RootElement.Clone();

        // Act
        var result = await controller.FetchAzureSearchContent(body, CancellationToken.None);

        // Assert
        var ok = Assert.IsType<OkObjectResult>(result);
        var json = JsonSerializer.Serialize(ok.Value);
        Assert.Contains("doc body", json);
        Assert.Contains("doc-source", json);
    }

    [Fact]
    public async Task FetchAzureSearchContent_DownstreamFailure_ReturnsOkWithError()
    {
        // Arrange
        var mockConfig = new Mock<IConfiguration>();
        mockConfig.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns("https://test.azure.com");
        mockConfig.Setup(c => c["AZURE_AI_SEARCH_ENDPOINT"]).Returns("https://allowed.search.windows.net");

        var mockCredentialFactory = new Mock<IAzureCredentialFactory>();
        mockCredentialFactory
            .Setup(f => f.Create(It.IsAny<string?>(), It.IsAny<string?>()))
            .Returns(new StaticTokenCredential());

        using var handler = new StubHttpMessageHandler(_ =>
            new HttpResponseMessage(HttpStatusCode.NotFound)
            {
                Content = new StringContent("not found")
            });
        using var httpClient = new HttpClient(handler);
        var mockHttpFactory = new Mock<IHttpClientFactory>();
        mockHttpFactory.Setup(f => f.CreateClient(It.IsAny<string>())).Returns(httpClient);

        var cache = new ExpCache<string, string>(
            maxSize: 1000,
            ttlSeconds: 3600.0,
            mockConfig.Object,
            NullLogger<ExpCache<string, string>>.Instance,
            azureAIEndpoint: "https://test.azure.com");

        var controller = new ChatController(
            _mockUserContext.Object,
            _mockRepo.Object,
            mockConfig.Object,
            NullLogger<ChatController>.Instance,
            cache,
            mockCredentialFactory.Object,
            mockHttpFactory.Object);

        var body = JsonDocument.Parse("{\"url\":\"https://allowed.search.windows.net/indexes/my-index/docs/my-doc?api-version=2024-07-01\",\"source\":\"fallback\"}").RootElement.Clone();

        // Act
        var result = await controller.FetchAzureSearchContent(body, CancellationToken.None);

        // Assert
        var ok = Assert.IsType<OkObjectResult>(result);
        var json = JsonSerializer.Serialize(ok.Value);
        Assert.Contains("HTTP 404", json);
    }

    private sealed class StaticTokenCredential : TokenCredential
    {
        public override AccessToken GetToken(TokenRequestContext requestContext, CancellationToken cancellationToken)
            => new("test-token", DateTimeOffset.UtcNow.AddMinutes(30));

        public override ValueTask<AccessToken> GetTokenAsync(TokenRequestContext requestContext, CancellationToken cancellationToken)
            => ValueTask.FromResult(new AccessToken("test-token", DateTimeOffset.UtcNow.AddMinutes(30)));
    }

    private sealed class StubHttpMessageHandler : HttpMessageHandler
    {
        private readonly Func<HttpRequestMessage, HttpResponseMessage> _handler;

        public StubHttpMessageHandler(Func<HttpRequestMessage, HttpResponseMessage> handler)
        {
            _handler = handler;
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            => Task.FromResult(_handler(request));
    }

    #endregion
}