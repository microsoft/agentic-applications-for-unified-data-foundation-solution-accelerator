using System.Text.Json;
using System.Text.Json.Serialization;

namespace CsApi.Converters;

/// <summary>
/// JSON converter to make DateTime serialization compatible with Python's .isoformat() output.
/// Python's datetime.isoformat() produces format like "2024-01-15T10:30:45.123456"
/// while .NET's default produces "2024-01-15T10:30:45.123456Z" with timezone indicator.
/// This converter ensures consistent datetime format across Python and C# implementations.
/// </summary>
public class PythonCompatibleDateTimeConverter : JsonConverter<DateTime>
{
    public override DateTime Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        var value = reader.GetString();
        if (string.IsNullOrEmpty(value))
            return default;

        // Handle both formats: with and without 'Z' suffix
        if (DateTime.TryParse(value, out var result))
        {
            return result;
        }

        throw new JsonException($"Unable to parse datetime: {value}");
    }

    public override void Write(Utf8JsonWriter writer, DateTime value, JsonSerializerOptions options)
    {
        // Format to match Python's .isoformat() output: "2024-01-15T10:30:45.123456"
        // Note: Python typically uses 6 decimal places for microseconds, .NET uses 7 for ticks
        // We'll format with 6 decimal places to match Python behavior exactly
        var formatted = value.ToString("yyyy-MM-ddTHH:mm:ss.ffffff");
        writer.WriteStringValue(formatted);
    }
}

/// <summary>
/// JSON converter for nullable DateTime to ensure consistent serialization.
/// </summary>
public class PythonCompatibleNullableDateTimeConverter : JsonConverter<DateTime?>
{
    public override DateTime? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        var value = reader.GetString();
        if (string.IsNullOrEmpty(value))
            return null;

        if (DateTime.TryParse(value, out var result))
        {
            return result;
        }

        throw new JsonException($"Unable to parse datetime: {value}");
    }

    public override void Write(Utf8JsonWriter writer, DateTime? value, JsonSerializerOptions options)
    {
        if (value.HasValue)
        {
            // Format to match Python's .isoformat() output
            var formatted = value.Value.ToString("yyyy-MM-ddTHH:mm:ss.ffffff");
            writer.WriteStringValue(formatted);
        }
        else
        {
            writer.WriteNullValue();
        }
    }
}