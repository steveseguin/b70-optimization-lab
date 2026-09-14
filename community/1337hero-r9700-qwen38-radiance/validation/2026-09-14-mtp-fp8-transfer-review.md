# Radiance ideas with official FP8 and native MTP retained

Reviewed September 14, 2026 against Radiance 1.0.16 source
`f295b9ef51ad413a68e4192371e0377741a354ce` and the installed qualified R304
B70 service. The user excludes DFlash. This review makes no model requests,
loads no model, and changes no installed runtime code. Read-only source copies
from the serving container establish the actual baseline; external files were
read as source, not executed.

**There is no substantial ready-to-adopt lossless speedup established here.**
One small MTP bookkeeping cleanup is concrete enough to prepare. Exact
native two-card communication is the strongest larger engineering lead.
Other techniques either already exist, have closed negative tests, target a
backend we do not use, or change target arithmetic.

## Ranked decisions

| Idea | What it would change here | Decision |
| --- | --- | --- |
| Avoid unused MTP metadata work | Build a GPU query-length tensor only in the mixed-request branch that consumes it | Small inactive patch prepared; no target arithmetic or draft-policy change. Source validation only; timing and full output gates pending. |
| Exact native two-card communication | Replace clone plus general XCCL reduction with dedicated out-of-place peer exchange and reduction | Strongest larger lead; native SYCL/Level Zero implementation and strict synchronization/arithmetic gates required. Not a flag or a current adoption. |
| Convolution channel tiling | Schedule independent channels in wider tiles without changing their four-tap accumulation | Worth retaining as a kernel design reference. Their Triton patch is outside our active native XPU path; no direct change to adopt. |
| Record actual operator shapes and dispatch; tune offline | Verify that configured chunk sizes reach intended kernels; avoid tuning live requests | Useful practice, largely already followed by this lab. No additional runtime setting or measured gain established. |

The small patch is deliberately separate from the larger communication work.
No reliable percentage improvement is predicted for either. A skipped metadata
operation should not be presented as a substantial prefill optimization.

## Smallest concrete MTP candidate

Radiance's [metadata patch](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/patch_gdn_metadata.py)
focuses on integer bookkeeping and avoiding unnecessary tensor operations.
Its description mentions skipping the GPU query-length subtraction, but its
actual replacement retains that eager subtraction. The useful transfer is the
source-level observation, not blindly applying the supplied patch.

The installed B70 metadata builder computes
`query_start_loc[1:] - query_start_loc[:-1]` before choosing its all-speculative
or mixed-request path. All uses of that result occur in the mixed branch.
Moving that one assignment into the branch removes unused device work from
steady MTP decoding while preserving every consumer and its inputs. It does
not skip target verification, reuse prompts, change MTP depth or compress data.

The [MTP audit](2026-09-14-mtp-audit-source.md) records the exact source identity
and [inactive patch with source proof](2026-09-14-mtp-audit-query-lens/README.md).
Before serving it, carry the delta onto the current reviewed upstream overlay,
check non-speculative, all-speculative and mixed metadata paths, then require
complete output/state equality and a matched latency screen. No application
reload was performed for this research task. The larger torch-to-NumPy rewrite
is not included: integer values alone do not establish equivalent tensor
aliasing, ownership, pinned-memory or asynchronous-copy lifetimes.

## Larger lead: uncompressed peer communication

Radiance/libr4d supplies a concrete exact two-rank implementation: persistent
double-buffered peer scratch, device counters, per-block handshakes and local
addition. Our current communicator clones each input, runs XCCL and waits.
A dedicated out-of-place implementation could remove a copy and some generic
collective overhead. The lab already proposed this in its September 4 profile;
Radiance contributes an implementation reference, not the original lab idea.

This is substantial engineering. AMD fine-grained IPC and instruction-level
ordering are not Intel guarantees. The reviewed peer timeout can continue into
reduction without reporting failure; that behavior must not be copied. The
FP16-via-FP32 addition must match our qualified XCCL results, including difficult
values, and buffers must remain correct across changing messages and reuse.

The [exact communication audit](2026-09-14-exact-comm-review.md) records the
pinned kernel, limitations and admission gates. Recent prefill traces include
20.5–27.2 ms summed all-reduce time per rank versus 107–112 ms matrix work;
those overlapping/waiting times are not request latency or predicted savings.
The idea merits a separate bounded native feasibility project, not disruption
of the recovered service during a source investigation.

## Kernel ideas that do not directly transfer

**Convolution channel tiling.** Their
[patch](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/patch_conv1d_blockn.py)
widened prefill `BLOCK_N` from 256 to 1024. Each channel retains the same
four-tap arithmetic; the changed scheduling addresses wide-stride memory
access and AMD occupancy. Their source reports a 2.22x isolated AMD kernel
result at 3296 tokens, not a B70 model speedup. It explicitly leaves decode
alone after a regression. Our served `forward_xpu` calls
`gdn_attention_core_xpu`, which dispatches `_xpu_C.gdn_attention`; editing the
Triton `causal_conv1d.py` constant would not change that native route. A native
port needs actual convolution-only timing and production-stride tests before
further work; total GDN time is not convolution time.

**Weight layout and non-temporal loads.** The RX5 gains pair fragment-order
MXFP4 weights with AMD decode loads. The idea of organizing data for kernel
access is sound, but it is not a switch for our FP8/FP16 oneDNN path. Keeping
FP8 weight bytes does not guarantee the same accumulation order. The native
B70 matrix path already prepares weight scales once, uses transpose views and
caches primitives. Their
[activation-scale transpose avoidance](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/radiance_kernels.py#L44-L53)
saves a W8A8 preparation step that our W8A16 route already avoids entirely.

**Skinny matrix kernels.** Their
[dispatcher](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/radiance_gemm.py#L43-L94)
leaves the GDN BA shapes outside the default shape table. Its own notes record
small output differences and lower draft acceptance despite faster kernels.
Those shapes require an override; the default enabled MoE-gate shape is not
this dense model. The claimed M band also starts at six rows, above our c1
MTP1 band. This is useful negative evidence, not a lossless optimization to port.

## Closed or excluded

- **Merged GDN projections:** their MXFP4 operands share one format; ours are
  heterogeneous FP8 QKVZ and FP16 BA. The exact dispatcher-only adaptation
  already tested neutral. Do not repeat that screen unchanged.
- **Draft-only low-precision output head:** already used by our MTP setup,
  while retaining the full target head. No new imported gain.
- **Per-rank draft argmax instead of full-logit exchange:** pre-existing
  lab/upstream idea. The earlier MTP2 screen was output-exact but measured
  -0.98% at c1 and -8.70% at c64; remains off absent new bottleneck evidence.
- **Confidence/history-based draft loop termination:** no remaining loop to
  shorten at MTP1; history n-grams are outside our benchmark policy. No adoption.
- **Shared V2 graph metadata, ROCm graph stream fixes and AITER geometry:**
  not applicable verbatim to the qualified V1/native-XPU service.
- **Removing XCCL waits or wrapping collectives for compilation:** already
  neutral here; no repeated wait/flag sweep.
- **Target INT2 shortlists, compressed all-reduce, FP8 activations/KV and
  normalization/quantization fusions:** outside the retained target arithmetic
  and lossless identity requirements.
- **DFlash:** excluded by user instruction, independently of the prior startup
  incident. Native MTP remains selected.

## Evidence and credit

The [kernel review receipt](2026-09-14-fp8-kernel-review.json) records 21 pinned
Radiance source files and hashes of installed B70 source snapshots. The
[communication receipt](2026-09-14-exact-comm-review.json) separately binds the
actual libr4d kernel and current communicator. Prior local results remain in
[the transfer packet](../../../experiments/qwen38-27b-b70/notes/2026-09-14-amd-transfer-results.md)
and [prefill profile](../../../experiments/qwen38-27b-b70/notes/2026-09-14-fp8-prefill-focus-results.md).

1337Hero is acknowledged for the benchmark lead, StillDeadcode for libr4d,
Brian/ggz14 for MXFP4 layout work, and magiccodingman/Radiance for the integrated
source and reports. The prepared metadata delta is a lab adaptation of a
source observation. No validated B70 boost or runtime integration is claimed.
