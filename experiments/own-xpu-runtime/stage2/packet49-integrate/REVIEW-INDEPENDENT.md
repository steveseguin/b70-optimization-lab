# Independent packet49 source and admission review

Reviewed on October 17, 2026. This review used source, metadata and mocked CPU
unit tests only. It did not launch a compiler, model process, device binary,
health probe or service, and did not read model payloads. The oracle's running
sources and every sealed predecessor remained unchanged.

## Runtime scope

The pinned comparison is packet45 SPEED6 commit `34c62b433`, rather than the
later packet45 working tree. Against that commit, `main.cpp` only adds the
production target QSA implementation12 override. `rank.hpp` and `mtp.hpp` are
byte-identical. `strict_snapshot.hpp` only changes the QSA scratch write extent.
The 23/25 split, draft placement, rollback policy and arena policy are retained.

The bridge issues admit, fixed32 tiles and combine in dependency order. Its
scalar host reference and independent full-model scalar oracle express the
same fixed32 padded reduction, partial maximum correction and final adjacent
tree. BF16 rounding precedes the unchanged sigmoid gate and final BF16 output.
The owner checks extents, lifetime, memory class and scratch/output aliasing.
For capacity4096/budget2048 the maximum65 partials fit the fixed arrays.

The full engine still submits verification attention as sequential M=1 rows.
Genuine M=2 bridge coverage comes from its separate integrated fixture. No
full-engine batching benefit is claimed. Draft attention retains its SPEED6
arithmetic; KD regenerates its CPU draft reference from new target streams
using the selected dispatch before testing two fresh device owners.

No packet48 kernel is enabled. The reconciliation distinguishes ordinary IQ2_S
gate/up and IQ4_NL down from dense control-wrapper differences, and does not
claim a single proven timing cause. Packet48b's matched production device
windows remain required before any per-class integration decision. Its
microbenchmark results cannot establish model speed.

## Orchestration and evidence

The queue separates K0/K1a/K1b/K2/W0p from the oracle-dependent model phase.
K1 records the actual integrated split32 bridge and requires fresh owner PIDs.
The model sequence includes WS128x before token-only WS128. The actual suite
comparison first validates the complete oracle, then compares all emitted
tokens and exactly the requested retained steps. The strict oracle checker
therefore does not incorrectly demand late retained steps from a token-only
runtime output. W2m uses its registered64-token prefix.

The CPU/build seal explicitly records pending full-model/device qualification.
Completing the oracle is separately bound and need not invalidate early-window
receipts. Build sources, binaries, compile/link flags, plan/snapshot proofs,
Python admission sources and oracle build inputs are checked. The queue checks
exit status and successful qualifying receipts, maintains the inter-window gap,
uses a durable user-unit admission and specific fault signatures, and never
retries a failed window.

The following issues were sent to the author immediately:

1. The original documented output was beside `build`, while window/storage
   admission requires a descendant of the external build tree. The queue and
   WINDOW now use `.../packet49-integrate/build/device-cards01-a`; a regression
   test covers the common boundary.
2. The original seal did not recheck the Python gate's source hashes. It now
   requires matching `sources_sha256`, a positive test count and zero errors
   and failures.
3. Direct model-window invocation also needs complete-oracle admission, so the
   required wait cannot be bypassed by omitting the queue. The author was asked
   to enforce completion and authoritative oracle paths before any device work.
4. `build.py seal` still pointed at historical seal45 machinery at review time.
   The author was asked to route it to packet49 or refuse it with an explicit
   current command.
5. The oracle README used `taskset -c4-15,20-31`, rejected by this host. The
   correct spelling is `taskset -c 4-15,20-31`.

Items3–5 were still being addressed when this review record was first written;
final disposition belongs below, before handoff.

## Validation and limits

The following command passed58 CPU metadata/mocked tests during review:

```bash
cd experiments/own-xpu-runtime/stage2/packet49-integrate
nice -n 19 taskset -c 4-15,20-31 python3 -B -m unittest -q \
  test_p49_integration test_queue_runner test_suite_metrics \
  test_suite_export_retention test_draft_window_cleanup
```

An earlier broader invocation also included inherited `test_suite_long`; it
ran91 tests and produced175 subcase errors. That file imports historical
context-window cases for unadmitted capacities/topologies and old arithmetic;
they are not a packet49 qualification matrix. The scoped passing command
above does not conceal that failure or claim all copied historical tests pass.

No device or full-model correctness verdict is made here. The new oracle must
finish, every dependent window must pass, deterministic fresh-process evidence
must remain valid, and measured model speed must come from the coordinator.
The128-token suite matches SPEED6's historical comparison scope and is not the
separate512-token publication gate. One-card integration is not covered.
