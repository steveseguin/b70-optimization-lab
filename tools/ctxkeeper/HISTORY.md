# ctxkeeper: how it got here

The build-by-build record behind version 1.0.0, kept as it was written while the proxy was measured (2026-10-11 to
2026-10-12; the later campaigns are in the lab note). For using the proxy, read [README.md](README.md).

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
(`sync_notesdelta.py` checks or renews the copy).

As this proxy (campaign 11, a plain agent that sends its whole history, `--notes-checks near`): 39/39 in 10 minutes
and 46/46 in 13 on the two 240K streams, against 39 in 17 and 44 in 18 for the full rewrite, with no value wrong in
any saved NOTES version (`proxy_notes_audit.py`). Its first run on the second stream scored 40/46: an asked-for
second reply had replaced the first and lost nine items' changes; replies are merged now, and every notes reply is
written to `events.jsonl`.

On the 1M-token stream the same build scored **216/228 in 76 minutes**: below the full rewrite's 222 (in 95) and
below the bar set for it (220 in under 70). Six answers were blank because the searches of one turn were lost when
that turn ended with an empty reply; six were questions about a numbered item, answered from search hits that
showed message numbers only; two NOTES values were wrong for a while (a value set in words, written as made-up
working that added up). What changed after that run:

- A search hit shows the first line of its message (`message 105 (tool, "ITEM 50/617 (UPDATE)"): ...`), so a
  sentence can be placed by item, file or command.
- The searches of a turn that ended with nothing for the client are shown once more in the next request (only to a
  history that continues the one they were made in, and only as far as the window has room). An empty reply is
  asked for once more with thinking off before it is handed to the client.
- `--max-recalls N` (8). A search result is cut to the room left beside the reply; once there is none, no further
  search is made in that turn.
- `--notes-scan REGEX`: with `--notes-checks`, only tool results and user messages that match are read as facts
  (so a question that names a thing is not counted as a mention of it).
- The checks follow a line that packs several changes part by part (`opened at 117, set to -190, +46 = -144`),
  take a line that repeats a change noted at the last call as no change, and (with `near`) want every amount in a
  line's working to be stated for that thing. On the saved replies of that run this would have asked again 9 times
  instead of 33.

With these (campaign 12, build X32n2): **39/39 in 8.8 minutes and 46/46 in 9.7 at 240K** (the harness arm it was
built from: 9.9 and 10.0), no value wrong in any saved NOTES version, and **220/228 on the 1M-token stream in 53
minutes** (the bar was 220 in under 70; the harness arm: 228 in 50). Of 53 minutes, 15 are the server reading (the
1.06M-token stream once, and 1.4M tokens more in turns re-read after cuts, search results and notes calls), 31 are
the server writing (119K tokens of notes, 43K in the agent's own turns, 29K in search rounds), the proxy itself adds
24 seconds, and the client and its shell commands the rest.

Seven of that run's eight misses were one confusion: `recall` counted messages, the task counts items, and a search
"before 332" meant as item 332 stopped at message 332. Hence:

- `--recall-label REGEX` (first group: the content's own number, for example `'(?m)^ITEM (\d+)/'`) and
  `--recall-unit WORD` (what that number counts, default `item`): `recall` then shows and takes that number and
  nothing else. Without the option it counts archived messages, as before.
- When there are more matches than fit, the ones nearest to where the search was anchored are shown (`before`: the
  last ones before it; `after`: the first ones after it; neither: the newest) and the line that says how many were
  left out comes first.
- A notes line for a name that the noted turns never mention, a letter or two from a mentioned name that has no
  line, is taken as that name misspelled.

With `--recall-label` (build X32p): **39/39 in 8.5 minutes, 46/46 in 9.4, and 226/228 on the 1M-token stream in 50
minutes**, every earlier-value question right, with fewer searches (112 against 161). After that run two more
things were changed and have not been run yet: a question that arrived in a tool result and is still open is never
cut out of view (it is shown after NOTES until a message matching `--think-until` closes it), and a notes line is
left out only when the turns contradict its number, never because the checker could not follow how it was written.

## Limits

- Measured on one synthetic task family, one model and one machine. As a harness policy: 39/39 and 46/46 at 240K,
  226/228 on a 1M-token stream. As this proxy, with a plain agent that sends its whole history: 37/39 and 42/46 at
  240K on its first two runs against the real server; the second exposed a defect in the notes call (fixed, not yet
  re-run; after the fixes 39/39, 44/46 and 222/228 on the 1M stream in 95 minutes; with in-place notes 39/39 in 9
  minutes, 46/46 in 9 and 226/228 in 50, see above). Not yet run under a real coding or research agent. Tests against a scripted model: `python3 -m unittest test_ctxkeeper test_notesdelta`.
- Token counts are characters over a ratio learned from the server's `usage.prompt_tokens`, with margins. A server
  that reports no usage keeps the starting guess of 3.6 characters per token.
- `recall` is a text and regular-expression search over archived sentences with message numbers: it answers "what
  was said". For "what was true at message N" every saved version of NOTES is kept, and `recall` with `notes_at`
  returns the one saved at or before N; what happened between that save and N still has to be read from the archive.
- If the model answers with `recall` and one of the client's tools in the same turn, the client's call is passed on
  and the recall is dropped. A turn gets at most `--max-recalls` searches (8) and no more than fit the window;
  after that the model is asked once more without the tool, and the client is never handed a `recall` call.
- A value set in words can still be noted as a change by the same number ("recorded at sixty-four" as `208 - 64 =
  144`), and a change can be noted with the wrong sign ("+35" as `-46 - 35 = -81`): the working adds up and the
  amount is in the sentence, so no check sees it. One such line in 77 notes calls at 1M, and one in 76.
- One choice per request (`n` = 1). A conversation is recognised as the same one by what was said (roles, text, tool
  calls), not by thinking the client may have dropped or by how text parts were split.
