#pragma once
#include "api.hpp"
#include <algorithm>
#include <bit>
#include <cmath>
#include <map>
#include <numeric>
#include <span>

// Host-only synthetic backend. It never opens a device or model file. Values
// are widened float representations of BF16 buffers; integers use exact float
// representation only in this bounded mock, never the native ABI.
namespace flash::mock {
using V = std::vector<float>;
inline float bf(float x) {
  return iq3::bits_float(std::uint32_t(iq3::bf16_bits(x)) << 16);
}
inline V rounded(V v) {
  for (auto &x : v)
    x = bf(x);
  return v;
}
inline float sigmoid(float x) { return 1.f / (1.f + std::exp(-x)); }
inline float silu(float x) { return x * sigmoid(x); }
inline float tree(V v) {
  if (v.empty())
    throw std::runtime_error("empty reduction");
  while (v.size() > 1) {
    if (v.size() % 2)
      v.push_back(0);
    for (size_t i = 0; i < v.size() / 2; ++i)
      v[i] = v[2 * i] + v[2 * i + 1];
    v.resize(v.size() / 2);
  }
  return v[0];
}
inline float dot(std::span<const float> a, std::span<const float> b,
                 bool gdn = false) {
  V p(a.size());
  for (size_t i = 0; i < a.size(); ++i)
    p[i] = a[i] * b[i];
  if (gdn && a.size() == 128) {
    V lanes(32, 0);
    for (int l = 0; l < 32; ++l)
      for (int j = 0; j < 4; ++j)
        lanes[l] = lanes[l] + p[l * 4 + j];
    return tree(lanes);
  }
  return tree(p);
}
inline float weight(const std::string &n, int r, int k, int expert = 0) {
  int salt = 0;
  for (unsigned char c : n)
    salt += c;
  return float((k * 3 + (r % 4) * 5 + salt + expert * 7) % 17 - 8) / 512.f;
}
inline V controls(const std::string &n, int count) {
  V w(count);
  for (int i = 0; i < count; ++i)
    w[i] = weight(n, 0, i);
  return w;
}
// Synthetic GGUF fixture: exporters store HC/QSA/PLE gains as 1+w and
// ssm_a as -exp(A_log). Construct those stored values from the base fixture;
// the operator consumes them directly. Never undo a real exporter transform.
inline float stored_gain(const std::string &w, int i) {
  return weight(w, 0, i) +
         (w.find("ssm_norm.weight") == std::string::npos ? 1.f : 0.f);
}
inline V norm(const V &x, int width, const std::string &w, bool unit = false,
              bool store = true) {
  V out(x.size());
  for (size_t r = 0; r < x.size() / width; ++r) {
    V sq(width);
    for (int k = 0; k < width; ++k)
      sq[k] = x[r * width + k] * x[r * width + k];
    float inv = 1.f / std::sqrt(tree(sq) / float(width) + 1e-6f);
    for (int k = 0; k < width; ++k) {
      float v = (x[r * width + k] * inv) *
                (stored_gain(w, int(r) * width + k) + float(unit));
      out[r * width + k] = store ? bf(v) : v;
    }
  }
  return out;
}
inline V head_norm(const V &x, int width, const std::string &w) {
  V out;
  for (size_t r = 0; r < x.size() / width; ++r) {
    V row(x.begin() + r * width, x.begin() + (r + 1) * width);
    auto y = norm(row, width, w);
    out.insert(out.end(), y.begin(), y.end());
  }
  return out;
}
inline V linear(const V &x, int rows, int cols, const std::string &w,
                int expert = 0) {
  if (x.size() != size_t(cols))
    throw std::runtime_error("linear input");
  float cycle[4];
  for (int r = 0; r < std::min(rows, 4); ++r) {
    float lane[32] = {};
    for (int l = 0; l < 32; ++l)
      for (int k = l; k < cols; k += 32) {
        float product = weight(w, r, k, expert) * x[k];
        lane[l] = lane[l] + product;
      }
    cycle[r] = bf(iq3::tree32(lane));
  }
  V out(rows);
  for (int r = 0; r < rows; ++r)
    out[r] = cycle[r % 4];
  return out;
}
inline V rope(V x, int heads, int dim, int rotary, int pos) {
  for (int h = 0; h < heads; ++h)
    for (int j = 0; j < rotary / 2; ++j) {
      float angle = float(pos) * std::pow(1e7f, -float(2 * j) / float(rotary));
      float c = bf(std::cos(angle)), s = bf(std::sin(angle)),
            a = x[h * dim + j], b = x[h * dim + j + rotary / 2];
      x[h * dim + j] = bf(a * c - b * s);
      x[h * dim + j + rotary / 2] = bf(b * c + a * s);
    }
  return x;
}
class Cpu final : public Backend {
  Geometry g;
  Event event = 0;
  std::map<std::string, V> committed;
  bool transaction = false;

public:
  std::map<std::string, V> data;
  bool active = true;
  explicit Cpu(const Plan &p) : g(p.g) {
    for (const auto &b : p.buffers) {
      size_t n = 1;
      for (int d : b.shape)
        n *= d;
      data[b.name] = V(n);
    }
    data["token_history"] = {float(g.eos), float(g.eos)};
    if (data.count("ple_metadata")) {
      data["ple_metadata"] = {3, 5, 7};
      data["ple_metadata"].insert(data["ple_metadata"].end(), 16, 17);
      for (int i = 0; i < 16; ++i)
        data["ple_metadata"].push_back(float(17 * i));
    }
    data["active"] = {1};
    committed = data;
  }
  Event enqueue(const Launch &l, Event dep) override {
    if (dep != event)
      throw std::runtime_error("missing dependency");
    const auto &op = l.op;
    auto in = [&](int i) -> V & { return data.at(l.inputs.at(i)); };
    auto out = [&](int i) -> V & { return data.at(l.outputs.at(i)); };
    const auto &s = l.shape;
    if (op == "begin") {
      active = data["active"][0] != 0;
      // Checkpoint only at transaction boundary; allowed host work in MOCK.
      committed = data;
      transaction = true;
      if (active)
        data["error"] = {0};
      if (active &&
          (data["position"][0] < 0 || data["position"][0] >= g.context))
        throw std::runtime_error("context exhausted");
    } else if (!active) { /* device active mask suppresses every mutation */
    } else if (op == "commit") {
      if (data["error"][0]) {
        auto token = data["token"];
        data = committed;
        data["token"] = token;
        data["error"] = {1};
      } else if (l.parameter)
        data["position"][0] += 1;
    } else if (op == "lookup") {
      V y;
      for (float id : in(0)) {
        if (id < 0 || !std::isfinite(id))
          throw std::runtime_error("lookup ID");
        for (int k = 0; k < s[1]; ++k)
          y.push_back(bf(weight(l.weights[0], int(id), k)));
      }
      out(0) = y;
    } else if (op == "broadcast") {
      out(0).clear();
      for (int i = 0; i < 4; ++i)
        out(0).insert(out(0).end(), in(0).begin(), in(0).end());
    } else if (op == "handoff" ||
               op == "handoff_result") { /* explicit dependency; same host bytes
                                            in mock */
    } else if (op == "gemv")
      out(0) = linear(in(0), s[1], s[2], l.weights[0]);
    else if (op == "routed_gemv") {
      V y;
      for (int j = 0; j < s[0]; ++j) {
        int e = int(in(1)[j * 3]);
        int offset = in(0).size() == size_t(s[2]) ? 0 : j * s[2];
        V x(in(0).begin() + offset, in(0).begin() + offset + s[2]);
        auto row = linear(x, s[1], s[2], l.weights[0], e);
        y.insert(y.end(), row.begin(), row.end());
      }
      out(0) = y;
      out(1) = V(s[0], 0);
    } else if (op == "check_status") {
      for (float status : in(0))
        if (status)
          out(0)[0] = 1;
    } else if (op == "norm")
      out(0) = norm(in(0), s[1], l.weights[0], l.parameter);
    else if (op == "silu_div4") {
      V y = in(0);
      for (auto &v : y)
        v = bf(silu(v / 4.f));
      out(0) = y;
    } else if (op == "silu_product") {
      V y = in(0);
      for (size_t i = 0; i < y.size(); ++i)
        y[i] = bf(silu(y[i]) * in(1)[i]);
      out(0) = y;
    } else if (op == "hc_mix") {
      V y(s[1], 0);
      for (int i = 0; i < 4; ++i)
        for (int k = 0; k < s[1]; ++k)
          y[k] = y[k] + sigmoid(in(1)[i * s[1] + k]) * in(0)[i * s[1] + k];
      for (auto &v : y)
        v = bf(v / 4.f);
      out(0) = y;
    } else if (op == "hc_combine") {
      V y = in(0);
      for (int i = 0; i < 4; ++i)
        for (int k = 0; k < s[1]; ++k)
          y[i * s[1] + k] =
              bf(y[i * s[1] + k] + in(1)[k] * (2.f * sigmoid(in(2)[i] / 4.f)));
      out(0) = y;
    } else if (op == "conv") {
      int hist = 3 * l.parameter;
      V y(s[0]), history = in(1);
      for (int ch = 0; ch < s[0]; ++ch) {
        float acc = 0;
        for (int tap = 0; tap < 4; ++tap) {
          float v = tap == 3 ? in(0)[ch] : in(1)[ch * hist + tap * l.parameter];
          acc = acc + v * weight(l.weights[0], ch, tap);
        }
        y[ch] = bf(silu(l.parameter == 3 ? bf(acc) : acc));
        for (int j = 0; j < hist - 1; ++j)
          history[ch * hist + j] = history[ch * hist + j + 1];
        history[ch * hist + hist - 1] = in(0)[ch];
      }
      out(0) = y;
      out(1) = history;
    } else if (op == "gdn") {
      int kh = s[0], vh = s[1], d = s[2];
      V q(kh * d), k(kh * d);
      const auto &v = in(0);
      for (int h = 0; h < kh; ++h) {
        auto qr = std::span(v).subspan(h * d, d),
             kr = std::span(v).subspan(kh * d + h * d, d);
        float qn = std::sqrt(dot(qr, qr, true) + 1e-6f),
              kn = std::sqrt(dot(kr, kr, true) + 1e-6f);
        for (int j = 0; j < d; ++j) {
          q[h * d + j] = (qr[j] / qn) / std::sqrt(float(d));
          k[h * d + j] = kr[j] / kn;
        }
      }
      V state = in(3), y(vh * d);
      for (int h = 0; h < vh; ++h) {
        float gate = in(1)[h] + weight(l.weights[1], 0, h);
        float sp = gate < 20.f ? std::log(1.f + std::exp(gate)) : gate;
        float stored_a = -std::exp(weight(l.weights[0], 0, h));
        float decay = std::exp(stored_a * sp);
        int key = h / (vh / kh);
        auto qr = std::span(q).subspan(key * d, d),
             kr = std::span(k).subspan(key * d, d);
        for (int j = 0; j < d; ++j) {
          int base = (h * d + j) * d;
          V row(d);
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
    } else if (op == "gdn_norm_gate") {
      V y;
      for (int h = 0; h < s[0]; ++h) {
        V row(in(0).begin() + h * s[1], in(0).begin() + (h + 1) * s[1]);
        auto n = norm(row, s[1], l.weights[0], false, false);
        for (int j = 0; j < s[1]; ++j)
          y.push_back(bf(n[j] * sigmoid(in(1)[h * s[1] + j])));
      }
      out(0) = y;
    } else if (op == "route") {
      V x = in(0);
      for (float v : x)
        if (!std::isfinite(v))
          throw std::runtime_error("nonfinite router");
      float m = *std::max_element(x.begin(), x.end());
      for (auto &v : x)
        v = std::exp(v - m);
      float sum = tree(x);
      for (auto &v : x)
        v = v / sum;
      std::vector<int> ids(x.size());
      std::iota(ids.begin(), ids.end(), 0);
      std::stable_sort(ids.begin(), ids.end(),
                       [&](int a, int b) { return x[a] > x[b]; });
      V idx, prob;
      for (int j = 0; j < s[1]; ++j) {
        idx.push_back(float(ids[j]));
        prob.push_back(x[ids[j]]);
      }
      sum = tree(prob);
      for (auto &v : prob)
        v = v / sum;
      out(0) = idx;
      out(1) = prob;
    } else if (op == "expert_gather") {
      V routes;
      for (float id : in(0)) {
        if (id < 0 || id >= g.experts)
          throw std::runtime_error("expert bounds");
        routes.insert(routes.end(), {id, 0, float(g.mid)});
      }
      out(0) = routes;
      for (size_t i = 2; i < routes.size(); i += 3)
        routes[i] = float(g.h);
      out(1) = routes;
      V repeated;
      for (int j = 0; j < g.top; ++j)
        repeated.insert(repeated.end(), in(1).begin(), in(1).end());
      out(2) = repeated;
    } else if (op == "moe_combine") {
      V y(s[1], 0);
      for (int j = 0; j < s[0]; ++j)
        for (int k = 0; k < s[1]; ++k)
          y[k] = y[k] + in(0)[j * s[1] + k] * in(1)[j];
      for (int k = 0; k < s[1]; ++k)
        y[k] = bf(bf(y[k]) + bf(in(2)[k] * sigmoid(in(3)[0])));
      out(0) = y;
    } else if (op == "qsa_prepare") {
      V q, gate;
      for (int h = 0; h < g.qh; ++h) {
        auto b = in(0).begin() + h * 2 * g.ad;
        q.insert(q.end(), b, b + g.ad);
        gate.insert(gate.end(), b + g.ad, b + 2 * g.ad);
      }
      int pos = int(data["position"][0]);
      out(0) =
          rope(head_norm(q, g.ad, l.weights[0]), g.qh, g.ad, g.rotary, pos);
      out(1) = gate;
      out(2) = rope(head_norm(in(1), g.ad, l.weights[1]), g.kvh, g.ad, g.rotary,
                    pos);
      out(3) =
          rope(head_norm(in(2), g.id, l.weights[2]), g.ih, g.id, g.rotary, pos);
    } else if (op == "qsa_append_pool") {
      int pos = int(data["position"][0]);
      std::copy(in(0).begin(), in(0).end(),
                out(0).begin() + pos * g.kvh * g.ad);
      std::copy(in(1).begin(), in(1).end(),
                out(1).begin() + pos * g.kvh * g.ad);
      std::copy(in(2).begin(), in(2).end(), out(2).begin() + pos * g.id);
      // Match packet1b recomputation of all complete pools; capacity fixed,
      // valid length comes from position. Native may retain identical pools.
      for (int b = 0; b < (pos + 1) / 4; ++b) {
        V row(g.id, 0);
        for (int j = 0; j < 4; ++j)
          for (int k = 0; k < g.id; ++k)
            row[k] = row[k] + out(2)[(b * 4 + j) * g.id + k];
        for (auto &v : row)
          v = bf(v / 4.f);
        row = rope(norm(row, g.id, l.weights[0]), 1, g.id, g.rotary, b * 4);
        std::copy(row.begin(), row.end(), out(3).begin() + b * g.id);
      }
    } else if (op == "qsa_select") {
      int pos = int(data["position"][0]), n = (pos + 1) / 4;
      V scores(n, 0);
      for (int h = 0; h < g.ih; ++h)
        for (int b = 0; b < n; ++b)
          scores[b] =
              scores[b] +
              std::max(0.f, dot(std::span(in(0)).subspan(h * g.id, g.id),
                                std::span(in(1)).subspan(b * g.id, g.id)));
      for (auto &v : scores)
        v = v / std::sqrt(float(g.id));
      std::vector<int> ids(n);
      std::iota(ids.begin(), ids.end(), 0);
      std::stable_sort(ids.begin(), ids.end(),
                       [&](int a, int b) { return scores[a] > scores[b]; });
      V selected;
      for (int i = 0; i < std::min(n, g.budget / 4); ++i)
        for (int j = 0; j < 4; ++j)
          selected.push_back(float(ids[i] * 4 + j));
      for (int i = n * 4; i <= pos; ++i)
        selected.push_back(float(i));
      selected.resize(g.budget + 3, -1);
      out(0) = selected;
    } else if (op == "qsa_attention") {
      V y(g.qh * g.ad);
      std::vector<int> ids;
      for (float v : in(4))
        if (v >= 0)
          ids.push_back(int(v));
      for (int h = 0; h < g.qh; ++h) {
        int kh = h / (g.qh / g.kvh);
        V scores;
        for (int id : ids)
          scores.push_back(
              dot(std::span(in(2)).subspan((id * g.kvh + kh) * g.ad, g.ad),
                  std::span(in(0)).subspan(h * g.ad, g.ad)) /
              std::sqrt(float(g.ad)));
        float m = *std::max_element(scores.begin(), scores.end());
        for (auto &v : scores)
          v = std::exp(v - m);
        float den = tree(scores);
        for (auto &v : scores)
          v = v / den;
        for (int k = 0; k < g.ad; ++k) {
          V terms;
          for (size_t i = 0; i < ids.size(); ++i)
            terms.push_back(scores[i] *
                            in(3)[(ids[i] * g.kvh + kh) * g.ad + k]);
          y[h * g.ad + k] = bf(bf(tree(terms)) * sigmoid(in(1)[h * g.ad + k]));
        }
      }
      out(0) = y;
    } else if (op == "ple_hash") {
      std::int64_t token = int(in(0)[0]), old0 = int(in(1)[0]),
                   old1 = int(in(1)[1]), eos = g.eos;
      if (old1 == eos)
        old0 = eos;
      V ids;
      for (int n : {2, 3}) {
        std::uint64_t mixed = std::uint64_t(token) * std::uint64_t(in(2)[0]);
        mixed ^= std::uint64_t(old1) * std::uint64_t(in(2)[1]);
        if (n == 3)
          mixed ^= std::uint64_t(old0) * std::uint64_t(in(2)[2]);
        auto mix = std::bit_cast<std::int64_t>(mixed);
        for (int h = 0; h < 8; ++h) {
          int index = (n - 2) * 8 + h;
          auto size = std::int64_t(in(2)[3 + index]);
          if (size <= 0)
            throw std::runtime_error("PLE metadata size");
          ids.push_back(float((mix % size + size) % size +
                              std::int64_t(in(2)[19 + index])));
        }
      }
      out(0) = ids;
      out(1) = {float(old1), float(token)};
    } else if (op == "ple_gate") {
      V y(4 * g.h);
      for (int h = 0; h < 4; ++h) {
        V products(g.h);
        for (int k = 0; k < g.h; ++k)
          products[k] = bf(in(0)[h * g.h + k] * in(1)[h * g.h + k]);
        float z = bf(bf(tree(products)) / std::sqrt(float(g.h)));
        float root = bf(std::sqrt(std::max(std::abs(z), 1e-6f)));
        float sign = z > 0 ? 1.f : z < 0 ? -1.f : 0.f;
        float gate = bf(sigmoid(bf(sign * root)));
        for (int k = 0; k < g.h; ++k)
          y[h * g.h + k] = bf(gate * in(2)[k]);
      }
      out(0) = y;
    } else if (op == "ple_add") {
      V y = in(0);
      for (size_t i = 0; i < y.size(); ++i)
        y[i] = bf(y[i] + bf(in(1)[i] + in(2)[i]));
      out(0) = y;
    } else if (op == "argmax") {
      int best = 0;
      bool finite = true;
      for (size_t i = 0; i < in(0).size(); ++i) {
        finite &= std::isfinite(in(0)[i]);
        if (in(0)[i] > in(0)[best])
          best = int(i);
      }
      out(0) = {float(best)};
      out(1) = {finite ? out(1)[0] : 1.f};
    } else
      throw std::runtime_error("unknown mock op " + op);
    if (op == "commit" && l.parameter)
      transaction = false;
    return ++event;
  }
  void submission_failed() noexcept override {
    if (transaction)
      data.swap(committed);
    transaction = false;
  }
  Event last() const { return event; }
};
} // namespace flash::mock
