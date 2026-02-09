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
    "small": {"primary": 16, "secondary": 40, "tables": "2-3", "relationships": "1-2", "documents": 3},
    "medium": {"primary": 50, "secondary": 200, "tables": "4-5", "relationships": "3-4", "documents": 5},
    "large": {"primary": 200, "secondary": 1000, "tables": "6-8", "relationships": "5-7", "documents": 8}
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
Number of tables: {table_count}
Number of relationships: {relationship_count}
Output directory: {data_dir}

=== AVAILABLE LIBRARIES (use ONLY these) ===
- os, json, random, datetime (Python standard library)
- pandas (for DataFrames and CSV)
- fpdf (from fpdf2, for PDF generation)

DO NOT use any other libraries like faker, numpy, etc. - they are not installed!

=== CRITICAL: DATA AND QUESTIONS MUST ALIGN ===
The #1 goal is generating data that supports interesting, answerable questions.
FIRST design the questions you want to ask, THEN design the data schema to answer them.
(See "QUESTION-DATA ALIGNMENT" section below for detailed rules)

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
2. Generate EXACTLY {table_count} related tables as CSV files in tables/ folder (no more, no less)
3. Create ontology_config.json in config/ folder - USE json.dump() with a Python dict!
4. Create sample_questions.txt in config/ folder
5. Generate EXACTLY {doc_count} PDF policy documents in documents/ folder
6. CSV files go in tables/ folder, NOT in the root
7. Create {relationship_count} relationships between tables (foreign key connections)

=== TABLE REQUIREMENTS ===
Create EXACTLY {table_count} tables - no more, no less. This is a hard requirement.
Think about what tables would naturally exist for {industry} - {usecase}. Examples:
- quality_inspections (inspection_id, part_id, inspector_id, result, inspection_date)
- defects (defect_id, part_id, defect_type, severity, reported_date)
- production_runs (run_id, part_id, quantity, run_date, machine_id)
- machines (machine_id, machine_name, status, last_maintenance_date)
- employees (employee_id, name, department, hire_date)
- shipments (shipment_id, order_id, ship_date, carrier, tracking_number)
Choose the {table_count} most important tables that enable the best queries and relationships.

=== CRITICAL: JSON CONFIG FILE ===
The ontology_config.json MUST be valid JSON. Use this EXACT code pattern:

IMPORTANT: EVERY table you create MUST be included in ontology_config.json!
If you save a CSV file, it MUST have a matching entry in the config.
Tables not in the config CANNOT be queried by the agent!

```python
config = {{
    "scenario": "logistics",  # lowercase, no spaces
    "name": "Fleet Management",
    "description": "Managing logistics fleet operations",
    "tables": {{
        # EVERY table you created must be listed here!
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
        # If you created more tables, add them here too!
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

RULE 4: ALWAYS save DataFrames to CSV files in the tables/ folder:
```python
# CRITICAL - You MUST save each DataFrame to CSV!
vehicles.to_csv(os.path.join(tables_dir, 'vehicles.csv'), index=False)
drivers.to_csv(os.path.join(tables_dir, 'drivers.csv'), index=False)
orders.to_csv(os.path.join(tables_dir, 'orders.csv'), index=False)
```

RULE 5: FOREIGN KEYS MUST REFERENCE EXISTING IDs - This is critical for data integrity!
```python
# GOOD - foreign keys reference actual IDs from parent table

RULE 6: ONTOLOGY TYPES MUST MATCH DATA - Use the correct type for each column:
```python
# Type mapping - use these EXACTLY:
# String  - for text, IDs, names, categories (e.g., "PART001", "Active", "John Smith")
# BigInt  - for whole numbers (e.g., quantity, count, age)
# Double  - for decimal numbers (e.g., price, rate, percentage as 0.15)
# Date    - for dates in YYYY-MM-DD format (e.g., "2024-01-15")
# DateTime - for timestamps (e.g., "2024-01-15T10:30:00")
# Boolean - for true/false values

# MATCH your DataFrame column types to ontology types:
production_runs = pd.DataFrame({{
    'run_id': [...],           # String - IDs are always String
    'quantity': [...],         # BigInt - whole numbers
    'unit_cost': [...],        # Double - decimals
    'run_date': [...],         # Date - YYYY-MM-DD format
    'is_complete': [...]       # Boolean - True/False
}})

# In ontology_config.json, declare matching types:
"types": {{
    "run_id": "String",
    "quantity": "BigInt",      # matches int values in DataFrame
    "unit_cost": "Double",     # matches float values in DataFrame  
    "run_date": "Date",        # matches YYYY-MM-DD strings
    "is_complete": "Boolean"   # matches True/False values
}}
```
NUM_PARTS = 16
part_ids = [f'PART{{str(i).zfill(3)}}' for i in range(1, NUM_PARTS + 1)]  # PART001 to PART016

parts = pd.DataFrame({{
    'part_id': part_ids,
    'part_name': [f'Part {{i}}' for i in range(1, NUM_PARTS + 1)]
}})

# Child table references ONLY existing part_ids using random.choice()
NUM_INSPECTIONS = 40
inspections = pd.DataFrame({{
    'inspection_id': [f'INS{{str(i).zfill(3)}}' for i in range(1, NUM_INSPECTIONS + 1)],
    'part_id': [random.choice(part_ids) for _ in range(NUM_INSPECTIONS)],  # References existing parts!
    'result': random.choices(['Pass', 'Fail'], weights=[80, 20], k=NUM_INSPECTIONS)
}})

# BAD - generates IDs that may not exist in parent table
inspections = pd.DataFrame({{
    'part_id': [f'PART{{random.randint(1, 50)}}' for _ in range(NUM_INSPECTIONS)]  # WRONG! May create PART25 when only PART1-16 exist
}})
```

=== DATA QUALITY REQUIREMENTS ===
Generate realistic, VARIED data - this is critical for meaningful analytics!

=== DATA INTEGRITY CHECKLIST (Review before finishing!) ===
Before completing your script, mentally verify:
1. FOREIGN KEYS: Every foreign key value exists in the parent table (use random.choice(parent_ids), not random.randint)
2. ID FORMAT: Use consistent ID format everywhere (if parts use PART001, inspections must reference PART001 not PART1)
3. PRIMARY KEYS: Every table has unique IDs with no duplicates
4. NO NULLS in ID columns: All ID and foreign key columns must have values
5. DATE RANGE: Dates should span several months (not all same date) for trend analysis
6. NUMERIC VARIANCE: Numeric columns should have realistic spread (not all same value)
7. CATEGORIES: Use 3-6 distinct values for category columns (good for charts)
8. SAVE ALL TABLES: Every DataFrame must be saved with .to_csv()

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

=== CHART-FRIENDLY DATA ===
Include data that supports visualizations:
- DATE columns spanning multiple months (for line charts showing trends over time)
- CATEGORY columns with 3-6 distinct values (for bar charts and pie charts)
- NUMERIC columns with variance (for meaningful aggregations like sum, avg, count)
- At least one table should have: date + category + numeric value (e.g., order_date, order_status, order_amount)

Example chart-ready table structure:
```python
orders = pd.DataFrame({{
    'order_id': [...],
    'order_date': [...],      # Spread over 6-12 months for trends
    'status': [...],          # 3-5 values: Completed, Pending, Cancelled, etc.
    'category': [...],        # Product types or regions for grouping
    'amount': [...],          # Numeric for sum/avg calculations
    'quantity': [...]         # Another numeric for comparisons
}})
```

PDF DOCUMENT REQUIREMENTS - CRITICAL:
Each PDF must contain REAL, DETAILED business content - NO placeholders, NO "..." truncation!
Generate {doc_count} different policy/guideline documents relevant to {industry}.
IMPORTANT: Use only ASCII characters in PDF text - no curly quotes, em-dashes, or special characters!
Replace smart quotes with straight quotes, and em-dashes with regular dashes.

DOCUMENT NAMING: Use descriptive, meaningful filenames - NOT generic names like "policy_1.pdf"!
Good examples: quality_control_manual.pdf, supplier_requirements.pdf, safety_guidelines.pdf, maintenance_procedures.pdf
Bad examples: policy_document_1.pdf, doc1.pdf, policy_1.pdf

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
- At least {doc_count} PDF documents with different topics (more if the scenario needs them)
- Each document: 6-8 sections minimum
- Each section content: 50-80 words (4-6 complete sentences)
- Include specific numbers: percentages, hours, distances, fees, limits
- NO ellipsis (...), NO truncation, NO placeholder text
- Write out complete sentences with real policy details
- IMPORTANT: Use only ASCII characters - NO curly quotes, NO special apostrophes
- Use straight quotes (") and straight apostrophes (') only
- Avoid Unicode characters like smart quotes or em-dashes

QUESTIONS - CRITICAL: MUST MATCH YOUR ACTUAL DATA!
Create sample_questions.txt with THREE distinct sections.

WARNING: DO NOT copy examples! Write questions specific to YOUR generated tables and documents for {industry}.
Every question MUST reference columns/tables/thresholds that ACTUALLY EXIST in your generated data.

=== SQL QUESTIONS (Fabric Data) ===
Questions answerable ONLY from YOUR database tables.

BEFORE writing SQL questions, review YOUR tables:
- What tables did you create?
- What columns does each table have?
- What numeric columns can be aggregated?
- What category columns can be grouped?

Write 5 questions that use YOUR actual columns. Include a mix of:
- Counts: "How many [records] have [column] = 'value'?" (use actual column and value from your data)
- Aggregations: "What is the average [numeric_column]?" (use actual numeric column)
- Groupings: "Show [records] grouped by [category]" (use actual category column)
- Top N: "Which [entity] has the highest [numeric_column]?" (use actual column)
- Trends: "What is the monthly breakdown of [metric]?" (only if you have date columns)

VALIDATION: For each SQL question, verify the column EXISTS in your table & there is relevant data.
If you ask "What is the average score?" → your table MUST have a 'score' column
If you ask "Show tickets by priority" → your table MUST have a 'priority' column

=== DOCUMENT QUESTIONS (AI Search) ===
Questions answerable ONLY from YOUR policy documents.

BEFORE writing document questions, review YOUR PDFs:
- What topics do your documents cover?
- What specific rules, procedures, or thresholds did you include?

Write 5 questions about content that ACTUALLY EXISTS in your documents.

VALIDATION: For each document question, verify the answer EXISTS in your PDFs.
If you ask "What is our return policy?" → one of your PDFs MUST contain return policy content
If you ask "How often should X be reviewed?" → one of your PDFs MUST state a review frequency

=== COMBINED INSIGHT QUESTIONS (MOST IMPORTANT!) ===
These questions require BOTH SQL data AND document content to answer.
The agent will: 1) Query SQL for current data, 2) Search docs for threshold/rule, 3) Compare them.

=== STEP-BY-STEP PROCESS FOR COMBINED QUESTIONS ===

STEP 1: Design 3-5 data-threshold pairs FIRST (before writing any code).
Each pair needs:
- A NUMERIC COLUMN in a table that can be compared
- A SPECIFIC THRESHOLD in a policy document
- Some data that VIOLATES the threshold (for interesting answers)

Generic pair patterns (adapt to your industry):
- [entity].score/rating column + "Minimum [score/rating]: [X] points/stars"
- [entity].rate/percentage column + "Maximum [rate]: [X]%"
- [entity].last_[action]_date column + "[Action] required every [X] days"
- [entity].count/quantity column + "Maximum [items] per [period]: [X]"
- [entity].duration/time column + "Maximum [time]: [X] hours/minutes"

STEP 2: Create the numeric columns with INTENTIONAL VIOLATIONS:
```python
# PATTERN: Create column with 70-80% passing, 20-30% failing threshold
values = []
for i in range(NUM_RECORDS):
    if i < int(NUM_RECORDS * 0.75):
        values.append(GOOD_VALUE)  # Within threshold
    else:
        values.append(BAD_VALUE)   # EXCEEDS threshold - creates interesting findings!
table['column_name'] = values

# Example: scores where some are below minimum
scores = []
for i in range(NUM_RECORDS):
    if i < int(NUM_RECORDS * 0.75):
        scores.append(random.randint(85, 100))  # Above 80 minimum
    else:
        scores.append(random.randint(50, 79))   # BELOW 80 minimum!
records['score'] = scores

# Example: dates where some are overdue  
from datetime import datetime, timedelta
today = datetime.now()
dates = []
for i in range(NUM_RECORDS):
    if i < int(NUM_RECORDS * 0.7):
        days_ago = random.randint(10, 25)   # Within 30-day requirement
    else:
        days_ago = random.randint(35, 90)   # OVERDUE! Past 30 days
    dates.append((today - timedelta(days=days_ago)).strftime('%Y-%m-%d'))
records['last_review_date'] = dates

# Example: rates where some exceed maximum
rates = []
for i in range(NUM_RECORDS):
    if i < int(NUM_RECORDS * 0.8):
        rates.append(round(random.uniform(1.0, 4.5), 1))  # Below 5% max
    else:
        rates.append(round(random.uniform(5.5, 12.0), 1)) # ABOVE 5% max!
records['error_rate'] = rates
```

STEP 3: Include EXACT thresholds in policy documents:
```python
# The threshold number MUST appear clearly in the document text
create_pdf("Standards and Guidelines", [
    ("1. Performance Standards",
     "All records must meet minimum performance requirements. The minimum acceptable "
     "score is 80 points out of 100. Records scoring below this threshold require "
     "immediate review and corrective action. Scores are evaluated monthly."),
    ("2. Review Requirements", 
     "Regular reviews must be conducted according to schedule. Reviews are required "
     "every 30 days. Items not reviewed within this timeframe are considered overdue "
     "and must be prioritized for immediate attention."),
    ("3. Error Rate Limits",
     "Error rates must remain below acceptable thresholds. The maximum error rate "
     "is 5 percent. Any entity exceeding this limit must be investigated and "
     "corrective measures implemented within one week."),
], "standards_policy.pdf")
```

STEP 4: Write combined questions in NATURAL, VARIED language:
Questions should sound like real questions someone would ask, not scripted templates.

IMPORTANT: Do NOT include the actual threshold numbers in the questions!
The agent should DISCOVER the threshold by searching the document - that's the demo value.

VARY the question style - don't use the same "[X], and does it [Y]?" pattern for every question!

GOOD - Natural and varied:
- "Are we meeting our response time targets according to the Service Policy?"
- "Do any tickets violate our SLA requirements?"
- "Is our current defect rate acceptable per company standards?"
- "Which items need attention based on the Maintenance Guidelines?"
- "Are there any compliance issues with our Quality Policy?"

BAD - Robotic and repetitive (same pattern every time):
- "What is X, and does it meet the requirements in Policy A?"
- "What is Y, and does it comply with Policy B?"
- "What is Z, and does it align with Policy C?"

BAD (threshold leaked into question):
- "What is our pass rate, and does it meet the 80% threshold?" ← Don't include "80%"!
- "Is our response time below the 72-hour maximum?" ← Don't include "72-hour"!

BAD (asks about data that doesn't exist):
- "Is there documentation for X?" ← Can't query SQL for "documentation"!
- "Are employees completing training?" ← Only if you have an employees table with training data!
- "Are there compliance issues?" ← Only if you have a column that tracks compliance!

EVERY combined question must reference a SPECIFIC COLUMN you created:
- If you ask about "maintenance overdue" → you need a maintenance table with dates
- If you ask about "inspection failures" → you need an inspections table with a result column
- If you ask about "employee training" → you need an employees table with a training_date column

The question should clearly indicate BOTH sources without revealing the answer:
- SQL part: reference actual columns like "inspection pass rate", "average resolution time", "maintenance next_due dates"
- Document part: "according to our [Policy Name]", "based on the [Guidelines]"

=== WHY THIS MATTERS ===
If you ask about a metric vs policy threshold but:
- Your table doesn't have that column → BROKEN (can't calculate)
- Your policy doesn't state a specific number → BROKEN (no threshold to compare)
- All data meets the threshold → BORING ("everything is fine" is a useless demo)

The demo is impressive when the agent says: "I found 4 items exceeding the 5% limit defined in your Policy document."
The demo is useless when the agent says: "All items are within acceptable limits."

DO NOT generate data where everything passes! Include 20-30% violations for interesting answers.

Include 5 questions per section (15 total).

=== SAMPLE_QUESTIONS.TXT FORMAT (MUST FOLLOW EXACTLY) ===
The file MUST have exactly this structure with section headers:
```python
with open(os.path.join(config_dir, "sample_questions.txt"), "w") as f:
    f.write("=== SQL QUESTIONS (Fabric Data) ===\\n")
    f.write("1. [Your first SQL question here]\\n")
    f.write("2. [Your second SQL question here]\\n")
    f.write("3. [Your third SQL question here]\\n")
    f.write("4. [Your fourth SQL question here]\\n")
    f.write("5. [Your fifth SQL question here]\\n")
    f.write("\\n")
    f.write("=== DOCUMENT QUESTIONS (AI Search) ===\\n")
    f.write("1. [Your first document question here]\\n")
    f.write("2. [Your second document question here]\\n")
    f.write("3. [Your third document question here]\\n")
    f.write("4. [Your fourth document question here]\\n")
    f.write("5. [Your fifth document question here]\\n")
    f.write("\\n")
    f.write("=== COMBINED INSIGHT QUESTIONS ===\\n")
    f.write("1. [Your first combined question here]\\n")
    f.write("2. [Your second combined question here]\\n")
    f.write("3. [Your third combined question here]\\n")
    f.write("4. [Your fourth combined question here]\\n")
    f.write("5. [Your fifth combined question here]\\n")
```

=== FINAL VERIFICATION CHECKLIST ===
Before finishing your script, verify:
1. EVERY CSV table is included in ontology_config.json (tables not in config cannot be queried!)
2. Every SQL question references columns that EXIST in tables listed in ontology_config.json
3. Every document question references content that EXISTS in your PDFs  
4. Every combined question has BOTH a matching data column AND a matching policy threshold
5. At least 20% of your data VIOLATES the thresholds (for interesting demo answers)
6. Policy thresholds are SPECIFIC NUMBERS (e.g., "5%", "80 points", "30 days") not vague text
7. Combined questions clearly name the policy document to search

=== CRITICAL: COMBINED QUESTION VALIDATION ===
For EACH combined question, verify this chain exists:
  QUESTION mentions "[metric] ... [Policy Name]"
     ↓
  TABLE has column that can calculate [metric]
     ↓  
  POLICY DOCUMENT actually contains a specific numeric threshold for [metric]
     ↓
  DATA has some rows that VIOLATE the threshold

If ANY link is missing, the question will FAIL. Do not write questions hoping thresholds exist.
Only write combined questions for data-threshold pairs you EXPLICITLY created.

WRONG approach:
1. Write question: "Does status distribution meet Operations Policy thresholds?"
2. Hope the Operations Policy has status thresholds (it probably doesn't!)
→ Result: Agent says "no thresholds found" - DEMO FAILS

RIGHT approach:
1. Create data column: operations['response_time'] with values 1-96 hours
2. Create policy text: "Maximum response time is 48 hours"
3. Make 25% of data exceed 48 hours
4. Write question: "What is our average response time, and does it meet the limit in our Response Policy?"
→ Result: Agent finds data AND threshold - DEMO WORKS

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
    table_count=size_config['tables'],
    relationship_count=size_config['relationships'],
    doc_count=size_config['documents'],
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

