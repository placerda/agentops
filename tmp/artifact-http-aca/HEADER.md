# Scenario: http-aca (HTTP agent with tool calling)

**Target:** A *real* Microsoft Agent Framework chat agent
(`agent_framework.Agent` + `OpenAIChatCompletionClient` against Azure
OpenAI `gpt-4o-mini`) deployed as an Azure Container App per workflow run by
`infra/e2e/perrun.bicep` at `https://aca-agent-run25054470832.niceriver-6fd14a29.eastus2.azurecontainerapps.io`.

**What it does:** The agent (see `infra/e2e/agent-app/app.py`) is a small
FastAPI service that exposes `POST /` accepting `{"message": "..."}`
and returning `{"text": "...", "tool_calls": [...]}`. The agent is
configured with one function tool, `get_weather(location)`, and these
instructions:

> *You are a concise factual assistant. When the user asks about the
> weather in a location, you MUST call the `get_weather` tool with that
> location instead of guessing. After the tool returns, summarize the
> weather for the user in one short sentence...*

Each POST is a single AgentOps invocation, but **inside** the agent
there are multiple internal turns: the model picks the tool, the
framework executes it locally, the model observes the canned tool
result, and produces a final natural-language answer. AgentOps captures
the structured tool calls (via `tool_calls_field: tool_calls`) for
`tool_call_accuracy` while the quality evaluators grade the final text.

The container authenticates to Azure OpenAI via a User-Assigned Managed
Identity (no API keys) granted `Cognitive Services OpenAI User` on the
shared AI Services account.

**Why this scenario exists:** It exercises AgentOps' `http-json`
invocation path *plus* tool-call evaluation against a freshly-deployed
Azure resource the workflow itself owns end to end (image built
server-side via `az acr build`, deployed via Bicep, pulled with managed
identity, torn down by the teardown job).

**Dataset:** `scripts/e2e_data/tools.jsonl` (3 weather questions across Paris, Tokyo,
São Paulo, each with the expected `get_weather` tool call).

**Evaluators (auto-inferred from dataset shape):** `tool_call_accuracy`,
`coherence`, `fluency`, `f1_score`, plus `avg_latency_seconds`.
Thresholds are intentionally permissive (`>=0`) because the goal is to
validate connectivity and the eval pipeline, not to gate on `gpt-4o-mini`
quality.
