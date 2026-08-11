"""
Minimal .env file loader -- no external dependency (avoids adding
python-dotenv just for this).

Why this exists: the agent reads several secrets/config values from the
environment (AI_FOUNDRY_*, GH_APP_*) via os.environ.get(...) scattered
across agent.py/llm_composer.py/llm_interpreter.py/github_app_auth.py.
Rather than requiring every one of those to be exported by hand in every
shell session, this loads a local, gitignored `.env` file (KEY=VALUE per
line) into os.environ once at startup, so a single `.env` file next to
agent.py can hold everything persistently on disk without ever being
committed.

Real environment variables always win: this never overwrites a variable
that is already set, so CI/CD secrets or explicit `$env:X = ...` in a
shell still take precedence over whatever is in `.env`.
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_env_file(path: Path = DEFAULT_ENV_PATH) -> list[str]:
    """Reads `path` (if it exists) and sets any KEY=VALUE pairs found into
    os.environ, skipping blank lines, '#' comments, and any key that is
    already set in the real environment. Returns the list of keys it set
    (for logging), silently doing nothing if the file doesn't exist."""
    if not path.exists():
        return []
    set_keys: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or key in os.environ:
            continue
        os.environ[key] = value
        set_keys.append(key)
    return set_keys
