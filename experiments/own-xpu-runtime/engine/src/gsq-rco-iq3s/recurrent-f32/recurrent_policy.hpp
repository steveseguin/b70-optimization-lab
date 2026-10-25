#pragma once
#include <stdexcept>
namespace recurrent_f32 {
inline constexpr int flag = 16;
// Dtype admission precedes every native submission. Legacy BF16 remains explicit.
// The specialised kernels (implementation 1) read the state through the activation accessor, so they are admitted
// for F32 state only when activations are F32 too: then both reads are the same F32 load.
template<class Scalar>
int admit(Scalar input, Scalar output, Scalar bf16, Scalar f32, int implementation, bool f32_activations = false) {
  if (input != output || (input != bf16 && input != f32))
    throw std::invalid_argument("recurrent input/output storage mismatch");
  if (input == f32 && implementation != 0 && !(implementation == 1 && f32_activations))
    throw std::invalid_argument("F32 recurrent state requires the corrected generic kernel");
  return input == f32 ? flag : 0;
}
}
