#pragma once
// Batched-prefill kernel choices: tuned defaults plus alternatives kept for future work.
#include <cstdlib>
namespace prefill_switches {
// Tiled dense token-row kernels (kopt MultiplyTiled): activations staged once per block of 16 weight rows, each weight
// decoded once per token tile. Exact, but much slower as written (2026-10-24: 581-token prompt 18.7 s vs 9.7 s),
// most likely accumulator spills. Off by default; OWNRT_PREFILL_TILED=1 selects it.
inline bool tiled_rows(){static const bool on=[]{const char* e=std::getenv("OWNRT_PREFILL_TILED");return e&&e[0]=='1';}();return on;}
// Dense token-row kernels that decode each weight once for a small tile of 4 tokens, one weight row per subgroup
// (small register tiles, after vllm-xpu-kernels PR #22 `launch_linear<Rows,Tokens>`). Exact. At 16 rows per chunk
// (2026-10-24 profile) they win for kopt (16-bit weights 2.16 -> 1.80 ms/row) and the dense blocks (IQ4_XS 0.55 -> 0.39,
// Q5_K 0.68 -> 0.55), so those use them by default (OWNRT_PREFILL_SMALLTILE=0 turns them off). For p33 Q6_K/Q8_0 they
// lose (0.95 -> 1.15, 0.85 -> 0.97), so p33's DenseRows stays opt-in through OWNRT_PREFILL_REUSE=1. (A 16-token tile was
// slower everywhere.)
inline bool small_tile_rows(){static const bool on=[]{const char* e=std::getenv("OWNRT_PREFILL_SMALLTILE");return !e||e[0]!='0';}();return on;}
inline bool weight_reuse_rows(){static const bool on=[]{const char* e=std::getenv("OWNRT_PREFILL_REUSE");return e&&e[0]=='1';}();return on;}
}
