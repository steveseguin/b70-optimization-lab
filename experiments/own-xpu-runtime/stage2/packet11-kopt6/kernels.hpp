#pragma once
#include "../packet8-kopt3/kernels.hpp"
#include "reference.hpp"
#include "dispatch.hpp"
namespace iq3::kopt6 {
using Matrix=kopt3::Matrix;
using Launch=kopt3::Launch;
// One launch, shared single activation vector; route ids stay on device.
Launch expert_gate_up(ownrt::Device&,const Matrix&,const Matrix&,unsigned split=1,Variant variant=Variant::baseline);
// One launch, per-slot activations. Also supports small-row K=2560 tests.
Launch expert_down(ownrt::Device&,const Matrix&,unsigned split=1,Variant variant=Variant::baseline);
Launch epilogue(ownrt::Device&,ownrt::Allocation down,ownrt::Allocation weights,
                ownrt::Allocation output,unsigned rows,ownrt::Allocation fp32=0);
Launch multiply_dispatched(ownrt::Device&,const Matrix&);
}
