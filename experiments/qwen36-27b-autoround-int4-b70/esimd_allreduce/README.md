# Qwen27 TP2 ESIMD IPC All-Reduce Prototype

Status: **closed as a standalone synchronization no-win; preserve for future
Level Zero/ESIMD reference**.

Standalone prototype for the remaining Qwen3.6 27B TP2 command-graph blocker.
The fast target graph intermittently corrupts the packed verifier's BF16
`[4, 5120]` row-parallel all-reduce; moving all 72 reductions outside capture
restores quality but reduces throughput below TP1.

This experiment deliberately avoids B70 peer atomics. Each rank writes its own
ring-buffered Level Zero IPC mailbox, publishes a local sequence, then reads
the peer mailbox with uncached ESIMD loads after a `system_acquire` fence. A
single workgroup performs copy, notification, polling, and reduction so it can
remain inside an XPU command graph.

## Outcome

The arithmetic kernel and local mailbox publication worked, but cross-card
device-side completion could not be made reliable on this B70 PCIe topology:

- uncached peer polling plus `system_acquire` timed out with both `100,000`
  and `10,000,000` poll budgets on both GPU pairs;
- Level Zero memory-range barriers and device/host-scoped local events did not
  make the peer sequence visible;
- default, uncached, and cached IPC open modes behaved the same;
- binary IPC events passed in one process, but importing an event pool into a
  second PyTorch process crashed the importing rank even with the pool file
  descriptor transferred through `SCM_RIGHTS` and rank-0-owned topology;
- external immediate counter events were accepted by Level Zero, but the
  cross-card semaphore wait deadlocked;
- precompiling the ESIMD kernel on both ranks ruled out JIT skew.

Do not repeat these variants without a new B70 peer-coherence primitive. The
successful replacement direction is the public oneCCL build and deterministic
graph oracle in `../oneccl_ll256/`.

Build:

```bash
cd /home/steve/llm-optimizations/experiments/qwen36-27b-autoround-int4-b70/esimd_allreduce
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh
/home/steve/.venvs/vllm-xpu/bin/python setup.py build_ext --inplace
```

Direct and command-graph validation on one TP2 pair:

```bash
ZE_AFFINITY_MASK=0,1 PYTHONPATH=. \
  /home/steve/.venvs/vllm-xpu/bin/torchrun --standalone --nproc-per-node=2 \
  test_tp2_allreduce.py --rows 4 --hidden 5120 --iterations 1000

ZE_AFFINITY_MASK=0,1 PYTHONPATH=. \
  /home/steve/.venvs/vllm-xpu/bin/torchrun --standalone --nproc-per-node=2 \
  test_tp2_allreduce.py --rows 4 --hidden 5120 --iterations 1000 --graph
```

This is not a promoted model result. Integration is allowed only after long
varying-input direct and graph-replay validation passes on both GPU pairs and
the kernel materially beats the existing eager collective boundary.
