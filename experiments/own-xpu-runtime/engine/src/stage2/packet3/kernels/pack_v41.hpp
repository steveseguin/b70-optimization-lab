// Device row layouts for the DeepSeek V4.1 weight formats ("packed" rows).
//
// The GGUF block formats interleave a 2-byte scale with the quant bytes
// (Q8_0: 34-byte blocks, IQ2_XXS: 66-byte blocks), so on the card every
// quant word is only 2-byte aligned and each sub-group reads its row in tiny
// dependent pieces. The packed row holds exactly the same bytes, regrouped so
// that one aligned sub-group block read returns, on lane l, the bytes lane l
// needs (lane l owns columns l, l+32, ... in every gemv; see iq3::lane_dot).
// The kernels that read packed rows (ops41sycl::*P in sycl_v41.hpp) perform
// the same float operations in the same order as the unpacked lane sums, so
// their outputs are bit-identical; the device gate checks every format.
//
// Packed row layouts (cols = elements per row):
//   Q8_0, C = cols/32 chunks, C % 4 == 0:
//     [C/4 quads x 32 u32] word l of quad m = q[4m][l] | q[4m+1][l]<<8 | q[4m+2][l]<<16 | q[4m+3][l]<<24
//     [C x u16 scale d][zero pad to a multiple of 16 bytes]
//   IQ2_XXS, NB = cols/256 blocks (66-byte blocks: d, then 8 x (lo, hi) u32):
//     [NB x 16 u32: lo0 s0 lo1 s1 ...: lo unchanged; s = expand_signs(hi)]
//     [NB x u32: nibble g = hi_g >> 28 (the 4-bit scale)][NB x u16 scale d][pad]
//   expand_signs: hi's four 7-bit sign fields (bits 7k..7k+6), each widened to
//   8 bits with its parity as bit 7 (iq2xs ksigns: the 8th sign is the parity
//   of the other seven), byte k of the result. The kernel then reads sign j of
//   field k as bit 8k + j (one shift) instead of a popcount over a mask.
//   IQ2_S (82-byte blocks: d, idx[32], signs[32], qh[8], scales[8]):
//     [NB x 16 u32: per group g, word 2g = idx bytes 4g..4g+3, word 2g+1 = sign bytes 4g..4g+3]
//     [NB x 4 u32: qh[8], scales[8]][NB x u16 d][pad]
//   IQ3_XXS (98-byte blocks: d, qs[64], scale/sign words[8]):
//     [NB x 24 u32: per group g, words 3g, 3g+1 = qs bytes 8g..8g+7, word 3g+2 = scale/sign word g]
//     [NB x u16 d][pad]
//     (expand_signs here measured 7 % SLOWER on the card, 2026-11-09: kept unexpanded)
//   IQ1_S (50-byte blocks: d, qs[32], qh u16[8]):
//     [NB x 8 u32: word g = qs bytes 4g..4g+3][NB x 8 u16 qh][NB x u16 d][pad]
//   IQ2_XS (74-byte blocks: d, qs u16[32], scales[8]):
//     [NB x 16 u32: qs, two u16 per word, group g in words 2g, 2g+1][NB x 8 scale bytes]
//     [NB x u16 d][pad]
//   Q6_K (210-byte blocks: ql[128], qh[64], scales int8[16], d):
//     [NB x 32 u32: word l = ql[l] | ql[32+l]<<8 | ql[64+l]<<16 | ql[96+l]<<24]
//     [NB x 32 u16: qh[l] | qh[32+l]<<8][NB x 16 scales][NB x u16 d][pad]
//   Q5_K (176-byte blocks: d, dmin, scales[12], qh[32], qs[128]):
//     [NB x 32 u32: word l = qs[l] | qs[32+l]<<8 | qs[64+l]<<16 | qs[96+l]<<24]
//     [NB x 32 qh bytes][NB x 16 bytes: d, dmin, scales[12] unchanged][pad]
// (quant words first so the whole-row block reads never run past the row)
// Row strides are multiples of 16 bytes so every row starts aligned.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
#include "stage2/packet2/kernels/math.hpp"

namespace pk41 {

inline size_t pad16(size_t n) { return (n + 15) & ~(size_t)15; }

inline uint32_t expand_signs(uint32_t w) {
    uint32_t r = 0;
    for (unsigned k = 0; k < 4; ++k) {
        const uint32_t s7 = (w >> (7 * k)) & 127u;
        const uint32_t par = (uint32_t)__builtin_popcount(s7) & 1u;
        r |= (s7 | (par << 7)) << (8 * k);
    }
    return r;
}

// Is there a packed form (and a packed kernel) for this format at this row
// length? `routed` = rank-3 expert bank (routed kernel), else dense gemv.
inline bool packable(iq3::Type t, size_t cols, bool routed) {
    switch (t) {
    case iq3::Type::Q8_0:
        if (routed) return false;
        return cols == 1280 || cols == 2304 || cols == 4096 || cols == 5120 || cols == 8192;
    case iq3::Type::Q6_K:
        if (routed) return false;
        return cols == 1280 || cols == 4096 || cols == 5120 || cols == 6144 || cols == 8192;
    case iq3::Type::Q5_K:
        if (routed) return false;
        return cols == 2304 || cols == 5120;
    case iq3::Type::IQ2_XXS:
    case iq3::Type::IQ2_S:
    case iq3::Type::IQ3_XXS:
    case iq3::Type::IQ1_S:
    case iq3::Type::IQ2_XS:
        return routed && (cols == 5120 || cols == 2304);
    default: return false;
    }
}

inline size_t packed_row_bytes(iq3::Type t, size_t cols) {
    switch (t) {
    case iq3::Type::Q8_0: { const size_t C = cols / 32; return pad16(C * 32 + C * 2); }
    case iq3::Type::IQ2_XXS: { const size_t nb = cols / 256; return pad16(nb * 70); }
    case iq3::Type::IQ2_S: { const size_t nb = cols / 256; return pad16(nb * 80 + nb * 2); }
    case iq3::Type::IQ3_XXS: { const size_t nb = cols / 256; return pad16(nb * 96 + nb * 2); }
    case iq3::Type::IQ1_S: { const size_t nb = cols / 256; return pad16(nb * 48 + nb * 2); }
    case iq3::Type::IQ2_XS: { const size_t nb = cols / 256; return pad16(nb * 72 + nb * 2); }
    case iq3::Type::Q6_K: return pad16(cols / 256 * 210);
    case iq3::Type::Q5_K: return pad16(cols / 256 * 176);
    default: return 0;
    }
}

// src: one GGUF row; dst: packed_row_bytes(t, cols) bytes.
inline void pack_row(iq3::Type t, const uint8_t *src, uint8_t *dst, size_t cols) {
    const size_t pb = packed_row_bytes(t, cols);
    std::memset(dst, 0, pb);
    if (t == iq3::Type::Q8_0) {
        const size_t C = cols / 32;
        for (size_t m = 0; m < C / 4; ++m)
            for (size_t l = 0; l < 32; ++l)
                for (size_t k = 0; k < 4; ++k) dst[m * 128 + l * 4 + k] = src[(4 * m + k) * 34 + 2 + l];
        for (size_t c = 0; c < C; ++c) std::memcpy(dst + C * 32 + 2 * c, src + c * 34, 2);
    } else if (t == iq3::Type::IQ2_XXS) {
        const size_t nb = cols / 256;
        for (size_t b = 0; b < nb; ++b) {
            uint32_t sc = 0;
            for (size_t g = 0; g < 8; ++g) {
                uint32_t lo, hi;
                std::memcpy(&lo, src + b * 66 + 2 + 8 * g, 4);
                std::memcpy(&hi, src + b * 66 + 6 + 8 * g, 4);
                const uint32_t es = expand_signs(hi);
                std::memcpy(dst + b * 64 + 8 * g, &lo, 4);
                std::memcpy(dst + b * 64 + 8 * g + 4, &es, 4);
                sc |= (hi >> 28) << (4 * g);
            }
            std::memcpy(dst + nb * 64 + 4 * b, &sc, 4);
            std::memcpy(dst + nb * 68 + 2 * b, src + b * 66, 2);
        }
    } else if (t == iq3::Type::IQ2_S) {
        const size_t nb = cols / 256;
        for (size_t b = 0; b < nb; ++b) {
            const uint8_t *s = src + b * 82;
            for (size_t g = 0; g < 8; ++g) {
                std::memcpy(dst + b * 64 + 8 * g, s + 2 + 4 * g, 4);
                std::memcpy(dst + b * 64 + 8 * g + 4, s + 34 + 4 * g, 4);
            }
            std::memcpy(dst + nb * 64 + b * 16, s + 66, 16);
            std::memcpy(dst + nb * 80 + 2 * b, s, 2);
        }
    } else if (t == iq3::Type::IQ3_XXS) {
        const size_t nb = cols / 256;
        for (size_t b = 0; b < nb; ++b) {
            const uint8_t *s = src + b * 98;
            for (size_t g = 0; g < 8; ++g) {
                std::memcpy(dst + b * 96 + 12 * g, s + 2 + 8 * g, 8);
                std::memcpy(dst + b * 96 + 12 * g + 8, s + 66 + 4 * g, 4);
            }
            std::memcpy(dst + nb * 96 + 2 * b, s, 2);
        }
    } else if (t == iq3::Type::IQ1_S) {
        const size_t nb = cols / 256;
        for (size_t b = 0; b < nb; ++b) {
            std::memcpy(dst + b * 32, src + b * 50 + 2, 32);
            std::memcpy(dst + nb * 32 + b * 16, src + b * 50 + 34, 16);
            std::memcpy(dst + nb * 48 + 2 * b, src + b * 50, 2);
        }
    } else if (t == iq3::Type::IQ2_XS) {
        const size_t nb = cols / 256;
        for (size_t b = 0; b < nb; ++b) {
            std::memcpy(dst + b * 64, src + b * 74 + 2, 64);
            std::memcpy(dst + nb * 64 + b * 8, src + b * 74 + 66, 8);
            std::memcpy(dst + nb * 72 + 2 * b, src + b * 74, 2);
        }
    } else if (t == iq3::Type::Q6_K) {
        const size_t nb = cols / 256;
        for (size_t b = 0; b < nb; ++b) {
            const uint8_t *s = src + b * 210;
            for (size_t l = 0; l < 32; ++l) {
                for (size_t k = 0; k < 4; ++k) dst[b * 128 + 4 * l + k] = s[32 * k + l];
                for (size_t k = 0; k < 2; ++k) dst[nb * 128 + b * 64 + 2 * l + k] = s[128 + 32 * k + l];
            }
            std::memcpy(dst + nb * 192 + b * 16, s + 192, 16);
            std::memcpy(dst + nb * 208 + 2 * b, s + 208, 2);
        }
    } else if (t == iq3::Type::Q5_K) {
        const size_t nb = cols / 256;
        for (size_t b = 0; b < nb; ++b) {
            const uint8_t *s = src + b * 176;
            for (size_t l = 0; l < 32; ++l)
                for (size_t k = 0; k < 4; ++k) dst[b * 128 + 4 * l + k] = s[48 + 32 * k + l];
            std::memcpy(dst + nb * 128 + b * 32, s + 16, 32);
            std::memcpy(dst + nb * 160 + b * 16, s, 16);
        }
    }
}

} // namespace pk41
