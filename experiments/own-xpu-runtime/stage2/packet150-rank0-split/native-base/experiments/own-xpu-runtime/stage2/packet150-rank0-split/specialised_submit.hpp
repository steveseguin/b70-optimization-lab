#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/specialised_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/build/checked/experiments/own-xpu-runtime/stage2/packet150-rank0-split/specialised.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/build/checked/experiments/own-xpu-runtime/stage2/packet150-rank0-split/performance.hpp"
namespace specialised {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
}
