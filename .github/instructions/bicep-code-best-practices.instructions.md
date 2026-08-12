---
description: 'Infrastructure as Code with Bicep -- applies repo-wide, to both human edits and the infra_composer_agent (tools/infra_composer_agent/skills/bicep-main-authoring.md is the authoritative, more detailed superset for that agent).'
applyTo: '**/*.bicep'
---

## Naming Conventions

- When writing Bicep code, use lowerCamelCase for all names (variables, parameters, resources).
- Use resource type descriptive symbolic names (e.g., 'storageAccount' not 'storageAccountName').
- Avoid using 'name' in a symbolic name as it represents the resource, not the resource's name.
- Avoid distinguishing variables and parameters by the use of suffixes.

## Structure and Declaration

- Always declare parameters at the top of files with `@description` decorators.
- Use latest stable API versions for all resources.
- Use descriptive `@description` decorators for all parameters (start with `Required.` or
  `Optional.`, per this repo's convention -- see bicep-main-authoring.md Section 2).
- Specify minimum and maximum character length for naming parameters where applicable.

## Parameters

- Set default values that are safe for test environments (use low-cost pricing tiers).
- Use `@allowed` decorator sparingly to avoid blocking valid deployments.
- Use parameters for settings that change between deployments -- never hardcode names, locations,
  or other configurable values.

## Variables

- Variables automatically infer type from the resolved value.
- Use variables to contain complex expressions instead of embedding them directly in resource
  properties.

## Resource References

- Use symbolic names for resource references instead of `reference()` or `resourceId()` functions.
- Create resource dependencies through symbolic names (`resourceA.id`) not explicit `dependsOn`.
- For accessing properties from other resources, use the `existing` keyword instead of passing
  values through outputs.

## Child Resources

- Avoid excessive nesting of child resources.
- Use the `parent` property or nesting instead of constructing resource names for child resources.

## Security

- Never include secrets or keys in outputs.
- Use resource properties directly in outputs (e.g., `storageAccount.properties.primaryEndpoints`).
- Always prefer managed identities + RBAC role assignments over static credentials, access keys,
  or connection strings (`listKeys()`, `listConnectionStrings()`, etc.) -- this is enforced as a
  hard, programmatic gate for agent-generated `main.bicep` files (see
  `tools/infra_composer_agent/bicep_validate.py`), and is the expected standard for hand-written
  Bicep in this repo too.

## Documentation

- Include helpful `//` comments within your Bicep files to improve readability.

## Module reuse

- Prefer composing existing modules under a project's own `infra/bicep/modules/` folder (or the
  Azure Verified Modules registry, `br/public:avm/...`) over duplicating resource definitions.
