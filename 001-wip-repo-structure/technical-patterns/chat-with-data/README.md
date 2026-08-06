# Chat With Your Data

A retrieval-augmented-generation (RAG) chatbot that lets users ask natural-language questions over their own documents/data.

## What this pattern does

Users upload documents into Blob Storage, which are chunked and embedded into a search index. A web chat UI (App Service) sends user questions to an orchestration layer that retrieves relevant chunks from Azure AI Search and calls Azure OpenAI (via an AI Foundry project) to generate a grounded answer, citing the source documents. Chat history is persisted in Cosmos DB. Secrets/keys are stored in Key Vault, all inbound traffic to data and AI services is locked down behind private endpoints, and a managed identity with least-privilege RBAC role assignments is used end-to-end instead of connection strings.

## Resources deployed

> This table is read directly by `infra_composer_agent` (see `tech_patterns.get_pattern_resources()`)
> to build its resource plan -- edit it here and the agent will pick up your changes on its next run.
> The `Module` column must match an exact module key from the source module library
> (`infra_new/avm/modules/<category>/<name>.bicep` on the `infra-core-modules-copy` branch).

| Resource | Module | Purpose |
|---|---|---|
| App Service (chat frontend) | `compute/app-service.bicep` | Hosts the web chat UI |
| App Service Plan | `compute/app-service-plan.bicep` | Compute plan for the App Service |
| Storage Account | `data/storage-account.bicep` | Source documents for the knowledge base |
| Azure AI Search | `ai/ai-search.bicep` | Vector/knowledge index for RAG retrieval |
| Azure AI Services (Azure OpenAI) | `ai/ai-services.bicep` | Chat/completions and embeddings |
| AI Foundry Project | `ai/ai-foundry-project.bicep` | Hosts the AI Foundry project/agents |
| AI Foundry Model Deployment | `ai/ai-foundry-model-deployment.bicep` | Deploys the chat/embedding models |
| Cosmos DB (NoSQL) | `data/cosmos-db-nosql.bicep` | Chat history / conversation state |
| Key Vault | `security/key-vault.bicep` | Secrets and certificates |
| Managed Identity | `identity/managed-identity.bicep` | Identity for service-to-service auth |
| Role Assignments | `identity/role-assignments.bicep` | Least-privilege RBAC for the identity |
| Log Analytics Workspace | `monitoring/log-analytics.bicep` | Central log sink |
| Application Insights | `monitoring/app-insights.bicep` | App telemetry/tracing |
| Virtual Network | `networking/virtual-network.bicep` | Network isolation boundary |
| Private Endpoint | `networking/private-endpoint.bicep` | Private connectivity to data/AI services |
| Private DNS Zone | `networking/private-dns-zone.bicep` | DNS resolution for private endpoints |

## How to deploy

This pattern is composed from existing, previously-reviewed AVM Bicep modules using the
[`infra_composer_agent`](../../../tools/infra_composer_agent/) tool rather than being generated from
scratch. To generate a deployable project for this pattern:

```bash
python tools/infra_composer_agent/agent.py \
  --tech-pattern chat-with-data \
  --prompt "<describe your specific solution name/naming convention and any resources to add or remove>" \
  --target-repo <your-target-repo-url> \
  --validate
```

The agent will first show you the resource table above (re-read live from this file) and ask you to
confirm before pulling any module from the source library or generating anything -- you can still add
or remove resources at that point.

> This README was generated automatically as placeholder documentation for the `chat-with-data` technical
> pattern. Regenerate it any time with
> `python tools/infra_composer_agent/generate_pattern_readmes.py`.
