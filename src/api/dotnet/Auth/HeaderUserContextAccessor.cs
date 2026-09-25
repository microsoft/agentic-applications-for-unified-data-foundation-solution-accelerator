using System.Security.Claims;
using CsApi.Interfaces;
using Microsoft.AspNetCore.Authentication;

namespace CsApi.Auth;

/// <summary>
/// Reads the authenticated user identity from the current <see cref="HttpContext"/>'s
/// <see cref="ClaimsPrincipal"/>, which is populated only after the JWT bearer
/// authentication middleware has cryptographically validated the caller's access
/// token against Entra ID.
/// </summary>
/// <remarks>
/// This accessor never trusts client-supplied headers such as
/// <c>x-ms-client-principal-id</c>, <c>x-ms-client-principal-name</c>, or
/// <c>x-ms-client-principal</c>. Those headers can be spoofed by any HTTP client
/// when the request does not traverse Azure App Service EasyAuth (for example,
/// local development, direct API access, or misconfigured deployments) and
/// therefore must not be used for authorization decisions.
/// </remarks>
public class HeaderUserContextAccessor : IUserContextAccessor
{
    private readonly IHttpContextAccessor _httpContextAccessor;

    public HeaderUserContextAccessor(IHttpContextAccessor httpContextAccessor)
    {
        _httpContextAccessor = httpContextAccessor;
    }

    public UserContext GetCurrentUser()
    {
        var ctx = _httpContextAccessor.HttpContext;
        if (ctx == null) return new UserContext();

        var principal = ctx.User;
        if (principal?.Identity == null || !principal.Identity.IsAuthenticated)
        {
            return new UserContext();
        }

        var userPrincipalId =
            principal.FindFirst("oid")?.Value
            ?? principal.FindFirst("http://schemas.microsoft.com/identity/claims/objectidentifier")?.Value
            ?? principal.FindFirst(ClaimTypes.NameIdentifier)?.Value
            ?? principal.FindFirst("sub")?.Value;

        var userName =
            principal.FindFirst("preferred_username")?.Value
            ?? principal.FindFirst("upn")?.Value
            ?? principal.FindFirst(ClaimTypes.Upn)?.Value
            ?? principal.FindFirst(ClaimTypes.Email)?.Value
            ?? principal.FindFirst("email")?.Value
            ?? principal.FindFirst(ClaimTypes.Name)?.Value;

        // The JwtBearer middleware stores the raw token so downstream OBO calls
        // can reuse it without ever having to reparse untrusted headers.
        var accessToken = ctx.Features.Get<IAuthenticateResultFeature>()
                             ?.AuthenticateResult?.Properties?.GetTokenValue("access_token")
                          ?? GetBearerToken(ctx.Request.Headers.Authorization.ToString());

        return new UserContext
        {
            UserPrincipalId = userPrincipalId,
            UserName = userName,
            AuthProvider = "aad",
            AuthToken = null,
            ClientPrincipalB64 = null,
            AadIdToken = null,
            AadAccessToken = accessToken
        };
    }

    private static string? GetBearerToken(string authorization)
    {
        const string bearerPrefix = "Bearer ";
        if (!authorization.StartsWith(bearerPrefix, StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }
        var token = authorization[bearerPrefix.Length..].Trim();
        return token.Length > 0 ? token : null;
    }
}

