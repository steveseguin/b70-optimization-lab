# Strata and Flash-Next quantization candidates — 2026-10-10

> **Owner decision after this note (2026-10-10):** weights must come from the
> official publisher or Unsloth; other sources need a written justification and
> the owner's approval. The ISTA GSQ IQ3_S first trial below is therefore
> withdrawn for now. Allowed Flash-Next candidates from this inventory:
> Unsloth UD-IQ3_XXS (81.96 GB), UD-Q3_K_XL (89.99 GB), UD-IQ4_XS (93.68 GB),
> UD-Q4_K_XL (111.34 GB), or our own AutoRound INT4 from the official FP8.
> Strata itself is not used; its ideas may be. See
> [docs/own-xpu-runtime-objective.md](../docs/own-xpu-runtime-objective.md).

**Recommendation: first evaluate the full, unpruned GSQ-RCO IQ3_S on two B70s,
as a separate Strata/SYCL quantized lane.** Its two files total **83,617,662,656
bytes (83.618 GB / 77.875 GiB)**. The transformer shard is 54.818 GB, which
offers a plausible two-card fit with the lookup table offloaded. This is a
capacity/quality trial, not a ready vLLM package or a lossless FP8 replacement.
For the existing **vLLM XPU path**, prepare symmetric AutoRound INT4 first;
the compact FP8-PLE hybrid is the preferred later download only after its
mixed-format loader and offload contracts pass CPU checks.

No weights, contributed programs, GPU jobs, servers, containers or units were
run. No device or live endpoint was opened. Shell work used nice 19 and
`OMP_NUM_THREADS=2`; only source, metadata and small text files were read.
The read-only Strata clone and this task's scratch were removed after review.
The repository stayed on main. Existing work and all fault markers were
preserved. This is a research-and-plan task; nothing is queued.

## Evidence and scope

- [Intake status and attribution](../community/niko1221-strata-flash-next-quants/STATUS.md):
  `community-reported`, static review only, no validated boost.
- [Metadata inventory](../community/niko1221-strata-flash-next-quants/reported/metadata-inventory.json):
  HF repository revisions, exact file bytes, publisher LFS SHA256 values and
  hashes of inspected cards/configs. These are metadata claims, not payload
  verification. Search was bounded, not an exhaustive HF catalog.
- [Download allow-lists](../community/niko1221-strata-flash-next-quants/reported/proposed-downloads.json):
  exact filenames and hashes for the three ranked download options.
- Strata was cloned with `GIT_LFS_SKIP_SMUDGE=1`, depth 1, main only; inspected
  commit **61b3fb5dd3f1e8ec09cf7e4e05208bc6d3c46406**, approximately 73 MiB
  including Git. No install script or remote code was executed.
- vLLM source reference: **v0.30.0**, commit
  **ced6857afa0ea7b2e3f0846a62e1394e90f15607**. This is a static compatibility
  reference, not a launched image or a claim about current nightly.

The requested experiment-root README/handoff does not exist. The actual entry
points are the [result README](../results/qwen38-flash-next-fp8-b70/README.md),
[handoff](../results/qwen38-flash-next-fp8-b70/HANDOFF.md) and current
[reopen README](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/README.md).
The [scoreboard](../results/scoreboard.md) preserves **46.854250 tok/s**, four
cards, official FP8, BF16 KV, exact-GDN MTP1, fixed cold realistic suite.
The **875 tok/s two-card multi-user package is Qwen3.8 27B**, not Flash-Next;
Flash-Next's many-user trials did not pass its exact-output authority. Neither
result is evidence for any new quant. The current four-card fault halt still
requires the owner's resolution before native testing.

## What Strata supplies

[Strata](https://github.com/Niko1221/Strata/tree/61b3fb5dd3f1e8ec09cf7e4e05208bc6d3c46406)
is a C++ inference engine, API/server tooling, installers and GGUF packers.
Its primary backends are CUDA/HIP; an experimental SYCL backend includes B70
community reports. It consumes published weights from other authors. It is
not a collection of AWQ/GPTQ/AutoRound safetensors, and it does not train the
full GSQ-RCO quantizations itself.

`tools/iq_pack.py` arranges GGUF expert bytes for native use; `--compat-bf16`
can introduce additional rounding for ordinary GGUF projections. It does not
recover the original FP8/BF16 model. `tools/mtp_pack.py` does perform small
round-to-nearest draft quantization (Q2_0/Q4_0/Q8_0), explicitly not GSQ.
GSQ/RCO are separate IST-DASLab projects. The useful contribution here is
model discovery, mixed tensor allocations and a compact-runtime comparison.
No Strata code has been adopted into the lab overlay.

### Published weights linked by Strata

Decimal GB below are sums of HF file metadata at the inventory revisions;
target totals exclude optional vision/MTP files. These are one model family,
not 27B/35B size variants. Full Flash-Next has 125B transformer parameters,
about 51.2B additional lookup parameters and a separate MTP block.

| Publisher / variant | Format / effective transformer precision | Transformer + lookup download | Candidate status |
|---|---|---:|---|
| ISTA GSQ-RCO Q2_0 | Mixed GGUF, 2.40 bpw | 37.624 + 28.800 = **66.424 GB** | Smallest full-model option; more quality loss |
| ISTA GSQ-RCO IQ2_XS | Mixed GGUF, 2.50 bpw | 39.226 + 28.800 = **68.026 GB** | Capacity alternative; not uniformly IQ2_XS |
| ISTA GSQ-RCO IQ3_XXS | Mixed GGUF, 3.00 bpw | 47.040 + 28.800 = **75.840 GB** | Second GGUF choice if IQ3_S runtime headroom fails |
| ISTA GSQ-RCO IQ3_S | Mixed GGUF, 3.50 bpw | 54.818 + 28.800 = **83.618 GB** | **First capacity/quality trial on two cards** |
| ISTA Coder IQ1_M | Pruned 256/512 experts; retained weights around 3.5 bpw; effective 1.89 over original transformer | 29.608 + 28.800 = **58.409 GB** | Exclude from unchanged-model quant plan |
| UkisAI Swift 1.5 | Fine-tuned GGUF Q2_0 / IQ2_XS / IQ3_XXS / IQ3_S | **66.550 / 68.152 / 75.966 / 83.744 GB** | Separate trained model, not FP8 quantization comparison |
| Unsloth UD-IQ4_XS / UD-Q4_K_XL | Mixed GGUF | **93.683 / 111.335 GB** | Strata regular/experimental options; larger than GSQ choices |
| Unsloth UD-Q6_K_XL | Mixed GGUF, Q8_0 lookup | **169.165 GB** | Manual experimental path; poor capacity target |
| OrcaRouter Uncensored IQ3_XXS | Modified-model GGUF | **85.203 GB** | Manual compatibility packing; exclude from unchanged-model plan |

HF sources: [ISTA full](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF/tree/ed59f92082b1e93c0e96d60a8b11aab089b52f09),
[Coder](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF/tree/5348543e0147355ac9cbcb031184a3546350988e),
[Swift](https://huggingface.co/ukisai/Swift-1.5-Qwen3.8-Flash-Next-GSQ-RCO-GGUF/tree/99bb8f7f95c7aa7b24a36a7786a4f657b30f5d3d),
[Unsloth](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/tree/766911a6b7369840a91dbcd95f9f997acaab6cd6),
[OrcaRouter](https://huggingface.co/orcarouter/Qwen3.8-Flash-Next-Uncensored-GGUF/tree/e43d00f4e2b8b40b89f75e9adeb1045ac34c8acc).
Strata's installer pins older Swift/Unsloth revisions and allows a missing-pin
fallback; lab acquisition must fail closed instead. Do not mix these snapshots.

Unsloth also publishes BF16 (354.030 GB), Q8_0 (188.225 GB), UD-IQ1_S/M
(72.546/74.539 GB), UD-IQ3_XXS (81.962 GB), UD-Q2_K_XL (78.869 GB),
UD-Q3_K_XL (89.986 GB) and UD-Q5_K_XL (158.286 GB). Inventory does not establish
Strata support for every GGUF in that repository. The ISTA vision projector is
907,543,008 bytes and is unnecessary for the first text-only trial. MTP is a
separate acquisition/quality decision; do not silently let setup fetch it.

### Quantization details and reported quality

ISTA's per-tensor allocation files are preserved unchanged in the intake.
The filename is a size class: IQ3_S mixes IQ2_S, IQ3_S, IQ3_XXS, IQ4_NL,
IQ4_XS, Q2_0, K-quants and floating tensors. GGUF block geometry is not AWQ
group size: Q2_0 uses 64 weights, IQ4_NL uses 32, and K/I superblocks generally
use 256 (see Strata's `third_party/ggml/ggml-common.h`). The 640-wide expert
down input is not divisible by 256, so its choices are constrained. Inspect
the actual tensor map, not just the suffix. All four full ISTA variants use
the same **IQ4_NL lookup table**, another precision change versus official FP8.

GSQ optimizes discrete quantization assignments/scales; RCO assigns tensor
formats under a size budget. The full-model release card does **not** specify
a reproducible calibration dataset revision, sample count, sequence length,
seed, full optimizer schedule or source-model revision. Record those as
unknown; general tooling defaults are not this release's calibration recipe.
Coder describes code/agentic/vision calibration but omits a fully pinned mix.
Swift supplies recipe/provenance files and disjoint reporting data, but changes
the trained model. These gaps prevent independent quantization reproduction.

Publisher-reported task averages against BF16 are 93.12 (base), 89.07 (Q2_0),
89.16 (IQ2_XS), 92.57 (IQ3_XXS) and 93.26 (IQ3_S). IQ3_S's LiveCodeBench v6
is **86.86 versus 87.43**, so “matches every task” is not an exact claim.
The authors themselves attribute small above-base scores to variance. Coder
reports SWE-bench 75.60 versus 82.80 and LiveCodeBench 86.28 versus 87.43 at
xhigh effort. None is a B70 measurement or an FP8-relative quality result.
[Pinned ISTA model card](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF/blob/ed59f92082b1e93c0e96d60a8b11aab089b52f09/README.md).

### Licenses

Strata code: MIT, Niko1221 and contributors. Bundled ggml/llama.cpp components:
MIT, with their own notices. Model weights are separate. ISTA full/Coder cards
say `apache-2.0` in metadata but say they inherit Qwen's license in the body;
the upstream model names **Qwen Community License 1.0**. Keep that conflict
explicit and resolve the weight license before redistribution. Intel,
albucino, NVIDIA and Unsloth cards identify inherited Qwen terms. Swift adds
**Swift Open License v1.0** to its contribution and retains Qwen terms for
base components. Orca and the inspected MXFP4 card also carry Apache metadata;
that alone does not establish rights over the base. This is a license inventory,
not clearance to publish weights. Preserve the source LICENSE/NOTICE chain.

## Mapping to vLLM XPU 0.30.0

The architecture is **Qwen4ExpForConditionalGeneration**, not the dense 27B
model: 48 layers comprising 36 Gated DeltaNet and 12 Qwen Sparse Attention
layers; hidden width 2560; 512 routed experts, top-10, intermediate width 640;
one shared expert; four hyperconnection branches; PLE lookup; one MTP block.
This is why dense INT4 success does not establish Flash-Next support.

| Format / concrete artifact | XPU 0.30 source support | Flash-Next work remaining |
|---|---|---|
| Official FP8 | Existing lab FP8 route and certified historical overlay | Current 0.30 refresh/loading stability remains unqualified; preserve old record |
| Symmetric AutoRound/GPTQ INT4 g128 | INC → AutoGPTQ MoE → XPUExpertsWNA16; native dense support too | PLE config dispatch, packing, EP maps, exact shapes, offload, model/MTP gates |
| AWQ asymmetric g32 in compressed-tensors | Dense support exists; XPU MoE selector accepts symmetric keys only | Asymmetric expert zero-point/packing/kernel support; not a CLI-only change |
| GGUF GSQ/Q2/IQ/K formats | No qualified native Flash-Next GGUF/XPU path | Separate Strata/llama.cpp runtime, or substantial format loader/kernel work |
| MXFP4 | XPUExpertsMxFp4 and dense routes exist | Artifact scheme/scales/activation mode and hybrid PLE/attention dispatch must match; B70 Flash-Next unqualified |
| NVFP4 | No qualified B70 Flash-Next route found | NVIDIA NVFP4 scaling/kernels are not MXFP4 or integer W4A16; substantial port or a new quant identity |

Source: [XPU expert classes](https://github.com/vllm-project/vllm/blob/ced6857afa0ea7b2e3f0846a62e1394e90f15607/vllm/model_executor/layers/fused_moe/experts/xpu_moe.py),
[WNA16 selection](https://github.com/vllm-project/vllm/blob/ced6857afa0ea7b2e3f0846a62e1394e90f15607/vllm/model_executor/layers/fused_moe/oracle/int_wna16.py),
[INC dispatch](https://github.com/vllm-project/vllm/blob/ced6857afa0ea7b2e3f0846a62e1394e90f15607/vllm/model_executor/layers/quantization/inc/schemes/inc_wna16_scheme.py).
`XPUExpertsWNA16` accepts `kInt4Static`/`kInt4Static32`, not the asymmetric key.
Use W4A16; an optional W4A8 backend changes activation arithmetic and needs a
separate quality decision. A vLLM quant-method registration is not a model pass.

The [MiniMax INT4 recipe](../docs/b70-minimax-ubuntu24-deployment.md) demonstrates
MoE experience, while [Qwen3.6 27B AutoRound](../results/qwen36-27b-autoround-int4-b70/README.md)
provides dense INT4/repacking and determinism lessons. Neither certifies this
model's 512-expert geometry, GDN, QSA, PLE or target hashes. Follow the current
research-map verdict, not the historical INT4 headline alone.

### Native-format alternatives discovered during metadata review

These are **not Strata-produced artifacts**. File totals include all listed
safetensors unless the row explicitly excludes a nested draft.

| Artifact | Revision | Format, calibration / reported quality | Weight files |
|---|---|---|---:|
| [Intel W4A16 AutoRound](https://huggingface.co/Intel/Qwen3.8-Flash-Next-W4A16-AutoRound) | `4c67bf686b7f7fd386bae6b07ab59e8ff1d5b897` | Symmetric g128, AutoRound 0.15, GPTQ packing; 200 iterations; sensitive paths/PLE/MTP excluded. Calibration dataset/seed not specified by card. Four-task average .8332 vs BF16 .8362, publisher only | **181.196 GB**, 17 shards |
| [albucino W4A16 + FP8PLE](https://huggingface.co/albucino/Qwen3.8-Flash-Next-W4A16-FP8PLE) | `c6af9fee7ad2cb8ef44b534a99b8c1b81fb0f6da` | Intel g128 experts plus RadixArk FP8 lookup; no matched FP8 quality gate. CUDA custom runtime claims do not validate XPU | **124.781 GB**, 25 target shards; optional g32 draft **4.140 GB** |
| [cyankiwi AWQ INT4](https://huggingface.co/cyankiwi/Qwen3.8-Flash-Next-AWQ-INT4) | `d39638a0e740fccb3e24ae0ea5cab34c15371ae6` | Compressed-tensors, asymmetric g32, MSE observer; STEM/agentic multilingual calibration link; exact run recipe and quant-specific quality evidence incomplete | **188.286 GB**, 38 shards |
| [NVIDIA NVFP4](https://huggingface.co/nvidia/Qwen3.8-Flash-Next-NVFP4) | `fc694b54fb0174e0913e6adf86691ef85a4ead47` | Float4 weight/activation groups16; do not equate with INT4; calibration/quality not reproduced | **132.680 GB**, 11 shards |
| [tcclaviger MXFP4-FP8-GPTQ](https://huggingface.co/tcclaviger/Qwen3.8-Flash-Next-MXFP4-FP8-GPTQ) | `6fe3e7464c1892004f886b4b614117333c5acd34` | Compressed-tensors float4 g32 experts plus FP8 attention; calibration/quality not reproduced | **120.301 GB**, 26 shards |
| [azampatti INT4 AutoRound](https://huggingface.co/azampatti/Qwen3.8-Flash-Next-125B-A5B-INT4-AutoRound) | `1464274120d36a4d8fcaa934552334a7d83ce0fd` | **Exclude:** top-10 → top-5 routing plus trained shared-expert healing; not just a quant | **130.769 GB**, 105 files including nested components |

Intel is the simpler provenance control but retains a **102.4 GB BF16 lookup**.
The current lab `screen1b_ple.py` is FP8-specific; it cannot simply map Intel's
table. INC config needs PLE dispatch support. The hybrid has the reverse
problem: inherited INC settings describe a 16-bit ignored PLE while serialized
bytes are FP8 plus scales. It needs an explicit mixed PLE loader contract.
Do not copy the contributor's swap, prefix-cache, INT8-KV or CUDA-UVA defaults.

## Capacity and speed arithmetic — projections, not measurements

Use both GB and GiB. Two nominal 32 GiB cards total 68.719 GB; actual usable
VRAM must be measured later without changing ECC or any power setting. A
planning reserve of **4 GiB per card** leaves 30.065 GB/card for weights;
this reserve is an assumption covering KV, PLE working rows, graphs and
workspace, not an admission result.

| Candidate | One card under that assumption | Two cards under that assumption |
|---|---|---|
| GSQ IQ3_S, 54.818 GB transformer | At least **24.753 GB** transformer offload, plus lookup outside VRAM | About **27.409 GB/card** before imbalance; transformer could fit; lookup remains outside VRAM |
| GSQ IQ3_XXS, 47.040 GB transformer | At least **16.975 GB** transformer offload | About **23.520 GB/card** before imbalance |
| GSQ Q2_0, 37.624 GB transformer | At least **7.559 GB** transformer offload | About **18.812 GB/card** before imbalance |
| Hybrid AutoRound, 73.551 GB non-PLE tensor payload | At least **43.486 GB** non-PLE offload | At least **13.421 GB** non-PLE offload |
| Intel AutoRound, ~78.796 GB files excluding BF16 lookup | More than **48.7 GB** offload, plus lookup | More than **18.6 GB** offload, plus lookup |

Hybrid uses its card's 124,750,778,874-byte target tensor payload less 51.2 GB
PLE; file headers explain the larger download. Intel's figure is a rough
file-level bound, not a final tensor census. Target-only can avoid unused MTP
allocations but cannot omit an arbitrary shard containing other tensors.
Neither native INT4 candidate is an all-resident one- or two-card model.
An expert-selective streaming/cache path is required; generic module offload
can transfer much more than the top-10 active experts. A 15 GiB host is not
the target for these offload designs.

For GSQ on this 128 GiB host, keep lookup mmap-backed with bounded working
rows; avoid retaining duplicate full expert arenas after GPU upload. For
the hybrid, plan at least 51.2 GB lookup backing plus the offloaded experts,
or demand-map the lookup with explicit host accounting. Intel needs a BF16
demand-mapped lookup to avoid exhausting host RAM. Pinned allocations, driver
backing, repacking transients, worker replicas and the approved memory exclusion
must be in the census. Loading guards stay enabled; a guessed low container
memory cap with swap is not a solution.

The 12 QSA layers' raw BF16/FP16 K+V cost is
`12 × 2 KV heads × 256 × 2 × 2 = 24,576 bytes/token` before runtime extras:
about 0.101 GB at 4K, 0.805 GB at 32K, 6.442 GB at 262K, aggregate if sharded
without replication. Add GDN state, indexer cache, MTP and concurrency. Start
at 4K and one user; neither weight fit nor upstream context claims certify 32K.

Symmetric INT4 g128 with 16-bit scales costs approximately
`0.5 + 2/128 = 0.515625 bytes/weight`; block FP8 with FP32 scales costs
`1 + 4/(128×128) = 1.000244`. The expert traffic reduction is **1.94× at equal
card count**, before packing/padding. With half as many cards, TP2 INT4 has
only **0.97×** the TP4 FP8 expert-only bandwidth capacity; TP1 has **0.485×**.
Consequently the 46.854250 tok/s line does not imply a 90+ tok/s two-card quant.
At the same topology, if experts account for fraction f of elapsed time, an
idealized bound is `1 / ((1-f) + f/1.94)`; f has not been measured for this
candidate. Offload, dequantization, GDN, QSA and MTP acceptance can dominate.
GGUF mixed grids need their own active-byte census and kernel efficiency data.
Strata's two-card path splits layers, not tensors. At one user, successive
layers run on their owning cards, so two cards do not automatically double
bandwidth. If every active tensor were provisionally treated as 3.5 bpw,
serial layer-split IQ3_S versus ideal four-way FP8 tensor parallelism would
have a rough `(8/3.5) / 4 = 0.57×` bandwidth ratio. Eliminating offload and
collectives may offset that disadvantage, but the amount is unknown. RCO's
bpw is a whole-transformer average, not a measured active-expert ratio.
Strata's reported GPU speeds use different prompts, KV and runtimes; no B70
speed forecast or public performance curve is justified here.

## Ranked execution plan

1. **CPU preparation first, no download:** retain the intake; finish a
   source-level Strata SYCL audit and a separate INC/PLE loader fixture.
   Confirm all 48 layers' tensor names, quant formats, 512/top-10 routing and
   scales. Review current sealed patches individually against newest upstream;
   keep existing bundles/hashes unchanged. Prepare a preregistered two-card
   target-only quality/capacity trial, without launching it.
2. **First quant trial: ISTA IQ3_S on two B70s, separate Strata/SYCL runtime.**
   Highest reported full-model quality among these compact candidates, with
   plausible resident transformer capacity. Use Strata's **layer split**
   (the inspected implementation requires a temporary `--serve` process),
   not vLLM TP2; this server is only a later authorized experiment. Use
   text-only, MTP0, 4K initial
   context and **`--kv fp16`**. This is accepted by the pinned SYCL
   `src/program/generate.cpp` (default field and parser), despite installer
   examples using compressed KV. Verify actual allocated dtype later.
   Native FP16-path quality/performance is unmeasured here. Audit and disable
   prompt reuse, checkpoint resume, learned/history drafting, expert skipping,
   steering/experimental speed projection and approximate verifier options.
   A cached expert's unchanged weight bytes are allowed; cached prompts are not.
   If some required exact path is absent, fix it or stop that arm; do not quietly
   switch to INT8 KV. A source build is needed; Intel release binaries are not
   supplied. This does not replace the vLLM FP8 lane.
3. **Preferred vLLM quant: hybrid AutoRound g128 + FP8 PLE**, only after CPU
   loader fixtures prove the mixed contract and an offload design fits. Verify
   tensor provenance to pinned Intel and RadixArk sources before borrowing
   their quality claims. Start TP2+EP2/MTP0 with BF16 KV; stage a bounded
   symmetric W4A16 expert offload/repack path. First clear operator-shape and
   determinism gates; then the model endpoint. Retain Intel's plain g128
   checkpoint as the simpler fallback if hybrid provenance/loader work fails,
   accepting its larger storage and BF16-mmap work.
4. **Capacity fallback:** IQ3_XXS two-card, then IQ2_XS/Q2_0 only if the owner
   accepts their observed quality tradeoff. One-card offload follows a measured
   two-card reference; it is not a low-effort configuration change.
5. **Later research:** model-specific MXFP4 qualification, asymmetric AWQ
   kernels, or lab-produced quantization. Coder, top-5 healing, Swift and
   uncensored derivatives remain separate model decisions, not shortcuts for
   this lane. NVFP4 is lower priority for B70 than existing symmetric INT4.

### Exact disk request

First acquisition, revision `ed59f92082b1e93c0e96d60a8b11aab089b52f09` of
`ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF`:

| File | Bytes |
|---|---:|
| `IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf` | 54,817,524,224 |
| `IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf` | 28,800,138,432 |
| **Total** | **83,617,662,656** |

Allow **100 GB incremental workspace** for these files, small tokenizer/config
assets, dense pack, source build and receipts, retaining the existing **50 GiB
free-space reserve**: require at least **153.687 GB available** on the approved
destination before admission. This assumes GGUF-in-place expert reads, not a
second `experts.bin`. If the selected SYCL pack requires duplication, add its
measured size and obtain a revised storage decision first. No MTP or vision
download belongs in this request. Do not use setup's auto-download path.

The October 10 [storage inventory](2026-10-10-storage-inventory.md) had only
95.285 GB available and proposed a still-unapproved 42.018 GB recovery. Even
that recovery gives about **137.303 GB**, below the 153.687 GB admission budget.
It would leave only about 53.685 GB after the two GGUFs alone, just below the
50 GiB reserve, with no build/pack room. Fresh capacity and mount ownership
checks are mandatory; this note grants no deletion or model move.

For the native hybrid, the allow-list names all **25 root safetensors files**
at `c6af9fee7ad2cb8ef44b534a99b8c1b81fb0f6da`, **124,781,270,509 bytes**.
Also acquire matching config, index (23,657,880 bytes), tokenizer
(19,989,325), tokenizer config (1,165), chat template (8,952), generation
config (214), hybrid_sources (1,155), LICENSE (3,235), and SHA256SUMS (9,453).
Small text-only assets total **43,937,850 bytes**, including config (266,471).
Plan **150 GB incremental / 203.687 GB available** with the reserve, provided
no second repacked checkpoint is written. Optional nested draft adds
4,140,094,152 weight-file bytes plus its config/tokenizer; it is not in the
target-only request. Intel fallback needs **181.196 GB weights** and a
provisional **210 GB incremental / 263.687 GB available** budget. Repacking
duplicates require extra space. HF cache plus a copied local directory must
not silently double any estimate.

### CPU-only preparation before approval

Completed here: pinned source/metadata review, allocation inventory, exact
download lists, quant dispatch audit and capacity arithmetic. No full model
index or weight payload was required for those conclusions. Some large index
responses were deliberately bounded and are not retained or treated as a
complete tensor census.

Next reversible preparation can be done without weights or GPU access:

- Read small GGUF headers or safetensors headers using strictly bounded Range
  requests that refuse a server ignoring Range; count bytes by expert, dense,
  lookup, MTP and vision. Do not stream tensor bodies. Record missing metadata
  rather than filling it from another quant. Pin file hashes from HF metadata.
- Build synthetic CPU packed tensors for g128 expert shapes 2560×640 and
  640×2560; check bit packing, signedness, scale axes, fused gate/up order,
  EP rank maps and shard coverage. Exercise INC/PLE factory dispatch with
  mocks, with device initialization forbidden. Do not import a runtime that
  probes XPU devices merely for a “CPU check”.
- Model all rank allocations, duplicate host/device staging, lookup page
  working set and repack peaks. Adapt the existing guarded loader accounting;
  no swap/cache/power change, no below-working-set cap, no watchdog removal.
- Stage an isolated source patch/config proposal and CPU fixture tests under
  the new quant experiment identity; never edit frozen FP8 runtime trees or
  rewrite their pinned hashes. CPU compile/import checks are not native proof.
- Pin evaluation datasets, prompts, settings, scoring scripts and baseline
  identities; estimate disk before fetching any dataset. Package the future
  trial as an explicit stage list with one launch per stage, graceful teardown,
  current fault admission, five-minute stop gap and no automatic restart.

### Launch identity to record later

Record source image tag, resolved registry manifest digest, local image ID,
creation time, upstream commit, torch/vLLM/Transformers/XPU-kernel/oneCCL
versions and overlay patch hashes. Pull/resolve newest upstream only when
authorized runtime work begins; preserve historical 0.30 and A367 anchors.
Inventory every accepted patch as upstreamed, ported, blocked or rejected,
separately from environment/topology/cache/compilation settings.

Bind model repo/revision, every shard hash, tokenizer/template/config hashes,
per-tensor quant and scales, PLE origin/precision, unchanged 512/top-10 routing,
target/draft identity and KV/GDN-state dtypes. Record GPU PCI IDs/order, usable
VRAM, driver/kernel/firmware, host memory exclusion, TP/EP/PP, concurrency,
context, batching, graph sizes, `COMPILATION_CONFIG`, GPU memory utilization,
`XPU_GRAPH`, `VLLM_XPU_ENABLE_XPU_GRAPH`, forced/noop communication graph flags,
GDN fallback, sampler/top-k fallbacks, async scheduler, full extra args and all
diagnostic flags. Add offload/cache capacities, thread counts, placement maps,
host allocator/driver environment, seeds, thinking mode, raw command and logs.
Strata additionally needs compiler/oneAPI/ggml revisions and every runtime
option. Record explicit false values for prompt/KV/response reuse.

## Quality acceptance and measurement

A quantized target is a **new, lossy numerical identity relative to FP8**.
Exact outputs on a few prompts cannot certify losslessness. The owner's
request authorizes research into quants, not silent replacement of the FP8
headline or acceptance of a particular quality loss.

Use two independent comparisons:

1. **Target quality versus FP8 and upstream claims.** Run matched tokenizer,
   prompts, reasoning effort, sampling/seeds, response budgets and scored
   tokens. Add a pinned teacher-forced NLL/perplexity harness: at least 100K
   held-out tokens per prose, code and multilingual stratum, identical windows
   and BOS handling, logprob coverage checks, corpus hashes, NLL delta and
   PPL ratio. Existing exact-response clients do not supply this measurement;
   the evaluator is new work. Where top-k logprobs omit the true next token,
   obtain exact scoring rather than treating missing probability as zero.
   Pair with the five zero-shot tasks in ISTA's claim, AIME25, GPQA-Diamond,
   LiveCodeBench v6, and practical code/arithmetic/JSON/tool/long-context tests.
   Reproduce upstream settings before calling a claim confirmed; BF16 is the
   upstream reference, so FP8 comparison alone cannot confirm it. If BF16 is
   unavailable, label that claim check pending. Report all per-task deltas,
   uncertainty and failure examples, not only an average.
   A Strata-quant versus vLLM-FP8 comparison measures the complete serving
   stacks, including arithmetic differences. To isolate quantization error,
   score both through a matched reference implementation (including a verified
   dequantization reader); otherwise retain the runtime difference as a
   confound and do not attribute the entire delta to weight precision.
2. **Implementation correctness within the accepted quant.** Reuse
   [Qwen text gates](../scripts/qwen38-text-quality-suite.py),
   [thinking-quality gates](../scripts/qwen38-official-thinking-quality.py),
   [Flash-Next long-context fixture](../experiments/qwen38-flash-next-fp8-b70/fixtures/long-context-semantic-16k-v1.json)
   and frozen certification structure. Establish a new same-kernel MTP0 oracle
   with deterministic same-server and fresh-server repeats. Verify loader
   output against the published quant reference, then require every optimized
   path/MTP accepted token to match its unchanged target. Do not reuse FP8
   hashes as the INT4 oracle. A batch-shape drift triggers the operator census
   before endpoint bisection.

Proposed screening thresholds for owner review: no hard practical-canary
regression; upper confidence bound on relative PPL increase ≤3% in each
stratum; no task drop exceeding 1 percentage point without explicit review.
These are proposed tolerances, not an existing lane policy or automatic
publication gate. Sample size must support the bound; inconclusive is not a
pass. Larger observed losses are recorded and left to the owner.

Only after target acceptance and correctness, use the
[fixed realistic suite](../scripts/bench-openai-realistic-suite.py): all varied
classes, each prompt once cold, `cached_tokens=0`, 512-token natural-completion
cap, conventional 99-interval rate and class-balanced median. Retain p10,
mean, TTFT, wall rate, full-completion rate, prompt/output hashes and cache
logs. Report separately measured 512-input, one-user prefill; “not measured”
until it exists. Require at least two fresh servers, retain every failure,
and assess concurrency/context only at measured points. Use a new quality
label and hash-bound promotion attestation; no Strata or quant speed goes into
the certified FP8 row. Publication remains a later owner-reviewed task.

## Producing a lab quant

Strata is not the full-model quantizer, so there is no supported “run Strata
on B70 to produce AWQ” recipe. Its CPU packers can rearrange existing GGUFs
and produce a small RTN draft, which does not create a new calibrated target.
Do not dequantize GSQ and requantize to INT4 while calling it the same model.

If published candidates fail, prefer **AutoRound symmetric W4A16 g128** from
the original BF16 target as the vLLM-oriented production project, or GSQ/RCO
for a GGUF research project. Pin dataset/sample count/length/seed, exclusion
list and algorithm revision; preserve routers, attention/GDN/hyperconnections,
norms and the selected PLE precision deliberately. Keep the full expert count
and top-10 routing. Quantizing from existing FP8 avoids a download but compounds
rounding and creates a different provenance/quality class; owner chooses it.

Inspected tool references: [GSQ 03fc16484c369e3127225615d5e03e8d3a6043e3](https://github.com/IST-DASLab/GSQ/tree/03fc16484c369e3127225615d5e03e8d3a6043e3)
and [RCO 9a1e09c07d468109cbe60a1b87d5036034a79d10](https://github.com/IST-DASLab/RCO/tree/9a1e09c07d468109cbe60a1b87d5036034a79d10).
GSQ describes layerwise/expert-parallel calibration on CUDA/Hopper; it does
not establish a B70/XPU training path. Its CUDA/flash-attention/NCCL assumptions
need a port and operator checks, or separately approved access to suitable
CUDA hardware. CPU-only full-model calibration has no credible time estimate
here. Four 32 GiB cards are not interchangeable with one 128 GiB accelerator:
weights, trainable quantizer logits, gradients, optimizer state and activations
must fit each layer/expert partition. Begin with a bounded representative-layer
pilot only after GPU authorization, measure peak RAM/VRAM and seconds per
iteration, then estimate all 48 layers plus lookup/MTP work. No hours-to-finish
claim is supported yet; use the measured pilot to request a campaign window.

Storage lower bound for a fresh BF16-source project is approximately **360.0 GB
source + 84–181 GB output**, before caches/checkpoints. Reserve at least
**500–600 GB incremental** for a single-output layerwise project, then add the
50 GiB free reserve and measured intermediate requirement. A multi-format
GSQ/RCO database can require **over 1 TB**; inventory its candidate ladder
before approving that path. These are planning budgets, not measured peaks.
The present NVMe cannot admit either. No unapproved cleanup, external-store
move, full BF16 download or quantizer run follows from this research note.

## Owner decisions before execution

Approve a destination with the first trial's **100 GB incremental budget plus
50 GiB untouched reserve**, or a different explicit capacity plan; the current
cleanup proposal alone is insufficient. Approve the separate Strata/SYCL
two-card quant trial and its quality tolerances, or choose the larger native
vLLM AutoRound development path. Resolve the existing host fault halt and
allocate an idle GPU window before any native work. Weight redistribution and
public promotion need a later license/evidence review. CPU-only preparation
can continue without any of those operational actions.
