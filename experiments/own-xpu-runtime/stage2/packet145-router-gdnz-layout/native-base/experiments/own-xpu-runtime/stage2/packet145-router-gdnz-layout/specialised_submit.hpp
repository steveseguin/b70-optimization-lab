#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet145-router-gdnz-layout/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/specialised_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet145-router-gdnz-layout/build/checked/experiments/own-xpu-runtime/stage2/packet145-router-gdnz-layout/specialised.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet145-router-gdnz-layout/build/checked/experiments/own-xpu-runtime/stage2/packet145-router-gdnz-layout/performance.hpp"
namespace specialised {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
}
