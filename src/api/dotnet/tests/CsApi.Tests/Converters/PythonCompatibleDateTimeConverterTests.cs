using CsApi.Converters;
using System.Text;
using System.Text.Json;
using Xunit;

namespace CsApi.Tests.Converters;

public class PythonCompatibleDateTimeConverterTests
{
    private readonly JsonSerializerOptions _options;

    public PythonCompatibleDateTimeConverterTests()
    {
        _options = new JsonSerializerOptions();
        _options.Converters.Add(new PythonCompatibleDateTimeConverter());
    }

    [Fact]
    public void Write_DateTime_FormatsPythonStyle()
    {
        // Arrange
        var dateTime = new DateTime(2024, 1, 15, 10, 30, 45, 123, DateTimeKind.Utc);
        var wrapper = new DateTimeWrapper { Value = dateTime };

        // Act
        var json = JsonSerializer.Serialize(wrapper, _options);

        // Assert
        // Should format as "2024-01-15T10:30:45.123000" (6 decimal places for microseconds)
        Assert.Contains("2024-01-15T10:30:45.123", json);
    }

    [Fact]
    public void Read_ValidDateString_ParsesCorrectly()
    {
        // Arrange
        var json = "{\"Value\":\"2024-01-15T10:30:45.123456\"}";

        // Act
        var result = JsonSerializer.Deserialize<DateTimeWrapper>(json, _options);

        // Assert
        Assert.NotNull(result);
        Assert.Equal(2024, result.Value.Year);
        Assert.Equal(1, result.Value.Month);
        Assert.Equal(15, result.Value.Day);
        Assert.Equal(10, result.Value.Hour);
        Assert.Equal(30, result.Value.Minute);
        Assert.Equal(45, result.Value.Second);
    }

    [Fact]
    public void Read_DateWithZSuffix_ParsesCorrectly()
    {
        // Arrange
        var json = "{\"Value\":\"2024-01-15T10:30:45.123456Z\"}";

        // Act
        var result = JsonSerializer.Deserialize<DateTimeWrapper>(json, _options);

        // Assert
        Assert.NotNull(result);
        Assert.Equal(2024, result.Value.Year);
    }

    [Fact]
    public void Read_EmptyString_ReturnsDefault()
    {
        // Arrange
        var json = "{\"Value\":\"\"}";

        // Act
        var result = JsonSerializer.Deserialize<DateTimeWrapper>(json, _options);

        // Assert
        Assert.NotNull(result);
        Assert.Equal(default(DateTime), result.Value);
    }

    [Fact]
    public void Read_NullString_ReturnsDefault()
    {
        // Arrange
        var json = "{\"Value\":null}";

        // Act
        var result = JsonSerializer.Deserialize<DateTimeWrapper>(json, _options);

        // Assert
        Assert.NotNull(result);
        Assert.Equal(default(DateTime), result.Value);
    }

    [Fact]
    public void Read_InvalidDateString_ThrowsJsonException()
    {
        // Arrange
        var json = "{\"Value\":\"not-a-date\"}";

        // Act & Assert
        Assert.Throws<JsonException>(() => JsonSerializer.Deserialize<DateTimeWrapper>(json, _options));
    }

    [Fact]
    public void Write_MinDateTime_FormatsCorrectly()
    {
        // Arrange
        var wrapper = new DateTimeWrapper { Value = DateTime.MinValue };

        // Act
        var json = JsonSerializer.Serialize(wrapper, _options);

        // Assert
        Assert.Contains("0001-01-01", json);
    }

    [Fact]
    public void Write_MaxDateTime_FormatsCorrectly()
    {
        // Arrange
        var wrapper = new DateTimeWrapper { Value = DateTime.MaxValue };

        // Act
        var json = JsonSerializer.Serialize(wrapper, _options);

        // Assert
        Assert.Contains("9999-12-31", json);
    }

    [Fact]
    public void Read_DateWithOffset_ParsesCorrectly()
    {
        // Arrange
        var json = "{\"Value\":\"2024-06-15T14:30:00+05:30\"}";

        // Act
        var result = JsonSerializer.Deserialize<DateTimeWrapper>(json, _options);

        // Assert
        Assert.NotNull(result);
        Assert.Equal(2024, result.Value.Year);
        Assert.Equal(6, result.Value.Month);
        Assert.Equal(15, result.Value.Day);
    }

    [Fact]
    public void RoundTrip_PreservesDateTime()
    {
        // Arrange
        var original = new DateTime(2024, 7, 20, 15, 45, 30, 500, DateTimeKind.Utc);
        var wrapper = new DateTimeWrapper { Value = original };

        // Act
        var json = JsonSerializer.Serialize(wrapper, _options);
        var result = JsonSerializer.Deserialize<DateTimeWrapper>(json, _options);

        // Assert
        Assert.NotNull(result);
        Assert.Equal(original.Year, result.Value.Year);
        Assert.Equal(original.Month, result.Value.Month);
        Assert.Equal(original.Day, result.Value.Day);
        Assert.Equal(original.Hour, result.Value.Hour);
        Assert.Equal(original.Minute, result.Value.Minute);
        Assert.Equal(original.Second, result.Value.Second);
    }

    private class DateTimeWrapper
    {
        public DateTime Value { get; set; }
    }
}

public class PythonCompatibleNullableDateTimeConverterTests
{
    private readonly JsonSerializerOptions _options;

    public PythonCompatibleNullableDateTimeConverterTests()
    {
        _options = new JsonSerializerOptions();
        _options.Converters.Add(new PythonCompatibleNullableDateTimeConverter());
    }

    [Fact]
    public void Write_NullValue_WritesNull()
    {
        // Arrange
        var wrapper = new NullableDateTimeWrapper { Value = null };

        // Act
        var json = JsonSerializer.Serialize(wrapper, _options);

        // Assert
        Assert.Contains("null", json);
    }

    [Fact]
    public void Write_HasValue_FormatsPythonStyle()
    {
        // Arrange
        var dateTime = new DateTime(2024, 1, 15, 10, 30, 45, 123, DateTimeKind.Utc);
        var wrapper = new NullableDateTimeWrapper { Value = dateTime };

        // Act
        var json = JsonSerializer.Serialize(wrapper, _options);

        // Assert
        Assert.Contains("2024-01-15T10:30:45.123", json);
    }

    [Fact]
    public void Read_NullValue_ReturnsNull()
    {
        // Arrange
        var json = "{\"Value\":null}";

        // Act
        var result = JsonSerializer.Deserialize<NullableDateTimeWrapper>(json, _options);

        // Assert
        Assert.NotNull(result);
        Assert.Null(result.Value);
    }

    [Fact]
    public void Read_EmptyString_ReturnsNull()
    {
        // Arrange
        var json = "{\"Value\":\"\"}";

        // Act
        var result = JsonSerializer.Deserialize<NullableDateTimeWrapper>(json, _options);

        // Assert
        Assert.NotNull(result);
        Assert.Null(result.Value);
    }

    [Fact]
    public void Read_ValidDateString_ParsesCorrectly()
    {
        // Arrange
        var json = "{\"Value\":\"2024-01-15T10:30:45.123456\"}";

        // Act
        var result = JsonSerializer.Deserialize<NullableDateTimeWrapper>(json, _options);

        // Assert
        Assert.NotNull(result);
        Assert.NotNull(result.Value);
        Assert.Equal(2024, result.Value.Value.Year);
    }

    [Fact]
    public void Read_InvalidDateString_ThrowsJsonException()
    {
        // Arrange
        var json = "{\"Value\":\"not-a-date\"}";

        // Act & Assert
        Assert.Throws<JsonException>(() => JsonSerializer.Deserialize<NullableDateTimeWrapper>(json, _options));
    }

    [Fact]
    public void RoundTrip_WithValue_PreservesDateTime()
    {
        // Arrange
        var original = new DateTime(2024, 7, 20, 15, 45, 30, 500, DateTimeKind.Utc);
        var wrapper = new NullableDateTimeWrapper { Value = original };

        // Act
        var json = JsonSerializer.Serialize(wrapper, _options);
        var result = JsonSerializer.Deserialize<NullableDateTimeWrapper>(json, _options);

        // Assert
        Assert.NotNull(result);
        Assert.NotNull(result.Value);
        Assert.Equal(original.Year, result.Value.Value.Year);
    }

    [Fact]
    public void RoundTrip_WithNull_PreservesNull()
    {
        // Arrange
        var wrapper = new NullableDateTimeWrapper { Value = null };

        // Act
        var json = JsonSerializer.Serialize(wrapper, _options);
        var result = JsonSerializer.Deserialize<NullableDateTimeWrapper>(json, _options);

        // Assert
        Assert.NotNull(result);
        Assert.Null(result.Value);
    }

    [Fact]
    public void Write_WithValueMinDateTime_FormatsCorrectly()
    {
        // Arrange
        var wrapper = new NullableDateTimeWrapper { Value = DateTime.MinValue };

        // Act
        var json = JsonSerializer.Serialize(wrapper, _options);

        // Assert
        Assert.Contains("0001-01-01", json);
    }

    [Fact]
    public void Write_WithValueMaxDateTime_FormatsCorrectly()
    {
        // Arrange
        var wrapper = new NullableDateTimeWrapper { Value = DateTime.MaxValue };

        // Act
        var json = JsonSerializer.Serialize(wrapper, _options);

        // Assert
        Assert.Contains("9999-12-31", json);
    }

    [Fact]
    public void Read_DateWithZSuffix_ParsesCorrectly()
    {
        // Arrange
        var json = "{\"Value\":\"2024-03-15T08:20:30.654321Z\"}";

        // Act
        var result = JsonSerializer.Deserialize<NullableDateTimeWrapper>(json, _options);

        // Assert
        Assert.NotNull(result);
        Assert.NotNull(result.Value);
        Assert.Equal(3, result.Value.Value.Month);
        Assert.Equal(15, result.Value.Value.Day);
    }

    [Fact]
    public void Read_DateWithOffset_ParsesCorrectly()
    {
        // Arrange
        var json = "{\"Value\":\"2024-08-20T16:45:00+03:00\"}";

        // Act
        var result = JsonSerializer.Deserialize<NullableDateTimeWrapper>(json, _options);

        // Assert
        Assert.NotNull(result);
        Assert.NotNull(result.Value);
        Assert.Equal(8, result.Value.Value.Month);
        Assert.Equal(20, result.Value.Value.Day);
    }

    private class NullableDateTimeWrapper
    {
        public DateTime? Value { get; set; }
    }
}
