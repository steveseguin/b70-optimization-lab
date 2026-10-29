# SC117 service speed: closed arms (do not repeat without a new reason)

All were exact (byte-identical state/outputs) unless noted; "slower" is measured on the device. Engine profiles are
under `b-prefill/profiles/`; patches for removed code are kept there too.

| Arm | Result | Evidence |
|---|---|---|
| Codebook in local memory (IQ2_S experts) | no change | `research/kbench/experts.cpp` |
| Gate+up in one launch (experts) | exactly 2× one launch (throughput-bound) | `research/kbench/experts.cpp` |
| Software prefetch of next expert chunk | slower | `research/kbench/experts.cpp` |
| 32-bit block loop + register IQ4 levels in the gsq dense-block kernel | slower (IQ4_XS +58%, Q4_K/Q5_K +10%); reverted | profiles `24e2f02c`, `ab87aad0` |
| Head-shared GDN (8 subgroups × 4 rows, head values once) | 933 → 1397 µs per step | `profiles/negative-gdn-head-shared-8sg.patch` |
| Specialised GDN with subgroup stages | 933 → 2878 µs | `profiles/negative-gdn-specialised-subgroup-stages.patch` |
| Route in one subgroup per row | 627 → 951 µs | `profiles/negative-route-one-subgroup.patch` |
| Small-K rows per subgroup (K ≤ 640: 1 or 2 rows) | neutral / worse; switch `OWNRT_SMALLK_ROWS` kept | profiles `8b0037be-smallk*` |
| IQ4_NL levels by subgroup shuffle | 54 → 85 µs | `research/kbench/iq4nl_levels.cpp` |
| Draft-only Q4 head (packet83) | 40.60 → 40.15 tok/s; switch `OWNRT_DRAFT_HEAD_Q4` off | suite runs 2026-10-25 |
| Draft prefix 80,128 / 122,880 rows | 39.13 / 39.22 vs 39.42 at 91,392 | unit comment |
| HC BF16: 2 or 4 rows per subgroup in decode | slower cold | `research/kbench/hc.cpp` |
| Attention tiles: grouped KV heads / pipelined K loads / 256-lane work-groups | 914 → 2913 / 1079 / 1597 µs at 3K (opt-in switches) | `p49_qsa_kernel.hpp` comments |
| 22/26 layer split (after the small-op kernels) | 43.46 vs 44.13 at 23/25 | unit comment |
| 32-row prefill chunks | about 2% (kept) | unit |
| IQ3_XXS expert kernel: FMA accumulate / lane-contiguous 8 weights / 1–8 rows per subgroup / 32–256-lane work-groups / grid in local memory | 62 / 69 / 60–74 / 60–61 / 55 µs vs 60 (warm 56; adjacent experts 60; no grid read at all 51.5): instruction-bound in the per-weight decode, no single cause | `research/kbench/iq3xxs_rows.cpp` |
| GSQ HC combine+norm fusion (`OWNRT_GSQ_FUSE_NORM=1`, opt-in) | rank 0 state exact, rank 1 differs from layer 23 KV on; cause not localized; worth ≤2% | `main.cpp` plan() |
| HC gate+mix fused launch (`OWNRT_FUSE_MIX=1`, opt-in, exact): 4 strided rows per work-group / 8 indices × 4 streams per 1024-lane work-group | suite 0.982× / 1.003×: the removed 7.7 µs mix launch reappears as a slower gate kernel; per-launch profile times overstate fusion savings | `packet6-kopt/kernels.cpp` MultiplyMix |
| Exact TP2 on rank 1 (row split, expert placement by id or by slot) | 16.72–17.25 vs 16.73 ms one-card: gathers cost what splits save | research/tp/2026-10-25-exact-tp-closeout.md |
| Prompt-lookup (n-gram) guesses as a draft fallback | suite: 54% coverage at 29% precision; n≥3 matches 12% of positions at 54–60% (draft 76%); no confidence signal to arbitrate | CPU analysis 2026-10-25 on f32-suite-7649fc43d0fc token ids |
| IQ3_XXS expert gate/up (rank 1, 2026-10-26): packed logical lanes (4/8 per item, SG16/32), block-hoisted loads ± prefetch, grid in local memory, uniform index loads, index/sign bytes by subgroup shuffle | 61–93 / 70–96 / 63–66 / 70–80 / 106–119 µs vs engine 57 (read floor 19, ALU floor of the formulation 35) | `research/decode-experts/` (RESULT.md, kbench/) |
| IQ3_S / IQ2_S expert gate/up: packed logical lanes; 1, 2 or 8 rows per subgroup; work-group 1–8 subgroups | 57 / 44 vs 35 / 32; R1/R2/R8 slower; WG equal | `research/decode-experts/kbench/kopt_*.cpp` |
| Route: exact rank-count top ten (32 broadcasts + 160-candidate count) | 9.8 → 20.8 µs microbench, 15.0 → 23.6 µs in engine | `research/decode-experts/kbench/route2.cpp` |
| Four-card miss-stall mechanisms (2026-10-29, CPU trace replay, `tpts` servers): start the corrected half at rank 1's verdict / guess the correction on rank 0 / reuse corrected-half work / overlap it with rank 1's next half / free snapshot+rollback | a miss costs 10.08 ms (fit 9.87), 18.0% of suite decode; 9.41 ms of it is the corrected half (pure dependency). Zero-cost projections: early start 0.41%, post-miss draft 0.13%, rank-1 post-idle 0.18%, reuse 0, overlap 0, snapshot+rollback 2.48% (ceiling 3.19%); correction guess needs an M=2 rank-0 row (1.6x, packet166), rank 0 has no slack (paces 71% of hit cycles) | `research/tp/miss-stall-2026-10-29/analysis.json`, `analyze.py` |
