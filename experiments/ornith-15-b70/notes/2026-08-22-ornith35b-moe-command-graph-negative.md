# Ornith 1.5 35B-A3B: MoE command graph is a decisive negative

Date: 2026-08-22 EDT

Status: **REJECTED — 52.08% decode regression**

## Candidate and safety repair

llama.cpp PR 25089, contributed by Captain-Tripps, identified that the fused
single-token SYCL `MUL_MAT_ID` implementation is device-only and may be eligible
for command-graph capture. That concrete eligibility observation was the input;
the maintained implementation and evidence live in this repository.

The proposed check was not safe unchanged on this stack. The first graph call
attempted to record the one-time K-quant expert reorder and failed because a
graph node depended on an event created before recording. The lab port therefore:

1. uses the exact fused-dispatch predicate for graph admission;
2. runs the first Q4_K/Q5_K/Q6_K expert reorder eagerly;
3. permits capture only after the persistent reordered layout exists; and
4. continues rejecting multi-token `MUL_MAT_ID` and contiguous dim-3 concat.

The archived candidate is
`../patches/llamacpp-ornith15-moe-command-graph-negative-20260822.patch`.

## Correctness gates

- Ornith gate/up shape: Q4_K, 256 experts / 8 used, `2048 -> 512`: PASS
  against the CPU backend.
- Ornith down shape: Q6_K, 256 experts / 8 used, `512 -> 2048`: PASS against
  the CPU backend.
- Repeated graph execution after the eager reorder: PASS.
- Multi-token `MUL_MAT_ID`: confirmed eager.
- Concat dim 0: graph-compatible and PASS; contiguous dim 3: confirmed eager.

Correctness was necessary but not sufficient. A one-node graph was already
slower than eager because update overhead could not be amortized:

| Exact expert op | Graph off | Graph on |
| --- | ---: | ---: |
| Q4_K gate or up | 10.05 us | 22.84 us |
| Q6_K down | 12.82 us | 30.40 us |

## Full-model matched A/B/A

Model identity was verified through both O_DIRECT and ordinary SHA-256 reads.
All runs used the same local file, candidate binary, one visible B70, F16 KV,
flash attention, 99 GPU layers, `p0/n128/d0`, and seven repetitions.

| Arm | Mean tok/s | Raw repetition range |
| --- | ---: | ---: |
| graph off A | 102.155 | 101.098–103.031 |
| graph on | 48.805 | 47.382–53.572 |
| graph off B | 101.537 | 100.600–102.579 |

The graph-off control mean is `101.846 tok/s`; graph-on is `-52.08%`. The
reverse control rules out a persistent host or GPU slowdown.

## Disposition

Do not enable `GGML_SYCL_ENABLE_GRAPH=1` for Ornith 1.5 35B-A3B on this stack.
Do not spend a serving-quality run on this candidate. Continue with MoE kernel
boundaries or target-verified speculation, where the remaining decode headroom
actually lies.

Machine-readable summary and raw llama-bench JSON are under `../data/`.
