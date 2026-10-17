#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/p49c_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/build/checked/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/p39_submit.hpp"
namespace p49c {
integrated::Launch dense_submit(ownrt::Device&,const integrated::Matrix&,p39::Kind,const p39::Bindings&);
integrated::Launch route(ownrt::Device&,const integrated::Spec&,std::span<const ownrt::Allocation>);
}
