#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p56_config.hpp"
#pragma once
// Generated from the independent, preregistered calibration; no runtime knob.
namespace p56 {
inline constexpr unsigned prefix_rows = 91392;
inline constexpr unsigned full_rows = 248320;
inline constexpr unsigned row_alignment = 256;
inline constexpr char calibration_sha256[] = "aa841860347076a8c0887303ea6fa428fc3b7c54af3218477ad5abb2d6abd273";
static_assert(prefix_rows > 0 && prefix_rows <= full_rows && prefix_rows % row_alignment == 0);
}
