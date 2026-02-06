# Build & Test (Customer PoC)

## Test your solution

After generation completes, test the agent:

```bash
python scripts/08_test_agent.py
```

## Use the Generated Sample Questions

Each scenario generates ready-to-use sample questions in the data folder:

```bash
# View sample questions for your scenario
cat data/default/config/sample_questions.txt
```

The file contains three categories of questions:

| Category | Source | Example |
|----------|--------|---------|
| **Structured data questions** | Fabric IQ (data) | "How many open claims do we have?" |
| **Unstructured data questions** | Foundry IQ (docs) | "What's our process for filing a property claim?" |
| **Combined questions** | Both sources | "Which claims are approaching our SLA deadline based on our process guidelines?" |

!!! tip "Use these questions first"
    The generated questions are tailored to your scenario's data and documents. Start with these before improvising.

## Testing Tips

### Start with structured data questions

Show the power of natural language over structured data:

```
"How many [entities] do we have?"
"What's the total [metric] for [time period]?"
"Show me the top 5 [entities] by [metric]"
```

### Then unstructured data questions

Demonstrate intelligent document retrieval:

```
"What's our policy on [topic]?"
"How do we handle [process]?"
"What are the requirements for [action]?"
```

### Finish with combined questions

This is the "wow" moment: questions that need both sources:

```
"Based on our [policy], which [entities] need attention?"
"Are we meeting our [documented SLA] according to the data?"
"Which [items] don't comply with our [policy/guidelines]?"
```

## Prepare your test script

Before customer meetings, prepare 5-7 questions:

| # | Question Type | Example |
|---|---------------|---------|
| 1 | Structured data | "How many open claims do we have?" |
| 2 | Structured data | "What's the total value of claims filed this month?" |
| 3 | Structured data | "Which agents have the most policies?" |
| 4 | Unstructured data | "What's our process for filing a property claim?" |
| 5 | Unstructured data | "What does our standard homeowner policy cover?" |
| 6 | **Combined** | "Which open claims are approaching our SLA deadline based on our process guidelines?" |
| 7 | **Combined** | "Do any current claims involve coverage types not in our standard policy?" |

!!! tip "Let customers ask questions"
    After your prepared questions, let customers ask their own questions. This shows the solution handles real scenarios, not just scripted ones.

## Deploy the Web Application (Optional)

If you want to deploy a web UI for your solution:

### Step 1: Enable app deployment and deploy

```bash
azd env set AZURE_ENV_DEPLOY_APP true
azd up
```

!!! warning "Wait for Completion"
    Deployment takes 5-7 minutes. Don't proceed until you see the success message with the web app URL.

### Step 2: Reconfigure the agent (Azure-only mode)

!!! note "Only for Azure-only mode"
    If you set `AZURE_ENV_ONLY=true` before deployment, run this additional step to update the agent configuration:
    
    ```bash
    python scripts/00_build_solution.py --from 05
    ```
    
    If you're using Fabric mode, skip this step.

### Step 3: Access the application

After deployment completes, the web app URL will be displayed in the output. Open it in your browser to interact with the agent through a chat interface.

## Checkpoint

!!! success "Ready for Customer PoC"
    Your custom PoC should:
    
    - [x] Answer structured data questions accurately
    - [x] Retrieve relevant unstructured document content
    - [x] Combine sources for complex questions
    - [x] Use industry-appropriate terminology
    
    **Next:** Review [Deep dive](../03-understand/index.md) to prepare for technical questions

## Quick Reference: Regenerate for another industry use case

```bash
# Edit .env with new customer's industry and use case, then:
python scripts/00_build_solution.py --clean

# Or inline:
python scripts/00_build_solution.py --clean \
  --industry "New Industry" \
  --usecase "New use case description"
```

---

[← Generate & Build](02-generate.md) | [Deep dive →](../03-understand/index.md)
