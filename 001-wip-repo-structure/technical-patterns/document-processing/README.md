# Document Processing

An event-driven pipeline that ingests documents, extracts structured data from them with AI, and stores the results for downstream use.

## What this pattern does

Documents land in Blob Storage, which raises an Event Grid notification that triggers a Function App. The function calls an Azure AI Services account (Document Intelligence-style extraction) to pull structured fields out of the document, optionally indexes the content in Azure AI Search for later lookup, and writes the extracted results to Cosmos DB. A managed identity with RBAC role assignments is used for every service-to-service call, secrets live in Key Vault, and Storage/Cosmos DB/AI Services sit behind private endpoints with public network access disabled.

## Resources used

- Storage Account (document ingestion)
- Event Grid (blob-created trigger)
- Function App (extraction processing)
- Azure AI Services (document/data extraction)
- Azure AI Search (extracted-content index)
- Cosmos DB (NoSQL) (extracted results store)
- Key Vault, Managed Identity, Role Assignments
- Log Analytics + Application Insights
- Virtual Network, Private Endpoints, Private DNS Zones

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

The agent will show you the resource list above (plus anything else it infers from your prompt) and
let you add or remove resources interactively before generating `main.bicep`, copying the required
modules, and committing them to a new branch in the target repo.

> This README was generated automatically as placeholder documentation for the `document-processing` technical
> pattern. Regenerate it any time with
> `python tools/infra_composer_agent/generate_pattern_readmes.py`.
