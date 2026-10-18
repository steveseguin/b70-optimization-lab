# Current-record lever table: awaiting packet77 events

Packet70's selected view is `1-draft-hc-batch` + `experts=wide64`, placement 1.
No current per-class values exist from this CPU-only preparation. Packet64 and
packet69 attribution predate this selected record and cannot supply its rates.

| Next question | Packet77 measurement | Decision after the screen |
| --- | --- | --- |
| Routed gate/up and down after wide64 | Pending, both ranks | Rank their remaining time above the 555 GB/s useful-read reference × occurrences. Do not reuse packet64's 144/160 GB/s as current. |
| Attention and FFN HC gates | Pending, both ranks | Compare current measured headroom × occurrences; a new mechanism still needs its own exactness/performance gate. |
| GDN recurrence | Pending, both ranks | Count BF16 state reads and per-half occurrences; low effective bandwidth alone does not establish a memory bottleneck. |
| Route | Pending, both ranks | Rank time cost alongside bandwidth headroom; it is a small, latency-sensitive multi-stage call. |
| Other dense/attention/shared classes | Pending, both ranks | Recalculate every class using its actual tensor representation; no old cost is silently carried forward. |
| Rank-1 target head, final norm/merge, argmax | Pending | Use separately measured outside-layer events, once per half. |
| Rank-1 residual | Pending | Retain signed host-command residual; no invented bytes or GB/s and no GPU-idle claim. |

The generator replaces this uncertainty with a ranked table in the run's
`attribution-summary.md`. It ranks each rank separately by
`(call µs − read bytes / 555000) × occurrences`. Negative headroom remains
visible. Half estimates, complete measured half spans, and instrumentation
overhead are retained separately. This does not forecast an end-to-end speed.

Prior mechanisms stay closed according to their original lane records. This
screen refreshes attribution; it does not reopen a failed kernel geometry or
promote a candidate. See [report method and caveats](README.md#reports-and-next-levers).
