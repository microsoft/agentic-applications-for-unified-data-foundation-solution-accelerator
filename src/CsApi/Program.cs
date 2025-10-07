using Azure.Identity;
using CsApi.Auth;
using CsApi.Interfaces;
using CsApi.Middleware;
using CsApi.Plugins;
using CsApi.Repositories;
using CsApi.Services;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Mvc;
using Microsoft.OpenApi.Models;
using System.Text.Json.Serialization;

var builder = WebApplication.CreateBuilder(args);

// Bind to port 8000 to mirror FastAPI default run configuration
builder.WebHost.UseUrls("http://0.0.0.0:8000");

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
});

// Swagger
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new OpenApiInfo { Title = "Conversation Knowledge Mining API", Version = "v1" });
    // Stable operation ids (controller + action name)
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
builder.Services.AddScoped<IChatService, ChatService>();
builder.Services.AddScoped<IChatRepository, ChatRepository>();
builder.Services.AddScoped<IHistoryService, HistoryService>();
builder.Services.AddScoped<IHistoryRepository, HistoryRepository>();
// SQL conversation repository for historyfab endpoints & streaming persistence
builder.Services.AddScoped<ISqlConversationRepository, SqlConversationRepository>();
// Agent kernel service for SQL and chart agent integration
builder.Services.AddScoped<IAgentKernelService, AgentKernelService>();

// Register ChatWithDataPlugin for agent plugins (with IAgentKernelService DI)
builder.Services.AddSingleton<ChatWithDataPlugin>(sp =>
    new ChatWithDataPlugin(
        sp.GetRequiredService<IAgentKernelService>(),
        sp.GetRequiredService<IConfiguration>(),
        sp.GetRequiredService<ILogger<ChatWithDataPlugin>>(),
        sp.GetRequiredService<ISqlConversationRepository>()
    ));

// Register orchestrator agent as singleton (initialized at startup)
builder.Services.AddSingleton<AzureAIAgentOrchestrator>(sp =>
{
    var config = sp.GetRequiredService<IConfiguration>();
    var logger = sp.GetRequiredService<ILogger<AzureAIAgentOrchestrator>>();
    var plugin = sp.GetRequiredService<ChatWithDataPlugin>();
    // Synchronous startup for demo; consider async startup for production
    return AzureAIAgentOrchestrator.CreateAsync(config, logger, new[] { plugin }).GetAwaiter().GetResult();
});

// Azure credential factory
builder.Services.AddSingleton<IAzureCredentialFactory, AzureCredentialFactory>();

// ProblemDetails customization
builder.Services.Configure<MvcOptions>(options =>
{
    // Additional filters if required
});

var app = builder.Build();

app.UseMiddleware<RequestLoggingMiddleware>();
app.UseMiddleware<UserContextMiddleware>();

app.UseExceptionHandler(appErr =>
{
    appErr.Run(async context =>
    {
        var feature = context.Features.Get<IExceptionHandlerPathFeature>();
        var problem = new ProblemDetails
        {
            Status = StatusCodes.Status500InternalServerError,
            Title = "Internal Server Error",
            Detail = feature?.Error.Message,
            Instance = context.Request.Path
        };
        context.Response.StatusCode = problem.Status ?? 500;
        await context.Response.WriteAsJsonAsync(problem);
    });
});

app.UseSwagger();
app.UseSwaggerUI();

app.UseCors(CorsPolicyName);
app.MapControllers();

app.MapGet("/health", () => Results.Json(new { status = "healthy" }));

// Simple readiness (checks env presence for SQL if configured)
app.MapGet("/ready", (IConfiguration cfg) =>
{
    var cs = cfg["FABRIC_SQL_CONNECTION_STRING"];
    return Results.Json(new { ready = !string.IsNullOrWhiteSpace(cs) });
});

app.Run();

public partial class Program { }
