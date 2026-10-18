#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet97-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet97-record-bundle/p49_qsa_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet98c-v5-native/sources/experiments/own-xpu-runtime/stage2/packet97-record-bundle/round2_submit.hpp"
namespace p49 {
inline size_t scratch_bytes(ng::Shape s){return 16+size_t(s.tokens)*24*((ng::launch_slots(s)+31)/32)*258*4;}
integrated::Launch attention(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
}
