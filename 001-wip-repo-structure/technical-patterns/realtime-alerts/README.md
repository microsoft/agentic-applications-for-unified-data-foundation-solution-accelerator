# Real-Time Alerts

A streaming telemetry pipeline that ingests high-volume events, evaluates them for conditions of interest, and raises alerts/dashboards in near real time.

## What this pattern does

Telemetry/events stream into an Event Hub, which a Function App consumes to evaluate alerting rules and write raw/aggregated results to a Storage Account and Cosmos DB (NoSQL) for alert-state tracking. Configuration for alerting thresholds lives in App Configuration. When a condition fires, an Event Grid topic publishes an alert event for downstream routing. Operational dashboards and workbooks in Log Analytics/Application Insights give on-call teams live visibility, a portal dashboard summarizes system health, and every service-to-service call uses a managed identity with least-privilege RBAC role assignments.

## Resources deployed

> This table is read directly by `infra_composer_agent` (see `tech_patterns.get_pattern_resources()`)
> to build its resource plan -- edit it here and the agent will pick up your changes on its next run.
> The `Module` column must match an exact module key from the source module library
> (`infra_new/avm/modules/<category>/<name>.bicep` on the `infra-core-modules-copy` branch).

| Resource | Module | Purpose |
|---|---|---|
| Event Hub | `data/event-hub.bicep` | Telemetry ingestion |
| Function App | `compute/function-app.bicep` | Stream processing / rule evaluation |
| Storage Account | `data/storage-account.bicep` | Raw/aggregated event data |
| Cosmos DB (NoSQL) | `data/cosmos-db-nosql.bicep` | Alert state |
| App Configuration | `data/app-configuration.bicep` | Alerting thresholds |
| Event Grid | `data/event-grid.bicep` | Alert fan-out |
| Key Vault | `security/key-vault.bicep` | Secrets and certificates |
| Managed Identity | `identity/managed-identity.bicep` | Identity for service-to-service auth |
| Role Assignments | `identity/role-assignments.bicep` | Least-privilege RBAC for the identity |
| Log Analytics Workspace | `monitoring/log-analytics.bicep` | Central log sink |
| Application Insights | `monitoring/app-insights.bicep` | Function/app telemetry |
| Data Collection Rule | `monitoring/data-collection-rule.bicep` | Routes telemetry into Log Analytics |
| Workbook | `monitoring/workbook.bicep` | Operational dashboards |
| Portal Dashboard | `monitoring/portal-dashboard.bicep` | System-health summary |
| Virtual Network | `networking/virtual-network.bicep` | Network isolation boundary |
| Private Endpoint | `networking/private-endpoint.bicep` | Private connectivity to data services |
| Private DNS Zone | `networking/private-dns-zone.bicep` | DNS resolution for private endpoints |

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

The agent will first show you the resource table above (re-read live from this file) and ask you to
confirm before pulling any module from the source library or generating anything -- you can still add
or remove resources at that point.

> This README was generated automatically as placeholder documentation for the `realtime-alerts` technical
> pattern. Regenerate it any time with
> `python tools/infra_composer_agent/generate_pattern_readmes.py`.
