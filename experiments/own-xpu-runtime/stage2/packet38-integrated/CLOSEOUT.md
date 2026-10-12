# Packet38 preparation closeout

<!-- experiment-closeout -->

Question: can the official draft, prepared dispatch, model-shape kernel
candidates, native controller and persistent suite runner coexist without
changing any target output?

Identity: packet36 draft plus packet37 prepared runtime on the packet32 base,
with packet30 candidates and arithmetic iq3-p17-detmath-v2. The final exact
source closure and binary hashes are in build-receipt.json.

Outcome: CPU qualification is being completed. No device ran; no speed claim.
Coordinator windows and device qualification are separate outstanding work.

Useful mechanisms: captured draft commands share stable owner allocations;
request reset zeroes state in place; rank1 owns target token decisions; native
request control uses bounded process-shared futex waits; suite requests reuse
owners while clearing all mutable state.

Failures and fixes retained: missing draft functor fields in prepared argument
serialization; reset uploads contaminating the next request's counters; queued
native work executing after an already-latched abort; p30 attention leaving
inactive score scratch unchanged. Each has an explicit regression gate or full
fixture proof. GCC13 ThreadSanitizer could not start on this host; LLVM22's CPU
ThreadSanitizer completed without changing host settings.

Evidence: CPU-RESULTS.md, cpu-tests.json, suite-gate-results.json,
native-mini-cpu.json, the independent review records, and evidence/. Scratch
retention and restoration are documented in scratch-cleanup.json and ARTIFACTS.md.

Revisit conditions: any arithmetic, owner-lifetime, protocol, reset, input
identity, compiler or dispatch change requires its corresponding gates again.
Device K2 must decide dispatch; no CPU timing substitutes for it. The complete
twelve-prompt speed window waits for all suite oracles and coordinator access.
