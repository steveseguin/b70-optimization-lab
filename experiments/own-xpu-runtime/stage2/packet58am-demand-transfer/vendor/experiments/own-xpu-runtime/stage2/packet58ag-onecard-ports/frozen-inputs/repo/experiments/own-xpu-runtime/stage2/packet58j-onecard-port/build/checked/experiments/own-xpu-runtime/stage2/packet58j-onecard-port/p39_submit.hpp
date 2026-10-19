#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p39_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p39_fused.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p28/submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/runtime_kernels.hpp"
namespace p39 {
constexpr int plan_tag=3900;
struct Bindings {ownrt::Allocation other=0,out=0,streams=0,inject=0,mixture=0,shared_gate=0,one=0,error=0,active=0,position=0;unsigned capacity=0;bool indirect=false;};
integrated::Launch submit(ownrt::Device&,const std::vector<integrated::Matrix>&,Kind,const Bindings&);
}
