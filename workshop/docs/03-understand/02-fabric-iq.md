# Fabric IQ: Data Intelligence

## What is Fabric IQ?

Fabric IQ is a semantic intelligence platform that connects AI agents to business data. It goes beyond simple database queries by understanding the meaning of your data through an **Ontology**.

## What is an Ontology?

An ontology is a semantic model that helps AI understand your business:

| Component | Purpose | Example |
|-----------|---------|---------|
| **Entities** | Business objects | Outages, Tickets, Regions |
| **Relationships** | How entities connect | Ticket → related to → Outage |
| **Rules** | Business logic | "Critical Outage = customerImpact > 1000" |
| **Actions** | Queryable operations | GetOutagesByRegion, GetTicketResolutionTime |

## How NL→SQL Works

```
User: "Which outages had the most customer impact last month?"

┌─────────────────────────────────────────────────────────────┐
│  Step 1: UNDERSTAND                                         │
│  Agent interprets intent using ontology:                    │
│  • "outages" → NetworkOutages entity                        │
│  • "customer impact" → customersAffected column              │
│  • "last month" → date filter                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: TRANSLATE                                          │
│  Generate SQL from semantic understanding:                  │
│                                                             │
│  SELECT outageId, region, customersAffected, duration       │
│  FROM network_outages                                       │
│  WHERE outageDate >= DATEADD(month, -1, GETDATE())          │
│  ORDER BY customersAffected DESC                            │
│  LIMIT 10                                                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: EXECUTE & EXPLAIN                                  │
│  Run against Fabric, format response:                       │
│                                                             │
│  "Here are the outages with highest customer impact:        │
│   1. OUT-1042 (Northeast) - 15,234 customers                │
│   2. OUT-1089 (West) - 12,891 customers                     │
│   3. OUT-1056 (South) - 8,445 customers"                    │
└─────────────────────────────────────────────────────────────┘
```

## Why Ontology Matters

### Without Ontology: Brittle Keyword Matching

```
User: "Show me our best customers"
System: ??? (what makes a customer "best"?)
```

### With Ontology: Business Understanding

```yaml
# Ontology defines:
rules:
  - name: "Premium Customer"
    definition: "totalSpend > 10000 AND orderCount > 5"
  - name: "Best Customer"
    definition: "Premium Customer with healthScore > 80"
```

```
User: "Show me our best customers"
Agent: Uses "Best Customer" rule → Correct SQL → Meaningful results
```

## The Power of Combined Intelligence

| Question Type | Source | Example |
|---------------|--------|---------|
| **Policy/Process** | Foundry IQ (Documents) | "What's our outage notification policy?" |
| **Metrics/Numbers** | Fabric IQ (Data) | "What's our average resolution time?" |
| **Combined** | Both | "Are we meeting our SLA targets?" |

### Combined Example

```
User: "Are we meeting our ticket resolution SLA?"

Agent thinking:
1. First, I need the SLA targets (documents)
   → Search Foundry IQ → "Critical: 4 hours, High: 8 hours, Medium: 24 hours"

2. Then, I need actual performance (data)
   → Query Fabric IQ → "Avg critical: 3.2 hrs, High: 7.1 hrs, Medium: 18.5 hrs"

3. Compare and respond:
   "Yes, we're meeting all SLA targets. Critical tickets average 
   3.2 hours (target: 4 hours), High priority averages 7.1 hours 
   (target: 8 hours), and Medium averages 18.5 hours (target: 24 hours)."
```

## Customer Talking Points

| Question | Response |
|----------|----------|
| "Why not just let users write SQL?" | "Most users can't write SQL. And even those who can may not know the schema. Natural language lets anyone query data." |
| "How do you handle ambiguous terms?" | "The ontology defines business terms. 'Critical outage', 'high impact', 'overdue ticket' all have precise definitions your business controls." |
| "What about performance?" | "Queries run against Fabric's optimized engine. The NL→SQL translation happens once, then it's standard SQL execution." |

## Technical Details

### Fabric Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Microsoft Fabric                         │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Lakehouse   │ →  │  Warehouse   │ →  │  Semantic    │  │
│  │  (Raw Data)  │    │  (SQL Tables)│    │  Model       │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                ↓            │
│                                          ┌──────────┐       │
│                                          │ Fabric IQ│       │
│                                          │ Ontology │       │
│                                          └──────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### Ontology Configuration

```json
{
  "entities": [
    {
      "name": "NetworkOutages",
      "table": "network_outages",
      "key": "outageId",
      "attributes": ["region", "outageType", "customersAffected", "duration"]
    }
  ],
  "relationships": [
    {
      "name": "related_to_outage",
      "from": "TroubleTickets",
      "to": "NetworkOutages",
      "type": "many-to-one"
    }
  ],
  "businessRules": [
    {
      "name": "CriticalOutage",
      "entity": "NetworkOutages",
      "condition": "customersAffected > 1000"
    }
  ]
}
```

---

[← Foundry IQ: Documents](01-foundry-iq.md) | [Cleanup →](../04-cleanup/index.md)
