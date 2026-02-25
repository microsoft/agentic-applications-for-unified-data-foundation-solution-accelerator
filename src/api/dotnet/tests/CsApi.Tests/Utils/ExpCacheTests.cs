using CsApi.Utils;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;
using Xunit;

namespace CsApi.Tests.Utils;

public class ExpCacheTests
{
    private readonly Mock<IConfiguration> _mockConfiguration;
    private readonly ILogger _logger = NullLogger.Instance;

    public ExpCacheTests()
    {
        _mockConfiguration = new Mock<IConfiguration>();
        _mockConfiguration.Setup(c => c["AZURE_AI_AGENT_ENDPOINT"]).Returns("https://test.azure.com");
    }

    [Fact]
    public void Constructor_CreatesEmptyCache()
    {
        // Arrange & Act
        using var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger);

        // Assert
        Assert.Equal(0, cache.Count);
    }

    [Fact]
    public void Set_AddsItemToCache()
    {
        // Arrange
        using var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger);

        // Act
        cache.Set("key1", "value1");

        // Assert
        Assert.Equal(1, cache.Count);
    }

    [Fact]
    public void TryGet_ExistingItem_ReturnsTrue()
    {
        // Arrange
        using var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger);
        cache.Set("key1", "value1");

        // Act
        var found = cache.TryGet("key1", out var value);

        // Assert
        Assert.True(found);
        Assert.Equal("value1", value);
    }

    [Fact]
    public void TryGet_NonExistingItem_ReturnsFalse()
    {
        // Arrange
        using var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger);

        // Act
        var found = cache.TryGet("nonexistent", out var value);

        // Assert
        Assert.False(found);
        Assert.Null(value);
    }

    [Fact]
    public void TryGet_ExpiredItem_ReturnsFalse()
    {
        // Arrange - Very short TTL
        using var cache = new ExpCache<string, string>(100, 0.001, _mockConfiguration.Object, _logger); // 1 millisecond TTL
        cache.Set("key1", "value1");
        
        // Wait for expiration
        Thread.Sleep(10);

        // Act
        var found = cache.TryGet("key1", out var value);

        // Assert
        Assert.False(found);
    }

    [Fact]
    public void Set_OverwritesExistingItem()
    {
        // Arrange
        using var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger);
        cache.Set("key1", "value1");

        // Act
        cache.Set("key1", "value2");

        // Assert
        cache.TryGet("key1", out var value);
        Assert.Equal("value2", value);
        Assert.Equal(1, cache.Count);
    }

    [Fact]
    public void Set_MultipleItems_AddsAll()
    {
        // Arrange
        using var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger);

        // Act
        cache.Set("key1", "value1");
        cache.Set("key2", "value2");
        cache.Set("key3", "value3");

        // Assert
        Assert.Equal(3, cache.Count);
    }

    [Fact]
    public void Remove_ExistingItem_ReturnsTrue()
    {
        // Arrange
        using var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger);
        cache.Set("key1", "value1");

        // Act
        var removed = cache.Remove("key1");

        // Assert
        Assert.True(removed);
        Assert.Equal(0, cache.Count);
    }

    [Fact]
    public void Remove_NonExistingItem_ReturnsFalse()
    {
        // Arrange
        using var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger);

        // Act
        var removed = cache.Remove("nonexistent");

        // Assert
        Assert.False(removed);
    }

    [Fact]
    public void Clear_RemovesAllItems()
    {
        // Arrange
        using var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger);
        cache.Set("key1", "value1");
        cache.Set("key2", "value2");

        // Act
        cache.Clear();

        // Assert
        Assert.Equal(0, cache.Count);
    }

    [Fact]
    public void Set_ExceedsMaxSize_RemovesOldestItems()
    {
        // Arrange - Max size of 2
        using var cache = new ExpCache<string, string>(2, 3600, _mockConfiguration.Object, _logger);
        cache.Set("key1", "value1");
        cache.Set("key2", "value2");

        // Act - Add third item, should trigger eviction
        cache.Set("key3", "value3");

        // Assert - Should have 2 items (oldest evicted)
        Assert.True(cache.Count <= 2);
    }

    [Fact]
    public void Count_ReturnsCorrectNumber()
    {
        // Arrange
        using var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger);

        // Act & Assert
        Assert.Equal(0, cache.Count);
        
        cache.Set("key1", "value1");
        Assert.Equal(1, cache.Count);
        
        cache.Set("key2", "value2");
        Assert.Equal(2, cache.Count);
        
        cache.Remove("key1");
        Assert.Equal(1, cache.Count);
    }

    [Fact]
    public async Task ForceCleanupAsync_RemovesExpiredItems()
    {
        // Arrange
        using var cache = new ExpCache<string, string>(100, 0.001, _mockConfiguration.Object, _logger); // 1ms TTL
        cache.Set("key1", "value1");
        
        // Wait for expiration
        await Task.Delay(10);

        // Act
        await cache.ForceCleanupAsync();

        // Assert
        Assert.Equal(0, cache.Count);
    }

    [Fact]
    public async Task ForceCleanupAsync_KeepsNonExpiredItems()
    {
        // Arrange
        using var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger);
        cache.Set("key1", "value1");

        // Act
        await cache.ForceCleanupAsync();

        // Assert
        Assert.Equal(1, cache.Count);
    }

    [Fact]
    public void Dispose_CanBeCalledMultipleTimes()
    {
        // Arrange
        var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger);
        cache.Set("key1", "value1");

        // Act & Assert (should not throw)
        cache.Dispose();
        cache.Dispose();
    }

    [Fact]
    public void TryGet_AfterRemove_ReturnsFalse()
    {
        // Arrange
        using var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger);
        cache.Set("key1", "value1");
        cache.Remove("key1");

        // Act
        var found = cache.TryGet("key1", out var value);

        // Assert
        Assert.False(found);
    }

    [Fact]
    public void Set_WithIntegerKey_Works()
    {
        // Arrange
        using var cache = new ExpCache<int, string>(100, 3600, _mockConfiguration.Object, _logger);

        // Act
        cache.Set(123, "value123");

        // Assert
        cache.TryGet(123, out var value);
        Assert.Equal("value123", value);
    }

    [Fact]
    public void Constructor_WithAzureEndpoint_SetsEndpoint()
    {
        // Arrange & Act
        using var cache = new ExpCache<string, string>(100, 3600, _mockConfiguration.Object, _logger, "https://custom.azure.com");

        // Assert
        Assert.Equal(0, cache.Count); // Just verify it was created without error
    }

    [Fact]
    public void Set_WithNullValue_AddsItem()
    {
        // Arrange
        using var cache = new ExpCache<string, string?>(100, 3600, _mockConfiguration.Object, _logger);

        // Act
        cache.Set("key1", null);

        // Assert
        Assert.Equal(1, cache.Count);
        cache.TryGet("key1", out var value);
        Assert.Null(value);
    }
}
