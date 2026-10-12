# Nonfinite GEMV inputs are not qualified

Packet 26's GEMV qualification uses finite weights and finite activations. Its
four fixture modes are varied finite values, signed zeros, finite subnormals,
and large/small finite values. Every output byte must match the unchanged
packet 18 kernel and its frozen CPU arithmetic. No tolerance or NaN
canonicalization is applied.

An additional synthetic diagnostic put mixed infinities and signed NaNs in
quantization scales. The unchanged packet 18 CPU baseline failed its own
separately compiled oracle: an IQ2 expert result was `0xffc0`, while the oracle
returned `0x7fc0`. Both are BF16 NaNs, but their bytes differ. Before a diagnostic
message was added, the full fixture binary first reported a Q6 projection
mismatch. The failure moving with compilation context is evidence that this
nonfinite NaN-sign behavior is not a qualified arithmetic identity. It is not
a candidate speed result or a reason to accept different bytes.

The failed source, binary/source hashes and exact mismatch are retained in
[evidence/gemv-nonfinite-diagnostic](../packet26-specialised/evidence/gemv-nonfinite-diagnostic/receipt.json).
Only a CPU mock ran. Device behavior remains unmeasured. Nonfinite GEMV inputs
must not be described as qualified by K1, including when a packet 25 candidate
is selected. Qualifying them later requires a separately reviewed, deterministic
arithmetic contract; the current baseline is unchanged.

The required route-NaN rejection fixtures are separate. They still run and must
match the reference core and packet 18 bytes exactly. Their gate was not changed.

Packet29 retains its own additional strict scalar diagnostic in
`expert-down-review-gates.json` and initial logs in
`evidence/expert-down-nonfinite-initial/`. Finite-input checks are separate from
nonfinite failures. No nonfinite failure is counted as an exactness pass.

Packet29's final independent diagnostic reports 31,416 finite comparisons per
process, all exact in four processes (GNU/Intel, two each). Mixed nonfinite
inputs remain unqualified: Intel reports 1,254 candidate-versus-R5 and 1,254
candidate-versus-scalar differences; R5-versus-scalar has zero differences in
this diagnostic. GNU reports zero differences. No failure was relabeled equal
and no kernel arithmetic was changed. See `expert-down-review-gates.json`.
