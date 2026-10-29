#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet194-expert-diet-engine/round2_submit.hpp"
namespace p49 {
inline size_t scratch_bytes(ng::Shape s){return 16+size_t(s.tokens)*ng::qsa_query_heads(s)*((ng::launch_slots(s)+31)/32)*258*4;}
integrated::Launch attention(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
}
