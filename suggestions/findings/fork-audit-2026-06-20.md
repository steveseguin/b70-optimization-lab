# vLLM-XPU Kernels Fork Audit

Date: 2026-06-20

Scope: public forks of `vllm-project/vllm-xpu-kernels`, not the much larger
`vllm-project/vllm` fork network.

## Method

- Queried GitHub API endpoint:
  `https://api.github.com/repos/vllm-project/vllm-xpu-kernels/forks?per_page=100&sort=newest`
- GitHub reported 76 public forks.
- Cloned upstream into a temporary bare repo and fetched each fork's default
  branch.
- Compared each fork default branch against upstream `main` at
  `11f42aa47ff51924b3d9527cfc2bfef5fd2d98e5`.
- Classification:
  - `identical_head`: fork default branch equals upstream `main`.
  - `behind_or_equal_history`: fork has no commits ahead of upstream `main`.
  - `ahead`: fork has commits not present in upstream `main`.

## Result Summary

- Total public forks checked: 76
- Identical to upstream head: 6
- Behind or equal history, no unique default-branch commits: 60
- Ahead of upstream default branch: 10

The earlier source notes were incomplete: they called out Jason Boukheir's
fork as the meaningful exception found in the first pass. The exhaustive pass
shows more ahead forks. Jason's fork remains the highest-signal GDN/DFlash
lead, but it is not the only fork worth mining.

## Ahead Forks

### `jasonboukheir/vllm-xpu-kernels`

- Ahead/behind: 1 ahead, 5 behind.
- Commit:
  - `63c50713578d55a349610797788c7f3da133b2ff`
  - Subject: `[GDN] narrow cudagraph-padded metadata index tensors to active size`
  - URL: https://github.com/jasonboukheir/vllm-xpu-kernels/commit/63c50713578d55a349610797788c7f3da133b2ff
- Touched file:
  - `csrc/xpu/gdn_attn/gdn_attn_interface.cpp`
- Value:
  - High. Directly overlaps graph-padded GDN/DFlash/spec metadata. It narrows
    padded metadata tensors to active prefixes before shape checks and kernel
    launches.
- Caveat:
  - Local GDN files are dirty and upstream has related issue/PR work, so inspect
    intent and adapt rather than applying blindly.

### `nc-BobLee/vllm-xpu-kernels`

- Ahead/behind: 4 ahead, 66 behind.
- Commits:
  - `a0c9f18ac354729bc42897330505509003a398f1` - draft head RMSNorm kernel.
  - `71500b35bc77d2b8bb1b6a09fe142a4b1b802090` - port IPEX layer norm to vLLM kernel.
  - `bd6e5bf8a7b96209c569d7e2ec0fe083158c9d85` - optimize fused add RMSNorm kernel.
  - `d9c95d7f025622cb6379adfe26e7635ebe7ac47e` - add hidden-size assert.
- Touched files:
  - `csrc/layernorm.cpp`
  - `csrc/head_rms_norm.cpp`
- Value:
  - Medium. LayerNorm/RMSNorm is not the leading Qwen35 B70 bottleneck, but an
    IPEX-derived RMSNorm path may be useful if profiling shows norm overhead or
    graph-capture compatibility issues.
- Caveat:
  - Old base and broad layernorm rewrite. Treat as a pattern source.

### `Wei-Lin-Intel/vllm-xpu-kernels`

- Ahead/behind: 5 ahead, 16 behind.
- Non-merge commits:
  - `715e79069dd132d920bf5a519befec73d96d920e` - create `optimized_triton_moe.py`.
  - `4d6a3d173b89f160d16efaacb06aa6570518605b` - create `moe_compare.py`.
- Touched files:
  - `tests/fused_moe/optimized_triton_moe.py`
  - `tests/fused_moe/moe_compare.py`
- Value:
  - Medium as a benchmarking/source-of-shapes lead. It may contain MoE
    comparison harnesses or Triton-MoE reference code useful for route-window
    tests.
- Caveat:
  - Test/benchmark files only. Not an implementation candidate by itself.

### `JianyuLi01/vllm-xpu-kernels`

- Ahead/behind: 2 ahead, 93 behind.
- Unique non-merge commit:
  - `a742d4b05d06e1b4aeed66b811e1cf3b8ef2b952`
  - Subject: enable fused softmax/sigmoid + top-k path for 1024 experts.
- Touched file:
  - `csrc/moe/topk.cpp`
- Value:
  - Low to medium. The commit adds a 1024-expert top-k launch case and reports
    uplift for 1024 experts. Qwen3.6-35B-A3B does not use 1024 experts, so this
    is only a future-proofing or benchmark-shape lead.

### `PershingSquare/vllm-xpu-kernels`

- Ahead/behind: 1 ahead, 178 behind.
- Commit:
  - `dbe6ec4aee54a8091954da5a8c92d64b613adf71`
  - Subject: added support for oneDNN W4A16 grouped GEMM.
  - URL: https://github.com/PershingSquare/vllm-xpu-kernels/commit/dbe6ec4aee54a8091954da5a8c92d64b613adf71
- Touched files:
  - `csrc/xpu/grouped_gemm/grouped_gemm_interface.cpp`
  - `csrc/xpu/onednn/grouped_gemm_w4a16.cpp`
  - `csrc/xpu/onednn/grouped_gemm_w4a16.h`
- Value:
  - Medium for quantization exploration. It is not Quark W8A8, but it is a
    concrete XPU grouped-GEMM quant path that could inform W4A16/INT4 trials or
    long-context/capacity lanes.
- Caveat:
  - Very old base; do not mix with current W8A8 work without a clean port plan.

### `1pikachu/vllm-xpu-kernels`

- Ahead/behind: 1 ahead, 20 behind.
- Commit:
  - `e7138aed6627514ab50d697939ce43f695aa386b`
  - Subject: update vLLM kernel benchmark scripts.
- Touched file:
  - `benchmark/src/flash_attn_interface_.py`
- Value:
  - Low. Benchmark-only lead.

### `chaojun-zhang/vllm-xpu-kernels`

- Ahead/behind: 1 ahead, 236 behind.
- Commit:
  - `c3af52c1047e707ce8826a87a4f2253999711e07`
  - Subject: add fused op `silu_and_mul_per_block_quant`.
  - URL: https://github.com/chaojun-zhang/vllm-xpu-kernels/commit/c3af52c1047e707ce8826a87a4f2253999711e07
- Touched files:
  - `csrc/activation.cpp`
  - `csrc/ops.h`
  - `csrc/torch_bindings.cpp`
  - `tests/test_fused_silu_mul_block_quant.py`
- Value:
  - Medium. This overlaps fused activation + block quantization, which is
    relevant to MoE/W8A8 dataflow.
- Caveat:
  - Very old base and possibly superseded by upstream fused quantization work
    in `v0.1.10`; compare against current upstream before spending time.

### `DiweiSun/vllm-xpu-kernels`

- Ahead/behind: 2 ahead, 251 behind.
- Commits:
  - `c7a0cc633f288c3a7645fa82d74d35d9f4394147` - refine benchmark test utils.
  - `473896317336c058d264a5c4e76a5b48858eaf3d` - enable IPEX kernel benchmarking for reshape/cache.
- Touched files:
  - `benchmark/benchmark_rmsnorm.py`
  - `benchmark/benchmark_reshape_and_cache.py`
  - `tests/utils.py`
- Value:
  - Low to medium. Useful only as a benchmark harness lead for cache/reshape
    comparisons.

### `rogerxfeng8/vllm-xpu-kernels`

- Ahead/behind: 1 ahead, 138 behind.
- Commit:
  - `32019606a6bdc915a3bca2d3c9dd1bb5ed5fa412`
  - Subject: refresh README.
- Value:
  - Low. Documentation-only.

### `jikunshang/vllm-xpu-kernels`

- Ahead/behind: 3 ahead, 84 behind.
- Commits:
  - `bfbca001dcbceba5b52b7197067094e16ad9aef4` - replace `int` with `size_t` for size/count/stride/index variables across `csrc`.
  - `d2a704b03d57ea0a856fc733992da07e2b2779b6` - fix.
  - `8f2e1dbf8b692c7365dc728faecd463c95ebcac7` - pre-commit cleanup.
- Touched files:
  - Broad `csrc` integer-width edits.
  - `csrc/moe/remap_hidden_states.cpp` in the targeted fix commit.
- Value:
  - Medium for correctness/hardening, especially large shapes and overflow
    risks in MoE remapping/cache/index paths. Not a speed lead by itself.
- Caveat:
  - Broad mechanical change. Needs selective review, not wholesale porting.

## Fork Leads Worth Carrying Forward

1. High priority:
   - Jason Boukheir GDN active-prefix metadata narrowing.

2. Medium priority:
   - PershingSquare oneDNN W4A16 grouped GEMM as a quantization/pattern source.
   - Chaojun Zhang fused SiLU + per-block quant op, but first compare to
     upstream `v0.1.10` fused quantization work.
   - Wei-Lin Intel MoE comparison scripts as route-window benchmark scaffolding.
   - nc-BobLee IPEX-derived RMSNorm/layernorm work if profiling shows norm cost.
   - Jikunshang integer-width/index hardening for large-shape correctness.

3. Low priority:
   - 1024-expert top-k launch case, benchmark-only commits, and README-only
     commits.

## Follow-Up

- Add the high/medium fork leads to the upstream-delta matrix alongside
  upstream PRs 392, 401, 422, 424, 429 and vLLM PRs 46210/46226.
- For each fork lead, first check whether upstream `v0.1.10` or newer PRs
  already supersede it.
- Do not cherry-pick any old-base fork directly into the working tree.
