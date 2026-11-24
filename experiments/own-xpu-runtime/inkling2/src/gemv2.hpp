// gemv2.hpp: matrix-vector kernels over a decoder D (planar.hpp: Q8_0P, NVFP4P, Q6_KP, or Raw<F> for the file
// layout) with exactly the arithmetic of gemv.hpp, so results are bit-identical to it. Per row the order is fixed:
// lane l takes chunks l, l+16, ...; each chunk's 32 products are summed in index order; the lane sums are added in
// chunk order; then the same xor butterfly. What differs is the work layout:
//  - Gemv1R: one vector, R rows per sub-group (the input chunk is loaded once for the R rows, 16-byte loads).
//  - GemvRoutedR: the routed expert form, R rows per sub-group.
//  - GemvM: M vectors (prompt steps), one row per sub-group (gemv.hpp's kernel over D).
#pragma once
#include "gemv.hpp"
#include "planar.hpp"
#include "xlane.hpp"
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>
#include <map>

namespace ink {

inline void load_x32(const float *xv, float *xs) {
    using V = sycl::vec<float, 4>;
    for (int i = 0; i < 8; ++i) {
        V v = *(const V *)(xv + 4 * i);
        xs[4 * i] = v[0]; xs[4 * i + 1] = v[1]; xs[4 * i + 2] = v[2]; xs[4 * i + 3] = v[3];
    }
}
// x in lane order (xlane.hpp): chunk c's 32 values
inline void load_x32_lane(const float *xl, int c, float *xs) {
    using V = sycl::vec<float, 4>;
    const float *p = xl + (size_t)(c >> 4) * 512 + (size_t)(c & 15) * 4;
    for (int q = 0; q < 8; ++q) {
        V v = *(const V *)(p + 64 * q);
        xs[4 * q] = v[0]; xs[4 * q + 1] = v[1]; xs[4 * q + 2] = v[2]; xs[4 * q + 3] = v[3];
    }
}
// F32 weights with each row in lane order (xlane.hpp): the 16 lanes' weight loads side by side too (rows padded to
// xlane_floats(cols) floats; the padding is never read). Same values in the same registers as the file layout.
namespace pl {
struct F32L {
    static void decode32(const uint8_t *row, int, int c, float *o) { load_x32_lane((const float *)row, c, o); }
};
} // namespace pl
inline sycl::event f32_lane_repack(sycl::queue &q, const float *src, float *dst, int rows, int cols) {
    const size_t lx = xlane_floats(cols);
    return q.parallel_for(sycl::range<2>((size_t)rows, (size_t)cols), [=](sycl::id<2> i) {
        dst[i[0] * lx + xlane_at((int)i[1])] = src[i[0] * cols + i[1]];
    });
}
// chunk c of x, plain (x = the vector) or lane order (xl)
inline void load_xc(const float *x, int c, float *xs, bool xl) {
    if (xl) load_x32_lane(x, c, xs);
    else load_x32(x + 32 * c, xs);
}

// rows r0..r0+R-1 of W times x into y (one sub-group); shared by Gemv1R and the multi-matrix launch (multi.hpp)
template <class D, int R, bool XL = false> // XL: x in lane order
inline void gemv1_rows(sycl::sub_group sg, const uint8_t *W, size_t rb, int rows, int cols, const float *x, float *y, int r0) {
    int lane = (int)sg.get_local_linear_id();
    float acc[R];
    for (int k = 0; k < R; ++k) acc[k] = 0.0f;
    const int nc = cols / 32;
    for (int c = lane; c < nc; c += SG) {
        float xs[32];
        load_xc(x, c, xs, XL);
        for (int k = 0; k < R; ++k) {
            if (r0 + k >= rows) break;
            float o[32];
            D::decode32(W + (size_t)(r0 + k) * rb, cols, c, o);
            float s = 0.0f;
            for (int i = 0; i < 32; ++i) s = mac(s, o[i], xs[i]);
            acc[k] += s;
        }
    }
    for (int k = 0; k < R; ++k) {
        float v = sg_sum(sg, acc[k]);
        if (lane == 0 && r0 + k < rows) y[r0 + k] = v;
    }
}
template <class D, int R, bool XL = false> struct Gemv1R {
    const uint8_t *W; size_t rb; int rows, cols;
    const float *x;
    float *y;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<1> it) const {
        auto sg = it.get_sub_group();
        int r0 = ((int)it.get_group(0) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        gemv1_rows<D, R, XL>(sg, W, rb, rows, cols, x, y, r0);
    }
};

template <class D, int M> struct GemvM {
    const uint8_t *W; size_t rb; int rows, cols;
    const float *x; int ldx;
    float *y; int ldy;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<1> it) const {
        auto sg = it.get_sub_group();
        int r = (int)it.get_group(0) * GEMV_ROWS + (int)sg.get_group_linear_id();
        if (r >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        const uint8_t *row = W + (size_t)r * rb;
        float acc[M];
        for (int m = 0; m < M; ++m) acc[m] = 0.0f;
        const int nc = cols / 32;
        for (int c = lane; c < nc; c += SG) {
            float o[32];
            D::decode32(row, cols, c, o);
            for (int m = 0; m < M; ++m) {
                const float *xv = x + (size_t)m * ldx + 32 * c;
                float s = 0.0f;
                for (int i = 0; i < 32; ++i) s = mac(s, o[i], xv[i]);
                acc[m] += s;
            }
        }
        for (int m = 0; m < M; ++m) {
            float v = sg_sum(sg, acc[m]);
            if (lane == 0) y[(size_t)m * ldy + r] = v;
        }
    }
};

// M vectors and R rows per sub-group, 16-byte input loads shared by the R rows; group(0) = block of M vectors (the
// vectors of block b start at x + b*M*ldx), group(1) = block of sgw*R rows. Each (row, vector) sum is Gemv1R's.
template <class D, int R, int M, bool INTERLEAVE = false, bool XL = false> struct GemvMR { // XL: each vector in lane order
    const uint8_t *W; size_t rb; int rows, cols;
    const float *x; int ldx;
    float *y; int ldy;
    int sgw;
    // R = 4: the large register file (256 registers per thread, half the threads per core)
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        if constexpr (R >= 4) return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<256>};
        else return sycl::ext::oneapi::experimental::properties{};
    }
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        auto sg = it.get_sub_group();
        int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        const size_t vb = (size_t)it.get_group(0) * M;
        const float *xb = x + vb * ldx;
        float acc[R][M];
        for (int k = 0; k < R; ++k) for (int m = 0; m < M; ++m) acc[k][m] = 0.0f;
        const int nc = cols / 32;
        for (int c = lane; c < nc; c += SG) {
            float o[R][32];
            for (int k = 0; k < R; ++k)
                if (r0 + k < rows) D::decode32(W + (size_t)(r0 + k) * rb, cols, c, o[k]);
            if constexpr (INTERLEAVE) {
                // the R*M chunk sums advance together, four terms at a time (each still in index order)
                float s[R][M];
                for (int k = 0; k < R; ++k) for (int m = 0; m < M; ++m) s[k][m] = 0.0f;
                for (int i4 = 0; i4 < 8; ++i4) {
                    for (int m = 0; m < M; ++m) {
                        sycl::vec<float, 4> xv = *(const sycl::vec<float, 4> *)(xb + (size_t)m * ldx + 32 * c + 4 * i4);
                        for (int j = 0; j < 4; ++j)
                            for (int k = 0; k < R; ++k) s[k][m] = mac(s[k][m], o[k][4 * i4 + j], xv[j]);
                    }
                }
                for (int k = 0; k < R; ++k) for (int m = 0; m < M; ++m) acc[k][m] += s[k][m];
            } else {
                for (int m = 0; m < M; ++m) {
                    float xs[32];
                    load_xc(xb + (size_t)m * ldx, c, xs, XL);
                    for (int k = 0; k < R; ++k) {
                        float s = 0.0f;
                        for (int i = 0; i < 32; ++i) s = mac(s, o[k][i], xs[i]);
                        acc[k][m] += s;
                    }
                }
            }
        }
        for (int k = 0; k < R; ++k)
            for (int m = 0; m < M; ++m) {
                float v = sg_sum(sg, acc[k][m]);
                if (lane == 0 && r0 + k < rows) y[(vb + m) * ldy + r0 + k] = v;
            }
    }
};

// routed: y[k*ldy + r] = W_{ids[k]} row r . x row (xdiv ? k / xdiv : 0); group(0) = k, group(1) = block of sgw*R rows
template <class D, int R, bool XL = false> struct GemvRoutedR { // XL: x in lane order
    const uint8_t *W; size_t rb, estride; int rows, cols;
    const int32_t *ids;
    const float *x; int ldx, xdiv;
    float *y; int ldy;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        auto sg = it.get_sub_group();
        int k = (int)it.get_group(0);
        int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        const uint8_t *base = W + (size_t)ids[k] * estride;
        const float *xv0 = x + (size_t)(xdiv ? k / xdiv : 0) * ldx;
        float acc[R];
        for (int j = 0; j < R; ++j) acc[j] = 0.0f;
        const int nc = cols / 32;
        for (int c = lane; c < nc; c += SG) {
            float xs[32];
            load_xc(xv0, c, xs, XL);
            for (int j = 0; j < R; ++j) {
                if (r0 + j >= rows) break;
                float o[32];
                D::decode32(base + (size_t)(r0 + j) * rb, cols, c, o);
                float s = 0.0f;
                for (int i = 0; i < 32; ++i) s = mac(s, o[i], xs[i]);
                acc[j] += s;
            }
        }
        for (int j = 0; j < R; ++j) {
            float v = sg_sum(sg, acc[j]);
            if (lane == 0 && r0 + j < rows) y[(size_t)k * ldy + r0 + j] = v;
        }
    }
};

// Gemv1R and GemvRoutedR with every weight load of a lane issued before any is used (NCL chunks per lane at most,
// R rows): same arithmetic, same order. Only for decoders with load()/dec() (Q8_0P, NVFP4P).
template <class D, int R, int NCL> struct Gemv1P {
    const uint8_t *W; size_t rb; int rows, cols;
    const float *x;
    float *y;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<1> it) const {
        auto sg = it.get_sub_group();
        int r0 = ((int)it.get_group(0) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        const int nc = cols / 32;
        typename D::Pre pre[NCL][R];
        for (int j = 0; j < NCL; ++j) {
            int c = lane + SG * j;
            if (c < nc)
                for (int k = 0; k < R; ++k)
                    if (r0 + k < rows) D::load(W + (size_t)(r0 + k) * rb, cols, c, pre[j][k]);
        }
        float acc[R];
        for (int k = 0; k < R; ++k) acc[k] = 0.0f;
        for (int j = 0; j < NCL; ++j) {
            int c = lane + SG * j;
            if (c >= nc) break;
            float xs[32];
            load_x32(x + 32 * c, xs);
            for (int k = 0; k < R; ++k) {
                if (r0 + k >= rows) break;
                float o[32];
                D::dec(pre[j][k], o);
                float s = 0.0f;
                for (int i = 0; i < 32; ++i) s = mac(s, o[i], xs[i]);
                acc[k] += s;
            }
        }
        for (int k = 0; k < R; ++k) {
            float v = sg_sum(sg, acc[k]);
            if (lane == 0 && r0 + k < rows) y[r0 + k] = v;
        }
    }
};
template <class D, int R, int NCL> struct GemvRoutedP {
    const uint8_t *W; size_t rb, estride; int rows, cols;
    const int32_t *ids;
    const float *x; int ldx, xdiv;
    float *y; int ldy;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        auto sg = it.get_sub_group();
        int k = (int)it.get_group(0);
        int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        const uint8_t *base = W + (size_t)ids[k] * estride;
        const float *xv0 = x + (size_t)(xdiv ? k / xdiv : 0) * ldx;
        const int nc = cols / 32;
        typename D::Pre pre[NCL][R];
        for (int j = 0; j < NCL; ++j) {
            int c = lane + SG * j;
            if (c < nc)
                for (int i = 0; i < R; ++i)
                    if (r0 + i < rows) D::load(base + (size_t)(r0 + i) * rb, cols, c, pre[j][i]);
        }
        float acc[R];
        for (int i = 0; i < R; ++i) acc[i] = 0.0f;
        for (int j = 0; j < NCL; ++j) {
            int c = lane + SG * j;
            if (c >= nc) break;
            float xs[32];
            load_x32(xv0 + 32 * c, xs);
            for (int i = 0; i < R; ++i) {
                if (r0 + i >= rows) break;
                float o[32];
                D::dec(pre[j][i], o);
                float s = 0.0f;
                for (int q = 0; q < 32; ++q) s = mac(s, o[q], xs[q]);
                acc[i] += s;
            }
        }
        for (int i = 0; i < R; ++i) {
            float v = sg_sum(sg, acc[i]);
            if (lane == 0 && r0 + i < rows) y[(size_t)k * ldy + r0 + i] = v;
        }
    }
};
template <class D> constexpr bool has_pre = requires { typename D::Pre; };

// two rows at once, from two matrices of the same shape (or two row ranges of one), each with Gemv1R's arithmetic,
// then op(k, r, a_r, b_r) on the pair. group(0) = slot k: routed (A and B offset by ids[k] * estride) or token k (ids
// null); x row = xdiv ? k / xdiv : k. Used for the expert gate|up rows + SITU and the loop gain|forget rows + control.
// one row of two matrices (rows ra, rbp) times xv0 in one sub-group; shared by GemvPair and multi.hpp's CtlMulti
template <class D, bool XL = false>
inline void gemv_pair_row(sycl::sub_group sg, const uint8_t *ra, const uint8_t *rbp, int cols, const float *xv0, float &va, float &vb) {
    int lane = (int)sg.get_local_linear_id();
    float acc[2] = {0.0f, 0.0f};
    const int nc = cols / 32;
    for (int c = lane; c < nc; c += SG) {
        float xs[32];
        load_xc(xv0, c, xs, XL);
        for (int j = 0; j < 2; ++j) {
            float o[32];
            D::decode32(j ? rbp : ra, cols, c, o);
            float s = 0.0f;
            for (int i = 0; i < 32; ++i) s = mac(s, o[i], xs[i]);
            acc[j] += s;
        }
    }
    va = sg_sum(sg, acc[0]); vb = sg_sum(sg, acc[1]);
}
template <class D, class Op, bool XL = false> struct GemvPair { // XL: x in lane order
    const uint8_t *A, *B; size_t rb, estride; int rows, cols;
    const int32_t *ids;
    const float *x; int ldx, xdiv;
    Op op;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        auto sg = it.get_sub_group();
        int k = (int)it.get_group(0);
        int r = (int)it.get_group(1) * sgw + (int)sg.get_group_linear_id();
        if (r >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        size_t eo = ids ? (size_t)ids[k] * estride : 0;
        const uint8_t *ra = A + eo + (size_t)r * rb, *rbp = B + eo + (size_t)r * rb;
        const float *xv0 = x + (size_t)(xdiv ? k / xdiv : k) * ldx;
        // what the epilogue reads from memory, read now so its latency hides under the row's reads
        float pre = 0.0f;
        if constexpr (requires { op.pre(k); }) pre = op.pre(k);
        float va, vb;
        gemv_pair_row<D, XL>(sg, ra, rbp, cols, xv0, va, vb);
        if constexpr (requires { op.pre(k); }) op.post(sg, lane, k, r, va, vb, pre);
        else if (lane == 0) op(k, r, va, vb);
    }
};
// ops::situ for slot k, row i, from the gate and up values
struct SituOp {
    const float *escale; const int32_t *ids; float beta, lb; float *hout; int nff;
    int ldo = 0; // > 0: slot k's output in lane order (xlane_at) at hout + k * ldo, for a lane-order down product
    size_t at(int k, int i) const { return ldo ? (size_t)k * ldo + xlane_at(i) : (size_t)k * nff + i; }
    float act(int k, float g, float u) const {
        if (escale) { float s = escale[ids[k]]; g = g * s; u = u * s; }
        float a = (sycl::tanh(g * (1.0f / beta)) * beta) * (1.0f / (1.0f + sycl::exp(-g)));
        if (lb > 0.0f) u = sycl::tanh(u * (1.0f / lb)) * lb;
        return a * u;
    }
    void operator()(int k, int i, float g, float u) const { hout[at(k, i)] = act(k, g, u); }
    // act() with the slot's expert scale read ahead (GemvPair): the same operations
    float pre(int k) const { return escale ? escale[ids[k]] : 1.0f; }
    // the two tanh in one pass: lane 0 takes the gate's, lane 1 the up value's (each lane computes the same function
    // of its own argument, so the values are act()'s); lane 0 stores
    void post(sycl::sub_group sg, int lane, int k, int i, float g, float u, float s) const {
        if (escale) { g = g * s; u = u * s; }
        const float th = sycl::tanh(lane == 1 ? u * (1.0f / lb) : g * (1.0f / beta));
        const float thu = sycl::select_from_group(sg, th, 1);
        if (lane == 0) {
            float a = (th * beta) * (1.0f / (1.0f + sycl::exp(-g)));
            if (lb > 0.0f) u = thu * lb;
            hout[at(k, i)] = a * u;
        }
    }
};
// ops::control_out for token k, channel i, from the gain and forget values
struct CtlOp {
    const float *cur, *msg; float *y; int n;
    void operator()(int k, int i, float g, float f) const {
        size_t j = (size_t)k * n + i;
        float fo = sycl::tanh(f), ga = sycl::tanh(g);
        y[j] = (fo * -1.0f + 1.0f) * cur[j] + ga * msg[j];
    }
};

// a weight as the kernels see it: layout kind, pointer, row stride
enum Kind { K_RAW = 0, K_Q8_0P = 1, K_NVFP4P = 2, K_Q6_KP = 3, K_Q5_0P = 4, K_IQ4_NLP = 5, K_IQ4_XSP = 6, K_Q4_KP = 7, K_Q5_KP = 8,
            K_F32L = 9 };
struct WView {
    const Tensor *t = nullptr;
    const uint8_t *p = nullptr;
    size_t rb = 0;
    int kind = K_RAW;
};

template <class Fn> inline void with_decoder(const WView &w, Fn &&f) {
    switch (w.kind) {
    case K_Q8_0P: f.template operator()<pl::Q8_0P>(); return;
    case K_NVFP4P: f.template operator()<pl::NVFP4P>(); return;
    case K_Q6_KP: f.template operator()<pl::Q6_KP>(); return;
    case K_Q5_0P: f.template operator()<pl::Q5_0P>(); return;
    case K_IQ4_NLP: f.template operator()<pl::IQ4_NLP>(); return;
    case K_IQ4_XSP: f.template operator()<pl::IQ4_XSP>(); return;
    case K_Q4_KP: f.template operator()<pl::Q4_KP>(); return;
    case K_Q5_KP: f.template operator()<pl::Q5_KP>(); return;
    case K_F32L: f.template operator()<pl::F32L>(); return;
    default: fmt::dispatch(w.t->type, [&]<class FT>() { f.template operator()<pl::Raw<FT>>(); });
    }
}

// launch tuning per call: R rows per sub-group and sub-groups per work-group (from tools/bench_gemv)
struct Tune {
    int R = 4, sgw = 4;
    bool pre = false; // the preload kernels (if the layout has them)
    int mr = 0;       // M > 1: blocks of mr vectors per sub-group (GemvMR); 0 = GemvM
    bool il = false;  // GemvMR: interleave the chunk sums of all rows and vectors
};

// xl: x in lane order (xlane.hpp; M = 1, or vector blocks (tu.mr) with ldx = xlane_floats(cols); not the preload kernels)
inline sycl::event gemv_v(sycl::queue &q, const WView &w, const float *x, int ldx, float *y, int ldy, int M, Tune tu = {},
                          bool xl = false) {
    sycl::event e;
    int rows = (int)w.t->rows(), cols = (int)w.t->ne[0];
    if (cols % 32) throw std::runtime_error("gemv: row length not a multiple of 32: " + w.t->name);
    with_decoder(w, [&]<class D>() {
        if (M == 1) {
            int R = tu.R, sgw = tu.sgw;
            if constexpr (has_pre<D>) {
                if (tu.pre) {
                    if (xl) throw std::runtime_error("gemv: preload kernel with x in lane order");
                    int ncl = (cols / 32 + SG - 1) / SG;
                    auto gp = [&]<int RR, int NC>() {
                        int nsg = (rows + RR - 1) / RR, ngr = (nsg + sgw - 1) / sgw;
                        e = q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ngr * sgw * SG), sycl::range<1>((size_t)sgw * SG)),
                                           Gemv1P<D, RR, NC>{w.p, w.rb, rows, cols, x, y, sgw});
                    };
                    auto gr = [&]<int RR>() {
                        switch (ncl) {
                        case 1: gp.template operator()<RR, 1>(); break;
                        case 2: gp.template operator()<RR, 2>(); break;
                        case 3: gp.template operator()<RR, 3>(); break;
                        case 4: gp.template operator()<RR, 4>(); break;
                        case 5: gp.template operator()<RR, 5>(); break;
                        case 6: gp.template operator()<RR, 6>(); break;
                        default: throw std::runtime_error("gemv: preload kernel needs rows of at most 3072 values");
                        }
                    };
                    if (R == 1) gr.template operator()<1>();
                    else if (R == 2) gr.template operator()<2>();
                    else throw std::runtime_error("gemv: preload kernel R must be 1 or 2");
                    return;
                }
            }
            auto go = [&]<int RR>() {
                int nsg = (rows + RR - 1) / RR, ngr = (nsg + sgw - 1) / sgw;
                const sycl::nd_range<1> nr(sycl::range<1>((size_t)ngr * sgw * SG), sycl::range<1>((size_t)sgw * SG));
                if (xl) e = q.parallel_for(nr, Gemv1R<D, RR, true>{w.p, w.rb, rows, cols, x, y, sgw});
                else e = q.parallel_for(nr, Gemv1R<D, RR>{w.p, w.rb, rows, cols, x, y, sgw});
            };
            switch (R) {
            case 1: go.template operator()<1>(); break;
            case 2: go.template operator()<2>(); break;
            case 4: go.template operator()<4>(); break;
            case 8: go.template operator()<8>(); break;
            default: throw std::runtime_error("gemv: R must be 1, 2, 4 or 8");
            }
            return;
        }
        if (tu.mr) { // nb blocks of tu.mr vectors (M = nb * tu.mr), R rows per sub-group
            const int MM = tu.mr, nb = M / MM, R = tu.R, sgw = tu.sgw;
            if (M % MM) throw std::runtime_error("gemv: M not a multiple of the vector block");
            auto go = [&]<int RR, int MB>() {
                int nsg = (rows + RR - 1) / RR, ngr = (nsg + sgw - 1) / sgw;
                sycl::nd_range<2> nr2(sycl::range<2>((size_t)nb, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
                if (tu.il && xl) throw std::runtime_error("gemv: interleaved vector blocks with x in lane order");
                if (tu.il) e = q.parallel_for(nr2, GemvMR<D, RR, MB, true>{w.p, w.rb, rows, cols, x, ldx, y, ldy, sgw});
                else if (xl) e = q.parallel_for(nr2, GemvMR<D, RR, MB, false, true>{w.p, w.rb, rows, cols, x, ldx, y, ldy, sgw});
                else e = q.parallel_for(nr2, GemvMR<D, RR, MB>{w.p, w.rb, rows, cols, x, ldx, y, ldy, sgw});
            };
            auto gm = [&]<int RR>() {
                switch (MM) {
                case 1: go.template operator()<RR, 1>(); break;
                case 2: go.template operator()<RR, 2>(); break;
                case 3: go.template operator()<RR, 3>(); break;
                case 4: go.template operator()<RR, 4>(); break;
                case 5: go.template operator()<RR, 5>(); break;
                case 6: go.template operator()<RR, 6>(); break;
                case 7: go.template operator()<RR, 7>(); break;
                case 8: go.template operator()<RR, 8>(); break;
                default: throw std::runtime_error("gemv: vector block must be 1..8");
                }
            };
            if (R == 1) gm.template operator()<1>();
            else if (R == 2) gm.template operator()<2>();
            else if (R == 4) gm.template operator()<4>();
            else throw std::runtime_error("gemv: R must be 1, 2 or 4 with vector blocks");
            return;
        }
        sycl::nd_range<1> nr(sycl::range<1>((size_t)((rows + GEMV_ROWS - 1) / GEMV_ROWS) * GEMV_ROWS * SG),
                             sycl::range<1>(GEMV_ROWS * SG));
        switch (M) {
#define INK_M2(K) case K: e = q.parallel_for(nr, GemvM<D, K>{w.p, w.rb, rows, cols, x, ldx, y, ldy}); break;
            INK_M2(2) INK_M2(3) INK_M2(4) INK_M2(5) INK_M2(6) INK_M2(7) INK_M2(8)
#undef INK_M2
        default: throw std::runtime_error("gemv: M must be 1..8");
        }
    });
    return e;
}

inline sycl::event gemv_routed_v(sycl::queue &q, const WView &w, const int32_t *ids, int K, const float *x, int ldx,
                                 int x_div, float *y, int ldy, Tune tu = {}, bool xl = false) {
    sycl::event e;
    int cols = (int)w.t->ne[0], rows = (int)w.t->ne[1];
    size_t estride = w.rb * (size_t)rows;
    with_decoder(w, [&]<class D>() {
        int sgw = tu.sgw;
        if constexpr (has_pre<D>) {
            if (tu.pre) {
                if (xl) throw std::runtime_error("gemv_routed: preload kernel with x in lane order");
                int ncl = (cols / 32 + SG - 1) / SG;
                auto gp = [&]<int RR, int NC>() {
                    int nsg = (rows + RR - 1) / RR, ngr = (nsg + sgw - 1) / sgw;
                    sycl::nd_range<2> nr(sycl::range<2>((size_t)K, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
                    e = q.parallel_for(nr, GemvRoutedP<D, RR, NC>{w.p, w.rb, estride, rows, cols, ids, x, ldx, x_div, y, ldy, sgw});
                };
                auto gr = [&]<int RR>() {
                    switch (ncl) {
                    case 3: gp.template operator()<RR, 3>(); break;
                    case 5: gp.template operator()<RR, 5>(); break;
                    default: throw std::runtime_error("gemv_routed: preload kernel for rows of 1152 or 2304 values only");
                    }
                };
                if (tu.R == 1) gr.template operator()<1>();
                else if (tu.R == 2) gr.template operator()<2>();
                else throw std::runtime_error("gemv_routed: preload kernel R must be 1 or 2");
                return;
            }
        }
        auto go = [&]<int RR>() {
            int nsg = (rows + RR - 1) / RR, ngr = (nsg + sgw - 1) / sgw;
            sycl::nd_range<2> nr(sycl::range<2>((size_t)K, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
            if (xl) e = q.parallel_for(nr, GemvRoutedR<D, RR, true>{w.p, w.rb, estride, rows, cols, ids, x, ldx, x_div, y, ldy, sgw});
            else e = q.parallel_for(nr, GemvRoutedR<D, RR>{w.p, w.rb, estride, rows, cols, ids, x, ldx, x_div, y, ldy, sgw});
        };
        switch (tu.R) {
        case 1: go.template operator()<1>(); break;
        case 2: go.template operator()<2>(); break;
        case 4: go.template operator()<4>(); break;
        case 8: go.template operator()<8>(); break;
        default: throw std::runtime_error("gemv_routed: R must be 1, 2, 4 or 8");
        }
    });
    return e;
}

// launch GemvPair: nslot slots, rows per matrix, A/B views of the same layout; sgw sub-groups per work-group
template <class Op> inline sycl::event gemv_pair(sycl::queue &q, const WView &a, const uint8_t *B, size_t estride, int rows,
                                                 const int32_t *ids, int nslot, const float *x, int ldx, int xdiv, Op op,
                                                 int sgw = 2, bool xl = false) {
    sycl::event e;
    int cols = (int)a.t->ne[0];
    with_decoder(a, [&]<class D>() {
        int ngr = (rows + sgw - 1) / sgw;
        sycl::nd_range<2> nr(sycl::range<2>((size_t)nslot, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
        if (xl) e = q.parallel_for(nr, GemvPair<D, Op, true>{a.p, B, a.rb, estride, rows, cols, ids, x, ldx, xdiv, op, sgw});
        else e = q.parallel_for(nr, GemvPair<D, Op>{a.p, B, a.rb, estride, rows, cols, ids, x, ldx, xdiv, op, sgw});
    });
    return e;
}

// regroup a tensor of the file layout into a planar layout: src (file) -> dst (planar); returns the kind
inline int planar_kind(const Tensor &t) {
    switch (t.type) {
    case G_Q8_0: return K_Q8_0P;
    case G_NVFP4: return K_NVFP4P;
    case G_Q6_K: return K_Q6_KP;
    default: return K_RAW;
    }
}
inline size_t planar_stride(const Tensor &t) {
    switch (t.type) {
    case G_Q6_K: return pl::Q6_KP::stride(t.row_bytes());
    default: return t.row_bytes();
    }
}
inline sycl::event planar_repack(sycl::queue &q, const Tensor &t, const uint8_t *src, uint8_t *dst) {
    size_t nrows = (size_t)t.rows();
    int cols = (int)t.ne[0];
    switch (t.type) {
    case G_Q8_0: return pl::repack<pl::Q8_0P>(q, src, t.row_bytes(), dst, planar_stride(t), cols, nrows);
    case G_NVFP4: return pl::repack<pl::NVFP4P>(q, src, t.row_bytes(), dst, planar_stride(t), cols, nrows);
    case G_Q6_K: return pl::repack<pl::Q6_KP>(q, src, t.row_bytes(), dst, planar_stride(t), cols, nrows);
    default: throw std::runtime_error("planar_repack: unsupported type");
    }
}

// decode copies (planar.hpp) of the expert formats of layers 20-23: kind, row stride, repack (K_RAW: none)
inline int dec_kind(const Tensor &t) {
    switch (t.type) {
    case G_Q5_0: return K_Q5_0P;
    case G_IQ4_NL: return K_IQ4_NLP;
    case G_IQ4_XS: return K_IQ4_XSP;
    case G_Q4_K: return K_Q4_KP;
    case G_Q5_K: return K_Q5_KP;
    default: return K_RAW;
    }
}
inline size_t dec_stride(const Tensor &t) {
    const int cols = (int)t.ne[0];
    switch (t.type) {
    case G_Q5_0: return pl::Q5_0P::stride(cols);
    case G_IQ4_NL: return pl::IQ4_NLP::stride(cols);
    case G_IQ4_XS: return pl::IQ4_XSP::stride(cols);
    case G_Q4_K: return pl::Q4_KP::stride(cols);
    case G_Q5_K: return pl::Q5_KP::stride(cols);
    default: return t.row_bytes();
    }
}
// decode copies on (INK_DEC=0: the few-token kernels read the file layout); dec_target: an expert tensor that gets one
inline bool dec_on() { return !std::getenv("INK_DEC") || std::atoi(std::getenv("INK_DEC")); }
// q6k_target: a Q6_K weight (planar copy with a padded row stride); the upload can leave it in the file so that only
// the planar copy goes on the card (planarize fetches it through a scratch buffer: ~0.45 GB less card memory)
inline bool q6k_target(const Tensor &t) { return t.type == G_Q6_K && t.name != "token_embd.weight"; }
inline bool dec_target(const Tensor &t) {
    const std::string sfx = "_exps.weight";
    return dec_kind(t) != K_RAW && t.name.size() > sfx.size() && t.name.compare(t.name.size() - sfx.size(), sfx.size(), sfx) == 0;
}
inline sycl::event dec_repack(sycl::queue &q, const Tensor &t, const uint8_t *src, uint8_t *dst) {
    const size_t nrows = (size_t)t.rows(), rb = dec_stride(t);
    const int cols = (int)t.ne[0];
    switch (t.type) {
    case G_Q5_0: return pl::repack<pl::Q5_0P>(q, src, t.row_bytes(), dst, rb, cols, nrows);
    case G_IQ4_NL: return pl::repack<pl::IQ4_NLP>(q, src, t.row_bytes(), dst, rb, cols, nrows);
    case G_IQ4_XS: return pl::repack<pl::IQ4_XSP>(q, src, t.row_bytes(), dst, rb, cols, nrows);
    case G_Q4_K: return pl::repack<pl::Q4_KP>(q, src, t.row_bytes(), dst, rb, cols, nrows);
    case G_Q5_K: return pl::repack<pl::Q5_KP>(q, src, t.row_bytes(), dst, rb, cols, nrows);
    default: throw std::runtime_error("dec_repack: unsupported type");
    }
}
// regroup every Q8_0 / NVFP4 / Q6_K weight used by the products into its planar layout (not the token embedding,
// which get_rows reads in the file layout). Q8_0 and NVFP4 in place (through a scratch copy on the card); Q6_K into a
// new buffer with a padded row stride (its file copy stays in the arena). Returns every tensor's view. own: tensors the
// caller left out of the upload and lays out itself (their view has no data, only the tensor's shape)
inline std::map<std::string, WView> planarize(Device &d, const GGUF &g, Weights &w, bool verbose = true,
                                              const std::function<bool(const Tensor &)> &own = {}) {
    std::map<std::string, WView> v;
    size_t scratch_bytes = 0;
    for (auto &t : g.tensors) {
        if (!w.has(t.name)) { // left in the file: decode copy below, or the caller's own layout
            if (own && own(t)) v[t.name] = WView{&t, nullptr, t.row_bytes(), K_RAW};
            continue;
        }
        v[t.name] = WView{&t, w[t.name], t.row_bytes(), K_RAW};
        if (t.name != "token_embd.weight" && planar_kind(t) != K_RAW && t.type != G_Q6_K)
            scratch_bytes = std::max<size_t>(scratch_bytes, t.bytes);
    }
    double t0 = now_s();
    uint8_t *scratch = scratch_bytes ? d.alloc<uint8_t>(scratch_bytes) : nullptr;
    size_t n = 0, extra = 0;
    for (auto &t : g.tensors) {
        int k = planar_kind(t);
        if (k == K_RAW || t.name == "token_embd.weight" || !w.has(t.name)) continue;
        uint8_t *p = w[t.name];
        WView &e = v[t.name];
        if (t.type == G_Q6_K) {
            size_t rb = planar_stride(t);
            uint8_t *dst = d.alloc<uint8_t>(rb * (size_t)t.rows());
            planar_repack(d.q, t, p, dst).wait();
            e.p = dst; e.rb = rb;
            extra += rb * (size_t)t.rows();
        } else {
            d.q.memcpy(scratch, p, t.bytes).wait();
            planar_repack(d.q, t, scratch, p).wait();
        }
        e.kind = k;
        ++n;
    }
    if (scratch) d.release(scratch);
    // tensors the upload left in the file (Weights::upload skip = dec_target): only their decode copy goes on the card
    size_t fb = 0, nd = 0, dec_bytes = 0;
    for (auto &t : g.tensors)
        if (!w.has(t.name) && !(own && own(t))) {
            if (!dec_target(t) && !q6k_target(t))
                throw std::runtime_error("planarize: " + t.name + " is not on the card and has no decode copy");
            fb = std::max<size_t>(fb, t.bytes);
        }
    if (fb) {
        uint8_t *file = d.alloc<uint8_t>(fb);
        for (auto &t : g.tensors) {
            if (w.has(t.name) || (own && own(t))) continue;
            if (q6k_target(t)) { // the planar copy only (the same bytes as from the arena copy)
                const size_t rb = planar_stride(t);
                uint8_t *dst = d.alloc<uint8_t>(rb * (size_t)t.rows());
                w.fetch(d, g, t, file);
                planar_repack(d.q, t, file, dst).wait();
                v[t.name] = WView{&t, dst, rb, K_Q6_KP};
                extra += rb * (size_t)t.rows();
                ++n;
                continue;
            }
            const size_t rb = dec_stride(t);
            uint8_t *dst = d.alloc<uint8_t>(rb * (size_t)t.rows());
            w.fetch(d, g, t, file);
            dec_repack(d.q, t, file, dst).wait();
            v[t.name] = WView{&t, dst, rb, dec_kind(t)};
            ++nd;
            dec_bytes += rb * (size_t)t.rows();
        }
        d.release(file);
    }
    if (verbose)
        std::fprintf(stderr, "[ink] planar layout for %zu tensors, decode copies only for %zu (%.2f GB), %.2f s (%.2f GB extra for Q6_K rows)\n",
                     n, nd, dec_bytes / 1e9, now_s() - t0, extra / 1e9);
    return v;
}

} // namespace ink
