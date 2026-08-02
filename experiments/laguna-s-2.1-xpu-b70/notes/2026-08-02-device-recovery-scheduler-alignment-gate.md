# Laguna device recovery and scheduler-alignment gate

Date registered: 2026-08-02 America/Toronto

Status: clean reboot authorized by Steve; pre-reboot state recorded; reboot and
post-reboot validation pending.

## Why recovery is required

The q12 mixed-depth diagnostic stalled before model loading. A later observer
also stalled, and the kernel reported repeated GuC execution-queue timeouts and
resets on `0000:47:00.0`. The service was already stuck before the observer,
but the observer immediately preceded the kernel messages, so the evidence does
not assign sole causality to either process. The run and teardown are preserved
in `long-context-mixed-depth-feasibility-20260802.json` and commit
`d69593cd5`.

Steve explicitly authorized device recovery on 2026-08-02. The conservative
action is one clean reboot. Do not precede or follow it with FLR, driver
reload, unbind/rebind, shared-memory deletion, or an automatic reset ladder.

## Pre-reboot identity

- boot ID: `216cdd68-fae6-44c5-bc4a-aff261a0da95`;
- boot time: `2026-08-02 13:40:49` America/Toronto;
- kernel: `7.0.0-28-generic`;
- kernel taint: `512`;
- all four expected BDFs enumerate: `23:00.0`, `27:00.0`, `43:00.0`, and
  `47:00.0`, each with a DRM directory;
- no vLLM, torchrun, pytest, build, or Laguna gate process;
- ports 8000 and 18080 are free; and
- both known Gemma service units are inactive.

No `xpu-smi` observer or Torch XPU import was used in this pre-reboot snapshot.

## Post-reboot host and device gate

1. Require a new boot ID and expected kernel/BDF/render identities. Record
   taint and a bounded kernel-log baseline.
2. Stop any GPU service automatically started by the reboot before importing
   Torch XPU.
3. Require no foreign vLLM/model/probe process and free ports 8000/18080.
4. Run exactly one bounded changing-value allocation/arithmetic/copy/sync probe
   on each physical card, sequentially, using
   `tools/laguna_xpu_device_probe.py` under a single-card
   `ZE_AFFINITY_MASK`. Every log must contain `import-done`, `device-set`,
   `tensor-allocated`, `compute-synchronized`, `verify-ok`, and exactly one
   `PROBE_RESULT=PASS physical_rank=N`.
5. Resolve the active CCL interface from the host rather than reusing obsolete
   `eno1`. Run exactly one corrected four-rank
   `run_xccl_collective_probe.sh` attempt in a fresh artifact root. Success is
   only `PROBE_RESULT=PASS clean_teardowns=4/4`, with every rank log reaching
   verified reduction and teardown.
6. Any device error, timeout, missing stage, mismatch, collective failure, or
   dirty teardown stops the campaign. Preserve evidence and do not retry.

## First post-recovery model gate

Only after the complete host gate passes, run the preregistered scheduler
alignment control A followed by candidate B from
`2026-08-02-long-scheduler-budget-alignment-preregistration.md`. This remains a
configuration-only comparison on vLLM exact-prefill source `4ddb91528`; do not
mix the later wide-prefill fusion into it.

The default-off wide-prefill fusion component and endpoint gates remain queued
behind the scheduler result. A reboot or successful health probe is not itself
performance or correctness evidence for either treatment.
