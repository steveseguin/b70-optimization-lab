#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet9-kopt4/kernels.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet8-kopt3/kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet9-kopt4/reference.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet9-kopt4/dispatch.hpp"
namespace iq3::kopt4 {
using Matrix=kopt3::Matrix;
using Launch=kopt3::Launch;
// One launch, shared single activation vector; route ids stay on device.
Launch expert_gate_up(ownrt::Device&,const Matrix&,const Matrix&,unsigned split=4);
// One launch, per-slot activations. Also supports small-row K=2560 tests.
Launch expert_down(ownrt::Device&,const Matrix&,unsigned split=1);
Launch epilogue(ownrt::Device&,ownrt::Allocation down,ownrt::Allocation weights,
                ownrt::Allocation output,unsigned rows,ownrt::Allocation fp32=0);
Launch multiply_dispatched(ownrt::Device&,const Matrix&);
}
