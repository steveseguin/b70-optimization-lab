#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/prototype/snapshot/rope.hpp"
#pragma once
#include <bit>
#include <cstdint>
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/build/checked/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/build/fusion-rope.hpp"
namespace rope_constants {
inline float cos(int pos,int j){return std::bit_cast<float>(uint32_t(table[(pos*32+j)*2])<<16);}
inline float sin(int pos,int j){return std::bit_cast<float>(uint32_t(table[(pos*32+j)*2+1])<<16);}
}
