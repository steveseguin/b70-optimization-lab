#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p49d_submit.hpp"
namespace p58ag {
integrated::Launch expert(ownrt::Device&,const std::vector<integrated::Matrix>&,const p39::Bindings&,ownrt::Allocation,bool cached=true,const std::string& gateup="production");
integrated::Launch expert_diet(ownrt::Device&,const std::vector<integrated::Matrix>&,const p39::Bindings&,ownrt::Allocation); // p58ag_diet_submit.cpp
bool other(ownrt::Device&); // no mutable global selection
}
