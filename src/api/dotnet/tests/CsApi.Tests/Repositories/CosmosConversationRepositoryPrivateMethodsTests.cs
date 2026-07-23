using Azure.Core;
using CsApi.Auth;
using CsApi.Models;
using CsApi.Repositories;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Moq;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using Xunit;

namespace CsApi.Tests.Repositories;

public class CosmosConversationRepositoryPrivateMethodsTests
{
    [Fact]
    public void Constructor_WithRequiredConfig_CreatesInstance()
    {
        var config = new Mock<IConfiguration>();
        config.Setup(c => c["AZURE_COSMOSDB_ENABLE_FEEDBACK"]).Returns("true");
        config.Setup(c => c["AZURE_COSMOSDB_ACCOUNT"]).Returns("sample-account");
        config.Setup(c => c["AZURE_COSMOSDB_DATABASE"]).Returns("sample-db");
        config.Setup(c => c["AZURE_COSMOSDB_CONVERSATIONS_CONTAINER"]).Returns("sample-container");
        config.Setup(c => c["AZURE_CLIENT_ID"]).Returns("client-id");

        var credentialFactory = new Mock<IAzureCredentialFactory>();
        credentialFactory
            .Setup(f => f.Create(It.IsAny<string?>(), It.IsAny<string?>()))
            .Returns(new StaticTokenCredential());

        var repo = new CosmosConversationRepository(
            config.Object,
            Mock.Of<ILogger<CosmosConversationRepository>>(),
            credentialFactory.Object);

        Assert.NotNull(repo);
    }

    [Fact]
    public async Task DisposeAsync_CanBeCalled()
    {
        var config = new Mock<IConfiguration>();
        config.Setup(c => c["AZURE_COSMOSDB_ENABLE_FEEDBACK"]).Returns("false");
        config.Setup(c => c["AZURE_COSMOSDB_ACCOUNT"]).Returns("sample-account");
        config.Setup(c => c["AZURE_COSMOSDB_DATABASE"]).Returns("sample-db");
        config.Setup(c => c["AZURE_COSMOSDB_CONVERSATIONS_CONTAINER"]).Returns("sample-container");
        config.Setup(c => c["AZURE_CLIENT_ID"]).Returns("client-id");

        var credentialFactory = new Mock<IAzureCredentialFactory>();
        credentialFactory
            .Setup(f => f.Create(It.IsAny<string?>(), It.IsAny<string?>()))
            .Returns(new StaticTokenCredential());

        var repo = new CosmosConversationRepository(
            config.Object,
            Mock.Of<ILogger<CosmosConversationRepository>>(),
            credentialFactory.Object);

        await repo.DisposeAsync();
    }

    [Fact]
    public void BuildContentPayloadNode_WithStructuredCitations_PreservesCitations()
    {
        var msg = new ChatMessage { Role = "assistant" };
        msg.SetContentFromString("hello");
        msg.Citations = JsonDocument.Parse("[\"source-1\"]").RootElement.Clone();

        var payload = (JsonNode?)InvokePrivateStatic("BuildContentPayloadNode", msg);

        Assert.NotNull(payload);
        Assert.Equal("assistant", payload!["role"]!.GetValue<string>());
        Assert.Equal("hello", payload["content"]!.GetValue<string>());
        Assert.NotNull(payload["citations"]);
    }

    [Fact]
    public void MapToConversationSummary_ValidDocument_ReturnsSummary()
    {
        var item = JsonDocument.Parse("{\"id\":\"c1\",\"title\":\"t1\",\"createdAt\":\"2026-01-01T00:00:00Z\",\"updatedAt\":\"2026-01-02T00:00:00Z\"}").RootElement.Clone();

        var result = (ConversationSummary?)InvokePrivateStatic("MapToConversationSummary", item);

        Assert.NotNull(result);
        Assert.Equal("c1", result!.ConversationId);
        Assert.Equal("t1", result.Title);
    }

    [Fact]
    public void MapToConversationSummary_InvalidDocument_ReturnsNull()
    {
        var item = JsonDocument.Parse("{\"title\":\"missing-id\"}").RootElement.Clone();

        var result = (ConversationSummary?)InvokePrivateStatic("MapToConversationSummary", item);

        Assert.Null(result);
    }

    [Fact]
    public void MapToChatMessage_ObjectContent_ReturnsMappedMessage()
    {
        var item = JsonDocument.Parse("{\"id\":\"m1\",\"role\":\"assistant\",\"content\":{\"content\":\"chart\",\"citations\":[{\"id\":\"d1\"}]},\"feedback\":\"up\",\"createdAt\":\"2026-01-03T00:00:00Z\"}").RootElement.Clone();

        var result = (ChatMessage?)InvokePrivateStatic("MapToChatMessage", item);

        Assert.NotNull(result);
        Assert.Equal("m1", result!.Id);
        Assert.Equal("assistant", result.Role);
        Assert.Equal("chart", result.GetContentAsString());
        Assert.Equal("up", result.Feedback);
        Assert.NotNull(result.Citations);
    }

    [Fact]
    public void MapToChatMessage_StringContent_ReturnsMappedMessage()
    {
        var item = JsonDocument.Parse("{\"id\":\"m2\",\"role\":\"user\",\"content\":\"hello\"}").RootElement.Clone();

        var result = (ChatMessage?)InvokePrivateStatic("MapToChatMessage", item);

        Assert.NotNull(result);
        Assert.Equal("hello", result!.GetContentAsString());
    }

    [Fact]
    public void MapToChatMessage_InvalidDocument_ReturnsNull()
    {
        var item = JsonDocument.Parse("{\"role\":\"user\"}").RootElement.Clone();

        var result = (ChatMessage?)InvokePrivateStatic("MapToChatMessage", item);

        Assert.Null(result);
    }

    [Fact]
    public void ParseDateTime_StringValue_ReturnsParsedDate()
    {
        var input = JsonDocument.Parse("\"2026-01-04T12:00:00Z\"").RootElement.Clone();

        var dt = (DateTime)InvokePrivateStatic("ParseDateTime", input)!;

        Assert.Equal(2026, dt.Year);
        Assert.Equal(1, dt.Month);
    }

    [Fact]
    public void ParseDateTime_NonStringValue_ReturnsUtcNowFallback()
    {
        var input = JsonDocument.Parse("123").RootElement.Clone();
        var before = DateTime.UtcNow.AddSeconds(-2);

        var dt = (DateTime)InvokePrivateStatic("ParseDateTime", input)!;

        Assert.True(dt >= before);
    }

    private static object? InvokePrivateStatic(string methodName, params object[] args)
    {
        var method = typeof(CosmosConversationRepository).GetMethod(methodName, BindingFlags.NonPublic | BindingFlags.Static);
        Assert.NotNull(method);
        return method!.Invoke(null, args);
    }

    private sealed class StaticTokenCredential : TokenCredential
    {
        public override AccessToken GetToken(TokenRequestContext requestContext, CancellationToken cancellationToken)
            => new("test-token", DateTimeOffset.UtcNow.AddMinutes(30));

        public override ValueTask<AccessToken> GetTokenAsync(TokenRequestContext requestContext, CancellationToken cancellationToken)
            => ValueTask.FromResult(new AccessToken("test-token", DateTimeOffset.UtcNow.AddMinutes(30)));
    }
}
