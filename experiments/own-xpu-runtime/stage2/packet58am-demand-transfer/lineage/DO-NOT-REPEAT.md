# Packet58al boundaries and prior closures

These records belong to this new prep packet. All older packets stay frozen.
Conditional rows below are policy, not fabricated completed experiments.

| Existing arm | Retained outcome and source | Difference required here |
| --- | --- | --- |
| packet125 miss transfer | [Actual result](../../../../notes/2026-10-18-own-runtime-packet125-micro-result.md): tile16 187.0/185.8 µs beats BCS pipeline3 192.2/194.9; no arm met 1.5×. Its README/DNR still say device pending. Real router IDs used **simulated cache masks**. | Actual published sparse misses and resident neighbors on the full 58ah line; include routing, dispatch, BCS contention and later-fill substitution. No lower-threshold rerun of the same micro. |
| packet58aa MTP | [Closeout](../packet58aa-onecard-mtp-recheck/CLOSEOUT.md): no build; smaller 18.216 GB target cache and unsupported favorable projection. | No draft, speculation, verifier or cache shrink. Only causal current-layer demand. |
| packet58ac publication | [Analysis](../packet58ac-cache-publication/ANALYSIS.md): CPU packing 0.053–0.060 ms does not support the needed 0.739 ms saving. | No claim to remove publication overhead; existing revoke/publish fences stay. |
| packet58ae / packet58af census preparation | [58ae note](../../../../notes/2026-10-18-own-runtime-packet58ae.md), [58af note](../../../../notes/2026-10-18-own-runtime-packet58af.md): mixed event service cannot isolate memory stalls; split dependency interval includes arithmetic and dispatch. | Whole-token observed ceiling and separate resident windows; actual BCS intersection must be measured. |
| packet58t resident lookups | [Result](../../../../notes/2026-10-18-own-runtime-packet58t-result.md): 26.092 versus 26.134 warm control, −0.162%. | No 29.3 GB lookup-copy or host paging/settings arm. |
| packet58x cache capacity | [Result](../../../../notes/2026-10-18-own-runtime-packet58x-result.md): 21.55 GB gain already adopted. | Same cache capacity, no temporary stage compute reuse on later tokens, no reserve borrowing. |
| packet58y attribution | [Result](../../../../notes/2026-10-18-own-runtime-packet58y-result.md): instrumentation added about 8 ms/token. The 20.77 ms compute tail is not a transport saving. | Qualify instrumentation overhead; neither whole tail nor cross-schedule subtraction is headroom. |
| packet58ab HC | [Boundaries](../packet58ab-onecard-hcfusion/DO-NOT-REPEAT.md): accepted three-stage HC with exact BF16 intermediates. | Keep adopted HC, capture and reset behavior. |
| packet58ag ports | [Boundaries](../packet58ag-onecard-ports/DO-NOT-REPEAT.md): HC-wide, p109, exact half table and ordered foreground retirement already adopted. | Retain all four dimensions and separate foreground/maintenance ownership. No second credit for their gain. |

Additional no-repeat rules:

- Do not issue compute on BCS or assume a second CCS. A copy queue is not
  another physical copy engine. Direct pinned-host loads remain CCS work.
- Do not use ordinary foreground `copy()` for early demand and then claim
  overlap: it immediately inserts a compute barrier in the parent backend.
- Do not reorder route/probability arrays or combine partition subtotals.
  Write original output slots and use the original ordered reduction.
- Do not infer residence from `prepare()` or generation alone. Pointer
  resolution does not enforce generations; real reader fences are required.
- No stage reuse by position parity, no reuse before its D2D reader finishes,
  and no second host transfer for a planned fill already supplied by a stage.
  Retained/discarded/repeated-demand bytes remain visible in the accounting.
- No growing the 21,552,729,600-byte cache or consuming the 8 GiB host or
  1.5 GB device reserve. Full staging admission is mandatory.
- A synthetic parser check or host-only binary cannot substitute for the
  device binary's **real argument and preparation path** running without a GPU.
- No time limit in a data proof; slow cold valid rows remain valid. In-run
  data checks are stream presence/format and exactness only. Timing numeric
  consistency belongs in the offline analyzer with relative tolerances.
- No v5 result is a public cold-suite headline. Preserve the 128-token scope,
  first view warm-up, fresh-process requirement and separate promotion gate.

## Current disposition

| Row | Status | Reopen condition |
| --- | --- | --- |
| 58al-pending-census | Build release withheld until complete, stable, exact census evidence. See timestamped `evidence/poll.json`; this is not a measured failure. | Apply DECISION.md to actual completed evidence. |

When a real verdict closes an arm, append its measured row and evidence-linked
closeout in the new owning packet. Never append a conditional outcome as if
the device ran, and never edit the frozen predecessor's DNR to do so.
