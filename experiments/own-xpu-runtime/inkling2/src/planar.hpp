// planar.hpp: card-side "planar" layouts of the three formats that carry most of the bytes (NVFP4 experts, Q8_0 and
// Q6_K), and their decoders. A planar row keeps the same bytes as the file's row, regrouped so that each lane reads its
// 32 values with aligned vector loads: all the quant bytes of the row first, then the scales. Decoded values are the
// same floats as formats.hpp (same operations in the same order), so every product is bit-identical.
//   Q8_0P : qs[cols] (int8)            | d[cols/32] (half)                       row stride: file stride (cols*34/32)
//   NVFP4P: qs[cols/2] (E2M1 pairs)    | d[cols/16] (UE4M3)                      row stride: file stride (cols*36/64)
//   Q6_KP : ql[cols/2] | qh[cols/4] | sc[cols/16] (int8) | d[cols/256] (half)   row stride: file stride rounded up to 16
// Q8_0 and NVFP4 are regrouped in place; Q6_K gets its own buffer (its file stride, 210/256 per value, is not even).
#pragma once
#include "formats.hpp"

namespace ink::pl {

using fmt::h2f;

template <int N> inline void load_bytes(const uint8_t *p, uint8_t *o) { // N bytes, p aligned to min(N, 16)
    if constexpr (N % 16 == 0) {
        using V = sycl::vec<uint32_t, 4>;
        for (int i = 0; i < N / 16; ++i) {
            V v = *(const V *)(p + 16 * i);
            for (int k = 0; k < 4; ++k) std::memcpy(o + 16 * i + 4 * k, &v[k], 4);
        }
    } else {
        using V = sycl::vec<uint32_t, 2>;
        for (int i = 0; i < N / 8; ++i) {
            V v = *(const V *)(p + 8 * i);
            for (int k = 0; k < 2; ++k) std::memcpy(o + 8 * i + 4 * k, &v[k], 4);
        }
    }
}

// E2M1 magnitude table without a lookup: 0 1 2 3 4 6 8 12, sign from bit 3 (= kvalues_mxfp4, as int8)
inline int fp4_int(int nib) {
    int m = nib & 7;
    int v = m < 4 ? m : ((4 + (m & 1) * 2) << ((m >> 1) - 2));
    return (nib & 8) ? -v : v;
}

// ue4m3 (formats.hpp) without ldexp: every UE4M3 value times 0.5 is exactly representable, so building the float from
// its bits gives the same value. e > 0: (8 + m) * 2^(e - 11) = 2^(e - 8) * (1 + m/8): exponent field e + 119,
// mantissa m << 20. e = 0: m * 2^-10 (exact). 0 and 0x7F are 0.
inline float ue4m3_bits(uint8_t x) {
    int e = (x >> 3) & 0xF, m = x & 0x7;
    uint32_t u = e ? ((uint32_t)(e + 119) << 23) | ((uint32_t)m << 20) : 0u;
    float f;
    std::memcpy(&f, &u, 4);
    if (e == 0) f = (float)m * 0x1p-10f;
    return (x == 0x7F) ? 0.0f : f;
}
// E2M1 magnitudes 0 1 2 3 4 6 8 12 packed four bits each
constexpr uint32_t FP4_MAG = 0xC8643210u;

struct Q8_0P {
    static constexpr uint32_t TYPE = G_Q8_0;
    static void decode32(const uint8_t *row, int cols, int c, float *o) {
        uint8_t q[32];
        load_bytes<32>(row + 32 * c, q);
        float d = h2f(row + cols + 2 * c);
        for (int i = 0; i < 32; ++i) o[i] = (int8_t)q[i] * d;
    }
    // the same decode split in two: load() issues the loads, dec() computes from registers (for kernels that load
    // every chunk of a lane before using any)
    struct Pre { sycl::vec<uint32_t, 4> a, b; uint16_t d; };
    static void load(const uint8_t *row, int cols, int c, Pre &p) {
        p.a = *(const sycl::vec<uint32_t, 4> *)(row + 32 * c);
        p.b = *(const sycl::vec<uint32_t, 4> *)(row + 32 * c + 16);
        std::memcpy(&p.d, row + cols + 2 * c, 2);
    }
    static void dec(const Pre &p, float *o) {
        uint8_t hb[2];
        std::memcpy(hb, &p.d, 2);
        float d = h2f(hb);
        for (int i = 0; i < 4; ++i) {
            uint32_t wa = p.a[i], wb = p.b[i];
            for (int k = 0; k < 4; ++k) {
                o[4 * i + k] = (int8_t)(uint8_t)(wa >> (8 * k)) * d;
                o[16 + 4 * i + k] = (int8_t)(uint8_t)(wb >> (8 * k)) * d;
            }
        }
    }
    // one block b of a row: file {d, qs[32]} at src + 34 b
    static void repack_block(const uint8_t *src, uint8_t *dst, int cols, int b) {
        const uint8_t *s = src + 34 * b;
        for (int i = 0; i < 32; ++i) dst[32 * b + i] = s[2 + i];
        dst[cols + 2 * b] = s[0];
        dst[cols + 2 * b + 1] = s[1];
    }
    static int blocks(int cols) { return cols / 32; }
    static size_t stride(size_t file_rb) { return file_rb; }
};

struct NVFP4P {
    static constexpr uint32_t TYPE = G_NVFP4;
    // rows of 1152 values have an 8-byte aligned stride: 8-byte loads always
    static void decode32(const uint8_t *row, int cols, int c, float *o) {
        uint8_t q[16];
        load_bytes<8>(row + 16 * c, q);
        load_bytes<8>(row + 16 * c + 8, q + 8);
        uint16_t dd;
        std::memcpy(&dd, row + cols / 2 + 2 * c, 2);
        for (int k = 0; k < 2; ++k) {
            float d = ue4m3_bits((uint8_t)(dd >> (8 * k)));
            float *ob = o + 16 * k;
            for (int j = 0; j < 8; ++j) {
                uint32_t b = q[8 * k + j];
                // value * d is exact (at most 6 significant bits), so (float)v * d equals formats.hpp's v0 * d
                int m0 = (int)((FP4_MAG >> ((b & 7) * 4)) & 0xF), m1 = (int)((FP4_MAG >> (((b >> 4) & 7) * 4)) & 0xF);
                int v0 = (b & 8) ? -m0 : m0, v1 = (b & 0x80) ? -m1 : m1; // -0 stays +0, as in kvalues_mxfp4
                ob[j] = (float)v0 * d;
                ob[j + 8] = (float)v1 * d;
            }
        }
    }
    struct Pre { sycl::vec<uint32_t, 2> a, b; uint16_t dd; };
    static void load(const uint8_t *row, int cols, int c, Pre &p) {
        p.a = *(const sycl::vec<uint32_t, 2> *)(row + 16 * c);
        p.b = *(const sycl::vec<uint32_t, 2> *)(row + 16 * c + 8);
        std::memcpy(&p.dd, row + cols / 2 + 2 * c, 2);
    }
    static void dec(const Pre &p, float *o) {
        uint32_t w[4] = {p.a[0], p.a[1], p.b[0], p.b[1]};
        for (int k = 0; k < 2; ++k) {
            float d = ue4m3_bits((uint8_t)(p.dd >> (8 * k)));
            float *ob = o + 16 * k;
            for (int j = 0; j < 8; ++j) {
                uint32_t b = (w[2 * k + j / 4] >> (8 * (j % 4))) & 0xFF;
                int m0 = (int)((FP4_MAG >> ((b & 7) * 4)) & 0xF), m1 = (int)((FP4_MAG >> (((b >> 4) & 7) * 4)) & 0xF);
                int v0 = (b & 8) ? -m0 : m0, v1 = (b & 0x80) ? -m1 : m1;
                ob[j] = (float)v0 * d;
                ob[j + 8] = (float)v1 * d;
            }
        }
    }
    // one block b (64 values) of a row: file {d[4], qs[32]} at src + 36 b
    static void repack_block(const uint8_t *src, uint8_t *dst, int cols, int b) {
        const uint8_t *s = src + 36 * b;
        for (int i = 0; i < 32; ++i) dst[32 * b + i] = s[4 + i];
        for (int i = 0; i < 4; ++i) dst[cols / 2 + 4 * b + i] = s[i];
    }
    static int blocks(int cols) { return cols / 64; }
    static size_t stride(size_t file_rb) { return file_rb; }
};

struct Q6_KP {
    static constexpr uint32_t TYPE = G_Q6_K;
    static void decode32(const uint8_t *row, int cols, int c, float *o) {
        const int sb = c >> 3, ib = c & 7, n = ib >> 2, w = ib & 3;
        uint8_t ql[32], qh[32];
        load_bytes<32>(row + 128 * sb + 64 * n + 32 * (w & 1), ql);
        load_bytes<32>(row + cols / 2 + 64 * sb + 32 * n, qh);
        const int8_t *sc = (const int8_t *)(row + cols / 2 + cols / 4) + 16 * sb + 8 * n + 2 * w;
        float d = h2f(row + cols / 2 + cols / 4 + cols / 16 + 2 * sb);
        // o[l] = d * sc[is + 2w] * q, evaluated as (d * sc) * q like formats.hpp
        const int lo_shift = (w >> 1) * 4, hi_shift = 2 * w;
        for (int l = 0; l < 32; ++l) {
            int q = (((ql[l] >> lo_shift) & 0xF) | (((qh[l] >> hi_shift) & 3) << 4)) - 32;
            o[l] = d * sc[l >> 4] * (int8_t)q;
        }
    }
    // one super-block b (256 values): file {ql[128], qh[64], sc[16], d} at src + 210 b
    static void repack_block(const uint8_t *src, uint8_t *dst, int cols, int b) {
        const uint8_t *s = src + 210 * b;
        for (int i = 0; i < 128; ++i) dst[128 * b + i] = s[i];
        for (int i = 0; i < 64; ++i) dst[cols / 2 + 64 * b + i] = s[128 + i];
        for (int i = 0; i < 16; ++i) dst[cols / 2 + cols / 4 + 16 * b + i] = s[192 + i];
        dst[cols / 2 + cols / 4 + cols / 16 + 2 * b] = s[208];
        dst[cols / 2 + cols / 4 + cols / 16 + 2 * b + 1] = s[209];
    }
    static int blocks(int cols) { return cols / 256; }
    static size_t stride(size_t file_rb) { return (file_rb + 15) / 16 * 16; }
};

// the file's own layout through the same interface
template <class FT> struct Raw {
    static void decode32(const uint8_t *row, int, int c, float *o) { FT::decode32(row, c, o); }
};

// regroup nrows rows of src (file layout, stride src_rb) into dst (planar, stride dst_rb); src and dst must not overlap
template <class PT> sycl::event repack(sycl::queue &q, const uint8_t *src, size_t src_rb, uint8_t *dst, size_t dst_rb,
                                       int cols, size_t nrows) {
    const int nb = PT::blocks(cols);
    return q.parallel_for(sycl::range<2>(nrows, (size_t)nb), [=](sycl::id<2> i) {
        PT::repack_block(src + i[0] * src_rb, dst + i[0] * dst_rb, cols, (int)i[1]);
    });
}

} // namespace ink::pl
