// Independent MXFP4 block decoder (GGUF type 39, 17 bytes / 32 elems).
// Layout: e = E8M0 scale byte (2^(e-127), halved to match the doubled
// e2m1 table); qs[16] = 32 packed e2m1 values (low nibble first).
// Value = (2^(e-127) * 0.5) * kvalues_fp4[code], kvalues = 2*e2m1.
// e2m1 grid (OCP MX spec): {0,.5,1,1.5,2,3,4,6} x sign -> doubled ints.
// Used by the dspark draft experts (config expert_dtype=fp4).
#pragma once
#include <cstdint>
#include <cstring>

namespace dsv41 {

struct block_mxfp4 {
    uint8_t e;
    uint8_t qs[16];
};
static_assert(sizeof(block_mxfp4) == 17, "mxfp4 block layout");

inline void dequantize_mxfp4(const block_mxfp4 *x, float *out, long long nb) {
    static const int8_t kv[16] = {0, 1, 2, 3, 4, 6, 8, 12, 0, -1, -2, -3, -4, -6, -8, -12};
    for (long long b = 0; b < nb; ++b) {
        // E8M0 -> float, halved (table values are doubled)
        uint32_t bits = (uint32_t)x[b].e << 23;
        float d;
        std::memcpy(&d, &bits, 4);
        d *= 0.5f;
        for (int j = 0; j < 16; ++j) {
            out[j]      = d * (float)kv[x[b].qs[j] & 0xF];   // low nibbles -> elems 0..15
            out[j + 16] = d * (float)kv[x[b].qs[j] >> 4];    // high nibbles -> elems 16..31
        }
        out += 32;
    }
}

} // namespace dsv41
