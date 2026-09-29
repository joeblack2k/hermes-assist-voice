# Hermes Assist Voice

Talk to a [Hermes Agent](https://github.com/NousResearch/hermes-agent) bot through **Home Assistant Assist**, for example from an ESPHome voice satellite such as the **Echo Muse** speaker.

```
 "Hey <wake word>, what's the weather tomorrow?"
        |
 ESPHome voice satellite (wake word runs on the device)
        |  audio
 Home Assistant Assist pipeline
        |-- STT (any Home Assistant speech-to-text engine)
        |-- Conversation agent: "Hermes Agent"  <-- custom_components/hermes_agent
        |         |  POST /voice  {"text", "device", "context"}
        |         v
        |   Hermes gateway, platform "ha_voice"  <-- hermes-plugin/ha-voice
        |         |  normal gateway turn: session policy, tools, memory, Home Assistant tools
        |         v
        |   short spoken answer
        |-- TTS (any Home Assistant text-to-speech engine)
        v
 speaker
```

This repository contains two small parts that work together:

| Part | Where it runs | What it does |
|---|---|---|
| [`hermes-plugin/ha-voice`](hermes-plugin/ha-voice) | Hermes Agent (gateway) | A Hermes *platform plugin*. Exposes `POST /voice`, feeds the text into the gateway as a normal chat message and returns the final answer in the HTTP response. |
| [`custom_components/hermes_agent`](custom_components/hermes_agent) | Home Assistant | A conversation agent that forwards Assist text to the plugin, so you can select it in any Assist pipeline. |

## Why a gateway platform and not the OpenAI-compatible API server?

Hermes' `api_server` platform is great for generic clients, but a voice assistant has different needs:

* **The bot, not the client, owns sessions.** With the API server the *caller* picks the session id, so a voice satellite either stays in one endless session or has to invent its own reset rules. With `ha_voice` the turn goes through the gateway's `SessionStore`, so the bot's own `session_reset` policy (idle timeout, daily reset) and commands like `/new` apply, exactly as for Telegram or Discord. Conversations show up in Hermes under the bot (one continuing conversation per speaker/device).
* **Spoken output.** The plugin injects a "this is spoken aloud" hint and lets you switch off tool-progress and interim messages for the platform, so only the final short answer reaches the speaker.
* **One place for behaviour.** Personality, language and tools live in the Hermes profile (`SOUL.md`, `config.yaml`), not in Home Assistant.

## Features

* Synchronous request/response: the final answer is returned as soon as the agent finishes.
* One conversation per voice device (`device` field, for example the satellite entity name), managed by the Hermes session policy.
* Optional per-request `context` (the integration sends the current local time) applied as an ephemeral system prompt that is never stored in the transcript.
* Bearer-token authentication, bind address defaults to loopback.
* Works with any Assist pipeline: STT, TTS and wake word are completely independent of this project.

## Requirements

* Hermes Agent with gateway platform plugin support. Developed and tested against **v0.21.5**, including a multiplexed profile (`gateway.multiplex_profiles`).
* Home Assistant **2024.x or newer** with the `conversation` integration (developed on 2026.9).
* Network path from Home Assistant to the plugin port (default `8651`).

## Quick start

1. **Hermes side** - copy `hermes-plugin/ha-voice` to `<HERMES_HOME>/plugins/ha-voice`, enable it and set a key. See [docs/installation.md](docs/installation.md#1-hermes-plugin).
2. **Home Assistant side** - install `hermes_agent` through HACS (custom repository) or by copying `custom_components/hermes_agent`, then add the integration and enter the plugin URL and key. See [docs/installation.md](docs/installation.md#2-home-assistant-integration).
3. **Assist pipeline** - create a pipeline that uses *Hermes Agent* as its conversation agent and pick your STT/TTS. See [docs/installation.md](docs/installation.md#3-assist-pipeline).
4. **Speaker** - assign the pipeline to your voice satellite (Echo Muse or any other). See [docs/echo-muse.md](docs/echo-muse.md).

## Documentation

* [Installation and configuration](docs/installation.md)
* [Using it with the Echo Muse / ESPHome voice satellites](docs/echo-muse.md)
* [Making the bot sound right for voice (prompting, language, speed)](docs/voice-tuning.md)
* [Endpoint reference](docs/api.md)
* [Troubleshooting](docs/troubleshooting.md)

## Security notes

* Anyone who can reach the port **and** knows `HA_VOICE_KEY` can talk to your bot with the tools you gave the `ha_voice` platform. Keep the key secret, keep the port on your LAN, and give the platform only the toolsets it needs.
* The plugin binds to `127.0.0.1` by default. If Home Assistant runs on another host, expose the port deliberately (bind to a LAN address, a port forward or a reverse proxy) and restrict it with a firewall.
* The key is compared in constant time. There is no TLS in the plugin itself; terminate TLS in a reverse proxy if the traffic leaves a trusted network.

## Limitations

* One in-flight request per device: a new request for the same `device` cancels the previous one (the previous caller gets HTTP 409).
* Text in, text out. Speech recognition and synthesis are handled by Home Assistant, not by this project.
* Streaming replies are not supported (the answer is returned at once, which is what Assist expects from a non-streaming agent).

## License

MIT, see [LICENSE](LICENSE).
