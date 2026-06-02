# 2026-06-02 U4 Signed-Compact Specialization Rejection

Goal: test whether compiling the MiniMax WS INT4 decode kernels for a constant
signed-compact mode can remove a branch from the hot U4 path and recover some of
the gap to the archived `89.499223` output tok/s REAP run.

## Source Experiment

Patch excerpt archived:

- `patches/llm-scaler-ws-signedcompact-specialization-rejected-20260602.patch`

The experiment specialized these WS kernels on `signed_compact`:

- `moe_ws_up_routed_cutlass_int4_kernel`
- `moe_ws_down_cutlass_int4_kernel`

The rejected variant changed the runtime `if (signed_compact)` decode branch into
`if constexpr (SignedCompact)` and dispatched separate true/false template
instantiations.

Build command:

```bash
set +u
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh >/dev/null 2>&1
set -u
source /home/steve/.venvs/vllm-xpu/bin/activate
export CC=icx
export CXX=icpx
export SYCL_CACHE_PERSISTENT=1
export TORCH_XPU_ARCH_LIST=bmg
python setup_moe_int4_only.py build_ext --inplace
```

Build result:

- succeeded
- installed `.so` size grew from `97M` to `115M`
- import check passed for
  `ops.moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws`

## Quality And Speed

Quality passed:

- file:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-u4specialized-logitsws-qk0-20260602T131747Z.json`
- generated tokens: `1152`
- distinct generated token IDs: `391`
- NUL/control output: none
- token SHA:
  `ff0577619b37527545ce980a0d160e1a2917fae5554089fec9b3a4efcd0130cf`

Decode regressed:

- log:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-u4specialized/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T132219Z.log`
- JSON:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-u4specialized/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T132219Z.json`
- elapsed: `19.198351889004698 s`
- total throughput: `106.67582362488797 tok/s`
- output throughput: `80.00686771866597 tok/s`

Decision: reject. It is quality-clean but materially slower than the current
quality-clean live-source baseline.

## Restore

The specialization was removed from active llm-scaler source and the one-op
extension was rebuilt.

Restore build result:

- succeeded
- installed `.so` size returned to `97M`
- import check passed for
  `ops.moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws`
- no `SignedCompact` or specialization dispatch symbols remain in
  `csrc/moe_batch/moe_int4.sycl`

Fresh async quality after restore:

- cache:
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-restored-u4runtime-20260602T1330`
- file:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/async-quality-smoke-restored-u4runtime-logitsws-qk0-20260602T1330.json`
- passed: `true`
- generated tokens: `384`
- distinct generated token IDs: `179`
- printable non-space chars: `1690`
- NUL/control output: none
- token SHA:
  `d1f5fc8afdb623226193fe96fd2d279f850f43ae6cf3e38ebabe510e2837e2d5`

Restored decode benchmark on the same cache:

- log:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-restored-u4runtime/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T133537Z.log`
- JSON:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode-restored-u4runtime/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T133537Z.json`
- elapsed: `18.23593598199659 s`
- total throughput: `112.30572436873467 tok/s`
- output throughput: `84.229293276551 tok/s`

## Interpretation

The branch removed by the specialization is not the decode bottleneck. The larger
binary and duplicated instantiations likely hurt instruction/cache behavior or
compiler scheduling enough to overwhelm any branch-removal benefit.

The active build is restored to the runtime `signed_compact` branch path. The
current quality-clean live-source best from this pass remains the earlier
`85.21` output tok/s run:

- `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260602T125056Z.log`

No LocalMaxxing submission is warranted.

## Next Work

- Focus on kernel-level MoE up/down runtime, not branch specialization.
- Use timing that splits WS up, WS down, top-k, and launch cost without adding
  synchronization to the benchmark path.
- Inspect generated code or IGC reports for H_TILE=4 versus H_TILE=8 register
  pressure and occupancy.
- Continue treating the archived `89.499223` run as historical until the same
  async quality path can reproduce it.
