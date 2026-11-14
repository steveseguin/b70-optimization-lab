// rux6 (2026-11-13): prompt routed-expert kernels with L1 prefetches ahead of use, BITWISE rux4's RoutedUP (and so
// RoutedUT / RoutedU3, production) on the same groups (RUGrp, ExpertGroupM). Bench: tools/bench/bench_rux6.cpp.
//
// Why (rux6 ledger, /home/steve/dsv41-work/rux6/README.md): today's forms (rux4's picks) run ~2x their issue floor
// (the vector engines co-issue the float and integer pipes, so the floor is the float pipe's ~38 clocks per (row-block,
// slot), against ~64-89 measured). Parts-removed runs (rux6_diag.hpp): no products -5 .. -9 %, no grid gathers
// -4 .. +7 %, but no per-slot x reads -36 .. -42 % on the two-row forms (IQ2_S / IQ1_S gate + up, IQ2_S down) and
// -16 .. -24 % on the four-row ones; no weight decode -22 .. -50 %. The 16 sub-groups of a work-group read the same x
// blocks at about the same time, so all of them wait for the same miss; each slot's read is waited on right after it
// is issued; each job's x is new to L1.
//
// RoutedUX<F, MT, R, E, XA, PF, LV, G, W, XP, XW, WP> = RoutedUP<F, MT, R, E, XA, PF, LV, G, W> (rux4: the same text,
// tiles, rows, decode phases, x reads, products, reduction and stores) plus L1 (+ L3) prefetches through the SYCL
// prefetch extension (IGC: LSC loads with a null destination and per-lane addresses; no inline asm -- the 04:09
// card-1 fault came from inline-asm messages whose single address IGC placed in a sub-register the send does not
// read; tools/sendcheck6.py checks every build's machine code for that):
//   XP  x: at the start of block b, the x blocks of block b + XP of the group's slots (0: none)
//   XW  0: every sub-group prefetches all of its group's slots; 1: sub-group s only slot s % cnt (the work-group's
//       16 sub-groups normally share one group, so every slot is still asked for, by ~16 / cnt sub-groups);
//       2: sub-group s < cnt only slot s (each slot once per work-group)
//   WP  row words: 1 = at the start of segment S, the quant bytes of segment S + 1 of the tile's R rows;
//       2 = 1 + at the start of a job, the next job's R rows (all their bytes)
//   PK  prefetch message: 0 = the SYCL prefetch extension -- IGC gives it L1-UNCACHED, L3-cached control
//       (`load.ugm.d8u32.a64.uc.ca (32|M0) null`, any prefetch_hint: isa/pft6), so it only warms L3;
//       1 = IGC's LSC prefetch builtin with L1-cached, L3-cached control (`.ca.ca`, isa/pft7): the line lands in L1
//       2 = x only: the OpenCL sub-group block prefetch (cl_intel_subgroup_buffer_prefetch, IGC's built-in library):
//       ONE address per message, 512 B each (`load.ugm.d64x64t.a64 (1|M0) null [rN:1]`, default = load cache
//       control, isa/pft8k2), 2 messages per 1 KB x block instead of 32 per-lane addresses (needs WP = 0)
// A prefetch only moves data between memory and caches: no register, no value and no operation of the sums changes.
//
// Bit-identity, per output (slot i, row r): exactly RoutedUP's argument (rux4): accumulator (h, i) receives
// sum = sum + v * x with v = F::wv's value (Dec<F>::wa + wb, the same float operations on the same table words and
// per-segment state) and x the same address, in the same (segment, block, element) order; only updates of DIFFERENT
// accumulators interleave; the same R2_XSUM reduction and lane 0's store at om[slot * rows + r]. The prefetches add
// loads whose results are discarded. Every prefetch address lies inside the x row of a slot of the group (block
// b + XP < NB) or inside a row of the weight bank of a valid job, so no access leaves the allocations.
#pragma once
#include <type_traits>
#include <utility>
#include <sycl/ext/oneapi/experimental/prefetch.hpp>
#include "stage2/packet3/kernels/sycl_v41_routed_rux4.hpp"

#ifdef __SYCL_DEVICE_ONLY__
// IGC's LSC prefetch builtin (IGC resolves __builtin_IB_lsc_* by name): base, element offset, LSC_LDCC cache control
extern "C" SYCL_EXTERNAL void __builtin_IB_lsc_prefetch_global_uchar(const __attribute__((opencl_global)) uint8_t *base,
                                                                      int imm_elem_off, int cache_opt);
// OpenCL cl_intel_subgroup_buffer_prefetch (C++ name = the built-in library's _Z34intel_sub_group_block_prefetch_ul4PU3AS1Km):
// the sub-group prefetches 32 lanes x 4 ulongs = 1 KB from ONE (sub-group uniform) address
SYCL_EXTERNAL void intel_sub_group_block_prefetch_ul4(const __attribute__((opencl_global)) uint64_t *p);
#endif
namespace ops41sycl {
namespace rux6 {
// LSC_LDCC value for L1 cached + L3 cached (machine code: isa/pft7, `load.ugm.d8u32.a64.ca.ca (32|M0) null`)
inline constexpr int PFCC_L1C_L3C = 4;
// Prefetches: the SYCL prefetch extension (sycl::ext::oneapi::experimental::prefetch, default hint = L1): each work-item
// names one address, IGC lowers it to an LSC load with a null destination and per-lane addresses (no inline asm). A
// request brings the address's 64-byte line into L1 (+ L3); it moves no value into a register.
template <unsigned PK = 0> [[gnu::always_inline]] inline void pfl(const void *p) {
    if constexpr (PK == 0) {
        sycl::ext::oneapi::experimental::prefetch(const_cast<void *>(p));
    } else {
#ifdef __SYCL_DEVICE_ONLY__
        // IGC LSC prefetch builtin: per-lane address (IGC builds the message), cache control LSC_LDCC PFCC_L1C_L3C
        __builtin_IB_lsc_prefetch_global_uchar((const __attribute__((opencl_global)) uint8_t *)p, 0, PFCC_L1C_L3C);
#else
        (void)p;
#endif
    }
}
// quant bytes per block of a packed row (the part segment S reads: [4 S QB, 4 (S + 1) QB)), per format
template <typename F> struct QBytes;
template <unsigned NB> struct QBytes<RU3IQ2XXS<NB>> { static constexpr unsigned QB = 64; };
template <unsigned NB> struct QBytes<RU3IQ2S<NB>> { static constexpr unsigned QB = 64; };
template <unsigned NB> struct QBytes<RU3IQ2XS<NB>> { static constexpr unsigned QB = 64; };
template <unsigned NB> struct QBytes<RU3IQ1S<NB>> { static constexpr unsigned QB = 32; };
template <unsigned NB> struct QBytes<RU3IQ3XXS<NB>> { static constexpr unsigned QB = 96; };
// prefetch the 1 KB x block at blk: lane l names blk + 8 l floats (two lanes per line: the block's 16 lines, one message)
template <unsigned PK = 0> [[gnu::always_inline]] inline void pf1k(const float *blk, unsigned lane) {
    if constexpr (PK == 2) { // blk: sub-group uniform, 8-byte aligned (x rows are 1 KB blocks)
#ifdef __SYCL_DEVICE_ONLY__
        intel_sub_group_block_prefetch_ul4((const __attribute__((opencl_global)) uint64_t *)blk);
#endif
        (void)lane;
    } else {
        pfl<PK>(blk + 8 * lane);
    }
}
} // namespace rux6

template <typename F, unsigned MT, unsigned R = 2, unsigned E = 8, unsigned XA = 0, unsigned PF = 0, unsigned LV = 0,
          unsigned G = 128, unsigned W = 0, unsigned XP = 1, unsigned XW = 0, unsigned WP = 0, unsigned PK = 0>
struct RoutedUX {
    static constexpr unsigned GRF = G;
    static constexpr unsigned WGCAP = W; // (the backend: launch_rows' max_wg lowered to W when W > 0)
    static_assert(MT >= 1 && MT <= RUGrp::CAP, "1 .. 16 slots per group");
    static_assert(R >= 1 && R <= 8, "rows per tile: 1 .. 8 (tiles only where rows % R == 0)");
    static_assert(E == 2 || E == 4 || E == 8, "elements per lane per x load: 2, 4, 8");
    static_assert(XA <= 3 && PF <= 1 && LV <= 1, "XA 0..3, PF 0..1, LV 0..1");
    static_assert(XP <= 4 && XW <= 2 && WP <= 2 && PK <= 2, "XP 0..4, XW 0..2, WP 0..2, PK 0..2");
    static_assert(PK != 2 || WP == 0, "PK 2 (block prefetch): x only");
    static constexpr unsigned QB = rux6::QBytes<F>::QB;
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
            // rux6: x prefetch of block bp (< NB) of the group's slots, 1 KB (one message) per slot;
            // XW 1: only slot (sub-group % cnt)
            auto pf_x = [&](unsigned bp) {
                if constexpr (XW == 1) {
                    rux6::pf1k<PK>(x + sycl::select_from_group(sg, xo, sg.get_group_linear_id() % cnt) + (size_t)bp * 256, lane);
                } else if constexpr (XW == 2) { // sub-group s < cnt: slot s only (each slot asked for once per work-group)
                    const unsigned s_ = (unsigned)sg.get_group_linear_id();
                    if (s_ < cnt) rux6::pf1k<PK>(x + sycl::select_from_group(sg, xo, s_) + (size_t)bp * 256, lane);
                } else {
#pragma unroll
                    for (unsigned i = 0; i < MT; ++i)
                        if (i < cnt) rux6::pf1k<PK>(x + sycl::select_from_group(sg, xo, i) + (size_t)bp * 256, lane);
                }
            };
            if constexpr (XP > 0) // blocks 0 .. XP - 1 of the job
                for (unsigned bp = 0; bp < XP && bp < NB; ++bp) pf_x(bp);
            if constexpr (WP == 2) { // rux6: this sub-group's next job's rows (all their bytes) into L1 + L3
                unsigned qn = 0, rn = 0;
                if constexpr (RR == R && R > 1) {
                    qn = q_ + R * P;
                    rn = R;
                    if (qn >= R * ntile) qn = R * ntile + p0, rn = R * ntile + p0 < nr_ ? 1u : 0u;
                } else {
                    qn = q_ + P;
                    rn = qn < nr_ ? 1u : 0u;
                }
                if (rn) {
                    unsigned un_ = qn / rows;
                    const unsigned rq = qn % rows;
                    const uint8_t *wq = w;
                    if (un_ >= nu) un_ -= nu, wq = w2;
                    const uint8_t *rb = wq + ((size_t)grp[RUGrp::EXP + un_] * rows + rq) * F::RB;
                    const unsigned nbytes = rn * (unsigned)F::RB; // rn consecutive rows of one expert
                    for (unsigned o = 0; o < nbytes; o += 2048) // lane l: the line at o + 64 l (2 KB per message)
                        if (o + 64 * lane < nbytes) rux6::pfl<PK>(rb + o + 64 * lane);
                }
            }
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
                if constexpr (WP >= 1) // rux6: segment S + 1's quant bytes of the RR rows (<= 384 B: one message per row)
                    if (4 * S + 4 < NB)
                        r2::sfor<RR>([&](auto hk) {
                            const uint8_t *qs = ra + decltype(hk)::value * F::RB + (size_t)(4 * S + 4) * QB;
                            const unsigned nbq = (4 * S + 8 <= NB ? 4 : NB - 4 * S - 4) * QB;
                            if (64 * lane < nbq) rux6::pfl<PK>(qs + 64 * lane);
                        });
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
                    if constexpr (XP > 0 && e0 == 0) // rux6: block 4 S + bb + XP's x into L1
                        if (4 * S + bb + XP < NB) pf_x(4 * S + bb + XP);
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

// rux6-1 selection (OWN_RUX6=1, the MT 6 prompt launches of rux4's picks): per (format, blocks) the prefetch parameters
// added to rux4's pick (Rux4Pick: the same R, E, XA, LV, G, W). XP = WP = 0 or no rux4 pick: no rux6 form (the launch
// keeps rux4's / today's kernel). Bench: bench_rux6 on card 1, real picks at 256 / 512 tokens (README).
template <iq3::Type TY, unsigned NB> struct Rux6Pick {
    static constexpr unsigned XP = 0, XW = 0, WP = 0, PK = 0;
};
//RUX6PICKS
// (out/run-x4a .. x10a, card 1, real 256 / 512 tokens, against rux4's pick in the same rounds; the engine's own type
// Rux6Q confirmed in out/run-x11a .. x11c; /home/steve/dsv41-work/rux6/README.md section 2)
// pairs: x per token is shared by the 6 experts' groups (already in L3): one sub-group per slot block-prefetches 1 KB into
// L1, 4 blocks ahead (IQ2_S -6.1 / -7.7 %, IQ1_S -7.0 / -7.2 %); IQ2_XXS pair: no form helps (none)
template <> struct Rux6Pick<iq3::Type::IQ2_S, 20> {
    static constexpr unsigned XP = 4, XW = 1, WP = 0, PK = 2;
};
template <> struct Rux6Pick<iq3::Type::IQ1_S, 20> {
    static constexpr unsigned XP = 4, XW = 1, WP = 0, PK = 2;
};
// downs: x per slot is new (from DRAM): the SYCL prefetch (L3) of the next block, one sub-group per slot -- the two-row
// forms (16 sub-groups on one group): XW 2; the four-row forms (work-groups straddle groups): XW 1
// (256 / 512 tokens: IQ3_XXS -11.2 / -17.3 %, IQ2_S -18.7 / -22.6 %, IQ2_XS -18.5 / -21.8 %, IQ2_XXS -13.8 / -19.8 %)
template <> struct Rux6Pick<iq3::Type::IQ3_XXS, 9> {
    static constexpr unsigned XP = 2, XW = 1, WP = 0, PK = 0;
};
template <> struct Rux6Pick<iq3::Type::IQ2_S, 9> {
    static constexpr unsigned XP = 1, XW = 2, WP = 0, PK = 0;
};
template <> struct Rux6Pick<iq3::Type::IQ2_XS, 9> {
    static constexpr unsigned XP = 1, XW = 2, WP = 0, PK = 0;
};
template <> struct Rux6Pick<iq3::Type::IQ2_XXS, 9> {
    static constexpr unsigned XP = 1, XW = 1, WP = 0, PK = 0;
};
//RUX6PICKS_END
namespace rux6 {
template <iq3::Type TY, unsigned NB> struct Fmt;
template <unsigned NB> struct Fmt<iq3::Type::IQ2_XXS, NB> { using T = RU3IQ2XXS<NB>; };
template <unsigned NB> struct Fmt<iq3::Type::IQ2_S, NB> { using T = RU3IQ2S<NB>; };
template <unsigned NB> struct Fmt<iq3::Type::IQ3_XXS, NB> { using T = RU3IQ3XXS<NB>; };
template <unsigned NB> struct Fmt<iq3::Type::IQ2_XS, NB> { using T = RU3IQ2XS<NB>; };
template <unsigned NB> struct Fmt<iq3::Type::IQ1_S, NB> { using T = RU3IQ1S<NB>; };
} // namespace rux6
// a rux6 form exists for (TY, NB): rux4 has a pick there and rux6 adds a prefetch
template <iq3::Type TY, unsigned NB>
inline constexpr bool rux6_has = Rux4Pick<TY, NB>::R != 0 && (Rux6Pick<TY, NB>::XP != 0 || Rux6Pick<TY, NB>::WP != 0);
template <iq3::Type TY, unsigned NB, typename P = Rux4Pick<TY, NB>, typename Q = Rux6Pick<TY, NB>>
using Rux6Q = RoutedUX<typename rux6::Fmt<TY, NB>::T, 6, (P::R ? P::R : 1u), P::E, P::XA, P::PF, P::LV, P::G, P::W, Q::XP,
                       Q::XW, Q::WP, Q::PK>;

} // namespace ops41sycl
