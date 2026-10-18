# Packet86: routed-expert and HC limiter diagnostic

**diagnostic_nonexact: true. CPU preparation only; device costs are not measured.**
Never use any view, including production, in a bundle, chain, submission or
headline. This packet deliberately changes outputs to expose costs. It does not
qualify a runtime optimization.

The source base is a byte-copied packet75 bundle, recorded in
[parent-source-manifest.json](parent-source-manifest.json). Existing packet75,
packet77, shared screen and ops files were not edited. Packet77's
[instrumentation patch](../packet77-attribution/instrumentation.patch) applied to
these copies; [apply log](evidence/instrumentation-apply.log). The control selects
packet75's retained `wide64` experts, production HC gates, production expanded
dense reads, batched miss copies and draft HC fusion; 24/24 layers, draft on
rank1, unchanged full BF16 KV. This is not an assertion that the control contains
every later selected packet75/84 winner.

Packet77 measured about 2.73/2.75 ms per half for experts and 1.198 ms for rank1
HC gates. Those are **historical packet77 measurements**, not packet86 results.
[Packet85](../packet85-critical-path/MODEL.md) explains why another static-load
change is insufficient after packet81's neutral result and packet73/74 losses.

## Selectable views in one binary

| View | Change | Identity gate |
| --- | --- | --- |
| production | Unchanged packet75 selection, with packet77 observation | Exact CPU fixture and device oracle required |
| exp-nodeq | Read the same packed code/high/scale/half bytes; use their raw unsigned values, without half/grid dequantization | Intentionally skipped |
| exp-constgrid | IQ2_S grid magnitudes and signs become register constants; retain scale math and the original product/add chains | Intentionally skipped |
| exp-onecached | Each routed slot reads expert 0 in that layer, after validating the original route; retain all slots, rows, reduction work and loads | Intentionally skipped |
| hc-nodeq | Expanded Q8 HC gate code bytes become raw unsigned values; retain scale-byte reads, skip sign/scale decoding | Intentionally skipped |
| hc-constscale | Expanded Q8 HC gates use the fixed scale 1/256; retain scale-byte reads and signed code conversion | Intentionally skipped |
| exp-loadkeep | Original wide64 arithmetic with the diagnostic read-retention policy | Exact operator bytes and device oracle required |
| hc-loadkeep | Original HC gate arithmetic with the diagnostic scale-read retention | Exact operator bytes and device oracle required |

The last two controls prevent dead-load elimination from being mistaken for a
lookup or dequantization saving. Diagnostic IQ2 reads use volatile scalar global
loads for codes and metadata; HC retains its otherwise-unused F32 scale load
with volatile. Production is untouched. IQ4 down still uses its original vector
code loads, with retained half-scale reads. Compare nodeq/constgrid to
**exp-loadkeep**, and HC ablations to **hc-loadkeep**; also report those controls
against production. FMAs are not introduced: this lineage deliberately uses
separate multiply/add operations with FP contraction disabled.

The raw-byte views can create large or nonfinite activations. Only token-output
mismatch is exempt from fault classification. Numerical sticky errors, invalid
routes, device faults, memory limits and protocol failures still stop the job.
A stopped arm has no invented timing result.

Onecached is a repeated-address/cache hypothesis, not proof of DRAM residency.
Collapsing slots to one expert makes intra-call reuse likely; intervening layers
can still evict weights. Do not claim a hardware DRAM/cache split without
counters or further matched evidence.

## Safety and promotion refusal

[policy.py](policy.py) rejects every bundle/chain/submission/headline purpose and
any timing mode other than attribution. The native engine independently refuses
diagnostic selections outside attribution rank execution. Only the new packet
understands the new selection names. [tests](evidence/python-tests.log) exercise
the actual runner refusals, mismatches and length failures, and a complete
25-request mock worker that drains successfully despite expected mismatches.

[run_screen.py](run_screen.py) invokes the unchanged, hash-pinned shared v4-lanes
wrapper. The only hooks select the packet-local worker and add diagnostic labels
to successful summaries. Real placement admission, memory checks, lane protocol,
fault supervision, cooperative cancellation, teardown and release remain shared.
The compatibility directory name satisfies the shared audited-placement predicate;
its audit binds this binary and this packet's sources.

Shared v4 deliberately rejects non-exact quality reports **after** device
postflight and both locks have been released. The adapter recognizes only that
exact `screen quality incomplete` reporting refusal, retains the shared failed
quality report verbatim, and emits a separate diagnostic completion. It never
sets `exact_oracle=true` for mismatches or converts a safety failure to success.
Every view's seal and summaries carry `diagnostic_nonexact: true`, including the
exact controls. The flag describes the packet's excluded scope; the separate
`output_changed_by_design` field identifies actual ablations.

The diagnostic seal has an explicit startup/safety gate, not a forged passing
byte-fixture. Byte-identity gates are skipped for non-exact views. Production and
load-retention controls retain their CPU byte evidence. The standard shared seal
verifier still checks source, binary, gate, dispatch, memory and placement hashes.

## CPU evidence

- [Build receipt](build-device-receipt.json): serial GNU host and Intel SYCL
  compilation; no device execution; about 112 MB at the engine-build stage.
- [Production CPU gate](evidence/cpu-gates.json): parent packet75, control and
  two fresh instrumented miniature runs match 96 target fixtures, 24 tokens,
  draft proposals and state each. The inherited `parent64` label in its receipt
  names the actual packet75 binary recorded in the command/hash.
- [Operator gates](evidence/operators.json): GNU and Intel, two fresh runs each;
  exact load-retention controls, intentional raw/grid/scale differences, and
  invalid-route rejection even in onecached.
- [Full-shape startup](evidence/fullshape.json): all eight selections on both
  ranks, real allocation, preparation, snapshot and post-load draft constructor.
  Device memory uses synthetic address tokens. No payload reads or model
  arithmetic; about 4.2 MB of host backing per rank.
- [Real memory admission](evidence/fullshape-admission.json): all sixteen
  post-load censuses pass the unchanged gate. This specifically exercises
  `cpu-plans-must-exercise-device-startup-paths`.
- [Python tests](evidence/python-tests.log): scope refusals, mismatch handling,
  protocol failure, full mock worker/drain and report aggregation/identity tests.
- [Temporary queue plans](evidence/queue-plans.json): all eight views pass on
  each lane, invoking the real `--plan`. Live queues are untouched.

## Reporting and mechanism budgets

[report.py](report.py) validates the same lane, binary, selection, seals, ordered
12-prompt inputs, event identities and every token's comparison classification.
It sums all stages of a complete site call, takes each prompt's median and then
the median across prompts. Multiply sampled GDN calls by 18 and QSA calls by 6
for an **estimated** ms/half. Rank0 speculative and corrected work stay separate;
missing layers or paths remain missing. Control and instrumented arms both run
all prompts once, from reset, in one load per view. The diagnostic forces 128
tokens, including beyond EOS; it is not a natural-completion benchmark.

The report includes each site's ms/half versus production and signed budgets:
loadkeep minus nodeq (raw-read surrogate), loadkeep minus constgrid (IQ2 lookup/
sign work), constgrid minus nodeq (remaining decoding), production minus
onecached (repeated-address cache hypothesis), and the corresponding HC scale/
decode differences. Nodeq still contains activation reads, reductions and stores,
so it is not a pure copy measurement. Changed downstream activations and routes
can also affect timings. These are overlapping, non-additive ablation bounds;
negative deltas are retained. **Achievable lossless budgets remain unmeasured**
until an exact implementation is tested. No model tok/s projection is made.

[Coordinator commands](WINDOW.md). [Retention and rebuild](RETENTION.md).

[Final CPU audit](evidence/final-check.json) and
[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).
