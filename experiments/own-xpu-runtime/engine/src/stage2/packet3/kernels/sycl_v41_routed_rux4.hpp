// rux4 (2026-11-12): software-pipelined prompt routed-expert kernels, BITWISE RoutedUT / RoutedU3's outputs
// (sycl_v41_routed_rux.hpp, sycl_v41_routed_r2.hpp) on the same groups (RUGrp, ExpertGroupM).
// Bench: tools/bench/bench_rux4.cpp (today's RoutedIQ*SUX<NB, 6> against these, every output float).
//
// Why: the shipped forms' machine code (128 registers) issues each grid-table gather of a block and waits for it
// before the next one (one scratch register r4 carries every address and result: 16 SLM round trips in a row per
// block of a row pair), and waits on each slot's x block read right before that slot's multiply-adds. With 8
// threads per vector engine that latency is not covered: ~94 clocks per (row-block, slot) against ~32 for the
// float pipe's multiply-adds (rux3).
//
// RoutedUP<F, MT, R, E, XA, PF, LV, G> = RoutedUT's schedule (tiles of R rows of one group, the same Row / Unit /
// Seg state per row, the same E-element sub-blocks) with the decode split in two phases:
//   A  every gather of the sub-block (R rows x E values): address + SLM load (Dec<F>::wa), all issued back to back
//      (LV = 1: volatile inline loads, so they keep their order and none waits for another)
//   B  the per-value finish (Dec<F>::wb): the same scale multiply and sign xor (IQ1_S: dl * (code + de)) as F::wv
//   XA  x reads: 0 = each slot's block read right before its products (RoutedUT XA 0);
//       1 = slot 0's read after phase A, slot i + 1's before slot i's products;
//       2 = slot 0's read before phase A, slot i + 1's before slot i's products;
//       3 = every slot's read of the sub-block up front (before phase A of the next sub-block; MT x E values held)
//   PF  1: phase A of the next sub-block of the segment is issued before this sub-block's products (its gathers
//       then run under the multiply-adds); 0: each sub-block's phase A at its start
//   G   register mode the launch pins (128 / 256; 0 = automatic)
//   W   work-group cap of the launch (WGCAP; 0 = the backend's o.pair_wg / o.down_wg, 128): the 256-register forms
//       hold 4 threads per vector engine, so 64 work-groups of 16 sub-groups fill the card once (one wave)
//
// Bit-identity, per output (slot i, row r): accumulator (h, i) receives sum = sum + v * x with v = F::wv<8 bb + g>'s
// value (the same float operations on the same table words and per-segment state: wa + wb is wv cut after the
// table load) and x the same address, in the same (segment, block, element) order; only updates of DIFFERENT
// accumulators are interleaved. The reduction is R2_XSUM (with OWN_R2_XORP the halving-add lowering, which leaves
// lane 0 with the butterfly's sum, operands in the same order: xperm-4) and lane 0 stores at om[slot * rows + r].
// Schedule, extra rows and job split as RoutedUT (EX = NoRows only).
#pragma once
#include <type_traits>
#include <utility>
#include "stage2/packet3/kernels/sycl_v41_routed_rux.hpp"

namespace ops41sycl {
namespace rux4 {
// 32-bit SLM load at byte offset a (the kernel's table is its only local memory, at offset 0, as RU3IQ1S's ld16)
#ifdef __SYCL_DEVICE_ONLY__
[[gnu::always_inline]] inline uint32_t ld32v(uint32_t a) {
    uint32_t r;
    __asm__ volatile("lsc_load.slm (M1, 32) %0:d32 flat[%1]:a32\n" : "=rw"(r) : "rw"(a));
    return r;
}
#else
inline uint32_t ld32v(uint32_t) { return 0; }
#endif

// phase A (wa: the table word) and phase B (wb: the value) of F::wv<M>, per format
template <typename F> struct Dec;
template <unsigned NB> struct Dec<RU3IQ2XXS<NB>> {
    using F = RU3IQ2XXS<NB>;
    template <unsigned M, unsigned LV> [[gnu::always_inline]] static inline uint32_t wa(const F &f, const typename F::Sg &u) {
        const uint32_t ad = r2::ag8<M % 16>(u.aw[M / 16], f.j4);
        if constexpr (LV) return ld32v(ad);
        else return *reinterpret_cast<const uint32_t *>(f.tb + ad);
    }
    template <unsigned M> [[gnu::always_inline]] static inline float wb(const F &f, sycl::sub_group sg, const typename F::Sg &u, uint32_t raw) {
        const float mag = sycl::bit_cast<float>(raw);
        const float p = sycl::select_from_group(sg, u.db, M) * mag;
        const uint32_t e = sycl::select_from_group(sg, u.ew, M);
        return sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p) ^ ((e << f.ssh) & 0x80000000u));
    }
};
template <unsigned NB> struct Dec<RU3IQ2S<NB>> {
    using F = RU3IQ2S<NB>;
    template <unsigned M, unsigned LV> [[gnu::always_inline]] static inline uint32_t wa(const F &f, const typename F::Sg &u) {
        const uint32_t ad = r2::ag8<M % 16>(u.aw[M / 16], f.j4);
        if constexpr (LV) return ld32v(ad);
        else return *reinterpret_cast<const uint32_t *>(f.tb + ad);
    }
    template <unsigned M> [[gnu::always_inline]] static inline float wb(const F &f, sycl::sub_group sg, const typename F::Sg &u, uint32_t raw) {
        const float mag = sycl::bit_cast<float>(raw);
        const float p = r2::mp16<M % 16>(u.dw[M / 16], mag);
        const uint32_t e = sycl::select_from_group(sg, u.ew, M);
        return sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p) ^ ((e << f.ssh) & 0x80000000u));
    }
};
template <unsigned NB> struct Dec<RU3IQ2XS<NB>> {
    using F = RU3IQ2XS<NB>;
    template <unsigned M, unsigned LV> [[gnu::always_inline]] static inline uint32_t wa(const F &f, const typename F::Sg &u) {
        const uint32_t ad = r2::ag8<M % 16>(u.aw[M / 16], f.j4);
        if constexpr (LV) return ld32v(ad);
        else return *reinterpret_cast<const uint32_t *>(f.tb + ad);
    }
    template <unsigned M> [[gnu::always_inline]] static inline float wb(const F &f, sycl::sub_group sg, const typename F::Sg &u, uint32_t raw) {
        const float mag = sycl::bit_cast<float>(raw);
        const float p = r2::mp16<M % 16>(u.dw[M / 16], mag);
        const uint32_t e = sycl::select_from_group(sg, u.ew, M);
        return sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p) ^ ((e << f.ssh) & 0x80000000u));
    }
};
template <unsigned NB> struct Dec<RU3IQ1S<NB>> {
    using F = RU3IQ1S<NB>;
    template <unsigned M, unsigned LV> [[gnu::always_inline]] static inline uint32_t wa(const F &f, const typename F::Sg &u) {
        return r2::ld16(r2::ag8<M % 16>(u.aw[M / 16], f.jb)); // (always a volatile inline load, as F::wv)
    }
    template <unsigned M> [[gnu::always_inline]] static inline float wb(const F &, sycl::sub_group sg, const typename F::Sg &u, uint32_t raw) {
        const float dl = sycl::select_from_group(sg, u.dl, M);
        const float code = sycl::bit_cast<float>(raw << 16);
        const float de = sycl::select_from_group(sg, u.de, M);
        return dl * (code + de);
    }
};
template <unsigned NB> struct Dec<RU3IQ3XXS<NB>> {
    using F = RU3IQ3XXS<NB>;
    template <unsigned M, unsigned LV> [[gnu::always_inline]] static inline uint32_t wa(const F &f, const typename F::Sg &u) {
        const uint32_t ad = r2::ag4<M % 8>(u.aw[M / 8], f.jj4);
        if constexpr (LV) return ld32v(ad);
        else return *reinterpret_cast<const uint32_t *>(f.tb + ad);
    }
    template <unsigned M> [[gnu::always_inline]] static inline float wb(const F &f, sycl::sub_group sg, const typename F::Sg &u, uint32_t raw) {
        const float mag = sycl::bit_cast<float>(raw);
        const float db = sycl::select_from_group(sg, u.db, M);
        const uint32_t e = sycl::select_from_group(sg, u.ew, M);
        return sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ ((e << f.ssh) & 0x80000000u));
    }
};
} // namespace rux4

template <typename F, unsigned MT, unsigned R = 2, unsigned E = 4, unsigned XA = 2, unsigned PF = 1, unsigned LV = 1,
          unsigned G = 128, unsigned W = 0>
struct RoutedUP {
    static constexpr unsigned GRF = G;
    static constexpr unsigned WGCAP = W; // (the backend: launch_rows' max_wg lowered to W when W > 0)
    static_assert(MT >= 1 && MT <= RUGrp::CAP, "1 .. 16 slots per group");
    static_assert(R >= 1 && R <= 8, "rows per tile: 1 .. 8 (tiles only where rows % R == 0)");
    static_assert(E == 2 || E == 4 || E == 8, "elements per lane per x load: 2, 4, 8");
    static_assert(XA <= 3 && PF <= 1 && LV <= 1, "XA 0..3, PF 0..1, LV 0..1");
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
            r2::sfor<RR>([&](auto hk) { f.row(sg, ra + decltype(hk)::value * F::RB, rr[decltype(hk)::value]); });
            float sum[RR][MT];
#pragma unroll
            for (unsigned h = 0; h < RR; ++h)
#pragma unroll
                for (unsigned i = 0; i < MT; ++i) sum[h][i] = 0;
            struct Raw {
                uint32_t a[RR][E];
            };
            // NBS blocks of segment S: NBS * 8 / E sub-blocks of E elements
            auto blocks = [&](auto nbs, unsigned S, const typename F::Sg (&sgs)[RR]) {
                constexpr unsigned NSB = decltype(nbs)::value * (8 / E);
                auto gath = [&](auto kk) {
                    constexpr unsigned k = decltype(kk)::value, bb = k / (8 / E), e0 = (k % (8 / E)) * E;
                    Raw q;
                    r2::sfor<E>([&](auto gk) {
                        constexpr unsigned g = decltype(gk)::value;
                        r2::sfor<RR>([&](auto hk) {
                            constexpr unsigned h = decltype(hk)::value;
                            q.a[h][g] = D::template wa<8 * bb + e0 + g, LV>(f, sgs[h]);
                        });
                    });
                    return q;
                };
                auto body = [&](auto kk, const Raw &cur, Raw *nxt) {
                    constexpr unsigned k = decltype(kk)::value, bb = k / (8 / E), e0 = (k % (8 / E)) * E;
                    const size_t xb = (size_t)(4 * S + bb) * 256 + e0 * 32;
                    sycl::vec<float, E> x0;
                    sycl::vec<float, E> xa[XA == 3 ? MT : 1];
                    if constexpr (XA == 2) x0 = xload<E>(sg, x + sycl::select_from_group(sg, xo, 0) + xb);
                    if constexpr (XA == 3) {
                        xa[0] = xload<E>(sg, x + sycl::select_from_group(sg, xo, 0) + xb); // slot 0: every group has one
#pragma unroll
                        for (unsigned i = 1; i < MT; ++i) {
                            xa[i] = sycl::vec<float, E>(0.0f);
                            if (i < cnt) xa[i] = xload<E>(sg, x + sycl::select_from_group(sg, xo, i) + xb);
                        }
                    }
                    if constexpr (PF)
                        if constexpr (k + 1 < NSB) *nxt = gath(std::integral_constant<unsigned, k + 1>{});
                    if constexpr (XA == 1) x0 = xload<E>(sg, x + sycl::select_from_group(sg, xo, 0) + xb);
                    float v[RR][E];
                    r2::sfor<E>([&](auto gk) {
                        constexpr unsigned g = decltype(gk)::value;
                        r2::sfor<RR>([&](auto hk) {
                            constexpr unsigned h = decltype(hk)::value;
                            v[h][g] = D::template wb<8 * bb + e0 + g>(f, sg, sgs[h], cur.a[h][g]);
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
                    if constexpr (XA == 3) {
                        prod(std::integral_constant<unsigned, 0>{}, xa[0]);
                        r2::sfor<MT - 1>([&](auto ik) {
                            constexpr unsigned i = decltype(ik)::value + 1;
                            if (i < cnt) prod(std::integral_constant<unsigned, i>{}, xa[i]);
                        });
                    } else if constexpr (XA == 0) {
#pragma unroll
                        for (unsigned i = 0; i < MT; ++i) {
                            if (i < cnt) {
                                const sycl::vec<float, E> xv = xload<E>(sg, x + sycl::select_from_group(sg, xo, i) + xb);
#pragma unroll
                                for (unsigned g = 0; g < E; ++g)
#pragma unroll
                                    for (unsigned h = 0; h < RR; ++h) sum[h][i] = sum[h][i] + v[h][g] * xv[g];
                            }
                        }
                    } else {
                        // nested: slot i's block holds slot i + 1's read (each loaded value defined where it is used)
                        auto chain = [&](auto self, auto ik, const sycl::vec<float, E> &xv) -> void {
                            constexpr unsigned i = decltype(ik)::value;
                            if constexpr (i + 1 < MT) {
                                if (i + 1 < cnt) {
                                    const sycl::vec<float, E> xn =
                                        xload<E>(sg, x + sycl::select_from_group(sg, xo, i + 1) + xb);
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
                };
                if constexpr (PF) {
                    // cur = sub-block k's table words, issued one sub-block ahead (the first at the segment start)
                    auto step = [&](auto self, auto kk, const Raw &cur) -> void {
                        constexpr unsigned k = decltype(kk)::value;
                        if constexpr (k + 1 < NSB) {
                            Raw nx;
                            body(kk, cur, &nx);
                            self(self, std::integral_constant<unsigned, k + 1>{}, nx);
                        } else {
                            body(kk, cur, nullptr);
                        }
                    };
                    step(step, std::integral_constant<unsigned, 0>{}, gath(std::integral_constant<unsigned, 0>{}));
                } else {
                    r2::sfor<NSB>([&](auto kk) {
                        const Raw cur = gath(kk);
                        body(kk, cur, nullptr);
                    });
                }
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

// rux4-1 selection (OWN_RUX4=1, MT 6 only): per (format, blocks) the bench winner (bench_rux4 on card 2, real 3K-prompt
// picks at 256 / 512 tokens, 2026-11-13, /home/steve/dsv41-work/rux4/README.md); R = 0 keeps today's form (RoutedIQ*SUX).
// Measured against today's kernel per launch at 256 tokens (queue12, today's kernel and these picks only in the rounds):
// IQ2_XXS gate + up -18.4 %, IQ1_S gate + up -12.4 %, IQ2_S gate + up -7.9 %, IQ3_XXS down -9.6 %, IQ2_S down -8.4 %,
// IQ2_XS down -5.1 %, IQ2_XXS down -10.4 % (512 tokens: -19.8, -11.3, -6.7, -9.5, -8.1, -5.0, -10.2 %).
// Slower everywhere: PF = 1, XA = 3, R 4 E 4, R 3, R = 6 / 8 tiles, R 2 E 8 with x read ahead (x1 / x2) at 128 registers.
template <iq3::Type TY, unsigned NB> struct Rux4Pick {
    static constexpr unsigned R = 0, E = 4, XA = 1, PF = 0, LV = 1, G = 128, W = 0;
};
//RUX4PICKS
// IQ2_XXS gate + up (15 layers): 4-row tiles at 256 registers, 64 work-groups (today: RoutedU3 pairs)
template <> struct Rux4Pick<iq3::Type::IQ2_XXS, 20> {
    static constexpr unsigned R = 4, E = 8, XA = 1, PF = 0, LV = 0, G = 256, W = 64;
};
// IQ1_S gate + up (10 layers): as IQ2_S gate + up (today: RoutedUT R 2 E 8 at 128)
template <> struct Rux4Pick<iq3::Type::IQ1_S, 20> {
    static constexpr unsigned R = 2, E = 8, XA = 0, PF = 0, LV = 0, G = 128, W = 0;
};
// IQ2_S gate + up (15 layers): RoutedUT R 2 E 8 at 128 registers with the gathers of a sub-block first, plain loads
template <> struct Rux4Pick<iq3::Type::IQ2_S, 20> {
    static constexpr unsigned R = 2, E = 8, XA = 0, PF = 0, LV = 0, G = 128, W = 0;
};
// IQ3_XXS down (15 layers; today: RoutedUT R 4 XA 2 at 256)
template <> struct Rux4Pick<iq3::Type::IQ3_XXS, 9> {
    static constexpr unsigned R = 4, E = 8, XA = 1, PF = 0, LV = 0, G = 256, W = 64;
};
// IQ2_S down (15 layers): as IQ2_S gate + up (today: RoutedUT R 2 E 8 at 128)
template <> struct Rux4Pick<iq3::Type::IQ2_S, 9> {
    static constexpr unsigned R = 2, E = 8, XA = 0, PF = 0, LV = 0, G = 128, W = 0;
};
// IQ2_XXS down (3 layers; today: RoutedUT R 4 XA 2 at 256)
template <> struct Rux4Pick<iq3::Type::IQ2_XXS, 9> {
    static constexpr unsigned R = 4, E = 8, XA = 1, PF = 0, LV = 0, G = 256, W = 64;
};
// IQ2_XS down (6 layers): as IQ2_S gate + up (today: RoutedU3 pairs)
template <> struct Rux4Pick<iq3::Type::IQ2_XS, 9> {
    static constexpr unsigned R = 2, E = 8, XA = 0, PF = 0, LV = 0, G = 128, W = 0;
};
//RUX4PICKS_END
template <typename F, iq3::Type TY, unsigned NB, unsigned MT, typename KEEP>
using Rux4Sel = std::conditional_t<MT != 6 || Rux4Pick<TY, NB>::R == 0, KEEP,
                                   RoutedUP<F, MT, (Rux4Pick<TY, NB>::R ? Rux4Pick<TY, NB>::R : 1u), Rux4Pick<TY, NB>::E,
                                            Rux4Pick<TY, NB>::XA, Rux4Pick<TY, NB>::PF, Rux4Pick<TY, NB>::LV,
                                            Rux4Pick<TY, NB>::G, Rux4Pick<TY, NB>::W>>;
template <unsigned NB, unsigned MT>
using RoutedIQ2XXSUP = Rux4Sel<RU3IQ2XXS<NB>, iq3::Type::IQ2_XXS, NB, MT, RoutedIQ2XXSUX<NB, MT>>;
template <unsigned NB, unsigned MT> using RoutedIQ2SUP = Rux4Sel<RU3IQ2S<NB>, iq3::Type::IQ2_S, NB, MT, RoutedIQ2SUX<NB, MT>>;
template <unsigned NB, unsigned MT>
using RoutedIQ3XXSUP = Rux4Sel<RU3IQ3XXS<NB>, iq3::Type::IQ3_XXS, NB, MT, RoutedIQ3XXSUX<NB, MT>>;
template <unsigned NB, unsigned MT> using RoutedIQ2XSUP = Rux4Sel<RU3IQ2XS<NB>, iq3::Type::IQ2_XS, NB, MT, RoutedIQ2XSUX<NB, MT>>;
template <unsigned NB, unsigned MT> using RoutedIQ1SUP = Rux4Sel<RU3IQ1S<NB>, iq3::Type::IQ1_S, NB, MT, RoutedIQ1SUX<NB, MT>>;

} // namespace ops41sycl
