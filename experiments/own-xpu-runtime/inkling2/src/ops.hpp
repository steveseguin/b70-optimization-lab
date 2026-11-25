// ops.hpp: the element-wise and per-row operations of the Inkling-2 forward pass (everything except the weight
// products, attention and the experts). All F32. Each row is handled by one work-group of OPS_WG threads; a row sum is
// per-thread strided partial sums, then a fixed xor butterfly in each sub-group, then the sub-group totals added in
// sub-group order: the result depends only on the row length, never on timing or on other rows.
// Formulas follow src/models/inkling2.cpp of the reference tree (cited per op).
#pragma once
#include "gemv.hpp"
#include "xlane.hpp"
#include "bfsplit.hpp"

namespace ink::ops {

constexpr int OPS_WG = 256;

template <int WG> inline float wg_sum(sycl::nd_item<1> it, float v, float *slm) {
    auto sg = it.get_sub_group();
    v = sg_sum(sg, v);
    int nsg = WG / SG, sid = (int)sg.get_group_linear_id();
    if (sg.get_local_linear_id() == 0) slm[sid] = v;
    sycl::group_barrier(it.get_group());
    float t = 0.0f;
    for (int i = 0; i < nsg; ++i) t += slm[i];
    sycl::group_barrier(it.get_group());
    return t;
}

inline sycl::nd_range<1> rows_range(int nrows) {
    return sycl::nd_range<1>(sycl::range<1>((size_t)nrows * OPS_WG), sycl::range<1>(OPS_WG));
}

// y = x / sqrt(mean(x^2) + eps) [* w]   (ggml_rms_norm, then build_norm's multiply by the weight)
// rows of n floats; x and y may be the same buffer; w may be null
// yl: also each row in lane order (xlane.hpp) at yl + r * xlane_floats(n); y null: only that copy
// yp (one row): also its three bf16 parts (bfsplit.hpp) at yp[p n + i]
inline sycl::event rms_norm(sycl::queue &q, const float *x, float *y, const float *w, int n, int nrows, float eps,
                            int ldx = -1, int ldy = -1, float *yl = nullptr, uint16_t *yp = nullptr) {
    if (ldx < 0) ldx = n;
    if (ldy < 0) ldy = n;
    const size_t lxl = xlane_floats(n);
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(OPS_WG / SG, h);
        h.parallel_for(rows_range(nrows), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            int r = (int)it.get_group(0), l = (int)it.get_local_id(0);
            const float *xr = x + (size_t)r * ldx;
            float *yr = y ? y + (size_t)r * ldy : nullptr;
            float *ylr = yl ? yl + (size_t)r * lxl : nullptr;
            constexpr int MV = 9; // rows of up to 9 * OPS_WG: unrolled, the reads go out together (same additions)
            if (n <= MV * OPS_WG) {
                float xv[MV], wv[MV];
#pragma unroll
                for (int u = 0; u < MV; ++u) {
                    const int i = l + OPS_WG * u;
                    xv[u] = i < n ? xr[i] : 0.0f;
                    wv[u] = (w && i < n) ? w[i] : 0.0f;
                }
                float s = 0.0f;
#pragma unroll
                for (int u = 0; u < MV; ++u) if (l + OPS_WG * u < n) s = mac(s, xv[u], xv[u]);
                float tot = wg_sum<OPS_WG>(it, s, &slm[0]);
                float scale = 1.0f / sycl::sqrt(tot / n + eps);
#pragma unroll
                for (int u = 0; u < MV; ++u) {
                    const int i = l + OPS_WG * u;
                    if (i < n) {
                        const float v = w ? (xv[u] * scale) * wv[u] : xv[u] * scale;
                        if (yr) yr[i] = v;
                        if (ylr) ylr[xlane_at(i)] = v;
                        if (yp) split3_store(v, yp + i, (size_t)n);
                    }
                }
                return;
            }
            float s = 0.0f;
            for (int i = l; i < n; i += OPS_WG) s = mac(s, xr[i], xr[i]);
            float tot = wg_sum<OPS_WG>(it, s, &slm[0]);
            float scale = 1.0f / sycl::sqrt(tot / n + eps);
            for (int i = l; i < n; i += OPS_WG) {
                const float v = w ? (xr[i] * scale) * w[i] : xr[i] * scale;
                if (yr) yr[i] = v;
                if (ylr) ylr[xlane_at(i)] = v;
                if (yp) split3_store(v, yp + i, (size_t)n);
            }
        });
    });
}

// clip (inkling2.cpp:207): x [* s]; then x * clamp(thr / (sqrt(sum(x^2)) + 1e-6), 0, 1), per row of n
// s has n * (rows per token) values, indexed by (row % srows) * n + i (the per-head scale), or is null
inline sycl::event clip(sycl::queue &q, float *x, const float *s, int srows, int n, int nrows, float thr) {
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(OPS_WG / SG, h);
        h.parallel_for(rows_range(nrows), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            int r = (int)it.get_group(0), l = (int)it.get_local_id(0);
            float *xr = x + (size_t)r * n;
            const float *sr = s ? s + (size_t)(r % srows) * n : nullptr;
            float acc = 0.0f;
            for (int i = l; i < n; i += OPS_WG) {
                float v = sr ? xr[i] * sr[i] : xr[i];
                acc = mac(acc, v, v);
            }
            float norm = sycl::sqrt(wg_sum<OPS_WG>(it, acc, &slm[0])) * 1.0f + 1e-6f;
            float f = sycl::clamp(thr / norm, 0.0f, 1.0f);
            for (int i = l; i < n; i += OPS_WG) {
                float v = sr ? xr[i] * sr[i] : xr[i];
                xr[i] = v * f;
            }
        });
    });
}

// mix (inkling2.cpp:221): attention over depth. states = [blocks[nb-1], ..., blocks[0], cur], each rms-normed
// (eps 1e-6, no weight); for each query j: p = softmax_s(states_s . query_j / sqrt(n)); out_j = sum_s p_s * states_s.
// states[s] points at the n floats of state s for token 0; tokens are ld apart. One work-group per (token, query).
// out: query-major, out + (j*ntok + t)*n, so each query's result is a contiguous [ntok][n] buffer. Max states: MIX_MAX.
constexpr int MIX_MAX = 12;
struct MixArgs {
    const float *st[MIX_MAX]; // in ggml order: st[0] = blocks[nb-1], ..., st[nb-1] = blocks[0], st[nb] = cur
    int ns = 0;
};
inline sycl::event mix(sycl::queue &q, MixArgs a, size_t ld, const float *query, int nq, float *out, int n, int ntok) {
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(OPS_WG / SG, h);
        sycl::local_accessor<float, 1> inv(MIX_MAX, h), sc(MIX_MAX, h);
        h.parallel_for(rows_range(ntok * nq), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            int g = (int)it.get_group(0), t = g / nq, j = g % nq, l = (int)it.get_local_id(0);
            const float *qv = query + (size_t)j * n;
            // rms scale of every state, then the scores
            for (int s = 0; s < a.ns; ++s) {
                const float *x = a.st[s] + (size_t)t * ld;
                float acc = 0.0f;
                for (int i = l; i < n; i += OPS_WG) acc = mac(acc, x[i], x[i]);
                float tot = wg_sum<OPS_WG>(it, acc, &slm[0]);
                if (l == 0) inv[s] = 1.0f / sycl::sqrt(tot / n + 1e-6f);
            }
            sycl::group_barrier(it.get_group());
            for (int s = 0; s < a.ns; ++s) {
                const float *x = a.st[s] + (size_t)t * ld;
                float is = inv[s], acc = 0.0f;
                for (int i = l; i < n; i += OPS_WG) acc = mac(acc, (x[i] * is), qv[i]);
                float tot = wg_sum<OPS_WG>(it, acc, &slm[0]);
                if (l == 0) sc[s] = tot;
            }
            sycl::group_barrier(it.get_group());
            // softmax over the states (ggml_soft_max_ext with scale 1/sqrt(n)), in state order
            float scale = 1.0f / sycl::sqrt((float)n), mx = -INFINITY;
            for (int s = 0; s < a.ns; ++s) mx = sycl::fmax(mx, sc[s] * scale);
            float p[MIX_MAX], sum = 0.0f;
            for (int s = 0; s < a.ns; ++s) { p[s] = sycl::exp(sc[s] * scale - mx); sum += p[s]; }
            float isum = 1.0f / sum;
            for (int s = 0; s < a.ns; ++s) p[s] *= isum;
            float *o = out + ((size_t)j * ntok + t) * n;
            for (int i = l; i < n; i += OPS_WG) {
                float acc = 0.0f;
                for (int s = 0; s < a.ns; ++s) acc = mac(acc, (a.st[s][(size_t)t * ld + i] * inv[s]), p[s]);
                o[i] = acc;
            }
        });
    });
}

// mix in two launches with the same arithmetic as mix() (bit-identical), parallel over states and then over the output:
//  mix_scores: one work-group per (token, state): inv[t][s] (rms scale) and sc[t][j][s] (state . query j), the same
//              strided sums and work-group reduction as mix();
//  mix_out:    softmax over the states (same order as mix()), out[j][t][i] = sum_s (x_s[i] * inv_s) * p_s.
// sc: [ntok][nq][MIX_MAX], inv: [ntok][MIX_MAX]
inline sycl::event mix_scores(sycl::queue &q, MixArgs a, size_t ld, const float *query, int nq, float *inv, float *sc,
                              int n, int ntok) {
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(OPS_WG / SG, h);
        h.parallel_for(rows_range(ntok * a.ns), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            int g = (int)it.get_group(0), t = g / a.ns, s = g % a.ns, l = (int)it.get_local_id(0);
            const float *x = a.st[s] + (size_t)t * ld;
            float acc = 0.0f;
            for (int i = l; i < n; i += OPS_WG) acc = mac(acc, x[i], x[i]);
            float tot = wg_sum<OPS_WG>(it, acc, &slm[0]);
            float is = 1.0f / sycl::sqrt(tot / n + 1e-6f);
            if (l == 0) inv[(size_t)t * MIX_MAX + s] = is;
            for (int j = 0; j < nq; ++j) {
                const float *qv = query + (size_t)j * n;
                float d = 0.0f;
                for (int i = l; i < n; i += OPS_WG) d = mac(d, (x[i] * is), qv[i]);
                float dt = wg_sum<OPS_WG>(it, d, &slm[0]);
                if (l == 0) sc[((size_t)t * nq + j) * MIX_MAX + s] = dt;
            }
        });
    });
}
// scores of query j at sc[((t * NQ + q0 + j) * MIX_MAX + s] (NQ 0: nq; a part of mix_scores_many's table)
inline sycl::event mix_out(sycl::queue &q, MixArgs a, size_t ld, int nq, const float *inv, const float *sc, float *out,
                           int n, int ntok, int NQ = 0, int q0 = 0) {
    if (NQ <= 0) NQ = nq;
    return q.parallel_for(sycl::range<3>((size_t)nq, (size_t)ntok, (size_t)n), [=](sycl::id<3> id) {
        int j = (int)id[0], t = (int)id[1], i = (int)id[2];
        const float *scr = sc + ((size_t)t * NQ + q0 + j) * MIX_MAX;
        const float *iv = inv + (size_t)t * MIX_MAX;
        float scale = 1.0f / sycl::sqrt((float)n), mx = -INFINITY;
        for (int s = 0; s < a.ns; ++s) mx = sycl::fmax(mx, scr[s] * scale);
        float p[MIX_MAX], sum = 0.0f;
        for (int s = 0; s < a.ns; ++s) { p[s] = sycl::exp(scr[s] * scale - mx); sum += p[s]; }
        float isum = 1.0f / sum;
        for (int s = 0; s < a.ns; ++s) p[s] *= isum;
        float acc = 0.0f;
        for (int s = 0; s < a.ns; ++s) acc = mac(acc, (a.st[s][(size_t)t * ld + i] * iv[s]), p[s]);
        out[((size_t)j * ntok + t) * n + i] = acc;
    });
}

// embedding rows: y[t] = decoded row ids[t] of W (any format), n values per row
inline sycl::event get_rows(sycl::queue &q, const Tensor &t, const uint8_t *W, const int32_t *ids, float *y, int ntok) {
    sycl::event e;
    int n = (int)t.ne[0];
    size_t rb = t.row_bytes();
    int nc = n / 32;
    fmt::dispatch(t.type, [&]<class FT>() {
        e = q.parallel_for(sycl::range<2>((size_t)ntok, (size_t)nc), [=](sycl::id<2> i) {
            float o[32];
            FT::decode32(W + (size_t)ids[i[0]] * rb, (int)i[1], o);
            float *yr = y + (size_t)i[0] * n + 32 * i[1];
            for (int k = 0; k < 32; ++k) yr[k] = o[k];
        });
    });
    return e;
}

// y = a + b (rows contiguous)
inline sycl::event add(sycl::queue &q, const float *a, const float *b, float *y, size_t n) {
    return q.parallel_for(sycl::range<1>(n), [=](sycl::id<1> i) { y[i] = a[i] + b[i]; });
}
// y = x * sigmoid(g)  (inkling2.cpp:595, the attention output gate)
inline sycl::event mul_sigmoid(sycl::queue &q, float *x, const float *g, size_t n) {
    return q.parallel_for(sycl::range<1>(n), [=](sycl::id<1> i) { x[i] = x[i] * (1.0f / (1.0f + sycl::exp(-g[i]))); });
}
// control (inkling2.cpp:237) final step: y = (1 - tanh(f)) * cur + tanh(g) * msg  (f, g: the forget and gain rows)
inline sycl::event control_out(sycl::queue &q, const float *cur, const float *msg, const float *f, const float *g,
                               float *y, size_t n) {
    return q.parallel_for(sycl::range<1>(n), [=](sycl::id<1> i) {
        float fo = sycl::tanh(f[i]), ga = sycl::tanh(g[i]);
        y[i] = (fo * -1.0f + 1.0f) * cur[i] + ga * msg[i];
    });
}
// x *= s[t] for vectors of n floats per token (the log-scaled positions, inkling2.cpp:461)
inline sycl::event scale_rows(sycl::queue &q, float *x, const float *s, int n, int ntok) {
    return q.parallel_for(sycl::range<1>((size_t)n * ntok), [=](sycl::id<1> i) { x[i] = x[i] * s[i / n]; });
}
// final logits: cap * tanh(x / cap)  (inkling2.cpp:659)
inline sycl::event softcap(sycl::queue &q, float *x, size_t n, float cap) {
    return q.parallel_for(sycl::range<1>(n), [=](sycl::id<1> i) { x[i] = sycl::tanh(x[i] * (1.0f / cap)) * cap; });
}

// ---- short convolution (inkling2.cpp:250-292, ssm_conv ops.cpp:10003) -------------------------------------
// x: this call's conv inputs [ntok][C]; st: this application's state, channel-major st[(off + c)*3 + k], k = 0 the
// oldest of the 3 inputs before this call; w: [C][4], tap i0 multiplies x(t - 3 + i0); dyn (or null): [ntok][H*4],
// dyn[t*H*4 + h*4 + lag] multiplies x(t - lag) for the channels of head h (C/H each).
// y = (x + conv) * (1/sqrt((dyn ? 2 : 1)*4 + 1)). Reads the state only; conv_store writes it afterwards.
inline sycl::event convolve(sycl::queue &q, const float *x, const float *st, int off, const float *w, const float *dyn,
                            int H, float *y, int C, int ntok) {
    const float scale = 1.0f / std::sqrt((float)((dyn ? 2 : 1) * 4 + 1));
    return q.parallel_for(sycl::range<2>((size_t)ntok, (size_t)C), [=](sycl::id<2> id) {
        int t = (int)id[0], c = (int)id[1];
        auto at = [&](int tt) { return tt >= 0 ? x[(size_t)tt * C + c] : st[(size_t)(off + c) * 3 + (3 + tt)]; };
        float win[4];
        for (int i = 0; i < 4; ++i) win[i] = at(t - 3 + i);
        float s = 0.0f;
        for (int i = 0; i < 4; ++i) s = mac(s, win[i], w[c * 4 + i]);
        if (dyn) {
            int h = c / (C / H);
            const float *dt = dyn + (size_t)t * H * 4 + h * 4;
            for (int lag = 0; lag < 4; ++lag) s = s + win[3 - lag] * dt[lag];
        }
        y[(size_t)t * C + c] = (win[3] + s) * scale;
    });
}
// the state after this call: the last 3 of [old state | x]
inline sycl::event conv_store(sycl::queue &q, const float *x, float *st, int off, int C, int ntok) {
    return q.parallel_for(sycl::range<1>((size_t)C), [=](sycl::id<1> id) {
        int c = (int)id[0];
        float *s = st + (size_t)(off + c) * 3;
        float v[3];
        for (int k = 0; k < 3; ++k) {
            int tt = ntok - 3 + k;
            v[k] = tt >= 0 ? x[(size_t)tt * C + c] : s[3 + tt];
        }
        for (int k = 0; k < 3; ++k) s[k] = v[k];
    });
}

// ---- attention -----------------------------------------------------------------------------------------
// store K/V rows of this call into the 16-bit cache at positions pos0..pos0+ntok-1 (rows of n halves)
inline sycl::event kv_store(sycl::queue &q, const float *x, sycl::half *cache, int pos0, int n, int ntok) {
    return q.parallel_for(sycl::range<1>((size_t)n * ntok), [=](sycl::id<1> i) {
        cache[(size_t)pos0 * n + i] = sycl::half(x[i]);
    });
}
// relative bias table (inkling2.cpp:514): tab[(t*nh + h)*ext + d] = sum_r R[(t*nh + h)*nr + r] * rb[d*nr + r]
inline sycl::event rel_table(sycl::queue &q, const float *R, const float *rb, int nr, int ext, float *tab, int nh, int ntok) {
    return q.parallel_for(sycl::range<2>((size_t)ntok * nh, (size_t)ext), [=](sycl::id<2> id) {
        const float *r = R + id[0] * nr, *b = rb + id[1] * nr;
        float s = 0.0f;
        for (int i = 0; i < nr; ++i) s = mac(s, b[i], r[i]);
        tab[id[0] * ext + id[1]] = s;
    });
}
// scores and softmax for query t (position pos0 + t), head h: keys j in [lo, p] (lo = p - win + 1 for a window),
// s_j = (q . k_j) * scale + tab[p - j] (only for p - j < ext), p_j = exp(s_j) / (exp(sink) + sum exp(s_k)).
// P: [ntok][nh][ldp], P[.. + (j - lo)] = p_j. One work-group per (t, h).
constexpr int ATT_WG = 128;
inline sycl::event attn_softmax(sycl::queue &q, const float *Q, const sycl::half *K, const float *tab, const float *sink,
                                int pos0, int ntok, int nh, int nkvh, int hd, int ext, int win, float scale,
                                float *P, int ldp) {
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(ATT_WG / SG, h), qs(hd, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * nh * ATT_WG), sycl::range<1>(ATT_WG)),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            int g = (int)it.get_group(0), t = g / nh, hh = g % nh, l = (int)it.get_local_id(0);
            int kvh = hh / (nh / nkvh), p = pos0 + t, lo = win > 0 ? sycl::max(0, p - win + 1) : 0;
            const float *qv = Q + (size_t)g * hd;
            for (int d = l; d < hd; d += ATT_WG) qs[d] = qv[d];
            sycl::group_barrier(it.get_group());
            const float *tb = tab + (size_t)g * ext;
            float *pr = P + (size_t)g * ldp;
            int kd = nkvh * hd;
            float mx = -INFINITY;
            for (int j = lo + l; j <= p; j += ATT_WG) {
                const sycl::half *kr = K + (size_t)j * kd + kvh * hd;
                float s = 0.0f;
                for (int d = 0; d < hd; ++d) s = mac(s, qs[d], (float)kr[d]);
                s = s * scale;
                int dist = p - j;
                if (dist < ext) s = s + tb[dist];
                pr[j - lo] = s;
                mx = sycl::fmax(mx, s);
            }
            // work-group max (exact in any order)
            mx = sycl::reduce_over_group(it.get_group(), mx, sycl::maximum<float>());
            float sk = sink[(size_t)t * nh + hh];
            mx = sycl::fmax(mx, sk);
            float acc = 0.0f;
            for (int j = lo + l; j <= p; j += ATT_WG) {
                float e = sycl::exp(pr[j - lo] - mx);
                pr[j - lo] = e;
                acc += e;
            }
            float tot = wg_sum<ATT_WG>(it, acc, &slm[0]) + sycl::exp(sk - mx);
            float inv = 1.0f / tot;
            for (int j = lo + l; j <= p; j += ATT_WG) pr[j - lo] = pr[j - lo] * inv;
        });
    });
}
// out[t][h*hd + d] = sum_j P[t][h][j - lo] * v_j[kvh*hd + d], j ascending. One work-group of hd threads per (t, h).
inline sycl::event attn_pv(sycl::queue &q, const float *P, int ldp, const sycl::half *V, int pos0, int ntok, int nh,
                           int nkvh, int hd, int win, float *out) {
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * nh * hd), sycl::range<1>((size_t)hd)),
                          [=](sycl::nd_item<1> it) {
        int g = (int)it.get_group(0), t = g / nh, hh = g % nh, d = (int)it.get_local_id(0);
        int kvh = hh / (nh / nkvh), p = pos0 + t, lo = win > 0 ? sycl::max(0, p - win + 1) : 0;
        const float *pr = P + (size_t)g * ldp;
        int kd = nkvh * hd;
        float acc = 0.0f;
        for (int j = lo; j <= p; ++j) acc = mac(acc, pr[j - lo], (float)V[(size_t)j * kd + kvh * hd + d]);
        out[(size_t)t * nh * hd + hh * hd + d] = acc;
    });
}

// ---- experts (llama-graph.cpp build_moe_ffn) ----------------------------------------------------------------
// per token: p = sigmoid(logit); top nu of p + bias (ties: lower index first); w = p[sel] / (sum + 1e-20) * wscale
// moe_route with one sub-group per token: lane l holds experts l, l+16, ..., the picks as moe_route's (largest
// selection score, lowest index among equal ones: max and min are exact in any order), weights as moe_route's
inline sycl::event moe_route_sg(sycl::queue &q, const float *logits, const float *bias, int ne, int nu, float wscale,
                                int32_t *ids, float *wts, int ntok) {
    constexpr int PER = 8;
    if (ne > PER * SG || nu > 16) throw std::runtime_error("moe_route_sg: more than 128 experts or 16 picks");
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * SG), sycl::range<1>(SG)),
                          [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
        auto sg = it.get_sub_group();
        int t = (int)it.get_group(0), lane = (int)sg.get_local_linear_id();
        float p[PER], sel[PER], lg[PER], bs[PER];
#pragma unroll
        for (int u = 0; u < PER; ++u) { // the reads first (clamped index past ne), so they go out together
            const int e = sycl::min(lane + SG * u, ne - 1);
            lg[u] = logits[(size_t)t * ne + e];
            bs[u] = bias ? bias[e] : 0.0f;
        }
#pragma unroll
        for (int u = 0; u < PER; ++u) {
            int e = lane + SG * u;
            p[u] = 0.0f; sel[u] = -INFINITY;
            if (e < ne) {
                p[u] = 1.0f / (1.0f + sycl::exp(-lg[u]));
                sel[u] = bias ? p[u] + bs[u] : p[u];
            }
        }
        int pick[16];
        for (int k = 0; k < nu; ++k) {
            float lm = sel[0];
            int lu = 0;
            for (int u = 1; u < PER; ++u) if (sel[u] > lm) { lm = sel[u]; lu = u; }
            float m = sycl::reduce_over_group(sg, lm, sycl::maximum<float>());
            int le = lane + SG * lu;
            int b = sycl::reduce_over_group(sg, (le < ne && lm == m) ? le : PER * SG, sycl::minimum<int>());
            for (int u = 0; u < PER; ++u) if (lane + SG * u == b) sel[u] = -INFINITY;
            pick[k] = b;
        }
        float w[16];
        for (int k = 0; k < nu; ++k) {
            const int b = pick[k], bu = b / SG;
            float pv = p[0];
            for (int u = 1; u < PER; ++u) if (u == bu) pv = p[u];
            w[k] = sycl::select_from_group(sg, pv, b % SG);
        }
        if (lane == 0) {
            int32_t *ix = ids + (size_t)t * nu;
            float *wo = wts + (size_t)t * nu;
            float s = 0.0f;
            for (int k = 0; k < nu; ++k) { ix[k] = pick[k]; s += w[k]; }
            s = s * 1.0f + 1e-20f;
            for (int k = 0; k < nu; ++k) wo[k] = (w[k] / s) * wscale;
        }
    });
}
inline sycl::event moe_route(sycl::queue &q, const float *logits, const float *bias, int ne, int nu, float wscale,
                             int32_t *ids, float *wts, int ntok) {
    // one work-group per token, one thread per expert; each of the nu picks is the largest remaining score, the lowest
    // expert index among equal scores (the same choice as a serial first-strictly-greater scan)
    constexpr int RW = 128;
    if (ne > RW || nu > 16) throw std::runtime_error("moe_route: more than 128 experts or 16 picks");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> pl(RW, h);
        sycl::local_accessor<int, 1> pick(16, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * RW), sycl::range<1>(RW)),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            int t = (int)it.get_group(0), e = (int)it.get_local_id(0);
            auto grp = it.get_group();
            float p = 0.0f, sel = -INFINITY;
            if (e < ne) {
                p = 1.0f / (1.0f + sycl::exp(-logits[(size_t)t * ne + e]));
                sel = bias ? p + bias[e] : p;
            }
            pl[e] = p;
            for (int k = 0; k < nu; ++k) {
                float m = sycl::reduce_over_group(grp, sel, sycl::maximum<float>());
                int b = sycl::reduce_over_group(grp, (e < ne && sel == m) ? e : RW, sycl::minimum<int>());
                if (e == b) sel = -INFINITY;
                if (e == 0) pick[k] = b;
            }
            sycl::group_barrier(grp);
            if (e == 0) {
                int32_t *ix = ids + (size_t)t * nu;
                float *w = wts + (size_t)t * nu;
                float s = 0.0f;
                for (int k = 0; k < nu; ++k) { ix[k] = pick[k]; w[k] = pl[pick[k]]; s += w[k]; }
                s = s * 1.0f + 1e-20f;
                for (int k = 0; k < nu; ++k) w[k] = (w[k] / s) * wscale;
            }
        });
    });
}
// SITU (llama-graph.cpp LLM_FFN_SITU): gu rows [K][2*nff] (gate | up), each times the slot's expert scale (if any);
// h = (beta*tanh(g/beta)) * sigmoid(g) * (lb*tanh(u/lb))
inline sycl::event situ(sycl::queue &q, const float *gu, const float *escale, const int32_t *ids, int nff, float beta,
                        float lb, float *hout, int K) {
    return q.parallel_for(sycl::range<2>((size_t)K, (size_t)nff), [=](sycl::id<2> id) {
        int k = (int)id[0], i = (int)id[1];
        float g = gu[(size_t)k * 2 * nff + i], u = gu[(size_t)k * 2 * nff + nff + i];
        if (escale) { float s = escale[ids[k]]; g = g * s; u = u * s; }
        float a = (sycl::tanh(g * (1.0f / beta)) * beta) * (1.0f / (1.0f + sycl::exp(-g)));
        if (lb > 0.0f) u = sycl::tanh(u * (1.0f / lb)) * lb;
        hout[(size_t)k * nff + i] = a * u;
    });
}
// out[t] = sum_k (y[t*nu + k] * escale[id]) * w[t*nu + k], k ascending
inline sycl::event moe_combine(sycl::queue &q, const float *y, const float *escale, const int32_t *ids, const float *w,
                               int nu, int n, float *out, int ntok) {
    return q.parallel_for(sycl::range<2>((size_t)ntok, (size_t)n), [=](sycl::id<2> id) {
        int t = (int)id[0], i = (int)id[1];
        float acc = 0.0f;
        for (int k = 0; k < nu; ++k) {
            int s = t * nu + k;
            float v = y[(size_t)s * n + i];
            if (escale) v = v * escale[ids[s]];
            v = v * w[s];
            acc = k == 0 ? v : acc + v;
        }
        out[(size_t)t * n + i] = acc;
    });
}

// greedy choice: out[0] = the first index of the largest of x[0..n) (the host loop `if (x[i] > x[b]) b = i`).
// One work-group: per-thread first maximum over a strided slice, the work-group maximum, then the lowest index among
// the threads that hold it.
// argmax() of nrows rows (row r at x + r * ld) in two launches: AG work-groups per row each find the first largest
// value of their span, then one work-group per row takes the first largest of those (spans in order), so the index is
// argmax()'s. pv / pi: nrows * ARGMAX_G scratch values
constexpr int ARGMAX_G = 64;
inline sycl::event argmax_rows2(sycl::queue &q, const float *x, size_t ld, int n, int nrows, int32_t *out, float *pv, int32_t *pi) {
    constexpr int AW = 256, AG = ARGMAX_G;
    const int span = (n + AG - 1) / AG;
    q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)nrows * AG * AW), sycl::range<1>(AW)), [=](sycl::nd_item<1> it) {
        const int g = (int)it.get_group(0), r = g / AG, a = g % AG, l = (int)it.get_local_id(0);
        const float *xr = x + (size_t)r * ld;
        const int lo = a * span, hi = sycl::min(n, lo + span);
        float bv = -INFINITY;
        int bi = n;
        for (int i = lo + l; i < hi; i += AW)
            if (bi == n || xr[i] > bv) { bv = xr[i]; bi = i; }
        const float m = sycl::reduce_over_group(it.get_group(), bv, sycl::maximum<float>());
        const int idx = sycl::reduce_over_group(it.get_group(), (bi < n && bv == m) ? bi : n, sycl::minimum<int>());
        if (l == 0) { pv[g] = m; pi[g] = idx; }
    });
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)nrows * AG), sycl::range<1>(AG)), [=](sycl::nd_item<1> it) {
        const int r = (int)it.get_group(0), l = (int)it.get_local_id(0), g = r * AG + l;
        const float bv = pv[g];
        const int bi = pi[g];
        const float m = sycl::reduce_over_group(it.get_group(), bv, sycl::maximum<float>());
        const int idx = sycl::reduce_over_group(it.get_group(), (bi < n && bv == m) ? bi : n, sycl::minimum<int>());
        if (l == 0) out[r] = idx;
    });
}
// Sampling (serving): one token per row from softmax(x / T) over the kept tokens. Kept: x >= the largest of the
// thresholds min_p (exp((x - max) / T) >= min_p), top_k (the k-th largest value, found by bisection on the values) and
// top_p (the highest value whose kept mass reaches top_p of the total, bisection), each off at its neutral setting
// (min_p 0, top_k 0, top_p 1). The token is the first index whose running sum, in index order, passes u[r] times the
// kept sum: each lane sums a contiguous slice of the row in order, lane 0 adds the slices up in lane order, and the
// lane whose slice holds the target walks it again in the same order. Every sum has a fixed order, so the same row
// and u give the same token on every run, whatever else ran in the step (a check row equals a one-token step's row,
// so guessing does not change a sampled text either).
struct SampleArgs { float T = 0.0f, topp = 1.0f, minp = 0.0f; int topk = 0; float u[8] = {}; };
inline sycl::event sample_rows(sycl::queue &q, const float *x, size_t ld, int n, int nrows, SampleArgs a, int32_t *out) {
    constexpr int W = 1024, IT = 32;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> pre(W + 1, h);
        sycl::local_accessor<int, 1> pick(1, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)nrows * W), sycl::range<1>(W)), [=](sycl::nd_item<1> it) {
            const int r = (int)it.get_group(0), l = (int)it.get_local_id(0);
            const auto grp = it.get_group();
            const float *xr = x + (size_t)r * ld;
            const float invT = 1.0f / a.T;
            float mx = -INFINITY, mn = INFINITY;
            for (int i = l; i < n; i += W) { const float v = xr[i]; mx = sycl::fmax(mx, v); mn = sycl::fmin(mn, v); }
            mx = sycl::reduce_over_group(grp, mx, sycl::maximum<float>());
            mn = sycl::reduce_over_group(grp, mn, sycl::minimum<float>());
            float th = mn;
            if (a.minp > 0.0f) th = sycl::fmax(th, mx + a.T * sycl::log(a.minp));
            if (a.topk > 0 && a.topk < n) { // count(x >= lo) >= k > count(x >= hi)
                float lo = mn, hi = mx;
                int cm = 0;
                for (int i = l; i < n; i += W) cm += xr[i] >= mx;
                if (sycl::reduce_over_group(grp, cm, sycl::plus<int>()) >= a.topk) lo = mx;
                else
                    for (int k = 0; k < IT; ++k) {
                        const float mid = lo + 0.5f * (hi - lo);
                        int c = 0;
                        for (int i = l; i < n; i += W) c += xr[i] >= mid;
                        if (sycl::reduce_over_group(grp, c, sycl::plus<int>()) >= a.topk) lo = mid; else hi = mid;
                    }
                th = sycl::fmax(th, lo);
            }
            if (a.topp < 1.0f) { // mass(x >= lo) >= top_p * mass(x >= th) > mass(x >= hi)
                auto mass = [&](float t) {
                    float s = 0.0f;
                    for (int i = l; i < n; i += W) { const float v = xr[i]; if (v >= t) s += sycl::exp((v - mx) * invT); }
                    return sycl::reduce_over_group(grp, s, sycl::plus<float>());
                };
                const float goal = a.topp * mass(th);
                float lo = th, hi = mx;
                if (mass(mx) >= goal) lo = mx;
                else
                    for (int k = 0; k < IT; ++k) {
                        const float mid = lo + 0.5f * (hi - lo);
                        if (mass(mid) >= goal) lo = mid; else hi = mid;
                    }
                th = sycl::fmax(th, lo);
            }
            // each lane's contiguous slice, summed in index order
            const int span = (n + W - 1) / W, i0 = sycl::min(n, l * span), i1 = sycl::min(n, i0 + span);
            float c = 0.0f;
            for (int i = i0; i < i1; ++i) { const float v = xr[i]; if (v >= th) c += sycl::exp((v - mx) * invT); }
            pre[l] = c;
            if (l == 0) pick[0] = -1;
            sycl::group_barrier(grp);
            if (l == 0) { // starts of the slices, in lane order
                float s = 0.0f;
                for (int j = 0; j < W; ++j) { const float t = pre[j]; pre[j] = s; s += t; }
                pre[W] = s;
            }
            sycl::group_barrier(grp);
            const float tot = pre[W];
            float target = a.u[r] * tot;
            if (!(target < tot)) target = sycl::nextafter(tot, 0.0f);
            const float s0 = pre[l], s1 = l + 1 < W ? pre[l + 1] : tot;
            if (s0 <= target && target < s1) { // exactly one lane (slices without mass have s0 == s1)
                const float dd = target - s0;
                float acc = 0.0f;
                int p = -1, last = -1;
                for (int i = i0; i < i1 && p < 0; ++i) {
                    const float v = xr[i];
                    if (v < th) continue;
                    acc += sycl::exp((v - mx) * invT);
                    last = i;
                    if (acc > dd) p = i;
                }
                pick[0] = p >= 0 ? p : last;
            }
            sycl::group_barrier(grp);
            if (l == 0) {
                int p = pick[0];
                if (p < 0) // (not reached) the first index of the largest value
                    for (int i = 0; i < n; ++i) if (xr[i] == mx) { p = i; break; }
                out[r] = p;
            }
        });
    });
}
// the uniform number of the token at position pos (sampling with this seed): 24 random bits, exact in float
inline float sample_u(uint64_t seed, int64_t pos) {
    uint64_t z = seed + 0x9E3779B97F4A7C15ull * (uint64_t)(pos + 1);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    z ^= z >> 31;
    return (float)(z >> 40) * (1.0f / 16777216.0f);
}
// argmax_rows2 that also gives the chosen value's softmax probability (1 / sum_i exp(x_i - max)) per row;
// ps: nrows * ARGMAX_G scratch sums. For guessers: how sure the guess is
// map (optional): out[r] = map[index] (a guesser's head over a vocabulary subset: index -> token id); col (optional):
// the index itself (0 if none was found)
inline sycl::event argmax_p_rows(sycl::queue &q, const float *x, size_t ld, int n, int nrows, int32_t *out, float *prob, float *pv,
                                 int32_t *pi, float *ps, const int32_t *map = nullptr, int32_t *col = nullptr) {
    constexpr int AW = 256, AG = ARGMAX_G;
    const int span = (n + AG - 1) / AG;
    q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)nrows * AG * AW), sycl::range<1>(AW)), [=](sycl::nd_item<1> it) {
        const int g = (int)it.get_group(0), r = g / AG, a = g % AG, l = (int)it.get_local_id(0);
        const float *xr = x + (size_t)r * ld;
        const int lo = a * span, hi = sycl::min(n, lo + span);
        float bv = -INFINITY, bs = 0.0f;
        int bi = n;
        for (int i = lo + l; i < hi; i += AW) {
            const float v = xr[i];
            if (bi == n || v > bv) { bs = (bi == n ? 0.0f : bs * sycl::exp(bv - v)) + 1.0f; bv = v; bi = i; }
            else bs += sycl::exp(v - bv);
        }
        const float m = sycl::reduce_over_group(it.get_group(), bv, sycl::maximum<float>());
        const int idx = sycl::reduce_over_group(it.get_group(), (bi < n && bv == m) ? bi : n, sycl::minimum<int>());
        const float sm = sycl::reduce_over_group(it.get_group(), bi < n ? bs * sycl::exp(bv - m) : 0.0f, sycl::plus<float>());
        if (l == 0) { pv[g] = m; pi[g] = idx; ps[g] = sm; }
    });
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)nrows * AG), sycl::range<1>(AG)), [=](sycl::nd_item<1> it) {
        const int r = (int)it.get_group(0), l = (int)it.get_local_id(0), g = r * AG + l;
        const float bv = pv[g];
        const int bi = pi[g];
        const float m = sycl::reduce_over_group(it.get_group(), bv, sycl::maximum<float>());
        const int idx = sycl::reduce_over_group(it.get_group(), (bi < n && bv == m) ? bi : n, sycl::minimum<int>());
        const float sm = sycl::reduce_over_group(it.get_group(), bi < n ? ps[g] * sycl::exp(bv - m) : 0.0f, sycl::plus<float>());
        if (l == 0) { out[r] = map && idx < n ? map[idx] : idx; prob[r] = 1.0f / sm; if (col) col[r] = idx < n ? idx : 0; }
    });
}
// argmax() of each of nrows rows (row r at x + r * ld), one work-group per row: the same choice per row
inline sycl::event argmax_rows(sycl::queue &q, const float *x, size_t ld, int n, int nrows, int32_t *out) {
    constexpr int AW = 1024;
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)nrows * AW), sycl::range<1>(AW)), [=](sycl::nd_item<1> it) {
        const int r = (int)it.get_group(0), l = (int)it.get_local_id(0);
        const float *xr = x + (size_t)r * ld;
        float bv = -INFINITY;
        int bi = n;
        for (int i = l; i < n; i += AW)
            if (bi == n || xr[i] > bv) { bv = xr[i]; bi = i; }
        float m = sycl::reduce_over_group(it.get_group(), bv, sycl::maximum<float>());
        int idx = sycl::reduce_over_group(it.get_group(), (bi < n && bv == m) ? bi : n, sycl::minimum<int>());
        if (l == 0) out[r] = idx;
    });
}
inline sycl::event argmax(sycl::queue &q, const float *x, int n, int32_t *out) {
    constexpr int AW = 1024;
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>(AW), sycl::range<1>(AW)), [=](sycl::nd_item<1> it) {
        int l = (int)it.get_local_id(0);
        float bv = -INFINITY;
        int bi = n;
        for (int i = l; i < n; i += AW)
            if (bi == n || x[i] > bv) { bv = x[i]; bi = i; }
        float m = sycl::reduce_over_group(it.get_group(), bv, sycl::maximum<float>());
        int idx = sycl::reduce_over_group(it.get_group(), (bi < n && bv == m) ? bi : n, sycl::minimum<int>());
        if (l == 0) out[0] = idx;
    });
}

} // namespace ink::ops
