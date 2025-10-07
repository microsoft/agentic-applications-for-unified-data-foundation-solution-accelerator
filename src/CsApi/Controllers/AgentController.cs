using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using System.Threading.Tasks;
using CsApi.Services;
using Microsoft.SemanticKernel.Agents.AzureAI;
using Microsoft.SemanticKernel.Agents;
using Microsoft.SemanticKernel;
using CsApi.Plugins;

namespace CsApi.Controllers
{
    [ApiController]
    [Route("api/agent")]
    public class AgentController : ControllerBase
    {
        private readonly AzureAIAgentOrchestrator _orchestrator;
        private readonly ILogger<AgentController> _logger;

        public AgentController(AzureAIAgentOrchestrator orchestrator, ILogger<AgentController> logger)
        {
            _orchestrator = orchestrator;
            _logger = logger;
        }

        [HttpPost("chat-sql")]
        public async Task<IActionResult> ChatWithSql([FromBody] string input, [FromServices] ChatWithDataPlugin plugin)
        {
            var result = await plugin.GetSqlResponseAsync(input);
            return Ok(result);
        }

        [HttpPost("chart-data")]
        public async Task<IActionResult> GenerateChartData([FromBody] string input, [FromServices] ChatWithDataPlugin plugin)
        {
            var result = await plugin.GetChartDataAsync(input);
            return Ok(result);
        }
    }
}
