#pragma once
#include "performance.hpp"
namespace packet18 {
// All scratch is owner-local, allocated once and retained until the chain drains.
// control: reserved 12-byte compatibility slot; score/probability: 24*(budget+3)*4.
integrated::Launch submit_parallel(ownrt::Device&, const integrated::Spec&,
 std::span<const ownrt::Allocation>, ownrt::Allocation control,
 ownrt::Allocation score, ownrt::Allocation probability,
 std::span<const ownrt::Event> dependencies = {});
}

namespace packet18 {
integrated::Launch submit_chain(ownrt::Device&,const std::vector<integrated::Spec>&,const std::vector<std::vector<ownrt::Allocation>>&,ownrt::Allocation,ownrt::Allocation,ownrt::Allocation);
}

namespace packet18 { integrated::Launch submit_rank(ownrt::Device&,const integrated::Spec&,const std::vector<ownrt::Allocation>&); }
