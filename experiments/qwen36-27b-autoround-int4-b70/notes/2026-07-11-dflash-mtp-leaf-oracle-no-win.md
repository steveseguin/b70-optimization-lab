# 2026-07-11 - DFlash plus intrinsic-MTP leaf oracle: no endpoint candidate

## Purpose and validity

This experiment tested whether cheap intrinsic-MTP leaves could improve the
existing 15-node Qwen27 DFlash DDTree enough to justify implementing a
composite proposer. It is an offline target-owned acceptance diagnostic, not an
endpoint throughput result and not eligible for LocalMaxxing.

The input corpus contains the first 100 fresh generation anchors for each of
the fixed realistic suite's 12 prompts. Four B70s processed disjoint shards;
there was no prompt/KV/history/response reuse. Every reported acceptance count
is checked against the target continuation recorded for that anchor.

## Candidate construction

- Base: 15-node best-first DFlash DDTree.
- Equal-row control: pure DFlash DDTree with 19 nodes.
- `leaf1/2/4/8`: add one intrinsic-MTP child to that many DFlash parents,
  ranked by path probability times uncovered DFlash child mass.
- `proxy_all`: give every DFlash parent one MTP child. This is an optimistic
  coverage proxy, not the proposed endpoint shape.
- `target_hidden_upper`: condition MTP on the future target hidden state. That
  state is not causally available to a proposer, so this is only an upper
  bound.

The implementable leaves use the DFlash pre-LM-head hidden row, one independent
Qwen intrinsic-MTP step, and the endpoint-style runtime INT4 draft LM head with
group-128 BF16 scales. Leaves can add at most one visible token per verifier
cycle.

## Results

Primary official-vLLM-RoPE run:

- tracked result:
  `../diagnostics/qwen27-dflash-mtp-leaf-oracle-20260711T100000Z.json`;
- raw shards:
  `/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/mtp-leaf-oracle-20260711T100000Z`;
- anchors: `1200` across `12` prompt clusters;
- base mean visible tokens/anchor: `3.81083`.

| Policy | Mean lift vs base | Repairs / 1200 | Prompt-cluster bootstrap 95% CI | First-100 median tokens/cycle |
|---|---:|---:|---:|---:|
| equal-row DFlash-19 | `+0.1125` | `130` | `[0.0908, 0.1350]` | `3.8462` |
| MTP leaf-1 | `+0.0425` | `51` | `[0.0317, 0.0533]` | `3.6376` |
| MTP leaf-2 | `+0.0742` | `89` | `[0.0550, 0.0933]` | `3.7037` |
| MTP leaf-4 | `+0.1283` | `154` | `[0.1025, 0.1542]` | `3.7749` |
| MTP leaf-8 | `+0.2067` | `248` | `[0.1767, 0.2392]` | `3.7749` |
| all-parent proxy | `+0.2958` | `355` | `[0.2592, 0.3358]` | `3.8519` |
| unavailable target-hidden upper | `+0.6392` | `767` | `[0.5992, 0.6783]` | `4.2572` |

The leaf-4 shape misses the predeclared `+0.35` implementation-spend gate by
almost 3x. More importantly, even the all-parent proxy's 95% upper bound stays
below that gate. Equal-row pure DFlash-19 is at least as useful as leaf-4 in
the first-100 simulation without adding a second model to the proposer.

The first run used the helper's local text-only Neox RoPE fallback:
`../diagnostics/qwen27-dflash-mtp-leaf-oracle-20260711T094930Z.json`. A direct
XPU probe found max difference `0` between that fallback and official Qwen
M-RoPE for text positions. The helper was nevertheless repaired to construct
the official vLLM op under a default offline config context, and the complete
four-GPU oracle was repeated. The conclusion was stable:

- leaf-4 lift: `0.1275 -> 0.1283`;
- all-parent lift: `0.2925 -> 0.2958`;
- base-visible values changed at only `16/1200` anchors, with zero aggregate
  mean shift; these were one-token boundary changes consistent with XPU
  numerical/tie variation.

## Decision

Close DFlash plus intrinsic-MTP leaf composition for this Qwen27 checkpoint.
Do not spend an endpoint run or implement the composite proposer. The measured
lift is too small before accounting for MTP body, draft LM-head, larger target
row count, and orchestration cost; challenging the current `68.236 tok/s` TP1
record was estimated to require close to `+0.9` visible token/cycle at low
single-digit millisecond overhead.

The causally unavailable target-hidden upper bound is useful architectural
evidence: a stronger predictor could still matter, but feeding current MTP with
DFlash proxy hidden states is not that predictor.

## Reproduction

```bash
cd /home/steve/llm-optimizations
bash experiments/qwen36-27b-autoround-int4-b70/scripts/run-dflash-mtp-leaf-oracle-4gpu.sh
```

The evaluator records `diagnostic=true`, `throughput_benchmark=false`, and
`localmaxxing_eligible=false` in every report.
