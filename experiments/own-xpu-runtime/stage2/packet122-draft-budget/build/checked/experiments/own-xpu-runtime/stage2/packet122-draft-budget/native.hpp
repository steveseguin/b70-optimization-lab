#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/native.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/build/checked/experiments/own-xpu-runtime/stage2/packet122-draft-budget/kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/build/checked/experiments/own-xpu-runtime/stage2/packet122-draft-budget/owner.hpp"
namespace ng {
// All allocations prebound; one event dependency chain, no wait/readback here.
ownrt::Event submit(ownrt::Device&,Shape,std::span<const ownrt::Allocation>,std::span<const ownrt::Event>);
}
