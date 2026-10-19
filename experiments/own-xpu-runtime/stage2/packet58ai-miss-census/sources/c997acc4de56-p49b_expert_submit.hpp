#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/d72f03a1ca06-kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p49b_expert_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/0a316979ee56-p39_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/21a81966f21c-p49b_gemv.hpp"
namespace p49b {
integrated::Launch submit(ownrt::Device&,const std::vector<integrated::Matrix>&,p39::Kind,const p39::Bindings&);
}
