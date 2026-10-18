#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/round2_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/build/checked/experiments/own-xpu-runtime/stage2/packet122-draft-budget/round2.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/build/checked/experiments/own-xpu-runtime/stage2/packet122-draft-budget/performance.hpp"
namespace round2 {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
integrated::Launch submit_simple(ownrt::Device&,const integrated::Spec&,std::span<const ownrt::Allocation>,std::span<const ownrt::Event> = {});
}
