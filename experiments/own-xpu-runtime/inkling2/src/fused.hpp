// fused.hpp: groups of the small per-application kernels of ops.hpp merged into single launches. Each value is
// computed with exactly the operations of the ops.hpp kernels it replaces, in the same order, so results are
// bit-identical; only the work layout changes.
//  - attn_prep: Q clip (+ log-scaled positions), K and V short convolutions + clip / rms norm + 16-bit cache store,
//    R clip (+ positions) and the relative bias table, in one launch of 128-thread work-groups.
//  - attn_tail: the post-attention convolution and the residual add.
//  - ffn_tail: the expert combine, the post-FFN convolution and the residual add.
// Convolution states are double-buffered: every kernel reads the state of the previous call (st_in) and writes the
// new one (st_out), so no separate state-store kernel is needed and no thread overwrites a state another still reads.
// Row sums over 128 values use 128-thread work-groups: ops.hpp's 256-thread rows of 128 values add eight exact zeros
// after the same first eight sub-group sums, which leaves a sum of squares unchanged.
#pragma once
#include "ops.hpp"

namespace ink::fz {

using ops::wg_sum;

// the conv window x(t-3..t) of channel c: rows of x for t >= 0, the previous state before
inline void conv_win(const float *x, int C, const float *st, int off, int c, int t, float *win) {
    for (int i = 0; i < 4; ++i) {
        int tt = t - 3 + i;
        win[i] = tt >= 0 ? x[(size_t)tt * C + c] : st[(size_t)(off + c) * 3 + (3 + tt)];
    }
}
// ops::convolve's formula; dt: the dynamic taps of this channel's head (or null)
inline float conv_out(const float *win, const float *w, int c, const float *dt, float scale) {
    float s = 0.0f;
    for (int i = 0; i < 4; ++i) s += win[i] * w[c * 4 + i];
    if (dt)
        for (int lag = 0; lag < 4; ++lag) s = s + win[3 - lag] * dt[lag];
    return (win[3] + s) * scale;
}
// the state after the call, from the last token's window (= ops::conv_store)
inline void conv_save(float *st, int off, int c, const float *win) {
    for (int k = 0; k < 3; ++k) st[(size_t)(off + c) * 3 + k] = win[1 + k];
}
// host: convolve()'s output scale
inline float conv_scale(bool dyn) { return 1.0f / std::sqrt((float)((dyn ? 2 : 1) * 4 + 1)); }

constexpr int PREP_WG = 128;

struct PrepArgs {
    int ntok, pos0, nh, nkvh, hd, nr, ext;
    bool full;            // full attention: dynamic K/V taps and log-scaled positions
    const float *tau;     // [ntok]
    float *Q; const float *q_clip; float qk_clip;
    const float *Kr, *Vr, *dynK, *dynV, *k_conv, *v_conv;
    const float *st_in; float *st_out; // this application's states (K at 0, V at kd)
    float *Kx, *Vx; sycl::half *Kc, *Vc;
    float eps, kv_scale;
    float *R; const float *rel_clip; float rel_clip_thr; const float *rel_bias; float *tab;
};

inline sycl::event attn_prep(sycl::queue &q, const PrepArgs a) {
    if (a.hd != PREP_WG || a.nr > SG || a.ext % PREP_WG) throw std::runtime_error("attn_prep: unsupported shape");
    const int nq = a.ntok * a.nh, nk = a.ntok * a.nkvh, ngroups = nq + 2 * nk + nq;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(PREP_WG / SG, h), rs(SG, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ngroups * PREP_WG), sycl::range<1>(PREP_WG)),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            int g = (int)it.get_group(0), l = (int)it.get_local_id(0);
            const int hd = a.hd, kd = a.nkvh * a.hd;
            if (g < nq) { // Q: clip with the per-head scale (ops::clip), then the positions (ops::scale_rows)
                int t = g / a.nh, hh = g % a.nh;
                float *row = a.Q + (size_t)g * hd;
                float v = row[l] * a.q_clip[(size_t)hh * hd + l];
                float norm = sycl::sqrt(wg_sum<PREP_WG>(it, v * v, &slm[0])) * 1.0f + 1e-6f;
                float f = sycl::clamp(a.qk_clip / norm, 0.0f, 1.0f);
                float x = v * f;
                if (a.full) x = x * a.tau[t];
                row[l] = x;
                return;
            }
            g -= nq;
            if (g < 2 * nk) { // K or V: convolution (ops::convolve), K clip / V rms norm, cache store (ops::kv_store)
                const bool isv = g >= nk;
                if (isv) g -= nk;
                int t = g / a.nkvh, hh = g % a.nkvh, c = hh * hd + l;
                const float *xr = isv ? a.Vr : a.Kr;
                const float *dyn = a.full ? (isv ? a.dynV : a.dynK) : nullptr;
                const int off = isv ? kd : 0;
                float win[4];
                conv_win(xr, kd, a.st_in, off, c, t, win);
                float v = conv_out(win, isv ? a.v_conv : a.k_conv, c, dyn ? dyn + (size_t)t * a.nkvh * 4 + hh * 4 : nullptr,
                                   a.kv_scale);
                float tot = wg_sum<PREP_WG>(it, v * v, &slm[0]);
                float x;
                if (!isv) {
                    float norm = sycl::sqrt(tot) * 1.0f + 1e-6f;
                    float f = sycl::clamp(a.qk_clip / norm, 0.0f, 1.0f);
                    x = v * f;
                } else {
                    float scale = 1.0f / sycl::sqrt(tot / hd + a.eps);
                    x = v * scale;
                }
                size_t i = (size_t)t * kd + c;
                (isv ? a.Vx : a.Kx)[i] = x;
                (isv ? a.Vc : a.Kc)[(size_t)a.pos0 * kd + i] = sycl::half(x);
                if (t == a.ntok - 1) conv_save(a.st_out, off, c, win);
                return;
            }
            g -= 2 * nk;
            { // R: clip with the per-head scale, the positions, then the bias table (ops::rel_table)
                int t = g / a.nh, hh = g % a.nh;
                float *row = a.R + (size_t)g * a.nr;
                float v = l < a.nr ? row[l] * a.rel_clip[(size_t)hh * a.nr + l] : 0.0f;
                float norm = sycl::sqrt(wg_sum<PREP_WG>(it, v * v, &slm[0])) * 1.0f + 1e-6f;
                float f = sycl::clamp(a.rel_clip_thr / norm, 0.0f, 1.0f);
                if (l < a.nr) {
                    float x = v * f;
                    if (a.full) x = x * a.tau[t];
                    row[l] = x;
                    rs[l] = x;
                }
                sycl::group_barrier(it.get_group());
                float *tb = a.tab + (size_t)g * a.ext;
                for (int dd = l; dd < a.ext; dd += PREP_WG) {
                    const float *b = a.rel_bias + (size_t)dd * a.nr;
                    float s = 0.0f;
                    for (int i = 0; i < a.nr; ++i) s += b[i] * rs[i];
                    tb[dd] = s;
                }
            }
        });
    });
}

// attn_out = convolution of ob (ops::convolve, no dynamic taps); ffn_inp = inpSA + attn_out (if inpSA)
inline sycl::event attn_tail(sycl::queue &q, const float *ob, const float *st_in, float *st_out, int off, const float *w,
                             float scale, float *attn_out, const float *inpSA, float *ffn_inp, int E, int ntok) {
    return q.parallel_for(sycl::range<2>((size_t)ntok, (size_t)E), [=](sycl::id<2> id) {
        int t = (int)id[0], c = (int)id[1];
        float win[4];
        conv_win(ob, E, st_in, off, c, t, win);
        float o = conv_out(win, w, c, nullptr, scale);
        size_t i = (size_t)t * E + c;
        attn_out[i] = o;
        if (inpSA) ffn_inp[i] = inpSA[i] + o;
        if (t == ntok - 1) conv_save(st_out, off, c, win);
    });
}

// ops::moe_combine's value for token t, channel c
inline float combine(const float *y, const float *escale, const int32_t *ids, const float *w, int nu, int n, int t, int c) {
    float acc = 0.0f;
    for (int k = 0; k < nu; ++k) {
        int s = t * nu + k;
        float v = y[(size_t)s * n + c];
        if (escale) v = v * escale[ids[s]];
        v = v * w[s];
        acc = k == 0 ? v : acc + v;
    }
    return acc;
}
// moe = combine of the expert outputs; ffn_out = convolution of moe; out = fi + ffn_out. The window's earlier tokens
// are combined again by each thread (the same values), so tokens need no second pass.
inline sycl::event ffn_tail(sycl::queue &q, const float *y, const float *escale, const int32_t *ids, const float *w, int nu,
                            const float *st_in, float *st_out, int off, const float *cw, float scale, float *ffn_out,
                            const float *fi, float *out, int E, int ntok) {
    return q.parallel_for(sycl::range<2>((size_t)ntok, (size_t)E), [=](sycl::id<2> id) {
        int t = (int)id[0], c = (int)id[1];
        float win[4];
        for (int i = 0; i < 4; ++i) {
            int tt = t - 3 + i;
            win[i] = tt >= 0 ? combine(y, escale, ids, w, nu, E, tt, c) : st_in[(size_t)(off + c) * 3 + (3 + tt)];
        }
        float o = conv_out(win, cw, c, nullptr, scale);
        size_t i = (size_t)t * E + c;
        ffn_out[i] = o;
        out[i] = fi[i] + o;
        if (t == ntok - 1) conv_save(st_out, off, c, win);
    });
}

// ops::attn_pv, then the output gate (ops::mul_sigmoid): out = acc * (1 / (1 + exp(-gate)))
inline sycl::event attn_pv_gate(sycl::queue &q, const float *P, int ldp, const sycl::half *V, int pos0, int ntok, int nh,
                                int nkvh, int hd, int win, const float *gate, float *out) {
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * nh * hd), sycl::range<1>((size_t)hd)),
                          [=](sycl::nd_item<1> it) {
        int g = (int)it.get_group(0), t = g / nh, hh = g % nh, d = (int)it.get_local_id(0);
        int kvh = hh / (nh / nkvh), p = pos0 + t, lo = win > 0 ? sycl::max(0, p - win + 1) : 0;
        const float *pr = P + (size_t)g * ldp;
        int kd = nkvh * hd;
        float acc = 0.0f;
        for (int j = lo; j <= p; ++j) acc += pr[j - lo] * (float)V[(size_t)j * kd + kvh * hd + d];
        size_t i = (size_t)t * nh * hd + hh * hd + d;
        out[i] = acc * (1.0f / (1.0f + sycl::exp(-gate[i])));
    });
}

// ---- attention, split for parallelism (same arithmetic as ops::attn_softmax and attn_pv_gate) -----------------
// attn_scores: s_j = (q . k_j) * scale (+ tab[p - j] if p - j < ext) into P[(t*nh + h)*ldp + j - lo], one key per
// thread (the dot product in d order, as ops::attn_softmax), keys of a (t, h) spread over many work-groups.
constexpr int SC_WG = 64;
inline sycl::event attn_scores(sycl::queue &q, const float *Q, const sycl::half *K, const float *tab, int pos0, int ntok, int nh,
                               int nkvh, int hd, int ext, int win, float scale, float *P, int ldp) {
    if (hd != 128) throw std::runtime_error("attn_scores: head size 128 only");
    const int pl = pos0 + ntok - 1, maxk = win > 0 ? sycl::min(win, pl + 1) : pl + 1;
    const int nb = (maxk + SC_WG - 1) / SC_WG;
    return q.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)ntok * nh, (size_t)nb * SC_WG), sycl::range<2>(1, SC_WG)),
                          [=](sycl::nd_item<2> it) {
        int g = (int)it.get_group(0), t = g / nh, hh = g % nh;
        int kvh = hh / (nh / nkvh), p = pos0 + t, lo = win > 0 ? sycl::max(0, p - win + 1) : 0;
        int j = lo + (int)it.get_global_id(1);
        if (j > p) return;
        const float *qv = Q + (size_t)g * hd;
        const sycl::half *kr = K + (size_t)j * nkvh * hd + kvh * hd;
        float s = 0.0f;
        for (int d8 = 0; d8 < 16; ++d8) {
            sycl::vec<sycl::half, 8> kv = *(const sycl::vec<sycl::half, 8> *)(kr + 8 * d8);
            sycl::vec<float, 4> q0 = *(const sycl::vec<float, 4> *)(qv + 8 * d8), q1 = *(const sycl::vec<float, 4> *)(qv + 8 * d8 + 4);
            for (int i = 0; i < 4; ++i) s += q0[i] * (float)kv[i];
            for (int i = 0; i < 4; ++i) s += q1[i] * (float)kv[4 + i];
        }
        s = s * scale;
        int dist = p - j;
        if (dist < ext) s = s + tab[(size_t)g * ext + dist];
        P[(size_t)g * ldp + j - lo] = s;
    });
}
// ops::attn_softmax after the scores: the same maximum, the same lane-strided sums of exponentials and work-group sum
inline sycl::event attn_softmax_norm(sycl::queue &q, const float *sink, int pos0, int ntok, int nh, int win, float *P, int ldp) {
    constexpr int AW = ops::ATT_WG;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(AW / SG, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * nh * AW), sycl::range<1>(AW)),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            int g = (int)it.get_group(0), t = g / nh, hh = g % nh, l = (int)it.get_local_id(0);
            int p = pos0 + t, lo = win > 0 ? sycl::max(0, p - win + 1) : 0;
            float *pr = P + (size_t)g * ldp;
            float mx = -INFINITY;
            for (int j = lo + l; j <= p; j += AW) mx = sycl::fmax(mx, pr[j - lo]);
            mx = sycl::reduce_over_group(it.get_group(), mx, sycl::maximum<float>());
            float sk = sink[(size_t)t * nh + hh];
            mx = sycl::fmax(mx, sk);
            float acc = 0.0f;
            for (int j = lo + l; j <= p; j += AW) {
                float e = sycl::exp(pr[j - lo] - mx);
                pr[j - lo] = e;
                acc += e;
            }
            float tot = wg_sum<AW>(it, acc, &slm[0]) + sycl::exp(sk - mx);
            float inv = 1.0f / tot;
            for (int j = lo + l; j <= p; j += AW) pr[j - lo] = pr[j - lo] * inv;
        });
    });
}
// attn_pv_gate with 16 channels per work-group (more groups in flight) and the loads of 16 keys issued before their
// products are added (still one by one, j ascending)
inline sycl::event attn_pv_gate2(sycl::queue &q, const float *P, int ldp, const sycl::half *V, int pos0, int ntok, int nh,
                                 int nkvh, int hd, int win, const float *gate, float *out) {
    constexpr int PW = 16, U = 16;
    const int nd = hd / PW;
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * nh * hd), sycl::range<1>(PW)), [=](sycl::nd_item<1> it) {
        int g = (int)it.get_group(0), gh = g / nd, t = gh / nh, hh = gh % nh;
        int d = (g % nd) * PW + (int)it.get_local_id(0);
        int kvh = hh / (nh / nkvh), p = pos0 + t, lo = win > 0 ? sycl::max(0, p - win + 1) : 0;
        const float *pr = P + (size_t)gh * ldp;
        const int kd = nkvh * hd;
        const sycl::half *vc = V + kvh * hd + d;
        float acc = 0.0f;
        int j = lo;
        for (; j + U - 1 <= p; j += U) {
            float pv[U], vv[U];
            for (int u = 0; u < U; ++u) { pv[u] = pr[j - lo + u]; vv[u] = (float)vc[(size_t)(j + u) * kd]; }
            for (int u = 0; u < U; ++u) acc += pv[u] * vv[u];
        }
        for (; j <= p; ++j) acc += pr[j - lo] * (float)vc[(size_t)j * kd];
        size_t i = (size_t)t * nh * hd + hh * hd + d;
        out[i] = acc * (1.0f / (1.0f + sycl::exp(-gate[i])));
    });
}

// ---- depth mix + norm ---------------------------------------------------------------------------------------
using ops::MixArgs;
using ops::MIX_MAX;
using ops::OPS_WG;
// ops::mix_scores with the nq query dot products in one pass over the state (each with its own accumulator, so the
// same per-query order) and their work-group sums behind one barrier pair (each the same order as wg_sum)
inline sycl::event mix_scores(sycl::queue &q, MixArgs a, size_t ld, const float *query, int nq, float *inv, float *sc,
                              int n, int ntok) {
    if (nq > 3) throw std::runtime_error("mix_scores: at most 3 queries");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(OPS_WG / SG, h), slm3(3 * (OPS_WG / SG), h);
        h.parallel_for(ops::rows_range(ntok * a.ns), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            int g = (int)it.get_group(0), t = g / a.ns, s = g % a.ns, l = (int)it.get_local_id(0);
            const float *x = a.st[s] + (size_t)t * ld;
            float acc = 0.0f;
            for (int i = l; i < n; i += OPS_WG) acc += x[i] * x[i];
            float tot = wg_sum<OPS_WG>(it, acc, &slm[0]);
            float is = 1.0f / sycl::sqrt(tot / n + 1e-6f);
            if (l == 0) inv[(size_t)t * MIX_MAX + s] = is;
            float dd[3] = {0.0f, 0.0f, 0.0f};
            for (int i = l; i < n; i += OPS_WG) {
                float xi = x[i] * is;
                for (int j = 0; j < 3; ++j)
                    if (j < nq) dd[j] += xi * query[(size_t)j * n + i];
            }
            auto sg = it.get_sub_group();
            constexpr int nsg = OPS_WG / SG;
            int sid = (int)sg.get_group_linear_id();
            for (int j = 0; j < 3; ++j) {
                float v = j < nq ? sg_sum(sg, dd[j]) : 0.0f;
                if (sg.get_local_linear_id() == 0) slm3[j * nsg + sid] = v;
            }
            sycl::group_barrier(it.get_group());
            if (l < nq) {
                float tt = 0.0f;
                for (int i = 0; i < nsg; ++i) tt += slm3[l * nsg + i];
                sc[((size_t)t * nq + l) * MIX_MAX + s] = tt;
            }
        });
    });
}
// ops::mix_out for a whole row per work-group, then ops::rms_norm of the row (the same strided sums, the same weight
// multiply): yn[j] (token-major, ntok rows of n) = rms_norm(mix row) * w[j]; out (if not null) gets the mix itself
// (query-major as ops::mix_out). Rows up to 12 * 256 values.
struct NormOut { float *y[3]; const float *w[3]; };
inline sycl::event mix_out_norm(sycl::queue &q, MixArgs a, size_t ld, int nq, const float *inv, const float *sc, float *out,
                                NormOut no, float eps, int n, int ntok) {
    constexpr int MAXV = 12;
    if (n > MAXV * OPS_WG || nq > 3) throw std::runtime_error("mix_out_norm: unsupported shape");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(OPS_WG / SG, h);
        h.parallel_for(ops::rows_range(nq * ntok), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            int g = (int)it.get_group(0), j = g / ntok, t = g % ntok, l = (int)it.get_local_id(0);
            const float *scr = sc + ((size_t)t * nq + j) * MIX_MAX;
            const float *iv = inv + (size_t)t * MIX_MAX;
            float scale = 1.0f / sycl::sqrt((float)n), mx = -INFINITY;
            for (int s = 0; s < a.ns; ++s) mx = sycl::fmax(mx, scr[s] * scale);
            float p[MIX_MAX], sum = 0.0f;
            for (int s = 0; s < a.ns; ++s) { p[s] = sycl::exp(scr[s] * scale - mx); sum += p[s]; }
            float isum = 1.0f / sum;
            for (int s = 0; s < a.ns; ++s) p[s] *= isum;
            float xv[MAXV];
            float ss = 0.0f;
            for (int u = 0; u < MAXV; ++u) {
                int i = l + OPS_WG * u;
                if (i >= n) break;
                float acc = 0.0f;
                for (int s = 0; s < a.ns; ++s) acc += (a.st[s][(size_t)t * ld + i] * iv[s]) * p[s];
                xv[u] = acc;
                if (out) out[((size_t)j * ntok + t) * n + i] = acc;
                ss += acc * acc;
            }
            float tot = wg_sum<OPS_WG>(it, ss, &slm[0]);
            float rs = 1.0f / sycl::sqrt(tot / n + eps);
            float *yr = no.y[j] + (size_t)t * n;
            const float *w = no.w[j];
            for (int u = 0; u < MAXV; ++u) {
                int i = l + OPS_WG * u;
                if (i >= n) break;
                yr[i] = w ? (xv[u] * rs) * w[i] : xv[u] * rs;
            }
        });
    });
}
// up to 4 ops::rms_norm calls of the same row length in one launch (each with its own input, output and weight)
struct NormJob { const float *x; float *y; const float *w; int ldx, ldy; };
inline sycl::event rms_norm_multi(sycl::queue &q, const NormJob *jobs, int njobs, int n, int nrows, float eps) {
    if (njobs < 1 || njobs > 4) throw std::runtime_error("rms_norm_multi: 1 to 4 jobs");
    struct J4 { NormJob j[4]; } jb{};
    for (int i = 0; i < njobs; ++i) jb.j[i] = jobs[i];
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(OPS_WG / SG, h);
        h.parallel_for(ops::rows_range(njobs * nrows), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            int g = (int)it.get_group(0), jn = g / nrows, r = g % nrows, l = (int)it.get_local_id(0);
            const NormJob &jj = jb.j[jn];
            const float *xr = jj.x + (size_t)r * jj.ldx;
            float *yr = jj.y + (size_t)r * jj.ldy;
            const float *w = jj.w;
            float s = 0.0f;
            for (int i = l; i < n; i += OPS_WG) s += xr[i] * xr[i];
            float tot = wg_sum<OPS_WG>(it, s, &slm[0]);
            float scale = 1.0f / sycl::sqrt(tot / n + eps);
            for (int i = l; i < n; i += OPS_WG) yr[i] = w ? (xr[i] * scale) * w[i] : xr[i] * scale;
        });
    });
}

} // namespace ink::fz
