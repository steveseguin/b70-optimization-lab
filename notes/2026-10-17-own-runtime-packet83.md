# Packet83: cut the draft head's bytes

The CPU preparation is complete and all four screen views are sealed. The Q4
choice halves the head's useful weight reads and adds139.45MiB on rank1. The
smaller-prefix choices use80,128 and74,752 rows, selected solely from packet56's
fixed independent text. The target's complete head, arithmetic, verifier and
BF16 cache stay unchanged; the draft stays on rank1.

The [census](../experiments/own-xpu-runtime/stage2/packet83-draft-bytes/CENSUS.md)
uses76 sampled packet77 hits. Draft wall time averages1.746ms; the head accounts
for0.521ms. Halving head bytes projects0.260ms off a16.1ms hit cycle, about1.62%,
before acceptance changes. Smaller-prefix projections are0.40% and0.59%.
These are planning numbers, not measured improvements. The residual0.202ms
cannot be called fixed launch overhead. The independent-text coverage ratios
illustrate acceptance0.7831 and0.7794 from0.787, but actual acceptance is unknown;
text coverage says nothing about Q4's numerical changes.

The lower-bit head is derived from the existing authenticated Unsloth Q6_K GGUF,
not original BF16 weights. Both compilers converted all91,392 real rows and
calculated every head output twice in fresh CPU processes. Q4 bytes and outputs
match across all four runs; every output matches an independent reference.
Miniature native-controller runs keep all target tokens/layer bytes equal to
packet75 and repeat each draft exactly. All eight full-size startup mocks pass
through the real allocation and post-load command setup. Rank1 fits under the
unchanged30GiB arena limit with about799MB to spare. Eighty shared-wrapper tests
and nine packet tests pass.

The [handoff](../experiments/own-xpu-runtime/stage2/packet83-draft-bytes/WINDOW.md)
has a full grid for each lane, so the coordinator can use whichever is free.
Only one first grid runs. The other lane confirms its exact improving winner
between two controls. Every screen reports acceptance checked against hit/guess
counts. All four proposed queue files were planned on temporary copies. No GPU,
service, live queue, host setting, sudo command or reboot ran during this task.
Real target-oracle results, GPU determinism, acceptance and speed remain pending.

The opening pull refused existing uncommitted work; fetch showed local main
already matched origin. Those edits were preserved. Preregistration and census
were committed and pushed separately before implementation was sealed. Sources
come from copied packet75 files; all existing packets, shared wrappers and ops
files were left unchanged. The general50GiB storage check refused with about19GiB
free; the task's explicit below1GB build budget was recorded and observed.
The completed local build uses about160MB, compiler peak RSS about715MiB.

[Complete evidence and limitations](../experiments/own-xpu-runtime/stage2/packet83-draft-bytes/CPU-PREPARATION-CLOSEOUT.md).

## Device result and closeout (coordinator, 2026-10-17 23:37 – 2026-10-18 00:02 UTC, lane B grid)

All exact. Production mean 54.198 tok/s (54.051 / 54.345):

| View | tok/s | vs production | Acceptance |
|---|---:|---:|---:|
| `q4-g32` | 53.752 | −0.82% | 0.7795 (from 0.7874) |
| `prefix990` | 53.975 | −0.41% | 0.7874 |
| `prefix985` | 54.056 | −0.26% | 0.7795 |

**Closed: no promotion.** The Q4 draft head costs acceptance (a lossy draft lowers agreement) and does not save enough. Smaller prefixes save too little (the head prefix is already about 0.5 ms at the bandwidth limit) and lose acceptance at 98.5%. The lane-A confirmation was not run. DO-NOT-REPEAT: lower-bit or smaller draft heads at the current acceptance trade.
