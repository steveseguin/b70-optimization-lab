#pragma once
#include "runtime_kernels.hpp"
#include "../packet9-kopt4/kernels.hpp"
#include "arithmetic.hpp"
namespace integrated {
using Matrix = iq3::kopt4::Matrix;
using Launch = iq3::kopt4::Launch;
Launch dense(ownrt::Device&, const Matrix&, unsigned variant);
Launch experts(ownrt::Device&, const std::vector<Matrix>&, bool shared);
Launch mixture(ownrt::Device&, ownrt::Allocation down, ownrt::Allocation prob,
               ownrt::Allocation out, unsigned rows);
}
