# The EP4 partition is compiled into the grouped-GEMM kernel

Date: 2026-08-04 America/Toronto

Status: **definitive. Seven gates traced; the last is a compile-time constant,
which ends the configuration route and gives an exact engineering scope.**

## The bottom of the stack

`csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2_interface.hpp:1725`

```cpp
constexpr int64_t hidden_size       = 3072;
constexpr int64_t intermediate_size = 1024;   // EP4 shard
constexpr int64_t topk              = 10;
TORCH_CHECK(
    num_local_experts == 64, "Laguna fused expert requires 64 local experts");
```

The fused expert kernel is **specialised at compile time to the expert-parallel
partition**. Tensor-parallel sharding of the same model gives 256 local experts
of intermediate size 256 -- identical total work (`64 x 1024 == 256 x 256 ==
65,536`) but a different tiling, and both figures are `constexpr`.

The string is present in `libgrouped_gemm_xe_2.so`, not in any Python file. No
environment variable can reach it.

## The full gate list

Seven independent gates enforce the EP4 partition. Six are Python or shell and
were relaxed behind default-off flags during this session; the seventh is the
binary above.

| # | gate | where | relaxable |
| ---: | :--- | :--- | :--- |
| 1 | q12 profile requires the M12 selector | `serve_laguna_long_context_nvme.sh` | yes |
| 2 | shared-elementwise "parallel identity is not TP4/PP1/DP1/EP4" | `laguna.py` | yes |
| 3 | breakable-graph `expert_parallel` term (two sites) | `gpu_model_runner.py` | yes |
| 4 | batched-exact MoE: `local_experts=64, ep_size=4, intermediate_size=1024` | `fused_moe_interface.py` | yes |
| 5 | BF16 router top-k requires gate 4 | `fused_moe_interface.py` | yes |
| 6 | transposed decode scales require `w13_scales(64, ...)` | `fused_moe_interface.py` | yes |
| 7 | **`num_local_experts == 64`, `intermediate_size` constexpr** | **`libgrouped_gemm_xe_2.so`** | **no -- needs a rebuild** |

## What this settles

The expert-parallel cost cannot be measured by configuration, at all. Every
previous attempt in this campaign stopped at gate 2 or 3 and recorded that the
engine would not initialise; the real depth is seven, and the floor is a
compiled constant.

It also gives the first precise scope for the work the trace argues for:

- **Edit**: `grouped_gemm_xe2_interface.hpp` -- make `intermediate_size` and the
  local-expert count template parameters rather than `constexpr`/assert, then
  instantiate the TP shape alongside the EP one.
- **Rebuild**: `libgrouped_gemm_xe_2.so` (the tree has `CMakeLists.txt`,
  `setup.py` and a `build_script`).
- **Then relax** gates 1-6, which are already flagged.
- **Verify** with the suite's `retrieval_pass` gate plus an output-SHA
  comparison; wrong output fails loudly.

Prize, from the warm trace: replacing ~70.8 MB of per-step all2all with ~3.54 MB
of all-reduce, against a step whose non-collective kernel time is ~2.2 ms of
~26.4 ms.

## Cost of the specialisation, measured

Warm 32,640-token decode with the M12 shared-elementwise selector **off** and
expert parallelism still on: **39.403** against **39.848** for the full stack --
**~1%**.

The kernel specialisation that forces the EP4 partition across seven components
is worth about one percent. The expert parallelism it forces costs ~94% of the
step. That is the argument for doing the rebuild, in one line.

## Repository changes made, for review

Three trees were modified, all default-off:

| tree | commit | change |
| :--- | :--- | :--- |
| `llm-optimizations` | several | `LAGUNA_EP_COST_DIAGNOSTIC` and selector overrides in the launcher/runner |
| `laguna-vllm-shared-elementwise-m12-20260731` | `7e985da07` | `VLLM_XPU_LAGUNA_ALLOW_NO_EP` on both `expert_parallel` contract sites |
| `laguna-xpu-kernels-shared-elementwise-m12-20260731` | `8f9eca6` | same flag drops the three partition terms in the batched-exact MoE contract |

With `VLLM_XPU_LAGUNA_ALLOW_NO_EP` unset and `LAGUNA_EP_COST_DIAGNOSTIC=0`,
behaviour is identical to before. Revert with `git revert` in each tree if the
campaign prefers them pinned.

## Boundaries

No quantisation change, no caching or speculation setting used to inflate any
number. No arm with expert parallelism disabled ever started, so no such
throughput figure is claimed. The 39.403/39.848 pair is a real warm measurement.
The protected `125.4619731637751 tok/s` conventional short-decode record is
untouched.
