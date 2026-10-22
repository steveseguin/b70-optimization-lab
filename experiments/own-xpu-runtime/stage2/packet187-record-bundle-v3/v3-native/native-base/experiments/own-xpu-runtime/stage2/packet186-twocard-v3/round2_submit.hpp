#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/round2_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/build/checked/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/round2.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/build/checked/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/performance.hpp"
namespace round2 {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
integrated::Launch submit_simple(ownrt::Device&,const integrated::Spec&,std::span<const ownrt::Allocation>,std::span<const ownrt::Event> = {});
}
