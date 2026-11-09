// Independent HC split+Sinkhorn for DeepSeek V4.1 Hyper-Connections.
// Semantics from the official inference/kernel.py hc_split_sinkhorn_kernel
// (MIT): per token, mixes[24] -> pre[4], post[4], comb[4x4]:
//   pre[j]   = sigmoid(m[j]*scale[0] + base[j]) + eps
//   post[j]  = 2*sigmoid(m[4+j]*scale[1] + base[4+j])
//   comb[jk] = m[8+jk]*scale[2] + base[8+jk]
//   comb = softmax_rows(comb) + eps; comb /= colsum + eps
//   repeat (iters-1): comb /= rowsum + eps; comb /= colsum + eps
// Defaults: iters=20, eps=1e-6, hc=4 (mix_hc=24).
#pragma once
#include <cmath>

namespace dsv41 {

template <typename T>
inline void hc_split_sinkhorn(const T *mixes, const T *scale, const T *base,
                              long long n, int iters, T eps,
                              T *pre, T *post, T *comb) {
    constexpr int HC = 4;
    auto sigmoid = [](T v) { return T(1) / (T(1) + std::exp(-v)); };
    for (long long i = 0; i < n; ++i) {
        const T *m = mixes + i * 24;
        T *c = comb + i * 16;
        for (int j = 0; j < HC; ++j)
            pre[i * HC + j]  = sigmoid(m[j] * scale[0] + base[j]) + eps;
        for (int j = 0; j < HC; ++j)
            post[i * HC + j] = T(2) * sigmoid(m[HC + j] * scale[1] + base[HC + j]);
        for (int j = 0; j < 16; ++j)
            c[j] = m[8 + j] * scale[2] + base[8 + j];
        // softmax over rows + eps
        for (int j = 0; j < HC; ++j) {
            T mx = c[j * HC];
            for (int k = 1; k < HC; ++k) mx = c[j * HC + k] > mx ? c[j * HC + k] : mx;
            T s = 0;
            for (int k = 0; k < HC; ++k) { c[j * HC + k] = std::exp(c[j * HC + k] - mx); s += c[j * HC + k]; }
            for (int k = 0; k < HC; ++k) c[j * HC + k] = c[j * HC + k] / s + eps;
        }
        // column normalize, then (iters-1) x (row normalize, column normalize)
        for (int it = 0; it < iters; ++it) {
            if (it > 0) {  // first pass above already did softmax+eps; rows renormalized from iter 1
                for (int j = 0; j < HC; ++j) {
                    T s = 0;
                    for (int k = 0; k < HC; ++k) s += c[j * HC + k];
                    for (int k = 0; k < HC; ++k) c[j * HC + k] = c[j * HC + k] / (s + eps);
                }
            }
            for (int k = 0; k < HC; ++k) {
                T s = 0;
                for (int j = 0; j < HC; ++j) s += c[j * HC + k];
                for (int j = 0; j < HC; ++j) c[j * HC + k] = c[j * HC + k] / (s + eps);
            }
        }
    }
}

} // namespace dsv41
