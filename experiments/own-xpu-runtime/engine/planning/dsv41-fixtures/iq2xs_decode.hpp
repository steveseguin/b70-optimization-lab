// Independent IQ2_XS block decoder (GGUF type 17, 74 bytes / 256 elems).
// Layout: fp16 d; qs[32] u16 (low 9 bits = 512-entry codebook index,
// high 7 bits = sign index); scales[8] bytes, two 4-bit sub-scales per
// 32-element group: db = d*(0.5+s)*0.25.
#pragma once
#include <cstdint>
#include "iq2xxs_decode.hpp"  // fp16_to_fp32_bits, ksigns/kmask via dsv41ref
#include "iq2xs_tables.h"

namespace dsv41 {

struct block_iq2_xs {
    uint16_t d;
    uint16_t qs[32];
    uint8_t  scales[8];
};
static_assert(sizeof(block_iq2_xs) == 74, "iq2_xs block layout");

inline void dequantize_iq2_xs(const block_iq2_xs *x, float *out, long long nb) {
    using namespace dsv41ref;
    for (long long b = 0; b < nb; ++b) {
        const float d = fp16_to_fp32_bits(x[b].d);
        for (int ib = 0; ib < 8; ++ib) {
            const uint16_t *aux = x[b].qs + 4*ib;
            const float db1 = d * (0.5f + (x[b].scales[ib] & 0xF)) * 0.25f;
            const float db2 = d * (0.5f + (x[b].scales[ib] >> 4)) * 0.25f;
            for (int l = 0; l < 4; ++l) {
                const uint8_t *code = (const uint8_t *)&iq2xs_grid[aux[l] & 511];
                const uint8_t signs = ksigns_iq2xs[aux[l] >> 9];
                const float db = (l >> 1) ? db2 : db1;
                for (int j = 0; j < 8; ++j)
                    *out++ = db * (float)code[j] * (signs & kmask_iq2xs[j] ? -1.f : 1.f);
            }
        }
    }
}

} // namespace dsv41
