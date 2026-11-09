#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include <cmath>
#include <cstdint>
#include <cstring>
#include <vector>
// Host bring-up kernels for the DeepSeek V4.1 op set (plan_v41.hpp).
// Serial, f32 compute, no speed claim -- semantic anchors for the SYCL
// kernels and the CPU mock path. Every equation here is gated bit-for-bit
// or f64-anchored against the official reference by the dsv41-fixtures
// (attn A1-A4, hc_sinkhorn, route_gate, ops_misc, engram_hash), which
// these implementations mirror term for term.
namespace ops41 {

inline float bf16(uint16_t b) { return std::bit_cast<float>(uint32_t(b) << 16); }
inline uint16_t bf16b(float f) {
  uint32_t b = std::bit_cast<uint32_t>(f);
  return uint16_t((b + 0x7fff + ((b >> 16) & 1)) >> 16); // RNE
}

// hc_mix41: flatten 4xh stream -> one rms statistic -> 24 mixes -> split
// + Sinkhorn(20). fn is [24, 4*h] row-major f32, scale[3], base[24].
inline void hc_mix(const uint16_t *streams, const float *fn, const float *scale,
                   const float *base, int h, float *pre, float *post, float *comb) {
  const int H = 4;
  std::vector<float> x(H * h);
  for (int i = 0; i < H * h; ++i) x[i] = bf16(streams[i]);
  double sq = 0;
  for (float v : x) sq += double(v) * v;
  float rsqrt = float(1.0 / std::sqrt(sq / (H * h) + 1e-20));
  float m[24];
  for (int j = 0; j < 24; ++j) {
    double acc = 0;
    for (int i = 0; i < H * h; ++i) acc += double(fn[j * H * h + i]) * x[i];
    m[j] = float(acc) * rsqrt;
  }
  auto sigmoid = [](float v) { return 1.0f / (1.0f + std::exp(-v)); };
  const float eps = 1e-6f;
  for (int j = 0; j < H; ++j) pre[j] = sigmoid(m[j] * scale[0] + base[j]) + eps;
  for (int j = 0; j < H; ++j) post[j] = 2.0f * sigmoid(m[H + j] * scale[1] + base[H + j]);
  for (int j = 0; j < 16; ++j) comb[j] = m[8 + j] * scale[2] + base[8 + j];
  for (int j = 0; j < H; ++j) { // softmax rows + eps
    float mx = comb[j * H];
    for (int k = 1; k < H; ++k) mx = comb[j * H + k] > mx ? comb[j * H + k] : mx;
    float s = 0;
    for (int k = 0; k < H; ++k) { comb[j * H + k] = std::exp(comb[j * H + k] - mx); s += comb[j * H + k]; }
    for (int k = 0; k < H; ++k) comb[j * H + k] = comb[j * H + k] / s + eps;
  }
  for (int it = 0; it < 20; ++it) { // col normalize, then (row, col) x (iters-1)
    if (it > 0)
      for (int j = 0; j < H; ++j) {
        float s = 0;
        for (int k = 0; k < H; ++k) s += comb[j * H + k];
        for (int k = 0; k < H; ++k) comb[j * H + k] = comb[j * H + k] / (s + eps);
      }
    for (int k = 0; k < H; ++k) {
      float s = 0;
      for (int j = 0; j < H; ++j) s += comb[j * H + k];
      for (int j = 0; j < H; ++j) comb[j * H + k] = comb[j * H + k] / (s + eps);
    }
  }
}

// hc_mix in the engine's standard reduction contract: 32 strided lanes
// (lane l sums i = l, l+32, ...) in double, then the tree32 pairing. This is
// what the device runs (HcMixDots32 + HcMixFinishD): the serial double loop
// of hc_mix costs ~3 ms per call on a B70 (26 % of a decode step). Same
// equation; the double sums differ from the serial order in the last bits
// only, and device == this anchor exactly.
// `seg` > 1: the columns are cut into seg equal segments, each reduced as
// above, and a row's segments are added in order (the device spreads the
// segments over hardware threads; seg = 1 is the unsegmented form).
inline void hc_mix_lanes(const uint16_t *streams, const float *fn, const float *scale,
                         const float *base, int h, float *pre, float *post, float *comb, int seg = 1) {
  const int N = 4 * h, len = N / seg;
  auto tree = [](double *v) {
    for (unsigned w = 1; w < 32; w *= 2)
      for (unsigned i = 0; i < 32; i += 2 * w) v[i] = v[i] + v[i + w];
    return v[0];
  };
  double lanes[32];
  double sq = 0;
  for (int k = 0; k < seg; ++k) {
    for (int l = 0; l < 32; ++l) {
      double acc = 0;
      for (int i = k * len + l; i < (k + 1) * len; i += 32) { float v = bf16(streams[i]); acc += double(v) * v; }
      lanes[l] = acc;
    }
    sq += tree(lanes);
  }
  float rsqrt = float(1.0 / std::sqrt(sq / N + 1e-20));
  float m[24];
  for (int j = 0; j < 24; ++j) {
    double tot = 0;
    for (int k = 0; k < seg; ++k) {
      for (int l = 0; l < 32; ++l) {
        double acc = 0;
        for (int i = k * len + l; i < (k + 1) * len; i += 32) acc += double(fn[(size_t)j * N + i]) * bf16(streams[i]);
        lanes[l] = acc;
      }
      tot += tree(lanes);
    }
    m[j] = float(tot) * rsqrt;
  }
  auto sigmoid = [](float v) { return 1.0f / (1.0f + std::exp(-v)); };
  const float eps = 1e-6f;
  for (int j = 0; j < 4; ++j) pre[j] = sigmoid(m[j] * scale[0] + base[j]) + eps;
  for (int j = 0; j < 4; ++j) post[j] = 2.0f * sigmoid(m[4 + j] * scale[1] + base[4 + j]);
  for (int j = 0; j < 16; ++j) comb[j] = m[8 + j] * scale[2] + base[8 + j];
  for (int j = 0; j < 4; ++j) {
    float mx = comb[j * 4];
    for (int k = 1; k < 4; ++k) mx = comb[j * 4 + k] > mx ? comb[j * 4 + k] : mx;
    float sm = 0;
    for (int k = 0; k < 4; ++k) { comb[j * 4 + k] = std::exp(comb[j * 4 + k] - mx); sm += comb[j * 4 + k]; }
    for (int k = 0; k < 4; ++k) comb[j * 4 + k] = comb[j * 4 + k] / sm + eps;
  }
  for (int it = 0; it < 20; ++it) {
    if (it > 0)
      for (int j = 0; j < 4; ++j) {
        float sm = 0;
        for (int k = 0; k < 4; ++k) sm += comb[j * 4 + k];
        for (int k = 0; k < 4; ++k) comb[j * 4 + k] = comb[j * 4 + k] / (sm + eps);
      }
    for (int k = 0; k < 4; ++k) {
      float sm = 0;
      for (int j = 0; j < 4; ++j) sm += comb[j * 4 + k];
      for (int j = 0; j < 4; ++j) comb[j * 4 + k] = comb[j * 4 + k] / (sm + eps);
    }
  }
}

inline void hc_pre(const uint16_t *streams, const float *mix, uint16_t *out, int h) {
  for (int i = 0; i < h; ++i) {
    float acc = 0;
    for (int j = 0; j < 4; ++j) acc += mix[j] * bf16(streams[j * h + i]);
    out[i] = bf16b(acc);
  }
}

// streams'[dst] = post[dst]*x + sum_src comb[src][dst]*streams[src]
// (official Block.hc_post sums over the FIRST comb index; llama.cpp
// build_hc_post reads the same element. The transpose shipped here until
// 2026-11-09 and was caught against the llama.cpp reference text.)
inline void hc_post(uint16_t *streams, const uint16_t *x, const float *post,
                    const float *comb, int h) {
  std::vector<float> old(4 * h);
  for (int i = 0; i < 4 * h; ++i) old[i] = bf16(streams[i]);
  for (int j = 0; j < 4; ++j)
    for (int i = 0; i < h; ++i) {
      float acc = post[j] * bf16(x[i]);
      for (int k = 0; k < 4; ++k) acc += comb[k * 4 + j] * old[k * h + i];
      streams[j * h + i] = bf16b(acc);
    }
}

// route41: sqrt(softplus(s)) scores; bias steers selection only; top-6;
// weights = raw scores, normalized (1e-20) then x1.5.
inline void route(const float *logits, const float *bias, int E, int k,
                  uint32_t *ids, float *prob) {
  std::vector<float> s(E);
  for (int i = 0; i < E; ++i) s[i] = std::sqrt(std::log1p(std::exp(logits[i])));
  std::vector<int> ord(E);
  for (int i = 0; i < E; ++i) ord[i] = i;
  std::partial_sort(ord.begin(), ord.begin() + k, ord.end(), [&](int a, int b) {
    return s[a] + bias[a] > s[b] + bias[b];
  });
  float sum = 0;
  for (int i = 0; i < k; ++i) { ids[i] = ord[i]; prob[i] = s[ord[i]]; sum += prob[i]; }
  for (int i = 0; i < k; ++i) prob[i] = prob[i] / (sum + 1e-20f) * 1.5f;
}

// swiglu_clamp: up clamped both sides, gate clamped above; silu(gate)*up.
inline void swiglu_clamp(const uint16_t *gate, const uint16_t *up, uint16_t *out,
                         long long n, float lim = 10.0f) {
  for (long long i = 0; i < n; ++i) {
    float g = std::min(bf16(gate[i]), lim);
    float u = std::clamp(bf16(up[i]), -lim, lim);
    out[i] = bf16b(g / (1.0f + std::exp(-g)) * u);
  }
}

inline void prob_scale(uint16_t *act, const float *prob, int rows, int n) {
  for (int r = 0; r < rows; ++r)
    for (int i = 0; i < n; ++i)
      act[r * n + i] = bf16b(prob[r] * bf16(act[r * n + i]));
}

inline void moe_combine(const uint16_t *exps, const uint16_t *shared, int top,
                        int h, uint16_t *out) {
  for (int i = 0; i < h; ++i) {
    float acc = bf16(shared[i]);
    for (int r = 0; r < top; ++r) acc += bf16(exps[r * h + i]);
    out[i] = bf16b(acc);
  }
}

// rope rotate (YaRN or base table precomputed by the binder), adjacent
// pairs as complex numbers, in place on the tail rdim of each row.
inline void rope_rotate(uint16_t *x, int rows, int d, int rdim,
                        const float *cosb, const float *sinb, bool inverse) {
  for (int r = 0; r < rows; ++r) {
    uint16_t *row = x + r * d + (d - rdim);
    for (int i = 0; i < rdim / 2; ++i) {
      float re = bf16(row[2 * i]), im = bf16(row[2 * i + 1]);
      float c = cosb[i], s = inverse ? -sinb[i] : sinb[i];
      row[2 * i] = bf16b(re * c - im * s);
      row[2 * i + 1] = bf16b(re * s + im * c);
    }
  }
}

// window_append: decode step writes one kv row into the 128-ring and
// emits the oldest-first index row (window_topk_idxs decode branch).
inline void window_append(uint16_t *ring, const uint16_t *kv, int win, int d,
                          int start_pos, int32_t *idxs) {
  std::memcpy(ring + (start_pos % win) * d, kv, d * sizeof(uint16_t));
  int oldest = (start_pos % win + 1) % win; // wraps to slot 0 at win-1
  // oldest-first ring order; slots never written yet read as -1
  for (int i = 0, j = oldest; i < win; ++i, j = (j + 1) % win)
    idxs[i] = j > start_pos ? -1 : j;
}

// sparse_attn41 decode row: per head, softmax over sinks + selected slots
// (window row then compress row; -1 skips; scale = hd^-0.5).
// Dual bases: slot < win_rows reads the window ring, else kv_c.
inline void sparse_attn(const uint16_t *q, const uint16_t *kv_w, const uint16_t *kv_c,
                        const float *sinks, const int32_t *idxs, int n_idx,
                        int heads, int hd, int win_rows, float *out) {
    const float scale = 1.0f / std::sqrt(float(hd));
    for (int h = 0; h < heads; ++h) {
        const uint16_t *qh = q + h * hd;
        std::vector<float> logits(n_idx + 1);
        logits[0] = sinks[h];
        int live = 1;
        for (int i = 0; i < n_idx; ++i) {
            int slot = idxs[i];
            if (slot < 0) continue;
            const uint16_t *k = slot < win_rows ? kv_w + (size_t)slot * hd
                                                : kv_c + (size_t)(slot - win_rows) * hd;
      float acc = 0;
      for (int j = 0; j < hd; ++j) acc += bf16(qh[j]) * bf16(k[j]);
      logits[live++] = acc * scale;
    }
    float mx = logits[0];
    for (int i = 1; i < live; ++i) mx = logits[i] > mx ? logits[i] : mx;
    float sum = 0;
    for (int i = 0; i < live; ++i) { logits[i] = std::exp(logits[i] - mx); sum += logits[i]; }
    std::vector<float> o(hd, 0);
    int li = 1;
    for (int i = 0; i < n_idx && li < live; ++i) {
      int slot = idxs[i];
      if (slot < 0) continue;
      float w = logits[li++] / sum;
      const uint16_t *k = slot < win_rows ? kv_w + (size_t)slot * hd
                                          : kv_c + (size_t)(slot - win_rows) * hd;
      for (int j = 0; j < hd; ++j) o[j] += w * bf16(k[j]);
    }
    for (int j = 0; j < hd; ++j) out[h * hd + j] = o[j];
  }
}

// engram_gate: split kvbuf into key[4,h]/value[h]; per-copy normalized dot
// with weight product qw*kw (stored premultiplied as engram_gate [4,h]);
// sigmoid(signed-sqrt(dot)); h += gate * value.
inline void engram_gate(uint16_t *streams, const uint16_t *kvbuf,
                        const float *gate_w, int h) { // gate_w is F32 in the GGUF
  const float eps = 1e-20f, clamp_v = 1e-6f;
  std::vector<float> key(4 * h), value(h);
  for (int i = 0; i < 4 * h; ++i) key[i] = bf16(kvbuf[i]);
  for (int i = 0; i < h; ++i) value[i] = bf16(kvbuf[4 * h + i]);
  for (int j = 0; j < 4; ++j) {
    double hsq = 0, ksq = 0;
    for (int i = 0; i < h; ++i) {
      float hv = bf16(streams[j * h + i]);
      hsq += double(hv) * hv;
      ksq += double(key[j * h + i]) * key[j * h + i];
    }
    double dot = 0;
    for (int i = 0; i < h; ++i)
      dot += double(bf16(streams[j * h + i])) * gate_w[j * h + i] * key[j * h + i];
    float rstd = float(1.0 / std::sqrt(hsq / h + eps) * (1.0 / std::sqrt(ksq / h + eps)));
    float d = float(dot) * rstd / std::sqrt(float(h));
    float g = 1.0f / (1.0f + std::exp(-std::copysign(std::sqrt(std::max(std::fabs(d), clamp_v)), d)));
    for (int i = 0; i < h; ++i)
      streams[j * h + i] = bf16b(bf16(streams[j * h + i]) + g * value[i]);
  }
}

// gemv_grouped: 8 independent gemvs, group g reads its 4096-slice of o and
// its 1024-row block of w ([8192, 4096] row-major, bf16 bits).
inline void gemv_grouped(const uint16_t *o, const uint16_t *w, int groups,
                         int n, int k, uint16_t *out) {
  for (int g = 0; g < groups; ++g)
    for (int r = 0; r < n; ++r) {
      float acc = 0;
      for (int i = 0; i < k; ++i)
        acc += bf16(w[(g * n + r) * k + i]) * bf16(o[g * k + i]);
      out[g * n + r] = bf16b(acc);
    }
}

inline void hc_mean(const uint16_t *streams, uint16_t *out, int h) {
  for (int i = 0; i < h; ++i) {
    float acc = 0;
    for (int j = 0; j < 4; ++j) acc += bf16(streams[j * h + i]);
    out[i] = bf16b(acc / 4);
  }
}

} // namespace ops41
