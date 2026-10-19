#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p42_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/build/checked/experiments/own-xpu-runtime/stage2/packet150-rank0-split/adapter.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/build/checked/experiments/own-xpu-runtime/stage2/packet150-rank0-split/kernels.hpp"
namespace p42 {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,int,std::span<const ownrt::Event> = {});
}
