using Azure.Core;
using Azure.Identity;
using CsApi.Interfaces;

namespace CsApi.Auth;

public interface IAzureCredentialFactory
{
    TokenCredential Create(string? clientId = null);
}

public class AzureCredentialFactory : IAzureCredentialFactory
{
    public TokenCredential Create(string? clientId = null)
    {
        var appEnv = Environment.GetEnvironmentVariable("APP_ENV")?.ToLowerInvariant() ?? "prod";
        if (appEnv == "dev")
        {
            return new DefaultAzureCredential();
        }
        return string.IsNullOrWhiteSpace(clientId)
            ? new ManagedIdentityCredential()
            : new ManagedIdentityCredential(clientId);
    }
}
