using CsApi.Interfaces;

namespace CsApi.Auth;

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

        var headers = ctx.Request.Headers;
        var hasPrincipal = headers.TryGetValue("x-ms-client-principal-id", out var userPrincipalIdValues);

        if (!hasPrincipal)
        {
            // Development fallback sample user (mirrors Python sample_user)
            return new UserContext
            {
                UserPrincipalId = "00000000-0000-0000-0000-000000000000",
                UserName = "sample.user@contoso.com",
                AuthProvider = "aad",
                AuthToken = null,
                ClientPrincipalB64 = null,
                AadIdToken = null
            };
        }

        return new UserContext
        {
            UserPrincipalId = userPrincipalIdValues.ToString(),
            UserName = headers.TryGetValue("x-ms-client-principal-name", out var userName) ? userName.ToString() : null,
            AuthProvider = headers.TryGetValue("x-ms-client-principal-idp", out var authProvider) ? authProvider.ToString() : null,
            AuthToken = headers.TryGetValue("x-ms-token-aad-id-token", out var token) ? token.ToString() : null,
            ClientPrincipalB64 = headers.TryGetValue("x-ms-client-principal", out var cp) ? cp.ToString() : null,
            AadIdToken = headers.TryGetValue("x-ms-token-aad-id-token", out var idt) ? idt.ToString() : null
        };
    }
}
