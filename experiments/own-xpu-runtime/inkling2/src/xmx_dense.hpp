// xmx_dense.hpp: Q8_0 dense matrices on the matrix engines with exact products (prototype, bench_xdense).
//
// Arithmetic (the same for every step size):
//   - every input x (fp32) is split into three bf16 parts (bfsplit.hpp split3, exact: x = x1 + x2 + x3);
//   - a Q8_0 code q (int8) is exactly a bf16; the block scale d (fp16, one per 32 inputs) is applied to the block's sum;
//   - one output (token, row) runs over the blocks b of 32 inputs (2 steps of 16): c1 = DPAS chain of x1 * q over the
//     block's two steps from 0, c23 = DPAS chain of x2 * q then x3 * q per step from 0; total = fma(d_b, c1 + c23,
//     total), total starting at 0, blocks in order;
//   - DPAS rows do not depend on the other rows of their tile, so the bits do not depend on how many tokens a step has.
//
// Weight layout ("Q8T", in place of the planar rows, the same bytes): [block of 16 rows][block b of 32 inputs][544
// bytes: step 0 = row n's 16 codes at 16 n, step 1 at 256 + 16 n, row n's half scale at 512 + 2 n]. A sub-group reads
// one step of 16 rows with one contiguous 256-byte load.
// Inputs: P[p][token][cols] bf16 (part stride pp, tokens past M zero up to the kernel's padding).
#pragma once
#include "xmx_moe.hpp"

namespace ink::xd {
namespace jm = sycl::ext::oneapi::experimental::matrix;
using bf = sycl::ext::oneapi::bfloat16;
constexpr int TQ = 544;

// planar Q8_0P rows (qs[cols] int8 | d[cols / 32] half; stride rb = cols * 34 / 32) -> Q8T, in place through tmp
inline void repack_q8t(sycl::queue &q, uint8_t *W, size_t rb, int rows, int cols, uint8_t *tmp) {
    if (rows % 16 || cols % 32 || rb * 32 != (size_t)cols * 34) throw std::runtime_error("xd::repack_q8t: shapes");
    q.memcpy(tmp, W, rb * rows).wait();
    const int nb = cols / 32;
    q.parallel_for(sycl::range<2>((size_t)(rows / 16) * nb, 16), [=](sycl::item<2> it) {
        const int u = (int)it[0], n = (int)it[1], r16 = u / nb, b = u % nb;
        const uint8_t *row = tmp + (size_t)(r16 * 16 + n) * rb;
        uint8_t *o = W + (size_t)u * TQ;
        for (int s = 0; s < 2; ++s)
            for (int i = 0; i < 16; ++i) o[s * 256 + n * 16 + i] = row[b * 32 + s * 16 + i];
        o[512 + 2 * n] = row[cols + 2 * b];
        o[513 + 2 * n] = row[cols + 2 * b + 1];
    }).wait();
}

inline uint32_t bf_bits(int8_t v) { return sycl::bit_cast<uint32_t>((float)v) >> 16; } // exact
// 16 codes (k order) -> 8 words of bf16 pairs (values 2j, 2j + 1) at o[j * os]
inline void q8_pairs(sycl::vec<uint32_t, 4> c, uint32_t *o, int os) {
#pragma unroll
    for (int w = 0; w < 4; ++w)
#pragma unroll
        for (int h = 0; h < 2; ++h) {
            const uint32_t u = c[w] >> (16 * h);
            o[(2 * w + h) * os] = bf_bits((int8_t)(u & 0xff)) | (bf_bits((int8_t)((u >> 8) & 0xff)) << 16);
        }
}
inline float half_f(uint16_t b) { sycl::half h = sycl::bit_cast<sycl::half>(b); return (float)h; }

// split: P[p][t][cols] from x[t][ldx] for t < M, zeros for M <= t < Mpad (8 columns per work-item)
inline sycl::event split(sycl::queue &q, const float *x, int ldx, int M, int Mpad, int cols, uint16_t *P, size_t pp) {
    const int c8 = cols / 8;
    return q.parallel_for(sycl::range<1>((size_t)Mpad * c8), [=](sycl::id<1> id) {
        const int t = (int)(id[0] / c8), c = (int)(id[0] % c8) * 8;
        uint16_t *o = P + (size_t)t * cols + c;
        for (int i = 0; i < 8; ++i) {
            const float v = t < M ? x[(size_t)t * ldx + c + i] : 0.0f;
            split3_store(v, o + i, pp);
        }
    });
}

// A operands built in registers (bench_xa: lane n = column n, element e = row e, for 1, 2, 4 and 8 rows): rows
// t0 + e of x (fp32, stride ldx), columns c0 + lane, split into three parts; rows >= mst read as 0
template <int MR, class A> inline void a_split(sycl::sub_group sg, const float *x, size_t ldx, int t0, int mst, int c0, int ln, A &a0, A &a1, A &a2) {
    uint16_t p0[MR], p1[MR], p2[MR];
#pragma unroll
    for (int e = 0; e < MR; ++e) {
        const float v = t0 + e < mst ? x[(size_t)(t0 + e) * ldx + c0 + ln] : 0.0f;
        split3(v, p0[e], p1[e], p2[e]);
    }
    int e0 = 0, e1 = 0, e2 = 0;
    jm::joint_matrix_apply(sg, a0, [&](bf &y) { y = sycl::bit_cast<bf>(p0[e0]); ++e0; });
    jm::joint_matrix_apply(sg, a1, [&](bf &y) { y = sycl::bit_cast<bf>(p1[e1]); ++e1; });
    jm::joint_matrix_apply(sg, a2, [&](bf &y) { y = sycl::bit_cast<bf>(p2[e2]); ++e2; });
}

// Steps of many tokens. Work-group = SM x SR sub-groups; a sub-group = NM row tiles of 8 tokens x NB B tiles (16 rows
// each). The work-group decodes its SR x NB B tiles for KC steps at a time into local memory (two buffers, one barrier
// per chunk); the scales of those blocks go there too as floats. M % (8 NM SM) == 0 for the inputs (padded), outputs
// stored for tokens < Mst.
// LE: weights in the Q8E layout (xmx_esimd.hpp); a sub-group block read gives each lane its row's 16 codes of a step.
// BF: bf16 weights in the BFE layout (xmx_esimd.hpp; each step's 512 bytes are the operand), scale 1, rows >= rv not stored
template <int SM, int SR, int NM, int NB, int KC, bool C23 = true, int G = 0, bool XS = false, bool LE = false, bool BF = false> struct XDense {
    static_assert(KC % 2 == 0, "XDense: whole blocks per chunk");
    static_assert(G == 0 || (2 * G) % KC == 0, "XDense: whole chunks per group");
    static constexpr int NSG = SM * SR, U = SR * NB * KC, US = SR * NB * KC / 2;
    static_assert(U % NSG == 0, "XDense: decode units");
    static constexpr int NU = U / NSG, NUS = (US + NSG - 1) / NSG;
    static constexpr int TILE = 128, BUF = SR * NB * KC * TILE, SBUF = SR * NB * (KC / 2) * 16;
    const uint8_t *W; int cols; const uint16_t *P; size_t pp; int Mst; float *Y; int ldy; const float *xs; int ldx;
    sycl::local_accessor<bf, 1> bs; sycl::local_accessor<float, 1> ss; sycl::local_accessor<float, 1> stg;
    int rv = 1 << 30;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<256>};
    }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        const auto sg = it.get_sub_group();
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int mi = sgi % SM, ri = sgi / SM;
        const int nb = cols / 32, steps = cols / 16, nch = steps / KC;
        const int r16w = (int)it.get_group(1) * SR * NB;
        const int t0 = ((int)it.get_group(0) * SM + mi) * NM * 8;
        uint32_t *bw = reinterpret_cast<uint32_t *>(&bs[0]);
        sycl::vec<uint32_t, BF ? 8 : 4> raw[NU];
        uint16_t rs[NUS];
        auto fetch = [&](int c) {
#pragma unroll
            for (int i = 0; i < NU; ++i) {
                const int u = sgi + i * NSG, tile = u / KC, kk = u % KC, k = c * KC + kk;
                if constexpr (BF)
                    raw[i] = sg.load<8>(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                        const_cast<uint32_t *>(reinterpret_cast<const uint32_t *>(W + ((size_t)(r16w + tile) * steps + k) * 512))));
                else if constexpr (LE)
                    raw[i] = sg.load<4>(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                        const_cast<uint32_t *>(reinterpret_cast<const uint32_t *>(W + ((size_t)(r16w + tile) * (nb / 8) + k / 16) * 4352 + 512 * ((k / 2) % 8) + 256 * (k & 1)))));
                else
                    raw[i] = *reinterpret_cast<const sycl::vec<uint32_t, 4> *>(W + ((size_t)(r16w + tile) * nb + k / 2) * TQ + (k & 1) * 256 + ln * 16);
            }
#pragma unroll
            for (int i = 0; i < NUS; ++i) {
                const int u = sgi + i * NSG;
                if (!BF && u < US) {
                    const int tile = u / (KC / 2), bb = u % (KC / 2), b = c * (KC / 2) + bb;
                    if constexpr (LE) rs[i] = *reinterpret_cast<const uint16_t *>(W + ((size_t)(r16w + tile) * (nb / 8) + b / 8) * 4352 + 4096 + 32 * (b % 8) + 2 * ln);
                    else rs[i] = *reinterpret_cast<const uint16_t *>(W + ((size_t)(r16w + tile) * nb + c * (KC / 2) + bb) * TQ + 512 + 2 * ln);
                }
            }
        };
        auto put = [&](int buf) {
#pragma unroll
            for (int i = 0; i < NU; ++i) {
                const int u = sgi + i * NSG, tile = u / KC, kk = u % KC;
                if constexpr (BF) {
#pragma unroll
                    for (int q = 0; q < 8; ++q) bw[buf * BUF + (tile * KC + kk) * TILE + q * 16 + ln] = raw[i][q];
                } else
                    q8_pairs(raw[i], bw + buf * BUF + (tile * KC + kk) * TILE + ln, 16);
            }
#pragma unroll
            for (int i = 0; i < NUS; ++i) {
                const int u = sgi + i * NSG;
                if (u < US) ss[buf * SBUF + u * 16 + ln] = BF ? 1.0f : half_f(rs[i]);
            }
        };
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, 8, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        C c1[NB][NM], c23[NB][C23 ? NM : 1], gs[NB][G ? NM : 1], tot[NB][NM], cz;
        jm::joint_matrix_fill(sg, cz, 0.0f);
#pragma unroll
        for (int j = 0; j < NB; ++j)
#pragma unroll
            for (int m = 0; m < NM; ++m) { jm::joint_matrix_fill(sg, tot[j][m], 0.0f); if constexpr (G > 0) jm::joint_matrix_fill(sg, gs[j][m], 0.0f); }
        auto lp = [](auto &acc, size_t off) { return acc.template get_multi_ptr<sycl::access::decorated::no>() + off; };
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        const bf *Pt = reinterpret_cast<const bf *>(P) + (size_t)t0 * cols;
        fetch(0);
        put(0);
        sycl::group_barrier(it.get_group());
        for (int c = 0; c < nch; ++c) {
            const int buf = c & 1;
            if (c + 1 < nch) fetch(c + 1);
#pragma unroll
            for (int kk = 0; kk < KC; ++kk) {
                const int k = c * KC + kk;
                B b[NB];
#pragma unroll
                for (int j = 0; j < NB; ++j) jm::joint_matrix_load(sg, b[j], lp(bs, (size_t)buf * BUF * 2 + (size_t)((ri * NB + j) * KC + kk) * TILE * 2), 32);
#pragma unroll
                for (int m = 0; m < NM; ++m) {
                    A a0, a1, a2;
                    if constexpr (XS) {
                        jm::joint_matrix_load(sg, a0, lp(bs, 0), 16); // defined before the apply (any values)
                        jm::joint_matrix_load(sg, a1, lp(bs, 0), 16);
                        jm::joint_matrix_load(sg, a2, lp(bs, 0), 16);
                        a_split<8>(sg, xs, (size_t)ldx, t0 + m * 8, Mst, k * 16, ln, a0, a1, a2);
                    } else {
                        const bf *pa = Pt + (size_t)(m * 8) * cols + (size_t)k * 16;
                        jm::joint_matrix_load(sg, a0, gp(pa), cols);
                        jm::joint_matrix_load(sg, a1, gp(pa + pp), cols);
                        jm::joint_matrix_load(sg, a2, gp(pa + 2 * pp), cols);
                    }
#pragma unroll
                    for (int j = 0; j < NB; ++j) {
                        if constexpr (C23) {
                            if (kk % 2 == 0) {
                                jm::joint_matrix_mad(sg, c1[j][m], a0, b[j], cz);
                                jm::joint_matrix_mad(sg, c23[j][m], a1, b[j], cz);
                            } else {
                                jm::joint_matrix_mad(sg, c1[j][m], a0, b[j], c1[j][m]);
                                jm::joint_matrix_mad(sg, c23[j][m], a1, b[j], c23[j][m]);
                            }
                            jm::joint_matrix_mad(sg, c23[j][m], a2, b[j], c23[j][m]);
                        } else { // one chain: x1, x2, x3 per step
                            if (kk % 2 == 0) jm::joint_matrix_mad(sg, c1[j][m], a0, b[j], cz);
                            else jm::joint_matrix_mad(sg, c1[j][m], a0, b[j], c1[j][m]);
                            jm::joint_matrix_mad(sg, c1[j][m], a1, b[j], c1[j][m]);
                            jm::joint_matrix_mad(sg, c1[j][m], a2, b[j], c1[j][m]);
                        }
                    }
                }
                if (kk % 2 == 1) {
#pragma unroll
                    for (int j = 0; j < NB; ++j) {
                        const float dj = ss[buf * SBUF + ((ri * NB + j) * (KC / 2) + kk / 2) * 16 + ln];
#pragma unroll
                        for (int m = 0; m < NM; ++m) {
                            if constexpr (C23) jm::joint_matrix_apply(sg, c1[j][m], c23[j][m], [](float &x, float &y) { x = x + y; });
                            if constexpr (G > 0) jm::joint_matrix_apply(sg, gs[j][m], c1[j][m], [=](float &x, float &y) { x = sycl::fma(dj, y, x); });
                            else jm::joint_matrix_apply(sg, tot[j][m], c1[j][m], [=](float &x, float &y) { x = sycl::fma(dj, y, x); });
                        }
                    }
                }
            }
            if constexpr (G > 0) {
                if ((c + 1) % (2 * G / KC) == 0 || c + 1 == nch) { // a group's end: total = total + group sum, group sum = 0
#pragma unroll
                    for (int j = 0; j < NB; ++j)
#pragma unroll
                        for (int m = 0; m < NM; ++m) {
                            jm::joint_matrix_apply(sg, tot[j][m], gs[j][m], [](float &x, float &y) { x = x + y; });
                            jm::joint_matrix_fill(sg, gs[j][m], 0.0f);
                        }
                }
            }
            if (c + 1 < nch) put(buf ^ 1);
            sycl::group_barrier(it.get_group());
        }
        // outputs: Y[t][row], tokens < Mst
#pragma unroll
        for (int j = 0; j < NB; ++j) {
            const int row = (r16w + ri * NB + j) * 16;
            if (row >= rv) continue;
            const bool rfull = row + 16 <= rv;
#pragma unroll
            for (int m = 0; m < NM; ++m) {
                const int tm = t0 + m * 8;
                if (tm + 8 <= Mst && rfull) {
                    jm::joint_matrix_store(sg, tot[j][m], sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(Y + (size_t)tm * ldy + row), ldy,
                                           jm::layout::row_major);
                } else if (tm < Mst) {
                    float *sp = &stg[0] + (size_t)sgi * 128;
                    jm::joint_matrix_store(sg, tot[j][m], lp(stg, (size_t)sgi * 128), 16, jm::layout::row_major);
                    sycl::group_barrier(sg);
                    for (int r = 0; r < 8 && tm + r < Mst; ++r) if (row + ln < rv) Y[(size_t)(tm + r) * ldy + row + ln] = sp[r * 16 + ln];
                    sycl::group_barrier(sg);
                }
            }
        }
    }
};
// BF: rows = the padded rows of the BFE copy, rv = the rows stored
template <int SM, int SR, int NM, int NB, int KC, bool C23 = true, int G = 0, bool XS = false, bool LE = false, bool BF = false>
inline sycl::event dense(sycl::queue &q, const uint8_t *W, int rows, int cols, const uint16_t *P, size_t pp, int Mpad, int Mst, float *Y, int ldy,
                         const float *xs = nullptr, int ldx = 0, int rv = 1 << 30) {
    if (cols % (16 * KC) || rows % (16 * NB * SR) || Mpad % (8 * NM * SM) || ((LE || BF) && cols % 256)) throw std::runtime_error("xd::dense: shapes");
    using K = XDense<SM, SR, NM, NB, KC, C23, G, XS, LE, BF>;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> bs(2 * K::BUF * 2, h);
        sycl::local_accessor<float, 1> ss(2 * K::SBUF, h);
        sycl::local_accessor<float, 1> stg((size_t)SM * SR * 128, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)Mpad / (8 * NM * SM), (size_t)rows / (16 * NB * SR) * SM * SR * 16),
                                         sycl::range<2>(1, (size_t)SM * SR * 16)),
                       K{W, cols, P, pp, Mst, Y, ldy, xs, ldx, bs, ss, stg, rv});
    });
}

// Steps of 1-8 tokens: one sub-group per 16 rows over all inputs, MR rows (1, 2, 4, 8) per DPAS tile; the B tile built
// in registers (joint_matrix_apply on a tile loaded once from zeros: lane n = column n, k in order), PF steps fetched
// ahead. Outputs for tokens < Mst.
template <int MR, int PF, int SGW> struct XDSmall {
    static_assert(PF % 2 == 0, "XDSmall: whole blocks");
    const uint8_t *W; int cols; const uint16_t *P; size_t pp; int Mst; float *Y; int ldy;
    sycl::local_accessor<bf, 1> zb; sycl::local_accessor<float, 1> st;
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<1> it) const {
        const auto sg = it.get_sub_group();
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int r16 = (int)it.get_group(0) * SGW + sgi, nb = cols / 32, steps = cols / 16;
        {
            const int lid = (int)it.get_local_linear_id();
            for (int i = lid; i < 128; i += SGW * 16) reinterpret_cast<uint32_t *>(&zb[0])[i] = 0u;
            sycl::group_barrier(it.get_group());
        }
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, MR, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, MR, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        const uint8_t *w = W + (size_t)r16 * nb * TQ;
        auto ldc = [&](int k) { return *reinterpret_cast<const sycl::vec<uint32_t, 4> *>(w + (size_t)(k / 2) * TQ + (k & 1) * 256 + ln * 16); };
        auto lds = [&](int k) { return *reinterpret_cast<const uint16_t *>(w + (size_t)(k / 2) * TQ + 512 + 2 * ln); };
        sycl::vec<uint32_t, 4> r[PF];
        uint16_t sr[PF / 2];
#pragma unroll
        for (int i = 0; i < PF; ++i) r[i] = ldc(i);
#pragma unroll
        for (int i = 0; i < PF / 2; ++i) sr[i] = lds(2 * i);
        C c1, c23, tot, cz;
        jm::joint_matrix_fill(sg, tot, 0.0f);
        jm::joint_matrix_fill(sg, cz, 0.0f);
        B rb;
        jm::joint_matrix_load(sg, rb, zb.template get_multi_ptr<sycl::access::decorated::no>(), 32);
        const bf *pa = reinterpret_cast<const bf *>(P);
        for (int kb = 0; kb < steps; kb += PF) {
            const int kn = sycl::min(kb + PF, steps - PF);
            sycl::vec<uint32_t, 4> n[PF];
            uint16_t sn[PF / 2];
#pragma unroll
            for (int i = 0; i < PF; ++i) n[i] = ldc(kn + i);
#pragma unroll
            for (int i = 0; i < PF / 2; ++i) sn[i] = lds(kn + 2 * i);
#pragma unroll
            for (int i = 0; i < PF; ++i) {
                float v[16];
#pragma unroll
                for (int e = 0; e < 16; ++e) v[e] = (float)(int8_t)((r[i][e / 4] >> (8 * (e % 4))) & 0xff);
                int e = 0;
                jm::joint_matrix_apply(sg, rb, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v[e]) >> 16)); ++e; });
                A x0, x1, x2;
                const bf *pk = pa + (size_t)(kb + i) * 16;
                jm::joint_matrix_load(sg, x0, gp(pk), cols);
                jm::joint_matrix_load(sg, x1, gp(pk + pp), cols);
                jm::joint_matrix_load(sg, x2, gp(pk + 2 * pp), cols);
                if (i % 2 == 0) {
                    jm::joint_matrix_mad(sg, c1, x0, rb, cz);
                    jm::joint_matrix_mad(sg, c23, x1, rb, cz);
                } else {
                    jm::joint_matrix_mad(sg, c1, x0, rb, c1);
                    jm::joint_matrix_mad(sg, c23, x1, rb, c23);
                }
                jm::joint_matrix_mad(sg, c23, x2, rb, c23);
                if (i % 2 == 1) {
                    const float d = half_f(sr[i / 2]);
                    jm::joint_matrix_apply(sg, c1, c23, [](float &x, float &y) { x = x + y; });
                    jm::joint_matrix_apply(sg, tot, c1, [=](float &x, float &y) { x = sycl::fma(d, y, x); });
                }
            }
#pragma unroll
            for (int i = 0; i < PF; ++i) r[i] = n[i];
#pragma unroll
            for (int i = 0; i < PF / 2; ++i) sr[i] = sn[i];
        }
        float *sp = &st[0] + (size_t)sgi * MR * 16;
        jm::joint_matrix_store(sg, tot, st.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)sgi * MR * 16, 16, jm::layout::row_major);
        sycl::group_barrier(sg);
        for (int t = 0; t < MR && t < Mst; ++t) Y[(size_t)t * ldy + r16 * 16 + ln] = sp[t * 16 + ln];
    }
};
template <int MR, int PF = 4, int SGW = 2>
inline sycl::event dsmall(sycl::queue &q, const uint8_t *W, int rows, int cols, const uint16_t *P, size_t pp, int Mst, float *Y, int ldy) {
    if (cols % (16 * PF) || rows % (16 * SGW)) throw std::runtime_error("xd::dsmall: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> zb(256, h);
        sycl::local_accessor<float, 1> st((size_t)SGW * MR * 16, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)rows / 16 * 16), sycl::range<1>((size_t)SGW * 16)),
                       XDSmall<MR, PF, SGW>{W, cols, P, pp, Mst, Y, ldy, zb, st});
    });
}
// Steps of 1-8 tokens with the grouped arithmetic (G blocks per group): one work-group per 16 rows, one sub-group per
// group (all its steps' codes loaded at once), group sums to local memory, then lane n adds row n's groups in order
// (total from 0). MR rows (1, 2, 4, 8) per DPAS tile, outputs for tokens < Mst. C23 as XDense.
template <int MR, int G, bool C23> struct XDGroup {
    const uint8_t *W; int cols; const uint16_t *P; size_t pp; int Mst; float *Y; int ldy;
    sycl::local_accessor<bf, 1> zb; sycl::local_accessor<float, 1> st;
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<1> it) const {
        const auto sg = it.get_sub_group();
        const int gi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int r16 = (int)it.get_group(0), nb = cols / 32, ng = nb / G;
        {
            const int lid = (int)it.get_local_linear_id();
            if (lid < 128) reinterpret_cast<uint32_t *>(&zb[0])[lid] = 0u;
            sycl::group_barrier(it.get_group());
        }
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, MR, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, MR, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        const uint8_t *w = W + ((size_t)r16 * nb + (size_t)gi * G) * TQ;
        sycl::vec<uint32_t, 4> r[2 * G];
        uint16_t sr[G];
#pragma unroll
        for (int i = 0; i < 2 * G; ++i) r[i] = *reinterpret_cast<const sycl::vec<uint32_t, 4> *>(w + (size_t)(i / 2) * TQ + (i & 1) * 256 + ln * 16);
#pragma unroll
        for (int i = 0; i < G; ++i) sr[i] = *reinterpret_cast<const uint16_t *>(w + (size_t)i * TQ + 512 + 2 * ln);
        C c1, c23, gsum, cz;
        jm::joint_matrix_fill(sg, gsum, 0.0f);
        jm::joint_matrix_fill(sg, cz, 0.0f);
        B rb;
        jm::joint_matrix_load(sg, rb, zb.template get_multi_ptr<sycl::access::decorated::no>(), 32);
        const bf *pa = reinterpret_cast<const bf *>(P) + (size_t)gi * G * 32;
#pragma unroll
        for (int i = 0; i < 2 * G; ++i) {
            float v[16];
#pragma unroll
            for (int e = 0; e < 16; ++e) v[e] = (float)(int8_t)((r[i][e / 4] >> (8 * (e % 4))) & 0xff);
            int e = 0;
            jm::joint_matrix_apply(sg, rb, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v[e]) >> 16)); ++e; });
            A x0, x1, x2;
            const bf *pk = pa + (size_t)i * 16;
            jm::joint_matrix_load(sg, x0, gp(pk), cols);
            jm::joint_matrix_load(sg, x1, gp(pk + pp), cols);
            jm::joint_matrix_load(sg, x2, gp(pk + 2 * pp), cols);
            if constexpr (C23) {
                if (i % 2 == 0) {
                    jm::joint_matrix_mad(sg, c1, x0, rb, cz);
                    jm::joint_matrix_mad(sg, c23, x1, rb, cz);
                } else {
                    jm::joint_matrix_mad(sg, c1, x0, rb, c1);
                    jm::joint_matrix_mad(sg, c23, x1, rb, c23);
                }
                jm::joint_matrix_mad(sg, c23, x2, rb, c23);
            } else {
                if (i % 2 == 0) jm::joint_matrix_mad(sg, c1, x0, rb, cz);
                else jm::joint_matrix_mad(sg, c1, x0, rb, c1);
                jm::joint_matrix_mad(sg, c1, x1, rb, c1);
                jm::joint_matrix_mad(sg, c1, x2, rb, c1);
            }
            if (i % 2 == 1) {
                const float d = half_f(sr[i / 2]);
                if constexpr (C23) jm::joint_matrix_apply(sg, c1, c23, [](float &x, float &y) { x = x + y; });
                jm::joint_matrix_apply(sg, gsum, c1, [=](float &x, float &y) { x = sycl::fma(d, y, x); });
            }
        }
        jm::joint_matrix_store(sg, gsum, st.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)gi * MR * 16, 16, jm::layout::row_major);
        sycl::group_barrier(it.get_group());
        if (gi == 0) {
            for (int t = 0; t < MR && t < Mst; ++t) {
                float tot = 0.0f;
                for (int g = 0; g < ng; ++g) tot = tot + st[(size_t)g * MR * 16 + t * 16 + ln];
                Y[(size_t)t * ldy + r16 * 16 + ln] = tot;
            }
        }
    }
};
template <int MR, int G = 8, bool C23 = true>
inline sycl::event dgroup(sycl::queue &q, const uint8_t *W, int rows, int cols, const uint16_t *P, size_t pp, int Mst, float *Y, int ldy) {
    const int ng = cols / 32 / G;
    if (cols % (32 * G) || rows % 16) throw std::runtime_error("xd::dgroup: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> zb(256, h);
        sycl::local_accessor<float, 1> st((size_t)ng * MR * 16, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)rows / 16 * ng * 16), sycl::range<1>((size_t)ng * 16)),
                       XDGroup<MR, G, C23>{W, cols, P, pp, Mst, Y, ldy, zb, st});
    });
}
// XDGroup with the inputs split in the kernel (x fp32 [t][ldx], the A tiles built by a_split) and every load of the
// group's codes and scales issued before the zero tile's barrier; one chain (x1, x2, x3 per step) per block, the
// grouped arithmetic of XDense<..., false, G>.
template <int MR, int G> struct XDGroupX {
    const uint8_t *W; int cols; const float *x; int ldx; int Mst; float *Y; int ldy;
    sycl::local_accessor<bf, 1> zb; sycl::local_accessor<float, 1> st;
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<1> it) const {
        const auto sg = it.get_sub_group();
        const int gi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int r16 = (int)it.get_group(0), nb = cols / 32, ng = nb / G;
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, MR, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, MR, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        const uint8_t *w = W + ((size_t)r16 * nb + (size_t)gi * G) * TQ;
        sycl::vec<uint32_t, 4> r[2 * G];
        uint16_t sr[G];
#pragma unroll
        for (int i = 0; i < 2 * G; ++i) r[i] = *reinterpret_cast<const sycl::vec<uint32_t, 4> *>(w + (size_t)(i / 2) * TQ + (i & 1) * 256 + ln * 16);
#pragma unroll
        for (int i = 0; i < G; ++i) sr[i] = *reinterpret_cast<const uint16_t *>(w + (size_t)i * TQ + 512 + 2 * ln);
        {
            const int lid = (int)it.get_local_linear_id();
            if (lid < 128) reinterpret_cast<uint32_t *>(&zb[0])[lid] = 0u;
            sycl::group_barrier(it.get_group());
        }
        C c1, gsum, cz;
        jm::joint_matrix_fill(sg, gsum, 0.0f);
        jm::joint_matrix_fill(sg, cz, 0.0f);
        B rb;
        A x0, x1, x2;
        jm::joint_matrix_load(sg, rb, zb.template get_multi_ptr<sycl::access::decorated::no>(), 32);
        jm::joint_matrix_load(sg, x0, zb.template get_multi_ptr<sycl::access::decorated::no>(), 16);
        jm::joint_matrix_load(sg, x1, zb.template get_multi_ptr<sycl::access::decorated::no>(), 16);
        jm::joint_matrix_load(sg, x2, zb.template get_multi_ptr<sycl::access::decorated::no>(), 16);
        const int c0 = gi * G * 32;
#pragma unroll
        for (int i = 0; i < 2 * G; ++i) {
            float v[16];
#pragma unroll
            for (int e = 0; e < 16; ++e) v[e] = (float)(int8_t)((r[i][e / 4] >> (8 * (e % 4))) & 0xff);
            int e = 0;
            jm::joint_matrix_apply(sg, rb, [&](bf &y) { y = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v[e]) >> 16)); ++e; });
            a_split<MR>(sg, x, (size_t)ldx, 0, Mst, c0 + i * 16, ln, x0, x1, x2);
            if (i % 2 == 0) jm::joint_matrix_mad(sg, c1, x0, rb, cz);
            else jm::joint_matrix_mad(sg, c1, x0, rb, c1);
            jm::joint_matrix_mad(sg, c1, x1, rb, c1);
            jm::joint_matrix_mad(sg, c1, x2, rb, c1);
            if (i % 2 == 1) {
                const float d = half_f(sr[i / 2]);
                jm::joint_matrix_apply(sg, gsum, c1, [=](float &y, float &z) { y = sycl::fma(d, z, y); });
            }
        }
        jm::joint_matrix_store(sg, gsum, st.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)gi * MR * 16, 16, jm::layout::row_major);
        sycl::group_barrier(it.get_group());
        if (gi == 0) {
            for (int t = 0; t < MR && t < Mst; ++t) {
                float tot = 0.0f;
                for (int g = 0; g < ng; ++g) tot = tot + st[(size_t)g * MR * 16 + t * 16 + ln];
                Y[(size_t)t * ldy + r16 * 16 + ln] = tot;
            }
        }
    }
};
template <int MR, int G = 8>
inline sycl::event dgroupx(sycl::queue &q, const uint8_t *W, int rows, int cols, const float *x, int ldx, int Mst, float *Y, int ldy) {
    const int ng = cols / 32 / G;
    if (cols % (32 * G) || rows % 16) throw std::runtime_error("xd::dgroupx: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> zb(256, h);
        sycl::local_accessor<float, 1> st((size_t)ng * MR * 16, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)rows / 16 * ng * 16), sycl::range<1>((size_t)ng * 16)),
                       XDGroupX<MR, G>{W, cols, x, ldx, Mst, Y, ldy, zb, st});
    });
}
// XDGroupX with every input load issued at the start too: row e's 256 inputs of the group with two sub-group block
// reads (lane n gets columns c0 + 16 i + n, i = 0..15: the A operand's lane order), split step by step in registers.
template <int MR, int G, int GRF> struct XDGroupB {
    static_assert(G == 8, "XDGroupB: groups of 8 blocks (2 block reads of 128 inputs)");
    const uint8_t *W; int cols; const float *x; int ldx; int Mst; float *Y; int ldy;
    sycl::local_accessor<bf, 1> zb; sycl::local_accessor<float, 1> st;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>};
    }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<1> it) const {
        const auto sg = it.get_sub_group();
        const int gi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int r16 = (int)it.get_group(0), nb = cols / 32, ng = nb / G;
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, MR, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, MR, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        const uint8_t *w = W + ((size_t)r16 * nb + (size_t)gi * G) * TQ;
        sycl::vec<uint32_t, 4> r[2 * G];
        uint16_t sr[G];
#pragma unroll
        for (int i = 0; i < 2 * G; ++i) r[i] = *reinterpret_cast<const sycl::vec<uint32_t, 4> *>(w + (size_t)(i / 2) * TQ + (i & 1) * 256 + ln * 16);
#pragma unroll
        for (int i = 0; i < G; ++i) sr[i] = *reinterpret_cast<const uint16_t *>(w + (size_t)i * TQ + 512 + 2 * ln);
        const int c0 = gi * G * 32;
        sycl::vec<float, 8> xv[MR][2];
#pragma unroll
        for (int e = 0; e < MR; ++e) {
            if (e < Mst) {
#pragma unroll
                for (int h = 0; h < 2; ++h)
                    xv[e][h] = sg.load<8>(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                        const_cast<float *>(x + (size_t)e * ldx + c0 + 128 * h)));
            } else {
                xv[e][0] = sycl::vec<float, 8>(0.0f);
                xv[e][1] = sycl::vec<float, 8>(0.0f);
            }
        }
        {
            const int lid = (int)it.get_local_linear_id();
            if (lid < 128) reinterpret_cast<uint32_t *>(&zb[0])[lid] = 0u;
            sycl::group_barrier(it.get_group());
        }
        C c1, gsum, cz;
        jm::joint_matrix_fill(sg, gsum, 0.0f);
        jm::joint_matrix_fill(sg, cz, 0.0f);
        B rb;
        A x0, x1, x2;
        jm::joint_matrix_load(sg, rb, zb.template get_multi_ptr<sycl::access::decorated::no>(), 32);
        jm::joint_matrix_load(sg, x0, zb.template get_multi_ptr<sycl::access::decorated::no>(), 16);
        jm::joint_matrix_load(sg, x1, zb.template get_multi_ptr<sycl::access::decorated::no>(), 16);
        jm::joint_matrix_load(sg, x2, zb.template get_multi_ptr<sycl::access::decorated::no>(), 16);
#pragma unroll
        for (int i = 0; i < 2 * G; ++i) {
            float v[16];
#pragma unroll
            for (int e = 0; e < 16; ++e) v[e] = (float)(int8_t)((r[i][e / 4] >> (8 * (e % 4))) & 0xff);
            int e = 0;
            jm::joint_matrix_apply(sg, rb, [&](bf &y) { y = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v[e]) >> 16)); ++e; });
            uint16_t p0[MR], p1[MR], p2[MR];
#pragma unroll
            for (int t = 0; t < MR; ++t) split3(xv[t][i / 8][i % 8], p0[t], p1[t], p2[t]);
            int e0 = 0, e1 = 0, e2 = 0;
            jm::joint_matrix_apply(sg, x0, [&](bf &y) { y = sycl::bit_cast<bf>(p0[e0]); ++e0; });
            jm::joint_matrix_apply(sg, x1, [&](bf &y) { y = sycl::bit_cast<bf>(p1[e1]); ++e1; });
            jm::joint_matrix_apply(sg, x2, [&](bf &y) { y = sycl::bit_cast<bf>(p2[e2]); ++e2; });
            if (i % 2 == 0) jm::joint_matrix_mad(sg, c1, x0, rb, cz);
            else jm::joint_matrix_mad(sg, c1, x0, rb, c1);
            jm::joint_matrix_mad(sg, c1, x1, rb, c1);
            jm::joint_matrix_mad(sg, c1, x2, rb, c1);
            if (i % 2 == 1) {
                const float d = half_f(sr[i / 2]);
                jm::joint_matrix_apply(sg, gsum, c1, [=](float &y, float &z) { y = sycl::fma(d, z, y); });
            }
        }
        jm::joint_matrix_store(sg, gsum, st.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)gi * MR * 16, 16, jm::layout::row_major);
        sycl::group_barrier(it.get_group());
        if (gi == 0) {
            for (int t = 0; t < MR && t < Mst; ++t) {
                float tot = 0.0f;
                for (int g = 0; g < ng; ++g) tot = tot + st[(size_t)g * MR * 16 + t * 16 + ln];
                Y[(size_t)t * ldy + r16 * 16 + ln] = tot;
            }
        }
    }
};
template <int MR, int GRF = 128>
inline sycl::event dgroupb(sycl::queue &q, const uint8_t *W, int rows, int cols, const float *x, int ldx, int Mst, float *Y, int ldy) {
    constexpr int G = 8;
    const int ng = cols / 32 / G;
    if (cols % (32 * G) || rows % 16) throw std::runtime_error("xd::dgroupb: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> zb(256, h);
        sycl::local_accessor<float, 1> st((size_t)ng * MR * 16, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)rows / 16 * ng * 16), sycl::range<1>((size_t)ng * 16)),
                       XDGroupB<MR, G, GRF>{W, cols, x, ldx, Mst, Y, ldy, zb, st});
    });
}
// Layout "Q8G" (the same bytes): [block of 16 rows][group of 8 blocks (256 inputs)][4352 bytes: block j's codes,
// row n's 32 at 512 j + 32 n; then row n's 8 half scales at 4096 + 16 n]. cols % 256 == 0.
constexpr int TG = 4352;
inline void repack_q8g(sycl::queue &q, const uint8_t *src, size_t rb, int rows, int cols, uint8_t *dst) {
    if (rows % 16 || cols % 256 || rb * 32 != (size_t)cols * 34) throw std::runtime_error("xd::repack_q8g: shapes");
    const int ng = cols / 256;
    q.parallel_for(sycl::range<2>((size_t)(rows / 16) * ng, 16), [=](sycl::item<2> it) {
        const int u = (int)it[0], n = (int)it[1], r16 = u / ng, g = u % ng;
        const uint8_t *row = src + (size_t)(r16 * 16 + n) * rb;
        uint8_t *o = dst + (size_t)u * TG;
        for (int j = 0; j < 8; ++j)
            for (int i = 0; i < 32; ++i) o[512 * j + 32 * n + i] = row[(g * 8 + j) * 32 + i];
        for (int j = 0; j < 8; ++j) {
            o[4096 + 16 * n + 2 * j] = row[cols + 2 * (g * 8 + j)];
            o[4096 + 16 * n + 2 * j + 1] = row[cols + 2 * (g * 8 + j) + 1];
        }
    }).wait();
}
// The steps of 1-8 tokens on Q8G: XDGroupB's arithmetic and input reads, the codes in 8 loads of 32 bytes and the
// scales in one of 16 per lane, the zero tile read from card memory (z: 512 zero bytes), no barrier before the sums.
template <int MR, int GRF, int ABL = 0, int DEC = 0, bool XP = false> struct XDGroupC { // XP: inputs from the parts P (x = P, ldx = cols, part stride pp); // ABL (measurement only, wrong values): 1 loads only, 2 no DPAS
    const uint8_t *W; int cols; const float *x; int ldx; int Mst; float *Y; int ldy; const bf *z;
    sycl::local_accessor<float, 1> st;
    size_t pp = 0;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>};
    }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<1> it) const { run(it, (int)it.get_group(0)); }
    void run(sycl::nd_item<1> it, int r16) const {
        const auto sg = it.get_sub_group();
        const int gi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int ng = cols / 256;
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, MR, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, MR, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        const uint8_t *w = W + ((size_t)r16 * ng + gi) * TG;
        sycl::vec<uint32_t, 8> r[8];
#pragma unroll
        for (int j = 0; j < 8; ++j) r[j] = *reinterpret_cast<const sycl::vec<uint32_t, 8> *>(w + 512 * j + 32 * ln);
        const sycl::vec<uint32_t, 4> sv = *reinterpret_cast<const sycl::vec<uint32_t, 4> *>(w + 4096 + 16 * ln);
        const int c0 = gi * 256;
        sycl::vec<float, 8> xv[XP ? 1 : MR][2];
#pragma unroll
        for (int e = 0; e < (XP ? 0 : MR); ++e) {
            if (e < Mst) {
#pragma unroll
                for (int h = 0; h < 2; ++h)
                    xv[e][h] = sg.load<8>(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                        const_cast<float *>(x + (size_t)e * ldx + c0 + 128 * h)));
            } else {
                xv[e][0] = sycl::vec<float, 8>(0.0f);
                xv[e][1] = sycl::vec<float, 8>(0.0f);
            }
        }
        if constexpr (ABL == 1) { // the loads alone: fold every word so none is dropped
            uint32_t acc = sv[0] ^ sv[1] ^ sv[2] ^ sv[3];
#pragma unroll
            for (int j = 0; j < 8; ++j)
#pragma unroll
                for (int q = 0; q < 8; ++q) acc ^= r[j][q];
            float fa = 0.0f;
#pragma unroll
            for (int e = 0; e < MR; ++e)
#pragma unroll
                for (int q = 0; q < 8; ++q) fa += xv[e][0][q] + xv[e][1][q];
            st[(size_t)gi * MR * 16 + ln] = (float)acc + fa;
            sycl::group_barrier(it.get_group());
            if (gi == 0) Y[(size_t)r16 * 16 + ln] = st[ln];
            return;
        }
        auto gz = sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(const_cast<bf *>(z));
        C c1, gsum, cz;
        jm::joint_matrix_fill(sg, gsum, 0.0f);
        jm::joint_matrix_fill(sg, cz, 0.0f);
        B rb;
        A x0, x1, x2;
        jm::joint_matrix_load(sg, rb, gz, 32);
        jm::joint_matrix_load(sg, x0, gz, 16);
        jm::joint_matrix_load(sg, x1, gz, 16);
        jm::joint_matrix_load(sg, x2, gz, 16);
#pragma unroll
        for (int i = 0; i < 16; ++i) {
            float v[16];
#pragma unroll
            for (int e = 0; e < 16; ++e) v[e] = 0.0f;
            int e = 0;
            if constexpr (DEC == 4) { // byte view, float, the card's own float -> bf16 conversion (exact: small integers)
                const int o4 = (i & 1) * 4;
                const sycl::vec<uint32_t, 4> h4(r[i / 2][o4], r[i / 2][o4 + 1], r[i / 2][o4 + 2], r[i / 2][o4 + 3]);
                const sycl::vec<int8_t, 16> b8 = sycl::bit_cast<sycl::vec<int8_t, 16>>(h4);
#ifdef __SYCL_DEVICE_ONLY__
                jm::joint_matrix_apply(sg, rb, [&](bf &y) { y = sycl::bit_cast<bf>((uint16_t)__spirv_ConvertFToBF16INTEL((float)b8[e])); ++e; });
#endif
            } else if constexpr (DEC == 2) { // byte view, word, float, top half
                const int o4 = (i & 1) * 4;
                const sycl::vec<uint32_t, 4> h4(r[i / 2][o4], r[i / 2][o4 + 1], r[i / 2][o4 + 2], r[i / 2][o4 + 3]);
                const sycl::vec<int8_t, 16> b8 = sycl::bit_cast<sycl::vec<int8_t, 16>>(h4);
                jm::joint_matrix_apply(sg, rb, [&](bf &y) { y = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>((float)(int16_t)b8[e]) >> 16)); ++e; });
            } else if constexpr (DEC == 3) { // magic number: 2^23 + 128 + q exactly, minus 2^23 + 128
                const int o4 = (i & 1) * 4;
                jm::joint_matrix_apply(sg, rb, [&](bf &y) {
                    const uint32_t u = ((r[i / 2][o4 + e / 4] >> (8 * (e % 4))) & 0xffu) ^ 0x80u;
                    const float f = sycl::bit_cast<float>(0x4B000000u | u) - 8388736.0f;
                    y = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(f) >> 16));
                    ++e;
                });
            } else if constexpr (DEC == 1) { // byte view, float, bf16 by conversion (exact: small integers)
                const int o4 = (i & 1) * 4;
                const sycl::vec<uint32_t, 4> h4(r[i / 2][o4], r[i / 2][o4 + 1], r[i / 2][o4 + 2], r[i / 2][o4 + 3]);
                const sycl::vec<int8_t, 16> b8 = sycl::bit_cast<sycl::vec<int8_t, 16>>(h4);
                jm::joint_matrix_apply(sg, rb, [&](bf &y) { y = bf((float)b8[e]); ++e; });
            } else {
#pragma unroll
                for (int k = 0; k < 16; ++k) v[k] = (float)(int8_t)((r[i / 2][(i & 1) * 4 + k / 4] >> (8 * (k % 4))) & 0xff);
                jm::joint_matrix_apply(sg, rb, [&](bf &y) { y = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v[e]) >> 16)); ++e; });
            }
            if constexpr (XP) {
                const bf *pk = reinterpret_cast<const bf *>(x) + c0 + i * 16;
                auto gpp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
                jm::joint_matrix_load(sg, x0, gpp(pk), ldx);
                jm::joint_matrix_load(sg, x1, gpp(pk + pp), ldx);
                jm::joint_matrix_load(sg, x2, gpp(pk + 2 * pp), ldx);
            } else {
                uint16_t p0[MR], p1[MR], p2[MR];
#pragma unroll
                for (int t = 0; t < MR; ++t) split3(xv[t][i / 8][i % 8], p0[t], p1[t], p2[t]);
                int e0 = 0, e1 = 0, e2 = 0;
                jm::joint_matrix_apply(sg, x0, [&](bf &y) { y = sycl::bit_cast<bf>(p0[e0]); ++e0; });
                jm::joint_matrix_apply(sg, x1, [&](bf &y) { y = sycl::bit_cast<bf>(p1[e1]); ++e1; });
                jm::joint_matrix_apply(sg, x2, [&](bf &y) { y = sycl::bit_cast<bf>(p2[e2]); ++e2; });
            }
            if constexpr (ABL == 2) {
                float acc = 0.0f;
                jm::joint_matrix_apply(sg, x0, [&](bf &y) { acc += (float)y; });
                jm::joint_matrix_apply(sg, x2, [&](bf &y) { acc += (float)y; });
                jm::joint_matrix_apply(sg, rb, [&](bf &y) { acc += (float)y; });
                jm::joint_matrix_apply(sg, gsum, [&](float &y) { y += acc; });
            } else {
                if (i % 2 == 0) jm::joint_matrix_mad(sg, c1, x0, rb, cz);
                else jm::joint_matrix_mad(sg, c1, x0, rb, c1);
                jm::joint_matrix_mad(sg, c1, x1, rb, c1);
                jm::joint_matrix_mad(sg, c1, x2, rb, c1);
            }
            if (i % 2 == 1) {
                const float d = half_f((uint16_t)(sv[i / 4] >> (16 * ((i / 2) & 1))));
                jm::joint_matrix_apply(sg, gsum, c1, [=](float &y, float &zz) { y = sycl::fma(d, zz, y); });
            }
        }
        jm::joint_matrix_store(sg, gsum, st.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)gi * MR * 16, 16, jm::layout::row_major);
        sycl::group_barrier(it.get_group());
        if (gi == 0) {
            for (int t = 0; t < MR && t < Mst; ++t) {
                float tot = 0.0f;
                for (int g = 0; g < ng; ++g) tot = tot + st[(size_t)g * MR * 16 + t * 16 + ln];
                Y[(size_t)t * ldy + r16 * 16 + ln] = tot;
            }
        }
    }
};
template <int MR, int GRF = 128, int ABL = 0, int DEC = 0>
inline sycl::event dgroupc(sycl::queue &q, const uint8_t *W, int rows, int cols, const float *x, int ldx, int Mst, float *Y, int ldy, const bf *z) {
    const int ng = cols / 256;
    if (cols % 256 || rows % 16) throw std::runtime_error("xd::dgroupc: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> st((size_t)ng * MR * 16, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)rows / 16 * ng * 16), sycl::range<1>((size_t)ng * 16)),
                       XDGroupC<MR, GRF, ABL, DEC>{W, cols, x, ldx, Mst, Y, ldy, z, st});
    });
}
// XDGroupC in phases: a work-group = one sub-group per group (ng), NP consecutive row blocks of 16 one after the
// other; the next block's codes are requested right after the current block's first step (so its data come behind
// the current block's in the memory queues and the decode of one block overlaps the transfer of the next). The inputs
// are read once (the same group for every block). Group sums of every block to local memory, one fold at the end.
template <int MR, int GRF, int NP> struct XDGroupP {
    const uint8_t *W; int cols; const float *x; int ldx; int Mst; float *Y; int ldy; const bf *z;
    sycl::local_accessor<float, 1> st;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>};
    }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<1> it) const {
        const auto sg = it.get_sub_group();
        const int gi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int rb0 = (int)it.get_group(0) * NP, ng = cols / 256;
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, MR, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, MR, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        using V8 = sycl::vec<uint32_t, 8>;
        using V4 = sycl::vec<uint32_t, 4>;
        auto load = [&](int r16, V8 *r, V4 &sv) {
            const uint8_t *w = W + ((size_t)r16 * ng + gi) * TG;
#pragma unroll
            for (int j = 0; j < 8; ++j) r[j] = *reinterpret_cast<const V8 *>(w + 512 * j + 32 * ln);
            sv = *reinterpret_cast<const V4 *>(w + 4096 + 16 * ln);
        };
        V8 ra[8], rbuf[8];
        V4 sa, sb;
        load(rb0, ra, sa);
        const int c0 = gi * 256;
        sycl::vec<float, 8> xv[MR][2];
#pragma unroll
        for (int e = 0; e < MR; ++e) {
            if (e < Mst) {
#pragma unroll
                for (int h = 0; h < 2; ++h)
                    xv[e][h] = sg.load<8>(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                        const_cast<float *>(x + (size_t)e * ldx + c0 + 128 * h)));
            } else {
                xv[e][0] = sycl::vec<float, 8>(0.0f);
                xv[e][1] = sycl::vec<float, 8>(0.0f);
            }
        }
        // the inputs in parts, once (16 steps x MR rows)
        uint16_t p0[16][MR], p1[16][MR], p2[16][MR];
#pragma unroll
        for (int i = 0; i < 16; ++i)
#pragma unroll
            for (int t = 0; t < MR; ++t) split3(xv[t][i / 8][i % 8], p0[i][t], p1[i][t], p2[i][t]);
        auto gz = sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(const_cast<bf *>(z));
        C c1, gsum, cz;
        jm::joint_matrix_fill(sg, cz, 0.0f);
        B rb;
        A x0, x1, x2;
        jm::joint_matrix_load(sg, rb, gz, 32);
        jm::joint_matrix_load(sg, x0, gz, 16);
        jm::joint_matrix_load(sg, x1, gz, 16);
        jm::joint_matrix_load(sg, x2, gz, 16);
        auto block = [&](int p, V8 *r, V4 &sv, V8 *rn, V4 &svn) {
            jm::joint_matrix_fill(sg, gsum, 0.0f);
#pragma unroll
            for (int i = 0; i < 16; ++i) {
                float v[16];
#pragma unroll
                for (int k = 0; k < 16; ++k) v[k] = (float)(int8_t)((r[i / 2][(i & 1) * 4 + k / 4] >> (8 * (k % 4))) & 0xff);
                if (i == 0 && p + 1 < NP) load(rb0 + p + 1, rn, svn);
                int e = 0;
                jm::joint_matrix_apply(sg, rb, [&](bf &y) { y = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v[e]) >> 16)); ++e; });
                int e0 = 0, e1 = 0, e2 = 0;
                jm::joint_matrix_apply(sg, x0, [&](bf &y) { y = sycl::bit_cast<bf>(p0[i][e0]); ++e0; });
                jm::joint_matrix_apply(sg, x1, [&](bf &y) { y = sycl::bit_cast<bf>(p1[i][e1]); ++e1; });
                jm::joint_matrix_apply(sg, x2, [&](bf &y) { y = sycl::bit_cast<bf>(p2[i][e2]); ++e2; });
                if (i % 2 == 0) jm::joint_matrix_mad(sg, c1, x0, rb, cz);
                else jm::joint_matrix_mad(sg, c1, x0, rb, c1);
                jm::joint_matrix_mad(sg, c1, x1, rb, c1);
                jm::joint_matrix_mad(sg, c1, x2, rb, c1);
                if (i % 2 == 1) {
                    const float d = half_f((uint16_t)(sv[i / 4] >> (16 * ((i / 2) & 1))));
                    jm::joint_matrix_apply(sg, gsum, c1, [=](float &y, float &zz) { y = sycl::fma(d, zz, y); });
                }
            }
            jm::joint_matrix_store(sg, gsum, st.template get_multi_ptr<sycl::access::decorated::no>() + ((size_t)p * ng + gi) * MR * 16, 16,
                                   jm::layout::row_major);
        };
#pragma unroll
        for (int p = 0; p < NP; ++p) {
            if (p % 2 == 0) block(p, ra, sa, rbuf, sb);
            else block(p, rbuf, sb, ra, sa);
        }
        sycl::group_barrier(it.get_group());
        for (int id = gi; id < NP * MR; id += ng) { // sub-group gi folds (block, row) pairs
            const int p = id / MR, t = id % MR;
            if (t >= Mst) continue;
            float tot = 0.0f;
            for (int g = 0; g < ng; ++g) tot = tot + st[((size_t)p * ng + g) * MR * 16 + t * 16 + ln];
            Y[(size_t)t * ldy + (rb0 + p) * 16 + ln] = tot;
        }
    }
};
template <int MR, int GRF = 256, int NP = 4>
inline sycl::event dgroupp(sycl::queue &q, const uint8_t *W, int rows, int cols, const float *x, int ldx, int Mst, float *Y, int ldy, const bf *z) {
    const int ng = cols / 256;
    if (cols % 256 || rows % (16 * NP)) throw std::runtime_error("xd::dgroupp: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> st((size_t)NP * ng * MR * 16, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)rows / 16 / NP * ng * 16), sycl::range<1>((size_t)ng * 16)),
                       XDGroupP<MR, GRF, NP>{W, cols, x, ldx, Mst, Y, ldy, z, st});
    });
}
// XDGroupC for groups of G = 4 or 8 blocks on the Q8G layout (a G = 4 group is half of a Q8G group): one sub-group
// per (16 rows, group), codes and scales loaded first, the zero tile from card memory.
template <int MR, int GRF, int G> struct XDGroupH {
    static_assert(G == 4 || G == 8, "XDGroupH: G");
    const uint8_t *W; int cols; const float *x; int ldx; int Mst; float *Y; int ldy; const bf *z;
    sycl::local_accessor<float, 1> st;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>};
    }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<1> it) const {
        const auto sg = it.get_sub_group();
        const int gi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int r16 = (int)it.get_group(0), ng = cols / (32 * G), h8 = (gi * G) % 8;
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, MR, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, MR, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        const uint8_t *w = W + ((size_t)r16 * (cols / 256) + (gi * G) / 8) * TG;
        sycl::vec<uint32_t, 8> r[G];
#pragma unroll
        for (int j = 0; j < G; ++j) r[j] = *reinterpret_cast<const sycl::vec<uint32_t, 8> *>(w + 512 * (h8 + j) + 32 * ln);
        sycl::vec<uint32_t, G / 2> sv = *reinterpret_cast<const sycl::vec<uint32_t, G / 2> *>(w + 4096 + 16 * ln + 2 * h8);
        const int c0 = gi * G * 32;
        constexpr int NX = G * 32 / 128; // block reads of 128 inputs per row
        sycl::vec<float, 8> xv[MR][NX];
#pragma unroll
        for (int e = 0; e < MR; ++e) {
#pragma unroll
            for (int hh = 0; hh < NX; ++hh)
                xv[e][hh] = e < Mst ? sg.load<8>(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                                          const_cast<float *>(x + (size_t)e * ldx + c0 + 128 * hh)))
                                    : sycl::vec<float, 8>(0.0f);
        }
        auto gz = sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(const_cast<bf *>(z));
        C c1, gsum, cz;
        jm::joint_matrix_fill(sg, gsum, 0.0f);
        jm::joint_matrix_fill(sg, cz, 0.0f);
        B rb;
        A x0, x1, x2;
        jm::joint_matrix_load(sg, rb, gz, 32);
        jm::joint_matrix_load(sg, x0, gz, 16);
        jm::joint_matrix_load(sg, x1, gz, 16);
        jm::joint_matrix_load(sg, x2, gz, 16);
#pragma unroll
        for (int i = 0; i < 2 * G; ++i) {
            float v[16];
#pragma unroll
            for (int k = 0; k < 16; ++k) v[k] = (float)(int8_t)((r[i / 2][(i & 1) * 4 + k / 4] >> (8 * (k % 4))) & 0xff);
            int e = 0;
            jm::joint_matrix_apply(sg, rb, [&](bf &y) { y = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v[e]) >> 16)); ++e; });
            uint16_t p0[MR], p1[MR], p2[MR];
#pragma unroll
            for (int t = 0; t < MR; ++t) split3(xv[t][i / 8][i % 8], p0[t], p1[t], p2[t]);
            int e0 = 0, e1 = 0, e2 = 0;
            jm::joint_matrix_apply(sg, x0, [&](bf &y) { y = sycl::bit_cast<bf>(p0[e0]); ++e0; });
            jm::joint_matrix_apply(sg, x1, [&](bf &y) { y = sycl::bit_cast<bf>(p1[e1]); ++e1; });
            jm::joint_matrix_apply(sg, x2, [&](bf &y) { y = sycl::bit_cast<bf>(p2[e2]); ++e2; });
            if (i % 2 == 0) jm::joint_matrix_mad(sg, c1, x0, rb, cz);
            else jm::joint_matrix_mad(sg, c1, x0, rb, c1);
            jm::joint_matrix_mad(sg, c1, x1, rb, c1);
            jm::joint_matrix_mad(sg, c1, x2, rb, c1);
            if (i % 2 == 1) {
                const float d = half_f((uint16_t)(sv[i / 4] >> (16 * ((i / 2) & 1))));
                jm::joint_matrix_apply(sg, gsum, c1, [=](float &y, float &zz) { y = sycl::fma(d, zz, y); });
            }
        }
        jm::joint_matrix_store(sg, gsum, st.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)gi * MR * 16, 16, jm::layout::row_major);
        sycl::group_barrier(it.get_group());
        if (gi == 0) {
            for (int t = 0; t < MR && t < Mst; ++t) {
                float tot = 0.0f;
                for (int g = 0; g < ng; ++g) tot = tot + st[(size_t)g * MR * 16 + t * 16 + ln];
                Y[(size_t)t * ldy + r16 * 16 + ln] = tot;
            }
        }
    }
};
template <int MR, int GRF = 128, int G = 4>
inline sycl::event dgrouph(sycl::queue &q, const uint8_t *W, int rows, int cols, const float *x, int ldx, int Mst, float *Y, int ldy, const bf *z) {
    const int ng = cols / (32 * G);
    if (cols % 256 || rows % 16) throw std::runtime_error("xd::dgrouph: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> st((size_t)ng * MR * 16, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)rows / 16 * ng * 16), sycl::range<1>((size_t)ng * 16)),
                       XDGroupH<MR, GRF, G>{W, cols, x, ldx, Mst, Y, ldy, z, st});
    });
}
// Several matrices with the same number of inputs in one launch (one token's attention inputs): XDGroupC per job,
// work-group w -> job by the jobs' first row blocks.
constexpr int XJ_MAX = 8;
struct XJob { const uint8_t *W; const float *x; float *y; int rb0, nrb; };
struct XJobs { XJob j[XJ_MAX]; int nj = 0, nrb = 0; };
inline void xjob_add(XJobs &m, const uint8_t *W, int rows, const float *x, float *y) {
    if (m.nj >= XJ_MAX || rows % 16) throw std::runtime_error("xd::xjob_add");
    m.j[m.nj++] = XJob{W, x, y, m.nrb, rows / 16};
    m.nrb += rows / 16;
}
template <int MR, int GRF, bool XP = false> struct XDGroupJ {
    XJobs jb; int cols; int Mst; int ldx; int ldy; const bf *z; size_t pp;
    sycl::local_accessor<float, 1> st;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>};
    }
    int ahead = 0; // > 0: prefetch (to the cache) the codes of work-group w + ahead, the likely next one on this slot
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<1> it) const {
        const int w = (int)it.get_group(0);
        int jn = 0;
#pragma unroll
        for (int k = 1; k < XJ_MAX; ++k) if (k < jb.nj && w >= jb.j[k].rb0) jn = k;
        if (ahead > 0 && w + ahead < jb.nrb) {
            const int w2 = w + ahead;
            int j2 = 0;
#pragma unroll
            for (int k = 1; k < XJ_MAX; ++k) if (k < jb.nj && w2 >= jb.j[k].rb0) j2 = k;
            const auto sg = it.get_sub_group();
            const int gi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
            const uint8_t *p2 = jb.j[j2].W + ((size_t)(w2 - jb.j[j2].rb0) * (cols / 256) + gi) * TG;
            namespace sx = sycl::ext::oneapi::experimental;
            for (int o = ln * 64; o < TG; o += 16 * 64) sx::prefetch((void *)(p2 + o), 64, sx::properties{sx::prefetch_hint_L3});
        }
        const XJob &J = jb.j[jn];
        XDGroupC<MR, GRF, 0, 0, XP>{J.W, cols, J.x, ldx, Mst, J.y, ldy, z, st, pp}.run(it, w - J.rb0);
    }
};
template <int MR, int GRF = 128, bool XP = false>
inline sycl::event dgroupj(sycl::queue &q, const XJobs &jb, int cols, const float *, int ldx, int Mst, int ldy, const bf *z, size_t pp = 0, int ahead = 0) {
    const int ng = cols / 256;
    if (cols % 256) throw std::runtime_error("xd::dgroupj: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> st((size_t)ng * MR * 16, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)jb.nrb * ng * 16), sycl::range<1>((size_t)ng * 16)),
                       XDGroupJ<MR, GRF, XP>{jb, cols, Mst, ldx, ldy, z, pp, st, ahead});
    });
}
} // namespace ink::xd
