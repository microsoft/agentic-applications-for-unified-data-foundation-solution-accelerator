# Call Center Copilot

A real-time contact-center copilot that ingests call/voice events and gives agents AI-generated summaries, sentiment, and knowledge-base answers.

## What this pattern does

Call events/recordings flow into an Event Hub and are stored in Blob Storage. A Container App (running in a dedicated Container App Environment, VNet-integrated) processes each call: it calls Azure AI Services for transcription/summarization/sentiment, looks up relevant knowledge-base articles in Azure AI Search, and calls Azure OpenAI (via an AI Foundry project) to draft next-best-action suggestions for the agent. An App Service hosts the agent-facing dashboard. Conversation state is stored in Cosmos DB, dashboards/alerts use a monitoring workbook, and every service-to-service call uses a managed identity with least-privilege RBAC role assignments instead of keys.

## Resources used

- Container App Environment + Container App (real-time call processing)
- App Service + App Service Plan (agent dashboard)
- Event Hub (call/voice event ingestion)
- Storage Account (call recordings)
- Azure AI Services (transcription/sentiment) + Azure AI Search (knowledge base)
- AI Foundry project & model deployment (Azure OpenAI)
- Cosmos DB (NoSQL) (conversation state)
- Key Vault, Managed Identity, Role Assignments
- Log Analytics + Application Insights + monitoring workbook
- Virtual Network, Private Endpoints, Private DNS Zones

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

The agent will show you the resource list above (plus anything else it infers from your prompt) and
let you add or remove resources interactively before generating `main.bicep`, copying the required
modules, and committing them to a new branch in the target repo.

> This README was generated automatically as placeholder documentation for the `call-center` technical
> pattern. Regenerate it any time with
> `python tools/infra_composer_agent/generate_pattern_readmes.py`.
