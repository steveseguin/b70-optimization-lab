// The one-token routed expert kernels (slot-major RoutedIQ2XXSP ... RoutedIQ1SP, the plain decode step's
// expert gate + up and down launches at the six-card shapes) timed against their work-group count, and a
// candidate form that computes R rows per sub-group so each activation value is read once for R rows
// (RoutedIQ2XXSR), BITWISE against the production kernel. One card.
//   pair: gate + up in one launch (w2 / out2), 384 rows per expert (2304 / 6), 20 blocks (5120 columns)
//   down: per-slot x, 864 rows per expert (card 2's slice of 5120), 9 blocks (2304 columns)
// Experts in the bank: 384 (the model's count); each timed launch uses 6 distinct random experts, 16 id sets
// interleaved, mean over 5 passes of the 16 (the weights come from card memory, not the cache).
//
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_routed_m1.cpp -o $S/bench_routed_m1 -lze_loader
//   LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib $S/bench_routed_m1 [CARD]
//   ONLY=q2k,xxs,iq2s,iq3,iq2xs,iq1 selects formats for the sweep (q2k: layer 0's fast Q2_K down kernel against
//   the generic one, M = 1..16 tokens). Exit status 1 on any mismatch.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <numeric>
#include <random>
#include <string>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
#ifdef OWN_PCS
#include "pcs.hpp" // EU stall sampling (build with -DOWN_PCS -I pti/include -lpti_view; run as root)
#endif
using namespace ops41sycl;
using Ty = iq3::Type;

static constexpr unsigned NEXP = 384, NSET = 16, PASSES = 5, PAIR_ROWS = 384, DOWN_ROWS = 864;
static int g_fail = 0;

// ---- candidate: R rows of one (matrix, slot) per sub-group, x read once per block for all R ---------------
// Row j's sum is the production kernel's: the same element expressions ((db * mag) ^ sign) * x added in
// the same order (blocks, then groups g), then the same xor butterfly. Units u = (matrix, slot, row group);
// rows past `rows` in the last group are computed on row r0 and not stored.
template <unsigned NB, unsigned R> struct RoutedIQ2XXSR {
    static constexpr unsigned TAB = 2048;
    unsigned rows;
    bool per_slot_x;
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_xxs_grid, k >> 3, k & 7));
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), l8 = lane >> 3, j = lane & 7u;
        const unsigned ssh = 31u - 8u * l8 - j;
        const unsigned rot = (37u - 8u * l8) & 31u, j4 = j << 2;
        const char *tb = reinterpret_cast<const char *>(tab);
        constexpr size_t RB = ((size_t)NB * 70 + 15) & ~(size_t)15;
        constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NC = NB * 8, NCR = (NC + 31) / 32;
        const unsigned stride = (unsigned)(it.get_global_range(0) / 32);
        const unsigned ngr = (rows + R - 1) / R, nu = (w2 ? 2 : 1) * nsl * ngr;
        for (unsigned u = packed_row_id(it); u < nu; u += stride) {
            unsigned slot = u / ngr;
            const unsigned r0 = (u % ngr) * R;
            const uint8_t *wm = w;
            float *om = out;
            if (slot >= nsl) {
                slot -= nsl;
                wm = w2;
                om = out2;
            }
            const float *xs = x + (size_t)(slot / 6) * xtok + (per_slot_x ? (size_t)(slot % 6) * NB * 256 : 0);
            uint32_t wd[R][NR];
            float dbc[R][NCR];
            float sum[R];
#pragma unroll
            for (unsigned q = 0; q < R; ++q) {
                const unsigned r = r0 + q < rows ? r0 + q : r0;
                const uint8_t *row = wm + ((size_t)ids[slot] * rows + r) * RB;
                const uint32_t *rw = reinterpret_cast<const uint32_t *>(row);
#pragma unroll
                for (unsigned k = 0; k < NR; ++k) wd[q][k] = row_words<NW>(sg, rw, k, lane);
                chunk_scales<NB>(sg, lane, reinterpret_cast<const uint16_t *>(row + (size_t)NB * 68),
                                 reinterpret_cast<const uint32_t *>(row + (size_t)NB * 64), 0.25f, dbc[q]);
                sum[q] = 0;
            }
#pragma unroll
            for (unsigned blk = 0; blk < NB; ++blk) {
                const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
#pragma unroll
                for (unsigned g = 0; g < 8; ++g) {
                    const unsigned wl = blk * 16 + 2 * g, wh = wl + 1, c = blk * 8 + g;
#pragma unroll
                    for (unsigned q = 0; q < R; ++q) {
                        const uint32_t lo = sycl::select_from_group(sg, wd[q][wl / 32], wl % 32);
                        const uint32_t es = sycl::select_from_group(sg, wd[q][wh / 32], wh % 32);
                        const float db = sycl::select_from_group(sg, dbc[q][c / 32], c % 32);
                        const float mag = *reinterpret_cast<const float *>(tb + ((sycl::rotate(lo, rot) & 0x1FE0u) | j4));
                        const uint32_t sb = (es << ssh) & 0x80000000u;
                        const float v = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ sb);
                        sum[q] = sum[q] + v * xv[g];
                    }
                }
            }
#pragma unroll
            for (unsigned q = 0; q < R; ++q) {
                float s = sum[q];
                for (int w_ = 16; w_; w_ >>= 1) s += sycl::select_from_group(sg, s, (int)lane ^ w_);
                if (lane == 0 && r0 + q < rows) om[slot * rows + r0 + q] = s;
            }
        }
    }
};

// ---- candidate 3 (2026-11-11, strategy K2 / local-survey L2): packed logical lanes. Item i of a row carries the
// production kernel's lanes L = P i .. P i + P - 1 (one 8-weight grid entry when P = 8): the index byte, the table
// read (one float4 per 4 weights), the sign byte, the chunk scale and the x loads are shared over its P lanes, and
// each logical lane keeps its own sum, added in the same order (blocks, then groups g) with the same element
// expression ((db * mag) ^ sign) * x. The end replays the xor butterfly: levels 16 .. P across items (shuffles,
// own + partner as production), levels P / 2 .. 1 inside the item (lower lane first, only those feeding lane 0).
// P rows per sub-group (32 / P items per row). STAB: the sign masks come from a 256 x 8 table in local memory
// (one uint4 read per 4 weights) instead of a shift and a mask per weight.
template <unsigned NB, unsigned P, bool STAB = false, bool PF = false, bool XB = false> struct RoutedIQ2XXSK {
    // XB: the item's x for the whole block (8 groups x P floats) loaded at the block's start (pcs1b: the mul waits on
    // the x load issued just before it)
    static_assert(P == 2 || P == 4 || P == 8, "P logical lanes per item");
    // PF: block blk + 1's quant words, scale word and half are loaded while block blk is computed (pcs1: without it
    // a third of the samples wait for these loads at the top of each block)
    static constexpr unsigned TAB = STAB ? 4096 : 2048;
    unsigned rows;
    bool per_slot_x;
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < 2048; k += (unsigned)it.get_local_range(0)) {
            tab[k] = float(grid64_byte(iq3::iq2_xxs_grid, k >> 3, k & 7));
            if constexpr (STAB) reinterpret_cast<uint32_t *>(tab)[2048 + k] = (((k >> 3) >> (k & 7)) & 1u) << 31;
        }
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        constexpr unsigned IR = 32 / P; // items per row
        const unsigned lane = sg.get_local_linear_id(), q = lane / IR, i = lane % IR;
        const unsigned L0 = i * P, l8 = L0 >> 3, j0 = L0 & 7u;
        constexpr size_t RB = ((size_t)NB * 70 + 15) & ~(size_t)15;
        const unsigned stride = (unsigned)(it.get_global_range(0) / 32);
        const unsigned ngr = (rows + P - 1) / P, nu = (w2 ? 2 : 1) * nsl * ngr;
        for (unsigned u = packed_row_id(it); u < nu; u += stride) {
            unsigned slot = u / ngr;
            const unsigned r0 = (u % ngr) * P, rq = r0 + q, r = rq < rows ? rq : r0;
            const uint8_t *wm = w;
            float *om = out;
            if (slot >= nsl) {
                slot -= nsl;
                wm = w2;
                om = out2;
            }
            const uint8_t *row = wm + ((size_t)ids[slot] * rows + r) * RB;
            const uint32_t *rw = reinterpret_cast<const uint32_t *>(row);
            const uint32_t *scw = reinterpret_cast<const uint32_t *>(row + (size_t)NB * 64);
            const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 68);
            const float *xs = x + (size_t)(slot / 6) * xtok + (per_slot_x ? (size_t)(slot % 6) * NB * 256 : 0) + L0;
            float acc[P];
#pragma unroll
            for (unsigned jj = 0; jj < P; ++jj) acc[jj] = 0;
            sycl::uint4 nq[4];
            uint32_t nsw = 0;
            uint16_t nd = 0;
            if constexpr (PF) {
#pragma unroll
                for (unsigned k = 0; k < 4; ++k) nq[k] = reinterpret_cast<const sycl::uint4 *>(rw)[k];
                nsw = scw[0];
                nd = dp[0];
            }
#pragma unroll 1
            for (unsigned blk = 0; blk < NB; ++blk) {
                float d;
                uint32_t sw;
                uint32_t wq[16];
                if constexpr (PF) {
                    d = iq3::half(nd);
                    sw = nsw;
#pragma unroll
                    for (unsigned k = 0; k < 4; ++k)
#pragma unroll
                        for (unsigned e = 0; e < 4; ++e) wq[4 * k + e] = nq[k][e];
                    const unsigned bn = blk + 1 < NB ? blk + 1 : blk;
#pragma unroll
                    for (unsigned k = 0; k < 4; ++k) nq[k] = reinterpret_cast<const sycl::uint4 *>(rw + (size_t)bn * 16)[k];
                    nsw = scw[bn];
                    nd = dp[bn];
                } else {
                    d = iq3::half(dp[blk]);
                    sw = scw[blk];
#pragma unroll
                    for (unsigned k = 0; k < 4; ++k) {
                        const sycl::uint4 v = reinterpret_cast<const sycl::uint4 *>(rw + (size_t)blk * 16)[k];
                        wq[4 * k] = v[0];
                        wq[4 * k + 1] = v[1];
                        wq[4 * k + 2] = v[2];
                        wq[4 * k + 3] = v[3];
                    }
                }
                [[maybe_unused]] sycl::float4 xbk[XB ? 8 * P / 4 : 1];
                if constexpr (XB) {
#pragma unroll
                    for (unsigned g = 0; g < 8; ++g)
#pragma unroll
                        for (unsigned k = 0; k < P / 4; ++k)
                            xbk[g * (P / 4) + k] = *reinterpret_cast<const sycl::float4 *>(xs + (size_t)blk * 256 + g * 32 + 4 * k);
                }
#pragma unroll
                for (unsigned g = 0; g < 8; ++g) {
                    const uint32_t lo = wq[2 * g], es = wq[2 * g + 1];
                    const float db = (d * (0.5f + float((sw >> (4 * g)) & 15u))) * 0.25f;
                    const unsigned idx = (lo >> (8 * l8)) & 255u;
                    const float *xg = xs + (size_t)blk * 256 + g * 32;
                    float mg[P], xv[P];
                    uint32_t sm[P];
                    if constexpr (P == 2) {
                        const sycl::float2 m = *reinterpret_cast<const sycl::float2 *>(tab + idx * 8 + j0);
                        const sycl::float2 xx = *reinterpret_cast<const sycl::float2 *>(xg);
                        mg[0] = m[0], mg[1] = m[1], xv[0] = xx[0], xv[1] = xx[1];
                    } else {
#pragma unroll
                        for (unsigned k = 0; k < P / 4; ++k) {
                            const sycl::float4 m = *reinterpret_cast<const sycl::float4 *>(tab + idx * 8 + j0 + 4 * k);
                            sycl::float4 xx;
                            if constexpr (XB) xx = xbk[g * (P / 4) + k];
                            else xx = *reinterpret_cast<const sycl::float4 *>(xg + 4 * k);
#pragma unroll
                            for (unsigned e = 0; e < 4; ++e) mg[4 * k + e] = m[e], xv[4 * k + e] = xx[e];
                        }
                    }
                    if constexpr (STAB) {
                        const unsigned sbyte = (es >> (8 * l8)) & 255u;
                        const uint32_t *st = reinterpret_cast<const uint32_t *>(tab) + 2048 + sbyte * 8 + j0;
                        if constexpr (P == 2) {
                            const sycl::uint2 v = *reinterpret_cast<const sycl::uint2 *>(st);
                            sm[0] = v[0], sm[1] = v[1];
                        } else {
#pragma unroll
                            for (unsigned k = 0; k < P / 4; ++k) {
                                const sycl::uint4 v = reinterpret_cast<const sycl::uint4 *>(st)[k];
#pragma unroll
                                for (unsigned e = 0; e < 4; ++e) sm[4 * k + e] = v[e];
                            }
                        }
                    } else {
                        const uint32_t sb8 = es >> (8 * l8 + j0);
#pragma unroll
                        for (unsigned jj = 0; jj < P; ++jj) sm[jj] = (sb8 << (31 - jj)) & 0x80000000u;
                    }
#pragma unroll
                    for (unsigned jj = 0; jj < P; ++jj) {
                        const float v = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mg[jj]) ^ sm[jj]);
                        acc[jj] = acc[jj] + v * xv[jj];
                    }
                }
            }
#pragma unroll
            for (unsigned wv = 16; wv >= P; wv >>= 1)
#pragma unroll
                for (unsigned jj = 0; jj < P; ++jj) acc[jj] += sycl::select_from_group(sg, acc[jj], lane ^ (wv / P));
#pragma unroll
            for (unsigned wv = P / 2; wv; wv >>= 1)
#pragma unroll
                for (unsigned jj = 0; jj < wv; ++jj) acc[jj] = acc[jj] + acc[jj + wv];
            if (i == 0 && rq < rows) om[slot * rows + rq] = acc[0];
        }
    }
};

// ---- candidate 2: the production kernel with the next row's quant words and scale words loaded while the
// current row is computed (double-buffered registers). Same per-row arithmetic and order; only when the
// loads are issued changes.
template <unsigned NB> struct RoutedIQ2XXSPF {
    static constexpr unsigned TAB = 2048;
    unsigned rows;
    bool per_slot_x;
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_xxs_grid, k >> 3, k & 7));
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), l8 = lane >> 3, j = lane & 7u;
        const unsigned ssh = 31u - 8u * l8 - j;
        const unsigned rot = (37u - 8u * l8) & 31u, j4 = j << 2;
        const char *tb = reinterpret_cast<const char *>(tab);
        constexpr size_t RB = ((size_t)NB * 70 + 15) & ~(size_t)15;
        constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NC = NB * 8, NCR = (NC + 31) / 32;
        static_assert(NB <= 32);
        const unsigned stride = (unsigned)(it.get_global_range(0) / 32);
        const unsigned nt = (w2 ? 2 : 1) * nsl * rows;
        // row p -> its bytes, its output slot, x
        auto rowp = [&](unsigned p) {
            unsigned slot = p / rows;
            const unsigned r = p % rows;
            const uint8_t *wm = w;
            if (slot >= nsl) slot -= nsl, wm = w2;
            return wm + ((size_t)ids[slot] * rows + r) * RB;
        };
        uint32_t wd[NR], sw = 0;
        float dl = 0;
        unsigned p = packed_row_id(it);
        auto fetch = [&](unsigned q, uint32_t (&wq)[NR], float &dq, uint32_t &sq) {
            const uint8_t *row = rowp(q);
            const uint32_t *rw = reinterpret_cast<const uint32_t *>(row);
#pragma unroll
            for (unsigned k = 0; k < NR; ++k) wq[k] = row_words<NW>(sg, rw, k, lane);
            dq = lane < NB ? iq3::half(reinterpret_cast<const uint16_t *>(row + (size_t)NB * 68)[lane]) : 0.0f;
            sq = lane < NB ? reinterpret_cast<const uint32_t *>(row + (size_t)NB * 64)[lane] : 0u;
        };
        if (p < nt) fetch(p, wd, dl, sw);
        for (; p < nt; p += stride) {
            uint32_t wn[NR], swn = 0;
            float dln = 0;
            if (p + stride < nt) fetch(p + stride, wn, dln, swn);
            unsigned slot = p / rows;
            const unsigned r = p % rows;
            float *om = out;
            if (slot >= nsl) slot -= nsl, om = out2;
            const float *xs = x + (size_t)(slot / 6) * xtok + (per_slot_x ? (size_t)(slot % 6) * NB * 256 : 0);
            // chunk_scales' expressions from the fetched half scales and scale words
            float dbc[NCR];
#pragma unroll
            for (unsigned k = 0; k < NCR; ++k) {
                const unsigned c = 32 * k + lane, b = c / 8 < NB ? c / 8 : NB - 1;
                const float d = sycl::select_from_group(sg, dl, b);
                const uint32_t s = sycl::select_from_group(sg, sw, b);
                dbc[k] = (d * (0.5f + float((s >> (4 * (c & 7))) & 15u))) * 0.25f;
            }
            float sum = 0;
#pragma unroll
            for (unsigned blk = 0; blk < NB; ++blk) {
                const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
#pragma unroll
                for (unsigned g = 0; g < 8; ++g) {
                    const unsigned wl = blk * 16 + 2 * g, wh = wl + 1, c = blk * 8 + g;
                    const uint32_t lo = sycl::select_from_group(sg, wd[wl / 32], wl % 32);
                    const uint32_t es = sycl::select_from_group(sg, wd[wh / 32], wh % 32);
                    const float db = sycl::select_from_group(sg, dbc[c / 32], c % 32);
                    const float mag = *reinterpret_cast<const float *>(tb + ((sycl::rotate(lo, rot) & 0x1FE0u) | j4));
                    const uint32_t sb = (es << ssh) & 0x80000000u;
                    const float v = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ sb);
                    sum = sum + v * xv[g];
                }
            }
            for (int w_ = 16; w_; w_ >>= 1) sum += sycl::select_from_group(sg, sum, (int)lane ^ w_);
            if (lane == 0) om[slot * rows + r] = sum;
#pragma unroll
            for (unsigned k = 0; k < NR; ++k) wd[k] = wn[k];
            dl = dln;
            sw = swn;
        }
    }
};

// ---- harness ----------------------------------------------------------------------------------------------
static uint64_t sm64(uint64_t &s) {
    uint64_t z = (s += 0x9E3779B97F4A7C15ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}
template <Ty TY> uint8_t *packed_bank(sycl::queue &q, unsigned cols, size_t nrow, uint64_t seed) {
    constexpr auto L = iq3::layout(TY);
    const size_t nb = cols / L.elements, rb = nb * L.bytes, prb = pk41::packed_row_bytes(TY, cols);
    uint8_t *d = sycl::malloc_device<uint8_t>(nrow * prb, q);
    if (!d) {
        std::printf("FAIL cannot allocate %.0f MB of card memory\n", nrow * prb / 1e6);
        std::exit(1);
    }
    constexpr size_t CH = 4096;
    std::vector<uint8_t> src(rb), dst(CH * prb);
    for (size_t r0 = 0; r0 < nrow; r0 += CH) {
        const size_t n = std::min(CH, nrow - r0);
        for (size_t r = 0; r < n; ++r) {
            for (size_t i = 0; i < rb; i += 8) {
                const uint64_t v = sm64(seed);
                std::memcpy(&src[i], &v, std::min<size_t>(8, rb - i));
            }
            for (size_t b = 0; b < nb; ++b) {
                const uint16_t h = 0x1400 + (sm64(seed) & 0x3ff);
                src[b * L.bytes] = h & 255;
                src[b * L.bytes + 1] = h >> 8;
            }
            pk41::pack_row(TY, src.data(), dst.data() + r * prb, cols);
        }
        q.memcpy(d + r0 * prb, dst.data(), n * prb).wait();
    }
    return d;
}
static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
// as Backend41::launch_rows: 512 items (16 sub-groups) per work-group, positions / 16 work-groups capped at maxwg
template <typename K>
static sycl::event launch(sycl::queue &q, size_t npos, size_t maxwg, const K &k, const uint8_t *w, const float *x,
                          const uint32_t *ids, float *y) {
    size_t nwg = (npos + 15) / 16;
    if (maxwg && nwg > maxwg) nwg = maxwg;
    const K kk = k;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> lt(K::TAB, h);
        h.parallel_for(sycl::nd_range<1>(nwg * 512, 512),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kk(it, w, x, ids, y, &lt[0]); });
    });
}
struct Bank {
    const uint8_t *w1, *w2;
    const float *x;
    const uint32_t *ids; // NSET x 6
    float *o1, *o2;
    unsigned rows;
    bool down;
};
template <typename K> static K make(const Bank &b) {
    K k{b.rows, b.down};
    if (!b.down) {
        k.w2 = b.w2;
        k.out2 = b.o2;
    }
    return k;
}
// mean us per launch over PASSES x NSET launches (sets interleaved)
template <typename K> static double time_k(sycl::queue &q, const Bank &b, size_t npos, size_t maxwg) {
    const K k = make<K>(b);
    for (unsigned s = 0; s < NSET; ++s) launch(q, npos, maxwg, k, b.w1, b.x, b.ids + 6 * s, b.o1);
    q.wait();
    double sum = 0;
    for (unsigned p = 0; p < PASSES; ++p)
        for (unsigned s = 0; s < NSET; ++s) {
            auto e = launch(q, npos, maxwg, k, b.w1, b.x, b.ids + 6 * s, b.o1);
            e.wait();
            sum += ev_us(e);
        }
    return sum / (PASSES * NSET);
}
template <typename K> static std::vector<float> run_out(sycl::queue &q, const Bank &b, size_t npos, size_t maxwg, unsigned set) {
    const size_t n = (size_t)6 * b.rows;
    q.memset(b.o1, 0xff, n * 4);
    q.memset(b.o2, 0xff, n * 4).wait();
    launch(q, npos, maxwg, make<K>(b), b.w1, b.x, b.ids + 6 * set, b.o1).wait();
    std::vector<float> h(2 * n);
    q.memcpy(h.data(), b.o1, n * 4);
    q.memcpy(h.data() + n, b.o2, n * 4).wait();
    return h;
}

static const size_t WGS[] = {64, 72, 96, 112, 128, 144, 160, 192, 256, 0};

template <Ty TY, typename KP, typename KD> static void sweep(sycl::queue &q, const char *name, const float *x,
                                                             const uint32_t *ids, float *o1, float *o2) {
    uint8_t *g = packed_bank<TY>(q, 5120, (size_t)NEXP * PAIR_ROWS, 11);
    uint8_t *u = packed_bank<TY>(q, 5120, (size_t)NEXP * PAIR_ROWS, 12);
    Bank bp{g, u, x, ids, o1, o2, PAIR_ROWS, false};
    std::printf("%-7s pair (12 x %u rows, 20 blocks):", name, PAIR_ROWS);
    for (size_t wg : WGS) std::printf(" wg%zu %.1f", wg, time_k<KP>(q, bp, (size_t)12 * PAIR_ROWS, wg));
    std::printf(" us\n");
    sycl::free(g, q);
    sycl::free(u, q);
    uint8_t *d = packed_bank<TY>(q, 2304, (size_t)NEXP * DOWN_ROWS, 13);
    Bank bd{d, nullptr, x, ids, o1, o2, DOWN_ROWS, true};
    std::printf("%-7s down (6 x %u rows, 9 blocks): ", name, DOWN_ROWS);
    for (size_t wg : WGS) std::printf(" wg%zu %.1f", wg, time_k<KD>(q, bd, (size_t)6 * DOWN_ROWS, wg));
    std::printf(" us\n");
    std::fflush(stdout);
    sycl::free(d, q);
}

template <unsigned NB, unsigned R> static void cand(sycl::queue &q, const Bank &b, size_t base_wg) {
    using KP = RoutedIQ2XXSP<NB, ActF32>;
    using KR = RoutedIQ2XXSR<NB, R>;
    const size_t mats = b.down ? 1 : 2, npos = mats * 6 * b.rows, nunit = mats * 6 * ((b.rows + R - 1) / R);
    size_t bad = 0, tot = 0;
    for (unsigned s = 0; s < 4; ++s) {
        const auto a = run_out<KP>(q, b, npos, base_wg, s), c = run_out<KR>(q, b, nunit, 0, s);
        const size_t n = (size_t)6 * b.rows * mats;
        for (size_t i = 0; i < n; ++i) bad += std::memcmp(&a[i], &c[i], 4) != 0;
        tot += n;
    }
    std::printf("  R %u %s: %s %zu of %zu differ |", R, b.down ? "down" : "pair", bad ? "FAIL" : "PASS", bad, tot);
    g_fail += bad != 0;
    std::printf(" prod wg%zu %.1f |", base_wg, time_k<KP>(q, b, npos, base_wg));
    for (size_t wg : WGS) std::printf(" wg%zu %.1f", wg, time_k<KR>(q, b, nunit, wg));
    std::printf(" us\n");
    std::fflush(stdout);
}

// any candidate KK against production KP: units = positions of KK (rows / R or rows / P per (matrix, slot))
template <typename KP, typename KK> static void cand_k(sycl::queue &q, const Bank &b, size_t base_wg, unsigned per, const char *lbl) {
    const size_t mats = b.down ? 1 : 2, npos = mats * 6 * b.rows, nunit = mats * 6 * ((b.rows + per - 1) / per);
    size_t bad = 0, tot = 0;
    for (unsigned s = 0; s < 4; ++s) {
        const auto a = run_out<KP>(q, b, npos, base_wg, s), c = run_out<KK>(q, b, nunit, 0, s);
        const size_t n = (size_t)6 * b.rows * mats;
        for (size_t i = 0; i < n; ++i) bad += std::memcmp(&a[i], &c[i], 4) != 0;
        tot += n;
    }
    std::printf("  %s %s: %s %zu of %zu differ |", lbl, b.down ? "down" : "pair", bad ? "FAIL" : "PASS", bad, tot);
    g_fail += bad != 0;
    std::printf(" prod wg%zu %.1f |", base_wg, time_k<KP>(q, b, npos, base_wg));
    for (size_t wg : WGS) std::printf(" wg%zu %.1f", wg, time_k<KK>(q, b, nunit, wg));
    std::printf(" us\n");
    std::fflush(stdout);
}

template <unsigned NB> static void cand_pf(sycl::queue &q, const Bank &b) {
    using KP = RoutedIQ2XXSP<NB, ActF32>;
    using KF = RoutedIQ2XXSPF<NB>;
    const size_t mats = b.down ? 1 : 2, npos = mats * 6 * b.rows;
    size_t bad = 0, tot = 0;
    for (size_t wg : {96, 128})
        for (unsigned s = 0; s < 4; ++s) {
            const auto a = run_out<KP>(q, b, npos, wg, s), c = run_out<KF>(q, b, npos, wg, s);
            const size_t n = (size_t)6 * b.rows * mats;
            for (size_t i = 0; i < n; ++i) bad += std::memcmp(&a[i], &c[i], 4) != 0;
            tot += n;
        }
    std::printf("  prefetch %s: %s %zu of %zu differ |", b.down ? "down" : "pair", bad ? "FAIL" : "PASS", bad, tot);
    g_fail += bad != 0;
    for (size_t wg : {64, 96, 128, 192, 256})
        std::printf(" wg%zu prod %.1f pf %.1f", wg, time_k<KP>(q, b, npos, wg), time_k<KF>(q, b, npos, wg));
    std::printf(" us\n");
    std::fflush(stdout);
}

// ---- layer 0's Q2_K expert down rows (unpacked GGUF bytes): RoutedQ2KF<9> against RoutedGemvT<Q2_K, ActF32>,
// launched as Backend41::launch_sg (one sub-group per work-group), M tokens (nsl = 6 M slots, per-slot x,
// token stride xtok = 6 * 2304), bitwise, then timed
template <typename K> static sycl::event launch_sg(sycl::queue &q, size_t groups, const K &k, const uint8_t *w,
                                                   const float *x, const uint32_t *ids, float *y) {
    const K kk = k;
    return q.submit([&](sycl::handler &h) {
        h.parallel_for(sycl::nd_range<1>(groups * 32, 32),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kk(it, w, x, ids, y); });
    });
}
static void q2k_gate(sycl::queue &q) {
    constexpr unsigned COLS = 2304, NBQ = 9, MMAX = 16;
    const size_t nrow = (size_t)NEXP * DOWN_ROWS, rb = (size_t)NBQ * 84;
    uint8_t *w = sycl::malloc_device<uint8_t>(nrow * rb, q);
    float *x = sycl::malloc_device<float>((size_t)MMAX * 6 * COLS, q);
    uint32_t *ids = sycl::malloc_device<uint32_t>((size_t)NSET * 6 * MMAX, q);
    float *ya = sycl::malloc_device<float>((size_t)MMAX * 6 * DOWN_ROWS, q), *yb = sycl::malloc_device<float>((size_t)MMAX * 6 * DOWN_ROWS, q);
    if (!w || !x || !ids || !ya || !yb) {
        std::printf("FAIL cannot allocate the Q2_K bank\n");
        std::exit(1);
    }
    uint64_t seed = 21;
    {
        constexpr size_t CH = 8192;
        std::vector<uint8_t> h(CH * rb);
        for (size_t r0 = 0; r0 < nrow; r0 += CH) {
            const size_t n = std::min(CH, nrow - r0);
            for (size_t i = 0; i < n * rb; i += 8) {
                const uint64_t v = sm64(seed);
                std::memcpy(&h[i], &v, std::min<size_t>(8, n * rb - i));
            }
            for (size_t b = 0; b < n * NBQ; ++b) { // d, dmin: normal halves
                const uint16_t d = 0x1400 + (sm64(seed) & 0x3ff), dm = 0x1000 + (sm64(seed) & 0x3ff);
                std::memcpy(&h[b * 84 + 80], &d, 2);
                std::memcpy(&h[b * 84 + 82], &dm, 2);
            }
            q.memcpy(w + r0 * rb, h.data(), n * rb).wait();
        }
    }
    std::mt19937 rng(7);
    std::uniform_real_distribution<float> ux(-1.f, 1.f);
    std::vector<float> hx((size_t)MMAX * 6 * COLS);
    for (auto &v : hx) v = ux(rng);
    std::vector<uint32_t> hid((size_t)NSET * 6 * MMAX);
    for (auto &v : hid) v = rng() % NEXP;
    q.memcpy(x, hx.data(), hx.size() * 4);
    q.memcpy(ids, hid.data(), hid.size() * 4).wait();
    const unsigned xtok = 6 * COLS;
    size_t bad = 0, tot = 0;
    for (unsigned m : {1u, 2u, 3u, 5u, 16u})
        for (unsigned s = 0; s < 4; ++s) {
            const unsigned nsl = 6 * m;
            const size_t n = (size_t)nsl * DOWN_ROWS;
            const uint32_t *is = ids + (size_t)s * 6 * MMAX;
            q.memset(ya, 0xff, n * 4);
            q.memset(yb, 0xff, n * 4);
            launch_sg(q, n, RoutedGemvT<Ty::Q2_K, ActF32>{DOWN_ROWS, COLS, true, nsl, xtok}, w, x, is, ya);
            launch_sg(q, n, RoutedQ2KF<NBQ>{DOWN_ROWS, COLS, true, nsl, xtok}, w, x, is, yb).wait();
            std::vector<float> a(n), b(n);
            q.memcpy(a.data(), ya, n * 4);
            q.memcpy(b.data(), yb, n * 4).wait();
            for (size_t i = 0; i < n; ++i) bad += std::memcmp(&a[i], &b[i], 4) != 0;
            tot += n;
        }
    std::printf("Q2_K down (6 M x %u rows, 9 blocks), M = 1,2,3,5,16: %s %zu of %zu differ |", DOWN_ROWS,
                bad ? "FAIL" : "PASS", bad, tot);
    g_fail += bad != 0;
    for (unsigned m : {1u, 4u, 16u}) {
        const unsigned nsl = 6 * m;
        const size_t n = (size_t)nsl * DOWN_ROWS;
        double ta = 0, tb = 0;
        for (unsigned p = 0; p < PASSES + 1; ++p)
            for (unsigned s = 0; s < NSET; ++s) {
                const uint32_t *is = ids + (size_t)s * 6 * MMAX;
                auto ea = launch_sg(q, n, RoutedGemvT<Ty::Q2_K, ActF32>{DOWN_ROWS, COLS, true, nsl, xtok}, w, x, is, ya);
                ea.wait();
                auto eb = launch_sg(q, n, RoutedQ2KF<NBQ>{DOWN_ROWS, COLS, true, nsl, xtok}, w, x, is, yb);
                eb.wait();
                if (p) ta += ev_us(ea), tb += ev_us(eb); // pass 0 warms
            }
        std::printf(" M%u generic %.1f fast %.1f", m, ta / (PASSES * NSET), tb / (PASSES * NSET));
    }
    std::printf(" us\n");
    std::fflush(stdout);
    sycl::free(w, q);
    sycl::free(x, q);
    sycl::free(ids, q);
    sycl::free(ya, q);
    sycl::free(yb, q);
}

int main(int argc, char **argv) {
    const int card = argc > 1 ? std::atoi(argv[1]) : 0;
#ifdef OWN_PCS
    if (!pcs::begin()) return 2;
#endif
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const sycl::device dev = l0.at(card);
    const sycl::context ctx(dev);
    sycl::queue q(ctx, dev, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    std::printf("card %d %s\n", card, dev.get_info<sycl::info::device::name>().c_str());
    const std::string only = getenv("ONLY") ? getenv("ONLY") : "q2k,xxs,iq2s,iq3,iq2xs,iq1";
    auto want = [&](const char *f) { return ("," + only + ",").find(std::string(",") + f + ",") != std::string::npos; };

    std::mt19937 rng(5);
    std::uniform_real_distribution<float> ux(-1.f, 1.f);
    std::vector<float> hx(6 * 5120 + 64);
    for (auto &v : hx) v = ux(rng);
    std::vector<uint32_t> hid(NSET * 6);
    for (unsigned s = 0; s < NSET; ++s) {
        std::vector<uint32_t> all(NEXP);
        std::iota(all.begin(), all.end(), 0u);
        std::shuffle(all.begin(), all.end(), rng);
        std::copy(all.begin(), all.begin() + 6, hid.begin() + 6 * s);
    }
    float *x = sycl::malloc_device<float>(hx.size(), q);
    uint32_t *ids = sycl::malloc_device<uint32_t>(hid.size(), q);
    const size_t on = (size_t)6 * DOWN_ROWS + 256;
    float *o1 = sycl::malloc_device<float>(on, q), *o2 = sycl::malloc_device<float>(on, q);
    q.memcpy(x, hx.data(), hx.size() * 4);
    q.memcpy(ids, hid.data(), hid.size() * 4).wait();

#ifdef OWN_PCS
    { // stall samples of production IQ2_XXS gate + up and the packed-lane forms, launched back to back
        uint8_t *g = packed_bank<Ty::IQ2_XXS>(q, 5120, (size_t)NEXP * PAIR_ROWS, 11);
        uint8_t *u = packed_bank<Ty::IQ2_XXS>(q, 5120, (size_t)NEXP * PAIR_ROWS, 12);
        Bank bp{g, u, x, ids, o1, o2, PAIR_ROWS, false};
        const size_t npos = 12 * PAIR_ROWS;
        pcs::start();
        for (int r = 0; r < 20; ++r) {
            time_k<RoutedIQ2XXSP<20, ActF32>>(q, bp, npos, 128);
            time_k<RoutedIQ2XXSK<20, 4, false, false, true>>(q, bp, npos / 4, 0);
            time_k<RoutedIQ2XXSK<20, 8, false, false, true>>(q, bp, npos / 8, 0);
        }
        pcs::stop_print("Routed", 150, 24);
        return 0;
    }
#endif
    if (want("q2k")) q2k_gate(q);
    // candidate first (IQ2_XXS), then the production sweep
    if (want("xxs")) {
        uint8_t *g = packed_bank<Ty::IQ2_XXS>(q, 5120, (size_t)NEXP * PAIR_ROWS, 11);
        uint8_t *u = packed_bank<Ty::IQ2_XXS>(q, 5120, (size_t)NEXP * PAIR_ROWS, 12);
        Bank bp{g, u, x, ids, o1, o2, PAIR_ROWS, false};
        std::printf("IQ2_XXS candidates:\n");
        cand_k<RoutedIQ2XXSP<20, ActF32>, RoutedIQ2XXSK<20, 4, false, false, true>>(q, bp, 128, 4, "K4xb");
        cand_k<RoutedIQ2XXSP<20, ActF32>, RoutedIQ2XXSK<20, 4, true, false, true>>(q, bp, 128, 4, "K4sxb");
        cand_k<RoutedIQ2XXSP<20, ActF32>, RoutedIQ2XXSK<20, 4, false, true, true>>(q, bp, 128, 4, "K4pfxb");
        cand_k<RoutedIQ2XXSP<20, ActF32>, RoutedIQ2XXSK<20, 8, false, false, true>>(q, bp, 128, 8, "K8xb");
        cand_k<RoutedIQ2XXSP<20, ActF32>, RoutedIQ2XXSK<20, 4>>(q, bp, 128, 4, "K4");
        if (getenv("K_ONLY")) {
            sycl::free(g, q);
            sycl::free(u, q);
            uint8_t *d = packed_bank<Ty::IQ2_XXS>(q, 2304, (size_t)NEXP * DOWN_ROWS, 13);
            Bank bd{d, nullptr, x, ids, o1, o2, DOWN_ROWS, true};
            cand_k<RoutedIQ2XXSP<9, ActF32>, RoutedIQ2XXSK<9, 4, false, false, true>>(q, bd, 128, 4, "K4xb");
            sycl::free(d, q);
            std::printf("%s\n", g_fail ? "FAIL" : "PASS");
            return g_fail ? 1 : 0;
        }
        cand_pf<20>(q, bp);
        if (!getenv("PF_ONLY")) {
            cand<20, 2>(q, bp, 128);
            cand<20, 3>(q, bp, 128);
            cand<20, 4>(q, bp, 128);
        }
        sycl::free(g, q);
        sycl::free(u, q);
        uint8_t *d = packed_bank<Ty::IQ2_XXS>(q, 2304, (size_t)NEXP * DOWN_ROWS, 13);
        Bank bd{d, nullptr, x, ids, o1, o2, DOWN_ROWS, true};
        cand_pf<9>(q, bd);
        if (!getenv("PF_ONLY")) {
            cand<9, 2>(q, bd, 128);
            cand<9, 4>(q, bd, 128);
        }
        sycl::free(d, q);
        if (getenv("PF_ONLY")) return g_fail ? 1 : 0;
    }
    std::printf("production kernels, work-groups (wg0 = one sub-group per row, no cap):\n");
    if (want("xxs")) sweep<Ty::IQ2_XXS, RoutedIQ2XXSP<20, ActF32>, RoutedIQ2XXSP<9, ActF32>>(q, "IQ2_XXS", x, ids, o1, o2);
    if (want("iq2s")) sweep<Ty::IQ2_S, RoutedIQ2SP<20, ActF32>, RoutedIQ2SP<9, ActF32>>(q, "IQ2_S", x, ids, o1, o2);
    if (want("iq3")) sweep<Ty::IQ3_XXS, RoutedIQ3XXSP<20, ActF32>, RoutedIQ3XXSP<9, ActF32>>(q, "IQ3_XXS", x, ids, o1, o2);
    if (want("iq2xs")) sweep<Ty::IQ2_XS, RoutedIQ2XSP<20, ActF32>, RoutedIQ2XSP<9, ActF32>>(q, "IQ2_XS", x, ids, o1, o2);
    if (want("iq1")) sweep<Ty::IQ1_S, RoutedIQ1SP<20, ActF32, true>, RoutedIQ1SP<9, ActF32, true>>(q, "IQ1_S", x, ids, o1, o2);
    sycl::free(x, q);
    sycl::free(ids, q);
    sycl::free(o1, q);
    sycl::free(o2, q);
    std::printf("%s\n", g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
