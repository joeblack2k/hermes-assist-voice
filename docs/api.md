# Endpoint reference

The plugin serves a tiny HTTP API on `platforms.ha_voice.extra.host:port` (default `127.0.0.1:8651`).

## `GET /health`

No authentication. Returns `{"status": "ok"}` while the platform is connected.

## `POST /voice`

Headers:

```
Authorization: Bearer <HA_VOICE_KEY>
Content-Type: application/json
```

Body:

| Field | Type | Required | Description |
|---|---|---|---|
| `text` | string | yes | What the user said (the STT result). May be a gateway command such as `/new`. |
| `device` | string | no (default `default`) | Identifies the speaker/room. Becomes the chat id, so each device gets its own continuing conversation. |
| `context` | string | no | Ephemeral system-prompt text for this turn only (for example the current time). Not stored in the transcript. |

Responses:

| Status | Body | Meaning |
|---|---|---|
| 200 | `{"text": "..."}` | Final answer of the agent. |
| 400 | `{"error": "invalid json"}` / `{"error": "text required"}` | Malformed request. |
| 401 | `{"error": "unauthorized"}` | Missing or wrong key. |
| 409 | `{"error": "superseded"}` | A newer request for the same `device` replaced this one. |
| 504 | `{"error": "timeout"}` | No final answer within 90 s. |

Only the final reply of a turn is returned. Tool-progress and interim assistant messages are ignored by the plugin (and should be switched off in `display.platforms.ha_voice`).

## How a turn flows through Hermes

1. The plugin builds a `MessageEvent` (platform `ha_voice`, chat type `dm`, chat id = `device`) and hands it to the gateway with `handle_message`.
2. The gateway resolves the session with the profile's `SessionStore` and reset policy, runs the agent and calls the adapter's `send()` with the final answer (marked `notify`).
3. The plugin completes the pending HTTP request with that text.

## Example

```bash
curl -s -X POST http://127.0.0.1:8651/voice \
  -H "Authorization: Bearer $HA_VOICE_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Turn off the kitchen light","device":"kitchen","context":"Current local time: 18:04"}'
```
