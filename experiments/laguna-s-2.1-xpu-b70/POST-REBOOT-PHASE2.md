# Laguna — post-reboot Phase 2 checklist

Written immediately before an authorized clean reboot on 2026-07-26.
Steve authorized the reboot; nothing beyond it is authorized yet.

## Pre-reboot state, for comparison

- boot_id before reboot: `ddb1ef05-660e-43d3-8931-12d87d796b76`
- boot time before reboot: 2026-07-25 22:12:05
- repo HEAD: `8494e1ce1` (local only; origin/main is `a81675454`)
- worktree clean; no vLLM, probe, ladder or leg processes; port 18080 free

## Why the reboot happened

The collective genuinely hung before any recovery action — four transport
configurations each reached `tensor-allocated` and never returned from
`all_reduce`. Recovery then went wrong: the probe launcher named
`$scratch/xccl_probe.py` while the tracked program is the sibling
`xccl_collective_probe.py`, so every post-recovery probe died with
`can't open file` and reported "0/4" that meant *zero programs started*. On that
non-result a driver unload/rebind, four PCIe FLRs, and the deletion of 37
`/dev/shm` objects were applied. Host state afterwards is therefore **unknown**,
and a clean reboot is the conservative reset. Commit `8494e1ce1` makes the probe
fail closed so this cannot recur.

## Phase 2 — host gate, before any model work

1. Confirm the reboot: `boot_id` differs from the value above.
2. Record kernel version, taint, and a bounded `dmesg` baseline.
3. Confirm all four B70 identities and BDF→DRM mappings
   (`0000:23:00.0`, `0000:27:00.0`, `0000:43:00.0`, `0000:47:00.0`).
4. Confirm no foreign GPU processes and strict idle (~43 MiB per card).
5. Bounded per-device execution check, **once** per card.
6. Exactly **one** corrected 4-rank collective probe, fresh artifact root:

       experiments/laguna-s-2.1-xpu-b70/tools/run_xccl_collective_probe.sh <label> \
         ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 \
         CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 FI_TCP_IFACE=eno1 CCL_KVS_IFACE=eno1

   Success is **only** the exact marker `PROBE_RESULT=PASS clean_teardowns=4/4`.
   Read the rank logs, not the summary line.
7. On anything else: stop, preserve logs, report the classified boundary, do not
   repeat the probe and do not invent a recovery conclusion.

## Phase 3 — re-establish the approved control

Only after the host gate passes. Width-8 control at the record identity;
require audited 146/145 on every rank, the full exact/cache-zero/canary gate,
actual identity capture, and comparison against **94.920039** tok/s without
relabelling ordinary variance as regression. If the control does not
re-establish health and correctness, stop — do not debug M12 on an invalid
baseline.

## Then

Phase 4 prove the parameterized source inert at M8. Phase 5 width 12 as one
bounded structural test with a preregistered topology ceiling. Phase 6 choose
the next mechanism from measurements, not projections.

## Standing

Approved record: **94.920039 tok/s**. No candidate has ever been measured
against it at any other width. Every higher figure in this lane's notes is a
projection.
