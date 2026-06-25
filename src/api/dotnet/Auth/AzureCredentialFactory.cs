using Azure.Core;
using Azure.Identity;

namespace CsApi.Auth;

public interface IAzureCredentialFactory
{
    TokenCredential Create(string? clientId = null, string? userAssertion = null);
}

public class AzureCredentialFactory : IAzureCredentialFactory
{
    private readonly IConfiguration _configuration;

    public AzureCredentialFactory(IConfiguration configuration)
    {
        _configuration = configuration;
    }

    public TokenCredential Create(string? clientId = null, string? userAssertion = null)
    {
        // Match Python behavior: if user assertion is available and OBO is configured,
        // prefer OBO credential for user-context calls.
        if (!string.IsNullOrWhiteSpace(userAssertion))
        {
            var oboClientId = _configuration["OBO_CLIENT_ID"];
            var oboClientSecret = _configuration["OBO_CLIENT_SECRET"];
            var oboTenantId = _configuration["OBO_TENANT_ID"];

            if (!string.IsNullOrWhiteSpace(oboClientId)
                && !string.IsNullOrWhiteSpace(oboClientSecret)
                && !string.IsNullOrWhiteSpace(oboTenantId))
            {
                return new OnBehalfOfCredential(
                    tenantId: oboTenantId,
                    clientId: oboClientId,
                    clientSecret: oboClientSecret,
                    userAssertion: userAssertion);
            }
        }

        var appEnv = _configuration["APP_ENV"]?.ToLowerInvariant() ?? "prod";
        if (appEnv == "dev")
        {
            return new DefaultAzureCredential(); // CodeQL [SM05137] Okay use of DefaultAzureCredential as it is only used in development
        }
        return string.IsNullOrWhiteSpace(clientId)
            ? new ManagedIdentityCredential()
            : new ManagedIdentityCredential(clientId);
    }
}
