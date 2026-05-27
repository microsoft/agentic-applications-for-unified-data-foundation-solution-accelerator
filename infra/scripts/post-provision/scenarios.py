"""
Scenario Registry
=================
Centralised registry of pre-built scenario packs.
Each entry maps a scenario name to its metadata and data folder.

Usage:
    from scenarios import list_scenarios, get_scenario, get_scenario_by_folder
"""

import os

# Resolve paths relative to project root
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_SCENARIOS_ROOT = os.path.join(_PROJECT_ROOT, "data", "scenarios")

# ============================================================================
# Scenario Registry
# ============================================================================

SCENARIOS = {
    "insurance": {
        "folder": "data/scenarios/insurance",
        "industry": "Insurance",
        "usecase": "Claims processing and customer management",
        "description": "Pre-built insurance scenario with claims, policies, customers and communications data.",
        "landing_text": "You can ask questions around customer policies, claims and communications.",
        "app_title": "Contoso Insurance",
        "app_header": "| Claims Analysis Agents",
    },
    "retail": {
        "folder": "data/scenarios/retail",
        "industry": "Retail",
        "usecase": "Inventory and sales operations",
        "description": "Pre-built retail scenario with products, orders, customers, and inventory data.",
        "landing_text": "You can ask questions around sales, products and orders.",
        "app_title": "Contoso Retail",
        "app_header": "| Unified Data Analysis Agents",
    },
    "default": {
        "folder": "data/scenarios/default",
        "industry": "Telecommunications",
        "usecase": "Network operations",
        "description": "Default telecommunications scenario with network operations data (small).",
        "landing_text": "You can ask questions around network operations and outages.",
        "app_title": "Contoso",
        "app_header": "| Unified Data Analysis Agents",
    },
    "default_large": {
        "folder": "data/scenarios/default_large",
        "industry": "Telecommunications",
        "usecase": "Network operations and outage tracking",
        "description": "Default telecommunications scenario with expanded network operations data (large).",
        "landing_text": "You can ask questions around network operations and outages.",
        "app_title": "Contoso",
        "app_header": "| Unified Data Analysis Agents",
    },
}


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
