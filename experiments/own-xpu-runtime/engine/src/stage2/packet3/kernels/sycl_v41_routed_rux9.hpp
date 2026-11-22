// rux9 (2026-11-17): prompt routed-expert rows with the work-group's x blocks staged once in local memory (SLM) and
// read from there by every row of the job. The bench: /home/steve/dsv41-work/rux9 (bench_rux9.cpp, README); the engine:
// OWN_RUX9 (rux9-1, opt-in; backend_sycl_v41_mt.inc routed_m: IQ2_S gate + up, 20 blocks, on forms A1 / A1w / A3 / B1).
// BITWISE production on the same groups (RUGrp, ExpertGroupM): OWN_RUX6=1's Rux6Q (IQ2_S / IQ1_S gate + up, the downs)
// and RoutedIQ2XXSUP (IQ2_XXS gate + up), i.e. RoutedUT / RoutedU3 / RoutedU (sycl_v41_routed_rux.hpp, _r2.hpp).
//
// Why (rux6 ledger, /home/steve/dsv41-work/rux6/README.md): IQ2_S gate + up (26 % of card 2's routed prompt time) runs
// at 74 clocks per (row-block, slot) against a ~38-41 clock issue floor. Removing the per-slot x reads saved 39 %, the
// decode 28 %. Each sub-group reads every slot's 1 KB x block itself from L1 (16 sub-groups read the same lines at the
// same time, each job's x is new to L1) and waits for it right before that slot's products.
//
// RoutedS9<F, MT, RR, E, EX, XA, XB, WGS, LV, WP, G>:
//   work-group  WGS items = NSG = WGS / 32 sub-groups; a job = one expert group u, one matrix (gate or up), RT = NSG RR
//               consecutive rows; sub-group s takes rows RT t + RR s + h (h < RR). Jobs: work-group w takes w, w + nwg,
//               ... (job = (matrix, group, tile), the order production's row list has). Every loop bound and branch
//               around a barrier is work-group uniform.
//   x slab      after the decoder's grid table in the same local buffer (the table stays at offset 0, which IQ1_S's
//               ld16 needs): 2 buffers x MT slots x XB blocks x 256 floats. A "stage" = XB blocks. At the start of
//               stage st every sub-group issues its share of stage st + 1's x (FN global block reads of 32 floats of the
//               group's slots) into registers, the rows compute stage st from buffer (gb + st) & 1, then the registers
//               are stored into the other buffer and ONE local-memory barrier (SLM fence only) closes the stage. The
//               x read of a job therefore costs one 128-byte global read per 32 floats per WORK-GROUP (not per
//               sub-group) and its latency runs under a stage of compute; the rows read x from SLM (lower latency than
//               L1 hits, no misses). gb = stages run by this work-group before the job, so a job's first fill never
//               writes the buffer the previous job's last stage may still be reading.
//   RR          rows per sub-group (1, 2): every SLM x read feeds RR rows (RR = 2: 512 B of x per (row-block, slot),
//               as production; RR = 1: 1 KB, the low-register fallback)
//   E           decode sub-block: RR x E grid gathers issued back to back (rux4's phase A), then the values (phase B)
//   EX          x values read per slot at once (<= E): the products of a slot run in E / EX parts of EX elements
//   XA          0: a slot's SLM x read right before its products; 1: slot i + 1's read before slot i's products (EX = E)
//   XB          blocks per stage (1, 2): one barrier per stage
//   WGS         512 or 1024 (1024: 2 work-groups per Xe-core at 128 registers, so the 32 KB table plus the slab fits
//               twice in 128 KB of SLM; 512 with the slab may drop to 2 work-groups per Xe-core: the P1 probe)
//   LV          rux4's gather form (0: plain loads, production's pick for every pair format)
//   WP          rows ahead: 0 none; >= 1: at each job start the NEXT job's rows of this sub-group (all their bytes),
//               rux6::pfl<0> (SYCL prefetch, default hint, as Rux6Q's rows ahead with PK 0); 2: + at each segment's
//               first stage the next segment's quant bytes, rux6::pfl<1> (LSC prefetch, L1 + L3 cached). Barriers line up the sub-groups, so their row reads at a segment start would wait
//               on memory all at once; WP moves those waits off the barrier-synchronised path. No value changes.
//   G           register mode (128)
// No inline asm beyond production's own decoder helpers; no matrix engines.
//
// Bit-identity, per output (slot s = group u's slot i, row r). Production: one sub-group; lane l keeps one accumulator
// per (row, slot), starts at 0.0f and, for S = 0 .. NS - 1 (unit T = S / SPU from F::unit, segment state from
// F::seg<S % SPU>), bb = 0 .. NBS(S) - 1, g = 0 .. 7, does acc = acc + v * x (multiply, then add; -ffp-contract=off)
// with v = Dec<F>::wb<8 bb + g>(f, sg, Sg, Dec<F>::wa<8 bb + g, LV>(f, Sg)) (= F::wv's value) and x = the float at
// column 256 (4 S + bb) + 32 g + l of the slot's x row; then R2_XSUM (OWN_R2_XORP's lowering) and lane 0 stores
// om[slot * rows + r]. Here: the same F::row / F::unit / F::seg calls on the same row bytes, the same table (F::fill,
// offset 0), the same wa / wb template arguments M = 8 bb + e0 + g (E only cuts g = 0 .. 7 into sub-blocks taken in
// ascending order; EX cuts them again into parts taken in ascending order), the same x float (the slab holds a bitwise
// copy: one float block load and one float store, no arithmetic; column 256 (4 S + bb) + 32 (e0 + p EX + q) + l is
// read at slab[i SW + (bb - b0) 256 + 32 (e0 + p EX + q) + l]), the same `sum = sum + v * x` in the same (S, bb, g)
// order. Only updates of DIFFERENT accumulators interleave (other rows, other slots); XA = 1 only moves a read
// earlier. Then the same R2_XSUM and the same store. Which sub-group / work-group sums a row changes nothing: each
// (row, slot) is summed whole by one sub-group, as in production. So every output float is production's.
#pragma once
#include <type_traits>
#include <utility>
#include "stage2/packet3/kernels/sycl_v41_routed_rux6.hpp"

namespace ops41sycl {

template <typename F, unsigned MT = 6, unsigned RR = 2, unsigned E = 4, unsigned EX = 4, unsigned XA = 0, unsigned XB = 2,
          unsigned WGS = 1024, unsigned LV = 0, unsigned WP = 0, unsigned G = 128>
struct RoutedS9 {
    static constexpr unsigned GRF = G;
    static constexpr unsigned WG = WGS;                    // launch: work-group size (items)
    static constexpr unsigned NSG = WGS / 32;              // sub-groups per work-group
    static constexpr unsigned RRV = RR;                    // rows per sub-group (host check: rows % RRV == 0)
    static constexpr unsigned RT = NSG * RR;               // rows per job
    static constexpr unsigned WGCAP = WGS == 1024 ? 64u : 128u; // launch: work-groups (one wave at 128 registers)
    static constexpr unsigned NB = F::NB, SPU = F::SPU, NS = F::NS;
    static constexpr unsigned NFU = (NB / 4) / SPU;
    static constexpr unsigned NST = (NB + XB - 1) / XB;    // stages per job
    static constexpr unsigned SW = XB * 256;               // slab floats per slot (one stage)
    static constexpr unsigned BUF = MT * SW;               // slab floats per buffer
    static constexpr unsigned NCH = MT * XB * 8;           // 32-float chunks per stage (all MT slots)
    static constexpr unsigned FN = (NCH + NSG - 1) / NSG;  // chunks per sub-group per stage (registers held)
    static constexpr unsigned TAB = F::TAB + 2 * BUF;      // local floats: grid table at 0, then the two buffers
    static constexpr unsigned QB = rux6::QBytes<F>::QB;    // quant bytes per block of a packed row
    static_assert(WGS == 512 || WGS == 1024, "work-groups of 512 or 1024 items");
    static_assert(MT >= 1 && MT <= 8, "1 .. 8 slots per group");
    static_assert(RR >= 1 && RR <= 2, "1 or 2 rows per sub-group");
    static_assert(E == 2 || E == 4 || E == 8, "decode sub-block: 2, 4, 8 elements");
    static_assert(EX >= 1 && EX <= E && E % EX == 0, "x parts divide the sub-block");
    static_assert(XA == 0 || (XA == 1 && EX == E), "XA 1: one x read per slot and sub-block");
    static_assert(XB == 1 || XB == 2, "1 or 2 blocks per stage");
    static_assert(LV <= 1 && WP <= 2, "LV 0..1, WP 0..2");
    static_assert(TAB * 4u <= 131072u, "local memory of one work-group");
    using D = rux4::Dec<F>;
    unsigned rows;
    bool per_slot_x;
    NoRows ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    unsigned nexp = 0;
    unsigned tile_nsl = 96; // (unused: every block runs the row tiles; kept for the backend's / bench's setters)

    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *grp,
                                     float *out, float *tab) const {
        F::fill(it, tab);
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const unsigned sgi = sg.get_group_linear_id();
        const F f(lane, tab);
        float *const slab = tab + F::TAB;
        const unsigned nu = grp[0];
        const unsigned ntl = (rows + RT - 1) / RT;
        const unsigned njob = (w2 ? 2u : 1u) * nu * ntl;
        const unsigned nwg = (unsigned)it.get_group_range(0);
        unsigned gb = 0; // stages this work-group ran before the job: stage st uses slab buffer (gb + st) & 1
#pragma unroll 1
        for (unsigned job = (unsigned)it.get_group_linear_id(); job < njob; job += nwg) {
            unsigned u = job / ntl;
            const unsigned r0 = (job % ntl) * RT + sgi * RR;
            // rows % RR == 0 (host check): a sub-group's rows are all valid or all past the end. Past the end (only
            // where RT does not divide rows): the sub-group runs row 0 (a valid row) through every stage and barrier,
            // and stores nothing.
            const bool active = r0 < rows;
            const unsigned r = active ? r0 : 0u;
            const uint8_t *wm = w;
            float *om = out;
            if (u >= nu) {
                u -= nu;
                wm = w2;
                om = out2;
            }
            const unsigned cnt = grp[RUGrp::CNT + u]; // 1 .. MT (host / ExpertGroupM groups of at most MT slots)
            const uint32_t sl = lane < cnt ? grp[RUGrp::SLOT + u * RUGrp::CAP + lane] : 0u;
            const uint32_t xo = (sl / 6) * xtok + (per_slot_x ? (sl % 6) * (NB * 256) : 0u);
            const unsigned eid = grp[RUGrp::EXP + u];
            const uint8_t *ra = wm + ((size_t)eid * rows + r) * F::RB;
            if constexpr (WP >= 1) { // the next job's rows of this sub-group (all their bytes), SYCL prefetch
                const unsigned jn = job + nwg;
                if (jn < njob) {
                    unsigned un_ = jn / ntl;
                    const unsigned rn = (jn % ntl) * RT + sgi * RR;
                    const uint8_t *wq = w;
                    if (un_ >= nu) un_ -= nu, wq = w2;
                    if (rn < rows) {
                        const uint8_t *rb = wq + ((size_t)grp[RUGrp::EXP + un_] * rows + rn) * F::RB;
                        constexpr unsigned NBY = RR * (unsigned)F::RB; // RR consecutive rows of one expert
                        r2::sfor<(NBY + 2047) / 2048>([&](auto ok) { // lane l: the line at o + 64 l (2 KB per message)
                            const unsigned o = (unsigned)decltype(ok)::value * 2048u + 64u * lane;
                            if (o < NBY) rux6::pfl<0>(rb + o);
                        });
                    }
                }
            }
            // ---- x slab: stage st = blocks [XB st, XB st + XB) of the group's cnt slots -----------------------------
            // chunk c (sub-group uniform: c = sgi + NSG k) = slot c / (8 XB), block XB st + (c / 8) % XB, floats
            // 32 (c % 8) .. + 31 of that block; slab offset i SW + 32 (c % (8 XB)). Every address stays inside the
            // slot's x row (block < NB, slot < cnt) and inside the slab.
            float fr[FN];
            auto fill_load = [&](unsigned st) {
                r2::sfor<FN>([&](auto kk) {
                    constexpr unsigned k = decltype(kk)::value;
                    const unsigned c = sgi + NSG * k, i = c / (XB * 8), b = st * XB + (c / 8) % XB;
                    if (c < NCH && i < cnt && b < NB)
                        fr[k] = sg_bload(sg, x + sycl::select_from_group(sg, xo, i) + (size_t)b * 256 + (c % 8) * 32);
                });
            };
            auto fill_store = [&](unsigned st) {
                float *const sb = slab + ((gb + st) & 1u) * BUF;
                r2::sfor<FN>([&](auto kk) {
                    constexpr unsigned k = decltype(kk)::value;
                    const unsigned c = sgi + NSG * k, i = c / (XB * 8), b = st * XB + (c / 8) % XB;
                    if (c < NCH && i < cnt && b < NB) sb[i * SW + (c % (XB * 8)) * 32 + lane] = fr[k];
                });
            };
            // stage st: next stage's x into registers, this stage's compute, store, one barrier (none after the last:
            // the next job's first fill goes to the other buffer, see gb)
            auto stage = [&](unsigned st, auto &&compute) {
                const bool more = st + 1 < NST; // work-group uniform
                if (more) fill_load(st + 1);
                compute(static_cast<const float *>(slab + ((gb + st) & 1u) * BUF));
                if (more) {
                    fill_store(st + 1);
                    it.barrier(sycl::access::fence_space::local_space);
                }
            };
            // WP 2: segment S + 1's quant bytes of the RR rows (<= 384 B: one message per row) into L1 + L3
            auto pf_seg = [&](unsigned S) {
                if constexpr (WP >= 2) {
                    if (4 * S + 4 < NB) {
                        const unsigned nbq = (4 * S + 8 <= NB ? 4u : NB - 4 * S - 4) * QB;
                        r2::sfor<RR>([&](auto hk) {
                            const uint8_t *qs = ra + decltype(hk)::value * F::RB + (size_t)(4 * S + 4) * QB;
                            if (64 * lane < nbq) rux6::pfl<1>(qs + 64 * lane);
                        });
                    }
                } else {
                    (void)S;
                }
            };
            typename F::Row rr[RR];
            r2::sfor<RR>([&](auto hk) { f.row(sg, ra + decltype(hk)::value * F::RB, rr[decltype(hk)::value]); });
            float sum[RR][MT];
#pragma unroll
            for (unsigned h = 0; h < RR; ++h)
#pragma unroll
                for (unsigned i = 0; i < MT; ++i) sum[h][i] = 0;
            fill_load(0); // the job's first stage (its latency runs beside the row loads above)
            fill_store(0);
            it.barrier(sycl::access::fence_space::local_space);
            // one decode sub-block: chunks M = 8 bb + e0 + g (g < E) of segment state sgs, x of the block at xp
            // (slab, slot 0, lane's column of element e0), then every slot's products
            auto sub = [&](auto bbk, auto e0k, const typename F::Sg (&sgs)[RR], const float *xp) {
                constexpr unsigned bb = decltype(bbk)::value, e0 = decltype(e0k)::value;
                uint32_t raw[RR][E];
                r2::sfor<E>([&](auto gk) { // phase A: every gather of the sub-block, back to back
                    constexpr unsigned g = decltype(gk)::value;
                    r2::sfor<RR>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        raw[h][g] = D::template wa<8 * bb + e0 + g, LV>(f, sgs[h]);
                    });
                });
                float v[RR][E];
                r2::sfor<E>([&](auto gk) { // phase B: the values (F::wv's float operations)
                    constexpr unsigned g = decltype(gk)::value;
                    r2::sfor<RR>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        v[h][g] = D::template wb<8 * bb + e0 + g>(f, sg, sgs[h], raw[h][g]);
                    });
                });
                // slot i, part p: elements p EX + q (q < EX) = lane's columns 32 (e0 + p EX + q) of the block
                auto xread = [&](auto ik, auto pk) {
                    constexpr unsigned i = decltype(ik)::value, p = decltype(pk)::value;
                    sycl::vec<float, EX> xv;
                    r2::sfor<EX>([&](auto qk) {
                        constexpr unsigned q = decltype(qk)::value;
                        xv[q] = xp[i * SW + (p * EX + q) * 32];
                    });
                    return xv;
                };
                auto prod = [&](auto ik, auto pk, const sycl::vec<float, EX> &xv) {
                    constexpr unsigned i = decltype(ik)::value, p = decltype(pk)::value;
                    r2::sfor<EX>([&](auto qk) {
                        constexpr unsigned q = decltype(qk)::value;
                        r2::sfor<RR>([&](auto hk) {
                            constexpr unsigned h = decltype(hk)::value;
                            sum[h][i] = sum[h][i] + v[h][p * EX + q] * xv[q];
                        });
                    });
                };
                if constexpr (XA == 0) {
                    r2::sfor<MT>([&](auto ik) {
                        constexpr unsigned i = decltype(ik)::value;
                        if (i < cnt) r2::sfor<E / EX>([&](auto pk) { prod(ik, pk, xread(ik, pk)); });
                    });
                } else {
                    // nested as RoutedUP's XA 1: slot i's block holds slot i + 1's read
                    using P0 = std::integral_constant<unsigned, 0>;
                    auto chain = [&](auto self, auto ik, const sycl::vec<float, EX> &xv) -> void {
                        constexpr unsigned i = decltype(ik)::value;
                        if constexpr (i + 1 < MT) {
                            if (i + 1 < cnt) {
                                const sycl::vec<float, EX> xn = xread(std::integral_constant<unsigned, i + 1>{}, P0{});
                                prod(ik, P0{}, xv);
                                self(self, std::integral_constant<unsigned, i + 1>{}, xn);
                            } else {
                                prod(ik, P0{}, xv);
                            }
                        } else {
                            prod(ik, P0{}, xv);
                        }
                    };
                    chain(chain, P0{}, xread(P0{}, P0{})); // slot 0: every group has one
                }
            };
            // NBS blocks of segment S, XB blocks per stage (XB divides 4: stages never straddle a segment)
            auto blocks = [&](auto nbs, unsigned S, const typename F::Sg (&sgs)[RR]) {
                constexpr unsigned NBS = decltype(nbs)::value;
                r2::sfor<(NBS + XB - 1) / XB>([&](auto tk) {
                    constexpr unsigned b0 = decltype(tk)::value * XB;
                    constexpr unsigned NBT = NBS - b0 < XB ? NBS - b0 : XB;
                    if constexpr (b0 == 0) pf_seg(S);
                    stage((4 * S + b0) / XB, [&](const float *xs) {
                        r2::sfor<NBT>([&](auto bk) {
                            constexpr unsigned bb = b0 + decltype(bk)::value;
                            const float *xp = xs + (bb - b0) * 256 + lane;
                            r2::sfor<8 / E>([&](auto kk) {
                                constexpr unsigned e0 = decltype(kk)::value * E;
                                sub(std::integral_constant<unsigned, bb>{}, std::integral_constant<unsigned, e0>{}, sgs,
                                    xp + e0 * 32);
                            });
                        });
                    });
                });
            };
            // production's unit / segment walk (RoutedUP): NFU units of SPU segments, then the last unit's segments
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
            if (active) {
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
            }
            gb += NST;
        }
    }
};

} // namespace ops41sycl
