// Independent IQ2_XXS block decoder for the Own Xe dsv41 port.
// Format contract (derived from the GGUF type-16 layout, 66 bytes / 256 elems):
//   fp16 scale d; then per 32-element group g (8 groups):
//     lo = u32 from qs[4g..4g+1], hi = u32 from qs[4g+2..4g+3]
//     sub-scale s = hi >> 28;  group scale = d * (0.5 + s) * 0.25
//     sub-block l (0..3): grid index = byte l of lo (8-bit codebook),
//     sign index = bits [7l, 7l+7) of hi; 8 outputs per sub-block.
// Written from the format semantics; tables are normative fixture data
// (see iq2xxs_tables.h). Verified bit-exact against the reference decoder
// by test_iq2xxs.cpp.
#pragma once
#include <cstdint>
#include <cstring>
#include "iq2xxs_tables.h"

namespace dsv41 {

inline float fp16_to_fp32_bits(uint16_t h) {
    uint32_t sign = (h & 0x8000u) << 16;
    uint32_t exp  = (h >> 10) & 0x1f;
    uint32_t mant = h & 0x03ff;
    uint32_t out;
    if (exp == 0) {
        if (mant == 0) { out = sign; }
        else {
            int e = -1;
            do { mant <<= 1; ++e; } while (!(mant & 0x0400));
            mant &= 0x03ff;
            out = sign | ((uint32_t)(127 - 15 - e) << 23) | (mant << 13);
        }
    } else if (exp == 31) {
        out = sign | 0x7f800000u | (mant << 13);
    } else {
        out = sign | ((exp + 112) << 23) | (mant << 13);
    }
    float f;
    std::memcpy(&f, &out, 4);
    return f;
}

struct block_iq2_xxs {           // 66 bytes, packed
    uint16_t d;
    uint16_t qs[32];
};
static_assert(sizeof(block_iq2_xxs) == 66, "iq2_xxs block layout");

// Decodes `nb` blocks (256*nb values) into out.
inline void dequantize_iq2_xxs(const block_iq2_xxs *x, float *out, long long nb) {
    using namespace dsv41ref;
    for (long long b = 0; b < nb; ++b) {
        const float d = fp16_to_fp32_bits(x[b].d);
        for (int g = 0; g < 8; ++g) {
            uint32_t lo = (uint32_t)x[b].qs[4*g] | ((uint32_t)x[b].qs[4*g+1] << 16);
            uint32_t hi = (uint32_t)x[b].qs[4*g+2] | ((uint32_t)x[b].qs[4*g+3] << 16);
            const float db = d * (0.5f + (float)(hi >> 28)) * 0.25f;
            for (int l = 0; l < 4; ++l) {
                const uint8_t *code = (const uint8_t *)&iq2xxs_grid[(lo >> (8*l)) & 0xff];
                const uint8_t signs = ksigns_iq2xs[(hi >> (7*l)) & 0x7f];
                for (int j = 0; j < 8; ++j)
                    *out++ = db * (float)code[j] * (signs & kmask_iq2xs[j] ? -1.f : 1.f);
            }
        }
    }
}

} // namespace dsv41
