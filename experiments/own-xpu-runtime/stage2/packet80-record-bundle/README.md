# Packet80 combined record bundle

CPU arithmetic, allocation and protocol gates passed. Copied from frozen
packet75, with packet76 rank1 ordered retirement, packet78 route/norm choices
and packet79 rank0 draft prefix. GNU host and Intel SYCL builds pass. All16
compositions pass2096 numerical cases twice under each compiler. All128
full-shape post-load mocks pass, and all64 configurations match packet75 target
and draft bytes in two fresh native miniature runs. All 128 shared-wrapper
screen plans and 704 chain-window plans passed. The final test run passed
200 chain tests, 24 subtests and 9 orchestration tests. No GPU, service or chain
was launched by this preparation. See the [CPU closeout](CPU-PREPARATION-CLOSEOUT.md)
and [ready receipt](../../ops/packet80-orchestration/ready.json).

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

Current ready selection: ordered host cleanup, fast route, fused norm, hc-wide,
rank1 at24/24, wide64 experts and production dense. Packet79's rank0 candidates
were exact but slower in lane A. Rerun the helper if screening evidence changes;
it never launches the command it records.
