// formats.hpp: device-side decoding of the weight formats in the Inkling-2 GGUFs, 32 values at a time.
// Every format exposes decode32(row, c, out): the values of elements [32c, 32c+32) of one row, computed with the same
// float operations as ggml's dequantize_row_* (ggml/src/ggml-quants.c of the reference tree), so a decoded value
// equals ggml's bit for bit (tools/test_formats.cpp checks this against the reference library).
#pragma once
#include "gguf.hpp"
#include <cstdint>
#include <sycl/sycl.hpp>

namespace ink::fmt {

inline float h2f(const uint8_t *p) { // little-endian IEEE half
    sycl::half h;
    uint16_t b = (uint16_t)p[0] | ((uint16_t)p[1] << 8);
    std::memcpy(&h, &b, 2);
    return (float)h;
}
inline float bf2f(uint16_t b) {
    uint32_t u = (uint32_t)b << 16;
    float f;
    std::memcpy(&f, &u, 4);
    return f;
}
// kvalues_mxfp4: 2 x the E2M1 values (ggml-common.h); NVFP4 scales carry the matching 0.5
inline int8_t kv_fp4(int i) {
    constexpr int8_t v[16] = {0, 1, 2, 3, 4, 6, 8, 12, 0, -1, -2, -3, -4, -6, -8, -12};
    return v[i];
}
inline int8_t kv_nl(int i) {
    constexpr int8_t v[16] = {-127, -104, -83, -65, -49, -35, -22, -10, 1, 13, 25, 38, 53, 69, 89, 113};
    return v[i];
}
// ggml_ue4m3_to_fp32 (ggml-impl.h): unsigned E4M3, bias 7, sign bit ignored, 0 and 0x7F decode to 0, times 0.5
inline float ue4m3(uint8_t x) {
    if (x == 0 || x == 0x7F) return 0.0f;
    int e = (x >> 3) & 0xF, m = x & 0x7;
    float raw = e == 0 ? sycl::ldexp((float)m, -9) : sycl::ldexp(1.0f + (float)m / 8.0f, e - 7);
    return raw * 0.5f;
}
inline void scale_min_k4(int j, const uint8_t *q, uint8_t &d, uint8_t &m) {
    if (j < 4) { d = q[j] & 63; m = q[j + 4] & 63; }
    else { d = (q[j + 4] & 0xF) | ((q[j - 4] >> 6) << 4); m = (q[j + 4] >> 4) | ((q[j] >> 6) << 4); }
}

template <uint32_t T> struct F;

template <> struct F<G_F32> {
    static constexpr int BLK = 1, BYTES = 4;
    static void decode32(const uint8_t *row, int c, float *o) {
        const float *r = (const float *)row + 32 * c;
        for (int i = 0; i < 32; ++i) o[i] = r[i];
    }
};
template <> struct F<G_F16> {
    static constexpr int BLK = 1, BYTES = 2;
    static void decode32(const uint8_t *row, int c, float *o) {
        for (int i = 0; i < 32; ++i) o[i] = h2f(row + 2 * (32 * c + i));
    }
};
template <> struct F<G_BF16> {
    static constexpr int BLK = 1, BYTES = 2;
    static void decode32(const uint8_t *row, int c, float *o) {
        const uint16_t *r = (const uint16_t *)row + 32 * c;
        for (int i = 0; i < 32; ++i) o[i] = bf2f(r[i]);
    }
};
template <> struct F<G_Q8_0> { // {half d; int8 qs[32]}: y = d*q
    static constexpr int BLK = 32, BYTES = 34;
    static void decode32(const uint8_t *row, int c, float *o) {
        const uint8_t *b = row + 34 * c;
        float d = h2f(b);
        const int8_t *q = (const int8_t *)(b + 2);
        for (int i = 0; i < 32; ++i) o[i] = q[i] * d;
    }
};
template <> struct F<G_Q5_0> { // {half d; u8 qh[4]; u8 qs[16]}
    static constexpr int BLK = 32, BYTES = 22;
    static void decode32(const uint8_t *row, int c, float *o) {
        const uint8_t *b = row + 22 * c;
        float d = h2f(b);
        uint32_t qh = (uint32_t)b[2] | ((uint32_t)b[3] << 8) | ((uint32_t)b[4] << 16) | ((uint32_t)b[5] << 24);
        const uint8_t *qs = b + 6;
        for (int j = 0; j < 16; ++j) {
            uint8_t xh0 = ((qh >> (j + 0)) << 4) & 0x10;
            uint8_t xh1 = ((qh >> (j + 12))) & 0x10;
            int32_t x0 = ((qs[j] & 0x0F) | xh0) - 16;
            int32_t x1 = ((qs[j] >> 4) | xh1) - 16;
            o[j] = x0 * d;
            o[j + 16] = x1 * d;
        }
    }
};
template <> struct F<G_IQ4_NL> { // {half d; u8 qs[16]}
    static constexpr int BLK = 32, BYTES = 18;
    static void decode32(const uint8_t *row, int c, float *o) {
        const uint8_t *b = row + 18 * c;
        float d = h2f(b);
        const uint8_t *qs = b + 2;
        for (int j = 0; j < 16; ++j) {
            o[j] = d * kv_nl(qs[j] & 0xf);
            o[j + 16] = d * kv_nl(qs[j] >> 4);
        }
    }
};
template <> struct F<G_IQ4_XS> { // {half d; u16 scales_h; u8 scales_l[4]; u8 qs[128]}, 256 values
    static constexpr int BLK = 256, BYTES = 136;
    static void decode32(const uint8_t *row, int c, float *o) {
        const uint8_t *b = row + 136 * (c >> 3);
        int ib = c & 7;
        float d = h2f(b);
        uint16_t sh = (uint16_t)b[2] | ((uint16_t)b[3] << 8);
        const uint8_t *sl = b + 4, *qs = b + 8 + 16 * ib;
        int ls = ((sl[ib / 2] >> 4 * (ib % 2)) & 0xf) | (((sh >> 2 * ib) & 3) << 4);
        float dl = d * (ls - 32);
        for (int j = 0; j < 16; ++j) {
            o[j] = dl * kv_nl(qs[j] & 0xf);
            o[j + 16] = dl * kv_nl(qs[j] >> 4);
        }
    }
};
template <> struct F<G_Q4_K> { // {half d; half dmin; u8 scales[12]; u8 qs[128]}
    static constexpr int BLK = 256, BYTES = 144;
    static void decode32(const uint8_t *row, int c, float *o) {
        const uint8_t *b = row + 144 * (c >> 3);
        int ib = c & 7;
        float d = h2f(b), mn = h2f(b + 2);
        uint8_t sc, m;
        scale_min_k4(ib, b + 4, sc, m);
        float d1 = d * sc, m1 = mn * m;
        const uint8_t *q = b + 16 + 32 * (ib / 2);
        if (ib & 1) for (int l = 0; l < 32; ++l) o[l] = d1 * (q[l] >> 4) - m1;
        else for (int l = 0; l < 32; ++l) o[l] = d1 * (q[l] & 0xF) - m1;
    }
};
template <> struct F<G_Q5_K> { // {half d; half dmin; u8 scales[12]; u8 qh[32]; u8 qs[128]}
    static constexpr int BLK = 256, BYTES = 176;
    static void decode32(const uint8_t *row, int c, float *o) {
        const uint8_t *b = row + 176 * (c >> 3);
        int ib = c & 7;
        float d = h2f(b), mn = h2f(b + 2);
        uint8_t sc, m;
        scale_min_k4(ib, b + 4, sc, m);
        float d1 = d * sc, m1 = mn * m;
        const uint8_t *qh = b + 16, *ql = b + 48 + 32 * (ib / 2);
        uint8_t u = (uint8_t)(1u << ib);
        if (ib & 1) for (int l = 0; l < 32; ++l) o[l] = d1 * ((ql[l] >> 4) + (qh[l] & u ? 16 : 0)) - m1;
        else for (int l = 0; l < 32; ++l) o[l] = d1 * ((ql[l] & 0xF) + (qh[l] & u ? 16 : 0)) - m1;
    }
};
template <> struct F<G_Q6_K> { // {u8 ql[128]; u8 qh[64]; i8 scales[16]; half d}
    static constexpr int BLK = 256, BYTES = 210;
    static void decode32(const uint8_t *row, int c, float *o) {
        const uint8_t *b = row + 210 * (c >> 3);
        int ib = c & 7, n = ib / 4, w = ib % 4;
        float d = h2f(b + 208);
        const uint8_t *ql = b + 64 * n, *qh = b + 128 + 32 * n;
        const int8_t *sc = (const int8_t *)(b + 192) + 8 * n;
        for (int l = 0; l < 32; ++l) {
            int is = l / 16;
            int8_t q;
            switch (w) {
            case 0: q = (int8_t)((ql[l] & 0xF) | (((qh[l] >> 0) & 3) << 4)) - 32; break;
            case 1: q = (int8_t)((ql[l + 32] & 0xF) | (((qh[l] >> 2) & 3) << 4)) - 32; break;
            case 2: q = (int8_t)((ql[l] >> 4) | (((qh[l] >> 4) & 3) << 4)) - 32; break;
            default: q = (int8_t)((ql[l + 32] >> 4) | (((qh[l] >> 6) & 3) << 4)) - 32; break;
            }
            o[l] = d * sc[is + 2 * w] * q;
        }
    }
};
template <> struct F<G_NVFP4> { // {u8 d[4] (UE4M3, one per 16 values); u8 qs[32] (E2M1 pairs)}, 64 values
    static constexpr int BLK = 64, BYTES = 36;
    static void decode32(const uint8_t *row, int c, float *o) {
        const uint8_t *b = row + 36 * (c >> 1);
        for (int k = 0; k < 2; ++k) {
            int s = 2 * (c & 1) + k;
            float d = ue4m3(b[s]);
            const uint8_t *qs = b + 4 + 8 * s;
            float *ob = o + 16 * k;
            for (int j = 0; j < 8; ++j) {
                int8_t v0 = kv_fp4(qs[j] & 0x0F), v1 = kv_fp4(qs[j] >> 4);
                ob[j] = v0 * d;
                ob[j + 8] = v1 * d;
            }
        }
    }
};

// call f.template operator()<F<T>>() for the runtime type t
template <class Fn> inline void dispatch(uint32_t t, Fn &&f) {
    switch (t) {
    case G_F32: f.template operator()<F<G_F32>>(); return;
    case G_F16: f.template operator()<F<G_F16>>(); return;
    case G_BF16: f.template operator()<F<G_BF16>>(); return;
    case G_Q8_0: f.template operator()<F<G_Q8_0>>(); return;
    case G_Q5_0: f.template operator()<F<G_Q5_0>>(); return;
    case G_IQ4_NL: f.template operator()<F<G_IQ4_NL>>(); return;
    case G_IQ4_XS: f.template operator()<F<G_IQ4_XS>>(); return;
    case G_Q4_K: f.template operator()<F<G_Q4_K>>(); return;
    case G_Q5_K: f.template operator()<F<G_Q5_K>>(); return;
    case G_Q6_K: f.template operator()<F<G_Q6_K>>(); return;
    case G_NVFP4: f.template operator()<F<G_NVFP4>>(); return;
    default: throw std::runtime_error(std::string("formats: no decoder for ") + type_name(t));
    }
}

} // namespace ink::fmt
