// multi.hpp: several one-vector matrix products in one launch (the matrices that read the same attention input).
// Each sub-group finds its job (matrix) in a small table and runs gemv1_rows for it, the same code as Gemv1R, so
// results equal one launch per matrix bit for bit. Decoders: Q8_0P, Q6_KP, BF16, Q5_K (the attention matrices).
#pragma once
#include "gemv2.hpp"

namespace ink {

struct GJob { const uint8_t *W; size_t rb; int rows, cols, kind, type, R; const float *x; float *y; int sg0; };
constexpr int MULTI_MAX = 8;
struct MultiJobs { GJob j[MULTI_MAX]; int nj = 0, nsg = 0; };

inline bool multi_ok(const WView &w) {
    if (w.kind == K_Q8_0P || w.kind == K_Q6_KP) return true;
    return w.kind == K_RAW && (w.t->type == G_BF16 || w.t->type == G_Q5_K || w.t->type == G_F32);
}
// add a job; R = rows per sub-group (1 or 2)
inline void multi_add(MultiJobs &m, const WView &w, const float *x, float *y, int R) {
    if (m.nj >= MULTI_MAX) throw std::runtime_error("multi: too many jobs");
    GJob &g = m.j[m.nj++];
    g.W = w.p; g.rb = w.rb; g.rows = (int)w.t->rows(); g.cols = (int)w.t->ne[0]; g.kind = w.kind; g.type = (int)w.t->type;
    g.R = R; g.x = x; g.y = y; g.sg0 = m.nsg;
    m.nsg += (g.rows + R - 1) / R;
}
struct GemvMulti {
    MultiJobs m;
    int sgw;
    template <class D> static void run(sycl::sub_group sg, const GJob &g, int r0) {
        if (g.R == 1) gemv1_rows<D, 1>(sg, g.W, g.rb, g.rows, g.cols, g.x, g.y, r0);
        else gemv1_rows<D, 2>(sg, g.W, g.rb, g.rows, g.cols, g.x, g.y, r0);
    }
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<1> it) const {
        auto sg = it.get_sub_group();
        const int s = (int)it.get_group(0) * sgw + (int)sg.get_group_linear_id();
        if (s >= m.nsg) return;
        int k = 0;
        for (int i = 1; i < MULTI_MAX; ++i) if (i < m.nj && m.j[i].sg0 <= s) k = i;
        const GJob &g = m.j[k];
        const int r0 = (s - g.sg0) * g.R;
        switch (g.kind) {
        case K_Q8_0P: run<pl::Q8_0P>(sg, g, r0); break;
        case K_Q6_KP: run<pl::Q6_KP>(sg, g, r0); break;
        default:
            if (g.type == G_BF16) run<pl::Raw<fmt::F<G_BF16>>>(sg, g, r0);
            else if (g.type == G_F32) run<pl::Raw<fmt::F<G_F32>>>(sg, g, r0);
            else run<pl::Raw<fmt::F<G_Q5_K>>>(sg, g, r0);
        }
    }
};
inline sycl::event gemv_multi(sycl::queue &q, const MultiJobs &m, int sgw = 2) {
    int ngr = (m.nsg + sgw - 1) / sgw;
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ngr * sgw * SG), sycl::range<1>((size_t)sgw * SG)), GemvMulti{m, sgw});
}

// the control outputs of several modules in one launch (engine control(), the gain and forget products with CtlOp):
// one row per sub-group, gemv_pair_row as GemvPair; F32 weights in the file layout (loop_gain / loop_forget)
struct CJob { const uint8_t *A, *B; size_t rb; int rows, cols; const float *x; CtlOp op; int sg0; };
struct CtlJobs { CJob j[4]; int nj = 0, nsg = 0; };
inline bool ctl_multi_ok(const WView &a, const WView &b) {
    return a.kind == K_RAW && b.kind == K_RAW && a.t->type == G_F32 && b.t->type == G_F32 && a.rb == b.rb;
}
inline void ctl_add(CtlJobs &m, const WView &a, const WView &b, const float *x, CtlOp op) {
    if (m.nj >= 4) throw std::runtime_error("ctl_multi: too many jobs");
    CJob &g = m.j[m.nj++];
    g.A = a.p; g.B = b.p; g.rb = a.rb; g.rows = (int)a.t->rows(); g.cols = (int)a.t->ne[0]; g.x = x; g.op = op; g.sg0 = m.nsg;
    m.nsg += g.rows;
}
struct CtlMulti {
    CtlJobs m;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<1> it) const {
        auto sg = it.get_sub_group();
        const int s = (int)it.get_group(0) * sgw + (int)sg.get_group_linear_id();
        if (s >= m.nsg) return;
        int k = 0;
        for (int i = 1; i < 4; ++i) if (i < m.nj && m.j[i].sg0 <= s) k = i;
        const CJob &g = m.j[k];
        const int r = s - g.sg0;
        float va, vb;
        gemv_pair_row<pl::Raw<fmt::F<G_F32>>>(sg, g.A + (size_t)r * g.rb, g.B + (size_t)r * g.rb, g.cols, g.x, va, vb);
        if (sg.get_local_linear_id() == 0) g.op(0, r, va, vb);
    }
};
// the same products with one work-item per row (rows of at most 16 chunks of 32, e.g. the 64 values of loop_gain):
// the work-item computes the 16 virtual lanes' sums of gemv_pair_row (lane l: chunks l, l+16, ...; lanes past the
// last chunk hold +0) and their xor butterfly (offsets 8, 4, 2, 1) in registers, the same additions as sg_sum
struct CtlRows {
    CtlJobs m;
    void operator()(sycl::nd_item<1> it) const {
        const int s = (int)it.get_global_id(0);
        if (s >= m.nsg) return;
        int k = 0;
        for (int i = 1; i < 4; ++i) if (i < m.nj && m.j[i].sg0 <= s) k = i;
        const CJob &g = m.j[k];
        const int r = s - g.sg0, nc = g.cols / 32;
        using D = pl::Raw<fmt::F<G_F32>>;
        float va[SG], vb[SG];
        for (int l = 0; l < SG; ++l) { va[l] = 0.0f; vb[l] = 0.0f; }
        for (int c = 0; c < nc; ++c) {
            float xs[32];
            load_x32(g.x + 32 * c, xs);
            for (int j = 0; j < 2; ++j) {
                float o[32];
                D::decode32((j ? g.B : g.A) + (size_t)r * g.rb, g.cols, c, o);
                float sm = 0.0f;
                for (int i = 0; i < 32; ++i) sm += o[i] * xs[i];
                if (j) vb[c % SG] += sm; else va[c % SG] += sm;
            }
        }
        for (int off = SG / 2; off > 0; off >>= 1) {
            float ta[SG], tb[SG];
            for (int l = 0; l < SG; ++l) { ta[l] = va[l] + va[l ^ off]; tb[l] = vb[l] + vb[l ^ off]; }
            for (int l = 0; l < SG; ++l) { va[l] = ta[l]; vb[l] = tb[l]; }
        }
        g.op(0, r, va[0], vb[0]);
    }
};
inline bool ctl_rows_ok(const CtlJobs &m) {
    for (int i = 0; i < m.nj; ++i) if (m.j[i].cols > 32 * SG) return false;
    return true;
}
inline sycl::event ctl_rows(sycl::queue &q, const CtlJobs &m, int wg = 64) {
    int ngr = (m.nsg + wg - 1) / wg;
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ngr * wg), sycl::range<1>((size_t)wg)), CtlRows{m});
}
inline sycl::event ctl_multi(sycl::queue &q, const CtlJobs &m, int sgw = 2) {
    int ngr = (m.nsg + sgw - 1) / sgw;
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ngr * sgw * SG), sycl::range<1>((size_t)sgw * SG)), CtlMulti{m, sgw});
}

} // namespace ink
