# Laguna M8 segmented graph substrate gate preregistration

Date: 2026-07-24 America/Toronto

## Scope

This authorizes one four-card, changing-input, substrate-only execution. It
does not load Laguna or DFlash, start an endpoint, tokenize a prompt, generate
a token, access the external USB, measure model throughput, stage a payload, or
contact LocalMaxxing.

The current approved record remains:

- `33.89498511171744 tok/s`;
- LocalMaxxing `cmrx6p5dv001bo4017hb7sixz`;
- record vLLM `8936aac144929190c1e53f8b8624ca397ce16f5b`; and
- XPU kernels `b6076ce1249ffee0e30bee528f4cd15c3bffb234`.

The source candidate under investigation is vLLM
`0964fe3d1b3508e39ee2455f70f1dbc7b13b0fd5`. It is not a record candidate
until every later model, trace, timing, exactness, freshness, and reproducibility
gate passes.

## Question

Can the installed four-B70 XPU/XCCL stack execute the corrected target-forward
boundary topology with changing data while every collective remains eager and
the graph segments before, between, and after those collectives replay exact
bytes through fixed addresses?

The topology is frozen as:

```text
graph prelude
eager embedding all-reduce: BF16 [8,3072]
graph bridge producing gather input 0
(
  eager all-gather: BF16 [1,8,3072] -> [4,8,3072]
  graph fixed-rank BF16 sum producing the next gather input
) x 96
```

The last post-gather graph writes the final tail. This is exactly 97 eager
collective boundaries and 98 graph segments. No collective is textually inside
a graph capture context.

The embedding fixture is owner-partitioned like a vocab-parallel embedding:
each element is nonzero on exactly one rank. This prevents an irrelevant
multi-contributor BF16 tree-order mismatch of the kind that terminated the
earlier synthetic direct-capture probe. Every later local gather input is
produced by the preceding graph, not staged by the host.

## Frozen identity

- tool commit:
  `c21aa5a275f49fd403990f74dc7d268942a65f64`;
- tool:
  `experiments/laguna-s-2.1-xpu-b70/tools/probe_laguna_m8_xccl_segmented_graph.py`;
- tool SHA-256:
  `58fb19e162dc8fe5d45c2475a68ad3f6c05c8a74d283bc9d5a29bbdf842cf173`;
- vLLM:
  `0964fe3d1b3508e39ee2455f70f1dbc7b13b0fd5`;
- output root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-xccl-segmented-substrate-c21aa5a27-20260724T145032Z`;
- epochs: 32;
- replays per epoch: 4; and
- total changing replays: 128 per rank.

The tool itself requires a clean exact vLLM worktree, four distinct physical
Arc Pro B70 UUIDs and PCI BDFs, matching DRM/sysfs `8086:e223` identities,
internal NVMe/ext4 output, nonaliasing persistent buffers, and unchanged
pointers before every replay. Those checks run before XCCL initialization.

## Frozen command

Immediately before execution, perform only read-only service/process,
four-device discovery, boot/taint, mount, and short idleness checks. If they
pass, run exactly:

```bash
env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 \
  ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 \
  ZE_AFFINITY_MASK=0,1,2,3 \
  CCL_ATL_TRANSPORT=ofi \
  CCL_TOPO_P2P_ACCESS=1 \
  FI_TCP_IFACE=eno1 \
  CCL_KVS_IFACE=eno1 \
  TORCH_XCCL_ASYNC_ERROR_HANDLING=1 \
  LD_LIBRARY_PATH=/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib \
  timeout --signal=TERM --kill-after=15s 300s \
  /home/steve/.venvs/deepseek-v4-xpu/bin/python \
  -m torch.distributed.run \
  --standalone \
  --nproc_per_node=4 \
  /home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/probe_laguna_m8_xccl_segmented_graph.py \
  --output-root /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-xccl-segmented-substrate-c21aa5a27-20260724T145032Z \
  --epochs 32 \
  --replays-per-epoch 4 \
  --timeout-seconds 120
```

## Pass and stop rules

A pass requires:

- four rank results plus one aggregate, all reporting `pass`;
- 24,832 raw comparisons per rank and 99,328 across the fleet;
- 127/127 changed input transitions and 127/127 changed tail transitions on
  every rank;
- 97 eager collectives and 98 graph segments in every rank protocol;
- identical tool/vLLM/boot/runtime/device identity across rank evidence where
  applicable;
- no alias or pointer drift, timeout, device loss, runtime error, kernel reject,
  or unexpected service/process; and
- an immutable sealed internal-NVMe result root.

Any raw mismatch, stale transition, topology/count drift, timeout, device or
runtime error, wrong identity, or non-NVMe output fails closed. A tooling
failure before graph construction may be corrected only under a new tool
identity and new root. A graph/runtime mismatch closes this substrate design.

Even a complete pass authorizes only construction and review of the actual
target-M8 model-forward/trace component gate. It does not prove the real
Breakable wrapper exact or faster and does not authorize a benchmark endpoint.
