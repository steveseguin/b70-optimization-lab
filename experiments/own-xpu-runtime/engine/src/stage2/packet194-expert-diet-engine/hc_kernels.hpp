#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
// OWNRT_HC_KERNELS (lab 2026-10-30, research/hc-kernels-2026-10-30, default off): exact decode HC kernels. "1" enables
// norm1,lowsel,cnorm; otherwise a comma list of tokens:
//  norm1   the HC norm (4 x 2560 F32 streams, F32 gain, one token row) in ONE launch instead of specialised's two:
//          work-group h owns stream row h; the same 32-leaf adjacent subtrees of x^2 (also written to the scratch row,
//          as stage 0 writes them), the same upper() over the 80 partials (evaluated by one subgroup, upper80), the
//          same rsqrt and output expression, the same guard results (specialised_submit.cpp).
//  lowsel  dense_v2 BF16 rows (the bf16_multi<1,8> sites: HC low + inject, the final HC low, ...) choose their matrix
//          by static indices instead of a runtime index into the captured descriptor array, which kept the
//          descriptors in private memory: bf16_multi_static<1,10>, the same bf16_rows per row (kopt kernels.cpp).
//  cnorm   decode only: an HC combine (CombineFast, F32) directly followed on the same card by the HC norm of the same
//          streams runs as one launch at the norm site (combine_norm, specialised_submit.cpp); the combine site then
//          issues nothing (generic_engine.hpp, main.cpp execute_site). Row replays (dev.view_row >= 0), batched
//          prefill and every non-adjacent pair keep both sites; the plan itself is unchanged.
#include <cstdint>
#include <cstdlib>
#include <string>
namespace hc_kernels {
inline const std::string& list() {
  static const std::string v = [] {
    const char* e = std::getenv("OWNRT_HC_KERNELS");
    const std::string s = e ? e : "";
    return s == "1" ? std::string("norm1,lowsel,cnorm") : s;
  }();
  return v;
}
inline bool enabled(const char* token) {
  const auto& v = list();
  if (v.empty() || v == "0") return false;
  return ("," + v + ",").find(std::string(",") + token + ",") != std::string::npos;
}
}  // namespace hc_kernels
#ifndef OWN_RT_HOST_ONLY
#include <sycl/sycl.hpp>
#include "stage2/packet194-expert-diet-engine/specialised.hpp"
namespace hc_kernels {
// specialised::upper(p, 80) by one 32-lane subgroup. upper()'s levels 1..16 are the adjacent subtrees of leaves 0..31
// (a), 32..63 (b) and 64..79 (c, levels 1..8); then stride 16: v64 = v64 + 0 (no right child); stride 32: v0 = v0 + v32,
// v64 = v64 + 0; stride 64: v0 = v0 + v64. Valid in lane 0.
inline float upper80(const sycl::sub_group& sg, const float* part, int lane) {
  float a = part[lane], b = part[32 + lane], c = lane < 16 ? part[64 + lane] : 0.f;
#pragma unroll
  for (int s = 1; s < 32; s *= 2) {
    const float ra = sycl::select_from_group(sg, a, (lane + s) % 32);
    const float rb = sycl::select_from_group(sg, b, (lane + s) % 32);
    const float rc = sycl::select_from_group(sg, c, (lane + s) % 32);
    if (lane % (2 * s) == 0) {
      a = a + ra;
      b = b + rb;
      if (s < 16) c = c + rc;
    }
  }
  float v64 = c + 0.f;
  float v0 = a + b;
  v64 = v64 + 0.f;
  v0 = v0 + v64;
  return v0;
}
// One HC norm row (row = stream h of 4, width 2560) or, with COMBINE, the CombineFast combine of that row first
// (gate = 2*sigmoid(inject[h]/4); streams[h][k] = streams[h][k] + branch[k]*gate, written back) and then the norm of the
// combined values. Guards as the separate kernels: inactive or error -> nothing written; the combine has no position
// check; the norm's position check (fail by item 0 of row 0) follows the combine's write.
struct NormArgs {
  float* x;              // streams (read; written back when COMBINE)
  const float* branch;   // COMBINE: the branch row (2560)
  const float* inject;   // COMBINE: the 4 inject values
  const float* gain;     // F32 gain (4 x 2560)
  float* y;              // norm output (4 x 2560)
  float* scratch;        // specialised scratch: partials row-major [4][80]
  int32_t* error;
  const int32_t* position;
  const int32_t* active;
  int capacity, tokens, flags;  // flags bit 0: unit offset
};
constexpr unsigned NORM_WGS = 640;  // 20 subgroups x 4 chunks of 32 per stream row
template <bool COMBINE, unsigned WGS = NORM_WGS>
inline void norm_row(const NormArgs a, sycl::nd_item<1> it, float* part /* >= 81 floats of local memory */) {
  constexpr int W = 2560, C = 80, HEADS = 4, NSG = WGS / 32;
  static_assert(WGS % 32 == 0 && C % NSG == 0, "chunks split evenly over the subgroups");
  constexpr int CPS = C / NSG;
  auto g = it.get_group();
  auto sg = it.get_sub_group();
  const int lane = int(sg.get_local_linear_id()), sgi = int(sg.get_group_linear_id());
  const int row = int(g.get_group_linear_id());
  using ref = sycl::atomic_ref<int32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                               sycl::access::address_space::global_space>;
  float xs[CPS], gs[CPS], bs[CPS];
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int k = (sgi + j * NSG) * 32 + lane;
    xs[j] = a.x[row * W + k];
    gs[j] = a.gain[(row % HEADS) * W + k];
    if constexpr (COMBINE) bs[j] = a.branch[k];
  }
  float inj = 0.f;
  if constexpr (COMBINE) inj = a.inject[row];
  const int act0 = lane == 0 ? a.active[0] : 0, err0 = lane == 0 ? ref(a.error[0]).load() : 0,
            pos0 = lane == 0 ? a.position[0] : 0;
  const int act = sycl::group_broadcast(sg, act0, 0), err = sycl::group_broadcast(sg, err0, 0),
            pos = sycl::group_broadcast(sg, pos0, 0);
  if (!act || err) return;
  if constexpr (COMBINE) {
    const float gate = 2.f * ng::sigmoid(inj / 4.f);
#pragma unroll
    for (int j = 0; j < CPS; ++j) {
      const int k = (sgi + j * NSG) * 32 + lane;
      xs[j] = xs[j] + bs[j] * gate;
      a.x[row * W + k] = xs[j];
    }
  }
  if (pos < 0 || pos > a.capacity - a.tokens) {
    if (row == 0 && it.get_local_linear_id() == 0) ref(a.error[0]).store(1);
    return;
  }
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int c = sgi + j * NSG;
    float v = xs[j] * xs[j];
#pragma unroll
    for (int s = 1; s < 32; s *= 2) {
      const float rhs = sycl::select_from_group(sg, v, (lane + s) % 32);
      if (lane % (2 * s) == 0) v = v + rhs;
    }
    if (lane == 0) {
      part[c] = v;
      a.scratch[row * C + c] = v;
    }
  }
  sycl::group_barrier(g);
  if (sgi == 0) {
    const float total = upper80(sg, part, lane);
    if (lane == 0) part[C] = detmath::rsqrt(total / float(W) + 1e-6f);
  }
  sycl::group_barrier(g);
  const float inv = part[C];
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int k = (sgi + j * NSG) * 32 + lane;
    a.y[row * W + k] = (xs[j] * inv) * (gs[j] + float(a.flags & 1));
  }
}
}  // namespace hc_kernels
#endif
