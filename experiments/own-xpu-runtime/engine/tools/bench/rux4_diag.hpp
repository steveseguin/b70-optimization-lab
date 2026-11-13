// rux4 DIAGNOSTIC (from rux3_diag.hpp) kernels (bench only, never in the engine; outputs are NOT the engine's): RoutedUT's loop
// (sycl_v41_routed_rux.hpp, EX = NoRows, XA = 0) with parts removed, to split the per-slot time into its pieces.
//   D = 0  the same code as RoutedUT<F, MT, NoRows, 6, R, E, 0, G> (control: must time as the real form)
//   D = 1  NOX: one x load per sub-block (slot 0's), used by every slot (the per-slot x reads removed, FP kept)
//   D = 2  NODEC: no weight decode and no weight reads; v = one value per row computed once per job (FP + x kept)
//   D = 3  both removed: the multiply-add chains, the group / store overhead and the loop
//   D = 4  x reads only (no decode, no float products): each slot's E x values xored into an integer per slot
//   D = 5  decode only (no x, no float products): each decoded value xored into an integer per row
#pragma once
#include "stage2/packet3/kernels/sycl_v41_routed_rux.hpp"

namespace ops41sycl {

template <typename F, unsigned MT, unsigned R, unsigned E, unsigned G, unsigned D> struct RoutedUTD {
    static constexpr unsigned GRF = G;
    static constexpr unsigned TAB = F::TAB, NB = F::NB, SPU = F::SPU, NS = F::NS;
    static constexpr unsigned NFU = (NB / 4) / SPU;
    static constexpr bool NOX = D == 1 || D == 3 || D == 5, NODEC = D == 2 || D == 3 || D == 4, NOFP = D >= 4;
    unsigned rows;
    bool per_slot_x;
    NoRows ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    unsigned nexp = 0;
    unsigned tile_nsl = 96;
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
            typename F::Row rr[RR];
            float vc[RR];
            if constexpr (!NODEC) {
                r2::sfor<RR>([&](auto hk) { f.row(sg, ra + decltype(hk)::value * F::RB, rr[decltype(hk)::value]); });
            } else {
                r2::sfor<RR>([&](auto hk) { vc[decltype(hk)::value] = (float)(eid + r + decltype(hk)::value + lane) * 1e-6f; });
            }
            float sum[RR][MT];
            uint32_t xs_[RR][MT];
#pragma unroll
            for (unsigned h = 0; h < RR; ++h)
#pragma unroll
                for (unsigned i = 0; i < MT; ++i) sum[h][i] = 0, xs_[h][i] = 0;
            auto blocks = [&](auto nbs, unsigned S, const typename F::Sg (&sgs)[RR]) {
                r2::sfor<decltype(nbs)::value>([&](auto bk) {
                    constexpr unsigned bb = decltype(bk)::value;
                    const size_t bo = (size_t)(4 * S + bb) * 256;
                    r2::sfor<8 / E>([&](auto ek) {
                        constexpr unsigned e0 = decltype(ek)::value * E;
                        float v[RR][E];
                        r2::sfor<E>([&](auto gk) {
                            constexpr unsigned g = decltype(gk)::value;
                            r2::sfor<RR>([&](auto hk) {
                                constexpr unsigned h = decltype(hk)::value;
                                if constexpr (!NODEC) v[h][g] = f.template wv<8 * bb + e0 + g>(sg, sgs[h]);
                                else v[h][g] = vc[h];
                            });
                        });
                        if constexpr (D == 5) {
                            r2::sfor<E>([&](auto gk) {
                                r2::sfor<RR>([&](auto hk) {
                                    xs_[decltype(hk)::value][0] ^= sycl::bit_cast<uint32_t>(v[decltype(hk)::value][decltype(gk)::value]);
                                });
                            });
                            return;
                        }
                        if constexpr (D == 4) {
#pragma unroll
                            for (unsigned i = 0; i < MT; ++i) {
                                if (i < cnt) {
                                    const sycl::vec<float, E> xv = xload<E>(sg, x + sycl::select_from_group(sg, xo, i) + bo + e0 * 32);
#pragma unroll
                                    for (unsigned g = 0; g < E; ++g) xs_[0][i] ^= sycl::bit_cast<uint32_t>(xv[g]);
                                }
                            }
                            return;
                        }
                        sycl::vec<float, E> x0;
                        if constexpr (NOX) x0 = xload<E>(sg, x + sycl::select_from_group(sg, xo, 0) + bo + e0 * 32);
#pragma unroll
                        for (unsigned i = 0; i < MT; ++i) {
                            if (i < cnt) {
                                sycl::vec<float, E> xv;
                                if constexpr (NOX) xv = x0;
                                else xv = xload<E>(sg, x + sycl::select_from_group(sg, xo, i) + bo + e0 * 32);
#pragma unroll
                                for (unsigned g = 0; g < E; ++g)
#pragma unroll
                                    for (unsigned h = 0; h < RR; ++h) sum[h][i] = sum[h][i] + v[h][g] * xv[g];
                            }
                        }
                    });
                });
            };
            auto segs = [&](auto spk, unsigned S, typename F::Unit (&un)[RR], auto nbs) {
                constexpr unsigned SP = decltype(spk)::value;
                typename F::Sg sgs[RR];
                if constexpr (!NODEC)
                    r2::sfor<RR>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        f.template seg<SP>(sg, rr[h], un[h], S, sgs[h]);
                    });
                blocks(nbs, S, sgs);
            };
#pragma unroll 1
            for (unsigned T = 0; T < NFU; ++T) {
                typename F::Unit un[RR];
                if constexpr (!NODEC) r2::sfor<RR>([&](auto hk) { f.unit(sg, rr[decltype(hk)::value], T, un[decltype(hk)::value]); });
                r2::sfor<SPU>([&](auto spk) { segs(spk, SPU * T + decltype(spk)::value, un, std::integral_constant<unsigned, 4>{}); });
            }
            if constexpr (SPU * NFU < NS) {
                typename F::Unit un[RR];
                if constexpr (!NODEC) r2::sfor<RR>([&](auto hk) { f.unit(sg, rr[decltype(hk)::value], NFU, un[decltype(hk)::value]); });
                r2::sfor<NS - SPU * NFU>([&](auto spk) {
                    constexpr unsigned SP = decltype(spk)::value, S = SPU * NFU + SP;
                    constexpr unsigned NBS = 4 * S + 4 <= NB ? 4 : NB - 4 * S;
                    segs(spk, S, un, std::integral_constant<unsigned, NBS>{});
                });
            }
#pragma unroll
            for (unsigned i = 0; i < MT; ++i) {
                if (i < cnt) {
                    const unsigned slot = sycl::select_from_group(sg, sl, i);
                    r2::sfor<RR>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        float s = sum[h][i];
                        if constexpr (NOFP) s = sycl::bit_cast<float>(xs_[h][i] & 0x3FFFFFFFu);
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

} // namespace ops41sycl
