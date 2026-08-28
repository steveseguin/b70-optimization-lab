# Flash-Next post-A11 retained host-memory recovery preregistration

Date: 2026-08-28
Status: frozen before any privileged device action

## Purpose and scope

Restore the host-memory baseline after graph attempt 7's TTM eviction failures and global OOM window and the subsequent progressive loss of clean-idle MemAvailable. This is recovery-only work. It grants no speed, quality, model-matrix, deployment, or website credit and cannot change any captured result. Attempt 11 remains a closed Grade-D pre-admission negative.

The protected eager TP4/MTP0 speed family and its 5.223788770 short-median and 4.757818102 exact-4K-median values remain immutable. No admission floor may be lowered to hide retained state.

## Frozen decision gate

1. Keep the host quiet for 15 minutes after the A11 closeout and sample MemAvailable, Cached, Slab, and SwapFree once per minute.
2. If MemAvailable reaches at least 110,100,480 KiB (105 GiB), remains at or above it, and does not decline by more than 262,144 KiB, skip the reload.
3. If it plateaus below 105 GiB or declines, authorize exactly one all-four B70 unbind followed by `modprobe -r xe` and `modprobe xe`. Do not use PCI FLR, per-device rebind, reboot, or repeated reloads.

## Mandatory pre-reload gates

- repository state and A11 closeout are durable;
- no vLLM, worker, serving, benchmark, XCCL, Torch-distributed, or relevant listener exists;
- `/proc/swaps` contains only `/swap.img`, size 8,388,604 KiB, priority -1, and no temporary A11 swapfile;
- a root-level holder check finds no owner of the four B70 card and render nodes;
- the four live BDFs are resolved again from vendor/device IDs rather than assumed;
- console ownership is the AST adapter, all B70 connectors are disconnected, display-manager is inactive, and the boot command line contains `xe.disable_display=1`;
- system and user managers are running with no failed system unit;
- capture pre-action meminfo, buddyinfo, swaps, modules, BDF/UUID/node mapping, idle device memory, ownership, and a journal cursor.

Any failed gate stops the procedure without unbinding a card.

## Exact recovery action

Unbind all four freshly resolved B70 BDFs from the single live `xe` driver, remove `xe`, and insert `xe` once. Every command is bounded and its exit status is retained. If unbind or module removal fails, stop; do not attempt a partial rebind or FLR. If module insertion fails, preserve evidence and request explicit reboot authorization.

## Post-reload qualification

Before any new model-matrix attempt:

1. Require four exact BDF/UUID/device-node mappings and no node holder.
2. Require three passive MemAvailable samples at 0, 60, and 300 seconds, each at least 110,100,480 KiB with no downward drift greater than 262,144 KiB; PSI must remain zero and the original swap layout exact.
3. Require established idle device memory near 43 MiB/card.
4. Run one small isolated copy/compute check on each physical card and require exact `2097152.0` on 4/4.
5. Run the existing peer-access check and require pass.
6. Run one four-rank XCCL all-reduce with the accepted `lo` interface identity and require exact `allreduce ok 4.0` on ranks 0 through 3.
7. Run the already-qualified known-good TP4/EP4/eager/MTP0/configured-512 exact-`OK` generation canary under a fresh output identity and port. It is diagnostic only.
8. Require bounded clean shutdown, managers stable, cards returned to idle, and no new B70/xe fatal event, TTM allocation/eviction failure, OOM, uncorrected PCIe event, timeout, or I/O failure in the recovery window.

Any failure stops before a successor vision packet. A complete pass authorizes only a separately registered attempt with fresh paths and identity, retaining A11's 104-GiB gate and every protected speed row.
