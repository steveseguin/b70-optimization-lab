# Rank-0 rollback coverage

`audit_rollback.py` derives the inventory from `launch-plan-rank0.json` and
checks the actual code. `rollback-inventory.json` lists every allocation and
writer. The independent reviewer received the launch dump and code before this
list. The real split is 24 layers per rank; the four-layer miniature puts both
GDN and QSA plus layer-1 PLE on rank 0.

| Persistent data | Count / bytes | Handling |
| --- | ---: | --- |
| GDN recurrent state | 18 × 1,572,864 | Existing kernels read committed bank and write alternate bank. |
| GDN convolution history | 18 × 61,440 | Separate old/new pointer arguments, unchanged kernel. |
| PLE convolution history | 1 × 184,320 | Separate old/new pointer arguments, unchanged kernel. |
| QSA keys / values / raw index rows / pools | 6 layers × 4 arrays | Append at current position; redo overwrites the same rows. Prior rows unchanged. |
| Device PLE token history | 16 | Hash writes through its input; checkpoint on host, restore on miss. |
| Host PLE histories | 16 | Restore the saved two int64 values on miss. |
| Position / commit counter | 4 | Half executes one unchanged commit. Undo restores the pre-half position. |
| Sticky error | 4 | Never cleared or rolled back; any nonzero value aborts. |
| Streams / hyper-connections | full 20,480-byte stream | Broadcast overwrites at each rank-0 half; no cross-position carry. |
| QSA selection IDs and other intermediates | listed individually in inventory | Written before their first read each position; redo overwrites. |
| FP32 prepared input cache | 696,320-byte workspace | Cache source/extent invalidated at bank transition; no stale cache can be consumed. Contents with invalid cache are scratch. |
| Prepared bindings | two operation maps and two immutable command vectors | Allocation IDs, operation map, command vector and parity swap together after drain. GEMV matrices never bind temporal state. |
| Host lookup IDs / selected experts / loaded layer | bounded host metadata | Lookup IDs regenerated; routes selected again; streaming layer released. |
| Fixture snapshots | initialized 983,040-byte workspace | Candidate bytes held privately; publish only after acceptance. Redo replaces candidate. |

The extra state bank is **29,601,792 bytes**, covering 37 allocations. The GDN
and convolution bank swap itself copies **zero state bytes**. The packet40
strict speculative image adds the separate copies described below. All banks
are initialized once, including unused output bytes read by the host adapter.

There are 1,015 rank-0 plan buffers and 890 plan sites: 37 banked, 24 QSA append
arrays, three temporal controls, four externally initialized, and 947 overwrite-only
buffers. Immutable weights, RoPE and PLE metadata are never speculative writes.
The inventory includes first-writer/first-reader evidence and explicitly handles
QSA partial writes instead of assuming that an output name means a whole-array
write. The owner allocation inventory also accounts for non-plan scratch,
slabs, routes, mixture buffers, snapshots and FP32 input storage.

QSA appends 1,024 bytes of keys, 1,024 bytes of values and 256 bytes of raw index
state per layer/position. A completed four-token block writes its 256-byte pooled
row. A miss followed by redo rewrites exactly those locations. Strict rollback
also restores all QSA bytes beyond the pre-speculation committed extent,
including a terminal abandon without redo. The already-committed prefix is
excluded from the backup so illegal writes to it cannot be hidden.

## Hot-path copy ledger

For each rank-0 half: position check 4-byte D2H; PLE-history checkpoint 16-byte
D2H; token 4-byte H2D; token embedding and PLE lookup 5,120-byte H2D each;
sticky-error check 4-byte D2H; confirmed/candidate boundary stream 20,480-byte
D2H. The same stream is copied into the producer shared slot, across to the
consumer slot by the coordinator, and then uploaded 20,480 bytes H2D on rank 1.
Each rank-1 half also checks position/error (4-byte D2H each), uploads the token
(4-byte H2D), and generation reads the target token (4-byte D2H).

The bounded pinned slab entails an ordinary host memcpy of the same byte count
for each H2D/D2H transfer. Python's shared-slot slice makes a bounded host temporary.
Commands are 32 bytes and replies 64 bytes. Model scalars travel in these frames;
no pointers/events do. Lookups read only their quantized file rows on CPU and
produce the BF16 upload bytes. Resident model weights and static constants have
no per-token uploads. The CPU gate's layer-streaming weight uploads are separate
from the native resident path.

The original rollback ledger contained a 16-byte D2H history checkpoint and
20 bytes H2D per miss. That is not the complete packet40 cost: before each
speculative half, a private image copies every potentially overwritten plan
output, inactive state bank, uncommitted QSA suffix and standalone mutable
allocation. On a miss or terminal abandon those saved extents are copied back.
The image also saves the rank0 shared slot and exact host-derived metadata.
`speculative-snapshot.json` records capacity, captures, restorations and payload
bytes. Private backup bytes are zeroed at quiescent dump/reset/finish boundaries;
model allocations are never scrubbed to manufacture equality. This adds memory
traffic whose device performance is unmeasured. Bank selection itself remains
a permutation, and redos incur the ordinary half ledger again.

For each of the eight retained fixture positions, each rank makes 24 × 20,480
bytes of local-device snapshot copies, then reads its initialized 983,040-byte
snapshot allocation. Fixture bytes are copied into private host candidate
vectors, checked against the oracle, and written only on acceptance. These
intentional gate costs belonged to inherited instrumented model-window wall
timing. Packet40 retains these copies only for diagnostic exactness windows;
its speed windows use `--retain-steps none`. The 128-token companion also
retains steps 97–104.

Full state gates compare every plan buffer's bytes, both active and inactive
banks, host histories and FP32 cache validity after a nonterminal miss plus
redo, against never speculating. The packet40 archive inventory gate also
compares every standalone mutable allocation, including invalid FP32 scratch
bytes, plus every host inventory field except the separately recorded logical
event counter. No model buffer is exempted from this nonterminal proof. Rank 1
only consumes confirmed streams; its target history stays sequential and needs
no rollback. Strict terminal abandonment now uses the same physical image
restoration and requires its own current-source full-state proof below.

## Prepared launch parity

Rank 0 first allocates every spare recurrent/conv buffer. It then prepares the
plan and launch commands for parity 0, swaps the banks, prepares parity 1, and
swaps back. The four artifacts move together: current/spare allocation IDs,
`prepared`/`alternate_prepared`, `issue_sites`/`alternate_issue_sites`, and the
parity bit. `swap_state_banks()` drains before this permutation and invalidates
FP32-input cache source/extent. Rank 1 never speculates and needs one command
vector.

A completed, uncancelled half writes candidate state into the spare bank,
drains, then swaps all four artifacts. Acceptance keeps that selection. A miss
drains again, checks the sticky error, and swaps all four back only if the
candidate previously swapped. A partially cancelled half never swapped. Both
paths restore the pre-half physical image, including position, token/history,
lookup IDs, selected routes and exact FP32 cache source/extent before redo.
Streaming layers must already be released; restoration checks that any saved
nonzero FP32 source is still live and cannot resurrect a freed allocation.
There is no allocation, pointer rebinding or command rebuild in the bank swap.
Appending QSA rows still follows the unchanged same-position overwrite rule.

For GNU resident CPU audits, each executed site reconstructs its operation and
bindings directly from the currently selected buffer IDs, bypassing the cached
operation map. It reconstructs the capture-time FP32-input cache prestate and
compares command count, allocation IDs, pointers, allocation/pointer argument
bytes and serialized operation bytes with the actual selected command vector.
Audit-only temporary allocations/logging are disabled in normal windows. This
catches a stale command vector even when its owner generation remains valid.
It also catches a stale operation map rather than trusting that map as the
reference. The audit runs through all guess modes; forced misses additionally
compare model output and rollback state bytes with the sequential control.

The serializer is GNU-only because it removes ABI padding with
`__builtin_clear_padding`. icpx runs still establish output/state correctness.
The real-model CPU gate uses bounded layer streaming with per-operation
preparation and 8 tokens / 384 layer comparisons per mode; the miniature
resident gate exercises persistent two-parity prepared vectors. These different
scopes are recorded explicitly. CPU gates cannot prove native callback/kernel
execution, so the corresponding coordinator gates remain mandatory.

`review_prepared_gate.py` independently checks the source-level ownership and
parity contract and rejects mutations that omit any bank artifact or the
independent argument comparison. This is a structural regression check, not a
substitute for actual forced-miss execution. Prepared capture does not change
kernel arithmetic or the inherited exceptional-value/NaN policy.

## Packet38 complete request reset inventory

At a quiescent boundary both ranks drain, reject a target sticky error, dump the
completed target and draft state, and restore parity zero. Every live mutable
allocation is zeroed in place: all plan buffers, both recurrent banks, QSA
keys/values/index rows/pools including unused tails, snapshots, controls, FP32
scratch and private draft state. Immutable weight/RoPE allocations and the
pinned slab stay alive. Restore active=1, unit scalar=1, EOS token history and
PLE metadata. Clear host histories, lookup IDs, selected experts, FP32 validity,
logical events and request timing/counters after reset uploads. Reopen output
streams. Draft position and disabled flag reset; no target or draft allocation
is released. Both prepared target parities and draft command lists survive.

Python constructs fresh draft provider/history/counters per request. Native
constructs a fresh Config/Result/history/script index per invocation. Shared
bytes are cleared only after both RESET replies; socket transaction sequences
remain monotonic. Input bundle weights and dispatch remain sealed for the
entire launch. `suite_gates.py` compares three prompts in different orders. Its inventory
covers every target plan allocation and both banks; SHA-256 hashes of standalone
mutable target allocations, including operator scratch and snapshots; lookup-ID
hashes, selected experts, loaded-layer state, FP32 cache labels/extents, bank
parity, histories and poison status; the logical event counter is retained
separately with the raw inventory hash because discarded launch counts vary; every mutable draft
allocation and draft position/disabled state; tokens, acceptance counters and
all eight retained fixture steps. Immutable weights/RoPE and the transient
pinned copy slab are excluded from mutable model state. The request-boundary
inventory helper runs only after drain and never changes model allocations.

At each boundary the Python wrapper validates target `state.json` hashes against
the raw buffer and alternate-bank files. It then stores each snapshot file's
size and SHA-256 plus exact JSON metadata in `state-evidence.json.gz`, verifies
the compressed round trip, and removes the raw state snapshots before the next
request. Standalone scratch is hash-only from the start. Selected layer-fixture steps remain raw through the oracle checker; packet40
can select none, steps 1–8, or steps 1–8 and 97–104. Gates compare the same
per-file hashes and metadata through this archive, rather than relying on raw
state files remaining on disk. Storage admission reserves one raw snapshot;
completed requests do not accumulate raw model-state dumps. See the current
independent review mapping in `review-p40-inherited-map.json`; the
copied packet38 review remains historical evidence.


## Packet40 cancellation at every compute submission

Rank 1 release-publishes only its checked target token and position in a separate
shared verification record. Rank 0 checks the matching position with acquire
ordering before every actual compute submission, including individual passes
inside a prepared or legacy multi-pass site. Copies are not compute launches.
On a mismatch it stops submitting.
The already submitted prefix drains. An after-submit observer records each event
as the owner tail even when an operation is interrupted before returning its
ordinary grouped event record. The cancellation marker is caught outside backend
fault handling and is never mistaken for a device error or used to poison the
owner. Sticky target errors remain fatal and cannot be restored away.

A partial half has not swapped recurrent banks. Its rollback therefore restores
position, token history and host histories without swapping. A fully completed
half uses the existing swap-back rollback. Both invalidate the prepared FP32-input
cache; redo executes the actual token and overwrites all partial QSA appends and
scratch. Cancelled fixture candidates cannot be published. No cancellation changes
kernel arithmetic or gives the guessed token authority to emit.

`cancellation_retention_gate.py` tests every actual miniature compute boundary,
including zero launches and the final boundary. Its real-model mode samples
indices with seed 4001. Each forced miss is followed by redo, and every token,
every target plan buffer and both recurrent banks must have the same final hash
as never speculating. `cancellation-inventory-gates.json` additionally proves
standalone allocation and host-inventory equality for all 204 forced-cut cases
(100 mini native, 100 mini Python, four real native), excluding only the logical
event counter while retaining its actual value and raw inventory hash.
The `--cancel-launch` option is rejected by device builds.

An EOS response discards its pending next-position guess without redo because
only the confirmed target may end the request. `SpeculativeImage` captures the
pre-half bytes before guessed token upload or history preparation. Rollback
drains, refuses a sticky failure, reverses a completed bank swap, then restores
saved physical extents and exact host metadata. It restores only rank0's shared
slot, never rank1 verification or draft publication. The active recurrent bank
and committed QSA prefix are deliberately not backed up; illegal mutation there
must survive rollback and fail comparison. Host-only negative controls exercise
this requirement. At a quiescent boundary only the private backup is zeroed.

The earlier committed-state-only EOS comparison is historical diagnostic
evidence. The strict implementation requires fresh complete physical-state
terminal, retention and cancellation checks before sealing. See
[EOS-STATE-SCOPE.md](EOS-STATE-SCOPE.md) for the original failure and correction.

Actual speculative launch counts can differ with process scheduling. Controller
parity excludes only the `logical_event` issue counter from ordinary inventory
comparison and records its actual value and the original inventory hash. No
model buffer is exempted for a nonterminal miss plus redo.

## Packet40 fixture independence

`--retain-steps` controls only snapshot copies and export. The generated-step
index still selects target head execution even when retention is `none`.
Captured snapshot buffers return to zeros after export; retention-off runs keep
them zero. The CPU retention gate compares every emitted token, both ranks'
complete plan/bank state hashes, standalone mutable allocations and host state.
The capture copies and zeroing belong only to diagnostic exactness windows.

## Operational fallback

Use the prepared `WSs` window or `--draft none` to disable speculation and its
cancellation path. `--controller python` selects the reference coordinator; it
still uses the same rank cancellation hook and is not a cancellation-off switch.
Preserve the failed window, state hashes and event ledger before choosing the
sequential fallback. Re-run the same prompt/oracle scope under its own receipt;
do not turn a failed speculative receipt into a passed sequential measurement.

CPU gates establish scheduling and state equivalence in the host backend. They
do not establish device queue overlap, a speed gain, or device fault recovery.
