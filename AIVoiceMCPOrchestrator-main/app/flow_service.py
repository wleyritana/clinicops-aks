# app/flow_service.py

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from .logging_loki import loki
from .llm_service import draft_documentation_note, draft_assessment_plan


# ------------------------------------------------------
# FlowServiceResult model
# ------------------------------------------------------

class FlowServiceResult(BaseModel):
    reply_text: str
    route: str   # which microservice or flow handled the request


# ------------------------------------------------------
# Main Flow Service Logic
# ------------------------------------------------------

def run_flow(
    intent: str,
    text: str,
    user_id: str,
    channel: str,
    session_id: str,
    trace_id: Optional[str] = None,
) -> FlowServiceResult:
    """
    Flow Service = domain orchestration layer.

    Responsibilities:
      - Route by INTENT (determined by intent_service.py)
      - Call correct microservice(s)
      - Assemble final reply_text
      - Handle business logic OUTSIDE of MCP

    The orchestrator simply calls `run_flow()` and returns the result.
    """

    # Log start of flow handling
    loki.log(
        "info",
        {
            "event_type": "flow_start",
            "intent": intent,
            "user": user_id,
            "channel": channel,
            "session_id": session_id,
        },
        service_type="flow_service",
        sync_mode="sync",
        io="in",
        trace_id=trace_id,
    )

    # ======================================================
    #  INTENT → FLOW ROUTING (ClinicOps, clinician-facing)
    # ======================================================

    # 1) DOCUMENTATION FLOW
    if intent == "documentation":
        reply_text = draft_documentation_note(
            text=text,
            user_id=user_id,
            channel=channel,
            session_id=session_id,
            trace_id=trace_id,
        )
        return FlowServiceResult(reply_text=reply_text, route="documentation")

    # 2) ASSESSMENT & PLAN FLOW
    if intent == "assessment_plan":
        reply_text = draft_assessment_plan(
            text=text,
            user_id=user_id,
            channel=channel,
            session_id=session_id,
            trace_id=trace_id,
        )
        return FlowServiceResult(reply_text=reply_text, route="assessment_plan")

    # ======================================================
    #  UNKNOWN / DEFAULT FLOW
    # ======================================================

    reply_text = (
        "I can help with clinician-facing ClinicOps tasks. Try one of:\n"
        "- 'Turn this into a SOAP note' (documentation)\n"
        "- 'Give me a differential and plan for this case' (assessment & plan)\n\n"
        "Tip: paste the case summary or your raw notes and specify the format you want."
    )

    loki.log(
        "info",
        {
            "event_type": "flow_fallback",
            "intent": intent,
            "user": user_id,
            "channel": channel,
            "session_id": session_id,
        },
        service_type="flow_service",
        sync_mode="sync",
        io="none",
        trace_id=trace_id,
    )

    return FlowServiceResult(reply_text=reply_text, route="fallback")

