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

// res[j] for rows rp[0..NR-1] and this lane's token, inputs xt (the tile, transposed)
template <class D, int NR>
inline void tile_dots(sycl::sub_group sg, const uint8_t *const *rp, int cols, const float *xt, int lane, float *res) {
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
            for (int j = 0; j < NR; ++j) { LD::get(rp[j], cols, c, lane, lo[j], hi[j]); s[j] = 0.0f; }
            for (int j = 0; j < NR; ++j)
                for (int i = 0; i < 32; ++i)
                    s[j] += sycl::select_from_group(sg, LD::hi(i) ? hi[j] : lo[j], LD::src(i)) * xs[i];
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
