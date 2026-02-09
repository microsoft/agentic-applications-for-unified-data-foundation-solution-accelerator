# Build solution

## Run the Full Pipeline

One command builds the solution including data processing and agent creation:

Fabric Workspace Mode

```bash
python scripts/00_build_solution.py --from 02
```

> **Note:** Press **Enter** key to start or **Ctrl+C** to cancel the process.

Azure Only Mode (if you ran `azd env set AZURE_ENV_ONLY true` before deploying)
```bash
python scripts/00_build_solution.py --from 04
```

> **Note:** Press **Enter** key to start or **Ctrl+C** to cancel the process.

This uses the `data/default` folder and runs all setup steps:

| Step | What Happens | Time |
|------|--------------|------|
| 02 | Setup Fabric workspace | ~30s |
| 03 | Load data into Fabric | ~1min |
| 04 | Generate NL2SQL prompt | ~5s |
| 05 | Create Fabric Data Agent | ~30s |
| 06 | Upload documents to AI Search | ~1min |
| 07a | Create Orchestrator Agent | ~10s |

## Expected Output

```
> [02] Create Fabric Items... [OK]
> [03] Load Data into Fabric... [OK]
> [04] Generate Agent Prompt... [OK]
> [05] Create Fabric Data Agent... [OK]
> [06] Upload to AI Search... [OK]
> [07] Create Foundry Agent... [OK]

------------------------------------------------------------
[OK] Pipeline completed successfully!

Next: python scripts/08_test_agent.py

```

## Test the Fabric Data Agent
1. Go to your [Microsoft Fabric](https://app.fabric.microsoft.com/) workspace
2. Select "New item" 
3. Search for and select "Data Agent" 
4. Select add data source and select your Ontology resource created in the previous step. 
5. Select Agent instructions and paste the below instructions. 
``` 
You are a helpful assistant that can answer user questions using data.
Support group by in GQL.
```

## Test the Agent

```bash
python scripts/08_test_agent.py
```


### Sample Conversation

```
============================================================
AI Agent Chat (Fabric SQL + Native Search)
============================================================
Chat Agent: dauypdob4c4d2k-ChatAgent
SQL Mode: Fabric Lakehouse
Lakehouse: <workshop_lakehouse_1>
Type 'quit' to exit, 'help' for sample questions

------------------------------------------------------------

You: How many tickets have priority = 'High'?

Agent: There are **4 tickets** with priority **High**.

You: What is the average score from inspections?

Agent: The average score from inspections is **77**.

You: What are the requirements for handling customer tickets?

Agent: Here are the requirements for handling customer tickets:

1. **Ticket Handling Procedures**:
   - All customer tickets must be acknowledged within **1 hour**.
   - Closed tickets should provide feedback to clients.

2. **Priority Definitions**:
   - High priority tickets must be resolved within **4 hours**.
   - Medium priority tickets should be resolved within **24 hours**.
   - Low priority tickets should not exceed **72 hours** for resolution.

3. **Compliance and Service Level Agreements (SLAs)**:
   - Define minimum service quality levels.
   - For major outages, resolutions must be completed within **4 hours**.

4. **Documentation Requirements**:
   - All outages and tickets must be documented, including resolution times and customer impacts.

5. **Response Time Expectations**:
   - Representatives must respond to outage inquiries within **1 hour** during business hours and within **3 hours** outside of business hours.

6. **Ticket Escalation Process**:
   - All outages and tickets must be documented, including resolution times and customer impacts.

7. **Customer Feedback Mechanism**:
   - Gather customer feedback through follow-up surveys sent within one week of ticket closure.

These procedures ensure timely communication, accountability, and continuous improvement in customer service.

You: Are we meeting our resolution targets for high priority tickets according to our Ticket Management Policy?

Agent: According to the Ticket Management Policy, high priority tickets must be resolved within 4 hours. Here’s the current status regarding high priority tickets:

- **Total High Priority Tickets:** 4
- **High Priority Tickets Resolved Within Target (4 hours):** 1

This indicates that we are currently not meeting our resolution target for high priority tickets, as only 1 out of 4 tickets were resolved within the specified timeframe.

You: quit
```

## Checkpoint

!!! success "Solution Deployed!"
    You now have a working solution with:
    
    - [x] **Data queries** via Fabric IQ or Azure SQL function tools for AzureOnly mode
    - [x] **Foundry IQ** retrieving document knowledge
    - [x] **Orchestrator Agent** combining both sources
    
    ---

[← Configure dev environment](03-configure.md) | [Customize for your use case →](../02-customize/index.md)
