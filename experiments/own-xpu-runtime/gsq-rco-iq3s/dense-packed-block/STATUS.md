# Dense packed block candidate status

**Historical internal parity only:** the [recurrent dtype finding](../reference-cpu/RECURRENT-DTYPE.md)
shows extra BF16 recurrent matrix rounding relative to theF32 reference. Preserve
the measured results, but do not infer no added quality loss from them. A new
precision-corrected numerical baseline is required before further acceleration.

The [full-engine qualification](engine/operating/launch-b/RESULT.md) passes all24
original token/state arms and54 independent bundle readbacks. This binary is the
current qualified short-screen engine:19.611 target-only /28.138 MTP tokens/s,
unchanged acceptance, precision and device allocation. Broader task coverage is
next; the result remains an internal128-output resident screen.

[CPU proof](CPU-RESULT.md) passes223,685 exact checks and42 refusals. The
[three-format micro](micro/RESULT.md) passes84 native comparisons with positive
physical contact and safe closure. Original sources and unexecuted launch-A
lineage remain preserved; launch-B corrects acknowledged storage accounting.
