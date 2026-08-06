# Call Center Copilot

A real-time contact-center copilot that ingests call/voice events and gives agents AI-generated summaries, sentiment, and knowledge-base answers.

## What this pattern does

Call events/recordings flow into an Event Hub and are stored in Blob Storage. A Container App (running in a dedicated Container App Environment, VNet-integrated) processes each call: it calls Azure AI Services for transcription/summarization/sentiment, looks up relevant knowledge-base articles in Azure AI Search, and calls Azure OpenAI (via an AI Foundry project) to draft next-best-action suggestions for the agent. An App Service hosts the agent-facing dashboard. Conversation state is stored in Cosmos DB, dashboards/alerts use a monitoring workbook, and every service-to-service call uses a managed identity with least-privilege RBAC role assignments instead of keys.

## Resources deployed

> This table is read directly by `infra_composer_agent` (see `tech_patterns.get_pattern_resources()`)
> to build its resource plan -- edit it here and the agent will pick up your changes on its next run.
> The `Module` column must match an exact module key from the source module library
> (`infra_new/avm/modules/<category>/<name>.bicep` on the `infra-core-modules-copy` branch).

| Resource | Module | Purpose |
|---|---|---|
| Container App Environment | `compute/container-app-environment.bicep` | Hosting environment for the processing app |
| Container App | `compute/container-app.bicep` | Real-time call processing |
| App Service (agent dashboard) | `compute/app-service.bicep` | Agent-facing dashboard |
| App Service Plan | `compute/app-service-plan.bicep` | Compute plan for the App Service |
| Event Hub | `data/event-hub.bicep` | Call/voice event ingestion |
| Storage Account | `data/storage-account.bicep` | Call recordings |
| Azure AI Services | `ai/ai-services.bicep` | Transcription/sentiment analysis |
| Azure AI Search | `ai/ai-search.bicep` | Knowledge base lookup |
| AI Foundry Project | `ai/ai-foundry-project.bicep` | Hosts the AI Foundry project/agents |
| AI Foundry Model Deployment | `ai/ai-foundry-model-deployment.bicep` | Deploys the summarization/chat model |
| Cosmos DB (NoSQL) | `data/cosmos-db-nosql.bicep` | Conversation state |
| Key Vault | `security/key-vault.bicep` | Secrets and certificates |
| Managed Identity | `identity/managed-identity.bicep` | Identity for service-to-service auth |
| Role Assignments | `identity/role-assignments.bicep` | Least-privilege RBAC for the identity |
| Log Analytics Workspace | `monitoring/log-analytics.bicep` | Central log sink |
| Application Insights | `monitoring/app-insights.bicep` | App/container telemetry |
| Workbook | `monitoring/workbook.bicep` | Agent/call metrics dashboard |
| Virtual Network | `networking/virtual-network.bicep` | Network isolation boundary |
| Private Endpoint | `networking/private-endpoint.bicep` | Private connectivity to data/AI services |
| Private DNS Zone | `networking/private-dns-zone.bicep` | DNS resolution for private endpoints |

## How to deploy

This pattern is composed from existing, previously-reviewed AVM Bicep modules using the
[`infra_composer_agent`](../../../tools/infra_composer_agent/) tool rather than being generated from
scratch. To generate a deployable project for this pattern:

```bash
python tools/infra_composer_agent/agent.py \
  --tech-pattern call-center \
  --prompt "<describe your specific solution name/naming convention and any resources to add or remove>" \
  --target-repo <your-target-repo-url> \
  --validate
```

The agent will first show you the resource table above (re-read live from this file) and ask you to
confirm before pulling any module from the source library or generating anything -- you can still add
or remove resources at that point.

> This README was generated automatically as placeholder documentation for the `call-center` technical
> pattern. Regenerate it any time with
> `python tools/infra_composer_agent/generate_pattern_readmes.py`.
