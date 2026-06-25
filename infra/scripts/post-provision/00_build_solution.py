"""
Build Solution - Unified Pipeline
Master script that runs all steps to build the complete solution.

Usage:
    # Run all steps from the beginning (uses Fabric Lakehouse + AI Search)
    python infra/scripts/post-provision/00_build_solution.py
    
    # Start from a specific step
    python infra/scripts/post-provision/00_build_solution.py --from 05

    # Bring your own data (skips AI data generation)
    python infra/scripts/post-provision/00_build_solution.py --custom-data data/customdata

Steps (Fabric SQL mode):
    01  - Create Fabric Lakehouse & Load Data
    02  - Generate agent prompt
    03  - Upload documents to AI Search
    04  - Create Foundry Agent (Fabric SQL + Search)
    05  - App Deployment Config

Custom Data mode (--custom-data):
    Uses your own data from the specified folder.
    The folder must contain:
        tables/*.csv                 - One CSV per table
        documents/*.pdf              - PDF documents for AI Search
    The config/ folder (ontology_config.json) is auto-generated from your CSVs.

Both modes always use:
    - Fabric Data Agent for structured data
    - Native AzureAISearchTool for document search
"""

import argparse
import subprocess
import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

# ============================================================================
# Configuration
# ============================================================================

STEPS = {
    "01": {"script": "01_create_fabric_items.py", "name": "Create Fabric Lakehouse & Load Data", "time": "~1.5min", "fabric": True},
    "02": {"script": "02_generate_agent_prompt.py", "name": "Generate Agent Prompt", "time": "~5s"},
    "03": {"script": "03_upload_to_search.py", "name": "Upload to AI Search", "time": "~1min"},
    "04": {"script": "04_create_agent.py", "name": "Create Foundry Agent", "time": "~10s"},
    "05": {"script": "05_app_deployment.py", "name": "App Deployment Config", "time": "~15s"},
}

# Pipeline order
FABRIC_PIPELINE = ["01", "02", "03", "04", "05"]

# ============================================================================
# Parse Arguments
# ============================================================================

parser = argparse.ArgumentParser(
    description="End-to-end setup: data → knowledge bases → agents",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  python infra/scripts/post-provision/00_build_solution.py                # Full Fabric mode or SQL mode
  python infra/scripts/post-provision/00_build_solution.py --from 04      # Start from step 04
  python infra/scripts/post-provision/00_build_solution.py --only 05      # Run only specific steps
  python infra/scripts/post-provision/00_build_solution.py --custom-data data/customdata  # Use your own data
  python infra/scripts/post-provision/00_build_solution.py --scenario insurance  # Use pre-built scenario
  python infra/scripts/post-provision/00_build_solution.py --list-scenarios      # Show available scenarios
"""
)
parser.add_argument("--scenario", type=str,
                    help="Use a pre-built scenario (e.g., insurance, retail). "
                         "Use --list-scenarios to see available scenarios.")
parser.add_argument("--list-scenarios", action="store_true",
                    help="List available scenarios and exit")
parser.add_argument("--industry", type=str, 
                    help="Industry for data generation")
parser.add_argument("--usecase", type=str, 
                    help="Use case for data generation")
parser.add_argument("--size", choices=["small", "medium", "large"],
                    help="Data size for generation (default: from scenarios.json or 'small')")
parser.add_argument("--custom-data", type=str,
                    help="Path to folder with tables/ (CSVs) and documents/ (PDFs). "
                         "Config is auto-generated from your CSV files.")
parser.add_argument("--clean", action="store_true",
                    help="Clean and recreate artifacts")

parser.add_argument("--from", dest="from_step", type=str,
                    help="Start from this step (e.g., --from 04)")
parser.add_argument("--only", nargs="+", type=str,
                    help="Run only these steps (e.g., --only 05)")

parser.add_argument("--dry-run", action="store_true",
                    help="Show what would be run without executing")
parser.add_argument("--continue-on-error", action="store_true",
                    help="Continue running steps even if one fails")
parser.add_argument("-v", "--verbose", action="store_true",
                    help="Show full output from all scripts")

args = parser.parse_args()

# Quiet mode is default (verbose must be explicitly requested)
args.quiet = not args.verbose

# Load environment from azd + project .env
from load_env import load_all_env
load_all_env()

# ============================================================================
# Scenario Discovery & Handling
# ============================================================================

from scenarios import list_scenarios, get_scenario, get_scenario_abs_path
from load_env import save_to_azd_env

project_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
data_root = os.path.join(project_root, "data")


if args.list_scenarios:
    scenarios = list_scenarios()
    if not scenarios:
        print("No scenarios found.")
    else:
        print(f"\nAvailable Scenarios ({len(scenarios)}):")
        print("-" * 80)
        print(f"  {'Name':<15} {'Type':<10} {'Industry':<15} {'Use Case':<30}")
        print("-" * 80)
        for name, meta in scenarios.items():
            stype = meta.get('type', 'prebuilt')
            print(f"  {name:<15} {stype:<10} {meta['industry']:<15} {meta['usecase']:<30}")
        print("-" * 80)
        print(f"\n  Types: prebuilt = ready-to-use data")
        print(f"         byod   = bring your own CSVs (auto-generates config)")
        print(f"         custom = AI creates synthetic data for your industry/usecase")
        print(f"\nUsage: python {os.path.basename(__file__)} --scenario <name>")
    sys.exit(0)

# Validate mutual exclusivity
if args.scenario and args.custom_data:
    print("ERROR: --scenario and --custom-data cannot be used together.")
    sys.exit(1)

# Default to "default" scenario when neither --scenario nor --custom-data is specified
# BUT if --industry/--usecase is provided, treat as a custom run (no preset scenario)
if not args.scenario and not args.custom_data:
    if args.industry or args.usecase:
        # User wants to generate data for a custom industry — don't use any preset scenario
        pass
    else:
        args.scenario = "default"

# Handle --scenario
scenario_pack_dir = None
if args.scenario:
    scenario_meta = get_scenario(args.scenario)
    
    if scenario_meta is None:
        print(f"ERROR: Scenario '{args.scenario}' not found.")
        available = list_scenarios()
        if available:
            print(f"Available scenarios: {', '.join(available.keys())}")
        print("Use --list-scenarios to see available scenarios with details.")
        sys.exit(1)
    
    scenario_pack_dir = get_scenario_abs_path(args.scenario)
    
    # Set DATA_FOLDER and INDUSTRY/USECASE from scenario metadata
    relative_data_dir = os.path.relpath(scenario_pack_dir, project_root)
    os.environ["DATA_FOLDER"] = relative_data_dir
    save_to_azd_env("DATA_FOLDER", relative_data_dir)
    os.environ["INDUSTRY"] = args.industry or scenario_meta.get("industry", "")
    os.environ["USECASE"] = args.usecase or scenario_meta.get("usecase", "")
    
    # Set DATA_SIZE for custom-type scenarios
    if scenario_meta.get("data_size"):
        os.environ["DATA_SIZE"] = args.size or scenario_meta["data_size"]
    elif args.size:
        os.environ["DATA_SIZE"] = args.size

    # For custom-type scenarios, ensure the output folder exists
    if scenario_meta.get("type") == "custom":
        os.makedirs(scenario_pack_dir, exist_ok=True)

    # For byod-type scenarios, auto-generate config if missing
    if scenario_meta.get("type") == "byod":
        config_dir = os.path.join(scenario_pack_dir, "config")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "ontology_config.json")
        questions_path = os.path.join(config_dir, "sample_questions.txt")
        
        if not (os.path.exists(config_path) and os.path.exists(questions_path)):
            custom_industry = os.environ["INDUSTRY"]
            custom_usecase = os.environ["USECASE"]
            
            if not custom_industry or not custom_usecase:
                print("\n" + "="*60)
                print("BYOD Scenario - Industry & Use Case")
                print("="*60)
                print("\nDescribe your data so the agent understands the domain context.\n")
                if not custom_industry:
                    custom_industry = input("Industry (e.g. Healthcare, Retail, Manufacturing): ").strip()
                    if not custom_industry:
                        print("ERROR: Industry is required for BYOD scenarios.")
                        sys.exit(1)
                if not custom_usecase:
                    custom_usecase = input("Use Case (e.g. Patient records and clinical notes): ").strip()
                    if not custom_usecase:
                        print("ERROR: Use case is required for BYOD scenarios.")
                        sys.exit(1)
                os.environ["INDUSTRY"] = custom_industry
                os.environ["USECASE"] = custom_usecase
            
            print(f"\n[...] Generating config and sample questions from CSV files...")
            gen_script = os.path.join(script_dir, "generate_config_from_csv.py")
            gen_cmd = [
                sys.executable, gen_script,
                "--data-folder", scenario_pack_dir,
                "--industry", custom_industry,
                "--usecase", custom_usecase,
            ]
            gen_result = subprocess.run(gen_cmd, cwd=script_dir)
            if gen_result.returncode != 0:
                print("ERROR: Failed to generate config from CSV files.")
                sys.exit(1)
        else:
            print(f"[OK] Using existing config: {config_path}")

    # Check for documents
    docs_dir = os.path.join(scenario_pack_dir, "documents")
    has_documents = os.path.isdir(docs_dir) and any(
        f.endswith(".pdf") for f in os.listdir(docs_dir)
    )
    
    print(f"\n[OK] Scenario: {args.scenario}")
    print(f"     Type: {'custom' if (args.industry or args.usecase) else scenario_meta.get('type', 'prebuilt')}")
    print(f"     Industry: {os.environ.get('INDUSTRY', '')}")
    print(f"     Use Case: {os.environ.get('USECASE', '')}")
    print(f"     Documents: {'Yes' if has_documents else 'None (step 03 will be skipped)'}")
    print(f"     DATA_FOLDER set to: {relative_data_dir}")

# ============================================================================
# Handle --custom-data: validate folder, generate config, set DATA_FOLDER
# ============================================================================

custom_data_dir = None
if args.custom_data:
    custom_data_dir = os.path.abspath(args.custom_data)

    # Require tables/ and documents/ subfolders
    required_subdirs = ["tables", "documents"]
    missing = [d for d in required_subdirs if not os.path.isdir(os.path.join(custom_data_dir, d))]
    if missing:
        print(f"ERROR: Custom data folder is missing required subfolders: {', '.join(missing)}")
        print(f"       Expected structure in '{custom_data_dir}':")
        print(f"         tables/      - CSV files (one per table)")
        print(f"         documents/   - PDF files")
        print(f"\n       See data/customdata/README.md for details.")
        sys.exit(1)

    csv_files = [f for f in os.listdir(os.path.join(custom_data_dir, "tables")) if f.endswith(".csv")]
    pdf_files = [f for f in os.listdir(os.path.join(custom_data_dir, "documents")) if f.endswith(".pdf")]
    if not csv_files:
        print(f"ERROR: No CSV files found in {os.path.join(custom_data_dir, 'tables')}")
        sys.exit(1)
    if not pdf_files:
        print(f"WARNING: No PDF files found in {os.path.join(custom_data_dir, 'documents')}")

    # Ensure config/ folder exists
    config_dir = os.path.join(custom_data_dir, "config")
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "ontology_config.json")
    questions_path = os.path.join(config_dir, "sample_questions.txt")

    # If both config and questions already exist, read industry/usecase from config
    if os.path.exists(config_path) and os.path.exists(questions_path):
        import json
        with open(config_path, "r") as f:
            existing_config = json.load(f)
        custom_industry = args.industry or existing_config.get("scenario", "").capitalize()
        custom_usecase = args.usecase or existing_config.get("name", "")
        print(f"[OK] Using existing config: {config_path}")
    else:
        # Need industry/usecase for config generation — prefer CLI args, then prompt
        custom_industry = args.industry
        custom_usecase = args.usecase

        if not custom_industry or not custom_usecase:
            # If config exists, read from it to avoid re-prompting
            if os.path.exists(config_path):
                import json
                with open(config_path, "r") as f:
                    existing_config = json.load(f)
                custom_industry = custom_industry or existing_config.get("scenario", "").capitalize()
                custom_usecase = custom_usecase or existing_config.get("name", "")

        if not custom_industry or not custom_usecase:
            print("\n" + "="*60)
            print("Custom Data - Industry & Use Case")
            print("="*60)
            print("\nDescribe your data so the agent understands the domain context.\n")
            if not custom_industry:
                custom_industry = input("Industry (e.g. Healthcare, Retail, Manufacturing): ").strip()
                if not custom_industry:
                    print("ERROR: Industry is required for custom data.")
                    sys.exit(1)
            if not custom_usecase:
                custom_usecase = input("Use Case (e.g. Patient records and clinical notes): ").strip()
                if not custom_usecase:
                    print("ERROR: Use case is required for custom data.")
                    sys.exit(1)

        print(f"\n[...] Generating config and sample questions from CSV files...")
        gen_script = os.path.join(script_dir, "generate_config_from_csv.py")
        gen_cmd = [
            sys.executable, gen_script,
            "--data-folder", custom_data_dir,
            "--industry", custom_industry,
            "--usecase", custom_usecase,
        ]
        gen_result = subprocess.run(gen_cmd, cwd=script_dir)
        if gen_result.returncode != 0:
            print("ERROR: Failed to generate config from CSV files.")
            sys.exit(1)

    # Set DATA_FOLDER in environment
    relative_data_dir = os.path.relpath(custom_data_dir, project_root)
    os.environ["DATA_FOLDER"] = relative_data_dir
    save_to_azd_env("DATA_FOLDER", relative_data_dir)
    os.environ["INDUSTRY"] = custom_industry
    os.environ["USECASE"] = custom_usecase

    print(f"\n[OK] Custom data folder: {custom_data_dir}")
    print(f"     Industry: {custom_industry}")
    print(f"     Use Case: {custom_usecase}")
    print(f"     Tables: {', '.join(csv_files)}")
    print(f"     Documents: {', '.join(pdf_files) if pdf_files else '(none)'}")
    print(f"     DATA_FOLDER set to: {relative_data_dir}")

# ============================================================================
# Handle custom mode: --industry/--usecase without --scenario or --custom-data
# ============================================================================

if not args.scenario and not custom_data_dir:
    # Derive folder from industry name
    industry_slug = (args.industry or "generated").lower().replace(" ", "_")[:20]
    generate_data_dir = os.path.join(project_root, "data", "scenarios", industry_slug)
    os.makedirs(generate_data_dir, exist_ok=True)

    relative_data_dir = os.path.relpath(generate_data_dir, project_root)
    os.environ["DATA_FOLDER"] = relative_data_dir
    save_to_azd_env("DATA_FOLDER", relative_data_dir)
    os.environ["INDUSTRY"] = args.industry or ""
    os.environ["USECASE"] = args.usecase or ""
    os.environ["DATA_SIZE"] = args.size or "small"

    print(f"\n[OK] Custom mode (AI data generation)")
    print(f"     Type: custom")
    print(f"     Industry: {args.industry}")
    print(f"     Use Case: {args.usecase}")
    print(f"     DATA_FOLDER set to: {relative_data_dir}")

# ============================================================================
# Determine Pipeline
# ============================================================================

if args.only:
    pipeline = args.only
else:
    pipeline = FABRIC_PIPELINE.copy()

# Skip document upload step if no documents available
if scenario_pack_dir or custom_data_dir:
    active_data_dir = scenario_pack_dir or custom_data_dir
    docs_path = os.path.join(active_data_dir, "documents")
    has_pdfs = os.path.isdir(docs_path) and any(
        f.endswith(".pdf") for f in os.listdir(docs_path)
    )
    if not has_pdfs and "03" in pipeline:
        pipeline = [s for s in pipeline if s != "03"]
        print("  (Skipping step 03 — no PDF documents found in data folder. Cleaning up search resources...)")

        # Clean up existing search index, knowledge base, and knowledge source
        cleanup_script = os.path.join(script_dir, "03_upload_to_search.py")
        if os.path.exists(cleanup_script):
            result = subprocess.run(
                [sys.executable, cleanup_script, "--cleanup"],
                cwd=script_dir,
                capture_output=True, text=True
            )
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    print(f"  {line}")
            if result.returncode != 0 and result.stderr:
                print(f"  [WARN] Search cleanup: {result.stderr.strip()[:200]}")

# Apply --from filter
if args.from_step:
    try:
        start_idx = pipeline.index(args.from_step)
        pipeline = pipeline[start_idx:]
    except ValueError:
        print(f"ERROR: Step '{args.from_step}' not in pipeline")
        print(f"Available steps: {pipeline}")
        sys.exit(1)

# ============================================================================
# Validate Scripts Exist
# ============================================================================

for step in pipeline:
    if step not in STEPS:
        print(f"ERROR: Unknown step '{step}'")
        sys.exit(1)
    script_path = os.path.join(script_dir, STEPS[step]["script"])
    if not os.path.exists(script_path):
        print(f"ERROR: Script not found: {STEPS[step]['script']}")
        sys.exit(1)

# ============================================================================
# Fabric Workspace ID (Fabric mode only)
# ============================================================================

fabric_workspace_id = os.getenv("FABRIC_WORKSPACE_ID", "").strip()
if fabric_workspace_id:
    print(f"\n[OK] Using existing Fabric Workspace: {fabric_workspace_id}")
else:
    print("\n[OK] No FABRIC_WORKSPACE_ID set — a new workspace will be created.")

# ============================================================================
# Print Plan
# ============================================================================

mode = "Fabric"
print("\n" + "="*60)
print(f"Build Solution Pipeline ({mode} Mode)")
print("="*60)

print(f"\nSteps ({len(pipeline)}):")
for i, step in enumerate(pipeline, 1):
    info = STEPS[step]
    print(f"  {i}. [{step}] {info['name']}")

if args.dry_run:
    print("\n[DRY RUN] No scripts will be executed.")
    sys.exit(0)

print("\n" + "-"*60)
input("Press Enter to start (Ctrl+C to cancel)...")
print()

# ============================================================================
# Run Pipeline
# ============================================================================

def run_step(step_id):
    """Run a single step"""
    import time
    info = STEPS[step_id]
    script_path = os.path.join(script_dir, info["script"])
    
    if args.quiet:
        # Compact progress line
        print(f"  [{step_id}] {info['name']}...", end="", flush=True)
    else:
        print(f"\n{'='*60}")
        print(f"[{step_id}] {info['name']}")
        print(f"{'='*60}")
    
    # Build command
    cmd = [sys.executable, script_path]
    
    # Add step-specific arguments
    if step_id == "01" and args.clean:
        cmd.append("--clean")
    
    # Run the script
    start_time = time.time()
    if args.quiet:
        # Capture output in quiet mode
        result = subprocess.run(cmd, cwd=script_dir, capture_output=True, text=True)
        elapsed = time.time() - start_time
        
        if result.returncode != 0:
            print(f" FAILED ({elapsed:.1f}s)")
            print(f"\n{'='*60}")
            print(f"Error in step {step_id}:")
            print(f"{'='*60}")
            # Show last 20 lines of output on error
            output = result.stdout + result.stderr
            lines = output.strip().split('\n')
            for line in lines[-20:]:
                print(f"  {line}")
            if not args.continue_on_error:
                sys.exit(result.returncode)
            return False
        else:
            print(f" OK ({elapsed:.1f}s)")
            return True
    else:
        result = subprocess.run(cmd, cwd=script_dir)
        elapsed = time.time() - start_time
    
        if result.returncode != 0:
            print(f"\n[FAIL] Step {step_id} failed with exit code {result.returncode}")
            if not args.continue_on_error:
                sys.exit(result.returncode)
            return False
        
        print(f"\n[OK] Step {step_id} completed in {elapsed:.1f}s")
        return True


# Execute pipeline
import time
total_start = time.time()
successful = 0
failed = 0

if args.quiet:
    print(f"\nRunning {len(pipeline)} steps...")

for step in pipeline:
    if run_step(step):
        successful += 1
    else:
        failed += 1

total_elapsed = time.time() - total_start

# ============================================================================
# Summary
# ============================================================================

web_app_url = os.getenv("WEB_APP_URL", "")

if args.quiet:
    print(f"\n✓ Done! {successful}/{len(pipeline)} steps completed in {total_elapsed:.1f}s")
    if failed == 0:
        print(f"  Next: python infra/scripts/post-provision/06_test_agent.py")
    else:
        print(f"  Some steps failed. Check output above.")
        sys.exit(1)
else:
    print("\n" + "="*60)
    print("Pipeline Complete!")
    print("="*60)
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Total time: {total_elapsed:.1f}s")

    if failed == 0:
        print(f"""
Next step - Test the agent:
  python infra/scripts/post-provision/06_test_agent.py

Sample questions to try:
  - "How many outages occurred last month?"
  - "What is the response time required for outages?"
  - "Which outages exceeded the maximum duration defined in our policy?"
""")
    else:
        print("\nSome steps failed. Check the output above for errors.")
        sys.exit(1)

if web_app_url and "05" in pipeline:
    print(f"🚀 Your app is live! Open it here: {web_app_url}")
