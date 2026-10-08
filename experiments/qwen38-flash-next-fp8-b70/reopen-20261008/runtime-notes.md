# Screen 1b runtime/source review (2026-10-08; CPU only)

Scope: static portability and experiment preparation under the repository's
review-model-contribution skill. Lumnus/wu1ff deltas remain community-reported;
no new speed, exactness or safe memory-fit result has been measured.

## Runtime choice

Choose official `vllm/vllm-openai-xpu:v0.30.0`, resolved to the inspected amd64
manifest, with the reviewed Lumnus Python files and lab port applied as hash-checked
replacements of the corresponding installed files. This is the cheapest way to screen a modern runtime without a
native compile. Do not mount a whole `vllm/` directory over site-packages: that
can hide wheel-provided compiled/Rust artifacts. Run from `/`, because the image's
`/workspace/vllm` source checkout otherwise shadows the installed package.
Pin each overlaid file and the official image digest. This is a **partial modern
stack**, not Lumnus's complete served stack. Static compatibility is not proof of
successful FP8 loading or adequate GPU memory.

Source inputs in `/home/steve/src/lumnus-20261008/`:

- `vllm` HEAD `9d79d28d7e32f33bdbd115c85d116583ce679cb6`;
  official V30 `ced6857afa0ea7b2e3f0846a62e1394e90f15607`.
- Official xpu-kernels 0.1.14.1 `6d92b1bfbf32767ecda8e819613eb151e70030ad`.
- `b70-flash-next/patches/vllm/`, `image/verify-overlay.sh` and `PROVENANCE.md`
  describe Python file identities and scoped wu1ff/Lumnus authorship.

Stock V30 explicitly rejects XPU in `vllm/models/qwen4_exp/__init__.py`.
Lumnus patch 0001 enables the NVIDIA-derived implementation. The certified lab
line used AMD-derived model code; changed model lineage, graph/compiler,
collectives and MoE arithmetic all confound a pin mismatch. A fused GDN miss is
expected, but Screen 1 cannot isolate its cost from all these other changes.

**Unchanged checkpoint handling:** mount the original 131-shard tree read-only;
never run Lumnus `prepare-serve.sh` or use its supplied serve config. Those expect
an external PLE table and a dense-QSA configuration. Preserve the actual FP8
checkpoint's indexer keys and quantization exclusions, and do not enable
`B70_PLE_FP8`, `B70_PLE_INT8`, `B70_PLE_INT8_NVME`, external `PLE_TABLE_PATH`,
CPU KV offload, sampler defaults or the private residency shim.

### Screen 1b port and memory gates

Screen 1 failed during loading. Its 16.25 GiB/rank generic offloader could
make both a pageable and pinned copy of the 12.800 GB native FP8 PLE shard.
The new Python overlay allocates final pinned PLE storage directly and exposes
an XPU UVA view. It counts that allocation in the same selective offload budget;
it never adds a second PLE table. Only explicitly checkpoint-backed PLE may
discard its initial unfilled bytes. Ordinary selected expert tensors preserve
their contents through bounded copies. Token embeddings remain on device.

The lab contracts come from the certified lossless-MTP1 series: direct
allocation (0010), root-level complete shard coverage (0027/0030/0031),
pre-materialization filtering (0033), device ownership (0007), and bounded
transport/drainage (0003/0032). The selected route is direct UVA; no separate
PLE worker, external table, compression or process transport is enabled. The
port refuses other routes instead of pretending to support them. PLE scales,
padding, shard ranges and original checkpoint values remain part of loading.

All new code is in Python whole-file replacements; `apply_overlay.py` verifies
the official V30 base or the exact already-applied output before replacing
files. `overlay-manifest.json` pins both sides. The original source tree is
unchanged. No native wheel, GDN operator, FP8 checkpoint or sampler is replaced
by this port. Existing pinned Lumnus files are included for a self-contained
Python overlay; upstream/native provenance remains separate.

One cross-rank allocation lock covers only collective-free pin allocations
and bounded copies, never the whole model constructor. The lazy safetensors
path filters unowned PLE shard names before materialization. Copies account for
source plus destination within a 256 MiB live-copy ceiling and drain before
source release. Root-load validation refuses missing, duplicate, malformed
or unexpected PLE shards. Unsupported oversized conversion temporaries refuse
rather than falling back to unbounded staging. Construction/postprocessing
allocations outside that copy mechanism remain an explicit qualification risk.

The loading guard observes `/screen/STOP` before new work. Worker startup and
engine/worker cleanup are patched for early cancellation and draining, including
the engine manager's separate escalation path. The controller's 250 ms watchdog
trips at whole-host pressure ≥80,000,000,000 bytes or MemAvailable ≤32 GiB.
Next-allocation admission uses the same limits. One controller SIGINT is shared
between watchdog and normal cleanup; no Docker stop-to-kill timeout is used.
A stalled drain is recorded for the owner and is never escalated to a hard kill.

#### MTP1 / maximum length 4,352 prediction

GB means decimal bytes; GiB means 2^30 bytes. Values are source/header-derived
sizes or explicitly labeled assumptions, **not measurements**.

| Whole-host component | Bytes | GB | Basis |
| --- | ---: | ---: | --- |
| Final pinned PLE + selected whole expert tensors | 70,494,044,160 | 70.494044 | Actual parameter order and budget overshoot; PLE counted once |
| Runtime/private/retained allocation allowance | 12,884,901,888 | 12.884902 | Fit-note assumption, unqualified on V30 |
| Active unique file/staging allowance | 4,294,967,296 | 4.294967 | Fit-note assumption, not all checkpoint page cache |
| Other host + driver allowance | 4,294,967,296 | 4.294967 | Fit-note assumption, not summed RSS |
| Maximum extra in-flight bounded copy | 268,435,456 | 0.268435 | One admitted rank; 256 MiB source plus destination |
| **Planning peak** | **92,237,316,096** | **92.237316** | **Exceeds 90 GB** |

`memory_plan.py` reads config/index and bounded safetensors headers, checks source
identity, enumerates PLE/w13/w2 registration order, and evaluates exactly:

```text
Hphase = B_other_host + sum_r(P_final_live + A_private_excluding_P
         + T_copies_live + A_retained) + F_active_unique + K_driver + safety
Hpred = max(Hphase)
Vpeak[r] = max(Vphase[r])
require Hpred <= 90_000_000_000
require physical_VRAM[r] - Vpeak[r] >= 4 * 2**30
require post-hash MemAvailable >= remaining_growth + shutdown_margin
```

The phase manifest explicitly lists construction, pinning, checkpoint copy,
postprocessing, MTP, KV, capture and serving. Unknown bounds are `null` and
refuse. Observed RSS/cgroup/meminfo values describe memory ownership; they are
not added on top of pinned storage. Complete bounds require source/config/launch
identity and qualified lifetime evidence, plus pre/post-hash observations.
`host-memory-prediction.json` is the static refusal receipt for the candidate.

Final v5 row placement is **not ported into Screen 1b**. It cannot remedy the
allocation-total conflict under these allowances. The static conditional proof
allows arbitrary placement and optimistically shards all checkpoint storage
except source-proven replicated HC matrices. Given the host pin ceiling, it
still needs at least 28.560915 GiB/card including the explicit full-precision KV,
even before GDN/capture/workspaces. A nominal 32 GiB card then has less than
four GiB spare. The actual physical capacity is smaller; exact per-card receipts
and complete V30 upper bounds remain required. This does not establish that
all lossless approaches are impossible: the allowances need evidence, and
further runtime-memory work can change the total.

The historical placement series' global compaction failed; it must not be
reintroduced. If later evidenced bounds show fine row placement is needed,
port final **load-time v5** resident/host allocation and row-view loading with
unchanged Triton addressing/scales, not the old whole-rank staging attempts.

#### Exactness limits and future command

Fused GDN remains active. The 2K/4K pins compare exact fixture token streams
against the certified older lane. A mismatch is real fixture divergence but
cannot isolate GDN from changed model lineage, MoE arithmetic or compilation.
A match is fixture evidence, not general output parity or a substitute for
quality gates and fresh-server repeats. MTP3 requires independent qualification.
No speed claim follows from this CPU port.

From `experiments/qwen38-flash-next-fp8-b70/reopen-20261008`:

```sh
python3 screen.py run --mode mtp1 --execute
```

The supplied configuration **refuses before launch**. It is the exact future
controller command, not permission to use cards currently owned by LTX. Use
`--dry-run` to print the complete prediction and launch flags on CPU.

### What missing b70.3 native changes lose

`b70-flash-next/docs/kernels.md` and
`patches/vllm-xpu-kernels/b70.3/` list seven changes:

| Native change absent from the official wheel | Consequence for this screen |
| --- | --- |
| `fa542f6`, int64 conv-state offsets | Large block indices can overflow signed 32-bit addressing; bound the actual cache geometry below that threshold. Lumnus's example fails at block 5,042 with stride 425,984. |
| `ba19ef4`, upstream #600, ragged speculation | Structured-output trimmed drafts may fail; no grammar/JSON-schema request is part of this fixed screen. This does not prove every ragged path unreachable. |
| `dd87485`, upstream #564, pinned UVA strides | Non-contiguous host views can have wrong strides; require contiguous offloaded tensors and inspect the actual route. |
| `d00fbf7`, upstream #563, unaligned-vocab top-k/top-p | Sampling correctness fix; greedy pin/suite requests avoid stochastic sampling, but retain the limitation. |
| `5fcc722`, upstream #578, negative expert IDs | EP padding guard missing in native XPU remap; the selected Triton/allgather-reducescatter path uses `moe_align_block_size`, not the affected `remap_hidden_states` route. Assert the served backend. |
| `e68951b`, upstream #586, grouped-GEMM counter initialization | Native Xe2 grouped-GEMM race fix absent; explicit Triton MoE avoids that expert implementation, subject to route verification. |
| `493364a`, B70-K1 direct pinned H2D KV copies | Faster transfers and bounded cached host staging for CPU KV offload; inactive here because CPU KV offload is disabled. |

The selected Triton route is source-distinct from `XpuFusedMoe`: its
`experts/triton_moe.py` calls `fused_moe._prepare_expert_assignment` and
`moe_align_block_size`; the affected `remap_hidden_states` callers are in
`vllm_xpu_kernels/fused_moe_interface.py` and `moe_utils.py`. Use explicit
`--all2all-backend allgather_reducescatter` and verify the actual backend at
startup. Keep missing native fixes visible as blockers if a different unsafe
route is selected. Python-only does not mean numerically qualified. No private `libgdn_index64.so` is supplied; patch 0027 falls back to the
official op and 0032 only rate-limits its warning. It does not repair that op.

## Other runtime paths and build estimates

**(b) Lumnus make-tree/build:** `scripts/make-tree.sh 0.30.0-b70.2 DIR`
fetches/clones or applies Python patches and verifies hashes. It compiles
nothing and is not a Docker build. Its `image/Dockerfile` derives the official
image, patches installed and source Python copies, copies two binary-only DSOs
from a pinned wu1ff image, and runs CPU verification. That Dockerfile does not
build/install the current b70.3 kernel wheel. A complete source kernel rebuild is
a separate operation: `_C`, `_xpu_C` including GDN, `_moe_C`, FlashAttention,
architecture kernels and allocator, with oneDNN/SYCL-TLA dependencies.
`docs/kernels.md` reports 2 h 40 min at 12 jobs and peak ~100 GB RAM; the <3 min
number is only an incremental b70.2-to-b70.3 `_C` rebuild. Its released wheel is
351,983,263 bytes, built against torch2.13/oneAPI2026.0. Full native work needs
hours and a separately admitted large build workspace, not this screen's
~1-hour pull/start/request budget. The lab's historical conservative full-stage
admission was 150 GiB free NVMe and 100 GiB available RAM; preserve the separate
50 GiB reserve when planning new allocations. Exact serial GDN reimplementation
is additional engineering and qualification, potentially days.

**(c) Existing historical image plus ports:** no pull is cheapest in disk, but an
old torch/vLLM image cannot receive V30 Python files wholesale. The available
local labels/history identify R276-era artifacts, not a confirmed R304 or V30
runtime; their approximately 23 GB disk footprint is no evidence of kernel
version. Selected orchestration ports would measure the old stack, not answer
the modern-stack Screen 1 question. Preserve those images as historical anchors.
Do not install packages into old environments or mix torch2.11 kernel DSOs with
new torch2.13 binaries.

## Confirmed launch vocabulary in V30

`config/compilation.py` defines `CUDAGraphMode.FULL_DECODE_ONLY` with that exact
spelling and accepts `cudagraph_capture_sizes`; no renamed setting is needed.
`platforms/xpu.py` requires `VLLM_XPU_ENABLE_XPU_GRAPH=1` and compatible torch.
Use TP4, `--enable-expert-parallel`, BF16 activations/KV, `--max-model-len 4352`,
one sequence, `--max-num-batched-tokens 64`, no async scheduling or prefix cache,
`--enable-prompt-tokens-details`, and a declared bounded KV allocation.
Capture sizes `[1]`, `[1,2]`, `[1,4]` correspond to separate no-MTP, MTP1 and
MTP3 arms; inspect what actually captures, since padded shapes are not evidence
of active-row geometry. Stock configuration is per-engine:

```text
MTP off: omit --speculative-config
MTP1: --speculative-config '{"method":"mtp","num_speculative_tokens":1}'
MTP3: --speculative-config '{"method":"mtp","num_speculative_tokens":3}'
```

There is no reviewed per-request switch. The morning note's maximum32 requests
(4 pins +12 realistic for each of K1/K3) requires unimplemented drained scheduler,
proposer, rollback and graph controls. A one-launch K1 screen is16 requests.
Separate arm command lines do not authorize a three-launch sweep. Do not edit an
environment variable mid-process or discard extra drafts and label it K1.

## Community queue beyond Lumnus; offline evidence only

The requested command was run against the local clone:

```sh
git -C /home/steve/src/lumnus-20261008/vllm log --oneline \
  76cfe1cd88d30d525eec8be5bff75f8b77471c88..v0.30.0 -- \
  vllm/models/qwen4_exp vllm/model_executor/models/qwen3_8.py \
  vllm/model_executor/layers/mamba/gdn \
  vllm/model_executor/layers/fused_moe/experts/xpu_moe.py \
  vllm/model_executor/layers/quantization/fp8.py \
  vllm/v1/attention/backends/gdn_attn.py
```

It returns only the unrelated V30 tip `ced6857`, CPU build PR#57871. The clone's
`.git/shallow` contains the old base, V30 and Lumnus HEAD: this is **not a
complete post-76cfe1cd PR history**. Do not invent PR numbers from endpoint diffs.
No fetch was performed. Useful pinned endpoint findings from
`../notes/2026-10-08-lumnus-v0300-stack-analysis.md` and local
`/home/steve/src/lumnus-20261008/upstream-review.md`:

- New Qwen4Exp package and PLE TP shard coverage; XPU needs the reviewed selector.
- GDN CPU metadata construction avoids a device-to-host draft-count copy;
  graph/capture orchestration changed. Inspect the saved
  `audit-evidence/vllm-selected-endpoint.diff`.
- FP8 loader scale-grid refinement handles incompatible TP/block partitioning;
  the XPU MoE implementation itself is byte-identical between the two endpoints.
  Native block-FP8 is pre-existing, not a new claimed speedup.
- Kernel history is available: #544 `5802a414` conv rollback layout, #537
  `1d5b4f5e` mixed speculative groups, #517 `95d80c7a` SYCL-TLA update.
  These are source/common-base deltas, not necessarily chronologically after
  certification. Relevant later upstream fixes adopted by Lumnus are
  #600/#564/#563/#578/#586 above; preserve upstream authorship.
- nacolias llama.cpp SYCL quad-B70 is a useful lead for TP/communication/kernel
  scheduling ideas. The supplied context has no locally pinned source or tested
  result. The earlier note's attempted URL read failed. Queue source/revision,
  exact GGUF quantization, topology, cache and quality evidence for a later
  authorized intake; do not transfer a GGUF speed to the unchanged FP8 lane.

No network beyond the parent's Docker manifest metadata inspection was used.
