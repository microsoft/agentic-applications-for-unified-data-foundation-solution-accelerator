"""
Build Solution - Unified Pipeline
Master script that runs all steps to build the complete solution.

Usage:
    # Run all steps from the beginning (uses either Fabric Lakehouse or Azure SQL + AI Search)
    python scripts/00_build_solution.py
    
    # Start from a specific step
    python scripts/00_build_solution.py --from 05

    # Bring your own data (skips AI data generation)
    python scripts/00_build_solution.py --custom-data data/customdata

Steps (Fabric SQL mode):
    01  - Generate sample data
    02  - Create Fabric Lakehouse & Load Data
    03  - Generate agent prompt
    05  - Upload documents to AI Search
    06  - Create Foundry Agent (Fabric SQL + Search)

Steps (Azure-only mode):
    01  - Generate sample data
    03  - Generate agent prompt
    04  - Upload data to Azure SQL
    05  - Upload documents to AI Search
    06  - Create Foundry Agent (Azure SQL + Search)

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
import atexit
import json
import subprocess
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

script_dir = os.path.dirname(os.path.abspath(__file__))

# ============================================================================
# WAF Network Access Helpers (MACAE pattern)
# ============================================================================
# For WAF deployments, public network access is disabled on Azure services.
# We temporarily enable it while running post-provisioning scripts, then restore.

_waf_original_state = {}  # tracks {resource_key: was_disabled}
_waf_resource_group = ""


_SHELL = sys.platform == "win32"  # az CLI on Windows is a .cmd, needs shell=True


def _run_az(args_list):
    """Run an az CLI command and return parsed JSON output (or None on error)."""
    cmd = ["az"] + args_list + ["-o", "json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=_SHELL)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def _run_az_update(args_list):
    """Run an az CLI update command (no JSON parsing needed)."""
    cmd = ["az"] + args_list + ["--output", "none"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=_SHELL)
    except Exception:
        pass


def is_waf_deployment(resource_group):
    """Check if the resource group has a Type=WAF tag (like MACAE pattern)."""
    try:
        cmd = ["az", "group", "show", "--name", resource_group, "--query", "tags.Type", "-o", "tsv"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, shell=_SHELL)
        return r.stdout.strip() == "WAF"
    except Exception:
        return False


def _check_public_access(resource_type, name, resource_group):
    """Check current public network access state for a resource."""
    try:
        if resource_type == "search":
            r = _run_az(["search", "service", "show", "--name", name,
                         "--resource-group", resource_group,
                         "--query", "publicNetworkAccess"])
            return str(r).strip().strip('"').lower() if r else "enabled"
        elif resource_type == "cognitiveservices":
            r = _run_az(["cognitiveservices", "account", "show", "--name", name,
                         "--resource-group", resource_group,
                         "--query", "properties.publicNetworkAccess"])
            return str(r).strip().strip('"').lower() if r else "enabled"
        elif resource_type == "cosmosdb":
            r = _run_az(["cosmosdb", "show", "--name", name,
                         "--resource-group", resource_group,
                         "--query", "publicNetworkAccess"])
            return str(r).strip().strip('"').lower() if r else "enabled"
        elif resource_type == "sql":
            r = _run_az(["sql", "server", "show", "--name", name,
                         "--resource-group", resource_group,
                         "--query", "publicNetworkAccess"])
            return str(r).strip().strip('"').lower() if r else "enabled"
    except Exception:
        pass
    return "enabled"


def _get_cognitiveservices_resource_id(name, resource_group):
    """Build the resource ID for a Cognitive Services account."""
    sub_id = os.getenv("AZURE_SUBSCRIPTION_ID", "").strip()
    if not sub_id:
        r = _run_az(["account", "show", "--query", "id"])
        sub_id = str(r).strip().strip('"') if r else ""
    if sub_id:
        return (f"/subscriptions/{sub_id}/resourceGroups/{resource_group}"
                f"/providers/Microsoft.CognitiveServices/accounts/{name}")
    return ""


def _enable_resource_public_access(resource_type, name, resource_group):
    """Enable public network access for a specific resource."""
    if resource_type == "search":
        _run_az_update(["search", "service", "update", "--name", name,
                        "--resource-group", resource_group,
                        "--public-network-access", "enabled"])
    elif resource_type == "cognitiveservices":
        res_id = _get_cognitiveservices_resource_id(name, resource_group)
        if res_id:
            _run_az_update(["resource", "update", "--ids", res_id,
                            "--set", "properties.publicNetworkAccess=Enabled"])
    elif resource_type == "cosmosdb":
        _run_az_update(["cosmosdb", "update", "--name", name,
                        "--resource-group", resource_group,
                        "--public-network-access", "ENABLED"])
    elif resource_type == "sql":
        _run_az_update(["sql", "server", "update", "--name", name,
                        "--resource-group", resource_group,
                        "--enable-public-network", "true"])


def _disable_resource_public_access(resource_type, name, resource_group):
    """Disable public network access for a specific resource."""
    if resource_type == "search":
        _run_az_update(["search", "service", "update", "--name", name,
                        "--resource-group", resource_group,
                        "--public-network-access", "disabled"])
    elif resource_type == "cognitiveservices":
        res_id = _get_cognitiveservices_resource_id(name, resource_group)
        if res_id:
            _run_az_update(["resource", "update", "--ids", res_id,
                            "--set", "properties.publicNetworkAccess=Disabled"])
    elif resource_type == "cosmosdb":
        _run_az_update(["cosmosdb", "update", "--name", name,
                        "--resource-group", resource_group,
                        "--public-network-access", "DISABLED"])
    elif resource_type == "sql":
        _run_az_update(["sql", "server", "update", "--name", name,
                        "--resource-group", resource_group,
                        "--enable-public-network", "false"])


def enable_waf_public_access(resource_group):
    """Temporarily enable public access on WAF-protected resources.

    Follows MACAE pattern but uses parallel execution for speed:
    check state, enable all disabled resources concurrently, single wait, verify all.
    """
    global _waf_resource_group
    _waf_resource_group = resource_group

    resources = []

    search_name = os.getenv("AZURE_AI_SEARCH_NAME", "").strip()
    if search_name:
        resources.append(("search", search_name, "AI Search"))

    ai_service = os.getenv("AI_SERVICE_NAME", "").strip()
    if ai_service:
        resources.append(("cognitiveservices", ai_service, "AI Services"))

    cosmos_account = os.getenv("AZURE_COSMOSDB_ACCOUNT", "").strip()
    if cosmos_account:
        resources.append(("cosmosdb", cosmos_account, "Cosmos DB"))

    sql_server = os.getenv("AZURE_SQLDB_SERVER", "").strip()
    if sql_server:
        resources.append(("sql", sql_server, "SQL Server"))

    if not resources:
        print("  No WAF-protected resources found in environment.")
        return

    print("\n=== Temporarily enabling public network access for WAF services ===")

    # Phase 1: Check current state in parallel
    def _check_one(res_type, res_name, display_name):
        current = _check_public_access(res_type, res_name, resource_group)
        return res_type, res_name, display_name, current

    with ThreadPoolExecutor(max_workers=len(resources)) as pool:
        futures = [pool.submit(_check_one, rt, rn, dn) for rt, rn, dn in resources]
        for f in as_completed(futures):
            res_type, res_name, display_name, current = f.result()
            if current == "disabled":
                _waf_original_state[f"{res_type}:{res_name}"] = True
            else:
                _waf_original_state[f"{res_type}:{res_name}"] = False
                print(f"  \u2713 {display_name} public access already enabled")

    # Phase 2: Enable all disabled resources in parallel
    to_enable = [(rt, rn, dn) for rt, rn, dn in resources
                 if _waf_original_state.get(f"{rt}:{rn}")]
    if to_enable:
        print(f"  Enabling public access for {len(to_enable)} resource(s) in parallel...")
        with ThreadPoolExecutor(max_workers=len(to_enable)) as pool:
            def _enable_one(res_type, res_name, display_name):
                _enable_resource_public_access(res_type, res_name, resource_group)
                return display_name
            futures = {pool.submit(_enable_one, rt, rn, dn): dn for rt, rn, dn in to_enable}
            for f in as_completed(futures):
                print(f"  \u2192 {f.result()} enable request sent")

        # Phase 3: Single wait, then verify all in parallel
        print(f"  Waiting 30s for changes to propagate...")
        time.sleep(30)

        def _verify_one(res_type, res_name, display_name):
            for attempt in range(1, 6):
                current = _check_public_access(res_type, res_name, resource_group)
                if current == "enabled":
                    return display_name, True, attempt
                time.sleep(5)
            return display_name, False, 5

        with ThreadPoolExecutor(max_workers=len(to_enable)) as pool:
            futures = [pool.submit(_verify_one, rt, rn, dn) for rt, rn, dn in to_enable]
            for f in as_completed(futures):
                name, ok, attempts = f.result()
                if ok:
                    print(f"  \u2713 {name} public access enabled successfully")
                else:
                    print(f"  Warning: verification timed out for {name}")

    print("===================================================================\n")


def restore_waf_network_access():
    """Restore original public access state for WAF-protected resources.

    Called via atexit to ensure cleanup even on errors/Ctrl+C.
    Uses parallel execution for speed.
    """
    if not _waf_original_state or not _waf_resource_group:
        return

    to_restore = [(k, v) for k, v in _waf_original_state.items() if v]
    if not to_restore:
        return

    print("\n=== Restoring network access settings ===")

    _display_names = {
        "search": "AI Search", "cognitiveservices": "AI Services",
        "cosmosdb": "Cosmos DB", "sql": "SQL Server"
    }

    def _restore_one(key):
        res_type, res_name = key.split(":", 1)
        display_name = _display_names.get(res_type, res_type)
        current = _check_public_access(res_type, res_name, _waf_resource_group)
        if current == "enabled":
            print(f"  Disabling public access for {display_name}: {res_name}")
            _disable_resource_public_access(res_type, res_name, _waf_resource_group)
            print(f"  \u2713 {display_name} public access disabled")
        else:
            print(f"  \u2713 {display_name} access unchanged (already at desired state)")

    with ThreadPoolExecutor(max_workers=len(to_restore)) as pool:
        list(pool.map(lambda kv: _restore_one(kv[0]), to_restore))

    print("==========================================\n")

    # Clear state to prevent double-restore (atexit + finally)
    _waf_original_state.clear()


# ============================================================================
# Configuration
# ============================================================================

STEPS = {
    "01": {"script": "01_generate_data.py", "name": "Generate Sample Data", "time": "~2min"},
    "02": {"script": "02_create_fabric_items.py", "name": "Create Fabric Lakehouse & Load Data", "time": "~1.5min", "fabric": True},
    "03": {"script": "03_generate_agent_prompt.py", "name": "Generate Agent Prompt", "time": "~5s"},
    "04": {"script": "04_upload_to_sql.py", "name": "Upload to Azure SQL", "time": "~30s", "azure_only": True},
    "05": {"script": "05_upload_to_search.py", "name": "Upload to AI Search", "time": "~1min"},
    "06": {"script": "06_create_agent.py", "name": "Create Foundry Agent", "time": "~10s"},
    "08": {"script": "08_app_deployment.py", "name": "App Deployment Config", "time": "~15s", "deploy_app": True},
}

# Pipeline order by mode
FABRIC_PIPELINE = ["01", "02", "03", "05", "06", "08"]
AZURE_ONLY_PIPELINE = ["01", "03", "04", "05", "06", "08"]

# ============================================================================
# Parse Arguments
# ============================================================================

parser = argparse.ArgumentParser(
    description="End-to-end setup: data → knowledge bases → agents",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  python scripts/00_build_solution.py                # Full Fabric mode or SQL mode
  python scripts/00_build_solution.py --from 05      # Start from step 05
  python scripts/00_build_solution.py --only 06      # Run only specific steps
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
                    help="Start from this step (e.g., --from 05)")
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
load_all_env()

# ============================================================================
# Generate .env from Azure if resource group provided
# ============================================================================

# If --resource-group is passed, generate/update .env from Azure
# Otherwise, use existing .env file as-is
if args.resource_group:
    print(f"\nFetching settings from resource group: {args.resource_group}")
    generate_script = os.path.join(script_dir, "generate_env_from_azure.py")
    
    gen_cmd = [sys.executable, generate_script, "--resource-group", args.resource_group]
    if args.quiet:
        gen_cmd.append("--quiet")
    
    result = subprocess.run(gen_cmd, cwd=script_dir)
    
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
    pipeline = [s for s in pipeline if s != "08"]

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
    create_workspace_flag = os.getenv("CREATE_FABRIC_WORKSPACE", "false").strip().lower() == "true"

    if not fabric_workspace_id and not create_workspace_flag:
        # No workspace ID and auto-create not enabled — prompt user
        print("\n" + "="*60)
        print("Fabric Workspace Configuration")
        print("="*60)
        print("\nFabric mode requires a Workspace ID.")
        print("You can find it in your Fabric URL: https://app.fabric.microsoft.com/groups/<workspace-id>")
        print("\nOr enable auto-creation: azd env set CREATE_FABRIC_WORKSPACE true")
        choice = input("\nFabric Workspace ID: ").strip()
        if choice:
            fabric_workspace_id = choice
        else:
            print("ERROR: Fabric Workspace ID is required in Fabric mode.")
            print("       Pass --fabric-workspace-id <id> or set FABRIC_WORKSPACE_ID in .env")
            print("       Or enable auto-creation: azd env set CREATE_FABRIC_WORKSPACE true")
            sys.exit(1)

    if fabric_workspace_id:
        # Make it available to downstream scripts
        os.environ["FABRIC_WORKSPACE_ID"] = fabric_workspace_id
        # Persist to scripts/.env so subsequent runs don't need to re-enter it
        from dotenv import set_key
        env_path = os.path.join(script_dir, ".env")
        set_key(env_path, "FABRIC_WORKSPACE_ID", fabric_workspace_id)
        # Also persist to azd env so .azure/<env>/.env stays in sync
        try:
            subprocess.run(["azd", "env", "set", "FABRIC_WORKSPACE_ID", fabric_workspace_id], check=True, capture_output=True)
        except Exception:
            pass
    # else: no workspace ID but CREATE_FABRIC_WORKSPACE is true — step 02 will auto-create

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
# WAF: Temporarily enable public access (MACAE pattern)
# ============================================================================

_is_waf = False
_rg = os.getenv("AZURE_RESOURCE_GROUP", "") or os.getenv("RESOURCE_GROUP_NAME", "")
if _rg:
    _is_waf = is_waf_deployment(_rg)

if _is_waf:
    # Register atexit handler FIRST so cleanup always runs (errors, Ctrl+C via KeyboardInterrupt)
    atexit.register(restore_waf_network_access)
    enable_waf_public_access(_rg)

# ============================================================================
# Run Pipeline
# ============================================================================

def run_step(step_id):
    """Run a single step"""
    info = STEPS[step_id]
    script_path = os.path.join(script_dir, info["script"])
    
    # Dynamic label for step 02 based on workspace mode
    step_name = info['name']
    if step_id == "02":
        create_ws = os.getenv("CREATE_FABRIC_WORKSPACE", "false").strip().lower() == "true"
        if create_ws:
            step_name = "Create Workspace, Lakehouse & Load Data"

    if args.quiet:
        # Compact progress line
        print(f"  [{step_id}] {step_name}...", end="", flush=True)
    else:
        print(f"\n{'='*60}")
        print(f"[{step_id}] {step_name}")
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
    
    if step_id == "02":
        if args.clean:
            cmd.append("--clean")
    
    if step_id == "06" and azure_only:
        cmd.append("--azure-only")
    
    # Run the script
    start_time = time.time()
    if args.quiet:
        # Capture output in quiet mode (use utf-8 to handle emoji from child scripts)
        result = subprocess.run(cmd, cwd=script_dir, capture_output=True, text=True, encoding='utf-8', errors='replace')
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
total_start = time.time()
successful = 0
failed = 0

try:
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
finally:
    # Restore WAF network access even if pipeline fails or is interrupted
    if _is_waf:
        restore_waf_network_access()

total_elapsed = time.time() - total_start

# ============================================================================
# Summary
# ============================================================================

web_app_url = os.getenv("WEB_APP_URL", "")

if args.quiet:
    print(f"\n✓ Done! {successful}/{len(pipeline)} steps completed in {total_elapsed:.1f}s")
    if failed == 0:
        print(f"  Next: python scripts/07_test_agent.py")
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
  python scripts/07_test_agent.py

Sample questions to try:
  - "How many outages occurred last month?"
  - "What is the response time required for outages?"
  - "Which outages exceeded the maximum duration defined in our policy?"
""")
    else:
        print("\nSome steps failed. Check the output above for errors.")
        sys.exit(1)

if web_app_url and "08" in pipeline:
    print(f"🚀 Your app is live! Open it here: {web_app_url}")
