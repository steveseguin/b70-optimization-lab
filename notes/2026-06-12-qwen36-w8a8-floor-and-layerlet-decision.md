# Qwen3.6 W8A8 Kernel Floor And Layerlet Decision

Date: 2026-06-12

## Scope

This packet tested the lower bound of the current XPU W8A8 building blocks for
`nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` on 4x Intel Arc Pro B70. The
accepted backend was stopped for the isolated XPU microbench and must be
restored before any user-facing run.

The question was not whether a new endpoint candidate is ready. The question
was whether ordinary helper-op and grouped-GEMM variants still have enough
headroom to reach the non-speculative `>200 tok/s` target.

## Counter Boundary

`xpu-smi dump` can list the desired GPU utilization, EU, memory, and bandwidth
metrics, but useful values require elevated MEI access on this host. `sudo -n`
is not available, and `unitrace`/VTune were not present in the current path.
For this packet, the reliable evidence is timing-derived kernel floor data.

## Commands

```bash
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels:${PYTHONPATH:-} \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:${LD_LIBRARY_PATH:-} \
/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-w8a8-kernel-floor.py \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.9\.' \
  --route-start-indices '0:64:4' \
  --route-window-size 1 \
  --include-compact-grouped \
  --include-quant \
  --iterations 80 \
  --warmup 20 \
  --output-json data/qwen36-quark-int8-w8a8-kernel-floor-layer9-routecapture6-w1-20260612an.json
```

```bash
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels:${PYTHONPATH:-} \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:${LD_LIBRARY_PATH:-} \
/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-w8a8-kernel-floor.py \
  --route-jsonl data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --route-layer-regex 'layers\.9\.' \
  --route-start-indices '0:64:4' \
  --route-window-size 16 \
  --include-compact-grouped \
  --include-quant \
  --iterations 80 \
  --warmup 20 \
  --output-json data/qwen36-quark-int8-w8a8-kernel-floor-layer9-routecapture6-w16-20260612an.json
```

## Results

Layer 9 routecapture6, W8A8 GEMM floor, means across route windows:

| Window | Stage | Exact grouped 256 | Compact active | Dense single | Active dense loop |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | gemm1 | `113.845 us` | `107.961 us` | `128.966 us` | `330.993 us` |
| 1 | gemm2 | `112.371 us` | `107.067 us` | `130.730 us` | `329.560 us` |
| 16 | gemm1 | `112.596 us` | `110.415 us` | `131.434 us` | `1529.484 us` |
| 16 | gemm2 | `114.068 us` | `113.034 us` | `127.710 us` | `1589.752 us` |

Quant helper floor:

| Window | Helper | Mean |
| --- | --- | ---: |
| 1 | quant hidden rows=8 | `100.618 us` |
| 1 | quant hidden rows=24 | `91.468 us` |
| 1 | quant intermediate rows=8 | `91.109 us` |
| 1 | quant intermediate rows=24 | `90.712 us` |
| 1 | SiLU+quant rows=8 | `89.575 us` |
| 1 | SiLU+quant rows=24 | `88.338 us` |
| 16 | quant hidden rows=8 | `114.990 us` |
| 16 | quant hidden rows=24 | `108.360 us` |
| 16 | quant intermediate rows=8 | `93.202 us` |
| 16 | quant intermediate rows=24 | `97.898 us` |
| 16 | SiLU+quant rows=8 | `90.016 us` |
| 16 | SiLU+quant rows=24 | `89.029 us` |

## Interpretation

- Exact grouped GEMM is nearly flat from route-window 1 to route-window 16:
  about `112-114 us` for each GEMM. That is launch/control/tiny-shape floor,
  not arithmetic scaling.
- For c1 decode, two exact grouped GEMM dispatches already cost about
  `226 us/layer` before route packing, quantization, activation, weighting,
  gather, scheduler metadata, attention, and collectives.
- The non-speculative `>200 tok/s` budget is about `168 us/layer`, so a
  two-dispatch MoE core cannot hit the target by itself.
- Compact-active grouped GEMM is only `~1-6 us` faster in this fixture and is
  not model-equivalent unless weights/layouts are changed to preserve exact
  expert semantics.
- The dense per-active-expert loop is a useful negative control: it explodes
  with many launches and reinforces the need for grouped or persistent work.

## External Signals

- Intel's Triton-XPU grouped-GEMM issue says MoE decode performance is strongly
  affected by real routing skew and tile configuration, matching our
  routecapture-driven fixture:
  https://github.com/intel/intel-xpu-backend-for-triton/issues/6389
- A newer Intel Triton-XPU grouped-GEMM issue shows oneDNN beating Triton in
  grouped GEMM controls on Intel GPUs, so a oneDNN grouped-matmul control path
  is worth measuring:
  https://github.com/intel/intel-xpu-backend-for-triton/issues/6861
- `vllm-xpu-kernels` release notes are actively tuning Xe2/Battlemage decode
  and MoE grouped-GEMM policy, so stack A/Bs remain useful but should be gated
  by exact route replay:
  https://github.com/vllm-project/vllm-xpu-kernels/releases
- oneDNN grouped matmul supports per-source and per-weight scales plus SiLU and
  binary multiply post-ops on CPU and GPU engines. That makes a fused grouped
  control path plausible without changing model quality:
  https://uxlfoundation.github.io/oneDNN/dev_guide_matmul.html

## Decision

Stop treating ordinary helper-op variants as likely to reach the full c1
target. Keep quant-out and scratch work as plumbing, but shift the main
non-speculative branch to one of these:

1. A persistent or one-dispatch MoE layerlet for layer-9 routecapture6 with
   exact parity against `xpu_fused_moe`.
2. A oneDNN grouped-matmul replay control that can fuse scale/post-op work and
   prove whether the SYCL-TLA grouped path is the floor.
3. Target-verified speculation with transactional rollback if the exact
   non-speculative layerlet cannot beat `168 us/layer`.

This packet is not an endpoint promotion and not a public benchmark candidate.
