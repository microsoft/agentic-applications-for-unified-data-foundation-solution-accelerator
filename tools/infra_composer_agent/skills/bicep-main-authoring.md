# Skill: Authoring `main.bicep` orchestrators (Azure Bicep)

This is a distilled rule set extracted directly from this repository's real, hand-authored
orchestrator: [`infra/bicep/main.bicep`](../../../infra/bicep/main.bicep). It is the authoritative
style guide the `infra_composer_agent`'s LLM author agent must follow when generating a new
`main.bicep` for any composed project. Every rule below is backed by a concrete example copied
verbatim (or near-verbatim) from that file so nothing here is speculative.

If a generation request needs a convention not covered here, DO NOT invent one silently -- flag it
in the run log as an open question instead of guessing.

## 1. File shape: pure orchestrator, nothing else

- `targetScope = 'resourceGroup'` is the first non-comment line (unless the composition is
  explicitly subscription-scoped -- see Section 8).
- The file only contains: a header comment, `param` declarations, `var` declarations, one resource
  block that tags the resource group (Section 4), `module` blocks, and `output` declarations.
- No inline resource (`resource ... = {...}`) definitions for actual infrastructure -- every real
  resource is deployed through a `module` block that references a local `.bicep` file under
  `./modules/`. The only inline `resource` allowed is the resource-group tag-merge resource
  (Section 4).
- Open with a header comment block:
  ```bicep
  // ============================================================================
  // main.bicep — Orchestrator
  // Description: Pure orchestrator for <solution>.
  //              All resource names are derived from params — no hardcoded names.
  //              This file only calls modules; no inline resource definitions.
  // ============================================================================
  ```

## 2. Parameters

- Group parameters under `// === Parameters — <Section> ===` comment headers (e.g. Core, AI
  Configuration, Compute, Feature Flags, Existing Resources, Identity, App Configuration) --
  don't declare a flat, ungrouped list.
- **Every** `param` has an `@description('Required. ...')` or `@description('Optional. ...')`
  decorator, starting with exactly the word `Required.` or `Optional.` (matching how AVM modules
  document parameters).
- Core params always present:
  ```bicep
  @minLength(3)
  @maxLength(20)
  @description('Optional. A unique application/solution name for all resources in this deployment.')
  param solutionName string = '<shortDefaultName>'

  @maxLength(5)
  @description('Optional. A unique text suffix appended to resource names for uniqueness.')
  param solutionUniqueText string = substring(uniqueString(subscription().id, resourceGroup().name, solutionName), 0, 5)

  @description('Optional. Primary Azure region for resource deployment. Defaults to resource group location.')
  param location string = resourceGroup().location

  @description('Optional. Tags to apply to all resources.')
  param tags object = {}
  ```
- Use `@allowed([...])` for any parameter with a fixed, known set of valid values (SKUs, runtime
  stacks, principal types, deployment types) -- never leave an enum-like parameter as a bare
  `string` with no `@allowed`.
- Use `@minValue`/`@minLength`/`@maxLength` wherever the underlying Azure resource actually
  enforces a bound (e.g. capacity `@minValue(10)`, name length limits).
- A parameter representing an existing resource (opt-out-of-creating-a-new-one pattern) defaults to
  `''` (empty string) -- see Section 7.
- A region/location parameter that drives AI model deployment availability uses `@allowed([...])`
  restricted to regions known to support the required models, plus an `@metadata({ azd: { type:
  'location', usageName: [...] } })` block if this project is meant to be `azd`-deployable.
- Feature-flag parameters are plain `bool` with a sensible default (`true`/`false` depending on
  whether the feature should be on by default) and a one-line `@description`.

## 3. Variables

- Keep a single `// === Variables ===` section, after all parameters, before the resource-group
  tag resource.
- Sanitize `solutionName` into a safe suffix used for actual resource naming -- never pass the raw
  `solutionName` param straight into a module; always derive and pass a sanitized `var`:
  ```bicep
  var solutionSuffix = toLower(trim(replace(
    replace(
      replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''),
      ' ',
      ''
    ),
    '*',
    ''
  )))
  ```
- Use `deployer()` to capture who's deploying, for tagging and for default RBAC assignment to the
  deploying principal:
  ```bicep
  var deployerInfo = deployer()
  var deployingUserPrincipalId = deployerInfo.objectId
  var createdBy = contains(deployerInfo, 'userPrincipalName') ? split(deployerInfo.userPrincipalName, '@')[0] : deployerInfo.objectId
  ```
- Merge existing resource-group tags with caller-supplied tags and standard metadata, don't
  overwrite either:
  ```bicep
  var existingTags = resourceGroup().tags ?? {}
  var resourceTags = union(existingTags, tags, {
    TemplateName: '<Solution Display Name>'
    CreatedBy: createdBy
    DeploymentName: deployment().name
    Type: 'Non-WAF'
  })
  ```
- Every "use existing resource vs. create new" parameter gets a paired `useExisting<Thing>` bool
  var derived from `!empty(<paramName>)`.
- Derive any per-deployment resource name that has extra naming constraints (e.g. ACR names:
  alphanumeric only, 5-50 chars) with `take('<prefix>${solutionSuffix}', <maxLen>)`, honoring an
  optional override parameter first (`!empty(overrideParam) ? overrideParam : take(...)`).

## 4. Resource-group tagging

Every orchestrator applies the merged tags back onto the resource group itself, as the only
non-module resource in the file:
```bicep
resource resourceGroupTags 'Microsoft.Resources/tags@2024-11-01' = {
  name: 'default'
  properties: {
    tags: resourceTags
  }
}
```

## 5. Module blocks

- One `module` block per logical resource, grouped under `// === Module: <Category> ===` comment
  headers matching the module's folder category (Monitoring, Data, Compute, AI, Identity, etc.).
- Deterministic, collision-safe module deployment name, always wrapped in `take(..., 64)` (ARM's
  deployment-name length limit):
  ```bicep
  module <symbolicName> './modules/<category>/<name>.bicep' = {
    name: take('module.<name>.${solutionName}', 64)
    params: { ... }
    scope: resourceGroup(resourceGroup().name)
  }
  ```
  Use the raw `${solutionName}` param (not `solutionSuffix`) inside the `name:` deployment-name
  string specifically -- that's what the real file does (deployment names tolerate the raw input;
  actual Azure resource names use `solutionSuffix`).
- Pass `solutionName: solutionSuffix` (the sanitized variable, NOT the raw param) as the module's
  own `solutionName` parameter.
- `scope: resourceGroup(resourceGroup().name)` is explicit on every module targeting the local
  resource group -- don't omit it even though it's the implicit default, except for a module that
  targets a genuinely different resource group/subscription (Section 8).
- Conditionally create a module with `if (<condition>)` only when there's a real reason to
  (existing-vs-new toggle, an opt-in feature flag) -- otherwise the module is unconditional.
- **Non-null assertion for conditional module outputs**: when a module was declared with an `if`
  condition, every reference to its `.outputs` MUST use the `!` non-null-assertion operator
  (`myModule!.outputs.foo`), because Bicep can't otherwise prove the module ran. Unconditional
  modules reference `.outputs` without `!`.
- For repeated instances of the same module (e.g. multiple model deployments), use a `for` loop
  over an array variable, with `@batchSize(1)` if the underlying resource type doesn't tolerate
  parallel creation:
  ```bicep
  @batchSize(1)
  module model_deployments './modules/ai/ai-foundry-model-deployment.bicep' = [for (item, i) in items: {
    name: take('module.model-deployment-${i}.${solutionName}', 64)
    params: { ... }
  }]
  ```

## 6. Parameter wiring between modules

- Wire a downstream module's parameter directly to an upstream module's output expression --
  never hardcode a value that another module already produces.
- Prefer ternary wiring for optional/conditional dependencies rather than duplicating module
  blocks: `workspaceResourceId: enableMonitoring ? logAnalytics!.outputs.resourceId : ''`.
- When a value can come from either an "existing resource" path or a "newly created" path, resolve
  it once into a `var` immediately after both branches are declared, then use that single `var`
  everywhere downstream -- don't repeat the ternary at every call site:
  ```bicep
  var aiFoundryEndpoint = useExistingAIProject ? existing_project_setup!.outputs.endpoint : ai_foundry_project!.outputs.endpoint
  ```

## 7. Existing-vs-new resource pattern

For any resource type the user might already have (Log Analytics workspace, AI Foundry project,
etc.):
- Add an `existing<Thing>ResourceId` (or `existing<Thing>Name`) string param, default `''`.
- Derive `useExisting<Thing> = !empty(existing<Thing>ResourceId)`.
- Guard the "create new" module with `if (!useExisting<Thing>)`.
- If runtime properties of the existing resource are needed (endpoints, identity principal ids),
  add a small dedicated "read-only setup" helper module (e.g. `existing-project-setup.bicep`)
  guarded by `if (useExisting<Thing>)`, scoped to the existing resource's own subscription/resource
  group (parsed out of its resource ID with `split(existingId, '/')[N]`).
- Resolve the final values used everywhere downstream into `var`s exactly as in Section 6.

## 8. Cross-scope modules

When a module must target a different subscription/resource group than the deployment's own
(e.g. writing a connection into an existing AI Foundry project that lives elsewhere), set an
explicit `scope: resourceGroup(<subscriptionId>, <resourceGroupName>)` on that module -- derive
those two values from the existing resource's ID via `split(...)`, same as Section 7.

## 9. Centralized role assignments

Do not scatter `Microsoft.Authorization/roleAssignments` resources across multiple modules. Create
exactly one `role-assignments` module call, fed every principal ID / resource ID it needs to grant
access to/from, e.g.:
```bicep
module role_assignments './modules/identity/role-assignments.bicep' = {
  name: take('module.role-assignments.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    <serviceX>ResourceId: <serviceXModule>.outputs.resourceId
    <serviceX>PrincipalId: <consumerModule>!.outputs.identityPrincipalId
    deployerPrincipalId: deployingUserPrincipalId
    deployerPrincipalType: deployingUserPrincipalType
  }
  scope: resourceGroup(resourceGroup().name)
}
```

## 10. Outputs

- One `// === Outputs ===`-style section at the end of the file (or grouped logically at the end),
  after every module block.
- Output names are `UPPER_SNAKE_CASE` (matching `azd`/env-var conventions), not camelCase.
- Every output has an `@description('...')` decorator.
- Output the identifying value(s) (`resourceId`, `name`, `endpoint`, connection string, etc.) of
  every module the user explicitly asked for -- prefer the most useful runtime value (an endpoint
  or connection identifier) over a bare resource ID when both exist.
- For a conditionally-created resource, the output expression itself carries the condition rather
  than the output being conditionally declared (Bicep outputs can't be conditional the way
  resources/modules can):
  ```bicep
  @description('The resource ID of the Fabric capacity.')
  output AZURE_FABRIC_CAPACITY_RESOURCE_ID string = createFabricWorkspace ? fabricCapacity!.outputs.resourceId : ''
  ```
- Stay under Bicep's 64-output linter limit (`max-outputs`) -- if the composition has many
  resources, output only the explicitly-requested modules' key values, not every auto-included
  dependency's outputs too.

## 11. General Bicep hygiene

- Never declare a custom/object `type` and then use its name directly as an `output`/`param` type
  position unless it's one of Bicep's actual primitive/generic types (`string`, `int`, `bool`,
  `array`, `object`, `resourceInput`, `resourceOutput`, `any`) -- a custom type name like
  `subnetOutputType` is not valid there and fails `BCP302`.
- Every module reference (`module ... = { ... }` path) must point at a file that actually exists
  under `./modules/` in the generated project -- never reference a module path that wasn't
  actually copied.
- Every parameter passed into a module must be one the module actually declares -- verify against
  the real parsed module list, don't guess a plausible-looking name.
- Prefer explicit, readable expressions over deeply nested ternaries; if wiring logic needs more
  than two levels of nesting, resolve intermediate values into named `var`s first (see Section 6).

---
This document is the single source of truth the LLM author agent (`llm_composer.py`) is instructed
to follow. Update it here first if a convention needs to change -- `llm_composer.py` loads this
file's content directly into its system prompt on every run (see `_load_skill()`), and
`update_agent_instructions.py` can push the same content into the persistent AI Foundry author
agent's stored `instructions` field so the agent "remembers" these rules across sessions too.
