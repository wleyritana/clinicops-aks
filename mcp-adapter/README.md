# Blinksbuy MCP Adapter (Canonical JSON v1.1)

### AI Automation Platform – Model Context Protocol Adapter  
*Version: 1.1 · Deployment ready for Railway*

---

## Overview

The **MCP Adapter** is the entry point for all external channels (web, mobile, voice, chat, WhatsApp, ElevenLabs, etc.) into the **Model Context Protocol (MCP) Platform**.

It converts **raw client messages** into a **Canonical JSON Envelope (v1.1)** that the MCP Orchestrator understands.  
It also converts the MCP’s canonical response back into a channel-agnostic JSON format that upstream systems can use (TTS, chat clients, UIs, etc.)

This adapter ensures that **all channels speak one unified protocol**, enabling consistent:

- Observability (trace/span/message IDs)  
- LLM prompt context  
- Session continuity  
- Microservice-safe routing  
- Multi-tenant behavior  
- Future multimodal inputs (audio, images, events, etc.)  

---

## Key Features

- **LLM-ready** – carries optional LLM hints (model, temperature, etc.)
- **Microservice-safe** – standardized error envelope on downstream failures.
- **Adapter-agnostic** – works for Web, Voice, Mobile, WhatsApp, etc.
- **Traceable** – `trace_id`, `span_id`, `message_id` for every message.
- **Versionable** – Canonical Envelope v1.1, backward-compatible with v1.0.
- **Future-proof for multimodal** – supports `type: text | audio | image | event`.

---

## Environment Variables

| Variable   | Description                                      | Example                                                     |
|-----------|--------------------------------------------------|-------------------------------------------------------------|
| `MCP_URL` | URL of the MCP Orchestrator `/orchestrate`      | `https://mcp-service.up.railway.app/orchestrate`          |
| `API_KEY` or `API_KEYS` | One or more allowed API keys       | `abc123,xyz789`                                            |

---

## Authentication

Every canonical request **must** include:

```http
X-API-Key: <your_key>
```

Requests without valid keys will return:

- `401 Unauthorized` (no key)
- `403 Forbidden` (invalid key)

---

## API Endpoints

### `GET /health`

Basic healthcheck.

**Response:**

```json
{
  "status": "ok",
  "service": "mcp_adapter_python",
  "mcp_url": "https://mcp-service.up.railway.app/orchestrate"
}
```

---

### `POST /canonical/message`  (Primary endpoint)

Channel-agnostic canonical message gateway.

**Headers:**

```http
X-API-Key: <your_key>
Content-Type: application/json
```

**Body (Canonical Request Envelope v1.1 – text example):**

```json
{
  "version": "1.1",
  "timestamp": "2025-11-21T21:28:56.146Z",
  "context": {
    "channel": "web",
    "device": "browser",
    "locale": "en-US",
    "tenant": "blinksbuy",
    "client_app": "elevenlabs",
    "llm": {
      "model_hint": "gpt-4.1-mini",
      "temperature": 0.2
    }
  },
  "session": {
    "session_id": "user-123:web",
    "conversation_id": "conv-001",
    "user_id": "user-123",
    "turn": 3
  },
  "request": {
    "type": "text",
    "text": "Can you read me the menu?",
    "intent_override": null,
    "metadata": {
      "raw_transcript": "can you read me the menu",
      "confidence": 0.97
    }
  },
  "observability": {
    "trace_id": "trace-abc-123",
    "span_id": "span-inbound-1",
    "message_id": "msg-0001"
  }
}
```

---

### Multimodal Example (Audio)

```json
{
  "version": "1.1",
  "timestamp": "2025-11-21T21:30:00Z",
  "context": {
    "channel": "voice",
    "device": "iphone",
    "locale": "en-US",
    "tenant": "blinksbuy",
    "client_app": "elevenlabs"
  },
  "session": {
    "session_id": "voice-user-44",
    "conversation_id": "conv-331",
    "user_id": "voice-user-44",
    "turn": 12
  },
  "request": {
    "type": "audio",
    "audio_url": "https://cdn.you/audio.wav",
    "transcript": "I would like to order garlic chicken"
  },
  "observability": {
    "trace_id": "trace-22aa1bb3",
    "span_id": "span-991",
    "message_id": "msg-0002"
  }
}
```

---

## Canonical Response (Success)

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
    "route": "food_ordering.menu"
  },
  "response": {
    "status": "success",
    "code": 200,
    "type": "text",
    "text": "Here is the menu from Uno Bistro:\n\n1. Garlic Chicken – 500\n2. Sizzling Pata – 650\n3. Sisig – 400",
    "metadata": {
      "source": "mcp_orchestrator",
      "duration_ms": 16250.315
    }
  },
  "error": null,
  "observability": {
    "trace_id": "trace-abc-123",
    "span_id": "span-outbound-1",
    "message_id": "msg-0003"
  }
}
```

---

## Canonical Response (Error)

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
    "message": "MCP orchestrator error: 503 Service Unavailable",
    "retryable": false,
    "details": {
      "mcp_url": "https://your-mcp-service.railway.app/orchestrate"
    }
  },
  "observability": {
    "trace_id": "trace-abc-123",
    "span_id": "span-error-1",
    "message_id": "msg-err-001"
  }
}
```

---

## Testing with Postman

1. Set headers:
   - `X-API-Key: <your_key>`
   - `Content-Type: application/json`
2. POST to:
   - `https://<your-railway-url>/canonical/message`
3. Paste a canonical request JSON body and send.

---

## Client Integration & Code Widgets

This section shows how different clients can send canonical requests to the Blinksbuy MCP Adapter.

All examples target the canonical text endpoint:

```http
POST https://<your-railway-url>/canonical/message
X-API-Key: <your_key>
Content-Type: application/json
```

The request body uses the Canonical JSON Envelope v1.1 structure shown above.

### Python (requests)

```python
import requests
import uuid
from datetime import datetime, timezone

API_KEY = "adapter-super-secret-key-1"
BASE_URL = "https://<your-railway-url>"
ENDPOINT = f"{BASE_URL}/canonical/message"

def build_payload(user_id: str, text: str) -> dict:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    session_id = f"{user_id}:web"
    conversation_id = f"conv-{uuid.uuid4()}"

    return {
        "version": "1.1",
        "timestamp": now,
        "context": {
            "channel": "web",
            "device": "browser",
            "locale": "en-US",
            "tenant": "blinksbuy",
            "client_app": "python-example",
            "llm": {
                "model_hint": "gpt-4.1-mini",
                "temperature": 0.2,
            },
        },
        "session": {
            "session_id": session_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "turn": 1,
        },
        "request": {
            "type": "text",
            "text": text,
            "intent_override": None,
            "metadata": {
                "raw_transcript": text,
                "confidence": 1.0,
            },
        },
        "observability": {
            "trace_id": f"trace-{uuid.uuid4()}",
            "span_id": f"span-{uuid.uuid4()}",
            "message_id": f"msg-{uuid.uuid4()}",
        },
    }

def send_message(user_id: str, text: str):
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json",
    }
    payload = build_payload(user_id, text)
    resp = requests.post(ENDPOINT, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()

if __name__ == "__main__":
    response = send_message("user-123", "Can you read me the menu?")
    print("Adapter response:")
    print(response)
```

### Node.js (fetch)

```js
import fetch from "node-fetch";
import { randomUUID } from "crypto";

const API_KEY = "adapter-super-secret-key-1";
const BASE_URL = "https://<your-railway-url>";
const ENDPOINT = `${BASE_URL}/canonical/message`;

function buildPayload(userId, text) {
  const now = new Date().toISOString();
  const sessionId = `${userId}:web`;
  const conversationId = `conv-${randomUUID()}`;

  return {
    version: "1.1",
    timestamp: now,
    context: {
      channel: "web",
      device: "node",
      locale: "en-US",
      tenant: "blinksbuy",
      client_app: "node-example",
      llm: {
        model_hint: "gpt-4.1-mini",
        temperature: 0.2,
      },
    },
    session: {
      session_id: sessionId,
      conversation_id: conversationId,
      user_id: userId,
      turn: 1,
    },
    request: {
      type: "text",
      text,
      intent_override: null,
      metadata: {
        raw_transcript: text,
        confidence: 1.0,
      },
    },
    observability: {
      trace_id: `trace-${randomUUID()}`,
      span_id: `span-${randomUUID()}`,
      message_id: `msg-${randomUUID()}`,
    },
  };
}

async function sendMessage(userId, text) {
  const payload = buildPayload(userId, text);

  const resp = await fetch(ENDPOINT, {
    method: "POST",
    headers: {
      "X-API-Key": API_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    const errorText = await resp.text();
    throw new Error(`Adapter error ${resp.status}: ${errorText}`);
  }

  const data = await resp.json();
  console.log("Adapter response:", data);
}

sendMessage("user-123", "Can you read me the menu?").catch(console.error);
```

### Browser HTML + JavaScript

Note: for production do not expose your API key directly in client-side code; use a backend proxy. This example is for internal testing and demos.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Blinksbuy MCP Adapter Demo</title>
</head>
<body>
  <h1>Blinksbuy MCP Adapter Demo</h1>

  <label>
    Message:
    <input id="user-input" type="text" value="Can you read me the menu?" />
  </label>
  <button id="send-btn">Send</button>

  <pre id="response-box"></pre>

  <script>
    const API_KEY = "adapter-super-secret-key-1"; // Do not expose in production
    const BASE_URL = "https://<your-railway-url>";
    const ENDPOINT = BASE_URL + "/canonical/message";

    function buildPayload(userId, text) {
      const now = new Date().toISOString();
      const sessionId = userId + ":web";
      const conversationId = "conv-" + crypto.randomUUID();

      return {
        version: "1.1",
        timestamp: now,
        context: {
          channel: "web",
          device: "browser",
          locale: "en-US",
          tenant: "blinksbuy",
          client_app: "browser-example",
          llm: {
            model_hint: "gpt-4.1-mini",
            temperature: 0.2,
          },
        },
        session: {
          session_id: sessionId,
          conversation_id: conversationId,
          user_id: userId,
          turn: 1,
        },
        request: {
          type: "text",
          text: text,
          intent_override: null,
          metadata: {
            raw_transcript: text,
            confidence: 1.0,
          },
        },
        observability: {
          trace_id: "trace-" + crypto.randomUUID(),
          span_id: "span-" + crypto.randomUUID(),
          message_id: "msg-" + crypto.randomUUID(),
        },
      };
    }

    async function sendMessage(text) {
      const userId = "web-demo-user";
      const payload = buildPayload(userId, text);

      const resp = await fetch(ENDPOINT, {
        method: "POST",
        headers: {
          "X-API-Key": API_KEY,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const responseBox = document.getElementById("response-box");

      if (!resp.ok) {
        const errorText = await resp.text();
        responseBox.textContent = "Error " + resp.status + ":\n" + errorText;
        return;
      }

      const data = await resp.json();
      responseBox.textContent = JSON.stringify(data, null, 2);
    }

    document.getElementById("send-btn").addEventListener("click", () => {
      const text = document.getElementById("user-input").value;
      sendMessage(text).catch((err) => {
        document.getElementById("response-box").textContent = String(err);
      });
    });
  </script>
</body>
</html>
```

### PowerShell (Invoke-RestMethod)

```powershell
$endpoint = "https://<your-railway-url>/canonical/message"
$apiKey   = "adapter-super-secret-key-1"

$userId         = "ps-user-" + [guid]::NewGuid().ToString()
$sessionId      = "$userId:web"
$conversationId = "conv-" + [guid]::NewGuid().ToString()
$traceId        = "trace-" + [guid]::NewGuid().ToString()
$spanId         = "span-" + [guid]::NewGuid().ToString()
$messageId      = "msg-" + [guid]::NewGuid().ToString()

$text = "Hello from PowerShell. Can you read me the menu?"

$headers = @{
    "Content-Type" = "application/json"
    "X-API-Key"    = $apiKey
}

$payload = @{
    version   = "1.1"
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
    context   = @{
        channel    = "web"
        device     = "powershell"
        locale     = "en-US"
        tenant     = "blinksbuy"
        client_app = "powershell-client"
        llm = @{
            model_hint  = "gpt-4.1-mini"
            temperature = 0.2
        }
    }
    session = @{
        session_id      = $sessionId
        conversation_id = $conversationId
        user_id         = $userId
        turn            = 1
    }
    request = @{
        type = "text"
        text = $text
        metadata = @{
            raw_transcript = $text
            confidence     = 1.0
        }
    }
    observability = @{
        trace_id   = $traceId
        span_id    = $spanId
        message_id = $messageId
    }
}

$json = $payload | ConvertTo-Json -Depth 10
$response = Invoke-RestMethod -Uri $endpoint -Method Post -Body $json -Headers $headers
$response | ConvertTo-Json -Depth 10
```

### Postman Collection (JSON)

You can import the following collection into Postman (Import → Raw Text):

```json
{
  "info": {
    "name": "Blinksbuy MCP Adapter",
    "_postman_id": "d5fd2fb2-9e09-49e3-9c8a-338b4a43c5bb",
    "description": "Postman collection for testing the Blinksbuy MCP-compatible canonical message endpoint.",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Canonical Message (Text)",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          },
          {
            "key": "X-API-Key",
            "value": "{{API_KEY}}",
            "type": "text"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"version\": \"1.1\",\n  \"timestamp\": \"{{timestamp}}\",\n  \"context\": {\n    \"channel\": \"web\",\n    \"device\": \"postman\",\n    \"locale\": \"en-US\",\n    \"tenant\": \"blinksbuy\",\n    \"client_app\": \"postman-client\",\n    \"llm\": {\n      \"model_hint\": \"gpt-4.1-mini\",\n      \"temperature\": 0.2\n    }\n  },\n  \"session\": {\n    \"session_id\": \"{{session_id}}\",\n    \"conversation_id\": \"{{conversation_id}}\",\n    \"user_id\": \"{{user_id}}\",\n    \"turn\": 1\n  },\n  \"request\": {\n    \"type\": \"text\",\n    \"text\": \"Hello from Postman. Can you read me the menu?\",\n    \"intent_override\": null,\n    \"metadata\": {\n      \"raw_transcript\": \"Hello from Postman. Can you read me the menu?\",\n      \"confidence\": 1.0\n    }\n  },\n  \"observability\": {\n    \"trace_id\": \"{{trace_id}}\",\n    \"span_id\": \"{{span_id}}\",\n    \"message_id\": \"{{message_id}}\"\n  }\n}"
        },
        "url": {
          "raw": "{{BASE_URL}}/canonical/message",
          "host": [
            "{{BASE_URL}}"
          ],
          "path": [
            "canonical",
            "message"
          ]
        }
      },
      "response": []
    }
  ],
  "event": [
    {
      "listen": "prerequest",
      "script": {
        "exec": [
          "pm.variables.set("timestamp", new Date().toISOString());",
          "pm:variables.set("user_id", "postman-user-" + crypto.randomUUID());",
          "pm.variables.set("session_id", pm.variables.get("user_id") + ":web");",
          "pm.variables.set("conversation_id", "conv-" + crypto.randomUUID());",
          "pm.variables.set("trace_id", "trace-" + crypto.randomUUID());",
          "pm.variables.set("span_id", "span-" + crypto.randomUUID());",
          "pm.variables.set("message_id", "msg-" + crypto.randomUUID());"
        ],
        "type": "text/javascript"
      }
    }
  ],
  "variable": [
    {
      "key": "BASE_URL",
      "value": "https://<your-railway-url>",
      "type": "string"
    },
    {
      "key": "API_KEY",
      "value": "adapter-super-secret-key-1",
      "type": "string"
    }
  ]
}
```

---

## Railway Deployment

This project is **Railway-ready**:

- `Procfile` is provided:
  ```bash
  web: uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
  ```
- Railway will:
  - Install dependencies from `requirements.txt`
  - Detect the Procfile
  - Expose the service on the assigned `$PORT`

> Set your `MCP_URL` and `API_KEY` / `API_KEYS` in **Railway → Variables**.

---

## Project Structure

```text
blinksbuy_mcp_adapter/
├── app.py           # FastAPI app with Canonical v1.1 adapter logic
├── README.md        # This documentation
├── requirements.txt # Python dependencies
├── Procfile         # Railway process definition
└── .env.example     # Example env vars (for local dev)
```

---

## Summary

The Blinksbuy MCP Adapter is:

- Channel-agnostic
- Multi-tenant & multi-locale
- LLM-aware and multimodal-ready
- Traceable end-to-end
- Designed for modern AI automation platforms
- Ready to deploy on **Railway** out of the box

