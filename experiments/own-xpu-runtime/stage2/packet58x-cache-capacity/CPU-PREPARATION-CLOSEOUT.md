# Packet58x larger-cache CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can measured one-card memory headroom fund at least 2 GB more immutable expert
cache and a projected gain of at least 2%, without changing outputs? October
18, 2026, CPU-only preparation on steve-b70s for one B70, Unsloth IQ3 weights,
tile16, `iq3-p49-split32-v1`, target-only, 4K BF16 KV, 12 × 64 smoke and
12 × 128 per bracket view. This is a private copy of frozen packet58v.

## Outcome

Prepared for the smoke, then the five-view bracket; neither is queued.
Admission allows 21,552,729,600 cache bytes, 3,552,729,600 above control.
The final receipt-aligned replay projects **26.821731 tok/s (+2.2614%)**,
conditional on the independent miss ratio and 25 GB/s copy-service proxy.
The earlier admission commit used a uniform mean fill cost (+2.2023%);
the final analysis charges each prompt's own 99-interval fill payload and
recomputes the class-balanced statistic. Neither is a device measurement.

CPU byte/protocol, maximum-shape, parser, entry, memory, drain and policy
checks pass. Both GNU host and oneAPI device binaries build; no device binary
ran. The maximum-shape mock has **27,841,642,228 device bytes** and proves
the same allocation descriptors survive ten switches per check (five per
maintenance mode). Mock allocation totals are not physical device occupancy.

## What worked

- One allocation, bounded capacity switching and empty residency at each view.
  The capacity byte test executes 15,672 checks and 402 refusal checks in each
  of two fresh CPU processes, including fills above the control extent.
- The copied async protocol retains its delayed-copy and stale-pointer checks;
  K1 checks the unchanged quantized mixed-source outputs.
- Two native parser paths and eight negative cases pass. Six real queue/window
  probes reach intercepted native execution with current host admission,
  passive topology, the actual lanequeue-derived service names, closed launch
  environment, recorded library path and unchanged resource limits.
- All **96** Python policy tests pass. The drain scanner finds one fixed path
  and no unfixed paths; the one-card teardown adapter's local regressions pass.
- Both proposals pass lanequeue planning in temporary directories. The build
  occupies about **80.6 MB**. Maximum observed compiler child RSS is below
  **0.73 GB**; maximum-shape mock RSS is about **30 MB**. No CPU job approached
  the 4 GB resident-memory ceiling.

## What failed or remains uncertain

The initial copied tests exposed legacy admission assumptions and a missing
not-yet-generated postload fixture; their log is retained. Historical sensor
regressions now explicitly use their original budget, while new tests check
the measured bound's exact admission and live-stop boundaries.

Static review caught a direct-launch capacity setting that would otherwise
have been ignored and a missing live occupancy sensor. Both were fixed before
the final build. The literal sweep also found the old native allocator bound;
both allocator and plan now use the admitted maximum. Native parser receipts
now report the actual view count instead of the inherited hardcoded five.

Packet58v's completed bracket is exact and its overlap rates are higher, but
control drift is 14.73%, above its registered 3% maximum. Serial remains the
default. The new packet can still select overlap explicitly with a matching
smoke. Replay routes have different topology and publication timing; no native
hit-rate improvement, device memory fit, quality pass or speedup is claimed.
Actual smoke, repeated/fresh-load quality and speed qualification remain open.

## Evidence and patches

- [Admission and source pins](admission.json), [explanation](ADMISSION.md),
  [maintenance decision](maintenance-decision.json).
- [Copy manifest](copy-manifest.json), [capacity overlay](capacity_source.py),
  [native cache](native/cache_table.hpp), [live occupancy sensor](device_memory.py).
- [Build and gate seal](build-receipt.json), [protocol checks](evidence/protocol-gates.json),
  [K1 bytes](evidence/k1-async-cpu.json), [full shape](evidence/fullshape-submit-cpu.json),
  [native parser](evidence/startup-cpu.json), [real entry](evidence/argument-gate.json),
  [memory budget](evidence/memory-budget.json), [policy tests](evidence/python-cpu-gates.json).
- [Temporary queue plans](evidence/queue-plans.json), [reproduction](README.md).

Generated binaries and objects are ignored. Rebuild through the shared compiler
turn from the frozen, hash-checked parent objects; the build receipt records
all commands and parent relink checks. No source, unique evidence, parent
artifact or unrelated work was removed.

## When to revisit

The coordinator may run the exact proposed smoke after checking the final
readiness marker and seal. Only an exact, cleanly drained smoke enables the
larger bracket. A measured win still needs its own fresh-process quality and
record qualification. Revisit capacity only with a new lifetime census and
admission calculation; keep the 1.5 GB device and 8 GiB host reserves.
