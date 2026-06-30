using CsApi.Interfaces;
using Xunit;

namespace CsApi.Tests.Interfaces;

public class UserContextTests
{
    [Fact]
    public void Constructor_SetsNullDefaults()
    {
        // Act
        var context = new UserContext();

        // Assert
        Assert.Null(context.UserPrincipalId);
        Assert.Null(context.UserName);
        Assert.Null(context.AuthProvider);
        Assert.Null(context.AuthToken);
        Assert.Null(context.ClientPrincipalB64);
        Assert.Null(context.AadIdToken);
    }

    [Fact]
    public void Properties_CanBeSet()
    {
        // Arrange & Act
        var context = new UserContext
        {
            UserPrincipalId = "user-123",
            UserName = "test@example.com",
            AuthProvider = "aad",
            AuthToken = "token-xyz",
            ClientPrincipalB64 = "base64data",
            AadIdToken = "id-token"
        };

        // Assert
        Assert.Equal("user-123", context.UserPrincipalId);
        Assert.Equal("test@example.com", context.UserName);
        Assert.Equal("aad", context.AuthProvider);
        Assert.Equal("token-xyz", context.AuthToken);
        Assert.Equal("base64data", context.ClientPrincipalB64);
        Assert.Equal("id-token", context.AadIdToken);
    }

    [Fact]
    public void Properties_CanBeSetToEmptyStrings()
    {
        // Arrange & Act
        var context = new UserContext
        {
            UserPrincipalId = "",
            UserName = "",
            AuthProvider = ""
        };

        // Assert
        Assert.Equal("", context.UserPrincipalId);
        Assert.Equal("", context.UserName);
        Assert.Equal("", context.AuthProvider);
    }

    [Fact]
    public void Properties_CanBeReassigned()
    {
        // Arrange
        var context = new UserContext
        {
            UserPrincipalId = "original"
        };

        // Act
        context.UserPrincipalId = "updated";

        // Assert
        Assert.Equal("updated", context.UserPrincipalId);
    }

    [Fact]
    public void UserContext_IsClass()
    {
        // Assert
        Assert.True(typeof(UserContext).IsClass);
    }

    [Fact]
    public void IUserContextAccessor_IsInterface()
    {
        // Assert
        Assert.True(typeof(IUserContextAccessor).IsInterface);
    }
}
