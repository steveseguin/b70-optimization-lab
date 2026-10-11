#pragma once
#include <string>
// Exact synthetic weight helper from packet3/kernels/mock.hpp lines 51-57.
namespace flash::mock {
inline float weight(const std::string &n, int r, int k, int expert = 0) {
  int salt = 0;
  for (unsigned char c : n) salt += c;
  return float((k * 3 + (r % 4) * 5 + salt + expert * 7) % 17 - 8) / 512.f;
}
}
