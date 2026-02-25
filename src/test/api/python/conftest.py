"""
Pytest configuration for app.py tests.
Sets up sys.path and conditionally mocks required modules.

This configuration file:
1. Adds the API Python path to sys.path for imports
2. Creates mock modules for chat, history, and history_sql routers ONLY when testing app.py
3. Ensures the test environment is properly configured before tests run
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

# Get absolute path to the test directory
test_dir = Path(__file__).parent.absolute()
# Navigate up to src directory: python -> api -> test -> src
src_dir = test_dir.parent.parent.parent
# Get the API Python path: src/api/python
api_python_path = src_dir / "api" / "python"

# Add to sys.path if not already there
api_python_str = str(api_python_path)
if api_python_str not in sys.path:
    sys.path.insert(0, api_python_str)


def create_mock_router():
    """
    Create a mock APIRouter instance.
    
    Returns:
        MagicMock: A mock router with routes and tags attributes.
    """
    mock_router = MagicMock()
    mock_router.routes = []
    mock_router.tags = []
    return mock_router


def should_mock_modules():
    """
    Determine if modules should be mocked based on which tests are being run.
    Only mock when testing app.py, not when testing chat.py or other modules.
    
    Returns:
        bool: True if modules should be mocked, False otherwise.
    """
    # Check command line arguments to see what's being tested
    for arg in sys.argv:
        # Don't mock if testing chat module
        if 'chat' in arg.lower() and 'test_chat' in arg.lower():
            return False
        # Don't mock if testing auth module  
        if 'auth' in arg.lower() and 'test_' in arg.lower():
            return False
        # Don't mock if testing history module
        if 'history' in arg.lower() and 'test_history' in arg.lower():
            return False
    
    # Mock if testing app.py or if no specific test file mentioned
    for arg in sys.argv:
        if 'test_app' in arg.lower():
            return True
    
    # Default: don't mock to allow real modules to load
    return False


def should_mock_azure_sdk():
    """
    Determine if Azure SDK modules should be mocked.
    
    Returns:
        bool: True if running any Python API tests that import chat or history modules.
    """
    # Always mock Azure SDK to prevent import errors
    return True


# Mock Azure SDK dependencies BEFORE any imports for chat tests
# This allows the chat module to be imported despite Azure SDK version issues
if should_mock_azure_sdk():
    # Create comprehensive mocks for problematic Azure imports
    mock_ai_projects_models = MagicMock()
    mock_ai_projects_models_internal = MagicMock()
    mock_ai_projects_aio = MagicMock()
    mock_ai_projects_operations = MagicMock()
    mock_ai_projects = MagicMock()
    mock_ai_projects.models = mock_ai_projects_models
    mock_ai_projects.aio = mock_ai_projects_aio
    mock_ai_projects.operations = mock_ai_projects_operations
    
    # Mock Azure AI Agents models to prevent import errors
    mock_ai_agents = MagicMock()
    mock_ai_agents_models = MagicMock()
    mock_ai_agents.models = mock_ai_agents_models
    
    # Mock specific classes that are imported
    mock_ai_agents_models.TruncationObject = MagicMock()
    
    # Register all mocks in sys.modules BEFORE any imports
    sys.modules['azure.ai.agents'] = mock_ai_agents
    sys.modules['azure.ai.agents.models'] = mock_ai_agents_models
    sys.modules['azure.ai.projects'] = mock_ai_projects
    sys.modules['azure.ai.projects.models'] = mock_ai_projects_models
    sys.modules['azure.ai.projects.models._models'] = mock_ai_projects_models_internal
    sys.modules['azure.ai.projects.aio'] = mock_ai_projects_aio
    sys.modules['azure.ai.projects.operations'] = mock_ai_projects_operations
    sys.modules['azure.ai.projects.operations._operations'] = MagicMock()
    sys.modules['azure.ai.projects.operations._patch'] = MagicMock()
    sys.modules['azure.ai.projects.operations._patch_datasets'] = MagicMock()
    sys.modules['azure.ai.projects._client'] = MagicMock()


# Conditionally create mock modules before they are imported by app.py
# This prevents import errors when testing app.py in isolation
# But allows other tests to import the real modules
if should_mock_modules():
    sys.modules['chat'] = MagicMock()
    sys.modules['history'] = MagicMock()
    sys.modules['history_sql'] = MagicMock()

    # Set up router mocks with proper attributes
    sys.modules['chat'].router = create_mock_router()
    sys.modules['history'].router = create_mock_router()
    sys.modules['history_sql'].router = create_mock_router()


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Set up the test environment before any tests run.
    
    This fixture runs automatically at the session scope to ensure
    all required mocks are in place before any test execution.
    
    Yields:
        None: Allows tests to run after setup.
    """
    # Conditionally ensure mocks are in place only for app.py tests
    if should_mock_modules():
        if 'chat' not in sys.modules:
            sys.modules['chat'] = MagicMock()
            sys.modules['chat'].router = create_mock_router()
        if 'history' not in sys.modules:
            sys.modules['history'] = MagicMock()
            sys.modules['history'].router = create_mock_router()
        if 'history_sql' not in sys.modules:
            sys.modules['history_sql'] = MagicMock()
            sys.modules['history_sql'].router = create_mock_router()
    
    yield
    
    # Cleanup is optional - mocks can persist for the test session

