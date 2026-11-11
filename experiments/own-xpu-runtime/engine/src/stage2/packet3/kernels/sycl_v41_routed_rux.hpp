// Row-tiled expert-major routed kernels for prompt blocks ("rux", 2026-11-11), BITWISE RoutedU3's outputs
// (sycl_v41_routed_r2.hpp) on the same groups (RUGrp / ExpertGroupM, sycl_v41.hpp).
// Bench: tools/bench/bench_rux.cpp (production's selectors RoutedIQ*SU against these, every output float).
//
// Why: in prompt blocks of 16-256 tokens a RoutedU3 launch costs about the same per slot at every block size
// (pp92 profiles): each (row, slot) re-reads that slot's whole x (20 KB for 5,120 columns) through the cache port,
// about 1 KB per row, block and slot, more than the multiplies need (bench: ~1.8 us per slot of a 768-row gate + up
// launch, about 2.6x the mul + add time). RoutedUT<F, MT, EX, SPT, R, E, XA, G> gives a sub-group R consecutive
// rows of one expert (one group, one matrix), so each x load feeds R rows' FMA chains: x bytes, load messages and
// address work per (row, slot) drop by R. The R rows' values of E elements per lane (F::wv, the RU3 decoders,
// unchanged) are decoded once per sub-block, then per slot one sg_bloadN<E> of those E x values (the same floats
// production's sg_bloadN<8> hands lane l: x[256 b + 32 g + l]) and the R x E products.
//   G   the launch pins the register mode (backend launch_rows: RowsGrfK; 0 = the build's automatic choice, which
//       picks 256 for R = 2 and halves the threads: R = 2 at 256 loses, at 128 wins with a few values in scratch)
//   XA  2: slot i + 1's x is asked for before slot i's products, slot 0's before the decode (nested blocks, so each
//       loaded value is defined where it is used); 0: each slot's load right before its products (RoutedU3's order)
// Shipped (RuxPick below): R = 2, E = 8, XA = 0, G = 128, and R = 4, E = 8, XA = 2, G = 256 for two down formats at
// MT 6. Tried and slower (bench_rux, 2026-11-11): E < 8 (more waited loads per row), R = 4 at 128 registers (spills),
// all of a sub-block's slot loads first (the compiler spills tens of KB).
//
// Bit-identity, per output (slot i, row r): production's accumulator is
//   sum = 0; for blocks b ascending, for g = 0..7: sum = sum + v[r][b][g] * x_i[256 b + 32 g + lane]
// then the xor butterfly (16, 8, 4, 2, 1 via select_from_group) and lane 0's store at om[slot * rows + r].
// Here v[r][b][g] is the same F::wv<8 bb + g> on the same per-segment state (F::row / unit / seg, the same
// code), x the same address, and accumulator (r, i) receives the same mul and add in the same (b, g) order:
// the sub-blocks only interleave the updates of DIFFERENT accumulators (other rows, other slots). Same
// butterfly, same store. Which sub-group runs a row changes nothing (each row's sums are whole in one
// sub-group). Extra rows (EX) run first, outside the row loop, as RoutedU3 (R2_EX_ROWS).
//
// Schedule (as RoutedU3's PAIRS): tiles of R rows first, ntile <= P * (rmax / R) where rmax = RoutedU3's rows per
// sub-group, so no sub-group runs more rows than there; then the remaining rows one by one. Tiles only when
// nsl >= tile_nsl (the backend's minimum block size) and rows % R == 0; otherwise every row is a single (exactly
// RoutedU3's loop with E-element sub-blocks).
#pragma once
#include <type_traits>
#include <utility>
#include "stage2/packet3/kernels/sycl_v41_routed_r2.hpp"

namespace ops41sycl {

template <typename F, unsigned MT, typename EX = NoRows, unsigned SPT = 6, unsigned R = 2, unsigned E = 8, unsigned XA = 0,
          unsigned G = 0>
struct RoutedUT {
    static constexpr unsigned GRF = G; // 0: the build's automatic register mode; 128 / 256: the launch pins it
    static_assert(MT >= 1 && MT <= RUGrp::CAP, "1 .. 16 slots per group");
    static_assert(R == 1 || R == 2 || R == 4, "rows per tile: 1, 2, 4");
    static_assert(E == 1 || E == 2 || E == 4 || E == 8, "elements per lane per x load: 1, 2, 4, 8");
    static_assert(XA == 0 || XA == 2, "x loads: 0 = each slot's before its products, 2 = one slot ahead");
    static constexpr unsigned TAB = F::TAB, NB = F::NB, SPU = F::SPU, NS = F::NS;
    static constexpr unsigned NFU = (NB / 4) / SPU; // units whose segments all have 4 blocks (run-time loop)
    unsigned rows; // per-expert rows
    bool per_slot_x;
    EX ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    unsigned nexp = 0;      // not read (as RoutedU3)
    unsigned tile_nsl = 96; // tiles only when nsl >= tile_nsl (96 = blocks of >= 16 tokens)
    template <unsigned N> [[gnu::always_inline]] static inline sycl::vec<float, N> xload(sycl::sub_group sg, const float *p) {
        if constexpr (N == 1) return sycl::vec<float, 1>(sg_bload(sg, p));
        else return sg_bloadN<N>(sg, p);
    }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *grp,
                                     float *out, float *tab) const {
        F::fill(it, tab);
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const F f(lane, tab);
        const unsigned nu = grp[0];
        const unsigned P = (unsigned)(it.get_global_range(0) / 32), p0 = packed_row_id(it);
        const unsigned nr_ = (w2 ? 2 : 1) * nu * rows;
        unsigned ntile = 0;
        if constexpr (R > 1) {
            const unsigned rmax = (nr_ + P - 1) / P, pc = P * (rmax / R);
            if (nsl >= tile_nsl && rows % R == 0) ntile = pc < nr_ / R ? pc : nr_ / R; // at most rmax rows per sub-group
        }
        // extra rows first, continuing the jobs' round (RoutedU3's R2_EX_ROWS with its job count)
        if constexpr (!std::is_same_v<EX, NoRows>) {
            const unsigned nj = ntile + (nr_ - R * ntile);
            for (unsigned k_ = (p0 + P - nj % P) % P; k_ < ex.n(); k_ += P) ex.row(sg, lane, k_);
        }
        // rows q_ .. q_ + RR - 1 of one group and matrix
        auto job = [&](auto rk, unsigned q_) {
            constexpr unsigned RR = decltype(rk)::value;
            unsigned u = q_ / rows;
            const unsigned r = q_ % rows;
            const uint8_t *wm = w;
            float *om = out;
            if (u >= nu) {
                u -= nu;
                wm = w2;
                om = out2;
            }
            const unsigned cnt = grp[RUGrp::CNT + u];
            const uint32_t sl = lane < cnt ? grp[RUGrp::SLOT + u * RUGrp::CAP + lane] : 0u;
            const uint32_t xo = (sl / SPT) * xtok + (per_slot_x ? (sl % SPT) * (NB * 256) : 0u);
            const unsigned eid = grp[RUGrp::EXP + u];
            const uint8_t *ra = wm + ((size_t)eid * rows + r) * F::RB;
            typename F::Row rr[RR];
            r2::sfor<RR>([&](auto hk) { f.row(sg, ra + decltype(hk)::value * F::RB, rr[decltype(hk)::value]); });
            float sum[RR][MT];
#pragma unroll
            for (unsigned h = 0; h < RR; ++h)
#pragma unroll
                for (unsigned i = 0; i < MT; ++i) sum[h][i] = 0;
            // NBS blocks of segment S: per sub-block of E elements the RR rows' values once, then every slot
            auto blocks = [&](auto nbs, unsigned S, const typename F::Sg (&sgs)[RR]) {
                r2::sfor<decltype(nbs)::value>([&](auto bk) {
                    constexpr unsigned bb = decltype(bk)::value;
                    const size_t bo = (size_t)(4 * S + bb) * 256;
                    r2::sfor<8 / E>([&](auto ek) {
                        constexpr unsigned e0 = decltype(ek)::value * E;
                        // XA == 2: one slot ahead (slot 0's x asked for before the decode, slot i + 1's before slot i's
                        // products); slot 0's address is valid for any group (lanes >= cnt read offset 0)
                        sycl::vec<float, E> xc;
                        if constexpr (XA == 2) xc = xload<E>(sg, x + sycl::select_from_group(sg, xo, 0) + bo + e0 * 32);
                        float v[RR][E];
                        r2::sfor<E>([&](auto gk) {
                            constexpr unsigned g = decltype(gk)::value;
                            r2::sfor<RR>([&](auto hk) {
                                constexpr unsigned h = decltype(hk)::value;
                                v[h][g] = f.template wv<8 * bb + e0 + g>(sg, sgs[h]);
                            });
                        });
                        if constexpr (XA == 2) {
                            // nested (slot i's block holds slot i + 1's): each loaded value is defined in the block that
                            // uses it, no merge with an undefined value (a flat form spilled tens of KB)
                            auto prod = [&](auto ik, const sycl::vec<float, E> &xv) {
                                constexpr unsigned i = decltype(ik)::value;
                                r2::sfor<E>([&](auto gk) {
                                    constexpr unsigned g = decltype(gk)::value;
                                    r2::sfor<RR>([&](auto hk) {
                                        constexpr unsigned h = decltype(hk)::value;
                                        sum[h][i] = sum[h][i] + v[h][g] * xv[g];
                                    });
                                });
                            };
                            auto chain = [&](auto self, auto ik, const sycl::vec<float, E> &xv) -> void {
                                constexpr unsigned i = decltype(ik)::value;
                                if constexpr (i + 1 < MT) {
                                    if (i + 1 < cnt) {
                                        const sycl::vec<float, E> xn =
                                            xload<E>(sg, x + sycl::select_from_group(sg, xo, i + 1) + bo + e0 * 32);
                                        prod(ik, xv);
                                        self(self, std::integral_constant<unsigned, i + 1>{}, xn);
                                    } else {
                                        prod(ik, xv);
                                    }
                                } else {
                                    prod(ik, xv);
                                }
                            };
                            chain(chain, std::integral_constant<unsigned, 0>{}, xc); // slot 0: every group has one
                        } else {
#pragma unroll
                            for (unsigned i = 0; i < MT; ++i) {
                                if (i < cnt) {
                                    const sycl::vec<float, E> xv = xload<E>(sg, x + sycl::select_from_group(sg, xo, i) + bo + e0 * 32);
#pragma unroll
                                    for (unsigned g = 0; g < E; ++g)
#pragma unroll
                                        for (unsigned h = 0; h < RR; ++h) sum[h][i] = sum[h][i] + v[h][g] * xv[g];
                                }
                            }
                        }
                    });
                });
            };
#pragma unroll 1
            for (unsigned T = 0; T < NFU; ++T) {
                typename F::Unit un[RR];
                r2::sfor<RR>([&](auto hk) { f.unit(sg, rr[decltype(hk)::value], T, un[decltype(hk)::value]); });
                r2::sfor<SPU>([&](auto spk) {
                    constexpr unsigned SP = decltype(spk)::value;
                    const unsigned S = SPU * T + SP;
                    typename F::Sg sgs[RR];
                    r2::sfor<RR>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        f.template seg<SP>(sg, rr[h], un[h], S, sgs[h]);
                    });
                    blocks(std::integral_constant<unsigned, 4>{}, S, sgs);
                });
            }
            if constexpr (SPU * NFU < NS) { // the rest: compile-time segments
                typename F::Unit un[RR];
                r2::sfor<RR>([&](auto hk) { f.unit(sg, rr[decltype(hk)::value], NFU, un[decltype(hk)::value]); });
                r2::sfor<NS - SPU * NFU>([&](auto spk) {
                    constexpr unsigned SP = decltype(spk)::value, S = SPU * NFU + SP;
                    constexpr unsigned NBS = 4 * S + 4 <= NB ? 4 : NB - 4 * S;
                    typename F::Sg sgs[RR];
                    r2::sfor<RR>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        f.template seg<SP>(sg, rr[h], un[h], S, sgs[h]);
                    });
                    blocks(std::integral_constant<unsigned, NBS>{}, S, sgs);
                });
            }
#pragma unroll
            for (unsigned i = 0; i < MT; ++i) {
                if (i < cnt) {
                    const unsigned slot = sycl::select_from_group(sg, sl, i);
                    r2::sfor<RR>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        float s = sum[h][i];
                        for (int w_ = 16; w_; w_ >>= 1) s += sycl::select_from_group(sg, s, (int)lane ^ w_);
                        if (lane == 0) om[slot * rows + r + h] = s;
                    });
                }
            }
        };
        if constexpr (R > 1)
            for (unsigned q_ = p0; q_ < ntile; q_ += P) job(std::integral_constant<unsigned, R>{}, R * q_);
        for (unsigned q_ = R * ntile + p0; q_ < nr_; q_ += P) job(std::integral_constant<unsigned, 1>{}, q_);
    }
};

// The backend's selectors (routed_m with OWN_MT_RUX): per format, blocks per row (20: gate + up, 9: down) and MT, the
// form bench_rux measured fastest on real 3K-prompt picks at 16-256 tokens (card 5, 2026-11-11, out/run-e8-all-c5.txt):
//   default            R = 2, E = 8, 128 registers (RoutedUT's two-row tiles)
//   IQ3_XXS / IQ2_XXS down, MT 6: R = 4, E = 8, slot i + 1's x asked for before slot i's products (XA = 2), 256 registers
//   IQ2_XXS gate + up and IQ2_XS down / gate + up, MT 6: production's RoutedU3 PAIRS (the same two-row tile; R = 0
//   keeps it); IQ2_XS gate + up MT 16: production
template <iq3::Type TY, unsigned NB, unsigned MT> struct RuxPick {
    static constexpr unsigned R = 2, E = 8, XA = 0, G = 128;
};
template <unsigned MT> struct RuxPickKeep {
    static constexpr unsigned R = 0, E = 8, XA = 0, G = 0;
};
struct RuxPickR4 {
    static constexpr unsigned R = 4, E = 8, XA = 2, G = 256;
};
template <> struct RuxPick<iq3::Type::IQ2_XXS, 20, 6> : RuxPickKeep<6> {};
template <> struct RuxPick<iq3::Type::IQ2_XS, 9, 6> : RuxPickKeep<6> {};
template <> struct RuxPick<iq3::Type::IQ2_XS, 20, 6> : RuxPickKeep<6> {};   // (no layer uses it today)
template <> struct RuxPick<iq3::Type::IQ2_XS, 20, 16> : RuxPickKeep<16> {}; // R = 2 is 14-28 % slower here
template <> struct RuxPick<iq3::Type::IQ3_XXS, 9, 6> : RuxPickR4 {};
template <> struct RuxPick<iq3::Type::IQ2_XXS, 9, 6> : RuxPickR4 {};
template <typename F, iq3::Type TY, unsigned NB, unsigned MT, typename PROD>
using RuxSel = std::conditional_t<RuxPick<TY, NB, MT>::R == 0, PROD,
                                  RoutedUT<F, MT, NoRows, 6, (RuxPick<TY, NB, MT>::R ? RuxPick<TY, NB, MT>::R : 1u),
                                           RuxPick<TY, NB, MT>::E, RuxPick<TY, NB, MT>::XA, RuxPick<TY, NB, MT>::G>>;
template <unsigned NB, unsigned MT>
using RoutedIQ2XXSUX = RuxSel<RU3IQ2XXS<NB>, iq3::Type::IQ2_XXS, NB, MT, RoutedIQ2XXSU<NB, MT>>;
template <unsigned NB, unsigned MT> using RoutedIQ2SUX = RuxSel<RU3IQ2S<NB>, iq3::Type::IQ2_S, NB, MT, RoutedIQ2SU<NB, MT>>;
template <unsigned NB, unsigned MT>
using RoutedIQ3XXSUX = RuxSel<RU3IQ3XXS<NB>, iq3::Type::IQ3_XXS, NB, MT, RoutedIQ3XXSU<NB, MT>>;
template <unsigned NB, unsigned MT> using RoutedIQ2XSUX = RuxSel<RU3IQ2XS<NB>, iq3::Type::IQ2_XS, NB, MT, RoutedIQ2XSU<NB, MT>>;
template <unsigned NB, unsigned MT> using RoutedIQ1SUX = RuxSel<RU3IQ1S<NB>, iq3::Type::IQ1_S, NB, MT, RoutedIQ1SU<NB, MT>>;

} // namespace ops41sycl
