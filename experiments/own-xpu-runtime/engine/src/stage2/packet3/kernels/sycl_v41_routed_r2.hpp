// Faster one-token routed expert kernels ("r2", 2026-11-11) for RoutedIQ2SP / RoutedIQ2XXSP / RoutedIQ2XSP /
// RoutedIQ3XXSP / RoutedIQ1SP (sycl_v41.hpp), on the same packed rows and tables, BITWISE the same outputs.
// Bench: tools/bench/bench_routed_r2.cpp (production against these at the six-card shapes, random and real rows).
//
// What changes is only integer work and data movement; the float operations per weight and their order are
// production's: v = (db * mag) with the sign xored into bit 31 (IQ1_S: dl * (code + de)), sum = sum + v * x,
// chunks ascending, then production's xor butterfly.
//  1. Per row, lane-parallel (one lane per chunk or per grid group, 32x fewer instructions than per weight):
//     aw = the 16-bit table byte offsets of the grid groups, two per dword (chunk m of a 16-chunk register in
//     halves 4m .. 4m + 3); ew = the chunk's sign word with lane l's sign in bit l (IQ3_XXS / IQ2_XS widen their
//     7-bit codes with the parity bit, the bit production's popcount picks); the scales.
//  2. Per weight: inline vISA `add (32) dst aw<1;8,0>:uw j` (lanes 8r .. 8r + 7 read half 4m + r: the group's
//     offset) + the lane's 4j, one local load, the scale multiply (IQ2_S / IQ2_XS: two SIMD16 muls by the low /
//     high nibble value as scalar operands), shl + bfn for the sign, mul x, add: 7-8 instructions (production
//     ~16, half of them the integer grid decode).
//  3. b forms read the row's words by block reads (as production) and hand each lane its words / bytes by
//     register-region moves (even2, odd2x, qhb, scb, ...) instead of per-lane gathers (the gathers' 64-bit
//     addresses and latency chains cost more than the decode saved).
//  4. d / e forms (IQ2_S, IQ2_XXS; EX = NoRows): a sub-group takes two consecutive rows of one slot first, so each
//     x block read feeds both rows (x traffic per row halved; these kernels are load-port bound), with the per-row
//     state built per 32-chunk segment to stay in 128 registers; e keeps the segment loop at run time (the fully
//     unrolled d spills at 20 blocks), d is used at 9 blocks. No sub-group runs more rows than in production.
//  5. Extra rows (EX: the stream mix's finish in gate + up with OWN_HC_FIN, the shared expert's dense rows) run
//     before a sub-group's routed rows, outside the row loop (R2_EX_ROWS), on the sub-groups that continue the
//     routed rows' round; production's in-loop placement kept the finish's code and a 64-bit division per row in
//     the hot loop (IQ1_S 26 -> 35.6 us with the row) and left the pair forms unusable with it (r3, 2026-11-11).
//  6. r4: the expert-major kernels of multi-token steps (RoutedU: checks, prompt blocks) with the b forms' decode
//     built per 4-block segment (RoutedU3, RU3*), named RoutedIQ2XXSU ... RoutedIQ1SU for the backend.
//  IQ1_S: table of the high 16 bits of float(code) (32 KB, as the I16 form) shifted up by an integer op instead of
//  a float convert: code is the same float, so code + de is.
// The selectors at the end (RoutedIQ2SPx, ...) pick the form per shape and EX; the backend dispatch names them.
// GPU note: the per-byte popcount form of widen4 gave wrong sign words on the device (IGC 2026.1); the SWAR form
// below is the one checked bitwise.
#pragma once
#include <type_traits>
#include <utility>
#include "stage2/packet3/kernels/sycl_v41.hpp"

namespace ops41sycl {
namespace r2 {

template <unsigned N, typename F> [[gnu::always_inline]] inline void sfor(F &&f) {
    [&]<unsigned... I>(std::integer_sequence<unsigned, I...>) {
        (f(std::integral_constant<unsigned, I>{}), ...);
    }(std::make_integer_sequence<unsigned, N>{});
}

// ag8<M>(a, j) = (16-bit view of a)[4M + (lane >> 3)] + j     M = 0..15 (chunk M of a 16-chunk register)
// ag4<M>(a, j) = (16-bit view of a)[8M + (lane >> 2)] + j     M = 0..7  (IQ3_XXS: 8 groups of 4 lanes)
template <unsigned M> inline uint32_t ag8(uint32_t a, uint32_t j);
template <unsigned M> inline uint32_t ag4(uint32_t a, uint32_t j);
// mp16<M>(d, m) = d[M + 16 (lane >> 4)] * m   M = 0..15 (lane M of d for lanes 0-15, lane 16 + M for lanes 16-31)
template <unsigned M> inline float mp16(float d, float m);
// ld8(a) = the byte at local-memory byte offset a, zero-extended (one d8u32 load, no byte moves after it)
inline uint32_t ld8(uint32_t a);
inline uint32_t ld16(uint32_t a);
// even2(w): lane l gets w's lane (l & ~1) (one region move)
inline uint32_t even2(uint32_t w);
// odd2x(a, b): lanes 0-15 get a's lanes 1, 3, ..., 31; lanes 16-31 get b's (two SIMD16 region moves)
inline uint32_t odd2x(uint32_t a, uint32_t b);
// even2x(a, b): lanes 0-15 get a's lanes 0, 2, ..., 30; lanes 16-31 get b's
inline uint32_t even2x(uint32_t a, uint32_t b);
// qhb<K>(m), m = 32 lanes of 4 bytes (128 bytes): lanes 0-15 get byte 32K + (l >> 1), lanes 16-31 byte 32K + 16 + ((l - 16) >> 1)
template <unsigned K> inline uint32_t qhb(uint32_t m);
// scb<K>(m): lanes j and 16 + j (j < 16) get byte 32K + 8 + 16 (j >> 3) + (j & 7)
template <unsigned K> inline uint32_t scb(uint32_t m);
// sb1<K>(m): lanes j and 16 + j (j < 16) get byte 16K + j
template <unsigned K> inline uint32_t sb1(uint32_t m);
// qsp<K>(w): lanes 0-15 get w's lanes 16K + (l >> 1), lanes 16-31 lanes 16K + 8 + ((l - 16) >> 1)  (K = 0, 1)
template <unsigned K> inline uint32_t qsp(uint32_t w);
// qhp<K>(m), m = 64 halves: lanes 0-15 get half 16K + (l >> 1), lanes 16-31 half 16K + 8 + ((l - 16) >> 1) (K = 0..3)
template <unsigned K> inline uint32_t qhp(uint32_t m);
// qh1<K>(m): lane l gets half 32K + l (K = 0, 1)
template <unsigned K> inline uint32_t qh1(uint32_t m);
// iq3q<K>(q0, q1): lanes 4m, 4m + 1 get q0's lane 8K + m, lanes 4m + 2, 4m + 3 get q1's (m = 0..7; four SIMD8 moves)
template <unsigned K> inline uint32_t iq3q(uint32_t q0, uint32_t q1);
#ifdef __SYCL_DEVICE_ONLY__
#define R2_MP(M, R, C)                                                                                              \
    template <> [[gnu::always_inline]] inline float mp16<M>(float d, float m) {                                    \
        float r;                                                                                                   \
        __asm__("mul (M1, 16) %0(0,0)<1> %1(0," #C ")<0;1,0> %2(0,0)<1;1,0>\n"                                  \
                "mul (M5, 16) %0(1,0)<1> %1(1," #C ")<0;1,0> %2(1,0)<1;1,0>\n"                                  \
                : "=rw"(r) : "rw"(d), "rw"(m));                                                                    \
        return r;                                                                                                  \
    }
[[gnu::always_inline]] inline uint32_t even2(uint32_t w) {
    uint32_t r;
    __asm__("mov (M1, 32) %0(0,0)<1> %1(0,0)<2;2,0>\n" : "=rw"(r) : "rw"(w));
    return r;
}
[[gnu::always_inline]] inline uint32_t odd2x(uint32_t a, uint32_t b) {
    uint32_t r;
    __asm__("mov (M1, 16) %0(0,0)<1> %1(0,1)<2;1,0>\n"
            "mov (M5, 16) %0(1,0)<1> %2(0,1)<2;1,0>\n"
            : "=rw"(r) : "rw"(a), "rw"(b));
    return r;
}
[[gnu::always_inline]] inline uint32_t even2x(uint32_t a, uint32_t b) {
    uint32_t r;
    __asm__("mov (M1, 16) %0(0,0)<1> %1(0,0)<2;1,0>\n"
            "mov (M5, 16) %0(1,0)<1> %2(0,0)<2;1,0>\n"
            : "=rw"(r) : "rw"(a), "rw"(b));
    return r;
}
#define R2_BYTES2(NAME, K, R0, C0, R1, C1, RG)                                                      \
    template <> [[gnu::always_inline]] inline uint32_t NAME<K>(uint32_t m) {                       \
        uint32_t r;                                                                                \
        __asm__("{\n.decl R2MB v_type=G type=ub num_elts=128 align=GRF alias=<%1,0>\n"             \
                "mov (M1, 16) %0(0,0)<1> R2MB(" #R0 "," #C0 ")" RG "\n"                            \
                "mov (M5, 16) %0(1,0)<1> R2MB(" #R1 "," #C1 ")" RG "\n}\n"                         \
                : "=rw"(r) : "rw"(m));                                                             \
        return r;                                                                                  \
    }
R2_BYTES2(qhb, 0, 0, 0, 0, 16, "<1;2,0>") R2_BYTES2(qhb, 1, 0, 32, 0, 48, "<1;2,0>")
R2_BYTES2(qhb, 2, 1, 0, 1, 16, "<1;2,0>") R2_BYTES2(qhb, 3, 1, 32, 1, 48, "<1;2,0>")
R2_BYTES2(scb, 0, 0, 8, 0, 8, "<16;8,1>") R2_BYTES2(scb, 1, 0, 40, 0, 40, "<16;8,1>")
R2_BYTES2(scb, 2, 1, 8, 1, 8, "<16;8,1>") R2_BYTES2(scb, 3, 1, 40, 1, 40, "<16;8,1>")
R2_BYTES2(sb1, 0, 0, 0, 0, 0, "<1;1,0>") R2_BYTES2(sb1, 1, 0, 16, 0, 16, "<1;1,0>")
R2_BYTES2(sb1, 2, 0, 32, 0, 32, "<1;1,0>") R2_BYTES2(sb1, 3, 0, 48, 0, 48, "<1;1,0>")
R2_BYTES2(sb1, 4, 1, 0, 1, 0, "<1;1,0>") R2_BYTES2(sb1, 5, 1, 16, 1, 16, "<1;1,0>")
R2_BYTES2(sb1, 6, 1, 32, 1, 32, "<1;1,0>") R2_BYTES2(sb1, 7, 1, 48, 1, 48, "<1;1,0>")
#undef R2_BYTES2
#define R2_HALVES2(NAME, K, TY, NE, R0, C0, R1, C1, RG)                                             \
    template <> [[gnu::always_inline]] inline uint32_t NAME<K>(uint32_t m) {                       \
        uint32_t r;                                                                                \
        __asm__("{\n.decl R2MH v_type=G type=" TY " num_elts=" NE " align=GRF alias=<%1,0>\n"       \
                "mov (M1, 16) %0(0,0)<1> R2MH(" #R0 "," #C0 ")" RG "\n"                            \
                "mov (M5, 16) %0(1,0)<1> R2MH(" #R1 "," #C1 ")" RG "\n}\n"                         \
                : "=rw"(r) : "rw"(m));                                                             \
        return r;                                                                                  \
    }
R2_HALVES2(qsp, 0, "ud", "32", 0, 0, 0, 8, "<1;2,0>") R2_HALVES2(qsp, 1, "ud", "32", 1, 0, 1, 8, "<1;2,0>")
R2_HALVES2(qhp, 0, "uw", "64", 0, 0, 0, 8, "<1;2,0>") R2_HALVES2(qhp, 1, "uw", "64", 0, 16, 0, 24, "<1;2,0>")
R2_HALVES2(qhp, 2, "uw", "64", 1, 0, 1, 8, "<1;2,0>") R2_HALVES2(qhp, 3, "uw", "64", 1, 16, 1, 24, "<1;2,0>")
R2_HALVES2(qh1, 0, "uw", "64", 0, 0, 0, 16, "<1;1,0>") R2_HALVES2(qh1, 1, "uw", "64", 1, 0, 1, 16, "<1;1,0>")
#undef R2_HALVES2
#define R2_IQ3Q(K, R, C)                                                                            \
    template <> [[gnu::always_inline]] inline uint32_t iq3q<K>(uint32_t q0, uint32_t q1) {         \
        uint32_t r;                                                                                \
        __asm__("mov (M1_NM, 8) %0(0,0)<4> %1(" #R "," #C ")<1;1,0>\n"                              \
                "mov (M1_NM, 8) %0(0,1)<4> %1(" #R "," #C ")<1;1,0>\n"                              \
                "mov (M1_NM, 8) %0(0,2)<4> %2(" #R "," #C ")<1;1,0>\n"                              \
                "mov (M1_NM, 8) %0(0,3)<4> %2(" #R "," #C ")<1;1,0>\n"                              \
                : "=rw"(r) : "rw"(q0), "rw"(q1));                                                  \
        return r;                                                                                  \
    }
R2_IQ3Q(0, 0, 0) R2_IQ3Q(1, 0, 8) R2_IQ3Q(2, 1, 0) R2_IQ3Q(3, 1, 8)
#undef R2_IQ3Q
[[gnu::always_inline]] inline uint32_t ld16(uint32_t a) {
    uint32_t r;
    __asm__ volatile("lsc_load.slm (M1, 32) %0:d16u32 flat[%1]:a32\n" : "=rw"(r) : "rw"(a));
    return r;
}
[[gnu::always_inline]] inline uint32_t ld8(uint32_t a) {
    uint32_t r;
    __asm__ volatile("lsc_load.slm (M1, 32) %0:d8u32 flat[%1]:a32\n" : "=rw"(r) : "rw"(a));
    return r;
}
#define R2_AG(NAME, W, M, R, C)                                                                                     \
    template <> [[gnu::always_inline]] inline uint32_t NAME<M>(uint32_t a, uint32_t j) {                           \
        uint32_t r;                                                                                                \
        __asm__("{\n.decl R2AW v_type=G type=uw num_elts=64 align=GRF alias=<%1,0>\n"                              \
                "add (M1, 32) %0(0,0)<1> R2AW(" #R "," #C ")<1;" #W ",0> %2(0,0)<1;1,0>\n}\n"                     \
                : "=rw"(r)                                                                                         \
                : "rw"(a), "rw"(j));                                                                               \
        return r;                                                                                                  \
    }
#else
#define R2_AG(NAME, W, M, R, C)                                                                                     \
    template <> inline uint32_t NAME<M>(uint32_t, uint32_t) { return 0; }
#define R2_MP(M, R, C)                                                                                              \
    template <> inline float mp16<M>(float, float) { return 0; }
inline uint32_t ld8(uint32_t) { return 0; }
inline uint32_t ld16(uint32_t) { return 0; }
inline uint32_t even2(uint32_t) { return 0; }
inline uint32_t odd2x(uint32_t, uint32_t) { return 0; }
inline uint32_t even2x(uint32_t, uint32_t) { return 0; }
template <unsigned K> inline uint32_t qhb(uint32_t) { return 0; }
template <unsigned K> inline uint32_t scb(uint32_t) { return 0; }
template <unsigned K> inline uint32_t sb1(uint32_t) { return 0; }
template <unsigned K> inline uint32_t qsp(uint32_t) { return 0; }
template <unsigned K> inline uint32_t qhp(uint32_t) { return 0; }
template <unsigned K> inline uint32_t qh1(uint32_t) { return 0; }
template <unsigned K> inline uint32_t iq3q(uint32_t, uint32_t) { return 0; }
#endif
R2_MP(0, 0, 0) R2_MP(1, 0, 1) R2_MP(2, 0, 2) R2_MP(3, 0, 3) R2_MP(4, 0, 4) R2_MP(5, 0, 5) R2_MP(6, 0, 6)
R2_MP(7, 0, 7) R2_MP(8, 0, 8) R2_MP(9, 0, 9) R2_MP(10, 0, 10) R2_MP(11, 0, 11) R2_MP(12, 0, 12) R2_MP(13, 0, 13)
R2_MP(14, 0, 14) R2_MP(15, 0, 15)
#undef R2_MP
R2_AG(ag8, 8, 0, 0, 0) R2_AG(ag8, 8, 1, 0, 4) R2_AG(ag8, 8, 2, 0, 8) R2_AG(ag8, 8, 3, 0, 12)
R2_AG(ag8, 8, 4, 0, 16) R2_AG(ag8, 8, 5, 0, 20) R2_AG(ag8, 8, 6, 0, 24) R2_AG(ag8, 8, 7, 0, 28)
R2_AG(ag8, 8, 8, 1, 0) R2_AG(ag8, 8, 9, 1, 4) R2_AG(ag8, 8, 10, 1, 8) R2_AG(ag8, 8, 11, 1, 12)
R2_AG(ag8, 8, 12, 1, 16) R2_AG(ag8, 8, 13, 1, 20) R2_AG(ag8, 8, 14, 1, 24) R2_AG(ag8, 8, 15, 1, 28)
R2_AG(ag4, 4, 0, 0, 0) R2_AG(ag4, 4, 1, 0, 8) R2_AG(ag4, 4, 2, 0, 16) R2_AG(ag4, 4, 3, 0, 24)
R2_AG(ag4, 4, 4, 1, 0) R2_AG(ag4, 4, 5, 1, 8) R2_AG(ag4, 4, 6, 1, 16) R2_AG(ag4, 4, 7, 1, 24)
#undef R2_AG

// the 7-bit sign codes of a chunk widened to 8 bits with their parity (bit 8q + j = sign of lane 8q + j)
// (32-bit SWAR parity: the per-byte popcount form came out wrong on the device, see notes in the bench output)
inline uint32_t widen4(uint32_t s0, uint32_t s1, uint32_t s2, uint32_t s3) {
    const uint32_t e = s0 | (s1 << 8) | (s2 << 16) | (s3 << 24); // 7-bit fields, bit 8q + 7 clear
    uint32_t t = e ^ (e >> 4);
    t ^= t >> 2;
    t ^= t >> 1; // bit 8q = parity of byte q
    return e | ((t & 0x01010101u) << 7);
}

// d of chunk 32k + lane's block (4k + lane / 8, clamped to NB - 1), picked from dv (lane b holds block b's d):
// four broadcasts and three selects instead of a per-lane load and half conversion
template <unsigned NB> [[gnu::always_inline]] inline float blk_d4(sycl::sub_group sg, float dv, unsigned k, unsigned lane) {
    const unsigned b0 = 4 * k < NB ? 4 * k : NB - 1, b1 = 4 * k + 1 < NB ? 4 * k + 1 : NB - 1;
    const unsigned b2 = 4 * k + 2 < NB ? 4 * k + 2 : NB - 1, b3 = 4 * k + 3 < NB ? 4 * k + 3 : NB - 1;
    const float s0 = sycl::select_from_group(sg, dv, b0), s1 = sycl::select_from_group(sg, dv, b1);
    const float s2 = sycl::select_from_group(sg, dv, b2), s3 = sycl::select_from_group(sg, dv, b3);
    return lane < 16 ? (lane < 8 ? s0 : s1) : (lane < 24 ? s2 : s3);
}
} // namespace r2

// production's row loop (OWN41_ROUTED_ROWS_BEGIN / END, sycl_v41.hpp) with the extra rows taken out of it: with
// P sub-groups, sub-group p takes the routed rows p, p + P, ... and, before them, the extra rows k with
// (S + k) mod P = p, S = the routed jobs' count (production spreads both over one list of positions; here the extra
// rows continue the routed rows' round, so every sub-group has as many jobs as in production). Each row is summed
// whole by one sub-group, so which sub-group runs it changes no value. The loop body no longer holds the extra
// row's code (register pressure) nor the position-to-row divisions.
#define R2_EX_ROWS(P_, p_, S_)                                                                   \
    if constexpr (!std::is_same_v<EX, NoRows>)                                                   \
        for (unsigned k_ = ((p_) + (P_) - (S_) % (P_)) % (P_); k_ < ex.n(); k_ += (P_)) ex.row(sg, lane, k_);
#define R2_ROWS_BEGIN(RB)                                                                        \
    const unsigned stride = (unsigned)(it.get_global_range(0) / 32), p0r_ = packed_row_id(it);   \
    const unsigned nr_ = (w2 ? 2 : 1) * nsl * rows;                                              \
    R2_EX_ROWS(stride, p0r_, nr_)                                                                \
    for (unsigned grp = p0r_; grp < nr_; grp += stride) {                                        \
        unsigned slot = grp / rows;                                                               \
        const unsigned r = grp % rows;                                                            \
        const uint8_t *wm_ = w;                                                                   \
        float *om_ = out;                                                                         \
        if (slot >= nsl) {                                                                        \
            slot -= nsl;                                                                          \
            wm_ = w2;                                                                             \
            om_ = out2;                                                                           \
        }                                                                                         \
        const uint8_t *row = wm_ + ((size_t)ids[slot] * rows + r) * (RB);                         \
        const uint32_t *rw = reinterpret_cast<const uint32_t *>(row);                             \
        const float *xs = x + (size_t)(slot / 6) * xtok + (per_slot_x ? (size_t)(slot % 6) * NB * 256 : 0); \
        float sum = 0;
#define R2_ROWS_END                                                                               \
        for (int w_ = 16; w_; w_ >>= 1) sum += sycl::select_from_group(sg, sum, (int)lane ^ w_); \
        if (lane == 0) om_[slot * rows + r] = sum;                                                \
    }

// b forms: the row's words come in by block reads (as production) and register-region moves hand each lane its
// words / bytes, instead of per-lane gathers. Same products in the same order as production.
template <unsigned NB, typename A, typename EX = NoRows> struct RoutedIQ2XXSPb {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static constexpr unsigned TAB = 2048;
    unsigned rows;
    bool per_slot_x;
    EX ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_xxs_grid, k >> 3, k & 7));
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), hs = lane & 1u;
        const uint32_t j4 = (lane & 7u) << 2;
        const unsigned ssh = 31u - lane;
        const char *tb = reinterpret_cast<const char *>(tab);
        constexpr size_t RB = ((size_t)NB * 70 + 15) & ~(size_t)15;
        constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NC = NB * 8, NA = (NC + 15) / 16, NE = (NC + 31) / 32;
        static_assert(NA == NR);
        R2_ROWS_BEGIN(RB)
        uint32_t wd[NR];
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) wd[k] = row_words<NW>(sg, rw, k, lane);
        uint32_t aw[NA];
#pragma unroll
        for (unsigned k = 0; k < NA; ++k) {
            const uint32_t lo = r2::even2(wd[k]), h = hs ? lo >> 16 : lo & 0xFFFFu;
            aw[k] = ((h & 255u) << 5) | ((h >> 8) << 21);
        }
        uint32_t ew[NE];
#pragma unroll
        for (unsigned k = 0; k < NE; ++k) ew[k] = r2::odd2x(wd[2 * k], wd[2 * k + 1 < NR ? 2 * k + 1 : NR - 1]);
        float dbc[NE];
        chunk_scales<NB>(sg, lane, reinterpret_cast<const uint16_t *>(row + (size_t)NB * 68),
                         reinterpret_cast<const uint32_t *>(row + (size_t)NB * 64), 0.25f, dbc);
        r2::sfor<NB>([&](auto bk) {
            constexpr unsigned blk = decltype(bk)::value;
            const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
            r2::sfor<8>([&](auto gk) {
                constexpr unsigned g = decltype(gk)::value, c = blk * 8 + g;
                const uint32_t ad = r2::ag8<c % 16>(aw[c / 16], j4);
                const float mag = *reinterpret_cast<const float *>(tb + ad);
                const float p = sycl::select_from_group(sg, dbc[c / 32], c % 32) * mag;
                const uint32_t e = sycl::select_from_group(sg, ew[c / 32], c % 32);
                const uint32_t sb = (e << ssh) & 0x80000000u;
                const float v = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p) ^ sb);
                sum = sum + v * xv[g];
            });
        });
        R2_ROWS_END
    }
};

template <unsigned NB, typename A, typename EX = NoRows> struct RoutedIQ2SPb {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static constexpr unsigned TAB = 8192;
    unsigned rows;
    bool per_slot_x;
    EX ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_s_grid, k >> 3, k & 7));
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), hs = lane & 1u;
        const uint32_t j4 = (lane & 7u) << 2;
        const unsigned ssh = 31u - lane;
        const char *tb = reinterpret_cast<const char *>(tab);
        constexpr size_t RB = ((size_t)NB * 82 + 15) & ~(size_t)15;
        constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NWM = NB * 4, NMR = (NWM + 31) / 32;
        constexpr unsigned NC = NB * 8, NA = (NC + 15) / 16, NE = (NC + 31) / 32;
        static_assert(NA == NR);
        R2_ROWS_BEGIN(RB)
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 80);
        const float dv = iq3::half(dp[lane < NB ? lane : NB - 1]); // lane b: block b's d
        uint32_t wd[NR], mr[NMR];
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) wd[k] = row_words<NW>(sg, rw, k, lane);
#pragma unroll
        for (unsigned k = 0; k < NMR; ++k) mr[k] = row_words<NWM>(sg, rw + NW, k, lane); // per block: qh[8], scales[8]
        uint32_t aw[NA];
        float dw[NA]; // lane j of register k: chunk 16k + (j & 15), scale nibble j >> 4
        r2::sfor<NA>([&](auto kk) {
            constexpr unsigned k = decltype(kk)::value;
            const uint32_t lo = r2::even2(wd[k]), qh = r2::qhb<k % 4>(mr[k / 4]);
            const uint32_t h = hs ? lo >> 16 : lo & 0xFFFFu, q = hs ? qh >> 4 : qh; // groups 2hs, 2hs + 1
            const uint32_t i0 = (h & 255u) | ((q & 3u) << 8), i1 = (h >> 8) | (((q >> 2) & 3u) << 8);
            aw[k] = (i0 << 5) | (i1 << 21);
            constexpr unsigned B0 = 2 * k < NB ? 2 * k : NB - 1, B1 = 2 * k + 1 < NB ? 2 * k + 1 : NB - 1;
            const float d0 = sycl::select_from_group(sg, dv, B0), d1 = sycl::select_from_group(sg, dv, B1);
            const float d = (lane & 8u) ? d1 : d0;
            const uint32_t sc = r2::scb<k % 4>(mr[k / 4]);
            dw[k] = (d * (0.5f + float((sc >> (4 * (lane >> 4))) & 15u))) * 0.25f;
        });
        uint32_t ew[NE];
#pragma unroll
        for (unsigned k = 0; k < NE; ++k) ew[k] = r2::odd2x(wd[2 * k], wd[2 * k + 1 < NR ? 2 * k + 1 : NR - 1]);
        r2::sfor<NB>([&](auto bk) {
            constexpr unsigned blk = decltype(bk)::value;
            const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
            r2::sfor<8>([&](auto gk) {
                constexpr unsigned g = decltype(gk)::value, c = blk * 8 + g;
                const uint32_t ad = r2::ag8<c % 16>(aw[c / 16], j4);
                const float mag = *reinterpret_cast<const float *>(tb + ad);
                const float p = r2::mp16<c % 16>(dw[c / 16], mag);
                const uint32_t e = sycl::select_from_group(sg, ew[c / 32], c % 32);
                const uint32_t sb = (e << ssh) & 0x80000000u;
                const float v = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p) ^ sb);
                sum = sum + v * xv[g];
            });
        });
        R2_ROWS_END
    }
};

template <unsigned NB, typename A, typename EX = NoRows> struct RoutedIQ2XSPb {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static constexpr unsigned TAB = 4096;
    unsigned rows;
    bool per_slot_x;
    EX ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_xs_grid, k >> 3, k & 7));
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), hs = lane & 1u;
        const uint32_t j4 = (lane & 7u) << 2;
        const unsigned ssh = 31u - lane;
        const char *tb = reinterpret_cast<const char *>(tab);
        constexpr size_t RB = ((size_t)NB * 74 + 15) & ~(size_t)15;
        constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NWS = NB * 2, NSR = (NWS + 31) / 32;
        constexpr unsigned NC = NB * 8, NE = (NC + 31) / 32;
        R2_ROWS_BEGIN(RB)
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 72);
        const float dv = iq3::half(dp[lane < NB ? lane : NB - 1]); // lane b: block b's d
        uint32_t wd[NR], sr[NSR];
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) wd[k] = row_words<NW>(sg, rw, k, lane);
#pragma unroll
        for (unsigned k = 0; k < NSR; ++k) sr[k] = row_words<NWS>(sg, rw + NW, k, lane); // one scale byte per chunk
        uint32_t aw[NR]; // word 32k + l = chunk 16k + l / 2, groups 2 (l & 1), 2 (l & 1) + 1: the packed row's own order
        float dw[NR];    // lane j of register k: chunk 16k + (j & 15), scale nibble j >> 4
        r2::sfor<NR>([&](auto kk) {
            constexpr unsigned k = decltype(kk)::value;
            const uint32_t a = wd[k];
            aw[k] = ((a & 511u) << 5) | (((a >> 16) & 511u) << 21);
            constexpr unsigned B0 = 2 * k < NB ? 2 * k : NB - 1, B1 = 2 * k + 1 < NB ? 2 * k + 1 : NB - 1;
            const float d0 = sycl::select_from_group(sg, dv, B0), d1 = sycl::select_from_group(sg, dv, B1);
            const float d = (lane & 8u) ? d1 : d0;
            const uint32_t sc = r2::sb1<k % 8>(sr[k / 8]);
            dw[k] = (d * (0.5f + float((sc >> (4 * (lane >> 4))) & 15u))) * 0.25f;
        });
        uint32_t ew[NE];
#pragma unroll
        for (unsigned k = 0; k < NE; ++k) {
            const uint32_t wa = wd[2 * k], wb = wd[2 * k + 1 < NR ? 2 * k + 1 : NR - 1];
            const uint32_t a0 = r2::even2x(wa, wb), a1 = r2::odd2x(wa, wb);
            ew[k] = r2::widen4((a0 >> 9) & 127u, a0 >> 25, (a1 >> 9) & 127u, a1 >> 25);
        }
        r2::sfor<NB>([&](auto bk) {
            constexpr unsigned blk = decltype(bk)::value;
            const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
            r2::sfor<8>([&](auto gk) {
                constexpr unsigned g = decltype(gk)::value, c = blk * 8 + g;
                const uint32_t ad = r2::ag8<c % 16>(aw[c / 16], j4);
                const float mag = *reinterpret_cast<const float *>(tb + ad);
                const float p = r2::mp16<c % 16>(dw[c / 16], mag);
                const uint32_t e = sycl::select_from_group(sg, ew[c / 32], c % 32);
                const uint32_t sb = (e << ssh) & 0x80000000u;
                const float v = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p) ^ sb);
                sum = sum + v * xv[g];
            });
        });
        R2_ROWS_END
    }
};

// IQ1_S b form: qs words and qh halves by block reads, register-region moves per lane. TM: table mode, 0 = int16
// codes, 1 = bytes of code + 1 with de - 1 (16 KB; slower), 3 = high 16 bits of float(code) (default)
template <unsigned NB, typename A, int TM = 3, typename EX = NoRows> struct RoutedIQ1SPb {
    static constexpr bool U8 = TM == 1;
    static_assert(TM == 0 || TM == 1 || TM == 3, "table modes 0, 1, 3");
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static constexpr unsigned TAB = U8 ? 4096 : 8192;
    unsigned rows;
    bool per_slot_x;
    EX ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        uint8_t *ubt = reinterpret_cast<uint8_t *>(tab);
        int16_t *sbt = reinterpret_cast<int16_t *>(tab);
        for (unsigned k = it.get_local_linear_id(); k < 16384; k += (unsigned)it.get_local_range(0)) {
            const int c = int(int8_t(uint8_t(grid64_byte(iq3::iq1_s_grid, k >> 3, k & 7))));
            if constexpr (U8) ubt[k] = uint8_t(c + 1);
            else if constexpr (TM == 3) sbt[k] = int16_t(c == 0 ? 0 : c > 0 ? 0x3F80 : 0xBF80); // float(c) >> 16
            else sbt[k] = int16_t(c);
        }
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), hs = lane & 1u;
        constexpr unsigned SH = U8 ? 3 : 4; // bytes per grid entry: 8 or 16
        const uint32_t jb = (lane & 7u) << (SH - 3);
        const char *tb = reinterpret_cast<const char *>(tab);
        constexpr size_t RB = ((size_t)NB * 50 + 15) & ~(size_t)15;
        constexpr unsigned NC = NB * 8, NA = (NC + 15) / 16, NE = (NC + 31) / 32;
        constexpr unsigned NWQ = NB * 8, NQR = (NWQ + 31) / 32, NWH = NB * 4, NHR = (NWH + 31) / 32;
        R2_ROWS_BEGIN(RB)
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 48);
        const float dv = iq3::half(dp[lane < NB ? lane : NB - 1]); // lane b: block b's d
        uint32_t wq[NQR], wh[NHR];
#pragma unroll
        for (unsigned k = 0; k < NQR; ++k) wq[k] = row_words<NWQ>(sg, rw, k, lane);
#pragma unroll
        for (unsigned k = 0; k < NHR; ++k) wh[k] = row_words<NWH>(sg, rw + NWQ, k, lane); // qh: one half per chunk
        uint32_t aw[NA];
        r2::sfor<NA>([&](auto kk) {
            constexpr unsigned k = decltype(kk)::value;
            const uint32_t qs = r2::qsp<k % 2>(wq[k / 2]), qh = r2::qhp<k % 4>(wh[k / 4]);
            const uint32_t h = hs ? qs >> 16 : qs & 0xFFFFu, q = hs ? qh >> 6 : qh; // groups 2hs, 2hs + 1
            const uint32_t i0 = (h & 255u) | ((q & 7u) << 8), i1 = (h >> 8) | (((q >> 3) & 7u) << 8);
            aw[k] = (i0 << SH) | (i1 << (16 + SH));
        });
        float dlr[NE], der[NE];
        r2::sfor<NE>([&](auto kk) {
            constexpr unsigned k = decltype(kk)::value;
            const uint32_t qh = r2::qh1<k % 2>(wh[k / 2]);
            dlr[k] = r2::blk_d4<NB>(sg, dv, k, lane) * float(2 * ((qh >> 12) & 7) + 1);
            if constexpr (U8) der[k] = (qh & 0x8000) ? -1.125f : -0.875f; // de - 1, exact
            else der[k] = (qh & 0x8000) ? -0.125f : 0.125f;
        });
        r2::sfor<NB>([&](auto bk) {
            constexpr unsigned blk = decltype(bk)::value;
            const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
            r2::sfor<8>([&](auto gk) {
                constexpr unsigned g = decltype(gk)::value, c = blk * 8 + g;
                const uint32_t ad = r2::ag8<c % 16>(aw[c / 16], jb);
                const float dl = sycl::select_from_group(sg, dlr[c / 32], c % 32);
                float code;
                if constexpr (U8) code = float(r2::ld8(ad));
                else if constexpr (TM == 3) code = sycl::bit_cast<float>(r2::ld16(ad) << 16);
                else code = float(int(*reinterpret_cast<const int16_t *>(tb + ad)));
                const float de = sycl::select_from_group(sg, der[c / 32], c % 32);
                sum = sum + (dl * (code + de)) * xv[g];
            });
        });
        R2_ROWS_END
    }
};


// IQ3_XXS b form: chunk c's three words (3c, 3c + 1, 3c + 2) by one 3-word load per lane (lane = chunk), then
// strided register moves give the grid lanes their index words.
template <unsigned NB, typename A, typename EX = NoRows> struct RoutedIQ3XXSPb {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static constexpr unsigned TAB = 1024;
    unsigned rows;
    bool per_slot_x;
    EX ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float((iq3::iq3_grid[k >> 2] >> (8 * (k & 3))) & 255);
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), hs = lane & 1u;
        const uint32_t jj4 = (lane & 3u) << 2;
        const unsigned ssh = 31u - lane;
        const char *tb = reinterpret_cast<const char *>(tab);
        constexpr size_t RB = ((size_t)NB * 98 + 15) & ~(size_t)15;
        constexpr unsigned NC = NB * 8, NA = (NC + 7) / 8, NE = (NC + 31) / 32;
        R2_ROWS_BEGIN(RB)
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 96);
        const float dv = iq3::half(dp[lane < NB ? lane : NB - 1]); // lane b: block b's d
        uint32_t q0[NE], q1[NE], ew[NE];
        float dbw[NE];
#pragma unroll
        for (unsigned k = 0; k < NE; ++k) {
            const unsigned c = 32 * k + lane < NC ? 32 * k + lane : NC - 1;
            const uint32_t *cp = rw + 3 * c; // = 24 (c >> 3) + 3 (c & 7)
            q0[k] = cp[0];
            q1[k] = cp[1];
            const uint32_t sw = cp[2];
            ew[k] = r2::widen4(sw & 127u, (sw >> 7) & 127u, (sw >> 14) & 127u, (sw >> 21) & 127u);
            dbw[k] = (r2::blk_d4<NB>(sg, dv, k, lane) * (0.5f + float(sw >> 28))) * 0.5f;
        }
        uint32_t aw[NA]; // dword l of register k: chunk 8k + l / 4, groups 2 (l & 3), 2 (l & 3) + 1
        r2::sfor<NA>([&](auto kk) {
            constexpr unsigned k = decltype(kk)::value;
            const uint32_t q = r2::iq3q<k % 4>(q0[k / 4], q1[k / 4]), h = hs ? q >> 16 : q & 0xFFFFu;
            aw[k] = ((h & 255u) << 4) | ((h >> 8) << 20);
        });
        r2::sfor<NB>([&](auto bk) {
            constexpr unsigned blk = decltype(bk)::value;
            const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
            r2::sfor<8>([&](auto gk) {
                constexpr unsigned g = decltype(gk)::value, c = blk * 8 + g;
                const uint32_t ad = r2::ag4<c % 8>(aw[c / 8], jj4);
                const float mag = *reinterpret_cast<const float *>(tb + ad);
                const float db = sycl::select_from_group(sg, dbw[c / 32], c % 32);
                const uint32_t e = sycl::select_from_group(sg, ew[c / 32], c % 32);
                const uint32_t sb = (e << ssh) & 0x80000000u;
                const float v = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ sb);
                sum = sum + v * xv[g];
            });
        });
        R2_ROWS_END
    }
};

// d forms: row pairs sharing each x block read, with the per-row state built per segment of 32 chunks (4 blocks)
// so that two rows fit in 128 registers. Schedule: extra rows first as in R2_ROWS_BEGIN, then sub-group p takes the
// row pairs (2q, 2q + 1),
// q = p + kP < npair (consecutive rows of one slot: rows per expert are even, else no pairs), then single rows
// 2 npair + p + kP. npair <= P * (rmax / 2), rmax = production's rows per sub-group, so no sub-group runs more rows
// than in production. Per row: the b form's products and sums in the b form's order (bitwise).
#define R2_PAIR_SCHED()                                                                         \
    const unsigned P = (unsigned)(it.get_global_range(0) / 32), p0 = packed_row_id(it);                   \
    const unsigned nr = (w2 ? 2 : 1) * nsl * rows, rmax = (nr + P - 1) / P, pc = P * (rmax / 2);         \
    const unsigned npair = rows % 2 ? 0 : pc < nr / 2 ? pc : nr / 2; /* at most rmax rows per sub-group */ \
    R2_EX_ROWS(P, p0, npair + (nr - 2 * npair)) /* after the pairs' and single rows' rounds */            \
    auto where = [&](unsigned grp, const uint8_t *&row, float *&dst, const float *&xs) {                  \
        unsigned slot = grp / rows;                                                                       \
        const unsigned r = grp % rows;                                                                    \
        const uint8_t *wm = w;                                                                            \
        float *om = out;                                                                                  \
        if (slot >= nsl) {                                                                                \
            slot -= nsl;                                                                                  \
            wm = w2;                                                                                      \
            om = out2;                                                                                    \
        }                                                                                                 \
        row = wm + ((size_t)ids[slot] * rows + r) * RB;                                                   \
        dst = om + slot * rows + r;                                                                       \
        xs = x + (size_t)(slot / 6) * xtok + (per_slot_x ? (size_t)(slot % 6) * NB * 256 : 0);            \
    };                                                                                                    \
    auto red = [&](float s_) {                                                                            \
        for (int w_ = 16; w_; w_ >>= 1) s_ += sycl::select_from_group(sg, s_, (int)lane ^ w_);            \
        return s_;                                                                                        \
    };                                                                                                    \
    for (unsigned q_ = p0; q_ < npair; q_ += P) {                                                         \
        const uint8_t *row;                                                                               \
        float *dst;                                                                                       \
        const float *xs;                                                                                  \
        where(2 * q_, row, dst, xs);                                                                      \
        float sa = 0, sb = 0;                                                                             \
        body2(row, xs, sa, sb);                                                                           \
        sa = red(sa);                                                                                     \
        sb = red(sb);                                                                                     \
        if (lane == 0) {                                                                                  \
            dst[0] = sa;                                                                                  \
            dst[1] = sb;                                                                                  \
        }                                                                                                 \
    }                                                                                                     \
    for (unsigned q_ = 2 * npair + p0; q_ < nr; q_ += P) {                                                \
        const uint8_t *row;                                                                               \
        float *dst;                                                                                       \
        const float *xs;                                                                                  \
        where(q_, row, dst, xs);                                                                          \
        float sa = 0;                                                                                     \
        body1(row, xs, sa);                                                                               \
        sa = red(sa);                                                                                     \
        if (lane == 0) dst[0] = sa;                                                                       \
    }

template <unsigned NB, typename A, typename EX = NoRows> struct RoutedIQ2SPd {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static constexpr unsigned TAB = 8192;
    unsigned rows;
    bool per_slot_x;
    EX ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    static constexpr size_t RB = ((size_t)NB * 82 + 15) & ~(size_t)15;
    static constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NWM = NB * 4, NMR = (NWM + 31) / 32;
    static constexpr unsigned NC = NB * 8, NS = (NC + 31) / 32; // segments of 32 chunks
    struct Rw {
        const uint32_t *rw;
        float dv;
        uint32_t mr[NMR];
    };
    struct Sg {
        uint32_t aw[2], ew;
        float dw[2];
    };
    [[gnu::always_inline]] static void rinit(sycl::sub_group sg, unsigned lane, const uint8_t *row, Rw &t) {
        t.rw = reinterpret_cast<const uint32_t *>(row);
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 80);
        t.dv = iq3::half(dp[lane < NB ? lane : NB - 1]);
#pragma unroll
        for (unsigned k = 0; k < NMR; ++k) t.mr[k] = row_words<NWM>(sg, t.rw + NW, k, lane);
    }
    template <unsigned S>
    [[gnu::always_inline]] static void sprep(sycl::sub_group sg, unsigned lane, unsigned hs, const Rw &t, Sg &u) {
        const uint32_t w0 = row_words<NW>(sg, t.rw, 2 * S, lane);
        const uint32_t w1 = 2 * S + 1 < NR ? row_words<NW>(sg, t.rw, 2 * S + 1, lane) : w0;
        r2::sfor<2>([&](auto jj) {
            constexpr unsigned j = decltype(jj)::value, k = 2 * S + j;
            const uint32_t lo = r2::even2(j ? w1 : w0), qh = r2::qhb<k % 4>(t.mr[k / 4]);
            const uint32_t h = hs ? lo >> 16 : lo & 0xFFFFu, q = hs ? qh >> 4 : qh;
            const uint32_t i0 = (h & 255u) | ((q & 3u) << 8), i1 = (h >> 8) | (((q >> 2) & 3u) << 8);
            u.aw[j] = (i0 << 5) | (i1 << 21);
            constexpr unsigned B0 = 2 * k < NB ? 2 * k : NB - 1, B1 = 2 * k + 1 < NB ? 2 * k + 1 : NB - 1;
            const float d0 = sycl::select_from_group(sg, t.dv, B0), d1 = sycl::select_from_group(sg, t.dv, B1);
            const float d = (lane & 8u) ? d1 : d0;
            const uint32_t sc = r2::scb<k % 4>(t.mr[k / 4]);
            u.dw[j] = (d * (0.5f + float((sc >> (4 * (lane >> 4))) & 15u))) * 0.25f;
        });
        u.ew = r2::odd2x(w0, w1);
    }
    template <unsigned C>
    [[gnu::always_inline]] static float wv(sycl::sub_group sg, const Sg &u, const char *tb, uint32_t j4, unsigned ssh) {
        constexpr unsigned m = C % 32;
        const uint32_t ad = r2::ag8<m % 16>(u.aw[m / 16], j4);
        const float mag = *reinterpret_cast<const float *>(tb + ad);
        const float p = r2::mp16<m % 16>(u.dw[m / 16], mag);
        const uint32_t e = sycl::select_from_group(sg, u.ew, m);
        const uint32_t sb = (e << ssh) & 0x80000000u;
        return sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p) ^ sb);
    }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_s_grid, k >> 3, k & 7));
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), hs = lane & 1u;
        const uint32_t j4 = (lane & 7u) << 2;
        const unsigned ssh = 31u - lane;
        const char *tb = reinterpret_cast<const char *>(tab);
        auto body2 = [&](const uint8_t *row, const float *xs, float &sa, float &sb) {
                Rw ra, rb;
                rinit(sg, lane, row, ra);
                rinit(sg, lane, row + RB, rb);
                r2::sfor<NS>([&](auto sk) {
                    constexpr unsigned S = decltype(sk)::value, B0 = 4 * S, B1 = 4 * S + 4 < NB ? 4 * S + 4 : NB;
                    Sg ua, ub;
                    sprep<S>(sg, lane, hs, ra, ua);
                    sprep<S>(sg, lane, hs, rb, ub);
                    r2::sfor<B1 - B0>([&](auto bk) {
                        constexpr unsigned blk = B0 + decltype(bk)::value;
                        const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
                        r2::sfor<8>([&](auto gk) {
                            constexpr unsigned g = decltype(gk)::value, c = blk * 8 + g;
                            const float va = wv<c>(sg, ua, tb, j4, ssh), vb = wv<c>(sg, ub, tb, j4, ssh);
                            sa = sa + va * xv[g];
                            sb = sb + vb * xv[g];
                        });
                    });
                });
        };
        auto body1 = [&](const uint8_t *row, const float *xs, float &sa) {
                Rw ra;
                rinit(sg, lane, row, ra);
                r2::sfor<NS>([&](auto sk) {
                    constexpr unsigned S = decltype(sk)::value, B0 = 4 * S, B1 = 4 * S + 4 < NB ? 4 * S + 4 : NB;
                    Sg ua;
                    sprep<S>(sg, lane, hs, ra, ua);
                    r2::sfor<B1 - B0>([&](auto bk) {
                        constexpr unsigned blk = B0 + decltype(bk)::value;
                        const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
                        r2::sfor<8>([&](auto gk) {
                            constexpr unsigned g = decltype(gk)::value, c = blk * 8 + g;
                            sa = sa + wv<c>(sg, ua, tb, j4, ssh) * xv[g];
                        });
                    });
                });
        };
        R2_PAIR_SCHED()
    }
};

template <unsigned NB, typename A, typename EX = NoRows> struct RoutedIQ2XXSPd {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static constexpr unsigned TAB = 2048;
    unsigned rows;
    bool per_slot_x;
    EX ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    static constexpr size_t RB = ((size_t)NB * 70 + 15) & ~(size_t)15;
    static constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NC = NB * 8, NS = (NC + 31) / 32;
    static_assert(NB <= 32);
    struct Rw {
        const uint32_t *rw;
        float dl;
        uint32_t sw;
    };
    struct Sg {
        uint32_t aw[2], ew;
        float db;
    };
    [[gnu::always_inline]] static void rinit(sycl::sub_group sg, unsigned lane, const uint8_t *row, Rw &t) {
        t.rw = reinterpret_cast<const uint32_t *>(row);
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 68);
        const uint32_t *scw = reinterpret_cast<const uint32_t *>(row + (size_t)NB * 64);
        t.dl = lane < NB ? iq3::half(dp[lane]) : 0.0f; // as chunk_scales
        t.sw = lane < NB ? scw[lane] : 0u;
    }
    template <unsigned S>
    [[gnu::always_inline]] static void sprep(sycl::sub_group sg, unsigned lane, unsigned hs, const Rw &t, Sg &u) {
        const uint32_t w0 = row_words<NW>(sg, t.rw, 2 * S, lane);
        const uint32_t w1 = 2 * S + 1 < NR ? row_words<NW>(sg, t.rw, 2 * S + 1, lane) : w0;
        r2::sfor<2>([&](auto jj) {
            constexpr unsigned j = decltype(jj)::value;
            const uint32_t lo = r2::even2(j ? w1 : w0), h = hs ? lo >> 16 : lo & 0xFFFFu;
            u.aw[j] = ((h & 255u) << 5) | ((h >> 8) << 21);
        });
        u.ew = r2::odd2x(w0, w1);
        // chunk_scales' expression for chunk c = 32S + lane, block b = c / 8 (clamped), from four broadcasts
        constexpr unsigned b0 = 4 * S < NB ? 4 * S : NB - 1, b1 = 4 * S + 1 < NB ? 4 * S + 1 : NB - 1;
        constexpr unsigned b2 = 4 * S + 2 < NB ? 4 * S + 2 : NB - 1, b3 = 4 * S + 3 < NB ? 4 * S + 3 : NB - 1;
        const float e0 = sycl::select_from_group(sg, t.dl, b0), e1 = sycl::select_from_group(sg, t.dl, b1);
        const float e2 = sycl::select_from_group(sg, t.dl, b2), e3 = sycl::select_from_group(sg, t.dl, b3);
        const uint32_t s0 = sycl::select_from_group(sg, t.sw, b0), s1 = sycl::select_from_group(sg, t.sw, b1);
        const uint32_t s2 = sycl::select_from_group(sg, t.sw, b2), s3 = sycl::select_from_group(sg, t.sw, b3);
        const float d = lane < 16 ? (lane < 8 ? e0 : e1) : (lane < 24 ? e2 : e3);
        const uint32_t sc = lane < 16 ? (lane < 8 ? s0 : s1) : (lane < 24 ? s2 : s3);
        u.db = (d * (0.5f + float((sc >> (4 * (lane & 7u))) & 15u))) * 0.25f;
    }
    template <unsigned C>
    [[gnu::always_inline]] static float wv(sycl::sub_group sg, const Sg &u, const char *tb, uint32_t j4, unsigned ssh) {
        constexpr unsigned m = C % 32;
        const uint32_t ad = r2::ag8<m % 16>(u.aw[m / 16], j4);
        const float mag = *reinterpret_cast<const float *>(tb + ad);
        const float p = sycl::select_from_group(sg, u.db, m) * mag;
        const uint32_t e = sycl::select_from_group(sg, u.ew, m);
        const uint32_t sb = (e << ssh) & 0x80000000u;
        return sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p) ^ sb);
    }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_xxs_grid, k >> 3, k & 7));
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), hs = lane & 1u;
        const uint32_t j4 = (lane & 7u) << 2;
        const unsigned ssh = 31u - lane;
        const char *tb = reinterpret_cast<const char *>(tab);
        auto body2 = [&](const uint8_t *row, const float *xs, float &sa, float &sb) {
                Rw ra, rb;
                rinit(sg, lane, row, ra);
                rinit(sg, lane, row + RB, rb);
                r2::sfor<NS>([&](auto sk) {
                    constexpr unsigned S = decltype(sk)::value, B0 = 4 * S, B1 = 4 * S + 4 < NB ? 4 * S + 4 : NB;
                    Sg ua, ub;
                    sprep<S>(sg, lane, hs, ra, ua);
                    sprep<S>(sg, lane, hs, rb, ub);
                    r2::sfor<B1 - B0>([&](auto bk) {
                        constexpr unsigned blk = B0 + decltype(bk)::value;
                        const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
                        r2::sfor<8>([&](auto gk) {
                            constexpr unsigned g = decltype(gk)::value, c = blk * 8 + g;
                            const float va = wv<c>(sg, ua, tb, j4, ssh), vb = wv<c>(sg, ub, tb, j4, ssh);
                            sa = sa + va * xv[g];
                            sb = sb + vb * xv[g];
                        });
                    });
                });
        };
        auto body1 = [&](const uint8_t *row, const float *xs, float &sa) {
                Rw ra;
                rinit(sg, lane, row, ra);
                r2::sfor<NS>([&](auto sk) {
                    constexpr unsigned S = decltype(sk)::value, B0 = 4 * S, B1 = 4 * S + 4 < NB ? 4 * S + 4 : NB;
                    Sg ua;
                    sprep<S>(sg, lane, hs, ra, ua);
                    r2::sfor<B1 - B0>([&](auto bk) {
                        constexpr unsigned blk = B0 + decltype(bk)::value;
                        const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
                        r2::sfor<8>([&](auto gk) {
                            constexpr unsigned g = decltype(gk)::value, c = blk * 8 + g;
                            sa = sa + wv<c>(sg, ua, tb, j4, ssh) * xv[g];
                        });
                    });
                });
        };
        R2_PAIR_SCHED()
    }
};

// e forms: the d forms with the segment loop kept as a runtime loop (#pragma unroll 1) so that the compiler cannot
// hoist the next segments' loads and keep them live (the fully unrolled d forms spill at 20 blocks). IQ2_S walks
// segment pairs (the meta register of 4 segments' qh / scale bytes, its 32-byte quarter by parity), IQ2_XXS single
// segments; the tail segments of a row are compile-time.
template <unsigned NB, typename A, typename EX = NoRows> struct RoutedIQ2SPe {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static constexpr unsigned TAB = 8192;
    unsigned rows;
    bool per_slot_x;
    EX ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    static constexpr size_t RB = ((size_t)NB * 82 + 15) & ~(size_t)15;
    static constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NWM = NB * 4;
    static constexpr unsigned NC = NB * 8, NS = (NC + 31) / 32, NFP = NB / 8; // full segment pairs (8 blocks)
    struct Sg {
        uint32_t aw[2], ew;
        float dw[2];
    };
    // segment S = 2T + SP (SP compile-time): row words 64S .. 64S + 63, meta quarter SP of meta register T
    template <unsigned SP>
    [[gnu::always_inline]] static void sprep(sycl::sub_group sg, unsigned lane, unsigned hs, const uint32_t *rw,
                                             float dv, uint32_t mr, unsigned S, Sg &u) {
        const uint32_t w0 = row_words<NW>(sg, rw, 2 * S, lane);
        const uint32_t w1 = 2 * S + 1 < NR ? row_words<NW>(sg, rw, 2 * S + 1, lane) : w0;
        r2::sfor<2>([&](auto jj) {
            constexpr unsigned j = decltype(jj)::value, kq = 2 * SP + j; // k % 4
            const unsigned k = 2 * S + j;
            const uint32_t lo = r2::even2(j ? w1 : w0), qh = r2::qhb<kq>(mr);
            const uint32_t h = hs ? lo >> 16 : lo & 0xFFFFu, q = hs ? qh >> 4 : qh;
            const uint32_t i0 = (h & 255u) | ((q & 3u) << 8), i1 = (h >> 8) | (((q >> 2) & 3u) << 8);
            u.aw[j] = (i0 << 5) | (i1 << 21);
            const unsigned B0 = 2 * k < NB ? 2 * k : NB - 1, B1 = 2 * k + 1 < NB ? 2 * k + 1 : NB - 1;
            const float d0 = sycl::select_from_group(sg, dv, B0), d1 = sycl::select_from_group(sg, dv, B1);
            const float d = (lane & 8u) ? d1 : d0;
            const uint32_t sc = r2::scb<kq>(mr);
            u.dw[j] = (d * (0.5f + float((sc >> (4 * (lane >> 4))) & 15u))) * 0.25f;
        });
        u.ew = r2::odd2x(w0, w1);
    }
    template <unsigned M>
    [[gnu::always_inline]] static float wv(sycl::sub_group sg, const Sg &u, const char *tb, uint32_t j4, unsigned ssh) {
        const uint32_t ad = r2::ag8<M % 16>(u.aw[M / 16], j4);
        const float mag = *reinterpret_cast<const float *>(tb + ad);
        const float p = r2::mp16<M % 16>(u.dw[M / 16], mag);
        const uint32_t e = sycl::select_from_group(sg, u.ew, M);
        const uint32_t sb = (e << ssh) & 0x80000000u;
        return sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p) ^ sb);
    }
    // NBS blocks of segment S (compile-time count), rows A (and B when TWO)
    template <unsigned NBS, bool TWO>
    [[gnu::always_inline]] static void seg(sycl::sub_group sg, const float *xs, unsigned S, const Sg &ua, const Sg &ub,
                                           const char *tb, uint32_t j4, unsigned ssh, float &sa, float &sb) {
        r2::sfor<NBS>([&](auto bk) {
            constexpr unsigned bb = decltype(bk)::value;
            const auto xv = sg_bloadN<8>(sg, xs + (size_t)(4 * S + bb) * 256);
            r2::sfor<8>([&](auto gk) {
                constexpr unsigned g = decltype(gk)::value, m = 8 * bb + g;
                if constexpr (TWO) {
                    const float va = wv<m>(sg, ua, tb, j4, ssh), vb = wv<m>(sg, ub, tb, j4, ssh);
                    sa = sa + va * xv[g];
                    sb = sb + vb * xv[g];
                } else {
                    sa = sa + wv<m>(sg, ua, tb, j4, ssh) * xv[g];
                }
            });
        });
    }
    template <bool TWO>
    [[gnu::always_inline]] static void rowrun(sycl::sub_group sg, unsigned lane, unsigned hs, const uint8_t *row,
                                              const float *xs, const char *tb, uint32_t j4, unsigned ssh, float &sa,
                                              float &sb) {
        const uint32_t *ra = reinterpret_cast<const uint32_t *>(row), *rb = reinterpret_cast<const uint32_t *>(row + RB);
        const uint16_t *dpa = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 80);
        const uint16_t *dpb = reinterpret_cast<const uint16_t *>(row + RB + (size_t)NB * 80);
        const float dva = iq3::half(dpa[lane < NB ? lane : NB - 1]);
        const float dvb = TWO ? iq3::half(dpb[lane < NB ? lane : NB - 1]) : 0.0f;
#pragma unroll 1
        for (unsigned T = 0; T < NFP; ++T) {
            const uint32_t ma = row_words<NWM>(sg, ra + NW, T, lane);
            const uint32_t mb = TWO ? row_words<NWM>(sg, rb + NW, T, lane) : 0u;
            r2::sfor<2>([&](auto spk) {
                constexpr unsigned SP = decltype(spk)::value;
                const unsigned S = 2 * T + SP;
                Sg ua, ub;
                sprep<SP>(sg, lane, hs, ra, dva, ma, S, ua);
                if constexpr (TWO) sprep<SP>(sg, lane, hs, rb, dvb, mb, S, ub);
                seg<4, TWO>(sg, xs, S, ua, ub, tb, j4, ssh, sa, sb);
            });
        }
        // tail: segments 2 NFP .. NS - 1 (compile-time)
        constexpr unsigned T0 = NFP;
        if constexpr (2 * T0 < NS) {
            const uint32_t ma = row_words<NWM>(sg, ra + NW, T0, lane);
            const uint32_t mb = TWO ? row_words<NWM>(sg, rb + NW, T0, lane) : 0u;
            r2::sfor<NS - 2 * T0>([&](auto spk) {
                constexpr unsigned SP = decltype(spk)::value, S = 2 * T0 + SP;
                constexpr unsigned NBS = 4 * S + 4 < NB ? 4 : NB - 4 * S;
                Sg ua, ub;
                sprep<SP>(sg, lane, hs, ra, dva, ma, S, ua);
                if constexpr (TWO) sprep<SP>(sg, lane, hs, rb, dvb, mb, S, ub);
                seg<NBS, TWO>(sg, xs, S, ua, ub, tb, j4, ssh, sa, sb);
            });
        }
    }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_s_grid, k >> 3, k & 7));
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), hs = lane & 1u;
        const uint32_t j4 = (lane & 7u) << 2;
        const unsigned ssh = 31u - lane;
        const char *tb = reinterpret_cast<const char *>(tab);
        auto body2 = [&](const uint8_t *row, const float *xs, float &sa, float &sb) {
            rowrun<true>(sg, lane, hs, row, xs, tb, j4, ssh, sa, sb);
        };
        auto body1 = [&](const uint8_t *row, const float *xs, float &sa) {
            float dummy = 0;
            rowrun<false>(sg, lane, hs, row, xs, tb, j4, ssh, sa, dummy);
        };
        R2_PAIR_SCHED()
    }
};

template <unsigned NB, typename A, typename EX = NoRows> struct RoutedIQ2XXSPe {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static constexpr unsigned TAB = 2048;
    unsigned rows;
    bool per_slot_x;
    EX ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    static constexpr size_t RB = ((size_t)NB * 70 + 15) & ~(size_t)15;
    static constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NC = NB * 8, NS = (NC + 31) / 32, NFS = NB / 4;
    static_assert(NB <= 32);
    struct Sg {
        uint32_t aw[2], ew;
        float db;
    };
    [[gnu::always_inline]] static void sprep(sycl::sub_group sg, unsigned lane, unsigned hs, const uint32_t *rw,
                                             float dl, uint32_t sw, unsigned S, Sg &u) {
        const uint32_t w0 = row_words<NW>(sg, rw, 2 * S, lane);
        const uint32_t w1 = 2 * S + 1 < NR ? row_words<NW>(sg, rw, 2 * S + 1, lane) : w0;
        r2::sfor<2>([&](auto jj) {
            constexpr unsigned j = decltype(jj)::value;
            const uint32_t lo = r2::even2(j ? w1 : w0), h = hs ? lo >> 16 : lo & 0xFFFFu;
            u.aw[j] = ((h & 255u) << 5) | ((h >> 8) << 21);
        });
        u.ew = r2::odd2x(w0, w1);
        // chunk_scales' expression for chunk c = 32S + lane, block b = c / 8 (clamped)
        const unsigned b0 = 4 * S < NB ? 4 * S : NB - 1, b1 = 4 * S + 1 < NB ? 4 * S + 1 : NB - 1;
        const unsigned b2 = 4 * S + 2 < NB ? 4 * S + 2 : NB - 1, b3 = 4 * S + 3 < NB ? 4 * S + 3 : NB - 1;
        const float e0 = sycl::select_from_group(sg, dl, b0), e1 = sycl::select_from_group(sg, dl, b1);
        const float e2 = sycl::select_from_group(sg, dl, b2), e3 = sycl::select_from_group(sg, dl, b3);
        const uint32_t s0 = sycl::select_from_group(sg, sw, b0), s1 = sycl::select_from_group(sg, sw, b1);
        const uint32_t s2 = sycl::select_from_group(sg, sw, b2), s3 = sycl::select_from_group(sg, sw, b3);
        const float d = lane < 16 ? (lane < 8 ? e0 : e1) : (lane < 24 ? e2 : e3);
        const uint32_t sc = lane < 16 ? (lane < 8 ? s0 : s1) : (lane < 24 ? s2 : s3);
        u.db = (d * (0.5f + float((sc >> (4 * (lane & 7u))) & 15u))) * 0.25f;
    }
    template <unsigned M>
    [[gnu::always_inline]] static float wv(sycl::sub_group sg, const Sg &u, const char *tb, uint32_t j4, unsigned ssh) {
        const uint32_t ad = r2::ag8<M % 16>(u.aw[M / 16], j4);
        const float mag = *reinterpret_cast<const float *>(tb + ad);
        const float p = sycl::select_from_group(sg, u.db, M) * mag;
        const uint32_t e = sycl::select_from_group(sg, u.ew, M);
        const uint32_t sb = (e << ssh) & 0x80000000u;
        return sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p) ^ sb);
    }
    template <unsigned NBS, bool TWO>
    [[gnu::always_inline]] static void seg(sycl::sub_group sg, const float *xs, unsigned S, const Sg &ua, const Sg &ub,
                                           const char *tb, uint32_t j4, unsigned ssh, float &sa, float &sb) {
        r2::sfor<NBS>([&](auto bk) {
            constexpr unsigned bb = decltype(bk)::value;
            const auto xv = sg_bloadN<8>(sg, xs + (size_t)(4 * S + bb) * 256);
            r2::sfor<8>([&](auto gk) {
                constexpr unsigned g = decltype(gk)::value, m = 8 * bb + g;
                if constexpr (TWO) {
                    const float va = wv<m>(sg, ua, tb, j4, ssh), vb = wv<m>(sg, ub, tb, j4, ssh);
                    sa = sa + va * xv[g];
                    sb = sb + vb * xv[g];
                } else {
                    sa = sa + wv<m>(sg, ua, tb, j4, ssh) * xv[g];
                }
            });
        });
    }
    template <bool TWO>
    [[gnu::always_inline]] static void rowrun(sycl::sub_group sg, unsigned lane, unsigned hs, const uint8_t *row,
                                              const float *xs, const char *tb, uint32_t j4, unsigned ssh, float &sa,
                                              float &sb) {
        const uint32_t *ra = reinterpret_cast<const uint32_t *>(row), *rb = reinterpret_cast<const uint32_t *>(row + RB);
        auto rinit = [&](const uint8_t *r, float &dl, uint32_t &sw) {
            const uint16_t *dp = reinterpret_cast<const uint16_t *>(r + (size_t)NB * 68);
            const uint32_t *scw = reinterpret_cast<const uint32_t *>(r + (size_t)NB * 64);
            dl = lane < NB ? iq3::half(dp[lane]) : 0.0f; // as chunk_scales
            sw = lane < NB ? scw[lane] : 0u;
        };
        float dla, dlb = 0;
        uint32_t swa, swb = 0;
        rinit(row, dla, swa);
        if constexpr (TWO) rinit(row + RB, dlb, swb);
#pragma unroll 1
        for (unsigned S = 0; S < NFS; ++S) {
            Sg ua, ub;
            sprep(sg, lane, hs, ra, dla, swa, S, ua);
            if constexpr (TWO) sprep(sg, lane, hs, rb, dlb, swb, S, ub);
            seg<4, TWO>(sg, xs, S, ua, ub, tb, j4, ssh, sa, sb);
        }
        if constexpr (NFS < NS) {
            constexpr unsigned S = NFS, NBS = NB - 4 * NFS;
            Sg ua, ub;
            sprep(sg, lane, hs, ra, dla, swa, S, ua);
            if constexpr (TWO) sprep(sg, lane, hs, rb, dlb, swb, S, ub);
            seg<NBS, TWO>(sg, xs, S, ua, ub, tb, j4, ssh, sa, sb);
        }
    }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_xxs_grid, k >> 3, k & 7));
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), hs = lane & 1u;
        const uint32_t j4 = (lane & 7u) << 2;
        const unsigned ssh = 31u - lane;
        const char *tb = reinterpret_cast<const char *>(tab);
        auto body2 = [&](const uint8_t *row, const float *xs, float &sa, float &sb) {
            rowrun<true>(sg, lane, hs, row, xs, tb, j4, ssh, sa, sb);
        };
        auto body1 = [&](const uint8_t *row, const float *xs, float &sa) {
            float dummy = 0;
            rowrun<false>(sg, lane, hs, row, xs, tb, j4, ssh, sa, dummy);
        };
        R2_PAIR_SCHED()
    }
};


// ==== r4: expert-major routed rows (RoutedU, multi-token steps: checks, prompt blocks) with the b decoders =====
// RoutedU3<F, MT, EX, SPT> = RoutedU's work items, group lookups, per-slot accumulators, x loads, reduction and
// stores, with the b forms' per-lane state (block reads + register-region moves) built per segment of 32 chunks
// (4 blocks) inside a run-time loop over units of F::SPU segments (one meta-register load per unit), as the e
// forms do: the whole-row state of the b forms with MT accumulators asks for 256 registers (half the threads,
// slower than RoutedU). F::wv<m>(u) = lane's value of chunk m of the segment: v = (db * mag) ^ sign (IQ1_S:
// dl * (code + de)), the same float values as RUFmt*::decode (which copy the slot-major kernels' expressions,
// as the b forms do). Per slot the same `sum = sum + v * x` in the same block / element order on the same x,
// the same xor butterfly, the same store: bitwise RoutedU's outputs. Extra rows run outside the row loop
// (R2_EX_ROWS). Bench: tools/bench/bench_routed_u2.cpp.
template <unsigned NB_> struct RU3IQ2XXS {
    static constexpr unsigned NB = NB_, TAB = 2048, SPU = 1;
    static constexpr size_t RB = ((size_t)NB * 70 + 15) & ~(size_t)15;
    static constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NC = NB * 8, NS = (NC + 31) / 32;
    static_assert(NB <= 32);
    static void fill(const sycl::nd_item<1> &it, float *tab) {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_xxs_grid, k >> 3, k & 7));
    }
    struct Row {
        const uint32_t *rw;
        float dl;
        uint32_t sw;
    };
    struct Unit {};
    struct Sg {
        uint32_t aw[2], ew;
        float db;
    };
    const char *tb;
    unsigned lane, hs, ssh;
    uint32_t j4;
    RU3IQ2XXS(unsigned lane_, float *tab)
        : tb(reinterpret_cast<const char *>(tab)), lane(lane_), hs(lane_ & 1u), ssh(31u - lane_), j4((lane_ & 7u) << 2) {}
    [[gnu::always_inline]] inline void row(sycl::sub_group, const uint8_t *r, Row &q) const {
        q.rw = reinterpret_cast<const uint32_t *>(r);
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(r + (size_t)NB * 68);
        const uint32_t *scw = reinterpret_cast<const uint32_t *>(r + (size_t)NB * 64);
        q.dl = lane < NB ? iq3::half(dp[lane]) : 0.0f; // as chunk_scales
        q.sw = lane < NB ? scw[lane] : 0u;
    }
    [[gnu::always_inline]] inline void unit(sycl::sub_group, const Row &, unsigned, Unit &) const {}
    template <unsigned SP>
    [[gnu::always_inline]] inline void seg(sycl::sub_group sg, const Row &q, const Unit &, unsigned S, Sg &u) const {
        const uint32_t w0 = row_words<NW>(sg, q.rw, 2 * S, lane);
        const uint32_t w1 = 2 * S + 1 < NR ? row_words<NW>(sg, q.rw, 2 * S + 1, lane) : w0;
        r2::sfor<2>([&](auto jj) {
            constexpr unsigned j = decltype(jj)::value;
            const uint32_t lo = r2::even2(j ? w1 : w0), h = hs ? lo >> 16 : lo & 0xFFFFu;
            u.aw[j] = ((h & 255u) << 5) | ((h >> 8) << 21);
        });
        u.ew = r2::odd2x(w0, w1);
        // chunk_scales' expression for chunk c = 32S + lane, block b = c / 8 (clamped)
        const unsigned b0 = 4 * S < NB ? 4 * S : NB - 1, b1 = 4 * S + 1 < NB ? 4 * S + 1 : NB - 1;
        const unsigned b2 = 4 * S + 2 < NB ? 4 * S + 2 : NB - 1, b3 = 4 * S + 3 < NB ? 4 * S + 3 : NB - 1;
        const float e0 = sycl::select_from_group(sg, q.dl, b0), e1 = sycl::select_from_group(sg, q.dl, b1);
        const float e2 = sycl::select_from_group(sg, q.dl, b2), e3 = sycl::select_from_group(sg, q.dl, b3);
        const uint32_t s0 = sycl::select_from_group(sg, q.sw, b0), s1 = sycl::select_from_group(sg, q.sw, b1);
        const uint32_t s2 = sycl::select_from_group(sg, q.sw, b2), s3 = sycl::select_from_group(sg, q.sw, b3);
        const float d = lane < 16 ? (lane < 8 ? e0 : e1) : (lane < 24 ? e2 : e3);
        const uint32_t sc = lane < 16 ? (lane < 8 ? s0 : s1) : (lane < 24 ? s2 : s3);
        u.db = (d * (0.5f + float((sc >> (4 * (lane & 7u))) & 15u))) * 0.25f;
    }
    template <unsigned M> [[gnu::always_inline]] inline float wv(sycl::sub_group sg, const Sg &u) const {
        const uint32_t ad = r2::ag8<M % 16>(u.aw[M / 16], j4);
        const float mag = *reinterpret_cast<const float *>(tb + ad);
        const float p = sycl::select_from_group(sg, u.db, M) * mag;
        const uint32_t e = sycl::select_from_group(sg, u.ew, M);
        return sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p) ^ ((e << ssh) & 0x80000000u));
    }
};
template <unsigned NB_> struct RU3IQ2S {
    static constexpr unsigned NB = NB_, TAB = 8192, SPU = 2;
    static constexpr size_t RB = ((size_t)NB * 82 + 15) & ~(size_t)15;
    static constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NWM = NB * 4, NC = NB * 8, NS = (NC + 31) / 32;
    static void fill(const sycl::nd_item<1> &it, float *tab) {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_s_grid, k >> 3, k & 7));
    }
    struct Row {
        const uint32_t *rw;
        float dv;
    };
    struct Unit {
        uint32_t mr; // meta register T: per block qh[8], scales[8] of blocks 8T .. 8T + 7
    };
    struct Sg {
        uint32_t aw[2], ew;
        float dw[2];
    };
    const char *tb;
    unsigned lane, hs, ssh;
    uint32_t j4;
    RU3IQ2S(unsigned lane_, float *tab)
        : tb(reinterpret_cast<const char *>(tab)), lane(lane_), hs(lane_ & 1u), ssh(31u - lane_), j4((lane_ & 7u) << 2) {}
    [[gnu::always_inline]] inline void row(sycl::sub_group, const uint8_t *r, Row &q) const {
        q.rw = reinterpret_cast<const uint32_t *>(r);
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(r + (size_t)NB * 80);
        q.dv = iq3::half(dp[lane < NB ? lane : NB - 1]); // lane b: block b's d
    }
    [[gnu::always_inline]] inline void unit(sycl::sub_group sg, const Row &q, unsigned T, Unit &un) const {
        un.mr = row_words<NWM>(sg, q.rw + NW, T, lane);
    }
    template <unsigned SP>
    [[gnu::always_inline]] inline void seg(sycl::sub_group sg, const Row &q, const Unit &un, unsigned S, Sg &u) const {
        const uint32_t w0 = row_words<NW>(sg, q.rw, 2 * S, lane);
        const uint32_t w1 = 2 * S + 1 < NR ? row_words<NW>(sg, q.rw, 2 * S + 1, lane) : w0;
        r2::sfor<2>([&](auto jj) {
            constexpr unsigned j = decltype(jj)::value, kq = 2 * SP + j; // k % 4
            const unsigned k = 2 * S + j;
            const uint32_t lo = r2::even2(j ? w1 : w0), qh = r2::qhb<kq>(un.mr);
            const uint32_t h = hs ? lo >> 16 : lo & 0xFFFFu, qq = hs ? qh >> 4 : qh;
            const uint32_t i0 = (h & 255u) | ((qq & 3u) << 8), i1 = (h >> 8) | (((qq >> 2) & 3u) << 8);
            u.aw[j] = (i0 << 5) | (i1 << 21);
            const unsigned B0 = 2 * k < NB ? 2 * k : NB - 1, B1 = 2 * k + 1 < NB ? 2 * k + 1 : NB - 1;
            const float d0 = sycl::select_from_group(sg, q.dv, B0), d1 = sycl::select_from_group(sg, q.dv, B1);
            const float d = (lane & 8u) ? d1 : d0;
            const uint32_t sc = r2::scb<kq>(un.mr);
            u.dw[j] = (d * (0.5f + float((sc >> (4 * (lane >> 4))) & 15u))) * 0.25f;
        });
        u.ew = r2::odd2x(w0, w1);
    }
    template <unsigned M> [[gnu::always_inline]] inline float wv(sycl::sub_group sg, const Sg &u) const {
        const uint32_t ad = r2::ag8<M % 16>(u.aw[M / 16], j4);
        const float mag = *reinterpret_cast<const float *>(tb + ad);
        const float p = r2::mp16<M % 16>(u.dw[M / 16], mag);
        const uint32_t e = sycl::select_from_group(sg, u.ew, M);
        return sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p) ^ ((e << ssh) & 0x80000000u));
    }
};
template <unsigned NB_> struct RU3IQ2XS {
    static constexpr unsigned NB = NB_, TAB = 4096, SPU = 4;
    static constexpr size_t RB = ((size_t)NB * 74 + 15) & ~(size_t)15;
    static constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NWS = NB * 2, NC = NB * 8, NS = (NC + 31) / 32;
    static void fill(const sycl::nd_item<1> &it, float *tab) {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_xs_grid, k >> 3, k & 7));
    }
    struct Row {
        const uint32_t *rw;
        float dv;
    };
    struct Unit {
        uint32_t sr; // scale register T: one scale byte per chunk of chunks 128T .. 128T + 127
    };
    struct Sg {
        uint32_t aw[2], ew;
        float dw[2];
    };
    const char *tb;
    unsigned lane, ssh;
    uint32_t j4;
    RU3IQ2XS(unsigned lane_, float *tab)
        : tb(reinterpret_cast<const char *>(tab)), lane(lane_), ssh(31u - lane_), j4((lane_ & 7u) << 2) {}
    [[gnu::always_inline]] inline void row(sycl::sub_group, const uint8_t *r, Row &q) const {
        q.rw = reinterpret_cast<const uint32_t *>(r);
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(r + (size_t)NB * 72);
        q.dv = iq3::half(dp[lane < NB ? lane : NB - 1]); // lane b: block b's d
    }
    [[gnu::always_inline]] inline void unit(sycl::sub_group sg, const Row &q, unsigned T, Unit &un) const {
        un.sr = row_words<NWS>(sg, q.rw + NW, T, lane);
    }
    template <unsigned SP>
    [[gnu::always_inline]] inline void seg(sycl::sub_group sg, const Row &q, const Unit &un, unsigned S, Sg &u) const {
        const uint32_t w0 = row_words<NW>(sg, q.rw, 2 * S, lane);
        const uint32_t w1 = 2 * S + 1 < NR ? row_words<NW>(sg, q.rw, 2 * S + 1, lane) : w0;
        r2::sfor<2>([&](auto jj) {
            constexpr unsigned j = decltype(jj)::value, k8 = 2 * SP + j; // k % 8
            const unsigned k = 2 * S + j;
            const uint32_t a = j ? w1 : w0;
            u.aw[j] = ((a & 511u) << 5) | (((a >> 16) & 511u) << 21);
            const unsigned B0 = 2 * k < NB ? 2 * k : NB - 1, B1 = 2 * k + 1 < NB ? 2 * k + 1 : NB - 1;
            const float d0 = sycl::select_from_group(sg, q.dv, B0), d1 = sycl::select_from_group(sg, q.dv, B1);
            const float d = (lane & 8u) ? d1 : d0;
            const uint32_t sc = r2::sb1<k8>(un.sr);
            u.dw[j] = (d * (0.5f + float((sc >> (4 * (lane >> 4))) & 15u))) * 0.25f;
        });
        const uint32_t a0 = r2::even2x(w0, w1), a1 = r2::odd2x(w0, w1);
        u.ew = r2::widen4((a0 >> 9) & 127u, a0 >> 25, (a1 >> 9) & 127u, a1 >> 25);
    }
    template <unsigned M> [[gnu::always_inline]] inline float wv(sycl::sub_group sg, const Sg &u) const {
        const uint32_t ad = r2::ag8<M % 16>(u.aw[M / 16], j4);
        const float mag = *reinterpret_cast<const float *>(tb + ad);
        const float p = r2::mp16<M % 16>(u.dw[M / 16], mag);
        const uint32_t e = sycl::select_from_group(sg, u.ew, M);
        return sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p) ^ ((e << ssh) & 0x80000000u));
    }
};
// IQ1_S: table of the high 16 bits of float(code) (the b form's TM 3): code is the same float as RUFmtIQ1S's
// float(int(byte)), so dl * (code + de) is
template <unsigned NB_> struct RU3IQ1S {
    static constexpr unsigned NB = NB_, TAB = 8192, SPU = 2;
    static constexpr size_t RB = ((size_t)NB * 50 + 15) & ~(size_t)15;
    static constexpr unsigned NC = NB * 8, NS = (NC + 31) / 32, NWQ = NB * 8, NWH = NB * 4;
    static void fill(const sycl::nd_item<1> &it, float *tab) {
        int16_t *sbt = reinterpret_cast<int16_t *>(tab);
        for (unsigned k = it.get_local_linear_id(); k < 16384; k += (unsigned)it.get_local_range(0)) {
            const int c = int(int8_t(uint8_t(grid64_byte(iq3::iq1_s_grid, k >> 3, k & 7))));
            sbt[k] = int16_t(c == 0 ? 0 : c > 0 ? 0x3F80 : 0xBF80); // float(c) >> 16
        }
    }
    struct Row {
        const uint32_t *rw;
        float dv;
    };
    struct Unit {
        uint32_t wh; // qh register T: one half per chunk of chunks 64T .. 64T + 63
    };
    struct Sg {
        uint32_t aw[2];
        float dl, de;
    };
    unsigned lane, hs;
    uint32_t jb;
    RU3IQ1S(unsigned lane_, float *) : lane(lane_), hs(lane_ & 1u), jb((lane_ & 7u) << 1) {}
    [[gnu::always_inline]] inline void row(sycl::sub_group, const uint8_t *r, Row &q) const {
        q.rw = reinterpret_cast<const uint32_t *>(r);
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(r + (size_t)NB * 48);
        q.dv = iq3::half(dp[lane < NB ? lane : NB - 1]); // lane b: block b's d
    }
    [[gnu::always_inline]] inline void unit(sycl::sub_group sg, const Row &q, unsigned T, Unit &un) const {
        un.wh = row_words<NWH>(sg, q.rw + NWQ, T, lane);
    }
    template <unsigned SP>
    [[gnu::always_inline]] inline void seg(sycl::sub_group sg, const Row &q, const Unit &un, unsigned S, Sg &u) const {
        const uint32_t wq = row_words<NWQ>(sg, q.rw, S, lane);
        r2::sfor<2>([&](auto jj) {
            constexpr unsigned j = decltype(jj)::value, k4 = 2 * SP + j; // k % 4, k = 2S + j
            const uint32_t qs = r2::qsp<j>(wq), qh = r2::qhp<k4>(un.wh);
            const uint32_t h = hs ? qs >> 16 : qs & 0xFFFFu, qq = hs ? qh >> 6 : qh; // groups 2hs, 2hs + 1
            const uint32_t i0 = (h & 255u) | ((qq & 7u) << 8), i1 = (h >> 8) | (((qq >> 3) & 7u) << 8);
            u.aw[j] = (i0 << 4) | (i1 << 20);
        });
        const uint32_t qh = r2::qh1<SP>(un.wh);
        u.dl = r2::blk_d4<NB>(sg, q.dv, S, lane) * float(2 * ((qh >> 12) & 7) + 1);
        u.de = (qh & 0x8000) ? -0.125f : 0.125f;
    }
    template <unsigned M> [[gnu::always_inline]] inline float wv(sycl::sub_group sg, const Sg &u) const {
        const uint32_t ad = r2::ag8<M % 16>(u.aw[M / 16], jb);
        const float dl = sycl::select_from_group(sg, u.dl, M);
        const float code = sycl::bit_cast<float>(r2::ld16(ad) << 16);
        const float de = sycl::select_from_group(sg, u.de, M);
        return dl * (code + de);
    }
};
template <unsigned NB_> struct RU3IQ3XXS {
    static constexpr unsigned NB = NB_, TAB = 1024, SPU = 1;
    static constexpr size_t RB = ((size_t)NB * 98 + 15) & ~(size_t)15;
    static constexpr unsigned NC = NB * 8, NS = (NC + 31) / 32;
    static void fill(const sycl::nd_item<1> &it, float *tab) {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float((iq3::iq3_grid[k >> 2] >> (8 * (k & 3))) & 255);
    }
    struct Row {
        const uint32_t *rw;
        float dv;
    };
    struct Unit {};
    struct Sg {
        uint32_t aw[4], ew;
        float db;
    };
    const char *tb;
    unsigned lane, hs, ssh;
    uint32_t jj4;
    RU3IQ3XXS(unsigned lane_, float *tab)
        : tb(reinterpret_cast<const char *>(tab)), lane(lane_), hs(lane_ & 1u), ssh(31u - lane_), jj4((lane_ & 3u) << 2) {}
    [[gnu::always_inline]] inline void row(sycl::sub_group, const uint8_t *r, Row &q) const {
        q.rw = reinterpret_cast<const uint32_t *>(r);
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(r + (size_t)NB * 96);
        q.dv = iq3::half(dp[lane < NB ? lane : NB - 1]); // lane b: block b's d
    }
    [[gnu::always_inline]] inline void unit(sycl::sub_group, const Row &, unsigned, Unit &) const {}
    template <unsigned SP>
    [[gnu::always_inline]] inline void seg(sycl::sub_group sg, const Row &q, const Unit &, unsigned S, Sg &u) const {
        const unsigned c = 32 * S + lane < NC ? 32 * S + lane : NC - 1;
        const uint32_t *cp = q.rw + 3 * c; // = 24 (c >> 3) + 3 (c & 7)
        const uint32_t q0 = cp[0], q1 = cp[1], sw = cp[2];
        u.ew = r2::widen4(sw & 127u, (sw >> 7) & 127u, (sw >> 14) & 127u, (sw >> 21) & 127u);
        u.db = (r2::blk_d4<NB>(sg, q.dv, S, lane) * (0.5f + float(sw >> 28))) * 0.5f;
        r2::sfor<4>([&](auto kk) {
            constexpr unsigned k = decltype(kk)::value;
            const uint32_t qq = r2::iq3q<k>(q0, q1), h = hs ? qq >> 16 : qq & 0xFFFFu;
            u.aw[k] = ((h & 255u) << 4) | ((h >> 8) << 20);
        });
    }
    template <unsigned M> [[gnu::always_inline]] inline float wv(sycl::sub_group sg, const Sg &u) const {
        const uint32_t ad = r2::ag4<M % 8>(u.aw[M / 8], jj4);
        const float mag = *reinterpret_cast<const float *>(tb + ad);
        const float db = sycl::select_from_group(sg, u.db, M);
        const uint32_t e = sycl::select_from_group(sg, u.ew, M);
        return sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ ((e << ssh) & 0x80000000u));
    }
};
// The kernel: RoutedU (sycl_v41.hpp) with F = RU3*; same members (aggregate order), launch and grp layout.
// PAIRS: in blocks of at least PAIR_NSL / 6 tokens (nsl, set by the backend) a sub-group first takes row pairs
// (2q, 2q + 1) of one group (rows per expert even), so each slot's x block read feeds both rows (as the one-token
// e forms), then single rows; npair <= P * (rmax / 2), rmax = RoutedU's rows per sub-group, so no sub-group runs
// more rows than RoutedU. Per row the same sums in the same order. (Pairs lose at 1-6 tokens: bench_routed_u2.)
template <typename F, unsigned MT, typename EX = NoRows, unsigned SPT = 6, bool PAIRS = false> struct RoutedU3 {
    static_assert(MT >= 1 && MT <= RUGrp::CAP, "1 .. 16 slots per group");
    static constexpr unsigned TAB = F::TAB, NB = F::NB, SPU = F::SPU, NS = F::NS;
    static constexpr unsigned NFU = (NB / 4) / SPU; // units whose segments all have 4 blocks (run-time loop)
    static constexpr unsigned PAIR_NSL = 96;
    unsigned rows; // per-expert rows
    bool per_slot_x;
    EX ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    unsigned nexp = 0; // not read (RoutedU's F::CLAMP_EXP formats are not RU3 formats)
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *grp,
                                     float *out, float *tab) const {
        F::fill(it, tab);
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const F f(lane, tab);
        const unsigned nu = grp[0];
        const unsigned P = (unsigned)(it.get_global_range(0) / 32), p0 = packed_row_id(it);
        const unsigned nr_ = (w2 ? 2 : 1) * nu * rows;
        unsigned npair = 0;
        if constexpr (PAIRS) {
            const unsigned rmax = (nr_ + P - 1) / P, pc = P * (rmax / 2);
            if (nsl >= PAIR_NSL && rows % 2 == 0) npair = pc < nr_ / 2 ? pc : nr_ / 2; // at most rmax rows per sub-group
        }
        R2_EX_ROWS(P, p0, npair + (nr_ - 2 * npair)) // after the pairs' and single rows' rounds
        // row q_ (TWO: rows q_, q_ + 1 of the same group and matrix)
        auto job = [&](auto two, unsigned q_) {
            constexpr bool TWO = decltype(two)::value;
            unsigned u = q_ / rows;
            const unsigned r = q_ % rows;
            const uint8_t *wm = w;
            float *om = out;
            if (u >= nu) {
                u -= nu;
                wm = w2;
                om = out2;
            }
            const unsigned cnt = grp[RUGrp::CNT + u];
            const uint32_t sl = lane < cnt ? grp[RUGrp::SLOT + u * RUGrp::CAP + lane] : 0u;
            const uint32_t xo = (sl / SPT) * xtok + (per_slot_x ? (sl % SPT) * (NB * 256) : 0u);
            const unsigned eid = grp[RUGrp::EXP + u];
            const uint8_t *ra = wm + ((size_t)eid * rows + r) * F::RB;
            typename F::Row rr[TWO ? 2 : 1];
            f.row(sg, ra, rr[0]);
            if constexpr (TWO) f.row(sg, ra + F::RB, rr[1]);
            float sum[TWO ? 2 : 1][MT];
#pragma unroll
            for (unsigned i = 0; i < MT; ++i) {
                sum[0][i] = 0;
                if constexpr (TWO) sum[1][i] = 0;
            }
            // NBS blocks of segment S: each lane's 8 values per block and row once, then every slot of the group
            auto blocks = [&](auto nbs, unsigned S, const typename F::Sg (&sgs)[TWO ? 2 : 1]) {
                r2::sfor<decltype(nbs)::value>([&](auto bk) {
                    constexpr unsigned bb = decltype(bk)::value;
                    float v[TWO ? 2 : 1][8];
                    r2::sfor<8>([&](auto gk) {
                        constexpr unsigned g = decltype(gk)::value;
                        v[0][g] = f.template wv<8 * bb + g>(sg, sgs[0]);
                        if constexpr (TWO) v[1][g] = f.template wv<8 * bb + g>(sg, sgs[1]);
                    });
                    const size_t bo = (size_t)(4 * S + bb) * 256;
#pragma unroll
                    for (unsigned i = 0; i < MT; ++i) {
                        if (i < cnt) {
                            const auto xv = sg_bloadN<8>(sg, x + sycl::select_from_group(sg, xo, i) + bo);
#pragma unroll
                            for (unsigned g = 0; g < 8; ++g) {
                                sum[0][i] = sum[0][i] + v[0][g] * xv[g];
                                if constexpr (TWO) sum[1][i] = sum[1][i] + v[1][g] * xv[g];
                            }
                        }
                    }
                });
            };
#pragma unroll 1
            for (unsigned T = 0; T < NFU; ++T) {
                typename F::Unit un[TWO ? 2 : 1];
                f.unit(sg, rr[0], T, un[0]);
                if constexpr (TWO) f.unit(sg, rr[1], T, un[1]);
                r2::sfor<SPU>([&](auto spk) {
                    constexpr unsigned SP = decltype(spk)::value;
                    const unsigned S = SPU * T + SP;
                    typename F::Sg sgs[TWO ? 2 : 1];
                    f.template seg<SP>(sg, rr[0], un[0], S, sgs[0]);
                    if constexpr (TWO) f.template seg<SP>(sg, rr[1], un[1], S, sgs[1]);
                    blocks(std::integral_constant<unsigned, 4>{}, S, sgs);
                });
            }
            if constexpr (SPU * NFU < NS) { // the rest: compile-time segments
                typename F::Unit un[TWO ? 2 : 1];
                f.unit(sg, rr[0], NFU, un[0]);
                if constexpr (TWO) f.unit(sg, rr[1], NFU, un[1]);
                r2::sfor<NS - SPU * NFU>([&](auto spk) {
                    constexpr unsigned SP = decltype(spk)::value, S = SPU * NFU + SP;
                    constexpr unsigned NBS = 4 * S + 4 <= NB ? 4 : NB - 4 * S;
                    typename F::Sg sgs[TWO ? 2 : 1];
                    f.template seg<SP>(sg, rr[0], un[0], S, sgs[0]);
                    if constexpr (TWO) f.template seg<SP>(sg, rr[1], un[1], S, sgs[1]);
                    blocks(std::integral_constant<unsigned, NBS>{}, S, sgs);
                });
            }
#pragma unroll
            for (unsigned i = 0; i < MT; ++i) {
                if (i < cnt) {
                    const unsigned slot = sycl::select_from_group(sg, sl, i);
                    r2::sfor<TWO ? 2 : 1>([&](auto hk) {
                        constexpr unsigned h = decltype(hk)::value;
                        float s = sum[h][i];
                        for (int w_ = 16; w_; w_ >>= 1) s += sycl::select_from_group(sg, s, (int)lane ^ w_);
                        if (lane == 0) om[slot * rows + r + h] = s;
                    });
                }
            }
        };
        if constexpr (PAIRS)
            for (unsigned q_ = p0; q_ < npair; q_ += P) job(std::true_type{}, 2 * q_);
        for (unsigned q_ = 2 * npair + p0; q_ < nr_; q_ += P) job(std::false_type{}, q_);
    }
};

// The five formats' expert-major kernels as the backend names them (backend_sycl_v41_mt.inc, routed_m): RoutedU3,
// with row pairs for IQ2_XXS / IQ2_XS at MT <= 6 (their pair forms stay in 128 registers; the others' do not and
// lose), and RoutedU's own form (RUFmt*, sycl_v41.hpp: RoutedIQ2XXSU0 ...) where RoutedU3 was not faster: MT 16 at
// 9 blocks for IQ1_S (256 registers there), IQ2_XXS and IQ3_XXS (bench_routed_u2, card 3, 2026-11-11). BYTES
// (RoutedU's IQ1_S table) changes no value.
template <unsigned NB, unsigned MT> inline constexpr bool r4_u0 = NB < 12 && MT > 8;
template <unsigned NB, unsigned MT>
using RoutedIQ2XXSU = std::conditional_t<r4_u0<NB, MT>, RoutedU<RUFmtIQ2XXS<NB>, MT>,
                                         RoutedU3<RU3IQ2XXS<NB>, MT, NoRows, 6, (MT <= 6)>>;
template <unsigned NB, unsigned MT> using RoutedIQ2SU = RoutedU3<RU3IQ2S<NB>, MT>;
template <unsigned NB, unsigned MT>
using RoutedIQ3XXSU = std::conditional_t<r4_u0<NB, MT>, RoutedU<RUFmtIQ3XXS<NB>, MT>, RoutedU3<RU3IQ3XXS<NB>, MT>>;
template <unsigned NB, unsigned MT> using RoutedIQ2XSU = RoutedU3<RU3IQ2XS<NB>, MT, NoRows, 6, (MT <= 6)>;
template <unsigned NB, unsigned MT, bool BYTES = true>
using RoutedIQ1SU = std::conditional_t<r4_u0<NB, MT>, RoutedU<RUFmtIQ1S<NB, BYTES>, MT>, RoutedU3<RU3IQ1S<NB>, MT>>;

// Per-shape choice (bench_routed_r2, card 3, 2026-11-11): row pairs for IQ2_S / IQ2_XXS (e at 20 blocks, d at 9)
// with no extra rows or the stream mix's finish row (HcFinishRows, gate + up with OWN_HC_FIN), the b form with the
// shared expert's dense rows (routed_gemv_ex); b for IQ2_XS, IQ3_XXS and IQ1_S.
template <typename EX> inline constexpr bool r2_pairs_ok = std::is_same_v<EX, NoRows> || std::is_same_v<EX, HcFinishRows>;
template <unsigned NB, typename A, typename EX = NoRows>
using RoutedIQ2SPx = std::conditional_t<!r2_pairs_ok<EX>, RoutedIQ2SPb<NB, A, EX>,
                                        std::conditional_t<(NB > 12), RoutedIQ2SPe<NB, A, EX>, RoutedIQ2SPd<NB, A, EX>>>;
template <unsigned NB, typename A, typename EX = NoRows>
using RoutedIQ2XXSPx = std::conditional_t<!r2_pairs_ok<EX>, RoutedIQ2XXSPb<NB, A, EX>,
                                          std::conditional_t<(NB > 12), RoutedIQ2XXSPe<NB, A, EX>, RoutedIQ2XXSPd<NB, A, EX>>>;
template <unsigned NB, typename A, typename EX = NoRows> using RoutedIQ2XSPx = RoutedIQ2XSPb<NB, A, EX>;
template <unsigned NB, typename A, typename EX = NoRows> using RoutedIQ3XXSPx = RoutedIQ3XXSPb<NB, A, EX>;
template <unsigned NB, typename A, typename EX = NoRows> using RoutedIQ1SPx = RoutedIQ1SPb<NB, A, 3, EX>;

#undef R2_PAIR_SCHED
#undef R2_EX_ROWS
#undef R2_ROWS_BEGIN
#undef R2_ROWS_END
} // namespace ops41sycl
