# Chat With Your Data

A retrieval-augmented-generation (RAG) chatbot that lets users ask natural-language questions over their own documents/data.

## What this pattern does

Users upload documents into Blob Storage, which are chunked and embedded into a search index. A web chat UI (App Service) sends user questions to an orchestration layer that retrieves relevant chunks from Azure AI Search and calls Azure OpenAI (via an AI Foundry project) to generate a grounded answer, citing the source documents. Chat history is persisted in Cosmos DB. Secrets/keys are stored in Key Vault, all inbound traffic to data and AI services is locked down behind private endpoints, and a managed identity with least-privilege RBAC role assignments is used end-to-end instead of connection strings.

## Resources used

- App Service + App Service Plan (chat frontend)
- Storage Account (source documents)
- Azure AI Search (vector/knowledge index)
- Azure AI Services / Azure OpenAI + AI Foundry project & model deployment
- Cosmos DB (NoSQL) (chat history)
- Key Vault, Managed Identity, Role Assignments
- Log Analytics + Application Insights
- Virtual Network, Private Endpoints, Private DNS Zones

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

The agent will show you the resource list above (plus anything else it infers from your prompt) and
let you add or remove resources interactively before generating `main.bicep`, copying the required
modules, and committing them to a new branch in the target repo.

> This README was generated automatically as placeholder documentation for the `chat-with-data` technical
> pattern. Regenerate it any time with
> `python tools/infra_composer_agent/generate_pattern_readmes.py`.
