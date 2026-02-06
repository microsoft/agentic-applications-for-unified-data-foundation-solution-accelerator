# Build solution

## Run the Full Pipeline

One command builds the solution including data processing and agent creation:

Fabric Workspace Mode

```bash
python scripts/00_build_solution.py --from 02
```

Azure Only Mode (if you ran `azd env set AZURE_ENV_ONLY true` before deploying)
```bash
python scripts/00_build_solution.py --from 04
```

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
Orchestrator Agent Chat
============================================================
Type 'quit' to exit, 'help' for sample questions

------------------------------------------------------------

You: How many outages occurred last month?

Agent: Based on the database, there were 16 network outages recorded 
       in January 2024.

You: What are the policies for notifying customers of outages?

Agent: According to our Customer Service Policies document:
       
       - Customers must be notified within 15 minutes of confirmed outage
       - Use SMS, email, and app notifications for affected customers
       - Provide estimated restoration time when available
       - Send updates every 30 minutes during extended outages
       
       [Source: customer_service_policies.pdf]

You: Which outages exceeded the maximum duration defined in our policy?

Agent: Let me check the outage data against our policy thresholds...

       Based on a 4-hour (240 minute) maximum duration policy, these 
       outages exceeded the threshold:
       
       | Outage ID | Duration (min) | Impact Level |
       |-----------|----------------|--------------|
       | OUT011    | 472            | Medium       |
       | OUT004    | 446            | Low          |
       | OUT007    | 445            | Low          |
       | OUT005    | 417            | Medium       |
       | OUT003    | 411            | Low          |
       
       5 outages exceeded the policy maximum duration.

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
