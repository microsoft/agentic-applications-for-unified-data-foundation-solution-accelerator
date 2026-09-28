using System.Security.Claims;
using CsApi.Auth;
using CsApi.Interfaces;
using Microsoft.AspNetCore.Http;
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
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns((HttpContext?)null);

        var result = _accessor.GetCurrentUser();

        Assert.NotNull(result);
        Assert.Null(result.UserPrincipalId);
        Assert.Null(result.UserName);
    }

    [Fact]
    public void GetCurrentUser_UnauthenticatedContext_ReturnsEmptyUserContext()
    {
        var httpContext = new DefaultHttpContext();
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        var result = _accessor.GetCurrentUser();

        Assert.NotNull(result);
        Assert.Null(result.UserPrincipalId);
        Assert.Null(result.UserName);
    }

    [Fact]
    public void GetCurrentUser_SpoofedPrincipalHeaders_AreIgnored()
    {
        // Attacker sets these headers directly. Because the request has no
        // authenticated principal, the accessor must ignore them.
        var httpContext = new DefaultHttpContext();
        httpContext.Request.Headers["x-ms-client-principal-id"] = "attacker-user";
        httpContext.Request.Headers["x-ms-client-principal-name"] = "attacker@evil.com";
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        var result = _accessor.GetCurrentUser();

        Assert.Null(result.UserPrincipalId);
        Assert.Null(result.UserName);
    }

    [Fact]
    public void GetCurrentUser_AuthenticatedPrincipal_ReturnsIdentityFromClaims()
    {
        var httpContext = BuildAuthenticatedContext(new[]
        {
            new Claim("oid", "user-oid-1"),
            new Claim("preferred_username", "user@example.com"),
            new Claim("tid", "tenant-1")
        });
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        var result = _accessor.GetCurrentUser();

        Assert.Equal("user-oid-1", result.UserPrincipalId);
        Assert.Equal("user@example.com", result.UserName);
        Assert.Equal("aad", result.AuthProvider);
    }

    [Fact]
    public void GetCurrentUser_FallsBackToSubClaim_WhenOidMissing()
    {
        var httpContext = BuildAuthenticatedContext(new[]
        {
            new Claim("sub", "subject-only"),
            new Claim("preferred_username", "sub@example.com")
        });
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        var result = _accessor.GetCurrentUser();

        Assert.Equal("subject-only", result.UserPrincipalId);
        Assert.Equal("sub@example.com", result.UserName);
    }

    [Fact]
    public void GetCurrentUser_UsesUpnWhenPreferredUsernameMissing()
    {
        var httpContext = BuildAuthenticatedContext(new[]
        {
            new Claim("oid", "user-upn"),
            new Claim("upn", "upn.user@example.com")
        });
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        var result = _accessor.GetCurrentUser();

        Assert.Equal("user-upn", result.UserPrincipalId);
        Assert.Equal("upn.user@example.com", result.UserName);
    }

    [Fact]
    public void GetCurrentUser_DoesNotUseSpoofedHeaders_EvenForAuthenticatedUser()
    {
        var httpContext = BuildAuthenticatedContext(new[]
        {
            new Claim("oid", "real-user"),
            new Claim("preferred_username", "real@example.com")
        });
        httpContext.Request.Headers["x-ms-client-principal-id"] = "attacker-user";
        httpContext.Request.Headers["x-ms-client-principal-name"] = "attacker@evil.com";
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        var result = _accessor.GetCurrentUser();

        Assert.Equal("real-user", result.UserPrincipalId);
        Assert.Equal("real@example.com", result.UserName);
    }

    [Fact]
    public void GetCurrentUser_UsesBearerTokenAsAccessToken()
    {
        var httpContext = BuildAuthenticatedContext(new[]
        {
            new Claim("oid", "bearer-user")
        });
        httpContext.Request.Headers.Authorization = "Bearer access-token-123";
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        var result = _accessor.GetCurrentUser();

        Assert.Equal("bearer-user", result.UserPrincipalId);
        Assert.Equal("access-token-123", result.AadAccessToken);
    }

    [Fact]
    public void GetCurrentUser_ImplementsIUserContextAccessor()
    {
        Assert.IsAssignableFrom<IUserContextAccessor>(_accessor);
    }

    [Fact]
    public void GetCurrentUser_ObjectIdentifierClaim_IsRecognized()
    {
        var httpContext = BuildAuthenticatedContext(new[]
        {
            new Claim(
                "http://schemas.microsoft.com/identity/claims/objectidentifier",
                "long-form-oid")
        });
        _mockHttpContextAccessor.Setup(h => h.HttpContext).Returns(httpContext);

        var result = _accessor.GetCurrentUser();

        Assert.Equal("long-form-oid", result.UserPrincipalId);
    }

    private static HttpContext BuildAuthenticatedContext(IEnumerable<Claim> claims)
    {
        var identity = new ClaimsIdentity(claims, "TestAuth");
        var principal = new ClaimsPrincipal(identity);
        return new DefaultHttpContext { User = principal };
    }
}
