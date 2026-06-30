using CsApi.Middleware;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using Xunit;

namespace CsApi.Tests.Middleware;

public class ExceptionHandlingExtensionsTests
{
    [Fact]
    public void UseGlobalExceptionHandler_ReturnsApplicationBuilder()
    {
        // Arrange
        var serviceCollection = new Microsoft.Extensions.DependencyInjection.ServiceCollection();
        serviceCollection.AddLogging();
        serviceCollection.AddSingleton<Microsoft.Extensions.Configuration.IConfiguration>(
            new Microsoft.Extensions.Configuration.ConfigurationBuilder().Build());
        
        var serviceProvider = serviceCollection.BuildServiceProvider();
        var applicationBuilder = new ApplicationBuilder(serviceProvider);

        // Act
        var result = applicationBuilder.UseGlobalExceptionHandler();

        // Assert
        Assert.NotNull(result);
        Assert.IsAssignableFrom<IApplicationBuilder>(result);
    }

    [Fact]
    public void UseGlobalExceptionHandler_ReturnsSameBuilder()
    {
        // Arrange
        var serviceCollection = new Microsoft.Extensions.DependencyInjection.ServiceCollection();
        serviceCollection.AddLogging();
        serviceCollection.AddSingleton<Microsoft.Extensions.Configuration.IConfiguration>(
            new Microsoft.Extensions.Configuration.ConfigurationBuilder().Build());
        
        var serviceProvider = serviceCollection.BuildServiceProvider();
        var applicationBuilder = new ApplicationBuilder(serviceProvider);

        // Act
        var result = applicationBuilder.UseGlobalExceptionHandler();

        // Assert
        Assert.Same(applicationBuilder, result);
    }
}
