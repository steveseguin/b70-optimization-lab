#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p42_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/build/checked/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/adapter.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/build/checked/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/kernels.hpp"
namespace p42 {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,int,std::span<const ownrt::Event> = {});
}
