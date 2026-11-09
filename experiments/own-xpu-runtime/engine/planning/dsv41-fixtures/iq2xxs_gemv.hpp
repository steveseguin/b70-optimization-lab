// Packed IQ2_XXS row dot: fused decode+dot with a fixed arithmetic contract.
//
// Contract (must hold bit-exactly on any implementation, CPU or device):
//   per 256-block, per 32-group, per 8-sub-block:
//     t  = db * (float)code[j]        // fp32 round
//     t  = t * sign                   // fp32 round (sign = +-1)
//     acc = fmaf(t, x[i], acc)        // single fused multiply-add
//   blocks and lanes in natural (sequential) order; one fp32 accumulator.
//
// This matches dequantize_iq2_xxs followed by a sequential fmaf dot, which
// test_gemv_iq2xxs.cpp gates. Device kernels may reorder ONLY if they keep
// per-term values identical and document the reduction order (e.g. tree32).
#pragma once
#include <cstdint>
#include <cmath>
#include "iq2xxs_decode.hpp"

namespace dsv41 {

inline float gemv_iq2xxs_row(const block_iq2_xxs *row, const float *x, long long nb) {
    using namespace dsv41ref;
    float acc = 0.f;
    long long i = 0;
    for (long long b = 0; b < nb; ++b) {
        const float d = fp16_to_fp32_bits(row[b].d);
        for (int g = 0; g < 8; ++g) {
            uint32_t lo = (uint32_t)row[b].qs[4*g] | ((uint32_t)row[b].qs[4*g+1] << 16);
            uint32_t hi = (uint32_t)row[b].qs[4*g+2] | ((uint32_t)row[b].qs[4*g+3] << 16);
            const float db = d * (0.5f + (float)(hi >> 28)) * 0.25f;
            for (int l = 0; l < 4; ++l) {
                const uint8_t *code = (const uint8_t *)&iq2xxs_grid[(lo >> (8*l)) & 0xff];
                const uint8_t signs = ksigns_iq2xs[(hi >> (7*l)) & 0x7f];
                for (int j = 0; j < 8; ++j, ++i) {
                    float t = db * (float)code[j];
                    t = t * (signs & kmask_iq2xs[j] ? -1.f : 1.f);
                    acc = std::fmaf(t, x[i], acc);
                }
            }
        }
    }
    return acc;
}

} // namespace dsv41
