using CsApi.Interfaces;
using CsApi.Middleware;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;
using Moq;
using Xunit;

namespace CsApi.Tests.Middleware;

public class UserContextMiddlewareTests
{
    private readonly Mock<ILogger<UserContextMiddleware>> _mockLogger;
    private readonly Mock<IUserContextAccessor> _mockUserContextAccessor;

    public UserContextMiddlewareTests()
    {
        _mockLogger = new Mock<ILogger<UserContextMiddleware>>();
        _mockUserContextAccessor = new Mock<IUserContextAccessor>();
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

        _mockUserContextAccessor.Setup(u => u.GetCurrentUser())
            .Returns(new UserContext { UserPrincipalId = "test-user" });

        var middleware = new UserContextMiddleware(next, _mockLogger.Object, _mockUserContextAccessor.Object);
        var httpContext = new DefaultHttpContext();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.True(nextCalled);
    }

    [Fact]
    public async Task InvokeAsync_SetsUserContextInItems()
    {
        // Arrange
        var expectedUser = new UserContext 
        { 
            UserPrincipalId = "test-user-123",
            UserName = "test@example.com" 
        };
        
        RequestDelegate next = context => Task.CompletedTask;
        
        _mockUserContextAccessor.Setup(u => u.GetCurrentUser())
            .Returns(expectedUser);

        var middleware = new UserContextMiddleware(next, _mockLogger.Object, _mockUserContextAccessor.Object);
        var httpContext = new DefaultHttpContext();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.True(httpContext.Items.ContainsKey(nameof(UserContext)));
        var storedUser = httpContext.Items[nameof(UserContext)] as UserContext;
        Assert.NotNull(storedUser);
        Assert.Equal(expectedUser.UserPrincipalId, storedUser!.UserPrincipalId);
        Assert.Equal(expectedUser.UserName, storedUser!.UserName);
    }

    [Fact]
    public async Task InvokeAsync_GetsUserFromAccessor()
    {
        // Arrange
        RequestDelegate next = context => Task.CompletedTask;
        
        _mockUserContextAccessor.Setup(u => u.GetCurrentUser())
            .Returns(new UserContext());

        var middleware = new UserContextMiddleware(next, _mockLogger.Object, _mockUserContextAccessor.Object);
        var httpContext = new DefaultHttpContext();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        _mockUserContextAccessor.Verify(u => u.GetCurrentUser(), Times.Once);
    }

    [Fact]
    public async Task InvokeAsync_PropagatesExceptionFromNext()
    {
        // Arrange
        RequestDelegate next = context => throw new Exception("Test exception");
        
        _mockUserContextAccessor.Setup(u => u.GetCurrentUser())
            .Returns(new UserContext());

        var middleware = new UserContextMiddleware(next, _mockLogger.Object, _mockUserContextAccessor.Object);
        var httpContext = new DefaultHttpContext();

        // Act & Assert
        await Assert.ThrowsAsync<Exception>(() => middleware.InvokeAsync(httpContext));
    }

    [Fact]
    public async Task InvokeAsync_WithNullUserContext_StillCallsNext()
    {
        // Arrange
        var nextCalled = false;
        RequestDelegate next = context =>
        {
            nextCalled = true;
            return Task.CompletedTask;
        };
        
        _mockUserContextAccessor.Setup(u => u.GetCurrentUser())
            .Returns((UserContext?)null!);

        var middleware = new UserContextMiddleware(next, _mockLogger.Object, _mockUserContextAccessor.Object);
        var httpContext = new DefaultHttpContext();

        // Act
        await middleware.InvokeAsync(httpContext);

        // Assert
        Assert.True(nextCalled);
    }
}
