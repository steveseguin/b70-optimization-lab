#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet194-expert-diet-engine/kernels.hpp"
#include "stage2/packet194-expert-diet-engine/owner.hpp"
namespace ng {
// All allocations prebound; one event dependency chain, no wait/readback here.
ownrt::Event submit(ownrt::Device&,Shape,std::span<const ownrt::Allocation>,std::span<const ownrt::Event>);
}
