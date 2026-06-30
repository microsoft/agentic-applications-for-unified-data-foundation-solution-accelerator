namespace CsApi.Interfaces;

public interface IUserContextAccessor
{
    UserContext GetCurrentUser();
}

public class UserContext
{
    public string? UserPrincipalId { get; set; }
    public string? UserName { get; set; }
    public string? AuthProvider { get; set; }
    public string? AuthToken { get; set; }
    public string? ClientPrincipalB64 { get; set; }
    public string? AadIdToken { get; set; }
}
