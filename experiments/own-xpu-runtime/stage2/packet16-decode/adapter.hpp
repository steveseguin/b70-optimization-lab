#pragma once
#include "performance.hpp"
namespace packet16 {
// All scratch is owner-local, allocated once and retained until the chain drains.
// control: 12 bytes; score/probability: each 24*(budget+3)*sizeof(float).
integrated::Launch submit_parallel(ownrt::Device&, const integrated::Spec&,
 std::span<const ownrt::Allocation>, ownrt::Allocation control,
 ownrt::Allocation score, ownrt::Allocation probability,
 std::span<const ownrt::Event> dependencies = {});
}
