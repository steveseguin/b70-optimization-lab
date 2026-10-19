# Packet58ai: one-card miss census, prepared without queueing

The new packet copies packet58ad and keeps its exact model, arithmetic,
tile16, HC fusion, maximum cache and overlap settings. It separates routed
cache misses from later cache fills. The current record stays 30.396 tok/s.

The first milestone retains the record packet and private native source
closure. It adds ordinary event measurement of the unchanged mixed kernels
and a separate resident/miss partition diagnostic. The latter changes
scheduling, so its cost is reported separately and controls measure overhead.
No model data, GPU, service, live queue or host setting was touched.

Preparation checks, final readiness and any remaining blockers will be
recorded below before the final marker is written. Device output equality,
acceptance identity and actual costs remain pending device execution.
