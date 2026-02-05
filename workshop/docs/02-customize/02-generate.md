# Generate Custom Data

## Run the AI Generator

With your `.env` configured, generate customer-specific data:

```bash
python scripts/00_build_solution.py --clean
```

| Flag | Purpose |
|------|---------|
| `--clean` | Reset Fabric artifacts (required when switching scenarios) |

### Alternative: Inline Parameters

Override `.env` settings directly from the command line:

```bash
python scripts/00_build_solution.py --clean \
  --industry "Insurance" \
  --usecase "Property insurance with claims processing and policy management"
```

## Generation Process

```
============================================================
Generating Custom Data with AI
============================================================

Industry: Insurance
Use Case: Property insurance with claims processing and policy management

[1/4] Generating ontology configuration...
  → Analyzing use case for entities and relationships
  → Created: Policies, Claims, Customers, Agents
  → Defined: 6 relationships, 4 business rules
  ✓ ontology_config.json

[2/4] Generating structured data (CSV)...
  → policies.csv (16 rows) — Policy details, coverage, premiums
  → claims.csv (40 rows) — Claim status, amounts, dates
  → customers.csv (20 rows) — Policyholder information
  → agents.csv (8 rows) — Agent assignments
  ✓ 4 CSV files generated

[3/4] Generating documents (PDF)...
  → claims_process.pdf — How to file and process claims
  → coverage_guide.pdf — Policy coverage explanations
  → underwriting_policy.pdf — Risk assessment guidelines
  ✓ 3 documents generated

[4/4] Generating sample questions...
  → 15 sample questions spanning data, documents, and combined
  ✓ sample_questions.txt

============================================================
Data generated: data/20260202_143022_insurance/
============================================================
```

## Review Generated Content

Check what was created:

```bash
# View the generated files
ls data/*/

# Read sample questions for testing
cat data/*/config/sample_questions.txt
```

### Sample Questions (Insurance Example)

```
# Structured data questions (Fabric IQ)
How many open claims do we have?
What's the total value of claims filed this month?
Which agents have the most policies?

# Unstructured data questions (Foundry IQ)
What's our process for filing a property claim?
What does our standard homeowner policy cover?
What are our underwriting criteria for high-risk properties?

# Combined questions (Both)
Which open claims are approaching our SLA deadline based on our process guidelines?
Do any current claims involve coverage types not in our standard policy?
```

## Expected Output

The complete build takes ~5 minutes:

```
============================================================
Building Solution: Insurance
============================================================

[01a/07] Generating AI data...
  ✓ Ontology, CSVs, PDFs, and questions generated

[02/07] Setting up Fabric workspace...
  ✓ Cleaned previous artifacts
  ✓ Lakehouse: iqworkshop_lakehouse
  ✓ Warehouse: iqworkshop_warehouse

[03/07] Loading data into Fabric...
  ✓ policies.csv → 16 rows
  ✓ claims.csv → 40 rows
  ✓ customers.csv → 20 rows
  ✓ agents.csv → 8 rows

[04/07] Generating NL2SQL prompt...
  ✓ Schema prompt created for insurance domain

[05/07] Creating Fabric Data Agent...
  ✓ Agent: fabric-agent-insurance

[06/07] Uploading documents to AI Search...
  ✓ 3 documents → 24 chunks indexed

[07/07] Creating Orchestrator Agent...
  ✓ Agent: insurance-multi-agent

============================================================
Build complete! Ready for customer PoC.
============================================================
```

## Troubleshooting

### AI generation times out

- Check your internet connection
- Try with `--size small` for faster generation
- Verify Azure AI Services quota

### Fabric errors on --clean

- Ensure `FABRIC_WORKSPACE_ID` is correct
- Check you have Contributor access to the workspace
- Wait a minute and retry (Fabric operations can be slow)

---

[← Overview](index.md) | [Test Your PoC →](03-demo.md)
