# Packet47 QSA arithmetic identities

The existing record remains `iq3-p17-detmath-v2`, with its historical QSA
probability-before-value reduction. Nothing in packet45 or packet46 is changed.
Packet47 compares an order-preserving implementation first. A speed improvement
for that implementation needs no oracle rebase. Its aligned 32-token subtrees
retain every original odd-tail `+0` and stop at the original root depth.

The alternative has a separate proposed operator identity,
`iq3-p47-qsa-split32-v1`. It is exact only against the new CPU reference below.
It is not claimed bit-identical to the old record, a new full-model oracle, or
a measured quality-preserving end-to-end implementation. The owner's packet47
instruction authorizes preparing this identity; adopting it in the engine still
requires its device gates and a new complete CPU-reference/full-model gate.
The [October 11 arithmetic rebase](../../../../notes/2026-10-11-first-device-answer-and-arithmetic-v2.md)
is the precedent for keeping old and new identities separate.

## Fixed arithmetic

All inputs, KV and final output remain BF16. Scores, sums and weighted value
partials are binary32. Ordinary multiplication and addition are separate;
`-fno-fast-math -ffp-contract=off -fno-associative-math` is required. The lab's
deterministic `detmath::exp` and sigmoid arithmetic are retained, including
their explicitly specified fused operations. No platform exponential is used.

For each row and each of 24 query heads, `kh = head / 12` selects one of two
KV heads. The selected-token order comes from the existing selector. It is
neither sorted by token position nor repartitioned according to device size.

1. Split `b` contains selected indices `32*b` through `32*b+31`.
2. Each score is the adjacent 256-leaf tree of `Q[d] * K[d]`, divided by 16.
3. A split's maximum is visited in increasing selected-index order. For every
   valid token, compute `e = detmath::exp(score - split_max)`.
4. The split denominator is the adjacent 32-leaf tree of `e`. A missing leaf
   is positive zero. All five lower reduction levels execute, even when the
   last split has fewer than 32 valid tokens.
5. For each value component, the split numerator is the same 32-leaf tree of
   `e * V[d]`; missing leaves are again positive zero.
6. Visit split maxima in increasing split-index order to obtain `global_max`.
   Compute `factor[b] = detmath::exp(max[b] - global_max)`.
7. The combined denominator is the adjacent tree of `sum[b] * factor[b]`.
   The combined numerator for each component is the same tree of
   `partial_value[b,d] * factor[b]`. The upper tree stops at
   `ceil(log2(number_of_splits))` levels, adding positive zero for a missing
   right child. Divide the numerator by the denominator once.
8. Round that value to BF16, multiply by the existing gate sigmoid, and round
   the output to BF16, preserving both historical rounding boundaries.

The changed normalization order changes binary32 rounding. The fixed tree
does not depend on the number of executing work-groups, subgroups, cards or
compute units. The gate emulates reverse split/head/row execution as an
independent scheduling check. Actual device scheduling independence remains
subject to E1/E2 and the fresh-process comparison.

## CPU gates and limits

`qsa_reference.hpp` implements the scalar reference. `cpu_test.cpp` independently
constructs a recursive tree and a differently scheduled split workspace. It
compares every raw output byte and every pre-gate binary32 byte. For the old
identity it also compares the inherited `ng::cpu` score, probability and output
buffers. That generic CPU oracle fills unused score slots with negative
infinity; the selected old device implementation may leave unused scratch
untouched. Final output and valid score/probability entries define arithmetic
agreement; a native full-buffer check must respect each implementation's
declared scratch-write extent.

The CPU matrix covers the five requested populated contexts at M=1 and M=2,
two changing deterministic seeds, selected counts up to 2,051, boundaries at
1/2/3/31/32/33/63/64/65, signed zeros/tied scores and large finite scores.
It also exhaustively proves the old blocked sum for every length 1..2,051
with cancellation and negative-zero leaves. Context denotes the occupied
count of the final row; at M=2, row 0 uses context-1 and row 1 uses context.
Fixtures have shuffled whole-pool ranking and append unpooled tail tokens;
they contain no model weights. Two fresh processes run under GNU and two
under Intel, with no accelerator runtime linked or initialized.

`cpu-gates.json` binds each process, compiler, source hash, binary hash, raw
comparison log and compressed raw output. The raw stream contains, per case,
the historical BF16 output, new BF16 output, and new pre-gate binary32 output,
in row/head/component order. C++ compares uncompressed bytes before retention.
Uncompressed bytes are SHA256-verified after gzip retention and removed only
after that check. The corresponding receipt records the uncompressed hash.

Old/new differences report maximum absolute difference and float32 ULP distance
both before gating and after BF16 output rounding. BF16 outputs are decoded to
float32 for this ULP metric, so one ordinary BF16 step is 65,536 float32 ULPs.
ULP distance can become very large around cancellation/zero; the absolute
difference is also reported. These are synthetic operator differences.
**Logits, model answers, semantic quality and full-model determinism are not
measured by this packet's CPU fixtures.** Nonfinite model-input behavior is
not qualified by the finite numerical fixture gate.

```bash
P47=experiments/own-xpu-runtime/stage2/packet47-qsa-attn
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P47/cpu_gate.py" build
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P47/cpu_gate.py" test
```

Device exactness and speed are pending the coordinator's E1/E2 and T1/T2.
CPU agreement does not establish GPU speed or satisfy a full-model promotion
gate, and it does not authorize replacing the historical record identity.
