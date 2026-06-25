using CsApi.Interfaces;
using System.Text;
using System.Text.Json;

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

        var hasPrincipal = headers.TryGetValue("x-ms-client-principal-id", out var userPrincipalIdValues)
            && !string.IsNullOrWhiteSpace(userPrincipalIdValues.ToString());

        var aadAccessToken = headers.TryGetValue("x-ms-token-aad-access-token", out var easyAuthAccessToken)
            ? easyAuthAccessToken.ToString()
            : (headers.TryGetValue("x-zumo-auth", out var zumoAuthToken) ? zumoAuthToken.ToString() : null);

        // If principal header is missing but a user token exists (e.g., Work IQ Teams via x-zumo-auth),
        // derive a usable user identity from token claims.
        if (!hasPrincipal && !string.IsNullOrWhiteSpace(aadAccessToken))
        {
            var tokenPrincipalId = GetPrincipalIdFromToken(aadAccessToken);
            var tokenUserName = GetUserNameFromToken(aadAccessToken);

            return new UserContext
            {
                UserPrincipalId = string.IsNullOrWhiteSpace(tokenPrincipalId) ? "zumo-auth-user" : tokenPrincipalId,
                UserName = tokenUserName,
                AuthProvider = "aad",
                AuthToken = headers.TryGetValue("x-ms-token-aad-id-token", out var tokenFromHeaders) ? tokenFromHeaders.ToString() : null,
                ClientPrincipalB64 = headers.TryGetValue("x-ms-client-principal", out var cpFromHeaders) ? cpFromHeaders.ToString() : null,
                AadIdToken = headers.TryGetValue("x-ms-token-aad-id-token", out var idtFromHeaders) ? idtFromHeaders.ToString() : null,
                AadAccessToken = aadAccessToken
            };
        }

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
                AadIdToken = null,
                AadAccessToken = null
            };
        }

        return new UserContext
        {
            UserPrincipalId = userPrincipalIdValues.ToString(),
            UserName = headers.TryGetValue("x-ms-client-principal-name", out var userName) ? userName.ToString() : null,
            AuthProvider = headers.TryGetValue("x-ms-client-principal-idp", out var authProvider) ? authProvider.ToString() : null,
            AuthToken = headers.TryGetValue("x-ms-token-aad-id-token", out var token) ? token.ToString() : null,
            ClientPrincipalB64 = headers.TryGetValue("x-ms-client-principal", out var cp) ? cp.ToString() : null,
            AadIdToken = headers.TryGetValue("x-ms-token-aad-id-token", out var idt) ? idt.ToString() : null,
            AadAccessToken = aadAccessToken
        };
    }

    private static string? GetPrincipalIdFromToken(string token)
    {
        if (!TryGetJwtPayload(token, out var payload)) return null;

        if (payload.TryGetProperty("oid", out var oid)) return oid.GetString();
        if (payload.TryGetProperty("sub", out var sub)) return sub.GetString();
        if (payload.TryGetProperty("nameid", out var nameId)) return nameId.GetString();
        return null;
    }

    private static string? GetUserNameFromToken(string token)
    {
        if (!TryGetJwtPayload(token, out var payload)) return null;

        if (payload.TryGetProperty("preferred_username", out var preferredUserName)) return preferredUserName.GetString();
        if (payload.TryGetProperty("upn", out var upn)) return upn.GetString();
        if (payload.TryGetProperty("email", out var email)) return email.GetString();
        if (payload.TryGetProperty("name", out var name)) return name.GetString();
        return null;
    }

    private static bool TryGetJwtPayload(string token, out JsonElement payload)
    {
        payload = default;
        try
        {
            var raw = token.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase)
                ? token[7..].Trim()
                : token.Trim();

            var parts = raw.Split('.');
            if (parts.Length < 2 || string.IsNullOrWhiteSpace(parts[1])) return false;

            var payloadBytes = DecodeBase64Url(parts[1]);
            var doc = JsonDocument.Parse(payloadBytes);
            payload = doc.RootElement.Clone();
            return true;
        }
        catch
        {
            return false;
        }
    }

    private static byte[] DecodeBase64Url(string input)
    {
        var padded = input.Replace('-', '+').Replace('_', '/');
        padded = padded.PadRight(padded.Length + (4 - padded.Length % 4) % 4, '=');
        return Convert.FromBase64String(padded);
    }
}
