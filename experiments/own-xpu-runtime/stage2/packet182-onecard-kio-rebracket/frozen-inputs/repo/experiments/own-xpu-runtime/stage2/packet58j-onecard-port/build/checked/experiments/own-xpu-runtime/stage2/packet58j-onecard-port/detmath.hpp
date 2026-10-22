#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet176-onecard-kernelio/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet176-onecard-kernelio/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/detmath.hpp"
#pragma once
// Single upstream-selected rsqrt switch: DETMATH_RSQRT_MODE in packet17.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet176-onecard-kernelio/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet17-detmath/detmath.hpp"

namespace detmath {
// HC is a unary operation. Quiet a NaN while retaining its input sign/payload
// before division or multiplication can select a different NaN operand. The
// finite equation and rounding order remain the arithmetic-v2 equation.
inline float silu_div4(float x) {
 const auto u=bits(x);
 if((u&0x7fffffffu)>0x7f800000u)return value(u|0x00400000u);
 const float scaled=x/4.f;
 return scaled*(1.f/(1.f+exp(-scaled)));
}
}
