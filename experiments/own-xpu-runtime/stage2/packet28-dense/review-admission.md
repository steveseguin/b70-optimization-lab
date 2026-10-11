# Independent admission and build review

Reviewed `summary.py`, `window.py`, `build.py`, packet26 `dispatch.hpp` and `performance.cpp`, packet28 `registry.hpp`/`class-registry.json`, and the recorded packet26 class times. CPU-only source review; no native/device executable run.

## Findings sent to the author

1. Initial summary trusted timing-row `exact=true` and window completion without rechecking the recorded timing/exactness/native receipt hashes. It did not cross-check candidate admission against `exactness.jsonl`. A stale or modified timing file could therefore change selection. Require bound receipts and a successful matching exactness entry before considering a candidate.
2. Initial summary accepted any candidate string observed in timing rows. An unknown candidate could become a `gemv` value. Require the registered per-format vocabulary and reject unknown class/workload/candidate identities.
3. Initial grouping checked unique event indices and 200 repetitions, but did not require the expected number of constituent GPU events or contiguous event indices per invocation. A missing event from a split projection would reduce measured time. Require per-invocation event coverage and consistency with the implementation's declared pass count.
4. Build sealing initially omitted `class-registry.json` and the externally read class-timing receipt. Both feed admission and should be hash-bound alongside source code.

Re-review of the final sources: **all four findings resolved**. `write_summary` verifies the build binding and each owner's native/exactness/timing hashes; checks registered class/workload/type-specific candidate identities; requires all five dense or six routed fixture modes with successful R5 and candidate checks; and requires `new_current_bytes_equal=true` for a new candidate. It checks failures before indexing mode fields, so partial timing failure records cannot escape exclusion. Timing groups require the declared 1/2 constituent events with contiguous indices; fewer than 200 repetitions cannot be admitted. Build sealing now binds the registry, model tensor census, and external class-time receipt.

These are source-review findings, not device results. Device execution remains pending.

## Correct mechanisms observed

- Class candidates are intersected across both owners and every shape/format workload belonging to that class. A candidate missing from either owner cannot win through the initial intersection.
- Selection requires each candidate median to be below 0.9 times its matched R5 median for both owners and every workload. A median across owners cannot hide one losing owner.
- Each R5 workload must reproduce the recorded logical-group cost within 15%; mismatch leaves R5 selected and the table explicitly labels the mismatch.
- Recorded timing is a sum of individual GPU event execution durations. `device_ms/groups` therefore gives the logical-invocation baseline, and multiplying group savings by `groups/tokens` is correct. Using `launches/tokens` here would double-count two-event split projections. Launch counts are retained separately.
- Mixed-format class savings use the smallest matched saving across workloads/owners. This conservative value avoids inventing format frequencies.
- The output uses packet26 schema `packet26.dispatch.v1` and the `gemv` section with class keys and string implementation values. New strings still require an integration adapter; unchanged packet26 cannot execute them merely by editing JSON.
- The window checks two distinct systemd units and process IDs, does not restart owners, and compares exactness receipt hashes between owners. G2 requires a matching K0 boot/card/binary/environment/build identity.
- Dependency preflight occurs before latch inspection/creation. Failure evidence is persisted before requesting cooperative teardown; no forced kill is introduced.
- Deadlines are limits, not expected-duration claims. G2 minimum watchdog is four times 400 s expected work plus two 17 s JIT allowances, or 1,736 s. K0 is at least 300 s. Submission budget 10 ms exceeds four times the cited ~2.2 ms logits maximum.
- Build compile and link commands both carry no-fast-math/no-contraction flags; device commands additionally carry IEEE-denormal and precise divide/sqrt flags. Device source mirrors wrap submissions with the capture-size assertion and require by-value device lambda capture.

## Final G2 source review

`g2.cpp` was subsequently reviewed against packet26 `performance.cpp` and `arithmetic.hpp`.

- Current dispatch is reused directly: the harness calls packet26 `arithmetic::r5_variant`, then linked `integrated::dense` or `integrated::experts`. Their native definitions dispatch to packet10 expanded GEMV, packet6 SG32, packet8 constant/split4, and packet9 routed gate/up/down exactly as the packet26 runtime does. Current kernel names identify these paths in receipts.
- The device gate uses production row/column shapes and 17-row repeating real-format fixture bytes. Its five dense modes cover finite, signed-zero, tiny, exceptional, and large finite input cases; routed fixtures add a sixth mode for invalid/empty/partial routes. Current versus host permits only NaN-category equivalence. New versus current requires byte equality on the same card. Successful candidates must pass every mode before timing.
- Exactness records carry output hashes. The window requires the entire exactness JSONL hash to agree across its two fresh owners, so both output hashes and exclusions repeat. Owners share recorded card, boot, binary, environment, and build identities. Summary checks each receipt against those recorded hashes.
- Timing creates/uploads its fixture once, before the repetition loop. Inside each of 200 repetitions there are kernel submissions, a completion wait, GPU-event timestamp reads, event-record writes, and retirement only. There is no upload, poison, output download, or device copy per timed launch. Multiple constituent event durations are summed per invocation before median/p90 calculation.
- Candidate failures are recorded and excluded, while other candidates continue. Baseline failure excludes that workload. Partial timing records cannot admit a candidate. No failure is converted into a winning row.
- The final SIGTERM/SIGINT handlers only set a `sig_atomic_t` flag. Launch-loop/completion checks raise through the outer failure path, which writes evidence before shutdown and retains the process if work remains in flight. K0 checks the stop flag after bundle construction, with no kernel launched. This fixes the initial default-SIGTERM termination hazard found by the author.

No remaining critical admission issue found in this source review. Native behavior, same-card bit identity, baseline representativeness, and speed remain pending K0/G2. One descriptive distinction was sent to the author: the window's 10 ms submission-budget field is not the native wait timeout; `Runner::finish` allows 300 s for completion/drain. Both exceed four times the cited measured maximum, but docs/receipts should state their different purposes rather than call 10 ms an enforced timeout.
