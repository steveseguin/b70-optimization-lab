# Qwen3.8 Q4_K_M TP1: conv state-I/O + SILU-L2 widening result

Date: 2026-08-21

Status: **accepted TP1 lane increment 2: +1.3% exact on top of increment 1;
lane at `27.71 tok/s`.** QK norm-RoPE remains inert pending a graph-order
investigation.

## What changed

The conv-state matcher and the fused SSM_CONV/SILU/L2 kernel admitted only
the TP2 per-device width (`d_inner = 5120`, 8 Q-conv + 8 K-conv heads); at
TP1 the full-model `10240` width (16+16+48 heads) fell back to the stock
`GET_ROWS -> CONCAT -> CPY -> SSM_CONV -> SILU -> 2x L2_NORM` chain on all
48 GDN layers. The widened matcher derives `d_inner` from the state size and
the launcher passes runtime head counts to the kernel (identical per-channel
and per-head arithmetic; the fused launch preserves the stock four-term
accumulation and the SG16 L2 lane order). The QK norm-RoPE matchers and
launcher were widened in the same commit (24 Q / 4 KV, derived strides) but
did not engage — the shapes pass in isolation, so a node-adjacency or
consumer-order assumption still rejects at TP1; inert and exactness-neutral.
Patch packet:
[`patches/qwen38-27b-q4km-tp1-b70s/`](../../../patches/qwen38-27b-q4km-tp1-b70s/README.md).

## Measurement

Same registered protocol (fixed cold 12-prompt suite, fresh server per leg,
GPU 0, `cached_tokens=0` on all requests, gates passed):

| Leg | Stack | Conventional median | vs baseline A |
|---|---|---|---|
| C/D (inc 1) | GDN state-IO | `27.358865` / `27.351846` | `+5.03%` / `+5.01%` |
| E (inc 2) | + conv IO/SILU-L2 | `27.707324 tok/s` | **`+6.37%`** |
| F (inc 2) | + conv IO/SILU-L2 | `27.712055 tok/s` | **`+6.39%`** |

- Exactness: 24/24 complete output hashes across E and F identical to the
  registered TP1 baseline oracle; the fixed seed-42 probe text is
  byte-identical.
- Mechanism: `fused_conv_state_ios=282720` and `fused_conv_silu_l2=282720`
  per leg (48 per decode graph); GDN counters unchanged at `282720`.
- Compute identity: `libggml-sycl.so`
  `31d9c48813fb2f10a0b6b779d28746eb8dba391bb930fea8f4fd10ee34bc6bc6`.

## Lane state and next rungs

`27.71 tok/s`; the 30 tok/s goal needs `+8.3%`. Next: (1) find and fix the
TP1 graph-order assumption blocking `fused_qk_norm_rope` (16 attention
layers, est. up to ~1%); (2) sweep remaining launch-gap reduction
opportunities now that state I/O is in place (the three eliminated conv
kernels only bought ~1.3%, confirming per-launch overhead of ~8-10 us is
the dominant recoverable cost); (3) revisit the clock droop (2650-2800 MHz
observed under decode) as a separately governed identity question.
