// tok_tiles.hpp: token-parallel products for steps of many tokens with one matrix (dense layers): a sub-group takes a
// tile of 16 tokens, one per lane, and R rows; every lane computes its token's whole product, replaying the fixed
// arithmetic of the lane-per-chunk kernels (gemv2.hpp): the 16 virtual lanes' sums (chunks v, v + 16, ...; each
// chunk's 32 products in index order; chunk sums added in order from +0) combined in sg_sum's xor-butterfly pairs
// (v with v + 8, then + 4, + 2, + 1; a + b = b + a exactly), built up in bit-reversed order of v. Results equal
// gemv_v / gemv_pair bit for bit. The weights of a chunk are decoded once per sub-group (lane l produces values
// LaneDec::src/hi say which), and the inputs are transposed per tile (column-major across the 16 lanes) so each
// chunk is read with four sub-group block reads.
#pragma once
#include "moe_group.hpp"

namespace ink {

// lane decoders: get() gives this lane's two values of chunk c, lo and hi; value i of the chunk is in lane src(i),
// register hi(i). The arithmetic of each value is the same as the decoder's decode32.
template <class D> struct LaneDec { // any decoder: decode the whole chunk in every lane and keep two values
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int cols, int c, int lane, float &lo, float &hi) {
        float o[32];
        D::decode32(row, cols, c, o);
        lo = o[0]; hi = o[16];
        for (int i = 1; i < 16; ++i) { if (lane == i) { lo = o[i]; hi = o[16 + i]; } }
    }
};
template <> struct LaneDec<pl::Q8_0P> { // o[i] = (int8_t)q[i] * d
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int cols, int c, int lane, float &lo, float &hi) {
        const uint8_t *q = row + 32 * c;
        float d = fmt::h2f(row + cols + 2 * c);
        lo = (int8_t)q[lane] * d;
        hi = (int8_t)q[16 + lane] * d;
    }
};
template <> struct LaneDec<pl::Q6_KP> { // o[v] = (d * sc[v / 16]) * (code - 32), as Q6_KP::decode32
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int cols, int c, int lane, float &lo, float &hi) {
        const int sb = c >> 3, ib = c & 7, n = ib >> 2, w = ib & 3;
        const uint8_t *ql = row + 128 * sb + 64 * n + 32 * (w & 1);
        const uint8_t *qh = row + cols / 2 + 64 * sb + 32 * n;
        const int8_t *sc = (const int8_t *)(row + cols / 2 + cols / 4) + 16 * sb + 8 * n + 2 * w;
        const float d = fmt::h2f(row + cols / 2 + cols / 4 + cols / 16 + 2 * sb);
        const int lo_shift = (w >> 1) * 4, hi_shift = 2 * w;
        const uint32_t q0 = ((ql[lane] >> lo_shift) & 0xFu) | (((qh[lane] >> hi_shift) & 3u) << 4);
        const uint32_t q1 = ((ql[16 + lane] >> lo_shift) & 0xFu) | (((qh[16 + lane] >> hi_shift) & 3u) << 4);
        lo = (d * (float)sc[0]) * ((float)q0 - 32.0f);
        hi = (d * (float)sc[1]) * ((float)q1 - 32.0f);
    }
};
template <> struct LaneDec<pl::Raw<fmt::F<G_F32>>> { // the floats themselves
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int, int c, int lane, float &lo, float &hi) {
        const float *r = (const float *)row + 32 * c;
        lo = r[lane];
        hi = r[16 + lane];
    }
};
template <> struct LaneDec<pl::Raw<fmt::F<G_BF16>>> { // fmt::bf2f, as F<G_BF16>::decode32
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int, int c, int lane, float &lo, float &hi) {
        const uint16_t *r = (const uint16_t *)row + 32 * c;
        lo = fmt::bf2f(r[lane]);
        hi = fmt::bf2f(r[16 + lane]);
    }
};
// the file-layout formats of layers 20-23's experts: each value with the expression of formats.hpp's decode32
template <> struct LaneDec<pl::Raw<fmt::F<G_Q5_0>>> {
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int, int c, int j, float &lo, float &hi) {
        const uint8_t *b = row + 22 * c;
        float d = fmt::h2f(b);
        uint32_t qh = (uint32_t)b[2] | ((uint32_t)b[3] << 8) | ((uint32_t)b[4] << 16) | ((uint32_t)b[5] << 24);
        uint8_t q = b[6 + j];
        uint8_t xh0 = ((qh >> (j + 0)) << 4) & 0x10;
        uint8_t xh1 = ((qh >> (j + 12))) & 0x10;
        int32_t x0 = ((q & 0x0F) | xh0) - 16;
        int32_t x1 = ((q >> 4) | xh1) - 16;
        lo = x0 * d;
        hi = x1 * d;
    }
};
template <> struct LaneDec<pl::Raw<fmt::F<G_IQ4_NL>>> {
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int, int c, int j, float &lo, float &hi) {
        const uint8_t *b = row + 18 * c;
        float d = fmt::h2f(b);
        uint8_t q = b[2 + j];
        lo = d * fmt::kv_nl(q & 0xf);
        hi = d * fmt::kv_nl(q >> 4);
    }
};
template <> struct LaneDec<pl::Raw<fmt::F<G_IQ4_XS>>> {
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int, int c, int j, float &lo, float &hi) {
        const uint8_t *b = row + 136 * (c >> 3);
        int ib = c & 7;
        float d = fmt::h2f(b);
        uint16_t sh = (uint16_t)b[2] | ((uint16_t)b[3] << 8);
        const uint8_t *sl = b + 4, *qs = b + 8 + 16 * ib;
        int ls = ((sl[ib / 2] >> 4 * (ib % 2)) & 0xf) | (((sh >> 2 * ib) & 3) << 4);
        float dl = d * (ls - 32);
        uint8_t q = qs[j];
        lo = dl * fmt::kv_nl(q & 0xf);
        hi = dl * fmt::kv_nl(q >> 4);
    }
};
template <> struct LaneDec<pl::Raw<fmt::F<G_Q4_K>>> {
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int, int c, int l, float &lo, float &hi) {
        const uint8_t *b = row + 144 * (c >> 3);
        int ib = c & 7;
        float d = fmt::h2f(b), mn = fmt::h2f(b + 2);
        uint8_t sc, m;
        fmt::scale_min_k4(ib, b + 4, sc, m);
        float d1 = d * sc, m1 = mn * m;
        const uint8_t *q = b + 16 + 32 * (ib / 2);
        if (ib & 1) { lo = d1 * (q[l] >> 4) - m1; hi = d1 * (q[16 + l] >> 4) - m1; }
        else { lo = d1 * (q[l] & 0xF) - m1; hi = d1 * (q[16 + l] & 0xF) - m1; }
    }
};
template <> struct LaneDec<pl::Raw<fmt::F<G_Q5_K>>> {
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int, int c, int l, float &lo, float &hi) {
        const uint8_t *b = row + 176 * (c >> 3);
        int ib = c & 7;
        float d = fmt::h2f(b), mn = fmt::h2f(b + 2);
        uint8_t sc, m;
        fmt::scale_min_k4(ib, b + 4, sc, m);
        float d1 = d * sc, m1 = mn * m;
        const uint8_t *qh = b + 16, *ql = b + 48 + 32 * (ib / 2);
        uint8_t u = (uint8_t)(1u << ib);
        if (ib & 1) {
            lo = d1 * ((ql[l] >> 4) + (qh[l] & u ? 16 : 0)) - m1;
            hi = d1 * ((ql[16 + l] >> 4) + (qh[16 + l] & u ? 16 : 0)) - m1;
        } else {
            lo = d1 * ((ql[l] & 0xF) + (qh[l] & u ? 16 : 0)) - m1;
            hi = d1 * ((ql[16 + l] & 0xF) + (qh[16 + l] & u ? 16 : 0)) - m1;
        }
    }
};
// the decode copies of the same formats (planar.hpp Q5_0P ... Q5_KP): lane l reads byte l of the chunk's 16 nibble
// bytes (codes l and l + 16); every value with the same expression as the file-layout decoders above
template <> struct LaneDec<pl::Q5_0P> {
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int cols, int c, int l, float &lo, float &hi) {
        const uint8_t q = row[16 * c + l];
        uint32_t hb;
        std::memcpy(&hb, row + cols / 2 + 4 * c, 4);
        const float d = pl::h2f16(pl::ld16(row + cols / 2 + cols / 8 + 2 * c));
        const int32_t x0 = ((q & 0x0F) | (int)(((hb >> l) & 1u) << 4)) - 16;
        const int32_t x1 = ((q >> 4) | (int)(((hb >> (l + 16)) & 1u) << 4)) - 16;
        lo = x0 * d;
        hi = x1 * d;
    }
};
template <> struct LaneDec<pl::IQ4_NLP> {
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int cols, int c, int l, float &lo, float &hi) {
        const uint8_t q = row[16 * c + l];
        const float d = pl::h2f16(pl::ld16(row + cols / 2 + 2 * c));
        lo = d * fmt::kv_nl(q & 0xf);
        hi = d * fmt::kv_nl(q >> 4);
    }
};
template <> struct LaneDec<pl::IQ4_XSP> {
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int cols, int c, int l, float &lo, float &hi) {
        const uint8_t q = row[16 * c + l];
        const int ls = (int8_t)row[cols / 2 + c];
        const float d = pl::h2f16(pl::ld16(row + cols / 2 + cols / 32 + 2 * (c >> 3)));
        const float dl = d * ls;
        lo = dl * fmt::kv_nl(q & 0xf);
        hi = dl * fmt::kv_nl(q >> 4);
    }
};
template <bool Q5> struct LaneDecQK {
    static constexpr int src(int i) { return i & 15; }
    static constexpr bool hi(int i) { return i >= 16; }
    static void get(const uint8_t *row, int cols, int c, int l, float &lo, float &hi) {
        using P = pl::QK_P<Q5>;
        const uint8_t q = row[16 * c + l];
        const size_t sm = P::off_sm(cols);
        const uint16_t scm = pl::ld16(row + sm + 2 * c);
        uint32_t dm;
        std::memcpy(&dm, row + sm + cols / 16 + 4 * (c >> 3), 4);
        const float d = pl::h2f16((uint16_t)dm), mn = pl::h2f16((uint16_t)(dm >> 16));
        const uint8_t sc = (uint8_t)scm, m = (uint8_t)(scm >> 8);
        const float d1 = d * sc, m1 = mn * m;
        int q0 = q & 0xF, q1 = q >> 4;
        if constexpr (Q5) {
            uint32_t hb;
            std::memcpy(&hb, row + cols / 2 + 4 * c, 4);
            q0 += ((hb >> l) & 1u) ? 16 : 0;
            q1 += ((hb >> (l + 16)) & 1u) ? 16 : 0;
        }
        lo = d1 * q0 - m1;
        hi = d1 * q1 - m1;
    }
};
template <> struct LaneDec<pl::Q4_KP> : LaneDecQK<false> {};
template <> struct LaneDec<pl::Q5_KP> : LaneDecQK<true> {};
template <> struct LaneDec<pl::NVFP4P> { // lane l decodes byte l: values 16k + b (low code) and 16k + 8 + b (high)
    static constexpr int src(int i) { return 8 * (i >> 4) + (i & 7); }
    static constexpr bool hi(int i) { return (i >> 3) & 1; }
    static void get(const uint8_t *row, int cols, int c, int lane, float &lo, float &hi) {
        uint32_t byte = row[16 * c + lane];
        float d = pl::ue4m3_bits(row[cols / 2 + 2 * c + (lane >> 3)]) * 32768.0f;
        lo = nvfp4_one(byte, 0, d);
        hi = nvfp4_one(byte, 4, d);
    }
};

// NVFP4 through tables in local memory (the gate|up expert tiles of prompt steps): lut[i] (i < 16) = the value of code
// i with d = 1 as nvfp4_one makes it, lut[16 + x] = ue4m3_bits(x) * 32768.0f for every byte x: the same floats.
// bench_moe 512 tokens (card 3): gate|up 4 rows 6.71-6.76 -> 6.35-6.40 ms; down 2 rows 3.52 -> 3.66-3.69 (not used)
constexpr int NV4_LUT = 16 + 256;
using LocalF = sycl::multi_ptr<float, sycl::access::address_space::local_space, sycl::access::decorated::yes>;
inline void nv4_lut_fill(sycl::nd_item<2> it, LocalF lut) {
    const int n = (int)it.get_local_range(1);
    for (int i = (int)it.get_local_id(1); i < NV4_LUT; i += n) {
        float v;
        if (i < 16) v = (float)sycl::bit_cast<sycl::half>((uint16_t)((((uint32_t)i & 7u) << 9) | (((uint32_t)i & 8u) << 12)));
        else v = pl::ue4m3_bits((uint8_t)(i - 16)) * 32768.0f;
        lut[i] = v;
    }
    sycl::group_barrier(it.get_group());
}
struct LaneDecLut { // LaneDec<NVFP4P> through the tables
    static void get(const uint8_t *row, int cols, int c, int lane, float &lo, float &hi, LocalF lut) {
        const uint32_t byte = row[16 * c + lane];
        const float d = lut[16 + row[cols / 2 + 2 * c + (lane >> 3)]];
        lo = lut[byte & 15u] * d;
        hi = lut[byte >> 4] * d;
    }
};

// res[j] for rows rp[0..NR-1] and this lane's token, inputs xt (the tile, transposed); LUT: NVFP4 through the tables
template <class D, int NR, bool LUT = false>
inline void tile_dots(sycl::sub_group sg, const uint8_t *const *rp, int cols, const float *xt, int lane, float *res, LocalF lut = {}) {
    using LD = LaneDec<D>;
    const int nc = cols / 32;
    float st[NR][4];
#pragma unroll
    for (int vi = 0; vi < 16; ++vi) {
        const int v = br4(vi);
        float acc[NR];
        for (int j = 0; j < NR; ++j) acc[j] = 0.0f;
        for (int c = v; c < nc; c += SG) {
            float xs[32];
            const float *xc = xt + (size_t)32 * MOE_TS * c;
            for (int q = 0; q < 4; ++q) {
                auto mp = sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                    const_cast<float *>(xc + 128 * q));
                sycl::vec<float, 8> v8 = sg.load<8>(mp);
                for (int k = 0; k < 8; ++k) xs[8 * q + k] = v8[k];
            }
            float lo[NR], hi[NR], s[NR];
            for (int j = 0; j < NR; ++j) {
                if constexpr (LUT) LaneDecLut::get(rp[j], cols, c, lane, lo[j], hi[j], lut);
                else LD::get(rp[j], cols, c, lane, lo[j], hi[j]);
                s[j] = 0.0f;
            }
            for (int j = 0; j < NR; ++j)
                for (int i = 0; i < 32; ++i)
                    s[j] = mac(s[j], sycl::select_from_group(sg, LD::hi(i) ? hi[j] : lo[j], LD::src(i)), xs[i]);
            for (int j = 0; j < NR; ++j) acc[j] += s[j];
        }
        for (int j = 0; j < NR; ++j) {
            float val = acc[j];
            int lev = 0;
            for (int tt = vi; tt & 1; tt >>= 1) val = st[j][lev++] + val;
            if (lev < 4) st[j][lev] = val;
            else res[j] = val;
        }
    }
}

// tile_dots for two tiles of the same expert at once (32 slots, two per lane): every decoded weight value serves 32
// tokens. Each token's sums are tile_dots' (chunk products in index order, chunk sums in order, the same butterfly), so
// the values are the same.
template <class D, int NR, bool LUT = false>
inline void tile_dots2(sycl::sub_group sg, const uint8_t *const *rp, int cols, const float *xt0, const float *xt1, int lane,
                       float *res0, float *res1, LocalF lut = {}) {
    using LD = LaneDec<D>;
    const int nc = cols / 32;
    float st0[NR][4], st1[NR][4];
#pragma unroll
    for (int vi = 0; vi < 16; ++vi) {
        const int v = br4(vi);
        float acc0[NR], acc1[NR];
#pragma unroll
        for (int j = 0; j < NR; ++j) { acc0[j] = 0.0f; acc1[j] = 0.0f; }
        for (int c = v; c < nc; c += SG) {
            float lo[NR], hi[NR], s0[NR], s1[NR];
#pragma unroll
            for (int j = 0; j < NR; ++j) {
                if constexpr (LUT) LaneDecLut::get(rp[j], cols, c, lane, lo[j], hi[j], lut);
                else LD::get(rp[j], cols, c, lane, lo[j], hi[j]);
                s0[j] = 0.0f; s1[j] = 0.0f;
            }
#pragma unroll
            for (int q = 0; q < 4; ++q) {
                auto m0 = sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                    const_cast<float *>(xt0 + (size_t)32 * MOE_TS * c + 128 * q));
                auto m1 = sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                    const_cast<float *>(xt1 + (size_t)32 * MOE_TS * c + 128 * q));
                const sycl::vec<float, 8> a = sg.load<8>(m0), b = sg.load<8>(m1);
#pragma unroll
                for (int k = 0; k < 8; ++k) {
                    const int i = 8 * q + k;
#pragma unroll
                    for (int j = 0; j < NR; ++j) {
                        const float w = sycl::select_from_group(sg, LD::hi(i) ? hi[j] : lo[j], LD::src(i));
                        s0[j] = mac(s0[j], w, a[k]);
                        s1[j] = mac(s1[j], w, b[k]);
                    }
                }
            }
#pragma unroll
            for (int j = 0; j < NR; ++j) { acc0[j] += s0[j]; acc1[j] += s1[j]; }
        }
#pragma unroll
        for (int j = 0; j < NR; ++j) {
            float v0 = acc0[j], v1 = acc1[j];
            int lev = 0;
            for (int tt = vi; tt & 1; tt >>= 1) { v0 = st0[j][lev] + v0; v1 = st1[j][lev] + v1; ++lev; }
            if (lev < 4) { st0[j][lev] = v0; st1[j][lev] = v1; }
            else { res0[j] = v0; res1[j] = v1; }
        }
    }
}

// Xd[(tile * cols + col) * 16 + lane] = x[token * ldx + col] (token = 16 tile + lane), zeros past M
inline sycl::event dense_gather(sycl::queue &q, const float *x, int ldx, int M, int cols, float *Xd) {
    constexpr int GW = 256;
    const int tiles = (M + MOE_TS - 1) / MOE_TS, ncb = (cols + 15) / 16;
    return q.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)tiles, (size_t)ncb * GW), sycl::range<2>(1, GW)), [=](sycl::nd_item<2> it) {
        const int t = (int)it.get_group(0), li = (int)it.get_local_id(1), lane = li & 15, col = (int)it.get_group(1) * 16 + (li >> 4);
        if (col >= cols) return;
        const int tok = t * MOE_TS + lane;
        Xd[((size_t)t * cols + col) * MOE_TS + lane] = tok < M ? x[(size_t)tok * ldx + col] : 0.0f;
    });
}

// y[token * ldy + r] = W[r] . x[token]
template <class D, int R> struct DenseT {
    const uint8_t *W; size_t rb; int rows, cols, M;
    const float *Xd;
    float *y; int ldy;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        const int t = (int)it.get_group(0);
        auto sg = it.get_sub_group();
        const int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        const int lane = (int)sg.get_local_linear_id();
        const uint8_t *rp[R];
        for (int j = 0; j < R; ++j) rp[j] = W + (size_t)sycl::min(r0 + j, rows - 1) * rb;
        float res[R];
        tile_dots<D, R>(sg, rp, cols, Xd + (size_t)t * cols * MOE_TS, lane, res);
        const int tok = t * MOE_TS + lane;
        if (tok < M)
            for (int j = 0; j < R; ++j)
                if (r0 + j < rows) y[(size_t)tok * ldy + r0 + j] = res[j];
    }
};
// rows r of A and of B for every token, then op(token, r, a, b) (gemv_pair with one matrix pair, ids = nullptr)
template <class D, class Op, int NP> struct DensePairT {
    const uint8_t *A, *B; size_t rb; int rows, cols, M;
    const float *Xd;
    Op op;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        const int t = (int)it.get_group(0);
        auto sg = it.get_sub_group();
        const int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * NP;
        if (r0 >= rows) return;
        const int lane = (int)sg.get_local_linear_id();
        const uint8_t *rp[2 * NP];
        for (int j = 0; j < NP; ++j) {
            int r = sycl::min(r0 + j, rows - 1);
            rp[j] = A + (size_t)r * rb;
            rp[NP + j] = B + (size_t)r * rb;
        }
        float res[2 * NP];
        tile_dots<D, 2 * NP>(sg, rp, cols, Xd + (size_t)t * cols * MOE_TS, lane, res);
        const int tok = t * MOE_TS + lane;
        if (tok < M)
            for (int j = 0; j < NP; ++j)
                if (r0 + j < rows) op(tok, r0 + j, res[j], res[NP + j]);
    }
};

// ---- expert tiles for any decoder (moe_group.hpp's tiles and transposed inputs) ---------------------------------
// gate|up rows of the tile's expert; TOUT: the activation goes to Ht[(t * rows + r) * 16 + lane], else op(...)
template <class D, class Op, int NG, bool TOUT, bool LUT = false> struct SlotPairG {
    const uint8_t *A, *B; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *Xt;
    Op op;
    float *Ht;
    int sgw;
    sycl::local_accessor<float, 1> lut;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        LocalF lp{};
        if constexpr (LUT) { lp = lut.get_multi_ptr<sycl::access::decorated::yes>(); nv4_lut_fill(it, lp); }
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        auto sg = it.get_sub_group();
        const int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * NG;
        if (r0 >= rows) return;
        const int lane = (int)sg.get_local_linear_id();
        const int cnt = g.tile_n[t];
        const size_t eo = (size_t)g.tile_exp[t] * estride;
        const uint8_t *rp[2 * NG];
        for (int j = 0; j < NG; ++j) {
            int r = sycl::min(r0 + j, rows - 1);
            rp[j] = A + eo + (size_t)r * rb;
            rp[NG + j] = B + eo + (size_t)r * rb;
        }
        float res[2 * NG];
        tile_dots<D, 2 * NG, LUT>(sg, rp, cols, Xt + (size_t)t * cols * MOE_TS, lane, res, lp);
        const int slot = g.slots[g.tile_s0[t] + sycl::min(lane, cnt - 1)];
        for (int j = 0; j < NG; ++j) {
            if (r0 + j >= rows) break;
            if constexpr (TOUT) Ht[((size_t)t * rows + r0 + j) * MOE_TS + lane] = lane < cnt ? op.act(slot, res[j], res[NG + j]) : 0.0f;
            else if (lane < cnt) op(slot, r0 + j, res[j], res[NG + j]);
        }
    }
};
// SlotPairG with a sub-group per pair of tiles (2p, 2p + 1): tiles of the same expert go through tile_dots2, others one
// after another through tile_dots. The same values.
template <class D, class Op, int NG, bool TOUT, bool LUT = false, bool PAIR = true, bool BIG = false> struct SlotPairG2 : GrfProps<BIG> {
    const uint8_t *A, *B; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *Xt;
    Op op;
    float *Ht;
    int sgw;
    sycl::local_accessor<float, 1> lut;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        LocalF lp{};
        if constexpr (LUT) { lp = lut.get_multi_ptr<sycl::access::decorated::yes>(); nv4_lut_fill(it, lp); }
        const int t0 = 2 * (int)it.get_group(0), ntl = g.ntiles[0];
        if (t0 >= ntl) return;
        auto sg = it.get_sub_group();
        const int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * NG;
        if (r0 >= rows) return;
        const int lane = (int)sg.get_local_linear_id();
        const uint8_t *rp[2 * NG];
        auto rows_of = [&](int t) {
            const size_t eo = (size_t)g.tile_exp[t] * estride;
#pragma unroll
            for (int j = 0; j < NG; ++j) {
                int r = sycl::min(r0 + j, rows - 1);
                rp[j] = A + eo + (size_t)r * rb;
                rp[NG + j] = B + eo + (size_t)r * rb;
            }
        };
        auto put = [&](int t, const float *res) {
            const int cnt = g.tile_n[t];
            const int slot = g.slots[g.tile_s0[t] + sycl::min(lane, cnt - 1)];
#pragma unroll
            for (int j = 0; j < NG; ++j) {
                if (r0 + j >= rows) break;
                if constexpr (TOUT) Ht[((size_t)t * rows + r0 + j) * MOE_TS + lane] = lane < cnt ? op.act(slot, res[j], res[NG + j]) : 0.0f;
                else if (lane < cnt) op(slot, r0 + j, res[j], res[NG + j]);
            }
        };
        float res0[2 * NG], res1[2 * NG];
        if (PAIR && t0 + 1 < ntl && g.tile_exp[t0 + 1] == g.tile_exp[t0]) {
            rows_of(t0);
            tile_dots2<D, 2 * NG, LUT>(sg, rp, cols, Xt + (size_t)t0 * cols * MOE_TS, Xt + (size_t)(t0 + 1) * cols * MOE_TS, lane, res0,
                                       res1, lp);
            put(t0, res0);
            put(t0 + 1, res1);
            return;
        }
        for (int t = t0; t < sycl::min(t0 + 2, ntl); ++t) {
            rows_of(t);
            tile_dots<D, 2 * NG, LUT>(sg, rp, cols, Xt + (size_t)t * cols * MOE_TS, lane, res0, lp);
            put(t, res0);
        }
    }
};
template <class D, int R> struct SlotRowsG {
    const uint8_t *W; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *Xt;
    float *y; int ldy;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        auto sg = it.get_sub_group();
        const int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        const int lane = (int)sg.get_local_linear_id();
        const int cnt = g.tile_n[t];
        const uint8_t *base = W + (size_t)g.tile_exp[t] * estride;
        const uint8_t *rp[R];
        for (int j = 0; j < R; ++j) rp[j] = base + (size_t)sycl::min(r0 + j, rows - 1) * rb;
        float res[R];
        tile_dots<D, R>(sg, rp, cols, Xt + (size_t)t * cols * MOE_TS, lane, res);
        if (lane < cnt) {
            const int slot = g.slots[g.tile_s0[t] + lane];
            for (int j = 0; j < R; ++j)
                if (r0 + j < rows) y[(size_t)slot * ldy + r0 + j] = res[j];
        }
    }
};
// SlotRowsG with a sub-group per pair of tiles (as SlotPairG2). The same values.
template <class D, int R, bool PAIR = true, bool BIG = false> struct SlotRowsG2 : GrfProps<BIG> {
    const uint8_t *W; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *Xt;
    float *y; int ldy;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        const int t0 = 2 * (int)it.get_group(0), ntl = g.ntiles[0];
        if (t0 >= ntl) return;
        auto sg = it.get_sub_group();
        const int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        const int lane = (int)sg.get_local_linear_id();
        const uint8_t *rp[R];
        auto rows_of = [&](int t) {
            const uint8_t *base = W + (size_t)g.tile_exp[t] * estride;
#pragma unroll
            for (int j = 0; j < R; ++j) rp[j] = base + (size_t)sycl::min(r0 + j, rows - 1) * rb;
        };
        auto put = [&](int t, const float *res) {
            if (lane < g.tile_n[t]) {
                const int slot = g.slots[g.tile_s0[t] + lane];
#pragma unroll
                for (int j = 0; j < R; ++j)
                    if (r0 + j < rows) y[(size_t)slot * ldy + r0 + j] = res[j];
            }
        };
        float res0[R], res1[R];
        if (PAIR && t0 + 1 < ntl && g.tile_exp[t0 + 1] == g.tile_exp[t0]) {
            rows_of(t0);
            tile_dots2<D, R>(sg, rp, cols, Xt + (size_t)t0 * cols * MOE_TS, Xt + (size_t)(t0 + 1) * cols * MOE_TS, lane, res0, res1);
            put(t0, res0);
            put(t0 + 1, res1);
            return;
        }
        for (int t = t0; t < sycl::min(t0 + 2, ntl); ++t) {
            rows_of(t);
            tile_dots<D, R>(sg, rp, cols, Xt + (size_t)t * cols * MOE_TS, lane, res0);
            put(t, res0);
        }
    }
};
// INK_TILE_LUT=0: NVFP4 gate|up tiles decode without the tables
inline bool tile_lut = [] { const char *e = std::getenv("INK_TILE_LUT"); return !e || std::atoi(e) != 0; }();
// INK_TILE_V2=0: the NVFP4 prompt expert tiles one tile per sub-group (slot_pair_g, slot_rows_g 2 rows) as before
inline bool tile_v2 = [] { const char *e = std::getenv("INK_TILE_V2"); return !e || std::atoi(e) != 0; }();
// ng = gate rows per sub-group (pair) or rows (down): 1 or 2
template <class Op>
inline sycl::event slot_pair_g(sycl::queue &q, const WView &a, const uint8_t *B, size_t estride, int rows, MoeGroups g, int tiles,
                               const float *Xt, Op op, float *Ht, int ng = 2) {
    const int cols = (int)a.t->ne[0], sgw = 1;
    sycl::event e;
    with_decoder(a, [&]<class D>() {
        auto go = [&]<int NG>() {
            int ngr = (rows + NG - 1) / NG;
            sycl::nd_range<2> nr(sycl::range<2>((size_t)tiles, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
            constexpr bool L = std::is_same_v<D, pl::NVFP4P>;
            const bool lut = L && tile_lut;
            e = q.submit([&](sycl::handler &h) {
                sycl::local_accessor<float, 1> la(lut ? NV4_LUT : 1, h);
                if (lut) {
                    if (Ht) h.parallel_for(nr, SlotPairG<D, Op, NG, true, L>{a.p, B, a.rb, estride, rows, cols, g, Xt, op, Ht, sgw, la});
                    else h.parallel_for(nr, SlotPairG<D, Op, NG, false, L>{a.p, B, a.rb, estride, rows, cols, g, Xt, op, Ht, sgw, la});
                } else if (Ht) h.parallel_for(nr, SlotPairG<D, Op, NG, true>{a.p, B, a.rb, estride, rows, cols, g, Xt, op, Ht, sgw, la});
                else h.parallel_for(nr, SlotPairG<D, Op, NG, false>{a.p, B, a.rb, estride, rows, cols, g, Xt, op, Ht, sgw, la});
            });
        };
        if (ng == 1) go.template operator()<1>(); else go.template operator()<2>();
    });
    return e;
}
// slot_pair_g with SlotPairG2 (pairs of tiles; pair = false: one tile at a time, two per sub-group), NVFP4 only (the
// tables on, the activation to the tiles): ng 1, 2 or 4 gate rows, big = 256 registers
template <class Op>
inline sycl::event slot_pair_g2(sycl::queue &q, const WView &a, const uint8_t *B, size_t estride, int rows, MoeGroups g, int tiles,
                                const float *Xt, Op op, float *Ht, int ng = 2, bool pair = true, bool big = false) {
    const int cols = (int)a.t->ne[0], sgw = 1;
    if (a.kind != K_NVFP4P || !Ht || !tile_lut) throw std::runtime_error("slot_pair_g2: NVFP4 tiles to Ht only");
    using D = pl::NVFP4P;
    sycl::event e;
    auto go = [&]<int NG, bool P, bool BG>() {
        int ngr = (rows + NG - 1) / NG;
        sycl::nd_range<2> nr(sycl::range<2>((size_t)(tiles + 1) / 2, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
        e = q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> la(NV4_LUT, h);
            h.parallel_for(nr, SlotPairG2<D, Op, NG, true, true, P, BG>{{}, a.p, B, a.rb, estride, rows, cols, g, Xt, op, Ht, sgw, la});
        });
    };
    auto gp = [&]<int NG>() {
        if (pair) { if (big) go.template operator()<NG, true, true>(); else go.template operator()<NG, true, false>(); }
        else { if (big) go.template operator()<NG, false, true>(); else go.template operator()<NG, false, false>(); }
    };
    if (ng == 1) gp.template operator()<1>(); else if (ng == 4) gp.template operator()<4>(); else gp.template operator()<2>();
    return e;
}
inline sycl::event slot_rows_g(sycl::queue &q, const WView &w, MoeGroups g, int tiles, const float *Xt, float *y, int ldy, int r = 2) {
    const int cols = (int)w.t->ne[0], rows = (int)w.t->ne[1], sgw = 1;
    const size_t estride = w.rb * (size_t)rows;
    sycl::event e;
    with_decoder(w, [&]<class D>() {
        auto go = [&]<int R>() {
            int ngr = (rows + R - 1) / R;
            sycl::nd_range<2> nr(sycl::range<2>((size_t)tiles, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
            e = q.parallel_for(nr, SlotRowsG<D, R>{w.p, w.rb, estride, rows, cols, g, Xt, y, ldy, sgw});
        };
        if (r == 1) go.template operator()<1>(); else go.template operator()<2>();
    });
    return e;
}

// NVFP4 only: r 1, 2 or 4 rows, pair / big as slot_pair_g2
inline sycl::event slot_rows_g2(sycl::queue &q, const WView &w, MoeGroups g, int tiles, const float *Xt, float *y, int ldy, int r = 2,
                                bool pair = true, bool big = false) {
    const int cols = (int)w.t->ne[0], rows = (int)w.t->ne[1], sgw = 1;
    const size_t estride = w.rb * (size_t)rows;
    if (w.kind != K_NVFP4P) throw std::runtime_error("slot_rows_g2: NVFP4 only");
    using D = pl::NVFP4P;
    sycl::event e;
    auto go = [&]<int R, bool P, bool BG>() {
        int ngr = (rows + R - 1) / R;
        sycl::nd_range<2> nr(sycl::range<2>((size_t)(tiles + 1) / 2, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
        e = q.parallel_for(nr, SlotRowsG2<D, R, P, BG>{{}, w.p, w.rb, estride, rows, cols, g, Xt, y, ldy, sgw});
    };
    auto gp = [&]<int R>() {
        if (pair) { if (big) go.template operator()<R, true, true>(); else go.template operator()<R, true, false>(); }
        else { if (big) go.template operator()<R, false, true>(); else go.template operator()<R, false, false>(); }
    };
    if (r == 1) gp.template operator()<1>(); else if (r == 4) gp.template operator()<4>(); else gp.template operator()<2>();
    return e;
}
struct DTune { int R = 2, sgw = 1; };
inline sycl::event dense_t(sycl::queue &q, const WView &w, int M, const float *Xd, float *y, int ldy, DTune dt = {}) {
    sycl::event e;
    const int rows = (int)w.t->rows(), cols = (int)w.t->ne[0], tiles = (M + MOE_TS - 1) / MOE_TS;
    with_decoder(w, [&]<class D>() {
        auto go = [&]<int R>() {
            int nsg = (rows + R - 1) / R, ngr = (nsg + dt.sgw - 1) / dt.sgw;
            sycl::nd_range<2> nr(sycl::range<2>((size_t)tiles, (size_t)ngr * dt.sgw * SG), sycl::range<2>(1, (size_t)dt.sgw * SG));
            e = q.parallel_for(nr, DenseT<D, R>{w.p, w.rb, rows, cols, M, Xd, y, ldy, dt.sgw});
        };
        switch (dt.R) {
        case 1: go.template operator()<1>(); break;
        case 2: go.template operator()<2>(); break;
        case 4: go.template operator()<4>(); break;
        default: throw std::runtime_error("dense_t: R must be 1, 2 or 4");
        }
    });
    return e;
}
template <class Op>
inline sycl::event dense_pair_t(sycl::queue &q, const WView &a, const uint8_t *B, int rows, int M, const float *Xd, Op op, DTune dt = {}) {
    sycl::event e;
    const int cols = (int)a.t->ne[0], tiles = (M + MOE_TS - 1) / MOE_TS;
    with_decoder(a, [&]<class D>() {
        auto go = [&]<int NP>() {
            int nsg = (rows + NP - 1) / NP, ngr = (nsg + dt.sgw - 1) / dt.sgw;
            sycl::nd_range<2> nr(sycl::range<2>((size_t)tiles, (size_t)ngr * dt.sgw * SG), sycl::range<2>(1, (size_t)dt.sgw * SG));
            e = q.parallel_for(nr, DensePairT<D, Op, NP>{a.p, B, a.rb, rows, cols, M, Xd, op, dt.sgw});
        };
        switch (dt.R) {
        case 1: go.template operator()<1>(); break;
        case 2: go.template operator()<2>(); break;
        default: throw std::runtime_error("dense_pair_t: R must be 1 or 2");
        }
    });
    return e;
}

} // namespace ink
