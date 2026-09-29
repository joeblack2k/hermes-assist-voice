# Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `Plugin 'ha-voice' has no register() function` in the gateway log | `__init__.py` is missing or empty. It must contain `from .adapter import register`. |
| Plugin is not loaded at all | Not listed under `plugins.enabled` of the profile that runs the gateway, or copied to the wrong `<HERMES_HOME>` (each profile has its own `plugins/` directory). |
| `curl /health` refused | Gateway not restarted, `platforms.ha_voice.enabled` missing, `HA_VOICE_KEY` unset (the platform refuses to start without it), or the port is taken. Check the gateway log for `[ha_voice]`. |
| Reachable locally but not from Home Assistant | The plugin binds to `127.0.0.1` by default. Set `platforms.ha_voice.extra.host`, or forward the port (container proxy, reverse proxy). |
| HA setup says "Cannot connect" | Wrong URL (use the base URL without `/voice`), firewall, or the plugin is down. The check calls `GET <url>/health`. |
| HA setup says "Invalid API key" / requests return 401 | `HA_VOICE_KEY` in Hermes and the key entered in Home Assistant differ (watch for trailing spaces). |
| The gateway silently ignores the messages | Authorisation: set `HA_VOICE_ALLOW_ALL_USERS=true` (the plugin authenticates requests itself). |
| Answers arrive in the wrong language | Almost always the transcript. Check it in *Settings -> Voice assistants -> Debug* for the pipeline run, set the STT language and give the STT engine a prompt/hint, and add a language rule to `SOUL.md`. See [voice-tuning.md](voice-tuning.md). |
| Spoken answers contain markdown/URLs/explanations | Tighten `SOUL.md`; make sure tool-progress and interim messages are off for `ha_voice`. |
| HTTP 504 after 90 s | The agent did not finish: slow model, stuck tool, or a busy session. Look at the gateway log; use a faster model or fewer tools. |
| HTTP 409 | A second request for the same `device` arrived while the first was running (for example a double trigger). The newest wins. |
| First answer after a restart takes 15-20 s | Agent initialisation; later answers are much faster. |
| Conversations never start fresh | Check `session_reset` of the profile, or send `/new`. Sessions are keyed by `device`. |
| Conversation entity missing after upgrade | Restart Home Assistant fully (custom component Python code is not hot-reloaded). |

## Long tasks are silent

* `display.platforms.ha_voice.interim_assistant_messages` must be `true`, otherwise Hermes never emits progress steps.
* The persona (`SOUL.md`) must ask for a short spoken sentence before long tool calls, and must not forbid "one moment"-style phrases.
* The first spoken step needs `ack_text` (see installation). Follow-up steps are announced with `assist_satellite.announce`; the satellite must support it and be idle again (the integration waits for that).

## Useful commands

```bash
# sessions of the voice profile (source: ha_voice)
hermes -p <profile> sessions list

# gateway log
journalctl -u hermes-gateway -n 100 --no-pager | grep -i ha_voice
```

In Home Assistant, *Settings -> Voice assistants -> (your assistant) -> Debug* shows the STT text, the conversation response and timings for each run, which quickly tells you which step is slow or wrong.
