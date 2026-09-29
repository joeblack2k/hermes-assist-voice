# Browser and computer access

The voice bot is a normal Hermes profile, so it can do anything Hermes can do for that profile. "Which tabs are open in my browser?" or "log in on the laptop and check X" is a matter of enabling the right toolsets, not of changing this project.

## Enable the tools

Add the toolsets you want to `platform_toolsets.ha_voice`, for example:

```yaml
platform_toolsets:
  ha_voice:
    - homeassistant
    - memory
    - session_search
    - web
    - terminal        # run commands, e.g. inspect a browser on a Linux desktop
    - browser         # Hermes' own browser tools
```

For a dedicated Mac (or any machine driven through accessibility APIs) register a computer-control MCP server in the profile:

```yaml
mcp_servers:
  computer:
    enabled: true
    command: ssh
    args: ["-i", "<key>", "<user>@<host>", "<mcp-binary>"]
```

Use a machine that is meant to be controlled by agents. Give the bot its own OS user, and do not expose a machine that holds data you would not hand to the agent.

## Tell the bot how to use it (`SOUL.md`)

Put short instructions in the profile persona: which machine has which browser, which route is fastest, and that it must announce steps out loud. Example:

```markdown
## Browser and computer
- Open tabs on the Mac: read them with the computer tool or AppleScript; on the Linux desktop use the browser's remote-debugging port or the desktop tools.
- Prefer the fastest route that gives a real answer. Never guess tab titles.

## Progress steps
Before every tool call that takes more than a couple of seconds, write one short spoken sentence ("I'm looking at your browser."). Report milestones ("I'm logged in on the laptop."). No tool names, paths or IDs. Finish with the answer in one to three sentences.
```

## macOS privacy prompts

macOS asks for permission the first time a process controls another app (Automation), reads the screen or uses the microphone. These prompts ignore synthetic mouse and keyboard events, so they must be approved once, either physically or through an accessibility-based click (for example the `click` action of your computer-control MCP server on the system dialog). Until they are approved, scripted commands such as `osascript` appear to hang. Approve them once on the agent machine and they stay approved.

## Why long tasks stay pleasant

Browser and computer tasks can take a minute or more. With `interim_assistant_messages: true` and the progress-step instruction above, the satellite speaks each step while the agent works, so there are no long silences. See [api.md](api.md) for how the steps travel from Hermes to the speaker.
