#pragma once
// The exact three-part split of an fp32 value into bf16 parts (x = a + b + c exactly; README "Matrix engines with
// exact products"), shared by the expert kernels (xmx_moe.hpp) and the norms that write their parts (fused.hpp, ops.hpp).
#include <sycl/sycl.hpp>
#include <cstdint>

namespace ink {
inline uint16_t bf_rn(float f) {
    const uint32_t u = sycl::bit_cast<uint32_t>(f);
    return (uint16_t)((u + 0x7fffu + ((u >> 16) & 1u)) >> 16);
}
inline float bf_f(uint16_t b) { return sycl::bit_cast<float>((uint32_t)b << 16); }
inline void split3(float x, uint16_t &a, uint16_t &b, uint16_t &c) {
    a = bf_rn(x);
    const float r1 = x - bf_f(a);
    b = bf_rn(r1);
    c = bf_rn(r1 - bf_f(b));
}
// value v's parts at p[0], p[ps], p[2 ps]
inline void split3_store(float v, uint16_t *p, size_t ps) {
    uint16_t a, b, c;
    split3(v, a, b, c);
    p[0] = a; p[ps] = b; p[2 * ps] = c;
}
} // namespace ink
