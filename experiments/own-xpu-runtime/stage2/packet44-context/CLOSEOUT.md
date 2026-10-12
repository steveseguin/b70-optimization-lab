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

CPU qualification passed under the coordinator’s reduced plan. The 25 retained
cases matched 200 tokens and 5,376 layer fixtures (13 GNU real-model cases
plus 12 rollback cases). The Intel composite matched four tokens and 192
layers with two forced misses. Both requested GNU KD references passed. See
[CPU-GATES.md](CPU-GATES.md) and [build-receipt.json](build-receipt.json).
All device windows remain pending. No speed is claimed.

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

## Coordinator reduction, 2026-10-12

The coordinator deliberately stopped the previous session at 22:35 UTC.
The remaining full Intel-host real-model matrix would cost about five more
CPU hours while the cards waited. It was waived because the coordinator's
real-hardware windows repeat the full exactness check in minutes. The retained
25 passes comprise 13 GNU real-model cases and 12 both-compiler rollback cases;
all were rechecked by parsing and SHA256 only, without rerunning a model.
The interrupted Intel decision-memo/capacity-256 attempt is **not run** for
qualification. Its stop receipt and compressed scratch inventory are retained
under evidence/. The graceful stop had already removed its partial scratch;
resume verified that none remains. This was not a model failure.

The replacement Intel qualification is one development-prompt request at
capacity 4,096, four generated tokens, real MTP execution and a guess script
forcing two misses and one hit. The compiled native controller does not accept
an MTP guess override, so this diagnostic uses the existing Python controller
and substitutes only the provider mailbox guesses after the real draft runs.
The target binary, model arithmetic and verifier remain unchanged. The GNU
native MTP gate and both compilers' native-controller gates remain qualified.
The exact outcome is in intel-composite-gate.json; no diagnostic speed is used.

Only GNU draft-head references at capacities 4,096 and 32,768 are generated
for KD. They consume the previously captured confirmed streams, without
running another target-model request, and each must match the frozen draft
valid-prefix oracle. The reduced seal explicitly records this two-reference
scope instead of claiming the original six-arm draft matrix.

## Not closed on CPU

The full Intel real-model matrix is waived, not passed. Intel draft-reference
arms and a capacity-256 KD reference are outside the resumed window scope.
Long real conversations, physical card residency, device output exactness,
prepared-launch wall time, selection latency and speeds remain coordinator
window work. A CPU seal is not a device or publication qualification.

The composite archive retains the unchanged pipeline receipt, whose inherited
`diagnostic` label does not know about harness mailbox injection. Its rates
and label are not performance evidence. The enclosing gate explicitly records
`no_speed_claim: true`, the script, all original/forced guesses and injection
scope. The seal also parses the archived receipt, checks real draft-provider
success, and rejects missing/invalid original guesses.
