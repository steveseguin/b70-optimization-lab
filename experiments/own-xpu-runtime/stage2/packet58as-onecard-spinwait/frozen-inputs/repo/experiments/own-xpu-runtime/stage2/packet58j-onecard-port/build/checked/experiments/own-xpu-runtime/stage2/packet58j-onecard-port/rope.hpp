#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/rope.hpp"
#pragma once
#include <bit>
#include <cstddef>
#include <cstdint>
namespace rope_constants {
inline constexpr int positions=32768;
inline constexpr std::size_t bytes=positions*128;
inline constexpr char sha256[]="92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390";
inline float cos(const uint16_t* table,int pos,int j){return std::bit_cast<float>(uint32_t(table[(pos*32+j)*2])<<16);}
inline float sin(const uint16_t* table,int pos,int j){return std::bit_cast<float>(uint32_t(table[(pos*32+j)*2+1])<<16);}
}
