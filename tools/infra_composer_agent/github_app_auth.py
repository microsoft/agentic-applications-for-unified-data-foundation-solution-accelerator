"""
GitHub App authentication for the composer agent's git operations.

Why this exists: without it, every clone/push made by this agent runs as
whichever human happens to have it checked out locally (their personal
Git Credential Manager login). That means commits/branches show up as
authored/pushed by that person's own GitHub identity, and the agent can
only reach repos that person personally has push access to.

A GitHub App gives the agent its own machine identity ("<app-name>[bot]")
instead, with access scoped to exactly the repos the app is installed on,
and short-lived (~1 hour) installation tokens instead of a long-lived
personal access token sitting in an env var.

Setup (one-time, done in the GitHub UI, not here):
    1. Create a GitHub App: Settings -> Developer settings -> GitHub Apps -> New.
    2. Grant it repository permission "Contents: Read & write" (and
       "Pull requests: Read & write" if the agent will open PRs later).
    3. Install the app on whichever target repo(s) it needs to push to.
    4. Download the app's private key (.pem) and note its App ID and the
       Installation ID for the target repo (Settings -> Installed GitHub
       Apps -> Configure -> the installation ID is in the URL).

Required environment variables at run time:
    GH_APP_ID              - the App's numeric ID
    GH_APP_PRIVATE_KEY_PATH - path to the downloaded .pem private key
                              (or set GH_APP_PRIVATE_KEY with the PEM
                              contents directly, e.g. from a secret store)
    GH_APP_INSTALLATION_ID - the installation ID for the target repo

If these are not set, git_ops falls back to whatever credential helper
is already configured locally (today's behavior) -- this is purely
additive and optional.
"""
from __future__ import annotations

import os
import time

import jwt
import requests

GITHUB_API = "https://api.github.com"


def _load_private_key() -> str:
    inline = os.environ.get("GH_APP_PRIVATE_KEY")
    if inline:
        return inline
    path = os.environ.get("GH_APP_PRIVATE_KEY_PATH")
    if not path:
        raise RuntimeError(
            "GitHub App auth requested but neither GH_APP_PRIVATE_KEY nor "
            "GH_APP_PRIVATE_KEY_PATH is set."
        )
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _app_jwt(app_id: str, private_key: str) -> str:
    """Builds the short-lived (10 min) JWT used to authenticate AS the app
    itself, which is then exchanged for a real installation access token."""
    now = int(time.time())
    payload = {
        "iat": now - 60,       # allow for clock drift
        "exp": now + 9 * 60,   # GitHub caps this at 10 minutes
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def get_installation_token(
    app_id: str | None = None,
    installation_id: str | None = None,
    private_key: str | None = None,
) -> str:
    """Exchanges the app's JWT for a real installation access token (valid
    ~1 hour) scoped to only the repos this installation covers. Reads
    GH_APP_ID / GH_APP_INSTALLATION_ID / GH_APP_PRIVATE_KEY[_PATH] from the
    environment when the corresponding argument is omitted."""
    app_id = app_id or os.environ.get("GH_APP_ID")
    installation_id = installation_id or os.environ.get("GH_APP_INSTALLATION_ID")
    if not app_id or not installation_id:
        raise RuntimeError(
            "GitHub App auth requires GH_APP_ID and GH_APP_INSTALLATION_ID."
        )
    private_key = private_key or _load_private_key()

    token = _app_jwt(app_id, private_key)
    resp = requests.post(
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def is_configured() -> bool:
    """True when enough env vars are present to attempt GitHub App auth."""
    return bool(
        os.environ.get("GH_APP_ID")
        and os.environ.get("GH_APP_INSTALLATION_ID")
        and (os.environ.get("GH_APP_PRIVATE_KEY") or os.environ.get("GH_APP_PRIVATE_KEY_PATH"))
    )


def get_app_bot_identity(app_id: str | None = None, token: str | None = None) -> tuple[str, str]:
    """Returns the (name, email) git identity for commits made by this app,
    following GitHub's convention for bot commit identities:
    '<app-slug>[bot]' / '<app-id>+<app-slug>[bot]@users.noreply.github.com'.
    Looks up the app's slug via the API using the given (or freshly
    exchanged) installation token."""
    app_id = app_id or os.environ.get("GH_APP_ID")
    resp = requests.get(
        f"{GITHUB_API}/app",
        headers={
            "Authorization": f"Bearer {_app_jwt(app_id, _load_private_key())}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    slug = resp.json()["slug"]
    name = f"{slug}[bot]"
    email = f"{app_id}+{slug}[bot]@users.noreply.github.com"
    return name, email


def inject_token_into_url(url: str, token: str) -> str:
    """Rewrites an https://github.com/... URL to embed the installation
    token so `git clone`/`git push` authenticate as the app, without
    needing any credential helper configured. GitHub App tokens use
    'x-access-token' as the username by convention."""
    if not url.startswith("https://"):
        return url  # only https URLs support inline token auth this way
    return url.replace("https://", f"https://x-access-token:{token}@", 1)
