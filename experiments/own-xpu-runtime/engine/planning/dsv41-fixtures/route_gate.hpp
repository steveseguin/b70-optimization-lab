// Independent MoE router (Gate) for DeepSeek V4.1.
// Semantics from official inference/model.py Gate.forward (MIT):
//   scores = sqrt(softplus(logits / gate_temp))     [config: sqrtsoftplus]
//   idx    = top-6 of (scores + bias)               [bias steers selection only]
//   w      = scores[idx]; w /= sum(w) + 1e-20; w *= route_scale
// Defaults from config.json: gate_temp=1.0, route_scale=1.5, k=6, E=384.
// Tie rule: descending value; equal values resolve to the lower expert index
// (documented contract; torch CPU topk observed compatible on the fixture).
#pragma once
#include <cmath>
#include <cstdint>

namespace dsv41 {

template <typename T>
inline void route_gate(const T *logits, const T *bias, long long n, int E, int k,
                       T route_scale, int32_t *out_idx, T *out_w) {
    auto score_of = [&](T v) { return std::sqrt(std::log1p(std::exp(v))); };  // softplus then sqrt
    for (long long t = 0; t < n; ++t) {
        const T *row = logits + t * E;
        // selection keys
        // (kept per-token on stack: E=384 fixed for dsv41 backbone)
        T sel[1024];
        T sc[1024];
        for (int e = 0; e < E; ++e) {
            sc[e] = score_of(row[e]);
            sel[e] = sc[e] + bias[e];
        }
        // partial selection, value-desc then index-asc
        int32_t idx[64];
        for (int i = 0; i < k; ++i) {
            int best = -1;
            for (int e = 0; e < E; ++e) {
                if (best < 0 || sel[e] > sel[best] || (sel[e] == sel[best] && e < best)) {
                    bool taken = false;
                    for (int j = 0; j < i; ++j) if (idx[j] == e) { taken = true; break; }
                    if (!taken) best = e;
                }
            }
            idx[i] = best;
        }
        T sum = 0;
        for (int i = 0; i < k; ++i) sum += sc[idx[i]];
        for (int i = 0; i < k; ++i) {
            out_idx[t * k + i] = idx[i];
            out_w[t * k + i] = sc[idx[i]] / (sum + T(1e-20)) * route_scale;
        }
    }
}

} // namespace dsv41
