#pragma once
#include "../packet4/kernels.hpp"
#include "../packet9-kopt4/kernels.hpp"
#include "arithmetic.hpp"
#include "../packet10-kopt5/kernels.hpp"
namespace integrated {
using Matrix = iq3::kopt4::Matrix;
using Launch = iq3::kopt4::Launch;
// Every call is ordered by Device::compute's existing last-event dependency.
// No wrapper wait/marker is needed: the owner chains frozen and R5 kernels,
// copies, and non-GEMV submissions alike on each card. Caller keeps all arena
// allocations live until the chain terminates and profiling has been collected.
Launch dense(ownrt::Device&, const Matrix&, unsigned variant);
Launch experts(ownrt::Device&, const std::vector<Matrix>&, bool shared);
Launch mixture(ownrt::Device&, ownrt::Allocation down, ownrt::Allocation prob,
               ownrt::Allocation out, unsigned rows);
}
