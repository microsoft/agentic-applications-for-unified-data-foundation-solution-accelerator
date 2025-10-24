using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.AI;
using Microsoft.Agents.AI;
using Azure.AI.OpenAI;
using Azure.Identity;
using Azure.AI.Agents.Persistent;
using OpenAI;
using CsApi.Interfaces;
using CsApi.Repositories;
using CsApi.Auth;

namespace CsApi.Services
{
    public interface IAgentFrameworkService
    {
        AIAgent Agent { get; }
        Task<string> RunSqlQueryAsync(string input);
    }

    public class AgentFrameworkService : IAgentFrameworkService
    {
        private readonly AIAgent _agent;
        private readonly IConfiguration _config;
        private readonly ILogger<AgentFrameworkService> _logger;
        private readonly ISqlConversationRepository _sqlRepo;

        public AIAgent Agent => _agent;

        public AgentFrameworkService(
            IConfiguration config, 
            ILogger<AgentFrameworkService> logger,
            ISqlConversationRepository sqlRepo)
        {
            _config = config;
            _logger = logger;
            _sqlRepo = sqlRepo;

            // Create Agent Framework client similar to Python implementation using single AGENT_ID_ORCHESTRATOR
            var endpoint = config["AZURE_AI_AGENT_ENDPOINT"] 
                ?? throw new InvalidOperationException("AZURE_AI_AGENT_ENDPOINT is required");

            var foundryAgentId = config["AGENT_ID_ORCHESTRATOR"]
                ?? throw new InvalidOperationException("AGENT_ID_ORCHESTRATOR is required");

            // Create function tools for SQL operations like Python SqlQueryTool
            var sqlTool = AIFunctionFactory.Create(RunSqlQueryAsync);

            var credentialFactory = new AzureCredentialFactory(_config);
            var credential = credentialFactory.Create();
            // Use Azure AI Projects agent endpoint to get the existing agent with custom tools
            var persistentAgentsClient = new PersistentAgentsClient(endpoint, credential);

            var chatOptions = new ChatOptions
            {
                Tools = new[] { sqlTool }
            };

            // Get the existing Azure AI Foundry agent and add our custom tools
            // Note: Using GetAwaiter().GetResult() instead of .Result to avoid AggregateException wrapping
            _agent = persistentAgentsClient.GetAIAgentAsync(foundryAgentId, chatOptions).GetAwaiter().GetResult();

    
        }

        /// <summary>
        /// Function tool for SQL database queries - directly executes SQL like Python SqlQueryTool
        /// </summary>
        [System.ComponentModel.Description("Executes SQL queries against the database to retrieve Sales, Products and Orders data.")]
        public async Task<string> RunSqlQueryAsync(
            [System.ComponentModel.Description("A SQL query to execute against the database")] string sqlQuery)
        {
            try
            {
                // Clean up the SQL query similar to the original implementation
                var cleanedQuery = sqlQuery.Replace("```sql", string.Empty).Replace("```", string.Empty).Trim();
                
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