#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/small_gemv.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/performance.hpp"
#include <string_view>
namespace packet27::small {
// These names identify compile-time tuples, never device-side descriptors.
struct Shape { iq3::Type type; unsigned rows,columns,variant; };
std::vector<Shape> shapes(std::string_view name);
std::vector<std::string> names();
void validate(ownrt::Device&,std::string_view,std::span<const integrated::Matrix>,std::span<const unsigned>);
integrated::Launch submit(ownrt::Device&,std::string_view,std::span<const integrated::Matrix>,std::span<const unsigned>);
}
