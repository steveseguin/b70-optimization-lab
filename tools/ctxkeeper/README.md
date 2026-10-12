# ctxkeeper

A small OpenAI-compatible proxy that lets an agent work on one task far past the model's live window without losing
what it was told. Standard library only; it sits between any client and the model server.

```
agent / client  --->  ctxkeeper (:18200)  --->  model server (:18196)
```

The client keeps sending its whole history. The proxy shows the model a bounded view of it:

```
[system messages] [first user message]  [NOTES, kept by the proxy]  [the recent turns, verbatim]
```

When the view would outgrow the window, the oldest turns are cut. Before they go the proxy writes them verbatim to an
archive on disk, asks the model once (no tools) to rewrite its NOTES from the old notes and the turns being cut, and
puts the notes where the cut turns were. NOTES has three parts: RULES (standing rules and methods; a rule the model
drops is put back), STATE (what later work depends on) and OPEN. The model gets one extra tool, `recall`, which the
proxy answers from the archive without the client seeing it, and the RULES are repeated after each new user message.

Nothing about the model's arithmetic changes. Only what it is shown changes, and what is not shown is kept and
searchable.

## Why this shape

It is the policy measured as arm N32j in
[`experiments/qwen38-27b-b70/notes/2026-10-10-context-16k-baseline.md`](../../experiments/qwen38-27b-b70/notes/2026-10-10-context-16k-baseline.md)
on Qwen3.8-27B FP8 with a 32K live window and a 240K-token task: 39/39 and 46/46 on two streams that plant a
standing rule and a method at the start and ask about them, and about old and current values and small details, up
to 130 items later. A plain sliding window scored 23/39 on the first of those; the best method that makes the agent
manage its own context scored 35/39 with twice the model calls. Three things in that record shaped the code:

- A rule needs a place that is never cut **and** a reminder where it is used. With neither, no method kept a rule
  stated at the start (0 of 20 questions across four methods).
- The request for notes must come **after** the turns being cut. Asked first, the model reads 8K tokens of its own
  turns last and writes one more of them instead of notes.
- The cut must happen while there is still room for the next large message, or that message arrives truncated.

## Use

```bash
python3 tools/ctxkeeper/ctxkeeper.py --upstream http://127.0.0.1:18196 --port 18200 --budget 32768
# then point the client at http://127.0.0.1:18200/v1
```

- `--budget` is the live window in tokens, reply included; `--reply-reserve` (4096) is the room kept for the reply.
  Decoding slows as the live context grows (on two B70s about 90 tok/s under 30K, 41 at 137K, 26 at 246K), so a small
  window with notes and an archive is both faster and, in the measurements above, more accurate than a full one.
- Turn off the client's own compaction or truncation and let it send everything: a history that no longer contains
  what the proxy archived is treated as a new conversation (notes start over; the old archive is set aside).
- One conversation is recognised by its model name, system messages and first user message, or by the header
  `X-Ctx-Session`. State is under `--state-dir` (default `~/.cache/ctxkeeper/<key>/`): `archive.jsonl`, `state.json`.
- `GET /ctxkeeper/status` shows cuts, recalls, rules put back and the token ratio learned from the server. A notes
  call whose reply is empty, too long or not in the RULES / STATE layout is asked for once more (without thinking, and
  with the correction); each rejection and its reason is written to `events.jsonl` in the conversation's folder.
- `--notes-thinking on|off|unset` sets `chat_template_kwargs.enable_thinking` for the notes call (a vLLM/Qwen
  field; `unset` sends nothing). Thinking notes were the measured setting.
- The proxy adds a short Memory paragraph to the system message (always the same text) so the model knows about
  NOTES and `recall`; `--no-memory-note` leaves the system message alone.
- Two optional settings for tasks where questions arrive in tool results rather than from the user, or where thinking
  on every call is too slow: `--recite-when REGEX` also repeats the RULES when the newest message matches, and
  `--think-when REGEX` turns thinking on only for a user message or a matching newest message (with `--effort medium`
  on Qwen, so that switching thinking does not change the system message and the prefix cache survives).
- Streaming clients get the finished reply as one server-sent event (the proxy has to see whether the model called
  `recall` before anything is sent on).

## In-place notes (`--notes-mode inplace`)

The first form above reads the cut turns a second time (as text in the notes call), rewrites the whole NOTES each
time, and reads the kept turns again at their new place after every cut. In the lab's 1M-token run that was half the
time. In-place notes avoid all three:

- When the turns before the newest exchange hold more than `--inplace-tokens` (15,000), the notes call is **the
  request the server has just read, plus one message** (same tool list, `tool_choice` none), so the server's prefix
  cache serves nearly all of it.
- The reply is **only what changed**: `NEW RULES`, `CHANGES` (one `name: value` line per fact, with the working when
  a value follows from the old one: `stock: 120 + 49 = 169`), `OPEN`. The proxy applies it: a line not mentioned is
  kept, a sum is recomputed, working must start from the value held. A reply that fails a check is asked for once
  more with the lines named; rules named in either reply are kept.
- Then **every turn it covered is moved out**. The view is the opening messages, NOTES and the newest exchange
  (the assistant's last tool calls with their results, or the newest user message). Nothing is read back.
- Two things stay in view on purpose: a question that arrived in a tool result and is still open (with
  `--think-when` / `--think-until`; no in-place cut is made until it is closed), and the latest user message if it
  has been moved out while the model is still working on it.
- If an in-place attempt fails (no usable reply twice), nothing changes and the ordinary cut handles those turns
  when the window fills. A cut is all or nothing: if saving it fails, the state is as before and the archive takes
  no message twice when the cut is made again.
- The cache only helps if the start of the prompt is the same in the notes call as in the call before it. On Qwen
  pass `--effort medium` (as for `--think-when`): without it, thinking in the notes call changes the system message
  and the server reads the whole request again. The notes are still right; the call is just slower.
- `--notes-checks count|near` adds two checks for ledger-like state whose things have names like `abcd12`: every
  mention of such a name in the noted turns must be accounted for by a change (or a `name: (no change)` line), and
  a value written without working must be one the turns state (`near`: in a sentence that names the thing, or the
  next one). Leave it `off` for ordinary agent work: tool output is full of such words that are not state.

Measured in the test harness (the same policy inside the lab's agent harness, lab note campaigns 10 and 10b):
39/39 and 46/46 at 240K in 10 minutes against 16 for the full rewrite, and 228/228 on the 1M-token stream in 50
minutes against 226/228 in 83, with NOTES that an audit against the true ledger found right in all 63 versions at
1M. `notesdelta.py` holds the parsing, applying and checks; its core is copied unchanged from that harness
(`sync_notesdelta.py` checks or renews the copy). As this proxy it has its unit tests and a scripted end-to-end run;
see Limits for what has been run against the real server.

## Limits

- Measured on one synthetic task family, one model and one machine. As a harness policy: 39/39 and 46/46 at 240K,
  226/228 on a 1M-token stream. As this proxy, with a plain agent that sends its whole history: 37/39 and 42/46 at
  240K on its first two runs against the real server; the second exposed a defect in the notes call (fixed, not yet
  re-run; after the fixes 39/39, 44/46 and 222/228 on the 1M stream in 95 minutes). Not yet run under a real coding
  or research agent. Tests against a scripted model: `python3 -m unittest test_ctxkeeper test_notesdelta`.
- Token counts are characters over a ratio learned from the server's `usage.prompt_tokens`, with margins. A server
  that reports no usage keeps the starting guess of 3.6 characters per token.
- `recall` is a text and regular-expression search over archived sentences with message numbers: it answers "what
  was said". For "what was true at message N" every saved version of NOTES is kept, and `recall` with `notes_at`
  returns the one saved at or before N; what happened between that save and N still has to be read from the archive.
- If the model answers with `recall` and one of the client's tools in the same turn, the client's call is passed on
  and the recall is dropped. A turn gets at most eight searches; after that the model is asked once more without
  the tool, and the client is never handed a `recall` call.
- One choice per request (`n` = 1). A conversation is recognised as the same one by what was said (roles, text, tool
  calls), not by thinking the client may have dropped or by how text parts were split.
