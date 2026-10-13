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

## Long-suite wrapper amendment, 2026-10-13

The coordinator queued the long-manifest WS window. `validate_manifest` refused
its 32-token cap before device contact because it admitted only 64/128. The
oracles and devices were not the cause. The completed c4096 and c32768 card
chains remain historical evidence under their original seal; this amendment
runs no device or real-model CPU request.

`suite.py` now accepts cap32 with the unchanged arithmetic-v2 identity and
selects the long run's checker. Its private adapter preserves the checker's
oracle admission, input/result/fixture bindings and validation.json midprompt
hashes. Token equality and steps 1–8 are unchanged. Absent actual midprompt
records are explicitly recorded in the request receipt with the evidence
limit: generation-step end-to-end equality with selection active for LONG-B,
not midprompt byte equality. Present records, even empty/incomplete directories,
must compare. No late fixture steps are claimed for cap32, and the submission
metric requires 100 events and stays unavailable here.

Changing the seal also changes the prerequisite identity. `window.py` therefore
accepts the exact prior seal only for K0/K1a/K1b/K2/W0p/KD prerequisites of
WS/WSs using this exact long-manifest hash. The current request still records
the amended seal. All other identity fields, dispatch and retained child hashes
remain strict. A read-only audit passed all six existing c4096b prerequisites.
No historical card receipt or model gate was rewritten.

CPU evidence: [long-suite-wrapper-gates.json](long-suite-wrapper-gates.json)
binds **131 checks**: 14 long-wrapper tests (including two mocked long windows),
10 compiler mocks, nine export checks, 11 warmup gates, four storage checks,
10 context tests (22 combinations), 37 inherited window tests including their
mini-model profiling case, and a separate 36-test mocked-only inherited run.
The two direct `suite.py --mini` dry paths (Python/native controller) each ran
four requests and 128 tokens, plus excluded warmup. Both real oracle directories
passed read-only admission: 32 tokens and 384 retained fixtures each. The seal
rehearsal passed **21 gates / 20 deliberately blocked window launches**.
These counts overlap by design; none is a model performance measurement.

The first storage-test invocation lacked its required `--output` argument and
exited at argument parsing. Its failed log is retained alongside the successful
rerun. No binary or device was reached by that invocation.

[amend_long_suite.py](amend_long_suite.py) regenerates the amendment from the
byte-preserved parent build receipt and CPU summary in
`evidence/long-wrapper-20261013/`. It rejects unrelated source changes and any
changed compiled artifact. Original model/rollback gates keep their old source
identities; they were not rerun. The amendment pins the changed wrappers, new
test/seal scripts, long checker, long manifest, new gate receipts and updated
admission rehearsal. The existing full `seal_context.py` describes the original
model qualification; do not repin those historical gates to make it pass after
this edit. Use the explicit amendment procedure below.

From the repository root, retaining affinity and numerical threads at two:

```bash
packet44=experiments/own-xpu-runtime/stage2/packet44-context
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python3 -B "$packet44/long_suite_cpu_gate.py"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet44/amend_long_suite.py" --candidate
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet44/test_window_seal_admission.py" --build-receipt "$packet44/build-admission-candidate.json"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet44/amend_long_suite.py"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet44/integration_inventory.py"
```

[WINDOW.md](WINDOW.md#long-prompt-wl-amendment-2026-10-13) contains the exact
coordinator command. Actual long-prompt device equality remains pending WL.
