# Qwen3.8 Q4_K_M TP1: GDN state-I/O widening result

Date: 2026-08-21

Status: **accepted TP1 lane increment: +5.0% exact, mechanism-verified.**

## What changed

At TP1 the accepted `GGML_SYCL_FUSED_GDN_STATE_IO` fusion never engaged
(`fused_gdn_state_ios=0` in both baseline legs): its matcher pinned the TP2
per-device half-shape (`128 x 128 x 24`). The widened matcher admits the
full-model 48-head shape under the same strictness (single row, contiguous,
unique consumers, persistent-state non-overlap, `beta_sigmoid` chain, poison
door), removing the `GET_ROWS -> GATED_DELTA_NET -> CPY` state round trip on
all 48 GDN layers: about 302 MB/token of eliminated VRAM traffic plus 96
eliminated kernel launches. The in-place kernel needed no change; it derives
head count and state width from tensor dimensions. Patch packet:
[`patches/qwen38-27b-q4km-tp1-b70s/`](../../../patches/qwen38-27b-q4km-tp1-b70s/README.md).

## Measurement

Fixed cold 12-prompt realistic suite, fresh server per leg, GPU 0,
`cached_tokens=0` on all requests, gates passed in every leg:

| Leg | Build | Conventional median | Delta vs baseline A |
|---|---|---|---|
| A (baseline) | matcher stock | `26.047863 tok/s` | — |
| B (baseline) | matcher stock | `26.068073 tok/s` | `+0.078%` |
| C (candidate) | widened | `27.358865 tok/s` | **`+5.033%`** |
| D (candidate) | widened | `27.351846 tok/s` | **`+5.006%`** |

- Exactness: **24/24 complete output SHA-256 hashes across C and D identical
  to the registered TP1 baseline oracle** (the fusion is bit-exact; the
  in-place update preserves the stock arithmetic order).
- Mechanism: `fused_gdn_state_ios=282720` in each candidate leg (48 per
  decode graph, all GDN layers), `graph_computes=5905`.
- Probe cross-check: the fixed seed-42 400-token probe text is byte-identical
  between builds (26.19 -> 27.54 tok/s).

## Attribution detail

Eliminated traffic (~302 MB/token at ~600 GB/s) explains only ~0.5 ms of the
~1.85 ms/token saved; the remainder is launch/scheduling gap time around the
two eliminated transfer kernels per GDN layer. Inter-kernel gap time, not
kernel-interior bandwidth, is the dominant recoverable overhead on this stack
at TP1 — the q4_K MMVQ GEMV itself already streams at the memory ceiling
(33.03 MB in 50.67 us, about 652 GB/s, versus a 597.6 GB/s SYCL read-bench
floor on the same card).

## Remaining dead doors at TP1

`fused_conv_state_ios=0`, `fused_conv_silu_l2=0`, and `fused_qk_norm_rope=0`
remain shape-blocked (conv channels 5120 -> 10240 and per-device attention
head counts doubled at TP1). The conv path needs kernel work, not just a
matcher change: `ssm_conv.cpp` hard-asserts `d_inner == 5120` and the SILU/L2
kernel fixes `q/k/v` channel layout at compile time. These are the next rungs.
