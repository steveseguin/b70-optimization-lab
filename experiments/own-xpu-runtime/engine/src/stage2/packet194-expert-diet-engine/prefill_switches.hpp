#pragma once
// Batched-prefill kernel choices that are kept for future work but off by default.
#include <cstdlib>
namespace prefill_switches {
// Dense token-row kernels that decode each weight once for 16 tokens (kopt MultiplyRows, p33 DenseRows, dense-block
// rows). Exact, but slower on the B70 at 16 rows (2026-10-24 profile: F32 activation re-reads, not weight bytes,
// bound these GEMVs, and one subgroup per weight row loses parallelism). OWNRT_PREFILL_REUSE=1 selects them.
inline bool weight_reuse_rows(){static const bool on=[]{const char* e=std::getenv("OWNRT_PREFILL_REUSE");return e&&e[0]=='1';}();return on;}
}
