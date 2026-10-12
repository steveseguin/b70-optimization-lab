# Packet44 real allocation capacities — closeout

<!-- campaign-closeout -->

## Question and identity

Can the copied packet38 quantized compressed Flash-Next runtime admit 4,096
and 32,768 positions while preserving arithmetic-v2 bytes and short-context
kernel work? The copied identity is [baseline.json](baseline.json); target
weights, official draft, dispatch vocabulary, two ranks and native controller
are retained. All work here on 2026-10-12 is CPU-only. Device artifacts are
compiled but never executed by this agent.

## Outcome

Qualification is in progress. A successful build is not a CPU or device gate.
The final authority will be build-receipt.json, emitted
only after all required current-binary CPU receipts pass. No speed is claimed.

## What worked

Allocation capacity is separated from valid-position launch bounds. QSA
selection and attention refresh at 32-position boundaries; recurrent bank
swaps carry their own bounds, and draft state tracks its bound independently.
Pooling launches append work only. See [CAPACITY.md](CAPACITY.md) and the
independent [capacity review](review-capacity.md).

The independent [selection review](review-selection.md) pins the lab v2 order:
stable descending pooled score, earlier block on ties, four token positions
per chosen complete block, followed by the incomplete tail. First eviction
occurs at 2,052 valid positions. The official model agrees structurally but
does not promise the same GPU top-k/scatter order. The unchanged lab arithmetic
is the gate, not a claim of universal official-kernel ordering.

The [memory plan](memory-plan.json) keeps BF16 throughout and has more than
1.5 GB headroom per rank at both requested capacities. Both exact baseline counts are bound to retained historical
censuses, with explicit reserves in the admission ceilings. Actual owner
allocations are checked before requests. Physical residency is still a device-window question.

## What failed or remains uncertain

The first GNU capacity-256 fixture attempt refused the expanded RoPE file in
an adapter fixture reader with an old fixed element count. The reader now uses
the declared table byte count; failed evidence remains in
[capacity-fixture-gates.json](capacity-fixture-gates.json). Review also found
an undersized long-attention reference arena and a fixture-header width coupled
to the enlarged C++ structure; both were corrected before qualification.

Prepared-command refresh time, actual kernel launch behavior, long-context
physical residency, device exactness and speed remain unmeasured. The finite
K2 deadline estimates are planning reservations derived from packet38 costs,
not measured capacity results. A short real prompt cannot prove a long real
conversation's correctness; long synthetic states exercise the selection and
attention boundaries on CPU, with device windows still required.

## Evidence and patches

[CPU-REPRO.md](CPU-REPRO.md) reproduces CPU gates and compiled binaries.
[WINDOW.md](WINDOW.md) provides the coordinator chain at each capacity.
[INTEGRATE.md](INTEGRATE.md) and [integration-delta.json](integration-delta.json)
list every changed copied file for packet40 integration. Raw logs are compressed
under evidence/. Disposable fixture bytes have exact hashes; model-layer
expectations remain in the read-only suite oracle. Build objects are regenerable
and removed after their hashes are recorded; compiled coordinator binaries and
necessary draft reference fixtures remain in ignored build/.

## When to revisit

Run the coordinator's full window chain at each capacity only after CPU sealing.
Repeat qualification after merging packet40; receipts do not transfer to a
changed binary. A device fault follows the host's evidence/recovery procedure,
never an automatic retry. Any slower short-context device result requires
investigation before adopting this capacity extension.
