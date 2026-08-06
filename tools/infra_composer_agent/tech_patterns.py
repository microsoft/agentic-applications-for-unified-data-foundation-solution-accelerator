"""
Catalog of predefined "technical patterns" -- common Azure AI solution
shapes (chat-with-data, document-processing, call-center, realtime-alerts)
that the infra composer agent can start a composition from directly,
instead of requiring the user to describe every single resource from
scratch in free text.

Workflow (see agent.compose() / interactive.py):
  1. The user gives a free-text --prompt.
  2. The prompt is matched against this catalog's `keywords` to pick a
     technical pattern (explicit --tech-pattern always wins; otherwise
     inferred, and confirmed interactively unless --non-interactive).
  3. The pattern's own README.md -- normally the on-disk file under
     001-wip-repo-structure/technical-patterns/<id>/README.md, generated
     from this catalog by generate_pattern_readmes.py -- is READ and its
     "## Resources deployed" table is parsed to get the exact list of AVM
     module keys (e.g. "compute/app-service.bicep") this pattern uses.
     Reading the actual README (not just this Python catalog) is
     deliberate: it means the README is the real source of truth the user
     can edit by hand, and the agent will pick up those edits next run
     without any code change.
  4. The resolved resource list is shown to the user with an explicit
     "shall I proceed?" confirmation -- ONLY after that confirmation does
     the agent pull the actual module files from the source module-library
     branch (infra-core-modules-copy) and start composing.

`PATTERNS` remains the fallback/generation source (used by
generate_pattern_readmes.py to (re)populate the on-disk READMEs, and as a
fallback if a README is ever missing or its table can't be parsed), but at
runtime the on-disk README is preferred whenever it exists and parses
cleanly -- see `get_pattern_resources()`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PATTERNS_ROOT = REPO_ROOT / "001-wip-repo-structure" / "technical-patterns"


@dataclass(frozen=True)
class ResourceEntry:
    display_name: str   # human-readable name, e.g. "Azure AI Search"
    module_key: str      # exact ModuleInfo.key in the source module library, e.g. "ai/ai-search.bicep"
    purpose: str          # one-line reason this resource is included in the pattern


@dataclass(frozen=True)
class TechPattern:
    id: str
    display_name: str
    summary: str
    description: str
    keywords: tuple[str, ...]
    resources: tuple[ResourceEntry, ...] = field(default_factory=tuple)

    @property
    def key_resources(self) -> tuple[str, ...]:
        """Backwards-compatible plain-text resource list (display_name only)."""
        return tuple(r.display_name for r in self.resources)

    @property
    def module_keys(self) -> tuple[str, ...]:
        return tuple(r.module_key for r in self.resources)


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
        resources=(
            ResourceEntry("App Service (chat frontend)", "compute/app-service.bicep", "Hosts the web chat UI"),
            ResourceEntry("App Service Plan", "compute/app-service-plan.bicep", "Compute plan for the App Service"),
            ResourceEntry("Storage Account", "data/storage-account.bicep", "Source documents for the knowledge base"),
            ResourceEntry("Azure AI Search", "ai/ai-search.bicep", "Vector/knowledge index for RAG retrieval"),
            ResourceEntry("Azure AI Services (Azure OpenAI)", "ai/ai-services.bicep", "Chat/completions and embeddings"),
            ResourceEntry("AI Foundry Project", "ai/ai-foundry-project.bicep", "Hosts the AI Foundry project/agents"),
            ResourceEntry("AI Foundry Model Deployment", "ai/ai-foundry-model-deployment.bicep", "Deploys the chat/embedding models"),
            ResourceEntry("Cosmos DB (NoSQL)", "data/cosmos-db-nosql.bicep", "Chat history / conversation state"),
            ResourceEntry("Key Vault", "security/key-vault.bicep", "Secrets and certificates"),
            ResourceEntry("Managed Identity", "identity/managed-identity.bicep", "Identity for service-to-service auth"),
            ResourceEntry("Role Assignments", "identity/role-assignments.bicep", "Least-privilege RBAC for the identity"),
            ResourceEntry("Log Analytics Workspace", "monitoring/log-analytics.bicep", "Central log sink"),
            ResourceEntry("Application Insights", "monitoring/app-insights.bicep", "App telemetry/tracing"),
            ResourceEntry("Virtual Network", "networking/virtual-network.bicep", "Network isolation boundary"),
            ResourceEntry("Private Endpoint", "networking/private-endpoint.bicep", "Private connectivity to data/AI services"),
            ResourceEntry("Private DNS Zone", "networking/private-dns-zone.bicep", "DNS resolution for private endpoints"),
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
        resources=(
            ResourceEntry("Storage Account", "data/storage-account.bicep", "Inbound document landing zone"),
            ResourceEntry("Event Grid", "data/event-grid.bicep", "Blob-created event trigger"),
            ResourceEntry("Function App", "compute/function-app.bicep", "Extraction processing"),
            ResourceEntry("Azure AI Services", "ai/ai-services.bicep", "Document/data extraction"),
            ResourceEntry("Azure AI Search", "ai/ai-search.bicep", "Index of extracted content"),
            ResourceEntry("Cosmos DB (NoSQL)", "data/cosmos-db-nosql.bicep", "Extracted results store"),
            ResourceEntry("Key Vault", "security/key-vault.bicep", "Secrets and certificates"),
            ResourceEntry("Managed Identity", "identity/managed-identity.bicep", "Identity for service-to-service auth"),
            ResourceEntry("Role Assignments", "identity/role-assignments.bicep", "Least-privilege RBAC for the identity"),
            ResourceEntry("Log Analytics Workspace", "monitoring/log-analytics.bicep", "Central log sink"),
            ResourceEntry("Application Insights", "monitoring/app-insights.bicep", "Function/app telemetry"),
            ResourceEntry("Virtual Network", "networking/virtual-network.bicep", "Network isolation boundary"),
            ResourceEntry("Private Endpoint", "networking/private-endpoint.bicep", "Private connectivity to data/AI services"),
            ResourceEntry("Private DNS Zone", "networking/private-dns-zone.bicep", "DNS resolution for private endpoints"),
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
        resources=(
            ResourceEntry("Container App Environment", "compute/container-app-environment.bicep", "Hosting environment for the processing app"),
            ResourceEntry("Container App", "compute/container-app.bicep", "Real-time call processing"),
            ResourceEntry("App Service (agent dashboard)", "compute/app-service.bicep", "Agent-facing dashboard"),
            ResourceEntry("App Service Plan", "compute/app-service-plan.bicep", "Compute plan for the App Service"),
            ResourceEntry("Event Hub", "data/event-hub.bicep", "Call/voice event ingestion"),
            ResourceEntry("Storage Account", "data/storage-account.bicep", "Call recordings"),
            ResourceEntry("Azure AI Services", "ai/ai-services.bicep", "Transcription/sentiment analysis"),
            ResourceEntry("Azure AI Search", "ai/ai-search.bicep", "Knowledge base lookup"),
            ResourceEntry("AI Foundry Project", "ai/ai-foundry-project.bicep", "Hosts the AI Foundry project/agents"),
            ResourceEntry("AI Foundry Model Deployment", "ai/ai-foundry-model-deployment.bicep", "Deploys the summarization/chat model"),
            ResourceEntry("Cosmos DB (NoSQL)", "data/cosmos-db-nosql.bicep", "Conversation state"),
            ResourceEntry("Key Vault", "security/key-vault.bicep", "Secrets and certificates"),
            ResourceEntry("Managed Identity", "identity/managed-identity.bicep", "Identity for service-to-service auth"),
            ResourceEntry("Role Assignments", "identity/role-assignments.bicep", "Least-privilege RBAC for the identity"),
            ResourceEntry("Log Analytics Workspace", "monitoring/log-analytics.bicep", "Central log sink"),
            ResourceEntry("Application Insights", "monitoring/app-insights.bicep", "App/container telemetry"),
            ResourceEntry("Workbook", "monitoring/workbook.bicep", "Agent/call metrics dashboard"),
            ResourceEntry("Virtual Network", "networking/virtual-network.bicep", "Network isolation boundary"),
            ResourceEntry("Private Endpoint", "networking/private-endpoint.bicep", "Private connectivity to data/AI services"),
            ResourceEntry("Private DNS Zone", "networking/private-dns-zone.bicep", "DNS resolution for private endpoints"),
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
        resources=(
            ResourceEntry("Event Hub", "data/event-hub.bicep", "Telemetry ingestion"),
            ResourceEntry("Function App", "compute/function-app.bicep", "Stream processing / rule evaluation"),
            ResourceEntry("Storage Account", "data/storage-account.bicep", "Raw/aggregated event data"),
            ResourceEntry("Cosmos DB (NoSQL)", "data/cosmos-db-nosql.bicep", "Alert state"),
            ResourceEntry("App Configuration", "data/app-configuration.bicep", "Alerting thresholds"),
            ResourceEntry("Event Grid", "data/event-grid.bicep", "Alert fan-out"),
            ResourceEntry("Key Vault", "security/key-vault.bicep", "Secrets and certificates"),
            ResourceEntry("Managed Identity", "identity/managed-identity.bicep", "Identity for service-to-service auth"),
            ResourceEntry("Role Assignments", "identity/role-assignments.bicep", "Least-privilege RBAC for the identity"),
            ResourceEntry("Log Analytics Workspace", "monitoring/log-analytics.bicep", "Central log sink"),
            ResourceEntry("Application Insights", "monitoring/app-insights.bicep", "Function/app telemetry"),
            ResourceEntry("Data Collection Rule", "monitoring/data-collection-rule.bicep", "Routes telemetry into Log Analytics"),
            ResourceEntry("Workbook", "monitoring/workbook.bicep", "Operational dashboards"),
            ResourceEntry("Portal Dashboard", "monitoring/portal-dashboard.bicep", "System-health summary"),
            ResourceEntry("Virtual Network", "networking/virtual-network.bicep", "Network isolation boundary"),
            ResourceEntry("Private Endpoint", "networking/private-endpoint.bicep", "Private connectivity to data services"),
            ResourceEntry("Private DNS Zone", "networking/private-dns-zone.bicep", "DNS resolution for private endpoints"),
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


# Matches markdown table rows of the form "| Display Name | `module/key.bicep` | purpose |"
# under the "## Resources deployed" section rendered by render_readme().
_RESOURCE_ROW_RE = re.compile(
    r"^\|\s*(?P<display>[^|]+?)\s*\|\s*`?(?P<module>[\w./-]+\.bicep)`?\s*\|\s*(?P<purpose>[^|]*?)\s*\|\s*$",
    re.MULTILINE,
)


def parse_resource_table(readme_text: str) -> list[ResourceEntry]:
    """Parses the "## Resources deployed" table out of a rendered pattern
    README's markdown, returning the exact ResourceEntry list encoded in it.
    This is what lets the on-disk README (which a human can hand-edit) stay
    the real source of truth: the agent re-derives its resource plan from
    whatever the README currently says, not from a cached Python copy."""
    entries: list[ResourceEntry] = []
    for m in _RESOURCE_ROW_RE.finditer(readme_text):
        display = m.group("display").strip()
        module = m.group("module").strip()
        purpose = m.group("purpose").strip()
        if display.lower() in ("resource", "---") or set(display) <= {"-"}:
            continue
        entries.append(ResourceEntry(display, module, purpose))
    return entries


def get_pattern_resources(pattern_id: str, patterns_root: Path = PATTERNS_ROOT) -> tuple[list[ResourceEntry], str]:
    """Resolves the resource list for a technical pattern, preferring the
    on-disk README (so hand-edits are picked up) and falling back to the
    in-code catalog if the README is missing/unparseable. Returns
    (resources, source_description) where source_description explains which
    of the two was actually used (for logging)."""
    pattern = PATTERNS.get(pattern_id)
    if pattern is None:
        raise ValueError(f"Unknown technical pattern '{pattern_id}'.")

    readme_path = patterns_root / pattern_id / "README.md"
    if readme_path.exists():
        text = readme_path.read_text(encoding="utf-8", errors="ignore")
        parsed = parse_resource_table(text)
        if parsed:
            return parsed, f"README at {readme_path}"

    return list(pattern.resources), "built-in tech_patterns.py catalog (README missing/unparseable)"


def render_readme(pattern: TechPattern) -> str:
    """Renders the standalone README.md content for a technical-pattern
    folder (001-wip-repo-structure/technical-patterns/<id>/README.md) --
    independent of any specific composed project, describing the pattern
    itself, the resources it uses, and how to deploy it with the composer
    agent. The "## Resources deployed" table below is also the machine-
    parseable source of truth read back by get_pattern_resources()."""
    resource_rows = "\n".join(
        f"| {r.display_name} | `{r.module_key}` | {r.purpose} |" for r in pattern.resources
    )
    return f"""# {pattern.display_name}

{pattern.summary}

## What this pattern does

{pattern.description}

## Resources deployed

> This table is read directly by `infra_composer_agent` (see `tech_patterns.get_pattern_resources()`)
> to build its resource plan -- edit it here and the agent will pick up your changes on its next run.
> The `Module` column must match an exact module key from the source module library
> (`infra_new/avm/modules/<category>/<name>.bicep` on the `infra-core-modules-copy` branch).

| Resource | Module | Purpose |
|---|---|---|
{resource_rows}

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

The agent will first show you the resource table above (re-read live from this file) and ask you to
confirm before pulling any module from the source library or generating anything -- you can still add
or remove resources at that point.

> This README was generated automatically as placeholder documentation for the `{pattern.id}` technical
> pattern. Regenerate it any time with
> `python tools/infra_composer_agent/generate_pattern_readmes.py`.
"""
