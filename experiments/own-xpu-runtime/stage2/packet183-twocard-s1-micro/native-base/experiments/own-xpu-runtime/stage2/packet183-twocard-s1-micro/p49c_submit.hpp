#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49c_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/build/checked/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/p39_submit.hpp"
namespace p49c {
integrated::Launch dense_submit(ownrt::Device&,const integrated::Matrix&,p39::Kind,const p39::Bindings&);
integrated::Launch route(ownrt::Device&,const integrated::Spec&,std::span<const ownrt::Allocation>);
}
