using Azure.Core;
using Azure.Identity;

namespace CsApi.Auth;

public interface IAzureCredentialFactory
{
    TokenCredential Create(string? clientId = null);
}

public class AzureCredentialFactory : IAzureCredentialFactory
{
    private readonly IConfiguration _configuration;

    public AzureCredentialFactory(IConfiguration configuration)
    {
        _configuration = configuration;
    }

    public TokenCredential Create(string? clientId = null)
    {
        var appEnv = _configuration["APP_ENV"]?.ToLowerInvariant() ?? "prod";
        if (appEnv == "dev")
        {
            return new DefaultAzureCredential();
        }
        return string.IsNullOrWhiteSpace(clientId)
            ? new ManagedIdentityCredential()
            : new ManagedIdentityCredential(clientId);
    }
}
