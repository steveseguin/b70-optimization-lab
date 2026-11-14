// rux7 bench-only (2026-11-13): the x-stationary RoutedUS forms (bench_rux7.cpp, VarS tags), moved out of
// sycl_v41_routed_rux7.hpp: they do not fit in registers. At SIMD32 every accumulator is 32 partial sums (2 GRFs; the
// lane-to-column mapping fixes the bits), so R 8 x MT 6 accumulators alone take 96 GRFs, and each row's segment
// decode state (IQ2_S: Row + Unit + Sg ~ 16 GRFs) is held for all R rows. Built: ~92 KB of spill per thread at 256
// registers (R8 E4 / E8; isa/s8, isa/p1). Not timed.
#pragma once
#include "stage2/packet3/kernels/sycl_v41_routed_rux7.hpp"

namespace ops41sycl {

// RoutedUS<F, MT, R, E, G, W, XP, XW, PK>: the "x-stationary" form of rux4's RoutedUP (coordinator's R8 x S6
//    proposal): per sub-block of E elements the x of every slot of the group is read once (MT x E values held), then
//    each of the R rows' E values is formed (Dec<F>::wa + wb, rux4) and multiplied into that row's MT accumulators.
//    x traffic per (row-block, slot) = 1 KB / R, as RoutedUP's R-row tiles; only one row's values live at a time, but every
//    row's decode state (Row, Unit, Sg) and its MT accumulators do.
//    Bit-identity: RoutedUP's argument (each accumulator gets the same mul and add on the same value and x, in the
//    same (segment, block, element) order; only different accumulators interleave; R2_XSUM; same stores).

// x-stationary RoutedUP (see above)
template <typename F, unsigned MT, unsigned R = 4, unsigned E = 8, unsigned G = 256, unsigned W = 64, unsigned XP = 0,
          unsigned XW = 1, unsigned PK = 0>
struct RoutedUS {
    static constexpr unsigned GRF = G;
    static constexpr unsigned WGCAP = W;
    static_assert(MT >= 1 && MT <= RUGrp::CAP, "1 .. 16 slots per group");
    static_assert(R >= 1 && R <= 8, "rows per tile: 1 .. 8");
    static_assert(E == 2 || E == 4 || E == 8, "elements per lane per x load: 2, 4, 8");
    static_assert(XP <= 4 && XW <= 2 && PK <= 2, "XP 0..4, XW 0..2, PK 0..2");
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
    unsigned tile_nsl = 96;
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
            if (nsl >= tile_nsl && rows % R == 0) ntile = pc < nr_ / R ? pc : nr_ / R;
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
            const unsigned cnt = grp[RUGrp::CNT + u];
            const uint32_t sl = lane < cnt ? grp[RUGrp::SLOT + u * RUGrp::CAP + lane] : 0u;
            const uint32_t xo = (sl / 6) * xtok + (per_slot_x ? (sl % 6) * (NB * 256) : 0u);
            const unsigned eid = grp[RUGrp::EXP + u];
            const uint8_t *ra = wm + ((size_t)eid * rows + r) * F::RB;
            auto pf_x = [&](unsigned bp) {
                if constexpr (XW == 1) {
                    rux6::pf1k<PK>(x + sycl::select_from_group(sg, xo, sg.get_group_linear_id() % cnt) + (size_t)bp * 256, lane);
                } else if constexpr (XW == 2) {
                    const unsigned s_ = (unsigned)sg.get_group_linear_id();
                    if (s_ < cnt) rux6::pf1k<PK>(x + sycl::select_from_group(sg, xo, s_) + (size_t)bp * 256, lane);
                } else {
#pragma unroll
                    for (unsigned i = 0; i < MT; ++i)
                        if (i < cnt) rux6::pf1k<PK>(x + sycl::select_from_group(sg, xo, i) + (size_t)bp * 256, lane);
                }
            };
            if constexpr (XP > 0)
                for (unsigned bp = 0; bp < XP && bp < NB; ++bp) pf_x(bp);
            typename F::Row rr[RR];
            r2::sfor<RR>([&](auto hk) { f.row(sg, ra + decltype(hk)::value * F::RB, rr[decltype(hk)::value]); });
            float sum[RR][MT];
#pragma unroll
            for (unsigned h = 0; h < RR; ++h)
#pragma unroll
                for (unsigned i = 0; i < MT; ++i) sum[h][i] = 0;
            auto blocks = [&](auto nbs, unsigned S, const typename F::Sg (&sgs)[RR]) {
                constexpr unsigned NSB = decltype(nbs)::value * (8 / E);
                r2::sfor<NSB>([&](auto kk) {
                    constexpr unsigned k = decltype(kk)::value, bb = k / (8 / E), e0 = (k % (8 / E)) * E;
                    if constexpr (XP > 0 && e0 == 0)
                        if (4 * S + bb + XP < NB) pf_x(4 * S + bb + XP);
                    const size_t xb = (size_t)(4 * S + bb) * 256 + e0 * 32;
                    // every slot's x of the sub-block (slot 0: every group has one; slots >= cnt: not used)
                    sycl::vec<float, E> xa[MT];
                    xa[0] = sg_bloadN<E>(sg, x + sycl::select_from_group(sg, xo, 0) + xb);
#pragma unroll
                    for (unsigned i = 1; i < MT; ++i) {
                        xa[i] = sycl::vec<float, E>(0.0f);
                        if (i < cnt) xa[i] = sg_bloadN<E>(sg, x + sycl::select_from_group(sg, xo, i) + xb);
                    }
                    // row by row: its E values (gathers first, then the finish), then its MT accumulators
                    r2::sfor<RR>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        uint32_t raw[E];
                        r2::sfor<E>([&](auto gk) {
                            constexpr unsigned g = decltype(gk)::value;
                            raw[g] = D::template wa<8 * bb + e0 + g, 0>(f, sgs[h]);
                        });
                        float v[E];
                        r2::sfor<E>([&](auto gk) {
                            constexpr unsigned g = decltype(gk)::value;
                            v[g] = D::template wb<8 * bb + e0 + g>(f, sg, sgs[h], raw[g]);
                        });
                        r2::sfor<E>([&](auto gk) {
                            constexpr unsigned g = decltype(gk)::value;
                            sum[h][0] = sum[h][0] + v[g] * xa[0][g];
                        });
                        r2::sfor<MT - 1>([&](auto ik) {
                            constexpr unsigned i = decltype(ik)::value + 1;
                            if (i < cnt)
                                r2::sfor<E>([&](auto gk) {
                                    constexpr unsigned g = decltype(gk)::value;
                                    sum[h][i] = sum[h][i] + v[g] * xa[i][g];
                                });
                        });
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
#pragma unroll
            for (unsigned i = 0; i < MT; ++i) {
                if (i < cnt) {
                    const unsigned slot = sycl::select_from_group(sg, sl, i);
                    r2::sfor<RR>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        float s = sum[h][i];
                        R2_XSUM(s);
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

} // namespace ops41sycl
