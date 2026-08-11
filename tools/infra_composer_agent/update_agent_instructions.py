"""
One-off script to push each persistent Azure AI Foundry agent's local
instructions source back to its stored `instructions` field, so the agent
itself "remembers" the rules across sessions in the AI Foundry portal --
not just for the current run. There are two independent agents this script
can target:

  - "author"      (default) -- infra-composer-main-bicep-author.
                   Instructions = llm_composer.SYSTEM_PROMPT, which embeds
                   skills/bicep-main-authoring.md. llm_composer.py already
                   re-sends the same system prompt on every generation
                   request regardless of whether this script has ever been
                   run -- this script additionally keeps the agent's own
                   persistent config in sync with it (visible/inspectable
                   directly in the AI Foundry portal).

  - "interpreter" -- infra-composer-prompt-interpreter.
                   Instructions = llm_interpreter.INTERPRETER_INSTRUCTIONS,
                   which defines the resource-request JSON schema
                   ("resources" to add, "excludes" to drop/replace from a
                   technical pattern's baseline). Same situation:
                   llm_interpreter.py sends these instructions inline with
                   every call already (via the agent's own stored
                   instructions being the ones actually executed on each
                   run) -- run this whenever INTERPRETER_INSTRUCTIONS
                   changes so the LIVE persistent agent's behavior (e.g.
                   the new exclude/baseline logic) actually reflects the
                   latest wording, not a stale version from when the agent
                   was first created.

Requires:
  - An Azure AI Foundry project endpoint (--endpoint, or AI_FOUNDRY_PROJECT_ENDPOINT in
    the environment / .env file -- this script loads .env automatically, same as agent.py).
  - Credentials that can manage the target agent (uses DefaultAzureCredential --
    `az login` first, or any other credential source DefaultAzureCredential supports).
  - The `azure-ai-agents` and `azure-identity` packages (already a dependency of
    llm_composer.py's ai-foundry backend).

Usage:
    python update_agent_instructions.py
        # updates BOTH agents (author + interpreter) -- endpoint read from .env automatically
    python update_agent_instructions.py --dry-run
        # prints what would be sent for BOTH agents, no API call
    python update_agent_instructions.py --target interpreter
        # updates ONLY the interpreter agent, if you only want one

Run this again any time skills/bicep-main-authoring.md or
llm_interpreter.INTERPRETER_INSTRUCTIONS changes and you want the
corresponding persistent agent's stored instructions to reflect the update.
"""
from __future__ import annotations

import argparse
import os

from env_file import load_env_file
from llm_composer import DEFAULT_AUTHOR_AGENT_ID, SYSTEM_PROMPT, _load_skill, BICEP_AUTHORING_SKILL_PATH
from llm_interpreter import DEFAULT_INTERPRETER_AGENT_ID, INTERPRETER_INSTRUCTIONS

load_env_file()

TARGETS = {
    "author": {
        "default_agent_id": DEFAULT_AUTHOR_AGENT_ID,
        "instructions": SYSTEM_PROMPT,
        "describe": lambda: f"Loaded skill from {BICEP_AUTHORING_SKILL_PATH} ({len(_load_skill())} chars).",
    },
    "interpreter": {
        "default_agent_id": DEFAULT_INTERPRETER_AGENT_ID,
        "instructions": INTERPRETER_INSTRUCTIONS,
        "describe": lambda: f"Loaded INTERPRETER_INSTRUCTIONS from llm_interpreter.py ({len(INTERPRETER_INSTRUCTIONS)} chars).",
    },
}


def sync_agent_instructions(endpoint: str, targets: list[str] | None = None,
                             client=None) -> list[str]:
    """Pushes local instructions to the given persistent agent(s) (default:
    both). Reused by both the standalone CLI below and agent.py's main(),
    which calls this automatically at the start of every run so the live
    agents are always in sync with the local instruction sources -- no
    separate manual step required. Returns a short log of what was updated.
    Raises on failure (caller decides whether that should block the run)."""
    targets_to_update = targets or list(TARGETS)
    if client is None:
        from azure.ai.agents import AgentsClient
        from azure.identity import DefaultAzureCredential
        client = AgentsClient(endpoint=endpoint, credential=DefaultAzureCredential())

    log: list[str] = []
    for target_name in targets_to_update:
        target = TARGETS[target_name]
        agent_id = target["default_agent_id"]
        instructions = target["instructions"]
        client.update_agent(agent_id, instructions=instructions)
        log.append(f"Synced '{target_name}' agent ({agent_id}) instructions ({len(instructions)} chars).")
    return log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=list(TARGETS), default=None,
                         help="Update only this one persistent agent instead of both (default: "
                              "updates both 'author' and 'interpreter').")
    parser.add_argument("--endpoint", default=None,
                         help="Azure AI Foundry project endpoint. Falls back to AI_FOUNDRY_PROJECT_ENDPOINT env var.")
    parser.add_argument("--agent-id", default=None,
                         help="Agent to update (only valid together with --target; ignored when updating "
                              "both agents, since each has its own fixed id).")
    parser.add_argument("--dry-run", action="store_true",
                         help="Print the instructions that would be sent, without calling the API.")
    args = parser.parse_args()

    if args.agent_id and not args.target:
        raise SystemExit("--agent-id requires --target (pick which agent it applies to).")

    targets_to_update = [args.target] if args.target else list(TARGETS)

    endpoint = args.endpoint or os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint and not args.dry_run:
        raise SystemExit("Provide --endpoint or set AI_FOUNDRY_PROJECT_ENDPOINT (or use --dry-run).")

    client = None
    if not args.dry_run:
        from azure.ai.agents import AgentsClient
        from azure.identity import DefaultAzureCredential
        client = AgentsClient(endpoint=endpoint, credential=DefaultAzureCredential())

    for target_name in targets_to_update:
        target = TARGETS[target_name]
        agent_id = args.agent_id or target["default_agent_id"]
        instructions = target["instructions"]

        print(target["describe"]())
        print(f"Target: {target_name} agent ({agent_id})")

        if args.dry_run:
            print(f"\n--- instructions that would be sent for '{target_name}' (--dry-run, no API call made) ---\n")
            print(instructions)
            print()
            continue

        client.update_agent(agent_id, instructions=instructions)
        print(f"Updated agent '{agent_id}' instructions ({len(instructions)} chars) at {endpoint}.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
