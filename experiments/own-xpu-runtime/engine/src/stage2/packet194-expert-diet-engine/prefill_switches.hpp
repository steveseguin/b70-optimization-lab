#pragma once
// Batched-prefill kernel choices: tuned defaults plus alternatives kept for future work.
#include <cstdlib>
namespace prefill_switches {
// Tiled dense token-row kernels (kopt MultiplyTiled): activations staged once per block of 16 weight rows, each weight
// decoded once per token tile. Exact, but much slower as written (2026-10-24: 581-token prompt 18.7 s vs 9.7 s),
// most likely accumulator spills. Off by default; OWNRT_PREFILL_TILED=1 selects it.
inline bool tiled_rows(){static const bool on=[]{const char* e=std::getenv("OWNRT_PREFILL_TILED");return e&&e[0]=='1';}();return on;}
// Dense token-row kernels that decode each weight once for 16 tokens with one subgroup per weight row (kopt
// MultiplyRows, p33 DenseRows, dense-block rows). Exact, but slower on the B70 at 16 rows (2026-10-24 profile: F32
// activation re-reads, not weight bytes, bound these GEMVs, and one subgroup per weight row loses parallelism).
// OWNRT_PREFILL_REUSE=1 selects them where no tiled kernel applies.
inline bool weight_reuse_rows(){static const bool on=[]{const char* e=std::getenv("OWNRT_PREFILL_REUSE");return e&&e[0]=='1';}();return on;}
}
