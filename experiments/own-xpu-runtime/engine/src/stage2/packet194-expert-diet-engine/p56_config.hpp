#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
// Generated from the independent, preregistered calibration; no runtime knob.
namespace p56 {
inline constexpr unsigned prefix_rows = 91392;
inline constexpr unsigned full_rows = 248320;
inline constexpr unsigned row_alignment = 256;
inline constexpr char calibration_sha256[] = "aa841860347076a8c0887303ea6fa428fc3b7c54af3218477ad5abb2d6abd273";
static_assert(prefix_rows > 0 && prefix_rows <= full_rows && prefix_rows % row_alignment == 0);
}
