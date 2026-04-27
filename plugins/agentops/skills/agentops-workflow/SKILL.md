---
name: agentops-workflow
description: Generate or update GitHub Actions workflows that run AgentOps evaluations on PRs and schedules. Trigger on "CI", "workflow", "pipeline", "GitHub Actions", "PR gate". Uses `agentops workflow generate` and the templates shipped with AgentOps.
---

# AgentOps Workflow

Wire AgentOps into CI so every PR gets evaluated automatically.

## Step 0 — Prerequisites

1. `pip install agentops-toolkit` if `agentops` is missing.
2. `agentops.yaml` exists at the project root and `agentops eval run`
   succeeds locally at least once.

## Step 1 — Generate the workflow

```bash
agentops workflow generate
```

Optional flags:

- `--force` — overwrite an existing workflow file.
- `--dir <path>` — write to a non-default directory.

This drops `.github/workflows/agentops-eval.yml` into the repository. It
runs `agentops eval run` on PRs and uploads `results.json` /
`report.md` as an artifact.

## Step 2 — Configure secrets

The workflow expects the following secrets (only the ones relevant to
your `agent:` value need to be set):

| Secret | Used for |
|---|---|
| `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET` | Foundry agent / model auth |
| `AZURE_AI_FOUNDRY_PROJECT_ENDPOINT` | Foundry project URL |
| Custom HTTP token vars (matching `auth_header_env` in `agentops.yaml`) | HTTP/JSON agents |

Add them under **Settings → Secrets and variables → Actions**.

## Step 3 — Gate on exit code

The workflow already fails the job when AgentOps returns exit code `2`
(thresholds failed) or `1` (runtime error). To require a passing
evaluation before merge:

1. **Settings → Branches → Branch protection rules**.
2. Require status checks to pass before merging.
3. Select the AgentOps job from the dropdown.

## Step 4 — Iterate

- To add scheduled runs, edit the workflow's `on:` block and add a
  `schedule:` entry.
- To publish each CI run to Foundry Evaluations, add `publish: foundry`
  in `agentops.yaml` and ensure `AZURE_AI_FOUNDRY_PROJECT_ENDPOINT` is
  set in Actions secrets.

## Guardrails

- Do not invent CLI flags. The supported commands are `agentops init`,
  `agentops eval run`, `agentops report generate`, `agentops workflow
  generate`, and `agentops skills install`.
- Do not duplicate workflows. Prefer editing the generated file over
  copy-pasting a parallel one.
