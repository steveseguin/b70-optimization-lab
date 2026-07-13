# Q6_K M=6 fused DFlash top-1 production record

Date: 2026-07-13

## Outcome

The guarded Q6_K DFlash decoder LM-head fusion produced a confirmed strict
single-B70 record. It computes only decoder rows 1 through 5, reduces them to
five greedy token IDs on device, and avoids materializing/copying five full
248,320-token logit rows.

The confirmed BMG AOT result was:

- median tokens 1-100 after TTFT: `47.818818 tok/s`;
- p10: `39.869534 tok/s`;
- mean: `46.638647 tok/s`;
- median full-output after-TTFT: `47.878598 tok/s`;
- median wall full-128: `32.923315 tok/s`;
- median TTFT: `1156.511 ms`;
- fixed realistic gate: pass;
- cached tokens: zero for all 12 unique prompts.

The first strict candidate also passed at `47.114289 tok/s`. The exact AOT
control, changing only `GGML_SYCL_XE2_Q6_M6_TOP1=0`, measured
`44.220504 tok/s`. The confirmation is therefore `8.14%` faster than the exact
control and `8.05%` faster than the previous matching `44.255388 tok/s`
LocalMaxxing record.

## Why this was slow

Native DFlash decodes a six-row noise block, but row 0 is not sampled. The old
path still projected all six rows through the Q6_K output weight, wrote full
logits, ran a separate argmax, copied results across the host boundary, and
constructed ordinary sampler candidates. Cycle timing put the ordinary warm
width-6 draft block near `8.42-8.54 ms`.

The production fusion expands the Q6_K output tensor once into signed int8
quants, int8 subscales, and fp16 superblock scales. A five-row kernel then
quantizes the useful activations, reuses each weight slice across all rows, and
performs lowest-token-ID top-1 reduction without writing logits. Warm A/B/A/B
timing reduced the width-6 draft block to `7.18-7.20 ms`, a `14.7-15.7%`
cycle-boundary reduction. Warm fixed-prompt throughput moved from
`75.88/76.30` control to `77.74/77.81 tok/s` candidate.

## Exactness and safety contracts

The optimized matcher is default-off and requires all of the following:

- BMG G31, SYCL graph disabled;
- Q6_K `output.weight`, exact `[5120, 248320]` identity;
- exact F32 M=6 input and contiguous F32 `[248320, 6]` output;
- rows 1 through 5 represented by the exact offset view;
- the LM-head output has exactly that view as its sole consumer;
- that view has exactly the matched I32[5] argmax as its sole consumer;
- the expanded pack has the exact expected layout and byte count.

The compact host boundary is enabled only for native DFlash with one sequence,
`n_max=5`, `n_min=0`, `p_min=0`, and the fixed raw-argmax sampler semantics.
Non-matching graphs execute the ordinary path. A successful fused dispatch
marks the ordinary argmax skipped only after the fused enqueue succeeds.

An independent safety audit found three pre-promotion gaps. They were fixed
before AOT promotion:

1. The rows1..5 view now must have the matched argmax as its only consumer.
2. A failed compact read rolls back the just-decoded noise block, permanently
   disables compact mode, and explicitly reruns the ordinary-logits graph.
   Rollback/retry failure throws instead of reading absent logits.
3. Generic SYCL argmax and the fused reducer now use the same lowest-token-ID
   finite-tie contract. Synthetic oracles cover full-vocabulary zero ties and
   crossing ties `1/256`, `255/256`, and `0/248319`.

The diagnostic forced-read-failure run completed without a missing-logits
access and retained the deterministic hash
`2a931ff83e89f577315a59bef7cdf6938145f3eceb3c9996d78b065bcc17bd71`
and acceptance `49/63`, mean draft length `4.50`.

## Production fixture and comparator

The real six-row normalized DFlash activation fixture is:

- `/mnt/fast-ai/bench-results/qwen27-q6k-m6-top1/dflash-real-m6-v1.bin`;
- SHA-256 `e2bcd65300f9fa4d7b733dd0491d3c01cf566aadbbf4e22f7587079867484e3f`.

The five exact production token IDs are `12305, 198, 727, 369, 36951`.
The final comparator passed those rows, the actual sampler IDs, the full finite
tie oracle, and the stride-crossing tie oracle. Its last short run measured a
`2450.10 us` fused boundary and passed the `<2.5 ms` micro gate.

## Memory and startup

The expanded output pack is retained in addition to raw Q6_K:

- pack bytes: `1,360,793,600` (`1.267 GiB` decimal conversion differs from
  the earlier representation-delta estimate);
- free before pack at the strict r2 startup: `18,853,158,912` bytes;
- free after pack: `17,492,287,488` bytes;
- temporary per-dispatch scratch: about `337.6 KiB`.

This pack currently improves decode but costs startup work. Persisting it as a
trusted native artifact is the next iteration-speed improvement.

## Strict run identity

- target: `Qwen3.6-27B-Q4_0.gguf` from shared RAM cache;
- target KV: Q8_0/Q8_0;
- draft: native `Qwen3.6-27B-DFlash-Q8_0.gguf`;
- draft KV: F16/F16;
- one active sequence, one B70, context 4096, batch 1024, ubatch 256;
- native DFlash5, `n_max=5`, `n_min=0`, `p_min=0`;
- graph off;
- 187 packed Q4 M=6 projections, joint gate/up enabled;
- GDN snapshot-cache fusion enabled;
- Q6_K M=6 top-1 pack/fusion enabled;
- prompt cache, context checkpoints, response reuse, and history acceleration
  disabled.

## Artifacts

- confirmed tracked result:
  `data/qwen36-27b-mtp-gguf-q4-b70-baselines/q6top1-aot-realistic128-r2-20260713.json`;
- first strict candidate:
  `data/qwen36-27b-mtp-gguf-q4-b70-baselines/q6top1-aot-realistic128-r1-20260713.json`;
- exact control:
  `data/qwen36-27b-mtp-gguf-q4-b70-baselines/q6top1-aot-control-realistic128-r1-20260713.json`;
- confirmed run directory:
  `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/runs/q6top1-aot-realistic128-r2-20260713`;
- structured summary: `data/qwen27-q6k-m6-fused-top1-record-20260713.json`;
- scoped protected-source patch snapshot:
  `patches/qwen27-q6k-m6-fused-top1-20260713.patch`;
- independent review: commit `f8e965a28`, note
  `experiments/qwen27-dflash-sycl-b70/notes/2026-07-13-q6k-m6-draft-top1-independent-safety-audit.md`.

The patch snapshot was extracted from a shared dirty protected worktree using
Q6/DFlash/argmax-specific hunks. Review it against the recorded source commit
and active worktree before applying it elsewhere.
