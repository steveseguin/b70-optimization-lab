#pragma once
// Q8_0 products for steps of 1-8 tokens on the matrix engines, written in ESIMD so that turning the int8 codes into the
// bf16 weight operand takes two instructions per 16 codes (a byte-to-float move and the card's float-to-bf16 move)
// instead of the ~7 the compiler emits through joint_matrix_apply. Same arithmetic as XDGroupC (xmx_dense.hpp): per
// block of 32 inputs one DPAS chain from 0 (parts 1, 2, 3 per step of 16, both steps), group sum = fma(scale, block
// sum, group sum) over the 8 blocks of a group (256 inputs), the groups added in order into a total from 0.
// The inputs come as their three bf16 parts (xd::split's layout: part p at P + p pp, token t at + t ldx).
#include "xmx_dense.hpp"
#include <sycl/ext/intel/esimd.hpp>
#include <sycl/ext/intel/experimental/esimd/math.hpp>

namespace ink::xd {
namespace es = sycl::ext::intel::esimd;
namespace esx = sycl::ext::intel::experimental::esimd;
namespace ex = sycl::ext::intel::esimd::xmx;

// Layout "Q8E" (the same bytes): [block of 16 rows][group of 8 blocks (256 inputs)][4352 bytes: block j's codes, the
// code of input k and row n at 512 j + 64 (k / 4) + 4 n + k % 4 (each 64 bytes: 4 inputs of the 16 rows, one dword per
// row); block j's 16 row scales (halves) at 4096 + 32 j + 2 n]. A sub-group block read of 4 dwords at 512 j + 256 s
// gives lane n row n's 16 codes of step s (as Q8T's per-lane load); in ESIMD input k's codes are one byte region.
inline void repack_q8e(sycl::queue &q, const uint8_t *src, size_t rb, int rows, int cols, uint8_t *dst) {
    if (rows % 16 || cols % 256 || rb * 32 != (size_t)cols * 34) throw std::runtime_error("xd::repack_q8e: shapes");
    const int ng = cols / 256;
    q.parallel_for(sycl::range<2>((size_t)(rows / 16) * ng, 16), [=](sycl::item<2> it) {
        const int u = (int)it[0], n = (int)it[1], r16 = u / ng, g = u % ng;
        const uint8_t *row = src + (size_t)(r16 * 16 + n) * rb;
        uint8_t *o = dst + (size_t)u * TG;
        for (int j = 0; j < 8; ++j)
            for (int i = 0; i < 32; ++i) o[512 * j + 64 * (i / 4) + 4 * n + i % 4] = row[(g * 8 + j) * 32 + i];
        for (int j = 0; j < 8; ++j) {
            o[4096 + 32 * j + 2 * n] = row[cols + 2 * (g * 8 + j)];
            o[4096 + 32 * j + 2 * n + 1] = row[cols + 2 * (g * 8 + j) + 1];
        }
    }).wait();
}

template <int MR> struct XDGroupE {
    const uint8_t *W; int cols; const uint16_t *P; int ldx; size_t pp; int Mst; float *Y; int ldy;
    void operator()(sycl::nd_item<1> it) const SYCL_ESIMD_KERNEL {
        constexpr int NGM = 12; // groups per row: up to 3,072 inputs
        es::slm_init<NGM * MR * 16 * 4>();
        const int ng = cols / 256, gi = (int)it.get_local_id(0), r16 = (int)it.get_group(0);
        const uint8_t *w = W + ((size_t)r16 * ng + gi) * TG;
        constexpr auto al = es::properties{es::alignment<16>};
        es::simd<uint32_t, 1024> cw;
#pragma unroll
        for (int j = 0; j < 8; ++j)
            cw.template select<128, 1>(128 * j) = es::block_load<uint32_t, 128>(reinterpret_cast<const uint32_t *>(w + 512 * j), al);
        es::simd<uint16_t, 128> sh = es::block_load<uint16_t, 128>(reinterpret_cast<const uint16_t *>(w + 4096), al);
        const int c0 = gi * 256;
        es::simd<uint16_t, MR * 256> pa[3];
#pragma unroll
        for (int p = 0; p < 3; ++p)
#pragma unroll
            for (int t = 0; t < MR; ++t)
                pa[p].template select<256, 1>(256 * t) = es::block_load<uint16_t, 256>(P + p * pp + (size_t)t * ldx + c0, al);
        auto cb = cw.template bit_cast_view<int8_t>();
        es::simd<float, MR * 16> g = 0.0f;
        const es::simd<float, MR * 16> zero = 0.0f;
#pragma unroll
        for (int j = 0; j < 8; ++j) {
            es::simd<float, MR * 16> c;
#pragma unroll
            for (int s = 0; s < 2; ++s) {
                es::simd<sycl::ext::oneapi::bfloat16, 256> B;
#pragma unroll
                for (int k = 0; k < 16; ++k) {
                    const es::simd<float, 16> f = cb.template select<16, 4>(512 * j + 64 * (4 * s + k / 4) + k % 4);
                    B.template select<16, 2>((k / 2) * 32 + (k % 2)) = f;
                }
                es::simd<uint16_t, MR * 16> a[3];
#pragma unroll
                for (int p = 0; p < 3; ++p)
#pragma unroll
                    for (int t = 0; t < MR; ++t) a[p].template select<16, 1>(16 * t) = pa[p].template select<16, 1>(256 * t + 32 * j + 16 * s);
#pragma unroll
                for (int p = 0; p < 3; ++p) {
                    const es::simd<sycl::ext::oneapi::bfloat16, MR * 16> ab = a[p].template bit_cast_view<sycl::ext::oneapi::bfloat16>();
                    c = ex::dpas<8, MR, float, float>(s == 0 && p == 0 ? zero : c, B, ab);
                }
            }
            es::simd<uint16_t, 16> s16 = sh.template select<16, 1>(16 * j);
            const es::simd<float, 16> dj = es::simd<sycl::half, 16>(s16.template bit_cast_view<sycl::half>());
#pragma unroll
            for (int t = 0; t < MR; ++t)
                g.template select<16, 1>(16 * t) = esx::fma(dj, es::simd<float, 16>(c.template select<16, 1>(16 * t)), es::simd<float, 16>(g.template select<16, 1>(16 * t)));
        }
        es::slm_block_store<float, MR * 16>((uint32_t)(gi * MR * 16 * 4), g);
        es::barrier();
        if (gi == 0) {
            es::simd<float, MR * 16> tot = 0.0f;
            for (int q = 0; q < ng; ++q) tot = tot + es::slm_block_load<float, MR * 16>((uint32_t)(q * MR * 16 * 4));
#pragma unroll
            for (int t = 0; t < MR; ++t)
                if (t < Mst) es::block_store<float, 16>(Y + (size_t)t * ldy + r16 * 16, tot.template select<16, 1>(16 * t));
        }
    }
};
template <int MR>
inline sycl::event dgroupe(sycl::queue &q, const uint8_t *W, int rows, int cols, const uint16_t *P, int ldx, size_t pp, int Mst, float *Y, int ldy) {
    const int ng = cols / 256;
    if (cols % 256 || rows % 16 || ng > 12) throw std::runtime_error("xd::dgroupe: shapes");
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)rows / 16 * ng), sycl::range<1>((size_t)ng)),
                          XDGroupE<MR>{W, cols, P, ldx, pp, Mst, Y, ldy});
}

// Parts layout "PE" for steps of MP <= 8 tokens: [part][group][block j][step s][token t < MP][16 values]; part stride
// cols x MP. Rows t >= M are zero.
template <int MP> inline sycl::event splite(sycl::queue &q, const float *x, int ldx, int M, int cols, uint16_t *Pe) {
    const size_t ps = (size_t)cols * MP;
    return q.parallel_for(sycl::range<2>(MP, (size_t)cols), [=](sycl::id<2> i) {
        const int t = (int)i[0], k = (int)i[1];
        const int g = k / 256, j = (k % 256) / 32, s = (k % 32) / 16, e = k % 16;
        const float v = t < M ? x[(size_t)t * ldx + k] : 0.0f;
        uint16_t a, b, c;
        split3(v, a, b, c);
        const size_t o = ((((size_t)g * 8 + j) * 2 + s) * MP + t) * 16 + e;
        Pe[o] = a; Pe[ps + o] = b; Pe[2 * ps + o] = c;
    });
}
// XDGroupE on PE parts: each block's parts loaded with it (3 loads of MR x 32 values), for 2-8 tokens
template <int MR, int GRF> struct XDGroupE2 {
    const uint8_t *W; int cols; const uint16_t *Pe; int Mst; float *Y; int ldy;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>};
    }
    void operator()(sycl::nd_item<1> it) const SYCL_ESIMD_KERNEL {
        constexpr int NGM = 12;
        es::slm_init<NGM * MR * 16 * 4>();
        const int ng = cols / 256, gi = (int)it.get_local_id(0), r16 = (int)it.get_group(0);
        const uint8_t *w = W + ((size_t)r16 * ng + gi) * TG;
        constexpr auto al = es::properties{es::alignment<16>};
        es::simd<uint32_t, 1024> cw;
#pragma unroll
        for (int j = 0; j < 8; ++j)
            cw.template select<128, 1>(128 * j) = es::block_load<uint32_t, 128>(reinterpret_cast<const uint32_t *>(w + 512 * j), al);
        es::simd<uint16_t, 128> sh = es::block_load<uint16_t, 128>(reinterpret_cast<const uint16_t *>(w + 4096), al);
        const size_t ps = (size_t)cols * MR;
        const uint16_t *pg = Pe + (size_t)gi * 8 * 2 * MR * 16;
        auto cb = cw.template bit_cast_view<int8_t>();
        es::simd<float, MR * 16> g = 0.0f;
        const es::simd<float, MR * 16> zero = 0.0f;
#pragma unroll
        for (int j = 0; j < 8; ++j) {
            es::simd<uint16_t, MR * 32> pa[3];
#pragma unroll
            for (int p = 0; p < 3; ++p) pa[p] = es::block_load<uint16_t, MR * 32>(pg + p * ps + (size_t)j * 2 * MR * 16, al);
            es::simd<float, MR * 16> c;
#pragma unroll
            for (int s = 0; s < 2; ++s) {
                es::simd<sycl::ext::oneapi::bfloat16, 256> B;
#pragma unroll
                for (int k = 0; k < 16; ++k) {
                    const es::simd<float, 16> f = cb.template select<16, 4>(512 * j + 64 * (4 * s + k / 4) + k % 4);
                    B.template select<16, 2>((k / 2) * 32 + (k % 2)) = f;
                }
#pragma unroll
                for (int p = 0; p < 3; ++p) {
                    es::simd<uint16_t, MR * 16> a = pa[p].template select<MR * 16, 1>(s * MR * 16);
                    const es::simd<sycl::ext::oneapi::bfloat16, MR * 16> ab = a.template bit_cast_view<sycl::ext::oneapi::bfloat16>();
                    c = ex::dpas<8, MR, float, float>(s == 0 && p == 0 ? zero : c, B, ab);
                }
            }
            es::simd<uint16_t, 16> s16 = sh.template select<16, 1>(16 * j);
            const es::simd<float, 16> dj = es::simd<sycl::half, 16>(s16.template bit_cast_view<sycl::half>());
#pragma unroll
            for (int t = 0; t < MR; ++t)
                g.template select<16, 1>(16 * t) = esx::fma(dj, es::simd<float, 16>(c.template select<16, 1>(16 * t)), es::simd<float, 16>(g.template select<16, 1>(16 * t)));
        }
        es::slm_block_store<float, MR * 16>((uint32_t)(gi * MR * 16 * 4), g);
        es::barrier();
        if (gi == 0) {
            es::simd<float, MR * 16> tot = 0.0f;
            for (int q = 0; q < ng; ++q) tot = tot + es::slm_block_load<float, MR * 16>((uint32_t)(q * MR * 16 * 4));
#pragma unroll
            for (int t = 0; t < MR; ++t)
                if (t < Mst) es::block_store<float, 16>(Y + (size_t)t * ldy + r16 * 16, tot.template select<16, 1>(16 * t));
        }
    }
};
template <int MR, int GRF = 128>
inline sycl::event dgroupe2(sycl::queue &q, const uint8_t *W, int rows, int cols, const uint16_t *Pe, int Mst, float *Y, int ldy) {
    const int ng = cols / 256;
    if (cols % 256 || rows % 16 || ng > 12) throw std::runtime_error("xd::dgroupe2: shapes");
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)rows / 16 * ng), sycl::range<1>((size_t)ng)),
                          XDGroupE2<MR, GRF>{W, cols, Pe, Mst, Y, ldy});
}

// Several matrices with the same input width in one launch (the attention inputs of a step): work-group w belongs to
// the job whose first row block rb0 <= w. Inputs as PE parts per job (MR rows), outputs y + t ldy + row.
constexpr int EJ_MAX = 8;
// lk = ldy | rows << 14 | bf16 << 28 (bf16: the weights are bf16 in the BFE layout, scale 1; rows % 8 == 0, the last
// block of 16 may hold 8)
struct EJob { const uint8_t *W; const uint16_t *P; float *y; int lk; int rb0; };
struct EJobs { EJob j[EJ_MAX]; int nj = 0, nrb = 0; };
inline void ejob_add(EJobs &m, const uint8_t *W, int rows, const uint16_t *P, float *y, int ldy, bool bf = false) {
    if (m.nj == EJ_MAX || rows % (bf ? 8 : 16) || ldy >= (1 << 14) || rows >= (1 << 14)) throw std::runtime_error("xd::ejob_add: too many jobs or rows");
    m.j[m.nj++] = EJob{W, P, y, ldy | rows << 14 | (bf ? 1 << 28 : 0), m.nrb};
    m.nrb += (rows + 15) / 16;
}
// Layout "BFE" of a bf16 matrix [rows][cols] (rows padded with zeros to rows_pad, a multiple of 16; cols % 256 == 0):
// [block of 16 rows][step of 16 inputs][512 bytes: dword kk n = (input 2 kk, row n) | (input 2 kk + 1, row n) << 16],
// i.e. each step is the DPAS weight operand as it sits in registers (and in XDense's local memory)
inline void repack_bfe(sycl::queue &q, const uint16_t *src, int rows, int cols, int rows_pad, uint16_t *dst) {
    if (rows_pad % 16 || rows_pad < rows || cols % 256) throw std::runtime_error("xd::repack_bfe: shapes");
    const int steps = cols / 16;
    q.parallel_for(sycl::range<2>((size_t)rows_pad, (size_t)cols), [=](sycl::id<2> i) {
        const int r = (int)i[0], k = (int)i[1];
        const size_t o = (((size_t)(r / 16) * steps + k / 16) * 8 + (k % 16) / 2) * 32 + (r % 16) * 2 + k % 2;
        dst[o] = r < rows ? src[(size_t)r * cols + k] : (uint16_t)0;
    }).wait();
}
// UP: all of the group's parts loaded at the start (MR 1; at MR 2 they spill), else each block's with it
// cm: the input width | the tokens to store << 16 (a separate int member made IGC 2026.1 crash: -11 in ocloc).
// XS (one token): the jobs' P are the fp32 inputs, split here with split3's expressions while the weights load
// Cache hints on the weight loads (study 2026-11-26; L1 streaming / uncached x L2 cached / uncached) do not help in the
// engine: with this kernel on, the expert kernels after it run ~2 % slower (a plain 16 MB read in bench_xe BENCH_FOLLOW
// 28.5 -> 30.0 us), and L1 streaming + L2 uncached fixes the bench's read but not the engine (writing 88.7 tok/s with
// no hints, 88.6 / 88.6 / 88.4 / 85.4 with the four hinted forms)
template <int MR, int GRF, bool UP, bool XS = false> struct XDGroupEJ {
    // (a split inside for 2-8 tokens, each block's MR x 32 inputs loaded and split before use, gave the same bits but
    // took 50.7 / 64.7 / 81.9 us at 2 / 4 / 8 tokens against 45.9 / 46.8 / 49.1 on parts; 2026-11-26)
    static_assert(!XS || (MR == 1 && UP), "XDGroupEJ: the split inside is for one token");
    EJobs jb; int cm;
    // split3 (bfsplit.hpp) of 16 inputs written out: bf_rn(f) = (u + 0x7fff + ((u >> 16) & 1)) >> 16
    static SYCL_ESIMD_FUNCTION void split16(es::simd<float, 16> x16, es::simd<uint32_t, 16> &a, es::simd<uint32_t, 16> &b, es::simd<uint32_t, 16> &c) {
        es::simd<uint32_t, 16> ux = x16.template bit_cast_view<uint32_t>();
        a = (ux + 0x7fffu + ((ux >> 16) & 1u)) >> 16;
        es::simd<uint32_t, 16> ah = a << 16;
        es::simd<float, 16> r1 = x16 - es::simd<float, 16>(ah.template bit_cast_view<float>());
        es::simd<uint32_t, 16> u1 = r1.template bit_cast_view<uint32_t>();
        b = (u1 + 0x7fffu + ((u1 >> 16) & 1u)) >> 16;
        es::simd<uint32_t, 16> bh = b << 16;
        es::simd<float, 16> r2 = r1 - es::simd<float, 16>(bh.template bit_cast_view<float>());
        es::simd<uint32_t, 16> u2 = r2.template bit_cast_view<uint32_t>();
        c = (u2 + 0x7fffu + ((u2 >> 16) & 1u)) >> 16;
    }
    // one group's sum g (MR x 16), BF: bf16 weights (BFE), else Q8E codes and scales; the two are separate code so
    // that neither carries the other's registers (mixing them in one loop cost the Q8 path ~10 %, 2026-11-26)
    // XS: xp = the group's 256 fp32 inputs
    template <bool BF> SYCL_ESIMD_FUNCTION es::simd<float, MR * 16> group(const uint8_t *wp, const uint16_t *pg, size_t ps, const float *xp) const {
        constexpr auto al = es::properties{es::alignment<16>};
        es::simd<uint32_t, (BF ? 16 : 1024)> cw;
        es::simd<uint16_t, (BF ? 16 : 128)> sh;
        if constexpr (!BF) {
#pragma unroll
            for (int j = 0; j < 8; ++j)
                cw.template select<128, 1>(128 * j) = es::block_load<uint32_t, 128>(reinterpret_cast<const uint32_t *>(wp + 512 * j), al);
            sh = es::block_load<uint16_t, 128>(reinterpret_cast<const uint16_t *>(wp + 4096), al);
        }
        es::simd<uint16_t, (UP && !XS ? 256 * MR : 16)> pall[3];
        es::simd<float, (XS ? 256 : 16)> xv;
        if constexpr (XS) { // the group's 256 inputs; their parts are made 16 at a time below, right before use
            xv.template select<128, 1>(0) = es::block_load<float, 128>(xp, al);
            xv.template select<128, 1>(128) = es::block_load<float, 128>(xp + 128, al);
        } else if constexpr (UP) {
#pragma unroll
            for (int p = 0; p < 3; ++p)
#pragma unroll
                for (int h = 0; h < MR; ++h) pall[p].template select<256, 1>(256 * h) = es::block_load<uint16_t, 256>(pg + p * ps + 256 * h, al);
        }
        auto cb = cw.template bit_cast_view<int8_t>();
        es::simd<float, MR * 16> g = 0.0f;
        const es::simd<float, MR * 16> zero = 0.0f;
#pragma unroll
        for (int j = 0; j < 8; ++j) {
            es::simd<uint16_t, MR * 32> pa[3];
            if constexpr (XS) {
#pragma unroll
                for (int s = 0; s < 2; ++s) {
                    es::simd<uint32_t, 16> a, b, c;
                    split16(xv.template select<16, 1>(32 * j + 16 * s), a, b, c);
                    pa[0].template select<16, 1>(16 * s) = a;
                    pa[1].template select<16, 1>(16 * s) = b;
                    pa[2].template select<16, 1>(16 * s) = c;
                }
            } else {
#pragma unroll
                for (int p = 0; p < 3; ++p) {
                    if constexpr (UP) pa[p] = pall[p].template select<MR * 32, 1>(j * MR * 32);
                    else pa[p] = es::block_load<uint16_t, MR * 32>(pg + p * ps + (size_t)j * 2 * MR * 16, al);
                }
            }
            es::simd<float, MR * 16> c;
            es::simd<uint32_t, (BF ? 256 : 16)> bw;
            if constexpr (BF) { // both steps
                bw.template select<128, 1>(0) = es::block_load<uint32_t, 128>(reinterpret_cast<const uint32_t *>(wp + 1024 * j), al);
                bw.template select<128, 1>(128) = es::block_load<uint32_t, 128>(reinterpret_cast<const uint32_t *>(wp + 1024 * j + 512), al);
            }
#pragma unroll
            for (int s = 0; s < 2; ++s) {
                es::simd<sycl::ext::oneapi::bfloat16, 256> B;
                if constexpr (BF) {
                    es::simd<uint32_t, 128> b2 = bw.template select<128, 1>(128 * s);
                    B = b2.template bit_cast_view<sycl::ext::oneapi::bfloat16>();
                } else {
#pragma unroll
                    for (int k = 0; k < 16; ++k) {
                        const es::simd<float, 16> f = cb.template select<16, 4>(512 * j + 64 * (4 * s + k / 4) + k % 4);
                        B.template select<16, 2>((k / 2) * 32 + (k % 2)) = f;
                    }
                }
#pragma unroll
                for (int p = 0; p < 3; ++p) {
                    es::simd<uint16_t, MR * 16> a = pa[p].template select<MR * 16, 1>(s * MR * 16);
                    const es::simd<sycl::ext::oneapi::bfloat16, MR * 16> ab = a.template bit_cast_view<sycl::ext::oneapi::bfloat16>();
                    c = ex::dpas<8, MR, float, float>(s == 0 && p == 0 ? zero : c, B, ab);
                }
            }
            if constexpr (BF) { // bf16 weights: fma(1, block sum, group sum) = their sum, rounded once
#pragma unroll
                for (int t = 0; t < MR; ++t)
                    g.template select<16, 1>(16 * t) = esx::fma(es::simd<float, 16>(1.0f), es::simd<float, 16>(c.template select<16, 1>(16 * t)),
                                                                es::simd<float, 16>(g.template select<16, 1>(16 * t)));
            } else {
                es::simd<uint16_t, 16> s16 = sh.template select<16, 1>(16 * j);
                const es::simd<float, 16> dj = es::simd<sycl::half, 16>(s16.template bit_cast_view<sycl::half>());
#pragma unroll
                for (int t = 0; t < MR; ++t)
                    g.template select<16, 1>(16 * t) = esx::fma(dj, es::simd<float, 16>(c.template select<16, 1>(16 * t)), es::simd<float, 16>(g.template select<16, 1>(16 * t)));
            }
        }
        return g;
    }
    void operator()(sycl::nd_item<1> it) const SYCL_ESIMD_KERNEL {
        constexpr int NGM = 12;
        es::slm_init<NGM * MR * 16 * 4>();
        const int cols = cm & 0xffff, mst = cm >> 16;
        const int ng = cols / 256, gi = (int)it.get_local_id(0), w = (int)it.get_group(0);
        int jn = 0;
#pragma unroll
        for (int k = 1; k < EJ_MAX; ++k) if (k < jb.nj && w >= jb.j[k].rb0) jn = k;
        const EJob &J = jb.j[jn];
        const int r16 = w - J.rb0;
        const int ldy = J.lk & 0x3fff, rv = (J.lk >> 14) & 0x3fff;
        const bool bfj = (J.lk >> 28) & 1;
        const size_t ps = (size_t)cols * MR;
        const uint16_t *pg = J.P + (size_t)gi * 8 * 2 * MR * 16;
        const float *xp = reinterpret_cast<const float *>(J.P) + (size_t)gi * 256;
        es::simd<float, MR * 16> g;
        if (bfj) g = group<true>(J.W + ((size_t)r16 * ng + gi) * 8192, pg, ps, xp);
        else g = group<false>(J.W + ((size_t)r16 * ng + gi) * TG, pg, ps, xp);
        es::slm_block_store<float, MR * 16>((uint32_t)(gi * MR * 16 * 4), g);
        es::barrier();
        if (gi == 0) {
            es::simd<float, MR * 16> tot = 0.0f;
            for (int q = 0; q < ng; ++q) tot = tot + es::slm_block_load<float, MR * 16>((uint32_t)(q * MR * 16 * 4));
            const bool half = rv - r16 * 16 < 16; // a bf16 job's last block of 8 rows
#pragma unroll
            for (int t = 0; t < MR; ++t)
                if (t < mst) {
                    if (half) es::block_store<float, 8>(J.y + (size_t)t * ldy + r16 * 16, tot.template select<8, 1>(16 * t));
                    else es::block_store<float, 16>(J.y + (size_t)t * ldy + r16 * 16, tot.template select<16, 1>(16 * t));
                }
        }
    }
};
// outputs stored for tokens < mst (default all MR)
template <int MR, int GRF = 128, bool UP = (MR == 1), bool XS = false>
inline sycl::event dgroupej(sycl::queue &q, const EJobs &jb, int cols, int mst = MR) {
    const int ng = cols / 256;
    if (cols % 256 || ng > 12 || jb.nj == 0 || mst < 1 || mst > MR) throw std::runtime_error("xd::dgroupej: shapes");
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)jb.nrb * ng), sycl::range<1>((size_t)ng)), XDGroupEJ<MR, GRF, UP, XS>{jb, cols | (mst << 16)});
}
} // namespace ink::xd
