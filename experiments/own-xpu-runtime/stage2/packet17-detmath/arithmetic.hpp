#pragma once
// Sole packet13 arithmetic authority. Reuse the measured kernels' own reference
// trees, do not duplicate their reductions. A selection/tree change bumps ID.
#include "../packet9-kopt4/reference.hpp"
#include "../packet9-kopt4/dispatch.hpp"
namespace integrated::arithmetic {
inline constexpr char version[] = "iq3-p17-detmath-v2";
inline unsigned variant(iq3::Type type, unsigned rows, unsigned cols,
                        unsigned experts, bool mini) {
  if (experts > 1 || mini) return 2; // fused SG32, packet9 measured expert winner
  return iq3::kopt4::dispatch_variant(unsigned(type), rows, cols, experts);
}
inline const char* name(unsigned v) {
  constexpr const char* names[]{"kopt_sg32", "splitk4_v1",
    "decode_const_sg32_v1", "decode_slm_sg32_v1",
    "decode_const_split4_v1", "decode_slm_split4_v1"};
  if (v > 5) throw std::invalid_argument("arithmetic variant");
  return names[v];
}
inline float row(iq3::Type t, const uint8_t* w, const uint16_t* x,
                 size_t k, unsigned v) {
  using namespace iq3;
  if (v == 0) return kopt::gemv_row(t,w,x,Type::BF16,k,32);
  if (v == 1) return kopt2::row(t,w,x,Type::BF16,k,kopt2::Variant::split4);
  return kopt3::row(t,w,x,Type::BF16,k,v >= 4 ?
    kopt3::Variant::constant_split4 : kopt3::Variant::constant);
}
// Nonlinear reductions/casts use packet4/core.hpp in both CPU and SYCL builds.
// Transcendental libraries still require device parity; shared source is no proof.
}
