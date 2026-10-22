#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/kernel_guard.hpp"
#pragma once
// Packet183 S1 submissions. Each mirrors one production submission exactly,
// except that its Q6_K lanes read the retained metadata scales (s1_lanes.hpp).
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/build/checked/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/p33_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/build/checked/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/p49c_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/build/checked/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/p49d_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/build/checked/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/s1_lanes.hpp"
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
