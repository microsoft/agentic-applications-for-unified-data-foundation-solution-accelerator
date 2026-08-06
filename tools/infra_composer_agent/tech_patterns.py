"""
Catalog of predefined "technical patterns" -- common Azure AI solution
shapes (chat-with-data, document-processing, call-center, realtime-alerts)
that the infra composer agent can start a composition from directly,
instead of requiring the user to describe every single resource from
scratch in free text.

This module is the single source of truth for technical-pattern content.
Both of the following are generated/driven from the same `PATTERNS` catalog
so they never drift out of sync:
  * the placeholder READMEs under
    001-wip-repo-structure/technical-patterns/<id>/README.md
    (see tools/infra_composer_agent/generate_pattern_readmes.py)
  * the agent's own --tech-pattern CLI flag / interactive prompt (see
    interactive.choose_tech_pattern() and agent.compose()), which prepends
    a pattern's `resource_prompt` to the user's free-text --prompt before
    interpretation, so "these are the resources I'm going to create for
    this pattern" always matches what's documented here.

Each pattern's `resource_prompt` is deliberately phrased as a plain-English
resource list (not Bicep) so it can be fed through either the deterministic
matcher (request_parser.match_requests) or the LLM interpreter
(llm_interpreter.interpret_with_llm) exactly like a normal user prompt.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TechPattern:
    id: str
    display_name: str
    summary: str
    description: str
    keywords: tuple[str, ...]
    resource_prompt: str
    key_resources: tuple[str, ...] = field(default_factory=tuple)


PATTERNS: dict[str, TechPattern] = {
    "chat-with-data": TechPattern(
        id="chat-with-data",
        display_name="Chat With Your Data",
        summary="A retrieval-augmented-generation (RAG) chatbot that lets users ask natural-language "
                "questions over their own documents/data.",
        description=(
            "Users upload documents into Blob Storage, which are chunked and embedded into a search "
            "index. A web chat UI (App Service) sends user questions to an orchestration layer that "
            "retrieves relevant chunks from Azure AI Search and calls Azure OpenAI (via an AI Foundry "
            "project) to generate a grounded answer, citing the source documents. Chat history is "
            "persisted in Cosmos DB. Secrets/keys are stored in Key Vault, all inbound traffic to data "
            "and AI services is locked down behind private endpoints, and a managed identity with "
            "least-privilege RBAC role assignments is used end-to-end instead of connection strings."
        ),
        keywords=("chat with data", "chat with your data", "rag", "retrieval augmented generation",
                   "knowledge base chat", "document chatbot", "grounded chat", "q&a over documents"),
        resource_prompt=(
            "1 App Service (Linux) for the chat web frontend, 1 App Service Plan, "
            "1 Storage Account for source documents, 1 Azure AI Search service for the vector/knowledge index, "
            "1 Azure AI Services account for Azure OpenAI, 1 AI Foundry project, 1 AI Foundry model deployment, "
            "1 Cosmos DB (NoSQL) account for chat history, 1 Key Vault, 1 Managed Identity, "
            "required Role Assignments for the managed identity on Storage/AI Search/AI Services/Cosmos DB/Key Vault, "
            "1 Log Analytics workspace, 1 Application Insights component, "
            "1 Virtual Network with private endpoints and private DNS zones for Storage, AI Search, AI Services, "
            "Cosmos DB, and Key Vault with public network access disabled."
        ),
        key_resources=(
            "App Service + App Service Plan (chat frontend)",
            "Storage Account (source documents)",
            "Azure AI Search (vector/knowledge index)",
            "Azure AI Services / Azure OpenAI + AI Foundry project & model deployment",
            "Cosmos DB (NoSQL) (chat history)",
            "Key Vault, Managed Identity, Role Assignments",
            "Log Analytics + Application Insights",
            "Virtual Network, Private Endpoints, Private DNS Zones",
        ),
    ),
    "document-processing": TechPattern(
        id="document-processing",
        display_name="Document Processing",
        summary="An event-driven pipeline that ingests documents, extracts structured data from them "
                "with AI, and stores the results for downstream use.",
        description=(
            "Documents land in Blob Storage, which raises an Event Grid notification that triggers a "
            "Function App. The function calls an Azure AI Services account (Document Intelligence-style "
            "extraction) to pull structured fields out of the document, optionally indexes the content in "
            "Azure AI Search for later lookup, and writes the extracted results to Cosmos DB. A managed "
            "identity with RBAC role assignments is used for every service-to-service call, secrets live "
            "in Key Vault, and Storage/Cosmos DB/AI Services sit behind private endpoints with public "
            "network access disabled."
        ),
        keywords=("document processing", "document intelligence", "form recognizer", "document extraction",
                   "intelligent document processing", "idp", "invoice processing", "document ingestion"),
        resource_prompt=(
            "1 Storage Account for inbound documents, 1 Event Grid topic/subscription for blob-created events, "
            "1 Function App for extraction processing, 1 Azure AI Services account for document extraction, "
            "1 Azure AI Search service for indexing extracted content, 1 Cosmos DB (NoSQL) account for "
            "extracted results, 1 Key Vault, 1 Managed Identity, required Role Assignments for the managed "
            "identity on Storage/AI Services/AI Search/Cosmos DB/Key Vault, 1 Log Analytics workspace, "
            "1 Application Insights component, 1 Virtual Network with private endpoints and private DNS zones "
            "for Storage, AI Services, AI Search, and Cosmos DB with public network access disabled."
        ),
        key_resources=(
            "Storage Account (document ingestion)",
            "Event Grid (blob-created trigger)",
            "Function App (extraction processing)",
            "Azure AI Services (document/data extraction)",
            "Azure AI Search (extracted-content index)",
            "Cosmos DB (NoSQL) (extracted results store)",
            "Key Vault, Managed Identity, Role Assignments",
            "Log Analytics + Application Insights",
            "Virtual Network, Private Endpoints, Private DNS Zones",
        ),
    ),
    "call-center": TechPattern(
        id="call-center",
        display_name="Call Center Copilot",
        summary="A real-time contact-center copilot that ingests call/voice events and gives agents "
                "AI-generated summaries, sentiment, and knowledge-base answers.",
        description=(
            "Call events/recordings flow into an Event Hub and are stored in Blob Storage. A Container "
            "App (running in a dedicated Container App Environment, VNet-integrated) processes each call: "
            "it calls Azure AI Services for transcription/summarization/sentiment, looks up relevant "
            "knowledge-base articles in Azure AI Search, and calls Azure OpenAI (via an AI Foundry project) "
            "to draft next-best-action suggestions for the agent. An App Service hosts the agent-facing "
            "dashboard. Conversation state is stored in Cosmos DB, dashboards/alerts use a monitoring "
            "workbook, and every service-to-service call uses a managed identity with least-privilege RBAC "
            "role assignments instead of keys."
        ),
        keywords=("call center", "call centre", "contact center", "contact centre", "agent copilot",
                   "call center copilot", "voice analytics", "call transcription"),
        resource_prompt=(
            "1 Container App Environment, 1 Container App for real-time call processing, "
            "1 App Service (Linux) for the agent dashboard, 1 App Service Plan, "
            "1 Event Hub for call/voice events, 1 Storage Account for call recordings, "
            "1 Azure AI Services account for transcription/sentiment, 1 Azure AI Search service for the "
            "knowledge base, 1 AI Foundry project, 1 AI Foundry model deployment, "
            "1 Cosmos DB (NoSQL) account for conversation state, 1 Key Vault, 1 Managed Identity, "
            "required Role Assignments for the managed identity on Storage/Event Hub/AI Services/AI Search/"
            "Cosmos DB/Key Vault, 1 Log Analytics workspace, 1 Application Insights component, "
            "1 monitoring workbook for agent/call metrics, "
            "1 Virtual Network with private endpoints and private DNS zones for Storage, AI Services, "
            "AI Search, and Cosmos DB with public network access disabled."
        ),
        key_resources=(
            "Container App Environment + Container App (real-time call processing)",
            "App Service + App Service Plan (agent dashboard)",
            "Event Hub (call/voice event ingestion)",
            "Storage Account (call recordings)",
            "Azure AI Services (transcription/sentiment) + Azure AI Search (knowledge base)",
            "AI Foundry project & model deployment (Azure OpenAI)",
            "Cosmos DB (NoSQL) (conversation state)",
            "Key Vault, Managed Identity, Role Assignments",
            "Log Analytics + Application Insights + monitoring workbook",
            "Virtual Network, Private Endpoints, Private DNS Zones",
        ),
    ),
    "realtime-alerts": TechPattern(
        id="realtime-alerts",
        display_name="Real-Time Alerts",
        summary="A streaming telemetry pipeline that ingests high-volume events, evaluates them for "
                "conditions of interest, and raises alerts/dashboards in near real time.",
        description=(
            "Telemetry/events stream into an Event Hub, which a Function App consumes to evaluate alerting "
            "rules and write raw/aggregated results to a Storage Account and Cosmos DB (NoSQL) for "
            "alert-state tracking. Configuration for alerting thresholds lives in App Configuration. When a "
            "condition fires, an Event Grid topic publishes an alert event for downstream routing. "
            "Operational dashboards and workbooks in Log Analytics/Application Insights give on-call teams "
            "live visibility, a portal dashboard summarizes system health, and every service-to-service "
            "call uses a managed identity with least-privilege RBAC role assignments."
        ),
        keywords=("realtime alerts", "real-time alerts", "real time alerting", "streaming alerts",
                   "telemetry alerting", "anomaly alerting", "iot alerting", "monitoring alerts"),
        resource_prompt=(
            "1 Event Hub for telemetry ingestion, 1 Function App for stream processing and rule evaluation, "
            "1 Storage Account for raw/aggregated event data, 1 Cosmos DB (NoSQL) account for alert state, "
            "1 App Configuration store for alerting thresholds, 1 Event Grid topic for alert fan-out, "
            "1 Key Vault, 1 Managed Identity, required Role Assignments for the managed identity on "
            "Event Hub/Storage/Cosmos DB/App Configuration/Key Vault, 1 Log Analytics workspace, "
            "1 Application Insights component, 1 data collection rule, 1 monitoring workbook, "
            "1 portal dashboard for system health, 1 Virtual Network with private endpoints and private "
            "DNS zones for Storage, Cosmos DB, and App Configuration with public network access disabled."
        ),
        key_resources=(
            "Event Hub (telemetry ingestion)",
            "Function App (stream processing / rule evaluation)",
            "Storage Account (raw/aggregated events)",
            "Cosmos DB (NoSQL) (alert state)",
            "App Configuration (alerting thresholds)",
            "Event Grid (alert fan-out)",
            "Key Vault, Managed Identity, Role Assignments",
            "Log Analytics + Application Insights + data collection rule + workbook",
            "Portal Dashboard (system health)",
            "Virtual Network, Private Endpoints, Private DNS Zones",
        ),
    ),
}


def infer_pattern(prompt: str) -> str | None:
    """Best-effort keyword match of a free-text prompt against the pattern
    catalog's `keywords`. Returns the pattern id with the most keyword hits,
    or None if nothing matches (ties broken by catalog order)."""
    lower = prompt.lower()
    best_id, best_score = None, 0
    for pid, pattern in PATTERNS.items():
        score = sum(1 for kw in pattern.keywords if kw in lower)
        if score > best_score:
            best_id, best_score = pid, score
    return best_id


def render_readme(pattern: TechPattern) -> str:
    """Renders the standalone README.md content for a technical-pattern
    folder (001-wip-repo-structure/technical-patterns/<id>/README.md) --
    independent of any specific composed project, describing the pattern
    itself, the resources it uses, and how to deploy it with the composer
    agent."""
    resources = "\n".join(f"- {r}" for r in pattern.key_resources)
    return f"""# {pattern.display_name}

{pattern.summary}

## What this pattern does

{pattern.description}

## Resources used

{resources}

## How to deploy

This pattern is composed from existing, previously-reviewed AVM Bicep modules using the
[`infra_composer_agent`](../../../tools/infra_composer_agent/) tool rather than being generated from
scratch. To generate a deployable project for this pattern:

```bash
python tools/infra_composer_agent/agent.py \\
  --tech-pattern {pattern.id} \\
  --prompt "<describe your specific solution name/naming convention and any resources to add or remove>" \\
  --target-repo <your-target-repo-url> \\
  --validate
```

The agent will show you the resource list above (plus anything else it infers from your prompt) and
let you add or remove resources interactively before generating `main.bicep`, copying the required
modules, and committing them to a new branch in the target repo.

> This README was generated automatically as placeholder documentation for the `{pattern.id}` technical
> pattern. Regenerate it any time with
> `python tools/infra_composer_agent/generate_pattern_readmes.py`.
"""
