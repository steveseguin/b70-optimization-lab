# GDN gate, output projection and stream-injection authority

## Question and identity

Packet202 proved synthetic two-row qkv/z projections and causal convolution/GDN
recurrence. Its z projection was compared but not consumed by that recurrence
proof. Packet203 adds the selected gated normalization, output projection and
four-stream injection. Alpha/beta, convolution parameters, normalization gain,
residual streams and injection values remain synthetic fixture inputs. This
does not implement their upstream production projections or HC construction.

The [authority inventory](authority-inputs.json) pins 23 existing inputs: the
packet202 proof, selected sources, current production dispatch/census and
packet198 link receipt. It also verifies exact relevant host arithmetic bodies
between raw source and frozen packet198 headers. No model, device or service
operation was used to prepare this inventory. Source-to-object lineage is a
separate independent-review obligation; recorded object hashes are not new
device execution evidence.

## Outcome

Require byte equality for both rows at every new boundary, plus inherited
upstream checks. Use the actual selected serial implementation as authority,
with a separate two-row candidate path:

| Boundary | Two-row bytes | Required arithmetic |
| --- | ---: | --- |
| Gated normalization | 24,576 | 48 heads ×128, FP32 gain, fixed128 reduction, sigmoid(z), BF16 result |
| Split partials | 163,840 | 2×2560×8 FP32 slots; first4 live, last4 unchanged sentinel |
| Output projection | 10,240 | Q6_K K6144→2560, variant7, split4, BF16 output |
| Updated four streams | 40,960 | BF16 residual plus BF16 projection times the original injection factor |

The p201 census records 512 bytes for `blk.0.ssm_norm.weight` (128 FP32 gains)
and 20,766,720 expanded bytes for `blk.0.ssm_out.weight`. The latter is 2560
rows at8112 bytes per expanded Q6_K row. Split count changes accumulation
order, not the row encoding.

## What worked

The selected normalization is `p42.tiny.wg256`, implementation8, invoking
`p42tiny::cooperative_group<gated_norm>`. Each128-element head first computes
the original adjacent reduction tree of squared BF16 values and
`rsqrt(sum/128 + 1e-6)`. It evaluates `(x*inverse)*gain`, then multiplies by
`sigmoid(z)` and writes BF16 once. There is **no extra BF16 rounding of the
normalized value before the gate**. Gain flags8 select FP32 and do not add a
unit offset. A chunk may parallelize independent heads/rows, not reassociate
their reductions or substitute an approximate sigmoid.

The selected output is the frozen
`p49c::DenseKernel<Q6_K,6144,4,attention_combine>`. Each split retains its
original per-lane multiplication/addition sequence and SG32 tree. The four
results combine as `(p0+p1)+(p2+p3)`, then round to BF16. The injection uses
that rounded value:

`BF16(residual + projected_BF16 * (2 * sigmoid(inject_BF16 / 4)))`

Apply it once to each of four row-local streams. The previous BF16 residual,
injection row, projected row and stream stride must not be interchanged between
the two tokens. Read-only weights/gain may be shared; writable gated outputs,
partials, projections and stream regions must not overlap inputs or each other.

## What failed or remains uncertain

The frozen HOST_ONLY dense kernel calculates and combines its partials privately;
it does not populate device scratch. Therefore a partial-sum gate reconstructed
from the original `p49c::dense_lane` and tree is a CPU arithmetic reference,
not an observed device scratch capture. Checking its live4/sentinel4 layout is
still useful but must retain that distinction.

The raw dense operation computes projection/scratch even when inactive or in
error; only stream injection is guarded. Also,
`position_valid<attention_combine>` deliberately returns true. Packet203 must
enforce its two-position bound at the **whole-tail entry** before calling raw
operators. An inactive or already-failed entry must leave all tail buffers
unchanged; invalid position must set sticky error without writing outputs.
Existing active/error values and position must otherwise be preserved. This
CPU wrapper guard is not evidence of an additional raw device-kernel guard.

The synthetic controls must discriminate:

- Zeroing z must change gated values and resulting streams. This is the
  planned `z_ignored_differs` negative; it substitutes sigmoid(0), rather than
  literally removing the sigmoid multiplication.
- Skipping stream injection must leave different bytes from the valid result;
  unchanged initial residuals cannot pass as a completed branch.
- Feeding an unrounded FP32 projection into injection should fail comparison
  when the chosen fixture discriminates it. Require the observed difference
  before claiming that negative control passed.

All positive comparisons must cover nonzero distinct, identical, permuted,
rounding-sensitive and nonzero-state fixtures inherited from packet202. Their
real-model relevance comes from production arithmetic/layout identity, not from
synthetic inputs being a representative performance workload. There is no
serving-speed result here.

## Evidence and patches

Relevant source hooks, with full paths and SHA values in the inventory:

- `p42_cooperative.hpp` lines5–11: active/error and position guards;
  lines35–44: exact gated normalization body.
- `p42_submit.cpp` lines29–39 and62: selected host/device cooperative
  dispatch; lines43–54: extent, lifetime and alias requirements.
- `adapter.cpp` lines281–292: FP32 gain flags and gated-norm bindings.
- `p49c_kernel.hpp` lines85–104: ordered expanded dense lane;
  lines111–113: host epilogue guard; lines122–156: split4 host finish and
  device partial/finish paths. Frozen copies add prepared-submission wrappers;
  the inventory separately matches the host lane/finish arithmetic bodies.
- `p39_fused.hpp` lines50–60 and77–80: attention position exemption,
  BF16 stream-combine expression and four-stream indexing.

Tests should bind the current binary, compiler dependency closure, production
binding and retained five-case result. Running planner/binding controls does not
require repeating the numerical proof. A failed compile or numerical run must
retain its exact sources/logs before correction.

## When to revisit

After CPU byte gates and independent source review, the next integration step
still needs actual upstream HC and gate projections, FFN/MoE, QSA/PLE coverage,
whole-model causal scheduling, safe cache cadence and full persistent-state
comparison. Those are outside this packet. No root admission, device build or
performance claim follows from a synthetic tail pass alone.
