# MCP Orchestrator (ClinicOps)  
Model Context Protocol – Intent Routing and Flow Execution  
Clinician-facing edition

## Overview

The MCP Orchestrator is the central coordination layer for the Model Context Protocol (MCP) platform. It receives thin normalized requests from the MCP Adapter and performs:

1. Intent classification (OpenAI-based or stubbed)
2. Domain flow routing via the Flow Service
3. Lightweight session tracking (turn counts, last_route)
4. Structured observability with Loki + Grafana
5. End-to-end trace_id propagation across adapter → orchestrator → intent → flow → LLM drafting

The orchestrator intentionally does not return canonical JSON. The MCP Adapter wraps its output into Canonical Response v1.1.

## Role in the Architecture

Client → Channel → MCP Adapter → MCP Orchestrator → Intent Service → Flow Service → LLM Service → MCP Adapter → Client

### MCP Adapter Responsibilities
- Canonical JSON v1.1 (input + output)
- Multimodal normalization
- Error envelope generation
- trace_id creation
- Device, locale, tenant, channel context

### MCP Orchestrator Responsibilities
- Intent classification
- Flow routing
- Thin session state
- Logging + trace propagation

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| GRAFANA_LOKI_URL | Grafana Cloud Loki push URL |
| GRAFANA_LOKI_USERNAME | Loki tenant ID |
| GRAFANA_LOKI_API_TOKEN | API token (logs:write) |
| MCP_APP_LABEL | Loki app label |
| OPENAI_API_KEY | Key for OpenAI intent classification |
| OPENAI_MODEL | OpenAI model name |
| (optional) MCP_APP_LABEL | Loki app label |

---

## API Endpoints

### GET /health

Example response:
```json
{
  "status": "ok",
  "service": "mcp_orchestrator_thin"
}
```

---

### POST /orchestrate

### Request (Thin Format)
```json
{
  "text": "Turn this into a SOAP note: 54M with DM2/HTN...",
  "user_id": "user-123",
  "channel": "web",
  "session_id": "user-123:web",
  "trace_id": "trace-123abc"
}
```

### Orchestrator Response (Thin Format)
```json
{
  "decision": "reply",
  "reply_text": "SOAP Note (Draft) ...",
  "session_id": "user-123:web",
  "route": "documentation",
  "intent": "documentation",
  "intent_confidence": 0.98,
  "trace_id": "trace-123abc"
}
```

---

## Canonical Response v1.1 (Success)

```json
{
  "version": "1.1",
  "timestamp": "2025-11-21T21:28:56.146Z",
  "context": {
    "channel": "web",
    "device": "browser",
    "locale": "en-US",
    "tenant": "blinksbuy",
    "client_app": "elevenlabs"
  },
  "session": {
    "session_id": "user-123:web",
    "conversation_id": "conv-001",
    "user_id": "user-123",
    "turn": 4,
    "route": "menu"
  },
  "response": {
    "status": "success",
    "code": 200,
    "type": "text",
    "text": "SOAP Note (Draft) ...",
    "metadata": {
      "source": "mcp_orchestrator",
      "duration_ms": 16250.315
    }
  },
  "error": null,
  "observability": {
    "trace_id": "trace-123abc",
    "span_id": "span-out-1",
    "message_id": "msg-0003"
  }
}
```

---

## Canonical Response v1.1 (Error)

```json
{
  "version": "1.1",
  "timestamp": "2025-11-21T21:28:56.146Z",
  "context": {
    "channel": "web",
    "device": "browser",
    "locale": "en-US",
    "tenant": "blinksbuy",
    "client_app": "elevenlabs"
  },
  "session": {
    "session_id": "user-123:web",
    "conversation_id": "conv-001",
    "user_id": "user-123",
    "turn": 4,
    "route": null
  },
  "response": {
    "status": "error",
    "code": 502,
    "type": "text",
    "text": null,
    "metadata": {
      "source": "mcp_adapter",
      "duration_ms": 112.529
    }
  },
  "error": {
    "type": "MCP_ORCHESTRATOR_ERROR",
    "code": 502,
    "message": "MCP orchestrator error: 500 Internal error in orchestrator",
    "retryable": false,
    "details": {
      "mcp_url": "https://your-mcp-service.railway.app/orchestrate"
    }
  },
  "observability": {
    "trace_id": "trace-123abc",
    "span_id": "span-error-1",
    "message_id": "msg-err-001"
  }
}
```

---

## Logging & Observability

All services log structured JSON into Grafana Loki using:

- trace_id  
- session_id  
- service_type  
- sync_mode  
- io  
- event_type  
- latency_ms  
- intent + confidence  

This enables full cross-service traceability.

---

## Project Structure

```
app/
  main.py
  flow_service.py
  intent_service.py
  llm_service.py
  logging_loki.py
grafana/
  mcp_orchestrator_loki_dashboard.json
Procfile
requirements.txt
README.md
```

---

## Railway Deployment

Procfile:
```
web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
```

Set environment variables:
- GRAFANA_LOKI_URL  
- GRAFANA_LOKI_USERNAME  
- GRAFANA_LOKI_API_TOKEN  
- OPENAI_API_KEY  
- OPENAI_MODEL (optional)  
- MCP_APP_LABEL (optional)  

### Notes on PHI
This repo avoids logging raw clinician text by default. Logs include only a short text fingerprint and text length for traceability.

---

## Summary

The orchestrator is now fully aligned with:
- MCP Canonical JSON v1.1  
- trace_id propagation  
- Upgraded intent, flow, menu services  
- Updated logging_loki with trace labels  
- Railway deployment requirements  
- Grafana dashboard traceability  
