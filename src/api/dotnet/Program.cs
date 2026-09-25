using CsApi.Auth;
using CsApi.Interfaces;
using CsApi.Middleware;
using CsApi.Repositories;
using CsApi.Services;
using CsApi.Converters;
using CsApi.Utils;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using Microsoft.OpenApi.Models;
using System.Text.Json.Serialization;

var builder = WebApplication.CreateBuilder(args);

// Suppress verbose ASP.NET MVC/Routing/CORS logs, keep request finished logs
builder.Logging.AddFilter("Microsoft.AspNetCore.Mvc", LogLevel.Warning);
builder.Logging.AddFilter("Microsoft.AspNetCore.Routing", LogLevel.Warning);
builder.Logging.AddFilter("Microsoft.AspNetCore.Cors", LogLevel.Warning);
builder.Logging.AddFilter("Microsoft.AspNetCore.Hosting.Diagnostics", LogLevel.Information);

// Suppress verbose Azure Monitor/OpenTelemetry exporter logs
builder.Logging.AddFilter("Azure.Monitor", LogLevel.Critical);
builder.Logging.AddFilter("Azure.Core", LogLevel.Warning);
builder.Logging.AddFilter("OpenTelemetry", LogLevel.Warning);

// CORS - allow all origins (adjust if needed)
var allowedOrigins = builder.Configuration.GetSection("Cors:AllowedOrigins").Get<string[]>() ?? new[] { "*" };
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

// --- Authentication ---
// Validates AAD access tokens against Entra ID JWKS. Identity is derived
// exclusively from validated token claims; client-supplied
// x-ms-client-principal-* headers are never trusted for authorization.
var oboTenantId = builder.Configuration["OBO_TENANT_ID"]
                  ?? Environment.GetEnvironmentVariable("OBO_TENANT_ID");
var oboClientId = builder.Configuration["OBO_CLIENT_ID"]
                  ?? Environment.GetEnvironmentVariable("OBO_CLIENT_ID");

if (string.IsNullOrWhiteSpace(oboTenantId) || string.IsNullOrWhiteSpace(oboClientId))
{
    throw new InvalidOperationException(
        "OBO_TENANT_ID and OBO_CLIENT_ID must be configured. " +
        "See infra/scripts/post-provision/setup_obo_auth.ps1.");
}

builder.Services
    .AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(JwtBearerDefaults.AuthenticationScheme, options =>
    {
        options.Authority = $"https://login.microsoftonline.com/{oboTenantId}/v2.0";
        options.MetadataAddress =
            $"https://login.microsoftonline.com/{oboTenantId}/v2.0/.well-known/openid-configuration";
        options.RequireHttpsMetadata = true;
        options.SaveToken = true;
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuers = new[]
            {
                $"https://login.microsoftonline.com/{oboTenantId}/v2.0",
                $"https://sts.windows.net/{oboTenantId}/"
            },
            ValidateAudience = true,
            ValidAudiences = new[]
            {
                $"api://{oboClientId}",
                oboClientId
            },
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            NameClaimType = "preferred_username",
            RoleClaimType = "roles",
            ClockSkew = TimeSpan.FromMinutes(2)
        };
    });

builder.Services.AddAuthorization(options =>
{
    // Every endpoint must be reached by an authenticated caller unless it
    // explicitly opts out via [AllowAnonymous]. This is defense in depth
    // on top of the per-controller [Authorize] attributes.
    options.FallbackPolicy = new Microsoft.AspNetCore.Authorization.AuthorizationPolicyBuilder(
            JwtBearerDefaults.AuthenticationScheme)
        .RequireAuthenticatedUser()
        .Build();
});

builder.Services.AddScoped<ISqlConversationRepository, SqlConversationRepository>();
builder.Services.AddScoped<ITitleGenerationService, TitleGenerationService>();
builder.Services.AddScoped<IAgentFrameworkService, AgentFrameworkService>();
builder.Services.AddSingleton<IAzureCredentialFactory, AzureCredentialFactory>();
builder.Services.AddHttpClient();


builder.Services.AddSingleton<IConversationRepository, CosmosConversationRepository>();

builder.Services.AddSingleton(sp =>
{
    var configuration = sp.GetRequiredService<IConfiguration>();
    var logger = sp.GetRequiredService<ILogger<ExpCache<string, string>>>();
    var endpoint = configuration["AZURE_AI_AGENT_ENDPOINT"] ?? string.Empty;
    return new ExpCache<string, string>(
        maxSize: 1000,
        ttlSeconds: 3600.0,
        configuration,
        logger,
        azureAIEndpoint: endpoint);
});

var app = builder.Build();

// Add global exception handler middleware first
app.UseGlobalExceptionHandler();

app.UseMiddleware<RequestLoggingMiddleware>();
app.UseMiddleware<UserContextMiddleware>();

app.UseSwagger();
app.UseSwaggerUI();

app.UseCors(CorsPolicyName);

app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();

app.MapGet("/health", () => Results.Json(new { status = "healthy" }))
    .AllowAnonymous();

app.MapGet("/ready", (IConfiguration cfg) =>
{
    var cs = cfg["FABRIC_SQL_CONNECTION_STRING"];
    return Results.Json(new { ready = !string.IsNullOrWhiteSpace(cs) });
}).AllowAnonymous();

app.Run();

public partial class Program { }
