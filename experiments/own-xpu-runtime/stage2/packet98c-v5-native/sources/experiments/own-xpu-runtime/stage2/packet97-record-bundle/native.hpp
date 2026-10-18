#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet97-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet97-record-bundle/native.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet98c-v5-native/sources/experiments/own-xpu-runtime/stage2/packet97-record-bundle/kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet98c-v5-native/sources/experiments/own-xpu-runtime/stage2/packet97-record-bundle/owner.hpp"
namespace ng {
// All allocations prebound; one event dependency chain, no wait/readback here.
ownrt::Event submit(ownrt::Device&,Shape,std::span<const ownrt::Allocation>,std::span<const ownrt::Event>);
}
