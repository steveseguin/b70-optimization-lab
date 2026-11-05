# Pi client for the four-card LAN server

Use this profile on the computer running Pi. Merge the `sc117` provider from
[models.json](models.json) into `~/.pi/agent/models.json`, and merge the desired
values from [settings.json](settings.json) into `~/.pi/agent/settings.json`.
Preserve other providers and personal settings. In Pi, open `/model` to reload
the model file, select the plain SC117 model, then choose `/thinking medium`.
Resumed sessions can retain their previous model and thinking level.

This profile targets the plain model on `192.168.2.44:18160`, with 131072 tokens
shared between input and output. Automatic compaction is enabled with 16384
tokens reserved and 20000 recent tokens retained. It advertises no keeper
model or unlimited context. The older two-card keeper profile is a different
service and must not be used for this endpoint.

Thinking defaults to medium and remains visible. The profile sends
`reasoning_effort` explicitly: low and medium keep their meaning; high, xhigh
and max select the template's xhigh mode. Off sends none. The old
`qwen-chat-template` toggle alone omitted effort and selected the template's
xhigh default. Responses stream thinking as `reasoning_content`, which Pi
recognizes. Both reasoning and the final answer consume the 8192-token output
budget. Low thinking is available when latency matters more.

The four-card service reuses its live prompt state when the next request has
an exactly matching token prefix. This passed full-state correctness checks
and real Pi tool turns. A different session or a changed earlier prefix requires
a fresh prompt read; large new tool results still take time to read. Automatic
Pi compaction reduces context growth. Native ctxkeeper and parked sessions remain
disabled; this profile does not claim their features.
Tool calls are sent once their complete arguments are available, while ordinary
answer text and reasoning stream incrementally. Images, forced tool choice and
non-greedy sampling are not supported. The dummy key is for an endpoint with
authentication disabled; supply your actual key locally if authentication is
enabled. No real credential belongs in this repository.

Schema and request mapping checked against Pi v1.2.0's official
[model schema](https://github.com/badlogic/pi-mono/blob/v1.2.0/packages/coding-agent/schemas/models.schema.json),
[OpenAI completion adapter](https://github.com/badlogic/pi-mono/blob/v1.2.0/packages/ai/src/api/openai-completions.ts)
and [settings reference](https://github.com/badlogic/pi-mono/blob/v1.2.0/packages/coding-agent/docs/settings.md).
The version installed on the other computer has not been inspected.
