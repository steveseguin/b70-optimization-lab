// rux7 (2026-11-13): prompt routed-expert kernels that do less work per weight-token, BITWISE production's.
// Bench: tools/bench/bench_rux7.cpp (every output float against production's kernel; /home/steve/dsv41-work/rux7/README.md).
//
// 1. RoutedQ2KG<NB, MT, R, E, G, W, XP, RED, DL, WL>: layer 0's Q2_K routed down rows (GGUF layout, 84-byte blocks, the
//    rows not packed) for prompt blocks, on the expert groups (RUGrp, ExpertGroupM / PM) like the packed formats' forms.
//    Today these rows run RoutedQ2KF (sycl_v41.hpp): one sub-group per (slot, row), so every slot re-reads and re-decodes
//    the row and reads its 9 KB of x for that one row (4.67 ms per 256-token launch on card 2, ~3x the other downs).
//    Here a sub-group takes R consecutive rows of one group (one expert, up to MT slots): each row's block is read and
//    its values formed once per group, then every slot of the group reads its x block once for the R rows.
//      R   rows per tile (1, 2, 4; tiles only where rows % R == 0 and nsl >= tile_nsl, else single rows)
//      E   elements per lane per x read (8 = the block's 8 chunks in one read, 4 = two reads of 4)
//      G   register mode the launch pins (128 / 256), W = work-group cap (0: the backend's o.down_wg)
//      XP  x prefetch (L3, the SYCL prefetch extension, rux6's downs): block b + XP of slot s by sub-group s < cnt
//      RED 0: RoutedQ2KF's butterfly (select_from_group, xor 16 .. 1); 1: R2_XSUM (OWN_R2_XORP's halving-add lowering
//          when the build sets it, which xperm-4 found to give lane 0 the butterfly's sum)
//      DL  1: a block's 16 (dl, ml) pairs formed lane-parallel (lane k: sub-block k) and broadcast per chunk; 0: every
//          lane forms its chunk's pair (RoutedQ2KF's code)
//      WL  1: a block's 84 bytes read as 21 words by one message, bytes taken by sub-group shuffles; 0: RoutedQ2KF's
//          byte reads
//    Bit-identity, per output (slot i, row r): RoutedQ2KF's lane l sum is
//      sum = 0; for blocks b ascending, chunks cc = 0..7: sum = sum + (dl * float(q) - ml) * x_i[256 b + 32 cc + l]
//    with dl = d * float(sc & 15), ml = dmin * float(sc >> 4), sc = scale byte 2 cc + (l >= 16), q the 2-bit quant of
//    element 32 cc + l (byte 16 + 32 (cc / 4) + l, bits 2 (cc % 4)), d / dmin the block's halves; then the xor
//    butterfly and lane 0's store at out[slot * rows + r]. Here: the same operands (the same bytes of the same row,
//    the same half() conversions; DL computes d * float(sc & 15) in another lane with the same operands), the same
//    float operations in the same order (-ffp-contract=off: value = round(round(dl * q) - ml), then
//    sum = round(sum + round(value * x))), the same x address; accumulator (h, i) receives its updates in the same
//    (b, cc) order; only updates of DIFFERENT accumulators interleave; RED 0 is the same butterfly text. Which
//    sub-group runs a row changes nothing (each row's sum is whole in one sub-group); every slot's output is written
//    by exactly one group.
#pragma once
#include <type_traits>
#include <utility>
#include "stage2/packet3/kernels/sycl_v41_routed_rux6.hpp"

namespace ops41sycl {

template <unsigned NB, unsigned MT = 6, unsigned R = 2, unsigned E = 8, unsigned G = 128, unsigned W = 0, unsigned XP = 0,
          unsigned RED = 0, unsigned DL = 1, unsigned WL = 0>
struct RoutedQ2KG {
    static constexpr unsigned GRF = G;
    static constexpr unsigned WGCAP = W;
    static constexpr unsigned TAB = 16; // no table; a small local buffer keeps the backend's pinned-register launch path
    static constexpr size_t RB = (size_t)NB * 84;
    static_assert(MT >= 1 && MT <= RUGrp::CAP, "1 .. 16 slots per group");
    static_assert(R == 1 || R == 2 || R == 4, "rows per tile: 1, 2, 4");
    static_assert(E == 4 || E == 8, "elements per lane per x read: 4, 8");
    static_assert(XP <= 2 && RED <= 1 && DL <= 1 && WL <= 1, "XP 0..2, RED / DL / WL 0..1");
    unsigned rows;
    bool per_slot_x;
    NoRows ex{};
    const uint8_t *w2 = nullptr; // (not used: Q2_K is a down matrix only)
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    unsigned nexp = 0;
    unsigned tile_nsl = 96;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *grp, float *out,
                                     float *) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const unsigned nu = grp[0];
        const unsigned P = (unsigned)(it.get_global_range(0) / 32), p0 = packed_row_id(it);
        const unsigned nr_ = nu * rows;
        unsigned ntile = 0;
        if constexpr (R > 1) {
            const unsigned rmax = (nr_ + P - 1) / P, pc = P * (rmax / R);
            if (nsl >= tile_nsl && rows % R == 0) ntile = pc < nr_ / R ? pc : nr_ / R;
        }
        auto job = [&](auto rk, unsigned q_) {
            constexpr unsigned RR = decltype(rk)::value;
            const unsigned u = q_ / rows, r = q_ % rows;
            const unsigned cnt = grp[RUGrp::CNT + u];
            const uint32_t sl = lane < cnt ? grp[RUGrp::SLOT + u * RUGrp::CAP + lane] : 0u;
            const uint32_t xo = (sl / 6) * xtok + (per_slot_x ? (sl % 6) * (NB * 256) : 0u);
            const unsigned eid = grp[RUGrp::EXP + u];
            const uint8_t *ra = w + ((size_t)eid * rows + r) * RB;
            auto pf_x = [&](unsigned bp) { // rux6's down prefetch (XW 2): sub-group s < cnt asks for slot s's block bp
                const unsigned s_ = (unsigned)sg.get_group_linear_id();
                if (s_ < cnt) rux6::pf1k<0>(x + sycl::select_from_group(sg, xo, s_) + (size_t)bp * 256, lane);
            };
            if constexpr (XP > 0)
                for (unsigned bp = 0; bp < XP && bp < NB; ++bp) pf_x(bp);
            float sum[RR][MT];
#pragma unroll
            for (unsigned h = 0; h < RR; ++h)
#pragma unroll
                for (unsigned i = 0; i < MT; ++i) sum[h][i] = 0;
#pragma unroll 1
            for (unsigned b = 0; b < NB; ++b) {
                if constexpr (XP > 0)
                    if (b + XP < NB) pf_x(b + XP);
                // the RR rows' block b: scale bytes (lane k < 16: byte k), quant bytes (lane l: 16 + l and 48 + l), d, dmin
                uint32_t scl[RR], q0[RR], q1[RR];
                float d[RR], dm[RR];
                r2::sfor<RR>([&](auto hk) {
                    constexpr unsigned h = decltype(hk)::value;
                    const uint8_t *bk = ra + h * RB + (size_t)b * 84;
                    if constexpr (WL == 0) {
                        scl[h] = lane < 16 ? bk[lane] : 0u;
                        q0[h] = bk[16 + lane];
                        q1[h] = bk[48 + lane];
                        d[h] = iq3::half(iq3::u16(bk + 80));
                        dm[h] = iq3::half(iq3::u16(bk + 82));
                    } else { // rows are 756-byte, blocks 84-byte: every block starts on a 4-byte boundary
                        const uint32_t *bw = reinterpret_cast<const uint32_t *>(bk);
                        const uint32_t wd = lane < 21 ? bw[lane] : 0u;
                        const unsigned sh = 8 * (lane & 3u);
                        const uint32_t ws = sycl::select_from_group(sg, wd, lane >> 2);       // words 0-3 (lanes 0-15)
                        const uint32_t wa = sycl::select_from_group(sg, wd, 4 + (lane >> 2));  // bytes 16 + l
                        const uint32_t wb = sycl::select_from_group(sg, wd, 12 + (lane >> 2)); // bytes 48 + l
                        scl[h] = lane < 16 ? (ws >> sh) & 255u : 0u;
                        q0[h] = (wa >> sh) & 255u;
                        q1[h] = (wb >> sh) & 255u;
                        const uint32_t dd = sycl::select_from_group(sg, wd, 20); // bytes 80..83: d, dmin (little endian)
                        d[h] = iq3::half(dd & 0xFFFFu);
                        dm[h] = iq3::half(dd >> 16);
                    }
                });
                float dla[RR], mla[RR];
                if constexpr (DL)
                    r2::sfor<RR>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        dla[h] = d[h] * float(scl[h] & 15u);
                        mla[h] = dm[h] * float(scl[h] >> 4);
                    });
                // element 32 cc + lane of row h: RoutedQ2KF's value
                auto val = [&](auto hk, auto ck) -> float {
                    constexpr unsigned h = decltype(hk)::value, cc = decltype(ck)::value, hh = cc / 4, j = cc % 4;
                    float dl, ml;
                    if constexpr (DL) {
                        const float a0 = sycl::select_from_group(sg, dla[h], 8 * hh + 2 * j);
                        const float a1 = sycl::select_from_group(sg, dla[h], 8 * hh + 2 * j + 1);
                        const float m0 = sycl::select_from_group(sg, mla[h], 8 * hh + 2 * j);
                        const float m1 = sycl::select_from_group(sg, mla[h], 8 * hh + 2 * j + 1);
                        dl = lane < 16 ? a0 : a1;
                        ml = lane < 16 ? m0 : m1;
                    } else {
                        const unsigned s0 = sycl::select_from_group(sg, scl[h], 8 * hh + 2 * j);
                        const unsigned s1 = sycl::select_from_group(sg, scl[h], 8 * hh + 2 * j + 1);
                        const unsigned sc = lane < 16 ? s0 : s1;
                        dl = d[h] * float(sc & 15);
                        ml = dm[h] * float(sc >> 4);
                    }
                    const unsigned q = ((hh ? q1[h] : q0[h]) >> (2 * j)) & 3;
                    return dl * float(q) - ml;
                };
                r2::sfor<8 / E>([&](auto ek) {
                    constexpr unsigned e0 = decltype(ek)::value * E;
                    float v[RR][E];
                    r2::sfor<E>([&](auto gk) {
                        constexpr unsigned g = decltype(gk)::value;
                        r2::sfor<RR>([&](auto hk) {
                            constexpr unsigned h = decltype(hk)::value;
                            v[h][g] = val(hk, std::integral_constant<unsigned, e0 + g>{});
                        });
                    });
#pragma unroll
                    for (unsigned i = 0; i < MT; ++i) {
                        if (i < cnt) {
                            const sycl::vec<float, E> xv =
                                sg_bloadN<E>(sg, x + sycl::select_from_group(sg, xo, i) + (size_t)b * 256 + e0 * 32);
#pragma unroll
                            for (unsigned g = 0; g < E; ++g)
#pragma unroll
                                for (unsigned h = 0; h < RR; ++h) sum[h][i] = sum[h][i] + v[h][g] * xv[g];
                        }
                    }
                });
            }
#pragma unroll
            for (unsigned i = 0; i < MT; ++i) {
                if (i < cnt) {
                    const unsigned slot = sycl::select_from_group(sg, sl, i);
                    r2::sfor<RR>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        float s = sum[h][i];
                        if constexpr (RED) {
                            R2_XSUM(s);
                        } else {
                            for (int w_ = 16; w_; w_ >>= 1) s += sycl::select_from_group(sg, s, (int)lane ^ w_);
                        }
                        if (lane == 0) out[slot * rows + r + h] = s;
                    });
                }
            }
        };
        if constexpr (R > 1)
            for (unsigned q_ = p0; q_ < ntile; q_ += P) job(std::integral_constant<unsigned, R>{}, R * q_);
        for (unsigned q_ = R * ntile + p0; q_ < nr_; q_ += P) job(std::integral_constant<unsigned, 1>{}, q_);
    }
};

// rux7-1 pick for layer 0's Q2_K down (OWN_RUX7 bit 1; MT 6 groups). bench_rux7 on card 1 under the 200 W cap, real
// blk.0 rows, real 3K picks (out/run-q1a.txt, out/run-q2a.txt; every float equal to RoutedQ2KF's): 256 tokens
// RoutedQ2KF 4856.2 -> 1624.0 us (-66.6 %), 512 tokens 9968.1 -> 3088.1 us (-69.0 %); 2-row tiles at 128 registers, the
// block's 8 chunks per x read, L3 prefetch of x one block ahead, R2_XSUM, the scale pairs formed lane-parallel.
// Slower: R1 (-40 %), R4 at 128 (spills) or 256 registers (-47 .. -53 %), E4, word reads of the block (WL 1), 256 registers.
// Rux7Q2KPick<NB, 0>: the same without the x prefetch (OWN_RUX7 bit 2; bench -61.5 %).
template <unsigned NB, unsigned XP_ = 1> struct Rux7Q2KPick {
    static constexpr unsigned R = 2, E = 8, G = 128, W = 0, XP = XP_, RED = 1, DL = 1, WL = 0;
};
template <unsigned NB, typename P = Rux7Q2KPick<NB>>
using Rux7Q2K = RoutedQ2KG<NB, 6, P::R, P::E, P::G, P::W, P::XP, P::RED, P::DL, P::WL>;

} // namespace ops41sycl
