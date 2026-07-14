# Exact-Q4 Native DFlash Trace Closeout

Date: 2026-07-13

Status: native hook and ABI smoke complete; real capture and adaptation screen
not run because the Qwen optimization lane closed before the protected runtime
tree could be frozen.

## Preserved implementation

- Runtime helper: `/home/steve/src/llama.cpp/common/dflash-target-trace.{h,cpp}`.
- Narrow plumbing: `common/CMakeLists.txt`, `common/speculative.{h,cpp}`, and
  `tools/server/server-context.cpp`.
- Native two-request smoke:
  `experiments/qwen27-dflash-sycl-b70/tests/dflash-q4-target-trace-native-smoke.cpp`.
- Contract/parser blueprint:
  `2026-07-13-dflash-q4-target-trace-hook-blueprint.md`.
- Protected-tree snapshot:
  `patches/qwen27-dflash-exact-q4-native-trace-protected-stack-20260713.patch`,
  SHA-256 `ef865ff8397bba95a98c33e7e92bfe537ac05c84134a0031795891be9c4b8970`.

The patch is deliberately labeled `protected-stack`: the shared
`speculative.cpp` and `server-context.cpp` were already dirty with the active
Q6 target-top1 experiment, so the snapshot contains that concurrent context as
well as the trace plumbing. Do not blindly apply it to a different tree; use
the isolated trace helper and named hook points from the blueprint when
rebasing.

## Verified

- Separate CPU `llama-server` build completed with both trace compile-time
  identities set; `speculative.cpp`, the helper, and `server-context.cpp` all
  compiled and linked.
- Warning-enabled standalone helper build passed.
- One trace object atomically captured and published two sequential requests,
  proving successful-finalize plus release-callback idempotency and reuse.
- Each native payload had the exact 256-byte header, three 51,216-byte rows,
  BF16 `[3,5,5120]` features, contiguous positions, and delayed labels.
- The native payload parsed into `qwen36_eagle_sequence_v2` with two training
  anchors. Native identity, payload-byte, position, and label corruptions were
  rejected.
- The existing synthetic session, ABI, parser, truncation, identity,
  prompt-reuse, and incomplete-payload suite remained fully green.

## Remaining risks

- No real Q4 target/DFlash model request exercised the gather hook. A real
  one-prompt capture is still required before trusting a corpus.
- The synchronous BF16 conversion and final write are diagnostic overhead; no
  performance number from a capture-enabled server is valid.
- Capture request gating checks cache disable and greedy temperature at the
  server boundary, but reopening should audit any newly added sampler
  transforms before collection.
- The compile-time dirty-patch SHA in the smoke was the earlier plan identity,
  not the final moving protected tree. It was only an ABI test identity.
- No acceptance training or screen was attempted. The hard continuation gate
  remains at least `4.0` accepted drafts and `5.0` emitted tokens per favorable
  width-six cycle.

## Reopen procedure

1. Rebase the isolated helper and lifecycle hooks onto a clean/frozen runtime.
2. Compute the full dirty patch SHA-256, update `capture-plan.json`, and rebuild
   with `LLAMA_DFLASH_TRACE_RUNTIME_COMMIT` and
   `LLAMA_DFLASH_TRACE_DIRTY_PATCH_SHA256` set to that exact identity.
3. Launch TP1/parallel-one DFlash with draft K/V F16, `n_max=n_min=0`,
   `p_min=0`, checkpoints off, reasoning off, and the two deep model hashes.
4. Run one collector prompt, parse it, and repeat the four corruption checks.
5. Only then collect train/heldout traces and run the bounded
   `layer-position-bias`, draft-token-five screen. Stop unless it clears the
   `4 accepted / 5 emitted` hard gate.
