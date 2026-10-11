#pragma once
#include "../model/directory.hpp"
#include <algorithm>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
namespace flash {
class Builder {
  Plan p;
  const Directory *directory;
  std::map<std::string, Buffer> bs;
  std::set<std::string> consumed;
  int card = 0;
  static std::uint64_t count(const std::vector<int> &s) {
    std::uint64_t n = 1;
    for (int d : s) {
      if (d < 1)
        throw std::runtime_error("shape");
      n *= d;
    }
    return n;
  }
  std::uint64_t size(const std::string &n) const {
    auto &b = bs.at(n);
    return count(b.shape) * scalar_bytes(b.type);
  }

public:
  explicit Builder(Geometry g, const Directory *d = nullptr) : directory(d) {
    p.g = g;
  }
  void buffer(std::string n, std::vector<int> s, Scalar t = Scalar::bf16) {
    bs[n] = {n, s, t, card};
  }
  void node(std::string op, std::string label, std::vector<std::string> in,
            std::vector<std::string> out, std::vector<int> shape,
            std::vector<std::string> w = {}, int param = 0) {
    for (const auto &control : {"active", "error"})
      if (op != "begin" && std::find(in.begin(), in.end(), control) == in.end())
        in.push_back(control);
    Launch l{op, label, in, out, w, shape, card, param, -1};
    if (op == "handoff" || op == "handoff_result")
      l.source_card = 1 - card;
    for (auto &n : in)
      l.read_bytes += size(n);
    for (auto &n : out)
      l.write_bytes += size(n);
    for (auto &n : w) {
      if (directory) {
        const auto &t = directory->at(n);
        auto b = t.bytes;
        if (t.component == "routed_experts")
          b = b / p.g.experts * p.g.top;
        if (t.component == "embedding")
          b = b / p.g.vocab;
        if (t.component == "ple_lookup")
          b = b / t.shape[0] * 16;
        l.weight_bytes += b;
      }
      consumed.insert(n);
    }
    if (op == "ple_hash")
      l.weight_bytes += 280;
    p.launches.push_back(l);
  }
  void linear(std::string x, std::string y, int n, int k, std::string w,
              int batch = 1, std::string ids = "") {
    if (directory) {
      const auto &actual = directory->at(w).shape;
      std::vector<int> expected = ids.empty()
                                      ? std::vector<int>{n, k}
                                      : std::vector<int>{p.g.experts, n, k};
      if (actual != expected &&
          !(ids.empty() && n == 1 && actual == std::vector<int>{k}))
        throw std::invalid_argument("GEMV shape " + w);
    }
    buffer(y, {batch, n});
    std::vector<std::string> in{x};
    if (!ids.empty())
      in.push_back(ids);
    std::vector<std::string> outputs{y};
    if (!ids.empty()) {
      buffer(y + ".status", {batch}, Scalar::u32);
      outputs.push_back(y + ".status");
    }
    node(ids.empty() ? "gemv" : "routed_gemv", y, in, outputs, {batch, n, k},
         {w});
    if (!ids.empty())
      node("check_status", y + ".check", {y + ".status", "error"}, {"error"},
           {batch});
  }
  void norm(std::string x, std::string y, int rows, int width, std::string w,
            int unit = 0) {
    if (directory && directory->at(w).shape != std::vector<int>{rows * width})
      throw std::invalid_argument("norm shape " + w);
    buffer(y, {rows, width});
    node("norm", y, {x}, {y}, {rows, width}, {w}, unit);
  }
  std::pair<std::string, std::string> hc(std::string streams,
                                         std::string prefix, std::string tag,
                                         bool inject = true) {
    const auto &g = p.g;
    std::string n = tag + ".norm", lo = tag + ".low", a = tag + ".act",
                gate = tag + ".gate", mix = tag + ".mix", inj = tag + ".inject";
    norm(streams, n, 4, g.h, prefix + "norm.weight");
    linear(n, lo, g.low, 4 * g.h, prefix + "down.weight");
    buffer(a, {g.low});
    node("silu_div4", a, {lo}, {a}, {g.low});
    linear(a, gate, 4 * g.h, g.low, prefix + "up.weight");
    buffer(mix, {g.h});
    node("hc_mix", mix, {n, gate}, {mix}, {4, g.h});
    if (inject)
      linear(n, inj, 4, 4 * g.h, prefix + "inject.weight");
    return {mix, inj};
  }
  void combine(std::string streams, std::string branch, std::string inj,
               std::string tag) {
    node("hc_combine", tag, {streams, branch, inj}, {streams}, {4, p.g.h});
  }
  void gdn(std::string x, std::string prefix, std::string out) {
    const auto &g = p.g;
    auto tag = prefix + "gdn.";
    int ch = (2 * g.kh + g.vh) * g.d;
    linear(x, tag + "qkv", ch, g.h, prefix + "attn_qkv.weight");
    linear(x, tag + "z", g.vh * g.d, g.h, prefix + "attn_gate.weight");
    linear(x, tag + "a", g.vh, g.h, prefix + "ssm_alpha.weight");
    linear(x, tag + "b", g.vh, g.h, prefix + "ssm_beta.weight");
    buffer(tag + "history", {ch, 3});
    buffer(tag + "conv", {ch});
    node("conv", tag + "conv", {tag + "qkv", tag + "history"},
         {tag + "conv", tag + "history"}, {ch}, {prefix + "ssm_conv1d.weight"},
         1);
    buffer(tag + "state", {g.vh, g.d, g.d});
    buffer(tag + "y", {g.vh, g.d});
    node("gdn", tag + "recurrence",
         {tag + "conv", tag + "a", tag + "b", tag + "state"},
         {tag + "y", tag + "state"}, {g.kh, g.vh, g.d},
         {prefix + "ssm_a", prefix + "ssm_dt.bias"}, -1);
    buffer(tag + "gated", {g.vh, g.d});
    node("gdn_norm_gate", tag + "gated", {tag + "y", tag + "z"},
         {tag + "gated"}, {g.vh, g.d}, {prefix + "ssm_norm.weight"});
    linear(tag + "gated", out, g.h, g.vh * g.d, prefix + "ssm_out.weight");
  }
  void qsa(std::string x, std::string prefix, std::string out) {
    const auto &g = p.g;
    auto t = prefix + "qsa.";
    linear(x, t + "qgate", 2 * g.qh * g.ad, g.h, prefix + "attn_q.weight");
    linear(x, t + "k", g.kvh * g.ad, g.h, prefix + "attn_k.weight");
    linear(x, t + "v", g.kvh * g.ad, g.h, prefix + "attn_v.weight");
    linear(x, t + "iq", g.ih * g.id, g.h, prefix + "indexer.q_proj.weight");
    linear(x, t + "ik", g.id, g.h, prefix + "indexer.k_proj.weight");
    buffer(t + "q", {g.qh, g.ad});
    buffer(t + "gate", {g.qh, g.ad});
    buffer(t + "kn", {g.kvh, g.ad});
    buffer(t + "iqn", {g.ih, g.id});
    node("qsa_prepare", t + "prepare",
         {t + "qgate", t + "k", t + "iq", "position"},
         {t + "q", t + "gate", t + "kn", t + "iqn"},
         {g.qh, g.kvh, g.ad, g.ih, g.id},
         {prefix + "attn_q_norm.weight", prefix + "attn_k_norm.weight",
          prefix + "indexer.q_norm.weight"});
    buffer(t + "keys", {g.context, g.kvh, g.ad});
    buffer(t + "values", {g.context, g.kvh, g.ad});
    buffer(t + "raw", {g.context, g.id});
    buffer(t + "pooled", {(g.context + 3) / 4, g.id});
    buffer(t + "ids", {g.budget + 3}, Scalar::i32);
    node("qsa_append_pool", t + "pool",
         {t + "kn", t + "v", t + "ik", "position", t + "raw"},
         {t + "keys", t + "values", t + "raw", t + "pooled"},
         {g.context, g.kvh, g.ad, g.id}, {prefix + "indexer.k_norm.weight"});
    node("qsa_select", t + "select", {t + "iqn", t + "pooled", "position"},
         {t + "ids"}, {g.budget + 3, g.ih, g.id});
    buffer(t + "y", {g.qh, g.ad});
    node("qsa_attention", t + "attention",
         {t + "q", t + "gate", t + "keys", t + "values", t + "ids"}, {t + "y"},
         {g.qh, g.kvh, g.ad, g.budget + 3});
    linear(t + "y", out, g.h, g.qh * g.ad, prefix + "attn_output.weight");
  }
  void ffn(std::string x, std::string t, std::string suffix, int batch,
           std::string ids = "") {
    const auto &g = p.g;
    auto y = t + suffix;
    linear(x, y + "gate", g.mid, g.h, t + "ffn_gate_" + suffix + ".weight",
           batch, ids);
    linear(x, y + "up", g.mid, g.h, t + "ffn_up_" + suffix + ".weight", batch,
           ids);
    buffer(y + "act", {batch, g.mid});
    node("silu_product", y + "act", {y + "gate", y + "up"}, {y + "act"},
         {batch, g.mid});
    linear(y + "act", y + "down", g.h, g.mid,
           t + "ffn_down_" + suffix + ".weight", batch,
           ids.empty() ? ids : ids + ".down");
  }
  void moe(std::string x, std::string t, std::string out) {
    const auto &g = p.g;
    linear(x, t + "router", g.experts, g.h, t + "ffn_gate_inp.weight");
    buffer(t + "ids", {g.top}, Scalar::u32);
    buffer(t + "prob", {g.top}, Scalar::f32);
    node("route", t + "route", {t + "router"}, {t + "ids", t + "prob"},
         {g.experts, g.top});
    // gather builds bounded device Route descriptors, not copies of whole
    // banks.
    buffer(t + "routes", {g.top, 3}, Scalar::u32);
    buffer(t + "routes.down", {g.top, 3}, Scalar::u32);
    buffer(t + "expert_input", {g.top, g.h});
    node("expert_gather", t + "gather", {t + "ids", x},
         {t + "routes", t + "routes.down", t + "expert_input"},
         {g.top, g.h, g.mid});
    ffn(t + "expert_input", t, "exps", g.top, t + "routes");
    ffn(x, t, "shexp", 1);
    linear(x, t + "shared_gate", 1, g.h, t + "ffn_gate_inp_shexp.weight");
    buffer(out, {g.h});
    node("moe_combine", out,
         {t + "expsdown", t + "prob", t + "shexpdown", t + "shared_gate"},
         {out}, {g.top, g.h});
  }
  void ple(std::string streams, std::string t) {
    const auto &g = p.g;
    buffer(t + "ple.ids", {16}, Scalar::i64);
    buffer("token_history", {2}, Scalar::i64);
    buffer("ple_metadata", {35}, Scalar::i64);
    node("ple_hash", t + "ple.hash", {"token", "token_history", "ple_metadata"},
         {t + "ple.ids", "token_history"}, {16});
    buffer(t + "ple.lookup", {g.h});
    node("lookup", t + "ple.lookup", {t + "ple.ids"}, {t + "ple.lookup"},
         {16, g.h / 16}, {"per_layer_token_embd.weight"});
    linear(t + "ple.lookup", t + "ple.key", 4 * g.h, g.h, t + "ple_key.weight");
    linear(t + "ple.lookup", t + "ple.value", g.h, g.h, t + "ple_value.weight");
    norm(t + "ple.key", t + "ple.kn", 4, g.h, t + "ple_norm_key.weight");
    norm(streams, t + "ple.qn", 4, g.h, t + "ple_norm_query.weight");
    buffer(t + "ple.gated", {4, g.h});
    node("ple_gate", t + "ple.gated",
         {t + "ple.kn", t + "ple.qn", t + "ple.value"}, {t + "ple.gated"},
         {4, g.h});
    norm(t + "ple.gated", t + "ple.cn", 4, g.h, t + "ple_norm_conv.weight");
    buffer(t + "ple.history", {4 * g.h, 9});
    buffer(t + "ple.conv", {4 * g.h});
    node("conv", t + "ple.conv", {t + "ple.cn", t + "ple.history"},
         {t + "ple.conv", t + "ple.history"}, {4 * g.h},
         {t + "ple_conv1d.weight"}, 3);
    node("ple_add", t + "ple.add", {streams, t + "ple.gated", t + "ple.conv"},
         {streams}, {4 * g.h});
  }
  Plan build(const std::vector<bool> &full, bool single_layer = false,
             bool mtp = false) {
    if (mtp)
      throw std::invalid_argument(
          "IQ3 directory has no MTP: separate authenticated draft/verification "
          "transaction required");
    const auto &g = p.g;
    buffer("token", {1}, Scalar::i32);
    buffer("position", {1}, Scalar::u32);
    buffer("active", {1}, Scalar::u32);
    buffer("error", {1}, Scalar::u32);
    buffer("streams", {4, g.h});
    buffer("embedding", {g.h});
    buffer("next_token", {1}, Scalar::i32);
    bool two_cards = full.size() == 48 && !single_layer;
    node("begin", "begin.0", {"active", "position"}, {"error"}, {1});
    if (two_cards) {
      card = 1;
      node("begin", "begin.1", {"active", "position"}, {"error"}, {1});
      card = 0;
    }
    node("lookup", "embedding", {"token"}, {"embedding"}, {1, g.h},
         {"token_embd.weight"});
    node("broadcast", "streams", {"embedding"}, {"streams"}, {4, g.h});
    for (size_t i = 0; i < full.size(); ++i) {
      int nextcard = two_cards ? int(i >= 24) : 0;
      if (nextcard != card) {
        card = nextcard;
        node("handoff", "handoff",
             {"streams", "token", "position", "active", "error"},
             {"streams", "token", "position", "active", "error"}, {4, g.h});
      }
      auto t = "blk." + std::to_string(i) + ".";
      if (i == 1)
        ple("streams", t);
      auto [x, inj] = hc("streams", t + "hc_attn_", t + "hc.a");
      if (full[i])
        qsa(x, t, t + "attention");
      else
        gdn(x, t, t + "attention");
      combine("streams", t + "attention", inj, t + "attn.combine");
      auto [y, j] = hc("streams", t + "hc_ffn_", t + "hc.f");
      moe(y, t, t + "moe");
      combine("streams", t + "moe", j, t + "ffn.combine");
    }
    if (!single_layer) {
      auto [x, unused] = hc("streams", "output_hc_", "final", false);
      linear(x, "logits", g.vocab, g.h, "output.weight");
      node("argmax", "argmax", {"logits"}, {"next_token", "error"}, {g.vocab});
    }
    if (two_cards) {
      card = 0;
      node("handoff_result", "handoff.result", {"next_token", "error"},
           {"next_token", "error"}, {1});
      node("commit", "commit.0", {"error", "active", "position"}, {"position"},
           {1}, {}, 0);
      card = 1;
    }
    node("commit", "commit.final", {"error", "active", "position"},
         {"position"}, {1}, {}, 1);
    if (two_cards)
      for (const auto &name :
           {"streams", "token", "position", "active", "error", "next_token"})
        bs.at(name).card = -1;
    if (directory && !single_layer)
      for (const auto &[n, t] : *directory)
        if (!consumed.count(n))
          throw std::runtime_error("unused tensor " + n);
    for (auto &[n, b] : bs)
      p.buffers.push_back(b);
    return p;
  }
};
inline Plan model_plan(const Directory &d) {
  std::vector<bool> full;
  for (int i = 0; i < 48; ++i) {
    auto p = "blk." + std::to_string(i) + ".";
    bool gdn = d.count(p + "ssm_a"), qsa = d.count(p + "attn_q.weight");
    if (gdn == qsa)
      throw std::runtime_error("ambiguous/missing layer");
    full.push_back(qsa);
  }
  return Builder(geometry_from_directory(d), &d).build(full);
}
} // namespace flash
