"""
Scenario Registry
=================
Loads scenario packs from data/scenarios/scenarios.json.
Users can edit that file to add/remove scenarios or configure custom data.

Usage:
    from scenarios import list_scenarios, get_scenario, get_scenario_by_folder
"""

import json
import os

# Resolve paths relative to project root
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_SCENARIOS_ROOT = os.path.join(_PROJECT_ROOT, "data", "scenarios")
_SCENARIOS_JSON = os.path.join(_SCENARIOS_ROOT, "scenarios.json")

# ============================================================================
# Scenario Registry (loaded from scenarios.json)
# ============================================================================


def _load_scenarios():
    """Load scenarios from JSON file. Returns empty dict if file not found."""
    if not os.path.isfile(_SCENARIOS_JSON):
        print(f"⚠️  scenarios.json not found at: {_SCENARIOS_JSON}")
        return {}
    with open(_SCENARIOS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


SCENARIOS = _load_scenarios()


def list_scenarios():
    """Return dict of all registered scenarios with their metadata.

    Only includes scenarios whose data folder actually exists on disk.
    """
    available = {}
    for name, meta in SCENARIOS.items():
        abs_folder = os.path.join(_PROJECT_ROOT, meta["folder"])
        if os.path.isdir(abs_folder):
            available[name] = meta
    return available


def get_scenario(name):
    """Get a scenario by name. Returns metadata dict or None if not found/invalid.

    Validates that the scenario's data folder exists.
    """
    name = name.lower().strip()
    if name not in SCENARIOS:
        return None
    meta = SCENARIOS[name]
    abs_folder = os.path.join(_PROJECT_ROOT, meta["folder"])
    if not os.path.isdir(abs_folder):
        return None
    return meta


def get_scenario_by_folder(data_folder):
    """Look up a scenario by its DATA_FOLDER value (relative path).

    Useful for determining the active scenario from environment.
    Returns (name, metadata) tuple or (None, None).
    """
    # Normalise path separators
    normalised = data_folder.replace("\\", "/").strip("/")
    for name, meta in SCENARIOS.items():
        if meta["folder"].replace("\\", "/").strip("/") == normalised:
            return name, meta
    return None, None


def get_scenario_abs_path(name):
    """Return the absolute path to a scenario's data folder."""
    meta = get_scenario(name)
    if meta is None:
        return None
    return os.path.join(_PROJECT_ROOT, meta["folder"])
