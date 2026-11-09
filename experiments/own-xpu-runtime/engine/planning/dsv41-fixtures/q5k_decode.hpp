// Independent Q5_K block decoder (GGUF type 13, 176 bytes / 256 elems).
// Layout: fp16 d, fp16 dmin, scales[12] (6-bit scale+min pairs via the
// k4 split), qh[32] high bits, qs[64] low nibbles.
//   8 groups of 32: value = d*sc*(qlo + 16*qhi) - dmin*min
// Needed for the UD-IQ2_XXS engram table (per_layer_token_embd, Q5_K).
#pragma once
#include <cstdint>
#include "iq2xxs_decode.hpp"  // dsv41::fp16_to_fp32_bits

namespace dsv41 {

struct block_q5_K {
    uint16_t d;
    uint16_t dmin;
    uint8_t  scales[12];
    uint8_t  qh[32];
    uint8_t  qs[128];
};
static_assert(sizeof(block_q5_K) == 176, "q5_K block layout");

static inline void get_scale_min_k4(int j, const uint8_t *q, uint8_t *d, uint8_t *m) {
    if (j < 4) { *d = q[j] & 63; *m = q[j + 4] & 63; }
    else       { *d = (q[j+4] & 0xF) | ((q[j-4] >> 6) << 4);
                 *m = (q[j+4] >>  4) | ((q[j  ] >> 6) << 4); }
}

inline void dequantize_q5_K(const block_q5_K *x, float *out, long long nb) {
    for (long long b = 0; b < nb; ++b) {
        const uint8_t *ql = x[b].qs;
        const uint8_t *qh = x[b].qh;
        const float d = fp16_to_fp32_bits(x[b].d);
        const float min = fp16_to_fp32_bits(x[b].dmin);
        int is = 0;
        uint8_t u1 = 1, u2 = 2;
        for (int j = 0; j < 256; j += 64) {
            uint8_t sc, m;
            get_scale_min_k4(is + 0, x[b].scales, &sc, &m);
            const float d1 = d * sc, m1 = min * m;
            get_scale_min_k4(is + 1, x[b].scales, &sc, &m);
            const float d2 = d * sc, m2 = min * m;
            for (int l = 0; l < 32; ++l) *out++ = d1 * ((ql[l] & 0xF) + (qh[l] & u1 ? 16 : 0)) - m1;
            for (int l = 0; l < 32; ++l) *out++ = d2 * ((ql[l] >> 4)   + (qh[l] & u2 ? 16 : 0)) - m2;
            ql += 32; is += 2;
            u1 <<= 2; u2 <<= 2;
        }
    }
}

} // namespace dsv41
