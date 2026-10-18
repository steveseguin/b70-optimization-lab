#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet103-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet103-record-bundle/p25_bridge.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet114-draft-prefix/sources/experiments/own-xpu-runtime/stage2/packet103-record-bundle/performance.hpp"
namespace packet26::p25bridge {
integrated::Launch submit(ownrt::Device&,const std::vector<integrated::Matrix>&,const std::string&,bool,unsigned,ownrt::Allocation prepared_fp32=0);
std::vector<std::string> alternatives(iq3::Type);
integrated::Launch prepare_input(ownrt::Device&,ownrt::Allocation,ownrt::Allocation,size_t);
}
