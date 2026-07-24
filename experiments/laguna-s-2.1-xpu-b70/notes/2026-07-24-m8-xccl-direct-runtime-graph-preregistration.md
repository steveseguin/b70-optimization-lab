# Laguna M8 direct-XCCL runtime-graph preregistration

Date: 2026-07-24 America/Toronto

## Scope

This authorizes one component-only probe of the runtime graph substrate. It
does not load the Laguna target or DFlash draft, start an endpoint, generate a
token, time endpoint throughput, stage a payload, use the network, or submit to
LocalMaxxing.

The approved record remains unchanged:

- `33.89498511171744 tok/s`;
- LocalMaxxing `cmrx6p5dv001bo4017hb7sixz`;
- vLLM `8936aac144929190c1e53f8b8624ca397ce16f5b`; and
- XPU kernels `b6076ce1249ffee0e30bee528f4cd15c3bffb234`.

The experimental target-only integration is separately committed at vLLM
`e09f34a008c31cb4c691697215a6eff3aa2eb5be`. It is default-off, keeps the
DFlash drafter eager, forces every target call except the true single-request
DFlash-7 M=8 verifier eager before graph padding/dispatch, pins the graph
output, and rejects any replay-time tensor pointer/offset/shape/stride/dtype or
device drift. Its focused CPU gate passed 17/17 and an independent re-audit
found no remaining dynamic-input blocker.

## Question

Can the installed XPU graph and XCCL stack directly record and replay the
incumbent Laguna collective pattern without stale data or changed BF16 bytes?

The probe records one graph containing exactly:

- 97 TP4 BF16 `all_gather_into_tensor` calls with per-rank shape
  `[1, 8, 3072]` and gathered shape `[4, 8, 3072]`;
- three literal rank-0, rank-1, rank-2, rank-3 BF16 additions after each
  gather; and
- one final BF16 XCCL all-reduce.

It then performs 32 changing-input epochs with four unique replays per epoch.
Every replay checks the raw uint8 view of all 97 gathered tensors, all 97
fixed-rank sums, and the final all-reduce. This is 24,960 raw comparisons per
rank and 99,840 across the four-card process group. Source and output digests
must change on all 127 transitions.

The final all-reduce fixture uses small integral BF16 values so its expected
sum is order-independent. The 97 rank sums use the literal incumbent
rank-ordered BF16 boundaries.

## Frozen identity

- tool commit: `d9e88ff060c9b98dd169547d6aeb9ae31f55c629`;
- tool:
  `experiments/laguna-s-2.1-xpu-b70/tools/probe_laguna_m8_xccl_graph.py`;
- tool SHA-256:
  `1797ae4df5f61f6583fa0ba8942cac7e212f4dfbdc36a28e971734d4f89f264f`;
- Python:
  `/home/steve/.venvs/deepseek-v4-xpu/bin/python`,
  SHA-256
  `202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8`;
- oneCCL:
  `/home/steve/.venvs/deepseek-v4-xpu/lib/libccl.so`,
  SHA-256
  `ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3`;
- Level Zero adapter SHA-256:
  `26fa68779adb03b200a8c3001cf81e59fc9a3d63e0f38627ec0005ffce574e7a`;
- Level Zero loader SHA-256:
  `0fe232b18985ae078dd546b57bc6d11bacf1030834c0544f7e3feb53ed71c1d0`;
- boot: `0b7f98a5-e50a-46a5-81ea-15938b55317a`;
- kernel: `7.0.0-28-generic`; and
- output:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-xccl-direct-graph-d9e88ff06-20260724T141124Z`.

The tool rejects any output outside the internal-NVMe artifact subtree,
requires a new root, and verifies its backing mount is ext4 on an NVMe block
device. The external Corsair/NTFS volume is forbidden.

## Frozen command

After a read-only four-card discovery/process check confirms no foreign XPU
work:

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
  LD_LIBRARY_PATH=/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib \
  timeout --signal=TERM --kill-after=15s 240s \
  /home/steve/.venvs/deepseek-v4-xpu/bin/python \
  -m torch.distributed.run \
  --standalone \
  --nproc_per_node=4 \
  /home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/probe_laguna_m8_xccl_graph.py \
  --output-root /mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-xccl-direct-graph-d9e88ff06-20260724T141124Z \
  --epochs 32 \
  --replays-per-epoch 4
```

## Decision rule

- Continue the direct-capture branch only if all four rank results and the
  aggregate report `pass`, all 99,840 raw comparisons match, every freshness
  transition changes, and there is no timeout, fallback, device loss, or
  runtime error.
- A capture/runtime failure or raw mismatch closes direct collective capture.
  It does not authorize a retry of unchanged code; the next permissible design
  is a separately reviewed segmented graph that keeps all 98 collectives eager
  with caller-owned persistent buffers.
- A tooling or infrastructure failure before graph construction may be fixed
  only under a new tool identity and new preregistration. It is not a
  performance or correctness result.
- Even a pass authorizes only an actual target-M8 component/trace gate. It does
  not authorize an endpoint. Model/revision/quantization hashes and the
  canonical q1 teacher contract must be bound separately before any model
  execution.
