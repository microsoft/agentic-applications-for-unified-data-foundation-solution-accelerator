#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "azure-ai-projects>=2.0.0",
#     "azure-identity>=1.17.0",
#     "openai>=2.0.0",
#     "requests>=2.31.0",
# ]
# ///
"""Run a grounding evaluation against a deployed Azure AI Foundry agent.

Generic, self-contained post-deployment script. Drop it into any azd-based
repository that deploys a Foundry agent; it has no imports from the host repo.

For each row of a JSONL dataset (``{"query": ..., "ground_truth": ...}``) it
asks the deployed agent the query, then starts a Foundry evaluation run that
scores the responses with the built-in Groundedness, Relevance, and Coherence
evaluators. By default it waits for the run and prints the results.

Target resolution (first match wins):

1. Command-line arguments.
2. ``--resource-group``: Foundry account/project discovered in that group.
3. Local azd environment (``azd env get-values``) -- the default. If it has no
   project endpoint but has a resource group, that group is discovered.
4. Process environment variables.

The agent defaults to a name found in the environment (see AGENT_NAME_KEYS),
otherwise the only agent in the project. The evaluator model defaults to the
agent's own model deployment.

Requirements: Python 3.10+; signed in with ``az login`` or ``azd auth login``,
with the Azure AI User role on the Foundry project. Missing Python packages
(see REQUIRED_PACKAGES) are pip-installed into the current interpreter on first
run; pass ``--skip-install`` to disable. ``uv run``/``pipx run`` also read the
inline dependency block above.

Examples:
    python run_agent_evaluation.py
    python run_agent_evaluation.py --environment dev --max-items 0
    python run_agent_evaluation.py --resource-group rg-app --subscription <id>
    python run_agent_evaluation.py -g rg-app --agent-name MyAgent --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("agent-evaluation")

# (pip requirement, import module, minimum major version); keep in sync with the inline block above.
REQUIRED_PACKAGES = (
    ("azure-ai-projects>=2.0.0", "azure.ai.projects", 2),
    ("azure-identity>=1.17.0", "azure.identity", 1),
    ("openai>=2.0.0", "openai", 2),
    ("requests>=2.31.0", "requests", 2),
)
ARM_ENDPOINT = "https://management.azure.com"
COGNITIVE_SERVICES_API_VERSION = "2025-06-01"
TERMINAL_RUN_STATUSES = {"completed", "failed", "canceled", "cancelled"}

# Environment keys checked, in order, in the azd environment and process environment.
ENDPOINT_KEYS = (
    "AZURE_AI_PROJECT_ENDPOINT",
    "AZURE_AI_AGENT_ENDPOINT",
    "AZURE_EXISTING_AIPROJECT_ENDPOINT",
    "FOUNDRY_PROJECT_ENDPOINT",
    "PROJECT_ENDPOINT",
    "projectEndpoint",
)
AGENT_NAME_KEYS = (
    "AGENT_EVALUATION_AGENT_NAME",
    "AZURE_AI_AGENT_NAME",
    "AZURE_AGENT_NAME",
    "FOUNDRY_AGENT_NAME",
    "AGENT_NAME",
    "AGENT_NAME_CHAT",
)
RESOURCE_GROUP_KEYS = ("AZURE_RESOURCE_GROUP", "AZURE_RESOURCE_GROUP_NAME", "RESOURCE_GROUP_NAME", "resourceGroupName")
SUBSCRIPTION_KEYS = ("AZURE_SUBSCRIPTION_ID",)

DATASET_CANDIDATES = (
    "data/evaluation/dataset.jsonl",
    "data/evaluation/eval_dataset.jsonl",
    "data/eval/dataset.jsonl",
    "evaluation/dataset.jsonl",
    "evaluations/dataset.jsonl",
    "evals/dataset.jsonl",
    "eval/dataset.jsonl",
)
SEARCH_SKIP_DIRS = {".git", ".azure", ".venv", "venv", "env", "node_modules", "__pycache__", "dist", "build", ".tox"}


class EvaluationConfigError(RuntimeError):
    """Raised when the evaluation target or inputs cannot be resolved."""


@dataclass
class EvaluationTarget:
    source: str
    subscription_id: str | None
    resource_group: str | None
    project_endpoint: str
    agent_name: str | None
    evaluator_model: str | None


def _first(*values: Any) -> str | None:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


# ---------------------------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------------------------

def _missing_packages() -> list[str]:
    import importlib.metadata
    import importlib.util

    missing: list[str] = []
    for requirement, module, min_major in REQUIRED_PACKAGES:
        distribution = requirement.split(">=")[0]
        try:
            installed = importlib.util.find_spec(module) is not None
        except ModuleNotFoundError:
            installed = False
        try:
            major = int(importlib.metadata.version(distribution).split(".")[0])
        except (importlib.metadata.PackageNotFoundError, ValueError):
            major = -1
        if not installed or major < min_major:
            missing.append(requirement)
    return missing


def ensure_dependencies(install: bool) -> bool:
    """Make sure the required packages are importable, pip-installing them if allowed."""
    missing = _missing_packages()
    if not missing:
        return True
    command = [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", *missing]
    if not install:
        LOGGER.error("Missing Python packages: %s. Install with: %s", ", ".join(missing), " ".join(command))
        return False

    LOGGER.info("Installing missing Python packages (this can take a few minutes): %s", ", ".join(missing))
    if sys.prefix == sys.base_prefix and not os.environ.get("CONDA_PREFIX"):
        command.append("--user")
    if subprocess.run(command, check=False).returncode != 0:
        LOGGER.error("Package installation failed. Install manually: %s", " ".join(command))
        return False

    import importlib
    import site

    importlib.invalidate_caches()
    user_site = site.getusersitepackages()
    if os.path.isdir(user_site) and user_site not in sys.path:
        sys.path.append(user_site)
    still_missing = _missing_packages()
    if still_missing:
        LOGGER.error("Packages still unavailable after install: %s. Re-run the script.", ", ".join(still_missing))
        return False
    return True


def _lookup(env: dict[str, str], keys: tuple[str, ...]) -> str | None:
    return _first(*(env.get(key) for key in keys))


# ---------------------------------------------------------------------------
# Project root and azd environment
# ---------------------------------------------------------------------------

def find_project_root(explicit: Path | None) -> Path:
    """azd project root (folder with azure.yaml), else git root, else the current directory."""
    if explicit:
        return explicit.resolve()
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for folder in (start, *start.parents):
            if (folder / "azure.yaml").is_file() or (folder / "azure.yml").is_file():
                return folder
    git = shutil.which("git")
    if git:
        result = subprocess.run([git, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    return Path.cwd()


def _parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_azd_env(project_root: Path, environment: str | None) -> dict[str, str]:
    """Return azd environment values, preferring the azd CLI over raw `.azure/<env>/.env` files."""
    azd = shutil.which("azd")
    if azd:
        command = [azd, "env", "get-values", "--output", "json", "--no-prompt"]
        if environment:
            command += ["--environment", environment]
        result = subprocess.run(command, cwd=project_root, capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            try:
                return {key: str(value) for key, value in json.loads(result.stdout).items()}
            except json.JSONDecodeError:
                pass
        LOGGER.debug("azd env get-values failed: %s", (result.stderr or "").strip())

    azure_dir = project_root / ".azure"
    if not environment and (azure_dir / "config.json").is_file():
        environment = json.loads((azure_dir / "config.json").read_text(encoding="utf-8")).get("defaultEnvironment")
    env_file = azure_dir / environment / ".env" if environment else None
    return _parse_dotenv(env_file) if env_file and env_file.is_file() else {}


# ---------------------------------------------------------------------------
# Azure Resource Manager discovery
# ---------------------------------------------------------------------------

def _current_cli_subscription() -> str | None:
    az = shutil.which("az")
    if not az:
        return None
    result = subprocess.run(
        [az, "account", "show", "--query", "id", "--output", "tsv"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _arm_get_all(credential, path: str) -> list[dict[str, Any]]:
    import requests

    token = credential.get_token(f"{ARM_ENDPOINT}/.default").token
    url: str | None = f"{ARM_ENDPOINT}{path}"
    items: list[dict[str, Any]] = []
    while url:
        response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
        if response.status_code >= 400:
            raise EvaluationConfigError(
                f"Azure Resource Manager request failed ({response.status_code}): {response.text[:500]}"
            )
        body = response.json()
        items.extend(body.get("value", []))
        url = body.get("nextLink")
    return items


def discover_foundry_project(
    credential,
    *,
    subscription_id: str,
    resource_group: str,
    account_name: str | None,
    project_name: str | None,
) -> tuple[str, str, str]:
    """Find exactly one Foundry project in a resource group. Returns (account, project, endpoint)."""
    base = (
        f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        "/providers/Microsoft.CognitiveServices/accounts"
    )
    try:
        accounts = _arm_get_all(credential, f"{base}?api-version={COGNITIVE_SERVICES_API_VERSION}")
    except EvaluationConfigError as exc:
        raise EvaluationConfigError(
            f"{exc}\nLooked in subscription {subscription_id}; pass --subscription if '{resource_group}' is elsewhere."
        ) from exc

    accounts = [
        account for account in accounts
        if str(account.get("kind", "")).lower() == "aiservices"
        and (not account_name or account["name"].lower() == account_name.lower())
    ]
    if not accounts:
        raise EvaluationConfigError(
            f"No Azure AI Foundry (AIServices) account found in resource group '{resource_group}'"
            + (f" named '{account_name}'." if account_name else ".")
        )

    candidates: list[tuple[str, str, str]] = []
    for account in accounts:
        for project in _arm_get_all(
            credential, f"{base}/{account['name']}/projects?api-version={COGNITIVE_SERVICES_API_VERSION}"
        ):
            name = project["name"].split("/")[-1]
            if project_name and name.lower() != project_name.lower():
                continue
            endpoints = (project.get("properties") or {}).get("endpoints") or {}
            endpoint = endpoints.get("AI Foundry API") or (
                f"https://{account['name']}.services.ai.azure.com/api/projects/{name}"
            )
            candidates.append((account["name"], name, endpoint))

    if not candidates:
        raise EvaluationConfigError(
            f"No Foundry project found in resource group '{resource_group}'"
            + (f" named '{project_name}'." if project_name else ".")
        )
    if len(candidates) > 1:
        listed = ", ".join(f"{account}/{project}" for account, project, _ in candidates)
        raise EvaluationConfigError(
            f"Multiple Foundry projects found ({listed}). Select one with --ai-account and/or --project-name."
        )
    return candidates[0]


# ---------------------------------------------------------------------------
# Target resolution
# ---------------------------------------------------------------------------

def resolve_target(args: argparse.Namespace, azd_env: dict[str, str], credential) -> EvaluationTarget:
    process_env = dict(os.environ)
    azd_rg = _lookup(azd_env, RESOURCE_GROUP_KEYS)
    explicit_model = _first(args.evaluator_model, os.environ.get("AGENT_EVALUATION_EVALUATOR_MODEL"))
    endpoint = _first(args.project_endpoint, _lookup(azd_env, ENDPOINT_KEYS), _lookup(process_env, ENDPOINT_KEYS))
    resource_group = args.resource_group or (None if endpoint else azd_rg)

    if resource_group and not args.project_endpoint:
        subscription_id = _first(
            args.subscription,
            _lookup(azd_env, SUBSCRIPTION_KEYS),
            _lookup(process_env, SUBSCRIPTION_KEYS),
            _current_cli_subscription(),
        )
        if not subscription_id:
            raise EvaluationConfigError("Could not determine the subscription. Pass --subscription.")
        account, project, endpoint = discover_foundry_project(
            credential,
            subscription_id=subscription_id,
            resource_group=resource_group,
            account_name=args.ai_account,
            project_name=args.project_name,
        )
        LOGGER.info("Discovered Foundry project '%s/%s' in '%s'", account, project, resource_group)
        # azd values describe the local deployment; only trust them for the same resource group.
        same_deployment = bool(azd_rg) and azd_rg.lower() == resource_group.lower()
        return EvaluationTarget(
            source=f"resource group '{resource_group}'",
            subscription_id=subscription_id,
            resource_group=resource_group,
            project_endpoint=endpoint,
            agent_name=_first(
                args.agent_name,
                os.environ.get("AGENT_EVALUATION_AGENT_NAME"),
                _lookup(azd_env, AGENT_NAME_KEYS) if same_deployment else None,
            ),
            evaluator_model=explicit_model,
        )

    if not endpoint:
        raise EvaluationConfigError(
            "No Foundry project endpoint or resource group found in the azd environment. "
            "Run from an azd project with a deployed environment, or pass --environment, "
            "--resource-group, or --project-endpoint."
        )
    env_name = _first(args.environment, azd_env.get("AZURE_ENV_NAME"))
    return EvaluationTarget(
        source=f"azd environment '{env_name}'" if azd_env else "arguments / process environment",
        subscription_id=_first(args.subscription, _lookup(azd_env, SUBSCRIPTION_KEYS)),
        resource_group=azd_rg,
        project_endpoint=endpoint,
        agent_name=_first(args.agent_name, _lookup(azd_env, AGENT_NAME_KEYS), _lookup(process_env, AGENT_NAME_KEYS)),
        evaluator_model=explicit_model,
    )


def resolve_agent_and_model(project_client, target: EvaluationTarget) -> None:
    """Confirm the agent exists (or pick the only one) and default the evaluator model to its model."""
    if target.agent_name:
        agent = project_client.agents.get(target.agent_name)
    else:
        agents = list(project_client.agents.list())
        if len(agents) != 1:
            names = ", ".join(sorted(agent.name for agent in agents)) or "<none>"
            raise EvaluationConfigError(
                f"Could not pick an agent automatically; the project has {len(agents)} ({names}). Pass --agent-name."
            )
        agent = agents[0]
        target.agent_name = agent.name

    if not target.evaluator_model:
        definition = getattr(getattr(agent.versions, "latest", None), "definition", None)
        target.evaluator_model = getattr(definition, "model", None)
        if not target.evaluator_model:
            raise EvaluationConfigError(
                f"Could not determine the model used by agent '{target.agent_name}'. Pass --evaluator-model."
            )


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

def resolve_dataset(explicit: Path | None, project_root: Path) -> Path:
    candidate = explicit or (Path(os.environ["AGENT_EVALUATION_DATASET"]) if os.environ.get("AGENT_EVALUATION_DATASET") else None)
    if candidate:
        path = candidate if candidate.is_absolute() else Path.cwd() / candidate
        if not path.is_file():
            raise EvaluationConfigError(f"Dataset not found: {path}")
        return path

    for relative in DATASET_CANDIDATES:
        path = project_root / relative
        if path.is_file():
            return path

    found: list[Path] = []
    for folder, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in SEARCH_SKIP_DIRS]
        if "dataset.jsonl" in files:
            found.append(Path(folder) / "dataset.jsonl")
    if len(found) == 1:
        return found[0]
    if found:
        listed = ", ".join(str(path.relative_to(project_root)) for path in found)
        raise EvaluationConfigError(f"Multiple dataset.jsonl files found ({listed}). Pass --dataset.")
    raise EvaluationConfigError(f"No dataset.jsonl found under {project_root}. Pass --dataset.")


def load_dataset(path: Path, query_field: str, ground_truth_field: str, max_items: int) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvaluationConfigError(f"{path}:{line_number}: invalid JSON ({exc})") from exc
            query = row.get(query_field)
            if not query:
                continue
            items.append({"query": str(query), "ground_truth": str(row.get(ground_truth_field) or "")})
            if max_items and len(items) >= max_items:
                break
    return items


# ---------------------------------------------------------------------------
# Agent responses and evaluation
# ---------------------------------------------------------------------------

def _response_text(response) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text
    parts = []
    for output in getattr(response, "output", None) or []:
        for content in getattr(output, "content", None) or []:
            value = getattr(content, "text", None)
            if value:
                parts.append(value)
    return "".join(parts)


def generate_responses(openai_client, agent_name: str, items: list[dict[str, str]], concurrency: int) -> list[dict[str, str]]:
    def ask(indexed: tuple[int, dict[str, str]]) -> dict[str, str] | None:
        index, item = indexed
        try:
            response = openai_client.responses.create(
                input=item["query"],
                extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
            )
            answer = _response_text(response)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Query %s/%s failed: %s", index, len(items), exc)
            return None
        if not answer:
            LOGGER.warning("Query %s/%s returned no text", index, len(items))
            return None
        return {**item, "response": answer}

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        results = list(pool.map(ask, enumerate(items, start=1)))
    enriched = [result for result in results if result]
    LOGGER.info("Agent answered %s/%s queries", len(enriched), len(items))
    return enriched


def _evaluator(name: str, builtin: str, model: str, threshold: int, with_context: bool) -> dict[str, Any]:
    mapping = {"query": "{{item.query}}", "response": "{{item.response}}"}
    if with_context:
        mapping["context"] = "{{item.ground_truth}}"
    return {
        "type": "azure_ai_evaluator",
        "name": name,
        "evaluator_name": builtin,
        "evaluator_version": "",
        "initialization_parameters": {"deployment_name": model, "threshold": threshold},
        "data_mapping": mapping,
    }


def create_or_get_evaluation(openai_client, eval_name: str, agent_name: str, model: str, threshold: int):
    """Reuse an evaluation with the same name, otherwise create it."""
    for existing in openai_client.evals.list():
        if existing.name == eval_name:
            LOGGER.info("Reusing evaluation '%s' (%s)", eval_name, existing.id)
            return existing

    evaluation = openai_client.evals.create(
        name=eval_name,
        metadata={"agent_name": agent_name},
        data_source_config={
            "type": "custom",
            "item_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "response": {"type": "string"},
                    "ground_truth": {"type": "string"},
                },
                "required": ["query", "response"],
            },
            "include_sample_schema": True,
        },
        testing_criteria=[
            _evaluator("Groundedness", "builtin.groundedness", model, threshold, with_context=True),
            _evaluator("Relevance", "builtin.relevance", model, threshold, with_context=False),
            _evaluator("Coherence", "builtin.coherence", model, threshold, with_context=False),
        ],
    )
    LOGGER.info("Created evaluation '%s' (%s)", eval_name, evaluation.id)
    return evaluation


def wait_for_run(openai_client, eval_id: str, run_id: str, timeout_seconds: int, poll_seconds: int):
    deadline = time.monotonic() + timeout_seconds
    while True:
        run = openai_client.evals.runs.retrieve(run_id, eval_id=eval_id)
        LOGGER.info("Run status: %s", run.status)
        if str(run.status).lower() in TERMINAL_RUN_STATUSES:
            return run
        if time.monotonic() >= deadline:
            LOGGER.warning("Timed out after %ss waiting for the evaluation run", timeout_seconds)
            return run
        time.sleep(poll_seconds)


def report_run(run) -> None:
    counts = run.result_counts
    if counts:
        LOGGER.info("Items: total=%s passed=%s failed=%s errored=%s", counts.total, counts.passed, counts.failed, counts.errored)
    for criteria in run.per_testing_criteria_results or []:
        total = criteria.passed + criteria.failed
        rate = f"{criteria.passed / total:.0%}" if total else "n/a"
        LOGGER.info("  %-12s passed=%s failed=%s (%s)", criteria.testing_criteria, criteria.passed, criteria.failed, rate)
    if run.error and getattr(run.error, "message", None):
        LOGGER.error("Run error: %s", run.error.message)
    if run.report_url:
        LOGGER.info("Report: %s", run.report_url)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a grounding evaluation against a deployed Azure AI Foundry agent.")
    target = parser.add_argument_group("target (defaults to the local azd environment)")
    target.add_argument("-e", "--environment", help="azd environment name. Defaults to the azd default environment.")
    target.add_argument("--project-dir", type=Path, help="azd project folder. Defaults to the nearest folder containing azure.yaml.")
    target.add_argument("-g", "--resource-group", help="Discover the Foundry project from this resource group.")
    target.add_argument("-s", "--subscription", help="Subscription ID. Defaults to the azd environment, then the current az CLI subscription.")
    target.add_argument("--ai-account", help="Foundry (AIServices) account name, when the resource group has several.")
    target.add_argument("--project-name", help="Foundry project name, when there are several.")
    target.add_argument("--project-endpoint", help="Foundry project endpoint. Skips discovery.")
    target.add_argument("--agent-name", help="Agent to evaluate. Defaults to an agent name in the environment, else the only agent in the project.")
    target.add_argument("--evaluator-model", help="Model deployment used by the evaluators. Defaults to the agent's model.")

    evaluation = parser.add_argument_group("evaluation")
    evaluation.add_argument("--eval-name", default=os.environ.get("AGENT_EVALUATION_NAME"), help="Evaluation name; reused if it exists. Defaults to '<agent> Grounding Evaluation'.")
    evaluation.add_argument("--dataset", type=Path, help="JSONL dataset. Defaults to a dataset.jsonl found in the project.")
    evaluation.add_argument("--query-field", default="query", help="Dataset field holding the question (default: query).")
    evaluation.add_argument("--ground-truth-field", default="ground_truth", help="Dataset field holding the expected answer (default: ground_truth).")
    evaluation.add_argument("--max-items", type=int, default=20, help="Rows to evaluate; 0 evaluates all rows (default: 20).")
    evaluation.add_argument("--threshold", type=int, default=3, help="Pass threshold (1-5) for each evaluator (default: 3).")
    evaluation.add_argument("--concurrency", type=int, default=4, help="Parallel agent calls (default: 4).")
    evaluation.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True, help="Wait for the run and print results (default: wait).")
    evaluation.add_argument("--timeout", type=int, default=1800, help="Seconds to wait for the run (default: 1800).")
    evaluation.add_argument("--poll-interval", type=int, default=15, help="Seconds between status checks (default: 15).")
    evaluation.add_argument("--dry-run", action="store_true", help="Resolve and print the target without calling the agent or creating an evaluation.")
    evaluation.add_argument("--skip-install", action="store_true", help="Do not pip-install missing Python packages.")
    evaluation.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
        force=True,
    )
    for noisy in ("azure", "httpx", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if args.max_items < 0:
        LOGGER.error("--max-items must be 0 (all rows) or a positive number")
        return 2

    if not ensure_dependencies(install=not args.skip_install):
        return 2

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    try:
        project_root = find_project_root(args.project_dir)
        dataset = resolve_dataset(args.dataset, project_root)
        items = load_dataset(dataset, args.query_field, args.ground_truth_field, args.max_items)
        if not items:
            raise EvaluationConfigError(f"No rows with a '{args.query_field}' field in {dataset}")

        credential = DefaultAzureCredential()
        target = resolve_target(args, load_azd_env(project_root, args.environment), credential)
        LOGGER.info("Using %s -> %s", target.source, target.project_endpoint)

        with AIProjectClient(endpoint=target.project_endpoint, credential=credential) as project_client:
            resolve_agent_and_model(project_client, target)
            eval_name = args.eval_name or f"{target.agent_name} Grounding Evaluation"

            LOGGER.info("Evaluation target (from %s):", target.source)
            LOGGER.info("  Project root:     %s", project_root)
            LOGGER.info("  Subscription:     %s", target.subscription_id or "-")
            LOGGER.info("  Resource group:   %s", target.resource_group or "-")
            LOGGER.info("  Project endpoint: %s", target.project_endpoint)
            LOGGER.info("  Agent:            %s", target.agent_name)
            LOGGER.info("  Evaluator model:  %s", target.evaluator_model)
            LOGGER.info("  Evaluation:       %s", eval_name)
            LOGGER.info("  Dataset:          %s (%s rows)", dataset, len(items))
            if args.dry_run:
                LOGGER.info("Dry run: no agent calls or evaluation runs were made.")
                return 0

            openai_client = project_client.get_openai_client()
            evaluation = create_or_get_evaluation(
                openai_client, eval_name, target.agent_name, target.evaluator_model, args.threshold
            )
            enriched = generate_responses(openai_client, target.agent_name, items, args.concurrency)
            if not enriched:
                LOGGER.error("The agent returned no responses; no evaluation run was created.")
                return 1

            run = openai_client.evals.runs.create(
                eval_id=evaluation.id,
                name=f"{target.agent_name}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                metadata={"agent_name": target.agent_name, "dataset": dataset.name},
                data_source={
                    "type": "jsonl",
                    "source": {"type": "file_content", "content": [{"item": item} for item in enriched]},
                },
            )
            LOGGER.info("Started run '%s' (%s)", run.name, run.id)
            if not args.wait:
                LOGGER.info("Not waiting for results (--no-wait).")
                return 0

            run = wait_for_run(openai_client, evaluation.id, run.id, args.timeout, args.poll_interval)
            report_run(run)
            return 0 if str(run.status).lower() == "completed" else 1
    except EvaluationConfigError as exc:
        LOGGER.error("%s", exc)
        return 2
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Evaluation failed", exc_info=True)
        LOGGER.error("Evaluation failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
