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
