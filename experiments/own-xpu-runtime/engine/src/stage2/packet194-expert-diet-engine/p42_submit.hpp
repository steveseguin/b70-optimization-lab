#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet194-expert-diet-engine/adapter.hpp"
#include "stage2/packet194-expert-diet-engine/kernels.hpp"
namespace p42 {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,int,std::span<const ownrt::Event> = {});
}
