// multi.hpp: several one-vector matrix products in one launch (the matrices that read the same attention input).
// Each sub-group finds its job (matrix) in a small table and runs gemv1_rows for it, the same code as Gemv1R, so
// results equal one launch per matrix bit for bit. Decoders: Q8_0P, Q6_KP, BF16, Q5_K (the attention matrices), F32 and
// certified F32 halfwords (K_F32H, the loop down products: a launch with such a job takes the H = true kernels, so the
// kernels of launches without one are the ones they were).
#pragma once
#include "gemv2.hpp"

namespace ink {

struct GJob { const uint8_t *W; size_t rb; int rows, cols, kind, type, R; const float *x; float *y; int sg0, ldx, ldy; };
constexpr int MULTI_MAX = 8;
struct MultiJobs { GJob j[MULTI_MAX]; int nj = 0, nsg = 0; };

inline bool multi_ok(const WView &w) {
    if (w.kind == K_Q8_0P || w.kind == K_Q6_KP || w.kind == K_F32H) return true;
    return w.kind == K_RAW && (w.t->type == G_BF16 || w.t->type == G_Q5_K || w.t->type == G_F32);
}
// add a job; R = rows per sub-group (1 or 2); ldx / ldy: vector strides of x and y (gemv_multi_m, several vectors)
inline void multi_add(MultiJobs &m, const WView &w, const float *x, float *y, int R, int ldx = 0, int ldy = 0) {
    if (m.nj >= MULTI_MAX) throw std::runtime_error("multi: too many jobs");
    GJob &g = m.j[m.nj++];
    g.W = w.p; g.rb = w.rb; g.rows = (int)w.t->rows(); g.cols = (int)w.t->ne[0]; g.kind = w.kind; g.type = (int)w.t->type;
    g.R = R; g.x = x; g.y = y; g.sg0 = m.nsg; g.ldx = ldx; g.ldy = ldy;
    m.nsg += (g.rows + R - 1) / R;
}
inline bool multi_has_half(const MultiJobs &m) {
    for (int i = 0; i < m.nj; ++i) if (m.j[i].kind == K_F32H) return true;
    return false;
}
// the job of sub-group s, copied out with constant indexes (unrolled). Taken by reference with a run-time index, the
// pointers lose what gptr gives them: the one-token attention inputs ran at 44 us instead of 41
inline GJob pick_job(const MultiJobs &m, int s) {
    GJob g = m.j[0];
#pragma unroll
    for (int i = 1; i < MULTI_MAX; ++i)
        if (i < m.nj && m.j[i].sg0 <= s) g = m.j[i];
    return g;
}
template <bool H = false> struct GemvMulti { // H: some job is K_F32H
    MultiJobs m;
    int sgw;
    template <class D> static void run(sycl::sub_group sg, const GJob &g, int r0) {
        if (g.R == 1) gemv1_rows<D, 1>(sg, gptr(g.W), g.rb, g.rows, g.cols, gptr(g.x), gptr(g.y), r0);
        else gemv1_rows<D, 2>(sg, gptr(g.W), g.rb, g.rows, g.cols, gptr(g.x), gptr(g.y), r0);
    }
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<1> it) const {
        auto sg = it.get_sub_group();
        const int s = (int)it.get_group(0) * sgw + (int)sg.get_group_linear_id();
        if (s >= m.nsg) return;
        const GJob g = pick_job(m, s);
        const int r0 = (s - g.sg0) * g.R;
        if constexpr (H) if (g.kind == K_F32H) { run<pl::F32H>(sg, g, r0); return; }
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
    const sycl::nd_range<1> nr(sycl::range<1>((size_t)ngr * sgw * SG), sycl::range<1>((size_t)sgw * SG));
    if (multi_has_half(m)) return q.parallel_for(nr, GemvMulti<true>{m, sgw});
    return q.parallel_for(nr, GemvMulti<>{m, sgw});
}
// rows r0..r0+R-1 times M vectors (vector m at x + m * ldx, lane order if XL) into y + m * ldy (one sub-group): every
// (row, vector) sum is gemv1_rows' (chunks l, l+16, ... per lane, each chunk's 32 products in index order, the lane
// sums in chunk order, the same butterfly), so a step of M tokens gives each token the one-token values bit for bit.
// Rows past the end read the last row (no branch around the reads) and are not stored.
template <class D, int R, int M, bool XL>
[[clang::always_inline]] inline void gemvM_rows(sycl::sub_group sg, const uint8_t *W, size_t rb, int rows, int cols, const float *x,
                                                int ldx, float *y, int ldy, int r0) {
    const int lane = (int)sg.get_local_linear_id();
    float acc[R][M];
#pragma unroll
    for (int k = 0; k < R; ++k)
#pragma unroll
        for (int m = 0; m < M; ++m) acc[k][m] = 0.0f;
    const int nc = cols / 32;
    for (int c = lane; c < nc; c += SG) {
        float o[R][32];
#pragma unroll
        for (int k = 0; k < R; ++k) D::decode32(W + (size_t)sycl::min(r0 + k, rows - 1) * rb, cols, c, o[k]);
#pragma unroll
        for (int m = 0; m < M; ++m) {
            float xs[32];
            load_xc(x + (size_t)m * ldx, c, xs, XL);
#pragma unroll
            for (int k = 0; k < R; ++k) {
                float s = 0.0f;
                for (int i = 0; i < 32; ++i) s = mac(s, o[k][i], xs[i]);
                acc[k][m] += s;
            }
        }
    }
#pragma unroll
    for (int k = 0; k < R; ++k)
#pragma unroll
        for (int m = 0; m < M; ++m) {
            const float v = sg_sum(sg, acc[k][m]);
            if (lane == 0 && r0 + k < rows) y[(size_t)m * ldy + r0 + k] = v;
        }
}
// GemvMulti for M vectors (2..8; 5-8 one row per sub-group: two rows were level for the output layer at 7 vectors,
// bench_gemv card 3 1,224-1,285 vs 1,219-1,336 us, and spill): the attention input matrices of a step of a few tokens
// in one launch. The job's
// pointers come from an array chosen at run time, so the compiler sees them as generic; gptr (gemv.hpp) makes the
// loads global (without it M = 4, R 2 took 26.4 us, with it 20.7)
// BIG: the large register file (256 registers per thread, half the threads per core) and 1, 2 or 4 rows per sub-group
// for any M: each x chunk loaded once serves R rows (5-8 vectors at one row per sub-group load 8 floats of x per
// weight). The (row, vector) sums are gemvM_rows' for any R, so the values do not change.
template <int M, bool XL, bool BIG = false, bool H = false> struct GemvMultiM { // H: some job is K_F32H
    MultiJobs m;
    int sgw;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        if constexpr (BIG) return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<256>};
        else return sycl::ext::oneapi::experimental::properties{};
    }
    template <class D> static void run(sycl::sub_group sg, const GJob &g, int r0) {
        const uint8_t *W = gptr(g.W);
        const float *x = gptr(g.x);
        float *y = gptr(g.y);
        if constexpr (BIG) {
            if (g.R == 4) gemvM_rows<D, 4, M, XL>(sg, W, g.rb, g.rows, g.cols, x, g.ldx, y, g.ldy, r0);
            else if (g.R == 2) gemvM_rows<D, 2, M, XL>(sg, W, g.rb, g.rows, g.cols, x, g.ldx, y, g.ldy, r0);
            else gemvM_rows<D, 1, M, XL>(sg, W, g.rb, g.rows, g.cols, x, g.ldx, y, g.ldy, r0);
        } else if constexpr (M > 4) gemvM_rows<D, 1, M, XL>(sg, W, g.rb, g.rows, g.cols, x, g.ldx, y, g.ldy, r0);
        else if (g.R == 1) gemvM_rows<D, 1, M, XL>(sg, W, g.rb, g.rows, g.cols, x, g.ldx, y, g.ldy, r0);
        else gemvM_rows<D, 2, M, XL>(sg, W, g.rb, g.rows, g.cols, x, g.ldx, y, g.ldy, r0);
    }
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<1> it) const {
        auto sg = it.get_sub_group();
        const int s = (int)it.get_group(0) * sgw + (int)sg.get_group_linear_id();
        if (s >= m.nsg) return;
        const GJob g = pick_job(m, s);
        const int r0 = (s - g.sg0) * g.R;
        if constexpr (H) if (g.kind == K_F32H) { run<pl::F32H>(sg, g, r0); return; }
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
inline sycl::event gemv_multi_m(sycl::queue &q, const MultiJobs &m, int M, bool xl, int sgw = 2, bool big = false) {
    for (int j = 0; j < m.nj; ++j)
        if (big ? (m.j[j].R != 1 && m.j[j].R != 2 && m.j[j].R != 4) : (M > 4 && m.j[j].R != 1))
            throw std::runtime_error(big ? "gemv_multi_m: 1, 2 or 4 rows per sub-group" : "gemv_multi_m: 5-8 vectors take one row per sub-group");
    const int ngr = (m.nsg + sgw - 1) / sgw;
    const sycl::nd_range<1> nr(sycl::range<1>((size_t)ngr * sgw * SG), sycl::range<1>((size_t)sgw * SG));
    if (multi_has_half(m)) { // certified F32 jobs (the loop down products of control_multi; mm with INK_MM_MULTI): x plain
        if (xl) throw std::runtime_error("gemv_multi_m: certified F32 jobs take x in the plain layout");
        auto go = [&]<int MM>() {
            return big ? q.parallel_for(nr, GemvMultiM<MM, false, true, true>{m, sgw}) : q.parallel_for(nr, GemvMultiM<MM, false, false, true>{m, sgw});
        };
        switch (M) {
        case 2: return go.template operator()<2>();
        case 3: return go.template operator()<3>();
        case 4: return go.template operator()<4>();
        case 5: return go.template operator()<5>();
        case 6: return go.template operator()<6>();
        case 7: return go.template operator()<7>();
        case 8: return go.template operator()<8>();
        default: throw std::runtime_error("gemv_multi_m: 2 to 8 vectors");
        }
    }
    if (big) switch (M * 2 + (xl ? 1 : 0)) {
    case 4: return q.parallel_for(nr, GemvMultiM<2, false, true>{m, sgw});
    case 5: return q.parallel_for(nr, GemvMultiM<2, true, true>{m, sgw});
    case 6: return q.parallel_for(nr, GemvMultiM<3, false, true>{m, sgw});
    case 7: return q.parallel_for(nr, GemvMultiM<3, true, true>{m, sgw});
    case 8: return q.parallel_for(nr, GemvMultiM<4, false, true>{m, sgw});
    case 9: return q.parallel_for(nr, GemvMultiM<4, true, true>{m, sgw});
    case 10: return q.parallel_for(nr, GemvMultiM<5, false, true>{m, sgw});
    case 11: return q.parallel_for(nr, GemvMultiM<5, true, true>{m, sgw});
    case 12: return q.parallel_for(nr, GemvMultiM<6, false, true>{m, sgw});
    case 13: return q.parallel_for(nr, GemvMultiM<6, true, true>{m, sgw});
    case 14: return q.parallel_for(nr, GemvMultiM<7, false, true>{m, sgw});
    case 15: return q.parallel_for(nr, GemvMultiM<7, true, true>{m, sgw});
    case 16: return q.parallel_for(nr, GemvMultiM<8, false, true>{m, sgw});
    case 17: return q.parallel_for(nr, GemvMultiM<8, true, true>{m, sgw});
    default: throw std::runtime_error("gemv_multi_m: 2 to 8 vectors");
    }
    switch (M * 2 + (xl ? 1 : 0)) {
    case 4: return q.parallel_for(nr, GemvMultiM<2, false>{m, sgw});
    case 5: return q.parallel_for(nr, GemvMultiM<2, true>{m, sgw});
    case 6: return q.parallel_for(nr, GemvMultiM<3, false>{m, sgw});
    case 7: return q.parallel_for(nr, GemvMultiM<3, true>{m, sgw});
    case 8: return q.parallel_for(nr, GemvMultiM<4, false>{m, sgw});
    case 9: return q.parallel_for(nr, GemvMultiM<4, true>{m, sgw});
    case 10: return q.parallel_for(nr, GemvMultiM<5, false>{m, sgw});
    case 11: return q.parallel_for(nr, GemvMultiM<5, true>{m, sgw});
    case 12: return q.parallel_for(nr, GemvMultiM<6, false>{m, sgw});
    case 13: return q.parallel_for(nr, GemvMultiM<6, true>{m, sgw});
    case 14: return q.parallel_for(nr, GemvMultiM<7, false>{m, sgw});
    case 15: return q.parallel_for(nr, GemvMultiM<7, true>{m, sgw});
    case 16: return q.parallel_for(nr, GemvMultiM<8, false>{m, sgw});
    case 17: return q.parallel_for(nr, GemvMultiM<8, true>{m, sgw});
    default: throw std::runtime_error("gemv_multi_m: 2 to 8 vectors");
    }
}

// F32 matrices with few rows (the loop controls' down products, the expert router): in gemv1_rows each lane walks its
// 5-9 chunks of 32 values one after another, waiting for each. Here a work-group takes one row and its sub-group j
// computes the chunk lane l would take on its j-th turn (c = l + 16 j, the same 32-term sum); lane l of sub-group 0
// then adds those sums in turn from 0.0f and the sub-group sums as before: gemv1_rows' values bit for bit.
// W: the FP32 rows (half = 0) or their certified halfwords (half = 1, K_F32H: rows of 2 x cols bytes; one kind per launch)
struct SplitJob { const float *W; int rows, cols; const float *x; float *y; int wg0; };
struct SplitJobs { SplitJob j[4]; int nj = 0, nwg = 0, J = 1; int half = 0; };
// Used where it pays (INK_PROF, card 3): one loop down product (64 x 4608) 7.15 -> 5.72 µs; not for the router
// (128 x 2304: 4.77 -> 5.51) or the three loop down products in one launch (3.5 MB, already at the memory's pace:
// 9.76 -> 10.80), hence rows <= 64 and rows of >= 4096 values.
inline bool split_ok(const WView &w) {
    return f32_like(w.kind, w.t->type) && w.t->rows() <= 64 && w.t->ne[0] >= 4096 && w.t->ne[0] % 32 == 0 &&
           w.t->ne[0] <= 32 * SG * 16;
}
inline void split_add(SplitJobs &m, const WView &w, const float *x, float *y) {
    if (m.nj >= 4 || !split_ok(w)) throw std::runtime_error("gemv_split: unsupported job");
    const int half = w.kind == K_F32H ? 1 : 0;
    if (m.nj > 0 && m.half != half) throw std::runtime_error("gemv_split: FP32 and certified F32 jobs in one launch");
    m.half = half;
    SplitJob &g = m.j[m.nj++];
    g.W = (const float *)w.p; g.rows = (int)w.t->rows(); g.cols = (int)w.t->ne[0]; g.x = x; g.y = y; g.wg0 = m.nwg;
    m.nwg += g.rows;
    m.J = std::max(m.J, (g.cols / 32 + SG - 1) / SG);
}
template <bool H> inline sycl::event gemv_split_t(sycl::queue &q, const SplitJobs &m) {
    const int J = m.J;
    const SplitJobs jm = m;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm((size_t)J * SG, h);
        h.parallel_for(sycl::nd_range<1>((size_t)jm.nwg * J * SG, (size_t)J * SG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            auto sg = it.get_sub_group();
            const int g = (int)it.get_group(0), j = (int)sg.get_group_linear_id(), lane = (int)sg.get_local_linear_id();
            int k = 0;
            for (int i = 1; i < 4; ++i) if (i < jm.nj && jm.j[i].wg0 <= g) k = i;
            const SplitJob &jb = jm.j[k];
            const int r = g - jb.wg0, nc = jb.cols / 32, c = lane + SG * j;
            if (c < nc) {
                float xs[32], o[32];
                load_x32(jb.x + 32 * c, xs);
                if constexpr (H) pl::F32H::decode32((const uint8_t *)jb.W + (size_t)r * jb.cols * 2, jb.cols, c, o);
                else fmt::F<G_F32>::decode32((const uint8_t *)(jb.W + (size_t)r * jb.cols), c, o);
                float sum = 0.0f;
                for (int i = 0; i < 32; ++i) sum = mac(sum, o[i], xs[i]);
                slm[j * SG + lane] = sum;
            }
            sycl::group_barrier(it.get_group());
            if (j == 0) {
                float acc = 0.0f;
                for (int jj = 0; jj < J; ++jj) if (lane + SG * jj < nc) acc += slm[jj * SG + lane];
                const float v = sg_sum(sg, acc);
                if (lane == 0) jb.y[r] = v;
            }
        });
    });
}
inline sycl::event gemv_split(sycl::queue &q, const SplitJobs &m) { return m.half ? gemv_split_t<true>(q, m) : gemv_split_t<false>(q, m); }

// the control outputs of several modules in one launch (engine control(), the gain and forget products with CtlOp):
// one row per sub-group, gemv_pair_row as GemvPair; F32 weights (loop_gain / loop_forget) in the file layout or as
// certified halfwords (K_F32H; one kind per launch, CtlJobs::kind: the H = true kernels decode them)
struct CJob { const uint8_t *A, *B; size_t rb; int rows, cols; const float *x; CtlOp op; int sg0; int ldx = 0; };
struct CtlJobs { CJob j[4]; int nj = 0, nsg = 0; int nt = 1; int kind = K_RAW; }; // nt tokens (CtlRows): token t reads x + t * ldx
inline bool ctl_multi_ok(const WView &a, const WView &b) {
    // one row stride and one row count for both (CJob keeps the gain's rows and cols): equal strides alone do not
    // make equal extents (a 64 x 2304 gain beside a 64 x 2 forget), so the dimensions must match too
    if (a.t->ne[0] != b.t->ne[0] || a.t->rows() != b.t->rows()) return false;
    if (a.kind == K_F32H && b.kind == K_F32H) return a.t->type == G_F32 && b.t->type == G_F32 && a.rb == b.rb;
    return a.kind == K_RAW && b.kind == K_RAW && a.t->type == G_F32 && b.t->type == G_F32 && a.rb == b.rb;
}
// a pair that may join m's launch (the same weight kind as its jobs)
inline bool ctl_join_ok(const CtlJobs &m, const WView &a, const WView &b) { return ctl_multi_ok(a, b) && (m.nj == 0 || m.kind == a.kind); }
inline void ctl_add(CtlJobs &m, const WView &a, const WView &b, const float *x, CtlOp op) {
    if (m.nj >= 4) throw std::runtime_error("ctl_multi: too many jobs");
    if (m.nj > 0 && m.kind != a.kind) throw std::runtime_error("ctl_multi: FP32 and certified F32 jobs in one launch");
    m.kind = a.kind;
    CJob &g = m.j[m.nj++];
    g.A = a.p; g.B = b.p; g.rb = a.rb; g.rows = (int)a.t->rows(); g.cols = (int)a.t->ne[0]; g.x = x; g.op = op; g.sg0 = m.nsg;
    m.nsg += g.rows;
}
template <bool H = false> struct CtlMulti { // H: K_F32H jobs
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
        using D = std::conditional_t<H, pl::F32H, pl::Raw<fmt::F<G_F32>>>;
        gemv_pair_row<D>(sg, g.A + (size_t)r * g.rb, g.B + (size_t)r * g.rb, g.cols, g.x, va, vb);
        if (sg.get_local_linear_id() == 0) g.op(0, r, va, vb);
    }
};
// the same products with one work-item per row (rows of at most 16 chunks of 32, e.g. the 64 values of loop_gain):
// the work-item computes the 16 virtual lanes' sums of gemv_pair_row (lane l: chunks l, l+16, ...; lanes past the
// last chunk hold +0) and their xor butterfly (offsets 8, 4, 2, 1) in registers, the same additions as sg_sum.
// m.nt > 1: work-item s takes token s / nsg (the same per-row operations for each token)
// H: K_F32H jobs. Each 16-byte load gives 8 weights, restored to their FP32 bits and multiplied in index order as
// they arrive (the same 32 macs of each chunk in the same order as the FP32 decode: the same sums; fewer live registers)
template <bool H = false> struct CtlRows {
    CtlJobs m;
    void operator()(sycl::nd_item<1> it) const {
        const int s0 = (int)it.get_global_id(0);
        if (s0 >= m.nsg * m.nt) return;
        const int t = s0 / m.nsg, s = s0 - t * m.nsg;
        int k = 0;
        for (int i = 1; i < 4; ++i) if (i < m.nj && m.j[i].sg0 <= s) k = i;
        const CJob &g = m.j[k];
        const int r = s - g.sg0, nc = g.cols / 32;
        const float *xt = g.x + (size_t)t * g.ldx;
        using D = pl::Raw<fmt::F<G_F32>>;
        float va[SG], vb[SG];
        for (int l = 0; l < SG; ++l) { va[l] = 0.0f; vb[l] = 0.0f; }
        for (int c = 0; c < nc; ++c) {
            float xs[32];
            load_x32(xt + 32 * c, xs);
            for (int j = 0; j < 2; ++j) {
                float sm = 0.0f;
                if constexpr (H) {
                    using V = sycl::vec<uint32_t, 4>;
                    const uint32_t *wr = (const uint32_t *)((j ? g.B : g.A) + (size_t)r * g.rb) + 16 * c;
                    for (int q = 0; q < 4; ++q) {
                        const V v = *(const V *)(wr + 4 * q);
                        for (int k = 0; k < 4; ++k) {
                            sm = mac(sm, cert::f32_even_from_pair(v[k]), xs[8 * q + 2 * k]);
                            sm = mac(sm, cert::f32_odd_from_pair(v[k]), xs[8 * q + 2 * k + 1]);
                        }
                    }
                } else {
                    float o[32];
                    D::decode32((j ? g.B : g.A) + (size_t)r * g.rb, g.cols, c, o);
                    for (int i = 0; i < 32; ++i) sm = mac(sm, o[i], xs[i]);
                }
                if (j) vb[c % SG] += sm; else va[c % SG] += sm;
            }
        }
        for (int off = SG / 2; off > 0; off >>= 1) {
            float ta[SG], tb[SG];
            for (int l = 0; l < SG; ++l) { ta[l] = va[l] + va[l ^ off]; tb[l] = vb[l] + vb[l ^ off]; }
            for (int l = 0; l < SG; ++l) { va[l] = ta[l]; vb[l] = tb[l]; }
        }
        g.op(t, r, va[0], vb[0]);
    }
};
inline bool ctl_rows_ok(const CtlJobs &m) {
    for (int i = 0; i < m.nj; ++i) if (m.j[i].cols > 32 * SG) return false;
    return true;
}
inline sycl::event ctl_rows(sycl::queue &q, const CtlJobs &m, int wg = 64) {
    int ngr = (m.nsg * m.nt + wg - 1) / wg;
    const sycl::nd_range<1> nr(sycl::range<1>((size_t)ngr * wg), sycl::range<1>((size_t)wg));
    if (m.kind == K_F32H) return q.parallel_for(nr, CtlRows<true>{m});
    return q.parallel_for(nr, CtlRows<>{m});
}
inline sycl::event ctl_multi(sycl::queue &q, const CtlJobs &m, int sgw = 2) {
    int ngr = (m.nsg + sgw - 1) / sgw;
    const sycl::nd_range<1> nr(sycl::range<1>((size_t)ngr * sgw * SG), sycl::range<1>((size_t)sgw * SG));
    if (m.kind == K_F32H) return q.parallel_for(nr, CtlMulti<true>{m, sgw});
    return q.parallel_for(nr, CtlMulti<>{m, sgw});
}

} // namespace ink
