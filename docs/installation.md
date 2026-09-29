# Installation and configuration

## 1. Hermes plugin

The plugin lives in `hermes-plugin/ha-voice`. Hermes loads user plugins from `<HERMES_HOME>/plugins/<name>/`.

* Default profile: `~/.hermes/plugins/ha-voice/`
* Named profile (for example one called `voice`): `~/.hermes/profiles/voice/plugins/ha-voice/`

A dedicated profile for the voice bot is recommended: it gets its own `SOUL.md`, model, memory and session history, and its conversations appear under that bot in the Hermes dashboard.

```bash
# example for a profile called "voice"
PROFILE_DIR=~/.hermes/profiles/voice
mkdir -p "$PROFILE_DIR/plugins"
cp -r hermes-plugin/ha-voice "$PROFILE_DIR/plugins/"
```

Make sure the files are readable by the user that runs the gateway. `__init__.py` must be present; it re-exports `register`.

### 1.1 Secrets (`<profile>/.env`)

```dotenv
# shared secret Home Assistant sends as "Authorization: Bearer <key>"
HA_VOICE_KEY=<a long random string, e.g. output of: openssl rand -hex 24>

# the plugin authenticates requests itself, so let the gateway accept the platform's "user"
HA_VOICE_ALLOW_ALL_USERS=true

# optional, default 8651
# HA_VOICE_PORT=8651
```

### 1.2 Profile config (`<profile>/config.yaml`)

```yaml
plugins:
  enabled:
    - ha-voice            # add to your existing list

platforms:
  ha_voice:
    enabled: true
    extra:
      # host: 127.0.0.1   # default. Use 0.0.0.0 (or a LAN address) if Home Assistant is on another machine
      # port: 8651
      ack_text: "One moment, I'll take a look."   # spoken if the agent is silent for ack_after seconds; "" disables
      ack_after: 6

# Tools the voice bot may use. Keep this list short: every tool adds latency and risk.
platform_toolsets:
  ha_voice:
    - homeassistant
    - memory
    - session_search
    - web

# Make the platform behave like a speaker instead of a chat window.
display:
  platforms:
    ha_voice:
      tool_progress: 'off'
      interim_assistant_messages: true   # spoken progress steps during long tasks
      streaming: false
      busy_ack_detail: false
      long_running_notifications: false
      message_reactions: false
```

`platform_toolsets` names depend on what your Hermes install provides; use the same names your other platforms use. If you already have a `platforms:` or `display.platforms:` block, merge these keys into it instead of adding a second block.

### 1.3 Session policy

The bot decides when a new conversation starts, using the normal gateway `session_reset` settings of the profile, for example:

```yaml
session_reset:
  mode: both          # idle and daily
  idle_minutes: 240
  at_hour: 4
```

Pick values that suit a speaker: a short idle time (30-60 min) keeps unrelated questions apart, a long one allows follow-ups hours later. Sending `/new` as a message also starts a fresh session.

### 1.4 Restart and verify

```bash
hermes gateway restart          # or restart the gateway service
curl http://127.0.0.1:8651/health
# {"status": "ok"}
```

Try a full turn (replace the key):

```bash
curl -s -X POST http://127.0.0.1:8651/voice \
  -H "Authorization: Bearer $HA_VOICE_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"text": "What time is it?", "device": "test"}'
# {"text": "It is a quarter to six."}
```

The first request after a gateway restart is slower (the agent is initialised); later requests are typically a few seconds, depending on your model.

If Hermes runs in a container or VM, forward the port so Home Assistant can reach it, and bind the plugin to an address that is reachable from that forward (for a Docker/Incus/LXC proxy that connects to the container's loopback, the default is enough).

## 2. Home Assistant integration

### Via HACS (custom repository)

1. HACS -> three-dot menu -> *Custom repositories*.
2. Add `https://github.com/joeblack2k/hermes-assist-voice` with type *Integration*.
3. Download *Hermes Agent* and restart Home Assistant.

### Manual

Copy `custom_components/hermes_agent` into your Home Assistant `config/custom_components/` directory and restart Home Assistant.

### Add the integration

*Settings -> Devices & services -> Add integration -> Hermes Agent*

| Field | Value |
|---|---|
| URL | Base URL of the plugin, for example `http://hermes-host:8651` (no trailing path) |
| API key | The value of `HA_VOICE_KEY` |
| Timeout | Seconds Home Assistant waits for an answer (default 90) |

The setup checks `GET <url>/health`. This creates a conversation entity called `conversation.hermes_agent`.

## 3. Assist pipeline

*Settings -> Voice assistants -> Add assistant*

* **Conversation agent:** Hermes Agent
* **Speech-to-text:** your choice. Set the language explicitly and prefer an engine that accepts a language hint or prompt; recognising the wrong language is the most common cause of odd answers. See [voice-tuning.md](voice-tuning.md).
* **Text-to-speech:** your choice, with a language/voice that matches the bot's language.
* **Prefer handling commands locally:** leave it on if you want Home Assistant's built-in intents (lights, timers, ...) to answer instantly and only send everything else to Hermes.

Test in the *Assist* dialog (chat icon) first, then attach the pipeline to your speaker: [echo-muse.md](echo-muse.md).

## 4. Updating

* Plugin: replace the files under `<profile>/plugins/ha-voice/` and restart the gateway.
* Integration: update through HACS, or replace the folder, and restart Home Assistant (Python changes need a full restart, not a reload).
