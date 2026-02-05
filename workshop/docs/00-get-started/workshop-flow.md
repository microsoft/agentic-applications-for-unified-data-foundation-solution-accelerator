# Workshop Flow

## Step 1: Deploy solution

Deploy infrastructure and run with pre-built **sample** scenario:

- Deploy **Microsoft Foundry** and Azure resources (AI Services, AI Search, Storage)
- Configure **Microsoft Fabric** connection
- Configure your development environment
- See the agent working with sample data
- Takes ~15 minutes

## Step 2: Customize for your use case

Generate custom data for **each use case**:

| Customer Industry | Use Case Example | Sample Questions |
|-------------------|------------------|------------------|
| Telecommunications | Network outages + service policies | "Which outages exceeded our SLA threshold?" |
| Manufacturing | Equipment data + maintenance docs | "Which machines are overdue for maintenance per our schedule?" |
| Retail | Product catalog + return policies | "What's our return policy for electronics over $500?" |
| Finance | Account data + lending policies | "Which loan applications meet our approval criteria?" |
| Insurance | Claims data + policy documents | "What's the status of claims filed this week vs our SLA?" |
| Energy | Grid monitoring + safety protocols | "Which substations are operating above 80% capacity?" |
| **Customer X** | **Their data + Their docs** | **Their burning questions** |

!!! tip "Pre-PoC prep"
    Run Step 2 before your PoC. Enter the industry and a brief use case description. The AI generates realistic sample data, documents, and test questions tailored to your scenario.

## Step 3: Deep dive

Prepare for technical questions in customer conversations:

- **Fabric IQ**: How ontology translates business questions to SQL
- **Foundry IQ**: How agentic retrieval plans, iterates, and reflects
- **Orchestrator Agent**: How the agent decides which source to query

---

[← Get Started](index.md) | [Deploy solution →](../01-deploy/index.md)
