"""
Build Solution - Unified Pipeline
Master script that runs all steps to build the complete solution.

Usage:
    # Run all steps from the beginning (uses either Fabric Lakehouse or Azure SQL + AI Search)
    python scripts/00_build_solution.py
    
    # Start from a specific step
    python scripts/00_build_solution.py --from 06

    # Bring your own data (skips AI data generation)
    python scripts/00_build_solution.py --custom-data data/customdata

Steps (Fabric SQL mode):
    01  - Generate sample data
    02  - Create Fabric Lakehouse & Load Data
    04  - Generate agent prompt
    06  - Upload documents to AI Search
    07  - Create Foundry Agent (Fabric SQL + Search)

Steps (Azure-only mode):
    01  - Generate sample data
    04  - Generate agent prompt
    05  - Upload data to Azure SQL
    06  - Upload documents to AI Search
    07  - Create Foundry Agent (Azure SQL + Search)

Custom Data mode (--custom-data):
    Skips step 01 and uses your own data from the specified folder.
    The folder must contain:
        tables/*.csv                 - One CSV per table
        documents/*.pdf              - PDF documents for AI Search
    The config/ folder (ontology_config.json) is auto-generated from your CSVs.

Both modes always use:
    - Native AzureAISearchTool for document search
    - execute_sql function tool for structured data
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
    "01": {"script": "01_generate_data.py", "name": "Generate Sample Data", "time": "~2min"},
    "02": {"script": "02_create_fabric_items.py", "name": "Create Fabric Lakehouse & Load Data", "time": "~1.5min", "fabric": True},
    "04": {"script": "04_generate_agent_prompt.py", "name": "Generate Agent Prompt", "time": "~5s"},
    "05": {"script": "05_upload_to_sql.py", "name": "Upload to Azure SQL", "time": "~30s", "azure_only": True},
    "06": {"script": "06_upload_to_search.py", "name": "Upload to AI Search", "time": "~1min"},
    "07": {"script": "07_create_agent.py", "name": "Create Foundry Agent", "time": "~10s"},
    "09": {"script": "09_app_deployment.py", "name": "App Deployment Config", "time": "~15s", "deploy_app": True},
}

# Pipeline order by mode
FABRIC_PIPELINE = ["01", "02", "04", "06", "07", "09"]
AZURE_ONLY_PIPELINE = ["01", "04", "05", "06", "07", "09"]

# ============================================================================
# Parse Arguments
# ============================================================================

parser = argparse.ArgumentParser(
    description="End-to-end setup: data → knowledge bases → agents",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  python scripts/00_build_solution.py                # Full Fabric mode or SQL mode
  python scripts/00_build_solution.py --from 06      # Start from step 06
  python scripts/00_build_solution.py --only 07      # Run only specific steps
  python scripts/00_build_solution.py -g rg-myproject-dev  # Pre-provisioned infra
  python scripts/00_build_solution.py --fabric-workspace-id <id>  # Pass Fabric workspace ID
  python scripts/00_build_solution.py --custom-data data/customdata  # Use your own data
"""
)
parser.add_argument("--industry", type=str, 
                    help="Industry for data generation (overrides .env)")
parser.add_argument("--usecase", type=str, 
                    help="Use case for data generation (overrides .env)")
parser.add_argument("--size", choices=["small", "medium", "large"],
                    help="Data size for generation (overrides .env)")
parser.add_argument("--fabric-workspace-id", type=str,
                    help="Fabric workspace ID (overrides FABRIC_WORKSPACE_ID in .env)")
parser.add_argument("--resource-group", "-g", type=str,
                    help="Azure resource group to fetch env settings from (for pre-provisioned infra)")
parser.add_argument("--custom-data", type=str,
                    help="Path to folder with tables/ (CSVs) and documents/ (PDFs). "
                         "Config is auto-generated from your CSV files.")
parser.add_argument("--clean", action="store_true",
                    help="Clean and recreate artifacts")

parser.add_argument("--from", dest="from_step", type=str,
                    help="Start from this step (e.g., --from 06)")
parser.add_argument("--only", nargs="+", type=str,
                    help="Run only these steps (e.g., --only 07)")

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
azd_loaded, project_loaded = load_all_env()

# ============================================================================
# Generate .env from Azure if resource group provided
# ============================================================================

# If --resource-group is passed, generate/update .env from Azure
# Otherwise, use existing .env file as-is
if args.resource_group:
    print(f"\nFetching settings from resource group: {args.resource_group}")
    generate_script = os.path.join(script_dir, "generate_env_from_azure.py")
    
    result = subprocess.run(
        [sys.executable, generate_script, "--resource-group", args.resource_group],
        cwd=script_dir
    )
    
    if result.returncode == 0:
        print("✓ Environment configured from Azure.")
        # Reload environment with new values
        from load_env import reload_env
        reload_env()
        load_all_env()
    else:
        print("Failed. Edit scripts/.env manually or retry with: python scripts/generate_env_from_azure.py -g <rg>")
        sys.exit(1)

# Get azure_only from environment variable (set AZURE_ENV_ONLY=true to use Azure SQL mode)
azure_only = os.getenv("AZURE_ENV_ONLY", "false").lower() in ("true", "1", "yes")
deploy_app = os.getenv("AZURE_ENV_DEPLOY_APP", "false").lower() in ("true", "1", "yes")

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

    # Set DATA_FOLDER in environment and persist to scripts/.env
    project_root = os.path.abspath(os.path.join(script_dir, ".."))
    relative_data_dir = os.path.relpath(custom_data_dir, project_root)
    os.environ["DATA_FOLDER"] = relative_data_dir

    from dotenv import set_key
    env_path = os.path.join(script_dir, ".env")
    set_key(env_path, "DATA_FOLDER", relative_data_dir)
    set_key(env_path, "INDUSTRY", custom_industry)
    set_key(env_path, "USECASE", custom_usecase)
    os.environ["INDUSTRY"] = custom_industry
    os.environ["USECASE"] = custom_usecase

    print(f"\n[OK] Custom data folder: {custom_data_dir}")
    print(f"     Industry: {custom_industry}")
    print(f"     Use Case: {custom_usecase}")
    print(f"     Tables: {', '.join(csv_files)}")
    print(f"     Documents: {', '.join(pdf_files) if pdf_files else '(none)'}")
    print(f"     DATA_FOLDER set to: {relative_data_dir}")

# ============================================================================
# Determine Pipeline
# ============================================================================

if args.only:
    pipeline = args.only
elif azure_only:
    pipeline = AZURE_ONLY_PIPELINE.copy()
else:
    pipeline = FABRIC_PIPELINE.copy()

# Skip data generation step when using custom data
if custom_data_dir and "01" in pipeline:
    pipeline = [s for s in pipeline if s != "01"]
    print("  (Skipping step 01 — using custom data instead of AI generation)")

# Apply --from filter
if args.from_step:
    try:
        start_idx = pipeline.index(args.from_step)
        pipeline = pipeline[start_idx:]
    except ValueError:
        print(f"ERROR: Step '{args.from_step}' not in pipeline")
        print(f"Available steps: {pipeline}")
        sys.exit(1)

# Append app deployment step if AZURE_ENV_DEPLOY_APP is true
if not deploy_app:
    pipeline = [s for s in pipeline if s != "09"]

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
# Interactive Prompt for Fabric Workspace ID (Fabric mode only)
# ============================================================================

if not azure_only:
    fabric_workspace_id = args.fabric_workspace_id or os.getenv("FABRIC_WORKSPACE_ID", "").strip()
    if not fabric_workspace_id:
        print("\n" + "="*60)
        print("Fabric Workspace Configuration")
        print("="*60)
        print("\nFabric mode requires a Workspace ID.")
        print("You can find it in your Fabric URL: https://app.fabric.microsoft.com/groups/<workspace-id>")
        fabric_workspace_id = input("\nFabric Workspace ID: ").strip()
        if not fabric_workspace_id:
            print("ERROR: Fabric Workspace ID is required in Fabric mode.")
            print("       Pass --fabric-workspace-id <id> or set FABRIC_WORKSPACE_ID in .env")
            print("       Or use AZURE_ENV_ONLY=true for Azure SQL mode.")
            sys.exit(1)
    # Make it available to downstream scripts
    os.environ["FABRIC_WORKSPACE_ID"] = fabric_workspace_id
    # Persist to scripts/.env so subsequent runs don't need to re-enter it
    from dotenv import set_key
    env_path = os.path.join(script_dir, ".env")
    set_key(env_path, "FABRIC_WORKSPACE_ID", fabric_workspace_id)

# ============================================================================
# Interactive Prompts for Data Generation
# ============================================================================

if "01" in pipeline:
    args.industry = args.industry or os.getenv("INDUSTRY")
    args.usecase = args.usecase or os.getenv("USECASE") or os.getenv("USE_CASE")
    args.size = args.size or os.getenv("DATA_SIZE", "small")
    
    if not args.industry or not args.usecase:
        print("\n" + "="*60)
        print("Data Generation Configuration")
        print("="*60)
        print("\nNo INDUSTRY/USECASE found. Sample scenarios:")
        print("-" * 60)
        samples = [
            ("Telecommunications", "Network operations"),
            ("Retail", "Inventory and sales"),
            ("Manufacturing", "Production tracking"),
            ("Insurance", "Claims processing"),
            ("Finance", "Transaction monitoring"),
        ]
        for ind, uc in samples:
            print(f"  {ind:<20} {uc}")
        print("-" * 60)
        
        if not args.industry:
            args.industry = input("\nIndustry: ").strip()
            if not args.industry:
                print("ERROR: Industry is required")
                sys.exit(1)
        if not args.usecase:
            args.usecase = input("Use Case: ").strip()
            if not args.usecase:
                print("ERROR: Use case is required")
                sys.exit(1)

# ============================================================================
# Print Plan
# ============================================================================

mode = "Azure SQL" if azure_only else "Fabric"
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
    if step_id == "01":
        if args.industry:
            cmd.extend(["--industry", args.industry])
        if args.usecase:
            cmd.extend(["--usecase", args.usecase])
        if args.size:
            cmd.extend(["--size", args.size])
    
    if step_id == "02" and args.clean:
        cmd.append("--clean")
    
    if step_id == "07" and azure_only:
        cmd.append("--azure-only")
    
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
        # Force reload environment after step 01 (it updates DATA_FOLDER, INDUSTRY, USECASE in .env)
        if step == "01":
            from load_env import reload_env
            reload_env()
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
        print(f"  Next: python scripts/08_test_agent.py")
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
  python scripts/08_test_agent.py

Sample questions to try:
  - "How many outages occurred last month?"
  - "What is the response time required for outages?"
  - "Which outages exceeded the maximum duration defined in our policy?"
""")
    else:
        print("\nSome steps failed. Check the output above for errors.")
        sys.exit(1)

if web_app_url and "09" in pipeline:
    print(f"🚀 Your app is live! Open it here: {web_app_url}")
