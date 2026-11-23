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
#include <map>

namespace ink {

inline void load_x32(const float *xv, float *xs) {
    using V = sycl::vec<float, 4>;
    for (int i = 0; i < 8; ++i) {
        V v = *(const V *)(xv + 4 * i);
        xs[4 * i] = v[0]; xs[4 * i + 1] = v[1]; xs[4 * i + 2] = v[2]; xs[4 * i + 3] = v[3];
    }
}

template <class D, int R> struct Gemv1R {
    const uint8_t *W; size_t rb; int rows, cols;
    const float *x;
    float *y;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<1> it) const {
        auto sg = it.get_sub_group();
        int r0 = ((int)it.get_group(0) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        float acc[R];
        for (int k = 0; k < R; ++k) acc[k] = 0.0f;
        const int nc = cols / 32;
        for (int c = lane; c < nc; c += SG) {
            float xs[32];
            load_x32(x + 32 * c, xs);
            for (int k = 0; k < R; ++k) {
                if (r0 + k >= rows) break;
                float o[32];
                D::decode32(W + (size_t)(r0 + k) * rb, cols, c, o);
                float s = 0.0f;
                for (int i = 0; i < 32; ++i) s += o[i] * xs[i];
                acc[k] += s;
            }
        }
        for (int k = 0; k < R; ++k) {
            float v = sg_sum(sg, acc[k]);
            if (lane == 0 && r0 + k < rows) y[r0 + k] = v;
        }
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

// routed: y[k*ldy + r] = W_{ids[k]} row r . x row (xdiv ? k / xdiv : 0); group(0) = k, group(1) = block of sgw*R rows
template <class D, int R> struct GemvRoutedR {
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
            load_x32(xv0 + 32 * c, xs);
            for (int j = 0; j < R; ++j) {
                if (r0 + j >= rows) break;
                float o[32];
                D::decode32(base + (size_t)(r0 + j) * rb, cols, c, o);
                float s = 0.0f;
                for (int i = 0; i < 32; ++i) s += o[i] * xs[i];
                acc[j] += s;
            }
        }
        for (int j = 0; j < R; ++j) {
            float v = sg_sum(sg, acc[j]);
            if (lane == 0 && r0 + j < rows) y[(size_t)k * ldy + r0 + j] = v;
        }
    }
};

// a weight as the kernels see it: layout kind, pointer, row stride
enum Kind { K_RAW = 0, K_Q8_0P = 1, K_NVFP4P = 2, K_Q6_KP = 3 };
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
    default: fmt::dispatch(w.t->type, [&]<class FT>() { f.template operator()<pl::Raw<FT>>(); });
    }
}

// launch tuning per call: R rows per sub-group and sub-groups per work-group (from tools/bench_gemv)
struct Tune { int R = 4, sgw = 4; };

inline sycl::event gemv_v(sycl::queue &q, const WView &w, const float *x, int ldx, float *y, int ldy, int M, Tune tu = {}) {
    sycl::event e;
    int rows = (int)w.t->rows(), cols = (int)w.t->ne[0];
    if (cols % 32) throw std::runtime_error("gemv: row length not a multiple of 32: " + w.t->name);
    with_decoder(w, [&]<class D>() {
        if (M == 1) {
            int R = tu.R, sgw = tu.sgw;
            auto go = [&]<int RR>() {
                int nsg = (rows + RR - 1) / RR, ngr = (nsg + sgw - 1) / sgw;
                e = q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ngr * sgw * SG), sycl::range<1>((size_t)sgw * SG)),
                                   Gemv1R<D, RR>{w.p, w.rb, rows, cols, x, y, sgw});
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
                                 int x_div, float *y, int ldy, Tune tu = {}) {
    sycl::event e;
    int cols = (int)w.t->ne[0], rows = (int)w.t->ne[1];
    size_t estride = w.rb * (size_t)rows;
    with_decoder(w, [&]<class D>() {
        int sgw = tu.sgw;
        auto go = [&]<int RR>() {
            int nsg = (rows + RR - 1) / RR, ngr = (nsg + sgw - 1) / sgw;
            sycl::nd_range<2> nr(sycl::range<2>((size_t)K, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
            e = q.parallel_for(nr, GemvRoutedR<D, RR>{w.p, w.rb, estride, rows, cols, ids, x, ldx, x_div, y, ldy, sgw});
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

// regroup every Q8_0 / NVFP4 / Q6_K weight used by the products into its planar layout (not the token embedding,
// which get_rows reads in the file layout). Q8_0 and NVFP4 in place (through a scratch copy on the card); Q6_K into a
// new buffer with a padded row stride (its file copy stays in the arena). Returns every tensor's view.
inline std::map<std::string, WView> planarize(Device &d, const GGUF &g, Weights &w, bool verbose = true) {
    std::map<std::string, WView> v;
    size_t scratch_bytes = 0;
    for (auto &t : g.tensors) {
        v[t.name] = WView{&t, w[t.name], t.row_bytes(), K_RAW};
        if (t.name != "token_embd.weight" && planar_kind(t) != K_RAW && t.type != G_Q6_K)
            scratch_bytes = std::max<size_t>(scratch_bytes, t.bytes);
    }
    double t0 = now_s();
    uint8_t *scratch = scratch_bytes ? d.alloc<uint8_t>(scratch_bytes) : nullptr;
    size_t n = 0, extra = 0;
    for (auto &t : g.tensors) {
        int k = planar_kind(t);
        if (k == K_RAW || t.name == "token_embd.weight") continue;
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
    if (verbose)
        std::fprintf(stderr, "[ink] planar layout for %zu tensors in %.2f s (%.2f GB extra for Q6_K rows)\n", n, now_s() - t0,
                     extra / 1e9);
    return v;
}

} // namespace ink
