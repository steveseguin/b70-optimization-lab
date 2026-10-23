#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/specialised_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/build/checked/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/specialised.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/build/checked/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/performance.hpp"
namespace specialised {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
}
