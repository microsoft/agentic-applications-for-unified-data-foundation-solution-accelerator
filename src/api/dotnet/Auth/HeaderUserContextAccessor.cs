using System.Text.Json;
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
        var hasPrincipal = headers.ContainsKey("x-ms-client-principal-id");

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
            UserPrincipalId = headers["x-ms-client-principal-id"].ToString(),
            UserName = headers["x-ms-client-principal-name"].ToString(),
            AuthProvider = headers["x-ms-client-principal-idp"].ToString(),
            AuthToken = headers.TryGetValue("x-ms-token-aad-id-token", out var token) ? token.ToString() : null,
            ClientPrincipalB64 = headers.TryGetValue("x-ms-client-principal", out var cp) ? cp.ToString() : null,
            AadIdToken = headers.TryGetValue("x-ms-token-aad-id-token", out var idt) ? idt.ToString() : null
        };
    }
}
