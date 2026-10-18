# Packet77 CPU preparation closeout

Question: what consumes time in packet70's actual wide64 record selection, and
which class has the largest remaining useful-read headroom per half?

Identity: packet70 `1-draft-hc-batch`, wide64 experts, placement 1, target
`iq3-p49-split32-v1`, full BF16 KV, packet49 oracle. One loaded pair, separate
control and attribution arms, lane B. [Source delta](instrumentation.patch),
[selection seal](compat/packet64-record-bundle/selections/1-draft-hc-batch-wide64/screen-seal.json).

Outcome: CPU preparation passes; no GPU/model payload/service ran. Both engine
builds, synthetic token/state repeats, observation reset, full production-shape
mock post-load allocation, real admission, worker imports, 80 Python checks,
report rendering, screen plan and temporary queue plan pass. See
[evidence index](README.md#cpu-evidence). A development-only mock interface mismatch
and an inherited local storage import were caught and fixed before sealing.

Retained mechanism: packet64 event boundaries and observation toggles plus
packet69 head labels; unchanged packet65 numerical objects, exact packet70
selection, shared pinned v4 safety wrapper and packet72 byte formulas. The
24/24 compatibility namespace is explicit and has a binary/source-bound audit;
no shared placement or admission predicate changed.

Uncertainty: current bandwidth, instrumentation overhead, device exactness and
ranking are unmeasured. Neither older attribution nor synthetic fixture timings
answer those questions. Rank costs are sample-based estimates and useful bytes
are not hardware DRAM traffic. Device execution is the coordinator's next step,
not part of this CPU-only task. [Proposed job and report paths](WINDOW.md).

Revisit after the complete current-selection screen returns its paired receipts.
Rank the next mechanism by current measured headroom × occurrences, preserve
past rejected mechanisms, and qualify any change independently. This closes CPU
preparation only; no optimization lever is declared exhausted or successful.
