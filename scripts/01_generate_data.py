"""
01a - Generate Sample Data using AI Agent
Uses AI to generate a custom data generation script for ANY industry and use case.

Usage:
    python 01_generate_sample_data.py --industry "Telecommunications" --usecase "Network outage tracking"
    python 01_generate_sample_data.py  # Interactive mode

The agent will:
    1. Generate a custom Python script for your scenario
    2. Execute the script to create all data files
    3. Save the generated script for reference

Output structure:
    data/<timestamp>_<industry>/
        config/     - ontology_config.json, sample_questions.txt
        tables/     - CSV files
        documents/  - PDF files
"""

import argparse
import os
import sys
from datetime import datetime

script_dir = os.path.dirname(os.path.abspath(__file__))

# Load environment from azd + project .env
from load_env import load_all_env
load_all_env()

from azure.identity import DefaultAzureCredential

# ============================================================================
# Configuration
# ============================================================================

# Azure services - from azd environment
FOUNDRY_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")

if not FOUNDRY_ENDPOINT:
    print("ERROR: AZURE_AI_PROJECT_ENDPOINT not set")
    print("       Run 'azd up' to deploy Azure resources")
    sys.exit(1)

# ============================================================================
# Parse Arguments
# ============================================================================

p = argparse.ArgumentParser(description="Generate sample data using AI for any industry/use case")
p.add_argument("--industry", help="Industry name (overrides .env INDUSTRY)")
p.add_argument("--usecase", help="Use case description (overrides .env USECASE)")
p.add_argument("--size", choices=["small", "medium", "large"],
               help="Data size (overrides .env DATA_SIZE)")
args = p.parse_args()

# Priority: CLI args > .env > interactive
industry = args.industry or os.getenv("INDUSTRY")
usecase = args.usecase or os.getenv("USECASE")
size = args.size or os.getenv("DATA_SIZE", "small")

if not industry:
    print("\n" + "="*60)
    print("AI-Powered Sample Data Generator")
    print("="*60)
    print("\nNo INDUSTRY found in .env or CLI args.\n")
    print("Examples:")
    print("  Industry: Telecommunications")
    print("  Use Case: Network operations with outage tracking")
    print()
    print("  Industry: Energy")
    print("  Use Case: Grid monitoring and outage response")
    print()
    industry = input("Industry: ").strip()
    if not industry:
        print("ERROR: Industry is required. Set INDUSTRY in .env or pass --industry")
        sys.exit(1)

if not usecase:
    usecase = input("Use Case: ").strip()
    if not usecase:
        print("ERROR: Use case is required. Set USECASE in .env or pass --usecase")
        sys.exit(1)
SIZE_CONFIG = {
    "small": {"primary": 16, "secondary": 40},
    "medium": {"primary": 50, "secondary": 200},
    "large": {"primary": 200, "secondary": 1000}
}
size_config = SIZE_CONFIG[size]

# Create output directory
base_data_dir = os.path.join(script_dir, "..", "data")
os.makedirs(base_data_dir, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
industry_slug = industry.lower().replace(" ", "_")[:20]
data_dir = os.path.join(base_data_dir, f"{timestamp}_{industry_slug}")
data_dir = os.path.abspath(data_dir)

print(f"\n{'='*60}")
print(f"Generating data for: {industry}")
print(f"Use case: {usecase}")
print(f"Size: {size}")
print(f"Output: {data_dir}")
print(f"{'='*60}")

# ============================================================================
# Initialize AI Client
# ============================================================================

print("\nInitializing AI client...")
credential = DefaultAzureCredential()

from azure.ai.projects import AIProjectClient
project_client = AIProjectClient(endpoint=FOUNDRY_ENDPOINT, credential=credential)
client = project_client.get_openai_client()
model = os.getenv("AZURE_CHAT_MODEL") or os.getenv("MODEL_DEPLOYMENT", "gpt-4o-mini")

print("[OK] AI client initialized")

# ============================================================================
# Prompt Template for Script Generation
# ============================================================================

SCRIPT_PROMPT = '''Generate a complete Python script that creates sample data for:

Industry: {industry}
Use Case: {usecase}
Primary table rows: {primary_rows}
Secondary table rows: {secondary_rows}
Output directory: {data_dir}

=== AVAILABLE LIBRARIES (use ONLY these) ===
- os, json, random, datetime (Python standard library)
- pandas (for DataFrames and CSV)
- fpdf (from fpdf2, for PDF generation)

DO NOT use any other libraries like faker, numpy, etc. - they are not installed!

=== CRITICAL: DATA AND QUESTIONS MUST ALIGN ===
The #1 goal is generating data that supports interesting, answerable questions.
FIRST design the questions you want to ask, THEN design the data schema to answer them.

STEP 1: Design Questions First
Think about what questions would be interesting for {industry}:
- SQL questions need specific columns to query (counts, averages, filters, joins)
- Document questions need specific policies with numeric thresholds
- Combined questions need data values that can be compared against policy thresholds

STEP 2: Design Data Schema to Support Questions
For each question, ensure the required columns exist:
- "Average appointment duration" needs a duration_minutes column
- "Appointments by type" needs an appointment_type column  
- "Patients over age threshold" needs date_of_birth with VARIED ages
- "Wait time exceeds policy" needs actual_wait_minutes in data AND max_wait in policy docs

STEP 3: Generate Realistic, Varied Data
- Dates should span realistic ranges (not all the same date!)
- Ages should vary (20-80 years old, not all born same day)
- Categories should have realistic distribution
- Numeric values should have variance for meaningful analytics

The script MUST create this EXACT folder structure:
{data_dir}/
    config/
        ontology_config.json
        sample_questions.txt
    tables/
        <table1>.csv
        <table2>.csv
        ...
    documents/
        <doc1>.pdf
        <doc2>.pdf
        ...

REQUIREMENTS:
1. Create folders: config/, tables/, documents/ under the output directory
2. Generate 2-3 related tables as CSV files in tables/ folder
3. Create ontology_config.json in config/ folder - USE json.dump() with a Python dict!
4. Create sample_questions.txt in config/ folder
5. Generate 3 PDF policy documents in documents/ folder (use fpdf2)
6. CSV files go in tables/ folder, NOT in the root

=== CRITICAL: JSON CONFIG FILE ===
The ontology_config.json MUST be valid JSON. Use this EXACT code pattern:

```python
config = {{
    "scenario": "logistics",  # lowercase, no spaces
    "name": "Fleet Management",
    "description": "Managing logistics fleet operations",
    "tables": {{
        "vehicles": {{
            "columns": ["vehicle_id", "vehicle_type", "capacity"],
            "types": {{"vehicle_id": "String", "vehicle_type": "String", "capacity": "BigInt"}},
            "key": "vehicle_id",
            "source_table": "vehicles"
        }},
        "drivers": {{
            "columns": ["driver_id", "name", "assigned_vehicle"],
            "types": {{"driver_id": "String", "name": "String", "assigned_vehicle": "String"}},
            "key": "driver_id", 
            "source_table": "drivers"
        }}
    }},
    "relationships": [
        {{"name": "driver_vehicle", "from": "drivers", "to": "vehicles", "fromKey": "assigned_vehicle", "toKey": "vehicle_id"}}
    ]
}}

with open(os.path.join(config_dir, "ontology_config.json"), "w") as f:
    json.dump(config, f, indent=4)
```

=== CRITICAL: DATAFRAME SAFETY RULES ===
DataFrame errors are the #1 cause of script failure. Follow these rules EXACTLY:

RULE 1: Define row count as a variable FIRST, then use it everywhere:
```python
NUM_VEHICLES = {primary_rows}  # Define count once
NUM_DRIVERS = {primary_rows}
NUM_ORDERS = {secondary_rows}
```

RULE 2: Use list comprehensions with range(), NOT list multiplication for varied data:
```python
# GOOD - guaranteed correct length:
vehicles = pd.DataFrame({{
    'vehicle_id': [f'VEH{{str(i).zfill(3)}}' for i in range(1, NUM_VEHICLES + 1)],
    'vehicle_type': [['Van', 'Truck', 'SUV'][i % 3] for i in range(NUM_VEHICLES)],
    'capacity': [100 + (i * 50) for i in range(NUM_VEHICLES)]
}})

# BAD - easy to miscount:
vehicles = pd.DataFrame({{
    'vehicle_id': [f'VEH{{i}}' for i in range(1, 17)],  # 16 items
    'vehicle_type': ['Van'] * 6 + ['Truck'] * 6 + ['SUV'] * 5,  # 17 items - WRONG!
}})
```

RULE 3: For categorical distribution, use modulo or random.choices:
```python
import random
vehicle_types = random.choices(['Van', 'Truck', 'SUV'], weights=[3, 2, 1], k=NUM_VEHICLES)
```

=== DATA QUALITY REQUIREMENTS ===
Generate realistic, VARIED data - this is critical for meaningful analytics!

DATES - Must have realistic variety:
```python
import random
from datetime import datetime, timedelta

# GOOD - varied dates over a year
base_date = datetime(2024, 1, 1)
dates = [(base_date + timedelta(days=random.randint(0, 365))).strftime('%Y-%m-%d') for _ in range(NUM_ROWS)]

# GOOD - varied birth dates (ages 20-80)
birth_years = [random.randint(1945, 2005) for _ in range(NUM_PATIENTS)]
dobs = [f"{{y}}-{{random.randint(1,12):02d}}-{{random.randint(1,28):02d}}" for y in birth_years]

# BAD - all same date
dates = ['2023-10-01'] * NUM_ROWS  # Useless for analysis!
```

NUMERIC VALUES - Must have variance:
```python
# GOOD - realistic distribution
wait_times = [random.randint(5, 60) for _ in range(NUM_APPOINTMENTS)]  # 5-60 min range
durations = [random.choice([15, 30, 45, 60]) for _ in range(NUM_APPOINTMENTS)]

# BAD - no variance
wait_times = [30] * NUM_APPOINTMENTS  # Can't analyze patterns!
```

CATEGORIES - Use realistic distributions:
```python
# GOOD - weighted realistic mix
appt_types = random.choices(['Checkup', 'Urgent', 'Specialist', 'Lab'], 
                           weights=[40, 20, 25, 15], k=NUM_APPOINTMENTS)
statuses = random.choices(['Completed', 'Cancelled', 'NoShow'], 
                         weights=[80, 15, 5], k=NUM_APPOINTMENTS)
```

NAMES - Use realistic variety:
```python
first_names = ['James', 'Mary', 'John', 'Patricia', 'Robert', 'Jennifer', 'Michael', 'Linda', 
               'William', 'Elizabeth', 'David', 'Barbara', 'Richard', 'Susan', 'Joseph', 'Jessica']
last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis']
names = [f"{{random.choice(first_names)}} {{random.choice(last_names)}}" for _ in range(NUM_ROWS)]
```

KEY COLUMNS TO INCLUDE (adapt to industry):
- Date columns with realistic ranges
- Numeric columns for aggregation (duration, amount, count, rating)
- Category columns for filtering/grouping (type, status, department)
- Threshold-comparable values (so combined questions can compare data vs policy)

PDF DOCUMENT REQUIREMENTS - CRITICAL:
Each PDF must contain REAL, DETAILED business content - NO placeholders, NO "..." truncation!
Generate 3 different policy/guideline documents relevant to {industry}.
IMPORTANT: Use only ASCII characters in PDF text - no curly quotes, em-dashes, or special characters!
Replace smart quotes with straight quotes, and em-dashes with regular dashes.

USE THIS EXACT PATTERN for creating PDFs:
```python
def create_pdf(title, sections, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    for heading, content in sections:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        # Ensure ASCII-only text
        content = content.encode('ascii', 'replace').decode('ascii')
        pdf.multi_cell(0, 6, content)
        pdf.ln(5)
    pdf.output(os.path.join(documents_dir, filename))

# Example - EACH content string must be 50+ words like this:
sections = [
    ("1. Scheduling Requirements", 
     "All delivery requests must be submitted at least 48 hours before the requested delivery date. "
     "Rush orders may be accommodated with a 25% surcharge, subject to vehicle availability. "
     "Deliveries scheduled for weekends or holidays require 72 hours advance notice and incur an "
     "additional 15% weekend/holiday fee. Cancellations made less than 24 hours before scheduled "
     "pickup will be charged a 50% cancellation fee."),
    ("2. Vehicle Assignment Policy",
     "Vehicles are assigned based on cargo weight, volume, and delivery distance. Standard vans handle "
     "loads up to 500kg within a 50km radius. Medium trucks are deployed for loads between 500kg and "
     "2000kg or distances exceeding 50km. Heavy-duty trucks are reserved for loads over 2000kg or "
     "specialized cargo requiring climate control or hazardous materials handling certification."),
    # ... 6-8 sections total, each with 50+ words
]
create_pdf("Delivery Operations Manual", sections, "delivery_operations.pdf")
```

MANDATORY REQUIREMENTS:
- 3 PDF documents with different topics
- Each document: 6-8 sections minimum
- Each section content: 50-80 words (4-6 complete sentences)
- Include specific numbers: percentages, hours, distances, fees, limits
- NO ellipsis (...), NO truncation, NO placeholder text
- Write out complete sentences with real policy details
- IMPORTANT: Use only ASCII characters - NO curly quotes, NO special apostrophes
- Use straight quotes (") and straight apostrophes (') only
- Avoid Unicode characters like smart quotes or em-dashes

QUESTIONS:
Create sample_questions.txt with THREE distinct sections:

```
=== SQL QUESTIONS (Fabric Data) ===
Questions answerable ONLY from database tables. Examples:
- How many orders were placed last month?
- What is the average delivery time by driver?
- Which vehicle has the most deliveries?

=== DOCUMENT QUESTIONS (AI Search) ===
Questions answerable ONLY from policy documents. Examples:
- What is our cancellation policy?
- What safety equipment is required for drivers?
- What are the vehicle maintenance intervals?

=== COMBINED INSIGHT QUESTIONS ===
These questions MUST require BOTH a SQL query AND a document search to answer.
The agent cannot answer with just one tool - it MUST call both.

PATTERN: "Compare actual data against a policy/threshold/rule from documents"

=== COMBINED INSIGHT QUESTIONS ===
These questions MUST require BOTH a SQL query AND a document search to answer.
The agent cannot answer with just one tool - it MUST call both.

PATTERN: "Compare actual data against a policy/threshold/rule from documents"

The pattern is: [Get numeric/date data from SQL] + [Compare against threshold from policy docs]
Examples of this pattern:
- "Which [entities] exceeded the maximum [metric] defined in our [policy]?"
  (SQL: get actual metric values | Docs: get max threshold from policy)
- "Which [entities] are overdue for [action] based on our [schedule/policy]?"
  (SQL: get last action date | Docs: get required frequency from policy)
- "What percentage of [transactions] met our [SLA/standard]?"
  (SQL: get actual performance data | Docs: get SLA threshold)

BAD examples (can be answered with ONE tool - DO NOT USE):
- "Which items are overdue?" (just SQL - no policy threshold needed)
- "What is our cancellation policy?" (just documents - no data comparison)
- "How does X affect Y?" (just SQL analysis - no policy reference)
```

Include 5 questions per section (15 total).
The COMBINED questions MUST follow the pattern: get data from SQL, compare against rule/threshold/policy from documents.

=== CRITICAL: QUESTION-DATA ALIGNMENT ===
Every question MUST be answerable with the actual data you generate!

STEP 1: Design your data schema with specific columns and category values
STEP 2: Write policy documents with specific numeric thresholds (e.g., "maximum 30 minutes", "required every 12 months")  
STEP 3: Write questions that ONLY reference columns/values that actually exist

VALIDATION RULES:
- If a question asks about a category (e.g., "Screening appointments"), that category MUST exist in your data
- If a question compares against a threshold, that threshold MUST appear in your policy documents
- Every SQL question must reference columns that exist in your tables
- Every combined question must reference BOTH a data column AND a policy threshold

DO NOT write questions about data that doesn't exist. If you don't generate "Screening" as an appointment type, 
don't ask about screening appointments. Instead, ask about types you DID generate.

OUTPUT FORMAT:
Return ONLY the Python code, no markdown formatting, no explanations.
The script should start with imports and end with a print statement confirming completion.
'''

# ============================================================================
# Generate the Script
# ============================================================================

print("\n[Step 1/2] Generating custom data script...")
print("(This may take 30-60 seconds)")

prompt = SCRIPT_PROMPT.format(
    industry=industry,
    usecase=usecase,
    primary_rows=size_config['primary'],
    secondary_rows=size_config['secondary'],
    data_dir=data_dir.replace("\\", "/")  # Use forward slashes for cross-platform
)

SYSTEM_INSTRUCTIONS = """You are an expert Python developer generating data scripts for a workshop.
Your code MUST work on the first try - workshop attendees cannot debug your code.

CRITICAL RULES:
1. DataFrame columns MUST have equal length arrays - this is the #1 cause of failure
2. Use range() with a constant, NOT list multiplication for varied data
3. Use only ASCII characters in strings (no smart quotes, em-dashes)
4. Test your logic mentally before writing - count array elements carefully

Generate clean, working Python code only. No markdown, no explanations."""

MAX_RETRIES = 3
generated_script = None
last_error = None

for attempt in range(1, MAX_RETRIES + 1):
    if attempt > 1:
        print(f"  Retry {attempt}/{MAX_RETRIES}...")
        # Add error context to help AI fix the issue
        retry_prompt = f"{prompt}\n\n=== PREVIOUS ATTEMPT FAILED ===\nError: {last_error}\nPlease fix this issue in your new code."
    else:
        retry_prompt = prompt
    
    # Use the responses API (available through project client)
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=retry_prompt
    )
    
    # Extract text from response
    generated_script = ""
    for item in response.output:
        if hasattr(item, 'type') and item.type == 'message':
            for content in item.content:
                if hasattr(content, 'text'):
                    generated_script += content.text
    
    # Clean up the script (remove markdown if present)
    if generated_script.startswith("```"):
        lines = generated_script.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        generated_script = "\n".join(lines)
    
    # Save the generated script for reference
    script_path = os.path.join(data_dir, "_generated_script.py")
    os.makedirs(data_dir, exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(generated_script)
    
    if attempt == 1:
        print(f"[OK] Script generated ({len(generated_script)} chars)")
        print(f"  Saved to: {script_path}")
    
    # Try to execute
    print(f"\n[Step 2/2] Executing generated script..." if attempt == 1 else "  Executing...")
    
    try:
        exec_globals = {"__name__": "__main__"}
        exec(generated_script, exec_globals)
        print("[OK] Script executed successfully")
        last_error = None
        break  # Success!
    except Exception as e:
        last_error = str(e)
        if attempt < MAX_RETRIES:
            print(f"[WARN] Attempt {attempt} failed: {e}")
        else:
            print(f"[FAIL] Script execution error after {MAX_RETRIES} attempts: {e}")

if last_error:
    print("\nThe generated script has been saved. You can review and fix it:")
    print(f"  {script_path}")
    print("\nTrying to create basic structure anyway...")
    
    # Create basic folder structure at minimum
    os.makedirs(os.path.join(data_dir, "config"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "tables"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "documents"), exist_ok=True)
    
    # Save error info
    with open(os.path.join(data_dir, "_error.txt"), "w") as f:
        f.write(f"Error executing generated script:\n{last_error}\n")
    sys.exit(1)

# ============================================================================
# Verify Output
# ============================================================================

print("\n" + "="*60)
print("Verifying generated files...")

config_dir = os.path.join(data_dir, "config")
tables_dir = os.path.join(data_dir, "tables")
docs_dir = os.path.join(data_dir, "documents")

# Check what was created
csv_files = [f for f in os.listdir(tables_dir) if f.endswith('.csv')] if os.path.exists(tables_dir) else []
pdf_files = [f for f in os.listdir(docs_dir) if f.endswith('.pdf')] if os.path.exists(docs_dir) else []
config_files = os.listdir(config_dir) if os.path.exists(config_dir) else []

# Validate ontology_config.json is valid JSON
ontology_path = os.path.join(config_dir, "ontology_config.json")
if os.path.exists(ontology_path):
    try:
        import json
        with open(ontology_path, 'r') as f:
            config = json.load(f)
        # Validate required keys
        required_keys = ["scenario", "name", "tables"]
        missing = [k for k in required_keys if k not in config]
        if missing:
            print(f"[WARN] ontology_config.json missing keys: {missing}")
        else:
            print("[OK] ontology_config.json is valid")
    except json.JSONDecodeError as e:
        print(f"[FAIL] ontology_config.json is invalid JSON: {e}")
        print("       This will cause downstream scripts to fail!")
        sys.exit(1)
else:
    print("[WARN] ontology_config.json not found")

print(f"""
{'='*60}
Data Generation Complete!
{'='*60}

Industry: {industry}
Use Case: {usecase}

Data folder: {data_dir}

Contents:
  config/   - {len(config_files)} files
  tables/   - {len(csv_files)} CSV files
  documents/- {len(pdf_files)} PDF files

Tables:""")

for csv in csv_files:
    csv_path = os.path.join(tables_dir, csv)
    with open(csv_path, 'r') as f:
        row_count = sum(1 for _ in f) - 1  # minus header
    print(f"  - {csv} ({row_count} rows)")

print(f"""
Next steps:
  1. Update .env: DATA_FOLDER={data_dir}
  2. Run the pipeline:
     python scripts/02_create_fabric_items.py
     python scripts/03_load_fabric_data.py
     python scripts/04_generate_agent_prompt.py
     python scripts/06_upload_to_search.py
     python scripts/07_create_foundry_agent.py
     python scripts/08_test_agent.py
""")

# ============================================================================
# Update .env with data folder path
# ============================================================================

env_path = os.path.join(script_dir, "..", ".env")
project_root = os.path.abspath(os.path.join(script_dir, ".."))

# Use relative path for .env (relative to project root)
relative_data_dir = os.path.relpath(data_dir, project_root)

if os.path.exists(env_path):
    with open(env_path, "r") as f:
        env_content = f.read()
    
    lines = env_content.split("\n")
    
    # Update or add each setting
    settings_to_update = {
        "DATA_FOLDER": relative_data_dir,
        "INDUSTRY": industry,
        "USECASE": usecase,
    }
    
    for key, value in settings_to_update.items():
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}")
    
    with open(env_path, "w") as f:
        f.write("\n".join(lines))
    
    print(f"[OK] Updated .env with DATA_FOLDER={relative_data_dir}")
    print(f"[OK] Updated .env with INDUSTRY={industry}")
    print(f"[OK] Updated .env with USECASE={usecase}")

# ============================================================================
# Clear Cosmos DB Conversation History
# ============================================================================

COSMOSDB_ACCOUNT = os.getenv("AZURE_COSMOSDB_ACCOUNT")
COSMOSDB_DATABASE = os.getenv("AZURE_COSMOSDB_DATABASE", "db_conversation_history")
COSMOSDB_CONTAINER = os.getenv("AZURE_COSMOSDB_CONVERSATIONS_CONTAINER", "conversations")
AZURE_RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP") or os.getenv("RESOURCE_GROUP_NAME")
AZURE_SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")

if COSMOSDB_ACCOUNT:
    print(f"\nClearing conversation history in Cosmos DB...")

    # ---- Delete all conversation history items ----
    try:
        from azure.cosmos import CosmosClient, exceptions as cosmos_exceptions

        cosmos_endpoint = f"https://{COSMOSDB_ACCOUNT}.documents.azure.com:443/"
        cosmos_client = CosmosClient(cosmos_endpoint, credential=credential)
        database = cosmos_client.get_database_client(COSMOSDB_DATABASE)
        container = database.get_container_client(COSMOSDB_CONTAINER)

        # Detect partition key configuration (single vs hierarchical)
        container_props = container.read()
        pk_paths = container_props["partitionKey"]["paths"]
        pk_kind = container_props["partitionKey"].get("kind", "Hash")
        pk_fields = [p.lstrip("/") for p in pk_paths]

        items = list(container.query_items(
            query="SELECT * FROM c",
            enable_cross_partition_query=True
        ))

        if items:
            deleted_count = 0
            for item in items:
                try:
                    # Always use list format for partition key (works for both null and non-null values)
                    pk_value = [item.get(f) for f in pk_fields]
                    container.delete_item(
                        item=item["id"],
                        partition_key=pk_value
                    )
                    deleted_count += 1
                except cosmos_exceptions.CosmosHttpResponseError as e:
                    print(f"  [WARN] Failed to delete item {item['id']}: {e.message}")
            print(f"[OK] Cleared {deleted_count}/{len(items)} conversation history items from Cosmos DB")
        else:
            print("[OK] No conversation history to clear")

    except ImportError:
        print("[WARN] azure-cosmos not installed. Run: pip install azure-cosmos")
        print("       Skipping conversation history cleanup.")
    except Exception as e:
        print(f"[WARN] Could not clear conversation history: {e}")
        print("       This is non-critical - continuing...")
else:
    print("\n[INFO] AZURE_COSMOSDB_ACCOUNT not set - skipping conversation history cleanup")

