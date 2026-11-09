// Independent attention-unit implementations for DeepSeek V4.1.
// Semantics from official inference/{model,kernel}.py (MIT). See
// test_attn.cpp for the gates and dump shapes.
#pragma once
#include <algorithm>
#include <cmath>
#include <limits>
#include <cstdint>
#include <vector>

namespace dsv41 {

// A1: sparse attention core. For each (query t, head hh): valid idxs (>=0),
// logits = scale*(q.kv) + attn_sink as extra logit, softmax, weighted sum.
// All-invalid row -> zero output (kernel convention via -1e30 bound).
template <typename T>
inline void sparse_attn_core(const T *q, const T *kv, const T *sink, const int32_t *idxs,
                             T scale, T *out, int m, int h, int d, int topk) {
    for (int t = 0; t < m; ++t)
        for (int hh = 0; hh < h; ++hh) {
            T *o = out + (t * h + hh) * d;
            const T *qh = q + (t * h + hh) * d;
            // gather valid
            std::vector<T> logits;
            std::vector<int> rows;
            for (int j = 0; j < topk; ++j) {
                int32_t r = idxs[t * topk + j];
                if (r < 0) continue;
                const T *k = kv + (size_t)r * d;
                T s = 0;
                for (int i = 0; i < d; ++i) s += qh[i] * k[i];
                logits.push_back(s * scale);
                rows.push_back(r);
            }
            if (rows.empty()) {
                for (int i = 0; i < d; ++i) o[i] = 0;
                continue;
            }
            logits.push_back(sink[hh]);
            T mx = logits[0];
            for (T v : logits) mx = v > mx ? v : mx;
            T sum = 0;
            for (T v : logits) sum += std::exp(v - mx);
            for (int i = 0; i < d; ++i) o[i] = 0;
            for (size_t j = 0; j < rows.size(); ++j) {
                T p = std::exp(logits[j] - mx) / sum;
                const T *k = kv + (size_t)rows[j] * d;
                for (int i = 0; i < d; ++i) o[i] += p * k[i];
            }
        }
}

// A2: compressor pooling (ratio r) + RMSNorm.
// kv/score: [groups][r][hd]; y = rmsnorm( sum_r softmax(score) * kv ) * nw
template <typename T>
inline void compress_pool(const T *kv, const T *score, const T *nw, T *out,
                          int groups, int r, int hd, T eps) {
    for (int g = 0; g < groups; ++g) {
        const T *sc = score + g * r * hd;
        std::vector<T> w(r * hd);
        for (int i = 0; i < hd; ++i) {
            T mx = sc[i];
            for (int j = 1; j < r; ++j) mx = sc[j * hd + i] > mx ? sc[j * hd + i] : mx;
            T sum = 0;
            for (int j = 0; j < r; ++j) { w[j * hd + i] = std::exp(sc[j * hd + i] - mx); sum += w[j * hd + i]; }
            T acc = 0;
            for (int j = 0; j < r; ++j) acc += kv[g * r * hd + j * hd + i] * (w[j * hd + i] / sum);
            out[g * hd + i] = acc;
        }
    }
    // RMSNorm over hd per group, weighted
    for (int g = 0; g < groups; ++g) {
        T v = 0;
        for (int i = 0; i < hd; ++i) v += out[g * hd + i] * out[g * hd + i];
        T rs = T(1) / std::sqrt(v / hd + eps);
        for (int i = 0; i < hd; ++i) out[g * hd + i] = out[g * hd + i] * rs * nw[i];
    }
}

// A3: indexer score = sum_h relu(q.k) * w, causal mask, topk sorted, offset.
// Returns also the masked score matrix for the candidate-block gate.
template <typename T>
inline void indexer_score(const T *q, const T *k, const T *w, int m, int H, int dk, int T_,
                          const int64_t *lens, T *score_out) {
    for (int t = 0; t < m; ++t)
        for (int j = 0; j < T_; ++j) {
            T s = 0;
            for (int hh = 0; hh < H; ++hh) {
                T d = 0;
                for (int i = 0; i < dk; ++i) d += q[(t * H + hh) * dk + i] * k[(size_t)j * dk + i];
                s += (d > 0 ? d : 0) * w[t * H + hh];
            }
            score_out[t * T_ + j] = (j < lens[t]) ? s : -std::numeric_limits<T>::infinity();
        }
}

// topk by score (value-desc, index-asc ties), re-sorted ascending, +offset, >=len -> -1
inline void indexer_topk(const float *score, int m, int T_, int k, const int64_t *lens,
                         int offset, int32_t *out_idx) {
    for (int t = 0; t < m; ++t) {
        std::vector<int32_t> sel;
        for (int i = 0; i < k; ++i) {
            int best = -1;
            for (int j = 0; j < T_; ++j) {
                float v = score[t * T_ + j];
                bool taken = false;
                for (int32_t s : sel) if (s == j) { taken = true; break; }
                if (taken) continue;
                if (best < 0 || v > score[t * T_ + best] ||
                    (v == score[t * T_ + best] && j < best)) best = j;
            }
            sel.push_back(best);
        }
        std::sort(sel.begin(), sel.end());
        for (int i = 0; i < k; ++i)
            out_idx[t * k + i] = (sel[i] < lens[t]) ? sel[i] + offset : -1;
    }
}

// candidate blocks: block score = max; pin last block; top blocks; expand mask
inline void select_candidate_blocks(const float *score, int m, int T_, const int64_t *lens,
                                    int topk_blocks, int block_size, uint8_t *mask_out) {
    int nb = (T_ + block_size - 1) / block_size;
    for (int t = 0; t < m; ++t) {
        std::vector<float> bs(nb, -std::numeric_limits<float>::infinity());
        for (int j = 0; j < T_; ++j) {
            float v = score[t * T_ + j];
            if (v > bs[j / block_size]) bs[j / block_size] = v;
        }
        int last = (int)((lens[t] - 1) / block_size);
        bs[last] = std::numeric_limits<float>::infinity();
        std::vector<uint8_t> keep(nb, 0);
        for (int i = 0; i < topk_blocks && i < nb; ++i) {
            int best = -1;
            for (int b = 0; b < nb; ++b) {
                if (keep[b]) continue;
                if (best < 0 || bs[b] > bs[best] || (bs[b] == bs[best] && b < best)) best = b;
            }
            if (best < 0 || bs[best] == -std::numeric_limits<float>::infinity()) break;  // drop -inf picks
            keep[best] = 1;
        }
        for (int j = 0; j < T_; ++j) mask_out[t * T_ + j] = keep[j / block_size];
    }
}

// A4: window topk idxs. Prefill (start_pos==0): causal rows over the ring;
// decode: whole ring oldest-first. -1 = empty slot. Bit-exact int gate.
inline void window_topk_idxs(int win, int seqlen, int start_pos, int32_t *out /*[seqlen][min(seqlen,win)] or [win]*/) {
    if (start_pos == 0) {
        int cols = seqlen < win ? seqlen : win;
        for (int t = 0; t < seqlen; ++t) {
            int base = t - win + 1 > 0 ? t - win + 1 : 0;
            for (int j = 0; j < cols; ++j) {
                int idx = base + j;
                out[t * cols + j] = idx > t ? -1 : idx;
            }
        }
    } else {
        int oldest = start_pos % win + 1;
        int c = 0;
        for (int i = oldest; i < win; ++i) out[c++] = i > start_pos ? -1 : i;
        for (int i = 0; i < oldest; ++i) out[c++] = i > start_pos ? -1 : i;
    }
}

} // namespace dsv41
