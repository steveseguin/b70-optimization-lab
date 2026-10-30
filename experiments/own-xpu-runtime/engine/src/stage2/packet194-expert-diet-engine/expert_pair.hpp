#pragma once
// OWNRT_TP_EXPERT_PAIR=1 (2026-10-30, research/tp/fixed-cost-2026-10-30; default off, decode only): a layer's routed
// expert gate and up GEMVs and their SiLU product run as ONE launch instead of three (generic_engine.hpp pairing,
// kernels in packet6-kopt/kernels.cpp MultiplyBlockRowsPair and dn2_kernels.hpp xxs_pair_packed).
// - Each gate row and each up row is computed exactly as by its own launch (same kernel body, lane mapping, decode,
//   product-then-add order and adjacent-pair tree); a subgroup now holds rows of both matrices, so a four-card compact
//   launch of 5 slots runs as many subgroups as a 10-slot launch. Both outputs and both status words are written as
//   before.
// - The product act[i] = ng::silu(gate[i]) * up[i] is the activation kernel's own expression on the same two stored
//   values (ng "ew" path), stored only under that kernel's guard: no store while the half is inactive or the sticky
//   error is set; a position outside [0, limit] sets the error (first item of the launch) and stores nothing.
#include <sycl/sycl.hpp>
#include <cstdint>
#include <cstdlib>
#include "stage2/packet194-expert-diet-engine/kernels.hpp"
namespace expert_pair {
inline bool enabled(){static const bool on=[]{const char* e=std::getenv("OWNRT_TP_EXPERT_PAIR");return e&&e[0]=='1';}();return on;}
// The activation's bindings (ng slots 2, 18, 15, 17) and its position bound (position_limit(s) - tokens).
struct Act {float* y=nullptr;const int32_t* active=nullptr;int32_t* error=nullptr;const int32_t* position=nullptr;int limit=0;};
inline float value(float gate,float up){return ng::silu(gate)*up;}
// The ew activation guard, evaluated by every lane of the subgroup (uniform result). first_item: the launch's item 0.
template<class SG> inline bool guard(const Act& a,const SG& sg,bool first_item){
  using ref=sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>;
  const int blocked=sycl::group_broadcast(sg,sg.get_local_linear_id()==0?int(!a.active[0]||ref(*a.error).load()):0,0);
  if(blocked)return false;
  const int pos=a.position[0];
  if(pos<0||pos>a.limit){if(first_item)ref(*a.error).store(1);return false;}
  return true;
}
}
