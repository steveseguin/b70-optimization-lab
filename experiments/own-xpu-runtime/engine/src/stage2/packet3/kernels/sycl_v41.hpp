// SYCL device kernels for the DeepSeek V4.1 op set (plan_v41.hpp /
// ops_v41.hpp). Each kernel mirrors its ops41:: host anchor's equation and
// reduction order; pure mul/add paths are bit-exact vs host, paths through
// exp/sigmoid/silu admit +-1 bf16 ulp (device vs host libm), same rule as
// the SC117 identity-v2 gates.
#pragma once
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#include "stage2/packet2/kernels/math.hpp"
#include "stage2/packet3/kernels/ops_v41.hpp"

namespace ops41sycl {
using iq3::Type;

// SG32 butterfly in tree32 pairing order (width 1,2,4,8,16; i += 2w).
inline float sg_tree32(sycl::sub_group sg, float v) {
    unsigned l = sg.get_local_linear_id();
    for (unsigned w = 1; w < 32; w *= 2) {
        float o = sycl::select_from_group(sg, v, (l + w) % 32);
        if (l % (2 * w) == 0) v = v + o;
    }
    return sycl::select_from_group(sg, v, 0);
}

// gemv over one quantized row: lane l sums k = l, l+32, ... serially
// (iq3::lane_dot order), tree32 butterfly, bf16 RNE out. One sub-group per
// row; global id = row.
// rmsnorm: y[i] = w[i] * x[i] / sqrt(mean(x^2)+eps). Host runner accumulates
// x^2 serially in double; device uses SG32 strided lanes + tree32 in double,
// same math different order -> gate at +-1 bf16 ulp.
struct RmsNorm {
    int n;
    void operator()(sycl::nd_item<1> it, const uint16_t *x, const float *w,
                    uint16_t *y) const {
        int lane = it.get_local_linear_id();
        sycl::sub_group sg = it.get_sub_group();
        int base = it.get_group_linear_id() * n;
        double acc = 0;
        for (int i = lane; i < n; i += 32) {
            float v = ops41::bf16(x[base + i]);
            acc += double(v) * v;
        }
        for (int w_ = 16; w_; w_ >>= 1)
            acc += sycl::select_from_group(sg, acc, lane ^ w_);
        float rs = float(1.0 / sycl::sqrt(acc / n + 1e-20));
        for (int i = lane; i < n; i += 32)
            y[base + i] = ops41::bf16b(w[i] * (ops41::bf16(x[base + i]) * rs));
    }
};

struct Gemv {
    Type wtype; unsigned rows, cols; // x is bf16
    bool f32out = false;             // logits parity: skip bf16 rounding
    void operator()(sycl::nd_item<1> it, const uint8_t *w, size_t row_bytes_,
                    const uint16_t *x, void *yv) const {
        auto sg = it.get_sub_group();
        unsigned l = sg.get_local_linear_id();
        unsigned r = it.get_group_linear_id();
        const uint8_t *row = w + (size_t)r * row_bytes_;
        float sum = 0;
        for (unsigned k = l; k < cols; k += 32)
            sum = sum + iq3::element(wtype, row, k) * ops41::bf16(x[k]);
        sum = sg_tree32(sg, sum);
        if (l == 0) {
            if (f32out) reinterpret_cast<float *>(yv)[r] = sum;
            else reinterpret_cast<uint16_t *>(yv)[r] = ops41::bf16b(sum);
        }
    }
};

// rope rotate tail rdim of each row, adjacent pairs. Pairs are independent:
// parallel over (row, pair) is bit-identical to the host serial loop.
struct RopePairs {
    unsigned rows, d, rdim; bool inverse;
    void operator()(sycl::nd_item<1> it, uint16_t *x, const float *cosb, const float *sinb) const {
        unsigned g = it.get_global_linear_id();
        unsigned pairs = rdim / 2;
        unsigned r = g / pairs, i = g % pairs;
        if (r >= rows) return;
        uint16_t *row = x + (size_t)r * d + (d - rdim);
        float re = ops41::bf16(row[2 * i]), im = ops41::bf16(row[2 * i + 1]);
        float c = cosb[i], s = inverse ? -sinb[i] : sinb[i];
        row[2 * i] = ops41::bf16b(re * c - im * s);
        row[2 * i + 1] = ops41::bf16b(re * s + im * c);
    }
};

// swiglu_clamp elementwise (one item per element; order-free).
struct Swiglu {
    long long n; float lim;
    void operator()(sycl::nd_item<1> it, const uint16_t *gate, const uint16_t *up, uint16_t *out) const {
        long long i = it.get_global_linear_id();
        if (i >= n) return;
        float g = sycl::fmin(ops41::bf16(gate[i]), lim);
        float u = sycl::clamp(ops41::bf16(up[i]), -lim, lim);
        out[i] = ops41::bf16b(g / (1.0f + sycl::exp(-g)) * u);
    }
};
struct ProbScale {
    int rows, n;
    void operator()(sycl::nd_item<1> it, uint16_t *act, const float *prob) const {
        int g = it.get_global_linear_id();
        int r = g / n, i = g % n;
        if (r >= rows) return;
        act[(size_t)r * n + i] = ops41::bf16b(prob[r] * ops41::bf16(act[(size_t)r * n + i]));
    }
};
struct MoeCombine {
    int top, h;
    void operator()(sycl::nd_item<1> it, const uint16_t *exps, const uint16_t *shared, uint16_t *out) const {
        int i = it.get_global_linear_id();
        if (i >= h) return;
        float acc = ops41::bf16(shared[i]);
        for (int r = 0; r < top; ++r) acc += ops41::bf16(exps[(size_t)r * h + i]);
        out[i] = ops41::bf16b(acc);
    }
};

// hc_pre: out[i] = sum_j mix[j] * streams[j][i] (serial over 4, host order).
struct HcPre {
    int h;
    void operator()(sycl::nd_item<1> it, const uint16_t *streams, const float *mix, uint16_t *out) const {
        int i = it.get_global_linear_id();
        if (i >= h) return;
        float acc = 0;
        for (int j = 0; j < 4; ++j) acc += mix[j] * ops41::bf16(streams[(size_t)j * h + i]);
        out[i] = ops41::bf16b(acc);
    }
};
// hc_post: streams'[j][i] = post[j]*x[i] + sum_k comb[k][j]*old[k][i]
// (comb is [src][dst], official Block.hc_post).
// `old` is a snapshot of streams (device memcpy first): in-place reads would
// race across work-items.
struct HcPost {
    int h;
    void operator()(sycl::nd_item<1> it, uint16_t *streams, const uint16_t *old,
                    const uint16_t *x, const float *post, const float *comb) const {
        int g = it.get_global_linear_id();
        int j = g / h, i = g % h;
        if (j >= 4) return;
        float acc = post[j] * ops41::bf16(x[i]);
        for (int k = 0; k < 4; ++k) acc += comb[k * 4 + j] * ops41::bf16(old[(size_t)k * h + i]);
        streams[(size_t)j * h + i] = ops41::bf16b(acc);
    }
};
struct HcMean {
    int h;
    void operator()(sycl::nd_item<1> it, const uint16_t *streams, uint16_t *out) const {
        int i = it.get_global_linear_id();
        if (i >= h) return;
        float acc = 0;
        for (int j = 0; j < 4; ++j) acc += ops41::bf16(streams[(size_t)j * h + i]);
        out[i] = ops41::bf16b(acc / 4);
    }
};

// window_append: one item; copies kv into ring slot, emits oldest-first idxs.
struct WindowAppend {
    int win, d, start_pos;
    void operator()(sycl::nd_item<1> it, uint16_t *ring, const uint16_t *kv, int32_t *idxs) const {
        if (it.get_global_linear_id() != 0) return;
        for (int i = 0; i < d; ++i) ring[(size_t)(start_pos % win) * d + i] = kv[i];
        int oldest = (start_pos % win + 1) % win; // wraps to slot 0 at win-1
        for (int i = 0, j = oldest; i < win; ++i, j = (j + 1) % win)
            idxs[i] = j > start_pos ? -1 : j;
    }
};

// sparse_attn decode row: one work-item per head; serial slot order as host.
// Dual bases: slot < win_rows reads the window ring, else kvc at
// slot-win_rows (compress mirror) -- matching the runner's win_ptr/comp_ptr.
struct SparseAttn {
    int n_idx, heads, hd, win_rows;
    void operator()(sycl::nd_item<1> it, const uint16_t *q, const uint16_t *kvw,
                    const uint16_t *kvc, const float *sinks, const int32_t *idxs,
                    float *out) const {
        int h = it.get_global_linear_id();
        if (h >= heads) return;
        const float scale = 1.0f / sycl::sqrt(float(hd));
        const uint16_t *qh = q + (size_t)h * hd;
        float logits[641]; // 128 window + 512 compress + sink
        logits[0] = sinks[h];
        int live = 1;
        for (int i = 0; i < n_idx; ++i) {
            int slot = idxs[i];
            if (slot < 0) continue;
            const uint16_t *k = slot < win_rows ? kvw + (size_t)slot * hd
                                                : kvc + (size_t)(slot - win_rows) * hd;
            float acc = 0;
            for (int j = 0; j < hd; ++j) acc += ops41::bf16(qh[j]) * ops41::bf16(k[j]);
            logits[live++] = acc * scale;
        }
        float mx = logits[0];
        for (int i = 1; i < live; ++i) mx = logits[i] > mx ? logits[i] : mx;
        float sum = 0;
        for (int i = 0; i < live; ++i) { logits[i] = sycl::exp(logits[i] - mx); sum += logits[i]; }
        float *o = out + (size_t)h * hd;
        for (int j = 0; j < hd; ++j) o[j] = 0;
        int li = 1;
        for (int i = 0; i < n_idx && li < live; ++i) {
            int slot = idxs[i];
            if (slot < 0) continue;
            float w = logits[li++] / sum;
            const uint16_t *k = slot < win_rows ? kvw + (size_t)slot * hd
                                                : kvc + (size_t)(slot - win_rows) * hd;
            for (int j = 0; j < hd; ++j) o[j] += w * ops41::bf16(k[j]);
        }
    }
};

// compressor decode pooling: one item; kv_state/score_state [r][hd] f32,
// softmax per channel over slots, weighted sum, then RMSNorm into out.
struct CompressPool {
    int r, hd;
    void operator()(sycl::nd_item<1> it, const float *kv_state, const float *score_state,
                    const float *nw, uint16_t *out) const {
        if (it.get_global_linear_id() != 0) return;
        float tmp[512];
        for (int i = 0; i < hd; ++i) {
            float mx = score_state[i];
            for (int j = 1; j < r; ++j) mx = score_state[j * hd + i] > mx ? score_state[j * hd + i] : mx;
            float sum = 0, acc = 0;
            for (int j = 0; j < r; ++j) sum += sycl::exp(score_state[j * hd + i] - mx);
            for (int j = 0; j < r; ++j)
                acc += kv_state[j * hd + i] * (sycl::exp(score_state[j * hd + i] - mx) / sum);
            tmp[i] = acc;
        }
        double sq = 0;
        for (int i = 0; i < hd; ++i) sq += double(tmp[i]) * tmp[i];
        float rs = float(1.0 / sycl::sqrt(sq / hd + 1e-20));
        for (int i = 0; i < hd; ++i) out[i] = ops41::bf16b(nw[i] * (tmp[i] * rs));
    }
};

// indexer score: one item per (query, slot); serial head order as host.
struct IndexerScore {
    int H, dk, T_, m;
    void operator()(sycl::nd_item<1> it, const uint16_t *q, const uint16_t *k,
                    const uint16_t *w, const int64_t *lens, float *score) const {
        int g = it.get_global_linear_id();
        int t = g / T_, j = g % T_;
        if (t >= m) return;
        if (j >= lens[t]) { score[(size_t)t * T_ + j] = -INFINITY; return; }
        float s = 0;
        for (int hh = 0; hh < H; ++hh) {
            float d = 0;
            for (int i = 0; i < dk; ++i)
                d += ops41::bf16(q[((size_t)t * H + hh) * dk + i]) * ops41::bf16(k[(size_t)j * dk + i]);
            s += (d > 0 ? d : 0) * ops41::bf16(w[(size_t)t * H + hh]);
        }
        score[(size_t)t * T_ + j] = s;
    }
};
// indexer topk: one item per query; selection order as host (desc value,
// asc index ties), re-sorted ascending, +offset, >=len -> -1.
struct IndexerTopk {
    int T_, k, offset;
    void operator()(sycl::nd_item<1> it, const float *score, const int64_t *lens, int32_t *out) const {
        int t = it.get_global_linear_id();
        int len = (int)lens[t];
        int32_t sel[512];
        int nk = k < len ? k : len;
        for (int i = 0; i < nk; ++i) {
            int best = -1;
            for (int j = 0; j < T_; ++j) {
                bool taken = false;
                for (int s2 = 0; s2 < i; ++s2) if (sel[s2] == j) { taken = true; break; }
                if (taken) continue;
                if (best < 0 || score[(size_t)t * T_ + j] > score[(size_t)t * T_ + best] ||
                    (score[(size_t)t * T_ + j] == score[(size_t)t * T_ + best] && j < best)) best = j;
            }
            sel[i] = best;
        }
        // insertion sort ascending (nk small relative to 512; host used std::sort)
        for (int i = 1; i < nk; ++i) {
            int32_t v = sel[i];
            int j = i - 1;
            while (j >= 0 && sel[j] > v) { sel[j + 1] = sel[j]; --j; }
            sel[j + 1] = v;
        }
        for (int i = 0; i < k; ++i)
            out[(size_t)t * k + i] = i < nk ? sel[i] + offset : -1;
    }
};

// engram_gate: one item per hc copy; double accumulators in host order.
struct EngramGate {
    int h;
    void operator()(sycl::nd_item<1> it, uint16_t *streams, const uint16_t *kvbuf,
                    const float *gate_w) const {
        int j = it.get_global_linear_id();
        if (j >= 4) return;
        const float eps = 1e-20f, clamp_v = 1e-6f;
        double hsq = 0, ksq = 0;
        for (int i = 0; i < h; ++i) {
            float hv = ops41::bf16(streams[(size_t)j * h + i]);
            hsq += double(hv) * hv;
            float kvv = ops41::bf16(kvbuf[(size_t)j * h + i]);
            ksq += double(kvv) * kvv;
        }
        double dot = 0;
        for (int i = 0; i < h; ++i)
            dot += double(ops41::bf16(streams[(size_t)j * h + i])) * gate_w[(size_t)j * h + i] *
                   ops41::bf16(kvbuf[(size_t)j * h + i]);
        float rstd = float(1.0 / sycl::sqrt(hsq / h + eps) * (1.0 / sycl::sqrt(ksq / h + eps)));
        float d = float(dot) * rstd / sycl::sqrt(float(h));
        float g = 1.0f / (1.0f + sycl::exp(-sycl::copysign(sycl::sqrt(sycl::fmax(sycl::fabs(d), clamp_v)), d)));
        for (int i = 0; i < h; ++i)
            streams[(size_t)j * h + i] =
                ops41::bf16b(ops41::bf16(streams[(size_t)j * h + i]) + g * ops41::bf16(kvbuf[(size_t)4 * h + i]));
    }
};

// gemv_grouped: SG32 per row, bf16 weights; lane_dot order + tree32.
struct GemvGrouped {
    int groups, n, k;
    void operator()(sycl::nd_item<1> it, const uint16_t *o, const uint16_t *w, uint16_t *out) const {
        auto sg = it.get_sub_group();
        unsigned l = sg.get_local_linear_id();
        unsigned r = it.get_group_linear_id(); // [0, groups*n)
        int g = r / n;
        const uint16_t *row = w + (size_t)r * k;
        const uint16_t *xg = o + (size_t)g * k;
        float sum = 0;
        for (int i = l; i < k; i += 32)
            sum = sum + ops41::bf16(row[i]) * ops41::bf16(xg[i]);
        sum = sg_tree32(sg, sum);
        if (l == 0) out[r] = ops41::bf16b(sum);
    }
};

// gemv_grouped over a QUANTIZED weight ([groups*n, k] rows of any iq3 type):
// row r belongs to group r/n and reads that group's k-slice of o. Same lane
// order + tree32 as Gemv.
struct GemvGroupedQ {
    iq3::Type wtype; unsigned n, k;
    void operator()(sycl::nd_item<1> it, const uint8_t *w, size_t row_bytes_,
                    const uint16_t *o, uint16_t *out) const {
        auto sg = it.get_sub_group();
        unsigned l = sg.get_local_linear_id();
        unsigned r = it.get_group_linear_id();
        const uint8_t *row = w + (size_t)r * row_bytes_;
        const uint16_t *xg = o + (size_t)(r / n) * k;
        float sum = 0;
        for (unsigned i = l; i < k; i += 32)
            sum = sum + iq3::element(wtype, row, i) * ops41::bf16(xg[i]);
        sum = sg_tree32(sg, sum);
        if (l == 0) out[r] = ops41::bf16b(sum);
    }
};

// route41 on f32 logits (official model.py computes the router in F32;
// llama.cpp pins GGML_PREC_F32 on the same node). Same order as Route.
struct RouteF32 {
    int experts, topk;
    void operator()(sycl::nd_item<1> it, const float *logits, const float *bias,
                    uint32_t *ids, float *prob) const {
        if (it.get_global_linear_id() != 0) return;
        float s[384], sb[384];
        for (int i = 0; i < experts; ++i) {
            s[i] = sycl::sqrt(sycl::log1p(sycl::exp(logits[i])));
            sb[i] = s[i] + bias[i];
        }
        float sum = 0;
        for (int t = 0; t < topk; ++t) {
            int best = -1;
            for (int i = 0; i < experts; ++i)
                if (best < 0 || sb[i] > sb[best]) best = i;
            ids[t] = (uint32_t)best;
            prob[t] = s[best];
            sum += s[best];
            sb[best] = -INFINITY;
        }
        for (int t = 0; t < topk; ++t) prob[t] = prob[t] / (sum + 1e-20f) * 1.5f;
    }
};

// hc_mix phase A: 24 items, serial double dot over 4*h in host order -> m[24].
// The rsqrt statistic is recomputed per item (grid-wide sync impossible in
// one launch); identical value everywhere since the loop order is fixed.
struct HcMixDots {
    int h;
    void operator()(sycl::nd_item<1> it, const uint16_t *streams, const float *fn, float *m24) const {
        int j = it.get_global_linear_id();
        if (j >= 24) return;
        int N = 4 * h;
        double sq = 0;
        for (int i = 0; i < N; ++i) { float v = ops41::bf16(streams[i]); sq += double(v) * v; }
        float rsqrt = float(1.0 / sycl::sqrt(sq / N + 1e-20));
        double acc = 0;
        for (int i = 0; i < N; ++i) acc += double(fn[(size_t)j * N + i]) * ops41::bf16(streams[i]);
        m24[j] = float(acc) * rsqrt;
    }
};
// hc_mix phase B: one item: split + sigmoid + 20 sinkhorn iters, host order.
struct HcMixFinish {
    void operator()(sycl::nd_item<1> it, const float *m24, const float *scale, const float *base,
                    float *pre, float *post, float *comb) const {
        if (it.get_global_linear_id() != 0) return;
        auto sig = [](float v) { return 1.0f / (1.0f + sycl::exp(-v)); };
        const float eps = 1e-6f;
        for (int j = 0; j < 4; ++j) pre[j] = sig(m24[j] * scale[0] + base[j]) + eps;
        for (int j = 0; j < 4; ++j) post[j] = 2.0f * sig(m24[4 + j] * scale[1] + base[4 + j]);
        for (int j = 0; j < 16; ++j) comb[j] = m24[8 + j] * scale[2] + base[8 + j];
        for (int j = 0; j < 4; ++j) {
            float mx = comb[j * 4];
            for (int k = 1; k < 4; ++k) mx = comb[j * 4 + k] > mx ? comb[j * 4 + k] : mx;
            float s = 0;
            for (int k = 0; k < 4; ++k) { comb[j * 4 + k] = sycl::exp(comb[j * 4 + k] - mx); s += comb[j * 4 + k]; }
            for (int k = 0; k < 4; ++k) comb[j * 4 + k] = comb[j * 4 + k] / s + eps;
        }
        for (int it2 = 0; it2 < 20; ++it2) {
            if (it2 > 0)
                for (int j = 0; j < 4; ++j) {
                    float s = 0;
                    for (int k = 0; k < 4; ++k) s += comb[j * 4 + k];
                    for (int k = 0; k < 4; ++k) comb[j * 4 + k] /= (s + eps);
                }
            for (int k = 0; k < 4; ++k) {
                float s = 0;
                for (int j = 0; j < 4; ++j) s += comb[j * 4 + k];
                for (int j = 0; j < 4; ++j) comb[j * 4 + k] /= (s + eps);
            }
        }
    }
};

// route41: single work-item; ops41::route order. s = sqrt(log1p(exp(logit))),
// top-k by s+bias (strict > keeps lowest id on ties), prob = s/(sum+1e-20)*1.5.
// logits bf16 buffer, bias f32, prob f32 out (feeds prob_scale41).
struct Route {
    int experts, topk;
    void operator()(sycl::nd_item<1> it, const uint16_t *logits,
                    const float *bias, uint32_t *ids, float *prob) const {
        if (it.get_global_linear_id() != 0) return;
        float s[384], sb[384];
        for (int i = 0; i < experts; ++i) {
            s[i] = sycl::sqrt(sycl::log1p(sycl::exp(ops41::bf16(logits[i]))));
            sb[i] = s[i] + bias[i];
        }
        float sum = 0;
        for (int t = 0; t < topk; ++t) {
            int best = -1;
            for (int i = 0; i < experts; ++i)
                if (best < 0 || sb[i] > sb[best]) best = i;
            ids[t] = (uint32_t)best;
            prob[t] = s[best];
            sum += s[best];
            sb[best] = -INFINITY;
        }
        for (int t = 0; t < topk; ++t) prob[t] = prob[t] / (sum + 1e-20f) * 1.5f;
    }
};

// argmax over f32 logits, tree reduce with first-max tie-break (host
// std::max_element order). One work-group; block partials then serial tail.
struct Argmax {
    int n;
    void operator()(sycl::nd_item<1> it, const float *logits, int32_t *out,
                    float *scratch) const {
        int lane = it.get_local_linear_id();
        sycl::sub_group sg = it.get_sub_group();
        float bv = -INFINITY; int bi = n;
        for (int i = lane; i < n; i += 32)
            if (logits[i] > bv) { bv = logits[i]; bi = i; }
        for (int w = 16; w; w >>= 1) {
            float ov = sycl::select_from_group(sg, bv, lane ^ w);
            int oi = sycl::select_from_group(sg, bi, lane ^ w);
            if (ov > bv || (ov == bv && oi < bi)) { bv = ov; bi = oi; }
        }
        if (lane == 0) *out = bi;
    }
};

// embedding row: decode one quant row to bf16 (engram-free token lookup).
struct EmbedRow {
    iq3::Type t; int cols;
    void operator()(sycl::nd_item<1> it, const uint8_t *row, uint16_t *out) const {
        int i = it.get_global_linear_id();
        if (i >= cols) return;
        auto l = iq3::layout(t);
        out[i] = ops41::bf16b(
            iq3::decode(t, row + (size_t)(i / l.elements) * l.bytes, i % l.elements));
    }
};

// candidate mask application: score[j] = mask[j] ? score[j] : -inf
struct MaskApply {
    int T_;
    void operator()(sycl::nd_item<1> it, float *score, const uint8_t *mask) const {
        int j = it.get_global_linear_id();
        if (j >= T_) return;
        if (!mask[j]) score[j] = -INFINITY;
    }
};

// f32 -> bf16 row convert (sparse_attn f32 out feeds rope/grouped gemv in bf16)
struct ToBf16 {
    int n;
    void operator()(sycl::nd_item<1> it, const float *x, uint16_t *y) const {
        int i = it.get_global_linear_id();
        if (i >= n) return;
        y[i] = ops41::bf16b(x[i]);
    }
};

// broadcast: streams[j][i] = x[i] for all 4 streams (identity at token start).
struct Broadcast4 {
    int h;
    void operator()(sycl::nd_item<1> it, const uint16_t *x, uint16_t *streams) const {
        int i = it.get_global_linear_id();
        if (i >= h) return;
        uint16_t v = x[i];
        for (int j = 0; j < 4; ++j) streams[(size_t)j * h + i] = v;
    }
};

// routed_gemv: group per (slot, row); expert bank row = ids[slot]*rows + row.
// Lane order/tree32 identical to Gemv -> bit-exact vs host per-expert gemv.
struct RoutedGemv {
    iq3::Type t; unsigned rows, cols; // per-expert matrix shape
    bool per_slot_x = false;          // down: x is [6][cols], one row per slot
    void operator()(sycl::nd_item<1> it, const uint8_t *w, const uint16_t *x,
                    const uint32_t *ids, uint16_t *out) const {
        unsigned g = it.get_global_linear_id();
        unsigned slot = g / (rows * 32), r = (g / 32) % rows;
        if (slot >= 6) return;
        auto l = iq3::layout(t);
        size_t rb = (size_t)(cols / l.elements) * l.bytes;
        const uint8_t *row = w + ((size_t)ids[slot] * rows + r) * rb;
        sycl::sub_group sg = it.get_sub_group();
        int lane = it.get_local_linear_id();
        const uint16_t *xs = per_slot_x ? x + (size_t)slot * cols : x;
        float a = iq3::lane_dot(t, row, xs, iq3::Type::BF16, cols, lane);
        for (int w_ = 16; w_; w_ >>= 1)
            a += sycl::select_from_group(sg, a, lane ^ w_);
        if (lane == 0) out[slot * rows + r] = ops41::bf16b(a);
    }
};

// bf16 -> f32 (compressor group state writes)
struct ToF32 {
    int n;
    void operator()(sycl::nd_item<1> it, const uint16_t *x, float *y) const {
        int i = it.get_global_linear_id();
        if (i >= n) return;
        y[i] = ops41::bf16(x[i]);
    }
};

// candidate blocks (layer 20, decode m=1): per-channel max over 8-blocks,
// last block forced, top-2048 selection (fixture select_candidate_blocks
// order: strict >, first-max ties, -inf dropped), mask bytes out.
struct CandidateBlocks {
    int T_, bs, topk_blocks;
    void operator()(sycl::nd_item<1> it, const float *score, const int64_t *lens,
                    uint8_t *mask) const {
        if (it.get_global_linear_id() != 0) return;
        int nb = (T_ + bs - 1) / bs;
        float bsc[2048];
        for (int b = 0; b < nb; ++b) bsc[b] = -INFINITY;
        for (int j = 0; j < T_; ++j) {
            float v = score[j];
            if (v > bsc[j / bs]) bsc[j / bs] = v;
        }
        int last = (int)((lens[0] - 1) / bs);
        bsc[last] = INFINITY;
        uint8_t keep[2048] = {};
        for (int i = 0; i < topk_blocks && i < nb; ++i) {
            int best = -1;
            for (int b = 0; b < nb; ++b) {
                if (keep[b]) continue;
                if (best < 0 || bsc[b] > bsc[best] || (bsc[b] == bsc[best] && b < best)) best = b;
            }
            if (best < 0 || bsc[best] == -INFINITY) break;
            keep[best] = 1;
        }
        for (int j = 0; j < T_; ++j) mask[j] = keep[j / bs];
    }
};

} // namespace ops41sycl
#endif
