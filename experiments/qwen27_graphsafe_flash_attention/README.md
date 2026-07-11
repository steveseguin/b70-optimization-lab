# Qwen27 graph-safe Intel FlashAttention chunk prefill

Status: implementation and CPU-side build/static checks complete; corrected
paged-KV GPU replay and endpoint gates remain pending.

Focused build result on 2026-07-11: PASS with IntelLLVM 2026.0.0. The compiled
target was
`chunk_prefill_kernel_template_chunk_policy_head256_ftfff.cpp.o`; the full
attention library/extension build and XPU replay gate remain deferred.

## Scope

The patch changes only
`csrc/xpu/attn/xe_2/chunk_prefill.hpp`. It replaces the graph-incompatible
`work_group_scratch_size` launch property with handler-owned, typed
`sycl::local_accessor<FMHAKernel::SharedStorage, 1>` storage and calls the existing
`FMHAKernel::operator()(Params, char*)` entry point. The launch still requests
subgroup 16 and 256 GRFs. Paged decode and all other kernels are out of scope.

Source identity inspected while producing the patch:

- tree: `/home/steve/src/vllm-xpu-kernels`
- commit: `3b4effeeffd83f6ef4696bbe7e76d924a0e9d171`
- source tree was already dirty in unrelated files; neither it nor any other
  path outside this experiment directory was modified

The first review revision incorrectly focused the non-paged `ftfff`
specialization and replayed unchanged outputs. Independent review caught both
problems before a GPU claim. The current revision builds paged causal `ttfff`,
uses typed/aligned local storage, poisons output before every replay, mutates
static graph inputs/sequence metadata, and uses nontrivial paged block tables.

## Artifacts

- `qwen27-chunk-prefill-local-accessor.patch`: one-file implementation patch
- `validate.sh`: patch applicability and invariant checks; never touches a GPU
- `build.sh`: copies the source into `work/source`, applies the patch there,
  configures under `work/build`, and compiles the focused FP16 causal head-256
  chunk-prefill object; `--full` also builds the attention library and Python
  extension
- `test_graph_replay.py`: XPU-only output-parity and command-graph replay gate

Generated `work/` contents are experiment-local and should not be committed.

## Validation and build

Run the static checks against the current source without modifying it:

```bash
cd /home/steve/llm-optimizations/experiments/qwen27_graphsafe_flash_attention
./validate.sh /home/steve/src/vllm-xpu-kernels
```

Build the focused specialization in an experiment-local source snapshot:

```bash
cd /home/steve/llm-optimizations/experiments/qwen27_graphsafe_flash_attention
MAX_JOBS=8 ./build.sh
```

Build the complete XE2 attention library and FA2 extension after the focused
object passes. The script places the extension in the staged package at
`work/source/vllm_xpu_kernels/`:

```bash
cd /home/steve/llm-optimizations/experiments/qwen27_graphsafe_flash_attention
MAX_JOBS=8 ./build.sh --full
```

To apply the patch later to a clean, explicitly approved kernel checkout:

```bash
git -C /path/to/vllm-xpu-kernels apply --check \
  /home/steve/llm-optimizations/experiments/qwen27_graphsafe_flash_attention/qwen27-chunk-prefill-local-accessor.patch
git -C /path/to/vllm-xpu-kernels apply \
  /home/steve/llm-optimizations/experiments/qwen27_graphsafe_flash_attention/qwen27-chunk-prefill-local-accessor.patch
```

## Deferred GPU gate

Only run this when the selected XPU is reserved. The probe enforces at least
1000 replays per shape and checks every replay against a float32 reference:

```bash
cd /home/steve/llm-optimizations/experiments/qwen27_graphsafe_flash_attention
source /opt/intel/oneapi/setvars.sh
PYTHONPATH=$PWD/work/source \
  /home/steve/.venvs/vllm-xpu/bin/python test_graph_replay.py \
  --device 0 --replays 1000 | tee graph-replay-result.json
```

The fixed gate is FP16, one packed MTP3 group (`rows=4`), TP2-local 12 query
heads and 2 KV heads, head dimension 256, paged causal KV lengths
128/1024/2048 with 64-token pages and nontrivial block tables, direct and
graph output parity, poisoned output before every replay, dynamic Q/sequence
metadata mutations, and 1000 command-graph replays for each shape (3000 total).
