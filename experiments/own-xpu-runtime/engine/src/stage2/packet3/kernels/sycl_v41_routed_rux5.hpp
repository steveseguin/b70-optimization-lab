// rux5 (2026-11-13): rux4's pipelined routed-expert form for one-token steps (M = 1) and checks (M = 2-6),
// BITWISE today's kernels' outputs (one-token: RoutedIQ*Px / RoutedIQ2SPe128, sycl_v41_routed_r2.hpp; checks:
// RoutedU3<RU3*, 6>). Bench: tools/bench/bench_rux5.cpp (today's kernel against these, every output float).
//
// RoutedUQ<F, MT, R, E, XA, LV, G, W, IDS> = rux4's RoutedUP (sycl_v41_routed_rux4.hpp; RoutedUT's schedule with
// each sub-block's grid gathers issued back to back, phase A, before their finish, phase B) with:
//   IDS  true: the one-token launch's slot-major ids (6 per token, the P forms' argument) in place of the expert
//        groups: group u = slot u (nu = nsl, one slot each, expert ids[u]); MT = 1. Same rows, same x (token
//        slot / 6, per-slot x for the downs), same outputs om[slot * rows + r] as the P forms.
//   R    rows per tile (tiles of one group and matrix, R consecutive rows sharing each x read; R = 1: single rows).
//        Tiles whenever rows % R == 0 (no block-size threshold: the backend picks these forms per shape).
//   E, XA, LV, G, W as RoutedUP (XA 0: each slot's x right before its products; 1: slot 0's after phase A and slot
//        i + 1's before slot i's products; 2: slot 0's before phase A; 3 (MT 1): the next sub-block's x read after this
//        sub-block's phase A, the segment's first at its start), PF = 0 (rux4: slower everywhere).
// Bit-identity, per output (slot i, row r): accumulator (h, i) receives sum = sum + v * x with v = F::wv<8 bb + g>'s
// value (wa + wb = wv cut after the table load; the same float operations on the same words) and x the same address
// (x[256 b + 32 g + lane] of the slot's x), blocks ascending and g ascending: the order of the P forms (b, d, e: per
// row blk ascending, g ascending, one accumulator per row) and of RoutedU3. Only updates of DIFFERENT accumulators
// interleave. Reduction R2_XSUM (as both), lane 0 stores. Which sub-group runs a row changes nothing.
// Schedule as RoutedUP: tiles of R rows first (at most rmax rows per sub-group), then single rows.
#pragma once
#include <type_traits>
#include <utility>
#include "stage2/packet3/kernels/sycl_v41_routed_rux4.hpp"

namespace ops41sycl {

template <typename F, unsigned MT, unsigned R = 1, unsigned E = 8, unsigned XA = 0, unsigned LV = 0, unsigned G = 128,
          unsigned W = 0, bool IDS = false>
struct RoutedUQ {
    static constexpr unsigned GRF = G;
    static constexpr unsigned WGCAP = W; // (the backend: launch_rows' max_wg lowered to W when W > 0)
    static_assert(MT >= 1 && MT <= RUGrp::CAP, "1 .. 16 slots per group");
    static_assert(!IDS || MT == 1, "one-token ids: one slot per group");
    static_assert(R >= 1 && R <= 8, "rows per tile: 1 .. 8 (tiles only where rows % R == 0)");
    static_assert(E == 2 || E == 4 || E == 8, "elements per lane per x load: 2, 4, 8");
    static_assert(XA <= 3 && LV <= 1, "XA 0..3, LV 0..1");
    static_assert(XA != 3 || MT == 1, "XA 3 (the next sub-block's x during this one): one slot per group");
    using D = rux4::Dec<F>;
    static constexpr unsigned TAB = F::TAB, NB = F::NB, SPU = F::SPU, NS = F::NS;
    static constexpr unsigned NFU = (NB / 4) / SPU;
    unsigned rows;
    bool per_slot_x;
    NoRows ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    unsigned nexp = 0;
    template <unsigned N> [[gnu::always_inline]] static inline sycl::vec<float, N> xload(sycl::sub_group sg, const float *p) {
        return sg_bloadN<N>(sg, p);
    }
    // grp: IDS ? the slots' expert ids : the RUGrp groups
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *grp,
                                     float *out, float *tab) const {
        F::fill(it, tab);
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const F f(lane, tab);
        const unsigned nu = IDS ? nsl : grp[0];
        const unsigned P = (unsigned)(it.get_global_range(0) / 32), p0 = packed_row_id(it);
        const unsigned nr_ = (w2 ? 2 : 1) * nu * rows;
        unsigned ntile = 0;
        if constexpr (R > 1) {
            const unsigned rmax = (nr_ + P - 1) / P, pc = P * (rmax / R);
            if (rows % R == 0) ntile = pc < nr_ / R ? pc : nr_ / R;
        }
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
            unsigned cnt, eid;
            uint32_t sl;
            if constexpr (IDS) {
                cnt = 1;
                sl = u;
                eid = grp[u];
            } else {
                cnt = grp[RUGrp::CNT + u];
                sl = lane < cnt ? grp[RUGrp::SLOT + u * RUGrp::CAP + lane] : 0u;
                eid = grp[RUGrp::EXP + u];
            }
            const uint32_t xo = (sl / 6) * xtok + (per_slot_x ? (sl % 6) * (NB * 256) : 0u);
            const uint8_t *ra = wm + ((size_t)eid * rows + r) * F::RB;
            typename F::Row rr[RR];
            r2::sfor<RR>([&](auto hk) { f.row(sg, ra + decltype(hk)::value * F::RB, rr[decltype(hk)::value]); });
            float sum[RR][MT];
#pragma unroll
            for (unsigned h = 0; h < RR; ++h)
#pragma unroll
                for (unsigned i = 0; i < MT; ++i) sum[h][i] = 0;
            auto xaddr = [&](unsigned i) -> const float * {
                if constexpr (IDS) return x + xo; // one slot, uniform
                else return x + sycl::select_from_group(sg, xo, i);
            };
            // NBS blocks of segment S: NBS * 8 / E sub-blocks of E elements
            auto blocks = [&](auto nbs, unsigned S, const typename F::Sg (&sgs)[RR]) {
                constexpr unsigned NSB = decltype(nbs)::value * (8 / E);
                auto xbo = [&](unsigned k) { return (size_t)(4 * S + k / (8 / E)) * 256 + (k % (8 / E)) * E * 32; };
                sycl::vec<float, E> xc; // XA 3: sub-block k's x, read during sub-block k - 1 (the first at the segment start)
                if constexpr (XA == 3) xc = xload<E>(sg, xaddr(0) + xbo(0));
                r2::sfor<NSB>([&](auto kk) {
                    constexpr unsigned k = decltype(kk)::value, bb = k / (8 / E), e0 = (k % (8 / E)) * E;
                    const size_t xb = (size_t)(4 * S + bb) * 256 + e0 * 32;
                    sycl::vec<float, E> x0;
                    if constexpr (XA == 2) x0 = xload<E>(sg, xaddr(0) + xb);
                    uint32_t a[RR][E]; // phase A: every gather of the sub-block
                    r2::sfor<E>([&](auto gk) {
                        constexpr unsigned g = decltype(gk)::value;
                        r2::sfor<RR>([&](auto hk) {
                            constexpr unsigned h = decltype(hk)::value;
                            a[h][g] = D::template wa<8 * bb + e0 + g, LV>(f, sgs[h]);
                        });
                    });
                    if constexpr (XA == 1) x0 = xload<E>(sg, xaddr(0) + xb);
                    if constexpr (XA == 3) {
                        x0 = xc;
                        if constexpr (k + 1 < NSB) xc = xload<E>(sg, xaddr(0) + xbo(k + 1));
                    }
                    float v[RR][E]; // phase B
                    r2::sfor<E>([&](auto gk) {
                        constexpr unsigned g = decltype(gk)::value;
                        r2::sfor<RR>([&](auto hk) {
                            constexpr unsigned h = decltype(hk)::value;
                            v[h][g] = D::template wb<8 * bb + e0 + g>(f, sg, sgs[h], a[h][g]);
                        });
                    });
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
                    if constexpr (XA == 0) {
                        r2::sfor<MT>([&](auto ik) {
                            constexpr unsigned i = decltype(ik)::value;
                            if (i == 0 || i < cnt) prod(ik, xload<E>(sg, xaddr(i) + xb));
                        });
                    } else {
                        // nested: slot i's block holds slot i + 1's read (each loaded value defined where it is used)
                        auto chain = [&](auto self, auto ik, const sycl::vec<float, E> &xv) -> void {
                            constexpr unsigned i = decltype(ik)::value;
                            if constexpr (i + 1 < MT) {
                                if (i + 1 < cnt) {
                                    const sycl::vec<float, E> xn = xload<E>(sg, xaddr(i + 1) + xb);
                                    prod(ik, xv);
                                    self(self, std::integral_constant<unsigned, i + 1>{}, xn);
                                } else {
                                    prod(ik, xv);
                                }
                            } else {
                                prod(ik, xv);
                            }
                        };
                        chain(chain, std::integral_constant<unsigned, 0>{}, x0); // slot 0: every group has one
                    }
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
            if constexpr (SPU * NFU < NS) {
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
            r2::sfor<MT>([&](auto ik) {
                constexpr unsigned i = decltype(ik)::value;
                if (i == 0 || i < cnt) {
                    const unsigned slot = IDS ? sl : sycl::select_from_group(sg, sl, i);
                    r2::sfor<RR>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        float s = sum[h][i];
                        R2_XSUM(s);
                        if (lane == 0) om[slot * rows + r + h] = s;
                    });
                }
            });
        };
        if constexpr (R > 1)
            for (unsigned q_ = p0; q_ < ntile; q_ += P) job(std::integral_constant<unsigned, R>{}, R * q_);
        for (unsigned q_ = R * ntile + p0; q_ < nr_; q_ += P) job(std::integral_constant<unsigned, 1>{}, q_);
    }
};

} // namespace ops41sycl

namespace ops41sycl {
// rux5-1 selection (OWN_RUX5=1): per (format, blocks) the bench winner (bench_rux5 on card 2, real 3K-prompt picks,
// /home/steve/dsv41-work/rux5/README.md); R = 0 keeps today's kernel. Rux5Pick1: one-token launches (routed_pair /
// routed_gemv, slot ids, MT 1); Rux5PickK<.., M>: checks of M = 2-6 tokens (routed_m's expert groups, cap 6; MT = 0:
// MT = M, enough: a token has 6 different experts, so a group holds at most M slots).
template <iq3::Type TY, unsigned NB> struct Rux5Pick1 {
    static constexpr unsigned R = 0, E = 8, XA = 0, LV = 0, G = 128, W = 0;
};
template <iq3::Type TY, unsigned NB, unsigned M> struct Rux5PickK {
    static constexpr unsigned R = 0, MT = 6, E = 8, XA = 0, LV = 0, G = 128, W = 0;
};
//RUX5PICKS
// M 1: R1 E8 x2 (queue 2 cold: -5.0 %)
template <> struct Rux5Pick1<iq3::Type::IQ2_S, 20> {
    static constexpr unsigned R = 1, E = 8, XA = 2, LV = 0, G = 128, W = 0;
};
// M 1: R2 E8 x2 (queue 2 cold: -1.4 %)
template <> struct Rux5Pick1<iq3::Type::IQ2_XXS, 20> {
    static constexpr unsigned R = 2, E = 8, XA = 2, LV = 0, G = 128, W = 0;
};
// M 1: R1 E8 x2 (queue 2 cold: -6.1 %)
template <> struct Rux5Pick1<iq3::Type::IQ1_S, 20> {
    static constexpr unsigned R = 1, E = 8, XA = 2, LV = 0, G = 128, W = 0;
};
// M 1: R1 E8 x2 (queue 2 cold: -4.9 %)
template <> struct Rux5Pick1<iq3::Type::IQ3_XXS, 9> {
    static constexpr unsigned R = 1, E = 8, XA = 2, LV = 0, G = 128, W = 0;
};
// M 1: R1 E4 x1 (queue 2 cold: -3.4 %)
template <> struct Rux5Pick1<iq3::Type::IQ2_S, 9> {
    static constexpr unsigned R = 1, E = 4, XA = 1, LV = 0, G = 128, W = 0;
};
// M 1: R1 E8 x1 lv1 (queue 2 cold: -2.5 %)
template <> struct Rux5Pick1<iq3::Type::IQ2_XS, 9> {
    static constexpr unsigned R = 1, E = 8, XA = 1, LV = 1, G = 128, W = 0;
};
// checks of 2-5 tokens: MT = M, x1 (queue 2 cold, check-weighted: -12.9 %)
template <unsigned M> struct Rux5PickK<iq3::Type::IQ2_S, 20, M> {
    static constexpr unsigned R = 1, MT = 0, E = 8, XA = 1, LV = 0, G = 128, W = 0;
};
// checks of 6 tokens: MT 6, x0 (-10.8 %)
template <> struct Rux5PickK<iq3::Type::IQ2_S, 20, 6> {
    static constexpr unsigned R = 1, MT = 6, E = 8, XA = 0, LV = 0, G = 128, W = 0;
};
// checks of 2-5 tokens: MT = M, x1 (-12.1 %)
template <unsigned M> struct Rux5PickK<iq3::Type::IQ2_XXS, 20, M> {
    static constexpr unsigned R = 1, MT = 0, E = 8, XA = 1, LV = 0, G = 128, W = 0;
};
// checks of 6 tokens: MT 6, x0 (-12.6 %)
template <> struct Rux5PickK<iq3::Type::IQ2_XXS, 20, 6> {
    static constexpr unsigned R = 1, MT = 6, E = 8, XA = 0, LV = 0, G = 128, W = 0;
};
// checks of 2-5 tokens: MT = M, x1 (-11.4 %)
template <unsigned M> struct Rux5PickK<iq3::Type::IQ1_S, 20, M> {
    static constexpr unsigned R = 1, MT = 0, E = 8, XA = 1, LV = 0, G = 128, W = 0;
};
// checks of 6 tokens: MT 6, x0 (-12.1 %)
template <> struct Rux5PickK<iq3::Type::IQ1_S, 20, 6> {
    static constexpr unsigned R = 1, MT = 6, E = 8, XA = 0, LV = 0, G = 128, W = 0;
};
// checks of 2-5 tokens: MT = M, x1 (-10.3 %)
template <unsigned M> struct Rux5PickK<iq3::Type::IQ3_XXS, 9, M> {
    static constexpr unsigned R = 1, MT = 0, E = 8, XA = 1, LV = 0, G = 128, W = 0;
};
// checks of 6 tokens: MT 6, x0 (-9.7 %)
template <> struct Rux5PickK<iq3::Type::IQ3_XXS, 9, 6> {
    static constexpr unsigned R = 1, MT = 6, E = 8, XA = 0, LV = 0, G = 128, W = 0;
};
// checks of 2-5 tokens: MT = M, x1 (-7.4 %)
template <unsigned M> struct Rux5PickK<iq3::Type::IQ2_S, 9, M> {
    static constexpr unsigned R = 1, MT = 0, E = 8, XA = 1, LV = 0, G = 128, W = 0;
};
// checks of 6 tokens: MT 6, x0 (-9.1 %)
template <> struct Rux5PickK<iq3::Type::IQ2_S, 9, 6> {
    static constexpr unsigned R = 1, MT = 6, E = 8, XA = 0, LV = 0, G = 128, W = 0;
};
// checks of 2-5 tokens: MT = M, x1 (-9.0 %)
template <unsigned M> struct Rux5PickK<iq3::Type::IQ2_XS, 9, M> {
    static constexpr unsigned R = 1, MT = 0, E = 8, XA = 1, LV = 0, G = 128, W = 0;
};
// checks of 6 tokens: MT 6, x0 (-10.4 %)
template <> struct Rux5PickK<iq3::Type::IQ2_XS, 9, 6> {
    static constexpr unsigned R = 1, MT = 6, E = 8, XA = 0, LV = 0, G = 128, W = 0;
};
// checks of 2-5 tokens: MT = M, x1 (-10.7 %)
template <unsigned M> struct Rux5PickK<iq3::Type::IQ2_XXS, 9, M> {
    static constexpr unsigned R = 1, MT = 0, E = 8, XA = 1, LV = 0, G = 128, W = 0;
};
// checks of 6 tokens: MT 6, x0 (-12.0 %)
template <> struct Rux5PickK<iq3::Type::IQ2_XXS, 9, 6> {
    static constexpr unsigned R = 1, MT = 6, E = 8, XA = 0, LV = 0, G = 128, W = 0;
};
//RUX5PICKS_END
template <iq3::Type TY, unsigned NB> struct Rux5F;
template <unsigned NB> struct Rux5F<iq3::Type::IQ2_XXS, NB> { using T = RU3IQ2XXS<NB>; };
template <unsigned NB> struct Rux5F<iq3::Type::IQ2_S, NB> { using T = RU3IQ2S<NB>; };
template <unsigned NB> struct Rux5F<iq3::Type::IQ3_XXS, NB> { using T = RU3IQ3XXS<NB>; };
template <unsigned NB> struct Rux5F<iq3::Type::IQ2_XS, NB> { using T = RU3IQ2XS<NB>; };
template <unsigned NB> struct Rux5F<iq3::Type::IQ1_S, NB> { using T = RU3IQ1S<NB>; };
template <iq3::Type TY, unsigned NB, typename P = Rux5Pick1<TY, NB>>
using Rux5Q1 = RoutedUQ<typename Rux5F<TY, NB>::T, 1, (P::R ? P::R : 1u), P::E, P::XA, P::LV, P::G, P::W, true>;
template <iq3::Type TY, unsigned NB, unsigned M, typename P = Rux5PickK<TY, NB, M>>
using Rux5QK = RoutedUQ<typename Rux5F<TY, NB>::T, (P::MT ? P::MT : M), (P::R ? P::R : 1u), P::E, P::XA, P::LV, P::G, P::W, false>;
} // namespace ops41sycl
