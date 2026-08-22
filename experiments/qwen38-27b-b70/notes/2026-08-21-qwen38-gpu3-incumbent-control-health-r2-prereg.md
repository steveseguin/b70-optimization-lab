# Qwen3.8 GPU3 incumbent-control health r2 preregistration

Date: 2026-08-21

Status: **preregistered; single launch authorized after commit/push and hash
recheck; not yet run.**

## Basis

The [r1 terminal result](2026-08-21-qwen38-gpu3-incumbent-control-health-result.md)
was a valid GPU3 stock-control health failure and requires that any further
stock-control health test use a new root and a new preregistration after a
separately authorized host-wide `xe` recovery. That recovery completed today
and passed its complete gate
([second recovery note](2026-08-21-measuring-host-xe-recovery-2.md)): four-
device discovery with expected BDF/UUIDs, per-card smokes, four-rank XCCL,
four-device peer read, an official-isolated exact-generation canary PASS, and
a zero-error post-reload journal window. This r2 asks the same bounded
question on the recovered stack: does the stock KV-128 FlashAttention
launch/synchronize prefix complete once on physical GPU3?

## Contract

This r2 adopts the
[r1 preregistration](2026-08-21-qwen38-gpu3-incumbent-control-health-prereg.md)
contract in full and without modification: same frozen worker, external
supervisor, CPU tests, and base qualifier —

- worker `bd8225e30e1335a3fe33e78421b1feb3cfb036ca04d0ca6738cb1eea8639b11f`;
- supervisor `eb619535786a3c7a8929b2d3b1c3848486d3edc1b96804c79831eaf8c3923375`;
- CPU tests `73ff3a5cd881a3a278db96b4b2130f18ddf55b8722bb56182363b36e9c83efc6`;
- base qualifier `0dd7b945ef35a11ff4d0a1ec085e604920524b996d539e089d89b4a019a5de1f`;

all four recomputed and matched on 2026-08-21 before this registration. Same
receipt chain, watchdog, 60-second deadline, decision rules, and terminal
classifications. The only changes are the fresh result root

```text
/home/steve/qwen38-gpu3-incumbent-control-health-20260821-r2
```

(which must not exist before launch; the immutable r1 root is preserved and
never reused) and the post-recovery boot context, which the harness rebinds
live (boot ID, device UUID `868023e2-0000-0000-4700-000000000000`, PCI
`0000:47:00.0`, `ZE_AFFINITY_MASK=3`).

A pass says only that this stock prefix completed once on GPU3 post-recovery
and may authorize writing a fresh preregistration for a two-GPU eight-arm
Q64xK32 operator campaign; it authorizes nothing else. Any failure preserves
the root, is terminal for this root, and authorizes no recovery by itself.
The r1 and Q64xK32 r2 roots remain terminal in every outcome.

## Launch condition

Clean `main == origin/main` including this note, hashes rechecked immediately
before the single launch, no model workload or AOT build running on any
card, and a quiet pre-launch kernel-journal check. One launch only; no
in-place retry.
