#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49_qsa_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/build/checked/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/round2_submit.hpp"
namespace p49 {
inline size_t scratch_bytes(ng::Shape s){return 16+size_t(s.tokens)*24*((ng::launch_slots(s)+31)/32)*258*4;}
integrated::Launch attention(ownrt::Device&,ng::Shape,std::span<const ownrt::Allocation>,ownrt::Allocation,std::span<const ownrt::Event> = {});
}
