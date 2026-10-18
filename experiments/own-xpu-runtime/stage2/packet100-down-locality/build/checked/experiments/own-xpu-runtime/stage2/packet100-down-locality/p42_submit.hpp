#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality/p42_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality/build/checked/experiments/own-xpu-runtime/stage2/packet100-down-locality/adapter.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet100-down-locality/build/checked/experiments/own-xpu-runtime/stage2/packet100-down-locality/kernels.hpp"
namespace p42 {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,int,std::span<const ownrt::Event> = {});
}
