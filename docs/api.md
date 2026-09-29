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
| 200 | `{"text": "...", "final": true, "turn": "..."}` | Final answer of the agent. |
| 200 | `{"text": "...", "final": false, "turn": "..."}` | Progress step or acknowledgement; the turn is still running. Fetch the rest with `GET /voice/next`. |
| 400 | `{"error": "invalid json"}` / `{"error": "text required"}` | Malformed request. |
| 401 | `{"error": "unauthorized"}` | Missing or wrong key. |
| 409 | `{"error": "superseded"}` | A newer request for the same `device` replaced this one. |
| 504 | `{"error": "timeout"}` | No final answer within 90 s. |

`POST /voice` returns as soon as the agent has something to say. That is either the final answer or, for long tasks, a short *progress step* (`final: false`). Progress steps are the interim assistant messages Hermes emits between tool calls ("I'm looking at your browser"), so `display.platforms.ha_voice.interim_assistant_messages` must be `true`. If nothing has been said after `ack_after` seconds (default 6) and `ack_text` is configured, that text is returned as the first step so the speaker is never silent. Raw tool progress stays off.

## `GET /voice/next`

Same `Authorization` header. Query parameters: `turn` (from the previous response) and `wait` (seconds to block, default 20, max 30).

Returns the next message of the turn as `{"text", "final", "turn"}`. An empty `text` with `final: false` means "nothing yet, poll again". Keep polling until `final` is `true`. Unknown or finished turns return `{"text": "", "final": true}`.

The bundled Home Assistant integration does this for you: it speaks the first step as the normal Assist answer, then polls in the background and announces every following step and the final answer on the same satellite with `assist_satellite.announce`. Without a satellite (for example the text API) it waits for the final answer instead.

## How a turn flows through Hermes

1. The plugin builds a `MessageEvent` (platform `ha_voice`, chat type `dm`, chat id = `device`) and hands it to the gateway with `handle_message`.
2. Before the turn, the adapter pins the voice chat to the profile's canonical hidden **`Bot Chat`** session (created on first use), so every voice device shares the one bot conversation that the Hermes apps show under the bot and that you can continue from any device. Then the gateway resolves the session with the profile's `SessionStore`, runs the agent and calls the adapter's `send()` with the final answer (marked `notify`).
3. Each `send()` (interim or final) is put on the turn's queue; `POST /voice` and `GET /voice/next` hand them out in order.

## Example

```bash
curl -s -X POST http://127.0.0.1:8651/voice \
  -H "Authorization: Bearer $HA_VOICE_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Turn off the kitchen light","device":"kitchen","context":"Current local time: 18:04"}'
```
