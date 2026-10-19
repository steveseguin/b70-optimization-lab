#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet163-full-gate/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet163-full-gate/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p49c_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet163-full-gate/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p39_submit.hpp"
namespace p49c {
integrated::Launch dense_submit(ownrt::Device&,const integrated::Matrix&,p39::Kind,const p39::Bindings&);
integrated::Launch route(ownrt::Device&,const integrated::Spec&,std::span<const ownrt::Allocation>);
}
