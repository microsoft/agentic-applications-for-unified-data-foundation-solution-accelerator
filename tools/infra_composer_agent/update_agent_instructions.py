"""
One-off script to publish each Foundry agent DEFINITION (model + system
instructions) via the new Responses-API-era Azure AI Foundry SDK
(azure-ai-projects' project.agents.get/create_version -- see
foundry_client.register_agent), purely so the agent is visible/inspectable
in the AI Foundry portal's Agents tab for governance/audit purposes. There
are two independent agent names this script can target:

  - "author"      (default) -- infra-composer-main-bicep-author.
                   Instructions = llm_composer.SYSTEM_PROMPT, which embeds
                   skills/bicep-main-authoring.md.

  - "planner"     -- infra-composer-resource-planner.
                   Instructions = conversational_planner.PLANNER_INSTRUCTIONS.

IMPORTANT: this registration is entirely optional for the agent to work --
llm_composer.py / conversational_planner.py call the Responses API directly
(foundry_client.call_responses) with `model` + `instructions` on every
request; they never look up or reference this registered agent definition.
Run this only when you want the AI Foundry portal's Agents tab to reflect
the current instructions for inspection purposes.

Requires:
  - An Azure AI Foundry project endpoint (--endpoint, or AI_FOUNDRY_PROJECT_ENDPOINT in
    the environment / .env file -- this script loads .env automatically, same as agent.py).
  - A model deployment name (--model, or AI_FOUNDRY_MODEL_DEPLOYMENT) -- required by
    the new PromptAgentDefinition (there's no pre-existing agent with a model already
    baked in anymore).
  - Credentials that can manage the target agent (uses DefaultAzureCredential --
    `az login` first, or any other credential source DefaultAzureCredential supports).
  - The `azure-ai-projects` and `azure-identity` packages (already a dependency of
    llm_composer.py's ai-foundry backend).

Usage:
    python update_agent_instructions.py
        # publishes BOTH agent definitions (author + planner) -- endpoint/model read from .env
    python update_agent_instructions.py --dry-run
        # prints what would be sent for BOTH agents, no API call
    python update_agent_instructions.py --target planner
        # publishes ONLY the planner agent definition, if you only want one

Run this again any time skills/bicep-main-authoring.md or
conversational_planner.PLANNER_INSTRUCTIONS changes and you want the portal's
agent definition to reflect the update.
"""
from __future__ import annotations

import argparse
import os

from env_file import load_env_file
from foundry_client import register_agent
from llm_composer import DEFAULT_AUTHOR_AGENT_NAME, SYSTEM_PROMPT, _load_skill, BICEP_AUTHORING_SKILL_PATH
from conversational_planner import DEFAULT_PLANNER_AGENT_NAME, PLANNER_INSTRUCTIONS

load_env_file()

TARGETS = {
    "author": {
        "agent_name": DEFAULT_AUTHOR_AGENT_NAME,
        "instructions": SYSTEM_PROMPT,
        "describe": lambda: f"Loaded skill from {BICEP_AUTHORING_SKILL_PATH} ({len(_load_skill())} chars).",
    },
    "planner": {
        "agent_name": DEFAULT_PLANNER_AGENT_NAME,
        "instructions": PLANNER_INSTRUCTIONS,
        "describe": lambda: f"Loaded PLANNER_INSTRUCTIONS from conversational_planner.py ({len(PLANNER_INSTRUCTIONS)} chars).",
    },
}



def sync_agent_instructions(endpoint: str, model: str | None = None,
                             targets: list[str] | None = None) -> list[str]:
    """Publishes local instructions to the given persistent agent definition(s)
    (default: both), via foundry_client.register_agent. Reused by both the
    standalone CLI below and agent.py's main(), which calls this automatically
    at the start of every run so the portal-visible agent definitions stay in
    sync with the local instruction sources. Returns a short log of what was
    updated. Raises on failure (caller decides whether that should block the
    run) -- but this registration itself is unused by the actual generation/
    interpretation calls, so a failure here is safe to treat as a warning."""
    if not model:
        raise RuntimeError(
            "Registering an agent definition requires a model deployment name "
            "(--model or AI_FOUNDRY_MODEL_DEPLOYMENT) -- the new PromptAgentDefinition "
            "has no pre-existing model baked in."
        )
    targets_to_update = targets or list(TARGETS)
    log: list[str] = []
    for target_name in targets_to_update:
        target = TARGETS[target_name]
        status = register_agent(endpoint, target["agent_name"], model, target["instructions"])
        log.append(status)
    return log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=list(TARGETS), default=None,
                         help="Update only this one persistent agent instead of both (default: "
                              "updates both 'author' and 'interpreter').")
    parser.add_argument("--endpoint", default=None,
                         help="Azure AI Foundry project endpoint. Falls back to AI_FOUNDRY_PROJECT_ENDPOINT env var.")
    parser.add_argument("--model", default=None,
                         help="Model deployment name. Falls back to AI_FOUNDRY_MODEL_DEPLOYMENT env var.")
    parser.add_argument("--dry-run", action="store_true",
                         help="Print the instructions that would be sent, without calling the API.")
    args = parser.parse_args()

    targets_to_update = [args.target] if args.target else list(TARGETS)

    endpoint = args.endpoint or os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
    model = args.model or os.environ.get("AI_FOUNDRY_MODEL_DEPLOYMENT")
    if not endpoint and not args.dry_run:
        raise SystemExit("Provide --endpoint or set AI_FOUNDRY_PROJECT_ENDPOINT (or use --dry-run).")
    if not model and not args.dry_run:
        raise SystemExit("Provide --model or set AI_FOUNDRY_MODEL_DEPLOYMENT (or use --dry-run).")

    for target_name in targets_to_update:
        target = TARGETS[target_name]
        agent_name = target["agent_name"]
        instructions = target["instructions"]

        print(target["describe"]())
        print(f"Target: {target_name} agent ('{agent_name}')")

        if args.dry_run:
            print(f"\n--- instructions that would be sent for '{target_name}' (--dry-run, no API call made) ---\n")
            print(instructions)
            print()
            continue

        status = register_agent(endpoint, agent_name, model, instructions)
        print(f"{status} at {endpoint}.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
