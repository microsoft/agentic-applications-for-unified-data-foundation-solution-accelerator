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
class UseCase:
    title: str
    persona: str
    challenge: str
    summary: str


@dataclass(frozen=True)
class TechPattern:
    id: str
    display_name: str
    summary: str
    description: str
    keywords: tuple[str, ...]
    resources: tuple[ResourceEntry, ...] = field(default_factory=tuple)
    # Richer, real-README-style content (modeled on the specific public solution
    # accelerator each pattern mirrors -- see the module docstring / the source
    # URLs cited in each pattern below) so the generated README reads like an
    # actual repo README, not just a bare resource list.
    architecture_mermaid: str = ""
    how_it_works: str = ""
    additional_resources: tuple[tuple[str, str], ...] = field(default_factory=tuple)  # (link text, url)
    key_features: tuple[str, ...] = field(default_factory=tuple)
    business_scenario: str = ""
    business_value: tuple[str, ...] = field(default_factory=tuple)
    use_cases: tuple[UseCase, ...] = field(default_factory=tuple)
    source_reference: str = ""  # the real public repo this pattern's README structure/content mirrors

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
        summary="Ground a conversational assistant in your own documents and get answers with inline "
                "citations back to the source.",
        description=(
            "Organizations hold vast unstructured knowledge in contracts, policies, product manuals, and "
            "benefit guides that is hard to search and slow to answer questions from. Chat With Your Data "
            "indexes that content and puts a natural-language chat experience in front of it, so people "
            "find grounded answers in seconds instead of digging through files. Users upload documents "
            "into a Storage Account; the content is chunked and embedded into an Azure AI Search index. "
            "The web chat UI (App Service) sends user questions to Azure OpenAI (via an AI Foundry "
            "project), which retrieves relevant chunks from the search index and generates a grounded "
            "answer with inline citations. Chat history is persisted in Cosmos DB. A single user-assigned "
            "managed identity and Azure RBAC authorize every downstream call -- Key Vault still stores any "
            "remaining certificates, and Storage/Cosmos DB/AI Search/AI Foundry sit behind private "
            "endpoints with public network access disabled."
        ),
        keywords=("chat with data", "chat with your data", "rag", "retrieval augmented generation",
                   "knowledge base chat", "document chatbot", "grounded chat", "q&a over documents"),
        source_reference="https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator",
        architecture_mermaid="""flowchart LR
  U[User browser] --> FE[App Service<br/>chat frontend]
  FE -->|questions| FDRY[Azure AI Foundry<br/>models + retrieval]
  FDRY --> SEARCH[Azure AI Search<br/>knowledge base index]
  FDRY --> COSMOS[(Cosmos DB<br/>chat history)]
  U -->|upload docs| STORE[(Storage Account<br/>source documents)]
  STORE -->|index write| SEARCH
  MI[Managed Identity + RBAC] -.-> FDRY
  MI -.-> SEARCH
  MI -.-> COSMOS
  MI -.-> STORE
  MI -.-> KV[Key Vault]
  VNET[Virtual Network] --- PE[Private Endpoints] --- SEARCH
  PE --- COSMOS
  PE --- STORE
  PE --- FDRY""",
        how_it_works=(
            "You ask a question in natural language. The App Service frontend sends it to Azure AI "
            "Foundry, which retrieves the most relevant passages from the Azure AI Search index, grounds "
            "the language model on that context, and returns the answer with inline citations to the "
            "source documents. Ingestion runs separately: documents you upload to the Storage Account are "
            "parsed, chunked, embedded, and written to the search index, ready for the next question."
        ),
        additional_resources=(
            ("Azure AI Foundry documentation", "https://learn.microsoft.com/azure/ai-foundry/"),
            ("Azure AI Search documentation", "https://learn.microsoft.com/azure/search/"),
            ("Azure App Service documentation", "https://learn.microsoft.com/azure/app-service/"),
        ),
        key_features=(
            "Responses are grounded in your indexed content with inline citations back to the source documents.",
            "Upload files to a document ingestion pipeline that parses, chunks, and embeds them for retrieval.",
            "Azure AI Search provides the vector/knowledge index; Cosmos DB persists chat history.",
            "A single user-assigned managed identity and Azure RBAC authorize every downstream call.",
            "Storage, Cosmos DB, AI Search, and AI Foundry are reachable only through private endpoints, "
            "with public network access disabled.",
            "A single-page chat interface streams answers to the browser and retains chat history across sessions.",
        ),
        business_scenario=(
            "Organizations hold large volumes of unstructured content including contracts, policies, and "
            "internal documentation that employees must search manually to answer questions or complete "
            "work. Chat With Your Data indexes that content and provides a grounded chat interface so "
            "employees get accurate, cited answers in seconds."
        ),
        business_value=(
            "Employees get accurate, grounded answers immediately instead of spending time searching "
            "through documents manually.",
            "Inline citations let users verify answers against source material, reducing the risk of "
            "acting on incorrect information.",
            "Deployment into your own Azure subscription keeps your data under your control and within "
            "your compliance boundary.",
        ),
        use_cases=(
            UseCase("Contract review and summarization", "Legal professional, compliance officer",
                    "Reading and extracting key terms from large document sets is slow and error-prone.",
                    "Index contracts and enable users to query them in natural language, surfacing "
                    "obligations, deadlines, and clauses with citations."),
            UseCase("Employee and HR assistance", "HR professional, employee",
                    "Finding the right policy documents or benefits information across large knowledge "
                    "bases takes too long.",
                    "Index HR policies and employee handbooks, then answer questions with citations to "
                    "the source document."),
            UseCase("Customer intelligence", "Customer success manager, analyst",
                    "Synthesizing account history and customer feedback from unstructured notes is "
                    "time-consuming.",
                    "Ground the assistant on customer-facing documents and notes, making account context "
                    "instantly accessible."),
        ),
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
        display_name="Content Processing (Document/Claim Processing)",
        summary="Process multi-document claims by extracting data from each document, applying schemas "
                "with confidence scoring, and generating AI-powered summaries and gap analysis across "
                "the entire claim.",
        description=(
            "Documents land in a Storage Account, which raises an Event Grid notification that triggers "
            "a Function App. The function calls an Azure AI Services account (Content Understanding-style "
            "extraction) to pull structured fields, tables, and images out of each document with "
            "confidence scoring, indexes extracted content in Azure AI Search for later lookup, and writes "
            "results to Cosmos DB. Once every document in a claim/batch is processed, the function calls "
            "Azure OpenAI (via an AI Foundry project) to generate a cross-document summary and perform gap "
            "analysis, flagging missing documents and discrepancies. A managed identity with RBAC role "
            "assignments is used for every service-to-service call, secrets live in Key Vault, and "
            "Storage/Cosmos DB/AI Services sit behind private endpoints with public network access disabled."
        ),
        keywords=("document processing", "document intelligence", "form recognizer", "document extraction",
                   "intelligent document processing", "idp", "invoice processing", "document ingestion",
                   "content processing", "claim processing", "content understanding"),
        source_reference="https://github.com/microsoft/content-processing-solution-accelerator",
        architecture_mermaid="""flowchart LR
  U[User] -->|upload claim docs| STORE[(Storage Account<br/>documents, manifests, results)]
  STORE -->|blob-created event| EG[Event Grid]
  EG --> FN[Function App<br/>Extract to Map to Evaluate to Save]
  FN -->|OCR + layout| AICU[Azure AI Services<br/>Content Understanding]
  FN -->|vision extraction| AOAI[Azure AI Foundry<br/>models]
  FN -->|index write| SEARCH[Azure AI Search]
  FN -->|save results| COSMOS[(Cosmos DB<br/>processes, schemas, claims)]
  FN -->|cross-doc summary + gap analysis| AOAI
  MI[Managed Identity + RBAC] -.-> FN
  MI -.-> AICU
  MI -.-> SEARCH
  MI -.-> COSMOS
  MI -.-> STORE
  VNET[Virtual Network] --- PE[Private Endpoints] --- STORE
  PE --- COSMOS
  PE --- AICU""",
        how_it_works=(
            "Upload multiple documents (invoices, forms, images, contracts) to a single claim through the "
            "Storage Account. Each document is processed through a 4-stage pipeline in the Function App: "
            "Extract (Azure AI Services pulls OCR/layout/entities) -> Map (schema-based transformation) -> "
            "Evaluate (confidence scoring) -> Save (Cosmos DB + Storage). Once every document in the claim "
            "is processed, a workflow stage calls Azure OpenAI via AI Foundry to produce a consolidated "
            "cross-document summary and a gap analysis that flags missing documents or discrepancies "
            "across the claim."
        ),
        additional_resources=(
            ("Azure AI Content Understanding documentation",
             "https://learn.microsoft.com/azure/ai-services/content-understanding/"),
            ("Azure AI Foundry documentation", "https://learn.microsoft.com/azure/ai-foundry/"),
            ("Azure Functions documentation", "https://learn.microsoft.com/azure/azure-functions/"),
        ),
        key_features=(
            "Multi-document claim processing -- upload multiple files to a single claim and process them "
            "as a batch, with cross-document summarization and gap analysis.",
            "Multi-modal content processing -- OCR-based text extraction plus vision-model processing for "
            "images, tables, and graphs.",
            "AI-powered summarization and gap analysis after all documents in a claim are processed.",
            "Schema-based data transformation -- maps extracted content to custom or industry-defined "
            "schemas, output as JSON.",
            "Confidence scoring for extraction accuracy and schema mapping to drive human-in-the-loop review.",
            "Every service-to-service call is authorized through a managed identity and Azure RBAC.",
        ),
        business_scenario=(
            "Teams that process multi-document claims -- insurance claims, contract packages, invoice "
            "batches, ID verification bundles, or logistics shipment records -- spend significant manual "
            "effort extracting data from each document and then cross-checking the set for missing "
            "pieces or inconsistencies."
        ),
        business_value=(
            "Consistent, schema-based extraction reduces manual data entry and transcription errors.",
            "Automated cross-document summarization and gap analysis surfaces missing documents and "
            "discrepancies before a human ever opens the claim.",
            "Confidence scoring focuses reviewer attention only where the model is uncertain.",
        ),
        use_cases=(
            UseCase("Insurance claims processing", "Claims adjuster",
                    "A claim can include many document types (forms, photos, reports) that must all be "
                    "cross-checked for completeness and consistency.",
                    "Extract structured data from every document in the claim, then summarize and flag "
                    "gaps automatically."),
            UseCase("Invoice / contract review", "Accounts payable analyst, contract reviewer",
                    "Reviewing invoices or contract packages line-by-line for missing fields or terms is "
                    "slow and error-prone.",
                    "Schema-based extraction with confidence scoring highlights fields needing review."),
            UseCase("Logistics shipment records", "Logistics coordinator",
                    "Shipment paperwork arrives from multiple sources in inconsistent formats.",
                    "Normalize shipment documents into a common schema and flag missing/incomplete records."),
        ),
        resources=(
            ResourceEntry("Storage Account", "data/storage-account.bicep", "Inbound document/claim landing zone"),
            ResourceEntry("Event Grid", "data/event-grid.bicep", "Blob-created event trigger"),
            ResourceEntry("Function App", "compute/function-app.bicep", "Extract -> Map -> Evaluate -> Save pipeline"),
            ResourceEntry("Azure AI Services", "ai/ai-services.bicep", "Content Understanding: document/data extraction"),
            ResourceEntry("Azure AI Search", "ai/ai-search.bicep", "Index of extracted content"),
            ResourceEntry("AI Foundry Project", "ai/ai-foundry-project.bicep", "Hosts summarization/gap-analysis models"),
            ResourceEntry("AI Foundry Model Deployment", "ai/ai-foundry-model-deployment.bicep", "Deploys the summarization model"),
            ResourceEntry("Cosmos DB (NoSQL)", "data/cosmos-db-nosql.bicep", "Processes, schemas, and claim results store"),
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
        display_name="Conversation Knowledge Mining (Call Center Copilot)",
        summary="Derive actionable insights from large volumes of conversational/call data using "
                "generative AI -- extract key phrases, model topics, and enable interactive natural "
                "language exploration across conversations, documents, and recordings.",
        description=(
            "Call recordings, transcripts, and related documents land in a Storage Account. An Azure AI "
            "Services account (Content Understanding-style extraction) pulls entities, topics, and "
            "relationships out of the conversations, which are then indexed in Azure AI Search for hybrid "
            "retrieval and written to Cosmos DB for structured analytics and chat history. An App Service "
            "hosts the agent-facing web experience -- a Chat/Explore surface that routes questions to an "
            "AI Foundry-hosted agent reasoning across both semantic search and structured data, and an "
            "Insights surface with an auto-generated, LLM-planned dashboard. Every service-to-service call "
            "uses a managed identity with least-privilege RBAC role assignments instead of keys, secrets "
            "live in Key Vault, and Storage/Cosmos DB/AI Search/AI Foundry sit behind private endpoints."
        ),
        keywords=("call center", "call centre", "contact center", "contact centre", "agent copilot",
                   "call center copilot", "voice analytics", "call transcription", "conversation mining",
                   "conversation knowledge mining"),
        source_reference="https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator",
        architecture_mermaid="""flowchart LR
  U[Analyst / Agent] --> FE[App Service<br/>Home / Explore / Insights UI]
  FE -->|questions| FDRY[Azure AI Foundry<br/>ChatAgent orchestration]
  FDRY --> SEARCH[Azure AI Search<br/>semantic retrieval]
  FDRY --> COSMOS[(Cosmos DB<br/>structured analytics + chat history)]
  U -->|upload calls/docs| STORE[(Storage Account<br/>recordings + transcripts)]
  STORE --> AISVC[Azure AI Services<br/>entity/topic extraction]
  AISVC -->|index write| SEARCH
  AISVC -->|write results| COSMOS
  MI[Managed Identity + RBAC] -.-> FDRY
  MI -.-> SEARCH
  MI -.-> COSMOS
  MI -.-> STORE
  MI -.-> AISVC
  VNET[Virtual Network] --- PE[Private Endpoints] --- SEARCH
  PE --- COSMOS
  PE --- STORE""",
        how_it_works=(
            "Home -- upload call recordings, transcripts, or documents to the Storage Account, or load a "
            "sample scenario pack; processing runs in the background. Explore -- converse with your data "
            "through the App Service UI, which routes questions to an AI Foundry ChatAgent with two tools: "
            "Azure AI Search for semantic retrieval and Cosmos DB for structured analytics -- the agent "
            "reasons across both and returns grounded, cited answers. Insights -- the LLM reads the "
            "dataset's schema and plans an adaptive dashboard of KPIs and charts driven entirely by data, "
            "not hard-coded layouts."
        ),
        additional_resources=(
            ("Azure AI Foundry documentation", "https://learn.microsoft.com/azure/ai-foundry/"),
            ("Azure AI Search documentation", "https://learn.microsoft.com/azure/search/"),
            ("Azure AI Content Understanding documentation",
             "https://learn.microsoft.com/azure/ai-services/content-understanding/"),
        ),
        key_features=(
            "Mined entities and relationships -- extracts entities, topics, and relationships from "
            "unstructured conversations to build a richer knowledge base.",
            "Processes high-volume conversation data at scale, generating embeddings and indexing results "
            "for fast hybrid retrieval.",
            "Visualized insights -- an interactive dashboard surfaces trends, distributions, and outliers.",
            "Natural language interaction -- ask contextual questions and get grounded, cited responses "
            "through an AI Foundry ChatAgent.",
            "LLM-planned insights dashboard -- the system analyzes the data schema, then plans and "
            "computes relevant KPIs and charts automatically.",
            "Every service-to-service call is authorized through a managed identity and Azure RBAC.",
        ),
        business_scenario=(
            "Analysts often work with large volumes of unstructured conversational data, making it "
            "difficult to extract actionable insights quickly and accurately. Traditional tools limit "
            "interaction with data, making it hard to surface patterns or ask the right follow-up "
            "questions without extensive manual exploration."
        ),
        business_value=(
            "Better decision-making -- summarized, contextualized data helps organizations make informed "
            "strategic decisions that drive operational improvements at scale.",
            "Time saved -- automated insight extraction and scalable data exploration reduce manual "
            "analysis effort.",
            "Interactive data insights -- employees engage directly with conversational data using "
            "natural language.",
            "Scalability -- handles increasing volumes of conversational data without proportional "
            "resource increases.",
        ),
        use_cases=(
            UseCase("Contact Center (IT Helpdesk)", "Helpdesk Analyst",
                    "High volumes of IT helpdesk call transcripts make it hard to mine sentiment, cluster "
                    "recurring topics, and measure agent performance.",
                    "Sentiment analysis, topic clustering, and agent performance insights over call "
                    "transcripts, with grounded chat exploration and an auto-generated dashboard."),
            UseCase("Mortgage Application Review", "Loan Analyst",
                    "Reviewing lengthy housing reports and purchase contracts manually is slow and "
                    "error-prone.",
                    "Document summarization, clause extraction, and risk analysis across housing reports "
                    "and purchase contracts."),
            UseCase("Telecom Call Analysis", "Operations Analyst",
                    "Call transcripts and audio recordings are difficult to transcribe, cluster, and act "
                    "on at scale.",
                    "Transcription, sentiment breakdowns, and topic clustering across call transcripts and "
                    "recordings."),
        ),
        resources=(
            ResourceEntry("App Service (agent/analyst UI)", "compute/app-service.bicep", "Hosts the Home/Explore/Insights web experience"),
            ResourceEntry("App Service Plan", "compute/app-service-plan.bicep", "Compute plan for the App Service"),
            ResourceEntry("Storage Account", "data/storage-account.bicep", "Call recordings, transcripts, and documents"),
            ResourceEntry("Azure AI Services", "ai/ai-services.bicep", "Entity/topic extraction from conversations"),
            ResourceEntry("Azure AI Search", "ai/ai-search.bicep", "Hybrid (semantic + keyword) retrieval index"),
            ResourceEntry("AI Foundry Project", "ai/ai-foundry-project.bicep", "Hosts the ChatAgent and orchestration"),
            ResourceEntry("AI Foundry Model Deployment", "ai/ai-foundry-model-deployment.bicep", "Deploys the chat/summarization model"),
            ResourceEntry("Cosmos DB (NoSQL)", "data/cosmos-db-nosql.bicep", "Structured analytics store and chat history"),
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
        source_reference="(mocked pattern -- not modeled on a specific public repo, for internal testing only)",
        architecture_mermaid="""flowchart LR
  DEV[Devices / telemetry sources] --> EH[Event Hub<br/>ingestion]
  EH --> FN[Function App<br/>rule evaluation]
  FN -->|raw/aggregated data| STORE[(Storage Account)]
  FN -->|alert state| COSMOS[(Cosmos DB)]
  CFG[App Configuration<br/>alerting thresholds] -.-> FN
  FN -->|condition fires| EG[Event Grid<br/>alert fan-out]
  FN --> LAW[Log Analytics Workspace]
  LAW --> WB[Workbook]
  LAW --> DASH[Portal Dashboard]
  MI[Managed Identity + RBAC] -.-> FN
  MI -.-> STORE
  MI -.-> COSMOS
  MI -.-> EH
  VNET[Virtual Network] --- PE[Private Endpoints] --- STORE
  PE --- COSMOS""",
        how_it_works=(
            "High-volume telemetry streams into the Event Hub. The Function App consumes each batch, "
            "evaluates it against alerting rules/thresholds stored in App Configuration, and writes both "
            "raw and aggregated results to the Storage Account and Cosmos DB (for alert-state tracking). "
            "When a rule condition fires, the function publishes an alert event to Event Grid for "
            "downstream routing (e.g. notifications, ticketing). Operational workbooks and a portal "
            "dashboard built on Log Analytics/Application Insights give on-call teams live visibility into "
            "both the pipeline's health and the alerts it has raised."
        ),
        additional_resources=(
            ("Azure Event Hubs documentation", "https://learn.microsoft.com/azure/event-hubs/"),
            ("Azure Functions documentation", "https://learn.microsoft.com/azure/azure-functions/"),
            ("Azure Monitor documentation", "https://learn.microsoft.com/azure/azure-monitor/"),
        ),
        key_features=(
            "High-throughput telemetry ingestion via Event Hub, decoupled from rule evaluation.",
            "Alerting thresholds/rules are externalized in App Configuration -- no redeploy needed to tune them.",
            "Event Grid fan-out lets any number of downstream systems react to a fired alert.",
            "Operational workbooks and a portal dashboard give on-call teams a single-pane view of system "
            "health and active alerts.",
            "Every service-to-service call is authorized through a managed identity and Azure RBAC.",
        ),
        business_scenario=(
            "Teams operating high-volume streaming/IoT workloads need to detect conditions of interest "
            "(thresholds, anomalies, SLA breaches) as they happen, not hours later in a batch report, and "
            "need on-call staff to see both the raw telemetry and the alerts it produced in one place."
        ),
        business_value=(
            "Near real-time detection reduces the time between an incident occurring and a team being "
            "notified.",
            "Externalized alerting thresholds let operations teams tune sensitivity without a code deployment.",
            "A unified operational dashboard reduces the number of tools on-call staff must check during "
            "an incident.",
        ),
        use_cases=(
            UseCase("IoT device health monitoring", "Operations/on-call engineer",
                    "Thousands of devices report telemetry continuously; manual review can't keep up with "
                    "the volume.",
                    "Stream device telemetry through Event Hub, evaluate health rules in near real time, "
                    "and alert on-call staff the moment a device degrades."),
            UseCase("SLA / threshold breach alerting", "Site reliability engineer",
                    "Detecting an SLA breach after the fact is too late to prevent customer impact.",
                    "Evaluate streaming metrics against configurable thresholds and fire alerts the moment "
                    "a breach condition is met."),
            UseCase("Anomaly detection on transaction streams", "Fraud/risk analyst",
                    "Reviewing transaction logs in batch misses time-sensitive fraud patterns.",
                    "Stream transactions through the pipeline and raise near-real-time alerts on anomalous "
                    "patterns for investigation."),
        ),
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
    folder (001-wip-repo-structure/technical-patterns/<id>/README.md).

    Mirrors the section structure of a real Azure solution-accelerator
    README (Solution overview / architecture diagram / how it works / key
    features / resources / business scenario / business value / use cases /
    supporting documentation) -- see `pattern.source_reference` for the
    real public repo each pattern's content is modeled on (mocked for
    'realtime-alerts'). This is deliberate: it lets a human (or the agent
    itself) read this file exactly like they would a real repo's README to
    understand what the pattern deploys and why, not just a bare list.

    The "## Resources deployed" table is also the machine-parseable source
    of truth read back by get_pattern_resources() -- keep its exact
    "| Display | `module/key.bicep` | Purpose |" row shape if you hand-edit
    it, since parse_resource_table() depends on that shape."""
    resource_rows = "\n".join(
        f"| {r.display_name} | `{r.module_key}` | {r.purpose} |" for r in pattern.resources
    )
    key_features_md = "\n".join(f"- {feat}" for feat in pattern.key_features)
    business_value_md = "\n".join(f"- {val}" for val in pattern.business_value)
    additional_resources_md = "\n".join(f"- [{text}]({url})" for text, url in pattern.additional_resources)
    use_cases_md = "\n".join(
        f"| {uc.title} | {uc.persona} | {uc.challenge} | {uc.summary} |" for uc in pattern.use_cases
    )

    return f"""# {pattern.display_name}

{pattern.summary}

<div align="center">

[**SOLUTION OVERVIEW**](#solution-overview) &nbsp;|&nbsp; [**RESOURCES DEPLOYED**](#resources-deployed) &nbsp;|&nbsp; [**BUSINESS SCENARIO**](#business-scenario) &nbsp;|&nbsp; [**SUPPORTING DOCUMENTATION**](#supporting-documentation)

</div>

> [!NOTE]
> This README is mocked/generated placeholder documentation for the `{pattern.id}` technical pattern,
> used only so `infra_composer_agent` has a concrete pattern to read and confirm resources from. Its
> content/structure is modeled on: {pattern.source_reference}

## Solution overview

{pattern.description}

### Architecture

```mermaid
{pattern.architecture_mermaid}
```

### How it works

{pattern.how_it_works}

### Additional resources

{additional_resources_md}

### Key features

<details open>
<summary>Click to learn more about the key features this pattern enables</summary>

{key_features_md}

</details>

## Resources deployed

> This table is read directly by `infra_composer_agent` (see `tech_patterns.get_pattern_resources()`)
> to build its resource plan -- edit it here and the agent will pick up your changes on its next run.
> The `Module` column must match an exact module key from the source module library
> (`infra_new/avm/modules/<category>/<name>.bicep` on the `infra-core-modules-copy` branch).

| Resource | Module | Purpose |
|---|---|---|
{resource_rows}

## Business scenario

{pattern.business_scenario}

### Business value

<details>
<summary>Click to learn more about the value this pattern provides</summary>

{business_value_md}

</details>

### Use cases

<details>
<summary>Click to learn more about the use cases this pattern supports</summary>

| Use case | Persona | Challenges | Summary |
|---|---|---|---|
{use_cases_md}

</details>

## Supporting documentation

### How to deploy

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

### Security guidelines

Every service-to-service call in this pattern is authorized through a managed identity and Azure RBAC
role assignments (see the `identity/managed-identity.bicep` and `identity/role-assignments.bicep` rows
above) rather than connection strings or keys. Data services are reachable only through private
endpoints, with public network access disabled.

> This README was generated automatically as placeholder documentation for the `{pattern.id}` technical
> pattern. Regenerate it any time with
> `python tools/infra_composer_agent/generate_pattern_readmes.py`.
"""

