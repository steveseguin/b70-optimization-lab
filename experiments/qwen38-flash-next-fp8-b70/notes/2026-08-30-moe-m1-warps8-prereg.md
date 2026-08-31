# Qwen3.8 Flash-Next FP8 production-M1 MoE warps screen preregistration

Date: 2026-08-30
Status: frozen before component execution

A28 proves the current single-sequence routed expert kernel receives M1. This
screen asks whether changing only `num_warps` from the production default 4 to
8 reduces the real-weight M1 Triton FP8 MoE latency without changing output
bytes.

Frozen scope:

- one B70; no model server, reboot, PLE mapping, or memory ballast;
- layer-0 rank-0 checkpoint weights from revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` on local NVMe;
- production 512-global/128-local expert map, EP rank 0, balanced-global
  routing, M1, top-k 10, hidden 2,560, intermediate 640, FP8 block 128x128;
- hidden seeds 20260826, 20260827, and 20260830;
- for each seed: fresh-process default, `num_warps=8`, fresh-process default;
- 10 warmups, 21 timed batches of 100 calls, plus 100 exact-hash repeats;
- component gate SHA-256
  `505ac4b230456bd5eb9d83d14d54b31dec88e0ec607cf557f434b4184ca71aa8`.

The candidate is a component positive only if all calls are finite, each arm
has one repeated hash, candidate and both controls share the same hash for all
three seeds, at least two seed candidates improve by 5% or more against their
bracketing-control mean, and the median candidate improvement across seeds is
at least 5%. Otherwise it is neutral or rejected. A component positive only
authorizes a separately receipt-bound endpoint candidate; it does not change a
protected speed result.
