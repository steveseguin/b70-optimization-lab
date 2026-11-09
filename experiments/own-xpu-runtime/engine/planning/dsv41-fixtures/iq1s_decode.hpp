// Independent IQ1_S block decoder (GGUF type 19, 50 bytes / 256 elems).
// Layout: fp16 d; qs[32] u8; qh[8] u16. Per 32-element group:
//   dl = d * (2*((qh>>12)&7)+1); delta = qh&0x8000 ? -0.125 : +0.125
//   sub-block l: 11-bit index qs[l] | ((qh>>(3*l))&7)<<8 into the
//   2048-entry int8x8 codebook; value = dl * (code[j] + delta).
#pragma once
#include <cstdint>
#include "iq2xxs_decode.hpp"  // fp16_to_fp32_bits
#include "iq1s_tables.h"

namespace dsv41 {

struct block_iq1_s {
    uint16_t d;
    uint8_t  qs[32];
    uint16_t qh[8];
};
static_assert(sizeof(block_iq1_s) == 50, "iq1_s block layout");

inline void dequantize_iq1_s(const block_iq1_s *x, float *out, long long nb) {
    using namespace dsv41ref;
    for (long long b = 0; b < nb; ++b) {
        const float d = fp16_to_fp32_bits(x[b].d);
        const uint8_t  *qs = x[b].qs;
        const uint16_t *qh = x[b].qh;
        for (int ib = 0; ib < 8; ++ib) {
            const float dl = d * (2 * ((qh[ib] >> 12) & 7) + 1);
            const float delta = qh[ib] & 0x8000 ? -IQ1S_DELTA : IQ1S_DELTA;
            for (int l = 0; l < 4; ++l) {
                const int8_t *code = (const int8_t *)&iq1s_grid[qs[l] | (((qh[ib] >> 3*l) & 7) << 8)];
                for (int j = 0; j < 8; ++j)
                    out[j] = dl * ((float)code[j] + delta);
                out += 8;
            }
            qs += 4;
        }
    }
}

} // namespace dsv41
