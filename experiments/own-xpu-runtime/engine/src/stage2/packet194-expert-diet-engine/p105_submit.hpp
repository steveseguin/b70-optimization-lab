#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet194-expert-diet-engine/p105_common.hpp"
#include "stage2/packet194-expert-diet-engine/performance.hpp"
namespace p105 {
ownrt::Event pack(ownrt::Device&,ownrt::Allocation logits,ownrt::Allocation index,ownrt::Allocation error,ownrt::Allocation best,unsigned rows,unsigned offset);
}
