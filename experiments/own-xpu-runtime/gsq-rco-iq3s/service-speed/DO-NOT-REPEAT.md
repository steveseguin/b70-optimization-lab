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
