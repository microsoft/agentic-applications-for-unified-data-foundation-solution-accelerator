using CsApi.Interfaces;
using CsApi.Middleware;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Moq;
using Xunit;

namespace CsApi.Tests.Middleware;

public class RequestLoggingMiddlewareTests
{
    private readonly Mock<ILogger<RequestLoggingMiddleware>> _mockLogger;

    public RequestLoggingMiddlewareTests()
    {
        _mockLogger = new Mock<ILogger<RequestLoggingMiddleware>>();
    }

    [Fact]
    public async Task InvokeAsync_CallsNext()
    {
        // Arrange
        var nextCalled = false;
        RequestDelegate next = context =>
        {
            nextCalled = true;
            return Task.CompletedTask;
        };

        var middleware = new RequestLoggingMiddleware(next, _mockLogger.Object);
        var httpContext = new DefaultHttpContext();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.True(nextCalled);
    }

    [Fact]
    public async Task InvokeAsync_CompletesSuccessfully()
    {
        // Arrange
        RequestDelegate next = context => Task.CompletedTask;
        var middleware = new RequestLoggingMiddleware(next, _mockLogger.Object);
        var httpContext = new DefaultHttpContext();

        // Act & Assert (should not throw)
        await middleware.InvokeAsync(httpContext);
    }

    [Fact]
    public async Task InvokeAsync_PropagatesExceptionFromNext()
    {
        // Arrange
        RequestDelegate next = context => throw new Exception("Test exception");
        var middleware = new RequestLoggingMiddleware(next, _mockLogger.Object);
        var httpContext = new DefaultHttpContext();

        // Act & Assert
        await Assert.ThrowsAsync<Exception>(() => middleware.InvokeAsync(httpContext));
    }
}
