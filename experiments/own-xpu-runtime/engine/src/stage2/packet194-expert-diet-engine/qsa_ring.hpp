#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
// OWNRT_QSA_RAW_RING=1 (lab 2026-10-26, default off; rank 1 only): each QSA layer's raw indexer-key buffer
// (blk.N.qsa.raw, context x 128 values, 33.5 MB in F32 at context 65536) becomes a 512-row ring.
//
// Why it is exact: qsa_append_pool is the buffer's only reader and writer (plan.hpp). A launch of T rows at positions
// [pos, pos+T) writes raw rows pos..pos+T-1, and it reads raw only for the earlier rows of the pools it completes:
// rows [4*(pos/4), pos), at most three of them. Rows older than those are never read again. T <= 256
// (ng::validate), so the at most T+3 rows that one launch touches are distinct modulo 512, and each read row was
// written by an earlier launch that the ring has not overwritten since (at most 259 newer rows). So every read returns
// the same bytes as with the full buffer, and every write and every output is unchanged. Only the storage of
// never-read-again rows is dropped.
#include <cstddef>
#include <cstdlib>
namespace qsaring {
inline bool enabled(){static const bool on=[]{const char* e=std::getenv("OWNRT_QSA_RAW_RING");return e&&e[0]=='1';}();return on;}
inline constexpr int rows=512;  // ring rows, a power of two >= 256 launch rows + 3 open-pool rows
inline constexpr int flag=128;  // ng::Shape flag of qsa_append_pool: raw row r lives at r & (rows-1)
inline int row(int r,int flags){return (flags&flag)?(r&(rows-1)):r;}
}
