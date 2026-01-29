using CsApi.Auth;
using CsApi.Interfaces;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Primitives;
using Moq;
using Xunit;

namespace CsApi.Tests.Auth;

public class HeaderUserContextAccessorTests
{
    private readonly Mock<IHttpContextAccessor> _mockHttpContextAccessor;
    private readonly HeaderUserContextAccessor _accessor;

    public HeaderUserContextAccessorTests()
    {
        _mockHttpContextAccessor = new Mock<IHttpContextAccessor>();
        _accessor = new HeaderUserContextAccessor(_mockHttpContextAccessor.Object);
    }

    [Fact]
    public void GetCurrentUser_NullHttpContext_ReturnsEmptyUserContext()
    {
        // Arrange
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns((HttpContext?)null);

        // Act
        var result = _accessor.GetCurrentUser();

        // Assert
        Assert.NotNull(result);
        Assert.Null(result.UserPrincipalId);
        Assert.Null(result.UserName);
    }

    [Fact]
    public void GetCurrentUser_NoPrincipalHeader_ReturnsSampleUser()
    {
        // Arrange
        var httpContext = new DefaultHttpContext();
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        // Act
        var result = _accessor.GetCurrentUser();

        // Assert
        Assert.NotNull(result);
        Assert.Equal("00000000-0000-0000-0000-000000000000", result.UserPrincipalId);
        Assert.Equal("sample.user@contoso.com", result.UserName);
        Assert.Equal("aad", result.AuthProvider);
    }

    [Fact]
    public void GetCurrentUser_WithPrincipalIdHeader_ReturnsUserFromHeaders()
    {
        // Arrange
        var httpContext = new DefaultHttpContext();
        httpContext.Request.Headers["x-ms-client-principal-id"] = "user-123";
        httpContext.Request.Headers["x-ms-client-principal-name"] = "testuser@example.com";
        httpContext.Request.Headers["x-ms-client-principal-idp"] = "aad";
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        // Act
        var result = _accessor.GetCurrentUser();

        // Assert
        Assert.Equal("user-123", result.UserPrincipalId);
        Assert.Equal("testuser@example.com", result.UserName);
        Assert.Equal("aad", result.AuthProvider);
    }

    [Fact]
    public void GetCurrentUser_WithAllHeaders_ReturnsCompleteUserContext()
    {
        // Arrange
        var httpContext = new DefaultHttpContext();
        httpContext.Request.Headers["x-ms-client-principal-id"] = "user-456";
        httpContext.Request.Headers["x-ms-client-principal-name"] = "complete@example.com";
        httpContext.Request.Headers["x-ms-client-principal-idp"] = "azure-ad";
        httpContext.Request.Headers["x-ms-token-aad-id-token"] = "token-xyz";
        httpContext.Request.Headers["x-ms-client-principal"] = "base64-encoded-principal";
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        // Act
        var result = _accessor.GetCurrentUser();

        // Assert
        Assert.Equal("user-456", result.UserPrincipalId);
        Assert.Equal("complete@example.com", result.UserName);
        Assert.Equal("azure-ad", result.AuthProvider);
        Assert.Equal("token-xyz", result.AuthToken);
        Assert.Equal("base64-encoded-principal", result.ClientPrincipalB64);
        Assert.Equal("token-xyz", result.AadIdToken);
    }

    [Fact]
    public void GetCurrentUser_WithPartialHeaders_ReturnsPartialUserContext()
    {
        // Arrange
        var httpContext = new DefaultHttpContext();
        httpContext.Request.Headers["x-ms-client-principal-id"] = "user-789";
        // No other headers
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        // Act
        var result = _accessor.GetCurrentUser();

        // Assert
        Assert.Equal("user-789", result.UserPrincipalId);
        Assert.Equal(string.Empty, result.UserName);
        Assert.Equal(string.Empty, result.AuthProvider);
        Assert.Null(result.AuthToken);
    }

    [Fact]
    public void GetCurrentUser_EmptyPrincipalId_ReturnsSampleUser()
    {
        // Arrange
        var httpContext = new DefaultHttpContext();
        // Headers without x-ms-client-principal-id
        httpContext.Request.Headers["x-ms-client-principal-name"] = "some@user.com";
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        // Act
        var result = _accessor.GetCurrentUser();

        // Assert
        Assert.Equal("00000000-0000-0000-0000-000000000000", result.UserPrincipalId);
        Assert.Equal("sample.user@contoso.com", result.UserName);
    }

    [Fact]
    public void GetCurrentUser_ImplementsIUserContextAccessor()
    {
        // Assert
        Assert.IsAssignableFrom<IUserContextAccessor>(_accessor);
    }

    [Fact]
    public void GetCurrentUser_MultipleCallsReturnsConsistentResult()
    {
        // Arrange
        var httpContext = new DefaultHttpContext();
        httpContext.Request.Headers["x-ms-client-principal-id"] = "consistent-user";
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        // Act
        var result1 = _accessor.GetCurrentUser();
        var result2 = _accessor.GetCurrentUser();

        // Assert
        Assert.Equal(result1.UserPrincipalId, result2.UserPrincipalId);
    }

    [Fact]
    public void GetCurrentUser_GuidStylePrincipalId_ReturnsAsIs()
    {
        // Arrange
        var guidId = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
        var httpContext = new DefaultHttpContext();
        httpContext.Request.Headers["x-ms-client-principal-id"] = guidId;
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        // Act
        var result = _accessor.GetCurrentUser();

        // Assert
        Assert.Equal(guidId, result.UserPrincipalId);
    }

    [Fact]
    public void GetCurrentUser_WithMicrosoftProvider_ReturnsCorrectProvider()
    {
        // Arrange
        var httpContext = new DefaultHttpContext();
        httpContext.Request.Headers["x-ms-client-principal-id"] = "ms-user";
        httpContext.Request.Headers["x-ms-client-principal-idp"] = "microsoft";
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        // Act
        var result = _accessor.GetCurrentUser();

        // Assert
        Assert.Equal("microsoft", result.AuthProvider);
    }
}
