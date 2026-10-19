#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/d72f03a1ca06-kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet8-kopt3/kernels.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/f39a41de4e01-kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/843635f24226-reference.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/b807a80bf315-dispatch.hpp"
namespace iq3::kopt3 {
using Matrix=kopt2::Matrix;
// Both passes are owned events. Timing MUST include first through last, with gap.
struct Launch {ownrt::Event first,last;unsigned passes;};
Launch multiply(ownrt::Device&,const std::vector<Matrix>&,Variant);
size_t workspace_bytes(size_t rows,unsigned count,Variant);
Launch expert_gate_up(ownrt::Device&,const Matrix&,const Matrix&,Variant);
Launch expert_down(ownrt::Device&,const Matrix&,Variant);
Launch multiply_dispatched(ownrt::Device&,const Matrix&);
std::string device_properties();
}
