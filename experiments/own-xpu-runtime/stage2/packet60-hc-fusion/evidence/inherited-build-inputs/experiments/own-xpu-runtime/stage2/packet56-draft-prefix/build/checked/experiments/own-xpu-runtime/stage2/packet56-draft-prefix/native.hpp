#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/native.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/build/checked/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/build/checked/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/owner.hpp"
namespace ng {
// All allocations prebound; one event dependency chain, no wait/readback here.
ownrt::Event submit(ownrt::Device&,Shape,std::span<const ownrt::Allocation>,std::span<const ownrt::Event>);
}
