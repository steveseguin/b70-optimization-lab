// Independent Q2_K block decoder (GGUF type 10, 84 bytes / 256 elems).
// Layout: scales[16] (low nibble = scale, high nibble = min), qs[64],
// fp16 d, fp16 dmin.  Two 128-element halves; per half four shift groups,
// each emitting 16 values from q[l] then 16 from q[l+16].
// Value = d*scale*q - dmin*min.
#pragma once
#include <cstdint>
#include "iq2xxs_decode.hpp"  // dsv41::fp16_to_fp32_bits

namespace dsv41 {

struct block_q2_K {
    uint8_t  scales[16];
    uint8_t  qs[64];
    uint16_t d;
    uint16_t dmin;
};
static_assert(sizeof(block_q2_K) == 84, "q2_K block layout");

inline void dequantize_q2_K(const block_q2_K *x, float *out, long long nb) {
    for (long long b = 0; b < nb; ++b) {
        const float d   = fp16_to_fp32_bits(x[b].d);
        const float min = fp16_to_fp32_bits(x[b].dmin);
        const uint8_t *q = x[b].qs;
        int is = 0;
        for (int n = 0; n < 256; n += 128) {
            int shift = 0;
            for (int j = 0; j < 4; ++j) {
                uint8_t sc = x[b].scales[is++];
                float dl = d * (sc & 0xF), ml = min * (sc >> 4);
                for (int l = 0; l < 16; ++l) *out++ = dl * (float)((q[l] >> shift) & 3) - ml;
                sc = x[b].scales[is++];
                dl = d * (sc & 0xF); ml = min * (sc >> 4);
                for (int l = 0; l < 16; ++l) *out++ = dl * (float)((q[l+16] >> shift) & 3) - ml;
                shift += 2;
            }
            q += 32;
        }
    }
}

} // namespace dsv41
