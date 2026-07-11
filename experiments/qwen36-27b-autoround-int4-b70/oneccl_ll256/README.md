# Qwen27 TP2 oneCCL LL256 Replay Lane

This lane isolates the packed-verifier TP2 corruption to oneCCL command-graph
replay and provides a reproducible replacement-library test without modifying
the installed XPU environment.

## Deterministic Oracle

`graph_allreduce_probe.py` captures the Qwen verifier's BF16 `[4, 5120]`
all-reduce, changes every input before every replay, and checks every output
element against an exactly representable BF16 sum.

Observed on 2026-07-11:

- packaged oneCCL `Gold-2021.17.2`, `HEAD/b9deca8`: failed on both ranks;
  `510/512` and `511/512` replay iterations were wrong;
- public oneCCL parent `b52f40c`, legacy library `4ceafd1`: passed `512/512`
  on both ranks and passed a separate `256/256` direct-collective control;
- the public build plus an explicit counter-kernel dependency also passed, but
  the source-matched public build passed without it. The dependency patch is
  therefore preserved as inconclusive and is not the attributed fix.

Evidence:

- `../../../data/qwen36-27b-autoround-int4-b70-baselines/oneccl-installed-ll256-graph-baseline-20260711.json`;
- `../../../data/qwen36-27b-autoround-int4-b70-baselines/oneccl-ll256-seqdep-direct-20260711.json`;
- `../../../data/qwen36-27b-autoround-int4-b70-baselines/oneccl-ll256-seqdep-graph-20260711.json`;
- `../../../data/qwen36-27b-autoround-int4-b70-baselines/oneccl-public-unpatched-ll256-direct-control-20260711.json`;
- `../../../data/qwen36-27b-autoround-int4-b70-baselines/oneccl-public-unpatched-ll256-graph-control-20260711.json`.

## Build

The 230 MiB library is intentionally not committed. Build it from pinned
public source. The validated host used Intel oneAPI compiler 2025.3 plus the
Ubuntu `libopenmpi-dev`, `openmpi-bin`, and `libpmix-dev` packages:

```bash
cd /home/steve/llm-optimizations
ONECCL_INSTALL_DIR=/mnt/usb-models/llm-runtime/oneccl-4ceafd1-b70 \
  experiments/qwen36-27b-autoround-int4-b70/oneccl_ll256/build-public-oneccl.sh
```

The build compatibility patch only disambiguates two ESIMD barrier calls for
Intel compiler 2025.3. The optional sequence dependency can be screened with
`APPLY_SEQUENCE_DEPENDENCY=1`, but it is not required by the standalone oracle.
The build script explicitly removes that optional patch when the flag is `0`,
so a reused source tree cannot silently contaminate the public control build.

## Validate

Use `LD_PRELOAD`; `LD_LIBRARY_PATH` alone does not override the RPATH used by
the installed PyTorch XPU library.

```bash
INSTALL=/tmp/oneccl-public-qwen27-build/install
LD_LIBRARY_PATH="$INSTALL/lib:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib" \
LD_PRELOAD="$INSTALL/lib/libccl.so.1.0" \
CCL_KERNEL_PATH="$INSTALL/lib/ccl/kernels" \
CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 CCL_ZE_IPC_EXCHANGE=pidfd \
ZE_AFFINITY_MASK=0,1 \
/home/steve/.venvs/vllm-xpu/bin/torchrun --standalone --nproc-per-node=2 \
  experiments/qwen36-27b-autoround-int4-b70/oneccl_ll256/graph_allreduce_probe.py \
  --mode graph --iterations 512
```

This oracle is a correctness diagnostic, not a throughput claim. Promotion
still requires the fixed fresh realistic suite, `cached_tokens=0`, target
verification, and the full quality gate.

## Promoted TP2 Endpoint

The checksum-gated endpoint wrapper is:

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=2,3 PORT=19443 \
QUALITY_REPEAT_RUNS=128 \
  experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-candidate.sh
```

The 2026-07-11 promotion uses the conservative isolated strict result:

- median `78.22635247759823 tok/s` for generated tokens 1-100 after TTFT;
- p10 `69.9633890122676`, mean `78.59814141426254`;
- all 12 fixed realistic prompts run once, `cached_tokens=0` throughout;
- no prompt/KV/history/response reuse and target-verified MTP3;
- a separate full-quality run reached `81.34114517681084 tok/s` and passed
  exact canaries, repeat128, baseline parity, and the 1K needle.

Use `78.226` as the reproducible headline because the two valid rows differ by
`3.98%`, inside the established `4.4%` endpoint variance band. See
`../../../results/qwen36-27b-autoround-int4-b70/tp2-public-oneccl-4ceafd1-20260711.json`
for exact runtime hashes and artifacts.
