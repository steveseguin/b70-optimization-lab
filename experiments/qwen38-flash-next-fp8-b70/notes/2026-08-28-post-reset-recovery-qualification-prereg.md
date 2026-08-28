# Flash-Next post-reset recovery qualification preregistration

Date: 2026-08-28

## Purpose and boundary

Requalify the four B70s after the MTP4 active-2K teardown window recorded one
compute- and one copy-class reset on every card. Device rediscovery and low
idle memory are not sufficient. This recovery program grants no model-matrix,
speed, quality, or deployment credit and cannot change any captured result.
It only decides whether a later separately preregistered GPU arm may start.

No driver reload, PCI reset, reboot, model launch, or serving request is
authorized by Stage A. Stop immediately on any missing device, per-card smoke
failure, collective failure, timeout, new B70 reset/fatal event, or residual
workload ownership.

## Frozen Stage-A identity

- repository `main` at or after the MTP4/2K closeout commit `fecff8891`;
- `/home/steve/.venvs/vllm-xpu/bin/python`, Torch `2.11.0+xpu`;
- `scripts/check-qwen36-xpu-xccl-health.sh` SHA-256
  `b15dd4c248d8c4d7035c2d180b9ecc5354b1b20bdabb0c47c540b5003a1cfb78`;
- `tools/xccl_probe.py` SHA-256
  `6ecd340651a6780fdbe0bd57d346540efe168bf2e3175d54e10dd8660ed5b30a`;
- physical devices and XCCL devices exactly `0,1,2,3`, four ranks, 120-second
  collective bound;
- output root
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/post-reset-recovery-qualification-20260828-stage-a`.

## Ordered Stage-A gate

1. Require a clean `main`, free host/GPU locks, no serving/benchmark process,
   no relevant listener, four expected B70 discovery records, and low idle
   memory. Capture a kernel-journal cutoff before active checks.
2. Run exactly one small Torch allocation/add/reduction/synchronization check
   on each physical card. Require `device_count 1` and `ok 2097152.0` for all
   four checks.
3. Run exactly one four-rank XCCL all-reduce with the accepted OFI/P2P settings.
   Require barrier completion and `rank 0` through `rank 3` each reporting
   `allreduce ok 4.0`.
4. Capture discovery, stats, ownership, and the kernel journal through the end
   of the check. Require no new B70 reset/fatal event and no residual check
   process.
5. Hash every durable Stage-A artifact. A Stage-A pass authorizes only the
   separately preregistered known-good generation canary; it does not authorize
   an unbounded matrix launch.

## Stage B and resumption rule

Stage B must use a known-good Flash-Next TP4/EP4/eager/MTP0 configured-512
identity, a fresh lifecycle controller, one cache-zero deterministic generation
canary, bounded clean shutdown, and a clean journal window. Only a complete
Stage-A plus Stage-B pass restores permission for the next matrix arm. A
failure remains evidence and requires assessment; it does not trigger an
automatic reload or reboot.
