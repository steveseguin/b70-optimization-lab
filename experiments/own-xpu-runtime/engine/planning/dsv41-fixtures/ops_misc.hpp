// Independent SwiGLU-clamp epilogue (Expert.forward), engram gate, and YaRN
#include <cstdint>
// rope for DeepSeek V4.1. Semantics from official inference/model.py (MIT).
#pragma once
#include <cmath>

namespace dsv41 {

// y = silu(clamp(gate, max=lim)) * clamp(up, +-lim); dsv41 lim = 10.0
template <typename T>
inline void swiglu_clamp(const T *gate, const T *up, T *out, long long n, T lim) {
    for (long long i = 0; i < n; ++i) {
        T g = gate[i] > lim ? lim : gate[i];
        T u = up[i] > lim ? lim : (up[i] < -lim ? -lim : up[i]);
        out[i] = (g / (T(1) + std::exp(-g))) * u;
    }
}

// Engram gate: per (token, hc copy) normalized dot with signed-sqrt sigmoid.
// h[B][hc][dim], key[B][hc][dim], qw/kw[hc][dim], value[B][dim], mask[B](0/1)
// y = h + gate * value   (per copy; masked tokens: gate = 0)
template <typename T>
inline void engram_gate(const T *h, const T *key, const T *qw, const T *kw,
                        const T *value, const uint8_t *mask, T *out,
                        long long B, int hc, int dim, T eps, T clamp_value) {
    for (long long b = 0; b < B; ++b)
        for (int c = 0; c < hc; ++c) {
            const T *hb = h + (b * hc + c) * dim;
            const T *kb = key + (b * hc + c) * dim;
            const T *wp = qw + c * dim, *wk = kw + c * dim;
            T sh = 0, sk = 0, dot = 0;
            for (int i = 0; i < dim; ++i) { sh += hb[i] * hb[i]; sk += kb[i] * kb[i]; }
            T rstd = T(1) / std::sqrt(sh / dim + eps) / std::sqrt(sk / dim + eps);
            for (int i = 0; i < dim; ++i) { T w = wp[i] * wk[i]; dot += (hb[i] * w) * kb[i]; }
            dot *= rstd / std::sqrt((T)dim);
            T mag = std::fabs(dot); if (mag < clamp_value) mag = clamp_value;
            T gate = T(1) / (T(1) + std::exp(-std::copysign(std::sqrt(mag), dot)));
            if (!mask[b]) gate = 0;
            T *ob = out + (b * hc + c) * dim;
            for (int i = 0; i < dim; ++i) ob[i] = hb[i] + gate * value[b * dim + i];
        }
}

// YaRN table: angles[pos][i] = pos * freq[i], freq from the corrected-dim ramp
// (base=10000, factor=16, beta_fast=32, beta_slow=1, original=65536, rdim=64).
template <typename T>
inline void yarn_freqs(T *freqs, int rdim, T base, T factor, T beta_fast, T beta_slow, int original_seq_len) {
    const T two_pi = T(2) * T(3.14159265358979323846);
    auto corrected_dim = [&](T rotations) {
        return (T)rdim * std::log((T)original_seq_len / (rotations * two_pi)) / (T(2) * std::log(base));
    };
    int low  = (int)std::floor(corrected_dim(beta_fast));  if (low < 0) low = 0;
    int high = (int)std::ceil(corrected_dim(beta_slow));   if (high > rdim - 1) high = rdim - 1;
    for (int i = 0; i < rdim / 2; ++i) {
        T f = T(1) / std::pow(base, (T)(2 * i) / (T)rdim);
        T ramp = ((T)i - (T)low) / ((T)high - (T)low > T(1e-3) ? (T)high - (T)low : T(1e-3));
        if (ramp < 0) ramp = 0; if (ramp > 1) ramp = 1;
        T smooth = T(1) - ramp;
        freqs[i] = f / factor * ramp + f * smooth;
    }
}

// rotate x[s][h][rdim] pairwise by angles cos/sin[s][i]; inverse conjugates.
template <typename T>
inline void rope_rotate(const T *x, const T *cosb, const T *sinb, T *out,
                        int s, int h, int rdim, bool inverse) {
    for (int p = 0; p < s; ++p)
        for (int j = 0; j < h; ++j)
            for (int i = 0; i < rdim / 2; ++i) {
                T c = cosb[p * (rdim / 2) + i], sn = sinb[p * (rdim / 2) + i];
                if (inverse) sn = -sn;
                T re = x[(p * h + j) * rdim + 2 * i], im = x[(p * h + j) * rdim + 2 * i + 1];
                out[(p * h + j) * rdim + 2 * i]     = re * c - im * sn;
                out[(p * h + j) * rdim + 2 * i + 1] = re * sn + im * c;
            }
}

} // namespace dsv41
