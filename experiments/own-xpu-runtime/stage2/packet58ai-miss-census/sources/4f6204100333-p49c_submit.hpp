#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/d72f03a1ca06-kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p49c_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/0a316979ee56-p39_submit.hpp"
namespace p49c {
integrated::Launch dense_submit(ownrt::Device&,const integrated::Matrix&,p39::Kind,const p39::Bindings&);
integrated::Launch route(ownrt::Device&,const integrated::Spec&,std::span<const ownrt::Allocation>);
}
