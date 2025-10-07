using CsApi.Interfaces;

namespace CsApi.Middleware;

public class UserContextMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<UserContextMiddleware> _logger;
    private readonly IUserContextAccessor _userContextAccessor;

    public UserContextMiddleware(RequestDelegate next, ILogger<UserContextMiddleware> logger, IUserContextAccessor userContextAccessor)
    {
        _next = next;
        _logger = logger;
        _userContextAccessor = userContextAccessor;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        var user = _userContextAccessor.GetCurrentUser();
        context.Items[nameof(UserContext)] = user;
        _logger.LogDebug("UserContext set for {UserId}", user.UserPrincipalId);
        await _next(context);
    }
}
