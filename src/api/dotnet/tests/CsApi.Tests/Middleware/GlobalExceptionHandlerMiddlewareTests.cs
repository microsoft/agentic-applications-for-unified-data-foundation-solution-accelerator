using CsApi.Middleware;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Moq;
using System.Text.Json;
using Xunit;

namespace CsApi.Tests.Middleware;

public class GlobalExceptionHandlerMiddlewareTests
{
    private readonly Mock<ILogger<GlobalExceptionHandlerMiddleware>> _mockLogger;
    private readonly Mock<IConfiguration> _mockConfiguration;

    public GlobalExceptionHandlerMiddlewareTests()
    {
        _mockLogger = new Mock<ILogger<GlobalExceptionHandlerMiddleware>>();
        _mockConfiguration = new Mock<IConfiguration>();
    }

    private GlobalExceptionHandlerMiddleware CreateMiddleware(RequestDelegate next)
    {
        return new GlobalExceptionHandlerMiddleware(next, _mockLogger.Object, _mockConfiguration.Object);
    }

    [Fact]
    public async Task InvokeAsync_NoException_CallsNextAndCompletes()
    {
        // Arrange
        var nextCalled = false;
        RequestDelegate next = context =>
        {
            nextCalled = true;
            return Task.CompletedTask;
        };

        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.True(nextCalled);
    }

    [Fact]
    public async Task InvokeAsync_ArgumentException_Returns400()
    {
        // Arrange
        RequestDelegate next = context => throw new ArgumentException("Invalid argument");
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(400, httpContext.Response.StatusCode);
        Assert.Equal("application/problem+json", httpContext.Response.ContentType);
    }

    [Fact]
    public async Task InvokeAsync_ArgumentNullException_Returns400()
    {
        // Arrange
        RequestDelegate next = context => throw new ArgumentNullException("parameter");
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(400, httpContext.Response.StatusCode);
    }

    [Fact]
    public async Task InvokeAsync_UnauthorizedAccessException_Returns401()
    {
        // Arrange
        RequestDelegate next = context => throw new UnauthorizedAccessException();
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(401, httpContext.Response.StatusCode);
    }

    [Fact]
    public async Task InvokeAsync_DirectoryServiceException_Returns403()
    {
        // Arrange
        RequestDelegate next = context => throw new DirectoryServiceException("Access denied");
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(403, httpContext.Response.StatusCode);
    }

    [Fact]
    public async Task InvokeAsync_FileNotFoundException_Returns404()
    {
        // Arrange
        RequestDelegate next = context => throw new FileNotFoundException();
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(404, httpContext.Response.StatusCode);
    }

    [Fact]
    public async Task InvokeAsync_DirectoryNotFoundException_Returns404()
    {
        // Arrange
        RequestDelegate next = context => throw new DirectoryNotFoundException();
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(404, httpContext.Response.StatusCode);
    }

    [Fact]
    public async Task InvokeAsync_InvalidOperationException_Returns409()
    {
        // Arrange
        RequestDelegate next = context => throw new InvalidOperationException();
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(409, httpContext.Response.StatusCode);
    }

    [Fact]
    public async Task InvokeAsync_NotImplementedException_Returns501()
    {
        // Arrange
        RequestDelegate next = context => throw new NotImplementedException();
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(501, httpContext.Response.StatusCode);
    }

    [Fact]
    public async Task InvokeAsync_TimeoutException_Returns408()
    {
        // Arrange
        RequestDelegate next = context => throw new TimeoutException();
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(408, httpContext.Response.StatusCode);
    }

    [Fact]
    public async Task InvokeAsync_TaskCanceledException_Returns408()
    {
        // Arrange
        RequestDelegate next = context => throw new TaskCanceledException();
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(408, httpContext.Response.StatusCode);
    }

    [Fact]
    public async Task InvokeAsync_OperationCanceledException_Returns499()
    {
        // Arrange
        RequestDelegate next = context => throw new OperationCanceledException();
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(499, httpContext.Response.StatusCode);
    }

    [Fact]
    public async Task InvokeAsync_GenericException_Returns500()
    {
        // Arrange
        RequestDelegate next = context => throw new Exception("Unknown error");
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(500, httpContext.Response.StatusCode);
    }

    [Fact]
    public async Task InvokeAsync_DevEnvironment_IncludesStackTrace()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("dev");
        RequestDelegate next = context => throw new Exception("Test error");
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        var memoryStream = new MemoryStream();
        httpContext.Response.Body = memoryStream;

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        memoryStream.Position = 0;
        using var reader = new StreamReader(memoryStream);
        var responseBody = await reader.ReadToEndAsync();
        Assert.Contains("stackTrace", responseBody);
    }

    [Fact]
    public async Task InvokeAsync_ProdEnvironment_ExcludesStackTrace()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("prod");
        RequestDelegate next = context => throw new Exception("Test error");
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        var memoryStream = new MemoryStream();
        httpContext.Response.Body = memoryStream;

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        memoryStream.Position = 0;
        using var reader = new StreamReader(memoryStream);
        var responseBody = await reader.ReadToEndAsync();
        Assert.DoesNotContain("stackTrace", responseBody);
    }

    [Fact]
    public async Task InvokeAsync_HttpRequestException_Returns502()
    {
        // Arrange
        RequestDelegate next = context => throw new HttpRequestException("External service failed");
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(502, httpContext.Response.StatusCode);
    }

    [Fact]
    public async Task InvokeAsync_HttpRequestExceptionWithTimeout_Returns408()
    {
        // Arrange
        RequestDelegate next = context => throw new HttpRequestException("Request timeout occurred");
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.Equal(408, httpContext.Response.StatusCode);
    }

    [Fact]
    public async Task InvokeAsync_ReturnsValidJson()
    {
        // Arrange
        RequestDelegate next = context => throw new Exception("Test error");
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        var memoryStream = new MemoryStream();
        httpContext.Response.Body = memoryStream;

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        memoryStream.Position = 0;
        using var reader = new StreamReader(memoryStream);
        var responseBody = await reader.ReadToEndAsync();
        
        // Should be valid JSON
        using var jsonDoc = JsonDocument.Parse(responseBody);
        Assert.NotNull(jsonDoc);
    }

    [Fact]
    public async Task InvokeAsync_IncludesRequestPath()
    {
        // Arrange
        RequestDelegate next = context => throw new Exception("Test error");
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Request.Path = "/api/test";
        var memoryStream = new MemoryStream();
        httpContext.Response.Body = memoryStream;

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        memoryStream.Position = 0;
        using var reader = new StreamReader(memoryStream);
        var responseBody = await reader.ReadToEndAsync();
        Assert.Contains("/api/test", responseBody);
    }

    [Fact]
    public async Task InvokeAsync_LogsError()
    {
        // Arrange
        RequestDelegate next = context => throw new Exception("Test error");
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        httpContext.Response.Body = new MemoryStream();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        _mockLogger.Verify(
            x => x.Log(
                LogLevel.Error,
                It.IsAny<EventId>(),
                It.Is<It.IsAnyType>((o, t) => true),
                It.IsAny<Exception>(),
                It.IsAny<Func<It.IsAnyType, Exception?, string>>()),
            Times.Once);
    }

    [Fact]
    public async Task InvokeAsync_WithInnerException_DevEnvironmentIncludesInnerException()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("dev");
        var innerException = new InvalidOperationException("Inner error");
        RequestDelegate next = context => throw new Exception("Outer error", innerException);
        var middleware = CreateMiddleware(next);
        var httpContext = new DefaultHttpContext();
        var memoryStream = new MemoryStream();
        httpContext.Response.Body = memoryStream;

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        memoryStream.Position = 0;
        using var reader = new StreamReader(memoryStream);
        var responseBody = await reader.ReadToEndAsync();
        Assert.Contains("innerException", responseBody);
    }
}

public class DirectoryServiceExceptionTests
{
    [Fact]
    public void Constructor_WithMessage_SetsMessage()
    {
        // Arrange & Act
        var exception = new DirectoryServiceException("Test message");

        // Assert
        Assert.Equal("Test message", exception.Message);
    }

    [Fact]
    public void Constructor_WithMessageAndInnerException_SetsBoth()
    {
        // Arrange
        var innerException = new Exception("Inner");
        
        // Act
        var exception = new DirectoryServiceException("Outer message", innerException);

        // Assert
        Assert.Equal("Outer message", exception.Message);
        Assert.Same(innerException, exception.InnerException);
    }
}
