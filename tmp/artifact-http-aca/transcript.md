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

---

## Target

| Field | Value |
|---|---|
| `kind` | `http_json` |
| `raw` | `https://aca-agent-run25054470832.niceriver-6fd14a29.eastus2.azurecontainerapps.io` |
| `protocol` | `http-json` |
| `name` | `None` |
| `version` | `None` |
| `url` | `https://aca-agent-run25054470832.niceriver-6fd14a29.eastus2.azurecontainerapps.io` |
| `deployment` | `None` |

## Per-row transcript

### Row 1

**Input**

```
What's the weather in Paris, France?
```

**Expected**

```
Calls get_weather with location='Paris, France'.
```

**Response**

```
The weather in Paris, France is currently 72°F (22°C) and partly cloudy.
```

**Tool calls**

```json
[
  {
    "type": "function_call",
    "name": "get_weather",
    "arguments": {
      "location": "Paris, France"
    }
  }
]
```

**Latency:** `3.752s`

**Metrics**

| Metric | Value |
|---|---|
| `coherence` | 4.0000 |
| `fluency` | 3.0000 |
| `similarity` | 1.0000 |
| `f1_score` | 0.1250 |
| `tool_call_accuracy` | 5.0000 |
| `intent_resolution` | 5.0000 |
| `task_adherence` | 1.0000 |
| `avg_latency_seconds` | 3.7524 |

### Row 2

**Input**

```
How is the weather right now in Tokyo, Japan?
```

**Expected**

```
Calls get_weather with location='Tokyo, Japan'.
```

**Response**

```
The weather in Tokyo, Japan, is currently 72°F (22°C) and partly cloudy.
```

**Tool calls**

```json
[
  {
    "type": "function_call",
    "name": "get_weather",
    "arguments": {
      "location": "Tokyo, Japan"
    }
  }
]
```

**Latency:** `1.798s`

**Metrics**

| Metric | Value |
|---|---|
| `coherence` | 4.0000 |
| `fluency` | 3.0000 |
| `similarity` | 1.0000 |
| `f1_score` | 0.1250 |
| `tool_call_accuracy` | 5.0000 |
| `intent_resolution` | 5.0000 |
| `task_adherence` | 1.0000 |
| `avg_latency_seconds` | 1.7982 |

### Row 3

**Input**

```
Tell me the current weather in Sao Paulo, Brazil.
```

**Expected**

```
Calls get_weather with location='Sao Paulo, Brazil'.
```

**Response**

```
The current weather in Sao Paulo, Brazil is 72°F (22°C) and partly cloudy with light winds.
```

**Tool calls**

```json
[
  {
    "type": "function_call",
    "name": "get_weather",
    "arguments": {
      "location": "Sao Paulo, Brazil"
    }
  }
]
```

**Latency:** `1.559s`

**Metrics**

| Metric | Value |
|---|---|
| `coherence` | 4.0000 |
| `fluency` | 3.0000 |
| `similarity` | 1.0000 |
| `f1_score` | 0.2857 |
| `tool_call_accuracy` | 5.0000 |
| `intent_resolution` | 5.0000 |
| `task_adherence` | 1.0000 |
| `avg_latency_seconds` | 1.5594 |

---

## Aggregate metrics

| Metric | Value |
|---|---|
| `avg_latency_seconds` | 2.3700 |
| `coherence` | 4.0000 |
| `f1_score` | 0.1786 |
| `fluency` | 3.0000 |
| `intent_resolution` | 5.0000 |
| `similarity` | 1.0000 |
| `task_adherence` | 1.0000 |
| `tool_call_accuracy` | 5.0000 |

## Thresholds

| Result | Metric | Criteria | Expected | Actual |
|---|---|---|---|---|
| ✅ PASS | `coherence` | `>=` | `>=0` | `4` |
| ✅ PASS | `fluency` | `>=` | `>=0` | `3` |
| ❌ FAIL | `similarity` | `>=` | `>=3` | `1` |
| ✅ PASS | `f1_score` | `>=` | `>=0` | `0.178571` |
| ✅ PASS | `tool_call_accuracy` | `>=` | `>=0` | `5` |
| ✅ PASS | `intent_resolution` | `>=` | `>=3` | `5` |
| ❌ FAIL | `task_adherence` | `>=` | `>=3` | `1` |
| ✅ PASS | `avg_latency_seconds` | `<=` | `<=60` | `2.36998` |

---

## Verdict: ❌ FAIL

- **Items:** 3/3 passed (100.00%)
- **Thresholds:** 6/8 passed (75.00%)
