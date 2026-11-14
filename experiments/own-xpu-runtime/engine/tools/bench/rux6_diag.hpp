// rux6 DIAGNOSTIC kernels (bench only, never in the engine; outputs are NOT the engine's except D = 0): rux4's
// RoutedUP (sycl_v41_routed_rux4.hpp, PF = 0) with parts removed or altered, to split today's (OWN_RUX4 picks) time
// per (row-block, slot) into its pieces. Same schedule, tiles, work-group cap and register mode as the pick.
//   D = 0  ctl     the same code as RoutedUP<F, MT, R, E, XA, 0, LV, G, W> (must time as the pick; bitwise checked)
//   D = 1  noX     one x read per sub-block (slot 0's), used by every slot (the per-slot x reads removed, FP kept)
//   D = 2  noDec   no weight decode (no gathers, no scale / sign work): v = one value per row (FP + x kept)
//   D = 3  fpOnly  1 + 2: the multiply-adds, the group / store overhead and the loop
//   D = 4  xOnly   x reads only: each slot's x values xored into an integer per slot (no decode, no products)
//   D = 5  decOnly decode only: each decoded value xored into an integer per row (no x, no products)
//   D = 6  cfG     the same instructions, but every grid gather conflict-free (the 4 (IQ3_XXS: 8) lane groups of a
//                  gather read entries in distinct 32-byte bank columns; the row's aw words replaced per segment)
//   D = 7  xSame   every slot's x read from slot 0's address (NOTE, ISA d1: IGC merges the same-address reads and
//                  the slots' multiplies, 96 x reads instead of 576 for IQ2_S: in effect noX without its spill)
//   D = 8  noGat   the gathers removed (the table word = the gather address), the rest of the decode kept
//   D = 9  noFP    4 + 5: the x reads and the decode, no products (the data-port users alone)
//   D = 10 xHit    slot i reads slot 0's x block shifted by 4 i floats (distinct reads the compiler cannot merge, all
//                  inside lines slot 0 just brought into L1: the x reads' L1-hit cost without the misses of slots 1+)
#pragma once
#include "stage2/packet3/kernels/sycl_v41_routed_rux6.hpp"

namespace ops41sycl {
namespace rux6d {
// conflict-free aw words for D = 6: half h of the 64-half (2 x 32-lane) view -> entry with (entry mod 8) = lane group
template <typename F> struct CfAw;
template <unsigned NB> struct CfAw<RU3IQ2XXS<NB>> { // 256 entries x 32 B; ag8: half 4M + (lane >> 3)
    static uint32_t half(uint32_t h) { return (((h & 3u) | (((h >> 2) & 31u) << 3)) << 5); }
    static constexpr unsigned N = 2;
};
template <unsigned NB> struct CfAw<RU3IQ2S<NB>> { // 1024 entries x 32 B
    static uint32_t half(uint32_t h) { return (((h & 3u) | (((h >> 2) & 127u) << 3)) << 5); }
    static constexpr unsigned N = 2;
};
template <unsigned NB> struct CfAw<RU3IQ2XS<NB>> { // 512 entries x 32 B
    static uint32_t half(uint32_t h) { return (((h & 3u) | (((h >> 2) & 63u) << 3)) << 5); }
    static constexpr unsigned N = 2;
};
template <unsigned NB> struct CfAw<RU3IQ1S<NB>> { // 2048 entries x 16 B (16-bit codes): column = 16 B, 16 columns
    static uint32_t half(uint32_t h) { return (((h & 3u) | (((h >> 2) & 127u) << 4)) << 4); }
    static constexpr unsigned N = 2;
};
template <unsigned NB> struct CfAw<RU3IQ3XXS<NB>> { // 256 entries x 16 B, ag4: half 8M + (lane >> 2), 8 groups
    static uint32_t half(uint32_t h) { return (((h & 7u) | (((h >> 3) & 15u) << 4)) << 4); }
    static constexpr unsigned N = 4;
};
} // namespace rux6d

template <typename F, unsigned MT, unsigned R, unsigned E, unsigned XA, unsigned LV, unsigned G, unsigned W, unsigned D,
          unsigned XP = 0>
struct RoutedUPD { // XP > 0: + RoutedUX's x prefetch (XW 0, PK 1: L1 + L3) of block b + XP at block b (the parts left once x is prefetched)
    static constexpr unsigned GRF = G;
    static constexpr unsigned WGCAP = W;
    static_assert(XA <= 2, "diag: XA 0..2");
    using Dc = rux4::Dec<F>;
    static constexpr unsigned TAB = F::TAB, NB = F::NB, SPU = F::SPU, NS = F::NS;
    static constexpr unsigned NFU = (NB / 4) / SPU;
    static constexpr bool NOX = D == 1 || D == 3 || D == 5, NODEC = D == 2 || D == 3 || D == 4;
    static constexpr bool NOFP = D == 4 || D == 5 || D == 9;
    unsigned rows;
    bool per_slot_x;
    NoRows ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    unsigned nexp = 0;
    unsigned tile_nsl = 96;
    template <unsigned N> [[gnu::always_inline]] static inline sycl::vec<float, N> xload(sycl::sub_group sg, const float *p) {
        return sg_bloadN<N>(sg, p);
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
        uint32_t cfw[4] = {0, 0, 0, 0};
        if constexpr (D == 6)
            for (unsigned k = 0; k < rux6d::CfAw<F>::N; ++k)
                cfw[k] = rux6d::CfAw<F>::half(64 * k + 2 * lane) | (rux6d::CfAw<F>::half(64 * k + 2 * lane + 1) << 16);
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
            auto pf_x = [&](unsigned bp) {
#pragma unroll
                for (unsigned i = 0; i < MT; ++i)
                    if (i < cnt) rux6::pf1k<1>(x + sycl::select_from_group(sg, xo, i) + (size_t)bp * 256, lane); // L1 + L3
            };
            if constexpr (XP > 0)
                for (unsigned bp = 0; bp < XP && bp < NB; ++bp) pf_x(bp);
            const uint8_t *ra = wm + ((size_t)eid * rows + r) * F::RB;
            typename F::Row rr[RR];
            float vc[RR];
            if constexpr (!NODEC) r2::sfor<RR>([&](auto hk) { f.row(sg, ra + decltype(hk)::value * F::RB, rr[decltype(hk)::value]); });
            else r2::sfor<RR>([&](auto hk) { vc[decltype(hk)::value] = (float)(eid + r + decltype(hk)::value + lane) * 1e-6f; });
            float sum[RR][MT];
            uint32_t xs_[RR][MT];
#pragma unroll
            for (unsigned h = 0; h < RR; ++h)
#pragma unroll
                for (unsigned i = 0; i < MT; ++i) sum[h][i] = 0, xs_[h][i] = 0;
            struct Raw {
                uint32_t a[RR][E];
            };
            auto blocks = [&](auto nbs, unsigned S, const typename F::Sg (&sgs)[RR]) {
                constexpr unsigned NSB = decltype(nbs)::value * (8 / E);
                r2::sfor<NSB>([&](auto kk) {
                    constexpr unsigned k = decltype(kk)::value, bb = k / (8 / E), e0 = (k % (8 / E)) * E;
                    if constexpr (XP > 0 && e0 == 0)
                        if (4 * S + bb + XP < NB) pf_x(4 * S + bb + XP);
                    const size_t xb = (size_t)(4 * S + bb) * 256 + e0 * 32;
                    float v[RR][E];
                    if constexpr (!NODEC) {
                        Raw q;
                        r2::sfor<E>([&](auto gk) {
                            constexpr unsigned g = decltype(gk)::value;
                            r2::sfor<RR>([&](auto hk) {
                                constexpr unsigned h = decltype(hk)::value;
                                if constexpr (D == 8) {
                                    constexpr unsigned M = 8 * bb + e0 + g;
                                    if constexpr (std::is_same_v<F, RU3IQ3XXS<NB>>) q.a[h][g] = r2::ag4<M % 8>(sgs[h].aw[M / 8], f.jj4);
                                    else if constexpr (std::is_same_v<F, RU3IQ1S<NB>>) q.a[h][g] = r2::ag8<M % 16>(sgs[h].aw[M / 16], f.jb);
                                    else q.a[h][g] = r2::ag8<M % 16>(sgs[h].aw[M / 16], f.j4);
                                } else {
                                    q.a[h][g] = Dc::template wa<8 * bb + e0 + g, LV>(f, sgs[h]);
                                }
                            });
                        });
                        r2::sfor<E>([&](auto gk) {
                            constexpr unsigned g = decltype(gk)::value;
                            r2::sfor<RR>([&](auto hk) {
                                constexpr unsigned h = decltype(hk)::value;
                                v[h][g] = Dc::template wb<8 * bb + e0 + g>(f, sg, sgs[h], q.a[h][g]);
                            });
                        });
                    } else {
#pragma unroll
                        for (unsigned g = 0; g < E; ++g)
#pragma unroll
                            for (unsigned h = 0; h < RR; ++h) v[h][g] = vc[h];
                    }
                    if constexpr (D == 5 || D == 9) {
                        r2::sfor<E>([&](auto gk) {
                            r2::sfor<RR>([&](auto hk) {
                                xs_[decltype(hk)::value][0] ^= sycl::bit_cast<uint32_t>(v[decltype(hk)::value][decltype(gk)::value]);
                            });
                        });
                    }
                    if constexpr (D == 5) return;
                    auto xaddr = [&](unsigned i) -> const float * {
                        if constexpr (D == 7) return x + sycl::select_from_group(sg, xo, 0) + xb;
                        else if constexpr (D == 10) // in bounds: shift up inside the row, down on its last block
                            return x + sycl::select_from_group(sg, xo, 0) + xb +
                                   (4 * S + bb + 1 < NB ? (ptrdiff_t)(4 * i) : -(ptrdiff_t)(4 * i));
                        else return x + sycl::select_from_group(sg, xo, i) + xb;
                    };
                    auto prod = [&](auto ik, const sycl::vec<float, E> &xv) {
                        constexpr unsigned i = decltype(ik)::value;
                        if constexpr (NOFP) {
#pragma unroll
                            for (unsigned g = 0; g < E; ++g) xs_[RR - 1][i] ^= sycl::bit_cast<uint32_t>(xv[g]);
                        } else {
                            r2::sfor<E>([&](auto gk) {
                                constexpr unsigned g = decltype(gk)::value;
                                r2::sfor<RR>([&](auto hk) {
                                    constexpr unsigned h = decltype(hk)::value;
                                    sum[h][i] = sum[h][i] + v[h][g] * xv[g];
                                });
                            });
                        }
                    };
                    if constexpr (NOX) {
                        const sycl::vec<float, E> x0 = xload<E>(sg, xaddr(0));
                        r2::sfor<MT>([&](auto ik) {
                            if (decltype(ik)::value < cnt) prod(ik, x0);
                        });
                    } else if constexpr (XA == 0) {
                        r2::sfor<MT>([&](auto ik) {
                            constexpr unsigned i = decltype(ik)::value;
                            if (i < cnt) {
                                const sycl::vec<float, E> xv = xload<E>(sg, xaddr(i));
                                prod(ik, xv);
                            }
                        });
                    } else {
                        // XA 1 (the R 4 picks): slot 0's read after the decode, slot i + 1's before slot i's products
                        auto chain = [&](auto self, auto ik, const sycl::vec<float, E> &xv) -> void {
                            constexpr unsigned i = decltype(ik)::value;
                            if constexpr (i + 1 < MT) {
                                if (i + 1 < cnt) {
                                    const sycl::vec<float, E> xn = xload<E>(sg, xaddr(i + 1));
                                    prod(ik, xv);
                                    self(self, std::integral_constant<unsigned, i + 1>{}, xn);
                                } else {
                                    prod(ik, xv);
                                }
                            } else {
                                prod(ik, xv);
                            }
                        };
                        const sycl::vec<float, E> x0 = xload<E>(sg, xaddr(0));
                        chain(chain, std::integral_constant<unsigned, 0>{}, x0);
                    }
                });
            };
            auto segs = [&](auto spk, unsigned S, typename F::Unit (&un)[RR], auto nbs) {
                constexpr unsigned SP = decltype(spk)::value;
                typename F::Sg sgs[RR];
                if constexpr (!NODEC)
                    r2::sfor<RR>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        f.template seg<SP>(sg, rr[h], un[h], S, sgs[h]);
                        if constexpr (D == 6)
                            for (unsigned k = 0; k < rux6d::CfAw<F>::N; ++k) sgs[h].aw[k] = cfw[k];
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
                        if constexpr (NOFP) s = sycl::bit_cast<float>((xs_[h][i] ^ xs_[h][0]) & 0x3FFFFFFFu);
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
