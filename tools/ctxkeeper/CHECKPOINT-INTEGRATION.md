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
