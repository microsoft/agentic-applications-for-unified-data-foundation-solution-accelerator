using Azure.AI.Projects;
using Azure.AI.Extensions.OpenAI;
using CsApi.Auth;
using CsApi.Repositories;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Foundry;
using Microsoft.Data.SqlClient;
using Microsoft.Extensions.AI;
using System.Data.Common;

namespace CsApi.Services
{
    public interface IAgentFrameworkService
    {
        FoundryAgent Agent { get; }
        AIProjectClient ProjectClient { get; }
        string ChatAgentName { get; }
        AITool SqlTool { get; }
        bool UseDataAgent { get; }
        Task<string> run_sql_query(string input);
    }

    public class AgentFrameworkService : IAgentFrameworkService
    {
        private readonly FoundryAgent _agent;
        private readonly AIProjectClient _projectClient;
        private readonly IConfiguration _config;
        private readonly ILogger<AgentFrameworkService> _logger;
        private readonly ISqlConversationRepository _sqlRepo;
        private readonly string _chatAgentName;
        private readonly AITool _sqlTool;
        private readonly bool _useDataAgent;

        public FoundryAgent Agent => _agent;
        public AIProjectClient ProjectClient => _projectClient;
        public string ChatAgentName => _chatAgentName;
        public AITool SqlTool => _sqlTool;
        public bool UseDataAgent => _useDataAgent;

        public AgentFrameworkService(
            IConfiguration config, 
            ILogger<AgentFrameworkService> logger,
            ISqlConversationRepository sqlRepo)
        {
            _config = config;
            _logger = logger;
            _sqlRepo = sqlRepo;

            var endpoint = config["AZURE_AI_AGENT_ENDPOINT"] 
                ?? throw new InvalidOperationException("AZURE_AI_AGENT_ENDPOINT is required");

            _chatAgentName = config["AGENT_NAME_CHAT"]
                ?? throw new InvalidOperationException("AGENT_NAME_CHAT is required");

            _useDataAgent = string.Equals(config["USE_DATA_AGENT"], "true", StringComparison.OrdinalIgnoreCase)
                         || string.Equals(config["USE_DATA_AGENT"], "1", StringComparison.OrdinalIgnoreCase);

            // Create function tool for SQL operations like Python SqlQueryTool
            _sqlTool = AIFunctionFactory.Create(run_sql_query);

            var credentialFactory = new AzureCredentialFactory(_config);
            var credential = credentialFactory.Create();

            // Use Azure AI Projects client (Foundry approach)
            _projectClient = new AIProjectClient(new Uri(endpoint), credential);

            // Create FoundryAgent using AgentReference (by name) matching the Python FoundryAgent pattern
            var agentReference = new AgentReference(_chatAgentName);

            if (_useDataAgent)
            {
                // Data Agent mode: MCP handles SQL server-side, no local tools needed
                _logger.LogInformation("Workshop mode: Using Fabric Data Agent (MCP) - skipping local SQL tool");
                _agent = _projectClient.AsAIAgent(agentReference);
            }
            else
            {
                // Standard mode: local SQL tool provided, connection routed by AZURE_ENV_ONLY
                var azureEnvOnly = string.Equals(config["AZURE_ENV_ONLY"], "true", StringComparison.OrdinalIgnoreCase);
                _logger.LogInformation("Workshop mode: Using local SQL tool ({DatabaseType})",
                    azureEnvOnly ? "Azure SQL Database" : "Fabric Lakehouse SQL");
                _agent = _projectClient.AsAIAgent(agentReference, tools: [_sqlTool]);
            }
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
            catch (SqlException ex)
            {
                _logger.LogError(ex, "SQL query execution error");
                return $"SQL Error: {ex.Message}. Please check the query syntax.";
            }
            catch (DbException ex)
            {
                _logger.LogError(ex, "Database query execution error");
                return $"Database Error: {ex.Message}";
            }
            catch (TimeoutException ex)
            {
                _logger.LogWarning(ex, "SQL query timeout");
                return "Query timed out. Please simplify the query or add filters.";
            }
            catch (OperationCanceledException)
            {
                return "Query was cancelled.";
            }
            catch (Exception ex) when (ex is not OperationCanceledException && ex is not SqlException && ex is not DbException && ex is not TimeoutException)
            {
                _logger.LogError(ex, "Unexpected SQL query execution error");
                return $"SQL query failed with error: {ex.Message}. Please fix the query and try again.";
            }
        }


    }
}