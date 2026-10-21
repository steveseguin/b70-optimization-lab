#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/small_gemv.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/build/checked/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/performance.hpp"
#include <string_view>
namespace packet27::small {
// These names identify compile-time tuples, never device-side descriptors.
struct Shape { iq3::Type type; unsigned rows,columns,variant; };
std::vector<Shape> shapes(std::string_view name);
std::vector<std::string> names();
void validate(ownrt::Device&,std::string_view,std::span<const integrated::Matrix>,std::span<const unsigned>);
integrated::Launch submit(ownrt::Device&,std::string_view,std::span<const integrated::Matrix>,std::span<const unsigned>);
}
