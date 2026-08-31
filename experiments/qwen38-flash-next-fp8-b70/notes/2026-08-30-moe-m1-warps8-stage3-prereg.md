# Qwen3.8 Flash-Next FP8 M1 warps-8 stage-3 preregistration

Date: 2026-08-30
Status: frozen before component execution

The qualified M1 candidate raises `num_warps` from 4 to 8 at `num_stages=4`.
Eight warps increases per-program resources; reducing the compiler pipeline to
three stages may recover occupancy without changing block geometry, K-loop
partitioning, reduction order, or output arithmetic.

Frozen screen:

- the same one-B70 real-weight M1/EP-rank-0 shape, three hidden seeds, runtime,
  model revision, routing, and gate used by the qualified warps-8 result;
- for each seed: fresh-process warps8/stage4, warps8/stage3, warps8/stage4;
- 10 warmups, 21 timed batches of 100 calls, and 100 exact-hash repeats;
- no model server, reboot, PLE mapping, or memory ballast.

Stage 3 is a refinement positive only if all hashes match the corresponding
stage-4 authority, every arm retains one hash, at least two seed candidates
improve by 3% against their bracketing stage-4 mean, and median improvement is
at least 3%. Otherwise preserve it as neutral or rejected. Do not screen stage
5 or stage 2 unless stage 3 is negative/neutral and a later source-backed need
remains.
