#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet194-expert-diet-engine/round2.hpp"
#include "stage2/packet194-expert-diet-engine/performance.hpp"
namespace round2 {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
integrated::Launch submit_simple(ownrt::Device&,const integrated::Spec&,std::span<const ownrt::Allocation>,std::span<const ownrt::Event> = {});
}
