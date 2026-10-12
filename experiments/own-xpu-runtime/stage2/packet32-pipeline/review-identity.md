# Independent arithmetic and bit-identity review

Review scope: packet29 main/plan, arithmetic implementations and dispatch;
packet32 rank split, state-bank argument rebinding and retained-fixture flow.
This reviewer used CPU file reads and source-byte comparisons only. No compiler,
model process, device binary or device discovery ran in this review.

`review-identity-sources.json` directly compares 35 packet-local kernel,
arithmetic, constant and dispatch files with packet29. All 35 are byte-identical.
The launch split keeps the original order within each rank; embedding and PLE
remain on rank0 (real layers 0–23), and rank1 keeps layers 24–47, final mixer,
head and argmax. The four-layer mini deliberately places its PLE layer on rank0.
The single-device backend substitutes process ownership for cross-card handoffs;
no reduction expression or dispatch name is changed by this substitution.

The changed GDN and convolution binding uses separate input and output state.
The core, tiny adapter, original parallel, specialised and round2 GDN paths all
read the old state from the input binding and completely write the next state
to the output binding. Convolution first reads input history into private
values, then writes its full output history. Neither requires input/output
aliasing for its arithmetic. Two prepared argument maps are swapped alongside
state-bank pointers. Matrix bindings do not reference these state buffers.
The cached FP32 input identity is invalidated at each bank switch.

Exactness follows by induction over confirmed positions. Rank0 half p consumes
its state through p−1 and the confirmed input token. Rank1 half p consumes its
own state through p−1 and the confirmed rank0 bytes. Rank1 never speculates, so
it needs no undo operation. A matching guess has exactly the same rank0 inputs
as sequential execution. A miss restores rank0 history/state/position and reruns
the same half with the confirmed token. This argument requires the mechanical
rollback review and actual byte gates; source preservation alone is not a
runtime correctness result.

Reviewed hazards communicated to implementation:

- Host PLE history changes in `prepare_token`, and device token history changes
  in `ple_hash`; both must restore on a miss.
- Rebinding only the named buffer map would leave prepared argument allocations
  stale. Both binding banks must change with the state bank.
- Prompt positions omit final/head/argmax but still commit. Their stale
  `next_token` cannot enter predictor history.
- Fixture step1 is the last prompt position. Rejected speculative fixture bytes
  must never be published as retained fixtures.
- A terminal token discards any in-flight next half. Snapshot bytes must be
  collected before the next broadcast overwrites rank0 streams.
- Newly allocated spare states needed initialization: the core evaluator reads
  output bytes before replacing its complete state output. Fixed by zeroing
  spare allocations once at initialization, with no hot-path state copy.
- Decode-only class timing must exclude prompt work or label it explicitly;
  rejected speculation belongs in separately identifiable redo/work totals.

Device concurrency, driver behavior, native execution identity and performance
remain coordinator-window gates. No speed result is established by this review.

Controller identity review found no additional token/fixture ordering defect.
The n-gram provider uses confirmed history and excludes the current suffix from
its earlier-match search; overlapping earlier occurrences remain valid. The
first script guess corresponds to the first emitted token. Prompt overlap
changes only scheduling. Generation fixtures publish only after an accepted
rank0 half, and terminal tokens drain and discard an already started candidate.

No kernel-source change or reduction-order change was found. Exactness gates
executed by the implementation owner remain separately recorded evidence; this
review does not substitute a source audit for those runtime tests.
