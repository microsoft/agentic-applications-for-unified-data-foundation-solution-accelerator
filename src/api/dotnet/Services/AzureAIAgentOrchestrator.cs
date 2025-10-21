using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Azure.Identity;
using Microsoft.SemanticKernel.Agents.AzureAI;
using Microsoft.SemanticKernel.Agents;
using Microsoft.SemanticKernel;
using CsApi.Services;

namespace CsApi.Services
{
    public class AzureAIAgentOrchestrator
    {
        public AzureAIAgent Agent { get; private set; }
        public AzureAIAgentOrchestrator(AzureAIAgent agent)
        {
            Agent = agent;
        }

    public static async Task<AzureAIAgentOrchestrator> CreateAsync(IConfiguration config, ILogger logger, IEnumerable<object> plugins)
        {
            var endpoint = config["AZURE_AI_AGENT_ENDPOINT"];
            var agentId = config["AGENT_ID_ORCHESTRATOR"];
            if (string.IsNullOrEmpty(endpoint) || string.IsNullOrEmpty(agentId))
                throw new InvalidOperationException("Missing Azure AI Agent endpoint or agent ID in configuration.");
            var client = AzureAIAgent.CreateAgentsClient(endpoint, new DefaultAzureCredential());
            var definition = await client.Administration.GetAgentAsync(agentId);
            // Cast plugins to IEnumerable<KernelPlugin>
            var pluginList = new List<KernelPlugin>();
            if (plugins != null)
            {
                foreach (var p in plugins)
                {
                    if (p is KernelPlugin kp)
                        pluginList.Add(kp);
                    else if (p != null)
                    {
                        // Try to create plugin from type if not already a KernelPlugin
                        var plugin = Microsoft.SemanticKernel.KernelPluginFactory.CreateFromObject(p);
                        pluginList.Add(plugin);
                    }
                }
            }
            var agent = new AzureAIAgent(definition, client, pluginList);
            logger.LogInformation($"AzureAIAgentOrchestrator initialized for agentId: {agentId}");
            return new AzureAIAgentOrchestrator(agent);
        }
    }
}
