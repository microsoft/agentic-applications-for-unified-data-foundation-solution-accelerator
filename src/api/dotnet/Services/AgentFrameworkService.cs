using Azure.AI.Projects;
using Azure.AI.Projects.OpenAI;
using CsApi.Auth;
using CsApi.Repositories;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace CsApi.Services
{
    public interface IAgentFrameworkService
    {
        AIAgent Agent { get; }
        AIProjectClient ProjectClient { get; }
        string ChatAgentName { get; }
        AITool SqlTool { get; }
        Task<string> run_sql_query(string input);
    }

    public class AgentFrameworkService : IAgentFrameworkService
    {
        private readonly AIAgent _agent;
        private readonly AIProjectClient _projectClient;
        private readonly IConfiguration _config;
        private readonly ILogger<AgentFrameworkService> _logger;
        private readonly ISqlConversationRepository _sqlRepo;
        private readonly string _chatAgentName;
        private readonly AITool _sqlTool;

        public AIAgent Agent => _agent;
        public AIProjectClient ProjectClient => _projectClient;
        public string ChatAgentName => _chatAgentName;
        public AITool SqlTool => _sqlTool;

        public AgentFrameworkService(
            IConfiguration config, 
            ILogger<AgentFrameworkService> logger,
            ISqlConversationRepository sqlRepo)
        {
            _config = config;
            _logger = logger;
            _sqlRepo = sqlRepo;

            // Create Agent Framework client similar to Python implementation
            var endpoint = config["AZURE_AI_AGENT_ENDPOINT"] 
                ?? throw new InvalidOperationException("AZURE_AI_AGENT_ENDPOINT is required");

            _chatAgentName = config["AGENT_NAME_CHAT"]
                ?? throw new InvalidOperationException("AGENT_NAME_CHAT is required");

            // Create function tools for SQL operations like Python SqlQueryTool
            _sqlTool = AIFunctionFactory.Create(run_sql_query);

            var credentialFactory = new AzureCredentialFactory(_config);
            var credential = credentialFactory.Create();

            // Use Azure AI Projects client (Foundry v2 approach)
            _projectClient = new AIProjectClient(new Uri(endpoint), credential);

            // Get the existing Azure AI Foundry agent by name with latest version
            _agent = _projectClient.GetAIAgent(name: _chatAgentName, tools: [_sqlTool]);
        }

        /// <summary>
        /// Function tool for SQL database queries - directly executes SQL like Python SqlQueryTool
        /// </summary>
        [System.ComponentModel.Description("Execute parameterized SQL query and return results as list of dictionaries.")]
        public async Task<string> run_sql_query(
            [System.ComponentModel.Description("Valid T-SQL query to execute against the SQL database in Fabric.")] string sql_query)
        {
            try
            {
                // Clean up the SQL query similar to the original implementation
                var cleanedQuery = sql_query.Replace("```sql", string.Empty).Replace("```", string.Empty).Trim();
                
                // Execute SQL query directly like Python SqlQueryTool
                var answerRaw = await _sqlRepo.ExecuteChatQuery(cleanedQuery, CancellationToken.None);
                string answer = answerRaw?.Length > 20000 ? answerRaw.Substring(0, 20000) : answerRaw ?? string.Empty;

                if (string.IsNullOrWhiteSpace(answer))
                    answer = "No results found.";

                return answer;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "SQL query execution error");
                return "Error executing SQL query. Please check the query syntax and try again.";
            }
        }


    }
}