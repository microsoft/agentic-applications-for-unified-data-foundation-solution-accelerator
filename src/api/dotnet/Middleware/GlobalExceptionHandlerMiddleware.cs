using Microsoft.AspNetCore.Mvc;
using Azure;
using System.Text.Json;

namespace CsApi.Middleware;

/// <summary>
/// Global exception handler middleware that catches all unhandled exceptions
/// and returns a consistent error response format.
/// </summary>
public class GlobalExceptionHandlerMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<GlobalExceptionHandlerMiddleware> _logger;
    private readonly IConfiguration _configuration;

    public GlobalExceptionHandlerMiddleware(
        RequestDelegate next,
        ILogger<GlobalExceptionHandlerMiddleware> logger,
        IConfiguration configuration)
    {
        _next = next;
        _logger = logger;
        _configuration = configuration;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await _next(context);
        }
        catch (OperationCanceledException)
        {
            // Client disconnected - don't log as error, don't try to write response
            context.Response.StatusCode = StatusCodes.Status499ClientClosedRequest;
        }
        catch (ArgumentException ex)
        {
            await HandleExceptionAsync(context, ex);
        }
        catch (UnauthorizedAccessException ex)
        {
            await HandleExceptionAsync(context, ex);
        }
        catch (DirectoryServiceException ex)
        {
            await HandleExceptionAsync(context, ex);
        }
        catch (FileNotFoundException ex)
        {
            await HandleExceptionAsync(context, ex);
        }
        catch (DirectoryNotFoundException ex)
        {
            await HandleExceptionAsync(context, ex);
        }
        catch (InvalidOperationException ex)
        {
            await HandleExceptionAsync(context, ex);
        }
        catch (NotImplementedException ex)
        {
            await HandleExceptionAsync(context, ex);
        }
        catch (TimeoutException ex)
        {
            await HandleExceptionAsync(context, ex);
        }
        catch (HttpRequestException ex)
        {
            await HandleExceptionAsync(context, ex);
        }
        catch (RequestFailedException ex)
        {
            await HandleExceptionAsync(context, ex);
        }
        catch (IOException ex)
        {
            await HandleExceptionAsync(context, ex);
        }
        catch (JsonException ex)
        {
            await HandleExceptionAsync(context, ex);
        }
        catch (Exception ex)
        {
            await HandleExceptionAsync(context, ex);
        }
    }

    private async Task HandleExceptionAsync(HttpContext context, Exception exception)
    {
        var safeMethod = SanitizeForLog(context.Request.Method);
        var safePath = SanitizeForLog(context.Request.Path.Value);
        var safeQueryString = SanitizeForLog(context.Request.QueryString.Value);

        // Log the exception with full details
        _logger.LogError(exception,
            "Unhandled exception occurred. Request: {Method} {Path} {QueryString}",
            safeMethod,
            safePath,
            safeQueryString);

        // Determine the appropriate status code and error details
        var (statusCode, title, detail) = GetErrorDetails(exception);

        // Create a standardized error response
        var problemDetails = new ProblemDetails
        {
            Status = statusCode,
            Title = title,
            Detail = detail,
            Instance = context.Request.Path
        };

        // Add additional properties for debugging in development
        var appEnv = _configuration["APP_ENV"];
        if (string.Equals(appEnv, "dev", StringComparison.OrdinalIgnoreCase))
        {
            problemDetails.Extensions["exception"] = exception.GetType().Name;
            problemDetails.Extensions["stackTrace"] = exception.StackTrace;

            // Include inner exception details if present
            if (exception.InnerException != null)
            {
                problemDetails.Extensions["innerException"] = new
                {
                    Type = exception.InnerException.GetType().Name,
                    Message = exception.InnerException.Message,
                    StackTrace = exception.InnerException.StackTrace
                };
            }
        }

        // Set response headers
        context.Response.StatusCode = statusCode;
        context.Response.ContentType = "application/problem+json";

        // Serialize and write the response
        var jsonOptions = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            WriteIndented = true
        };

        var response = JsonSerializer.Serialize(problemDetails, jsonOptions);
        await context.Response.WriteAsync(response);
    }

    private static (int statusCode, string title, string detail) GetErrorDetails(Exception exception)
    {
        return exception switch
        {
            ArgumentException or ArgumentNullException =>
                (StatusCodes.Status400BadRequest, "Bad Request", "Invalid request parameters."),

            UnauthorizedAccessException =>
                (StatusCodes.Status401Unauthorized, "Unauthorized", "Authentication required."),

            DirectoryServiceException =>
                (StatusCodes.Status403Forbidden, "Forbidden", "Access denied."),

            FileNotFoundException or DirectoryNotFoundException =>
                (StatusCodes.Status404NotFound, "Not Found", "The requested resource was not found."),

            InvalidOperationException =>
                (StatusCodes.Status409Conflict, "Conflict", "The operation conflicts with the current state."),

            NotImplementedException =>
                (StatusCodes.Status501NotImplemented, "Not Implemented", "This functionality is not implemented."),

            TimeoutException =>
                (StatusCodes.Status408RequestTimeout, "Request Timeout", "The request timed out."),

            HttpRequestException httpEx when httpEx.Message.Contains("timeout") =>
                (StatusCodes.Status408RequestTimeout, "Request Timeout", "External service request timed out."),

            HttpRequestException _ =>
                (StatusCodes.Status502BadGateway, "Bad Gateway", "External service error."),

            TaskCanceledException =>
                (StatusCodes.Status408RequestTimeout, "Request Timeout", "The operation was cancelled due to timeout."),

            _ => (StatusCodes.Status500InternalServerError, "Internal Server Error", "An unexpected error occurred.")
        };
    }

    private static string SanitizeForLog(string? value)
    {
        return (value ?? string.Empty).Replace("\r", string.Empty).Replace("\n", string.Empty);
    }
}

/// <summary>
/// Custom exception for directory service related errors
/// </summary>
public class DirectoryServiceException : Exception
{
    public DirectoryServiceException(string message) : base(message) { }
    public DirectoryServiceException(string message, Exception innerException) : base(message, innerException) { }
}