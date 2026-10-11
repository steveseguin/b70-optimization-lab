#pragma once
#include "../packet4/core.hpp"
// The original scalar helpers and trees; only head/channel indices change.
namespace tp2_state {
using namespace integrated;
struct Core:integrated::Core {
  int rank=0;
  void run() {
    if (op == Op::conv) {
      int hist = 3 * l.parameter;
      V y = make(s[0]), history = clone(in(1));
      for (int ch = rank*(s[0]/2); ch < (rank+1)*(s[0]/2); ++ch) {
        int local_ch=ch-rank*(s[0]/2);
        float acc = 0;
        for (int tap = 0; tap < 4; ++tap) {
          float v = tap == 3 ? in(0)[ch] : in(1)[local_ch * hist + tap * l.parameter];
          acc = acc + v * gain(l.weights[0], ch * 4 + tap);
        }
        y[ch] = bf(silu(l.parameter == 3 ? bf(acc) : acc));
        for (int j = 0; j < hist - 1; ++j)
          history[local_ch * hist + j] = history[local_ch * hist + j + 1];
        history[local_ch * hist + hist - 1] = in(0)[ch];
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
        float qn = std::sqrt(dot(qr, qr, true) + 1e-6f),
              kn = std::sqrt(dot(kr, kr, true) + 1e-6f);
        for (int j = 0; j < d; ++j) {
          q[h * d + j] = (qr[j] / qn) / std::sqrt(float(d));
          k[h * d + j] = kr[j] / kn;
        }
      }
      V state = clone(in(3)), y = make(vh * d);
      for (int h = rank*(vh/2); h < (rank?vh:vh/2); ++h) {
        float gate = in(1)[h] + gain(l.weights[1], h);
        float sp = gate < 20.f ? std::log(1.f + std::exp(gate)) : gate;
        float stored_a = gain(l.weights[0], h);
        float decay = std::exp(stored_a * sp);
        int key = packed_heads ? h % kh : h / (vh / kh);
        auto qr = q.span().subspan(key * d, d),
             kr = k.span().subspan(key * d, d);
        for (int j = 0; j < d; ++j) {
          int base = ((h-rank*(vh/2)) * d + j) * d;
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
    } else if (op == Op::qsa_append_pool) {
      int pos = position;
      int local_kv=g.kvh>1?g.kvh/2:1, first_kv=g.kvh>1?rank*local_kv:0;
      std::copy(in(0).begin()+first_kv*g.ad,in(0).begin()+(first_kv+local_kv)*g.ad,out(0).begin()+pos*local_kv*g.ad);
      std::copy(in(1).begin()+first_kv*g.ad,in(1).begin()+(first_kv+local_kv)*g.ad,out(1).begin()+pos*local_kv*g.ad);
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
    } else if (op == Op::qsa_attention) {
      V y = make(g.qh * g.ad);
      V ids = make();
      for (float v : in(4))
        if (v >= 0)
          ids.push_back(int(v));
      for (int h = rank*(g.qh/2); h < (rank+1)*(g.qh/2); ++h) {
        int local_kv=g.kvh>1?g.kvh/2:1;
        int kh = h / (g.qh / g.kvh)-(g.kvh>1?rank*local_kv:0);
        V scores = make();
        for (int id : ids)
          scores.push_back(
              dot(in(2).span().subspan((id * local_kv + kh) * g.ad, g.ad),
                  in(0).span().subspan(h * g.ad, g.ad)) /
              std::sqrt(float(g.ad)));
        float m = *std::max_element(scores.begin(), scores.end());
        for (auto &v : scores)
          v = std::exp(v - m);
        float den = tree(scores);
        for (auto &v : scores)
          v = v / den;
        for (int k = 0; k < g.ad; ++k) {
          V terms = make();
          for (size_t i = 0; i < ids.size(); ++i)
            terms.push_back(scores[i] *
                            in(3)[(ids[i] * local_kv + kh) * g.ad + k]);
          y[h * g.ad + k] = bf(bf(tree(terms)) * sigmoid(in(1)[h * g.ad + k]));
        }
      }
      out(0) = y;
    } else failed=1;
  }
};
}
