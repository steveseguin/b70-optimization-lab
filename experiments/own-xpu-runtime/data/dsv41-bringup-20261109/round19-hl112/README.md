# hl112: prompt head layout with the slow card lighter (2026-11-13 23:59 - 2026-11-14 01:40, 200 W cap)

Why: under the owner's 200 W cap card 3 (0000:83) runs the prompt kernels ~12 % slower than the other cards and is
the critical card (round19-tlpx112). The prompt head layout (`OWN_TP_HEADS`, units of 4 heads, used for blocks of
>= 16 tokens) can move attention work between cards without changing any bits. tp112 binary, `hl112.sh`.

- Gate: 3K traces at px-512 vs runs/gm64/t3k_ref: both arms TRACE_IDENTICAL, IDS40_SAME.
- Every 3K answer (256 tokens) the same as runs/e52.

| arm | OWN_TP_HEADS (units of 4 heads per card) | 3K read (s) |
|---|---|---|
| D (default) | 3,3,3,3,2,2 | 5.23 / 5.26 |
| L1 | 3,3,2,2,3,3 (pairs 0-1, 4-5) | 5.01 / 5.06 (-4.0 %) |
| L2 | 3,3,3,2,3,2 (pairs 0-1, 2-3, 3-4) | 5.00 / 5.04 (-4.3 %) |

In plain words: giving the slow card fewer attention heads makes prompt reading ~4 % faster under the cap, same
answers. It is a cap-specific setting (uncapped, card 3 was one of the fast cards), so it stays a launch setting
(`OWN_TP_HEADS=... OWN_TP_HEADS_MIN=16`), not a source default. It combines with prt's token weights (card 3 gets
fewer tokens in the token splits, round19-prt / dsv41-work/prt).
