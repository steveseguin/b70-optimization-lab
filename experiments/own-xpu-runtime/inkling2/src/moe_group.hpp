// moe_group.hpp: expert products for several tokens with each chosen expert's rows decoded once per batch of up to
// MB slots that chose it (a slot = one token's k-th expert). Per (row, slot) the arithmetic is exactly GemvPair's /
// GemvRoutedR's (same decode, same chunk-per-lane sums, same butterfly), so results equal the one-slot-at-a-time
// kernels bit for bit; only the work layout changes.
//  moe_group: slots grouped by expert (ascending expert id, ascending slot inside a group).
//  GroupedPair: gate and up rows + SITU (as GemvPair<D, SituOp>); GroupedRows: R rows (as GemvRoutedR<D, R>).
#pragma once
#include "gemv2.hpp"

namespace ink {

struct MoeGroups {
    int32_t *count = nullptr; // [1] active experts A
    int32_t *exp = nullptr;   // [ne] expert of group a
    int32_t *off = nullptr;   // [ne + 1] first slot index (in slots) of group a; off[A] = K
    int32_t *slots = nullptr; // [K] slots, grouped
    void alloc(Device &d, int ne, int kmax) {
        count = d.alloc<int32_t>(1); exp = d.alloc<int32_t>(ne); off = d.alloc<int32_t>(ne + 1); slots = d.alloc<int32_t>(kmax);
    }
};

// one work-group, one thread per expert (ne <= 128)
inline sycl::event moe_group(sycl::queue &q, const int32_t *ids, int K, int ne, MoeGroups g) {
    constexpr int GW = 128;
    if (ne > GW) throw std::runtime_error("moe_group: more than 128 experts");
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>(GW), sycl::range<1>(GW)), [=](sycl::nd_item<1> it) {
        int e = (int)it.get_local_id(0);
        auto grp = it.get_group();
        int cnt = 0;
        if (e < ne)
            for (int s = 0; s < K; ++s) cnt += ids[s] == e;
        int start = sycl::exclusive_scan_over_group(grp, cnt, sycl::plus<int>());
        int act = cnt > 0 ? 1 : 0;
        int a = sycl::exclusive_scan_over_group(grp, act, sycl::plus<int>());
        int na = sycl::reduce_over_group(grp, act, sycl::plus<int>());
        if (act) { g.exp[a] = e; g.off[a] = start; }
        if (e == 0) { g.count[0] = na; g.off[na] = K; }
        if (cnt) {
            int j = start;
            for (int s = 0; s < K; ++s)
                if (ids[s] == e) g.slots[j++] = s;
        }
    });
}

constexpr int MOE_MB = 8; // slots per decode

// gate rows r and up rows r (+ rows of B) of the group's expert for every slot of the group, then op(slot, r, g, u)
template <class D, class Op> struct GroupedPair {
    const uint8_t *A, *B; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *x; int ldx, xdiv;
    Op op;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        int a = (int)it.get_group(0);
        if (a >= g.count[0]) return;
        auto sg = it.get_sub_group();
        int r = (int)it.get_group(1) * sgw + (int)sg.get_group_linear_id();
        if (r >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        size_t eo = (size_t)g.exp[a] * estride;
        const uint8_t *ra = A + eo + (size_t)r * rb, *rbp = B + eo + (size_t)r * rb;
        const int s0 = g.off[a], s1 = g.off[a + 1], nc = cols / 32;
        for (int b0 = s0; b0 < s1; b0 += MOE_MB) {
            const int cnt = sycl::min(MOE_MB, s1 - b0);
            int sl[MOE_MB];
            for (int m = 0; m < MOE_MB; ++m) sl[m] = m < cnt ? g.slots[b0 + m] : 0;
            float acc[2][MOE_MB];
            for (int j = 0; j < 2; ++j) for (int m = 0; m < MOE_MB; ++m) acc[j][m] = 0.0f;
            for (int c = lane; c < nc; c += SG) {
                float o[2][32];
                D::decode32(ra, cols, c, o[0]);
                D::decode32(rbp, cols, c, o[1]);
                for (int m = 0; m < MOE_MB; ++m) {
                    if (m >= cnt) break;
                    float xs[32];
                    load_x32(x + (size_t)(xdiv ? sl[m] / xdiv : sl[m]) * ldx + 32 * c, xs);
                    for (int j = 0; j < 2; ++j) {
                        float s = 0.0f;
                        for (int i = 0; i < 32; ++i) s += o[j][i] * xs[i];
                        acc[j][m] += s;
                    }
                }
            }
            for (int m = 0; m < MOE_MB; ++m) {
                if (m >= cnt) break;
                float va = sg_sum(sg, acc[0][m]), vb = sg_sum(sg, acc[1][m]);
                if (lane == 0) op(sl[m], r, va, vb);
            }
        }
    }
};

// rows r0..r0+R-1 of the group's expert for every slot: y[slot * ldy + r] (x row = slot)
template <class D, int R> struct GroupedRows {
    const uint8_t *W; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *x; int ldx;
    float *y; int ldy;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        int a = (int)it.get_group(0);
        if (a >= g.count[0]) return;
        auto sg = it.get_sub_group();
        int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        const uint8_t *base = W + (size_t)g.exp[a] * estride;
        const int s0 = g.off[a], s1 = g.off[a + 1], nc = cols / 32;
        for (int b0 = s0; b0 < s1; b0 += MOE_MB) {
            const int cnt = sycl::min(MOE_MB, s1 - b0);
            int sl[MOE_MB];
            for (int m = 0; m < MOE_MB; ++m) sl[m] = m < cnt ? g.slots[b0 + m] : 0;
            float acc[R][MOE_MB];
            for (int j = 0; j < R; ++j) for (int m = 0; m < MOE_MB; ++m) acc[j][m] = 0.0f;
            for (int c = lane; c < nc; c += SG) {
                float o[R][32];
                for (int j = 0; j < R; ++j)
                    if (r0 + j < rows) D::decode32(base + (size_t)(r0 + j) * rb, cols, c, o[j]);
                for (int m = 0; m < MOE_MB; ++m) {
                    if (m >= cnt) break;
                    float xs[32];
                    load_x32(x + (size_t)sl[m] * ldx + 32 * c, xs);
                    for (int j = 0; j < R; ++j) {
                        if (r0 + j >= rows) break;
                        float s = 0.0f;
                        for (int i = 0; i < 32; ++i) s += o[j][i] * xs[i];
                        acc[j][m] += s;
                    }
                }
            }
            for (int m = 0; m < MOE_MB; ++m) {
                if (m >= cnt) break;
                for (int j = 0; j < R; ++j) {
                    float v = sg_sum(sg, acc[j][m]);
                    if (lane == 0 && r0 + j < rows) y[(size_t)sl[m] * ldy + r0 + j] = v;
                }
            }
        }
    }
};

template <class Op> inline sycl::event grouped_pair(sycl::queue &q, const WView &a, const uint8_t *B, size_t estride, int rows,
                                                    MoeGroups g, int amax, const float *x, int ldx, int xdiv, Op op, int sgw = 2) {
    sycl::event e;
    int cols = (int)a.t->ne[0];
    with_decoder(a, [&]<class D>() {
        int ngr = (rows + sgw - 1) / sgw;
        sycl::nd_range<2> nr(sycl::range<2>((size_t)amax, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
        e = q.parallel_for(nr, GroupedPair<D, Op>{a.p, B, a.rb, estride, rows, cols, g, x, ldx, xdiv, op, sgw});
    });
    return e;
}
inline sycl::event grouped_rows(sycl::queue &q, const WView &w, MoeGroups g, int amax, const float *x, int ldx, float *y,
                                int ldy, int sgw = 2) {
    sycl::event e;
    int cols = (int)w.t->ne[0], rows = (int)w.t->ne[1];
    size_t estride = w.rb * (size_t)rows;
    with_decoder(w, [&]<class D>() {
        constexpr int R = 2;
        int nsg = (rows + R - 1) / R, ngr = (nsg + sgw - 1) / sgw;
        sycl::nd_range<2> nr(sycl::range<2>((size_t)amax, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
        e = q.parallel_for(nr, GroupedRows<D, R>{w.p, w.rb, estride, rows, cols, g, x, ldx, y, ldy, sgw});
    });
    return e;
}

} // namespace ink
