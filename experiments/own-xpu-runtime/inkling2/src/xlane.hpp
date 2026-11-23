#pragma once
// A vector in "lane order". The matrix kernels give chunk c (32 values) of a row to lane c % 16; read from the plain
// layout, one float4 load of the 16 lanes touches 16 cache lines (lane stride 128 bytes), and for 4-bit weights these
// loads, not the weights, set the pace (bench_gemv 2026-11-23: expert down 33 -> 25 us, gate|up 51 -> 48). In lane
// order the 16 lanes' float4 of one load sit side by side (256 bytes):
//   chunk c = 16 j + l, values 4 q .. 4 q + 3  ->  floats ((j * 8 + q) * 16 + l) * 4 .. + 3.
// The same values reach the same registers, so every sum is unchanged. Producers (norms, SITU) write this copy.
#include <cstddef>

namespace ink {
inline size_t xlane_floats(int cols) { return (size_t)((cols / 32 + 15) / 16) * 512; }
inline size_t xlane_at(int i) { // where value i of the plain vector goes
    const int c = i / 32, r = i % 32, j = c / 16, l = c % 16, q = r / 4;
    return ((size_t)(j * 8 + q) * 16 + l) * 4 + r % 4;
}
} // namespace ink
