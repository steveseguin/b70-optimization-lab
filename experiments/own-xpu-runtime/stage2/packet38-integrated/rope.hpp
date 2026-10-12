#pragma once
#include <bit>
#include <cstddef>
#include <cstdint>
namespace rope_constants {
inline constexpr int positions=4096;
inline constexpr std::size_t bytes=positions*128;
inline constexpr char sha256[]="ccdfe87fa7360fc6b4aa7c999fa7b920f791f5635010cf303ae76f4d01dca058";
inline float cos(const uint16_t* table,int pos,int j){return std::bit_cast<float>(uint32_t(table[(pos*32+j)*2])<<16);}
inline float sin(const uint16_t* table,int pos,int j){return std::bit_cast<float>(uint32_t(table[(pos*32+j)*2+1])<<16);}
}
