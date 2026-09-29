# Using it with the Echo Muse and other ESPHome voice satellites

The Echo Muse is a smart speaker that can run ESPHome's voice assistant firmware. Any ESPHome device that acts as a Home Assistant *Assist satellite* (Echo Muse, ATOM Echo, Home Assistant Voice PE, DIY ESP32-S3 speakers, ...) works the same way, because this project only sits in the *conversation* step of the pipeline.

```
Echo Muse ----audio----> Home Assistant Assist pipeline
   ^                       STT -> Hermes Agent (this project) -> TTS
   '-----spoken answer-----------------------------------------'
```

## What runs where

| Step | Runs on | Notes |
|---|---|---|
| Wake word | The speaker itself (microWakeWord/openWakeWord model in the ESPHome firmware) | Nothing leaves the speaker until the wake word fires. |
| Speech-to-text | Home Assistant, using the engine of the pipeline | Local (Whisper/Speech-to-Phrase) or a cloud engine. |
| Conversation | **Hermes Agent** via this project | Returns the short spoken answer. |
| Text-to-speech | Home Assistant, using the engine of the pipeline | The audio is streamed back to the speaker. |

## Setup

1. Flash/configure the speaker with an ESPHome voice assistant configuration and add it to Home Assistant (*Settings -> Devices & services*, it is discovered as an ESPHome device). It appears as an *Assist satellite* entity.
2. Create the pipeline as described in [installation.md](installation.md#3-assist-pipeline).
3. Open the speaker's device page and set its **Assistant** select entity to that pipeline. (The same select exists per satellite, so different rooms can use different pipelines.)
4. Choose the **wake word** on the device page. Wake words are models compiled into or loaded by the firmware; a custom word such as "Alexa" or "Jarvis" needs a matching model on the device. Wake word detection is entirely on the device, independent of this project.
5. Say the wake word and ask something.

## Conversations and sessions

The integration sends the satellite entity name (for example `living_room_voice_assistant_assist_satellite`) as the `device`. The Hermes plugin uses it as the chat id, so:

* every speaker has its own continuing conversation in Hermes, visible under the bot in the dashboard and in `hermes sessions list`;
* follow-up questions ("and the day after?") work because the session is reused;
* the bot's session policy starts a new session after the configured idle time or at the daily reset; you can also send `/new` from the Assist text dialog to force one.

Two speakers in the same room can share a conversation by sending the same `device` value; by default each satellite is separate.

## Tips for a speaker

* Keep answers short. Add a "spoken answer" instruction to the bot's `SOUL.md`; see [voice-tuning.md](voice-tuning.md).
* If the speaker should ask a follow-up question, enable *continued conversation* on the satellite where your Home Assistant version supports it; the bot then keeps listening after a question.
* Use *Prefer handling commands locally* in the pipeline so simple commands ("turn on the light") never wait on an LLM.
* Latency budget: wake word + STT (1-2 s) + LLM (2-6 s, model dependent) + TTS (1-2 s). A fast, small model with few tools is the biggest lever.

## Microphone here, speaker somewhere else

The satellite can be used as a microphone only, while a better speaker (for example a Sonos) plays the answers. Open *Settings -> Devices & services -> Hermes Agent -> Configure* and pick a *Speaker* (any media player). Then:

* Every reply, including the early acknowledgement and the spoken progress steps of long tasks, is played on that media player with the pipeline's own TTS engine, language and voice.
* The conversation returns no text to the pipeline, so the satellite itself stays silent. The pipeline therefore skips its TTS step.
* Clear the field to go back to speaking on the satellite.

The media player must accept announcements (`tts.speak`). Some players (Sonos) do not show a state change while they announce, so check by listening rather than by looking at the entity.
