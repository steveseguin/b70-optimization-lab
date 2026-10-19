#pragma once
#include "demand.hpp"
#include "../build/native/p58ag_submit.hpp"
namespace p58am {
integrated::Launch partition(ownrt::Device&,const std::vector<integrated::Matrix>&,const p39::Bindings&,ownrt::Allocation,ownrt::Allocation,ownrt::Allocation,unsigned,bool);
integrated::Launch descriptor(ownrt::Device&,ownrt::Allocation,std::array<ownrt::Allocation,3>,ownrt::Allocation,uint64_t,uint64_t);
}
