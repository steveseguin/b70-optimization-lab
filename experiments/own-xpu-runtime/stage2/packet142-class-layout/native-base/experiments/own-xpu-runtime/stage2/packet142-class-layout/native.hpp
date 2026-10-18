#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/native.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/owner.hpp"
namespace ng {
// All allocations prebound; one event dependency chain, no wait/readback here.
ownrt::Event submit(ownrt::Device&,Shape,std::span<const ownrt::Allocation>,std::span<const ownrt::Event>);
}
