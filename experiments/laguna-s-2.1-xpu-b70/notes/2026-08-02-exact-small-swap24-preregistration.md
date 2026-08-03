# Laguna exact-small portfolio: swap24 resource-remediation smoke

Date: 2026-08-02 America/Toronto

Status: **preregistered; one fresh non-scored TP4 2x400 smoke is authorized
only after this packet, the reviewed resource harness, and a separate
non-self-referential execution lock are committed. No endpoint is authorized.**

Steve asked not to stop optimizing. The corrected ordinary-swap smoke is
consumed and preserved as an inconclusive resource-gate stop: it loaded target
and draft, then crossed the frozen combined host guard during KV-cache
initialization before API health, graph capture, or any request. This packet is
a new one-shot resource-remediation gate, not a reuse of tag or lock
`20260803T010333Z`.

## Evidence-backed resource change

The only model/resource change is one nonpersistent 16 GiB swap file at
`/swap-laguna-longctx.img`, yielding the exact active layout:

```text
/swap-laguna-longctx.img:16777212
/swap.img:8388604
```

All selectors, source/native/model hashes, TP/EP topology, workload, GPU
utilization `0.90`, and 8/16 GiB memory plus 4 GiB free-swap guards remain
identical to the consumed smoke.

This is the smallest validated resource treatment:

- the consumed exact-small smoke alarmed at `16,013,720/341,476 kB`
  MemAvailable/SwapFree after consuming about 7.67 GiB of ordinary swap;
- the scheduler control and candidate both completed their TP4 arms with this
  exact 24 GiB total layout, reaching independent minima of
  `11,254,440/14,753,984 kB` and `9,546,816/16,540,240 kB` respectively;
- an earlier `gpu_memory_utilization=0.80` lane with ordinary 8 GiB swap still
  crossed the same combined guard at `16,037,464/935,928 kB`, so lowering GPU
  utilization alone is not a validated remedy and would change benchmark
  identity;
- a smaller swap addition is not authorized because the post-graph peak for
  this candidate is unknown, while the 16 GiB addition is already proven.

The temporary swap is a safety/resource envelope, not performance evidence.
Smoke latency must not be interpreted or promoted.

Before the execution lock, Bash syntax and whitespace checks, Ruff, and all
18 executable CPU harness checks pass; the nineteenth check is intentionally
skipped until the new lock exists. No privileged, model, or device action was
used for those checks. The frozen source trees also repeat-pass all 14
candidate-kernel static contracts and all three focused vLLM mapped-tail
integration tests.

## Frozen identity and entry point

The frozen source, native, runtime, model, and selector identity is exactly the
one in
[`2026-08-02-exact-small-postrecovery-preregistration.md`](2026-08-02-exact-small-postrecovery-preregistration.md),
including vLLM `0c9dea8cf9aa46c1854d5bce8f4dfb180732b16d`, XPU kernels
`46a6393fc188c11661ddab9cf1320d2f3de45087`, GPU utilization `0.90`, M12,
DFlash11, mapped tail, no-K-loop barriers, scale-lane dedup, and the same
2x400 non-scored request gate.

After the harness commit and a separate lock-only commit, the only authorized
entry point is:

```bash
experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_exact_small_swap24.sh \
  20260803T014822Z
```

The lock binds the exact tag and these fresh roots:

- resource:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-exact-small-postrecovery-20260803T014822Z-swap24-resource`;
- campaign:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-exact-small-postrecovery-20260803T014822Z-campaign`;
- smoke:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-exact-small-postrecovery-20260803T014822Z-smoke`.

The resource wrapper starts under `env -i`, validates the lock and fresh roots
before privileged action, acquires a stable mutex, proves the temporary path
absent and ordinary swap exact, then uses the local out-of-repository sudo
credential without printing it. A locked helper uses exclusive, no-follow
creation and POSIX allocation, records the created device/inode/owner/mode/size
identity, converts HUP/INT/TERM during allocation into a cleanup path, and
removes only the same created inode on allocation failure or interruption. The wrapper
requires that same exact regular root-owned mode-`600` 16 GiB identity before
and after `mkswap`/`swapon`, then proves the exact 24 GiB layout.
It requires at least 32 GiB free on the root filesystem before allocation and
never changes `/etc/fstab`.

The core wrapper requires resource-arm evidence and the exact active layout at
prestart, postsmoke, and terminal audit. On every terminal path the outer
wrapper uses the locked resource-safety helper to stop the persistent core
process-group identity even if its leader has exited, stops the exact recorded service, proves no
model process or protected listener remains, then fallback-seals any core
roots. It runs `swapoff` and removes the backing file only after a strict
inactive-state check and a same-device/inode identity check. If owned teardown,
core-root sealing, state inspection, identity, or `swapoff` fails, it must not
delete the file; the resource cleanup fails closed and preserves the exact
state for controlled recovery. In particular, writable campaign/smoke roots
are explicitly reported and preserved when complete owned-process teardown
cannot be proved (`core_seal_status=125`). Forced core termination propagates
failure even if fallback cleanup succeeds. The resource root is sealed
read-only; campaign and smoke roots are sealed only after the owned teardown
proof. The pre-seal status never claims sealing success, so actual permissions
plus process exit are the authority. A final kernel-journal scan spans resource
creation through swapoff/removal and fails on any matching XPU,
NVMe/controller, PCIe/AER corrected, uncorrected, reset, timeout, or error
event.

## Pass, stop, and next authorization

The candidate pass criteria are unchanged: 2/2 exact/cache-zero request
prefixes, four-rank target `146/145` and draft `14/13` capture/replay, four-rank
real `num_rows=12` and mapped-tail enable/dispatch proof, both grouped selectors
and prerequisites in all workers, exact grouped DSO maps, clean device journal,
clean teardown, and restored ordinary `/swap.img:8388604` as the sole swap.

Any resource, model, correctness, capture, dispatch, device, cleanup, or
sealing failure consumes this tag and stops. There is no retry. A pass
authorizes only a separately preregistered and locked cold 13x512 endpoint; it
does not authorize scoring or LocalMaxxing submission by itself. No XPU probe,
reset, FLR, driver reload, reboot, or unrelated recovery action is authorized.
