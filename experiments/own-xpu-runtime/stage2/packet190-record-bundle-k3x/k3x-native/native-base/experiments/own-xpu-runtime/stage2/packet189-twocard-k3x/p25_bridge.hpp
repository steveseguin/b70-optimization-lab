#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p25_bridge.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/build/checked/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/performance.hpp"
namespace packet26::p25bridge {
integrated::Launch submit(ownrt::Device&,const std::vector<integrated::Matrix>&,const std::string&,bool,unsigned,ownrt::Allocation prepared_fp32=0);
std::vector<std::string> alternatives(iq3::Type);
integrated::Launch prepare_input(ownrt::Device&,ownrt::Allocation,ownrt::Allocation,size_t);
}
