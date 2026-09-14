# Exact F32 diagnostic arithmetic — CPU gate 01

The new inactive `scripts/f32_difference.py` decodes finite binary32 words into
signed integer multiples of 2^-149. It rounds a maximum absolute integer
difference once to IEEE binary32 nearest, ties to even, with positive infinity
on overflow. Rounding the maximum once is valid because this rounding rule is
monotone. The reported Python float is constructed from the rounded significand
with `math.ldexp`; no hardware binary32 subtraction or cast is used.

Both signed zeros decode to integer zero. Raw-byte equality must remain the
acceptance gate: a signed-zero mismatch has zero numerical difference. NaNs,
infinities, invalid words, and invalid difference arguments are rejected.

The bounded standard-library test ran successfully on 2026-09-14:

```text
python3 -B -S experiments/ltx25-b70/scripts/test-f32-difference.py --output experiments/ltx25-b70/data/f32-difference-cpu-01.json
```

Seven test methods passed. Coverage includes signed zero, minimum subnormals,
the subnormal/normal boundary, exact cancellation to a subnormal, normal
midpoints with even/odd ties and significand carry across exponents, the finite
maximum, the overflow midpoint and its neighbors, and opposite finite extrema.
The receipt contains the test transcript, Python version, and source hashes.

- Helper SHA256: `2667349c13d28277f97b4623560c97fab6c9832823afb27f432b25c8177710d2`
- Test SHA256: `40743267fc52aee0054f69af215aff113fbefe9871969c1b85cddf32d54c1771`
- Receipt: `data/f32-difference-cpu-01.json`

This verifies the specified integer/IEEE arithmetic only. Equivalence to the
actual Torch runtime mode, native checkpoint comparison, and runtime speed are
untested. No Torch, model weights, device operations, server actions, or host
setting changes were involved. This makes no claim about the cause or recovery
of the existing kernel fault.
