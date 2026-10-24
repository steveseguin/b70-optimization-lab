#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet8-kopt3/kernels.hpp"
#include "stage2/packet9-kopt4/reference.hpp"
#include "stage2/packet9-kopt4/dispatch.hpp"
namespace iq3::kopt4 {
using Matrix=kopt3::Matrix;
using Launch=kopt3::Launch;
// One launch, shared single activation vector; route ids stay on device.
Launch expert_gate_up(ownrt::Device&,const Matrix&,const Matrix&,unsigned split=4);
// One launch, per-slot activations. Also supports small-row K=2560 tests.
Launch expert_down(ownrt::Device&,const Matrix&,unsigned split=1);
Launch epilogue(ownrt::Device&,ownrt::Allocation down,ownrt::Allocation weights,
                ownrt::Allocation output,unsigned rows,ownrt::Allocation fp32=0);
// Exact-mode F32 variant of epilogue (same slot order and arithmetic, no BF16 store).
Launch epilogue_f32(ownrt::Device&,ownrt::Allocation down,ownrt::Allocation weights,ownrt::Allocation output,unsigned rows);
Launch multiply_dispatched(ownrt::Device&,const Matrix&);
}
