# Proposed rolling qualification packet, version 6

This is a future evidence contract, not an admission to run GPUs or a claim that
rolling inference has passed. The frozen v5 scripted pending-provider gate and
its comparator/finalizer remain unchanged. V5 deliberately requires specific
forced cases, stage-zero-only speculation and provider advancement at every
abort. Those are coverage requirements for that experiment, not invariants of
every valid rolling execution.

Use an explicit new state-set schema `ownrt.pipeline-state-set.v6` and a new
rolling proof schema. Do not reinterpret a v5 packet or silently select relaxed
checks from its observed counters. The v6 packet must name its controller mode,
exact native attestation schema, code pins, model/draft hashes, arithmetic flags,
device geometry, layer cuts, prompt/output hashes, EOS/cap policy and final
position. A separate native schema is needed only if native field semantics
change: the current pending-provider native emitter already permits downstream
tentative work and records whether each stage-zero abort advanced the provider.
Its original schema and actual mode must be retained, not relabeled as v6.

## Authenticate proposals before using them

The controller must not load expected outputs, retained proposal references or
scripted wrong guesses. Its admitted source closure and plan must establish
that restriction. References are supplied only to an offline finalizer after the
run. Pin the actual model/draft identity independently of candidate evidence.

Retain each validated final-owned 360-byte record with its SHA, original final
ROW and ACCEPT sequence, immutable request/epoch/row/prefix metadata and hidden
SHA/extent. Retain each actual 192-byte provider publication and its SHA, the
transport reply identity, and decoded fields. These small witnesses allow the
offline finalizer to repeat the real codecs against retained command identities.
The native provider trace must independently agree on true-pair position,
input token, parent hidden SHA, proposal tokens/depth, serial and restoration.
The full hidden arrays need not be duplicated in every trace, but their hashes
must be linked to the independently copied final owner record and the provider
publication. State which bytes are retained and which are attested by hashes.

For every op27, bind the original locally ACCEPTed ROW ticket and tentative bit,
its actual ACCEPT sequence, the independently committed final parent, provider
serial and exact physical/committed/pending snapshot. Provider advancement is
exactly once per canonical true pair. The final-record lease must remain held
until the complete validated provider reply; elapsed time or send completion
does not prove the native reader has copied it.

## Replay actual distributed commands

Reconstruct every owner's monotonically increasing wire sequence, including
op27 in stage zero's same sequence. Compare the controller journal to complete
native command traces. Rebuild full row and prefix identities from the admitted
request/prompt and actual final target output. Verify every ROW, ACCEPT and
ABORT against its original immutable ROW and exact pending list. Issued work
must not change when a fresh canonical d1 disagrees with an older recursive d2.
For each speculative ROW, record the actual publication ticket and depth that
supplied its token; require the matching hypothetical prefix. Merely matching
an eventual target token does not establish proposal provenance.

Every suffix correction must follow target verification, drain all issued
commands, retain the already verified prefix, abort each affected owner once,
receive and validate all abort acknowledgments, then issue corrected work with
fresh row IDs. Validate byte-restore flags against the admitted verification
policy, not only the controller's requested policy. Final-stage ROWs remain
verified-only. Earlier stages may have actual tentative rows and aborts.

At the terminal boundary, every stage must be quiescent with zero pending rows,
active slots, sticky errors and unconsumed commands. For each stage separately,
recompute row/commit/discard and capture/release/accepted-tentative conservation;
recompute abort command counts and actual discarded depths from its trace.
Do not require downstream abort counts to be zero.

## Verify survival without manufacturing coverage

Every stage-zero target abort must have exactly one native survival record,
bound to its actual abort sequence, full oldest ROW, ordered discarded suffix
and the provider position/serial recorded at each target snapshot. Validate
the complete before/after canonical device+pinned allocation inventory, private
image, current and saved host state, Sequence and typed prepared-binding
identity. Preserve the native source's explicit exclusions for shared counters
and opaque closure internals; do not describe them as fully serialized bytes.

Before and after must match exactly whether or not provider advancement occurred.
Derive `advanced_since_snapshot` independently by comparing the pre-abort
provider position and serial to the oldest snapshot. Both coordinates must
advance together or both remain equal; regression or disagreement is a failure.
Do not force the v5 gate's `provider_position + 1 == oldest.position` relation:
in rolling execution the canonical provider may lag the rejected target row.
Instead bind its position, last seed and last result to the last actual completed
op27 before this abort, and prove that seed belongs to the accepted true prefix.
For downstream aborts, require complete target restoration but no invented
provider-survival receipt: those owners have no provider allocation partition.

Count observed provider borrows at depths zero, one and two, and split survival
records by advancement and discarded depth. An unobserved case is absent
coverage, not a pass or a reason to inject scripted tokens into this run.
Retain and link the separate v5 forced two-row/one-row coverage proof. If the
rolling qualification needs broader coverage, choose additional ordinary prompts
and report what actually occurred. No trace omission is allowed; the current
128-record survival bound must be admitted for the chosen request or fail closed.

## State parity and scope

For normal EOS/cap completion, compare all persistent canonical target buffers
across the stage union with the matched sequential reference: exact producer
coverage, names, types, shapes and bytes. Reuse the registered scratch/bank
semantics only; never omit a buffer to obtain parity. Compare all canonical
draft allocations, including both pinned allocations, to a reference replay
of precisely the same true pairs, head mask, context and terminal policy.
Current cohort counts are 2,065 target buffers and 73 draft allocations, but
derive inventories from authenticated layouts rather than hardcoding a model
architecture as the engine's universal contract.

Require all canonical true pairs, actual proposal identities and retained
legacy/cohort comparisons that are applicable to that same input. Different
requests cannot borrow the 117-pair/32-proposal coverage numbers. At completed
boundary provider pair count equals final target input position minus one.
Preserve raw state bundles, sealed metadata, source/config identities, terminal
exit statuses, host guard evidence and exact archive member hashes.

Cancellation is a separate outcome. Drain already reserved work and retain its
actual emitted prefix; do not mark an incomplete provider prefix as successful
normal qualification. `cancelled_provider_incomplete` is a conservative coverage
exclusion and is not evidence that state bytes differed. Native reset, continuous
multi-request operation and throughput certification remain separate gates.
Only after rolling output/state parity should an unchanged cold suite measure
decode with an explicit numerator, denominator and timestamp window.
