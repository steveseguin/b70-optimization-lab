#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/small_gemv.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/performance.hpp"
#include <string_view>
namespace packet27::small {
// These names identify compile-time tuples, never device-side descriptors.
struct Shape { iq3::Type type; unsigned rows,columns,variant; };
std::vector<Shape> shapes(std::string_view name);
std::vector<std::string> names();
void validate(ownrt::Device&,std::string_view,std::span<const integrated::Matrix>,std::span<const unsigned>);
integrated::Launch submit(ownrt::Device&,std::string_view,std::span<const integrated::Matrix>,std::span<const unsigned>);
}
