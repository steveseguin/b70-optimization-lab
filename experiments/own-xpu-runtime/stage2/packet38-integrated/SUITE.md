# Persistent suite execution

`suite.py` starts two ranks once, snapshots the supplied manifest bytes, runs an
untimed warm-up request, then executes every listed request for each repeat.
Before launching, the wrapper snapshots each input bundle, verifies its complete
manifest binding through the read-only checker, and requires matching plan,
identity and model directory for the entire launch. Prompt token lists come from
those snapshots. The checker source is itself read and compiled from one byte
snapshot; receipts hash those executed bytes even if its external file changes.

Warm-up traverses the first prompt and two generated tokens, so every layer and
the target head run before timed requests. With MTP, draft generation also runs.
The rank launch receipt records its packet-local persistent-cache HOME and
whether files were present before launch. File presence is not proof that a
driver cache lookup hit. The warm-up and every request record each rank's first
position time; no compilation time is silently removed from a timed request.

Each boundary sends RESET to both quiescent ranks. Allocation addresses and
prepared commands stay live. All live mutable allocations are zeroed in bounded
chunks, including both recurrent banks and unused QSA tails. EOS history,
active controls and immutable PLE metadata are restored. Draft state, lookup
metadata, candidate state and request timing counters are reset. Each request
gets a fresh controller/provider, token history and counters. Socket sequence
numbers stay monotonic to prevent replay; the native mailbox is zeroed only
after both RESET acknowledgements. Reset maintenance is outside request timing.

Each request contains the same token, timing and rank rows as the single-request
controller. The wrapper combines the two ranks' retained layer fixtures into
`step1` through `step8`, writes their exact hashes, then invokes the existing
read-only `suite_check.py.check_prompt`. It checks the manifest's input/oracle
hash binding, all tokens and every retained fixture byte. A comparison failure
marks that request and the window failed but the next request still runs.
Execution faults instead follow the shared bounded stop path and stop launches.

State evidence is bounded to one raw request at a time. After the next RESET
captures the completed request, the wrapper verifies the target's recorded
buffer hashes, retains every snapshot file's SHA-256 and size and its exact
JSON metadata in `state-evidence.json.gz`, verifies that archive, then deletes
the raw state and draft-cache snapshots. The request-state inventory already
stores standalone target scratch as hashes. The eight layer-fixture steps stay
raw for `suite_check.py`; token receipts and timing rows are retained. The final
RESET captures and archives the last request too. `state-retention.json` binds
the archive hash and records original and retained byte counts.

Before RESET, `storage.admit` reserves 550 MB for a real-model snapshot (8 MB for
the miniature), checks root free space and the packet build budget, and refuses
new writes if the limits cannot be met. Per-request fixture/receipt writes have
a separate admission. Hash mismatches or storage failures follow bounded stop;
raw state is not deleted before its verified archive exists. The lightweight
`test_state_retention.py` gate checks exact hash/metadata retention, raw-state
removal, retained fixture bytes and corruption refusal before deletion.

The per-request decode rate is `(N-1)/(t_N-t_1)` for N non-EOG generated tokens,
with times in seconds and N at most 64. Thus 64 tokens use exactly 63 intervals
ending at tokens 2 through 64. Immediate EOG has no decode rate. The summary
uses the ordinary median of successful finite positive per-request rates over
all listed prompts and repeats, matching the reference table's pooled observed
rows. Failed, missing, zero and nonfinite rates do not enter that median. Each
repeat also has its own median. Different window directories are never pooled.
An incomplete manifest is explicitly marked incomplete; it cannot establish the
frozen twelve-prompt suite result.

`suite_gates.py` executes three miniature prompts in two different orders in the
same pair of rank processes, for both controller modes and none/MTP providers.
It runs the resident prepared path with GNU argument auditing. It compares
tokens, acceptance counters, every plan allocation and both banks, standalone
mutable target allocation hashes, host lookup/selected/loaded-layer/FP32 cache
metadata, parity, logical event, histories and poison status, every draft
mutable allocation and draft position/disabled state, and all 32 retained
miniature layer fixture files. Matching per-order invariant hashes are retained
in the gate JSON.
This proves request-order independence on the CPU miniature. The receipt schema
is also checked against the exact real-model oracles available at gate time by
using oracle-derived fixtures and rejecting a deliberately changed token. Those
schema checks are not described as real-model runtime executions. Full model
suite execution remains a coordinator window.

Per-token receipts retain the rank-0-to-rank-1 handover and the reverse direction
when a confirmed next half exists. A successful guess may start before rank 1
finishes: its signed gap records that overlap and its nonnegative handover cost
is zero. A discarded terminal guess is excluded. Token-mode rank idle estimates
use request wall time minus the union of all host command envelopes, including
rollback and transfer work. This is a conservative lower bound; it is not GPU
event timing. Profiled runs retain the separate kernel-time complement estimate.

`cpu_campaign.py suite` calls `suite_export.py` after successful actual execution.
The exported `suite-real-cpu.json` binds both rank launch/teardown receipts, each
request's token IDs and trace/timing hashes, the input admission, and retained
fixture inventory hashes. It rechecks each request against the read-only oracle.
Partial manifests retain their actual admitted/request counts and explicitly
report `complete_frozen_suite=false`; they cannot establish twelve-prompt coverage.
