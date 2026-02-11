# Build solution

## Run the Full Pipeline

One command builds the solution including data processing and agent creation:

Fabric Workspace Mode

```bash
python scripts/00_build_solution.py --from 02 --fabric-workspace-id <your-workspace-id>
```

> **Note:** If you omit `--fabric-workspace-id`, the script will prompt you for it interactively. Press **Enter** key to start or **Ctrl+C** to cancel the process.

Azure Only Mode (if you ran `azd env set AZURE_ENV_ONLY true` before deploying)
```bash
python scripts/00_build_solution.py --from 04
```

> **Note:** Press **Enter** key to start or **Ctrl+C** to cancel the process.

This uses the `data/default` folder and runs all setup steps:

| Step | What Happens | Time |
|------|--------------|------|
| 02 | Create Fabric Lakehouse | ~30s |
| 03 | Load data into Fabric | ~1min |
| 04 | Generate Agent Prompt | ~5s |
| 06 | Upload documents to AI Search | ~1min |
| 07 | Create Foundry Agent | ~10s |

## Expected Output

```
> [02] Create Fabric Lakehouse... OK
> [03] Load Data into Fabric... OK
> [04] Generate Agent Prompt... OK
> [06] Upload to AI Search... OK
> [07] Create Foundry Agent... OK

Done! 5/5 steps completed
Next: python scripts/08_test_agent.py

```

<!-- ## Create the Ontology

Before testing the Fabric Data Agent, set up an Ontology in Microsoft Fabric for your scenario.

Follow the step-by-step guide: **[Create Ontology](05-ontology-creation.md)** to set up the default use case. -->

This sets up entity types (Tickets, Inspections), data bindings from your Lakehouse tables, and relationships between them.

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

> Note: The Ontology set up may take up to 15 minutes so retry after some time if you don't see good responses. 

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


You: What is the average score from inspections?

Agent: The average score from inspections is **77**.

You: What constitutes a failed inspection?

Agent: A failed inspection is defined by the following criteria:

1. **Score Requirement**: All inspections must achieve a minimum score of 80 out of 100.
2. **Follow-up Actions**: Inspections falling below this threshold will require immediate review and corrective action, along with follow-up assessments within 48 hours.

Teams must document all corrective actions taken.

You: Do any inspections violate quality control standards in our Inspection Procedures?

Agent: Yes, there are several inspections that violate the quality control standards as they scored below the required minimum of 80. Here are the details:

| Inspection ID  | Customer Name | Result | Score |
|----------------|---------------|--------|-------|
| INSPECTION002  | Customer 4    | Pass   | 65    |
| INSPECTION009  | Customer 10   | Pass   | 60    |
| INSPECTION010  | Customer 5    | Pass   | 71    |
| INSPECTION011  | Customer 6    | Pass   | 74    |
| INSPECTION012  | Customer 1    | Fail   | 69    |
| INSPECTION013  | Customer 15   | Pass   | 69    |
| INSPECTION016  | Customer 10   | Pass   | 64    |
| INSPECTION019  | Customer 11   | Pass   | 73    |
| INSPECTION020  | Customer 6    | Pass   | 72    |
| INSPECTION022  | Customer 2    | Pass   | 62    |
| INSPECTION024  | Customer 7    | Fail   | 70    |
| INSPECTION026  | Customer 3    | Pass   | 67    |
| INSPECTION027  | Customer 5    | Pass   | 69    |
| INSPECTION028  | Customer 8    | Pass   | 62    |
| INSPECTION029  | Customer 10   | Pass   | 75    |
| INSPECTION030  | Customer 11   | Pass   | 60    |
| INSPECTION031  | Customer 8    | Pass   | 60    |
| INSPECTION032  | Customer 3    | Pass   | 62    |
| INSPECTION033  | Customer 2    | Pass   | 68    |
| INSPECTION036  | Customer 15   | Pass   | 62    |
| INSPECTION037  | Customer 3    | Pass   | 67    |
| INSPECTION040  | Customer 4    | Pass   | 74    |

These inspections need to be reviewed and may require corrective actions.

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
