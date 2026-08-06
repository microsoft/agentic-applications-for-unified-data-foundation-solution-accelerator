# Real-Time Alerts

A streaming telemetry pipeline that ingests high-volume events, evaluates them for conditions of interest, and raises alerts/dashboards in near real time.

## What this pattern does

Telemetry/events stream into an Event Hub, which a Function App consumes to evaluate alerting rules and write raw/aggregated results to a Storage Account and Cosmos DB (NoSQL) for alert-state tracking. Configuration for alerting thresholds lives in App Configuration. When a condition fires, an Event Grid topic publishes an alert event for downstream routing. Operational dashboards and workbooks in Log Analytics/Application Insights give on-call teams live visibility, a portal dashboard summarizes system health, and every service-to-service call uses a managed identity with least-privilege RBAC role assignments.

## Resources used

- Event Hub (telemetry ingestion)
- Function App (stream processing / rule evaluation)
- Storage Account (raw/aggregated events)
- Cosmos DB (NoSQL) (alert state)
- App Configuration (alerting thresholds)
- Event Grid (alert fan-out)
- Key Vault, Managed Identity, Role Assignments
- Log Analytics + Application Insights + data collection rule + workbook
- Portal Dashboard (system health)
- Virtual Network, Private Endpoints, Private DNS Zones

## How to deploy

This pattern is composed from existing, previously-reviewed AVM Bicep modules using the
[`infra_composer_agent`](../../../tools/infra_composer_agent/) tool rather than being generated from
scratch. To generate a deployable project for this pattern:

```bash
python tools/infra_composer_agent/agent.py \
  --tech-pattern realtime-alerts \
  --prompt "<describe your specific solution name/naming convention and any resources to add or remove>" \
  --target-repo <your-target-repo-url> \
  --validate
```

The agent will show you the resource list above (plus anything else it infers from your prompt) and
let you add or remove resources interactively before generating `main.bicep`, copying the required
modules, and committing them to a new branch in the target repo.

> This README was generated automatically as placeholder documentation for the `realtime-alerts` technical
> pattern. Regenerate it any time with
> `python tools/infra_composer_agent/generate_pattern_readmes.py`.
