# 104: measure unchanged-ledger write suppression

The103 ten-fixture qualification passed exact outputs, but late delivery drift
coincided with unrelated repository activity. The cause remains unknown. The
synthetic client profile measured17.23ms per ledger save; this motivates one
bounded comparison, not a predicted speed gain or a new default.

104 preserves640×384,25 frames, original8+3 steps, native BF16, encoder window64,
W2/B1/shared pool,23/25 placement and the decoder replica on card2. All ten
original scenes and seeds run in the same order for both timing blocks.
Twenty native executions establish repeat pairs; fourteen candidate requests
emit ten clips. Each fourteen-request timing block has four unscored fills and
ten scored clips. Together with nine setup requests this is71 requests and64
raw captures, with a fresh5GiB allowance above50GiB reserve.

All setup, native, candidate and control requests use the original always-save
policy. Only the second timing block omits a ledger rewrite when both storage
fields are unchanged. Every source/process/fault/free-space check still runs.
All changed state and request attempts, IDs, completions and failures retain
their explicit durable saves; event-log flush/fsync remains unchanged. A
source-bound per-request policy receipt records checkpoint, write and skip
counts before durable completion. A fast block with no skipped writes is valid
evidence of no opportunity, not an implementation success claim.

The control block must pass exact four-tensor verification before its durable
barrier permits the second block. Both blocks use the existing timing authority;
there is no extension of the consumed103 plan. The final proof reconstructs
the native, candidate and control evidence. Verification actions have a bounded
300-second response allowance for these additional CPU scans, with no retry;
other phase actions retain180seconds.

During both timed blocks, suspend unrelated Git operations, builds, CPU tests
and agent file writes. Retain the same passive FD observer. Compare nine
server-success intervals per block and their actual checkpoint counts. Fixed
control-first order and repeated qualification inputs limit this to a short
screen; no public record, cold-input or endurance claim follows.

The author runtime sources are in
[recovery/20261007-resolution-runtime](../recovery/20261007-resolution-runtime/README.md).
The [fixed plan](../recovery/20261007-client-compare-104/README.md) remains unchanged.
103 remains the reviewed predecessor and99b the immutable constructor source.
The application is reloaded only after a complete sealed successor is ready;
success retains it. Faults halt new requests. No host, driver, power, RAM, swap
or page-cache setting changes are part of this experiment.

Status: implementation and independent review complete. All fifteen CPU suites
passed; [validation](../data/resume-20261007/resolution104-cpu-validation.json).
The71 request names and64 capture indices were checked against retained evidence
and reserved without collisions. The104 source packet is sealed, manifest
`49892a00ece1cf4a7d84ce5d03e6a9c2290ffc3af9b2822ba4866e72cfa2e93a`.
A check-only attempt before cleanup correctly refused insufficient storage;
no application was started by that check. After verified duplicate retirement,
fresh5GiB+50GiB admission and the source-only launcher check passed.
The campaign completed successfully at18:54:45UTC on the same boot; the application remains idle. Server PID3311653,
start ticks27195355; unit `ltx104-client-server-20261007`. Campaign unit
`ltx104-client-campaign-20261007` admitted its first setup request.
Client contract SHA256 is
`461306985ea3db9bb93c73d8242c435712b19b98e973b9a02b0a351ee15ba105`.
Both timing blocks passed exact outputs. Control measured12.0398FPS and the
unchanged-storage policy12.7863FPS, an observed6.20% gain with fixed-order limits.
The sealed full proof rebuilt after completion. All unrelated tests, Git work
and agent file writes were suspended during both timing blocks.
[Measured result](2026-10-07-client104-performance.md).
