"""
Build Solution
Master script that runs all steps to build the complete solution.

Usage:
    # Run full solution
    python scripts/00_build_solution.py

    # Foundry-only mode (no Fabric required)
    python scripts/00_build_solution.py --foundry-only
    
    # Start from a specific step
    python scripts/00_build_solution.py --from 04

Steps:
    01  - Generate sample data (AI-powered)
    02  - Create Fabric items (lakehouse, warehouse)
    03  - Load data into Fabric
    04  - Generate agent prompt
    05  - Create Fabric Data Agent
    06  - Upload documents to AI Search
    6a  - Upload data to Azure SQL Server
    07  - Create Foundry agent
    08  - Test agent

Foundry-only mode skips Fabric (02-05) and creates a search-only agent.
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
    "01": {"script": "01_generate_sample_data.py", "name": "Generate Sample Data", "time": "~2min"},
    "02": {"script": "02_create_fabric_items.py", "name": "Create Fabric Items", "time": "~30s"},
    "03": {"script": "03_load_fabric_data.py", "name": "Load Data into Fabric", "time": "~1min"},
    "04": {"script": "04_generate_agent_prompt.py", "name": "Generate Agent Prompt", "time": "~5s"},
    "05": {"script": "05_create_fabric_agent.py", "name": "Create Fabric Data Agent", "time": "~30s"},
    "06": {"script": "06_upload_to_search.py", "name": "Upload to AI Search", "time": "~1min"},
    "6a": {"script": "6a_upload_to_sql.py", "name": "Upload to Azure SQL", "time": "~1min"},
    "07": {"script": "07_create_foundry_agent.py", "name": "Create Foundry Agent", "time": "~10s"},
    "07-search": {"script": "07_create_foundry_agent.py", "name": "Create Foundry Agent (Search Only)", "time": "~10s", "args": ["--foundry-only"]},
    "08": {"script": "08_test_foundry_agent.py", "name": "Test Foundry Agent", "time": "interactive"},
}

# Default pipeline order
DEFAULT_PIPELINE = ["01", "02", "03", "04", "05", "06", "6a", "07"]
FOUNDRY_ONLY_PIPELINE = ["01", "06", "07-search"]

# ============================================================================
# Parse Arguments
# ============================================================================

parser = argparse.ArgumentParser(
    description="End-to-end setup: data → knowledge bases → agents → API → app",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  python scripts/00_build_solution.py                # Build full solution
  python scripts/00_build_solution.py --from 04      # Start from step 04
  python scripts/00_build_solution.py --only 07      # Run only specific steps
  python scripts/00_build_solution.py --skip-fabric  # Skip Fabric steps
  python scripts/00_build_solution.py --foundry-only # No Fabric required (Search only)
"""
)

parser.add_argument("--foundry-only", action="store_true",
                    help="Foundry-only mode: skip Fabric entirely, use AI Search only")
parser.add_argument("--industry", type=str, 
                    help="Industry for data generation (overrides .env)")
parser.add_argument("--usecase", type=str, 
                    help="Use case for data generation (overrides .env)")
parser.add_argument("--size", choices=["small", "medium", "large"],
                    help="Data size for generation (overrides .env)")
parser.add_argument("--clean", action="store_true",
                    help="Clean and recreate Fabric artifacts (use when switching scenarios)")

parser.add_argument("--from", dest="from_step", type=str,
                    help="Start from this step (e.g., --from 04)")
parser.add_argument("--only", nargs="+", type=str,
                    help="Run only these steps (e.g., --only 07 08)")

parser.add_argument("--skip-fabric", action="store_true",
                    help="Skip Fabric setup steps (02, 03)")
parser.add_argument("--skip-search", action="store_true",
                    help="Skip AI Search upload (06)")
parser.add_argument("--skip-agents", action="store_true",
                    help="Skip agent creation and testing (05, 07, 08)")

parser.add_argument("--dry-run", action="store_true",
                    help="Show what would be run without executing")
parser.add_argument("--continue-on-error", action="store_true",
                    help="Continue running steps even if one fails")

args = parser.parse_args()

# ============================================================================
# Determine Pipeline
# ============================================================================

if args.only:
    pipeline = args.only
elif args.foundry_only:
    pipeline = FOUNDRY_ONLY_PIPELINE.copy()
else:
    pipeline = DEFAULT_PIPELINE.copy()

# Apply --from filter
if args.from_step:
    try:
        start_idx = pipeline.index(args.from_step)
        pipeline = pipeline[start_idx:]
    except ValueError:
        print(f"ERROR: Step '{args.from_step}' not in pipeline")
        print(f"Available steps: {pipeline}")
        sys.exit(1)

# Apply skip filters
if args.skip_fabric:
    pipeline = [s for s in pipeline if s not in ["02", "03"]]
if args.skip_search:
    pipeline = [s for s in pipeline if s != "06"]
if args.skip_agents:
    pipeline = [s for s in pipeline if s not in ["05", "07", "08"]]

# ============================================================================
# Validate
# ============================================================================

# Check all scripts exist
for step in pipeline:
    script_path = os.path.join(script_dir, STEPS[step]["script"])
    if not os.path.exists(script_path):
        print(f"WARNING: Script not found: {STEPS[step]['script']}")

# Load environment from azd + project .env
from load_env import load_all_env
load_all_env()

# Data generation arguments: CLI > .env
if "01" in pipeline:
    args.industry = args.industry or os.getenv("INDUSTRY")
    args.usecase = args.usecase or os.getenv("USECASE")
    args.size = args.size or os.getenv("DATA_SIZE", "small")
    
    if not args.industry or not args.usecase:
        print("\n" + "="*60)
        print("Data Generation")
        print("="*60)
        print("\nNo INDUSTRY/USECASE found in .env or CLI args.")
        print("\nSample scenarios you can use:")
        print("-" * 60)
        print(f"  {'Industry':<18} {'Use Case':<40}")
        print("-" * 60)
        samples = [
            ("Telecommunications", "Network operations and service management"),
            ("Retail", "Inventory management with sales analytics"),
            ("Manufacturing", "Production line tracking with quality control"),
            ("Insurance", "Claims processing and policy management"),
            ("Finance", "Transaction monitoring and fraud detection"),
            ("Energy", "Grid monitoring and outage response"),
            ("Education", "Student enrollment and course management"),
            ("Hospitality", "Hotel reservations and guest services"),
            ("Logistics", "Fleet management with delivery tracking"),
            ("Real Estate", "Property listings and lease management"),
        ]
        for ind, uc in samples:
            print(f"  {ind:<18} {uc:<40}")
        print("-" * 60)
        print()
        if not args.industry:
            args.industry = input("Industry: ").strip()
            if not args.industry:
                print("ERROR: Industry is required. Set INDUSTRY in .env or pass --industry")
                sys.exit(1)
        if not args.usecase:
            args.usecase = input("Use Case: ").strip()
            if not args.usecase:
                print("ERROR: Use case is required. Set USECASE in .env or pass --usecase")
                sys.exit(1)

# ============================================================================
# Print Plan
# ============================================================================

print("\n" + "="*60)
print("Foundry IQ + Fabric IQ Pipeline")
print("="*60)

print(f"\nSteps ({len(pipeline)}):")
for i, step in enumerate(pipeline, 1):
    info = STEPS[step]
    print(f"  {i}. {info['name']} ({info['time']})")

if args.industry:
    print(f"\n  Industry: {args.industry}")
    print(f"  Use Case: {args.usecase}")

if args.dry_run:
    print("\n[DRY RUN] No scripts will be executed.")
    sys.exit(0)

print()
input("Press Enter to start...")
print()

# ============================================================================
# Run Pipeline
# ============================================================================

def run_step(step_id):
    """Run a single pipeline step."""
    info = STEPS[step_id]
    script_path = os.path.join(script_dir, info["script"])
    
    print(f"> [{step_id}] {info['name']}...", end=" ", flush=True)
    
    if not os.path.exists(script_path):
        print("SKIP (not found)")
        return True
    
    # Build command
    cmd = [sys.executable, script_path]
    
    # Add step-specific arguments defined in STEPS
    if "args" in info:
        cmd.extend(info["args"])
    
    # Add arguments for data generation script
    if step_id == "01" and args.industry:
        cmd.extend(["--industry", args.industry])
        cmd.extend(["--usecase", args.usecase])
        if args.size:
            cmd.extend(["--size", args.size])
    
    # Pass --clean to step 02 if requested
    if step_id == "02" and args.clean:
        cmd.append("--clean")
    
    # Create a clean environment that forces re-reading from .env
    # Remove DATA_FOLDER so child process reads fresh value from .env
    clean_env = os.environ.copy()
    clean_env.pop("DATA_FOLDER", None)
    
    # Run with output captured
    result = subprocess.run(cmd, cwd=os.path.dirname(script_dir), 
                           capture_output=True, text=True, env=clean_env)
    
    if result.returncode != 0:
        print("[FAIL] FAILED")
        print(f"\n  Error output:\n{result.stderr[-500:] if result.stderr else result.stdout[-500:]}")
        return False
    
    print("[OK]")
    return True


# Track results
results = {}
failed = False

for step in pipeline:
    success = run_step(step)
    results[step] = success
    
    if not success:
        failed = True
        if not args.continue_on_error:
            print(f"\nPipeline stopped. Use --continue-on-error to continue despite failures.")
            break

# ============================================================================
# Summary
# ============================================================================

print("\n" + "-"*60)

if failed:
    print("⚠ Pipeline completed with errors")
    sys.exit(1)
else:
    print("[OK] Pipeline completed successfully!")
    if args.foundry_only:
        print("\nNext: python scripts/08_test_foundry_agent.py --foundry-only")
    else:
        print("\nNext: python scripts/08_test_foundry_agent.py")
