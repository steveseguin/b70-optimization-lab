#pragma once
#include "../packet2/kernels/device.hpp"
#include "core_v2.hpp"
#include <cstring>
namespace integrated {
using flash::Scalar;
struct View {
  void *p = nullptr;
  size_t n = 0;
  Scalar type = Scalar::bf16;
  float get(size_t i) const {
    switch (type) {
    case Scalar::bf16:
      return iq3::bits_float(uint32_t(static_cast<uint16_t *>(p)[i]) << 16);
    case Scalar::f32:
      return static_cast<float *>(p)[i];
    case Scalar::i32:
      return float(static_cast<int32_t *>(p)[i]);
    case Scalar::u32:
      return float(static_cast<uint32_t *>(p)[i]);
    case Scalar::i64:
      return float(static_cast<int64_t *>(p)[i]);
    }
    return 0;
  }
  void put(size_t i, float v) const {
    switch (type) {
    case Scalar::bf16:
      static_cast<uint16_t *>(p)[i] = iq3::bf16_bits(v);
      break;
    case Scalar::f32:
      static_cast<float *>(p)[i] = v;
      break;
    case Scalar::i32:
      static_cast<int32_t *>(p)[i] = int32_t(v);
      break;
    case Scalar::u32:
      static_cast<uint32_t *>(p)[i] = uint32_t(v);
      break;
    case Scalar::i64:
      static_cast<int64_t *>(p)[i] = int64_t(v);
      break;
    }
  }
};
enum class Special { normal, begin, commit, broadcast, ple_hash, check_status };
struct Spec {
  Geometry g;
  Op op{};
  Special special = Special::normal;
  Core::Site site;
  int ni = 0, no = 0, nw = 0;
  size_t sizes[20]{};
  Scalar types[20]{};
  iq3::Type grids[4]{};
  size_t weight_elements[4]{};
  bool packed_heads = false;
  uint8_t parameter_padding[7]{};
};
static_assert(sizeof(Spec)==440);
// Bind inputs, outputs, weights, scratch, error, position, active, RoPE in that
// order.
inline void evaluate(Spec spec, void *const *p) {
  View in[10], out[6];
  int k = 0;
  for (int i = 0; i < spec.ni; ++i, ++k)
    in[i] = {p[k], spec.sizes[k], spec.types[k]};
  for (int i = 0; i < spec.no; ++i, ++k)
    out[i] = {p[k], spec.sizes[k], spec.types[k]};
  int weight_base = k;
  k += spec.nw;
  float *scratch = static_cast<float *>(p[k++]);
  auto error = static_cast<uint32_t *>(p[k++]);
  auto pos = static_cast<uint32_t *>(p[k++]);
  auto active = static_cast<uint32_t *>(p[k++]);
  if (!*active)
    return;
  if (spec.special == Special::begin) {
    if (*pos >= unsigned(spec.g.context))
      *error = 1;
    return;
  }
  if (*error)
    return;
  if (spec.special == Special::commit) {
    ++*pos;
    return;
  }
  if (spec.special == Special::broadcast) {
    for (size_t i = 0; i < out[0].n; ++i)
      out[0].put(i, in[0].get(i % in[0].n));
    return;
  }
  if (spec.special == Special::check_status) {
    for (size_t i = 0; i < in[0].n; ++i)
      if (in[0].get(i))
        *error = 1;
    return;
  }
  if (spec.special == Special::ple_hash) {
    auto history = static_cast<int64_t *>(in[1].p);
    auto meta = static_cast<int64_t *>(in[2].p);
    auto ids = static_cast<int64_t *>(out[0].p);
    int64_t token = static_cast<int32_t *>(in[0].p)[0], old0 = history[0],
            old1 = history[1];
    if (old1 == spec.g.eos)
      old0 = spec.g.eos;
    for (int n = 2; n <= 3; ++n) {
      uint64_t hash = uint64_t(token) * uint64_t(meta[0]);
      hash ^= uint64_t(old1) * uint64_t(meta[1]);
      if (n == 3)
        hash ^= uint64_t(old0) * uint64_t(meta[2]);
      auto v = std::bit_cast<int64_t>(hash);
      for (int h = 0; h < 8; ++h) {
        int i = (n - 2) * 8 + h;
        auto size = meta[3 + i];
        if (size <= 0) {
          *error = 1;
          return;
        }
        ids[i] = (v % size + size) % size + meta[19 + i];
      }
    }
    history[0] = old1;
    history[1] = token;
    return;
  }
  Core c;
  c.pool = {scratch, 0, 64ull * 1024 * 1024, 0};
  c.g = spec.g;
  c.rope_table=static_cast<const uint16_t*>(p[k]);
  c.op = spec.op;
  c.l = spec.site;
  c.s = c.l.shape;
  // The serial control path must guard standalone QSA submissions too.
  // Never narrow a poisoned unsigned position before checking its range.
  if (*pos >= unsigned(spec.g.context)) { *error = 1; c.position = 0; }
  else c.position = int(*pos);
  c.packed_heads = spec.packed_heads;
  for (int i = 0; i < spec.ni; ++i) {
    c.inputs[i] = c.make(in[i].n);
    for (size_t j = 0; j < in[i].n; ++j)
      c.inputs[i][j] = in[i].get(j);
  }
  for (int i = 0; i < spec.no; ++i) {
    c.outputs[i] = c.make(out[i].n);
    for (size_t j = 0; j < out[i].n; ++j)
      c.outputs[i][j] = out[i].get(j);
  }
  for (int i = 0; i < spec.nw; ++i)
    c.weights[i] = {static_cast<const uint8_t *>(p[weight_base + i]),
                    spec.grids[i], spec.weight_elements[i]};
  c.run();
  if (c.failed || c.pool.failed) {
    *error = 1;
    return;
  }
  for (int i = 0; i < spec.no; ++i) {
    if (c.outputs[i].n != out[i].n) {
      *error = 1;
      return;
    }
  }
  for (int i = 0; i < spec.no; ++i)
    for (size_t j = 0; j < out[i].n; ++j)
      out[i].put(j, c.outputs[i][j]);
}
#ifdef OWN_RT_HOST_ONLY
struct HostOperation : ownrt::Operation {
  virtual void run(std::span<void *const>) const = 0;
};
#endif
} // namespace integrated
namespace iq3 {
// Packet2 kernel extension for packet3's compound sites, same Arena/event API.
ownrt::Event step_operator(ownrt::Device &, const integrated::Spec &,
                           std::span<const ownrt::Allocation>);
} // namespace iq3
