#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet143-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/adapter.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet143-record-bundle/build/checked/experiments/own-xpu-runtime/stage2/packet143-record-bundle/performance.hpp"
namespace packet18 {
// All scratch is owner-local, allocated once and retained until the chain drains.
// control: reserved 12-byte compatibility slot; score/probability: 24*(budget+3)*4.
integrated::Launch submit_parallel(ownrt::Device&, const integrated::Spec&,
 std::span<const ownrt::Allocation>, ownrt::Allocation control,
 ownrt::Allocation score, ownrt::Allocation probability,
 std::span<const ownrt::Event> dependencies = {});
}
