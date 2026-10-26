#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet6-kopt/kernels.hpp"
#include "stage2/packet7-kopt2/reference.hpp"
namespace iq3::kopt2 {
struct Matrix : kopt::Matrix {
  uint32_t experts=1,count=1,span=0;
  // Dense (unrouted) matrices only: number of independent token rows. x is [tokens][columns] and y is
  // [tokens][rows]; each row keeps the single-token arithmetic. Routed matrices express tokens through count.
  uint32_t tokens=1;
  ownrt::Allocation routes=0,status=0,workspace=0;
  // OWNRT_DENSE_RAW (lab 2026-10-26): w holds raw-size Q6_K/Q8_0 rows (dense_raw.hpp) instead of variant-6 expanded rows.
  bool raw=false;
};
// Both passes are owned events. Timing MUST include first through last, with gap.
struct Launch {ownrt::Event first,last;unsigned passes;};
Launch multiply(ownrt::Device&,const std::vector<Matrix>&,Variant);
size_t workspace_bytes(size_t rows,unsigned count,Variant);
ownrt::Event streaming_read(ownrt::Device&,ownrt::Allocation,ownrt::Allocation,size_t);
ownrt::Event device_memcpy(ownrt::Device&,ownrt::Allocation,ownrt::Allocation,size_t);
std::string device_properties();
}
