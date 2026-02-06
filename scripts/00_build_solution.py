"""
Build Solution - Unified Pipeline
Master script that runs all steps to build the complete solution.

Usage:
    # Run all steps from the beginning (uses either Fabric Lakehouse or SQL + AI Search)
    python scripts/00_build_solution.py
    
    # Start from a specific step
    python scripts/00_build_solution.py --from 06

Steps (Full mode):
    01  - Generate sample data
    02  - Create Fabric Lakehouse
    03  - Load data into Fabric
    04  - Generate agent prompt
    06  - Upload documents to AI Search
    07  - Create Foundry Agent (Fabric SQL + Search)

Steps (Azure-only mode):
    01  - Generate sample data
    04  - Generate agent prompt
    05  - Upload data to Azure SQL
    06  - Upload documents to AI Search
    07  - Create Foundry Agent (Azure SQL + Search)

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
    "02": {"script": "02_create_fabric_items.py", "name": "Create Fabric Lakehouse", "time": "~30s", "fabric": True},
    "03": {"script": "03_load_fabric_data.py", "name": "Load Data into Fabric", "time": "~1min", "fabric": True},
    "04": {"script": "04_generate_agent_prompt.py", "name": "Generate Agent Prompt", "time": "~5s"},
    "05": {"script": "05_upload_to_sql.py", "name": "Upload to Azure SQL", "time": "~30s", "azure_only": True},
    "06": {"script": "06_upload_to_search.py", "name": "Upload to AI Search", "time": "~1min"},
    "07": {"script": "07_create_agent.py", "name": "Create Foundry Agent", "time": "~10s"},
}

# Pipeline order by mode
FABRIC_PIPELINE = ["01", "02", "03", "04", "06", "07"]
AZURE_ONLY_PIPELINE = ["01", "04", "05", "06", "07"]

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
"""
)
parser.add_argument("--industry", type=str, 
                    help="Industry for data generation (overrides .env)")
parser.add_argument("--usecase", type=str, 
                    help="Use case for data generation (overrides .env)")
parser.add_argument("--size", choices=["small", "medium", "large"],
                    help="Data size for generation (overrides .env)")
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
load_all_env()

# Get azure_only from environment variable (set AZURE_ENV_ONLY=true to use Azure SQL mode)
azure_only = os.getenv("AZURE_ENV_ONLY", "false").lower() in ("true", "1", "yes")

# ============================================================================
# Determine Pipeline
# ============================================================================

if args.only:
    pipeline = args.only
elif azure_only:
    pipeline = AZURE_ONLY_PIPELINE.copy()
else:
    pipeline = FABRIC_PIPELINE.copy()

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
    print(f"  {i}. [{step}] {info['name']} ({info['time']})")

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
