# Stable Cores

A **Stable Core** is the customer-agnostic **platform/infra baseline** every
solution sits on — the reliable, enterprise-ready foundation with **no customer-
or domain-specific content**.

- **Owns:** IaC (**both Bicep and Terraform**, each with reusable `modules/`),
  landing zone, core service wiring, identity/network/security baselines,
  deployment entrypoint, engineering guardrails.
- **Does not own:** app/agent architecture (→ Technical Pattern) or domain
  data/prompts/rules (→ Industry Scenario).
- **Hard rules:** ships **both IaC flavors**; **vanilla-only** — no Azure Verified
  Modules (`avm/`) and no `br/public:avm/...` references; authored to WAF
  principles.

## Catalog

| Stable Core | Deciding factor (platform baseline) | Status |
|---|---|---|
| [`agentic-apps`](./agentic-apps/) | Platform baseline for agentic-app solutions. | Placeholder |
| [`ms-iq`](./ms-iq/) | Microsoft IQ platform baseline. | Placeholder |

`.shared/` is **not** a Stable Core — it holds shared infrastructure assets reused
across cores.

## Adding a new stable core

Create a new `stable-cores/<name>/` folder **only** when the platform/infra
baseline is genuinely different from every existing core (different core service
integrations, deployment topology, or landing-zone baseline). App/agent behavior
goes to the **Technical Pattern** layer; domain content goes to the **Industry
Scenario** layer; a reusable platform capability added to an existing core is a
**Delta**. When adding one: follow the canonical shape (both IaC flavors,
vanilla-only, WAF), add a per-core `README.md`, and add a **Catalog** row here.

## Authoritative rule

This README is a human-facing index of *outcomes*. The authoritative
classification procedure (New vs. Same vs. Delta) and canonical folder shape /
IaC rules are owned by the `fde-contribution-layer-split` skill — see
`.github/skills/fde-contribution-layer-split/SKILL.md` and
`references/layer-structures.md`.
