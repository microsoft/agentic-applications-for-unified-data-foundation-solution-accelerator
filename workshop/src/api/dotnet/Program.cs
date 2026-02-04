using CsApi.Auth;
using CsApi.Interfaces;
using CsApi.Middleware;
using CsApi.Repositories;
using CsApi.Services;
using CsApi.Converters;
using Microsoft.OpenApi.Models;
using System.Text.Json.Serialization;

var builder = WebApplication.CreateBuilder(args);

// CORS - allow all origins (adjust if needed)
var allowedOrigins = builder.Configuration.GetSection("Cors:AllowedOrigins").Get<string[]>() ?? new[] {"*"};
const string CorsPolicyName = "UiCors";

builder.Services.AddCors(options =>
{
    options.AddPolicy(CorsPolicyName, policy =>
    {
        policy.SetIsOriginAllowed(_ => true)
              .AllowAnyHeader()
              .AllowAnyMethod()
              .AllowCredentials();
    });
});

// Controllers with JSON options to keep property names as-is
builder.Services.AddControllers().AddJsonOptions(o =>
{
    o.JsonSerializerOptions.PropertyNamingPolicy = null; // preserve original casing
    o.JsonSerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
    o.JsonSerializerOptions.Converters.Add(new PythonCompatibleDateTimeConverter());
});

// Swagger
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new OpenApiInfo { Title = "Agentic Applications for Unified Data Foundation Solution Accelerator", Version = "v1" });
    c.CustomOperationIds(apiDesc =>
    {
        var action = apiDesc.ActionDescriptor.RouteValues.TryGetValue("action", out var a) ? a : null;
        var ctrl = apiDesc.ActionDescriptor.RouteValues.TryGetValue("controller", out var ctrlName) ? ctrlName : null;
        return string.IsNullOrWhiteSpace(ctrl) ? action : ctrl + "." + action;
    });
});

// Dependency Injection registrations
builder.Services.AddHttpContextAccessor();
builder.Services.AddSingleton<IUserContextAccessor, HeaderUserContextAccessor>();
builder.Services.AddScoped<ISqlConversationRepository, SqlConversationRepository>();
builder.Services.AddScoped<ITitleGenerationService, TitleGenerationService>();
builder.Services.AddSingleton<IAgentFrameworkService, AgentFrameworkService>();
builder.Services.AddSingleton<IAzureCredentialFactory, AzureCredentialFactory>();

var app = builder.Build();

// Add global exception handler middleware first
app.UseGlobalExceptionHandler();

app.UseMiddleware<RequestLoggingMiddleware>();
app.UseMiddleware<UserContextMiddleware>();

app.UseSwagger();
app.UseSwaggerUI();

app.UseCors(CorsPolicyName);
app.MapControllers();

app.MapGet("/health", () => Results.Json(new { status = "healthy" }));

app.MapGet("/ready", (IConfiguration cfg) =>
{
    var cs = cfg["FABRIC_SQL_CONNECTION_STRING"];
    return Results.Json(new { ready = !string.IsNullOrWhiteSpace(cs) });
});

app.Run();

public partial class Program { }
