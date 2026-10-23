#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/native.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/build/checked/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/build/checked/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/owner.hpp"
namespace ng {
// All allocations prebound; one event dependency chain, no wait/readback here.
ownrt::Event submit(ownrt::Device&,Shape,std::span<const ownrt::Allocation>,std::span<const ownrt::Event>);
}
