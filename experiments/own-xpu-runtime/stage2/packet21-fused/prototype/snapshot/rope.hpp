#pragma once
#include <bit>
#include <cstdint>
#include "../../build/fusion-rope.hpp"
namespace rope_constants {
inline float cos(int pos,int j){return std::bit_cast<float>(uint32_t(table[(pos*32+j)*2])<<16);}
inline float sin(int pos,int j){return std::bit_cast<float>(uint32_t(table[(pos*32+j)*2+1])<<16);}
}
