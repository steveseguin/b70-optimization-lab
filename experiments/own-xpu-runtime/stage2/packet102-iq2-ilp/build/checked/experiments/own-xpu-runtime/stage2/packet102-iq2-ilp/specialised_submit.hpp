#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/specialised_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/build/checked/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/specialised.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/build/checked/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/performance.hpp"
namespace specialised {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
}
