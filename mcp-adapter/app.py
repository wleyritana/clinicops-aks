import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# --------- Core config ---------


MCP_URL = os.getenv("MCP_URL")  # e.g. https://your-mcp-service.up.railway.app/orchestrate
if not MCP_URL:
    print(
        "[WARN] MCP_URL env var is not set. "
        "Set it in your environment (or Railway variables) before using the canonical endpoints."
    )

# --------- API key protection ---------
# You can configure:
#   - API_KEYS = "key1,key2,key3"
#   - or API_KEY = "single-key"

RAW_API_KEYS = os.getenv("API_KEYS") or os.getenv("API_KEY")
if not RAW_API_KEYS:
    raise RuntimeError(
        "API_KEYS or API_KEY environment variable must be set for API key protection. "
        "Set API_KEYS to a comma-separated list of allowed API keys, "
        "or API_KEY to a single key."
    )

API_KEYS = {k.strip() for k in RAW_API_KEYS.split(",") if k.strip()}


async def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> str:
    """
    Simple API key protection.

    - Expects the client to send:  X-API-Key: <key>
    - Compares it against the configured API_KEYS set.
    """
    if x_api_key is None:
        raise HTTPException(
            status_code=401,
            detail="Missing API key header 'X-API-Key'",
        )

    if x_api_key not in API_KEYS:
        # Do not leak which specific keys exist; just say it's invalid.
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
        )

    return x_api_key


# --------- App init ---------


app = FastAPI(title="MCP Python Adapter (Canonical JSON v1.1)")


# --------- Canonical models (v1.1, backward-compatible with v1.0) ---------


class CanonicalLLMContext(BaseModel):
    """Optional LLM-related hints that the adapter just passes through."""
    model_hint: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    # Free-form extras for future tuning knobs
    extra: Optional[Dict[str, Any]] = None


class CanonicalContext(BaseModel):
    channel: Optional[str] = "web"
    device: Optional[str] = None
    locale: Optional[str] = None
    tenant: Optional[str] = None
    client_app: Optional[str] = None
    # Optional nested LLM config, ignored by the adapter but useful for MCP/LLM layer
    llm: Optional[CanonicalLLMContext] = None


class CanonicalSession(BaseModel):
    session_id: str
    conversation_id: Optional[str] = None
    user_id: str
    turn: int = 0
    # In responses we may populate the resolved route (e.g. "food_ordering.menu")
    route: Optional[str] = None


class CanonicalObservability(BaseModel):
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    message_id: Optional[str] = None


class CanonicalRequest(BaseModel):
    """
    Generic request envelope that is multi-modal friendly.

    For v1.0 compatibility, most clients will send:
        { "type": "text", "text": "..." }

    Future-friendly fields (audio/image/event) are optional and can be
    introduced progressively without breaking older clients.
    """

    type: str = Field(
        default="text",
        description="Type of the request payload: text | audio | image | event | etc.",
    )

    # Text-based input (current primary usage)
    text: Optional[str] = None

    # Audio-specific fields (future)
    audio_url: Optional[str] = None
    transcript: Optional[str] = None  # e.g. STT result from ElevenLabs

    # Image-specific fields (future)
    image_url: Optional[str] = None
    alt_text: Optional[str] = None

    # Optional override for downstream routing / intent classification
    intent_override: Optional[str] = None

    # Free-form metadata from the adapter or client
    metadata: Optional[Dict[str, Any]] = None


class CanonicalError(BaseModel):
    type: str
    code: int
    message: str
    retryable: bool = False
    details: Optional[Dict[str, Any]] = None


class CanonicalResponseBody(BaseModel):
    status: Optional[str] = None  # "success" | "error"
    code: Optional[int] = None
    type: str = "text"
    text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CanonicalEnvelope(BaseModel):
    """
    Canonical envelope for inbound requests (v1.0 / v1.1).

    This is what adapters receive from channels and send into the MCP adapter.
    """

    version: str = "1.1"
    timestamp: Optional[datetime] = None
    context: CanonicalContext
    session: CanonicalSession
    request: CanonicalRequest
    observability: Optional[CanonicalObservability] = None


class CanonicalResponseEnvelope(BaseModel):
    """
    Canonical envelope for outbound responses.

    Mirrors CanonicalEnvelope but with `response` + optional `error`.
    """

    version: str = "1.1"
    timestamp: datetime
    context: CanonicalContext
    session: CanonicalSession
    response: CanonicalResponseBody
    error: Optional[CanonicalError] = None
    observability: CanonicalObservability


# --------- Helper: call MCP orchestrator ---------


async def call_mcp(
    text: str,
    user_id: str,
    channel: str,
    session_id: str,
    trace_id: Optional[str],
) -> Dict[str, Any]:
    """
    Calls the MCP /orchestrate endpoint with the minimal request body
    and returns the JSON.

    We keep this compatible with the existing MCP orchestrator implementation:
        {
            "text": "...",
            "user_id": "...",
            "channel": "...",
            "session_id": "..."
        }

    Additional observability fields can be added over time as the MCP side evolves.
    """
    if not MCP_URL:
        raise HTTPException(
            status_code=500,
            detail="MCP_URL is not configured on the adapter service",
        )

    payload: Dict[str, Any] = {
        "text": text,
        "user_id": user_id,
        "channel": channel,
        "session_id": session_id,
    }
    if trace_id:
        payload["trace_id"] = trace_id

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(MCP_URL, json=payload)

        if resp.status_code != 200:
            # Bubble up as an adapter-level error; the route handler will
            # convert this into a canonical error envelope.
            raise HTTPException(
                status_code=502,
                detail=f"MCP orchestrator error: {resp.status_code} {resp.text}",
            )

        return resp.json()

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Error communicating with MCP orchestrator: {exc}",
        ) from exc


# --------- Routes ---------


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "mcp_adapter_python",
        "mcp_url": MCP_URL,
    }


@app.post("/canonical/voice", dependencies=[Depends(require_api_key)])
@app.post("/canonical/message", dependencies=[Depends(require_api_key)])
async def canonical_message(envelope: CanonicalEnvelope) -> Dict[str, Any]:
    """
    Entry point for canonical JSON from any client / channel.

    Flow:
    - Validates the canonical structure
    - Ensures timestamp & observability defaults are set
    - Maps to MCP request (text-only for now)
    - Calls MCP /orchestrate
    - Wraps response in a canonical response envelope (v1.1)
    """
    start = time.perf_counter()

    # Ensure timestamp is set
    now_utc = datetime.now(timezone.utc)
    if not envelope.timestamp:
        envelope.timestamp = now_utc

    # Ensure observability object exists and has at least a trace_id and message_id
    if envelope.observability is None:
        envelope.observability = CanonicalObservability()

    if not envelope.observability.trace_id:
        envelope.observability.trace_id = f"trace-{uuid.uuid4().hex}"

    if not envelope.observability.message_id:
        envelope.observability.message_id = f"msg-{uuid.uuid4().hex}"

    trace_id = envelope.observability.trace_id

    # Determine the effective text to send to MCP
    req = envelope.request
    effective_text: Optional[str] = None

    if req.type == "text":
        effective_text = req.text
    elif req.type == "audio":
        # For now, we rely on upstream STT providing a transcript.
        # In the future you can plug in your own STT here.
        effective_text = req.transcript or req.text
    else:
        # For now we only support text/audio -> text semantics.
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported request.type '{req.type}' for this adapter. "
            "Currently supported types: text, audio.",
        )

    if not effective_text:
        raise HTTPException(
            status_code=400,
            detail="No text content available to send to MCP (empty text/transcript).",
        )

    # Extract fields for MCP call
    user_id = envelope.session.user_id
    session_id = envelope.session.session_id
    channel = envelope.context.channel or "web"

    # Call MCP orchestrator and capture potential HTTPException for error mapping
    mcp_reply: Dict[str, Any]
    error_obj: Optional[CanonicalError] = None

    try:
        mcp_reply = await call_mcp(
            text=effective_text,
            user_id=user_id,
            channel=channel,
            session_id=session_id,
            trace_id=trace_id,
        )
    except HTTPException as exc:
        # Build canonical error structure
        error_obj = CanonicalError(
            type="MCP_ORCHESTRATOR_ERROR",
            code=exc.status_code,
            message=str(exc.detail),
            retryable=False,
            details={"mcp_url": MCP_URL},
        )
        mcp_reply = {}

    duration_ms = (time.perf_counter() - start) * 1000.0

    # Build response/session data from MCP reply (if any)
    route = mcp_reply.get("route") if isinstance(mcp_reply, dict) else None
    reply_text = None

    if mcp_reply:
        # Your orchestrator today typically returns:
        # {
        #   "decision": "reply",
        #   "reply_text": "...",
        #   "session_id": "...",
        #   "route": "menu"
        # }
        reply_text = mcp_reply.get("reply_text") or mcp_reply.get("text")

        # Optionally update session_id if MCP decides to override
        new_session_id = mcp_reply.get("session_id")
        if isinstance(new_session_id, str) and new_session_id.strip():
            envelope.session.session_id = new_session_id

    # Populate session.route from MCP route if present
    envelope.session.route = route

    # Build canonical response envelope
    response_body = CanonicalResponseBody(
        status="success" if error_obj is None else "error",
        code=200 if error_obj is None else error_obj.code,
        type="text",
        text=reply_text,
        metadata={
            "source": "mcp_orchestrator" if error_obj is None else "mcp_adapter",
            "duration_ms": duration_ms,
        },
    )

    response_envelope = CanonicalResponseEnvelope(
        version=envelope.version or "1.1",
        timestamp=now_utc,
        context=envelope.context,
        session=envelope.session,
        response=response_body,
        error=error_obj,
        observability=envelope.observability,
    )

    # Return as plain dict so FastAPI can JSON-serialize it
    return response_envelope.dict()
