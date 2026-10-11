#pragma once
#include "kernels.hpp"
#include "owner.hpp"
namespace ng {
// All allocations prebound; one event dependency chain, no wait/readback here.
ownrt::Event submit(ownrt::Device&,Shape,std::span<const ownrt::Allocation>,std::span<const ownrt::Event>);
ownrt::Event submit_reference(ownrt::Device&,Shape,int,std::span<const ownrt::Allocation>,std::span<const ownrt::Event>);
}
