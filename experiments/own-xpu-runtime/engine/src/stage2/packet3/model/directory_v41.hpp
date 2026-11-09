#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet3/model/directory.hpp"
#include <stdexcept>
// DeepSeek V4.1 Flash (deepseek41) directory adapter. Separate struct and
// gate from the SC117 Geometry: this packet supports this exact admitted
// family/shape, never silently coerces another directory into a friendly
// model name. Shape-derived fields only; rope/window/sinkhorn constants
// come from the deployment profile, not from tensor shapes.
namespace flash41 {
struct GeometryV41 {
  int h = 5120, vocab = 129280;
  int layers = 40;          // counted from blk.N tensor names
  int experts = 384, mid = 2304;
  int qrank = 1280, qh = 64, hd = 512;  // q LoRA rank, q heads, head dim
  int krank = 512;                      // latent KV rank
  int ototal = 8192, oin = 4096;        // output LoRA: o_groups*o_rank out, v total in
  int hcs = 20480, hcw = 24;            // hyperconnection stream floats, mix width
  int engram_dim = 256;                 // per_layer_token_embd row width
  std::uint64_t engram_rows = 768022850; // both engram layers concatenated
};
inline GeometryV41 geometry_v41_from_directory(const flash::Directory &d) {
  GeometryV41 g;
  auto shape = [&](const std::string &n) -> const std::vector<int> & {
    return d.at(n).shape;
  };
  auto matrix = [&](const std::string &n) {
    const auto &s = shape(n);
    if (s.size() != 2)
      throw std::invalid_argument("expected matrix " + n);
    return s;
  };
  const auto &embed = matrix("token_embd.weight");
  g.h = embed[1];
  g.vocab = embed[0];
  int layers = 0;
  for (const auto &[name, t] : d)
    if (name.rfind("blk.", 0) == 0)
      layers = std::max(layers, std::stoi(name.substr(4, name.find('.', 4) - 4)) + 1);
  g.layers = layers;
  const auto &experts = shape("blk.0.ffn_gate_exps.weight");
  if (experts.size() != 3)
    throw std::invalid_argument("expert bank shape");
  g.experts = experts[0];
  g.mid = experts[1];
  const auto &qb = matrix("blk.0.attn_q_b.weight");
  g.qrank = qb[1];
  const auto &sinks = shape("blk.0.attn_sinks.weight");
  if (sinks.size() != 1)
    throw std::invalid_argument("attn sinks shape");
  g.qh = sinks[0];
  g.hd = qb[0] / g.qh;
  g.krank = matrix("blk.0.attn_kv.weight")[0];
  const auto &oa = matrix("blk.0.attn_output_a.weight");
  g.ototal = oa[0];
  g.oin = oa[1];
  const auto &hcf = matrix("blk.0.hc_attn_fn.weight");
  g.hcs = hcf[1];
  g.hcw = hcf[0];
  const auto &engram = shape("per_layer_token_embd.weight");
  if (engram.size() != 2)
    throw std::invalid_argument("engram table shape");
  g.engram_dim = engram[1];
  g.engram_rows = std::uint64_t(engram[0]);
  if (g.h != 5120 || g.vocab != 129280 || g.layers != 40 || g.experts != 384 ||
      g.mid != 2304 || g.qrank != 1280 || g.qh != 64 || g.hd != 512 ||
      g.krank != 512 || g.ototal != 8192 || g.oin != 4096 || g.hcs != 20480 ||
      g.hcw != 24 || g.engram_dim != 256 || g.engram_rows != 768022850)
    throw std::invalid_argument(
        "directory differs from admitted DeepSeek V4.1 Flash geometry");
  return g;
}
} // namespace flash41
