#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/d72f03a1ca06-kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet10-kopt5/kernels.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/45d72eaa0974-expanded.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/515f4be32379-kernels.hpp"
namespace iq3::expanded {
ownrt::Event dequant(ownrt::Device&,Type,ownrt::Allocation,ownrt::Allocation,unsigned rows,unsigned k);
// Dense only: experts retain the qualified packed fused packet9 path.
kopt3::Launch gemv(ownrt::Device&,const kopt3::Matrix&,unsigned split);
inline unsigned dispatch_split(Type t,unsigned rows,unsigned k) {
 unsigned v=kopt4::dispatch_variant(unsigned(t),rows,k,1);
 return v==1 || v==4?4:1;
}
}
