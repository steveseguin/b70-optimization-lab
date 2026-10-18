#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet97-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet97-record-bundle/p49c_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet98c-v5-native/sources/experiments/own-xpu-runtime/stage2/packet97-record-bundle/p39_submit.hpp"
namespace p49c {
integrated::Launch dense_submit(ownrt::Device&,const integrated::Matrix&,p39::Kind,const p39::Bindings&);
integrated::Launch route(ownrt::Device&,const integrated::Spec&,std::span<const ownrt::Allocation>);
}
