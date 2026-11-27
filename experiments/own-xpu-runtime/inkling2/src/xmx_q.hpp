#pragma once
// xmx_q.hpp: the experts of layers 20-23 (gate|up Q5_K, Q5_K, Q4_K, IQ4_XS; down Q5_0, Q5_0, Q5_0, IQ4_NL) on the
// matrix engines with exact products (INK_XMX_Q: default since 2026-11-26, baseline v8; 0 = the FP32 kernels, v7).
//
// Arithmetic (the same for every step size; README "Matrix engines with exact products"):
//   - inputs in three bf16 parts (split3: x = x1 + x2 + x3 exactly);
//   - a weight is s x c + o with c a small integer, exact in bf16 (Q5_0: q - 16; IQ4_NL, IQ4_XS: kvalues_iq4nl[q];
//     Q5_K: q - 16; Q4_K: q - 8), s the row's scale of its block of 32 inputs (Q5_0, IQ4_NL: d; IQ4_XS: d x (ls -
//     32); Q4_K, Q5_K: d x sc; exact products in fp32) and, for Q4_K / Q5_K, o = fma(s, C, -m1) with C = 16 / 8 and
//     m1 = dmin x m: llama.cpp's s x q - m1 (planar.hpp's decoders compute the same s and m1). Centred codes keep
//     the two terms small (with the codes q themselves, s A and m1 X nearly cancel: error 0.18 against 0.11 for
//     today's FP32 order, bench_xq);
//   - one output (slot, row): T = 0; per group of up to 8 blocks: G = 0; per block: A = one DPAS chain from 0 over its
//     two steps (x1, x2, x3 per step), G = fma(s, A, G), then (Q4_K, Q5_K) G = fma(o, X, G) with X the block's
//     input sum (xsum: Neumaier's compensated fp32 sum in input order); after the group T = T + G;
//   - rows of a DPAS tile do not depend on each other (bench_xm1): every tile height gives the same bits.
// gate|up: H = act(T_gate, T_up) (xm::act); down: y[slot][row] = T.
//
// Layout XQ (made in place from the planar decode copy, gemv2.hpp dec_kind; the same bytes per row, the row padding
// unused): per expert, per block of 16 rows (stride rb16), per group of 8 blocks of 32 inputs: 8 units of UB bytes,
// then GX bytes of group data (IQ4_XS: row n's half d at 2n; Q4_K, Q5_K: half d, half dmin at 4n). A unit (16 rows x
// 32 inputs): the codes of step s (inputs 16s..16s+15) at 128s, row n's 8 bytes at 8n with input i's code in bits 4i
// of the 64-bit word; Q5: row n's 32 high bits at 256 + 4n (bit k = bit 4 of input k's code); then per row (RD0):
// Q5_0, IQ4_NL half d at 2n; IQ4_XS int8 ls - 32 at n; Q4_K, Q5_K 6-bit sc and m at 2n, 2n + 1. A sub-group reads a
// step's codes with one 128-byte load. The down product (1,152 inputs: 36 blocks, 4.5 groups) has no group data.
#include "xmx_moe.hpp"

namespace ink::xq {
namespace jm = sycl::ext::oneapi::experimental::matrix;
using bf = sycl::ext::oneapi::bfloat16;
using xm::ActOp;
using xm::SEG;

enum Fmt { F_Q5_0 = 0, F_IQ4_NL = 1, F_IQ4_XS = 2, F_Q4_K = 3, F_Q5_K = 4 };
inline int fmt_of(uint32_t type) {
    switch (type) {
    case G_Q5_0: return F_Q5_0;
    case G_IQ4_NL: return F_IQ4_NL;
    case G_IQ4_XS: return F_IQ4_XS;
    case G_Q4_K: return F_Q4_K;
    case G_Q5_K: return F_Q5_K;
    default: return -1;
    }
}
template <int F> struct Lay {
    static constexpr bool HB = F == F_Q5_0 || F == F_Q5_K;     // 5-bit codes
    static constexpr bool KQ = F == F_Q4_K || F == F_Q5_K;     // a min per block
    static constexpr bool NL = F == F_IQ4_NL || F == F_IQ4_XS; // codes through kvalues_iq4nl
    static constexpr bool GD = KQ || F == F_IQ4_XS;            // group data
    static constexpr int RD0 = 256 + (HB ? 64 : 0);
    static constexpr int UB = RD0 + (F == F_IQ4_XS ? 16 : 32);
    static constexpr int GX = KQ ? 64 : F == F_IQ4_XS ? 32 : 0;
    static constexpr int GB = 8 * UB + GX;
    static size_t rb16(int cols) { return cols % 256 == 0 ? (size_t)(cols / 256) * GB : (size_t)(cols / 32) * UB; }
    static size_t unit(int b) { return (size_t)(b >> 3) * GB + (size_t)(b & 7) * UB; }
    static size_t garea(int b) { return (size_t)(b >> 3) * GB + 8 * UB; }
};

// ---- the layout, in place of a planar decode copy (rows x srb bytes per expert, ne experts; tmp: one expert)
template <int F> inline void repack_t(sycl::queue &q, uint8_t *W, size_t srb, int rows, int cols, int ne, uint8_t *tmp) {
    using LF = Lay<F>;
    const size_t es = srb * (size_t)rows, r16 = LF::rb16(cols);
    const int nb = cols / 32, nblk = rows / 16;
    if (rows % 16 || cols % 32 || (cols % 256 && LF::GX) || r16 * nblk > es) throw std::runtime_error("xq::repack: shapes");
    for (int e = 0; e < ne; ++e) {
        uint8_t *we = W + (size_t)e * es;
        q.memcpy(tmp, we, es);
        q.parallel_for(sycl::range<2>((size_t)nblk * nb, 16), [=](sycl::id<2> i) {
            const int bk = (int)(i[0] / nb), b = (int)(i[0] % nb), n = (int)i[1];
            const uint8_t *row = tmp + (size_t)(bk * 16 + n) * srb;
            uint8_t *blk = we + (size_t)bk * r16, *u = blk + LF::unit(b);
            const uint8_t *nib = row + 16 * b; // planar: byte j = code j | code j + 16 << 4
            for (int s = 0; s < 2; ++s)
                for (int j = 0; j < 8; ++j) {
                    const int k0 = 16 * s + 2 * j, k1 = k0 + 1;
                    const int c0 = k0 < 16 ? (nib[k0] & 0xF) : (nib[k0 - 16] >> 4);
                    const int c1 = k1 < 16 ? (nib[k1] & 0xF) : (nib[k1 - 16] >> 4);
                    u[128 * s + 8 * n + j] = (uint8_t)(c0 | (c1 << 4));
                }
            if constexpr (LF::HB)
                for (int j = 0; j < 4; ++j) u[256 + 4 * n + j] = row[cols / 2 + 4 * b + j];
            uint8_t *rd = u + LF::RD0;
            if constexpr (F == F_Q5_0) {
                rd[2 * n] = row[cols / 2 + cols / 8 + 2 * b];
                rd[2 * n + 1] = row[cols / 2 + cols / 8 + 2 * b + 1];
            } else if constexpr (F == F_IQ4_NL) {
                rd[2 * n] = row[cols / 2 + 2 * b];
                rd[2 * n + 1] = row[cols / 2 + 2 * b + 1];
            } else if constexpr (F == F_IQ4_XS) {
                rd[n] = row[cols / 2 + b];
                if (b % 8 == 0) {
                    uint8_t *g = blk + LF::garea(b);
                    g[2 * n] = row[cols / 2 + cols / 32 + 2 * (b >> 3)];
                    g[2 * n + 1] = row[cols / 2 + cols / 32 + 2 * (b >> 3) + 1];
                }
            } else {
                const size_t sm = (size_t)cols / 2 + (LF::HB ? cols / 8 : 0);
                rd[2 * n] = row[sm + 2 * b];
                rd[2 * n + 1] = row[sm + 2 * b + 1];
                if (b % 8 == 0) {
                    uint8_t *g = blk + LF::garea(b);
                    for (int j = 0; j < 4; ++j) g[4 * n + j] = row[sm + cols / 16 + 4 * (b >> 3) + j];
                }
            }
        });
    }
    q.wait();
}
inline void repack(sycl::queue &q, int f, uint8_t *W, size_t srb, int rows, int cols, int ne, uint8_t *tmp) {
    switch (f) {
    case F_Q5_0: return repack_t<F_Q5_0>(q, W, srb, rows, cols, ne, tmp);
    case F_IQ4_NL: return repack_t<F_IQ4_NL>(q, W, srb, rows, cols, ne, tmp);
    case F_IQ4_XS: return repack_t<F_IQ4_XS>(q, W, srb, rows, cols, ne, tmp);
    case F_Q4_K: return repack_t<F_Q4_K>(q, W, srb, rows, cols, ne, tmp);
    case F_Q5_K: return repack_t<F_Q5_K>(q, W, srb, rows, cols, ne, tmp);
    default: throw std::runtime_error("xq::repack: format");
    }
}
inline size_t rb16_of(int f, int cols) {
    switch (f) {
    case F_Q5_0: return Lay<F_Q5_0>::rb16(cols);
    case F_IQ4_NL: return Lay<F_IQ4_NL>::rb16(cols);
    case F_IQ4_XS: return Lay<F_IQ4_XS>::rb16(cols);
    case F_Q4_K: return Lay<F_Q4_K>::rb16(cols);
    case F_Q5_K: return Lay<F_Q5_K>::rb16(cols);
    default: throw std::runtime_error("xq::rb16: format");
    }
}

// ---- one lane's data of a block: row ln's codes (both steps), high bits, row data and group data
struct QRaw { uint32_t c[4]; uint32_t hb, rd, gd; };
template <int F> inline QRaw fetch(const uint8_t *u, const uint8_t *ga, int ln) {
    using LF = Lay<F>;
    QRaw r;
    const sycl::vec<uint32_t, 2> a = *reinterpret_cast<const sycl::vec<uint32_t, 2> *>(u + 8 * ln);
    const sycl::vec<uint32_t, 2> b = *reinterpret_cast<const sycl::vec<uint32_t, 2> *>(u + 128 + 8 * ln);
    r.c[0] = a[0]; r.c[1] = a[1]; r.c[2] = b[0]; r.c[3] = b[1];
    r.hb = LF::HB ? *reinterpret_cast<const uint32_t *>(u + 256 + 4 * ln) : 0u;
    if constexpr (F == F_IQ4_XS) r.rd = u[LF::RD0 + ln];
    else r.rd = *reinterpret_cast<const uint16_t *>(u + LF::RD0 + 2 * ln);
    if constexpr (LF::KQ) r.gd = *reinterpret_cast<const uint32_t *>(ga + 4 * ln);
    else if constexpr (F == F_IQ4_XS) r.gd = *reinterpret_cast<const uint16_t *>(ga + 2 * ln);
    else r.gd = 0u;
    return r;
}
inline float h2f(uint32_t bits) { return (float)sycl::bit_cast<sycl::half>((uint16_t)bits); }
// the block's scale s and (Q4_K, Q5_K) offset o = s x C - m1 for the lane's row
template <int F> inline void scale(const QRaw &r, float &s, float &nm) {
    if constexpr (F == F_Q5_0 || F == F_IQ4_NL) { s = h2f(r.rd); nm = 0.0f; }
    else if constexpr (F == F_IQ4_XS) { s = h2f(r.gd) * (float)(int)(int8_t)(uint8_t)r.rd; nm = 0.0f; }
    else {
        s = h2f(r.gd) * (float)(int)(r.rd & 0xFFu);
        const float m1 = h2f(r.gd >> 16) * (float)(int)(r.rd >> 8);
        nm = sycl::fma(s, F == F_Q5_K ? 16.0f : 8.0f, -m1);
    }
}
// the local table of code pairs: entry i = the bf16 bits of the values of code byte i & 255 (low nibble first) with
// the two high bits i >> 8 (Q5: 1,024 entries; others 256)
template <int F> struct Lut { static constexpr int N = Lay<F>::HB ? 1024 : 256; };
template <int F> inline int pval(int nib, int h) {
    if constexpr (Lay<F>::NL) return pl::kv_nl_sel(nib);
    else if constexpr (F == F_Q4_K) return nib - 8;
    else return (nib | (h << 4)) - 16; // Q5_0, Q5_K
}
template <int F> inline uint32_t lut_pair(int i) {
    const int b = i & 255, h = i >> 8;
    return (sycl::bit_cast<uint32_t>((float)pval<F>(b & 15, h & 1)) >> 16) | (sycl::bit_cast<uint32_t>((float)pval<F>(b >> 4, h >> 1)) & 0xFFFF0000u);
}
template <int F> inline uint32_t pair_of(uint32_t lo, uint32_t hi, uint32_t h16, int j, const uint32_t *lut) {
    uint32_t i = ((j < 4 ? lo : hi) >> (8 * (j & 3))) & 0xFFu;
    if constexpr (Lay<F>::HB) i |= ((h16 >> (2 * j)) & 3u) << 8;
    return lut[i];
}
// the bf16 bits of the 16 values of step st (exact small integers), input order, through lut (Lut<F>::N lut_pair
// entries in local memory; IQ4 with selects per value: 81 us per one-token gate|up, a shuffle per value 181, the
// table 43.5)
template <int F> inline void bits16(const QRaw &r, int st, uint32_t *v, const uint32_t *lut) {
    const uint32_t lo = r.c[2 * st], hi = r.c[2 * st + 1], h16 = r.hb >> (16 * st);
#pragma unroll
    for (int j = 0; j < 8; ++j) {
        const uint32_t p = pair_of<F>(lo, hi, h16, j, lut);
        v[2 * j] = p & 0xFFFFu;
        v[2 * j + 1] = p >> 16;
    }
}
// as 8 words of bf16 pairs (inputs 2j, 2j + 1) at o[j * os]; LT false (Q4_K, Q5_K, Q5_0): from the codes by
// arithmetic, the same bits (the prompt kernel: 2-4 % faster than its table reads, which share local memory with the B
// tiles; the one-token kernel is the other way round)
template <int F, bool LT = true> inline void words(const QRaw &r, int st, uint32_t *o, int os, const uint32_t *lut) {
    const uint32_t lo = r.c[2 * st], hi = r.c[2 * st + 1], h16 = r.hb >> (16 * st);
    if constexpr (LT || Lay<F>::NL) {
#pragma unroll
        for (int j = 0; j < 8; ++j) o[j * os] = pair_of<F>(lo, hi, h16, j, lut);
    } else {
        uint32_t v[16];
#pragma unroll
        for (int i = 0; i < 16; ++i) {
            int q = (int)(((i < 8 ? lo : hi) >> (4 * (i & 7))) & 0xFu);
            if constexpr (Lay<F>::HB) q |= (int)((h16 >> i) & 1u) << 4;
            if constexpr (F == F_Q5_0 || F == F_Q5_K) q -= 16;
            if constexpr (F == F_Q4_K) q -= 8;
            v[i] = sycl::bit_cast<uint32_t>((float)q) >> 16;
        }
#pragma unroll
        for (int j = 0; j < 8; ++j) o[j * os] = v[2 * j] | (v[2 * j + 1] << 16);
    }
}

// ---- the block sums X[r][b] of rows of inputs (Q4_K, Q5_K gate|up): from fp32 rows x (stride ldx) or, with P, from
// their parts (x1 + (x2 + x3) is x exactly); Neumaier's compensated sum in input order (the sum to about one rounding)
// nsum32, psum32: bfsplit.hpp
inline sycl::event xsum(sycl::queue &q, const float *x, int ldx, const uint16_t *P, size_t pp, int rows, int cols, float *X) {
    const int nb = cols / 32;
    return q.parallel_for(sycl::range<1>((size_t)rows * nb), [=](sycl::id<1> id) {
        const int r = (int)(id[0] / nb), b = (int)(id[0] % nb);
        if (P) X[(size_t)r * nb + b] = psum32(P + (size_t)r * cols + 32 * b, pp);
        else {
            float v[32];
#pragma unroll
            for (int i = 0; i < 32; ++i) v[i] = x[(size_t)r * ldx + 32 * b + i];
            X[(size_t)r * nb + b] = nsum32(v);
        }
    });
}

// ---- steps of 1-8 tokens: one sub-group per (tile, 16 rows) over all inputs (xm::XFull's shape and outputs), the
// weights PB blocks ahead, the B tile built in registers. Inputs P by sorted position (row tile_s0[t] + r, part stride
// pp) or with one the single row 0. X (Q4_K, Q5_K gate|up): block sums by token, token of sorted position s =
// one ? 0 : slots[s] / xdiv (computing them inside, for one token: 54 -> 65-69 us per gate|up launch, against a
// 2.6 us xsum launch). MODE 0: gate|up (work-group = the gate and up tiles of 16 rows), H in parts to
// Hp[p][tile_s0[t] + r][i]; MODE 1: down, y[slots[tile_s0[t] + r]][row]; MODE 2 (tests): gate|up sums to
// Y[slot][2 nff] (row = the tensor's row).
template <int F, int MMAX, int MODE, int PB = 2, int SRF = 4, int GRF = 128> struct XFullQ {
    using LF = Lay<F>;
    const uint8_t *W; size_t estride; int cols, nff;
    MoeGroups g; const uint16_t *P; size_t pp; bool one;
    const float *X; int xdiv;
    ActOp op; uint16_t *Hp; size_t hpp; float *Y; int ldy;
    sycl::local_accessor<float, 1> st;
    sycl::local_accessor<uint32_t, 1> lt;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>};
    }
    template <int M> void body(sycl::sub_group sg, int sgi, int ln, const uint8_t *w, size_t row0, const int *tok) const {
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, M, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, M, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        const int nb = cols / 32;
        QRaw r[PB];
#pragma unroll
        for (int i = 0; i < PB; ++i) r[i] = fetch<F>(w + LF::unit(i), w + LF::garea(i), ln);
        C c, gs, tot;
        jm::joint_matrix_fill(sg, tot, 0.0f);
        jm::joint_matrix_fill(sg, gs, 0.0f);
        B rb;
        jm::joint_matrix_fill(sg, rb, bf(0.0f));
        const bf *pa = reinterpret_cast<const bf *>(P) + row0 * cols;
        for (int b0 = 0; b0 < nb; b0 += PB) {
            QRaw n[PB];
#pragma unroll
            for (int i = 0; i < PB; ++i) {
                const int bn = sycl::min(b0 + PB + i, nb - 1);
                n[i] = fetch<F>(w + LF::unit(bn), w + LF::garea(bn), ln);
            }
#pragma unroll
            for (int i = 0; i < PB; ++i) {
                const int b = b0 + i;
                float s, nm;
                scale<F>(r[i], s, nm);
                jm::joint_matrix_fill(sg, c, 0.0f);
#pragma unroll
                for (int h = 0; h < 2; ++h) {
                    uint32_t v[16];
                    bits16<F>(r[i], h, v, &lt[0]);
                    int e = 0;
                    jm::joint_matrix_apply(sg, rb, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)v[e]); ++e; });
                    A x0, x1, x2;
                    const bf *pk = pa + (size_t)(2 * b + h) * 16;
                    jm::joint_matrix_load(sg, x0, gp(pk), cols);
                    jm::joint_matrix_load(sg, x1, gp(pk + pp), cols);
                    jm::joint_matrix_load(sg, x2, gp(pk + 2 * pp), cols);
                    jm::joint_matrix_mad(sg, c, x0, rb, c);
                    jm::joint_matrix_mad(sg, c, x1, rb, c);
                    jm::joint_matrix_mad(sg, c, x2, rb, c);
                }
                jm::joint_matrix_apply(sg, gs, c, [=](float &x, float &y) { x = sycl::fma(s, y, x); });
                if constexpr (LF::KQ && MODE != 1) {
                    float xv[M];
#pragma unroll
                    for (int q = 0; q < M; ++q) xv[q] = X[(size_t)tok[q] * nb + b];
                    int e = 0;
                    jm::joint_matrix_apply(sg, gs, [&](float &x) { x = sycl::fma(nm, xv[e], x); ++e; });
                }
                if ((b & 7) == 7 || b == nb - 1) {
                    jm::joint_matrix_apply(sg, tot, gs, [](float &x, float &y) { x = x + y; });
                    jm::joint_matrix_fill(sg, gs, 0.0f);
                }
            }
#pragma unroll
            for (int i = 0; i < PB; ++i) r[i] = n[i];
        }
        jm::joint_matrix_store(sg, tot, st.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)sgi * MMAX * 16, 16, jm::layout::row_major);
    }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        const auto sg = it.get_sub_group();
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id(), gi = (int)it.get_group(1);
        const int cnt = g.tile_n[t], s0 = g.tile_s0[t];
        const int blk = MODE != 1 ? sgi * (nff / 16) + gi : gi * SRF + sgi; // block of 16 rows
        const uint8_t *w = W + (size_t)g.tile_exp[t] * estride + (size_t)blk * LF::rb16(cols);
        const size_t row0 = one ? 0 : (size_t)s0;
        int tok[MMAX];
#pragma unroll
        for (int q = 0; q < MMAX; ++q) tok[q] = (one || !LF::KQ || MODE == 1) ? 0 : g.slots[s0 + sycl::min(q, cnt - 1)] / xdiv;
        { // the IQ4 table (the B matrix is defined by joint_matrix_fill in body)
            const int lid = (int)it.get_local_linear_id(), nl = (int)it.get_local_range(1);
            for (int i = lid; i < Lut<F>::N; i += nl) lt[i] = lut_pair<F>(i);
            sycl::group_barrier(it.get_group());
        }
        if constexpr (MMAX == 1) body<1>(sg, sgi, ln, w, row0, tok);
        else {
            if (cnt <= 1) body<1>(sg, sgi, ln, w, row0, tok);
            else if (cnt <= 2) body<2>(sg, sgi, ln, w, row0, tok);
            else if (cnt <= 4) body<4>(sg, sgi, ln, w, row0, tok);
            else body<8>(sg, sgi, ln, w, row0, tok);
        }
        const float *sp = &st[0];
        if constexpr (MODE == 0) {
            sycl::group_barrier(it.get_group());
            const int lid = (int)it.get_local_linear_id();
            const bool sc = op.escale != nullptr;
            const float es = sc ? op.escale[g.tile_exp[t]] : 1.0f;
            for (int id = lid; id < cnt * 16; id += 32) {
                const int r = id / 16, c = id % 16;
                split3_store(xm::act(sp[r * 16 + c], sp[MMAX * 16 + r * 16 + c], es, sc, op.beta, op.lb), Hp + (size_t)(s0 + r) * nff + gi * 16 + c, hpp);
            }
        } else {
            sycl::group_barrier(sg);
            const int row = MODE == 1 ? blk * 16 + ln : (sgi == 0 ? gi * 16 : nff + gi * 16) + ln;
            for (int r = 0; r < cnt; ++r) Y[(size_t)g.slots[s0 + r] * ldy + row] = sp[(size_t)sgi * MMAX * 16 + r * 16 + ln];
        }
    }
};
// MODE 0 / 2: gate|up (cols inputs, nff rows each); MODE 1: down (cols = nff inputs, rows outputs)
template <int F, int MMAX, int MODE, int PB = 2, int SRF = 4, int GRF = 128>
inline sycl::event full_q(sycl::queue &q, const uint8_t *W, size_t estride, int cols, int nff, int rows, MoeGroups g, int tiles,
                          const uint16_t *P, size_t pp, bool one, const float *X, int xdiv, ActOp op, uint16_t *Hp, size_t hpp, float *Y, int ldy) {
    if (cols % 32 || (cols / 32) % PB || (MODE == 1 && (rows / 16) % SRF) || (MODE != 1 && nff % 16)) throw std::runtime_error("xq::full_q: shapes");
    const int sgw = MODE != 1 ? 2 : SRF, ngr = MODE != 1 ? nff / 16 : rows / 16 / SRF;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> st((size_t)sgw * MMAX * 16, h);
        sycl::local_accessor<uint32_t, 1> lt(Lut<F>::N, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)tiles, (size_t)ngr * sgw * 16), sycl::range<2>(1, (size_t)sgw * 16)),
                       XFullQ<F, MMAX, MODE, PB, SRF, GRF>{W, estride, cols, nff, g, P, pp, one, X, xdiv, op, Hp, hpp, Y, ldy, st, lt});
    });
}

// ---- the block sums by tile (prompts, Q4_K / Q5_K gate|up): XG[t][b][r] = X of the token of the tile's slot r (zero
// past its count), token = slot / xdiv
inline sycl::event xgather(sycl::queue &q, MoeGroups g, int tiles, const float *X, int xdiv, int nb, float *XG) {
    return q.parallel_for(sycl::range<2>((size_t)tiles, (size_t)nb * 16), [=](sycl::id<2> id) {
        const int t = (int)id[0];
        if (t >= g.ntiles[0]) return;
        const int b = (int)(id[1] / 16), r = (int)(id[1] % 16);
        XG[((size_t)t * nb + b) * 16 + r] = r < g.tile_n[t] ? X[(size_t)(g.slots[g.tile_s0[t] + r] / xdiv) * nb + b] : 0.0f;
    });
}

// ---- prompts: xm::XProd2's shape (work-group = SM tiles of one super-tile x SR row blocks; a sub-group = one tile of
// 16 slots x 2 B tiles; weights decoded for KC steps at a time into local memory, two buffers), with the blocks'
// scales (and -m1) in local memory; for Q4_K / Q5_K gate|up the block sums of an m-tile's 8 slots are one 32-byte
// read of XG (xgather). Inputs P [tile][3][16][cols]; MODE 0: H in parts to Hp [tile][3][16][nff]; MODE 1:
// y[slot][row]; MODE 2 (tests): gate|up sums to Y[slot][2 nff].
template <int F, int SM, int SR, int KC, int MODE, int NM = 2> struct XProdQ {
    using LF = Lay<F>;
    static_assert(SEG % KC == 0 && KC % 2 == 0 && (2 * KC) % SM == 0, "XProdQ: shapes");
    static constexpr bool XL = LF::KQ && MODE != 1;
    const uint8_t *W; size_t estride; int cols, nff;
    MoeGroups g; xm::Super st;
    const uint16_t *P; const float *XG; ActOp op; uint16_t *Hp; float *Y; int ldy;
    sycl::local_accessor<bf, 1> bs; sycl::local_accessor<float, 1> ss; sycl::local_accessor<float, 1> stg; sycl::local_accessor<uint32_t, 1> lt;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<256>};
    }
    int blkof(int rbk, int j) const { return MODE == 1 ? rbk * 2 + j : j * (nff / 16) + rbk; }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        const int w = (int)it.get_group(0);
        if (w >= st.count[0]) return;
        const auto sg = it.get_sub_group();
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int mt = sgi % SM, rbi = sgi / SM, rb0 = (int)it.get_group(1) * SR;
        const int t0 = st.t0[w], ntl = st.n[w], e = g.tile_exp[t0];
        const int t = t0 + mt;
        const bool active = mt < ntl;
        const int cnt = active ? g.tile_n[t] : 0;
        const int steps = cols / 16, nch = steps / KC, nb = cols / 32;
        const size_t r16 = LF::rb16(cols);
        const uint8_t *We = W + (size_t)e * estride;
        uint32_t *bw = reinterpret_cast<uint32_t *>(&bs[0]);
        constexpr int TILE = 128, BUF = SR * 2 * KC * TILE, NU = 2 * KC / SM, KB = KC / 2, SBUF = SR * 2 * KB * 16;
        QRaw raw[NU];
        auto fetch_c = [&](int c) {
#pragma unroll
            for (int i = 0; i < NU; ++i) {
                const int u = sgi + i * SM * SR, kk = u % KC, j = (u / KC) % 2, r = u / (2 * KC);
                const int b = (c * KC + kk) / 2;
                const uint8_t *bb = We + (size_t)blkof(rb0 + r, j) * r16;
                raw[i] = fetch<F>(bb + LF::unit(b), bb + LF::garea(b), ln);
            }
        };
        auto put = [&](int buf) {
#pragma unroll
            for (int i = 0; i < NU; ++i) {
                const int u = sgi + i * SM * SR, kk = u % KC, j = (u / KC) % 2, r = u / (2 * KC);
                words<F, false>(raw[i], kk % 2, bw + buf * BUF + ((r * 2 + j) * KC + kk) * TILE + ln, 16, &lt[0]);
                if (kk % 2 == 0) {
                    float s, nm;
                    scale<F>(raw[i], s, nm);
                    const int o = buf * 2 * SBUF + ((r * 2 + j) * KB + kk / 2) * 16 + ln;
                    ss[o] = s;
                    ss[o + SBUF] = nm;
                }
            }
        };
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, 8, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        C cc[2][NM], gs[2][NM], tot[2][NM], cz;
        jm::joint_matrix_fill(sg, cz, 0.0f);
#pragma unroll
        for (int j = 0; j < 2; ++j)
#pragma unroll
            for (int m = 0; m < NM; ++m) jm::joint_matrix_fill(sg, tot[j][m], 0.0f);
        auto lp = [](auto &acc, size_t off) { return acc.template get_multi_ptr<sycl::access::decorated::no>() + off; };
        const size_t per = (size_t)16 * cols;
        const bf *Pt = reinterpret_cast<const bf *>(P) + (size_t)t * 3 * per;
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        if constexpr (LF::NL) {
            for (int i = (int)it.get_local_linear_id(); i < Lut<F>::N; i += SM * SR * 16) lt[i] = lut_pair<F>(i);
            sycl::group_barrier(it.get_group());
        }
        fetch_c(0);
        put(0);
        sycl::group_barrier(it.get_group());
        int c = 0;
        for (int s0 = 0; s0 < steps; s0 += SEG) {
            const int ce = sycl::min(steps, s0 + SEG) / KC;
#pragma unroll
            for (int j = 0; j < 2; ++j)
#pragma unroll
                for (int m = 0; m < NM; ++m) jm::joint_matrix_fill(sg, gs[j][m], 0.0f);
            for (; c < ce; ++c) {
                const int buf = c & 1;
                if (c + 1 < nch) fetch_c(c + 1);
                if (active) {
#pragma unroll
                    for (int kk = 0; kk < KC; ++kk) {
                        const int k = c * KC + kk;
                        B b[2];
#pragma unroll
                        for (int j = 0; j < 2; ++j)
                            jm::joint_matrix_load(sg, b[j], lp(bs, (size_t)buf * BUF * 2 + (size_t)((rbi * 2 + j) * KC + kk) * TILE * 2), 32);
#pragma unroll
                        for (int m = 0; m < NM; ++m) {
                            A a0, a1, a2;
                            const bf *pa = Pt + (size_t)(m * 8) * cols + (size_t)k * 16;
                            jm::joint_matrix_load(sg, a0, gp(pa), cols);
                            jm::joint_matrix_load(sg, a1, gp(pa + per), cols);
                            jm::joint_matrix_load(sg, a2, gp(pa + 2 * per), cols);
#pragma unroll
                            for (int j = 0; j < 2; ++j) {
                                if (kk % 2 == 0) jm::joint_matrix_mad(sg, cc[j][m], a0, b[j], cz);
                                else jm::joint_matrix_mad(sg, cc[j][m], a0, b[j], cc[j][m]);
                                jm::joint_matrix_mad(sg, cc[j][m], a1, b[j], cc[j][m]);
                                jm::joint_matrix_mad(sg, cc[j][m], a2, b[j], cc[j][m]);
                            }
                        }
                        if (kk % 2 == 1) { // the block's end: G = fma(s, A, G) (and the min)
                            const int bl = k / 2;
                            float xv[NM][8];
                            if constexpr (XL) {
#pragma unroll
                                for (int m = 0; m < NM; ++m) {
                                    const float *xr = XG + ((size_t)t * nb + bl) * 16 + m * 8;
                                    const sycl::float4 u0 = *reinterpret_cast<const sycl::float4 *>(xr), u1 = *reinterpret_cast<const sycl::float4 *>(xr + 4);
#pragma unroll
                                    for (int q = 0; q < 4; ++q) { xv[m][q] = u0[q]; xv[m][4 + q] = u1[q]; }
                                }
                            }
#pragma unroll
                            for (int j = 0; j < 2; ++j) {
                                const int o = buf * 2 * SBUF + ((rbi * 2 + j) * KB + kk / 2) * 16 + ln;
                                const float s = ss[o];
#pragma unroll
                                for (int m = 0; m < NM; ++m) {
                                    jm::joint_matrix_apply(sg, gs[j][m], cc[j][m], [=](float &x, float &y) { x = sycl::fma(s, y, x); });
                                    if constexpr (XL) {
                                        const float nm = ss[o + SBUF];
                                        int ei = 0;
                                        jm::joint_matrix_apply(sg, gs[j][m], [&](float &x) { x = sycl::fma(nm, xv[m][ei], x); ++ei; });
                                    }
                                }
                            }
                        }
                    }
                }
                if (c + 1 < nch) put(buf ^ 1);
                sycl::group_barrier(it.get_group());
            }
#pragma unroll
            for (int j = 0; j < 2; ++j)
#pragma unroll
                for (int m = 0; m < NM; ++m) jm::joint_matrix_apply(sg, tot[j][m], gs[j][m], [](float &x, float &y) { x = x + y; });
        }
        if (!active) return;
        float *sp = &stg[0] + (size_t)sgi * 256;
        auto lps = [&](int off) { return stg.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)sgi * 256 + off; };
        const int rbk = rb0 + rbi;
        if constexpr (MODE == 0) {
            const bool sc = op.escale != nullptr;
            const float sv = sc ? op.escale[e] : 1.0f, beta = op.beta, lb = op.lb;
#pragma unroll
            for (int m = 0; m < NM; ++m) {
                jm::joint_matrix_apply(sg, tot[0][m], tot[1][m], [=](float &x, float &y) { x = xm::act(x, y, sv, sc, beta, lb); });
                jm::joint_matrix_store(sg, tot[0][m], lps(m * 128), 16, jm::layout::row_major);
            }
            sycl::group_barrier(sg);
            const size_t ph = (size_t)16 * nff;
            uint16_t *ho = Hp + (size_t)t * 3 * ph + rbk * 16 + ln;
            for (int r = 0; r < 16; ++r) {
                const float v = r < cnt ? sp[r * 16 + ln] : 0.0f;
                uint16_t a, b, d;
                split3(v, a, b, d);
                ho[(size_t)r * nff] = a; ho[ph + (size_t)r * nff] = b; ho[2 * ph + (size_t)r * nff] = d;
            }
        } else {
#pragma unroll
            for (int j = 0; j < 2; ++j) {
#pragma unroll
                for (int m = 0; m < NM; ++m) jm::joint_matrix_store(sg, tot[j][m], lps(m * 128), 16, jm::layout::row_major);
                sycl::group_barrier(sg);
                const int row = (MODE == 1 ? rbk * 32 + j * 16 : j * nff + rbk * 16) + ln;
                for (int r = 0; r < cnt; ++r) {
                    const int slot = g.slots[g.tile_s0[t] + r];
                    Y[(size_t)slot * ldy + row] = sp[r * 16 + ln];
                }
                sycl::group_barrier(sg);
            }
        }
    }
};
template <int F, int SM, int SR, int KC, int MODE, int NM = 2>
inline sycl::event prod_q(sycl::queue &q, const uint8_t *W, size_t estride, int cols, int nff, int nrb, MoeGroups g, xm::Super st, int stb,
                          const uint16_t *P, const float *XG, ActOp op, uint16_t *Hp, float *Y, int ldy) {
    using K = XProdQ<F, SM, SR, KC, MODE, NM>;
    if (cols % (16 * KC) || nrb % SR || st.sm != SM) throw std::runtime_error("xq::prod_q: shapes");
    return q.submit([&](sycl::handler &h) {
        constexpr int KB = KC / 2, SBUF = SR * 2 * KB * 16;
        sycl::local_accessor<bf, 1> bs(2 * SR * 2 * KC * 256, h);
        sycl::local_accessor<float, 1> ss(2 * 2 * SBUF, h);
        sycl::local_accessor<float, 1> stg(SM * SR * 256, h);
        sycl::local_accessor<uint32_t, 1> lt(Lay<F>::NL ? Lut<F>::N : 1, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)stb, (size_t)(nrb / SR) * SM * SR * 16), sycl::range<2>(1, SM * SR * 16)),
                       K{W, estride, cols, nff, g, st, P, XG, op, Hp, Y, ldy, bs, ss, stg, lt});
    });
}

// ---- dispatch by format (the engine's layers: gate|up Q5_K / Q4_K / IQ4_XS, down Q5_0 / IQ4_NL)
template <int MMAX, int MODE>
inline sycl::event full(sycl::queue &q, int f, const uint8_t *W, size_t estride, int cols, int nff, int rows, MoeGroups g, int tiles,
                        const uint16_t *P, size_t pp, bool one, const float *X, int xdiv, ActOp op, uint16_t *Hp, size_t hpp, float *Y, int ldy) {
    if constexpr (MODE == 1) {
        if (f == F_Q5_0) return full_q<F_Q5_0, MMAX, 1>(q, W, estride, cols, nff, rows, g, tiles, P, pp, one, X, xdiv, op, Hp, hpp, Y, ldy);
        if (f == F_IQ4_NL) return full_q<F_IQ4_NL, MMAX, 1>(q, W, estride, cols, nff, rows, g, tiles, P, pp, one, X, xdiv, op, Hp, hpp, Y, ldy);
    } else {
        if (f == F_Q5_K) return full_q<F_Q5_K, MMAX, MODE>(q, W, estride, cols, nff, rows, g, tiles, P, pp, one, X, xdiv, op, Hp, hpp, Y, ldy);
        if (f == F_Q4_K) return full_q<F_Q4_K, MMAX, MODE>(q, W, estride, cols, nff, rows, g, tiles, P, pp, one, X, xdiv, op, Hp, hpp, Y, ldy);
        if (f == F_IQ4_XS) return full_q<F_IQ4_XS, MMAX, MODE>(q, W, estride, cols, nff, rows, g, tiles, P, pp, one, X, xdiv, op, Hp, hpp, Y, ldy);
    }
    throw std::runtime_error("xq::full: format");
}
template <int MODE, int SM = 4, int SR = 4, int KC = 4>
inline sycl::event prod(sycl::queue &q, int f, const uint8_t *W, size_t estride, int cols, int nff, int nrb, MoeGroups g, xm::Super st, int stb,
                        const uint16_t *P, const float *XG, ActOp op, uint16_t *Hp, float *Y, int ldy) {
    if constexpr (MODE == 1) {
        if (f == F_Q5_0) return prod_q<F_Q5_0, SM, SR, KC, 1>(q, W, estride, cols, nff, nrb, g, st, stb, P, XG, op, Hp, Y, ldy);
        if (f == F_IQ4_NL) return prod_q<F_IQ4_NL, SM, SR, KC, 1>(q, W, estride, cols, nff, nrb, g, st, stb, P, XG, op, Hp, Y, ldy);
    } else {
        if (f == F_Q5_K) return prod_q<F_Q5_K, SM, SR, KC, MODE>(q, W, estride, cols, nff, nrb, g, st, stb, P, XG, op, Hp, Y, ldy);
        if (f == F_Q4_K) return prod_q<F_Q4_K, SM, SR, KC, MODE>(q, W, estride, cols, nff, nrb, g, st, stb, P, XG, op, Hp, Y, ldy);
        if (f == F_IQ4_XS) return prod_q<F_IQ4_XS, SM, SR, KC, MODE>(q, W, estride, cols, nff, nrb, g, st, stb, P, XG, op, Hp, Y, ldy);
    }
    throw std::runtime_error("xq::prod: format");
}
} // namespace ink::xq
