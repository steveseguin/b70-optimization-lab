# Packet71b CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Repair packet71's pre-rank import failure and cheaply batch the remaining HC
gates, router and route for depth-two lane-B screening. Official lane oracle:
packet49, `iq3-p49-split32-v1`, the same quantized target and BF16 state. CPU-only
preparation on steve-b70s, October 17; no model or GPU execution.

## Outcome

Screen-ready. GNU and Intel each pass 2,728 byte comparisons and agree across
compilers; host/device binaries compile. Eleven wrapper/import tests pass.
Both kernel selections are sealed. All five direct plans and four proposed
lane-B queue plans pass, including the actual worker import closure.

## What worked

The screen-only storage module imports without a chain registration. Both
lineage checks recognize packet71b. Planning performs the worker's real imports
inside the closed launch environment. HC retains its production vector loads
and gate/mix geometry; router retains split4 scratch and reduction; route
retains the selected exp32/rank4 four-pass algorithm with independent row state.

## What failed or remains uncertain

The first compile exposed a duplicate capture guard through the checked mirror;
an explicit include guard fixed it. The first seal plan rejected external
oracle data symlinks in the generic source map; retain those under the existing
oracle validator and audited read-dependency receipt. Frozen packet71 still
reproduces its missing chain-registration failure. Packet71b's full-model
row/state correctness, determinism and speed require the coordinator's screens.
No new CPU model or full-chain qualification was run, and no speed is inferred.

## Evidence and patches

[Build](build-device-receipt.json), [bytes](fixture/m2-receipt.json),
[worker imports](evidence/worker-import-check.json),
[wrapper tests](evidence/wrapper-tests.log), [metadata](evidence/metadata-gate.json),
[queue plans](evidence/lanequeue-plan.jsonl), [source ancestry](packet71-copy.json),
[retention and restoration](RETENTION.md). New kernels are
[production_router.hpp](production_router.hpp),
[production_route.hpp](production_route.hpp), and the edited
[batched_hc.hpp](batched_hc.hpp); dispatch is in [dependent_rows.hpp](dependent_rows.hpp).

## When to revisit

Run the proposed smoke once, followed by matched control/candidate/control
screens after smoke passes. Any failed identity gate blocks a speed conclusion.
The measured packet68c cost leaves little margin; use the screen result to
judge this lever without expanding CPU preparation into a long campaign.
