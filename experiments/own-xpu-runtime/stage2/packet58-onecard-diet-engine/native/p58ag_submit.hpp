#pragma once
#include "p49d_submit.hpp"
namespace p58ag {
integrated::Launch expert(ownrt::Device&,const std::vector<integrated::Matrix>&,const p39::Bindings&,ownrt::Allocation,bool cached=true,const std::string& gateup="production");
integrated::Launch expert_diet(ownrt::Device&,const std::vector<integrated::Matrix>&,const p39::Bindings&,ownrt::Allocation); // p58ag_diet_submit.cpp
bool other(ownrt::Device&); // no mutable global selection
}
