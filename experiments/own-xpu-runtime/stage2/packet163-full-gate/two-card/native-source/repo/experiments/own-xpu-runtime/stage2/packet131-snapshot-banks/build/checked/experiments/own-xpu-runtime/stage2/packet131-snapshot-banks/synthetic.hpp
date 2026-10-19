#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet163-full-gate/two-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet163-full-gate/two-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/synthetic.hpp"
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
