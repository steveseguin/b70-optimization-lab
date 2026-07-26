# Laguna — the M=12 topology explosion wedged the GPU collective stack

Date: 2026-07-26 America/Toronto

Status: **host blocked, reboot required.** Approved record remains
**94.920039** tok/s. Goal of 102 not met. No measurement was possible this
session.

## The failure, end to end

1. A width-12 run serialized the exact linear paths per row, inflating the
   breakable-graph topology from the audited **146 graphs / 145 eager breaks**
   to **685 / 684** — `685 − 146 = 539 = 11 × 49`, i.e. `(M−1)` extra breaks per
   layer.
2. Capture kept going. Each extra segment holds device memory, and the run
   eventually died inside a Level Zero graph replay with
   `UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY`.
3. That OOM left the collective stack wedged. **Every** run since hangs in
   `xpu_worker.init_device` at its warm-up `all_reduce` — including runs at the
   untouched record commit `ef334233d`.

The last run to get past init was `laguna-m12coll3` at 02:17 UTC, which is the
run that hit the OOM at 02:42. Everything after it hangs.

## Isolation: the fault is below vLLM

A 40-line probe — four ranks, one 8-element float32 `all_reduce`, no vLLM, no
model, no graphs — hangs at exactly the same point. All four ranks reach
tensor allocation, then the collective never returns and the ranks spin at
~75% CPU.

Three CCL configurations were tried and all hang identically:

| configuration | ranks completing `all_reduce` |
| --- | ---: |
| `ofi` transport, `CCL_TOPO_P2P_ACCESS=1` (the record setting) | 0 / 4 |
| `ofi` transport, `CCL_TOPO_P2P_ACCESS=0` | 0 / 4 |
| CCL defaults, no overrides | 0 / 4 |

Supporting state: all four B70s enumerate, report healthy, sit at 43 MiB idle,
and Torch sees 4 × 32656 MiB. The `xe` module refcount is **76**, far above a
quiescent value, so a module reload cannot succeed. Device enumeration and
ordering are correct, so this is not a device-selection problem.

## Refinement: the driver has leaked execution resources, progressively

The four-configuration sweep showed the collective always hangs, but stopping
there was wrong. Testing each card **individually**, with no collective
involved at all, shows plain single-card matmuls failing too:

| device | first pass | later pass |
| --- | --- | --- |
| `xpu:0` | OK | — |
| `xpu:1` | **fails** | **fails** |
| `xpu:2` | OK | — |
| `xpu:3` | not reached | **fails** |

The errors alternate between `UR_RESULT_ERROR_DEVICE_LOST` (20) and
`UR_RESULT_ERROR_OUT_OF_RESOURCES` (40) on cards reporting 43 MiB used. An
earlier reading of this as "one bad card" was too strong: `xpu:3` passed nothing
and then failed, so cards are degrading as attempts accumulate. The consistent
reading is driver-wide exhaustion of GuC execution resources, with each attempt
leaking more.

This fully explains the collective hang — `all_reduce` waits forever on a rank
whose device cannot execute — and it means the collective was the symptom, not
the fault. It also means single-card work is not a safe fallback: the cards that
still pass today are not reliably usable.

All four B70s remain bound to `xe` and PCI-enabled, so nothing has dropped off
the bus. Network is not implicated either: `eno1`, which
`FI_TCP_IFACE`/`CCL_KVS_IFACE` point at, is UP at 10.0.0.65.

## Recovery

No CCL configuration avoids the wedged card, and this build of `xpu-smi` has no
`reset` subcommand, so there is no unprivileged reset path. `sysfs` FLR is
root-only.

The `xe` refcount fell from 76 to 10 as the leaked processes exited, with no
process holding a render node. `modprobe -r` needs 0, so the reload is a long
shot and the reboot is the realistic step:

    sudo modprobe -r xe && sudo modprobe xe   # try first, much less disruptive
    sudo reboot                                # reliable fallback

Either needs Steve — this host has no passwordless sudo.

## The guard that stops this recurring

Capture now carries a **segment ceiling of twice the audited graph count** and
raises the moment it is crossed, so a wrong topology stays a Python error
instead of costing a reboot. The ceiling defaults to `None`, leaving everything
outside the audited Laguna path unchanged. Three tests cover the ceiling, its
default absence, and rejection of a non-positive value.

This matters beyond tidiness: the same explosion has now cost two recovery
cycles. The failure mode is not "the measurement was wrong", it is "the host
stops working".

## What is still unproven

Whether the three batched-M1 bound fixes actually restore a topology near
146/145 at width 12. They are statically confirmed inert at width 8 and to
admit width 12, but no width-12 run has reached capture since they landed.

## Post-reboot order

1. Width 8 at the record commit — startup completes, 146/145, median near
   94.920. Confirms the host.
2. Width 8 at current HEAD — same checks; confirms the parameterization is
   inert in practice.
3. Width 12 — topology near 146/145, still exact. The ceiling now makes a
   failure here cheap.
4. Measure width 12, then width 16.

## Why width 16 is now the target rather than width 12

The drafter's own config carries `dflash_config.block_size: 16`; vLLM never
reads it, so nothing enforces it, but it says the drafter was trained to
predict a block of 16. We have been using 7. That is consistent with the
measured result that conditional acceptance is flat across depth.

Fitting a flat-acceptance geometric model to the two measured points —
depth 7 emitting 3.703 tokens/cycle and depth 11 emitting 3.958 — gives
p ≈ 0.760 and 0.756 respectively, a very mild decay. Extrapolating that decay
to depth 15 projects ≈ 3.996 emitted/cycle, i.e. **+7.9%** over the record, or
about **102.4 tok/s at unchanged cycle time**.

That clears 102, but only by 0.4%, and only if cycle time is genuinely flat in
M. It is a real candidate, not a safe one. The width-two tree remains the lever
with actual margin: greedily spending a 15-node budget on the measured top-2
coverage (72.2% → 84.2%) projects ≈ 4.379 emitted/cycle, **+18.3%**. That needs
tree attention in the verifier and is a much larger change.
