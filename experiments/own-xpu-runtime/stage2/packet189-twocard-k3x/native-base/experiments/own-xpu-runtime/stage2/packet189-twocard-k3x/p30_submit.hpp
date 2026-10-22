#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p30_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/build/checked/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/round2_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/build/checked/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/small_gemv.hpp"
namespace p30integrated {
integrated::Launch attention(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,unsigned,std::span<const ownrt::Event> = {});
integrated::Launch small(ownrt::Device&,std::string_view,std::span<const integrated::Matrix>,std::span<const unsigned>);
}
