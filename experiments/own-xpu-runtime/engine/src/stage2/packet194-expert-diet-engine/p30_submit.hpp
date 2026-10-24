#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet194-expert-diet-engine/round2_submit.hpp"
#include "stage2/packet194-expert-diet-engine/small_gemv.hpp"
namespace p30integrated {
integrated::Launch attention(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,unsigned,std::span<const ownrt::Event> = {});
integrated::Launch small(ownrt::Device&,std::string_view,std::span<const integrated::Matrix>,std::span<const unsigned>);
}
