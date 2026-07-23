using Azure.AI.Projects;
using Azure.AI.Extensions.OpenAI;
using CsApi.Auth;
using CsApi.Interfaces;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Foundry;

namespace CsApi.Services
{
    public interface IAgentFrameworkService
    {
        FoundryAgent Agent { get; }
        AIProjectClient ProjectClient { get; }
        string ChatAgentName { get; }
    }

    public class AgentFrameworkService : IAgentFrameworkService
    {
        private readonly FoundryAgent _agent;
        private readonly AIProjectClient _projectClient;
        private readonly ILogger<AgentFrameworkService> _logger;
        private readonly string _chatAgentName;

        public FoundryAgent Agent => _agent;
        public AIProjectClient ProjectClient => _projectClient;
        public string ChatAgentName => _chatAgentName;

        public AgentFrameworkService(
            IConfiguration config, 
                ILogger<AgentFrameworkService> logger,
                IUserContextAccessor userContextAccessor,
                IAzureCredentialFactory credentialFactory)
        {
            _logger = logger;

            var endpoint = config["AZURE_AI_AGENT_ENDPOINT"] 
                ?? throw new InvalidOperationException("AZURE_AI_AGENT_ENDPOINT is required");

            _chatAgentName = config["AGENT_NAME_CHAT"]
                ?? throw new InvalidOperationException("AGENT_NAME_CHAT is required");

            var useUserAccessToken = string.Equals(config["USE_USER_ACCESS_TOKEN"], "true", StringComparison.OrdinalIgnoreCase);
            var user = userContextAccessor.GetCurrentUser();
            var userAssertion = useUserAccessToken ? user.AadAccessToken : null;

            var credential = credentialFactory.Create(userAssertion: userAssertion);

            // Use Azure AI Projects client (Foundry approach)
            _projectClient = new AIProjectClient(new Uri(endpoint), credential);

            // Create FoundryAgent — SQL handled server-side via Fabric Data Agent (MCP)
            var agentReference = new AgentReference(_chatAgentName);
            _logger.LogInformation("Using Fabric Data Agent (MCP) for SQL queries");
            _agent = _projectClient.AsAIAgent(agentReference);
        }
    }
}