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
    int vld;              // > 0: V cache transposed, Vc[(kvh*hd + c) * vld + position] (attn_pv_t)
    float eps, kv_scale;
    const float *R; float *Rc; const float *rel_clip; float rel_clip_thr; const float *rel_bias; float *tab; // R clipped into Rc
};

inline sycl::event attn_prep(sycl::queue &q, const PrepArgs a) {
    if (a.hd != PREP_WG || a.nr > SG || a.ext % PREP_WG) throw std::runtime_error("attn_prep: unsupported shape");
    // R rows: ext / PREP_WG groups per row, one table entry per thread (each group clips the row itself; the first
    // writes it to Rc)
    const int nq = a.ntok * a.nh, nk = a.ntok * a.nkvh, nch = a.ext / PREP_WG, ngroups = nq + 2 * nk + nq * nch;
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
                if (isv && a.vld > 0) a.Vc[(size_t)c * a.vld + a.pos0 + t] = sycl::half(x);
                else (isv ? a.Vc : a.Kc)[(size_t)a.pos0 * kd + i] = sycl::half(x);
                if (t == a.ntok - 1) conv_save(a.st_out, off, c, win);
                return;
            }
            g -= 2 * nk;
            { // R: clip with the per-head scale, the positions, then the bias table (ops::rel_table)
                const int ch = g % nch;
                g /= nch;
                int t = g / a.nh, hh = g % a.nh;
                const float *row = a.R + (size_t)g * a.nr;
                float v = l < a.nr ? row[l] * a.rel_clip[(size_t)hh * a.nr + l] : 0.0f;
                float norm = sycl::sqrt(wg_sum<PREP_WG>(it, v * v, &slm[0])) * 1.0f + 1e-6f;
                float f = sycl::clamp(a.rel_clip_thr / norm, 0.0f, 1.0f);
                if (l < a.nr) {
                    float x = v * f;
                    if (a.full) x = x * a.tau[t];
                    if (ch == 0) a.Rc[(size_t)g * a.nr + l] = x;
                    rs[l] = x;
                }
                sycl::group_barrier(it.get_group());
                const int dd = ch * PREP_WG + l;
                const float *b = a.rel_bias + (size_t)dd * a.nr;
                float s = 0.0f;
                for (int i = 0; i < a.nr; ++i) s += b[i] * rs[i];
                a.tab[(size_t)g * a.ext + dd] = s;
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
// attn_pv_gate2 with U keys per batch (more loads in flight: the kernel waits once per batch) and P read once per
// 16 keys per sub-group (lane l loads key 16b + l; the products take it with select_from_group); each channel still
// adds j ascending from 0, so the result equals attn_pv_gate2's
template <int U>
inline sycl::event attn_pv_gate_u(sycl::queue &q, const float *P, int ldp, const sycl::half *V, int pos0, int ntok, int nh,
                                  int nkvh, int hd, int win, const float *gate, float *out) {
    constexpr int PW = 16;
    static_assert(U % PW == 0);
    const int nd = hd / PW;
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * nh * hd), sycl::range<1>(PW)),
                          [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(PW)]] {
        auto sg = it.get_sub_group();
        const int lane = (int)it.get_local_id(0);
        int g = (int)it.get_group(0), gh = g / nd, t = gh / nh, hh = gh % nh;
        int d = (g % nd) * PW + lane;
        int kvh = hh / (nh / nkvh), p = pos0 + t, lo = win > 0 ? sycl::max(0, p - win + 1) : 0;
        const float *pr = P + (size_t)gh * ldp;
        const int kd = nkvh * hd;
        const sycl::half *vc = V + kvh * hd + d;
        float acc = 0.0f;
        int j = lo;
        for (; j + U - 1 <= p; j += U) {
            float pl[U / PW];
            sycl::half vv[U];
#pragma unroll
            for (int b = 0; b < U / PW; ++b) pl[b] = pr[j - lo + PW * b + lane];
#pragma unroll
            for (int u = 0; u < U; ++u) vv[u] = vc[(size_t)(j + u) * kd];
#pragma unroll
            for (int u = 0; u < U; ++u) acc += sycl::select_from_group(sg, pl[u / PW], u % PW) * (float)vv[u];
        }
        for (; j <= p; ++j) acc += pr[j - lo] * (float)vc[(size_t)j * kd];
        size_t i = (size_t)t * nh * hd + hh * hd + d;
        out[i] = acc * (1.0f / (1.0f + sycl::exp(-gate[i])));
    });
}
// attn_pv_gate2 on the transposed value cache Vt[(kvh*hd + c) * vld + j] (a channel's values over the keys are
// contiguous): lane = channel, 8 keys per 16-byte load, U keys per batch, P as attn_pv_gate_u. Each channel adds j
// ascending from 0 (the keys before the first multiple of 8 one at a time): the result equals attn_pv_gate2's
template <int U>
inline sycl::event attn_pv_t(sycl::queue &q, const float *P, int ldp, const sycl::half *Vt, int vld, int pos0, int ntok, int nh,
                             int nkvh, int hd, int win, const float *gate, float *out) {
    constexpr int PW = 16;
    static_assert(U % PW == 0);
    using HV = sycl::vec<sycl::half, 8>;
    const int nd = hd / PW;
    if (vld % 8) throw std::runtime_error("attn_pv_t: stride not a multiple of 8");
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * nh * hd), sycl::range<1>(PW)),
                          [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(PW)]] {
        auto sg = it.get_sub_group();
        const int lane = (int)it.get_local_id(0);
        int g = (int)it.get_group(0), gh = g / nd, t = gh / nh, hh = gh % nh;
        const int d = (g % nd) * PW + lane;
        int kvh = hh / (nh / nkvh), p = pos0 + t, lo = win > 0 ? sycl::max(0, p - win + 1) : 0;
        const float *pr = P + (size_t)gh * ldp;
        const sycl::half *row = Vt + (size_t)(kvh * hd + d) * vld;
        float acc = 0.0f;
        int j = lo;
        for (; j <= p && (j & 7); ++j) acc += pr[j - lo] * (float)row[j];
        for (; j + U - 1 <= p; j += U) {
            float pl[U / PW];
            HV vv[U / 8];
#pragma unroll
            for (int b = 0; b < U / PW; ++b) pl[b] = pr[j - lo + PW * b + lane];
#pragma unroll
            for (int b = 0; b < U / 8; ++b) vv[b] = *(const HV *)(row + j + 8 * b);
#pragma unroll
            for (int u = 0; u < U; ++u) acc += sycl::select_from_group(sg, pl[u / PW], u % PW) * (float)vv[u / 8][u % 8];
        }
        for (; j <= p; ++j) acc += pr[j - lo] * (float)row[j];
        size_t i = (size_t)t * nh * hd + hh * hd + d;
        out[i] = acc * (1.0f / (1.0f + sycl::exp(-gate[i])));
    });
}
// attn_pv_gate2 with sub-group block reads of V (one message per key: the 16 lanes' channels are 16 consecutive halves
// at one sub-group-uniform address, so no per-lane address arithmetic) and U keys per batch; P as attn_pv_gate_u.
// Each channel adds j ascending from 0: the result equals attn_pv_gate2's
template <int U>
inline sycl::event attn_pv_blk(sycl::queue &q, const float *P, int ldp, const sycl::half *V, int pos0, int ntok, int nh,
                               int nkvh, int hd, int win, const float *gate, float *out) {
    constexpr int PW = 16;
    static_assert(U % PW == 0);
    const int nd = hd / PW;
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * nh * hd), sycl::range<1>(PW)),
                          [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(PW)]] {
        auto sg = it.get_sub_group();
        const int lane = (int)it.get_local_id(0);
        int g = (int)it.get_group(0), gh = g / nd, t = gh / nh, hh = gh % nh;
        const int d0 = (g % nd) * PW;
        int kvh = hh / (nh / nkvh), p = pos0 + t, lo = win > 0 ? sycl::max(0, p - win + 1) : 0;
        const float *pr = P + (size_t)gh * ldp;
        const int kd = nkvh * hd;
        const uint16_t *vb = (const uint16_t *)(V + kvh * hd + d0); // sub-group uniform
        auto vrow = [&](int j) {
            uint16_t u = sg.load(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                const_cast<uint16_t *>(vb + (size_t)j * kd)));
            return (float)sycl::bit_cast<sycl::half>(u);
        };
        float acc = 0.0f;
        int j = lo;
        for (; j + U - 1 <= p; j += U) {
            float pl[U / PW], vv[U];
#pragma unroll
            for (int b = 0; b < U / PW; ++b) pl[b] = pr[j - lo + PW * b + lane];
#pragma unroll
            for (int u = 0; u < U; ++u) vv[u] = vrow(j + u);
#pragma unroll
            for (int u = 0; u < U; ++u) acc += sycl::select_from_group(sg, pl[u / PW], u % PW) * vv[u];
        }
        for (; j <= p; ++j) acc += pr[j - lo] * vrow(j);
        size_t i = (size_t)t * nh * hd + hh * hd + d0 + lane;
        out[i] = acc * (1.0f / (1.0f + sycl::exp(-gate[i])));
    });
}
// attn_pv_gate2 with C consecutive channels per lane (one C-half vector load per key and lane; a sub-group covers
// 16C channels of one head) and U keys per batch, P as attn_pv_gate_u; each channel adds j ascending from 0
template <int C, int U>
inline sycl::event attn_pv_wide(sycl::queue &q, const float *P, int ldp, const sycl::half *V, int pos0, int ntok, int nh,
                                int nkvh, int hd, int win, const float *gate, float *out) {
    constexpr int PW = 16;
    static_assert(U % PW == 0);
    using HV = sycl::vec<sycl::half, C>;
    const int nd = hd / (PW * C);
    if (hd % (PW * C)) throw std::runtime_error("attn_pv_wide: head size");
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * nh * nd * PW), sycl::range<1>(PW)),
                          [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(PW)]] {
        auto sg = it.get_sub_group();
        const int lane = (int)it.get_local_id(0);
        int g = (int)it.get_group(0), gh = g / nd, t = gh / nh, hh = gh % nh;
        int d = (g % nd) * PW * C + lane * C;
        int kvh = hh / (nh / nkvh), p = pos0 + t, lo = win > 0 ? sycl::max(0, p - win + 1) : 0;
        const float *pr = P + (size_t)gh * ldp;
        const int kd = nkvh * hd;
        const sycl::half *vc = V + kvh * hd + d;
        float acc[C];
        for (int c = 0; c < C; ++c) acc[c] = 0.0f;
        int j = lo;
        for (; j + U - 1 <= p; j += U) {
            float pl[U / PW];
            HV vv[U];
#pragma unroll
            for (int b = 0; b < U / PW; ++b) pl[b] = pr[j - lo + PW * b + lane];
#pragma unroll
            for (int u = 0; u < U; ++u) vv[u] = *(const HV *)(vc + (size_t)(j + u) * kd);
#pragma unroll
            for (int u = 0; u < U; ++u) {
                const float pu = sycl::select_from_group(sg, pl[u / PW], u % PW);
#pragma unroll
                for (int c = 0; c < C; ++c) acc[c] += pu * (float)vv[u][c];
            }
        }
        for (; j <= p; ++j) {
            const float pu = pr[j - lo];
            HV v = *(const HV *)(vc + (size_t)j * kd);
            for (int c = 0; c < C; ++c) acc[c] += pu * (float)v[c];
        }
        for (int c = 0; c < C; ++c) {
            size_t i = (size_t)t * nh * hd + hh * hd + d + c;
            out[i] = acc[c] * (1.0f / (1.0f + sycl::exp(-gate[i])));
        }
    });
}
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
// mix_scores for many queries at once (the loop mixes of a whole pass: their states are fixed for the pass): work-group
// (t, s, group of 8 queries), each query's dot product in mix_scores' order; queries j < nqa at qa + j*n, then qb.
// Results at sc[((t * NQ + j) * MIX_MAX + s] (NQ = nqa + nqb), as mix_scores with nq = NQ; inv as mix_scores.
inline sycl::event mix_scores_many(sycl::queue &q, MixArgs a, size_t ld, const float *qa, int nqa, const float *qb, int nqb,
                                   float *inv, float *sc, int n, int ntok) {
    constexpr int QG = 8;
    const int NQ = nqa + nqb, ngq = (NQ + QG - 1) / QG;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(OPS_WG / SG, h), slmq(QG * (OPS_WG / SG), h);
        h.parallel_for(ops::rows_range(ntok * a.ns * ngq), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            int g = (int)it.get_group(0), qg = g % ngq, ts = g / ngq, t = ts / a.ns, s = ts % a.ns, l = (int)it.get_local_id(0);
            const float *x = a.st[s] + (size_t)t * ld;
            float acc = 0.0f;
            for (int i = l; i < n; i += OPS_WG) acc += x[i] * x[i];
            float tot = wg_sum<OPS_WG>(it, acc, &slm[0]);
            float is = 1.0f / sycl::sqrt(tot / n + 1e-6f);
            if (l == 0 && qg == 0) inv[(size_t)t * MIX_MAX + s] = is;
            const float *qp[QG];
            for (int j = 0; j < QG; ++j) {
                int jj = qg * QG + j;
                qp[j] = jj < nqa ? qa + (size_t)jj * n : qb + (size_t)(jj - nqa) * n;
            }
            const int nqg = sycl::min(QG, NQ - qg * QG);
            float dd[QG];
            for (int j = 0; j < QG; ++j) dd[j] = 0.0f;
            for (int i = l; i < n; i += OPS_WG) {
                float xi = x[i] * is;
                for (int j = 0; j < QG; ++j)
                    if (j < nqg) dd[j] += xi * qp[j][i];
            }
            auto sg = it.get_sub_group();
            constexpr int nsg = OPS_WG / SG;
            int sid = (int)sg.get_group_linear_id();
            for (int j = 0; j < QG; ++j) {
                float v = j < nqg ? sg_sum(sg, dd[j]) : 0.0f;
                if (sg.get_local_linear_id() == 0) slmq[j * nsg + sid] = v;
            }
            sycl::group_barrier(it.get_group());
            if (l < nqg) {
                float tt = 0.0f;
                for (int i = 0; i < nsg; ++i) tt += slmq[l * nsg + i];
                sc[((size_t)t * NQ + qg * QG + l) * MIX_MAX + s] = tt;
            }
        });
    });
}
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

// mix with the scores of the saved states (blocks) read from a table: a block's state never changes after it is
// saved, so its rms scale and its dot products with every mix query are computed once, when it is saved (role B,
// below), in mix_scores' order. The current state's scale and score are computed by each output work-group
// (role A), again in mix_scores' order, then the softmax and the output (mix_out) or output + norm (mix_out_norm)
// as those kernels do: results equal mix_scores + mix_out / mix_out_norm bit for bit.
struct MixF {
    const float *st[MIX_MAX]; int ns = 0;  // st[ns-1] = the current state, st[s < ns-1] = blocks (ggml order)
    int slot[MIX_MAX];                     // table slot of st[s], s < ns-1
    const float *query = nullptr; int nq = 0, qi0 = 0; // this call's queries (rows of query); table index of row 0
    float *tinv = nullptr, *tsc = nullptr; int T = 0, NQA = 0; // tinv[slot*T + t], tsc[(slot*T + t)*NQA + qi]
    int mk_slot = -1;                      // >= 0: also save the current state at this slot (role B)
    const uint64_t *qall = nullptr;        // the NQA query rows' addresses
};
template <int MAXV>
inline sycl::event mix_fused_v(sycl::queue &q, MixF a, size_t ld, float *out, const NormOut *nop, float eps, int n, int ntok) {
    // every loop has a constant trip count and is unrolled, so a thread's loads are issued together (these kernels run
    // as a few work-groups, nothing else hides their latency); the additions keep mix_scores' / mix_out's order
    constexpr int QG = 8;
    if (n > MAXV * OPS_WG || a.nq > 3 || a.ns < 1 || a.ns > MIX_MAX) throw std::runtime_error("mix_fused: unsupported shape");
    const NormOut no = nop ? *nop : NormOut{};
    const bool norm = nop != nullptr;
    const int nA = a.nq * ntok, ngq = (a.NQA + QG - 1) / QG, nB = a.mk_slot >= 0 ? ntok * ngq : 0;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(OPS_WG / SG, h), slmq(QG * (OPS_WG / SG), h);
        h.parallel_for(ops::rows_range(nA + nB), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
            int g = (int)it.get_group(0), l = (int)it.get_local_id(0);
            auto sg = it.get_sub_group();
            constexpr int nsg = OPS_WG / SG;
            const int sid = (int)sg.get_group_linear_id();
            const int cs = a.ns - 1;
            const int t = g < nA ? g % ntok : (g - nA) / ngq;
            const float *x = a.st[cs] + (size_t)t * ld;
            float xv[MAXV], qv0[MAXV], wv[MAXV];
            const int j = g < nA ? g / ntok : 0;
            const float *qp0 = a.query ? a.query + (size_t)j * n : x;
            const float *w = norm ? no.w[j] : nullptr;
#pragma unroll
            for (int u = 0; u < MAXV; ++u) {
                int i = l + OPS_WG * u;
                xv[u] = i < n ? x[i] : 0.0f;
                qv0[u] = i < n ? qp0[i] : 0.0f;
                wv[u] = (w && i < n) ? w[i] : 0.0f;
            }
            float acc = 0.0f;
#pragma unroll
            for (int u = 0; u < MAXV; ++u) if (l + OPS_WG * u < n) acc += xv[u] * xv[u];
            float tot = wg_sum<OPS_WG>(it, acc, &slm[0]);
            const float cis = 1.0f / sycl::sqrt(tot / n + 1e-6f);
            if (g >= nA) { // role B: the current state's scale and its dots with every query, into the table
                const int qg = (g - nA) % ngq;
                const size_t row = (size_t)a.mk_slot * a.T + t;
                if (l == 0 && qg == 0) a.tinv[row] = cis;
                const int nqg = sycl::min(QG, a.NQA - qg * QG);
                float dd[QG];
#pragma unroll
                for (int j = 0; j < QG; ++j) {
                    const float *qp = (const float *)a.qall[sycl::min(qg * QG + j, a.NQA - 1)];
                    float qv[MAXV];
#pragma unroll
                    for (int u = 0; u < MAXV; ++u) { int i = l + OPS_WG * u; qv[u] = i < n ? qp[i] : 0.0f; }
                    float d0 = 0.0f;
#pragma unroll
                    for (int u = 0; u < MAXV; ++u) if (l + OPS_WG * u < n) d0 += (xv[u] * cis) * qv[u];
                    dd[j] = d0;
                }
#pragma unroll
                for (int j = 0; j < QG; ++j) {
                    float v = j < nqg ? sg_sum(sg, dd[j]) : 0.0f;
                    if (sg.get_local_linear_id() == 0) slmq[j * nsg + sid] = v;
                }
                sycl::group_barrier(it.get_group());
                if (l < nqg) {
                    float tt = 0.0f;
                    for (int i = 0; i < nsg; ++i) tt += slmq[l * nsg + i];
                    a.tsc[row * a.NQA + qg * QG + l] = tt;
                }
                return;
            }
            // role A: output j for token t (mix_out_norm's group order)
            float iv[MIX_MAX], scr[MIX_MAX];
#pragma unroll
            for (int s = 0; s < MIX_MAX; ++s) {
                iv[s] = 0.0f; scr[s] = 0.0f;
                if (s < cs) {
                    const size_t row = (size_t)a.slot[s] * a.T + t;
                    iv[s] = a.tinv[row];
                    scr[s] = a.tsc[row * a.NQA + a.qi0 + j];
                }
            }
            {
                float dd = 0.0f;
#pragma unroll
                for (int u = 0; u < MAXV; ++u) if (l + OPS_WG * u < n) dd += (xv[u] * cis) * qv0[u];
                float v = sg_sum(sg, dd);
                if (sg.get_local_linear_id() == 0) slmq[sid] = v;
            }
            sycl::group_barrier(it.get_group());
            float csc = 0.0f;
            for (int i = 0; i < nsg; ++i) csc += slmq[i];
#pragma unroll
            for (int s = 0; s < MIX_MAX; ++s) if (s == cs) { iv[s] = cis; scr[s] = csc; }
            float scale = 1.0f / sycl::sqrt((float)n), mx = -INFINITY;
#pragma unroll
            for (int s = 0; s < MIX_MAX; ++s) if (s < a.ns) mx = sycl::fmax(mx, scr[s] * scale);
            float p[MIX_MAX], sum = 0.0f;
#pragma unroll
            for (int s = 0; s < MIX_MAX; ++s) { p[s] = 0.0f; if (s < a.ns) { p[s] = sycl::exp(scr[s] * scale - mx); sum += p[s]; } }
            float isum = 1.0f / sum;
#pragma unroll
            for (int s = 0; s < MIX_MAX; ++s) p[s] *= isum;
            float ov[MAXV];
#pragma unroll
            for (int u = 0; u < MAXV; ++u) ov[u] = 0.0f;
#pragma unroll
            for (int s = 0; s < MIX_MAX; ++s) {
                if (s < cs) { // the current state is in registers
                    const float *xs = a.st[s] + (size_t)t * ld;
                    float sv[MAXV];
#pragma unroll
                    for (int u = 0; u < MAXV; ++u) { int i = l + OPS_WG * u; sv[u] = i < n ? xs[i] : 0.0f; }
#pragma unroll
                    for (int u = 0; u < MAXV; ++u) ov[u] += (sv[u] * iv[s]) * p[s];
                } else if (s == cs) {
#pragma unroll
                    for (int u = 0; u < MAXV; ++u) ov[u] += (xv[u] * iv[s]) * p[s];
                }
            }
            float ss = 0.0f;
#pragma unroll
            for (int u = 0; u < MAXV; ++u) {
                int i = l + OPS_WG * u;
                if (i < n) {
                    if (out) out[((size_t)j * ntok + t) * n + i] = ov[u];
                    ss += ov[u] * ov[u];
                }
            }
            if (!norm) return;
            float tot2 = wg_sum<OPS_WG>(it, ss, &slm[0]);
            float rs = 1.0f / sycl::sqrt(tot2 / n + eps);
            float *yr = no.y[j] + (size_t)t * n;
#pragma unroll
            for (int u = 0; u < MAXV; ++u) {
                int i = l + OPS_WG * u;
                if (i < n) yr[i] = w ? (ov[u] * rs) * wv[u] : ov[u] * rs;
            }
        });
    });
}
inline sycl::event mix_fused(sycl::queue &q, MixF a, size_t ld, float *out, const NormOut *nop, float eps, int n, int ntok) {
    if (n <= 9 * OPS_WG) return mix_fused_v<9>(q, a, ld, out, nop, eps, n, ntok);
    return mix_fused_v<12>(q, a, ld, out, nop, eps, n, ntok);
}
// up to 4 ops::rms_norm calls of the same row length in one launch (each with its own input, output and weight)
struct NormJob { const float *x; float *y; const float *w; int ldx, ldy; };
inline sycl::event rms_norm_multi(sycl::queue &q, const NormJob *jobs, int njobs, int n, int nrows, float eps) {
    if (njobs < 1 || njobs > 8) throw std::runtime_error("rms_norm_multi: 1 to 8 jobs");
    struct J4 { NormJob j[8]; } jb{};
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
