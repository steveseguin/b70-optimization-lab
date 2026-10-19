#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49b_expert_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/build/checked/experiments/own-xpu-runtime/stage2/packet150-rank0-split/p39_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet150-rank0-split/build/checked/experiments/own-xpu-runtime/stage2/packet150-rank0-split/p49b_gemv.hpp"
namespace p49b {
integrated::Launch submit(ownrt::Device&,const std::vector<integrated::Matrix>&,p39::Kind,const p39::Bindings&);
}
