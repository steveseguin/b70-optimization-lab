#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/round2_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/round2.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/performance.hpp"
namespace round2 {
integrated::Launch submit(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
integrated::Launch submit_simple(ownrt::Device&,const integrated::Spec&,std::span<const ownrt::Allocation>,std::span<const ownrt::Event> = {});
}
