#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet3/model/directory_v41.hpp"
#include <cstdlib>
#include <map>
#include <set>
#include <vector>
// DeepSeek V4.1 Flash decode-step plan builder. Parallel family to
// packet3/step/plan.hpp: same Launch/Buffer/Backend contract types, own
// geometry and op vocabulary. Op order mirrors the official model.py
// decode step exactly:
//   embed -> 4 hc copies -> per layer:
//     [engram (layers 1,14): hash 24 rows -> NVMe lookup -> wkv gemv
//      -> normalized-dot gate -> add into streams]
//     [MTP capture (37,38,39): mean over hc copies, pre-block]
//     hc_mixes(attn) -> hc_pre(prev ffn mix) -> attn_norm ->
//     q LoRA + q_norm -> q_b -> rope(YaRN tail 64) ->
//     wkv -> kv_norm -> rope -> window ring append + window idxs ->
//     [ratio>0: compressor on kv sources {2,8,14,20}, indexer on index
//      sources {2,8,14,20,24,28,32,36}; other layers reference the latest
//      published caches] ->
//     sparse_attn(window+compress, sinks, scale 512^-0.5) ->
//     inverse rope on the output tail -> grouped o_a (8 x 1024x4096)
//     -> o_b -> hc_post ->
//     hc_mixes(ffn) -> hc_pre(attn mix) -> ffn_norm ->
//     router (sqrtsoftplus top-6, bias-select, norm x1.5) -> gather ->
//     gate/up -> swiglu(clamp 10: up both sides, gate above) ->
//     prob scale (pre-down, matches training) -> down -> + shared expert
//     -> hc_post
//   -> hc_pre(last ffn mix) -> output_norm -> output gemv -> argmax.
// Numerics note: the engine runs activations in bf16/f32; the reference
// fp8/fp4 act_quant steps are lower-precision re-quantizations and are
// intentionally not emitted (equal-or-better precision).
// Weight names are GGUF names, validated against the directory; build
// fails on any unused tensor.
namespace flash41 {
using flash::Backend;
using flash::Buffer;
using flash::Directory;
using flash::Event;
using flash::Launch;
using flash::Scalar;
using flash::scalar_bytes;
struct Plan41 {
  GeometryV41 g;
  std::vector<Launch> launches;
  std::vector<Buffer> buffers;
  Event execute(Backend &b, Event inputs_ready) const {
    auto e = inputs_ready;
    try {
      for (const auto &launch : launches)
        e = b.enqueue(launch, e);
    } catch (...) {
      b.submission_failed();
      throw;
    }
    return e;
  }
};
class BuilderV41 {
  Plan41 p;
  std::map<std::string, Buffer> bs;
  std::set<std::string> consumed;
  const Directory *directory;
  int card = 0;
  int max_seq;
  std::uint64_t size(const std::string &n) const {
    const auto &b = bs.at(n);
    std::uint64_t s = scalar_bytes(b.type);
    for (int d : b.shape) s *= d;
    return s;
  }
  void buffer(const std::string &name, std::vector<int> shape,
              Scalar t = Scalar::bf16) {
    Buffer b{name, std::move(shape), t, card};
    if (!bs.emplace(name, b).second)
      throw std::invalid_argument("duplicate buffer " + name);
  }
  void node(const std::string &op, const std::string &label,
            std::vector<std::string> in, std::vector<std::string> out,
            std::vector<int> shape, std::vector<std::string> w = {},
            int param = 0) {
    Launch l;
    l.op = op; l.label = label; l.inputs = std::move(in);
    l.outputs = std::move(out); l.shape = std::move(shape);
    l.card = card; l.parameter = param; l.weights = std::move(w);
    for (auto &n : l.inputs) l.read_bytes += size(n);
    for (auto &n : l.outputs) l.write_bytes += size(n);
    for (auto &n : l.weights) {
      if (directory) {
        auto it = directory->find(n);
        if (it == directory->end())
          throw std::invalid_argument("weight absent from directory " + n);
        const auto &t = it->second;
        auto b = t.bytes;
        if (t.component == "embedding") b = b / p.g.vocab;
        if (n == "per_layer_token_embd.weight") b = 0; // NVMe store, not VRAM
        l.weight_bytes += b;
      }
      consumed.insert(n);
    }
    p.launches.push_back(std::move(l));
  }
  void linear(std::string x, std::string y, int n, int k, std::string w,
              int batch = 1, std::string ids = "") {
    if (directory) {
      const auto &actual = directory->at(w).shape;
      std::vector<int> expected = ids.empty()
                                      ? std::vector<int>{n, k}
                                      : std::vector<int>{p.g.experts, n, k};
      if (actual != expected)
        throw std::invalid_argument("GEMV shape " + w);
    }
    buffer(y, {batch, n});
    std::vector<std::string> in{x};
    if (!ids.empty()) in.push_back(ids);
    node(ids.empty() ? "gemv" : "routed_gemv", y, in, {y}, {batch, n, k}, {w});
  }
  void norm(std::string x, std::string y, int rows, int width, std::string w) {
    if (directory && directory->at(w).shape != std::vector<int>{rows * width})
      throw std::invalid_argument("norm shape " + w);
    buffer(y, {rows, width});
    node("norm", y, {x}, {y}, {rows, width}, {w});
  }
  void hc_mixes(std::string streams, std::string prefix, std::string tag) {
    const auto &g = p.g;
    buffer(tag + ".pre", {4}, Scalar::f32);
    buffer(tag + ".post", {4}, Scalar::f32);
    buffer(tag + ".comb", {4, 4}, Scalar::f32);
    node("hc_mix41", tag + ".mix", {streams},
         {tag + ".pre", tag + ".post", tag + ".comb"}, {4, g.h},
         {prefix + "fn.weight", prefix + "scale.weight", prefix + "base.weight"});
  }
  void hc_pre(std::string streams, std::string mix, std::string out) {
    buffer(out, {p.g.h});
    node("hc_pre", out + ".pre", {streams, mix}, {out}, {4, p.g.h});
  }
  void hc_post(std::string streams, std::string x, std::string post,
               std::string comb, std::string tag) {
    node("hc_post", tag + ".post", {streams, x, post, comb}, {streams},
         {4, p.g.h});
  }
  // Latest publisher at or below `layer` from `sources` (shared_attn caches).
  static int published_by(int layer, const std::set<int> &sources) {
    int s = -1;
    for (int c : sources)
      if (c <= layer) s = c;
    return s;
  }
  void attention(std::string x, std::string t, std::string out, int layer,
                 bool kv_source, bool index_source, int ratio) {
    const auto &g = p.g;
    linear(x, t + "attn.qa", g.qrank, g.h, t + "attn_q_a.weight");
    norm(t + "attn.qa", t + "attn.qn", 1, g.qrank, t + "attn_q_a_norm.weight");
    linear(t + "attn.qn", t + "attn.q", g.qh * g.hd, g.qrank, t + "attn_q_b.weight");
    linear(x, t + "attn.kv", g.krank, g.h, t + "attn_kv.weight");
    norm(t + "attn.kv", t + "attn.kvn", 1, g.krank, t + "attn_kv_a_norm.weight");
    // param: 1 = YaRN(16x, compress_rope_theta) layers, 0 = base rope (0,1)
    int yarn = ratio > 0 ? 1 : 0;
    node("rope_yarn", t + "attn.rope.q", {t + "attn.q", "position"},
         {t + "attn.q"}, {g.qh, g.hd, 64}, {}, yarn);
    node("rope_yarn", t + "attn.rope.kv", {t + "attn.kvn", "position"},
         {t + "attn.kvn"}, {1, g.hd, 64}, {}, yarn);
    buffer(t + "attn.window_kv", {128, g.hd});
    buffer(t + "attn.window_idxs", {128}, Scalar::i32);
    node("window_append", t + "attn.wappend", {t + "attn.kvn", "position"},
         {t + "attn.window_kv", t + "attn.window_idxs"}, {128, g.hd});
    // compress path: only source layers own caches; others reference the
    // latest publisher's buffers (shared_attn.compress_kv / topk_idxs).
    std::string ckv, cidx;
    if (ratio > 0) {
      int src = published_by(layer, kv_sources);
      int isrc = published_by(layer, index_sources);
      ckv = "blk." + std::to_string(src) + ".attn.compress_kv";
      cidx = "blk." + std::to_string(isrc) + ".attn.topk_idxs";
      if (kv_source) {
        buffer(ckv, {max_seq / ratio, g.hd});
        // ratio 1: plain projection (no gate/pooling); ratio>1: gated
        // softmax pooling with partial-group state (reference Compressor)
        std::vector<std::string> cw{t + "attn_compressor_kv.weight",
                                    t + "attn_compressor_norm.weight"};
        if (ratio > 1)
          cw.push_back(t + "attn_compressor_gate.weight");
        node("compress41", t + "attn.compress", {x, "position"}, {ckv},
             {ratio, g.hd}, cw, ratio);
      }
      if (index_source) {
        buffer(cidx, {512}, Scalar::i32);
        // index keys derive from the compressor's latent, so only kv-source
        // layers own wk/k_norm; other indexers read the published cache and
        // their checkpoint attn_k/k_norm tensors are unused residue.
        std::vector<std::string> iw{t + "indexer.attn_q_b.weight",
                                    t + "indexer.proj.weight"};
        if (kv_source)
          iw.insert(iw.end(), {t + "indexer.attn_k.weight",
                               t + "indexer.k_norm.weight"});
        node("index41", t + "attn.index", {t + "attn.qn", ckv, "position"},
             {cidx}, {512, 128}, iw, layer > 20 ? 1 : 0); // 1: two-level via candidate blocks
      }
    }
    buffer(out, {g.qh, g.hd});
    std::vector<std::string> ain{t + "attn.q", t + "attn.window_kv",
                                 t + "attn.window_idxs"};
    if (ratio > 0) ain.insert(ain.end(), {ckv, cidx});
    node("sparse_attn41", t + "attention", ain, {out},
         {g.qh, g.hd, 128, ratio > 0 ? 512 : 0}, {t + "attn_sinks.weight"});
    node("rope_yarn_inv", t + "attn.irope", {out, "position"}, {out},
         {g.qh, g.hd, 64});
    // grouped output LoRA: 8 groups, each projects only its own heads.
    buffer(t + "attn.oa", {g.ototal});
    node("gemv_grouped", t + "attn.oa.g", {out}, {t + "attn.oa"},
         {8, g.ototal / 8, g.oin}, {t + "attn_output_a.weight"});
    linear(t + "attn.oa", t + "attn.ob", g.h, g.ototal, t + "attn_output_b.weight");
  }
  void expert(std::string x, std::string t, std::string suffix, int batch,
              std::string ids, std::string down) {
    const auto &g = p.g;
    linear(x, t + suffix + "gate", g.mid, g.h, t + "ffn_gate_" + suffix + ".weight", batch, ids);
    linear(x, t + suffix + "up", g.mid, g.h, t + "ffn_up_" + suffix + ".weight", batch, ids);
    buffer(t + suffix + "act", {batch, g.mid});
    node("swiglu_clamp", t + suffix + "swiglu",
         {t + suffix + "gate", t + suffix + "up"}, {t + suffix + "act"},
         {batch, g.mid});
    linear(t + suffix + "act", down, g.h, g.mid, t + "ffn_down_" + suffix + ".weight", batch, ids);
  }
  void moe(std::string x, std::string t, std::string out) {
    const auto &g = p.g;
    linear(x, t + "router", g.experts, g.h, t + "ffn_gate_inp.weight");
    buffer(t + "ids", {6}, Scalar::u32);
    buffer(t + "prob", {6}, Scalar::f32);
    node("route41", t + "route", {t + "router"}, {t + "ids", t + "prob"},
         {g.experts, 6}, {t + "exp_probs_b.bias", t + "exp_probs_b_vl.bias"});
    buffer(t + "expert_input", {6, g.h});
    node("expert_gather", t + "gather", {t + "ids", x}, {t + "expert_input"},
         {6, g.h, g.mid});
    // routed experts: weights applied to the silu product BEFORE down,
    // matching the reference Expert.forward (weights * x then w2).
    linear(t + "expert_input", t + "expsgate", g.mid, g.h,
           t + "ffn_gate_exps.weight", 6, t + "ids");
    linear(t + "expert_input", t + "expsup", g.mid, g.h,
           t + "ffn_up_exps.weight", 6, t + "ids");
    buffer(t + "act", {6, g.mid});
    node("swiglu_clamp", t + "swiglu", {t + "expsgate", t + "expsup"},
         {t + "act"}, {6, g.mid});
    node("prob_scale41", t + "pscale", {t + "act", t + "prob"}, {t + "act"},
         {6, g.mid});
    linear(t + "act", t + "expsdown", g.h, g.mid, t + "ffn_down_exps.weight",
           6, t + "ids");
    expert(x, t, "shexp", 1, "", t + "shdown");
    buffer(out, {g.h});
    node("moe_combine41", t + "moe.combine", {t + "expsdown", t + "shdown"},
         {out}, {6, g.h});
  }
  void engram(std::string streams, std::string t) {
    const auto &g = p.g;
    buffer(t + "engram.ids", {24}, Scalar::i64); // (ngram-1)*8 heads
    node("engram_hash", t + "engram.hash", {"token", "token_history"},
         {t + "engram.ids", "token_history"}, {24});
    buffer(t + "engram.rows", {24 * g.engram_dim});
    node("engram_lookup", t + "engram.lookup", {t + "engram.ids"},
         {t + "engram.rows"}, {24, g.engram_dim}, {"per_layer_token_embd.weight"});
    buffer(t + "engram.kvbuf", {5 * g.h});
    node("gemv", t + "engram.kv", {t + "engram.rows"}, {t + "engram.kvbuf"},
         {1, 5 * g.h, 24 * g.engram_dim}, {t + "engram_kv.weight"});
    node("engram_gate", t + "engram.gate", {streams, t + "engram.kvbuf"},
         {streams}, {4, g.h}, {t + "engram_gate.weight"});
  }

public:
  static inline const std::set<int> kv_sources = {2, 8, 14, 20};
  static inline const std::set<int> index_sources = {2, 8, 14, 20, 24, 28, 32, 36};
  BuilderV41(GeometryV41 g, const Directory *d, int max_seq_len = 32768)
      : directory(d), max_seq(max_seq_len) { p.g = g; }
  Plan41 build() {
    const auto &g = p.g;
    buffer("token", {1}, Scalar::i32);
    buffer("position", {1}, Scalar::u32);
    buffer("active", {1}, Scalar::u32);
    buffer("error", {1}, Scalar::u32);
    buffer("streams", {4, g.h});
    buffer("embedding", {g.h});
    buffer("next_token", {1}, Scalar::i32);
    buffer("pre_mix", {4}, Scalar::f32);
    buffer("token_history", {4}, Scalar::i64);
    node("begin", "begin.0", {"active", "position"}, {"error"}, {1});
    node("lookup", "embedding", {"token"}, {"embedding"}, {1, g.h},
         {"token_embd.weight"});
    node("broadcast", "streams", {"embedding"}, {"streams"}, {4, g.h});
    node("identity_mix", "pre_mix.init", {}, {"pre_mix"}, {4});
    static const std::set<int> engram_layers = {1, 14};
    static const std::set<int> mtp_targets = {37, 38, 39};
    for (int i = 0; i < g.layers; ++i) {
      auto t = "blk." + std::to_string(i) + ".";
      if (engram_layers.count(i))
        engram("streams", t);
      if (mtp_targets.count(i)) {
        buffer("main_hidden." + std::to_string(i), {g.h});
        node("hc_mean", t + "mtp.capture", {"streams"},
             {"main_hidden." + std::to_string(i)}, {4, g.h});
      }
      hc_mixes("streams", t + "hc_attn_", t + "hc.a");
      hc_pre("streams", "pre_mix", t + "attn.in");
      norm(t + "attn.in", t + "attn.n", 1, g.h, t + "attn_norm.weight");
      attention(t + "attn.n", t, t + "attn.out", i, kv_sources.count(i),
                index_sources.count(i), i < 2 ? 0 : (i < 20 ? 2 : 1));
      hc_post("streams", t + "attn.ob", t + "hc.a.post", t + "hc.a.comb",
              t + "attn");
      hc_mixes("streams", t + "hc_ffn_", t + "hc.f");
      hc_pre("streams", t + "hc.a.pre", t + "ffn.in");
      norm(t + "ffn.in", t + "ffn.n", 1, g.h, t + "ffn_norm.weight");
      moe(t + "ffn.n", t, t + "moe");
      hc_post("streams", t + "moe", t + "hc.f.post", t + "hc.f.comb", t + "ffn");
      node("copy", t + "mix.thread", {t + "hc.f.pre"}, {"pre_mix"}, {4});
    }
    hc_pre("streams", "pre_mix", "final");
    norm("final", "final.n", 1, g.h, "output_norm.weight");
    linear("final.n", "logits", g.vocab, g.h, "output.weight");
    node("argmax", "argmax", {"logits"}, {"next_token", "error"}, {g.vocab});
    node("commit", "commit.final", {"error", "active", "position"},
         {"position"}, {1}, {}, 1);
    if (directory)
      for (const auto &[n, t] : *directory)
        if (!consumed.count(n) && !checkpoint_residue(n))
          throw std::runtime_error("unused tensor " + n);
    for (auto &[n, b] : bs)
      p.buffers.push_back(b);
    return p;
  }
  static bool checkpoint_residue(const std::string &n) {
    // Index keys come from the compressor's latent, so indexer wk/k_norm on
    // non-kv-source layers (24,28,32,36) are checkpoint residue the official
    // forward never reads (Indexer.owns_k == False there).
    if (n.find("indexer.") == std::string::npos) return false;
    if (n.find("attn_k.weight") == std::string::npos &&
        n.find("k_norm.weight") == std::string::npos) return false;
    int layer = std::stoi(n.substr(4, n.find('.', 4) - 4));
    return index_sources.count(layer) && !kv_sources.count(layer);
  }
};
inline Plan41 model_plan_v41(const Directory &d, int max_seq = 32768) {
  return BuilderV41(geometry_v41_from_directory(d), &d, max_seq).build();
}
} // namespace flash41
