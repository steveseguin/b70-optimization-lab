# Qwen3.8 Flash-Next TP4 CPU/L3 affinity A1 preregistration

Date: 2026-08-31
Status: refrozen as an independent component; statically validated

## Lifecycle-policy supersession

The original same-boot chain admission rule is deleted for this affinity
component by explicit user direction. Prior GPU experiments, a full-load marker,
the event-chain A1 boot ID, and HC-SiLU A1/A2 state neither authorize nor block
this arm. The boot ID is captured as evidence only. This supersession changes
only lifecycle admission and failure cleanup; the frozen treatment, four-arm
order, runtime/toolchain identities, topology, correctness, timing thresholds,
locks, no-clobber output policy, and endpoint interpretation remain unchanged.

## Question

A28 found that ranks 2 and 3 were the latest host submitters in 270 of 291
aligned target-token collectives, with cross-rank submission skew growing to
16.362 ms. Real-weight partition/device tests did not reproduce a corresponding
static arithmetic imbalance. The host has two eight-core/16-thread L3 domains,
and the four B70s form two PCIe host-bridge pairs. Does keeping each rank and
its oneCCL worker on a disjoint four-core/eight-thread set reduce the
97-collective critical cycle without changing collective code or results?

This is a component screen. It does not load the model and cannot produce a
tok/s claim. The accepted oneCCL, SYCL runtime, kernel bundle, XCCL settings,
tensor shape, and protocol are identical in control and candidate arms. Rank
process plus oneCCL-worker CPU/L3 affinity is the sole coherent treatment.

## Frozen design

Four fresh `torchrun` process groups run in `control / pinned / pinned /
control` order. Control ranks inherit CPUs 0-31. Before importing Torch, pinned
ranks select these disjoint sets so later helper threads inherit the rank
treatment:

- rank 0: `0-3,16-19`;
- rank 1: `4-7,20-23`;
- rank 2: `8-11,24-27`;
- rank 3: `12-15,28-31`.

oneCCL does not inherit its worker placement: it independently pins one worker
per local rank. Both arms therefore set that mechanism explicitly. Control
uses `31,30,29,28`, exactly preserving oneCCL's current automatically selected
worker CPU for local ranks 0-3. Candidate uses `19,23,27,31`, placing each
worker inside its corresponding rank set. After process-group initialization,
every rank records `/proc/self/task/*/{comm,status}`. Every candidate thread
must remain inside its rank set, and every arm must show a singleton thread on
the expected worker CPU. The host has one NUMA node, and both arms set the same
oneCCL mechanism, so the only between-arm change is CPU/L3 placement.

Each arm performs 8 warmups and 60 measured cycles. Every cycle contains 97
ordinary clone-plus-`dist.all_reduce` operations over BF16 `[1,2560]`, matching
the A28 target-token collective count and shape. Inputs change across measured
cycles and both local outputs and an untimed protocol receipt must equal an
independently computed, exactly representable four-rank SUM. Every rank must
show `Rt64_128_PCIE`, and outputs must hash-match across ranks and arms. The
synchronization used to align the protocol receipt occurs before the Kineto
scope, so the receipt trace contains only the target reduction and completion
wait.

Each matched control/pinned pair must improve slowest-rank median cycle time by
at least 5% and must not regress p90. Both pairs must pass before affinity may
receive a separately preregistered endpoint arm. Any miss closes the idea
without loading the checkpoint.

## Lifecycle boundary

This runner pins exact runtime hashes, CPU/L3 layout, GPU BDF order, evidence
mount, output path, and authorization token. It holds the host, four-GPU,
full-load-lifecycle, and component-state locks strictly for serialization; it
does not inspect the full-load marker or require any prior component state.
Every arm has a timeout and exact-path cleanup, and a runtime/correctness
failure stops before the next arm.

One idempotent EXIT finalizer is armed before initial ordered four-BDF discovery
and the existing four-B70 arithmetic/free-memory preflight. Every later exit,
including a preflight, arm, comparison, signal, or unexpected shell failure,
preserves its incoming nonzero status while the finalizer attempts every
cleanup/postflight step without early exit: exact-process cleanup, exact ordered
four-BDF rediscovery, the same four-card arithmetic/free-memory helper, host
memory and swap recovery gates, the bounded kernel-journal window, and the
evidence manifest. A finalizer failure converts an otherwise successful exit to
nonzero. The runner neither reads nor writes attempted/completed component boot
state; the retained component-state lock is serialization only. The packet
never authorizes or requires a reboot.

Structured preregistration:
[`20260831-tp4-count2560-cpu-affinity-a1-prereg.json`](../data/20260831-tp4-count2560-cpu-affinity-a1-prereg.json).
