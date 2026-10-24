#pragma once
#include <stdexcept>
namespace recurrent_f32 {
inline constexpr int flag = 16;
// Dtype admission precedes every native submission. Legacy BF16 remains explicit.
template<class Scalar>
int admit(Scalar input, Scalar output, Scalar bf16, Scalar f32, int implementation) {
  if (input != output || (input != bf16 && input != f32))
    throw std::invalid_argument("recurrent input/output storage mismatch");
  if (input == f32 && implementation != 0)
    throw std::invalid_argument("F32 recurrent state requires the corrected generic kernel");
  return input == f32 ? flag : 0;
}
}
