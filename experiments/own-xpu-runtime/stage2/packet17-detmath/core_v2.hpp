#include "detmath.hpp"
#include "rope.hpp"
#pragma once
// Original lab equations adapted from packet3/kernels/mock.hpp. Serial bring-up
// kernels: deliberately no speed claim, heap allocation, BLAS or host routing.
#include "../packet3/kernels/api.hpp"
#include <algorithm>
#include <cmath>
#include <span>
namespace integrated {
using flash::Geometry;
enum class Op {
  norm,
  silu_div4,
  silu_product,
  hc_mix,
  hc_combine,
  conv,
  gdn,
  gdn_norm_gate,
  route,
  expert_gather,
  moe_combine,
  qsa_prepare,
  qsa_append_pool,
  qsa_select,
  qsa_attention,
  ple_gate,
  ple_add,
  argmax
};
struct Pool {
  float *base;
  size_t used = 0, capacity;
  int failed = 0;
  float *alloc(size_t n) {
    if (n > capacity - used) {
      failed = 1;
      return base;
    }
    auto p = base + used;
    used += n;
    return p;
  }
};
struct V {
  Pool *pool;
  float *p = nullptr;
  size_t n = 0, cap = 0;
  float *begin() const { return pool->failed ? pool->base : p; }
  float *end() const { return n ? begin() + n : begin(); }
  float &operator[](size_t i) const {
    return pool->failed ? pool->base[0] : p[i];
  }
  size_t size() const { return n; }
  bool empty() const { return !n; }
  std::span<const float> span() const { return {p, n}; }
  void reserve(size_t k) {
    if (k <= cap)
      return;
    auto q = pool->alloc(k);
    if (pool->failed)
      return;
    for (size_t i = 0; i < n; ++i)
      q[i] = p[i];
    p = q;
    cap = k;
  }
  void resize(size_t k, float value = 0) {
    reserve(k);
    if (pool->failed)
      return;
    for (size_t i = n; i < k; ++i)
      p[i] = value;
    n = k;
  }
  void clear() { n = 0; }
  void push_back(float x) {
    if (n == cap)
      reserve(std::max(size_t(16), cap * 2));
    if (!pool->failed)
      p[n++] = x;
  }
  void insert(float *, const float *a, const float *b) {
    size_t old = n;
    resize(n + (b - a));
    if (!pool->failed)
      for (size_t j = 0; j < size_t(b - a); ++j)
        p[old + j] = a[j];
  }
  void insert(float *, std::initializer_list<float> xs) {
    for (float x : xs)
      push_back(x);
  }
};
struct Weight {
  const uint8_t *p = nullptr;
  iq3::Type type = iq3::Type::F32;
  size_t elements = 0;
};
struct Core {
  Pool pool;
  Geometry g;
  Op op;
  int position = 0;
  bool packed_heads = false;
  int failed = 0;
  struct Site {
    int shape[8]{}, weights[4]{0, 1, 2, 3};
    int parameter = 0;
  } l;
  int *s = l.shape;
  V inputs[10]{}, outputs[6]{};
  Weight weights[4]{};
  V make(size_t n = 0, float value = 0) {
    V v{&pool};
    v.resize(n, value);
    return v;
  }
  V make(const float *a, const float *b) {
    auto v = make(b - a);
    for (size_t i = 0; i < v.n; ++i)
      v[i] = a[i];
    return v;
  }
  V clone(V x) { return make(x.begin(), x.end()); }
  V &in(int i) { return inputs[i]; }
  V &out(int i) { return outputs[i]; }
  float bad() {
    failed = 1;
    return 0;
  }
  float gain(int w, int i) {
    if (w < 0 || w >= 4 || i < 0 || size_t(i) >= weights[w].elements)
      return bad();
    return iq3::element(weights[w].type, weights[w].p, i);
  }
  template <class Compare> void stable_sort(float *a, float *b, Compare cmp) {
    if (a == b) return;
    for (auto i = a + 1; i < b; ++i) {
      float x = *i;
      auto j = i;
      while (j > a && cmp(int(x), int(j[-1]))) {
        *j = j[-1];
        --j;
      }
      *j = x;
    }
  }
  float bf(float x) {
    return iq3::bits_float(std::uint32_t(iq3::bf16_bits(x)) << 16);
  }
  V rounded(V v) {
    for (auto &x : v)
      x = bf(x);
    return v;
  }
  float sigmoid(float x) { return 1.f / (1.f + detmath::exp(-x)); }
  float silu(float x) { return x * sigmoid(x); }
  float tree(V v) {
    v = clone(v);
    if (v.empty())
      return bad();
    while (v.size() > 1) {
      if (v.size() % 2)
        v.push_back(0);
      for (size_t i = 0; i < v.size() / 2; ++i)
        v[i] = v[2 * i] + v[2 * i + 1];
      v.resize(v.size() / 2);
    }
    return v[0];
  }
  float dot(std::span<const float> a, std::span<const float> b,
            bool gdn = false) {
    V p = make(a.size());
    for (size_t i = 0; i < a.size(); ++i)
      p[i] = a[i] * b[i];
    if (gdn && a.size() == 128) {
      V lanes = make(32, 0);
      for (int l = 0; l < 32; ++l)
        for (int j = 0; j < 4; ++j)
          lanes[l] = lanes[l] + p[l * 4 + j];
      return tree(lanes);
    }
    return tree(p);
  }
  V norm(const V &x, int width, int w, bool unit = false, bool store = true) {
    V out = make(x.size());
    for (size_t r = 0; r < x.size() / width; ++r) {
      V sq = make(width);
      for (int k = 0; k < width; ++k)
        sq[k] = x[r * width + k] * x[r * width + k];
      float inv = detmath::rsqrt(tree(sq) / float(width) + 1e-6f);
      for (int k = 0; k < width; ++k) {
        float v = (x[r * width + k] * inv) *
                  (gain(w, int(r) * width + k) + float(unit));
        out[r * width + k] = store ? bf(v) : v;
      }
    }
    return out;
  }
  V head_norm(const V &x, int width, int w) {
    V out = make();
    for (size_t r = 0; r < x.size() / width; ++r) {
      V row = make(x.begin() + r * width, x.begin() + (r + 1) * width);
      auto y = norm(row, width, w);
      out.insert(out.end(), y.begin(), y.end());
    }
    return out;
  }
  V rope(V x, int heads, int dim, int rotary, int pos) {
    if(rotary!=64 || pos<0 || pos>=rope_constants::positions){bad();return x;}
    for (int h = 0; h < heads; ++h)
      for (int j = 0; j < rotary / 2; ++j) {
        float c = rope_constants::cos(pos,j), s = rope_constants::sin(pos,j),
              a = x[h * dim + j], b = x[h * dim + j + rotary / 2];
        x[h * dim + j] = bf(a * c - b * s);
        x[h * dim + j + rotary / 2] = bf(b * c + a * s);
      }
    return x;
  }

  void run() {
    if (op == Op::norm)
      out(0) = norm(in(0), s[1], l.weights[0], l.parameter);
    else if (op == Op::silu_div4) {
      V y = clone(in(0));
      for (auto &v : y)
        v = bf(silu(v / 4.f));
      out(0) = y;
    } else if (op == Op::silu_product) {
      V y = clone(in(0));
      for (size_t i = 0; i < y.size(); ++i)
        y[i] = bf(silu(y[i]) * in(1)[i]);
      out(0) = y;
    } else if (op == Op::hc_mix) {
      V y = make(s[1], 0);
      for (int i = 0; i < 4; ++i)
        for (int k = 0; k < s[1]; ++k)
          y[k] = y[k] + sigmoid(in(1)[i * s[1] + k]) * in(0)[i * s[1] + k];
      for (auto &v : y)
        v = bf(v / 4.f);
      out(0) = y;
    } else if (op == Op::hc_combine) {
      V y = clone(in(0));
      for (int i = 0; i < 4; ++i)
        for (int k = 0; k < s[1]; ++k)
          y[i * s[1] + k] =
              bf(y[i * s[1] + k] + in(1)[k] * (2.f * sigmoid(in(2)[i] / 4.f)));
      out(0) = y;
    } else if (op == Op::conv) {
      int hist = 3 * l.parameter;
      V y = make(s[0]), history = clone(in(1));
      for (int ch = 0; ch < s[0]; ++ch) {
        float acc = 0;
        for (int tap = 0; tap < 4; ++tap) {
          float v = tap == 3 ? in(0)[ch] : in(1)[ch * hist + tap * l.parameter];
          acc = acc + v * gain(l.weights[0], ch * 4 + tap);
        }
        y[ch] = bf(silu(l.parameter == 3 ? bf(acc) : acc));
        for (int j = 0; j < hist - 1; ++j)
          history[ch * hist + j] = history[ch * hist + j + 1];
        history[ch * hist + hist - 1] = in(0)[ch];
      }
      out(0) = y;
      out(1) = history;
    } else if (op == Op::gdn) {
      int kh = s[0], vh = s[1], d = s[2];
      V q = make(kh * d), k = make(kh * d);
      const auto &v = in(0);
      for (int h = 0; h < kh; ++h) {
        auto qr = v.span().subspan(h * d, d),
             kr = v.span().subspan(kh * d + h * d, d);
        float qn = detmath::sqrt(dot(qr, qr, true) + 1e-6f),
              kn = detmath::sqrt(dot(kr, kr, true) + 1e-6f);
        for (int j = 0; j < d; ++j) {
          q[h * d + j] = (qr[j] / qn) / detmath::sqrt(float(d));
          k[h * d + j] = kr[j] / kn;
        }
      }
      V state = clone(in(3)), y = make(vh * d);
      for (int h = 0; h < vh; ++h) {
        float gate = in(1)[h] + gain(l.weights[1], h);
        float sp = gate < 20.f ? detmath::log(1.f + detmath::exp(gate)) : gate;
        float stored_a = gain(l.weights[0], h);
        float decay = detmath::exp(stored_a * sp);
        int key = packed_heads ? h % kh : h / (vh / kh);
        auto qr = q.span().subspan(key * d, d),
             kr = k.span().subspan(key * d, d);
        for (int j = 0; j < d; ++j) {
          int base = (h * d + j) * d;
          V row = make(d);
          for (int a = 0; a < d; ++a)
            row[a] = state[base + a] * decay;
          float delta = (v[2 * kh * d + h * d + j] - dot(row, kr, true)) *
                        sigmoid(in(2)[h]);
          for (int a = 0; a < d; ++a)
            row[a] = row[a] + delta * kr[a];
          y[h * d + j] = bf(dot(row, qr, true));
          for (int a = 0; a < d; ++a)
            state[base + a] = bf(row[a]);
        }
      }
      out(0) = y;
      out(1) = state;
    } else if (op == Op::gdn_norm_gate) {
      V y = make();
      for (int h = 0; h < s[0]; ++h) {
        V row = make(in(0).begin() + h * s[1], in(0).begin() + (h + 1) * s[1]);
        auto n = norm(row, s[1], l.weights[0], false, false);
        for (int j = 0; j < s[1]; ++j)
          y.push_back(bf(n[j] * sigmoid(in(1)[h * s[1] + j])));
      }
      out(0) = y;
    } else if (op == Op::route) {
      V x = clone(in(0));
      for (float v : x)
        if (!std::isfinite(v)) {
          failed = 1;
          return;
        };
      float m = *std::max_element(x.begin(), x.end());
      for (auto &v : x)
        v = detmath::exp(v - m);
      float sum = tree(x);
      for (auto &v : x)
        v = v / sum;
      V ids = make(x.size());
      for (size_t i = 0; i < ids.size(); ++i)
        ids[i] = float(i);
      stable_sort(ids.begin(), ids.end(),
                  [&](int a, int b) { return x[a] > x[b]; });
      V idx = make(), prob = make();
      for (int j = 0; j < s[1]; ++j) {
        idx.push_back(float(ids[j]));
        prob.push_back(x[ids[j]]);
      }
      sum = tree(prob);
      for (auto &v : prob)
        v = v / sum;
      out(0) = idx;
      out(1) = prob;
    } else if (op == Op::expert_gather) {
      V routes = make();
      for (float id : in(0)) {
        if (id < 0 || id >= g.experts) {
          failed = 1;
          return;
        };
        routes.insert(routes.end(), {id, 0, float(g.mid)});
      }
      out(0) = clone(routes);
      for (size_t i = 2; i < routes.size(); i += 3)
        routes[i] = float(g.h);
      out(1) = routes;
      V repeated = make();
      for (int j = 0; j < g.top; ++j)
        repeated.insert(repeated.end(), in(1).begin(), in(1).end());
      out(2) = repeated;
    } else if (op == Op::moe_combine) {
      V y = make(s[1], 0);
      for (int j = 0; j < s[0]; ++j)
        for (int k = 0; k < s[1]; ++k)
          y[k] = y[k] + in(0)[j * s[1] + k] * in(1)[j];
      for (int k = 0; k < s[1]; ++k)
        y[k] = bf(bf(y[k]) + bf(in(2)[k] * sigmoid(in(3)[0])));
      out(0) = y;
    } else if (op == Op::qsa_prepare) {
      V q = make(), gate = make();
      for (int h = 0; h < g.qh; ++h) {
        auto b = in(0).begin() + h * 2 * g.ad;
        q.insert(q.end(), b, b + g.ad);
        gate.insert(gate.end(), b + g.ad, b + 2 * g.ad);
      }
      int pos = position;
      out(0) =
          rope(head_norm(q, g.ad, l.weights[0]), g.qh, g.ad, g.rotary, pos);
      out(1) = gate;
      out(2) = rope(head_norm(in(1), g.ad, l.weights[1]), g.kvh, g.ad, g.rotary,
                    pos);
      out(3) =
          rope(head_norm(in(2), g.id, l.weights[2]), g.ih, g.id, g.rotary, pos);
    } else if (op == Op::qsa_append_pool) {
      int pos = position;
      std::copy(in(0).begin(), in(0).end(),
                out(0).begin() + pos * g.kvh * g.ad);
      std::copy(in(1).begin(), in(1).end(),
                out(1).begin() + pos * g.kvh * g.ad);
      std::copy(in(2).begin(), in(2).end(), out(2).begin() + pos * g.id);
      // Match packet1b recomputation of all complete pools; capacity fixed,
      // valid length comes from position. Native may retain identical pools.
      for (int b = 0; b < (pos + 1) / 4; ++b) {
        V row = make(g.id, 0);
        for (int j = 0; j < 4; ++j)
          for (int k = 0; k < g.id; ++k)
            row[k] = row[k] + out(2)[(b * 4 + j) * g.id + k];
        for (auto &v : row)
          v = bf(v / 4.f);
        row = rope(norm(row, g.id, l.weights[0]), 1, g.id, g.rotary, b * 4);
        std::copy(row.begin(), row.end(), out(3).begin() + b * g.id);
      }
    } else if (op == Op::qsa_select) {
      int pos = position, n = (pos + 1) / 4;
      V scores = make(n, 0);
      for (int h = 0; h < g.ih; ++h)
        for (int b = 0; b < n; ++b)
          scores[b] = scores[b] +
                      std::max(0.f, dot(in(0).span().subspan(h * g.id, g.id),
                                        in(1).span().subspan(b * g.id, g.id)));
      for (auto &v : scores)
        v = v / detmath::sqrt(float(g.id));
      V ids = make(n);
      for (size_t i = 0; i < ids.size(); ++i)
        ids[i] = float(i);
      stable_sort(ids.begin(), ids.end(),
                  [&](int a, int b) { return scores[a] > scores[b]; });
      V selected = make();
      for (int i = 0; i < std::min(n, g.budget / 4); ++i)
        for (int j = 0; j < 4; ++j)
          selected.push_back(float(ids[i] * 4 + j));
      for (int i = n * 4; i <= pos; ++i)
        selected.push_back(float(i));
      selected.resize(g.budget + 3, -1);
      out(0) = selected;
    } else if (op == Op::qsa_attention) {
      V y = make(g.qh * g.ad);
      V ids = make();
      for (float v : in(4))
        if (v >= 0)
          ids.push_back(int(v));
      for (int h = 0; h < g.qh; ++h) {
        int kh = h / (g.qh / g.kvh);
        V scores = make();
        for (int id : ids)
          scores.push_back(
              dot(in(2).span().subspan((id * g.kvh + kh) * g.ad, g.ad),
                  in(0).span().subspan(h * g.ad, g.ad)) /
              detmath::sqrt(float(g.ad)));
        float m = *std::max_element(scores.begin(), scores.end());
        for (auto &v : scores)
          v = detmath::exp(v - m);
        float den = tree(scores);
        for (auto &v : scores)
          v = v / den;
        for (int k = 0; k < g.ad; ++k) {
          V terms = make();
          for (size_t i = 0; i < ids.size(); ++i)
            terms.push_back(scores[i] *
                            in(3)[(ids[i] * g.kvh + kh) * g.ad + k]);
          y[h * g.ad + k] = bf(bf(tree(terms)) * sigmoid(in(1)[h * g.ad + k]));
        }
      }
      out(0) = y;
    } else if (op == Op::ple_gate) {
      V y = make(4 * g.h);
      for (int h = 0; h < 4; ++h) {
        V products = make(g.h);
        for (int k = 0; k < g.h; ++k)
          products[k] = bf(in(0)[h * g.h + k] * in(1)[h * g.h + k]);
        float z = bf(bf(tree(products)) / detmath::sqrt(float(g.h)));
        float root = bf(detmath::sqrt(std::max(std::abs(z), 1e-6f)));
        float sign = z > 0 ? 1.f : z < 0 ? -1.f : 0.f;
        float gate = bf(sigmoid(bf(sign * root)));
        for (int k = 0; k < g.h; ++k)
          y[h * g.h + k] = bf(gate * in(2)[k]);
      }
      out(0) = y;
    } else if (op == Op::ple_add) {
      V y = clone(in(0));
      for (size_t i = 0; i < y.size(); ++i)
        y[i] = bf(y[i] + bf(in(1)[i] + in(2)[i]));
      out(0) = y;
    } else if (op == Op::argmax) {
      int best = 0;
      bool finite = true;
      for (size_t i = 0; i < in(0).size(); ++i) {
        finite &= std::isfinite(in(0)[i]);
        if (in(0)[i] > in(0)[best])
          best = int(i);
      }
      out(0) = make(1, float(best));
      out(1) = make(1, finite ? out(1)[0] : 1.f);
    }
  }
};
} // namespace integrated
