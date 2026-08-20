# Decode step cost model: GEMMs are at the roofline; half the step is NOT weight streaming

Date: 2026-08-19
Status: measured on this host with production ops; residual decomposition and
the full-graph arm are measuring-host work

Question: after the scratch fix (+~1.5) and rerank (+1.5-4.5), what else
moves decode rate? Answer: not GEMM kernels — they are already at the
memory roofline. The recoverable mass is the 53% of the step that is not
weight traffic, and the biggest assembled-but-unscreened weapon for it is
full-graph capture of the GDN regions.

## Measurements (burst-timed production `_xpu_C` ops, TP2-local shapes)

Script `scripts/qwen38-step-cost-model.py`, data
`data/2026-08-19-step-cost-model.json`. MTP5 step = 35.3 ms
(101.922 tok/s ÷ ~3.6 accepted tokens/step).

| component | us/call | effective GB/s |
|---|---|---|
| MLP gate_up int4 M=6 (real weights) | 84.6 | 543 |
| MLP down int4 M=6 | 21.0 | 1092 |
| target LM head int8 M=6 (75968 local) | 722.0 | 539 |
| draft LM head int4 M=1 | 340.8 | 588 |
| GDN in_proj int8 M=6 | 81.4 | 518 |
| GDN out_proj int4 M=6 | 9.1 | 889 |
| attn qkv int4 M=6 | 8.7 | 1248 |
| GDN spec-decode op (record lane) | 43.4 | — |

## The bandwidth-cliff artifact (do not repeat this mistake)

An N-sweep showed N≤8704 at 1.1-1.25 TB/s and N≥17408 at ~570-580 GB/s,
suggesting a kernel-path cliff and a split-N lever. **False.** The narrow
matrices (≤22 MB packed) are L2-resident under the 100-call burst loop; the
wide ones exceed L2 and show true HBM rate. Storage-separated split-N is
bit-exact but SLOWER (int4 17408: 93.1 vs 79.5 µs; int8 head 8×9496: 963.6
vs 722.3 µs). The wide GEMMs run at ~540-590 GB/s ≈ 90%+ of the B70's
~608 GB/s HBM (256-bit GDDR6 @ 19 Gbps). **There is no meaningful GEMM
kernel headroom. Close that space; do not write int4 GEMM kernels.**

## Step budget

Measured component floor (burst-amortized): **16.6 ms** — MLP 6.8, GDN 6.4,
draft loop 2.4, target head 0.7, attention GEMMs 0.3. Pure weight-traffic
floor at ~576 GB/s: ~9.0 GB/step/rank → **15.7 ms**. Both say the same
thing: of the 35.3 ms step, **~18.7 ms (53%) is not weight streaming** —
dependent-kernel latency, eager GDN-region dispatch, 128 TP2 collectives,
sampler, draft serialization, host logic.

### Collectives priced (2026-08-19, 2-rank XCCL on the rebuilt oneCCL)

Script `scripts/qwen38-tp2-collective-latency.py`, data
`data/2026-08-19-tp2-collective-latency.json`:

| collective | eager us | burst us | graph-captured us |
|---|---|---|---|
| layer allreduce [6,5120] fp16 | 43.0 | 14.6 | **6.3** |
| draft allreduce [1,5120] fp16 | 42.7 | 14.6 | 5.5 |
| logits allgather [6,75968] fp16 | 44.1 | — | — |
| draft logits allgather [1,75968] | 42.0 | — | — |

Per MTP5 step (128 layer + 10 draft allreduces, 1+5 logits allgathers):
**≈6.2 ms if each pays full eager latency, ≈2.3 ms burst-amortized,
≈1.1 ms fully graph-captured.** The collectives alone are a ~5 ms/step
(~14%, +10-14 tok/s) argument for the full-graph arm — before counting the
launch-latency savings on the GDN eager regions themselves.

### Small ops priced (burst, 2026-08-19)

`per_token_quant_int8_xpu [6,5120]`: 5.7 µs; `qwen_gemma_rms_norm_f32`
[6,5120]: 4.8 µs. Per-step small-op totals at burst rates: ~54 quant calls
(GDN dedup reuses one per layer) + 128 RMSNorm + 128 residual adds ≈
**1.6 ms**; at eager dispatch rates roughly double that.

### Final residual accounting

| block | ms/step |
|---|---|
| measured big components (GEMMs, spec op, heads) | 16.6 |
| collectives (burst) | 2.3 |
| small ops (quant/norm/add, burst) | 1.6 |
| attention kernels (16 × ~40 µs est.) | ~0.6 |
| **accounted** | **~21.1** |
| **actual step** | **35.3** |
| **unaccounted: eager dispatch penalty, draft serialization, sampler, host** | **~14.2** |

The dominant recoverable mass is the dispatch penalty itself — exactly what
full-graph capture removes. Even capturing only the 48 GDN layer regions
(whose graph breaks force eager dispatch today) attacks the largest slice.

## The unscreened arm this points to

Every prerequisite for full-graph capture of the record lane was rebuilt
and validated on 2026-08-18, and no Qwen3.8 MTP benchmark of it exists:

- graph-safe head256 FA stage (forced one-token chunk decode, packed
  verifier rows) — 12,000 passing replays;
- rebuilt oneCCL passing both graph collectives oracles;
- the GDN persistent scratch (whose existence motive is "captured Level
  Zero command graphs cannot replay allocator-reused storage") — now
  zero-init built here, parity-gate bit-exact at MTP4/MTP5 shapes, and
  200 graph replays bit-exact vs eager.

The record config runs PIECEWISE with `DDTREE_FULL_GRAPH=0 /
CAPTURE_GDN_CORE=0`. The collaborator's config-space closure (9f90e2c38)
retested only tie-break/oneDNN flags — NOT the capture doors. If full-graph
capture recovers even half the residual, that is +8-9 ms/step ≈ +25-30%
— larger than scratch+rerank combined. Risks: capture may fail or force
numerics changes at verifier width 6 (that's what the oracles de-risk, but
only a server run proves it); July's Qwen3.6 full-graph record proves the
door itself is viable on this fork.

## Recommended order (measuring host)

1. Strict-25 with the zero-init rebuild + `PERSISTENT_SCRATCH=1`
   (≈103-104 expected, unblocks serial-exact and is the full-graph
   prerequisite).
2. Full-graph screen: `VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1
   VLLM_XPU_DDTREE_FULL_GRAPH=1 VLLM_XPU_DDTREE_CAPTURE_GDN_CORE=1`,
   `FULL_AND_PIECEWISE` capture size 6, per the July Qwen3.6 record recipe.
3. Rerank K=2 (acceptance axis, orthogonal).
4. If the residual persists after capture: unitrace profile
   (`scripts/profile-current-recipe-unitrace.sh`) to name the remainder
   before touching anything else.
