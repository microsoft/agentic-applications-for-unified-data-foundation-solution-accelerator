using CsApi.Repositories; 
using Microsoft.SemanticKernel;
using Microsoft.SemanticKernel.Functions;
using System.ComponentModel;
using System.Threading.Tasks;
using System.Text.Json;

namespace CsApi.Plugins
{
    public class ChatWithDataPlugin
    {
        private readonly IConfiguration _config;
        private readonly ILogger<ChatWithDataPlugin> _logger;
        private readonly Services.IAgentKernelService _kernelService;
        private readonly ISqlConversationRepository _sqlConversationRepository;

        public ChatWithDataPlugin(Services.IAgentKernelService kernelService, 
            IConfiguration config, ILogger<ChatWithDataPlugin> logger,
            ISqlConversationRepository sqlConversationRepository)
        {
            _kernelService = kernelService;
            _config = config;
            _logger = logger;
            _sqlConversationRepository = sqlConversationRepository;
        }

        [KernelFunction("ChatWithSQLDatabase")]
        [Description("Provides quantified results, metrics, or structured data from the SQL database.")]
        public async Task<string> GetSqlResponseAsync(
            [Description("the question")] string input)
        {
            // Console.WriteLine("---------Fabric-SQL-Kernel-invoked---------"); // Verbose logging removed
            var endpoint = _config["AZURE_AI_AGENT_ENDPOINT"];
            var sqlAgentId = _config["AGENT_ID_SQL"];
            if (string.IsNullOrWhiteSpace(endpoint) || string.IsNullOrWhiteSpace(sqlAgentId))
                return "Details could not be retrieved. Please try again later.";
            try
            {
                var credential = new Azure.Identity.DefaultAzureCredential();
                var agentsClient = new Azure.AI.Agents.Persistent.PersistentAgentsClient(endpoint, credential);

                // Create thread
                var thread = agentsClient.Threads.CreateThread().Value;

                // Add user message
                var message = agentsClient.Messages.CreateMessage(
                    thread.Id,
                    Azure.AI.Agents.Persistent.MessageRole.User,
                    input
                );

                // Run agent
                var run = agentsClient.Runs.CreateRun(
                    thread.Id,
                    sqlAgentId
                ).Value;
                // Wait for run to complete
                while (run.Status == Azure.AI.Agents.Persistent.RunStatus.Queued || run.Status == Azure.AI.Agents.Persistent.RunStatus.InProgress)
                {
                    await Task.Delay(500);
                    run = agentsClient.Runs.GetRun(thread.Id, run.Id).Value;
                }
                if (run.Status == Azure.AI.Agents.Persistent.RunStatus.Failed)
                {
                    _logger.LogWarning("Run failed: {Error}", run.LastError?.Message);
                    return "Details could not be retrieved. Please try again later.";
                }

                // Get SQL query from agent messages
                string sqlQuery = string.Empty;
                foreach (var msg in agentsClient.Messages.GetMessages(thread.Id))
                {
                    if (msg.Role == Azure.AI.Agents.Persistent.MessageRole.Agent)
                    {
                        foreach (var contentItem in msg.ContentItems)
                        {
                            if (contentItem is Azure.AI.Agents.Persistent.MessageTextContent textItem)
                            {
                                sqlQuery = textItem.Text;
                                break;
                            }
                        }
                        if (!string.IsNullOrWhiteSpace(sqlQuery))
                            break;
                    }
                }
                sqlQuery = sqlQuery.Replace("```sql", string.Empty).Replace("```", string.Empty).Trim();
                // Console.WriteLine("USER INPUT: " + input); // Verbose logging removed
                // Console.WriteLine("SQL QUERY GENERATED: " + sqlQuery); // Verbose logging removed

                // Call runSqlQuery (delegate to kernel service or implement here)
                var answerRaw = await _sqlConversationRepository.ExecuteChatQuery(sqlQuery, CancellationToken.None);
                //var answerRaw = await _kernelService.GetSqlResponseAsync(sqlQuery);
                string answer = answerRaw?.Length > 20000 ? answerRaw.Substring(0, 20000) : answerRaw;
                // Console.WriteLine("SQL QUERY RESULT: " + answer); // Verbose logging removed
                if (string.IsNullOrWhiteSpace(answer))
                    answer = "No results found.";

                // Clean up
                agentsClient.Threads.DeleteThread(thread.Id);

                _logger.LogInformation("fabric-SQL-Kernel-response: {Answer}", answer);
                return answer;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Fabric-SQL-Kernel-error");
                return "Details could not be retrieved. Please try again later.";
            }
        }

        [KernelFunction("GenerateChartData")]
        [Description("Generates Chart.js v4.4.4 compatible JSON data for data visualization requests using current and immediate previous context.")]
        public async Task<string> GetChartDataAsync(
            [Description("The user's data visualization request along with relevant conversation history and context needed to generate appropriate chart data")] string input)
        {
            var endpoint = _config["AZURE_AI_AGENT_ENDPOINT"];
            var chartAgentId = _config["AGENT_ID_CHART"];
            if (string.IsNullOrWhiteSpace(endpoint) || string.IsNullOrWhiteSpace(chartAgentId))
                return "Details could not be retrieved. Please try again later.";
            try
            {
                var credential = new Azure.Identity.DefaultAzureCredential();
                var agentsClient = new Azure.AI.Agents.Persistent.PersistentAgentsClient(endpoint, credential);

                var thread = agentsClient.Threads.CreateThread().Value;

                var message = agentsClient.Messages.CreateMessage(
                    thread.Id,
                    Azure.AI.Agents.Persistent.MessageRole.User,
                    input.Trim()
                );

                var run = agentsClient.Runs.CreateRun(
                    thread.Id,
                    chartAgentId
                ).Value;
                while (run.Status == Azure.AI.Agents.Persistent.RunStatus.Queued || run.Status == Azure.AI.Agents.Persistent.RunStatus.InProgress)
                {
                    await Task.Delay(500);
                    run = agentsClient.Runs.GetRun(thread.Id, run.Id).Value;
                }
                if (run.Status == Azure.AI.Agents.Persistent.RunStatus.Failed)
                {
                    _logger.LogWarning("Run failed: {Error}", run.LastError?.Message);
                    return "Details could not be retrieved. Please try again later.";
                }

                string chartData = string.Empty;
                foreach (var msg in agentsClient.Messages.GetMessages(thread.Id))
                {
                    if (msg.Role == Azure.AI.Agents.Persistent.MessageRole.Agent)
                    {
                        foreach (var contentItem in msg.ContentItems)
                        {
                            if (contentItem is Azure.AI.Agents.Persistent.MessageTextContent textItem)
                            {
                                chartData = textItem.Text;
                                break;
                            }
                        }
                        if (!string.IsNullOrWhiteSpace(chartData))
                            break;
                    }
                }

                agentsClient.Threads.DeleteThread(thread.Id);

                _logger.LogInformation("fabric-Chat-Kernel-response: {ChartData}", chartData);
                return chartData;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "fabric-Chat-Kernel-error");
                return "Details could not be retrieved. Please try again later.";
            }
        }
    }
}
