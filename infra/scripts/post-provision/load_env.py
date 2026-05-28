"""
Load environment variables from azd deployment.

This module loads Azure service configuration from the azd environment (.azure/<env>/.env).
Project-specific settings (industry, usecase, data_size) are managed via scenarios.json.

Azure services (from azd):
    - AZURE_AI_AGENT_ENDPOINT
    - AZURE_AI_ENDPOINT  
    - AZURE_OPENAI_ENDPOINT
    - AZURE_AI_SEARCH_ENDPOINT
    - AZURE_STORAGE_BLOB_ENDPOINT
    - AZURE_CHAT_MODEL
    - AZURE_EMBEDDING_MODEL
    - FABRIC_WORKSPACE_ID
    - etc.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv


def load_azd_env():
    """
    Load environment variables from azd deployment.
    
    Reads from .azure/<defaultEnvironment>/.env
    Returns True if azd env was found and loaded.
    """
    script_dir = Path(__file__).parent
    azure_dir = script_dir.parent.parent.parent / ".azure"
    
    # Get environment name from config.json or AZURE_ENV_NAME
    env_name = os.environ.get("AZURE_ENV_NAME", "")
    
    if not env_name and (azure_dir / "config.json").exists():
        with open(azure_dir / "config.json") as f:
            config = json.load(f)
            env_name = config.get("defaultEnvironment", "")
    
    if env_name:
        env_path = azure_dir / env_name / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            return True
    
    return False


def load_all_env():
    """
    Load azd environment variables.
    
    Reads Azure service endpoints from .azure/<env>/.env (created by azd up).
    Project-specific settings (scenario, industry, etc.) come from scenarios.json.
    
    Returns True if azd env was loaded.
    """
    azd_loaded = load_azd_env()
    
    if not azd_loaded:
        print("⚠️  No azd environment found.")
        print("   Run 'azd up' to deploy infrastructure, or set Azure env vars manually.")
    
    return azd_loaded


def get_required_env(var_name: str, description: str = None) -> str:
    """
    Get a required environment variable or raise an error.
    
    Args:
        var_name: Environment variable name
        description: Human-readable description for error message
        
    Returns:
        The environment variable value
        
    Raises:
        ValueError: If variable is not set
    """
    value = os.environ.get(var_name)
    if not value:
        desc = description or var_name
        raise ValueError(
            f"{var_name} not set. {desc}\n"
            f"Run 'azd up' to deploy Azure resources or set the variable manually."
        )
    return value


def get_data_folder() -> str:
    """
    Get DATA_FOLDER resolved to an absolute path.
    
    DATA_FOLDER in .env can be relative (to project root) or absolute.
    This function always returns an absolute path.
    
    Returns:
        Absolute path to the data folder
        
    Raises:
        ValueError: If DATA_FOLDER is not set
    """
    data_folder = os.environ.get("DATA_FOLDER")
    if not data_folder:
        raise ValueError(
            "DATA_FOLDER not set.\n"
            "Use --scenario or --custom-data to specify data, "
            "or set DATA_FOLDER environment variable."
        )
    
    # If already absolute, return as-is
    if os.path.isabs(data_folder):
        return data_folder
    
    # Resolve relative path from project root (3 levels up from infra/scripts/post-provision/)
    project_root = Path(__file__).parent.parent.parent.parent
    return str((project_root / data_folder).resolve())


def print_env_status():
    """Print status of loaded environment variables (for debugging)."""
    print("\n📋 Environment Configuration:")
    print("-" * 50)
    
    # Azure services (from azd)
    azure_vars = [
        ("AZURE_AI_AGENT_ENDPOINT", "AI Foundry Project"),
        ("AZURE_AI_ENDPOINT", "AI Services"),
        ("AZURE_OPENAI_ENDPOINT", "OpenAI"),
        ("AZURE_AI_SEARCH_ENDPOINT", "AI Search"),
        ("AZURE_CHAT_MODEL", "Chat Model"),
        ("AZURE_EMBEDDING_MODEL", "Embedding Model"),
    ]
    
    print("\n🔵 Azure Services (from azd):")
    for var, name in azure_vars:
        value = os.environ.get(var, "")
        if value:
            # Truncate long URLs
            display = value[:50] + "..." if len(value) > 50 else value
            print(f"  [OK] {name}: {display}")
        else:
            print(f"  [FAIL] {name}: not set")
    
    # Project settings (from scenario or env)
    project_vars = [
        ("FABRIC_WORKSPACE_ID", "Fabric Workspace"),
        ("SOLUTION_NAME", "Solution Name"),
        ("AZURE_ENV_NAME", "azd Environment"),
        ("INDUSTRY", "Industry"),
        ("USECASE", "Use Case"),
        ("DATA_FOLDER", "Data Folder"),
    ]
    
    print("\n🟢 Project Settings:")
    for var, name in project_vars:
        value = os.environ.get(var, "")
        if value:
            display = value[:50] + "..." if len(value) > 50 else value
            print(f"  [OK] {name}: {display}")
        else:
            print(f"  ○ {name}: not set")
    
    print("-" * 50)



