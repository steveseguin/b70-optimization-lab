// Weight-stationary dense rows for prompt blocks of M tokens (prefill plan 2026-11-11, step A), one card.
// The engine's M-token forms (DenseRowsG<D, G> / DenseRowsGR<D, G, R>, D = GemvQ8P / GemvQ6KP / GemvQ5KP) decode
// every weight once per token group of G = 4 (8 on output-b): rowg<NT> loads all NT tokens' activations first
// and then runs the products, so G is held to 4-8 by registers. The forms here ("rowt<T, R>") decode a quant
// word's values for R rows once into registers and then stream T = 8 / 16 tokens past them, one activation block
// per token. For EVERY (row, token) the lane sum is the same serial chain as rowg / rowgr (chunks ascending, the
// value d * float(q) (Q8_0), (d * scale) * float(code - 32) (Q6_K), f * float(code) - o (Q5_K), times the
// activation, added to the running sum, from 0), and the lane sums are reduced by sg_tree32's additions: either
// sg_tree32 itself (TREE = 0) or tree32_n below (TREE = 1), which forms the same additions with the same operands
// in the same order for all R * T sums at once (every lane busy) and leaves sum s in lane s. Only the order in
// which independent sums advance and how registers are reused changes, so every output is bit-identical; the
// bench checks that per (row, token) with memcmp against the one-token kernel and against the engine form.
//
// Shapes: a 12-head card's matrices (as bench_dense_m16.cpp) plus the engine's q_a / kv / shared gate+up launches;
// M = 16 / 32 / 64 tokens; cold (256 MiB read between launches), event timing, median of REPS launches.
//   env ONLY=<substring of shape names>  MS=16,32,64  REPS=21  REAL=1 (also check bitwise on real GGUF rows)
//       FMT=8|6|5|865 (formats to run; default all)  NOTIME=1 (bitwise only)
//
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src -I tools/bench tools/bench/bench_dense_ws.cpp -o $S/bench_dense_ws
//   LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib \
//     ONEAPI_DEVICE_SELECTOR=level_zero:3 $S/bench_dense_ws
// -DWS_CK=1 (binary bench_dense_ws_ck): the guessing checks' blocks of 2 .. 6 tokens instead (MS default 2,3,4,5,6;
// FMT=865h, h = the H16 rows): the engine's check forms (tg87 BEST: token groups 1 / 3 / 2 / 3 / 3, R = 4 from 4,096
// rows) against forms that decode each weight once for the whole block (T = M).
// Built with the OWN_MT_WS patch's header first on the include path (-I <patched tree>/src -I src; the header
// defines OPS41_DENSE_WS): the patch's forms instead (ops41sycl::WsTab picks through ws_rows, the kernel types the
// engine launches) against the engine's form for the same launch at MS = 2-6 and 9-256 tokens (see "Patched
// header" below; -DWS_ALT=1 adds the candidate forms the tables were chosen from).
// Exit status 1 on any mismatch.
#include <sycl/sycl.hpp>
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>
#include <fcntl.h>
#include <unistd.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
using namespace ops41sycl;

#ifndef OPS41_DENSE_WS // the explorer's forms (the unpatched header); patched: the header's (ops41sycl::WsTab)
// ---------------------------------------------------------------------------------------------------------------
// sg_tree32 for N sums at once. sg_tree32 on one value: for w = 1, 2, 4, 8, 16, lane l with l % 2w == 0 becomes
// v_l + v_{l+w}; the result is lane 0's. Here a[0..N-1] are N such values. Step w < N pairs registers 2i, 2i+1:
// lanes with bit w clear keep register 2i's block sums, lanes with bit w set register 2i+1's, so after step w a
// block of 2w lanes starting at lane L of sum s (s's low bits = its slot) sits at lane L + slot. Each addition is
// (lower lane's partial) + (upper lane's partial), as in sg_tree32. Steps w >= N run on the one register left;
// lanes with bit w set compute values nobody reads. Lane s < N returns sum s's sg_tree32 value, bit for bit.
template <unsigned N, unsigned W = 1> [[gnu::always_inline]] inline void tree32_steps(sycl::sub_group sg, unsigned lane, float (&a)[N]) {
    if constexpr (W < 32) {
        const bool lo = (lane & W) == 0;
        if constexpr (W < N) {
#pragma unroll
            for (unsigned i = 0; i < N / (2 * W); ++i) {
                const float A = a[2 * i], B = a[2 * i + 1];
                const float S = lo ? B : A;                              // lane l^W of S: A's (l lo) or B's (l hi)
                const float Sx = sycl::permute_group_by_xor(sg, S, W);  // lo lane: A[l + W]; hi lane: B[l - W]
                const float lhs = lo ? A : Sx, rhs = lo ? Sx : B;        // lower lane first
                a[i] = lhs + rhs;
            }
        } else {
            // sg_tree32's own shuffle ((lane + W) % 32 = lane ^ W on the lanes read). NOT permute_group_by_xor: IGC
            // matches back-to-back xor-butterfly adds (N = 8: W = 8 then 16) as a sub-group reduction and reorders
            // them ((a_l + a_l+16) + (a_l+8 + a_l+24), ws-q8a.log: T8 R1 differed on 36 % of the values)
            const float o = sycl::select_from_group(sg, a[0], (lane + W) % 32);
            a[0] = a[0] + o; // lo lanes: v_l + v_{l+W}
        }
        tree32_steps<N, W * 2>(sg, lane, a);
    }
}
template <unsigned N> [[gnu::always_inline]] inline float tree32_n(sycl::sub_group sg, unsigned lane, float (&a)[N]) {
    static_assert(N >= 1 && N <= 32 && (N & (N - 1)) == 0);
    tree32_steps<N>(sg, lane, a);
    return a[0];
}
static constexpr unsigned pow2_at_least(unsigned n) {
    unsigned p = 1;
    while (p < n) p *= 2;
    return p;
}
// R * T sums (index j * T + t) -> y[t * ys + r0 + j] for r0 + j < rows and t < mt. TREE = 1 with R * T not a power
// of two: padded with zero sums (a lane's result only ever adds partials of one sum: the pads reach no store)
template <unsigned R, unsigned T, unsigned TREE>
[[gnu::always_inline]] inline void reduce_store(sycl::sub_group sg, unsigned lane, float (&sum)[R * T], unsigned r0,
                                                unsigned rows, float *y, size_t ys, unsigned mt) {
    if constexpr (TREE == 0) {
#pragma unroll
        for (unsigned i = 0; i < R * T; ++i) sum[i] = sg_tree32(sg, sum[i]);
        if (lane == 0) {
#pragma unroll
            for (unsigned j = 0; j < R; ++j)
                if (r0 + j < rows)
#pragma unroll
                    for (unsigned t = 0; t < T; ++t)
                        if (t < mt) y[t * ys + r0 + j] = sum[j * T + t];
        }
    } else {
        constexpr unsigned NP = pow2_at_least(R * T);
        float a[NP];
#pragma unroll
        for (unsigned i = 0; i < NP; ++i) a[i] = i < R * T ? sum[i] : 0.0f;
        const float v = tree32_n<NP>(sg, lane, a);
        const unsigned j = lane / T, t = lane % T;
        if (lane < R * T && r0 + j < rows && t < mt) y[t * ys + r0 + j] = v;
    }
}

// ---------------------------------------------------------------------------------------------------------------
// Q8_0 packed rows (pack_v41: [C/4 x 32 words: word 32m + l = bytes of chunks 4m..4m+3 at column l][C halves d]).
// rowt<T, R, XW, TREE, LOOP>: R rows r0.., T tokens (x + t * xs, y + t * ys, t < mt stored).
//   XW: quant words per activation block load (1: vec4 = 128 columns, 2: vec8 = 256 columns)
//   LOOP = 0: everything unrolled, the row's chunk scales loaded up front (dv[R][C/32], as rowgr);
//   LOOP = 1: a loop over segments of 8 words (32 chunks), each segment's 32 scales loaded per lane with its quant
//             words (one segment ahead), so the scale broadcast lanes stay constants (needs C % 32 == 0).
template <unsigned C> struct WsQ8 {
    unsigned rows, xn;
    static constexpr size_t RB = ((size_t)C * 34 + 15) & ~(size_t)15;
    template <unsigned R, unsigned T, unsigned XW>
    [[gnu::always_inline]] static inline void word_group(sycl::sub_group sg, const uint32_t (&q)[R][XW],
                                                         const float (&dsc)[R], unsigned c0lane, const float *xw,
                                                         size_t xs, float (&sum)[R * T]) {
        // q[j][mm]: row j's word of chunks 4 (m0 + mm) .. +3; chunk c's scale is lane (c0lane + 4 mm + k) of dsc[j]
        float e[R][4 * XW];
#pragma unroll
        for (unsigned mm = 0; mm < XW; ++mm)
#pragma unroll
            for (unsigned k = 0; k < 4; ++k)
#pragma unroll
                for (unsigned j = 0; j < R; ++j) {
                    const float d = sycl::select_from_group(sg, dsc[j], c0lane + 4 * mm + k);
                    e[j][4 * mm + k] = d * float(int8_t(uint8_t(q[j][mm] >> (8 * k)))); // iq3::decode Q8_0
                }
#pragma unroll
        for (unsigned t = 0; t < T; ++t) {
            const auto xv = sg_bloadN<4 * XW>(sg, xw + t * xs);
#pragma unroll
            for (unsigned i = 0; i < 4 * XW; ++i)
#pragma unroll
                for (unsigned j = 0; j < R; ++j) sum[j * T + t] = sum[j * T + t] + e[j][i] * xv[i];
        }
    }
    template <unsigned T, unsigned R, unsigned XW, unsigned TREE, unsigned LOOP, unsigned SEGW>
    [[gnu::always_inline]] inline void rowt(sycl::sub_group sg, unsigned lane, unsigned r0, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        constexpr unsigned NQ = C / 4, ND = (C + 31) / 32;
        const float *xr = xn ? x + (size_t)(r0 / xn) * C * 32 : x; // token t: xr + t * xs
        const uint8_t *rowp[R];
#pragma unroll
        for (unsigned j = 0; j < R; ++j) rowp[j] = w + (size_t)(r0 + j < rows ? r0 + j : r0) * RB;
        float sum[R * T];
#pragma unroll
        for (unsigned i = 0; i < R * T; ++i) sum[i] = 0;
        if constexpr (LOOP == 0) {
            constexpr unsigned SEGQ = SEGW ? SEGW : Q8Seg<C>::v; // quant words loaded ahead
            static_assert(NQ % SEGQ == 0 && SEGQ % XW == 0);
            float dv[R][ND];
#pragma unroll
            for (unsigned j = 0; j < R; ++j) {
                const uint16_t *dp = reinterpret_cast<const uint16_t *>(rowp[j] + (size_t)C * 32);
#pragma unroll
                for (unsigned k = 0; k < ND; ++k) dv[j][k] = 32 * k + lane < C ? iq3::half(dp[32 * k + lane]) : 0.0f;
            }
#pragma unroll
            for (unsigned s0 = 0; s0 < NQ; s0 += SEGQ) {
                uint32_t q[R][SEGQ];
#pragma unroll
                for (unsigned j = 0; j < R; ++j)
#pragma unroll
                    for (unsigned m = 0; m < SEGQ; ++m)
                        q[j][m] = sg_bload(sg, reinterpret_cast<const uint32_t *>(rowp[j]) + (size_t)(s0 + m) * 32);
#pragma unroll
                for (unsigned m0 = 0; m0 < SEGQ; m0 += XW) {
                    const unsigned c0 = (s0 + m0) * 4; // XW * 4 chunks never cross a 32-chunk scale register
                    static_assert(32 % (4 * XW) == 0);
                    uint32_t qq[R][XW];
                    float ds[R];
#pragma unroll
                    for (unsigned j = 0; j < R; ++j) {
                        ds[j] = dv[j][c0 / 32];
#pragma unroll
                        for (unsigned mm = 0; mm < XW; ++mm) qq[j][mm] = q[j][m0 + mm];
                    }
                    word_group<R, T, XW>(sg, qq, ds, c0 % 32, xr + (size_t)(s0 + m0) * 128, xs, sum);
                }
            }
        } else {
            static_assert(C % 32 == 0);
            constexpr unsigned NS = NQ / 8; // segments of 8 words = 32 chunks
            uint32_t q[R][8];
            float ds[R];
            auto load = [&](unsigned s, uint32_t (&qd)[R][8], float (&dd)[R]) {
#pragma unroll
                for (unsigned j = 0; j < R; ++j) {
                    const uint32_t *qw = reinterpret_cast<const uint32_t *>(rowp[j]) + (size_t)s * 256;
#pragma unroll
                    for (unsigned m = 0; m < 8; ++m) qd[j][m] = sg_bload(sg, qw + m * 32);
                    dd[j] = iq3::half(reinterpret_cast<const uint16_t *>(rowp[j] + (size_t)C * 32)[s * 32 + lane]);
                }
            };
            load(0, q, ds);
#pragma nounroll
            for (unsigned s = 0; s < NS; ++s) {
                uint32_t qn[R][8];
                float dn[R];
                if (s + 1 < NS) load(s + 1, qn, dn);
#pragma unroll
                for (unsigned m0 = 0; m0 < 8; m0 += XW) {
                    uint32_t qq[R][XW];
#pragma unroll
                    for (unsigned j = 0; j < R; ++j)
#pragma unroll
                        for (unsigned mm = 0; mm < XW; ++mm) qq[j][mm] = q[j][m0 + mm];
                    word_group<R, T, XW>(sg, qq, ds, m0 * 4, xr + (size_t)(s * 8 + m0) * 128, xs, sum);
                }
#pragma unroll
                for (unsigned j = 0; j < R; ++j) {
                    ds[j] = dn[j];
#pragma unroll
                    for (unsigned m = 0; m < 8; ++m) q[j][m] = qn[j][m];
                }
            }
        }
        reduce_store<R, T, TREE>(sg, lane, sum, r0, rows, y, ys, mt);
    }
};

// ---------------------------------------------------------------------------------------------------------------
// Q6_K packed rows (GemvQ6KP's layout and value expression). Per block b and lane: one ql word, one qh pair, 8
// chunks c; the R rows' 8 values are decoded once, then the T tokens' vec8 activation blocks stream past.
// SEGB blocks of quant words are loaded ahead (KSeg as rowgr). dbs (d * scale per lane) as rowgr.
template <unsigned NB> struct WsQ6 {
    unsigned rows, xn;
    static constexpr size_t RB = ((size_t)NB * 210 + 15) & ~(size_t)15;
    template <unsigned T, unsigned R, unsigned XW, unsigned TREE, unsigned LOOP, unsigned SEGW>
    [[gnu::always_inline]] inline void rowt(sycl::sub_group sg, unsigned lane, unsigned r0, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        static_assert(XW == 1);
        constexpr unsigned NS = NB * 16, NSR = (NS + 31) / 32, SEG = SEGW ? SEGW : KSeg<NB>::v;
        static_assert(NB % SEG == 0);
        const float *xr = xn ? x + (size_t)(r0 / xn) * NB * 256 : x;
        const uint32_t *ql[R];
        const uint16_t *qh[R];
        float dbs[R][NSR];
#pragma unroll
        for (unsigned j = 0; j < R; ++j) {
            const uint8_t *row = w + (size_t)(r0 + j < rows ? r0 + j : r0) * RB;
            ql[j] = reinterpret_cast<const uint32_t *>(row);
            qh[j] = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 128);
            const int8_t *scl = reinterpret_cast<const int8_t *>(row + (size_t)NB * 192);
            const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 208);
#pragma unroll
            for (unsigned k = 0; k < NSR; ++k) {
                const unsigned si = 32 * k + lane < NS ? 32 * k + lane : NS - 1;
                dbs[j][k] = iq3::half(dp[si >> 4]) * float(int(scl[si]));
            }
        }
        float sum[R * T];
#pragma unroll
        for (unsigned i = 0; i < R * T; ++i) sum[i] = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NB; s0 += SEG) {
            uint32_t qa[R][SEG], qb[R][SEG];
#pragma unroll
            for (unsigned j = 0; j < R; ++j)
#pragma unroll
                for (unsigned m = 0; m < SEG; ++m) {
                    qa[j][m] = sg_bload(sg, ql[j] + (size_t)(s0 + m) * 32);
                    qb[j][m] = qh[j][(size_t)(s0 + m) * 32 + lane];
                }
#pragma unroll
            for (unsigned m = 0; m < SEG; ++m) {
                const unsigned b = s0 + m;
                float v[R][8];
#pragma unroll
                for (unsigned c = 0; c < 8; ++c) {
                    const unsigned h = c >> 2, cc = c & 3u;
                    const unsigned si = b * 16 + 2 * c;
#pragma unroll
                    for (unsigned j = 0; j < R; ++j) {
                        const unsigned low = (qa[j][m] >> (8 * (2 * h + (cc & 1u)) + 4 * (cc >> 1))) & 15u;
                        const unsigned high = (qb[j][m] >> (8 * h + 2 * cc)) & 3u;
                        const float d0 = sycl::select_from_group(sg, dbs[j][si / 32], si % 32);
                        const float d1 = sycl::select_from_group(sg, dbs[j][si / 32], si % 32 + 1);
                        v[j][c] = (lane < 16 ? d0 : d1) * float(int(low | (high << 4)) - 32);
                    }
                }
#pragma unroll
                for (unsigned t = 0; t < T; ++t) {
                    const auto xv = sg_bloadN<8>(sg, xr + t * xs + (size_t)b * 256);
#pragma unroll
                    for (unsigned c = 0; c < 8; ++c)
#pragma unroll
                        for (unsigned j = 0; j < R; ++j) sum[j * T + t] = sum[j * T + t] + v[j][c] * xv[c];
                }
            }
        }
        reduce_store<R, T, TREE>(sg, lane, sum, r0, rows, y, ys, mt);
    }
};

// Q5_K packed rows (GemvQ5KP's layout and value expression f * float(code) - o)
template <unsigned NB> struct WsQ5 {
    unsigned rows, xn;
    static constexpr size_t RB = ((size_t)NB * 176 + 15) & ~(size_t)15;
    template <unsigned T, unsigned R, unsigned XW, unsigned TREE, unsigned LOOP, unsigned SEGW>
    [[gnu::always_inline]] inline void rowt(sycl::sub_group sg, unsigned lane, unsigned r0, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        static_assert(XW == 1);
        constexpr unsigned NG = NB * 8, NGR = (NG + 31) / 32, SEG = SEGW ? SEGW : KSeg<NB>::v;
        static_assert(NB % SEG == 0);
        const float *xr = xn ? x + (size_t)(r0 / xn) * NB * 256 : x;
        const uint32_t *qs[R];
        const uint8_t *qh[R];
        float fac[R][NGR], off[R][NGR];
#pragma unroll
        for (unsigned j = 0; j < R; ++j) {
            const uint8_t *row = w + (size_t)(r0 + j < rows ? r0 + j : r0) * RB;
            qs[j] = reinterpret_cast<const uint32_t *>(row);
            qh[j] = row + (size_t)NB * 128;
            const uint8_t *hd = row + (size_t)NB * 160;
#pragma unroll
            for (unsigned k = 0; k < NGR; ++k) {
                const unsigned gi = 32 * k + lane < NG ? 32 * k + lane : NG - 1, c = gi & 7u, c3 = c & 3u;
                const uint8_t *hb = hd + 16 * (gi >> 3), *s = hb + 4;
                const unsigned u0 = s[c3], u1 = s[4 + c3], u2 = s[8 + c3];
                const unsigned scale = c < 4 ? u0 & 63u : (u2 & 15u) | ((u0 >> 6) << 4);
                const unsigned minimum = c < 4 ? u1 & 63u : (u2 >> 4) | ((u1 >> 6) << 4);
                fac[j][k] = iq3::half(iq3::u16(hb)) * float(scale);
                off[j][k] = iq3::half(iq3::u16(hb + 2)) * float(minimum);
            }
        }
        float sum[R * T];
#pragma unroll
        for (unsigned i = 0; i < R * T; ++i) sum[i] = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NB; s0 += SEG) {
            uint32_t qa[R][SEG], qb[R][SEG];
#pragma unroll
            for (unsigned j = 0; j < R; ++j)
#pragma unroll
                for (unsigned m = 0; m < SEG; ++m) {
                    qa[j][m] = sg_bload(sg, qs[j] + (size_t)(s0 + m) * 32);
                    qb[j][m] = qh[j][(size_t)(s0 + m) * 32 + lane];
                }
#pragma unroll
            for (unsigned m = 0; m < SEG; ++m) {
                const unsigned b = s0 + m;
                float v[R][8];
#pragma unroll
                for (unsigned c = 0; c < 8; ++c) {
                    const unsigned gi = b * 8 + c;
#pragma unroll
                    for (unsigned j = 0; j < R; ++j) {
                        const unsigned code = ((qa[j][m] >> (4 * c)) & 15u) | (((qb[j][m] >> c) & 1u) << 4);
                        const float f = sycl::select_from_group(sg, fac[j][gi / 32], gi % 32);
                        const float o = sycl::select_from_group(sg, off[j][gi / 32], gi % 32);
                        v[j][c] = f * float(code) - o;
                    }
                }
#pragma unroll
                for (unsigned t = 0; t < T; ++t) {
                    const auto xv = sg_bloadN<8>(sg, xr + t * xs + (size_t)b * 256);
#pragma unroll
                    for (unsigned c = 0; c < 8; ++c)
#pragma unroll
                        for (unsigned j = 0; j < R; ++j) sum[j * T + t] = sum[j * T + t] + v[j][c] * xv[c];
                }
            }
        }
        reduce_store<R, T, TREE>(sg, lane, sum, r0, rows, y, ys, mt);
    }
};

// H16 rows (GemvH16P: F32 rows stored as their upper 16 bits). rowg's chain per (row, token): segments s of 8
// values per lane ascending, m ascending, sum + float(w << 16) * x. The R rows' 8 values are widened once per
// segment, then the T tokens' vec8 activation blocks stream past.
template <unsigned C> struct WsH16 {
    unsigned rows, xn; // xn unused (GemvH16P has no grouped rows)
    template <unsigned T, unsigned R, unsigned XW, unsigned TREE, unsigned LOOP, unsigned SEGW>
    [[gnu::always_inline]] inline void rowt(sycl::sub_group sg, unsigned lane, unsigned r0, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        static_assert(C % 8 == 0 && XW == 1);
        const uint16_t *rp[R];
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
            rp[j] = reinterpret_cast<const uint16_t *>(w) + (size_t)(r0 + j < rows ? r0 + j : r0) * C * 32;
        float sum[R * T];
#pragma unroll
        for (unsigned i = 0; i < R * T; ++i) sum[i] = 0;
#pragma unroll
        for (unsigned s = 0; s < C / 8; ++s) {
            float wf[R][8];
#pragma unroll
            for (unsigned j = 0; j < R; ++j) {
                const auto wv = sg_bloadN<8>(sg, rp[j] + (size_t)s * 256);
#pragma unroll
                for (unsigned m = 0; m < 8; ++m) wf[j][m] = sycl::bit_cast<float>(uint32_t(wv[m]) << 16);
            }
#pragma unroll
            for (unsigned t = 0; t < T; ++t) {
                const auto xv = sg_bloadN<8>(sg, x + t * xs + (size_t)s * 256);
#pragma unroll
                for (unsigned m = 0; m < 8; ++m)
#pragma unroll
                    for (unsigned j = 0; j < R; ++j) sum[j * T + t] = sum[j * T + t] + wf[j][m] * xv[m];
            }
        }
        reduce_store<R, T, TREE>(sg, lane, sum, r0, rows, y, ys, mt);
    }
};

// position p = (row block p / ng, token group p % ng), as DenseRowsGR
template <typename D, unsigned T, unsigned R, unsigned XW, unsigned TREE, unsigned LOOP, unsigned SEGW = 0> struct DenseRowsWS {
    D k;
    const uint8_t *w;
    const float *x;
    size_t xs;
    float *y;
    size_t ys;
    unsigned mt, ng;
    unsigned n() const { return (k.rows + R - 1) / R * ng; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned p) const {
        const unsigned r0 = p / ng * R, t0 = (p % ng) * T;
        k.template rowt<T, R, XW, TREE, LOOP, SEGW>(sg, lane, r0, w, x + t0 * xs, xs, y + t0 * ys, ys, mt - t0);
    }
};
// GRF = 128: launched with the grf_size<128> kernel property (else the build's automatic choice)
template <unsigned T, unsigned R, unsigned XW, unsigned TREE, unsigned LOOP, unsigned SEGW = 0, unsigned GRF = 0> struct WsForm {
    static constexpr unsigned t = T, r = R, xw = XW, tree = TREE, loop = LOOP, segw = SEGW, grf = GRF;
};

#endif // !OPS41_DENSE_WS
template <typename K> inline constexpr bool is_h16_v = false;
template <unsigned C, typename A> inline constexpr bool is_h16_v<GemvH16P<C, A>> = true;
// ---------------------------------------------------------------------------------------------------------------
static constexpr unsigned MMAX = 264; // tokens in the buffers (the engine's MTA = MTX + 8)
static constexpr size_t FLUSH_WORDS = (size_t)64 << 20; // 256 MiB
static uint32_t *g_flush = nullptr;
static int g_fail = 0, g_reps = 21;
static bool g_notime = false;

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
static void flush(sycl::queue &q, uint32_t v) {
    const uint32_t *p = g_flush;
    uint32_t *o = g_flush;
    q.parallel_for(sycl::range<1>(FLUSH_WORDS / 4), [=](sycl::id<1> i) {
        const size_t b = (size_t)i[0];
        const uint32_t s = p[b] ^ p[b + FLUSH_WORDS / 4] ^ p[b + FLUSH_WORDS / 2] ^ p[b + 3 * FLUSH_WORDS / 4];
        if (s == v + 0x80000000u) o[b] = 0;
    });
}
template <typename T> T *dev_copy(sycl::queue &q, const std::vector<T> &h) {
    T *d = sycl::malloc_device<T>(h.size(), q);
    q.memcpy(d, h.data(), h.size() * sizeof(T)).wait();
    return d;
}
static std::vector<float> rand_f(size_t n, unsigned seed, float lo, float hi) {
    std::mt19937 rng(seed);
    std::uniform_real_distribution<float> u(lo, hi);
    std::vector<float> v(n);
    for (auto &f : v) f = u(rng);
    return v;
}
// random GGUF rows of type t (scales set to sane halves), packed
static std::vector<uint8_t> packed_rand(iq3::Type t, unsigned cols, unsigned rows, unsigned seed) {
    const auto L = iq3::layout(t);
    const size_t rb = (size_t)cols / L.elements * L.bytes, prb = pk41::packed_row_bytes(t, cols);
    std::mt19937 rng(seed);
    std::vector<uint8_t> hw((size_t)rows * rb);
    for (auto &b : hw) b = uint8_t(rng());
    for (size_t blk = 0; blk < hw.size() / L.bytes; ++blk) {
        uint8_t *bp = hw.data() + blk * L.bytes;
        auto seth = [&](size_t o) {
            const uint16_t h = 0x1400 + (rng() & 0x3ff);
            bp[o] = h & 255;
            bp[o + 1] = h >> 8;
        };
        if (t == iq3::Type::Q8_0) seth(0);
        else if (t == iq3::Type::Q6_K) seth(208);
        else if (t == iq3::Type::Q5_K) { seth(0); seth(2); }
    }
    std::vector<uint8_t> hp((size_t)rows * prb);
    for (size_t r = 0; r < rows; ++r) pk41::pack_row(t, hw.data() + r * rb, hp.data() + r * prb, cols);
    return hp;
}

// random F32 rows with zero low halves, as GemvH16P's packed rows (the upper 16 bits of floats in [-0.5, 0.5])
static std::vector<uint8_t> h16_rand(unsigned cols, unsigned rows, unsigned seed) {
    const auto f = rand_f((size_t)rows * cols, seed, -0.5f, 0.5f);
    std::vector<uint8_t> hp((size_t)rows * cols * 2);
    for (size_t i = 0; i < f.size(); ++i) {
        uint32_t u;
        std::memcpy(&u, &f[i], 4);
        const uint16_t h = uint16_t(u >> 16);
        std::memcpy(&hp[2 * i], &h, 2);
    }
    return hp;
}

// ---- real GGUF rows (REAL=1): the first `rows` rows of a tensor, packed -------------------------------------
static const char *GGUF_DIR = "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS";
struct GgufT {
    std::string file;
    uint64_t off = 0; // absolute
    uint32_t type = 0;
    uint64_t ne0 = 0, ne1 = 0;
};
static bool gguf_find(const std::string &name, GgufT &out) {
    for (int part = 1; part <= 6; ++part) {
        char fn[512];
        std::snprintf(fn, sizeof fn, "%s/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-%05d-of-00006.gguf", GGUF_DIR, part);
        const int fd = open(fn, O_RDONLY);
        if (fd < 0) continue;
        std::vector<uint8_t> h((size_t)32 << 20);
        const ssize_t n = pread(fd, h.data(), h.size(), 0);
        close(fd);
        if (n < 64 || std::memcmp(h.data(), "GGUF", 4)) continue;
        const uint8_t *p = h.data() + 4, *end = h.data() + n;
        auto rd = [&](auto &v) { std::memcpy(&v, p, sizeof v); p += sizeof v; };
        uint32_t ver;
        uint64_t nt, nkv;
        rd(ver), rd(nt), rd(nkv);
        static const int tsz[13] = {1, 1, 2, 2, 4, 4, 4, 1, -1, -1, 8, 8, 8};
        uint64_t align = 32;
        bool bad = false;
        for (uint64_t i = 0; i < nkv && !bad; ++i) {
            uint64_t kl;
            rd(kl);
            const std::string key((const char *)p, kl);
            p += kl;
            uint32_t t;
            rd(t);
            if (t == 8) { uint64_t m; rd(m); p += m; }
            else if (t == 9) {
                uint32_t et;
                uint64_t m;
                rd(et), rd(m);
                if (et == 8) for (uint64_t j = 0; j < m; ++j) { uint64_t sl; rd(sl); p += sl; }
                else p += m * tsz[et];
            } else {
                if (key == "general.alignment" && t == 4) { uint32_t a; std::memcpy(&a, p, 4); align = a; }
                p += tsz[t];
            }
            if (p > end) bad = true;
        }
        if (bad) continue;
        bool found = false;
        GgufT g;
        for (uint64_t i = 0; i < nt && p < end; ++i) {
            uint64_t nl;
            rd(nl);
            const std::string tn((const char *)p, nl);
            p += nl;
            uint32_t nd;
            rd(nd);
            uint64_t dims[4] = {1, 1, 1, 1};
            for (uint32_t d = 0; d < nd; ++d) rd(dims[d]);
            uint32_t ty;
            uint64_t off;
            rd(ty), rd(off);
            if (tn == name) { found = true; g.file = fn; g.type = ty; g.ne0 = dims[0]; g.ne1 = dims[1]; g.off = off; }
        }
        if (!found) continue;
        const size_t data = ((size_t)(p - h.data()) + align - 1) / align * align;
        g.off += data;
        out = g;
        return true;
    }
    return false;
}
static bool real_rows(iq3::Type t, const std::string &name, unsigned cols, unsigned r0, unsigned rows,
                      std::vector<uint8_t> &packed) {
    GgufT g;
    if (!gguf_find(name, g)) { std::printf("   real: %s not found\n", name.c_str()); return false; }
    const auto L = iq3::layout(t);
    if (g.ne0 != cols || (uint32_t)t != g.type || g.ne1 < r0 + rows) {
        std::printf("   real: %s shape/type mismatch (%llu x %llu type %u)\n", name.c_str(), (unsigned long long)g.ne0,
                    (unsigned long long)g.ne1, g.type);
        return false;
    }
    const size_t rb = (size_t)cols / L.elements * L.bytes, prb = pk41::packed_row_bytes(t, cols);
    std::vector<uint8_t> hw((size_t)rows * rb);
    const int fd = open(g.file.c_str(), O_RDONLY);
    const ssize_t n = pread(fd, hw.data(), hw.size(), (off_t)(g.off + (uint64_t)r0 * rb));
    close(fd);
    if (n != (ssize_t)hw.size()) return false;
    packed.assign((size_t)rows * prb, 0);
    for (size_t r = 0; r < rows; ++r) pk41::pack_row(t, hw.data() + r * rb, packed.data() + r * prb, cols);
    return true;
}

// ---- a shape: one-token reference per token, the engine form and the new forms at M tokens -------------------
template <typename K, typename W> struct Shape {
    K k;   // one-token kernel (GemvQ8P / GemvQ6KP / GemvQ5KP): rows, xn = 0
    W ws;  // WsQ8 / WsQ6 / WsQ5 with the same rows
    unsigned cols = 0;
    const uint8_t *w = nullptr;
    const float *x = nullptr;
    size_t xs = 0, ys = 0;
    float *ym = nullptr;
    std::vector<float> ref; // MMAX tokens
    char name[64];
    double wbytes = 0;
    // optional rider (q_a's launch carries the attention mix's dot rows)
    bool rider = false;
    const float *rstreams = nullptr, *rfn = nullptr;
    double *rout = nullptr;
};
using HD = TokRows<HcDotsRows<5120, 8>>;
template <typename K, typename W> static HD rider_of(const Shape<K, W> &s, unsigned M) {
    return {HcDotsRows<5120, 8>{s.rstreams, s.rfn, s.rout}, M, {(size_t)4 * 5120, (size_t)25 * 8, 0, 0}};
}
namespace syclex = sycl::ext::oneapi::experimental;
template <typename RW, unsigned GRF> struct RowsPG { // RowsP with a fixed register file size
    RowsP<RW> k;
    void operator()(sycl::nd_item<1> it) const { k(it); }
    auto get(syclex::properties_tag) const {
        return syclex::properties{sycl::ext::intel::experimental::grf_size<GRF>, syclex::sub_group_size<32>};
    }
};
template <unsigned GRF = 0, typename RW> static sycl::event launch(sycl::queue &q, const RW &rw) {
    const RowsP<RW> kr{rw};
    const size_t wg = 512, per = wg / 32, nwg = ((size_t)rw.n() + per - 1) / per;
    if constexpr (GRF == 0)
        return q.parallel_for(sycl::nd_range<1>(nwg * wg, wg),
                              [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kr(it); });
    else return q.parallel_for(sycl::nd_range<1>(nwg * wg, wg), RowsPG<RW, GRF>{kr});
}
template <unsigned GRF = 0, typename RW> static double med_us(sycl::queue &q, const RW &rw) {
    for (int i = 0; i < 5; ++i) launch<GRF>(q, rw);
    q.wait();
    std::vector<double> t;
    for (int rep = 0; rep < g_reps; ++rep) {
        flush(q, (uint32_t)rep);
        sycl::event e = launch<GRF>(q, rw);
        q.wait();
        t.push_back(ev_us(e));
    }
    std::sort(t.begin(), t.end());
    return t[t.size() / 2];
}
template <typename K, typename W> static void compute_ref(sycl::queue &q, Shape<K, W> &s) {
    const size_t n = (size_t)MMAX * s.ys;
    float *yr = sycl::malloc_device<float>(n, q);
    q.memset(yr, 0xff, n * 4).wait();
    for (unsigned t = 0; t < MMAX; ++t) {
        const auto kk = s.k;
        const uint8_t *ww = s.w;
        const float *xx = s.x + t * s.xs;
        float *yy = yr + t * s.ys;
        q.parallel_for(sycl::nd_range<1>(((size_t)s.k.rows + 15) / 16 * 512, 512),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kk(it, ww, xx, yy); });
    }
    q.wait();
    s.ref.resize(n);
    q.memcpy(s.ref.data(), yr, n * 4).wait();
    sycl::free(yr, q);
}
// bitwise against the one-token rows for tokens < M; nothing written past the rows or past M tokens
template <unsigned GRF, typename K, typename W, typename RW> static bool same(sycl::queue &q, Shape<K, W> &s, const RW &rw, unsigned M) {
    const size_t n = (size_t)MMAX * s.ys;
    q.memset(s.ym, 0xff, n * 4).wait();
    launch<GRF>(q, rw).wait();
    std::vector<float> got(n);
    q.memcpy(got.data(), s.ym, n * 4).wait();
    size_t differ = 0, stray = 0;
    for (unsigned t = 0; t < MMAX; ++t)
        for (size_t i = 0; i < s.ys; ++i) {
            const float *g = &got[t * s.ys + i];
            if (t < M && i < s.k.rows) differ += std::memcmp(g, &s.ref[t * s.ys + i], 4) != 0;
            else {
                uint32_t u;
                std::memcpy(&u, g, 4);
                stray += u != 0xffffffffu;
            }
        }
    if (differ || stray) std::printf("   (%zu values differ, %zu stray writes)\n", differ, stray);
    return !differ && !stray;
}
static double g_base = 0;
template <bool RIDER, unsigned GRF, typename K, typename W, typename RW>
static double form(sycl::queue &q, Shape<K, W> &s, const RW &rw, unsigned M, const char *what, bool base) {
    const bool ok = same<GRF>(q, s, rw, M);
    g_fail += !ok;
    if (g_notime) {
        std::printf("%s %-26s M=%-2u %-22s\n", ok ? "bitwise" : "DIFFERS", s.name, M, what);
        return 0;
    }
    double us;
    if constexpr (RIDER) {
        const RowsPair<HD, RW> rp{rider_of(s, M), rw};
        us = med_us<GRF>(q, rp);
    } else us = med_us<GRF>(q, rw);
    if (base) g_base = us;
    const double wt = (double)s.k.rows * s.cols * M;
    std::printf("%s %-26s M=%-2u %-22s | cold %7.1f us  %5.2f T wt/s  %4.0f GB/s", ok ? "bitwise" : "DIFFERS", s.name,
                M, what, us, wt / us * 1e-6, s.wbytes / us * 1e-3);
    if (!base && g_base > 0) std::printf("  x%.3f", g_base / us);
    std::printf("\n");
    std::fflush(stdout);
    return us;
}
#ifndef OPS41_DENSE_WS
template <bool RIDER, typename F, typename K, typename W> static void ws_form(sycl::queue &q, Shape<K, W> &s, unsigned M) {
    constexpr unsigned T = F::t, R = F::r;
    // a block of M tokens that is not a multiple of T: the last group's tokens past M are computed, not stored
    // (the activation rows past M exist: MMAX tokens, as the engine's MTA)
    const DenseRowsWS<W, T, R, F::xw, F::tree, F::loop, F::segw> rw{s.ws, s.w, s.x, s.xs, s.ym, s.ys, M, (M + T - 1) / T};
    char b[48];
    char sg[8] = "";
    if (F::segw) std::snprintf(sg, sizeof sg, " s%u", F::segw);
    std::snprintf(b, sizeof b, "WS T%u R%u%s%s%s%s%s", T, R, F::xw == 2 ? " X2" : "", F::tree ? " tt" : "",
                  F::loop ? " loop" : "", sg, F::grf ? " g128" : "");
    form<RIDER, F::grf>(q, s, rw, M, b, false);
}
#endif
template <bool RIDER, unsigned G, unsigned R, typename K, typename W> static void eng_form(sycl::queue &q, Shape<K, W> &s, unsigned M, bool base) {
    char b[48];
    if constexpr (R == 1) {
        std::snprintf(b, sizeof b, "engine G%u", G);
        form<RIDER, 0>(q, s, DenseRowsG<K, G>{s.k, s.w, s.x, s.xs, s.ym, s.ys, M, (M + G - 1) / G}, M, b, base);
    } else {
        std::snprintf(b, sizeof b, "engine G%u R%u", G, R);
        form<RIDER, 0>(q, s, DenseRowsGR<K, G, R>{s.k, s.w, s.x, s.xs, s.ym, s.ys, M, (M + G - 1) / G}, M, b, base);
    }
}
#ifndef WS_CK
#define WS_CK 0 // 1: the guessing checks' blocks of 2 .. 6 tokens (run_ck) instead of the prompt blocks
#endif
static std::vector<unsigned> g_ms = WS_CK ? std::vector<unsigned>{2, 3, 4, 5, 6} : std::vector<unsigned>{16, 32, 64};
static const char *g_only = nullptr;
static bool g_real = false;

// one shape: K one-token kernel, W ws kernel; body(s, M) runs the engine form and the new forms at M tokens
template <typename K, typename W, bool RIDER, typename B>
static void run_shape(sycl::queue &q, iq3::Type ty, unsigned cols, unsigned rows, unsigned seed, const char *label,
                      const char *real_name, unsigned real_r0, unsigned xn, B &&body) {
    constexpr bool rider = RIDER;
    char nm[64];
    std::snprintf(nm, sizeof nm, "%s %ux%u", label, rows, cols);
    if (g_only && !std::strstr(nm, g_only)) return;
    Shape<K, W> s{};
    s.k.rows = rows;
    if constexpr (requires { s.k.xn; }) s.k.xn = xn; // xn: grouped rows (row r reads x + (r / xn) * cols)
    s.ws.rows = rows;
    s.ws.xn = xn;
    s.cols = cols;
    std::snprintf(s.name, sizeof s.name, "%s", nm);
    s.xs = (size_t)cols * (xn ? (rows + xn - 1) / xn : 1) + 32;
    s.ys = rows + 8;
    std::vector<uint8_t> hw;
    if constexpr (is_h16_v<K>) hw = h16_rand(cols, rows, seed);
    else hw = packed_rand(ty, cols, rows, seed);
    s.wbytes = (double)hw.size();
    uint8_t *wd = dev_copy(q, hw);
    s.w = wd;
    float *xd = dev_copy(q, rand_f(MMAX * s.xs, seed + 1, -2.0f, 2.0f));
    s.x = xd;
    s.ym = sycl::malloc_device<float>((size_t)MMAX * s.ys, q);
    if (rider) {
        s.rider = true;
        s.rstreams = dev_copy(q, rand_f((size_t)MMAX * 4 * 5120, seed + 2, -1.0f, 1.0f));
        s.rfn = dev_copy(q, rand_f((size_t)24 * 4 * 5120, seed + 3, -0.05f, 0.05f));
        s.rout = sycl::malloc_device<double>((size_t)MMAX * 25 * 8, q);
    }
    compute_ref(q, s);
    std::printf("-- %s: weights %.2f MB, %.1f M weight-tokens per token%s\n", s.name, hw.size() / 1e6,
                (double)rows * cols / 1e6, rider ? " (+ the mix's dot rows of every token in the launch)" : "");
    for (unsigned M : g_ms) body(s, M);
    if (g_real && real_name) { // the same forms on real rows, bitwise only
        std::vector<uint8_t> hr;
        if (real_rows(ty, real_name, cols, real_r0, rows, hr)) {
            q.memcpy(wd, hr.data(), hr.size()).wait();
            compute_ref(q, s);
            std::snprintf(s.name, sizeof s.name, "real %s", nm);
            const bool keep = g_notime;
            g_notime = true;
            for (unsigned M : g_ms) body(s, M);
            g_notime = keep;
        }
    }
    sycl::free(wd, q);
    sycl::free(xd, q);
    sycl::free(s.ym, q);
    if (rider) {
        sycl::free((void *)s.rstreams, q);
        sycl::free((void *)s.rfn, q);
        sycl::free(s.rout, q);
    }
}
#ifndef OPS41_DENSE_WS
// prompt blocks: EG / ER the engine's form at 16 tokens (and, as the mtx64 runner gives it, at 32 / 64), Fs the
// new forms
template <typename K, typename W, unsigned EG, unsigned ER, bool RIDER, typename... Fs>
static void run(sycl::queue &q, iq3::Type ty, unsigned cols, unsigned rows, unsigned seed, const char *label,
                const char *real_name, unsigned real_r0) {
    run_shape<K, W, RIDER>(q, ty, cols, rows, seed, label, real_name, real_r0, 0, [&](auto &s, unsigned M) {
        eng_form<RIDER, EG, ER>(q, s, M, true);
        (ws_form<RIDER, Fs>(q, s, M), ...);
    });
}
// guessing checks (blocks of 2 .. 6 tokens): the engine's forms with tg87's BEST settings (OWN_MT_TGM =
// 1:1,2:1,3:3,4:2,5:3,6:3 -> token groups G = 1 at 2 tokens, 3 at 3 / 5 / 6, 2 at 4; OWN_MT_TGR = 2..6:4 from
// 4,096 rows -> ER = 4 there), and the new forms with T = M (one sub-group decodes each weight once for all the
// block's tokens): Cs = CkForm<R, TREE, XW>
template <unsigned R, unsigned TREE, unsigned XW> struct CkForm {};
template <bool RIDER, unsigned T, unsigned R, unsigned TREE, unsigned XW, typename S>
static void ck_ws(sycl::queue &q, S &s, unsigned M) {
    ws_form<RIDER, WsForm<T, R, XW, TREE, 0>>(q, s, M);
}
template <bool RIDER, typename C, typename S> struct CkRun;
template <bool RIDER, unsigned R, unsigned TREE, unsigned XW, typename S> struct CkRun<RIDER, CkForm<R, TREE, XW>, S> {
    static void go(sycl::queue &q, S &s, unsigned M) {
        switch (M) {
        case 2: return ck_ws<RIDER, 2, R, TREE, XW>(q, s, M);
        case 3: return ck_ws<RIDER, 3, R, TREE, XW>(q, s, M);
        case 4: return ck_ws<RIDER, 4, R, TREE, XW>(q, s, M);
        case 5: return ck_ws<RIDER, 5, R, TREE, XW>(q, s, M);
        case 6: return ck_ws<RIDER, 6, R, TREE, XW>(q, s, M);
        default: return;
        }
    }
};
template <typename K, typename W, unsigned ER, bool RIDER, typename... Cs>
static void run_ck(sycl::queue &q, iq3::Type ty, unsigned cols, unsigned rows, unsigned seed, const char *label,
                   const char *real_name, unsigned real_r0) {
    run_shape<K, W, RIDER>(q, ty, cols, rows, seed, label, real_name, real_r0, 0, [&](auto &s, unsigned M) {
        using S = std::decay_t<decltype(s)>;
        if (M < 2 || M > 6) return;
        if (M == 2) eng_form<RIDER, 1, ER>(q, s, M, true);
        else if (M == 4) eng_form<RIDER, 2, ER>(q, s, M, true);
        else eng_form<RIDER, 3, ER>(q, s, M, true);
        (CkRun<RIDER, Cs, S>::go(q, s, M), ...);
    });
}

// the new forms per format and shape (T, R, XW, TREE, LOOP, SEGW, GRF)
using F16_1X = WsForm<16, 1, 2, 1, 0>;
using F16_1n = WsForm<16, 1, 2, 0, 0>; // sg_tree32 per sum (diagnostic: the tree's cost)
using F8_1X = WsForm<8, 1, 2, 1, 0>;
using F8_2X = WsForm<8, 2, 2, 1, 0>;
using F8_2Xg = WsForm<8, 2, 2, 1, 0, 0, 128>;
using F8_2L = WsForm<8, 2, 2, 1, 1>;
using F8_2Lg = WsForm<8, 2, 2, 1, 1, 0, 128>;
using F8_2s4g = WsForm<8, 2, 1, 1, 0, 4, 128>;
using F8_2s5g = WsForm<8, 2, 1, 1, 0, 5, 128>;
using F8_2s6g = WsForm<8, 2, 1, 1, 0, 6, 128>;
using F16_2X = WsForm<16, 2, 2, 1, 0>;
using F16_2Xg = WsForm<16, 2, 2, 1, 0, 0, 128>;
using F4_4X = WsForm<4, 4, 2, 1, 0>;
using F4_2X = WsForm<4, 2, 2, 1, 0>;
using F8_4X = WsForm<8, 4, 2, 1, 0>;
// K-quants (XW = 1, LOOP = 0)
using K16_1 = WsForm<16, 1, 1, 1, 0>;
using K8_1 = WsForm<8, 1, 1, 1, 0>;
using K8_2 = WsForm<8, 2, 1, 1, 0>;
using K8_2g = WsForm<8, 2, 1, 1, 0, 0, 128>;
using K8_2s1g = WsForm<8, 2, 1, 1, 0, 1, 128>;
using K8_2s2g = WsForm<8, 2, 1, 1, 0, 2, 128>;
using K16_2 = WsForm<16, 2, 1, 1, 0>;
using K16_2g = WsForm<16, 2, 1, 1, 0, 0, 128>;
using K4_2 = WsForm<4, 2, 1, 1, 0>;
using K4_4 = WsForm<4, 4, 1, 1, 0>;
using K8_4 = WsForm<8, 4, 1, 1, 0>;
// guessing checks: T = the block's tokens; R rows per sub-group, transposed tree, XW (Q8_0: 2, others 1)
using C1X = CkForm<1, 1, 2>;
using C2X = CkForm<2, 1, 2>;
using C4X = CkForm<4, 1, 2>;
using C1 = CkForm<1, 1, 1>;
using C2 = CkForm<2, 1, 1>;
using C4 = CkForm<4, 1, 1>;

int main() {
    if (const char *e = getenv("ONLY")) g_only = e;
    if (const char *e = getenv("REPS")) g_reps = std::max(3, atoi(e));
    g_notime = getenv("NOTIME") && atoi(getenv("NOTIME"));
    g_real = getenv("REAL") && atoi(getenv("REAL"));
    if (const char *e = getenv("MS")) {
        g_ms.clear();
        for (const char *p = e; *p;) {
            const unsigned m = (unsigned)strtoul(p, (char **)&p, 10);
            if (m && m <= MMAX) g_ms.push_back(m);
            while (*p == ',') ++p;
        }
    }
    const std::string fmt = getenv("FMT") ? getenv("FMT") : WS_CK ? "865h" : "865";
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    const auto dev = q.get_device();
    std::printf("%s", dev.get_info<sycl::info::device::name>().c_str());
    if (dev.has(sycl::aspect::ext_intel_pci_address))
        std::printf(" %s", dev.get_info<sycl::ext::intel::info::device::pci_address>().c_str());
    std::printf("\n");
    g_flush = sycl::malloc_device<uint32_t>(FLUSH_WORDS, q);
    q.fill(g_flush, 0x01234567u, FLUSH_WORDS).wait();
    using iq3::Type;
#if !WS_CK
    if (fmt.find('8') != std::string::npos) {
        // engine forms at 16 tokens (OWN_MT_TG=4, OWN_MT_TGR=16:4 from 4,096 rows, OWN_MT_W16 on): q_b G4 R4, q_a / kv /
        // shared gate+up / output-a G4, output-b G8 R2, shared down G4 R2 (the mtx64 runner: the same at 32 / 64)
        run<GemvQ8P<40, ActF32>, WsQ8<40>, 4, 4, false, F16_2X, F8_2Xg, F8_2s5g, F8_4X>(
            q, Type::Q8_0, 1280, 6144, 11, "Q8_0 q_b", "blk.3.attn_q_b.weight", 0);
        run<GemvQ8P<160, ActF32>, WsQ8<160>, 4, 1, true, F8_2X, F16_2X, F4_4X, F4_2X, F8_1X>(
            q, Type::Q8_0, 5120, 1280, 12, "Q8_0 q_a+dots", nullptr, 0);
        run<GemvQ8P<160, ActF32>, WsQ8<160>, 4, 1, false, F8_2X, F16_2X, F4_4X, F4_2X, F8_1X>(
            q, Type::Q8_0, 5120, 1280, 12, "Q8_0 q_a", "blk.3.attn_q_a.weight", 0);
        run<GemvQ8P<160, ActF32>, WsQ8<160>, 4, 1, false, F8_2X, F16_2X, F4_4X, F4_2X, F8_1X>(
            q, Type::Q8_0, 5120, 512, 16, "Q8_0 kv", "blk.3.attn_kv.weight", 0);
        run<GemvQ8P<160, ActF32>, WsQ8<160>, 4, 1, false, F8_2X, F16_2X, F4_4X, F4_2X, F8_1X>(
            q, Type::Q8_0, 5120, 768, 17, "Q8_0 sh gate+up", "blk.3.ffn_gate_shexp.weight", 0);
        // the engine's output-a launches on a 12-head card hold whole groups (1,024 rows) or half of one (512)
        run<GemvQ8P<128, ActF32>, WsQ8<128>, 4, 1, false, F8_2L, F8_2X, F16_2X, F4_4X, F4_2X, F8_1X>(
            q, Type::Q8_0, 4096, 768, 15, "Q8_0 o_a", "blk.3.attn_output_a.weight", 0);
        run<GemvQ8P<128, ActF32>, WsQ8<128>, 4, 1, false, F8_2L, F8_2X, F16_2X, F4_4X, F4_2X, F8_1X>(
            q, Type::Q8_0, 4096, 512, 18, "Q8_0 o_a", "blk.3.attn_output_a.weight", 0);
        run<GemvQ8P<128, ActF32>, WsQ8<128>, 4, 1, false, F8_2L, F8_2X, F16_2X, F4_4X, F4_2X, F8_1X>(
            q, Type::Q8_0, 4096, 1024, 19, "Q8_0 o_a", "blk.3.attn_output_a.weight", 0);
        run<GemvQ8P<256, ActF32>, WsQ8<256>, 8, 2, false, F8_2L, F8_2X, F16_2X, F4_4X, F4_2X>(
            q, Type::Q8_0, 8192, 864, 13, "Q8_0 o_b", "blk.3.attn_output_b.weight", 0);
        run<GemvQ8P<72, ActF32>, WsQ8<72>, 4, 2, false, F16_2X, F8_2Xg, F4_4X, F4_2X, F8_1X>(
            q, Type::Q8_0, 2304, 864, 14, "Q8_0 sh down", "blk.3.ffn_down_shexp.weight", 0);
    }
    if (fmt.find('6') != std::string::npos) {
        // Q6_K engine forms at 16 tokens (W16): q_b G4, others G4 R2
        run<GemvQ6KP<5, ActF32>, WsQ6<5>, 4, 1, false, K16_2, K8_2s1g, K8_2g, K8_4>(
            q, Type::Q6_K, 1280, 6144, 21, "Q6_K q_b", "blk.30.attn_q_b.weight", 0);
        run<GemvQ6KP<20, ActF32>, WsQ6<20>, 4, 2, false, K8_2, K16_2, K4_2, K4_4, K8_1>(
            q, Type::Q6_K, 5120, 1280, 22, "Q6_K q_a", "blk.30.attn_q_a.weight", 0);
        run<GemvQ6KP<20, ActF32>, WsQ6<20>, 4, 2, false, K8_2, K16_2, K4_2, K4_4, K8_1>(
            q, Type::Q6_K, 5120, 512, 26, "Q6_K kv", "blk.30.attn_kv.weight", 0);
        run<GemvQ6KP<16, ActF32>, WsQ6<16>, 4, 2, false, K8_2, K16_2, K4_2, K4_4, K8_1>(
            q, Type::Q6_K, 4096, 768, 24, "Q6_K o_a", "blk.30.attn_output_a.weight", 0);
        run<GemvQ6KP<16, ActF32>, WsQ6<16>, 4, 2, false, K8_2, K16_2, K4_2, K4_4, K8_1>(
            q, Type::Q6_K, 4096, 512, 25, "Q6_K o_a", "blk.30.attn_output_a.weight", 0);
        run<GemvQ6KP<16, ActF32>, WsQ6<16>, 4, 2, false, K8_2, K16_2, K4_2, K4_4, K8_1>(
            q, Type::Q6_K, 4096, 1024, 27, "Q6_K o_a", "blk.30.attn_output_a.weight", 0);
        run<GemvQ6KP<32, ActF32>, WsQ6<32>, 4, 2, false, K8_2, K16_2, K4_2, K4_4, K8_1>(
            q, Type::Q6_K, 8192, 864, 23, "Q6_K o_b", "blk.30.attn_output_b.weight", 0);
    }
    if (fmt.find('5') != std::string::npos) {
        // Q5_K shared expert (13 layers): gate+up G4 (RoutePMRows), down G4 (no rowgr)
        run<GemvQ5KP<20, ActF32>, WsQ5<20>, 4, 1, false, K8_2, K16_2, K4_2, K4_4, K8_1, K16_1>(
            q, Type::Q5_K, 5120, 768, 31, "Q5_K sh gate+up", "blk.30.ffn_gate_shexp.weight", 0);
        run<GemvQ5KP<9, ActF32>, WsQ5<9>, 4, 1, false, K8_2, K16_2, K4_2, K4_4, K8_1, K16_1>(
            q, Type::Q5_K, 2304, 864, 32, "Q5_K sh down", "blk.30.ffn_down_shexp.weight", 0);
    }
#else
    // the guessing checks' launches on a 12-head card (tg87 tl_ck timeline names): ER = 4 from 4,096 rows
    if (fmt.find('8') != std::string::npos) {
        run_ck<GemvQ8P<160, ActF32>, WsQ8<160>, 1, true, C1X, C2X>(q, Type::Q8_0, 5120, 1280, 41, "Q8_0 q_a+dots", nullptr, 0);
        run_ck<GemvQ8P<160, ActF32>, WsQ8<160>, 1, false, C1X, C2X>(q, Type::Q8_0, 5120, 1280, 41, "Q8_0 q_a", "blk.3.attn_q_a.weight", 0);
        run_ck<GemvQ8P<160, ActF32>, WsQ8<160>, 1, false, C1X, C2X>(q, Type::Q8_0, 5120, 512, 42, "Q8_0 kv", "blk.3.attn_kv.weight", 0);
        run_ck<GemvQ8P<160, ActF32>, WsQ8<160>, 1, false, C1X, C2X>(q, Type::Q8_0, 5120, 768, 43, "Q8_0 sh gate+up", "blk.3.ffn_gate_shexp.weight", 0);
        run_ck<GemvQ8P<40, ActF32>, WsQ8<40>, 4, false, C1X, C2X, C4X>(q, Type::Q8_0, 1280, 6144, 44, "Q8_0 q_b", "blk.3.attn_q_b.weight", 0);
        run_ck<GemvQ8P<128, ActF32>, WsQ8<128>, 1, false, C1X, C2X>(q, Type::Q8_0, 4096, 1024, 45, "Q8_0 o_a", "blk.3.attn_output_a.weight", 0);
        run_ck<GemvQ8P<128, ActF32>, WsQ8<128>, 1, false, C1X, C2X>(q, Type::Q8_0, 4096, 512, 49, "Q8_0 o_a", "blk.3.attn_output_a.weight", 0);
        run_ck<GemvQ8P<256, ActF32>, WsQ8<256>, 1, false, C1X, C2X>(q, Type::Q8_0, 8192, 864, 46, "Q8_0 o_b", "blk.3.attn_output_b.weight", 0);
        run_ck<GemvQ8P<72, ActF32>, WsQ8<72>, 1, false, C1X, C2X>(q, Type::Q8_0, 2304, 864, 47, "Q8_0 sh down", "blk.3.ffn_down_shexp.weight", 0);
        // the draft's fc rows (15,360 columns: layers 37-39's features), this card's 864 (output-b's split)
        run_ck<GemvQ8P<480, ActF32>, WsQ8<480>, 1, false, C1X, C2X>(q, Type::Q8_0, 15360, 864, 48, "Q8_0 draft fc", nullptr, 0);
    }
    if (fmt.find('6') != std::string::npos) {
        run_ck<GemvQ6KP<20, ActF32>, WsQ6<20>, 1, true, C1, C2>(q, Type::Q6_K, 5120, 1280, 51, "Q6_K q_a+dots", nullptr, 0);
        run_ck<GemvQ6KP<20, ActF32>, WsQ6<20>, 1, false, C1, C2>(q, Type::Q6_K, 5120, 512, 52, "Q6_K kv", "blk.30.attn_kv.weight", 0);
        run_ck<GemvQ6KP<5, ActF32>, WsQ6<5>, 4, false, C1, C2, C4>(q, Type::Q6_K, 1280, 6144, 53, "Q6_K q_b", "blk.30.attn_q_b.weight", 0);
        run_ck<GemvQ6KP<16, ActF32>, WsQ6<16>, 1, false, C1, C2>(q, Type::Q6_K, 4096, 1024, 54, "Q6_K o_a", "blk.30.attn_output_a.weight", 0);
        run_ck<GemvQ6KP<32, ActF32>, WsQ6<32>, 1, false, C1, C2>(q, Type::Q6_K, 8192, 864, 55, "Q6_K o_b", "blk.30.attn_output_b.weight", 0);
        // engram_kv (layers 1 / 14): this card's ~4,266 of 25,600 rows; the head: 21,547 of 129,280 rows
        run_ck<GemvQ6KP<24, ActF32>, WsQ6<24>, 4, false, C1, C2, C4>(q, Type::Q6_K, 6144, 4266, 56, "Q6_K engram", "blk.1.engram_kv.weight", 0);
        run_ck<GemvQ6KP<20, ActF32>, WsQ6<20>, 4, false, C1, C2, C4>(q, Type::Q6_K, 5120, 21547, 57, "Q6_K head", "output.weight", 0);
    }
    if (fmt.find('5') != std::string::npos) {
        run_ck<GemvQ5KP<20, ActF32>, WsQ5<20>, 1, false, C1, C2>(q, Type::Q5_K, 5120, 768, 61, "Q5_K sh gate+up", "blk.30.ffn_gate_shexp.weight", 0);
        run_ck<GemvQ5KP<9, ActF32>, WsQ5<9>, 1, false, C1, C2>(q, Type::Q5_K, 2304, 864, 62, "Q5_K sh down", "blk.30.ffn_down_shexp.weight", 0);
    }
    if (fmt.find('h') != std::string::npos) {
        // F32 rows as upper halves: the router (384 rows, with the mix's dot rows), 5,120-column rows (512), and
        // 512-column rows (128)
        run_ck<GemvH16P<160, ActF32>, WsH16<160>, 1, true, C1, C2>(q, Type::Q8_0, 5120, 384, 71, "H16 router+dots", nullptr, 0);
        run_ck<GemvH16P<160, ActF32>, WsH16<160>, 1, false, C1, C2>(q, Type::Q8_0, 5120, 512, 72, "H16 5120 cols", nullptr, 0);
        run_ck<GemvH16P<16, ActF32>, WsH16<16>, 1, false, C1, C2>(q, Type::Q8_0, 512, 128, 73, "H16 512 cols", nullptr, 0);
    }
#endif
    std::printf(g_fail ? "FAIL (%d forms differ)\n" : "PASS\n", g_fail);
    return g_fail ? 1 : 0;
}
#else // OPS41_DENSE_WS
// Patched header (OPS41_DENSE_WS): the forms OWN_MT_WS=1 launches (ops41sycl::WsTab<..>::pick + ws_rows, the kernel
// types dense_m / route_shared_m build) against the engine's form for the same launch, at every block size in MS.
// The engine's form is backend_sycl_v41_mt.inc's choice under tg87 BEST's settings (OWN_MT_TG=4 OWN_MT_TG_MAX=16,
// OWN_MT_W16 on (default), OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3, OWN_MT_TGR=2..6:4 and the default 16:4 (also past 16
// tokens) from 4,096 rows); b_w16_g / b_w16_r are copies of w16_g / w16_r. Launch kinds: WS_PLAIN alone (RowsP,
// 512-item groups), WS_DOTS behind the stream mix's dot rows (RowsP<RowsPair<HD, rows>>), WS_SHARED the gate + up
// pair (rows / 2 each, the two halves of one matrix here) in the router's launch (RoutePMRows: 384 experts, top 6;
// without the FFN mix's finish rows). A pick that ws_rows does not launch counts as a failure.
//   env MS=2,3,...  ONLY=<name part>  REPS=21  REAL=1  FMT=865  NOTIME=1
// -DWS_ALT=1: also candidate forms at blocks of 9+ tokens (to choose WsTab's entries).
#ifndef WS_ALT
#define WS_ALT 0
#endif
template <unsigned N> using UC = std::integral_constant<unsigned, N>;
template <typename K> static constexpr unsigned b_w16_g() {
    constexpr unsigned n = dense_cols_v<K>;
    if constexpr (is_q6kp_v<K>) return n == 1280 || n == 4096 || n == 5120 || n == 8192 ? 4 : 0;
    else return n == 8192 ? 8 : n == 2304 ? 4 : 0;
}
template <typename K> static constexpr unsigned b_w16_r() {
    constexpr unsigned n = dense_cols_v<K>;
    if constexpr (is_q6kp_v<K>) return n == 1280 ? 1 : 2;
    else return 2;
}
static unsigned b_tgm(unsigned M) { // mt_tg_of with BEST's OWN_MT_TGM; 7+ tokens: OWN_MT_TG=4
    static const unsigned t[7] = {0, 1, 1, 3, 2, 3, 3};
    return M <= 6 ? t[M] : 4;
}
static unsigned b_tgr(unsigned M) { return (M >= 2 && M <= 6) || M >= 16 ? 4 : 0; } // mt_tgr[M] (from 4,096 rows)
struct EngF {
    unsigned g, r;
};
template <typename K, unsigned KIND> static EngF eng_pick(unsigned rows, unsigned xn, unsigned M) {
    if (KIND == WS_SHARED) return {b_tgm(M), 1}; // route_shared_m: DenseRowsG<DK, tg>
    if constexpr (requires { &K::template rowgr<2, 2>; }) {
        constexpr unsigned WG = b_w16_g<K>(), WR = b_w16_r<K>();
        if (WG && M >= 9 && rows <= 8192 && (WR == 1 || xn % WR == 0)) return {WG, WR}; // OWN_MT_W16
        const unsigned rr = rows >= 4096 ? b_tgr(M) : 0;
        if (rr == 4 && xn % 4 == 0) return {b_tgm(M), 4};
    }
    return {b_tgm(M), 1};
}
template <typename K, typename F>
static void eng_go(const EngF &e, const K &k, const uint8_t *w, const float *x, size_t xs, float *y, size_t ys,
                   unsigned M, F &&f) {
    auto g = [&](auto gc, auto rc) {
        constexpr unsigned G = decltype(gc)::value, R = decltype(rc)::value;
        if constexpr (R == 1) f(DenseRowsG<K, G>{k, w, x, xs, y, ys, M, (M + G - 1) / G});
        else f(DenseRowsGR<K, G, R>{k, w, x, xs, y, ys, M, (M + G - 1) / G});
    };
    constexpr bool gr = requires { &K::template rowgr<2, 2>; };
    switch (e.g * 8 + e.r) {
    case 1 * 8 + 1: return g(UC<1>{}, UC<1>{});
    case 2 * 8 + 1: return g(UC<2>{}, UC<1>{});
    case 3 * 8 + 1: return g(UC<3>{}, UC<1>{});
    case 4 * 8 + 1: return g(UC<4>{}, UC<1>{});
    default: break;
    }
    if constexpr (gr) {
        switch (e.g * 8 + e.r) {
        case 1 * 8 + 4: return g(UC<1>{}, UC<4>{});
        case 2 * 8 + 4: return g(UC<2>{}, UC<4>{});
        case 3 * 8 + 4: return g(UC<3>{}, UC<4>{});
        case 4 * 8 + 4: return g(UC<4>{}, UC<4>{});
        case 4 * 8 + 2: return g(UC<4>{}, UC<2>{});
        default: break;
        }
        if constexpr (b_w16_g<K>() == 8)
            if (e.g == 8 && e.r == 2) return g(UC<8>{}, UC<2>{});
    }
    std::printf("   (no engine form G%u R%u)\n", e.g, e.r);
    ++g_fail;
}
struct RouteIn { // the router's inputs (WS_SHARED) and a matrix's packed row bytes
    float *logits = nullptr, *bias = nullptr, *prob = nullptr;
    uint32_t *ids = nullptr;
    size_t rb = 0;
};
template <unsigned KIND, typename K, typename W, typename RW>
static sycl::event launch_k(sycl::queue &q, Shape<K, W> &s, const RouteIn &rt, unsigned M, const RW &rw) {
    if constexpr (KIND == WS_PLAIN) return launch<0>(q, rw);
    else if constexpr (KIND == WS_DOTS) return launch<0>(q, RowsPair<HD, RW>{rider_of(s, M), rw});
    else {
        RW up = rw; // the second matrix: the rows after the first's
        up.w = rw.w + (size_t)rw.k.rows * rt.rb;
        up.y = rw.y + rw.k.rows;
        using RX = RowsPair<RW, RW>;
        const RoutePMRows<RX> k{RouteP{384, 6}, (size_t)384, M, RX{rw, up}};
        const size_t ngr = (size_t)M + (k.rows.n() + 15) / 16;
        const float *lg = rt.logits, *bs = rt.bias;
        uint32_t *ids = rt.ids;
        float *pb = rt.prob;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(2 * 1024 + 6, h);
            h.parallel_for(sycl::nd_range<1>(ngr * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k(it, lg, bs, ids, pb, &lt[0]);
            });
        });
    }
}
// bitwise against the one-token rows (tokens < M, rows < the shape's), no stray writes; then cold timing
template <unsigned KIND, typename K, typename W, typename RW>
static double run_l(sycl::queue &q, Shape<K, W> &s, const RouteIn &rt, unsigned M, const RW &rw, const char *what, bool base) {
    auto go = [&]() { return launch_k<KIND>(q, s, rt, M, rw); };
    const size_t n = (size_t)MMAX * s.ys;
    q.memset(s.ym, 0xff, n * 4).wait();
    go().wait();
    std::vector<float> got(n);
    q.memcpy(got.data(), s.ym, n * 4).wait();
    size_t differ = 0, stray = 0;
    for (unsigned t = 0; t < MMAX; ++t)
        for (size_t i = 0; i < s.ys; ++i) {
            const float *gp = &got[t * s.ys + i];
            if (t < M && i < s.k.rows) differ += std::memcmp(gp, &s.ref[t * s.ys + i], 4) != 0;
            else {
                uint32_t u;
                std::memcpy(&u, gp, 4);
                stray += u != 0xffffffffu;
            }
        }
    const bool ok = !differ && !stray;
    if (!ok) std::printf("   (%zu values differ, %zu stray writes)\n", differ, stray);
    g_fail += !ok;
    if (g_notime) {
        std::printf("%s %-28s M=%-3u %-22s\n", ok ? "bitwise" : "DIFFERS", s.name, M, what);
        return 0;
    }
    for (int i = 0; i < 5; ++i) go();
    q.wait();
    std::vector<double> t;
    for (int rep = 0; rep < g_reps; ++rep) {
        flush(q, (uint32_t)rep);
        sycl::event e = go();
        q.wait();
        t.push_back(ev_us(e));
    }
    std::sort(t.begin(), t.end());
    const double us = t[t.size() / 2];
    if (base) g_base = us;
    std::printf("%s %-28s M=%-3u %-22s | cold %8.1f us  %4.0f GB/s", ok ? "bitwise" : "DIFFERS", s.name, M, what, us,
                s.wbytes / us * 1e-3);
    if (!base && g_base > 0) std::printf("  x%.3f", g_base / us);
    std::printf("\n");
    std::fflush(stdout);
    return us;
}
static const char *ws_name(unsigned id, const char *tag) {
    static char b[48];
    std::snprintf(b, sizeof b, "%s T%u R%u%s%s", tag, id & 255u, (id >> 8) & 15u, ((id >> 12) & 3u) == 2 ? " X2" : "",
                  (id >> 14) ? " loop" : "");
    return b;
}
using AltQ8 = WsList<WfX16R2, WsF<8, 2, 2, 0>, WfX8R2L, WfX4R4>; // (T8 R2 X2 without the loop: no table entry)
using AltK = WsList<WfK16R2, WfK8R2, WfK4R2>;
template <typename K, unsigned KIND>
static void run_p(sycl::queue &q, iq3::Type ty, unsigned cols, unsigned rows, unsigned xn, unsigned seed,
                  const char *label, const char *real_name, bool ck_only = false) {
    using O = WsOf<K>;
    using W = typename O::type;
    RouteIn rt{};
    rt.rb = pk41::packed_row_bytes(ty, cols);
    if constexpr (KIND == WS_SHARED) {
        rt.logits = dev_copy(q, rand_f((size_t)MMAX * 384, seed + 7, -4.0f, 4.0f));
        rt.bias = dev_copy(q, rand_f(384, seed + 8, -0.5f, 0.5f));
        rt.prob = sycl::malloc_device<float>((size_t)MMAX * 6, q);
        rt.ids = sycl::malloc_device<uint32_t>((size_t)MMAX * 6, q);
    }
    run_shape<K, W, KIND == WS_DOTS>(q, ty, cols, rows, seed, label, real_name, 0, xn, [&](auto &s, unsigned M) {
        if (ck_only && M > 6) return;
        K k = s.k;
        if (KIND == WS_SHARED) k.rows = rows / 2;
        const EngF e = eng_pick<K, KIND>(k.rows, xn, M);
        char what[48];
        std::snprintf(what, sizeof what, e.r > 1 ? "engine G%u R%u" : "engine G%u", e.g, e.r);
        eng_go(e, k, s.w, s.x, s.xs, s.ym, s.ys, M, [&](const auto &rw) { run_l<KIND>(q, s, rt, M, rw, what, true); });
        const unsigned id = WsTab<O::fmt, O::cols, KIND>::pick(k.rows, M);
        if (id) {
            const bool ok = ws_rows<K, KIND>(k, s.w, s.x, s.xs, s.ym, s.ys, M, MMAX, [&](const auto &rw) {
                run_l<KIND>(q, s, rt, M, rw, ws_name(id, "pick"), false);
            });
            if (!ok) {
                std::printf("NOT DISPATCHED %s M=%u %s\n", s.name, M, ws_name(id, "pick"));
                ++g_fail;
            }
        }
#if WS_ALT
        if (M >= 9) {
            auto alt = [&](auto fm) {
                using FM = decltype(fm);
                if constexpr (FM::loop == 0 || O::cols % 1024 == 0) {
                    if (FM::id == id || xn % FM::r) return false;
                    run_l<KIND>(q, s, rt, M,
                                DenseRowsWS<W, FM::t, FM::r, FM::xw, FM::loop>{W{k.rows, xn}, s.w, s.x, s.xs, s.ym, s.ys, M,
                                                                               (M + FM::t - 1) / FM::t},
                                ws_name(FM::id, "alt"), false);
                }
                return false;
            };
            if constexpr (O::fmt == 8) ws_each(AltQ8{}, alt);
            else ws_each(AltK{}, alt);
        }
#endif
    });
    if constexpr (KIND == WS_SHARED) {
        sycl::free(rt.logits, q);
        sycl::free(rt.bias, q);
        sycl::free(rt.prob, q);
        sycl::free(rt.ids, q);
    }
}
int main() {
    if (const char *e = getenv("ONLY")) g_only = e;
    if (const char *e = getenv("REPS")) g_reps = std::max(3, atoi(e));
    g_notime = getenv("NOTIME") && atoi(getenv("NOTIME"));
    g_real = getenv("REAL") && atoi(getenv("REAL"));
    g_ms = {2, 3, 4, 5, 6, 9, 12, 16, 17, 24, 32, 33, 48, 64, 65, 96, 128, 160, 256};
    if (const char *e = getenv("MS")) {
        g_ms.clear();
        for (const char *p = e; *p;) {
            const unsigned m = (unsigned)strtoul(p, (char **)&p, 10);
            if (m && m <= 256) g_ms.push_back(m);
            while (*p == ',') ++p;
        }
    }
    const std::string fmt = getenv("FMT") ? getenv("FMT") : "865";
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    const auto dev = q.get_device();
    std::printf("%s", dev.get_info<sycl::info::device::name>().c_str());
    if (dev.has(sycl::aspect::ext_intel_pci_address))
        std::printf(" %s", dev.get_info<sycl::ext::intel::info::device::pci_address>().c_str());
    std::printf("  (patched header: OWN_MT_WS forms%s)\n", WS_ALT ? " + candidates" : "");
    g_flush = sycl::malloc_device<uint32_t>(FLUSH_WORDS, q);
    q.fill(g_flush, 0x01234567u, FLUSH_WORDS).wait();
    using iq3::Type;
    // a 12-head card's launches (card 2), q_b also as an 8-head card's (4,096 rows), output-a also with two row
    // groups in one launch (xn = 512) and at 768 rows
    if (fmt.find('8') != std::string::npos) {
        run_p<GemvQ8P<40, ActF32>, WS_PLAIN>(q, Type::Q8_0, 1280, 6144, 0, 11, "Q8_0 q_b", "blk.3.attn_q_b.weight");
        run_p<GemvQ8P<40, ActF32>, WS_PLAIN>(q, Type::Q8_0, 1280, 4096, 0, 12, "Q8_0 q_b", "blk.3.attn_q_b.weight");
        run_p<GemvQ8P<160, ActF32>, WS_DOTS>(q, Type::Q8_0, 5120, 1280, 0, 13, "Q8_0 q_a+dots", "blk.3.attn_q_a.weight");
        run_p<GemvQ8P<160, ActF32>, WS_PLAIN>(q, Type::Q8_0, 5120, 1280, 0, 14, "Q8_0 q_a", "blk.3.attn_q_a.weight");
        run_p<GemvQ8P<160, ActF32>, WS_PLAIN>(q, Type::Q8_0, 5120, 512, 0, 15, "Q8_0 kv", "blk.3.attn_kv.weight");
        run_p<GemvQ8P<160, ActF32>, WS_SHARED>(q, Type::Q8_0, 5120, 768, 0, 16, "Q8_0 sh gate+up", "blk.3.ffn_gate_shexp.weight");
        run_p<GemvQ8P<128, ActF32>, WS_PLAIN>(q, Type::Q8_0, 4096, 1024, 0, 17, "Q8_0 o_a", "blk.3.attn_output_a.weight");
        run_p<GemvQ8P<128, ActF32>, WS_PLAIN>(q, Type::Q8_0, 4096, 1024, 512, 18, "Q8_0 o_a xn512", "blk.3.attn_output_a.weight");
        run_p<GemvQ8P<128, ActF32>, WS_PLAIN>(q, Type::Q8_0, 4096, 768, 0, 19, "Q8_0 o_a", "blk.3.attn_output_a.weight");
        run_p<GemvQ8P<128, ActF32>, WS_PLAIN>(q, Type::Q8_0, 4096, 512, 0, 20, "Q8_0 o_a", "blk.3.attn_output_a.weight");
        run_p<GemvQ8P<256, ActF32>, WS_PLAIN>(q, Type::Q8_0, 8192, 864, 0, 21, "Q8_0 o_b", "blk.3.attn_output_b.weight");
        run_p<GemvQ8P<72, ActF32>, WS_PLAIN>(q, Type::Q8_0, 2304, 864, 0, 22, "Q8_0 sh down", "blk.3.ffn_down_shexp.weight");
    }
    if (fmt.find('6') != std::string::npos) {
        run_p<GemvQ6KP<5, ActF32>, WS_PLAIN>(q, Type::Q6_K, 1280, 6144, 0, 31, "Q6_K q_b", "blk.30.attn_q_b.weight");
        run_p<GemvQ6KP<5, ActF32>, WS_PLAIN>(q, Type::Q6_K, 1280, 4096, 0, 32, "Q6_K q_b", "blk.30.attn_q_b.weight");
        run_p<GemvQ6KP<20, ActF32>, WS_DOTS>(q, Type::Q6_K, 5120, 1280, 0, 33, "Q6_K q_a+dots", "blk.30.attn_q_a.weight");
        run_p<GemvQ6KP<20, ActF32>, WS_PLAIN>(q, Type::Q6_K, 5120, 1280, 0, 34, "Q6_K q_a", "blk.30.attn_q_a.weight");
        run_p<GemvQ6KP<20, ActF32>, WS_PLAIN>(q, Type::Q6_K, 5120, 512, 0, 35, "Q6_K kv", "blk.30.attn_kv.weight");
        run_p<GemvQ6KP<16, ActF32>, WS_PLAIN>(q, Type::Q6_K, 4096, 1024, 0, 36, "Q6_K o_a", "blk.30.attn_output_a.weight");
        run_p<GemvQ6KP<16, ActF32>, WS_PLAIN>(q, Type::Q6_K, 4096, 1024, 512, 37, "Q6_K o_a xn512", "blk.30.attn_output_a.weight");
        run_p<GemvQ6KP<16, ActF32>, WS_PLAIN>(q, Type::Q6_K, 4096, 768, 0, 38, "Q6_K o_a", "blk.30.attn_output_a.weight");
        run_p<GemvQ6KP<16, ActF32>, WS_PLAIN>(q, Type::Q6_K, 4096, 512, 0, 39, "Q6_K o_a", "blk.30.attn_output_a.weight");
        run_p<GemvQ6KP<32, ActF32>, WS_PLAIN>(q, Type::Q6_K, 8192, 864, 0, 40, "Q6_K o_b", "blk.30.attn_output_b.weight");
        run_p<GemvQ6KP<24, ActF32>, WS_PLAIN>(q, Type::Q6_K, 6144, 4266, 0, 41, "Q6_K engram", "blk.1.engram_kv.weight");
        run_p<GemvQ6KP<20, ActF32>, WS_PLAIN>(q, Type::Q6_K, 5120, 21547, 0, 42, "Q6_K head", "output.weight", true);
    }
    if (fmt.find('5') != std::string::npos) {
        run_p<GemvQ5KP<20, ActF32>, WS_SHARED>(q, Type::Q5_K, 5120, 768, 0, 51, "Q5_K sh gate+up", "blk.30.ffn_gate_shexp.weight");
        run_p<GemvQ5KP<9, ActF32>, WS_PLAIN>(q, Type::Q5_K, 2304, 864, 0, 52, "Q5_K sh down", "blk.30.ffn_down_shexp.weight");
    }
    std::printf(g_fail ? "FAIL (%d forms differ or were not launched)\n" : "PASS\n", g_fail);
    return g_fail ? 1 : 0;
}
#endif
