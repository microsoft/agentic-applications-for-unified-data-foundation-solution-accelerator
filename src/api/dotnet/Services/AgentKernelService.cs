using System;
using System.Text.Json;
using System.Threading.Tasks;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using CsApi.Repositories;

namespace CsApi.Services
{
    public interface IAgentKernelService
    {
        Task<string> GetSqlResponseAsync(string input);
        Task<string> GetChartDataAsync(string input);
    }

    public class AgentKernelService : IAgentKernelService
    {
        private readonly IConfiguration _config;
        private readonly ILogger<AgentKernelService> _logger;
        private readonly ISqlConversationRepository _sqlRepo;
        private readonly string _aiProjectEndpoint;
        private readonly string _aiProjectApiVersion;
        private readonly string _foundrySqlAgentId;
        private readonly string _foundryChartAgentId;

        public AgentKernelService(IConfiguration config, ILogger<AgentKernelService> logger, ISqlConversationRepository sqlRepo)
        {
            _config = config;
            _logger = logger;
            _sqlRepo = sqlRepo;
            _aiProjectEndpoint = _config["AZURE_AI_AGENT_ENDPOINT"];
            _aiProjectApiVersion = _config["AZURE_AI_AGENT_API_VERSION"] ?? "2025-05-01";
            _foundrySqlAgentId = _config["AGENT_ID_SQL"];
            _foundryChartAgentId = _config["AGENT_ID_CHART"];
        }

        public async Task<string> GetSqlResponseAsync(string input)
        {
            // Delegate to plugin (DI recommended)
            return "[Use ChatWithDataPlugin for agent logic]";
        }

        public async Task<string> GetChartDataAsync(string input)
        {
            // Delegate to plugin (DI recommended)
            return "[Use ChatWithDataPlugin for agent logic]";
        }
    }
}
