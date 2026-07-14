# Exact-Q4 DFlash Target-Trace Hook Blueprint

Date: 2026-07-13

Status: the parser, collector control plane, binary ABI, native runtime hook,
and synthetic/native ABI tests are implemented. A real-model capture is still
pending a frozen full dirty-tree fingerprint and a matching rebuild; no corpus
or adaptation result is claimed yet.

## Outcome

The missing Q4 adaptation corpus now has a source-ready capture contract. It
records the exact five target layer-input vectors consumed by native DFlash,
the linear greedy target token stream, and enough immutable identity to reject
a trace from a different model or runtime. The resulting parser emits the
existing `qwen36_eagle_sequence_v2` subset required by the offline trainer and
supports the intended five-draft-token, width-six (`B=6`)
`layer-position-bias` screen.

This does not claim that a corpus has been captured or trained. Capture must
wait until the active llama.cpp kernel work settles: applying the hook changes
the dirty-tree checksum, so the capture plan and compile-time runtime identity
must be regenerated from the exact final source snapshot before any request is
accepted.

## Exact Native Hook Points

The line numbers below refer to llama.cpp commit
`e3546c7948e3af463d0b401e6421d5a4c2faf565`; use function names when the dirty
tree moves.

1. `common/speculative.cpp`, `common_speculative_impl` near line 226:
   add an optional `virtual void end(llama_seq_id, bool complete) {}`. Other
   speculative implementations remain unchanged.
2. `common/speculative.cpp`, `common_speculative_impl_draft_dflash` near line
   967: own the trace session, per-sequence provisional state, one pending row,
   BF16 conversion chunks, and bounded writer. Constructor validation belongs
   here because it already has `n_seq`, DFlash parameters, target layer IDs,
   target hidden size, and both contexts.
3. The same class constructor near lines 995-1085: enable only when
   `LLAMA_DFLASH_TARGET_TRACE_CAPTURE_DIR` is nonempty and every fixed contract
   field matches: `n_seq=1`, `n_max=0`, `n_min=0`, `p_min=0`, hidden size 5120,
   and target layer IDs `[2,17,32,47,62]`. Write the session manifest only after
   launcher-supplied model hashes and compile-time runtime identities pass.
4. `common_speculative_impl_draft_dflash::process()` near lines 1113-1190:
   after the existing gather into `features_buf` and before `llama_encode`,
   synchronously convert the gathered F32 rows to an owned BF16 chunk. Pair
   each row with `batch_in.token`, position, sequence ID, and prompt/generated
   state. This uses the exact data already consumed by DFlash.
5. `common_speculative_impl_draft_dflash::begin()` near line 1095: prefill
   `process()` calls happen before `begin()`. The hook therefore provisionally
   claims `next-request.json` on the first prefill batch, buffers rows across
   ubatches, and here verifies that buffered token IDs exactly equal `prompt`,
   positions start at zero, and the complete prompt length matches. Only then
   does the capture become active.
6. `common/speculative.cpp`, wrapper section near line 2832: add
   `common_speculative_end()` that invokes `end()` on every implementation.
   Declare it beside `common_speculative_begin()` in `common/speculative.h`.
7. `tools/server/server-context.cpp`, `send_final_response()` near line 2082:
   call `common_speculative_end(spec.get(), slot.id, true)` before response
   fields are moved. This publishes the successful trace.
8. `tools/server/server-context.cpp`, slot `callback_on_release` near line
   1315: call `common_speculative_end(spec.get(), id_slot, false)` before
   popping deferred work. `end()` is idempotent, so the normal release after a
   successful final response becomes a no-op while errors and cancellations
   cannot leave a complete-looking trace.

## Request Lifecycle And Label Alignment

The collector atomically writes `next-request.json` before sending an HTTP
request. With `parallel=1`, the first target prefill batch atomically renames
that control file to a claimed name and creates a provisional capture. Missing,
stale, duplicate, or identity-mismatched controls are fatal when capture mode
is enabled.

`process()` is called after target decode and before DFlash drafting. It may run
several times for prompt ubatches, so rows are accumulated by sequence and
position. `begin()` occurs only after prompt prefill; it verifies the full
tokenized prompt against the buffered rows and marks the first
`num_prompt_tokens` inputs as prompt rows.

One row remains pending until the next contiguous target input arrives. That
next input token becomes the pending row's `sampled_next_token_id`, after which
the completed row is queued for disk. The new row becomes pending. At request
end, the final pending row is dropped because its next-token label is unknown.
This gives the invariant:

```text
row[t].sampled_next_token_id == row[t + 1].input_token_id
```

The final prompt-input row therefore predicts the first generated token. The
parser marks it as a training anchor and starts trainer anchors at
`num_prompt_tokens - 1`, which is exactly what `make_block()` in
`scripts/train-qwen27-dflash-offline.py` expects. With `--draft-tokens 5`, each
training example produces one seed plus five labels, matching verifier width
six.

## Binary ABI

The machine-readable authority is
`experiments/qwen27-dflash-sycl-b70/harness/dflash-q4-target-trace-schema.json`.
The payload is little-endian, starts with a fixed 256-byte header, and stores
51,216 bytes per completed row:

| Region | Bytes | Contents |
|---|---:|---|
| row prefix | 16 | input token, next token, position, flags |
| features | 51,200 | BF16 `[5,5120]` target-layer inputs |

The fixed layer order is `[2,17,32,47,62]`. The header embeds raw target and
draft SHA-256 values, the 20-byte runtime Git commit, dirty-patch SHA-256,
prompt SHA-256, request ordinal, shape, and exact payload length. The complete
bit is initially clear and is rewritten only after successful request end.

## Copy And I/O Semantics

No new XPU copy or event belongs in this diagnostic hook.
`llama_get_embeddings_layer_inp()` already yields host-readable F32 data after
the target decode, and the current production code immediately copies those
values into `features_buf`. The trace path converts/copies the five gathered
vectors into an owned BF16 chunk synchronously before `features_buf` can be
resized or reused.

A single background writer may perform disk I/O and hashing. Its queue must be
bounded by bytes (recommended 256 MiB) and a small chunk count. Queue-full,
allocation, conversion, write, flush, or fsync failures fail the capture; the
implementation must never silently skip rows. Capture timing is diagnostic and
must not be used as a decode benchmark.

Successful finalization rewrites the header with row count, payload bytes, and
the complete flag; flushes and fsyncs; closes and hashes the payload; atomically
renames it; then atomically publishes `request-%06d.json` last. Abort leaves no
complete sidecar. An incomplete `.failed` payload may be retained for audit but
the parser rejects it.

## Identity And Safety Gates

- The launcher deep-hashes the exact target and draft GGUF files before server
  start. The hook does not hash a 16+ GiB model on the decode thread.
- Runtime commit and dirty-patch SHA are compile-time build definitions, not
  free-form request metadata. If either definition is absent, capture mode
  refuses to start.
- The session manifest repeats all identities and fixed server settings. The
  collector validates it before publishing any request control.
- Every request control and trace header repeats model/runtime identities. The
  collector checks the sidecar; the parser independently checks payload SHA,
  binary header identity, ordinal, prompt hash, layers, shape, file size,
  positions, token-label alignment, and prompt/generation boundaries.
- Capture requires TP1, one server slot, no prompt/context/checkpoint/history
  reuse, reasoning off, greedy sampling, native DFlash present but drafting
  disabled, and F16 draft K/V. Any mismatch fails closed.
- The parser output is explicitly diagnostic training data and not an endpoint
  result or LocalMaxxing-eligible artifact.

## Minimal Patch Blueprint

Native code should stay small and isolated:

```text
common/speculative.h
  + common_speculative_end(spec, seq_id, complete)

common/speculative.cpp
  + optional common_speculative_impl::end()
  + trace_header_v1 / trace_row_prefix_v1 packed structs with static_asserts
  + dflash_trace_writer (bounded queue, atomic finalize, no row dropping)
  + provisional/active per-seq capture state and one-row label delay
  + constructor/session validation
  + process() BF16 owned-copy enqueue
  + begin() full prompt validation
  + DFlash end() success/abort finalization
  + common_speculative_end() wrapper

tools/server/server-context.cpp
  + successful end before send_final_response moves response fields
  + abort end in callback_on_release
```

Use explicit little-endian serialization rather than writing a native C++
struct directly. If packed structs are used as an intermediate, require
`static_assert(sizeof(header) == 256)` and offset assertions matching the JSON
contract.

## Implemented Experiment-Side Artifacts

- Binary ABI reader/writer fixture:
  `scripts/qwen27_dflash_trace_format.py`
- Fail-closed native-session collector and atomic next-request control:
  `scripts/collect-qwen27-dflash-q4-training-corpus.py`
- Exact-Q4 parser:
  `scripts/parse-qwen27-dflash-q4-target-trace.py`
- Synthetic ABI/corruption/identity test:
  `experiments/qwen27-dflash-sycl-b70/tests/test-qwen27-dflash-q4-target-trace.py`
- Capture identity and family split:
  `data/qwen27-dflash-q4-adaptation-capture-20260713/capture-plan.json`

## Native Implementation Gate

After protected Q6 work is committed or snapshotted:

1. Recompute and record the exact full llama.cpp dirty-patch SHA, including the
   trace hook, and rebuild with commit/patch identity definitions.
2. Update the capture plan to that exact identity.
3. Implement the native patch at the function boundaries above.
4. Run the synthetic parser test, then a one-prompt native capture.
5. Corrupt one identity, one payload byte, one position, and one label; confirm
   all four are rejected.
6. Run a short train/heldout capture and invoke the trainer with
   `--train-scope layer-position-bias --draft-tokens 5`.
7. Continue only if the heldout screen reaches at least four accepted and five
   emitted tokens per favorable cycle without target-quality failures.

## Native Implementation Result

The runtime implementation is isolated in
`common/dflash-target-trace.{h,cpp}` with narrow lifecycle calls from
`common/speculative.{h,cpp}` and `tools/server/server-context.cpp`. It adds:

- compile-time runtime commit and dirty-patch identities;
- launcher-provided deep model hashes;
- fixed server, DFlash shape, F16 draft-K/V, and greedy-request gates;
- atomic request-control claim and duplicate/stale rejection;
- synchronous owned F32-to-BF16 conversion before feature-buffer reuse;
- bounded prefill buffering, exact prompt-token/position comparison, and
  one-row delayed target labels;
- header/payload fsync, atomic payload rename, payload SHA-256, and sidecar-last
  publication;
- idempotent abort/finalize behavior and sequential multi-request reuse.

The isolated CPU `llama-server` build passed with the trace compile definitions,
including both `speculative.cpp` and `server-context.cpp`. The native smoke in
`tests/dflash-q4-target-trace-native-smoke.cpp` captured two sequential requests
through one trace object. Each payload had three complete rows and parsed via
the production parser into `qwen36_eagle_sequence_v2`. Native payload identity,
payload byte, position, and label corruptions were all rejected. The original
synthetic contract/corruption suite also remained green.

No real model capture has run. The source tree contains concurrent kernel work,
so embedding a fingerprint now would immediately make the corpus identity
stale. The next action is to freeze that tree, recompute the full dirty patch
SHA-256, rebuild with both compile-time identity definitions, update the plan,
then run one real prompt before any train/heldout collection.
