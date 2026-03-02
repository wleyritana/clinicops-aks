import os
import time
import json
import hashlib
from typing import Optional, List

from pydantic import BaseModel
from openai import OpenAI

from .logging_loki import loki


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

client: Optional[OpenAI] = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    print("[intent_service] OPENAI_API_KEY not set – intent classification will be stubbed.")


class IntentResult(BaseModel):
    intent: str
    confidence: float
    raw_reasoning: str


def _stub_intent(text: str) -> IntentResult:
    """
    Fallback intent classifier when no OpenAI key is configured.
    Keeps behaviour similar to what you had before.
    """
    t = text.lower()

    # ClinicOps (clinician-facing) stub intents
    if any(k in t for k in [
        "soap", "h&p", "history and physical", "progress note", "discharge summary",
        "consult note", "referral letter", "write note", "format note", "documentation",
    ]):
        return IntentResult(intent="documentation", confidence=0.8, raw_reasoning="keyword match: documentation")

    if any(k in t for k in [
        "ddx", "differential", "assessment", "a/p", "assessment and plan", "workup",
        "management", "plan for",
    ]):
        return IntentResult(intent="assessment_plan", confidence=0.75, raw_reasoning="keyword match: assessment_plan")

    if any(k in t for k in [
        "labs", "lab", "imaging", "ct", "mri", "x-ray", "xray", "ultrasound",
        "ecg", "ekg", "troponin", "cbc", "cmp", "interpret",
    ]):
        return IntentResult(intent="results_review", confidence=0.7, raw_reasoning="keyword match: results_review")

    if any(k in t for k in ["hi", "hello", "good morning", "good evening"]):
        return IntentResult(intent="greeting", confidence=0.6, raw_reasoning="keyword match: greeting")

    if any(k in t for k in ["thanks", "thank you", "lol", "how are you"]):
        return IntentResult(intent="smalltalk", confidence=0.55, raw_reasoning="keyword match: smalltalk")

    return IntentResult(intent="unknown", confidence=0.5, raw_reasoning="fallback: unknown")


def _text_fingerprint(text: str) -> str:
    """Short, non-reversible fingerprint for observability without logging PHI."""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:12]


def classify_intent(
    text: str,
    user_id: str,
    channel: str,
    session_id: str,
    history: Optional[List[dict]] = None,
    trace_id: Optional[str] = None,
) -> IntentResult:
    """
    Classify the user's intent using OpenAI (or stub if no key).
    This is treated as an ASYNC-style microservice in logging terms.

    Note:
    - Signature is backward compatible with older orchestrator calls.
    - `trace_id` is optional and used only for observability.
    """

    start = time.perf_counter()

    text_fp = _text_fingerprint(text)

    # --- LOG: service_call (async / out) ---
    loki.log(
        "info",
        {
            "event_type": "service_call",
            "reason": "classify_intent",
            "user": user_id,
            "channel": channel,
            "session_id": session_id,
            "text_fingerprint": text_fp,
            "text_len": len(text),
        },
        service_type="intent_service",
        sync_mode="async",
        io="out",
        trace_id=trace_id,
    )

    # If no OpenAI key, use the stub and still log service_return
    if client is None:
        result = _stub_intent(text)
        latency_ms = round((time.perf_counter() - start) * 1000.0, 3)

        loki.log(
            "info",
            {
                "event_type": "service_return",
                "user": user_id,
                "channel": channel,
                "session_id": session_id,
                "latency_ms": latency_ms,
                "intent": result.intent,
                "confidence": result.confidence,
                "reason": result.raw_reasoning,
            },
            service_type="intent_service",
            sync_mode="async",
            io="in",
            trace_id=trace_id,
        )
        return result

    try:
        # --------- OpenAI call ----------
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an intent classifier for a clinician-facing ClinicOps assistant.\n"
                    "Classify the user's message into one of: "
                    "documentation, assessment_plan, results_review, greeting, smalltalk, unknown.\n"
                    "\n"
                    "Guidance:\n"
                    "- documentation: requests to format, rewrite, or generate clinical notes (SOAP, H&P, progress note, discharge summary, consult note).\n"
                    "- assessment_plan: requests for differential diagnosis, assessment, workup, management plan, disposition.\n"
                    "- results_review: requests to interpret labs, imaging impressions, ECG/EKG text, pathology summaries.\n"
                    "- greeting/smalltalk: conversational.\n"
                    "Return a short JSON object: "
                    "{\"intent\": \"...\", \"confidence\": 0.xx, \"reason\": \"...\"}."
                ),
            },
            {"role": "user", "content": text},
        ]

        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.2,
        )
        content = completion.choices[0].message.content

        # Loose JSON parsing, with cleaning if needed
        parsed = {}
        try:
            parsed = json.loads(content)
        except Exception:
            try:
                cleaned = content.strip().strip("`")
                if cleaned.lower().startswith("json"):
                    cleaned = cleaned[4:].lstrip()
                parsed = json.loads(cleaned)
            except Exception:
                parsed = {}

        intent = parsed.get("intent", "unknown")
        confidence = float(parsed.get("confidence", 0.5))
        reason = parsed.get("reason", content)

        result = IntentResult(intent=intent, confidence=confidence, raw_reasoning=reason)

        # --- LOG: service_return (async / in) ---
        latency_ms = round((time.perf_counter() - start) * 1000.0, 3)
        loki.log(
            "info",
            {
                "event_type": "service_return",
                "user": user_id,
                "channel": channel,
                "session_id": session_id,
                "latency_ms": latency_ms,
                "intent": result.intent,
                "confidence": result.confidence,
                "reason": result.raw_reasoning,
            },
            service_type="intent_service",
            sync_mode="async",
            io="in",
            trace_id=trace_id,
        )

        return result

    except Exception as e:
        latency_ms = round((time.perf_counter() - start) * 1000.0, 3)

        # --- LOG: service_error ---
        loki.log(
            "error",
            {
                "event_type": "service_error",
                "user": user_id,
                "channel": channel,
                "session_id": session_id,
                "latency_ms": latency_ms,
                "error": str(e),
            },
            service_type="intent_service",
            sync_mode="async",
            io="none",
            trace_id=trace_id,
        )

        # Fall back to stubbed intent on error so the orchestrator can still respond
        return _stub_intent(text)
