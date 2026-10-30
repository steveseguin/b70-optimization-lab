#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet194-expert-diet-engine/specialised.hpp"
#include "stage2/packet194-expert-diet-engine/performance.hpp"
namespace specialised {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
// OWNRT_HC_KERNELS cnorm (hc_kernels.hpp): the CombineFast combine of streams (branch, inject) then the HC norm `s` of the
// same streams, one launch. `a` are the norm's 19 bindings as for submit (0 streams, 1 gain, 2 output, 15 error,
// 17 position, 18 active); `scratch` the norm's scratch.
integrated::Launch submit_combine_norm(ownrt::Device&,ng::Shape s,std::span<const ownrt::Allocation> a,ownrt::Allocation scratch,
                                       ownrt::Allocation branch,ownrt::Allocation inject,std::span<const ownrt::Event> = {});
// True when the HC norm one-launch kernels (norm1 / cnorm) admit this norm shape: 4 x 2560 rows, F32 gain, F32
// activations, one token row.
bool hc_norm_admitted(ng::Shape s);
}
