#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet97-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet97-record-bundle/specialised_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet98c-v5-native/sources/experiments/own-xpu-runtime/stage2/packet97-record-bundle/specialised.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet98c-v5-native/sources/experiments/own-xpu-runtime/stage2/packet97-record-bundle/performance.hpp"
namespace specialised {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
}
