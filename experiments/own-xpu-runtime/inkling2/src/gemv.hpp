// gemv.hpp: y[m][r] = sum_k W[r][k] * x[m][k] for quantized W (formats.hpp) and F32 x, M vectors at once.
// One sub-group of 16 lanes per row; lane l takes the 32-value chunks c = l, l + 16, ...; each chunk is decoded once
// and used for all M vectors. Sums: per lane in chunk order, each chunk's 32 products summed in index order, then a
// fixed xor butterfly over the 16 lanes. The order depends only on the row length, so a result is the same bit for
// bit in every run and for every M (a vector's sum does not depend on the other vectors in the call).
#pragma once
#include "device.hpp"
#include "formats.hpp"

namespace ink {

constexpr int SG = 16;      // sub-group size
constexpr int GEMV_ROWS = 8; // rows (sub-groups) per work-group

inline float sg_sum(sycl::sub_group sg, float v) {
    for (int o = SG / 2; o > 0; o >>= 1) v += sycl::permute_group_by_xor(sg, v, o);
    return v;
}

// W: rows x cols, row stride rb bytes; x: M x ldx floats; y: M x ldy floats (y[m*ldy + r])
// expert variant: W of expert e at W + e * estride; experts[m] picks the matrix per vector (nullptr: same for all)
template <class FT, int M> struct GemvKernel {
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
            FT::decode32(row, c, o);
            for (int m = 0; m < M; ++m) {
                const float *xv = x + (size_t)m * ldx + 32 * c;
                float s = 0.0f;
                for (int i = 0; i < 32; ++i) s += o[i] * xv[i];
                acc[m] += s;
            }
        }
        for (int m = 0; m < M; ++m) {
            float v = sg_sum(sg, acc[m]);
            if (lane == 0) y[(size_t)m * ldy + r] = v;
        }
    }
};

// launch: M in 1..8 picked at run time
template <class FT> sycl::event gemv_t(sycl::queue &q, const uint8_t *W, size_t rb, int rows, int cols, const float *x,
                                       int ldx, float *y, int ldy, int M) {
    sycl::nd_range<1> nr(sycl::range<1>((size_t)((rows + GEMV_ROWS - 1) / GEMV_ROWS) * GEMV_ROWS * SG),
                         sycl::range<1>(GEMV_ROWS * SG));
    switch (M) {
#define INK_M(K) case K: return q.parallel_for(nr, GemvKernel<FT, K>{W, rb, rows, cols, x, ldx, y, ldy});
        INK_M(1) INK_M(2) INK_M(3) INK_M(4) INK_M(5) INK_M(6) INK_M(7) INK_M(8)
#undef INK_M
    default: throw std::runtime_error("gemv: M must be 1..8");
    }
}

// Routed (expert) form: for k in [0, K): y[k*ldy + r] = sum_c W_{ids[k]}[r][c] * x[(xk ? k : 0)*ldx + c], with
// expert e's matrix at W + e * estride and ids read on the card (no host round trip). Same per-row sum order as
// GemvKernel, so a routed row equals the plain kernel's row for the same expert and vector, bit for bit.
template <class FT> struct GemvRoutedKernel {
    const uint8_t *W; size_t rb, estride; int rows, cols;
    const int32_t *ids;
    const float *x; int ldx; bool xk;
    float *y; int ldy;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        auto sg = it.get_sub_group();
        int k = (int)it.get_group(0);
        int r = (int)it.get_group(1) * GEMV_ROWS + (int)sg.get_group_linear_id();
        if (r >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        const uint8_t *row = W + (size_t)ids[k] * estride + (size_t)r * rb;
        const float *xv0 = x + (size_t)(xk ? k : 0) * ldx;
        float acc = 0.0f;
        const int nc = cols / 32;
        for (int c = lane; c < nc; c += SG) {
            float o[32];
            FT::decode32(row, c, o);
            const float *xv = xv0 + 32 * c;
            float s = 0.0f;
            for (int i = 0; i < 32; ++i) s += o[i] * xv[i];
            acc += s;
        }
        float v = sg_sum(sg, acc);
        if (lane == 0) y[(size_t)k * ldy + r] = v;
    }
};

// a 3-D expert tensor t (ne = [cols, rows, n_expert]); K vectors, one expert id each
inline sycl::event gemv_routed(sycl::queue &q, const Tensor &t, const uint8_t *W, const int32_t *ids, int K,
                               const float *x, int ldx, bool x_per_k, float *y, int ldy) {
    sycl::event e;
    int cols = (int)t.ne[0], rows = (int)t.ne[1];
    size_t rb = t.row_bytes(), estride = rb * (size_t)rows;
    sycl::nd_range<2> nr(sycl::range<2>((size_t)K, (size_t)((rows + GEMV_ROWS - 1) / GEMV_ROWS) * GEMV_ROWS * SG),
                         sycl::range<2>(1, GEMV_ROWS * SG));
    fmt::dispatch(t.type, [&]<class FT>() {
        e = q.parallel_for(nr, GemvRoutedKernel<FT>{W, rb, estride, rows, cols, ids, x, ldx, x_per_k, y, ldy});
    });
    return e;
}

// y = W x for a weight tensor of any supported type; x has M rows of t.ne[0] floats
inline sycl::event gemv(sycl::queue &q, const Tensor &t, const uint8_t *W, const float *x, int ldx, float *y, int ldy,
                        int M = 1) {
    sycl::event e;
    int rows = (int)t.rows(), cols = (int)t.ne[0];
    if (cols % 32) throw std::runtime_error("gemv: row length not a multiple of 32: " + t.name);
    fmt::dispatch(t.type, [&]<class FT>() { e = gemv_t<FT>(q, W, t.row_bytes(), rows, cols, x, ldx, y, ldy, M); });
    return e;
}

} // namespace ink
