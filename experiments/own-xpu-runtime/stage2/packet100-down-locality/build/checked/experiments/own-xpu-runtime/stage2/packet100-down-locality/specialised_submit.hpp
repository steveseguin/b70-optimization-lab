#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality/specialised_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality/build/checked/experiments/own-xpu-runtime/stage2/packet100-down-locality/specialised.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality/build/checked/experiments/own-xpu-runtime/stage2/packet100-down-locality/performance.hpp"
namespace specialised {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
}
