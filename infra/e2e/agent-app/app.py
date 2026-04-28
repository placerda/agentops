"""AgentOps E2E hello-agent.

A minimal Microsoft Agent Framework chat agent exposed over HTTP so the
``http-aca`` AgentOps scenario can exercise the http-json invocation path
against a real LLM (not just an echo).

Endpoints:
    GET  /        -> health check (``{"ok": true, "agent": "..."}``)
    POST /        -> chat        (``{"message": "..."}`` -> ``{"text": "..."}``)

Auth:
    Azure OpenAI is reached via Microsoft Entra ID using
    ``DefaultAzureCredential``. In Azure Container Apps this resolves to the
    container's managed identity, which must be granted ``Cognitive Services
    OpenAI User`` on the AI Services / Foundry account. Locally, fall back to
    ``az login`` or environment variables.

Required environment:
    AZURE_OPENAI_ENDPOINT      e.g. https://<account>.openai.azure.com/ or
                               https://<account>.cognitiveservices.azure.com/
    AZURE_OPENAI_DEPLOYMENT    deployment name, e.g. ``gpt-4o-mini``

Optional:
    AZURE_CLIENT_ID            user-assigned managed identity client id
                               (DefaultAzureCredential picks it up
                               automatically when set).
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("hello-agent")

INSTRUCTIONS = (
    "You are a concise factual assistant. "
    "Answer the user's question in one short sentence. "
    "Do not add caveats, disclaimers, or follow-up questions."
)

_agent = None
_credential = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the agent once at startup, close credential at shutdown."""
    global _agent, _credential
    # Lazy import so the container starts even if env vars are missing —
    # health check will still work and the failure surfaces on POST.
    from agent_framework import Agent
    from agent_framework.openai import OpenAIChatCompletionClient
    from azure.identity.aio import DefaultAzureCredential

    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")

    if not endpoint or not deployment:
        log.warning(
            "AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_DEPLOYMENT not set — agent "
            "will return 503 on POST until configured."
        )
        yield
        return

    _credential = DefaultAzureCredential()
    _agent = Agent(
        client=OpenAIChatCompletionClient(
            model=deployment,
            azure_endpoint=endpoint,
            credential=_credential,
        ),
        instructions=INSTRUCTIONS,
    )
    log.info("Agent initialized (endpoint=%s, deployment=%s)", endpoint, deployment)
    try:
        yield
    finally:
        if _credential is not None:
            await _credential.close()


app = FastAPI(title="agentops-e2e-hello-agent", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str


@app.get("/")
async def root():
    return {
        "ok": True,
        "agent": "agentops-e2e-hello-agent",
        "ready": _agent is not None,
    }


@app.post("/")
async def chat(req: ChatRequest):
    if _agent is None:
        raise HTTPException(
            status_code=503,
            detail="agent not initialized; check AZURE_OPENAI_ENDPOINT/DEPLOYMENT and managed identity role",
        )
    try:
        result = await _agent.run(req.message)
    except Exception as exc:  # noqa: BLE001 — surface real error to caller
        log.exception("agent.run failed")
        raise HTTPException(status_code=500, detail=f"agent.run failed: {exc}") from exc

    text: Optional[str] = None
    # AgentRunResponse exposes the final text via __str__; fall back to attrs.
    for attr in ("text", "content", "message"):
        value = getattr(result, attr, None)
        if isinstance(value, str) and value.strip():
            text = value
            break
    if text is None:
        text = str(result)
    return {"text": text}
