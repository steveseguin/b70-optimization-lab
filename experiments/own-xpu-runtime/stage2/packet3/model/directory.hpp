#pragma once
#include "../kernels/api.hpp"
#include <algorithm>
#include <fstream>
#include <limits>
#include <map>
#include <sstream>
namespace flash {
using Directory = std::map<std::string, Tensor>;
inline std::string grid_name(Type t) {
  switch (t) {
  case Type::F32:
    return "F32";
  case Type::BF16:
    return "BF16";
  case Type::Q8_0:
    return "Q8_0";
  case Type::Q6_K:
    return "Q6_K";
  case Type::IQ2_S:
    return "IQ2_S";
  case Type::IQ3_S:
    return "IQ3_S";
  case Type::IQ4_NL:
    return "IQ4_NL";
  default:
    throw std::invalid_argument("grid absent from IQ3 census");
  }
}
inline Type grid_type(const std::string &name) {
  for (auto t : {Type::F32, Type::BF16, Type::Q8_0, Type::Q6_K, Type::IQ2_S,
                 Type::IQ3_S, Type::IQ4_NL})
    if (grid_name(t) == name)
      return t;
  throw std::invalid_argument("unknown grid");
}
inline void validate_descriptor(const Tensor &t) {
  auto block = iq3::layout(grid_type(t.grid));
  if (t.shape.empty() || t.shape.back() < 1 || t.shape.back() % block.elements)
    throw std::invalid_argument("row/grid alignment");
  std::uint64_t elements = 1;
  for (int d : t.shape) {
    if (d < 1 || elements > std::numeric_limits<std::uint64_t>::max() / d)
      throw std::invalid_argument("tensor shape overflow");
    elements *= d;
  }
  auto blocks = elements / block.elements;
  if (blocks > std::numeric_limits<std::uint64_t>::max() / block.bytes ||
      blocks * block.bytes != t.bytes)
    throw std::invalid_argument("tensor extent mismatch");
}
// Direct adapter for packet2 iq3::Model::plan / vector<iq3::Planned>.
// Template avoids importing the device owner just to record a host graph.
// Authentication, shard offsets and residency admission remain loader duties.
template <class Records>
Directory directory_from_loader(const Records &records) {
  Directory d;
  for (const auto &r : records) {
    Tensor t{r.name, grid_name(r.type), r.component, {}, r.bytes};
    for (auto dim : r.dimensions) {
      if (dim > std::numeric_limits<int>::max())
        throw std::invalid_argument("dimension overflow");
      t.shape.push_back(int(dim));
    }
    std::reverse(t.shape.begin(), t.shape.end());
    validate_descriptor(t);
    if (!d.emplace(t.name, t).second)
      throw std::invalid_argument("duplicate tensor");
  }
  return d;
}
inline Directory read_directory(std::istream &f) {
  Directory d;
  std::string name, grid, dims, component;
  std::uint64_t bytes;
  while (f >> name >> grid >> dims >> bytes >> component) {
    Tensor t{name, grid, component, {}, bytes};
    std::stringstream s(dims);
    std::string v;
    while (std::getline(s, v, ',')) {
      size_t end = 0;
      auto x = std::stoi(v, &end);
      if (end != v.size())
        throw std::invalid_argument("dimension text");
      t.shape.push_back(x);
    }
    std::reverse(t.shape.begin(), t.shape.end());
    validate_descriptor(t);
    if (!d.emplace(name, t).second)
      throw std::invalid_argument("duplicate tensor");
  }
  if (!f.eof() || d.empty())
    throw std::invalid_argument("invalid directory");
  return d;
}
inline Geometry geometry_from_directory(const Directory &d) {
  Geometry g;
  auto shape = [&](const std::string &n) -> const std::vector<int> & {
    return d.at(n).shape;
  };
  auto matrix = [&](const std::string &n) {
    const auto &s = shape(n);
    if (s.size() != 2)
      throw std::invalid_argument("expected matrix " + n);
    return s;
  };
  auto embed = matrix("token_embd.weight");
  g.h = embed[1];
  g.vocab = embed[0];
  g.low = matrix("output_hc_down.weight")[0];
  const auto &experts = shape("blk.0.ffn_gate_exps.weight");
  if (experts.size() != 3)
    throw std::invalid_argument("expert bank shape");
  g.experts = experts[0];
  g.mid = experts[1];
  const auto &norm = shape("blk.0.ssm_norm.weight");
  if (norm.size() != 1)
    throw std::invalid_argument("GDN norm shape");
  g.d = norm[0];
  g.vh = matrix("blk.0.ssm_alpha.weight")[0];
  g.kh = (matrix("blk.0.attn_qkv.weight")[0] / g.d - g.vh) / 2;
  const auto &qn = shape("blk.3.attn_q_norm.weight");
  if (qn.size() != 1)
    throw std::invalid_argument("QSA norm shape");
  g.ad = qn[0];
  g.qh = matrix("blk.3.attn_q.weight")[0] / (2 * g.ad);
  g.kvh = matrix("blk.3.attn_k.weight")[0] / g.ad;
  const auto &iqn = shape("blk.3.indexer.q_norm.weight");
  if (iqn.size() != 1)
    throw std::invalid_argument("index norm shape");
  g.id = iqn[0];
  g.ih = matrix("blk.3.indexer.q_proj.weight")[0] / g.id;
  // This packet supports this exact admitted family/shape, never silently
  // coerces another directory into a friendly model name.
  if (g.h != 2560 || g.vocab != 248320 || g.low != 320 || g.experts != 512 ||
      g.mid != 640 || g.d != 128 || g.kh != 16 || g.vh != 48 || g.ad != 256 ||
      g.qh != 24 || g.kvh != 2 || g.id != 128 || g.ih != 4)
    throw std::invalid_argument(
        "directory differs from admitted Flash-Next geometry");
  return g;
}
} // namespace flash
