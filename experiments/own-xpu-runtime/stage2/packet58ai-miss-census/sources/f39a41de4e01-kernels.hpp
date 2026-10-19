#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/d72f03a1ca06-kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet7-kopt2/kernels.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/995db44ab772-kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/fa92d08429e0-reference.hpp"
namespace iq3::kopt2 {
struct Matrix : kopt::Matrix {
  uint32_t experts=1,count=1,span=0;
  ownrt::Allocation routes=0,status=0,workspace=0;
};
// Both passes are owned events. Timing MUST include first through last, with gap.
struct Launch {ownrt::Event first,last;unsigned passes;};
Launch multiply(ownrt::Device&,const std::vector<Matrix>&,Variant);
size_t workspace_bytes(size_t rows,unsigned count,Variant);
ownrt::Event streaming_read(ownrt::Device&,ownrt::Allocation,ownrt::Allocation,size_t);
ownrt::Event device_memcpy(ownrt::Device&,ownrt::Allocation,ownrt::Allocation,size_t);
std::string device_properties();
}
