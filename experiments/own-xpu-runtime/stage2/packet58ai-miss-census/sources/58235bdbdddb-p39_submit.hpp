#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/3a8ce69382d2-kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p39_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/6158314596b5-p39_fused.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/d3d77f67f433-submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/1721a20dc076-runtime_kernels.hpp"
namespace p39 {
constexpr int plan_tag=3900;
struct Bindings {ownrt::Allocation other=0,out=0,streams=0,inject=0,mixture=0,shared_gate=0,one=0,error=0,active=0,position=0;unsigned capacity=0;bool indirect=false;};
integrated::Launch submit(ownrt::Device&,const std::vector<integrated::Matrix>&,Kind,const Bindings&);
}
