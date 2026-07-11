# Qwen27 FP16 Scale And Position-FC MTP3 Screens

Date: 2026-07-11

## Scope

These screens continue from the promoted TP2 FP16 target-compute result
(`91.714405 tok/s` conservative full-quality median). All throughput rows use
the fixed 12-prompt realistic suite, each prompt once, token-id timing for
generated tokens 1-100 after TTFT, `cached_tokens=0`, and no prefix/history or
response reuse. Diagnostic rows are not records until the full quality and
pair-swap gates pass.

## FP16 LM-Head Scale Storage

The candidate changes only these two scale-storage dtypes on top of the FP16
record recipe:

```bash
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=fp16
VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=fp16
```

The launcher now exposes both existing BF16 defaults as environment overrides;
normal behavior is unchanged when the variables are unset.

First simultaneous TP2 diagnostic (`GPU 0,1` candidate; `GPU 2,3` control,
256 output-token budget, quality intentionally skipped):

| lane | median tok/s | mean | p10 | fresh/cached-zero |
|---|---:|---:|---:|---|
| FP16 scales | **`90.199918`** | `90.008076` | `83.572585` | pass |
| BF16-scale control | `85.794077` | `86.911599` | `79.032885` | pass |

The candidate moved `+5.14%` on median in this pairing, but neither row was a
promotable record: quality was skipped and the control was below the promoted
FP16 run. A GPU-pair swap then ran with a 512-token budget, repeat128, exact
cases, baseline parity, and the 1K needle.

Pair-swapped result (`GPU 2,3` candidate; `GPU 0,1` control):

| lane | median tok/s | mean | p10 | quality |
|---|---:|---:|---:|---|
| FP16 scales | `86.464705` | `88.936610` | **`81.591542`** | pass |
| BF16-scale control | **`88.250026`** | **`88.956448`** | `81.367636` | skipped |

The candidate passed exact cases, repeat128, baseline parity, and the 1K
needle, but lost by `2.02%` on swapped median and was effectively identical on
mean (`-0.02%`). Averaging the two GPU assignments still leaves only a small
movement inside the established endpoint variance band. Decision:
**quality-safe, no reproducible speed win; do not promote or submit**. Keep the
override plumbing for future dtype/kernel diagnostics while retaining BF16 as
the default scale dtype.

Artifacts:

- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-tp2-fp16-scales-20260711T183722Z`;
- pair-swapped full gate:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-tp2-fp16-scales-swap-20260711T184708Z`.

The first pair-swap launch at `20260711T184417Z` stopped before a benchmark
because the root filesystem had no free blocks. This is an infrastructure
failure, not a model result. The regenerable 27 GB home vLLM compile cache was
moved intact to `/mnt/usb-models/cache-archive/vllm-home-cache-20260711T184625Z`,
restoring 27 GB on NVMe; model weights, promoted caches, logs, and research
artifacts were not deleted. The pair-swap was then restarted.

## Position-Specific FC Checkpoint At MTP3

An independent audit found one untried combination: evaluate the preserved
five-position `allfc-allsteps-lr2e5` checkpoint at MTP3 instead of the costly
MTP5 endpoint where it was previously considered. Shared and position-FC
oracles ran simultaneously on GPUs 2 and 3 over all target-owned continuation
starts in the fixed 12-prompt corpus (`2338` starts, maximum three draft
steps, INT4-dequant draft LM head with group 128 and BF16 scales).

| oracle | accepted drafts/start | step-1 | step-2 conditional | step-3 conditional |
|---|---:|---:|---:|---:|
| shared FC | `1.012831` | `0.588537` | `0.505087` | `0.427338` |
| position FC | **`1.136014`** | `0.621471` | `0.550585` | `0.503750` |
| delta | **`+0.123182`** | `+0.032934` | `+0.045498` | `+0.076412` |

Every prompt cluster improved (`12/12`; minimum cluster delta `+0.005319`).
The prompt-cluster paired mean delta is `+0.121953` with an approximate 95%
CI of `[+0.085109, +0.158797]`, so this is a real acceptance improvement, not
noise, but the aggregate gain remains below the predeclared `+0.25`
accepted-token/step endpoint gate. The runtime patch would
also temporarily disable draft AOT/graph specialization, creating a likely
5-10% latency penalty. Decision: preserve this as a statistically positive
training result, but do not spend an endpoint build on this checkpoint. Reopen
only if a new checkpoint exceeds `+0.25` at MTP3 or position dispatch becomes
graph-safe with effectively zero steady-state cost.

Artifacts:

- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-mtp3-positionfc-pregate-20260711T184208Z/shared.json`;
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-mtp3-positionfc-pregate-20260711T184208Z/positionfc.json`;
- checkpoint:
  `/mnt/usb-models/llm-optimization-artifacts/qwen27-position-fc/mtp5-4gpu-20260709T225258Z/allfc-allsteps-lr2e5/model_extra_tensors.safetensors`;
- preserved runtime patch:
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-position-fc-adapter-runtime-20260709.patch`.

## Next Code Lane

The next structural prototype targets the 64 repeated verifier boundaries
`residual add -> post-attention RMSNorm -> dense gate_up W4A16` per MTP step.
Intel llm-scaler commit `db05b45831a5a534b74510797832dcf9b3c7e7ab`
contains a repaired row-1 reference kernel, but the Qwen27 TP2 verifier needs a
capturable M=4 implementation at local shape `K=5120, N=17408`. It must first
prove real-weight correctness, 512 graph replays, and at least `0.04 ms/layer`
savings before any vLLM integration.
