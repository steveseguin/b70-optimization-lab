#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/d72f03a1ca06-kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/performance.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/e141427b38a8-runtime_kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/515f4be32379-kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/bfe14e3c625b-arithmetic.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/8672ac02ad2f-kernels.hpp"
namespace integrated {
using Matrix = iq3::kopt4::Matrix;
using Launch = iq3::kopt4::Launch;
// Every call is ordered by Device::compute's existing last-event dependency.
// No wrapper wait/marker is needed: the owner chains frozen and R5 kernels,
// copies, and non-GEMV submissions alike on each card. Caller keeps all arena
// allocations live until the chain terminates and profiling has been collected.
Launch dense(ownrt::Device&, const Matrix&, unsigned variant);
Launch experts(ownrt::Device&, const std::vector<Matrix>&, bool shared);
Launch mixture(ownrt::Device&, ownrt::Allocation down, ownrt::Allocation prob,
               ownrt::Allocation out, unsigned rows);
}
