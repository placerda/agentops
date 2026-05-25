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
| Evaluator model deployment | `gpt-4o-mini` |
| Application Insights connection string | optional, but recommended |

Set the deployment used by evaluators:

```powershell
$env:AZURE_OPENAI_DEPLOYMENT = "gpt-4o-mini"
```

## 5. Initialize AgentOps

```powershell
agentops init `
  --dir . `
  --azd-env dev `
  --project-endpoint "https://<resource>.services.ai.azure.com/api/projects/<project>" `
  --agent "travel-agent:1" `
  --dataset ".agentops/data/travel-smoke.jsonl" `
  --no-prompt
```

If your published agent version is not `1`, replace `travel-agent:1` with the
exact value from Foundry.

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
project_endpoint: https://<resource>.services.ai.azure.com/api/projects/<project>
```

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

## 8. Run Doctor and create release evidence locally

```powershell
agentops doctor --workspace . --evidence-pack
code .agentops/release/latest/evidence.md
```

Doctor is read-only. It checks whether the repo has the signals a release
reviewer needs: eval gates, telemetry wiring, CI, trace-regression readiness,
and links back to Foundry where Foundry owns the runtime view.

## 9. Open Cockpit

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
- `agentops doctor --evidence-pack` writes
  `.agentops/release/latest/evidence.md`.
- Cockpit opens and links the repo-side readiness view back to Foundry.
