# Document Processing

An event-driven pipeline that ingests documents, extracts structured data from them with AI, and stores the results for downstream use.

## What this pattern does

Documents land in Blob Storage, which raises an Event Grid notification that triggers a Function App. The function calls an Azure AI Services account (Document Intelligence-style extraction) to pull structured fields out of the document, optionally indexes the content in Azure AI Search for later lookup, and writes the extracted results to Cosmos DB. A managed identity with RBAC role assignments is used for every service-to-service call, secrets live in Key Vault, and Storage/Cosmos DB/AI Services sit behind private endpoints with public network access disabled.

## Resources deployed

> This table is read directly by `infra_composer_agent` (see `tech_patterns.get_pattern_resources()`)
> to build its resource plan -- edit it here and the agent will pick up your changes on its next run.
> The `Module` column must match an exact module key from the source module library
> (`infra_new/avm/modules/<category>/<name>.bicep` on the `infra-core-modules-copy` branch).

| Resource | Module | Purpose |
|---|---|---|
| Storage Account | `data/storage-account.bicep` | Inbound document landing zone |
| Event Grid | `data/event-grid.bicep` | Blob-created event trigger |
| Function App | `compute/function-app.bicep` | Extraction processing |
| Azure AI Services | `ai/ai-services.bicep` | Document/data extraction |
| Azure AI Search | `ai/ai-search.bicep` | Index of extracted content |
| Cosmos DB (NoSQL) | `data/cosmos-db-nosql.bicep` | Extracted results store |
| Key Vault | `security/key-vault.bicep` | Secrets and certificates |
| Managed Identity | `identity/managed-identity.bicep` | Identity for service-to-service auth |
| Role Assignments | `identity/role-assignments.bicep` | Least-privilege RBAC for the identity |
| Log Analytics Workspace | `monitoring/log-analytics.bicep` | Central log sink |
| Application Insights | `monitoring/app-insights.bicep` | Function/app telemetry |
| Virtual Network | `networking/virtual-network.bicep` | Network isolation boundary |
| Private Endpoint | `networking/private-endpoint.bicep` | Private connectivity to data/AI services |
| Private DNS Zone | `networking/private-dns-zone.bicep` | DNS resolution for private endpoints |

## How to deploy

This pattern is composed from existing, previously-reviewed AVM Bicep modules using the
[`infra_composer_agent`](../../../tools/infra_composer_agent/) tool rather than being generated from
scratch. To generate a deployable project for this pattern:

```bash
python tools/infra_composer_agent/agent.py \
  --tech-pattern document-processing \
  --prompt "<describe your specific solution name/naming convention and any resources to add or remove>" \
  --target-repo <your-target-repo-url> \
  --validate
```

The agent will first show you the resource table above (re-read live from this file) and ask you to
confirm before pulling any module from the source library or generating anything -- you can still add
or remove resources at that point.

> This README was generated automatically as placeholder documentation for the `document-processing` technical
> pattern. Regenerate it any time with
> `python tools/infra_composer_agent/generate_pattern_readmes.py`.
