# Quickstart: Foundry Prompt Agent

Use this quickstart when you want a Foundry-managed prompt agent referenced as
`name:version`. The example creates a small **Travel Agent** in Foundry and then
uses AgentOps to add repo-side readiness, CI gates, Doctor, release evidence,
and Cockpit.

This path validates the Foundry-native route:

- Foundry owns the prompt agent runtime and official AI Agent Evaluation.
- AgentOps owns repo-side readiness: `agentops.yaml`, CI gates, Doctor,
  release evidence, and Cockpit.

## Journey you will exercise

| Step | Main tool | What you do | AgentOps role |
|---|---|---|---|
| Create the agent | Foundry portal, Foundry SDK, Foundry Toolkit, or `microsoft-foundry` skill | Create and publish `travel-agent`. | No ownership; AgentOps consumes the published target. |
| Try and debug | Foundry playground, VS Code, Copilot Chat | Validate behavior before adding release gates. | Optional quick eval later. |
| Evaluate in CI | Official Microsoft AI Agent Evaluation | Run Foundry-native evaluation for `travel-agent:<version>`. | Generates routing and records evidence. |
| Review readiness | AgentOps Doctor and Cockpit | Check CI, eval, telemetry, evidence, and links. | Primary owner of repo-side release proof. |

## 1. Create the Travel Agent in Foundry

Create a prompt agent first. AgentOps starts after the agent exists.

1. Open the [Azure AI Foundry portal](https://ai.azure.com) and select your
   project.
2. Go to the agents area and create a new prompt-based agent.
3. Use these values:

   | Field | Value |
   |---|---|
   | Name | `travel-agent` |
   | Model deployment | `gpt-4o-mini` or another chat-capable deployment in the project |
   | Description | Helps plan short trips and explains tradeoffs. |

4. Paste these instructions:

   ```text
   You are Travel Agent, a concise travel planning assistant.

   Help users plan short leisure trips. Always include:
   - a short summary;
   - a day-by-day plan when the user asks for an itinerary;
   - practical notes about budget, transit, weather, or booking constraints;
   - a reminder that you cannot make live reservations or purchases.

   Ask one clarifying question only when the destination, duration, or traveler
   preference is missing. Do not invent booking confirmations, prices, or
   availability.
   ```

5. Save and publish the agent.
6. Copy the published reference. The rest of this tutorial assumes
   `travel-agent:1`; if Foundry shows a different version, use that exact
   `name:version` value instead.

Test it in the Foundry playground with:

```text
Plan a 3-day first-time trip to Lisbon for a couple who likes food and history.
```

## 2. Create a clean workspace and install AgentOps

```powershell
mkdir agentops-prompt-quickstart
cd agentops-prompt-quickstart
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install "agentops-toolkit[foundry,agent]"
agentops --version
```

If you need the latest unreleased changes from the repository instead of the
published package, use:

```powershell
python -m pip install "agentops-toolkit[foundry,agent] @ git+https://github.com/Azure/agentops.git@main"
```

## 3. Create the travel eval dataset

Create a small JSONL dataset that matches the Travel Agent behavior.

```powershell
New-Item -ItemType Directory -Force .agentops\data | Out-Null
@'
{"input":"Plan a 3-day first-time trip to Lisbon for a couple who likes food and history.","expected":"A concise 3-day Lisbon itinerary with food, history, neighborhoods such as Baixa, Alfama, and Belem, practical notes, and no claim to make live bookings."}
{"input":"Suggest a low-budget weekend in Seattle for a solo traveler who likes coffee and museums.","expected":"A practical weekend Seattle plan with low-budget choices, coffee and museum suggestions, transit or weather notes, and no claim to make live bookings."}
{"input":"I want to visit Tokyo for 5 days with two kids. What should we do?","expected":"A family-friendly 5-day Tokyo itinerary with kid-appropriate activities, transit and pacing notes, and no claim to make live bookings."}
'@ | Set-Content -Encoding utf8 .agentops\data\travel-smoke.jsonl
```

## 4. Sign in and capture Foundry values

```powershell
az login
```

You need:

| Value | Example |
|---|---|
| Foundry project endpoint | `https://<resource>.services.ai.azure.com/api/projects/<project>` |
| Prompt agent reference | `travel-agent:1` or the version Foundry published |
| Application Insights connection string | optional, but recommended |

You do not need to set an evaluator deployment before initialization.
`agentops init` collects the workspace values. The evaluator deployment is a
CI/local-eval setting you add later when a runner needs a judge model.

## 5. Initialize AgentOps interactively

```powershell
agentops init
```

Answer the prompts as the wizard asks them:

| Prompt | Answer |
|---|---|
| Foundry project endpoint | `https://<resource>.services.ai.azure.com/api/projects/<project>` |
| Agent | `travel-agent:1`, or the exact published version from Foundry |
| Dataset path | `.agentops/data/travel-smoke.jsonl` |
| Application Insights connection string | Paste it if you have one, or press Enter to let AgentOps auto-discover/leave it blank |

The interactive path is intentional: you see what each value means, and each
answer is saved as soon as it validates. If you want an azd environment name
other than the default `dev`, run `agentops init --azd-env <name>`.

This creates:

```text
agentops.yaml
.agentops/
.azure/dev/.env
.github/skills/
```

`agentops.yaml` should stay small:

```yaml
version: 1
agent: travel-agent:1
dataset: .agentops/data/travel-smoke.jsonl
```

The Foundry project endpoint and App Insights connection string live in
`.azure/dev/.env`, not in source control.

## 6. Check the selected eval runner

```powershell
agentops workflow analyze --format text
```

For `agent: name:version`, AgentOps should recommend:

```text
recommended_eval_runner: official-ai-agent-evaluation
```

That means generated CI uses the official Microsoft AI Agent Evaluation runner
for the eval step, then uses AgentOps to collect evidence and readiness signals.

## 7. Generate the PR gate

```powershell
agentops workflow generate --kinds pr,watchdog --force
```

Before you run the generated workflow in GitHub Actions or Azure Pipelines, set
the evaluator deployment as a CI variable:

```text
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
```

That variable is not an `agentops init` answer. It tells the official eval
runner which model deployment should judge responses.

The PR workflow should contain the official eval action:

```text
microsoft/ai-agent-evals@v3-beta
```

It also records:

```text
.agentops/official-eval/metadata.json
.agentops/official-eval/result.json
.agentops/release/latest/evidence.md
```

## 8. Force a prompt regression, then fix it

This step makes the quickstart more than a happy path. You will intentionally
ship a worse prompt, watch the eval gate or metrics move, then recover.

1. In Foundry, edit the `travel-agent` instructions to this intentionally bad
   version:

   ```text
   Answer travel questions in one vague sentence. Do not include day-by-day
   plans, practical notes, constraints, or booking caveats.
   ```

2. Publish it as the next version, for example `travel-agent:2`.
3. Re-run the wizard and update only the agent value:

   ```powershell
   agentops init --reconfigure
   ```

   Keep the same endpoint and dataset, but answer `Agent` with the regressed
   version such as `travel-agent:2`.
4. Run the PR workflow, or run the official eval step from your pipeline branch.
   In Foundry Evaluations and the workflow summary, compare the new run with the
   previous `travel-agent:1` run. The regressed prompt should lose quality
   because it no longer satisfies the dataset expectations.
5. Restore the original Travel Agent instructions from step 1, publish again
   as the next version, for example `travel-agent:3`.
6. Re-run `agentops init --reconfigure`, set `Agent` to the fixed version, and
   run the pipeline again.

The learning loop is the point: Foundry owns prompt versioning and the managed
evaluation run; AgentOps keeps the repo pointed at the exact version under
review and records the evidence for the release discussion.

## 9. Run Doctor and create release evidence locally

```powershell
agentops doctor --workspace . --evidence-pack
code .agentops\agent\report.md
code .agentops\release\latest\evidence.md
```

Open both files. The Doctor report explains what is ready and what is missing;
the evidence pack is the reviewer-friendly summary. In a fresh quickstart it is
normal to see warnings for production telemetry, scheduled CI, or trace
regression history. Those warnings are useful because they show the difference
between "the eval ran once" and "this agent has enough release evidence."

Doctor is read-only. It does not create Foundry resources or run red-team scans.
It checks whether the repo has the signals a release reviewer needs: eval gates,
telemetry wiring, CI, trace-regression readiness, and links back to Foundry
where Foundry owns the runtime view.

## 10. Open Cockpit

```powershell
agentops cockpit --workspace .
```

Open the local URL printed by the command. The Cockpit should show Foundry
connection, official eval readiness, Doctor findings, release evidence, CI/CD,
and next actions.

## Success criteria

You are done when:

- The Travel Agent exists in Foundry and has a published `travel-agent:<version>` reference.
- `agentops workflow analyze` selects `official-ai-agent-evaluation`.
- `agentops workflow generate` creates a PR workflow with
  `microsoft/ai-agent-evals@v3-beta`.
- You published a deliberately regressed prompt version, saw the eval/pipeline
  signal move, restored the prompt, and reran the gate.
- `agentops doctor --evidence-pack` writes
  `.agentops/release/latest/evidence.md`.
- Cockpit opens and links the repo-side readiness view back to Foundry.
