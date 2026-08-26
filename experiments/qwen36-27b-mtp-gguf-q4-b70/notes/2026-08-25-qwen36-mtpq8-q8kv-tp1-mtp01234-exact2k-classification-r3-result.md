# Qwen 3.6 embedded-Q8 Q8KV exact-2K classifier R3 result

Classification: Grade C, deterministic route divergence. Direct site authority
remains zero.

All 18 exact-2K requests passed their strict receipt gates with zero cached
tokens. The opening and closing MTP0 controls were each stable across three
repeats and identical across the temporal bracket, always producing
`e11b5a317688e28bf0cd4b1e1d234b72327feb06a435357ef846acc5344a620d`.
This rules out within-arm noise and temporal control drift for this bounded
packet.

Every candidate was also stable across its three repeats but diverged from the
bracketing controls at zero-based token index 73 (one-based position 74), where
the control token is 7888 and the candidate token is 4434. MTP1 produced
`15ae89335b6e0ad365cf9f9ad524d621befbaea3580940374943a7b2e02dcf72`
with 55 aligned positions different. MTP2, MTP3, and MTP4 all produced
`6177d7799a71763d852b589188137db878177ff878b600de0977a5182264b3b6`
with 54 aligned positions different.

Draft counters were repeat-stable and conserved for every candidate request:
MTP1 58/69 accepted/generated (0.84058), MTP2 72/109 (0.66055), MTP3
78/144 (0.54167), and MTP4 81/179 (0.45251). All 65 strict R3 checks,
all eight identity checks, and all six lifecycle cleanup gates passed.

The 99-interval decode measurements are preserved in the structured result:
16.085–16.104 tok/s across the controls, 25.750–25.777 for MTP1,
31.388–31.670 for MTP2, 32.569–32.914 for MTP3, and 31.630–31.947 for
MTP4. The preregistered packet explicitly gives these no direct speed or site
authority.

The raw root is
`/mnt/fast-ai/bench-results/qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-20260825-r3`.
Terminal SHA is
`ea7e3d23dd4409cd84c1f9558e64fca85135303c0b9b44793ac145719382192b`,
identity SHA is
`9a32a5c11bdea720cffa4bd4d52c607123f20a2e5e5750439eabc5800b534aef`,
and the complete 75-file inventory SHA is
`5c4421edcf63d5e94a4169abfc3e701689056dd01c6a18d1d222462a68edfcc1`.
Grade C classifies
the exact-2K phenomenon only; it does not itself authorize a curve, quality
claim, site cell, protected replacement, record, or LocalMaxxing submission.
