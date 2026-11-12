#pragma once
// xperm-2 (2026-11-11): the SLM grid tables of the routed IQ2_S, IQ2_XS and IQ1_S kernels as constant images, built
// by the compiler with the same expressions the kernels' fill loops use, so the table bits are the same (checked on
// the CPU for every word: xperm/p2/check/imgcheck.cpp). With OWN_R2_TAB_COPY=1 (compile-time) each work-group copies
// its table from the image (r2::tab_copy: 8 loads in flight per item, then 8 stores) instead of computing every
// entry (a byte load from the grid and an int -> float convert per entry; IQ1_S also a sign select). Only the fill
// changes; the table, the barrier and the row code are untouched. Card 5 (xperm bench_xdq, 128 work-groups of 512,
// outputs bit-identical on random and real rows): fill-only launches IQ1_S 8.62 -> 3.12 us, IQ2_S 6.25 -> 5.09,
// IQ2_XS 2.33 -> 1.80; between 128-register neighbours: IQ1_S gate+up 27.34 -> 23.50 us, IQ2_S gate+up at 128
// registers (xperm-1) 30.09 -> 28.96, IQ2_S down 17.97 -> 16.88, IQ2_XS down 15.78 -> 15.39. IQ2_XXS (neutral) and
// IQ3_XXS (its 1 KB table computes faster than it copies: +0.3 us) keep their computed fills.
#include <bit>
#include <cstdint>
#include "stage2/packet2/kernels/grids.hpp"

namespace r2tab {
template <unsigned N> struct Img {
    uint32_t v[N];
};
// tab[k] = float(grid64_byte(grid, k >> 3, k & 7)): byte j = k & 7 of the 64-bit entry k >> 3 (little-endian)
template <unsigned N> constexpr Img<N> grid8(const uint64_t *grid) {
    Img<N> t{};
    for (unsigned k = 0; k < N; ++k) t.v[k] = std::bit_cast<uint32_t>(float(unsigned(grid[k >> 3] >> (8 * (k & 7))) & 255u));
    return t;
}
// IQ1_S, TM = 3 (int16 entries): sbt[k] = int16_t(c == 0 ? 0 : c > 0 ? 0x3F80 : 0xBF80), c = int8 byte k of the grid;
// entry k is the low (k even) or high (k odd) half of word k >> 1 (little-endian), 16384 entries in 8192 words
constexpr Img<8192> iq1s_tm3() {
    Img<8192> t{};
    for (unsigned k = 0; k < 16384; ++k) {
        const int c = int(int8_t(uint8_t(iq3::iq1_s_grid[k >> 3] >> (8 * (k & 7)))));
        const uint16_t h = uint16_t(int16_t(c == 0 ? 0 : c > 0 ? 0x3F80 : 0xBF80));
        t.v[k >> 1] |= uint32_t(h) << (16 * (k & 1));
    }
    return t;
}
inline constexpr Img<4096> iq2_xs = grid8<4096>(iq3::iq2_xs_grid);
inline constexpr Img<8192> iq2_s = grid8<8192>(iq3::iq2_s_grid);
inline constexpr Img<8192> iq1_s3 = iq1s_tm3();
#if OWN_R2_TAB_COPY_XXS
// xperm-3: IQ2_XXS as grid8; IQ3_XXS tab[k] = float((grid[k >> 2] >> (8 * (k & 3))) & 255) (byte k & 3 of entry k >> 2)
template <unsigned N> constexpr Img<N> grid4(const uint32_t *grid) {
    Img<N> t{};
    for (unsigned k = 0; k < N; ++k) t.v[k] = std::bit_cast<uint32_t>(float((grid[k >> 2] >> (8 * (k & 3))) & 255));
    return t;
}
inline constexpr Img<2048> iq2_xxs = grid8<2048>(iq3::iq2_xxs_grid);
inline constexpr Img<1024> iq3_xxs = grid4<1024>(iq3::iq3_grid);
#endif
} // namespace r2tab
