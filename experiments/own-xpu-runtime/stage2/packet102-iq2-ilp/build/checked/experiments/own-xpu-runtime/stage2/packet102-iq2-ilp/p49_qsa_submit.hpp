#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/p49_qsa_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/build/checked/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/round2_submit.hpp"
namespace p49 {
inline size_t scratch_bytes(ng::Shape s){return 16+size_t(s.tokens)*24*((ng::launch_slots(s)+31)/32)*258*4;}
integrated::Launch attention(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
}
