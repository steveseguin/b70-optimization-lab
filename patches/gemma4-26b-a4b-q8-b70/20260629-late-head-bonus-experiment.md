# Gemma 4 26B Q8: late head-only bonus experiment

Date: 2026-06-29

## Intent

Try to reduce verifier cost without changing target/verifier semantics. The
main verifier still runs the target model over the draft rows, but the final
bonus-producing row is marked `logits=false`. On full draft match only, a small
exact output-head graph is run over the already-produced final `t_h_nextn` row
to produce the bonus token.

This targets the expensive verifier LM-head rows while preserving the accepted
draft-token verification path. The feature is default-off behind:

```bash
LLAMA_SPEC_VERIFY_LATE_HEAD_BONUS=1
```

## Patch Snapshots

- Source experiment patch:
  `20260629-late-head-bonus-source-experiment.patch`
  - SHA256:
    `defe41022026c8a7175afc87cda4ed24ad87f8a595277d6096cb91832a061a5e`
- Harness identity patch:
  `20260629-late-head-bonus-harness-identity.patch`
  - SHA256:
    `988cee435ee1161c38db1cc84ca46b600e87a19a8446287fbeafd3dcc5a52377`

The source patch is against the active local Gemma record worktree based on
llama.cpp `c926ad098`, not clean upstream. The broader record stack remains
captured in `20260629-current-llamacpp-gemma-record-worktree.patch`.

## Build Status

Built successfully with:

```bash
source /opt/intel/oneapi/setvars.sh
cmake --build /home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 8
```

## Validation Plan

First screen:

- fixed realistic cold prompt suite;
- each prompt once, `cached_tokens=0`;
- UD-Q8_K_XL target/verifier, Q4_0 MTP draft;
- `MAX_TOKENS=128`, `REALISTIC_METRIC_TOKENS=100`;
- 32 canary repeats;
- no LocalMaxxing submission unless a full512 strict run beats the current
  valid record `98.34046474459183 tok/s`.

Expected risk: the separate head graph may be correct but slower if graph
rebuild/scheduler overhead dominates the saved verifier rows.

## Result

Status: **negative / do not promote**.

Run:

- `data/gemma4-q8-gpu0-lateheadbonus-strict128-20260629T024814Z/summary.json`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-lateheadbonus-strict128-20260629T024814Z.server.log`

Validity:

- canary: **128/128 rows passed**;
- realistic final gate: **passed**;
- fixed realistic suite, each prompt once;
- `cached_tokens=0` for all 12 prompts;
- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- `LLAMA_SPEC_VERIFY_LATE_HEAD_BONUS=1` captured in launcher identity.

Metrics (`MAX_TOKENS=128`, metric window 1-100 after TTFT):

- median: **96.91021564463527 tok/s**;
- p10: **89.08089786599679 tok/s**;
- mean: **95.26184416965226 tok/s**;
- median wall-clock full-output: **84.32209460571781 tok/s**;
- median TTFT: **178.4658479737118 ms**.

Current promoted valid record remains:

- `98.34046474459183 tok/s`;
- `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-confirm-B-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/summary.json`.

Interpretation:

The path is exact enough to pass the strict gate, but it is slower than the
record. The likely cause is the extra one-row output-head graph/scheduler work
on every full-match bonus path. It improves neither the headline median nor the
full-output wall speed enough to justify a full512 promotion run.

Follow-up:

Do not retry this shape as another config sweep. If revisiting the idea, the
bonus head must be fused into the existing verifier graph/output path rather
than launched as a separate graph.
