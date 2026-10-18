#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/native.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/build/checked/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/build/checked/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/owner.hpp"
namespace ng {
// All allocations prebound; one event dependency chain, no wait/readback here.
ownrt::Event submit(ownrt::Device&,Shape,std::span<const ownrt::Allocation>,std::span<const ownrt::Event>);
}
