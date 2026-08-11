# ms-iq

**Stable Core — customer-agnostic platform/infra baseline.** Microsoft IQ
platform/infra foundation, with no customer- or domain-specific content. Fill in
the specifics once the core's contents are finalized.

## Contents

- **`infra/`** — IaC in **both Bicep and Terraform** (each with reusable
  `modules/`), plus the landing zone (networking, security/identity baseline).
- **`src/`** — core service integration and environment bootstrap (`azd up`
  entrypoint).
- **`skills/`**, **`docs/`** — reusable engineering automation/guardrails and
  deployment/architecture guidance.

## Relationships

- **Hard rules:** ships both IaC flavors; **vanilla-only** (no `avm/`, no
  `br/public:avm/...`); authored to WAF principles.
- **Used by:** Technical Patterns (`technical-patterns/<name>/`); Industry
  Scenarios then supply the domain values.

See the [Stable Cores catalog](../README.md); the authoritative
layer-classification rule is owned by the `fde-contribution-layer-split` skill.
