#pragma once
#include "performance.hpp"
namespace p116 {
integrated::Launch submit(ownrt::Device&,const integrated::Spec&,std::span<const ownrt::Allocation>,ownrt::Allocation,ownrt::Allocation,ownrt::Allocation,std::span<const ownrt::Event>);
}
