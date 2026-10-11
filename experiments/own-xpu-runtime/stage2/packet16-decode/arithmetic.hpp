#pragma once
// Sole packet13 arithmetic authority. Reuse the measured kernels' own reference
// trees, do not duplicate their reductions. A selection/tree change bumps ID.
#include "../packet9-kopt4/reference.hpp"
#include "../packet9-kopt4/dispatch.hpp"
#include "../packet10-kopt5/expanded.hpp"
namespace integrated::arithmetic {
inline constexpr char version[] = "iq3-p13-r234-sg32-split4-bf16-v1";
inline unsigned variant(iq3::Type type, unsigned rows, unsigned cols,
                        unsigned experts, bool mini) {
  if (experts > 1 || mini) return 2; // fused SG32, packet9 measured expert winner
  return iq3::kopt4::dispatch_variant(unsigned(type), rows, cols, experts);
}
inline const char* name(unsigned v) {
  constexpr const char* names[]{"kopt_sg32", "splitk4_v1",
    "decode_const_sg32_v1", "decode_slm_sg32_v1",
    "decode_const_split4_v1", "decode_slm_split4_v1",
    "expanded_sg32_v1", "expanded_split4_v1"};
  if (v > 7) throw std::invalid_argument("arithmetic variant");
  return names[v];
}
inline float row(iq3::Type t, const uint8_t* w, const uint16_t* x,
                 size_t k, unsigned v) {
  using namespace iq3;
  if (v == 6 || v == 7) return expanded::row(t,w,x,Type::BF16,k,v == 7 ? 4 : 1);
  if (v == 0) return kopt::gemv_row(t,w,x,Type::BF16,k,32);
  if (v == 1) return kopt2::row(t,w,x,Type::BF16,k,kopt2::Variant::split4);
  return kopt3::row(t,w,x,Type::BF16,k,v >= 4 ?
    kopt3::Variant::constant_split4 : kopt3::Variant::constant);
}
// R5's actual timed layer code preserves the frozen reduction tree. Its two
// names select different HEAD trees only (packet10/tests/timing.cpp:119).
// The head SG32 winner keeps v1; making all dense rows split4 would not.
inline unsigned r5_variant(iq3::Type type, unsigned rows, unsigned cols,
                           unsigned experts, bool mini) {
  const auto frozen = variant(type, rows, cols, experts, mini);
  if (mini || experts > 1 || !iq3::expanded::quantized(type)) return frozen;
  return frozen == 1 || frozen == 4 ? 7 : 6;
}
inline bool is_expanded(unsigned v) { return v == 6 || v == 7; }
inline size_t row_bytes(iq3::Type type, size_t columns, unsigned v) {
  auto fmt=iq3::layout(type);
  return is_expanded(v) ? iq3::expanded::row_bytes(type, columns) :
    columns / fmt.elements * fmt.bytes;
}
// Nonlinear reductions/casts use packet4/core.hpp in both CPU and SYCL builds.
// Transcendental libraries still require device parity; shared source is no proof.
}
