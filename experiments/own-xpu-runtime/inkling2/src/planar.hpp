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

struct Q8_0P {
    static constexpr uint32_t TYPE = G_Q8_0;
    static void decode32(const uint8_t *row, int cols, int c, float *o) {
        uint8_t q[32];
        load_bytes<32>(row + 32 * c, q);
        float d = h2f(row + cols + 2 * c);
        for (int i = 0; i < 32; ++i) o[i] = (int8_t)q[i] * d;
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
        const uint8_t *dp = row + cols / 2 + 2 * c;
        for (int k = 0; k < 2; ++k) {
            float d = fmt::ue4m3(dp[k]);
            float *ob = o + 16 * k;
            for (int j = 0; j < 8; ++j) {
                uint8_t b = q[8 * k + j];
                int8_t v0 = (int8_t)fp4_int(b & 0x0F), v1 = (int8_t)fp4_int(b >> 4);
                ob[j] = v0 * d;
                ob[j + 8] = v1 * d;
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
