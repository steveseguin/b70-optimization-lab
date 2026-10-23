# Runtime checkpoint integration review — 2026-10-21

Reviewed packet179 at `4250d39dc4c1` against the session-swap design update
`beded0544`. This is a read-only source review, not a device qualification.
The sealed packet and its active window are unchanged. ctxkeeper's journal
supports text recovery; it does not invoke runtime checkpoint operations.

## What the implementation currently exposes

- Native CLI flags: `--checkpoint-save DIR --checkpoint-id ID` and
  `--checkpoint-restore DIR --checkpoint-id ID`, alongside the existing
  admitted runtime arguments and input token file.
- `--checkpoint-inspect CHECKPOINT_DIRECTORY` and
  `--checkpoint-delete CHECKPOINT_DIRECTORY` dispatch before model/device
  initialization. They are native process operations, not HTTP endpoints.
- Save records the processed prefix as the original prompt plus generated
  tokens **except the last generated token**. That last token is saved as
  `next_token` and has not yet been processed by the model.
- Restore verifies the original prompt, restores the processed state, then
  steps the pending token and continues the same generation.

Sources: [checkpoint.hpp](../../experiments/own-xpu-runtime/stage2/packet179-session-swap/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native/checkpoint.hpp)
and [main.cpp](../../experiments/own-xpu-runtime/stage2/packet179-session-swap/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native/main.cpp).
Line numbers below refer to the reviewed commit, not a later amended packet.

## Gaps to resolve before connecting ctxkeeper

1. **New conversation turns are not yet supported by restore.**
   `checkpoint.hpp:229–232` requires the supplied input length to equal the
   original `prompt_length`, and compares only that original prompt against
   the saved tokens. `main.cpp:2115–2132` resumes decoding from the stored
   pending token; there is no appended-input prefill path. This can prove
   interrupted-generation resumption, but not the contract's general
   exact-prefix-plus-delta continuation. Add a separately specified/tested
   append operation, or narrow the contract until that operation exists.

2. **Restore metadata has two inconsistent sources of truth.**
   `checkpoint.hpp:202–211` reads `fields.tsv` and verifies its stated hash
   of `manifest.json`. Later, line 280 uses `history0/history1` from the TSV
   without comparing them with the JSON's `token_history`. Changing one of
   those TSV values leaves the JSON and blob hashes unchanged. This is a
   metadata-integrity gap even without a malicious writer. Prefer one
   authoritative parsed manifest, or explicitly cross-check all duplicated
   semantic fields. Add a negative test that changes only a TSV host-state
   value and requires refusal before any device upload.

3. **Deletion and restoration need shared atomic locking.**
   Restore reads metadata and all blobs before exclusively creating
   `restore.lock` (line 267). Delete checks whether that file exists and
   then calls `remove_all` (lines 287–290). These are separate operations:
   delete can pass its check before restore creates the lock, then remove
   the directory while restore holds it. Use a common atomic lock protocol
   outside the directory being removed and acquire it before reads/deletion.
   The delete CLI also accepts an arbitrary directory with no checkpoint
   validation; do not expose it through a user-facing adapter as written.

4. **Inspect's transport and cost differ from the conceptual contract.**
   Lines 293–302 emit the manifest followed by per-blob JSON records and a
   final status record. Inspect reads and hashes every blob, and writes
   the manifest before verification completes. A caller must check exit
   status and the final result; parsing stdout as one JSON object will fail.
   Specify this JSON-lines contract or provide a single-result mode, and
   distinguish cheap metadata listing from full payload verification.

5. **Repeated parking needs a restore-then-save operation.**
   `main.cpp:291` makes save and restore modes mutually exclusive. The
   current invocation cannot restore a session, advance it and checkpoint
   the resulting state again. Qualify that lifecycle alongside appended
   conversation turns; do not assume the first interrupted-generation test
   covers repeated parking.

These findings do not require cancelling the current restart-and-continue
measurement. Preserve that packet's evidence and scope. Fixes that change
sealed source/binary identities need the runtime owner's next qualified
revision, not edits to a packet currently under test.

## Handoff to the runtime owner

The first GPU result should be labeled **same-generation save/restart/resume**.
For the next integration contract, specify a continuation operation that accepts
an exact saved token prefix plus new input, the pending-token semantics, a
tokenizer/template identity, and the process/API transport and error schema.
Provide a safe inspect/delete protocol and metadata-integrity tests above.
ctxkeeper will keep its normal notes placement and use text replay on misses;
it will not append stale or revised notes just to preserve a cache hit.

Model identity in this packet uses host-local shard stat pins. Moving or
reinstalling the same model files can invalidate those pins; this is not a
portable model-content identity. Complete textual conversation backups remain
independent of that runtime compatibility decision.

The proposed ownrt TP1 clean-host replay cannot run on TURIND8 at the published
configuration: its [reproduction guide](../../repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/README.md)
requires 98,990,252,032 bytes available host RAM, while TURIND8 has 15 GiB total.
Keep that portability item open pending suitable hardware; do not weaken admission.

## Update 2026-10-22: the device gate passed

The four-card host ran packet179 row B on device (lane A, `lanequeue-A34`, engine
`064452363` after an in-packet pin-closure repair): save at K=256, two
fresh-process restores decoding M=128 each, merged stream equal to the
uninterrupted reference at [0:384), repeat restores identical, oracle-128 exact;
save 1.10 s / 68.8 MB, restore 0.46 s against a 36.75 s cold prefix. Receipts
at `8bf76113f`. This qualifies **same-generation save/restart/resume** only; the
five gaps above (appended turns, restore-then-save, one manifest source of truth,
shared locking, inspect modes) are the next engine work and ctxkeeper still does
not call the checkpoint operations. The manifest label stays `experimental`.

## Update 2026-10-22, 15:29 EDT: the five gaps are closed on device; what the adapter needs now

packet180 (append, restore-then-save, one manifest source, shared lock, inspect modes; lifecycle row 36/36 on device)
and packet181 (`qualified-one-card` label, `contract: v1.2+p181`, packet180 read compatibility, prompt-path record;
43/43) close every item of the review above. The contract's status block carries the details and sources. The
append rule for an integrator: `--input` = the saved processed history + the pending token + the new tokens; the
engine refuses unless the saved part matches token for token; the appended tokens run at the warm per-position
rate in a long-running process (the 22.7 tok/s seen on device was a fresh process's cold expert cache).

**The adapter, with ownership.** ctxkeeper is an HTTP proxy that speaks OpenAI chat completions to a server; the
engine is a bounded native process that takes token ids. Three pieces are needed, two of them not ctxkeeper's:

1. *Runtime (four-card host):* a request front for the engine that accepts a chat request (messages, or already
   rendered token ids) and returns a completion, holding the process warm between requests, with the four
   checkpoint operations as calls on that front and `inspect` cheap. Without it there is nothing for a proxy to
   address. TP2 is out of scope for v1.
2. *Integrator, first deliverable, CPU only:* a rendering-parity harness. ctxkeeper deals in messages; a checkpoint
   is valid only for an exact token prefix. The harness renders a message list with the pinned chat template and
   tokenizer (`one-card/tokenizer-identity.tsv`: GGUF shard-1 header incl. the template, `tokenizer.py`) and must
   reproduce the engine's reference prompt ids exactly for the recorded packet prompts; a JSON message hash is not
   a token-prefix hash (CONVERSATIONS.md). Inputs needed from the runtime owner: the pinned tokenizer files and
   three recorded (messages, token ids) pairs from the sealed profile.
3. *Integrator, after 1 and 2:* the parking policy in ctxkeeper (which sessions to park at a cut, when, eviction),
   addressing checkpoints by id, consuming `inspect` metadata, and the rule that a note edit or any change inside
   the saved prefix re-prefills rather than restores. The conversation journal of 1.3.0 is the text side of this
   and stays independent of the runtime's compatibility decisions.

Until piece 1 exists, ctxkeeper does not call the checkpoint operations; this review's boundary stands.

## Step 1 of the parity harness done, 15:31 EDT: text to the exact token prefix, 12/12

`experiments/own-xpu-runtime/integration/render_parity.py` loads the pinned oracle tokenizer
(`packet2-cpu-oracle/tokenizer.py`, sha256 `1c284c06b6a159c3…` = the pin in the packets'
tokenizer-identity.tsv) with the vocabulary and merges of this host's `qwen3.8-27b-fp8/tokenizer.json`
(sha256 `0997f410c57a1f4e…`, since the GGUF shards are on the other host), encodes each of the
12 sealed suite prompts (texts matching their recorded sha256) and compares with the token lists the sealed
profile recorded against the GGUF header: **12/12 identical**, receipt
`experiments/own-xpu-runtime/integration/receipts/render-parity-20261022.json`. So the token-prefix side of a
checkpoint can be reproduced on this host from text. Run it from a Python with the `regex` module (the oracle
tokenizer imports it); the system Python here has none.

Step 2, messages to that text, needs one input from the runtime owner: the chat template exactly as the GGUF
header carries it (`tokenizer.chat_template`, inside the pinned header sha256 `7c1460a9…`), or its sha256 so the
Hugging Face `tokenizer_config.json` template here can be checked against it. Until then the harness covers
already-rendered text only, and ctxkeeper still does not call the checkpoint operations.

## Step 2 done, 2026-10-22 23:29 EDT: messages to that text, 12/12, from the pinned header itself

The input did not need the other host after all: GGUF shard 1 of the runtime's model is only 10.9 MB and is
almost entirely header, so it was fetched from the publisher at the pinned revision (`766911a6`), checked
(whole-file sha256 `268f81fd…` and header sha256 `7c1460a9…` both equal to the admission receipt's), and
`tokenizer.chat_template` was read out of it (2026-10-22 EDT): 9,993 characters, sha256 `12827f24…`, which is exactly the
`template_sha256` the sealed prompt manifest (`packet2-cpu-oracle/prompts/prompts.json`) pins. The text is saved
as `experiments/own-xpu-runtime/integration/chat_template-7c1460a9.jinja`.

**The Hugging Face copy on this host was the wrong template.** `stage1/packet1/metadata/tokenizer_config.json`
(8,952 characters, sha256 `c3cf9e34…`) differs from the header's: the header's version merges every leading
`system` or `developer` message into one system block (joined with newlines), renders `developer` as `system`,
and maps reasoning effort `high` to `xhigh`. Checking the two by sha256, as the previous section proposed, would
have failed, and an adapter built on the HF copy would have rendered a different prefix for any request with a
developer message or more than one system message. That is the reason the step existed.

`experiments/own-xpu-runtime/integration/template_parity.py` renders the suite's 12 raw prompts with the saved
template the way the sealed files were made (jinja2 `ImmutableSandboxedEnvironment`, one user message,
`add_generation_prompt`, thinking off) and compares bytes with the sealed files: **12/12 identical**, from the
saved copy and again straight from the shard header (`--gguf`), receipt
`integration/receipts/template-parity-20261023.json`. The receipt also records the rendering of four message
shapes ctxkeeper sends, as the fixtures an adapter is checked against:

| Shape | Rendered as |
| --- | --- |
| system + user | `<\|im_start\|>system\n…<\|im_end\|>\n<\|im_start\|>user\n…<\|im_end\|>\n<\|im_start\|>assistant\n<think>\n\n</think>\n\n` |
| two turns (user, assistant, user) | the earlier assistant turn is rendered **with an empty think block before its text** (`<think>\n\n</think>\n\nBlue.`), so a reply stored in history must be re-rendered this way, not as the raw text the client saw |
| two system messages | one system block, contents joined with a newline |
| developer + user | the developer message becomes the system block |

Step 1 was also re-run with the vocabulary, merges and token types read from the same header
(`render_parity.py --gguf`, header pin checked): **12/12 identical**, receipt
`integration/receipts/render-parity-gguf-20261023.json`. The HF `tokenizer.json` stand-in is no longer part of the
evidence. Both steps together: messages → text → the exact token prefix a checkpoint is valid for, reproducible on
this host from the pinned header alone. Nothing on the parity side is open; the adapter's parking policy in
ctxkeeper is next.


## Step 3 done, 2026-10-22 23:35 EDT: prompt + generated ids is the next turn's prefix, 50/60 exact; the 10 misses are one trimmed tail token

A parked session's checkpoint holds the engine's token history, the prompt ids followed by the ids it generated.
The next request is rendered from messages, so a restore needs that history to be an exact prefix of the new
rendering. `experiments/own-xpu-runtime/integration/continuation_parity.py` checks it on every one-card device
run that recorded generated ids (packets 178, 179, 180, 181: five runs, 12 prompts each, fixed 512-token greedy
generations): decode the generated ids with the pinned tokenizer and the header vocabulary, render
[user: raw prompt, assistant: decoded reply, user: "Continue."] with the pinned template, tokenize, compare.
Receipt `integration/receipts/continuation-parity-20261023.json`.

- **50/60 requests exact; 29,905 of 29,915 generated ids reproduced in place.** Re-tokenizing the decoded reply
  gives the generated ids back everywhere, and the template's stored-assistant rendering (`<think>\n\n</think>\n\n`
  + content) matches the opener the engine generated after.
- **The 10 misses are two prompts (release-plan, technical-guide) in all five runs, each losing exactly the last
  generated id:** a `\n` or `\n\n` token at the cut-off point of the 512-token generation, which the template's
  `|trim` on stored assistant content removes. A fixed-length generation ends mid-text, so this is the
  cut-off artefact of the measurement, not a property of finished replies.
- **Finished replies on the agent stream:** of the 2,580 assistant messages the client re-sent as history in
  campaign 55 (both seeds), 0 end or start with whitespace. The raw engine output is not logged there, so a
  reply that the engine ended with whitespace before `<|im_end|>` and the client stripped is not excluded by this
  count; such a reply re-prefills under the policy below (the saved history would not be a prefix), it never
  restores wrongly.

Parity is therefore closed for the one-card runtime at this template and tokenizer: messages → text → ids
(steps 1 and 2), and ids held by the engine → the next request's prefix (step 3), all reproducible on this host
from the pinned header. Whitespace at the end of a reply is the one known way the prefix breaks, and it costs a
re-prefill, not an error.

## Piece 3 built, 2026-10-22 23:35 EDT: the parking policy, CPU-tested, not yet wired into the request path

`tools/ctxkeeper/parking.py` (stdlib, 13 tests in `test_parking.py`) is ctxkeeper's side of §9 of the contract,
behind an `Engine` interface that mirrors the four operations plus the running engine's identity, so the
four-card host's request front can be dropped in when it exists. What it fixes:

- **Identity by token prefix.** A parked session's checkpoint id is derived from the sha256 of its token ids
  (rendered with the pinned template, tokenized with the pinned tokenizer; both injected), never from the JSON
  messages. Two message lists that render to the same tokens share an id; the same JSON under a different
  template does not.
- **Before a request:** `inspect` the session's checkpoint (no device), check model identity, engine identity
  and the qualified label against the running engine, then check that the saved history is an exact prefix of
  the new rendering (length and `tokens_sha256`). Only then `restore` and append the delta. Any other case,
  including a notes cut or edit inside the saved prefix, a shorter prompt or a trimmed reply tail, is a
  **prefill** with the named reason, and the stale checkpoint is deleted. There is no approximate restore.
- **Parking:** one checkpoint per session, saved at the end of a turn as prompt ids + generated ids; a re-park
  of the same prefix saves nothing; the earlier checkpoint is deleted after the new one is visible.
- **Eviction:** the total parked bytes (from the manifests' blob sizes, which `inspect` provides) stay under a
  budget by deleting the least recently used sessions' checkpoints; the session just parked is never evicted;
  a checkpoint the runtime reports `in_use` is skipped and, if it was being dropped, retried on the next pass.
- `FakeEngine` models the contract's fail-closed semantics (identity checks, exact prefix extension, `in_use`
  on delete during a restore) so the tests exercise the policy against the same refusals the engine gives.

The boundary stands: ctxkeeper's request path does not call these operations; CONVERSATIONS.md's journal is
unchanged. Wiring needs piece 1 (the request front) and, for the two-card lane, the TP2 decision of §10.

## Update 2026-10-23: native postreply front and host adapter integration passed; HTTP remains unwired

The native request front now exists. Packet197 retained one owner across eight
requests; packet198 added protocol-v2 postreply SAVE/RELEASE. The
[packet198 device audit](../../experiments/own-xpu-runtime/stage2/packet198-postreply-checkpoint/evidence/independent-device-result.json)
verified eight requests, 1,408 exact generated tokens and five checkpoint states
against packet197, followed by clean drain. Its label remains
`experimental-postreply-front`, contract `v1.2+p198`; this does not inherit p181's
qualified label or authorize HTTP serving.

The CPU integration pieces now include a
[locked native snapshot/delete store](../../experiments/own-xpu-runtime/integration/native_checkpoint_store.py),
explicit p198 admission in the
[identity bridge](../../experiments/own-xpu-runtime/integration/checkpoint_bridge.py),
and an [attached-owner adapter](../../experiments/own-xpu-runtime/integration/CHECKPOINT-ENGINE.md).
Parking now has 25 focused CPU tests. It admits experimental contracts only by
explicit trusted `(label, contract)` configuration, validates native-safe IDs,
reserves trusted peak SAVE bytes before writing, counts detached in-use and
ambiguous states, and reinspects same-ID shortcuts. It does not silently relabel
checkpoints. A normal no-save or same-ID hit releases the pending reply; ambiguous
failures halt adapter intake without automatic retry or owner restart.

The actual front, store, bridge, Parking and adapter together passed a separate
[tiny GNU HOST_ONLY integration probe](../../experiments/own-xpu-runtime/integration/receipts/checkpoint-engine-host-b-closeout.json):
context64/vocab16, one model load, eight requests, 44 generated tokens, five saves,
three releases and clean stopped. Appended restore matched fresh tokens and
state exactly; edited-prefix prefill and same-ID release passed. The first
attempt's empty identity TSV failed SAVE's three-row requirement; its evidence
was retained before the corrected synthetic fixture passed in a fresh output.
The [six-section closeout](../../experiments/own-xpu-runtime/notes/2026-10-23-checkpoint-engine-host-closeout.md)
records exact identities, evidence, limitations and replay conditions.

These are distinct proofs: the fixed native worker has the packet198 device
lifecycle result, while the complete policy/adapter path has tiny-host
integration evidence. **ctxkeeper's HTTP request path still does not call these
operations.** No HTTP endpoint, release bump, real-model adapter serving
qualification or speed claim was introduced. The next integration boundary must
retain tokenizer/template identity, exact-prefix fallback, bounded requests,
cancellation and the admitted persistent owner's fault/drain rules. TP2 remains
outside this one-card path.
