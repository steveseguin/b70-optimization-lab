#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/specialised_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/build/checked/experiments/own-xpu-runtime/stage2/packet122-draft-budget/specialised.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/build/checked/experiments/own-xpu-runtime/stage2/packet122-draft-budget/performance.hpp"
namespace specialised {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
}
