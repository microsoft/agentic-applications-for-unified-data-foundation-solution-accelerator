# ado-cicd-post-deploy

Generates the **Azure DevOps stage** that runs a solution's **post-deployment steps and tests**
after the infrastructure is provisioned. The `ado-cicd-bicep-workflows` and
`ado-cicd-terraform-workflows` deploy pipelines reference this stage between their Provision and
Cleanup stages.

The stage reads the solution's configuration back **from the provisioned resource group via `az`**
(the deployment outputs), hydrates an azd environment, runs the discovered post-provision/
post-deploy scripts, then runs the unit and Playwright tests that are present. It never edits the
repo's infra, application, or post-provision sources — only the pipeline YAML is authored. The
resource group is torn down by the deploy pipeline's Cleanup stage.

## Files

```
ado-cicd-post-deploy/
├── SKILL.md
├── README.md
├── scripts/
│   ├── check-prereqs.sh          # jq/git/grep/find required; az/azd recommended
│   ├── inspect-post-deploy.sh    # discover azd hooks, guides, ordered post-deploy plan
│   ├── discover-tests.sh         # discover unit (frontend/pytest/dotnet) + Playwright tests
│   └── validate-pipelines.sh     # offline YAML + placeholder + template-ref checks
├── templates/
│   └── azure-pipelines-post-deploy.yml   # reusable STAGE template: PostDeployTest
└── references/
    └── post-deploy-conventions.md
```

## Quick start (for the agent)

1. `bash scripts/check-prereqs.sh`
2. `bash scripts/inspect-post-deploy.sh <repo_root> > .agent/tmp/post-deploy-facts.json`
3. `bash scripts/discover-tests.sh <repo_root> > .agent/tmp/test-facts.json`
4. Read every path in `guides`; confirm with the user which steps CI runs and which are manual.
5. Get approval, render `azure-pipelines-post-deploy.yml` next to the infra deploy pipeline:
   fill `__POST_DEPLOY_STEPS__` / `__MANUAL_POST_STEPS__` / Python + test placeholders; keep only
   the test jobs whose category is present; fix the `playwright` job's `dependsOn`.
6. `bash scripts/validate-pipelines.sh <rendered file>`
7. Remove `.agent/tmp/`.

## What the stage does

`PostDeployTest` (the Cleanup stage depends on this name):

- **`post_deploy`** — reads the latest succeeded ARM deployment's outputs from the resource group,
  hydrates the azd env + a repo-root `.env`, then runs the discovered post-deploy scripts in order.
- **`unit_frontend`** / **`unit_backend_pytest`** / **`unit_backend_dotnet`** — rendered only when
  `discover-tests.sh` finds them.
- **`playwright`** — end-to-end tests, rendered only when present (python **or** node variant).

Cleanup (delete the resource group) is **not** in this stage — the infra deploy pipeline's Cleanup
stage does it with `condition: always()`, so tests run against live infrastructure and it is always
torn down afterward.

## How a repo is read (no solution-specific content)

- **`inspect-post-deploy.sh`** reads `azure.yaml` `hooks:` (POSIX variant, since CI is Linux),
  classifies each hook `executes` vs `prints_only`, merges guide-referenced scripts, and emits an
  ordered `post_deploy_plan` deduped by filename stem, with toolchain needs and an
  interactive-prompt flag.
- **`discover-tests.sh`** reports `unit_frontend` (package.json `test` script), `unit_backend`
  (pytest + dotnet test projects), and `playwright` (config or Python Playwright usage), with
  directories.
- **The main `README.md` is the front door.** Read it first and follow its links to whatever
  deployment doc it redirects to; from there capture the **application-deploy** step (build+push the
  image, deploy the app) in addition to the configuration scripts, so Playwright/e2e has a live app.
  It is detected by the commands it runs — never a hardcoded target/filename — and run in CI when it
  has an unattended command, or surfaced as a reminder when it depends on live infra state.

See `references/post-deploy-conventions.md` for the discovery contract, the resource-group →
azd-env hydration bridge, the CI-vs-manual classification rules, and the render mapping.

## Prerequisites

The infra deploy pipeline (from `ado-cicd-bicep-workflows` / `ado-cicd-terraform-workflows`)
provides the Azure Resource Manager **service connection** and **variable group**, and references
this stage between Provision and Cleanup. Any value a script needs that is **not** a deployment
output (e.g. a secret minted by a `preprovision` hook) must be supplied as a variable or handled
manually — surfaced by discovery, not synthesized by the skill.
