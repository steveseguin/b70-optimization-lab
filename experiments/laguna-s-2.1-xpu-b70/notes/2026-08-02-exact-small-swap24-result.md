# Laguna exact-small swap24 smoke result

Date: 2026-08-02 America/Toronto

Status: **INCONCLUSIVE — the 24 GiB resource treatment cleared the prior host
memory gate, but the smoke stopped at an invalid post-`setproctitle` worker
environment proof before any request. The independent resource journal also
failed on three corrected PCIe RxErr events from the root-filesystem NVMe
endpoint. The tag is consumed.**

The fail-closed resource harness and lock-only commits are `638e0270a` and
`db59f62c1`. All 19 lock-aware CPU tests, 14/14 kernel static contracts, and
3/3 focused vLLM tests passed before the only authorized launch of
`20260803T014822Z`.

Structured result:
`data/laguna-exact-small-swap24-smoke-20260803.json`, SHA-256
`61658d944a35cba3e0c2a16f2bf54ac5e9d975192d12b150534fd3c41123cc7b`.

## Resource question answered

The temporary root-owned 16 GiB swap file produced the exact frozen layout:

```text
/swap-laguna-longctx.img:16777212
/swap.img:8388604
```

This cleared the consumed smoke's resource stop. Target and draft loading,
KV-cache creation, PIECEWISE graph capture, application startup, and two HTTP
health checks all completed. vLLM reported `17.27 GiB` model memory,
`39.133567 s` loading time, `5.92 GiB` KV-cache memory, and 114,051 KV-cache
tokens. Across 284 one-second host samples, the independent minima were:

- `MemAvailable=9,892,724 kB` at `02:52:38Z`;
- `SwapFree=14,714,468 kB` at `02:52:08Z`.

The frozen combined guard never crossed. This validates the resource remedy
for initialization only; smoke latency is not performance evidence.

## Primary smoke stop: invalid worker proof source

After API health, the runner attempted to prove the selector environment from
`/proc/<worker>/environ`. It found all four workers, created the two summary
files, and began with worker 74477. That transformed proc snapshot contained
5,082 NUL-delimited lines but only 31 nonempty environment entries; the
required `VLLM_XPU_LAGUNA_DECODE_NO_KLOOP_BARRIERS=1` entry was absent. The
first strict grep therefore returned status 1. Only one worker snapshot exists,
and both the worker-environment and DSO-map summaries are empty.

This does not show selector loss. The service environment has all required
values, and all four ranks emitted the M12 shared and mapped-tail enable
markers. A synchronized CPU reproduction using the frozen venv and
`setproctitle 1.3.7` passed a sentinel environment variable to a child. Static
inspection binds the direct title call to frozen vLLM commit `0c9dea8cf` and
`vllm/utils/system_utils.py` SHA-256
`f22b8d420dcfde31f92114d7f5b916797d5dcce4b840bfddfc99d287ce185452`,
whose wrapper delegates to the same call. Before the title change, the proc
snapshot had five nonempty entries and the sentinel; afterward it had zero
nonempty entries and no sentinel while the same child still read the sentinel
from `os.environ`. The output is preserved in
`data/laguna-setproctitle-proc-environ-reproduction-20260803.json` with SHA-256
`720f3ccb49b2916c3d84281eb76e07131c913fbb323b3cc00dd76abcee3aac6b`.
Reproduce it with
`experiments/laguna-s-2.1-xpu-b70/tools/reproduce_setproctitle_proc_environ.py`;
the executable pins the frozen venv interpreter directly.
This proves `setproctitle` can overwrite the kernel-visible initial environment
block, making post-title proc inspection incomplete and unreliable; absence
cannot prove selector loss. The harness correctly stopped on its frozen rule,
but that rule needs replacement with worker-emitted evidence before any future
model attempt.

No request began. There are no `num_rows=12` or mapped-tail dispatch markers,
no target 146/145 capture proof, no output, and no correctness or throughput
result. Initialization produced four-rank M12 enable, `num_rows=8192`,
`num_rows=1`, 14/13 capture, and 31-projection FP8 preparation markers only.

## Independent resource-journal failure

The outer resource journal found three corrected PCIe events at local times
22:47:34, 22:51:22, and 22:51:45. All identify the `0000:01:00.0` Samsung 980
PRO root-filesystem NVMe endpoint, with `aer_cor_status=0x00000001`, no
uncorrected status, and `RxErr` at the physical layer/receiver. The kernel says
hardware corrected the events and no further action is required. Nevertheless,
the preregistration explicitly fails on corrected PCIe/NVMe events, so
`resource_cleanup_status=1` and this is not a clean model gate. There was no
matching GPU/Xe error.

## Teardown and decision

The runner recorded original status 1 and stop/worker/idle statuses 0. The core
wrapper recorded exit 2 with cleanup, terminal audit, and sealing all 0. The
resource wrapper safely stopped all owned processes, proved no protected
listener, restored `/swap.img:8388604` as the sole swap, removed the temporary
file by exact inode after `swapoff`, and sealed all three roots read-only. Its
status remains failure because the resource journal matched. Current host
memory and ordinary swap recovered; no model process remains.

Roots:

- resource:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-exact-small-postrecovery-20260803T014822Z-swap24-resource`;
- campaign:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-exact-small-postrecovery-20260803T014822Z-campaign`;
- smoke:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-exact-small-postrecovery-20260803T014822Z-smoke`.

Consume the tag and lock. Do not retry, score, submit, or treat the run as
candidate evidence. The safe next work is offline: replace the invalid proc
environment proof with explicit per-worker selector logging and tests. The
corrected root-filesystem NVMe endpoint events also mean no further heavy model
run, XPU probe, reset, reload, reboot, or recovery action is authorized by this
packet.
