"""
One-off script to push the bicep-main-authoring skill (see skills/bicep-main-authoring.md)
into the persistent Azure AI Foundry author agent's stored `instructions` field, so the
agent itself "remembers" these rules across sessions -- not just for the current run
(llm_composer.py already loads the same file into every generation request's system
prompt regardless of whether this script has ever been run; this script additionally
keeps the agent's own persistent configuration in sync with it).

Requires:
  - An Azure AI Foundry project endpoint (--endpoint or AI_FOUNDRY_PROJECT_ENDPOINT env var).
  - Credentials that can manage the target agent (uses DefaultAzureCredential --
    `az login` first, or any other credential source DefaultAzureCredential supports).
  - The `azure-ai-agents` and `azure-identity` packages (already a dependency of
    llm_composer.py's ai-foundry backend).

Usage:
    python update_agent_instructions.py --endpoint https://<project>.services.ai.azure.com/api/projects/<name>
    python update_agent_instructions.py --agent-id asst_XXXXXXXX --endpoint ...
    python update_agent_instructions.py --dry-run   # just prints what would be sent, no API call

Run this again any time skills/bicep-main-authoring.md changes and you want the persistent
agent's own instructions to reflect the update (llm_composer.py picks up the file
automatically on its own -- this script is only needed to also update the agent's stored
`instructions`, e.g. so the rules are visible/inspectable directly in the AI Foundry portal).
"""
from __future__ import annotations

import argparse
import os

from llm_composer import DEFAULT_AUTHOR_AGENT_ID, SYSTEM_PROMPT, _load_skill, BICEP_AUTHORING_SKILL_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=None,
                         help="Azure AI Foundry project endpoint. Falls back to AI_FOUNDRY_PROJECT_ENDPOINT env var.")
    parser.add_argument("--agent-id", default=None,
                         help=f"Agent to update (default: the persistent author agent, {DEFAULT_AUTHOR_AGENT_ID}).")
    parser.add_argument("--dry-run", action="store_true",
                         help="Print the instructions that would be sent, without calling the API.")
    args = parser.parse_args()

    agent_id = args.agent_id or DEFAULT_AUTHOR_AGENT_ID
    instructions = SYSTEM_PROMPT

    print(f"Loaded skill from {BICEP_AUTHORING_SKILL_PATH} ({len(_load_skill())} chars).")
    print(f"Target agent: {agent_id}")

    if args.dry_run:
        print("\n--- instructions that would be sent (--dry-run, no API call made) ---\n")
        print(instructions)
        return 0

    endpoint = args.endpoint or os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise SystemExit("Provide --endpoint or set AI_FOUNDRY_PROJECT_ENDPOINT (or use --dry-run).")

    from azure.ai.agents import AgentsClient
    from azure.identity import DefaultAzureCredential

    client = AgentsClient(endpoint=endpoint, credential=DefaultAzureCredential())
    client.update_agent(agent_id, instructions=instructions)
    print(f"Updated agent '{agent_id}' instructions ({len(instructions)} chars) at {endpoint}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
