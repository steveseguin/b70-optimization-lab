#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p39_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p39_fused.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p28/submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/build/checked/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/runtime_kernels.hpp"
namespace p39 {
constexpr int plan_tag=3900;
struct Bindings {ownrt::Allocation other=0,out=0,streams=0,inject=0,mixture=0,shared_gate=0,one=0,error=0,active=0,position=0;unsigned capacity=0;};
integrated::Launch submit(ownrt::Device&,const std::vector<integrated::Matrix>&,Kind,const Bindings&);
}
