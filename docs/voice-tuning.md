# Making the bot sound right for voice

## Give the bot a voice persona

Put voice rules in the profile's `SOUL.md` (or your equivalent system prompt). Example:

```markdown
# Voice assistant

You answer through a speaker. Rules:
- Answer in one or two short sentences, in plain spoken language.
- No markdown, lists, links, code or emoji. Spell out numbers and units the way you would say them.
- Never mention tools, entity ids or errors; if something fails, say briefly that you could not do it.
- Always answer in <your language>. If the input is unintelligible or in another language, ask the user to repeat it and do nothing else.
```

The plugin already adds a generic "spoken aloud" hint, and the integration sends the current local time with every request, so the bot does not need to look up the time itself.

## Language and speech recognition

Wrong-language transcripts are the number one reason a voice bot "answers in the wrong language": the LLM faithfully replies to whatever the STT produced.

* Set the pipeline's STT language explicitly.
* If your STT engine accepts a **prompt / vocabulary hint**, give it a sentence in the target language that resembles real commands. This strongly biases short utterances toward the right language.
* Audio that is too quiet or clipped hurts recognition; check the speaker's microphone gain and distance.
* Add a rule to the bot that unintelligible input is answered with a short "please repeat" instead of a guess.

## Speed

* Choose a small, fast model for the voice profile; big reasoning models are too slow for a conversation.
* Restrict `platform_toolsets.ha_voice` to what you need. Web search is slow; prefer pre-computed Home Assistant sensors (for example a weather forecast template sensor) and tell the bot in `SOUL.md` which entity to read.
* Keep tool-progress and interim messages off for the platform (see [installation.md](installation.md#12-profile-config-profileconfigyaml)); they are not spoken but they cost time and tokens.
* The first request after a gateway restart is slower. Send a warm-up request from an automation after Hermes restarts if that bothers you.

## Text-to-speech

* Match TTS language/voice to the bot's language. Some engines need a full locale (for example `nl-NL`, not `nl`).
* Very long answers make TTS slow; the persona rules above are the best fix.
