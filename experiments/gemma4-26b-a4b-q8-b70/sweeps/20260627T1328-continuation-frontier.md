# 2026-06-27T13:28Z Gemma 4 26B Q8 Continuation Frontier

## Current Valid Record

The promoted fresh-response 1xB70 record remains:

- run: `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/`
- row0 fresh after-TTFT throughput: `104.30919255569083 tok/s`
- wall row0: `90.85119259916031 tok/s`
- canary: `6144/6144`
- LocalMaxxing ID: `cmqw1tgzx0366qr01g4lkv7f1`

Headline policy remains row0 only with `cached_tokens=0`. Later repeated rows
are support-only unless prompts/continuations are independently fresh.

## Rebuild/Control Validation Outcome

The rebuild/control full confirmation completed the canary but did not produce
benchmark artifacts:

- run: `data/gemma4-q8-gpu0-ub768-control-rebuild-fullconfirm-20260627T125811Z/`
- GPU/port: GPU0, `18310`
- canary: `6144/6144` rows clean in `chat-canary.json`
- benchmark/summary: missing; the harness died after canary, so this is
  correctness evidence only, not a speed result and not a record candidate.
- purpose: it still increases confidence that the rebuilt current binary/source
  stack preserves the record canary behavior, but does not replace the promoted
  `104.30919255569083 tok/s` run.

The server exited and GPU0 is no longer reserved by this run.

## Lanes Confirmed As Dead Ends

Do not rerun unchanged:

- warmed/history/n-gram continuation speedups as fresh-response records;
- blind `n_max`/`p_min`/direct-unroll depth sweeps;
- MTP draft quant variants (`Q5_K_M`, `Q6_K`, `Q8_0`, etc.);
- top2 score-gated direct-unroll depth; best valid screen was only
  `84.58980110621081 tok/s` fresh row0;
- existing verifier `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1`;
- existing verifier softcap argmax;
- route/gather/scatter plumbing around `MUL_MAT_ID`;
- broad `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1` **without Q8_0
  MoE expert reorder**;
- grouped/per-slot Q8 `MUL_MAT_ID` flags as currently implemented;
- `VDR_Q8_0_Q8_1_MMVQ=4`, `MMVY=2`, prequant route rows, and small-ncols
  Q8 MMVQ reuse-x patches.
- paired Q8 gate/up row body for `ffn_moe_gate_up`
  (`LLAMA_SYCL_MUL_MAT_ID_GATE_UP_PAIR_Q8_0=1`): quality-clean but much slower,
  `84.75499805492217` row0 fresh vs `104.28417032791086` same-binary control.
  See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1348-gateup-pair-q8-negative.md`
  and
  `patches/gemma4-26b-a4b-q8-b70/gateup-pair-q8-negative-20260627.patch`.

The consistent profile finding is that target/verifier `process_ubatch`
dominates. Draft-side and route-plan micro-work is already too small to move
the record materially.

## Active Frontier

Two read-only audits were launched for the remaining useful source frontier:

1. Q8 `MUL_MAT_ID` expert-matmul body improvements that are not duplicate
   grouped/per-slot/VDR/MMVY/prequant/small-ncols losses.
2. Fresh-valid speculation structures that could move beyond the current MTP
   verifier ceiling without using warmed repeated continuations.

The two audit outputs pointed to:

- Q8_0 MoE-ID reorder/SoA as the next plausible kernel-level lane;
- exact verifier candidate-vs-max LM-head work as a higher-potential but harder
  lane, provided it does not repeat the already-killed fused-output/softcap
  argmax shortcuts.

Follow-up update: the Q8_0 MoE-ID reorder lane from the audit produced the
first `>150 tok/s` fresh-response screens. See
`20260627T1420-q8-moe-id-reorder-breakthrough.md` and
`patches/gemma4-26b-a4b-q8-b70/q8-moe-id-reorder-positive-20260627.md`.
The broad fast path is still a loss without that reorder, but no longer dead as
a class.
