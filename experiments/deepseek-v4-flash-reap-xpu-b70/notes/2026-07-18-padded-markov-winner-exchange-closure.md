# Padded Markov Winner Exchange Closure

Date: **2026-07-18**

Status: **exact communication microgate; performance rejected before integration**

## Outcome

The earlier two-FP32 winner-pair all-gather was not slow because of its byte
count. It fell onto a pathological tiny-message route in the current oneCCL
runtime. Padding the logical score/token pair repairs that route, but it does
not create a useful DSpark sampler win.

The four-B70 gate measures the seven sequential exchanges in one speculative
cycle. The incumbent gathers 32,320 BF16 W2-bias values per rank per step and
reaches a 371.347 us slowest-rank median. An unpadded eight-byte pair takes
1,192.6645 us. Padding to 1,024 bytes is the best conservative result:

- all ranks reproduce the score/token payload exactly;
- seven padded exchanges take 352.652 us at the slowest rank;
- the conservative saving is only **6.4315 us/cycle**;
- 256-byte, 4-KiB, and 8-KiB payloads save only 5.7655, 3.6665, and
  4.9745 us/cycle respectively;
- 16-KiB and larger payloads are neutral or slower.

The incumbent full-bias gather is therefore already in the fast,
latency-dominated collective class. Replacing it with a padded pair cannot
repay the additional local W2/base-logit winner selection, packing, gathered
winner reduction, and next-token commit. The measured ceiling is two orders of
magnitude below the 0.50 ms standalone gate.

## Evidence

- reusable gate:
  `../scripts/bench-tp4-padded-pair-allgather.py`;
- raw summary:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-padded-pair-allgather-20260718T2350Z/sweep.json`;
- warmups/iterations: 12/80;
- topology: four B70s, XCCL, seven sequential all-gathers;
- all tested payloads were exact on all ranks.

This is a communication-only gate. No vLLM/XPU source was changed, no service
was loaded, and no endpoint or LocalMaxxing claim is made.

## Decision

Do not integrate padded pair transport as an isolated sampler change. It fixes
the tiny-message route but leaves no useful performance margin. A future
sampler redesign may reuse padding only as an incidental transport detail
inside a larger transaction that also deletes full base-logit materialization,
local bias output materialization, and sampler launches.

