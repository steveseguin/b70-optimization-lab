# Packet80 combined record bundle

CPU preparation in progress. Copied from frozen packet75, with packet76 rank1
ordered retirement, packet78 route/norm choices and packet79 rank0 draft prefix.
The GNU host and Intel SYCL binaries compile. No GPU, service or chain runs in
preparation. CPU fixture, full-shape, placement and consumer gates must all pass
before the preparation helper can mark this bundle ready.

Independent choices: host production/ordered, route production/fast, norm
production/fused, HC production/hc-wide. Experts stay wide64; dense stays
production. Each of the 16 compositions supports four placements subject to its
real allocation census: 1 (24/24), 1-split23, 0 (24/24), 0-split23. Ordered
retirement remains rank1-only when the draft moves. Rank0 allocates only the
91,392-row draft prefix. Target arithmetic iq3-p49-split32-v1 and packet49's
oracle remain unchanged. No compressed KV or target weight change.

Packet75's chain retains 90-second gaps, lease release before CPU reporting,
resume-capable submission and fast reseal. The pinned shared screen/v4-lanes
lifecycle is referenced unchanged; a local audited placement policy extends
admission using the complete memory census, as in packet79.

The preparation helper in ../../ops/packet80-orchestration reads each packet's
own compare/best logic. Only exact 13/13 winners that improve both lanes are
selected. Missing evidence leaves that packet's choices at production. No
performance claim is made for a composition before its fresh device chain.
