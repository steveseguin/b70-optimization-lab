#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/specialised_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/build/checked/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/specialised.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/build/checked/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/performance.hpp"
namespace specialised {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
}
