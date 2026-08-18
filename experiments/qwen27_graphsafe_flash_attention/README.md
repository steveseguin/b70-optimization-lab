# Qwen27 graph-safe Intel FlashAttention

Status on 2026-07-11: the focused chunk-prefill implementation is graph-safe,
the short-context chunk-decode fallback is graph-safe and quality-clean, and
the exact Qwen27 TP2 record topology now captures one full four-row target
graph instead of failing on SYCL scratch memory. Crossover testing showed a
reproducible improvement over PIECEWISE controls, and the cooled solo
confirmation set a strict quality-gated record of `93.036242 tok/s`.

## Scope

`qwen27-chunk-prefill-local-accessor.patch` replaces the
graph-incompatible `work_group_scratch_size` launch property in XE2 chunk
prefill with handler-owned, typed
`sycl::local_accessor<FMHAKernel::SharedStorage, 1>` storage. It preserves
subgroup 16, 256 GRFs, and the existing kernel math.

`qwen27-force-chunk-decode.patch` adds a default-off
`VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1` dispatch option. It routes one-token paged
decode through the graph-safe chunk kernel, avoiding a rebuild of the
monolithic paged-decode translation unit, which exceeded 110 GiB RAM in prior
compile attempts. This fallback is intended only for short-context research:
it is close to paged-decode latency at 128 KV tokens but scales substantially
worse by 2K tokens.

Source identity:

- XPU kernels commit `3b4effeeffd83f6ef4696bbe7e76d924a0e9d171`;
- deployed object compiler IntelLLVM 2025.3;
- model `webhie/Qwen3.6-27B-int4-AutoRound` revision
  `f5750c90b3776db658594df5fe8051098226dd8e`;
- record identity: TP2, FP16 target compute, MTP3, runtime INT8 target LM-head,
  runtime INT4 draft LM-head, public oneCCL `4ceafd1`, captured GDN core.

The external XPU-kernel source was patched only inside guarded focused builds
and restored afterward. Generated `work/` and `staged-package/` binaries are
ignored; the source patches, tests, and conclusions are tracked here.

## Validation

The packed MTP3 chunk-prefill oracle passed 1,000 command-graph replays at
each KV length 128/1024/2048 (3,000 total). It uses FP16, rows=4, TP2-local
12 query heads and 2 KV heads, head dimension 256, paged causal KV, shuffled
block tables, poisoned output before every replay, and live Q/sequence-length
mutations. Maximum absolute deviation from the FP32 reference was
`0.00048828125`.

The forced one-token chunk-decode oracle passed another 3,000 graph replays
with the same mutation/poison checks and exact FP16 tolerance. Direct kernel
latency versus stock paged decode was:

| KV tokens | stock paged decode | forced chunk decode |
|---:|---:|---:|
| 128 | 18.133 us | 20.589 us |
| 1024 | 29.180 us | 109.625 us |
| 2048 | 22.618 us | 214.984 us |

Raw results live outside Git under
`/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/`:

- `qwen27-graphsafe-flash-chunk-prefill-replay-20260711.json`;
- `qwen27-fa-paged-decode-baseline-20260711.json`;
- `qwen27-fa-forced-chunk-decode-replay-20260711.json`.

The endpoint then compiled, captured, and served with
`FULL_AND_PIECEWISE`, one full four-row decode graph, and FlashAttention. The
former `sycl_ext_oneapi_work_group_scratch_memory` capture failure did not
recur. Smoke returned the exact expected JSON with `cached_tokens=0`.

Quality passed completely: exact arithmetic/copy/JSON cases, repeat128,
baseline output parity, and the 1K needle. Artifact:

`data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-fp16-graphsafe-fa-full-quality128-repeat128-ctx1024-20260711T203355Z.json`.

Strict fresh speed, each prompt once and all `cached_tokens=0`:

| Window | Full-graph candidate | PIECEWISE control | Relative |
|---|---:|---:|---:|
| candidate GPUs 0,1 / control 2,3 | 90.433 | 87.439 | +3.42% |
| candidate GPUs 2,3 / control 0,1 | 91.606 | 89.413 | +2.45% |

Candidate mean across the two crossover rows is `91.019 tok/s`; control mean
is `88.426 tok/s`, a `+2.93%` relative improvement. A subsequent cooled solo
run on GPUs 2,3 reached median **`93.036242 tok/s`**, mean `92.773145`, p10
`82.845516`, full-output after-TTFT median `91.219731`, wall median
`79.837069`, and TTFT median `742.232 ms`. This exceeds the prior
`91.714405 tok/s` headline by `1.44%`; the crossover is the supporting evidence
that this small headline delta is not merely run variance.

## Commands

Static checks:

```bash
cd /home/steve/llm-optimizations/experiments/qwen27_graphsafe_flash_attention
./validate.sh /home/steve/src/vllm-xpu-kernels
```

Focused source-snapshot build:

```bash
cd /home/steve/llm-optimizations/experiments/qwen27_graphsafe_flash_attention
MAX_JOBS=8 ./build.sh
```

Run the packed-prefill replay against a staged package:

```bash
cd /home/steve/llm-optimizations
STAGE=$PWD/experiments/qwen27_graphsafe_flash_attention/staged-package
PYTHONPATH=$STAGE \
LD_LIBRARY_PATH=$STAGE/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib \
ONEAPI_DEVICE_SELECTOR=level_zero:0 ZE_AFFINITY_MASK=0 \
  /home/steve/.venvs/vllm-xpu/bin/python \
  experiments/qwen27_graphsafe_flash_attention/test_graph_replay.py \
  --device 0 --replays 1000
```

Endpoint experiment (requires the staged hybrid library and extension):

```bash
cd /home/steve/llm-optimizations
STAGE=$PWD/experiments/qwen27_graphsafe_flash_attention/staged-package
PYTHONPATH=$STAGE VLLM_XPU_KERNELS_SRC=$STAGE \
VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1 VLLM_XPU_DDTREE_FULL_GRAPH=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[4],"max_cudagraph_capture_size":4}' \
VLLM_CACHE_ROOT=/mnt/fast-ai/vllm-cache-exp/qwen27-graphsafe-fa-full \
GPU_INDEX=0,1 ZE_AFFINITY_MASK=0,1 ONEAPI_DEVICE_SELECTOR=level_zero:0,1 \
PORT=19512 QUALITY_REPEAT_RUNS=128 \
  experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-draftgraph-capturegdn-fp16-candidate.sh
```

Authoritative packet:
`results/qwen36-27b-autoround-int4-b70/tp2-fp16-graphsafe-flash-fullgraph-20260711.json`.
LocalMaxxing approved the record as `cmrgue7kl007pmj01yrkcyqmv`.

## Qwen3.8 two-B70 rebuild (2026-08-18)

The two-card, 15 GiB host reproduced this runtime from XPU-kernels commit
`2dd55f380df753a10a88fcd9e96192561066e713` with IntelLLVM 2025.3.3 and
`MAX_JOBS=1`. The current source already contains the completion barrier, so
the local-accessor patch was rebased onto that source without changing its
kernel math.

The build now defaults to the checked-in Qwen3.8-specific AOT configs. They
cover head dimension 256, GQA ratio 6, block size 64, initial prefill, packed
MTP verification, forced one-token chunk decode, and the paged reference.
This produced 8 chunk and 2 paged variants instead of the full preset's 632.
Override `VLLM_CHUNK_PREFILL_CONFIG` and `VLLM_PAGED_DECODE_CONFIG` when
building a general-purpose package.

Current upstream also has a Python speculative-decode fast dispatch in front
of the C++ force-chunk switch. Without bypassing it, packed rows enter the
graph-incompatible paged kernel even when
`VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1`. The default-off
`qwen27-force-chunk-decode-python.patch` makes the Python and C++ switches
consistent; the first oracle intentionally caught this before model launch.

Both B70s then passed 6,000 packed-MTP3 and 6,000 forced-one-token graph
replays, with live input/length mutations, poisoned outputs, and FP32-reference
comparison. Worst absolute deviation was `0.00048828125`; both devices
remained normal and the kernel log contained no reset, fault, hang, OOM, or
panic. The machine-readable summary is
`repro/qwen38-27b-autoround-int4-b70/evidence/graph-stage-oracles-20260818.json`.
