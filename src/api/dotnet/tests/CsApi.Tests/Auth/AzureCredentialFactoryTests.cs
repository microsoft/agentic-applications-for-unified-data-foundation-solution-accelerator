using Azure.Core;
using Azure.Identity;
using CsApi.Auth;
using Microsoft.Extensions.Configuration;
using Moq;
using Xunit;

namespace CsApi.Tests.Auth;

public class AzureCredentialFactoryTests
{
    private readonly Mock<IConfiguration> _mockConfiguration;

    public AzureCredentialFactoryTests()
    {
        _mockConfiguration = new Mock<IConfiguration>();
    }

    [Fact]
    public void Create_DevEnvironment_ReturnsDefaultAzureCredential()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("dev");
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Act
        var result = factory.Create();

        // Assert
        Assert.IsType<DefaultAzureCredential>(result);
    }

    [Fact]
    public void Create_DevEnvironmentUpperCase_ReturnsDefaultAzureCredential()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("DEV");
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Act
        var result = factory.Create();

        // Assert
        Assert.IsType<DefaultAzureCredential>(result);
    }

    [Fact]
    public void Create_DevEnvironmentMixedCase_ReturnsDefaultAzureCredential()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("Dev");
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Act
        var result = factory.Create();

        // Assert
        Assert.IsType<DefaultAzureCredential>(result);
    }

    [Fact]
    public void Create_ProdEnvironment_ReturnsManagedIdentityCredential()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("prod");
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Act
        var result = factory.Create();

        // Assert
        Assert.IsType<ManagedIdentityCredential>(result);
    }

    [Fact]
    public void Create_ProdEnvironmentUpperCase_ReturnsManagedIdentityCredential()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("PROD");
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Act
        var result = factory.Create();

        // Assert
        Assert.IsType<ManagedIdentityCredential>(result);
    }

    [Fact]
    public void Create_NullAppEnv_ReturnsManagedIdentityCredential()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns((string?)null);
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Act
        var result = factory.Create();

        // Assert
        Assert.IsType<ManagedIdentityCredential>(result);
    }

    [Fact]
    public void Create_EmptyAppEnv_ReturnsManagedIdentityCredential()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("");
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Act
        var result = factory.Create();

        // Assert
        Assert.IsType<ManagedIdentityCredential>(result);
    }

    [Fact]
    public void Create_UnknownEnvironment_ReturnsManagedIdentityCredential()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("staging");
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Act
        var result = factory.Create();

        // Assert
        Assert.IsType<ManagedIdentityCredential>(result);
    }

    [Fact]
    public void Create_WithClientId_ReturnsManagedIdentityCredentialWithClientId()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("prod");
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);
        var clientId = "test-client-id-123";

        // Act
        var result = factory.Create(clientId);

        // Assert
        Assert.IsType<ManagedIdentityCredential>(result);
    }

    [Fact]
    public void Create_WithNullClientId_ReturnsManagedIdentityCredential()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("prod");
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Act
        var result = factory.Create(null);

        // Assert
        Assert.IsType<ManagedIdentityCredential>(result);
    }

    [Fact]
    public void Create_WithEmptyClientId_ReturnsManagedIdentityCredential()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("prod");
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Act
        var result = factory.Create("");

        // Assert
        Assert.IsType<ManagedIdentityCredential>(result);
    }

    [Fact]
    public void Create_WithWhitespaceClientId_ReturnsManagedIdentityCredential()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("prod");
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Act
        var result = factory.Create("   ");

        // Assert
        Assert.IsType<ManagedIdentityCredential>(result);
    }

    [Fact]
    public void Create_DevWithClientId_ReturnsDefaultAzureCredentialIgnoringClientId()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("dev");
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Act
        var result = factory.Create("test-client-id");

        // Assert
        Assert.IsType<DefaultAzureCredential>(result);
    }

    [Fact]
    public void Create_ImplementsIAzureCredentialFactory()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("prod");
        
        // Act
        IAzureCredentialFactory factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Assert
        Assert.NotNull(factory);
        Assert.IsAssignableFrom<IAzureCredentialFactory>(factory);
    }

    [Fact]
    public void Create_ReturnsTokenCredential()
    {
        // Arrange
        _mockConfiguration.Setup(c => c["APP_ENV"]).Returns("prod");
        var factory = new AzureCredentialFactory(_mockConfiguration.Object);

        // Act
        var result = factory.Create();

        // Assert
        Assert.IsAssignableFrom<TokenCredential>(result);
    }
}
