#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/kernel_guard.hpp"
#pragma once
// Packet183 S1 submissions. Each mirrors one production submission exactly,
// except that its Q6_K lanes read the retained metadata scales (s1_lanes.hpp).
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/build/checked/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/p33_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/build/checked/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/p49c_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/build/checked/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/p49d_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/build/checked/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/s1_lanes.hpp"
#include <span>
#include <string_view>
#include <vector>
namespace p183 {
// p33::submit(..., "p33.dense.segment", shared, variant) for expanded Q6_K.
integrated::Launch segment(ownrt::Device&,const std::vector<integrated::Matrix>&,bool shared,unsigned variant);
// p49c::dense_submit(..., Kind::attention_combine, ...) for Q6_K K6144.
integrated::Launch attention(ownrt::Device&,const integrated::Matrix&,const p39::Bindings&);
// p49d::small(..., "small.ffn.q6", ...): F32 router/shared router unchanged,
// Q6_K shared gate/up on the metadata scales.
integrated::Launch small(ownrt::Device&,std::string_view,std::span<const integrated::Matrix>,std::span<const unsigned>);
} // namespace p183
