# Source-only expert candidate appraisal

The current class profile makes expert gate/up the next measured area. Selection
of a concrete format still awaits the narrow actual attribution result.

The existing expanded IQ3_XXS representation is lossless, but its ready-made GEMV
uses lane*8+j then a256-element stride. The current generic packed IQ3_XXS path
uses k=lane, lane+32, and so on. Different floating-point accumulation orders make
the expanded GEMV an unsuitable direct substitution for the exact current oracle.
Any consumer must preserve the current lane chain, SG32 tree and BF16 rounding.

AtK2560 an IQ3_XXS row expands from980 to2,980 bytes. Gate plus up for one expert
with640rows would occupy3,814,400 expanded bytes. Expanding all17layer pairs would
add22,282,240,000bytes, which is outside this two-card memory budget. A bounded
exact weight cache is a later design option: previous cache/publication mechanisms
exist, but the current facade requires complete packed banks and lacks an indirect
cache binding. That is more work than changing one packed decoding loop.

A smaller candidate, if attribution supports it, is blockwise IQ3_XXS decoding:
256elements per98-byte block, eight32-element sign/scale groups. Hoist the common
half-scale decode per block and reuse group fields while retaining every lane's
eight products in their existing order. It adds no resident weight expansion or
route changes. The compiler may already hoist some work; source plausibility is
not a measured benefit. Preserve original exact decoder equations, exceptional
behavior and live inputs, and check native output equality before any adoption.
No candidate code, build or GPU comparison is implied by this appraisal.
