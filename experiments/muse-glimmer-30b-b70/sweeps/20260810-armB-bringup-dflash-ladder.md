# 2026-08-10 Arm B Bring-Up: UD-Q8_K_XL 2xB70 + DFlash Ladder

Runtime: `/home/steve/src/llama.cpp-muse-glimmer` upstream `030ebb558`
(version 10358), SYCL AOT bmg-g31, clean master. Target
`Muse-Glimmer-30B-UD-Q8_K_XL.gguf` (32,300,651,040 B), drafter
`dflash-kquant.gguf`. GPUs 2+3, `ONEAPI_DEVICE_SELECTOR=level_zero:2,3`,
`-ngl 99 -c 32768 -b 1024 -ub 1024 -fa on --jinja`, VMM on, immediate
command lists on. Split ~14.6 GB (GPU2) + ~16.2 GB (GPU3).

Bench: greedy (`temperature=0`, `cache_prompt=false`), fixed B-tree prose
prompt via `/apply-template`, 192-512 predicted tokens, server `timings`.
Bring-up screen only - not a promoted packet; realistic-suite gates pending.

## Results

| Config | gen tok/s | draft accept | Note |
| --- | --- | --- | --- |
| no-spec (3 runs, 512 tok) | 15.838 / 15.831 / 15.830 | - | baseline, extremely stable |
| dflash n_max=15 | 3.80-4.47 | 12.9-14.1% | collapse: pays 16-token verify for ~2 emitted |
| dflash n_max=7 | ~29.5 (restart ladder implied) | - | request-level `speculative.n_max` override is IGNORED for dflash; early identical "ladder" rows were all n_max=15 |
| dflash n_max=6 | 30.483 | 31.8% | |
| dflash n_max=5 | **30.799** | 36.4% | **peak: 1.945x no-spec** |
| dflash n_max=4 | 30.125 | 40.5% | |
| dflash n_max=3 | 29.524 | 48.3% | |
| dflash n_max=2 | 28.716 | 62.7% | |
| dflash n_max=15, drafter on CPU (`--spec-draft-ngl 0`) | 3.956 | 14.5% | acceptance identical to GPU drafter -> no SYCL drafter-kernel numeric bug; layer-split feature taps fine |
| `-sm row` | crash | - | dies silently during model load, no log line after `load_model`; NO-GO on this stack, matches historical SYCL row-split fragility |

## Findings

1. Per-drafted-token acceptance decays steeply with block depth
   (62.7% at depth<=2 down to ~14% at depth 15), so deep blocks are
   anti-productive on B70 where a 16-token verify batch costs ~4x a
   single-token step. Upstream PR #26841 self-reports 34% acceptance,
   mean accepted length 3.04 - consistent with our n_max 3-5 sweet spot.
2. Chat-templated vs raw prompt made no material acceptance difference
   (12.9% vs 11.2% at n_max=15).
3. Exact verification confirmed upstream (PR: temp-0 output byte-identical
   with and without drafter), so DFlash is quality-free speed under the
   lossless-first directive; our own exactness gate still required before
   promotion.
4. Layer split is the working 2-GPU topology; row split documented NO-GO.

## Next

- p_min ladder for dflash (currently 0.00): adaptive early-stop may recover
  deeper blocks only when confident; interacts with n_max peak.
- Arm A BF16 same ladder once download lands; then Arm B vs Arm A greedy
  exact-match + canary gate on the fixed suite.
- Batch-16/verify-path SYCL kernel profile (mmq/mmvq crossover) - the
  n_max=15 collapse magnitude says verify batches are far from ideal on B70.
- Prompt-class acceptance spread (code/agentic/prose) before fixing n_max.
