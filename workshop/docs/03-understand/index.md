# Deep dive

This section prepares you for technical questions during customer conversations.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User Question                                │
│            "Which outages exceeded our policy thresholds?"          │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Orchestrator Agent                              │
│                                                                     │
│   1. Analyzes question                                              │
│   2. Decides which tool(s) to use                                   │
│   3. Orchestrates calls                                             │
│   4. Synthesizes response                                           │
└─────────────────────────────────────────────────────────────────────┘
                    │                           │
                    ▼                           ▼
    ┌───────────────────────┐   ┌───────────────────────┐
    │      Foundry IQ       │   │       Fabric IQ       │
    │  (Document Search)    │   │    (Data Queries)     │
    │                       │   │                       │
    │  • Agentic retrieval  │   │  • Ontology           │
    │  • Plan, iterate,     │   │  • NL → SQL           │
    │    reflect            │   │  • Business rules     │
    │  • Citations          │   │                       │
    └───────────────────────┘   └───────────────────────┘
              │                           │
              ▼                           ▼
    ┌───────────────────────┐   ┌───────────────────────┐
    │   Azure AI Search     │   │   Microsoft Fabric    │
    │   (Vector Index)      │   │   (Lakehouse/WH)      │
    └───────────────────────┘   └───────────────────────┘
```

## Key Technologies

| Component | What It Does | Customer Benefit |
|-----------|--------------|------------------|
| **Foundry IQ** | Intelligent search over documents | Answers policy/process questions with citations |
| **Fabric IQ** | Natural language to SQL | Answers data questions without writing queries |
| **Orchestrator Agent** | Orchestrates both tools | Single interface for all enterprise knowledge |

## Common Customer Questions

### "How is this different from ChatGPT?"

> **Your answer:** "ChatGPT uses general internet knowledge. This agent is grounded in YOUR documents and YOUR data. It can't hallucinate about your outage policies because it retrieves the actual policy. It can't make up ticket metrics because it queries your actual database."

### "Is our data secure?"

> **Your answer:** "Everything runs in your Azure tenant. Documents stay in your AI Search index. Data stays in your Fabric workspace. The AI models are Azure OpenAI, not public endpoints. Authentication uses your Entra ID."

### "How accurate is it?"

> **Your answer:** "Foundry IQ uses agentic retrieval — the AI plans what to search, evaluates results, and iterates if needed. For data, Fabric IQ translates to SQL and runs against actual data. Both provide citations so users can verify."

### "How hard is it to set up?"

> **Your answer:** "This PoC took [X] minutes. For production, you'd connect your real documents and data sources. The accelerator handles all the plumbing — embedding, indexing, agent configuration."

## Deep Dive Pages

- **[Foundry IQ: Documents](01-foundry-iq.md)**: How agentic retrieval works
- **[Fabric IQ: Data](02-fabric-iq.md)**: How ontology enables NL→SQL

---

[← Test Your PoC](../02-customize/03-demo.md) | [Foundry IQ: Documents →](01-foundry-iq.md)
