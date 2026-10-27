#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include <bit>
#include <cstddef>
#include <cstdint>
namespace rope_constants {
inline constexpr int positions=262144;
inline constexpr std::size_t bytes=positions*128;
inline constexpr char sha256[]="e53a22a0792ef60aa6c5ebb7db7f30749b577f6cc355b661dd4ea31da5ee63bc";
inline float cos(const uint16_t* table,int pos,int j){return std::bit_cast<float>(uint32_t(table[(pos*32+j)*2])<<16);}
inline float sin(const uint16_t* table,int pos,int j){return std::bit_cast<float>(uint32_t(table[(pos*32+j)*2+1])<<16);}
// Exact-mode F32 table: same authority (glibc powf/cosf/sinf, f32(pos*powf(1e7f,-2j/64))) without BF16 rounding.
inline float cos(const float* table,int pos,int j){return table[(pos*32+j)*2];}
inline float sin(const float* table,int pos,int j){return table[(pos*32+j)*2+1];}
}
