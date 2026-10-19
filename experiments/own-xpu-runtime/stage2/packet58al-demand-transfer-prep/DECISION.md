# Census verdict to next action

Read `evidence/poll.json` for the latest timestamp, discovered reports and
hashes. This document defines the decision before evidence arrives. A READY
marker, smoke success or partial request is **not** a complete census verdict.

Packet58ai's analyzer uses `upper_bound_ms_per_token`: mean of directly
observed whole-token sums over generated indices 2..100. Each sum includes
the entire original mixed gate/up and down kernel in layers with any miss.
That is a generous bound on removable expert service, including necessary
arithmetic. Its split miss/resident timings and router gap have different
meanings. Never sum the gap with the ceiling or subtract B1 from B0 when
cache demand differs. No extrapolated layer means or packet125 gain credit.

Before acting on a numeric verdict require complete queue/window/native
closure, exact oracle and token coverage, clean graceful teardown, the
declared identity, all 12 prompts × five views, 48 layers/position, no added
token waits, and the analyzer's stability gate. Its B0 overhead must be
within ±2% against **both** warm controls and warm-control drift ≤3%.
A0 is the cold exact warm-up and excluded from warm speed comparisons.

| Packet58ai state / decision | Action for packet58am | DO-NOT-REPEAT disposition |
| --- | --- | --- |
| Valid `brief-transfer-mechanism`, bound **≥1.000 ms/token**, useful resident windows present | Build **only `bcs-demand-retained32x2`**, as specified in PLAN and briefs/build.md. This is conditional CPU preparation, not a predicted gain or device launch. | Record measured identity, bound, sparse counts/window distribution and chosen variant. Do not repeat p125's pipeline sweep. |
| Valid `close-rank-4`, bound **<0.670 ms/token** | No transfer build. Close this rank-4 arm under the measured identity and link the complete evidence. | Append `58al-rank4-below-bound`: value, report hash, identity and threshold; revisit only on a materially different measured miss cost. Do not claim that an older 58ad result conclusively closes every 58ah variant. |
| Valid `between-thresholds-measure-tighter-bound`, **0.670 ≤ bound <1.000** (including exactly 0.670) | No transfer build. Close this build authorization as insufficient; next permissible work is a tighter **current-parent** census with changed overhead/window attribution, not a transport sweep. | Append `58al-rank4-middle`: do not promote a generous ceiling into net saving; reopen only with valid ≥1.000 evidence or another independently qualified mechanism. |
| `measurement-overhead-or-drift-blocks-rank4`, regardless of the ungated threshold label | No build and no numeric closure of rank 4. Preserve all numbers; address measurement validity once in a fresh, separately prepared diagnostic. | Append `58al-census-invalid`: do not overhead-correct by subtraction, choose a favorable control, or use `threshold_decision_before_stability_gate` as admission. |
| ≥1.000 but no useful resident window, all eligible misses already in maintenance, or stage fit/ownership fails | Close **this staging variant** without a build/device job. The large expert-service bound alone supplies no copy overlap. | Append `58al-no-admissible-overlap`, with the actual mechanism/blocker; rank 4 is not globally closed. |
| Failed exactness, fault, incomplete/missing stream, changed hash, wrong identity or malformed report | No build. Preserve evidence and diagnose the specific failure on CPU. Device recovery belongs to the live coordinator, not this prep. | Append `58al-unqualified-census`; no retry loop, false zero or borrowed missing metric. |
| Pending device, smoke-only, partial/live files, no analyzer output by this task's time box | Keep the brief ready but **not released for build**. Stop this bounded prep after commit/push. The next builder rechecks the complete census first. | `58al-pending-census`: do not call pending evidence a negative result or launch on the 2.35 ms proxy. |

Thresholds are the supplied preregistration, not fitted after results. At the
new parent rate, the reciprocal interval is about 31.583 ms; a 0.670 ms
uniform saving would imply about 2.17%, **a sensitivity only**. The exact
matched speed decision must reaggregate prompt/class rates; it does not use
reciprocal-average arithmetic as a new measurement.

## The predecessor/current-parent distinction

Packet58ai's `PLAN.md`, `README.md`, `build-receipt.json`, native argv and
`analyze.py` bind it to **58ad / 30.396**, with HC p60fusion but without all
58ag ports. Packet58ah's actual chain-b argv selects hc-wide,
wide64+halfcache, other-fusion and ordered-foreground. Identical selection
JSON alone is insufficient: those dimensions are separate flags.

A clean ≥1 ms **predecessor** verdict can release this bounded CPU build
brief as the requested follow-up hypothesis. It cannot be quoted as the
31.663 line's measured bound, cannot certify a speedup and cannot replace a
same-parent baseline. The smoke must collect an instrumented, exact 58ah
control with the new dormant hooks. Its 64-token current-parent check is
explicitly screening: require eligible staged misses, observed BCS overlap,
exactness and acceptable instrumentation overhead before v5. It cannot claim
the 2..100 primary bound from only 64 outputs. The subsequent matched,
unprofiled v5 decides speed. If the predecessor
closes below the bar, do not build merely to acquire that confirmation.

If packet58ai is changed to the full composition, require its new hashes,
actual argv and new oracle/quality closure, then identify that result
explicitly. Do not rewrite the older observation. This prep never changes
58ai or its analyzer.

The minimum recorded result packet is: report path/hash; runtime and full
composition; exactness and closure status; B0 ceiling; split miss/resident
services; real miss-count distribution; router-to-expert interval; potential
resident interval; actual overlap if measured (58ai reports zero concurrent
compute by construction); B0 overhead against A1/A2; control drift; cold
first-request rows; and action. Missing values remain null, not zero.
