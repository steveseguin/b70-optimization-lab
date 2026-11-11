// SYCL device kernels for the DeepSeek V4.1 op set (plan_v41.hpp /
// ops_v41.hpp). Each kernel mirrors its ops41:: host anchor's equation and
// reduction order; pure mul/add paths are bit-exact vs host, paths through
// exp/sigmoid/silu admit +-1 bf16 ulp (device vs host libm), same rule as
// the SC117 identity-v2 gates.
#pragma once
// Tokens per multi-token step (prompt block, checked block), at most: Backend41::MTX. Build with -DOWN41_MTX=n
// (16 <= n <= 256; default 256). Only capacities follow it (the block kernels' per-token tables, the expert
// groups' slot and group counts, the window ring's block area, the block buffers); no kernel's per-token
// arithmetic depends on it.
#ifndef OWN41_MTX
#define OWN41_MTX 256
#endif
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#include "stage2/packet2/kernels/math.hpp"
#include "stage2/packet3/kernels/ops_v41.hpp"
#include <sycl/ext/oneapi/experimental/prefetch.hpp>

namespace ops41sycl {
using iq3::Type;
inline constexpr unsigned MT_MAX = OWN41_MTX;
// >= 16: the one-sub-group block forms (DenseRowsM / GemvTM / HcDotsRowsM at 16 tokens) read 16 tokens' inputs;
// <= 256: the index kernels carry a per-token table int lens[MT_MAX] in their arguments (1 KiB at 256, under the
// devices' 2 KiB kernel-argument limit with the other members; past 256 they would have to move to card memory).
// (Past 128 tokens two block tokens share a ring row: RingCommitM / DraftKvRows write only the last 128.)
static_assert(MT_MAX >= 16 && MT_MAX <= 256, "OWN41_MTX: 16 .. 256 tokens per block step");

// SG32 butterfly in tree32 pairing order (width 1,2,4,8,16; i += 2w).
inline float sg_tree32(sycl::sub_group sg, float v) {
    unsigned l = sg.get_local_linear_id();
    for (unsigned w = 1; w < 32; w *= 2) {
        float o = sycl::select_from_group(sg, v, (l + w) % 32);
        if (l % (2 * w) == 0) v = v + o;
    }
    return sycl::select_from_group(sg, v, 0);
}

// gemv over one quantized row: lane l sums k = l, l+32, ... serially
// (iq3::lane_dot order), tree32 butterfly, bf16 RNE out. One sub-group per
// row; global id = row.
// rmsnorm: y[i] = w[i] * x[i] / sqrt(mean(x^2)+eps). Host runner accumulates
// x^2 serially in double; device uses SG32 strided lanes + tree32 in double,
// same math different order -> gate at +-1 bf16 ulp.
struct RmsNorm {
    int n;
    void operator()(sycl::nd_item<1> it, const uint16_t *x, const float *w,
                    uint16_t *y) const {
        int lane = it.get_local_linear_id();
        sycl::sub_group sg = it.get_sub_group();
        int base = it.get_group_linear_id() * n;
        double acc = 0;
        for (int i = lane; i < n; i += 32) {
            float v = ops41::bf16(x[base + i]);
            acc += double(v) * v;
        }
        for (int w_ = 16; w_; w_ >>= 1)
            acc += sycl::select_from_group(sg, acc, lane ^ w_);
        float rs = float(1.0 / sycl::sqrt(acc / n + 1e-20));
        for (int i = lane; i < n; i += 32)
            y[base + i] = ops41::bf16b(w[i] * (ops41::bf16(x[base + i]) * rs));
    }
};

struct Gemv {
    Type wtype; unsigned rows, cols; // x is bf16
    bool f32out = false;             // logits parity: skip bf16 rounding
    void operator()(sycl::nd_item<1> it, const uint8_t *w, size_t row_bytes_,
                    const uint16_t *x, void *yv) const {
        auto sg = it.get_sub_group();
        unsigned l = sg.get_local_linear_id();
        unsigned r = it.get_group_linear_id();
        const uint8_t *row = w + (size_t)r * row_bytes_;
        float sum = 0;
        for (unsigned k = l; k < cols; k += 32)
            sum = sum + iq3::element(wtype, row, k) * ops41::bf16(x[k]);
        sum = sg_tree32(sg, sum);
        if (l == 0) {
            if (f32out) reinterpret_cast<float *>(yv)[r] = sum;
            else reinterpret_cast<uint16_t *>(yv)[r] = ops41::bf16b(sum);
        }
    }
};

// Type-specialized forms of Gemv / RoutedGemv / GemvGroupedQ: the weight
// format is a template argument, so iq3::decode folds to one format's field
// equations (the runtime-type kernels re-select the format per element).
// Same element values, same lane order, same reductions -> bit-identical.
// Activation storage policy. The executor's buffers between operators are
// either BF16 (8 significant bits, the official model's style, the original
// bring-up) or F32. F32 is the default: BF16 activations add about 1 % of
// noise per layer output, enough to flip a 0.4-logit token against the f32
// reference (seen at token 27 of the first six-card run). KV rows (window
// rings, compressed rows, index keys) are BF16 in both modes.
struct ActBF16 {
    using T = uint16_t;
    static float rd(T v) { return ops41::bf16(v); }
    static T wr(float f) { return ops41::bf16b(f); }
};
struct ActF32 {
    using T = float;
    static float rd(T v) { return v; }
    static T wr(float f) { return f; }
};

// Element decode for the specialized kernels. Same field equations as
// iq3::decode (packet2/kernels/math.hpp, left untouched: the SC117 build
// identity includes it); the only change is how the magnitude byte leaves a
// 64-bit grid entry: a byte load from the table instead of
// (grid[ix] >> (8*j)) & 255, because a 64-bit VARIABLE shift is emulated on
// the B70. Bit-exact against iq3::decode by the device gate (decode_fast_*).
inline uint32_t grid64_byte(const uint64_t *grid, unsigned ix, unsigned j) {
    return reinterpret_cast<const uint8_t *>(grid)[(size_t)ix * 8 + j]; // little-endian byte j
}
template <iq3::Type T> [[gnu::always_inline]] inline float dec_t(const uint8_t *b, uint32_t i) {
    using iq3::half;
    using iq3::u16;
    using iq3::u32;
    if constexpr (T == iq3::Type::IQ2_XXS) {
        const unsigned g = i / 32, l = (i % 32) / 8, j = i % 8;
        const uint32_t lo = u32(b + 2 + 8 * g), hi = u32(b + 2 + 8 * g + 4);
        const auto mag = grid64_byte(iq3::iq2_xxs_grid, (lo >> (8 * l)) & 255, j);
        const int sign = ((iq3::iq2_signs[(hi >> (7 * l)) & 127] >> j) & 1) ? -1 : 1;
        return (((half(u16(b)) * (0.5f + float(hi >> 28))) * 0.25f) * float(mag)) * float(sign);
    } else if constexpr (T == iq3::Type::IQ2_XS) {
        const unsigned g = i / 32, l = (i % 32) / 8, j = i % 8;
        const unsigned aux = u16(b + 2 + 2 * (4 * g + l));
        const unsigned sc = (b[66 + g] >> (4 * (l >> 1))) & 15;
        const auto mag = grid64_byte(iq3::iq2_xs_grid, aux & 511, j);
        const int sign = ((iq3::iq2_signs[aux >> 9] >> j) & 1) ? -1 : 1;
        return (((half(u16(b)) * (0.5f + float(sc))) * 0.25f) * float(mag)) * float(sign);
    } else if constexpr (T == iq3::Type::IQ1_S) {
        const unsigned g = i / 32, l = (i % 32) / 8, j = i % 8;
        const uint32_t qh = u16(b + 34 + 2 * g);
        const float dl = half(u16(b)) * float(2 * ((qh >> 12) & 7) + 1);
        const float delta = (qh & 0x8000) ? -0.125f : 0.125f;
        const unsigned ix = b[2 + 4 * g + l] | (((qh >> (3 * l)) & 7) << 8);
        const int code = int(int8_t(uint8_t(grid64_byte(iq3::iq1_s_grid, ix, j))));
        return dl * (float(code) + delta);
    } else if constexpr (T == iq3::Type::IQ2_S) {
        auto q = i / 8;
        auto ix = b[2 + q] | (((b[66 + q / 4] >> (2 * (q % 4))) & 3) << 8);
        auto mag = grid64_byte(iq3::iq2_s_grid, ix, i % 8);
        int sign = (b[34 + q] >> (i % 8)) & 1 ? -1 : 1;
        auto sc = (b[74 + i / 32] >> (4 * ((i / 16) % 2))) & 15;
        return (((half(u16(b)) * (0.5f + float(sc))) * 0.25f) * float(mag)) * float(sign);
    } else {
        return iq3::decode(T, b, i);
    }
}

// iq2_signs[k] is k with its parity in bit 7 (checked below), so the sign
// bit needs no table read. Table reads are the expensive part of these
// kernels on the B70: dropping this one alone was 2.6x on IQ2_XXS.
constexpr bool iq2_signs_are_parity() {
    for (unsigned k = 0; k < 128; ++k)
        if (iq3::iq2_signs[k] != (k | ((unsigned(std::popcount(k)) & 1u) << 7))) return false;
    return true;
}
static_assert(iq2_signs_are_parity());
inline uint32_t sign7_bit(uint32_t k, unsigned j) {
    return ((k | ((uint32_t(std::popcount(k)) & 1u) << 7)) >> j) & 1u;
}

// Lane l's partial sum over columns l, l+32, ... in ascending order (the
// iq3::lane_dot order), written per format so that block and chunk state is
// read once (uniform across the sub-group) and the lane only picks bit
// fields and does one grid read. The float operations and their order are
// exactly those of iq3::decode, so results are bit-identical: the device
// gate lane_sum_* checks every format against lane_sum_ref on the card and
// on the host. Kernel microbench 2026-11-09 (G elements/s, per-element form
// -> this): IQ2_XXS 23 -> 302, IQ3_XXS 53 -> 301, IQ1_S 129 -> 334,
// IQ2_XS 131 -> 293, IQ2_S 62 -> 266, Q5_K 49 -> 129.
template <iq3::Type T, typename A = ActBF16>
[[gnu::always_inline]] inline float lane_sum_t(const uint8_t *row, const typename A::T *x, unsigned cols, unsigned lane) {
    using iq3::half;
    using iq3::u16;
    using iq3::u32;
    constexpr auto L = iq3::layout(T);
    float sum = 0;
    lane &= 31u;
    [[maybe_unused]] const unsigned l8 = lane >> 3, j = lane & 7u;
    if constexpr (T == iq3::Type::IQ2_XXS) {
        for (unsigned blk = 0; blk < cols / 256; ++blk) {
            const uint8_t *b = row + (size_t)blk * 66;
            const float d = half(u16(b));
            const typename A::T *xb = x + (size_t)blk * 256 + lane;
            for (unsigned g = 0; g < 8; ++g) {
                const uint32_t lo = u32(b + 2 + 8 * g), hi = u32(b + 6 + 8 * g);
                const float db = (d * (0.5f + float(hi >> 28))) * 0.25f;
                const uint32_t mag = grid64_byte(iq3::iq2_xxs_grid, (lo >> (8 * l8)) & 255, j);
                const int sign = sign7_bit((hi >> (7 * l8)) & 127, j) ? -1 : 1;
                sum = sum + ((db * float(mag)) * float(sign)) * A::rd(xb[g * 32]);
            }
        }
    } else if constexpr (T == iq3::Type::IQ2_XS) {
        // flat chunk loop: the block->chunk nest is wrong on the B70 for this
        // format with f32 activations (same hazard as IQ2_S below)
        for (unsigned c = 0; c < cols / 32; ++c) {
            const uint8_t *b = row + (size_t)(c >> 3) * 74;
            const unsigned g = c & 7u;
            const float d = half(u16(b));
            const uint32_t a0 = u32(b + 2 + 8 * g), a1 = u32(b + 6 + 8 * g);
            const uint32_t aux = ((l8 < 2 ? a0 : a1) >> (16 * (l8 & 1))) & 0xffffu;
            const unsigned sc = (b[66 + g] >> (4 * (l8 >> 1))) & 15;
            const uint32_t mag = grid64_byte(iq3::iq2_xs_grid, aux & 511, j);
            const int sign = sign7_bit(aux >> 9, j) ? -1 : 1;
            sum = sum + ((((d * (0.5f + float(sc))) * 0.25f) * float(mag)) * float(sign)) * A::rd(x[(c << 5) | lane]);
        }
    } else if constexpr (T == iq3::Type::IQ1_S) {
        for (unsigned blk = 0; blk < cols / 256; ++blk) {
            const uint8_t *b = row + (size_t)blk * 50;
            const float d = half(u16(b));
            const typename A::T *xb = x + (size_t)blk * 256 + lane;
            for (unsigned g = 0; g < 8; ++g) {
                const uint32_t qh = u16(b + 34 + 2 * g);
                const float dl = d * float(2 * ((qh >> 12) & 7) + 1);
                const float delta = (qh & 0x8000) ? -0.125f : 0.125f;
                const uint32_t qs = u32(b + 2 + 4 * g);
                const unsigned ix = ((qs >> (8 * l8)) & 255) | (((qh >> (3 * l8)) & 7) << 8);
                const int code = int(int8_t(uint8_t(grid64_byte(iq3::iq1_s_grid, ix, j))));
                sum = sum + (dl * (float(code) + delta)) * A::rd(xb[g * 32]);
            }
        }
    } else if constexpr (T == iq3::Type::IQ2_S) {
        // FLAT chunk loop on purpose. The block->chunk nest used by the other
        // formats gives WRONG sums on lanes 1..31 for this format on the B70
        // (icpx 2026.1 / NEO 26.x; the same source is right on the host and the
        // flat form is right on the device; even the nest with iq3::decode
        // inside is wrong). Any change here must pass the lane_sum_iq2_s gate.
        for (unsigned c = 0; c < cols / 32; ++c) {
            const uint8_t *b = row + (size_t)(c >> 3) * 82;
            const unsigned g = c & 7u;
            const float d = half(u16(b));
            const unsigned qhb = b[66 + g], scb = b[74 + g];
            const unsigned ix = b[2 + 4 * g + l8] | (((qhb >> (2 * l8)) & 3) << 8);
            const uint32_t mag = grid64_byte(iq3::iq2_s_grid, ix, j);
            const int sign = ((b[34 + 4 * g + l8] >> j) & 1) ? -1 : 1;
            const unsigned sc = (scb >> (4 * (lane >> 4))) & 15;
            sum = sum + ((((d * (0.5f + float(sc))) * 0.25f) * float(mag)) * float(sign)) * A::rd(x[(c << 5) | lane]);
        }
    } else if constexpr (T == iq3::Type::IQ3_XXS) {
        const unsigned l4 = lane >> 2;
        for (unsigned blk = 0; blk < cols / 256; ++blk) {
            const uint8_t *b = row + (size_t)blk * 98;
            const float d = half(u16(b));
            const typename A::T *xb = x + (size_t)blk * 256 + lane;
            for (unsigned g = 0; g < 8; ++g) {
                const uint32_t word = u32(b + 66 + 4 * g);
                const uint32_t code = (word >> (7 * l8)) & 127;
                const int sign = sign7_bit(code, j) ? -1 : 1;
                const uint32_t w0 = u32(b + 2 + 8 * g), w1 = u32(b + 6 + 8 * g);
                const unsigned gi = ((l4 < 4 ? w0 : w1) >> (8 * (l4 & 3))) & 255;
                const uint32_t mag = (iq3::iq3_grid[gi] >> (8 * (lane & 3))) & 255;
                sum = sum + ((((d * (0.5f + float(word >> 28))) * 0.5f) * float(mag)) * float(sign)) * A::rd(xb[g * 32]);
            }
        }
    } else if constexpr (L.elements >= 32) {
        constexpr unsigned CPB = L.elements / 32; // chunks per block
        const unsigned chunks = cols / 32;
        for (unsigned c = 0; c < chunks; ++c) {
            const uint8_t *blk = row + (size_t)(c / CPB) * L.bytes;
            const unsigned i = ((c % CPB) << 5) | lane;
            sum = sum + dec_t<T>(blk, i) * A::rd(x[(c << 5) | lane]);
        }
    } else {
        for (unsigned k = lane; k < cols; k += 32)
            sum = sum + dec_t<T>(row + (size_t)(k / L.elements) * L.bytes, k % L.elements) * A::rd(x[k]);
    }
    return sum;
}
// reference form of the same lane sum (per-element iq3::decode); gates and benches compare against it
template <iq3::Type T, typename A = ActBF16>
[[gnu::always_inline]] inline float lane_sum_ref(const uint8_t *row, const typename A::T *x, unsigned cols, unsigned lane) {
    constexpr auto L = iq3::layout(T);
    float sum = 0;
    for (unsigned k = lane; k < cols; k += 32)
        sum = sum + iq3::decode(T, row + (size_t)(k / L.elements) * L.bytes, k % L.elements) * A::rd(x[k]);
    return sum;
}
// ---- multi-token rows (2026-11-09) --------------------------------------------
// A row kernel's rowm<MT>(...) runs one row for MT tokens (MT compile-time,
// accumulators unrolled): token t reads its own activations (x + t * xs) into
// its own accumulator; every weight value is loaded and dequantized once and
// applied to each token with the one-token row()'s exact expression (same
// operands, same order, same intermediate products), and each token's sum goes
// through row()'s reduction. Each token's float operations are therefore those
// of row() on that token alone: bit-identical under the build's
// -fp-model=precise -ffp-contract=off (no contraction, no reassociation).
// Tokens t < mt (mt <= MT, uniform) are stored; the others run on in-bounds data
// (the caller's buffers hold MT tokens) and are dropped. Tokens run in groups of
// at most G (default: the kernel's MTG); each group re-reads the row (from the
// card's cache) so that the per-token activation vectors stay in registers. A
// group changes no token's operations. Gate: tools/bench/test_rows_mt.cpp.
//
// lane_sum_t for NT tokens: same lane order, same expression per element. Only
// lane_sum_t's generic branches (F32, F16, BF16, Q8_0, the K-quants, ...), not
// its hand-written IQ loops.
template <iq3::Type T, typename A, unsigned NT>
[[gnu::always_inline]] inline void lane_sum_tm(const uint8_t *row, const typename A::T *x, size_t xs, unsigned cols,
                                               unsigned lane, float (&sum)[NT]) {
    static_assert(T != iq3::Type::IQ2_XXS && T != iq3::Type::IQ2_XS && T != iq3::Type::IQ1_S &&
                      T != iq3::Type::IQ2_S && T != iq3::Type::IQ3_XXS,
                  "lane_sum_tm: no multi-token form of lane_sum_t's hand-written IQ loops");
    constexpr auto L = iq3::layout(T);
    lane &= 31u;
#pragma unroll
    for (unsigned t = 0; t < NT; ++t) sum[t] = 0;
    if constexpr (L.elements >= 32) {
        constexpr unsigned CPB = L.elements / 32; // chunks per block
        const unsigned chunks = cols / 32;
        for (unsigned c = 0; c < chunks; ++c) {
            const uint8_t *blk = row + (size_t)(c / CPB) * L.bytes;
            const unsigned i = ((c % CPB) << 5) | lane;
            const float v = dec_t<T>(blk, i);
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) sum[t] = sum[t] + v * A::rd(x[t * xs + ((c << 5) | lane)]);
        }
    } else {
        for (unsigned k = lane; k < cols; k += 32) {
            const float v = dec_t<T>(row + (size_t)(k / L.elements) * L.bytes, k % L.elements);
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) sum[t] = sum[t] + v * A::rd(x[t * xs + k]);
        }
    }
}
template <iq3::Type T, typename A = ActBF16> struct GemvT {
    unsigned rows, cols;
    bool f32out = false;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const typename A::T *x, void *yv) const {
        constexpr auto L = iq3::layout(T);
        const size_t rb = (size_t)(cols / L.elements) * L.bytes;
        auto sg = it.get_sub_group();
        unsigned l = sg.get_local_linear_id();
        unsigned r = it.get_group_linear_id();
        const uint8_t *row = w + (size_t)r * rb;
        float sum = lane_sum_t<T, A>(row, x, cols, l);
        sum = sg_tree32(sg, sum);
        if (l == 0) {
            if (f32out) reinterpret_cast<float *>(yv)[r] = sum;
            else reinterpret_cast<typename A::T *>(yv)[r] = A::wr(sum);
        }
    }
    // M tokens (see "multi-token rows" above): token t reads x + t * xs and writes output element
    // t * ys + r (float when f32out, else A::T) when t < mt. The lane loop is not unrolled and keeps
    // one activation per token live, so all 16 tokens fit one group.
    static constexpr unsigned MTG = 16;
    template <unsigned MT, unsigned G = MTG, unsigned T0 = 0>
    [[gnu::always_inline]] inline void rowm(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                            const typename A::T *x, size_t xs, void *yv, size_t ys, unsigned mt) const {
        if constexpr (T0 < MT) {
            constexpr unsigned NT = MT - T0 < G ? MT - T0 : G;
            if (T0 < mt) rowg<NT>(sg, lane, r, w, x + T0 * xs, xs, yv, T0 * ys, ys, mt - T0);
            rowm<MT, G, T0 + NT>(sg, lane, r, w, x, xs, yv, ys, mt);
        }
    }
    // NT tokens from output element y0 (token t at y0 + t * ys + r); stores t < mt
    template <unsigned NT>
    [[gnu::always_inline]] inline void rowg(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                            const typename A::T *x, size_t xs, void *yv, size_t y0, size_t ys,
                                            unsigned mt) const {
        constexpr auto L = iq3::layout(T);
        const size_t rb = (size_t)(cols / L.elements) * L.bytes;
        const uint8_t *row = w + (size_t)r * rb;
        float sum[NT];
        lane_sum_tm<T, A, NT>(row, x, xs, cols, lane, sum);
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) sum[t] = sg_tree32(sg, sum[t]);
        if (lane == 0) {
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) {
                if (t >= mt) continue;
                if (f32out) reinterpret_cast<float *>(yv)[y0 + t * ys + r] = sum[t];
                else reinterpret_cast<typename A::T *>(yv)[y0 + t * ys + r] = A::wr(sum[t]);
            }
        }
    }
};
// GemvT for M tokens as its own launch (launch_sg: one sub-group per work-group, row = group id; the
// pointers stay direct kernel arguments). xs / ys: per-token strides of x and of the output, in elements.
template <iq3::Type T, typename A, unsigned MT, unsigned G = GemvT<T, A>::MTG> struct GemvTM {
    GemvT<T, A> k;
    size_t xs, ys;
    unsigned mt;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const typename A::T *x, void *yv) const {
        auto sg = it.get_sub_group();
        k.template rowm<MT, G>(sg, sg.get_local_linear_id(), (unsigned)it.get_group_linear_id(), w, x, xs, yv, ys, mt);
    }
};
// GemvTM's tokens in groups of G over sub-groups (GemvTM runs all MT accumulators whatever mt is): work-group p
// = (row p / ng, tokens (p % ng) * G ..); per token the same sums as GemvT (lane_sum_tm keeps every token's
// order whatever the group size).
template <iq3::Type T, typename A, unsigned G> struct GemvTMG {
    GemvT<T, A> k;
    size_t xs, ys;
    unsigned mt, ng;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const typename A::T *x, void *yv) const {
        auto sg = it.get_sub_group();
        const unsigned p = (unsigned)it.get_group_linear_id(), r = p / ng, t0 = (p % ng) * G;
        k.template rowg<G>(sg, sg.get_local_linear_id(), r, w, x + t0 * xs, xs, yv, t0 * ys, ys, mt - t0);
    }
};
template <iq3::Type T, typename A = ActBF16> struct GemvGroupedQT {
    unsigned n, k;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const typename A::T *o,
                                     typename A::T *out) const {
        constexpr auto L = iq3::layout(T);
        const size_t rb = (size_t)(k / L.elements) * L.bytes;
        auto sg = it.get_sub_group();
        unsigned l = sg.get_local_linear_id();
        unsigned r = it.get_group_linear_id();
        const uint8_t *row = w + (size_t)r * rb;
        const typename A::T *xg = o + (size_t)(r / n) * k;
        float sum = lane_sum_t<T, A>(row, xg, k, l);
        sum = sg_tree32(sg, sum);
        if (l == 0) out[r] = A::wr(sum);
    }
};
template <iq3::Type T, typename A = ActBF16> struct RoutedGemvT {
    unsigned rows, cols; // per-expert matrix shape
    bool per_slot_x = false;
    unsigned nsl = 6, xtok = 0; // slots (6 per token) and the x stride between tokens (multi-token step)
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const typename A::T *x,
                                     const uint32_t *ids, typename A::T *out) const {
        constexpr auto L = iq3::layout(T);
        const size_t rb = (size_t)(cols / L.elements) * L.bytes;
        // slot/row from the GROUP id: uniform across the sub-group, so the row
        // pointer and everything loaded through it stays uniform (deriving
        // them from the global id made every load a per-lane gather)
        const unsigned grp = it.get_group_linear_id();
        const unsigned slot = grp / rows, r = grp % rows;
        if (slot >= nsl) return;
        const uint8_t *row = w + ((size_t)ids[slot] * rows + r) * rb;
        sycl::sub_group sg = it.get_sub_group();
        int lane = it.get_local_linear_id();
        const typename A::T *xs = x + (size_t)(slot / 6) * xtok + (per_slot_x ? (size_t)(slot % 6) * cols : 0);
        float a = lane_sum_t<T, A>(row, xs, cols, (unsigned)lane);
        for (int w_ = 16; w_; w_ >>= 1)
            a += sycl::select_from_group(sg, a, lane ^ w_);
        if (lane == 0) out[slot * rows + r] = A::wr(a);
    }
};
// the formats present in the UD-IQ2_XXS release (profile census)
#define OWN41_WEIGHT_TYPES(X) \
    X(F32) X(Q8_0) X(Q2_K) X(Q5_K) X(Q6_K) X(IQ2_XXS) X(IQ2_XS) X(IQ3_XXS) X(IQ1_S) X(IQ2_S) X(BF16)

// rope rotate tail rdim of each row, adjacent pairs. Pairs are independent:
// parallel over (row, pair) is bit-identical to the host serial loop.
struct RopePairs {
    unsigned rows, d, rdim; bool inverse;
    void operator()(sycl::nd_item<1> it, uint16_t *x, const float *cosb, const float *sinb) const {
        unsigned g = it.get_global_linear_id();
        unsigned pairs = rdim / 2;
        unsigned r = g / pairs, i = g % pairs;
        if (r >= rows) return;
        uint16_t *row = x + (size_t)r * d + (d - rdim);
        float re = ops41::bf16(row[2 * i]), im = ops41::bf16(row[2 * i + 1]);
        float c = cosb[i], s = inverse ? -sinb[i] : sinb[i];
        row[2 * i] = ops41::bf16b(re * c - im * s);
        row[2 * i + 1] = ops41::bf16b(re * s + im * c);
    }
};

// swiglu_clamp elementwise (one item per element; order-free).
struct Swiglu {
    long long n; float lim;
    void operator()(sycl::nd_item<1> it, const uint16_t *gate, const uint16_t *up, uint16_t *out) const {
        long long i = it.get_global_linear_id();
        if (i >= n) return;
        float g = sycl::fmin(ops41::bf16(gate[i]), lim);
        float u = sycl::clamp(ops41::bf16(up[i]), -lim, lim);
        out[i] = ops41::bf16b(g / (1.0f + sycl::exp(-g)) * u);
    }
};
struct ProbScale {
    int rows, n;
    void operator()(sycl::nd_item<1> it, uint16_t *act, const float *prob) const {
        int g = it.get_global_linear_id();
        int r = g / n, i = g % n;
        if (r >= rows) return;
        act[(size_t)r * n + i] = ops41::bf16b(prob[r] * ops41::bf16(act[(size_t)r * n + i]));
    }
};
struct MoeCombine {
    int top, h;
    void operator()(sycl::nd_item<1> it, const uint16_t *exps, const uint16_t *shared, uint16_t *out) const {
        int i = it.get_global_linear_id();
        if (i >= h) return;
        float acc = ops41::bf16(shared[i]);
        for (int r = 0; r < top; ++r) acc += ops41::bf16(exps[(size_t)r * h + i]);
        out[i] = ops41::bf16b(acc);
    }
};

// hc_pre: out[i] = sum_j mix[j] * streams[j][i] (serial over 4, host order).
struct HcPre {
    int h;
    void operator()(sycl::nd_item<1> it, const uint16_t *streams, const float *mix, uint16_t *out) const {
        int i = it.get_global_linear_id();
        if (i >= h) return;
        float acc = 0;
        for (int j = 0; j < 4; ++j) acc += mix[j] * ops41::bf16(streams[(size_t)j * h + i]);
        out[i] = ops41::bf16b(acc);
    }
};
// hc_post: streams'[j][i] = post[j]*x[i] + sum_k comb[k][j]*old[k][i]
// (comb is [src][dst], official Block.hc_post).
// `old` is a snapshot of streams (device memcpy first): in-place reads would
// race across work-items.
struct HcPost {
    int h;
    void operator()(sycl::nd_item<1> it, uint16_t *streams, const uint16_t *old,
                    const uint16_t *x, const float *post, const float *comb) const {
        int g = it.get_global_linear_id();
        int j = g / h, i = g % h;
        if (j >= 4) return;
        float acc = post[j] * ops41::bf16(x[i]);
        for (int k = 0; k < 4; ++k) acc += comb[k * 4 + j] * ops41::bf16(old[(size_t)k * h + i]);
        streams[(size_t)j * h + i] = ops41::bf16b(acc);
    }
};
struct HcMean {
    int h;
    void operator()(sycl::nd_item<1> it, const uint16_t *streams, uint16_t *out) const {
        int i = it.get_global_linear_id();
        if (i >= h) return;
        float acc = 0;
        for (int j = 0; j < 4; ++j) acc += ops41::bf16(streams[(size_t)j * h + i]);
        out[i] = ops41::bf16b(acc / 4);
    }
};

// window_append: one item; copies kv into ring slot, emits oldest-first idxs.
struct WindowAppend {
    int win, d, start_pos;
    void operator()(sycl::nd_item<1> it, uint16_t *ring, const uint16_t *kv, int32_t *idxs) const {
        if (it.get_global_linear_id() != 0) return;
        for (int i = 0; i < d; ++i) ring[(size_t)(start_pos % win) * d + i] = kv[i];
        int oldest = (start_pos % win + 1) % win; // wraps to slot 0 at win-1
        for (int i = 0, j = oldest; i < win; ++i, j = (j + 1) % win)
            idxs[i] = j > start_pos ? -1 : j;
    }
};

// sparse_attn decode row: one work-item per head; serial slot order as host.
// Dual bases: slot < win_rows reads the window ring, else kvc at
// slot-win_rows (compress mirror) -- matching the runner's win_ptr/comp_ptr.
struct SparseAttn {
    int n_idx, heads, hd, win_rows;
    void operator()(sycl::nd_item<1> it, const uint16_t *q, const uint16_t *kvw,
                    const uint16_t *kvc, const float *sinks, const int32_t *idxs,
                    float *out) const {
        int h = it.get_global_linear_id();
        if (h >= heads) return;
        const float scale = 1.0f / sycl::sqrt(float(hd));
        const uint16_t *qh = q + (size_t)h * hd;
        float logits[641]; // 128 window + 512 compress + sink
        logits[0] = sinks[h];
        int live = 1;
        for (int i = 0; i < n_idx; ++i) {
            int slot = idxs[i];
            if (slot < 0) continue;
            const uint16_t *k = slot < win_rows ? kvw + (size_t)slot * hd
                                                : kvc + (size_t)(slot - win_rows) * hd;
            float acc = 0;
            for (int j = 0; j < hd; ++j) acc += ops41::bf16(qh[j]) * ops41::bf16(k[j]);
            logits[live++] = acc * scale;
        }
        float mx = logits[0];
        for (int i = 1; i < live; ++i) mx = logits[i] > mx ? logits[i] : mx;
        float sum = 0;
        for (int i = 0; i < live; ++i) { logits[i] = sycl::exp(logits[i] - mx); sum += logits[i]; }
        float *o = out + (size_t)h * hd;
        for (int j = 0; j < hd; ++j) o[j] = 0;
        int li = 1;
        for (int i = 0; i < n_idx && li < live; ++i) {
            int slot = idxs[i];
            if (slot < 0) continue;
            float w = logits[li++] / sum;
            const uint16_t *k = slot < win_rows ? kvw + (size_t)slot * hd
                                                : kvc + (size_t)(slot - win_rows) * hd;
            for (int j = 0; j < hd; ++j) o[j] += w * ops41::bf16(k[j]);
        }
    }
};

// sparse_attn split into three launches with the SAME arithmetic order as
// SparseAttn (so the output is bit-identical) but 41k / 64 / 33k work-items
// instead of 64 long serial ones:
//   SparseScore   one item per (head, slot): serial dot over hd, * scale
//   SparseSoftmax one item per head: max, exp, sum in slot order (sink first)
//   SparseOut     one item per (head, j): serial sum over slots
// score is [heads][n_idx] f32; skipped slots (idx < 0) are never read.
struct SparseScore {
    int n_idx, heads, hd, win_rows;
    void operator()(sycl::nd_item<1> it, const uint16_t *q, const uint16_t *kvw, const uint16_t *kvc,
                    const int32_t *idxs, float *score) const {
        size_t g = it.get_global_linear_id();
        int h = (int)(g / n_idx), i = (int)(g % n_idx);
        if (h >= heads) return;
        int slot = idxs[i];
        if (slot < 0) return;
        const float scale = 1.0f / sycl::sqrt(float(hd));
        const uint16_t *qh = q + (size_t)h * hd;
        const uint16_t *k = slot < win_rows ? kvw + (size_t)slot * hd : kvc + (size_t)(slot - win_rows) * hd;
        float acc = 0;
        for (int j = 0; j < hd; ++j) acc += ops41::bf16(qh[j]) * ops41::bf16(k[j]);
        score[g] = acc * scale;
    }
};
struct SparseSoftmax {
    int n_idx, heads;
    void operator()(sycl::nd_item<1> it, const float *sinks, const int32_t *idxs, float *score) const {
        int h = it.get_global_linear_id();
        if (h >= heads) return;
        float *s = score + (size_t)h * n_idx;
        float mx = sinks[h];
        for (int i = 0; i < n_idx; ++i)
            if (idxs[i] >= 0) mx = s[i] > mx ? s[i] : mx;
        float sum = sycl::exp(sinks[h] - mx);
        for (int i = 0; i < n_idx; ++i)
            if (idxs[i] >= 0) { s[i] = sycl::exp(s[i] - mx); sum += s[i]; }
        for (int i = 0; i < n_idx; ++i)
            if (idxs[i] >= 0) s[i] = s[i] / sum;
    }
};
struct SparseOut {
    int n_idx, heads, hd, win_rows;
    void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                    const float *w, float *out) const {
        size_t g = it.get_global_linear_id();
        int h = (int)(g / hd), j = (int)(g % hd);
        if (h >= heads) return;
        const float *wh = w + (size_t)h * n_idx;
        float o = 0;
        for (int i = 0; i < n_idx; ++i) {
            int slot = idxs[i];
            if (slot < 0) continue;
            const uint16_t *k = slot < win_rows ? kvw + (size_t)slot * hd : kvc + (size_t)(slot - win_rows) * hd;
            o += wh[i] * ops41::bf16(k[j]);
        }
        out[g] = o;
    }
};

// compressor decode pooling: one item; kv_state/score_state [r][hd] f32,
// softmax per channel over slots, weighted sum, then RMSNorm into out.
struct CompressPool {
    int r, hd;
    void operator()(sycl::nd_item<1> it, const float *kv_state, const float *score_state,
                    const float *nw, uint16_t *out) const {
        if (it.get_global_linear_id() != 0) return;
        float tmp[512];
        for (int i = 0; i < hd; ++i) {
            float mx = score_state[i];
            for (int j = 1; j < r; ++j) mx = score_state[j * hd + i] > mx ? score_state[j * hd + i] : mx;
            float sum = 0, acc = 0;
            for (int j = 0; j < r; ++j) sum += sycl::exp(score_state[j * hd + i] - mx);
            for (int j = 0; j < r; ++j)
                acc += kv_state[j * hd + i] * (sycl::exp(score_state[j * hd + i] - mx) / sum);
            tmp[i] = acc;
        }
        double sq = 0;
        for (int i = 0; i < hd; ++i) sq += double(tmp[i]) * tmp[i];
        float rs = float(1.0 / sycl::sqrt(sq / hd + 1e-20));
        for (int i = 0; i < hd; ++i) out[i] = ops41::bf16b(nw[i] * (tmp[i] * rs));
    }
};

// indexer score: one item per (query, slot); serial head order as host.
struct IndexerScore {
    int H, dk, T_, m;
    void operator()(sycl::nd_item<1> it, const uint16_t *q, const uint16_t *k,
                    const uint16_t *w, const int64_t *lens, float *score) const {
        int g = it.get_global_linear_id();
        int t = g / T_, j = g % T_;
        if (t >= m) return;
        if (j >= lens[t]) { score[(size_t)t * T_ + j] = -INFINITY; return; }
        float s = 0;
        for (int hh = 0; hh < H; ++hh) {
            float d = 0;
            for (int i = 0; i < dk; ++i)
                d += ops41::bf16(q[((size_t)t * H + hh) * dk + i]) * ops41::bf16(k[(size_t)j * dk + i]);
            s += (d > 0 ? d : 0) * ops41::bf16(w[(size_t)t * H + hh]);
        }
        score[(size_t)t * T_ + j] = s;
    }
};
// indexer topk: one item per query; selection order as host (desc value,
// asc index ties), re-sorted ascending, +offset, >=len -> -1.
struct IndexerTopk {
    int T_, k, offset;
    void operator()(sycl::nd_item<1> it, const float *score, const int64_t *lens, int32_t *out) const {
        int t = it.get_global_linear_id();
        int len = (int)lens[t];
        int32_t sel[512];
        int nk = k < len ? k : len;
        for (int i = 0; i < nk; ++i) {
            int best = -1;
            for (int j = 0; j < T_; ++j) {
                bool taken = false;
                for (int s2 = 0; s2 < i; ++s2) if (sel[s2] == j) { taken = true; break; }
                if (taken) continue;
                if (best < 0 || score[(size_t)t * T_ + j] > score[(size_t)t * T_ + best] ||
                    (score[(size_t)t * T_ + j] == score[(size_t)t * T_ + best] && j < best)) best = j;
            }
            sel[i] = best;
        }
        // insertion sort ascending (nk small relative to 512; host used std::sort)
        for (int i = 1; i < nk; ++i) {
            int32_t v = sel[i];
            int j = i - 1;
            while (j >= 0 && sel[j] > v) { sel[j + 1] = sel[j]; --j; }
            sel[j + 1] = v;
        }
        for (int i = 0; i < k; ++i)
            out[(size_t)t * k + i] = i < nk ? sel[i] + offset : -1;
    }
};

// engram_gate: one item per hc copy; double accumulators in host order.
struct EngramGate {
    int h;
    void operator()(sycl::nd_item<1> it, uint16_t *streams, const uint16_t *kvbuf,
                    const float *gate_w) const {
        int j = it.get_global_linear_id();
        if (j >= 4) return;
        const float eps = 1e-20f, clamp_v = 1e-6f;
        double hsq = 0, ksq = 0;
        for (int i = 0; i < h; ++i) {
            float hv = ops41::bf16(streams[(size_t)j * h + i]);
            hsq += double(hv) * hv;
            float kvv = ops41::bf16(kvbuf[(size_t)j * h + i]);
            ksq += double(kvv) * kvv;
        }
        double dot = 0;
        for (int i = 0; i < h; ++i)
            dot += double(ops41::bf16(streams[(size_t)j * h + i])) * gate_w[(size_t)j * h + i] *
                   ops41::bf16(kvbuf[(size_t)j * h + i]);
        float rstd = float(1.0 / sycl::sqrt(hsq / h + eps) * (1.0 / sycl::sqrt(ksq / h + eps)));
        float d = float(dot) * rstd / sycl::sqrt(float(h));
        float g = 1.0f / (1.0f + sycl::exp(-sycl::copysign(sycl::sqrt(sycl::fmax(sycl::fabs(d), clamp_v)), d)));
        for (int i = 0; i < h; ++i)
            streams[(size_t)j * h + i] =
                ops41::bf16b(ops41::bf16(streams[(size_t)j * h + i]) + g * ops41::bf16(kvbuf[(size_t)4 * h + i]));
    }
};

// gemv_grouped: SG32 per row, bf16 weights; lane_dot order + tree32.
struct GemvGrouped {
    int groups, n, k;
    void operator()(sycl::nd_item<1> it, const uint16_t *o, const uint16_t *w, uint16_t *out) const {
        auto sg = it.get_sub_group();
        unsigned l = sg.get_local_linear_id();
        unsigned r = it.get_group_linear_id(); // [0, groups*n)
        int g = r / n;
        const uint16_t *row = w + (size_t)r * k;
        const uint16_t *xg = o + (size_t)g * k;
        float sum = 0;
        for (int i = l; i < k; i += 32)
            sum = sum + ops41::bf16(row[i]) * ops41::bf16(xg[i]);
        sum = sg_tree32(sg, sum);
        if (l == 0) out[r] = ops41::bf16b(sum);
    }
};

// gemv_grouped over a QUANTIZED weight ([groups*n, k] rows of any iq3 type):
// row r belongs to group r/n and reads that group's k-slice of o. Same lane
// order + tree32 as Gemv.
struct GemvGroupedQ {
    iq3::Type wtype; unsigned n, k;
    void operator()(sycl::nd_item<1> it, const uint8_t *w, size_t row_bytes_,
                    const uint16_t *o, uint16_t *out) const {
        auto sg = it.get_sub_group();
        unsigned l = sg.get_local_linear_id();
        unsigned r = it.get_group_linear_id();
        const uint8_t *row = w + (size_t)r * row_bytes_;
        const uint16_t *xg = o + (size_t)(r / n) * k;
        float sum = 0;
        for (unsigned i = l; i < k; i += 32)
            sum = sum + iq3::element(wtype, row, i) * ops41::bf16(xg[i]);
        sum = sg_tree32(sg, sum);
        if (l == 0) out[r] = ops41::bf16b(sum);
    }
};

// route41 on f32 logits (official model.py computes the router in F32;
// llama.cpp pins GGML_PREC_F32 on the same node). Same order as Route.
struct RouteF32 {
    int experts, topk;
    void operator()(sycl::nd_item<1> it, const float *logits, const float *bias,
                    uint32_t *ids, float *prob) const {
        if (it.get_global_linear_id() != 0) return;
        float s[384], sb[384];
        for (int i = 0; i < experts; ++i) {
            s[i] = sycl::sqrt(sycl::log1p(sycl::exp(logits[i])));
            sb[i] = s[i] + bias[i];
        }
        float sum = 0;
        for (int t = 0; t < topk; ++t) {
            int best = -1;
            for (int i = 0; i < experts; ++i)
                if (best < 0 || sb[i] > sb[best]) best = i;
            ids[t] = (uint32_t)best;
            prob[t] = s[best];
            sum += s[best];
            sb[best] = -INFINITY;
        }
        for (int t = 0; t < topk; ++t) prob[t] = prob[t] / (sum + 1e-20f) * 1.5f;
    }
};

// route41 in three launches, bit-identical to RouteF32 (one serial work-item
// doing 384 softplus + 6 x 384 scans cost ~0.3 ms per layer):
//   RouteScore one item per expert: s = sqrt(log1p(exp(logit))), sb = s + bias
//   RouteRank  one item per expert: its rank under (sb desc, index asc) --
//              exactly the order RouteF32's repeated first-max scan picks in;
//              ranks below topk write ids[rank] and the raw score
//   RouteNorm  one item: sum in rank order, prob = raw / (sum + 1e-20) * 1.5
struct RouteScore {
    int experts;
    void operator()(sycl::nd_item<1> it, const float *logits, const float *bias, float *s, float *sb) const {
        int i = it.get_global_linear_id();
        if (i >= experts) return;
        float v = sycl::sqrt(sycl::log1p(sycl::exp(logits[i])));
        s[i] = v;
        sb[i] = v + bias[i];
    }
};
struct RouteRank {
    int experts, topk;
    void operator()(sycl::nd_item<1> it, const float *s, const float *sb, uint32_t *ids, float *praw) const {
        int i = it.get_global_linear_id();
        if (i >= experts) return;
        const float v = sb[i];
        int rank = 0;
        for (int j = 0; j < experts; ++j) rank += (sb[j] > v || (sb[j] == v && j < i)) ? 1 : 0;
        if (rank < topk) {
            ids[rank] = (uint32_t)i;
            praw[rank] = s[i];
        }
    }
};
struct RouteNorm {
    int topk;
    void operator()(sycl::nd_item<1> it, float *prob) const {
        if (it.get_global_linear_id() != 0) return;
        float sum = 0;
        for (int t = 0; t < topk; ++t) sum += prob[t];
        for (int t = 0; t < topk; ++t) prob[t] = prob[t] / (sum + 1e-20f) * 1.5f;
    }
};

// hc_mix phase A: 24 items, serial double dot over 4*h in host order -> m[24].
// The rsqrt statistic is recomputed per item (grid-wide sync impossible in
// one launch); identical value everywhere since the loop order is fixed.
struct HcMixDots {
    int h;
    void operator()(sycl::nd_item<1> it, const uint16_t *streams, const float *fn, float *m24) const {
        int j = it.get_global_linear_id();
        if (j >= 24) return;
        int N = 4 * h;
        double sq = 0;
        for (int i = 0; i < N; ++i) { float v = ops41::bf16(streams[i]); sq += double(v) * v; }
        float rsqrt = float(1.0 / sycl::sqrt(sq / N + 1e-20));
        double acc = 0;
        for (int i = 0; i < N; ++i) acc += double(fn[(size_t)j * N + i]) * ops41::bf16(streams[i]);
        m24[j] = float(acc) * rsqrt;
    }
};
// hc_mix phase B: one item: split + sigmoid + 20 sinkhorn iters, host order.
struct HcMixFinish {
    void operator()(sycl::nd_item<1> it, const float *m24, const float *scale, const float *base,
                    float *pre, float *post, float *comb) const {
        if (it.get_global_linear_id() != 0) return;
        auto sig = [](float v) { return 1.0f / (1.0f + sycl::exp(-v)); };
        const float eps = 1e-6f;
        for (int j = 0; j < 4; ++j) pre[j] = sig(m24[j] * scale[0] + base[j]) + eps;
        for (int j = 0; j < 4; ++j) post[j] = 2.0f * sig(m24[4 + j] * scale[1] + base[4 + j]);
        for (int j = 0; j < 16; ++j) comb[j] = m24[8 + j] * scale[2] + base[8 + j];
        for (int j = 0; j < 4; ++j) {
            float mx = comb[j * 4];
            for (int k = 1; k < 4; ++k) mx = comb[j * 4 + k] > mx ? comb[j * 4 + k] : mx;
            float s = 0;
            for (int k = 0; k < 4; ++k) { comb[j * 4 + k] = sycl::exp(comb[j * 4 + k] - mx); s += comb[j * 4 + k]; }
            for (int k = 0; k < 4; ++k) comb[j * 4 + k] = comb[j * 4 + k] / s + eps;
        }
        for (int it2 = 0; it2 < 20; ++it2) {
            if (it2 > 0)
                for (int j = 0; j < 4; ++j) {
                    float s = 0;
                    for (int k = 0; k < 4; ++k) s += comb[j * 4 + k];
                    for (int k = 0; k < 4; ++k) comb[j * 4 + k] /= (s + eps);
                }
            for (int k = 0; k < 4; ++k) {
                float s = 0;
                for (int j = 0; j < 4; ++j) s += comb[j * 4 + k];
                for (int j = 0; j < 4; ++j) comb[j * 4 + k] /= (s + eps);
            }
        }
    }
};

// hc_mix in lane/tree form (anchor ops41::hc_mix_lanes): 25 sub-groups of 32
// lanes. Group r < 24: dot of fn row r with the flattened streams; group 24:
// sum of squares. Strided lanes in double, tree32 pairing, lane 0 writes.
struct HcMixDots32 {
    int h;
    void operator()(sycl::nd_item<1> it, const uint16_t *streams, const float *fn, double *out) const {
        auto sg = it.get_sub_group();
        unsigned l = sg.get_local_linear_id();
        unsigned r = it.get_group_linear_id();
        const int N = 4 * h;
        double acc = 0;
        if (r < 24) {
            for (int i = l; i < N; i += 32) acc += double(fn[(size_t)r * N + i]) * ops41::bf16(streams[i]);
        } else {
            for (int i = l; i < N; i += 32) { float v = ops41::bf16(streams[i]); acc += double(v) * v; }
        }
        for (unsigned w = 1; w < 32; w *= 2) {
            double o = sycl::select_from_group(sg, acc, (l + w) % 32);
            if (l % (2 * w) == 0) acc = acc + o;
        }
        if (l == 0) out[r] = acc;
    }
};
// finish from the 25 doubles: rsqrt statistic, 24 mixes, then HcMixFinish.
struct HcMixFinishD {
    int h;
    void operator()(sycl::nd_item<1> it, const double *d25, const float *scale, const float *base,
                    float *pre, float *post, float *comb) const {
        if (it.get_global_linear_id() != 0) return;
        const int N = 4 * h;
        float rsqrt = float(1.0 / sycl::sqrt(d25[24] / N + 1e-20));
        float m24[24];
        for (int j = 0; j < 24; ++j) m24[j] = float(d25[j]) * rsqrt;
        auto sig = [](float v) { return 1.0f / (1.0f + sycl::exp(-v)); };
        const float eps = 1e-6f;
        for (int j = 0; j < 4; ++j) pre[j] = sig(m24[j] * scale[0] + base[j]) + eps;
        for (int j = 0; j < 4; ++j) post[j] = 2.0f * sig(m24[4 + j] * scale[1] + base[4 + j]);
        for (int j = 0; j < 16; ++j) comb[j] = m24[8 + j] * scale[2] + base[8 + j];
        for (int j = 0; j < 4; ++j) {
            float mx = comb[j * 4];
            for (int k = 1; k < 4; ++k) mx = comb[j * 4 + k] > mx ? comb[j * 4 + k] : mx;
            float s = 0;
            for (int k = 0; k < 4; ++k) { comb[j * 4 + k] = sycl::exp(comb[j * 4 + k] - mx); s += comb[j * 4 + k]; }
            for (int k = 0; k < 4; ++k) comb[j * 4 + k] = comb[j * 4 + k] / s + eps;
        }
        for (int it2 = 0; it2 < 20; ++it2) {
            if (it2 > 0)
                for (int j = 0; j < 4; ++j) {
                    float s = 0;
                    for (int k = 0; k < 4; ++k) s += comb[j * 4 + k];
                    for (int k = 0; k < 4; ++k) comb[j * 4 + k] /= (s + eps);
                }
            for (int k = 0; k < 4; ++k) {
                float s = 0;
                for (int j = 0; j < 4; ++j) s += comb[j * 4 + k];
                for (int j = 0; j < 4; ++j) comb[j * 4 + k] /= (s + eps);
            }
        }
    }
};

// route41: single work-item; ops41::route order. s = sqrt(log1p(exp(logit))),
// top-k by s+bias (strict > keeps lowest id on ties), prob = s/(sum+1e-20)*1.5.
// logits bf16 buffer, bias f32, prob f32 out (feeds prob_scale41).
struct Route {
    int experts, topk;
    void operator()(sycl::nd_item<1> it, const uint16_t *logits,
                    const float *bias, uint32_t *ids, float *prob) const {
        if (it.get_global_linear_id() != 0) return;
        float s[384], sb[384];
        for (int i = 0; i < experts; ++i) {
            s[i] = sycl::sqrt(sycl::log1p(sycl::exp(ops41::bf16(logits[i]))));
            sb[i] = s[i] + bias[i];
        }
        float sum = 0;
        for (int t = 0; t < topk; ++t) {
            int best = -1;
            for (int i = 0; i < experts; ++i)
                if (best < 0 || sb[i] > sb[best]) best = i;
            ids[t] = (uint32_t)best;
            prob[t] = s[best];
            sum += s[best];
            sb[best] = -INFINITY;
        }
        for (int t = 0; t < topk; ++t) prob[t] = prob[t] / (sum + 1e-20f) * 1.5f;
    }
};

// argmax over f32 logits, tree reduce with first-max tie-break (host
// std::max_element order). One work-group; block partials then serial tail.
struct Argmax {
    int n;
    void operator()(sycl::nd_item<1> it, const float *logits, int32_t *out,
                    float *scratch) const {
        int lane = it.get_local_linear_id();
        sycl::sub_group sg = it.get_sub_group();
        float bv = -INFINITY; int bi = n;
        for (int i = lane; i < n; i += 32)
            if (logits[i] > bv) { bv = logits[i]; bi = i; }
        for (int w = 16; w; w >>= 1) {
            float ov = sycl::select_from_group(sg, bv, lane ^ w);
            int oi = sycl::select_from_group(sg, bi, lane ^ w);
            if (ov > bv || (ov == bv && oi < bi)) { bv = ov; bi = oi; }
        }
        if (lane == 0) *out = bi;
    }
};

// embedding row: decode one quant row to bf16 (engram-free token lookup).
struct EmbedRow {
    iq3::Type t; int cols;
    void operator()(sycl::nd_item<1> it, const uint8_t *row, uint16_t *out) const {
        int i = it.get_global_linear_id();
        if (i >= cols) return;
        auto l = iq3::layout(t);
        out[i] = ops41::bf16b(
            iq3::decode(t, row + (size_t)(i / l.elements) * l.bytes, i % l.elements));
    }
};

// candidate mask application: score[j] = mask[j] ? score[j] : -inf
struct MaskApply {
    int T_;
    void operator()(sycl::nd_item<1> it, float *score, const uint8_t *mask) const {
        int j = it.get_global_linear_id();
        if (j >= T_) return;
        if (!mask[j]) score[j] = -INFINITY;
    }
};

// f32 -> bf16 row convert (sparse_attn f32 out feeds rope/grouped gemv in bf16)
struct ToBf16 {
    int n;
    void operator()(sycl::nd_item<1> it, const float *x, uint16_t *y) const {
        int i = it.get_global_linear_id();
        if (i >= n) return;
        y[i] = ops41::bf16b(x[i]);
    }
};

// broadcast: streams[j][i] = x[i] for all 4 streams (identity at token start).
struct Broadcast4 {
    int h;
    void operator()(sycl::nd_item<1> it, const uint16_t *x, uint16_t *streams) const {
        int i = it.get_global_linear_id();
        if (i >= h) return;
        uint16_t v = x[i];
        for (int j = 0; j < 4; ++j) streams[(size_t)j * h + i] = v;
    }
};

// routed_gemv: group per (slot, row); expert bank row = ids[slot]*rows + row.
// Lane order/tree32 identical to Gemv -> bit-exact vs host per-expert gemv.
struct RoutedGemv {
    iq3::Type t; unsigned rows, cols; // per-expert matrix shape
    bool per_slot_x = false;          // down: x is [6][cols], one row per slot
    void operator()(sycl::nd_item<1> it, const uint8_t *w, const uint16_t *x,
                    const uint32_t *ids, uint16_t *out) const {
        unsigned g = it.get_global_linear_id();
        unsigned slot = g / (rows * 32), r = (g / 32) % rows;
        if (slot >= 6) return;
        auto l = iq3::layout(t);
        size_t rb = (size_t)(cols / l.elements) * l.bytes;
        const uint8_t *row = w + ((size_t)ids[slot] * rows + r) * rb;
        sycl::sub_group sg = it.get_sub_group();
        int lane = it.get_local_linear_id();
        const uint16_t *xs = per_slot_x ? x + (size_t)slot * cols : x;
        float a = iq3::lane_dot(t, row, xs, iq3::Type::BF16, cols, lane);
        for (int w_ = 16; w_; w_ >>= 1)
            a += sycl::select_from_group(sg, a, lane ^ w_);
        if (lane == 0) out[slot * rows + r] = ops41::bf16b(a);
    }
};

// bf16 -> f32 (compressor group state writes)
struct ToF32 {
    int n;
    void operator()(sycl::nd_item<1> it, const uint16_t *x, float *y) const {
        int i = it.get_global_linear_id();
        if (i >= n) return;
        y[i] = ops41::bf16(x[i]);
    }
};

// candidate blocks (layer 20, decode m=1): per-channel max over 8-blocks,
// last block forced, top-2048 selection (fixture select_candidate_blocks
// order: strict >, first-max ties, -inf dropped), mask bytes out.
struct CandidateBlocks {
    int T_, bs, topk_blocks;
    void operator()(sycl::nd_item<1> it, const float *score, const int64_t *lens,
                    uint8_t *mask) const {
        if (it.get_global_linear_id() != 0) return;
        int nb = (T_ + bs - 1) / bs;
        float bsc[2048];
        for (int b = 0; b < nb; ++b) bsc[b] = -INFINITY;
        for (int j = 0; j < T_; ++j) {
            float v = score[j];
            if (v > bsc[j / bs]) bsc[j / bs] = v;
        }
        int last = (int)((lens[0] - 1) / bs);
        bsc[last] = INFINITY;
        uint8_t keep[2048] = {};
        for (int i = 0; i < topk_blocks && i < nb; ++i) {
            int best = -1;
            for (int b = 0; b < nb; ++b) {
                if (keep[b]) continue;
                if (best < 0 || bsc[b] > bsc[best] || (bsc[b] == bsc[best] && b < best)) best = b;
            }
            if (best < 0 || bsc[best] == -INFINITY) break;
            keep[best] = 1;
        }
        for (int j = 0; j < T_; ++j) mask[j] = keep[j / bs];
    }
};

// ---- activation-generic forms (A = ActBF16 or ActF32) of the kernels the
// executor launches. With A = ActBF16 each is the same arithmetic as its
// BF16 namesake above (the decode trace stays byte-identical). KV rows are
// always BF16.
template <typename A> struct RmsNormA {
    int n;
    void operator()(sycl::nd_item<1> it, const typename A::T *x, const float *w, typename A::T *y) const {
        int lane = it.get_local_linear_id();
        sycl::sub_group sg = it.get_sub_group();
        int base = it.get_group_linear_id() * n;
        double acc = 0;
        for (int i = lane; i < n; i += 32) {
            float v = A::rd(x[base + i]);
            acc += double(v) * v;
        }
        for (int w_ = 16; w_; w_ >>= 1)
            acc += sycl::select_from_group(sg, acc, lane ^ w_);
        float rs = float(1.0 / sycl::sqrt(acc / n + 1e-20));
        for (int i = lane; i < n; i += 32)
            y[base + i] = A::wr(w[i] * (A::rd(x[base + i]) * rs));
    }
};
template <typename A> struct RopePairsA {
    unsigned rows, d, rdim; bool inverse;
    void operator()(sycl::nd_item<1> it, typename A::T *x, const float *cosb, const float *sinb) const {
        unsigned g = it.get_global_linear_id();
        unsigned pairs = rdim / 2;
        unsigned r = g / pairs, i = g % pairs;
        if (r >= rows) return;
        typename A::T *row = x + (size_t)r * d + (d - rdim);
        float re = A::rd(row[2 * i]), im = A::rd(row[2 * i + 1]);
        float c = cosb[i], s = inverse ? -sinb[i] : sinb[i];
        row[2 * i] = A::wr(re * c - im * s);
        row[2 * i + 1] = A::wr(re * s + im * c);
    }
};
template <typename A> struct SwigluA {
    long long n; float lim;
    void operator()(sycl::nd_item<1> it, const typename A::T *gate, const typename A::T *up, typename A::T *out) const {
        long long i = it.get_global_linear_id();
        if (i >= n) return;
        float g = sycl::fmin(A::rd(gate[i]), lim);
        float u = sycl::clamp(A::rd(up[i]), -lim, lim);
        out[i] = A::wr(g / (1.0f + sycl::exp(-g)) * u);
    }
};
template <typename A> struct ProbScaleA {
    int rows, n;
    void operator()(sycl::nd_item<1> it, typename A::T *act, const float *prob) const {
        int g = it.get_global_linear_id();
        int r = g / n, i = g % n;
        if (r >= rows) return;
        act[(size_t)r * n + i] = A::wr(prob[r] * A::rd(act[(size_t)r * n + i]));
    }
};
template <typename A> struct MoeCombineA {
    int top, h;
    void operator()(sycl::nd_item<1> it, const typename A::T *exps, const typename A::T *shared, typename A::T *out) const {
        int i = it.get_global_linear_id();
        if (i >= h) return;
        float acc = A::rd(shared[i]);
        for (int r = 0; r < top; ++r) acc += A::rd(exps[(size_t)r * h + i]);
        out[i] = A::wr(acc);
    }
};
template <typename A> struct HcPreA {
    int h;
    void operator()(sycl::nd_item<1> it, const typename A::T *streams, const float *mix, typename A::T *out) const {
        int i = it.get_global_linear_id();
        if (i >= h) return;
        float acc = 0;
        for (int j = 0; j < 4; ++j) acc += mix[j] * A::rd(streams[(size_t)j * h + i]);
        out[i] = A::wr(acc);
    }
};
template <typename A> struct HcPostA {
    int h;
    void operator()(sycl::nd_item<1> it, typename A::T *streams, const typename A::T *old, const typename A::T *x,
                    const float *post, const float *comb) const {
        int g = it.get_global_linear_id();
        int j = g / h, i = g % h;
        if (j >= 4) return;
        float acc = post[j] * A::rd(x[i]);
        for (int k = 0; k < 4; ++k) acc += comb[k * 4 + j] * A::rd(old[(size_t)k * h + i]);
        streams[(size_t)j * h + i] = A::wr(acc);
    }
};
// window_append: the KV row is stored BF16 whatever the activation type
template <typename A> struct WindowAppendA {
    int win, d, start_pos;
    void operator()(sycl::nd_item<1> it, uint16_t *ring, const typename A::T *kv, int32_t *idxs) const {
        if (it.get_global_linear_id() != 0) return;
        for (int i = 0; i < d; ++i) ring[(size_t)(start_pos % win) * d + i] = ops41::bf16b(A::rd(kv[i]));
        int oldest = (start_pos % win + 1) % win;
        for (int i = 0, j = oldest; i < win; ++i, j = (j + 1) % win)
            idxs[i] = j > start_pos ? -1 : j;
    }
};
template <typename A> struct SparseScoreA {
    int n_idx, heads, hd, win_rows;
    void operator()(sycl::nd_item<1> it, const typename A::T *q, const uint16_t *kvw, const uint16_t *kvc,
                    const int32_t *idxs, float *score) const {
        size_t g = it.get_global_linear_id();
        int h = (int)(g / n_idx), i = (int)(g % n_idx);
        if (h >= heads) return;
        int slot = idxs[i];
        if (slot < 0) return;
        const float scale = 1.0f / sycl::sqrt(float(hd));
        const typename A::T *qh = q + (size_t)h * hd;
        const uint16_t *k = slot < win_rows ? kvw + (size_t)slot * hd : kvc + (size_t)(slot - win_rows) * hd;
        float acc = 0;
        for (int j = 0; j < hd; ++j) acc += A::rd(qh[j]) * ops41::bf16(k[j]);
        score[g] = acc * scale;
    }
};
template <typename A> struct CompressPoolA {
    int r, hd;
    void operator()(sycl::nd_item<1> it, const float *kv_state, const float *score_state, const float *nw,
                    typename A::T *out) const {
        if (it.get_global_linear_id() != 0) return;
        float tmp[512];
        for (int i = 0; i < hd; ++i) {
            float mx = score_state[i];
            for (int j = 1; j < r; ++j) mx = score_state[j * hd + i] > mx ? score_state[j * hd + i] : mx;
            float sum = 0, acc = 0;
            for (int j = 0; j < r; ++j) sum += sycl::exp(score_state[j * hd + i] - mx);
            for (int j = 0; j < r; ++j)
                acc += kv_state[j * hd + i] * (sycl::exp(score_state[j * hd + i] - mx) / sum);
            tmp[i] = acc;
        }
        double sq = 0;
        for (int i = 0; i < hd; ++i) sq += double(tmp[i]) * tmp[i];
        float rs = float(1.0 / sycl::sqrt(sq / hd + 1e-20));
        for (int i = 0; i < hd; ++i) out[i] = A::wr(nw[i] * (tmp[i] * rs));
    }
};
// indexer score: query and head weights are activations, keys are BF16 KV rows
template <typename A> struct IndexerScoreA {
    int H, dk, T_, m;
    void operator()(sycl::nd_item<1> it, const typename A::T *q, const uint16_t *k, const typename A::T *w,
                    const int64_t *lens, float *score) const {
        int g = it.get_global_linear_id();
        int t = g / T_, j = g % T_;
        if (t >= m) return;
        if (j >= lens[t]) { score[(size_t)t * T_ + j] = -INFINITY; return; }
        float s = 0;
        for (int hh = 0; hh < H; ++hh) {
            float d = 0;
            for (int i = 0; i < dk; ++i)
                d += A::rd(q[((size_t)t * H + hh) * dk + i]) * ops41::bf16(k[(size_t)j * dk + i]);
            s += (d > 0 ? d : 0) * A::rd(w[(size_t)t * H + hh]);
        }
        score[(size_t)t * T_ + j] = s;
    }
};
// IndexerScoreA for one token (m = 1, H = 32, dk = 128) with each row's sums in the
// same order (heads in order, each head's 128 products in order), but the row's keys
// read once: the query and head weights sit in local memory and the 32 head sums run
// side by side. One item per row, 16-lane sub-groups; rows [len, T_) get -inf as in A.
// Local memory: 32 * 128 + 32 floats.
template <typename A> struct IndexerScoreB {
    static constexpr int H = 32, DK = 128, CH = 16;
    int len, T_;
    void operator()(sycl::nd_item<1> it, const typename A::T *q, const uint16_t *k, const typename A::T *w,
                    float *score, float *lq) const {
        run(it, (int)it.get_global_linear_id(), q, k, w, score, lq);
    }
    // row j on this item (the multi-token form, IndexerScoreBM, numbers rows per token)
    [[gnu::always_inline]] inline void run(sycl::nd_item<1> it, int j, const typename A::T *q, const uint16_t *k,
                                           const typename A::T *w, float *score, float *lq) const {
        const int lid = (int)it.get_local_linear_id(), nl = (int)it.get_local_range(0);
        for (int i = lid; i < H * DK; i += nl) lq[i] = A::rd(q[i]);
        for (int i = lid; i < H; i += nl) lq[H * DK + i] = A::rd(w[i]);
        sycl::group_barrier(it.get_group());
        if (j >= len) {
            if (j < T_) score[j] = -INFINITY;
            return;
        }
        float d[H];
#pragma unroll
        for (int hh = 0; hh < H; ++hh) d[hh] = 0;
        const uint16_t *kr = k + (size_t)j * DK;
        for (int i0 = 0; i0 < DK; i0 += CH) {
            float kf[CH];
#pragma unroll
            for (int ii = 0; ii < CH; ++ii) kf[ii] = ops41::bf16(kr[i0 + ii]);
#pragma unroll
            for (int hh = 0; hh < H; ++hh)
#pragma unroll
                for (int ii = 0; ii < CH; ++ii) d[hh] += lq[hh * DK + i0 + ii] * kf[ii];
        }
        float s = 0;
#pragma unroll
        for (int hh = 0; hh < H; ++hh) s += (d[hh] > 0 ? d[hh] : 0) * lq[H * DK + hh];
        score[j] = s;
    }
};
// IndexerScoreB over the layer-20 candidate rows only (OWN_IDX_CAND): item i scores row bl[1 + i / 8] * 8 + i % 8
// (bl as TopKSelC's, blocks of 8 rows) with IndexerScoreB::run, so each row's sum is the same; the other rows'
// scores are not written (TopKSelC reads the candidate rows only).
template <typename A> struct IndexerScoreBC {
    IndexerScoreB<A> b;
    void operator()(sycl::nd_item<1> it, const typename A::T *q, const uint16_t *k, const typename A::T *w,
                    float *score, const int32_t *bl, float *lq) const {
        const int i = (int)it.get_global_linear_id();
        int j = b.T_; // no row: run() writes nothing at or past T_
        if ((i >> 3) < bl[0]) {
            const int r = bl[1 + (i >> 3)] * 8 + (i & 7);
            if (r < b.len) j = r;
        }
        b.run(it, j, q, k, w, score, lq);
    }
};
template <typename A> struct EngramGateA {
    int h;
    void operator()(sycl::nd_item<1> it, typename A::T *streams, const typename A::T *kvbuf, const float *gate_w) const {
        int j = it.get_global_linear_id();
        if (j >= 4) return;
        const float eps = 1e-20f, clamp_v = 1e-6f;
        double hsq = 0, ksq = 0;
        for (int i = 0; i < h; ++i) {
            float hv = A::rd(streams[(size_t)j * h + i]);
            hsq += double(hv) * hv;
            float kvv = A::rd(kvbuf[(size_t)j * h + i]);
            ksq += double(kvv) * kvv;
        }
        double dot = 0;
        for (int i = 0; i < h; ++i)
            dot += double(A::rd(streams[(size_t)j * h + i])) * gate_w[(size_t)j * h + i] *
                   A::rd(kvbuf[(size_t)j * h + i]);
        float rstd = float(1.0 / sycl::sqrt(hsq / h + eps) * (1.0 / sycl::sqrt(ksq / h + eps)));
        float d = float(dot) * rstd / sycl::sqrt(float(h));
        float g = 1.0f / (1.0f + sycl::exp(-sycl::copysign(sycl::sqrt(sycl::fmax(sycl::fabs(d), clamp_v)), d)));
        for (int i = 0; i < h; ++i)
            streams[(size_t)j * h + i] =
                A::wr(A::rd(streams[(size_t)j * h + i]) + g * A::rd(kvbuf[(size_t)4 * h + i]));
    }
};
// hc_mix statistics, segmented: the 20480 columns are cut into SEG equal
// segments; group (r, seg) sums its segment as 32 strided double lanes +
// tree32 into out[r * SEG + seg]; the finish kernel adds a row's segments
// in order. 25 rows x 8 segments = 200 hardware threads instead of 25
// (anchor: ops41::hc_mix_lanes with the same segment count).
template <typename A> struct HcMixDots32A {
    int h, seg;
    void operator()(sycl::nd_item<1> it, const typename A::T *streams, const float *fn, double *out) const {
        auto sg = it.get_sub_group();
        unsigned l = sg.get_local_linear_id();
        const unsigned grp = it.get_group_linear_id();
        const unsigned r = grp / seg, sgi = grp % seg;
        const int N = 4 * h, len = N / seg;
        const int i0 = (int)sgi * len, i1 = i0 + len;
        double acc = 0;
        if (r < 24) {
            for (int i = i0 + (int)l; i < i1; i += 32) acc += double(fn[(size_t)r * N + i]) * A::rd(streams[i]);
        } else {
            for (int i = i0 + (int)l; i < i1; i += 32) { float v = A::rd(streams[i]); acc += double(v) * v; }
        }
        for (unsigned w = 1; w < 32; w *= 2) {
            double o = sycl::select_from_group(sg, acc, (l + w) % 32);
            if (l % (2 * w) == 0) acc = acc + o;
        }
        if (l == 0) out[grp] = acc;
    }
};
struct HcMixFinishSeg {
    int h, seg;
    void operator()(sycl::nd_item<1> it, const double *d, const float *scale, const float *base,
                    float *pre, float *post, float *comb) const {
        if (it.get_global_linear_id() != 0) return;
        const int N = 4 * h;
        double tot[25];
        for (int r = 0; r < 25; ++r) {
            double t = 0;
            for (int k = 0; k < seg; ++k) t += d[r * seg + k];
            tot[r] = t;
        }
        float rsqrt = float(1.0 / sycl::sqrt(tot[24] / N + 1e-20));
        float m24[24];
        for (int j = 0; j < 24; ++j) m24[j] = float(tot[j]) * rsqrt;
        auto sig = [](float v) { return 1.0f / (1.0f + sycl::exp(-v)); };
        const float eps = 1e-6f;
        for (int j = 0; j < 4; ++j) pre[j] = sig(m24[j] * scale[0] + base[j]) + eps;
        for (int j = 0; j < 4; ++j) post[j] = 2.0f * sig(m24[4 + j] * scale[1] + base[4 + j]);
        for (int j = 0; j < 16; ++j) comb[j] = m24[8 + j] * scale[2] + base[8 + j];
        for (int j = 0; j < 4; ++j) {
            float mx = comb[j * 4];
            for (int k = 1; k < 4; ++k) mx = comb[j * 4 + k] > mx ? comb[j * 4 + k] : mx;
            float sm = 0;
            for (int k = 0; k < 4; ++k) { comb[j * 4 + k] = sycl::exp(comb[j * 4 + k] - mx); sm += comb[j * 4 + k]; }
            for (int k = 0; k < 4; ++k) comb[j * 4 + k] = comb[j * 4 + k] / sm + eps;
        }
        for (int it2 = 0; it2 < 20; ++it2) {
            if (it2 > 0)
                for (int j = 0; j < 4; ++j) {
                    float sm = 0;
                    for (int k = 0; k < 4; ++k) sm += comb[j * 4 + k];
                    for (int k = 0; k < 4; ++k) comb[j * 4 + k] /= (sm + eps);
                }
            for (int k = 0; k < 4; ++k) {
                float sm = 0;
                for (int j = 0; j < 4; ++j) sm += comb[j * 4 + k];
                for (int j = 0; j < 4; ++j) comb[j * 4 + k] /= (sm + eps);
            }
        }
    }
};
template <typename A> struct ToActA { // f32 -> activation
    int n;
    void operator()(sycl::nd_item<1> it, const float *x, typename A::T *y) const {
        int i = it.get_global_linear_id();
        if (i >= n) return;
        y[i] = A::wr(x[i]);
    }
};
template <typename A> struct ToF32A { // activation -> f32
    int n;
    void operator()(sycl::nd_item<1> it, const typename A::T *x, float *y) const {
        int i = it.get_global_linear_id();
        if (i >= n) return;
        y[i] = A::rd(x[i]);
    }
};
template <typename A> struct Broadcast4A {
    int h;
    void operator()(sycl::nd_item<1> it, const typename A::T *x, typename A::T *streams) const {
        int i = it.get_global_linear_id();
        if (i >= h) return;
        typename A::T v = x[i];
        for (int j = 0; j < 4; ++j) streams[(size_t)j * h + i] = v;
    }
};
// Broadcast4A plus the first stream mix's pre weights {1, 0, 0, 0} (items 0..3), which tp_embed copied from the
// host before (OWN_PRE_K, 2026-11-11: a 16-byte copy from host memory runs on the host after the queue drains,
// ~24 us of idle card per step in the tg87 timeline); the same values
template <typename A> struct Broadcast4PA {
    int h;
    void operator()(sycl::nd_item<1> it, const typename A::T *x, typename A::T *streams, float *pre) const {
        int i = it.get_global_linear_id();
        if (i < 4) pre[i] = i == 0 ? 1.0f : 0.0f;
        if (i >= h) return;
        typename A::T v = x[i];
        for (int j = 0; j < 4; ++j) streams[(size_t)j * h + i] = v;
    }
};
template <typename A> struct EmbedRowA {
    iq3::Type t; int cols;
    void operator()(sycl::nd_item<1> it, const uint8_t *row, typename A::T *out) const {
        int i = it.get_global_linear_id();
        if (i >= cols) return;
        auto l = iq3::layout(t);
        out[i] = A::wr(iq3::decode(t, row + (size_t)(i / l.elements) * l.bytes, i % l.elements));
    }
};

// n engram rows of one Q5_K block each (176 bytes -> 256 values), EmbedRowA's decode per value
template <typename A> struct EngRowsA {
    unsigned n;
    void operator()(sycl::nd_item<1> it, const uint8_t *raw, typename A::T *out) const {
        const unsigned i = (unsigned)it.get_global_linear_id();
        if (i >= n * 256u) return;
        out[i] = A::wr(iq3::decode(iq3::Type::Q5_K, raw + (size_t)(i / 256u) * 176u, i % 256u));
    }
};

// ---- kernels over packed rows (layouts: pack_v41.hpp) ------------------------
// Same float operations in the same order as lane_sum_t / GemvT / RoutedGemvT
// (bit-identical outputs, gated per format in test_ops_v41_device.cpp), but:
//  * a row's quant words arrive in a few aligned sub-group block reads issued
//    up front, instead of many dependent 1-2 byte loads (the old kernels were
//    bound by memory latency per sub-group, ~70-250 GB/s);
//  * per-block values (scales, grid-index words) are computed lane-parallel
//    once and broadcast from a constant lane (free register-region operands);
//  * grid magnitudes come from a float table in shared local memory (32-bit
//    addresses, no byte->float conversion), filled once per work-group.
// Activations must be f32 (the default executor build).
template <typename T> inline T sg_bload(sycl::sub_group sg, const T *p) {
    return sg.load(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
        const_cast<T *>(p)));
}
template <int N, typename T> inline sycl::vec<T, N> sg_bloadN(sycl::sub_group sg, const T *p) {
    return sg.load<N>(sycl::address_space_cast<sycl::access::address_space::global_space,
                                                sycl::access::decorated::yes>(const_cast<T *>(p)));
}
// RoutedGemvT<Q2_K> (layer 0's expert down rows, GGUF layout, 84-byte blocks) with the block's bytes read by
// sub-group loads instead of per-element gathers. Lane l's sum is lane_sum_t's generic branch: chunks c
// ascending, element i = (c % 8) * 32 + l of block c / 8, value iq3::decode's (dl * float(q)) - ml with
// dl = d * float(sc & 15), ml = dmin * float(sc >> 4), then sum + value * x; the same xor butterfly.
// Launch as RoutedGemvT (one sub-group per work-group, group = slot * rows + row). Gate:
// tools/bench/bench_routed_m1.cpp (bitwise against RoutedGemvT<Q2_K>).
template <unsigned NB> struct RoutedQ2KF {
    unsigned rows, cols; // per-expert matrix shape (cols == NB * 256)
    bool per_slot_x = false;
    unsigned nsl = 6, xtok = 0;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out) const {
        const unsigned grp = it.get_group_linear_id();
        const unsigned slot = grp / rows, r = grp % rows;
        if (slot >= nsl) return;
        const uint8_t *row = w + ((size_t)ids[slot] * rows + r) * ((size_t)NB * 84);
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const float *xs = x + (size_t)(slot / 6) * xtok + (per_slot_x ? (size_t)(slot % 6) * NB * 256 : 0);
        float sum = 0;
        for (unsigned b = 0; b < NB; ++b) {
            const uint8_t *bk = row + (size_t)b * 84;
            // scales bytes 0..15 (lane l < 16 holds byte l), quants bytes 16..79 (lane l holds 16 + l, 48 + l)
            const unsigned scl = lane < 16 ? bk[lane] : 0u;
            const unsigned q0 = bk[16 + lane], q1 = bk[48 + lane];
            const float d = iq3::half(iq3::u16(bk + 80)), dm = iq3::half(iq3::u16(bk + 82));
            const auto xv = sg_bloadN<8>(sg, xs + (size_t)b * 256);
#pragma unroll
            for (unsigned cc = 0; cc < 8; ++cc) { // chunk 8b + cc: h = cc / 4, j = cc % 4
                const unsigned h = cc / 4, j = cc % 4;
                const unsigned s0 = sycl::select_from_group(sg, scl, 8 * h + 2 * j);
                const unsigned s1 = sycl::select_from_group(sg, scl, 8 * h + 2 * j + 1);
                const unsigned sc = lane < 16 ? s0 : s1;
                const float dl = d * float(sc & 15), ml = dm * float(sc >> 4);
                const unsigned q = ((h ? q1 : q0) >> (2 * j)) & 3;
                sum = sum + (dl * float(q) - ml) * xv[cc];
            }
        }
        for (int w_ = 16; w_; w_ >>= 1) sum += sycl::select_from_group(sg, sum, (int)lane ^ w_);
        if (lane == 0) out[slot * rows + r] = sum;
    }
};
// Words [32k, 32k + 32) of the NW quant words at the start of a packed row:
// one block read when all 32 lie inside them, else a per-lane load of those
// that do (0 above). A block read past the quant words could run past the row
// and, on the last row of a bank, past the allocation (page fault, 2026-11-09:
// IQ2_XXS with 9 blocks per row has 144 quant words in a 152-word row).
template <unsigned NW> inline uint32_t row_words(sycl::sub_group sg, const uint32_t *rw, unsigned k, unsigned lane) {
    if (32 * k + 32 <= NW) return sg_bload(sg, rw + 32 * k);
    return 32 * k + lane < NW ? rw[32 * k + lane] : 0u;
}
inline unsigned packed_row_id(const sycl::nd_item<1> &it) {
    return it.get_group_linear_id() * (unsigned)(it.get_local_range(0) / 32) +
           it.get_sub_group().get_group_linear_id();
}

// Q8_0, C chunks per row. Row r reads x + (r / xn) * 32C when xn > 0 (the
// grouped output LoRA), else x. Reduction sg_tree32, as GemvT / GemvGroupedQT.
// Q8Seg<C, NT>: quant words per load segment. rowg for groups of 3 tokens on rows of 32+ words, and of 2 tokens on
// rows of 40+ words, loads every quant word before the first product: bench_q8_rows (round18 e69pre, 230 W card,
// cold) 5120 columns x 1024 rows 5 tokens 24.0 -> 20.9 us, 8192 x 864 35.9 -> 29.2, 4096 x 864 19.9 -> 17.1;
// 4 tokens 5120 x 1024 18.3 -> 17.2, 8192 x 864 25.9 -> 22.5. Same products in the same order (bitwise). One
// token, 2304 columns, and 2 tokens on 4096 columns (14.4 -> 22.9) keep the 8 / 6 word segments.
template <unsigned C, unsigned NT = 1> struct Q8Seg {
    static constexpr unsigned NQ = C / 4, b = NQ % 8 == 0 ? 8 : (NQ <= 10 ? NQ : 6);
    static constexpr unsigned v = (NT == 3 && NQ >= 32) || (NT == 2 && NQ >= 40) ? NQ : b;
};
template <unsigned C, typename A> struct GemvQ8P {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static_assert(C % 4 == 0);
    unsigned rows, xn;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, float *y) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned r = packed_row_id(it);
        if (r >= rows) return;
        row(sg, sg.get_local_linear_id(), r, w, x, y);
    }
    // one row on one sub-group (also run inside fused launches: DenseRows)
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                           const float *x, float *y) const {
        constexpr unsigned NQ = C / 4, SEGQ = Q8Seg<C>::v, ND = (C + 31) / 32;
        static_assert(NQ % SEGQ == 0);
        constexpr size_t RB = ((size_t)C * 34 + 15) & ~(size_t)15;
        const uint8_t *row = w + (size_t)r * RB;
        const float *xr = xn ? x + (size_t)(r / xn) * C * 32 : x;
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)C * 32);
        float dv[ND];
#pragma unroll
        for (unsigned k = 0; k < ND; ++k) dv[k] = 32 * k + lane < C ? iq3::half(dp[32 * k + lane]) : 0.0f;
        const uint32_t *qw = reinterpret_cast<const uint32_t *>(row);
        float sum = 0;
        // fully unrolled: every chunk index, register and broadcast lane is a constant
#pragma unroll
        for (unsigned s0 = 0; s0 < NQ; s0 += SEGQ) {
            uint32_t q[SEGQ];
#pragma unroll
            for (unsigned m = 0; m < SEGQ; ++m) q[m] = sg_bload(sg, qw + (size_t)(s0 + m) * 32);
#pragma unroll
            for (unsigned m = 0; m < SEGQ; ++m) {
                const auto xv = sg_bloadN<4>(sg, xr + (size_t)(s0 + m) * 128);
#pragma unroll
                for (unsigned k = 0; k < 4; ++k) {
                    const unsigned c = (s0 + m) * 4 + k;
                    const float d = sycl::select_from_group(sg, dv[c / 32], c % 32);
                    const float e = d * float(int8_t(uint8_t(q[m] >> (8 * k)))); // iq3::decode Q8_0
                    sum = sum + e * xv[k];
                }
            }
        }
        sum = sg_tree32(sg, sum);
        if (lane == 0) y[r] = sum;
    }
    // M tokens (see "multi-token rows" at lane_sum_tm): token t reads x + t * xs (then row()'s r / xn
    // group offset) and writes y[t * ys + r] when t < mt; xs % 4 == 0 (block reads).
    static constexpr unsigned MTG = 8;
    template <unsigned MT, unsigned G = MTG, unsigned T0 = 0>
    [[gnu::always_inline]] inline void rowm(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        if constexpr (T0 < MT) {
            constexpr unsigned NT = MT - T0 < G ? MT - T0 : G;
            if (T0 < mt) rowg<NT>(sg, lane, r, w, x + T0 * xs, xs, y + T0 * ys, ys, mt - T0);
            rowm<MT, G, T0 + NT>(sg, lane, r, w, x, xs, y, ys, mt);
        }
    }
    template <unsigned NT>
    [[gnu::always_inline]] inline void rowg(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        constexpr unsigned NQ = C / 4, SEGQ = Q8Seg<C, NT>::v, ND = (C + 31) / 32;
        static_assert(NQ % SEGQ == 0);
        constexpr size_t RB = ((size_t)C * 34 + 15) & ~(size_t)15;
        const uint8_t *row = w + (size_t)r * RB;
        const float *xr = xn ? x + (size_t)(r / xn) * C * 32 : x; // token t: xr + t * xs
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)C * 32);
        float dv[ND];
#pragma unroll
        for (unsigned k = 0; k < ND; ++k) dv[k] = 32 * k + lane < C ? iq3::half(dp[32 * k + lane]) : 0.0f;
        const uint32_t *qw = reinterpret_cast<const uint32_t *>(row);
        float sum[NT];
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) sum[t] = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NQ; s0 += SEGQ) {
            uint32_t q[SEGQ];
#pragma unroll
            for (unsigned m = 0; m < SEGQ; ++m) q[m] = sg_bload(sg, qw + (size_t)(s0 + m) * 32);
#pragma unroll
            for (unsigned m = 0; m < SEGQ; ++m) {
                sycl::vec<float, 4> xv[NT];
#pragma unroll
                for (unsigned t = 0; t < NT; ++t) xv[t] = sg_bloadN<4>(sg, xr + t * xs + (size_t)(s0 + m) * 128);
#pragma unroll
                for (unsigned k = 0; k < 4; ++k) {
                    const unsigned c = (s0 + m) * 4 + k;
                    const float d = sycl::select_from_group(sg, dv[c / 32], c % 32);
                    const float e = d * float(int8_t(uint8_t(q[m] >> (8 * k)))); // iq3::decode Q8_0
#pragma unroll
                    for (unsigned t = 0; t < NT; ++t) sum[t] = sum[t] + e * xv[t][k];
                }
            }
        }
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) sum[t] = sg_tree32(sg, sum[t]);
        if (lane == 0) {
#pragma unroll
            for (unsigned t = 0; t < NT; ++t)
                if (t < mt) y[t * ys + r] = sum[t];
        }
    }
    // rowg<NT> for the R rows r0 .. r0 + R - 1 at once (rows past `rows` are computed on row r0 and not
    // stored): each token's activations are read once for the R rows instead of once per row. Every row's
    // sums are rowg's expressions in rowg's order. Grouped rows (xn > 0) need xn % R == 0 and r0 % R == 0.
    template <unsigned NT, unsigned R>
    [[gnu::always_inline]] inline void rowgr(sycl::sub_group sg, unsigned lane, unsigned r0, const uint8_t *w,
                                             const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        constexpr unsigned NQ = C / 4, SEGQ = Q8Seg<C>::v, ND = (C + 31) / 32;
        static_assert(NQ % SEGQ == 0);
        constexpr size_t RB = ((size_t)C * 34 + 15) & ~(size_t)15;
        const float *xr = xn ? x + (size_t)(r0 / xn) * C * 32 : x; // token t: xr + t * xs
        const uint32_t *qw[R];
        float dv[R][ND];
#pragma unroll
        for (unsigned j = 0; j < R; ++j) {
            const uint8_t *row = w + (size_t)(r0 + j < rows ? r0 + j : r0) * RB;
            const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)C * 32);
#pragma unroll
            for (unsigned k = 0; k < ND; ++k) dv[j][k] = 32 * k + lane < C ? iq3::half(dp[32 * k + lane]) : 0.0f;
            qw[j] = reinterpret_cast<const uint32_t *>(row);
        }
        float sum[R][NT];
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) sum[j][t] = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NQ; s0 += SEGQ) {
            uint32_t q[R][SEGQ];
#pragma unroll
            for (unsigned j = 0; j < R; ++j)
#pragma unroll
                for (unsigned m = 0; m < SEGQ; ++m) q[j][m] = sg_bload(sg, qw[j] + (size_t)(s0 + m) * 32);
#pragma unroll
            for (unsigned m = 0; m < SEGQ; ++m) {
                sycl::vec<float, 4> xv[NT];
#pragma unroll
                for (unsigned t = 0; t < NT; ++t) xv[t] = sg_bloadN<4>(sg, xr + t * xs + (size_t)(s0 + m) * 128);
#pragma unroll
                for (unsigned k = 0; k < 4; ++k) {
                    const unsigned c = (s0 + m) * 4 + k;
#pragma unroll
                    for (unsigned j = 0; j < R; ++j) {
                        const float d = sycl::select_from_group(sg, dv[j][c / 32], c % 32);
                        const float e = d * float(int8_t(uint8_t(q[j][m] >> (8 * k)))); // iq3::decode Q8_0
#pragma unroll
                        for (unsigned t = 0; t < NT; ++t) sum[j][t] = sum[j][t] + e * xv[t][k];
                    }
                }
            }
        }
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) sum[j][t] = sg_tree32(sg, sum[j][t]);
        if (lane == 0) {
#pragma unroll
            for (unsigned j = 0; j < R; ++j)
                if (r0 + j < rows)
#pragma unroll
                    for (unsigned t = 0; t < NT; ++t)
                        if (t < mt) y[t * ys + r0 + j] = sum[j][t];
        }
    }
};

// Routed packed kernels (layouts in pack_v41.hpp). Each sub-group loops over
// rows grp, grp + stride, ... so a launch with fewer work-groups fills the
// local table fewer times. Per-block / per-chunk scales are built
// lane-parallel and broadcast; "lane < 16 ? a : b" picks a half-dependent
// operand (both broadcasts are constant lanes). The element arithmetic of each
// kernel is that of lane_sum_t for its format, in the same order, and the
// reduction is RoutedGemvT's xor butterfly.
// Lane-parallel per-chunk scales for the layouts with a [NB x u32 nibble]
// scale array (IQ2_XXS): chunk c = 32k + lane of the row gets
// (d_b * (0.5 + nibble)) * MUL, b = c / 8, the same expression as computing
// it from the 4-bit field of the block's sign word. NB <= 32.
template <unsigned NB, unsigned NCR>
inline void chunk_scales(sycl::sub_group sg, unsigned lane, const uint16_t *dp, const uint32_t *scw, float mul,
                         float (&dbc)[NCR]) {
    static_assert(NB <= 32);
    const float dl = lane < NB ? iq3::half(dp[lane]) : 0.0f;
    const uint32_t sw = lane < NB ? scw[lane] : 0u;
#pragma unroll
    for (unsigned k = 0; k < NCR; ++k) {
        const unsigned c = 32 * k + lane, b = c / 8 < NB ? c / 8 : NB - 1;
        const float d = sycl::select_from_group(sg, dl, b);
        const uint32_t s = sycl::select_from_group(sg, sw, b);
        dbc[k] = (d * (0.5f + float((s >> (4 * (c & 7))) & 15u))) * mul;
    }
}

// Extra rows run by a routed kernel's sub-groups between its own rows (one
// launch; the memory-bound dense rows of the shared expert overlap the
// ALU-bound expert rows). Each extra row is computed by the dense kernel's own
// row body, so its output is the same as from its own launch.
struct NoRows {
    unsigned n() const { return 0; }
    void row(sycl::sub_group, unsigned, unsigned) const {}
};
template <typename D> struct DenseRows {
    D k; // GemvQ8P / GemvQ5KP / GemvQ6KP: rows and xn
    const uint8_t *w;
    const float *x;
    float *y;
    unsigned n() const { return k.rows; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r) const { k.row(sg, lane, r, w, x, y); }
};
// DenseRows for MT tokens (D::rowm<MT>, see "multi-token rows" at lane_sum_tm): token t reads x + t * xs,
// writes y + t * ys; tokens t >= mt are not stored. Composes with RowsP / RowsPair like DenseRows.
template <typename D, unsigned MT, unsigned G = D::MTG> struct DenseRowsM {
    D k; // GemvQ8P / GemvQ5KP / GemvQ6KP / GemvH16P / GemvF32P: rows and xn
    const uint8_t *w;
    const float *x;
    size_t xs;
    float *y;
    size_t ys;
    unsigned mt;
    unsigned n() const { return k.rows; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r) const {
        k.template rowm<MT, G>(sg, lane, r, w, x, xs, y, ys, mt);
    }
};
// A dense packed kernel D for MT tokens as its own launch, laid out as D's operator() (launch_rows: one
// row per sub-group, rows >= D::rows idle; the pointers stay direct kernel arguments)
template <typename D, unsigned MT, unsigned G = D::MTG> struct DenseM {
    D k;
    size_t xs, ys;
    unsigned mt;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, float *y) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned r = packed_row_id(it);
        if (r >= k.rows) return;
        k.template rowm<MT, G>(sg, sg.get_local_linear_id(), r, w, x, xs, y, ys, mt);
    }
};
// DenseRowsM with the token groups spread over sub-groups (2026-11-10): position p runs row p / ng's token
// group p % ng (tokens G * (p % ng) .. + G - 1) through D::rowg<G>, the group body rowm runs one after
// another on one sub-group. The same operations per token as rowm (a group changes no token's operations);
// a block of a few tokens gets ng times as many sub-groups (a 384-row slice at 6 tokens was 384 sub-groups,
// most of the card idle). Tokens >= mt run on in-bounds data and are not stored (G * ng <= mt + G - 1: the
// block buffers hold Backend41::MTA = MTX + 8 tokens, so any G <= 9 stays inside them).
template <typename D, unsigned G> struct DenseRowsG {
    D k;
    const uint8_t *w;
    const float *x;
    size_t xs;
    float *y;
    size_t ys;
    unsigned mt, ng;
    unsigned n() const { return k.rows * ng; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned p) const {
        const unsigned r = p / ng, t0 = (p % ng) * G;
        k.template rowg<G>(sg, lane, r, w, x + t0 * xs, xs, y + t0 * ys, ys, mt - t0);
    }
};
// DenseRowsG with R rows per sub-group (D::rowgr): position p = (row block p / ng, token group p % ng)
template <typename D, unsigned G, unsigned R> struct DenseRowsGR {
    D k;
    const uint8_t *w;
    const float *x;
    size_t xs;
    float *y;
    size_t ys;
    unsigned mt, ng;
    unsigned n() const { return (k.rows + R - 1) / R * ng; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned p) const {
        const unsigned r0 = p / ng * R, t0 = (p % ng) * G;
        k.template rowgr<G, R>(sg, lane, r0, w, x + t0 * xs, xs, y + t0 * ys, ys, mt - t0);
    }
};
template <typename R1, typename R2> struct RowsPair {
    R1 a;
    R2 b;
    unsigned n() const { return a.n() + b.n(); }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r) const {
        if (r < a.n()) a.row(sg, lane, r);
        else b.row(sg, lane, r - a.n());
    }
};

// Row positions p = sub-group, sub-group + stride, ...; with ne extra rows the
// ne of nt positions are spread evenly (position p is extra when ceil((p+1)ne/nt)
// > ceil(p ne/nt): position 0 is always one, so a single long extra row starts at once).
#define OWN41_ROUTED_ROWS_BEGIN(RB)                                                              \
    const unsigned stride = (unsigned)(it.get_global_range(0) / 32);                             \
    const unsigned nr_ = (w2 ? 2 : 1) * nsl * rows, ne_ = ex.n(), nt_ = nr_ + ne_;               \
    for (unsigned p_ = packed_row_id(it); p_ < nt_; p_ += stride) {                              \
        unsigned grp = p_;                                                                        \
        if (ne_) {                                                                                \
            const unsigned d0 = (unsigned)(((uint64_t)p_ * ne_ + nt_ - 1) / nt_);                 \
            const unsigned d1 = (unsigned)(((uint64_t)(p_ + 1) * ne_ + nt_ - 1) / nt_);           \
            if (d1 > d0) {                                                                        \
                ex.row(sg, lane, d0);                                                             \
                continue;                                                                         \
            }                                                                                     \
            grp = p_ - d1;                                                                        \
        }                                                                                         \
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
#define OWN41_ROUTED_ROWS_END                                                                     \
        for (int w_ = 16; w_; w_ >>= 1) sum += sycl::select_from_group(sg, sum, (int)lane ^ w_); \
        if (lane == 0) om_[slot * rows + r] = sum;                                                \
    }

// Routed IQ2_XXS over packed rows (sign words expanded to 8 bits per group
// by the packer, 4-bit scales in their own array), NB blocks per row: work-group = 16 rows
// (sub-groups), grid table tab[ix*8 + j] = float(byte j of iq2_xxs_grid[ix])
// in local memory (2048 floats). Same element arithmetic as lane_sum_t
// <IQ2_XXS>: ((db * mag) * sign) * x, the sign applied as a sign-bit xor
// (== multiplying a finite value by -1); same xor-butterfly reduction as
// RoutedGemvT.
template <unsigned NB, typename A, typename EX = NoRows> struct RoutedIQ2XXSP {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static constexpr unsigned TAB = 2048;
    unsigned rows; // per-expert rows
    bool per_slot_x;
    EX ex{}; // extra rows run in the same launch (NoRows: none)
    // a second matrix of the same format and shape on the same x and ids (expert gate + up in one launch):
    // positions nsl * rows .. 2 * nsl * rows - 1 read w2 and write out2
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0; // slots (6 per token) and the x stride between tokens (multi-token step)
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_xxs_grid, k >> 3, k & 7));
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), l8 = lane >> 3, j = lane & 7u;
        // sign of element j of 8-group l8 = bit 8*l8 + j of the expanded sign word (pack_v41.hpp)
        const unsigned ssh = 31u - 8u * l8 - j;
        // grid-index byte l8 rotated to bits 5..12: (index * 8 + j) * 4 is the table's BYTE offset
        // (one shift per weight fewer than indexing tab[] by element)
        const unsigned rot = (37u - 8u * l8) & 31u, j4 = j << 2;
        const char *tb = reinterpret_cast<const char *>(tab);
        constexpr size_t RB = ((size_t)NB * 70 + 15) & ~(size_t)15;
        constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NC = NB * 8, NCR = (NC + 31) / 32;
        OWN41_ROUTED_ROWS_BEGIN(RB)
        uint32_t wd[NR]; // word k of the row's qs words lives in wd[k / 32], lane k % 32
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) wd[k] = row_words<NW>(sg, rw, k, lane);
        // chunk scale db = (d * (0.5 + scale nibble)) * 0.25, chunk c in dbc[c / 32], lane c % 32
        float dbc[NCR];
        chunk_scales<NB>(sg, lane, reinterpret_cast<const uint16_t *>(row + (size_t)NB * 68),
                         reinterpret_cast<const uint32_t *>(row + (size_t)NB * 64), 0.25f, dbc);
#pragma unroll
        for (unsigned blk = 0; blk < NB; ++blk) {
            const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
#pragma unroll
            for (unsigned g = 0; g < 8; ++g) {
                const unsigned wl = blk * 16 + 2 * g, wh = wl + 1, c = blk * 8 + g;
                const uint32_t lo = sycl::select_from_group(sg, wd[wl / 32], wl % 32);
                const uint32_t es = sycl::select_from_group(sg, wd[wh / 32], wh % 32);
                const float db = sycl::select_from_group(sg, dbc[c / 32], c % 32);
                const float mag = *reinterpret_cast<const float *>(tb + ((sycl::rotate(lo, rot) & 0x1FE0u) | j4));
                const uint32_t sb = (es << ssh) & 0x80000000u;
                const float v = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ sb);
                sum = sum + v * xv[g];
            }
        }
        OWN41_ROUTED_ROWS_END
    }
};

// IQ2_S: ((((d * (0.5 + sc)) * 0.25) * mag) * sign) * x; table 1024 x 8 floats.
template <unsigned NB, typename A, typename EX = NoRows> struct RoutedIQ2SP {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static constexpr unsigned TAB = 8192;
    unsigned rows;
    bool per_slot_x;
    EX ex{}; // extra rows run in the same launch (NoRows: none)
    // a second matrix of the same format and shape on the same x and ids (expert gate + up in one launch):
    // positions nsl * rows .. 2 * nsl * rows - 1 read w2 and write out2
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0; // slots (6 per token) and the x stride between tokens (multi-token step)
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_s_grid, k >> 3, k & 7));
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), l8 = lane >> 3, j = lane & 7u;
        const unsigned rot = (37u - 8u * l8) & 31u; // idx byte l8 -> bits 5..12 (byte offset into tab)
        const unsigned qsh = 13u - 2u * l8;         // qh bits 2*l8, 2*l8+1 -> bits 13, 14
        const unsigned j4 = j << 2;
        const char *tb = reinterpret_cast<const char *>(tab);
        const unsigned ssh = 31u - 8u * l8 - j;     // sign bit 8*l8 + j -> bit 31
        constexpr size_t RB = ((size_t)NB * 82 + 15) & ~(size_t)15;
        constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NC = NB * 8, NCR = (NC + 31) / 32;
        OWN41_ROUTED_ROWS_BEGIN(RB)
        uint32_t wd[NR];
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) wd[k] = row_words<NW>(sg, rw, k, lane);
        const uint8_t *meta = row + (size_t)NB * 64; // per block: qh[8], scales[8]
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 80);
        float dbl[NCR], dbh[NCR];
        uint32_t qhc[NCR];
#pragma unroll
        for (unsigned k = 0; k < NCR; ++k) {
            const unsigned c = 32 * k + lane < NC ? 32 * k + lane : NC - 1, b = c >> 3, g = c & 7u;
            const float d = iq3::half(dp[b]);
            const unsigned scb = meta[16 * b + 8 + g];
            qhc[k] = meta[16 * b + g];
            dbl[k] = (d * (0.5f + float(scb & 15u))) * 0.25f;
            dbh[k] = (d * (0.5f + float(scb >> 4))) * 0.25f;
        }
#pragma unroll
        for (unsigned blk = 0; blk < NB; ++blk) {
            const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
#pragma unroll
            for (unsigned g = 0; g < 8; ++g) {
                const unsigned c = blk * 8 + g, wl = blk * 16 + 2 * g, wh = wl + 1;
                const uint32_t lo = sycl::select_from_group(sg, wd[wl / 32], wl % 32);
                const uint32_t hi = sycl::select_from_group(sg, wd[wh / 32], wh % 32);
                const float dlo = sycl::select_from_group(sg, dbl[c / 32], c % 32);
                const float dhi = sycl::select_from_group(sg, dbh[c / 32], c % 32);
                const uint32_t qhb = sycl::select_from_group(sg, qhc[c / 32], c % 32);
                const float db = lane < 16 ? dlo : dhi;
                const float mag =
                    *reinterpret_cast<const float *>(tb + ((sycl::rotate(lo, rot) & 0x1FE0u) | ((qhb << qsh) & 0x6000u) | j4));
                const uint32_t sb = (hi << ssh) & 0x80000000u;
                const float v = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ sb);
                sum = sum + v * xv[g];
            }
        }
        OWN41_ROUTED_ROWS_END
    }
};

// IQ3_XXS: ((((d * (0.5 + s)) * 0.5) * mag) * sign) * x; table 256 x 4 floats.
template <unsigned NB, typename A, typename EX = NoRows> struct RoutedIQ3XXSP {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static constexpr unsigned TAB = 1024;
    unsigned rows;
    bool per_slot_x;
    EX ex{}; // extra rows run in the same launch (NoRows: none)
    // a second matrix of the same format and shape on the same x and ids (expert gate + up in one launch):
    // positions nsl * rows .. 2 * nsl * rows - 1 read w2 and write out2
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0; // slots (6 per token) and the x stride between tokens (multi-token step)
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float((iq3::iq3_grid[k >> 2] >> (8 * (k & 3))) & 255);
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), l8 = lane >> 3, j = lane & 7u;
        const unsigned rot = (36u - 8u * ((lane >> 2) & 3u)) & 31u; // grid byte -> bits 4..11 (byte offset into tab)
        const uint32_t smask = j == 7 ? (127u << (7 * l8)) : (1u << (7 * l8 + j));
        const unsigned jj4 = (lane & 3u) << 2;
        const char *tb = reinterpret_cast<const char *>(tab);
        constexpr size_t RB = ((size_t)NB * 98 + 15) & ~(size_t)15;
        constexpr unsigned NW = NB * 24, NR = (NW + 31) / 32;
        OWN41_ROUTED_ROWS_BEGIN(RB)
        uint32_t wd[NR];
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) wd[k] = row_words<NW>(sg, rw, k, lane);
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 96);
        float dbw[NR]; // valid at the scale/sign words (index 3g + 2 of each block)
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) {
            const unsigned wi = 32 * k + lane < NW ? 32 * k + lane : NW - 1;
            dbw[k] = (iq3::half(dp[wi / 24]) * (0.5f + float(wd[k] >> 28))) * 0.5f;
        }
#pragma unroll
        for (unsigned blk = 0; blk < NB; ++blk) {
            const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
#pragma unroll
            for (unsigned g = 0; g < 8; ++g) {
                const unsigned w0 = blk * 24 + 3 * g, w1 = w0 + 1, ws = w0 + 2;
                const uint32_t q0 = sycl::select_from_group(sg, wd[w0 / 32], w0 % 32);
                const uint32_t q1 = sycl::select_from_group(sg, wd[w1 / 32], w1 % 32);
                const uint32_t sw = sycl::select_from_group(sg, wd[ws / 32], ws % 32);
                const float db = sycl::select_from_group(sg, dbw[ws / 32], ws % 32);
                const uint32_t q = lane < 16 ? q0 : q1;
                const float mag = *reinterpret_cast<const float *>(tb + ((sycl::rotate(q, rot) & 0xFF0u) | jj4));
                const uint32_t sb = uint32_t(sycl::popcount(sw & smask)) << 31;
                const float v = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ sb);
                sum = sum + v * xv[g];
            }
        }
        OWN41_ROUTED_ROWS_END
    }
};

// IQ2_XS: ((((d * (0.5 + sc)) * 0.25) * mag) * sign) * x; table 512 x 8 floats.
template <unsigned NB, typename A, typename EX = NoRows> struct RoutedIQ2XSP {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static constexpr unsigned TAB = 4096;
    unsigned rows;
    bool per_slot_x;
    EX ex{}; // extra rows run in the same launch (NoRows: none)
    // a second matrix of the same format and shape on the same x and ids (expert gate + up in one launch):
    // positions nsl * rows .. 2 * nsl * rows - 1 read w2 and write out2
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0; // slots (6 per token) and the x stride between tokens (multi-token step)
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_xs_grid, k >> 3, k & 7));
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), l8 = lane >> 3, j = lane & 7u, hs = 16u * (l8 & 1u);
        const unsigned rot = (5u - hs) & 31u, j4 = j << 2; // aux bits 0..8 -> bits 5..13 (byte offset into tab)
        const char *tb = reinterpret_cast<const char *>(tab);
        const uint32_t smask = j == 7 ? (127u << (hs + 9)) : (1u << (hs + 9 + j));
        constexpr size_t RB = ((size_t)NB * 74 + 15) & ~(size_t)15;
        constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NC = NB * 8, NCR = (NC + 31) / 32;
        OWN41_ROUTED_ROWS_BEGIN(RB)
        uint32_t wd[NR];
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) wd[k] = row_words<NW>(sg, rw, k, lane);
        const uint8_t *scl = row + (size_t)NB * 64;
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 72);
        float dbl[NCR], dbh[NCR];
#pragma unroll
        for (unsigned k = 0; k < NCR; ++k) {
            const unsigned c = 32 * k + lane < NC ? 32 * k + lane : NC - 1;
            const float d = iq3::half(dp[c >> 3]);
            const unsigned scb = scl[c]; // block c >> 3, group c & 7
            dbl[k] = (d * (0.5f + float(scb & 15u))) * 0.25f;
            dbh[k] = (d * (0.5f + float(scb >> 4))) * 0.25f;
        }
#pragma unroll
        for (unsigned blk = 0; blk < NB; ++blk) {
            const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
#pragma unroll
            for (unsigned g = 0; g < 8; ++g) {
                const unsigned c = blk * 8 + g, w0 = blk * 16 + 2 * g, w1 = w0 + 1;
                const uint32_t a0 = sycl::select_from_group(sg, wd[w0 / 32], w0 % 32);
                const uint32_t a1 = sycl::select_from_group(sg, wd[w1 / 32], w1 % 32);
                const float dlo = sycl::select_from_group(sg, dbl[c / 32], c % 32);
                const float dhi = sycl::select_from_group(sg, dbh[c / 32], c % 32);
                const uint32_t a = lane < 16 ? a0 : a1;
                const float db = lane < 16 ? dlo : dhi;
                const float mag = *reinterpret_cast<const float *>(tb + ((sycl::rotate(a, rot) & 0x3FE0u) | j4));
                const uint32_t sb = uint32_t(sycl::popcount(a & smask)) << 31;
                const float v = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ sb);
                sum = sum + v * xv[g];
            }
        }
        OWN41_ROUTED_ROWS_END
    }
};

// IQ1_S: (dl * (code + delta)) * x, dl = d * (2 * ((qh >> 12) & 7) + 1);
// table 2048 x 8 floats (the int8 grid codes).
template <unsigned NB, typename A, bool BYTES = true, typename EX = NoRows> struct RoutedIQ1SP {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    // BYTES: the codes as int8 (16 KiB, more work-groups per core), else as floats (64 KiB)
    static constexpr unsigned TAB = BYTES ? 4096 : 16384;
    unsigned rows;
    bool per_slot_x;
    EX ex{}; // extra rows run in the same launch (NoRows: none)
    // a second matrix of the same format and shape on the same x and ids (expert gate + up in one launch):
    // positions nsl * rows .. 2 * nsl * rows - 1 read w2 and write out2
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0; // slots (6 per token) and the x stride between tokens (multi-token step)
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        int8_t *btab = reinterpret_cast<int8_t *>(tab);
        for (unsigned k = it.get_local_linear_id(); k < 16384; k += (unsigned)it.get_local_range(0)) {
            const int8_t c = int8_t(uint8_t(grid64_byte(iq3::iq1_s_grid, k >> 3, k & 7)));
            if constexpr (BYTES) btab[k] = c;
            else tab[k] = float(int(c));
        }
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), l8 = lane >> 3, j = lane & 7u;
        const unsigned rot = (35u - 8u * l8) & 31u; // qs byte l8 -> bits 3..10
        const unsigned qsh = 11u - 3u * l8;         // qh bits 3*l8 .. 3*l8+2 -> bits 11..13
        constexpr size_t RB = ((size_t)NB * 50 + 15) & ~(size_t)15;
        constexpr unsigned NG = NB * 8, NW = NG, NR = (NW + 31) / 32;
        OWN41_ROUTED_ROWS_BEGIN(RB)
        uint32_t wd[NR]; // qs word of group k (block k >> 3)
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) wd[k] = row_words<NW>(sg, rw, k, lane);
        const uint16_t *qh16 = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 32);
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 48);
        float dlr[NR], der[NR];
        uint32_t qhr[NR];
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) {
            const unsigned gi = 32 * k + lane < NG ? 32 * k + lane : NG - 1;
            const uint32_t qh = qh16[gi];
            qhr[k] = qh;
            dlr[k] = iq3::half(dp[gi >> 3]) * float(2 * ((qh >> 12) & 7) + 1);
            der[k] = (qh & 0x8000) ? -0.125f : 0.125f;
        }
#pragma unroll
        for (unsigned blk = 0; blk < NB; ++blk) {
            const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
#pragma unroll
            for (unsigned g = 0; g < 8; ++g) {
                const unsigned gi = blk * 8 + g;
                const uint32_t qs = sycl::select_from_group(sg, wd[gi / 32], gi % 32);
                const uint32_t qh = sycl::select_from_group(sg, qhr[gi / 32], gi % 32);
                const float dl = sycl::select_from_group(sg, dlr[gi / 32], gi % 32);
                const float de = sycl::select_from_group(sg, der[gi / 32], gi % 32);
                const unsigned a = (sycl::rotate(qs, rot) & 0x7F8u) | ((qh << qsh) & 0x3800u) | j;
                float code;
                if constexpr (BYTES) code = float(int(btab[a]));
                else code = tab[a];
                sum = sum + (dl * (code + de)) * xv[g];
            }
        }
        OWN41_ROUTED_ROWS_END
    }
};
#undef OWN41_ROUTED_ROWS_BEGIN
#undef OWN41_ROUTED_ROWS_END

// Dense K-quant gemv over packed rows (layouts in pack_v41.hpp), NB blocks per
// row, one sub-group per row, sg_tree32 reduction as GemvT / GemvGroupedQT.
// Row r reads x + (r / xn) * NB * 256 when xn > 0 (the grouped output LoRA).
// Each lane's quant bytes for a block arrive in one word (its own lane: no
// broadcast); the per-16 / per-32 scale products are built lane-parallel.
template <unsigned NB> struct KSeg { static constexpr unsigned v = NB % 4 == 0 ? 4 : NB % 5 == 0 ? 5 : NB % 3 == 0 ? 3 : 1; };
// Q6_K rows for 1-3 tokens load every block's quant words before the first product (Q6Seg = NB up to 32 blocks):
// bench_q6k_rows, the head's 21,547 rows at one token 199 -> 169 us, output_b 19.4 -> 16.3, three tokens equal;
// same products in the same order (bitwise). 4+ tokens keep KSeg (registers).
template <unsigned NB, unsigned NT> struct Q6Seg { static constexpr unsigned v = NT <= 3 && NB <= 32 ? NB : KSeg<NB>::v; };

// Q6_K element (block b, chunk c, lane l; h = c >> 2, cc = c & 3), iq3::decode order:
//   (d * float(scale[2c + (l >> 4)])) * float((low | high << 4) - 32), then * x
//   low = nibble (cc >> 1) of ql byte 2h + (cc & 1); high = bits 8h + 2cc of the qh pair
template <unsigned NB, typename A> struct GemvQ6KP {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    unsigned rows, xn;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, float *y) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned r = packed_row_id(it);
        if (r >= rows) return;
        row(sg, sg.get_local_linear_id(), r, w, x, y);
    }
    // one row on one sub-group (also run inside fused launches: DenseRows)
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                           const float *x, float *y) const {
        constexpr size_t RB = ((size_t)NB * 210 + 15) & ~(size_t)15;
        constexpr unsigned NS = NB * 16, NSR = (NS + 31) / 32, SEG = Q6Seg<NB, 1>::v;
        const uint8_t *row = w + (size_t)r * RB;
        const float *xr = xn ? x + (size_t)(r / xn) * NB * 256 : x;
        const uint32_t *ql = reinterpret_cast<const uint32_t *>(row);
        const uint16_t *qh = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 128);
        const int8_t *scl = reinterpret_cast<const int8_t *>(row + (size_t)NB * 192);
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 208);
        float dbs[NSR]; // d * scale, scale index 32k + lane
#pragma unroll
        for (unsigned k = 0; k < NSR; ++k) {
            const unsigned si = 32 * k + lane < NS ? 32 * k + lane : NS - 1;
            dbs[k] = iq3::half(dp[si >> 4]) * float(int(scl[si]));
        }
        float sum = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NB; s0 += SEG) {
            uint32_t qa[SEG], qb[SEG];
#pragma unroll
            for (unsigned m = 0; m < SEG; ++m) {
                qa[m] = sg_bload(sg, ql + (size_t)(s0 + m) * 32);
                qb[m] = qh[(size_t)(s0 + m) * 32 + lane];
            }
#pragma unroll
            for (unsigned m = 0; m < SEG; ++m) {
                const unsigned b = s0 + m;
                const auto xv = sg_bloadN<8>(sg, xr + (size_t)b * 256);
#pragma unroll
                for (unsigned c = 0; c < 8; ++c) {
                    const unsigned h = c >> 2, cc = c & 3u;
                    const unsigned low = (qa[m] >> (8 * (2 * h + (cc & 1u)) + 4 * (cc >> 1))) & 15u;
                    const unsigned high = (qb[m] >> (8 * h + 2 * cc)) & 3u;
                    const unsigned si = b * 16 + 2 * c; // even: si and si + 1 share a register
                    const float d0 = sycl::select_from_group(sg, dbs[si / 32], si % 32);
                    const float d1 = sycl::select_from_group(sg, dbs[si / 32], si % 32 + 1);
                    const float v = (lane < 16 ? d0 : d1) * float(int(low | (high << 4)) - 32);
                    sum = sum + v * xv[c];
                }
            }
        }
        sum = sg_tree32(sg, sum);
        if (lane == 0) y[r] = sum;
    }
    // M tokens (see "multi-token rows" at lane_sum_tm): token t reads x + t * xs (then row()'s r / xn
    // group offset) and writes y[t * ys + r] when t < mt; xs % 4 == 0 (block reads).
    static constexpr unsigned MTG = 4;
    template <unsigned MT, unsigned G = MTG, unsigned T0 = 0>
    [[gnu::always_inline]] inline void rowm(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        if constexpr (T0 < MT) {
            constexpr unsigned NT = MT - T0 < G ? MT - T0 : G;
            if (T0 < mt) rowg<NT>(sg, lane, r, w, x + T0 * xs, xs, y + T0 * ys, ys, mt - T0);
            rowm<MT, G, T0 + NT>(sg, lane, r, w, x, xs, y, ys, mt);
        }
    }
    template <unsigned NT>
    [[gnu::always_inline]] inline void rowg(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        constexpr size_t RB = ((size_t)NB * 210 + 15) & ~(size_t)15;
        constexpr unsigned NS = NB * 16, NSR = (NS + 31) / 32, SEG = Q6Seg<NB, NT>::v;
        const uint8_t *row = w + (size_t)r * RB;
        const float *xr = xn ? x + (size_t)(r / xn) * NB * 256 : x; // token t: xr + t * xs
        const uint32_t *ql = reinterpret_cast<const uint32_t *>(row);
        const uint16_t *qh = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 128);
        const int8_t *scl = reinterpret_cast<const int8_t *>(row + (size_t)NB * 192);
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 208);
        float dbs[NSR]; // d * scale, scale index 32k + lane
#pragma unroll
        for (unsigned k = 0; k < NSR; ++k) {
            const unsigned si = 32 * k + lane < NS ? 32 * k + lane : NS - 1;
            dbs[k] = iq3::half(dp[si >> 4]) * float(int(scl[si]));
        }
        float sum[NT];
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) sum[t] = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NB; s0 += SEG) {
            uint32_t qa[SEG], qb[SEG];
#pragma unroll
            for (unsigned m = 0; m < SEG; ++m) {
                qa[m] = sg_bload(sg, ql + (size_t)(s0 + m) * 32);
                qb[m] = qh[(size_t)(s0 + m) * 32 + lane];
            }
#pragma unroll
            for (unsigned m = 0; m < SEG; ++m) {
                const unsigned b = s0 + m;
                sycl::vec<float, 8> xv[NT];
#pragma unroll
                for (unsigned t = 0; t < NT; ++t) xv[t] = sg_bloadN<8>(sg, xr + t * xs + (size_t)b * 256);
#pragma unroll
                for (unsigned c = 0; c < 8; ++c) {
                    const unsigned h = c >> 2, cc = c & 3u;
                    const unsigned low = (qa[m] >> (8 * (2 * h + (cc & 1u)) + 4 * (cc >> 1))) & 15u;
                    const unsigned high = (qb[m] >> (8 * h + 2 * cc)) & 3u;
                    const unsigned si = b * 16 + 2 * c; // even: si and si + 1 share a register
                    const float d0 = sycl::select_from_group(sg, dbs[si / 32], si % 32);
                    const float d1 = sycl::select_from_group(sg, dbs[si / 32], si % 32 + 1);
                    const float v = (lane < 16 ? d0 : d1) * float(int(low | (high << 4)) - 32);
#pragma unroll
                    for (unsigned t = 0; t < NT; ++t) sum[t] = sum[t] + v * xv[t][c];
                }
            }
        }
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) sum[t] = sg_tree32(sg, sum[t]);
        if (lane == 0) {
#pragma unroll
            for (unsigned t = 0; t < NT; ++t)
                if (t < mt) y[t * ys + r] = sum[t];
        }
    }
    // rowg<NT> for the R rows r0 .. r0 + R - 1 at once, as GemvQ8P::rowgr (rows past `rows` computed on r0,
    // not stored; grouped rows need xn % R == 0): every row's sums are rowg's expressions in rowg's order
    template <unsigned NT, unsigned R>
    [[gnu::always_inline]] inline void rowgr(sycl::sub_group sg, unsigned lane, unsigned r0, const uint8_t *w,
                                             const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        constexpr size_t RB = ((size_t)NB * 210 + 15) & ~(size_t)15;
        constexpr unsigned NS = NB * 16, NSR = (NS + 31) / 32, SEG = KSeg<NB>::v;
        const float *xr = xn ? x + (size_t)(r0 / xn) * NB * 256 : x; // token t: xr + t * xs
        const uint32_t *ql[R];
        const uint16_t *qh[R];
        float dbs[R][NSR]; // d * scale, scale index 32k + lane
#pragma unroll
        for (unsigned j = 0; j < R; ++j) {
            const uint8_t *row = w + (size_t)(r0 + j < rows ? r0 + j : r0) * RB;
            ql[j] = reinterpret_cast<const uint32_t *>(row);
            qh[j] = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 128);
            const int8_t *scl = reinterpret_cast<const int8_t *>(row + (size_t)NB * 192);
            const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 208);
#pragma unroll
            for (unsigned k = 0; k < NSR; ++k) {
                const unsigned si = 32 * k + lane < NS ? 32 * k + lane : NS - 1;
                dbs[j][k] = iq3::half(dp[si >> 4]) * float(int(scl[si]));
            }
        }
        float sum[R][NT];
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) sum[j][t] = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NB; s0 += SEG) {
            uint32_t qa[R][SEG], qb[R][SEG];
#pragma unroll
            for (unsigned j = 0; j < R; ++j)
#pragma unroll
                for (unsigned m = 0; m < SEG; ++m) {
                    qa[j][m] = sg_bload(sg, ql[j] + (size_t)(s0 + m) * 32);
                    qb[j][m] = qh[j][(size_t)(s0 + m) * 32 + lane];
                }
#pragma unroll
            for (unsigned m = 0; m < SEG; ++m) {
                const unsigned b = s0 + m;
                sycl::vec<float, 8> xv[NT];
#pragma unroll
                for (unsigned t = 0; t < NT; ++t) xv[t] = sg_bloadN<8>(sg, xr + t * xs + (size_t)b * 256);
#pragma unroll
                for (unsigned c = 0; c < 8; ++c) {
                    const unsigned h = c >> 2, cc = c & 3u;
                    const unsigned si = b * 16 + 2 * c; // even: si and si + 1 share a register
#pragma unroll
                    for (unsigned j = 0; j < R; ++j) {
                        const unsigned low = (qa[j][m] >> (8 * (2 * h + (cc & 1u)) + 4 * (cc >> 1))) & 15u;
                        const unsigned high = (qb[j][m] >> (8 * h + 2 * cc)) & 3u;
                        const float d0 = sycl::select_from_group(sg, dbs[j][si / 32], si % 32);
                        const float d1 = sycl::select_from_group(sg, dbs[j][si / 32], si % 32 + 1);
                        const float v = (lane < 16 ? d0 : d1) * float(int(low | (high << 4)) - 32);
#pragma unroll
                        for (unsigned t = 0; t < NT; ++t) sum[j][t] = sum[j][t] + v * xv[t][c];
                    }
                }
            }
        }
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) sum[j][t] = sg_tree32(sg, sum[j][t]);
        if (lane == 0) {
#pragma unroll
            for (unsigned j = 0; j < R; ++j)
                if (r0 + j < rows)
#pragma unroll
                    for (unsigned t = 0; t < NT; ++t)
                        if (t < mt) y[t * ys + r0 + j] = sum[j][t];
        }
    }
};

template <typename T> inline constexpr bool is_q6kp_v = false;
template <unsigned NB, typename A> inline constexpr bool is_q6kp_v<GemvQ6KP<NB, A>> = true;
// columns of a packed dense row kernel with row blocks (rowgr): Q8_0 chunks of 32, Q6_K super-blocks of 256; 0 else
template <typename T> inline constexpr unsigned dense_cols_v = 0;
template <unsigned C, typename A> inline constexpr unsigned dense_cols_v<GemvQ8P<C, A>> = 32 * C;
template <unsigned NB, typename A> inline constexpr unsigned dense_cols_v<GemvQ6KP<NB, A>> = 256 * NB;

// F32 rows stored as their upper 16 bits (pack_v41 F32: only rows whose low
// halves are all zero, e.g. the router). Widening gives the F32 row's floats
// bit for bit; same lanes, order and tree as GemvF32P, half the bytes read.
template <unsigned C, typename A> struct GemvH16P {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static_assert(C % 8 == 0);
    unsigned rows;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, float *y) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned r = packed_row_id(it);
        if (r >= rows) return;
        row(sg, sg.get_local_linear_id(), r, w, x, y);
    }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                           const float *x, float *y) const {
        const uint16_t *row = reinterpret_cast<const uint16_t *>(w) + (size_t)r * C * 32;
        float sum = 0;
#pragma unroll
        for (unsigned s = 0; s < C / 8; ++s) {
            const auto wv = sg_bloadN<8>(sg, row + (size_t)s * 256);
            const auto xv = sg_bloadN<8>(sg, x + (size_t)s * 256);
#pragma unroll
            for (unsigned m = 0; m < 8; ++m) sum = sum + sycl::bit_cast<float>(uint32_t(wv[m]) << 16) * xv[m];
        }
        sum = sg_tree32(sg, sum);
        if (lane == 0) y[r] = sum;
    }
    // M tokens (see "multi-token rows" at lane_sum_tm): token t reads x + t * xs and writes
    // y[t * ys + r] when t < mt; xs % 4 == 0 (block reads).
    static constexpr unsigned MTG = 8;
    template <unsigned MT, unsigned G = MTG, unsigned T0 = 0>
    [[gnu::always_inline]] inline void rowm(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        if constexpr (T0 < MT) {
            constexpr unsigned NT = MT - T0 < G ? MT - T0 : G;
            if (T0 < mt) rowg<NT>(sg, lane, r, w, x + T0 * xs, xs, y + T0 * ys, ys, mt - T0);
            rowm<MT, G, T0 + NT>(sg, lane, r, w, x, xs, y, ys, mt);
        }
    }
    template <unsigned NT>
    [[gnu::always_inline]] inline void rowg(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        const uint16_t *row = reinterpret_cast<const uint16_t *>(w) + (size_t)r * C * 32;
        float sum[NT];
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) sum[t] = 0;
#pragma unroll
        for (unsigned s = 0; s < C / 8; ++s) {
            const auto wv = sg_bloadN<8>(sg, row + (size_t)s * 256);
            sycl::vec<float, 8> xv[NT];
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) xv[t] = sg_bloadN<8>(sg, x + t * xs + (size_t)s * 256);
#pragma unroll
            for (unsigned m = 0; m < 8; ++m) {
                const float wf = sycl::bit_cast<float>(uint32_t(wv[m]) << 16);
#pragma unroll
                for (unsigned t = 0; t < NT; ++t) sum[t] = sum[t] + wf * xv[t][m];
            }
        }
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) sum[t] = sg_tree32(sg, sum[t]);
        if (lane == 0) {
#pragma unroll
            for (unsigned t = 0; t < NT; ++t)
                if (t < mt) y[t * ys + r] = sum[t];
        }
    }
};

// Q5_K element (block b, group c, lane l), iq3::decode order:
//   (d * float(scale_c)) * float(code) - dmin * float(min_c), then * x
//   code = nibble c of the qs word (byte c >> 1, half c & 1) | bit c of qh byte l << 4
template <unsigned NB, typename A> struct GemvQ5KP {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    unsigned rows, xn;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, float *y) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned r = packed_row_id(it);
        if (r >= rows) return;
        row(sg, sg.get_local_linear_id(), r, w, x, y);
    }
    // one row on one sub-group (also run inside fused launches: DenseRows)
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                           const float *x, float *y) const {
        constexpr size_t RB = ((size_t)NB * 176 + 15) & ~(size_t)15;
        constexpr unsigned NG = NB * 8, NGR = (NG + 31) / 32, SEG = KSeg<NB>::v;
        const uint8_t *row = w + (size_t)r * RB;
        const float *xr = xn ? x + (size_t)(r / xn) * NB * 256 : x;
        const uint32_t *qs = reinterpret_cast<const uint32_t *>(row);
        const uint8_t *qh = row + (size_t)NB * 128;
        const uint8_t *hd = row + (size_t)NB * 160; // per block: d, dmin, scales[12]
        float fac[NGR], off[NGR]; // group 32k + lane
#pragma unroll
        for (unsigned k = 0; k < NGR; ++k) {
            const unsigned gi = 32 * k + lane < NG ? 32 * k + lane : NG - 1, c = gi & 7u, c3 = c & 3u;
            const uint8_t *hb = hd + 16 * (gi >> 3), *s = hb + 4;
            const unsigned u0 = s[c3], u1 = s[4 + c3], u2 = s[8 + c3];
            const unsigned scale = c < 4 ? u0 & 63u : (u2 & 15u) | ((u0 >> 6) << 4);
            const unsigned minimum = c < 4 ? u1 & 63u : (u2 >> 4) | ((u1 >> 6) << 4);
            fac[k] = iq3::half(iq3::u16(hb)) * float(scale);
            off[k] = iq3::half(iq3::u16(hb + 2)) * float(minimum);
        }
        float sum = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NB; s0 += SEG) {
            uint32_t qa[SEG], qb[SEG];
#pragma unroll
            for (unsigned m = 0; m < SEG; ++m) {
                qa[m] = sg_bload(sg, qs + (size_t)(s0 + m) * 32);
                qb[m] = qh[(size_t)(s0 + m) * 32 + lane];
            }
#pragma unroll
            for (unsigned m = 0; m < SEG; ++m) {
                const unsigned b = s0 + m;
                const auto xv = sg_bloadN<8>(sg, xr + (size_t)b * 256);
#pragma unroll
                for (unsigned c = 0; c < 8; ++c) {
                    const unsigned code = ((qa[m] >> (4 * c)) & 15u) | (((qb[m] >> c) & 1u) << 4);
                    const unsigned gi = b * 8 + c;
                    const float f = sycl::select_from_group(sg, fac[gi / 32], gi % 32);
                    const float o = sycl::select_from_group(sg, off[gi / 32], gi % 32);
                    const float v = f * float(code) - o;
                    sum = sum + v * xv[c];
                }
            }
        }
        sum = sg_tree32(sg, sum);
        if (lane == 0) y[r] = sum;
    }
    // M tokens (see "multi-token rows" at lane_sum_tm): token t reads x + t * xs (then row()'s r / xn
    // group offset) and writes y[t * ys + r] when t < mt; xs % 4 == 0 (block reads).
    static constexpr unsigned MTG = 4;
    template <unsigned MT, unsigned G = MTG, unsigned T0 = 0>
    [[gnu::always_inline]] inline void rowm(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        if constexpr (T0 < MT) {
            constexpr unsigned NT = MT - T0 < G ? MT - T0 : G;
            if (T0 < mt) rowg<NT>(sg, lane, r, w, x + T0 * xs, xs, y + T0 * ys, ys, mt - T0);
            rowm<MT, G, T0 + NT>(sg, lane, r, w, x, xs, y, ys, mt);
        }
    }
    template <unsigned NT>
    [[gnu::always_inline]] inline void rowg(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        constexpr size_t RB = ((size_t)NB * 176 + 15) & ~(size_t)15;
        constexpr unsigned NG = NB * 8, NGR = (NG + 31) / 32, SEG = KSeg<NB>::v;
        const uint8_t *row = w + (size_t)r * RB;
        const float *xr = xn ? x + (size_t)(r / xn) * NB * 256 : x; // token t: xr + t * xs
        const uint32_t *qs = reinterpret_cast<const uint32_t *>(row);
        const uint8_t *qh = row + (size_t)NB * 128;
        const uint8_t *hd = row + (size_t)NB * 160; // per block: d, dmin, scales[12]
        float fac[NGR], off[NGR]; // group 32k + lane
#pragma unroll
        for (unsigned k = 0; k < NGR; ++k) {
            const unsigned gi = 32 * k + lane < NG ? 32 * k + lane : NG - 1, c = gi & 7u, c3 = c & 3u;
            const uint8_t *hb = hd + 16 * (gi >> 3), *s = hb + 4;
            const unsigned u0 = s[c3], u1 = s[4 + c3], u2 = s[8 + c3];
            const unsigned scale = c < 4 ? u0 & 63u : (u2 & 15u) | ((u0 >> 6) << 4);
            const unsigned minimum = c < 4 ? u1 & 63u : (u2 >> 4) | ((u1 >> 6) << 4);
            fac[k] = iq3::half(iq3::u16(hb)) * float(scale);
            off[k] = iq3::half(iq3::u16(hb + 2)) * float(minimum);
        }
        float sum[NT];
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) sum[t] = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NB; s0 += SEG) {
            uint32_t qa[SEG], qb[SEG];
#pragma unroll
            for (unsigned m = 0; m < SEG; ++m) {
                qa[m] = sg_bload(sg, qs + (size_t)(s0 + m) * 32);
                qb[m] = qh[(size_t)(s0 + m) * 32 + lane];
            }
#pragma unroll
            for (unsigned m = 0; m < SEG; ++m) {
                const unsigned b = s0 + m;
                sycl::vec<float, 8> xv[NT];
#pragma unroll
                for (unsigned t = 0; t < NT; ++t) xv[t] = sg_bloadN<8>(sg, xr + t * xs + (size_t)b * 256);
#pragma unroll
                for (unsigned c = 0; c < 8; ++c) {
                    const unsigned code = ((qa[m] >> (4 * c)) & 15u) | (((qb[m] >> c) & 1u) << 4);
                    const unsigned gi = b * 8 + c;
                    const float f = sycl::select_from_group(sg, fac[gi / 32], gi % 32);
                    const float o = sycl::select_from_group(sg, off[gi / 32], gi % 32);
                    const float v = f * float(code) - o;
#pragma unroll
                    for (unsigned t = 0; t < NT; ++t) sum[t] = sum[t] + v * xv[t][c];
                }
            }
        }
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) sum[t] = sg_tree32(sg, sum[t]);
        if (lane == 0) {
#pragma unroll
            for (unsigned t = 0; t < NT; ++t)
                if (t < mt) y[t * ys + r] = sum[t];
        }
    }
};

// ---- weight-stationary dense rows (OWN_MT_WS; tools/bench/bench_dense_ws.cpp, 2026-11-11) ---------------------
// DenseRowsG / DenseRowsGR decode every weight once per token group of G (rowg<G> loads the G tokens'
// activations before the products, so G stays at 1-8). The rows here decode one quant word (Q8_0) or block
// (Q6_K / Q5_K) of R rows once into registers and then run T tokens' activation blocks past them. For every
// (row, token) the lane sum is rowg's serial chain (the same value expression, the same activation, added to the
// running sum from 0, chunks ascending) and the 32 lane sums are added in sg_tree32's pairs and order (ws_tree32_n
// below: all R * T sums at once, sum s ends in lane s). Only the order in which independent sums advance changes:
// every output is bit-identical to the one-token rows (bench_dense_ws: memcmp per (row, token), random and real
// GGUF rows). WsTab picks a form per matrix shape and block size where the bench measured it faster than the
// engine's form (one card, cold weights, event timing, median); everything else keeps the engine's form.
#define OPS41_DENSE_WS 1
// sg_tree32 for N sums at once (N a power of two <= 32). sg_tree32: for w = 1, 2, 4, 8, 16, lane l with l % 2w == 0
// becomes v_l + v_{l+w}. Step w < N pairs registers 2i and 2i + 1: lanes with bit w clear keep register 2i's
// partials, lanes with bit w set register 2i + 1's, so after step w the partial of sum s's 2w-lane block starting at
// lane L sits in lane L + (s's low bits). Each addition is (the lower lane's partial) + (the upper lane's), as in
// sg_tree32. Steps w >= N run on the one register left. Every cross-lane read is sg_tree32's own shuffle
// (select_from_group): IGC rewrites back-to-back permute_group_by_xor additions of one value as a sub-group reduction
// in another order ((a_l + a_l+16) + (a_l+8 + a_l+24)), which changed 36 % of the outputs of an N = 8 form.
template <unsigned N, unsigned W = 1>
[[gnu::always_inline]] inline void ws_tree32_steps(sycl::sub_group sg, unsigned lane, float (&a)[N]) {
    if constexpr (W < 32) {
        const bool lo = (lane & W) == 0;
        if constexpr (W < N) {
#pragma unroll
            for (unsigned i = 0; i < N / (2 * W); ++i) {
                const float A = a[2 * i], B = a[2 * i + 1];
                const float S = lo ? B : A;                               // what lane l ^ W needs from lane l
                const float Sx = sycl::select_from_group(sg, S, lane ^ W); // lo: A of lane l + W; hi: B of lane l - W
                const float lhs = lo ? A : Sx, rhs = lo ? Sx : B;         // the lower lane's partial first
                a[i] = lhs + rhs;
            }
        } else {
            const float o = sycl::select_from_group(sg, a[0], (lane + W) % 32); // sg_tree32's shuffle
            a[0] = a[0] + o;
        }
        ws_tree32_steps<N, W * 2>(sg, lane, a);
    }
}
static constexpr unsigned ws_pow2_at_least(unsigned n) {
    unsigned p = 1;
    while (p < n) p *= 2;
    return p;
}
// R * T sums (index j * T + t) -> y[t * ys + r0 + j] for r0 + j < rows and t < mt; padded to a power of two with
// zero sums (a lane's result only ever adds partials of one sum, so the pads reach no store)
template <unsigned R, unsigned T>
[[gnu::always_inline]] inline void ws_reduce_store(sycl::sub_group sg, unsigned lane, float (&sum)[R * T], unsigned r0,
                                                   unsigned rows, float *y, size_t ys, unsigned mt) {
    constexpr unsigned NP = ws_pow2_at_least(R * T);
    static_assert(NP <= 32);
    float a[NP];
#pragma unroll
    for (unsigned i = 0; i < NP; ++i) a[i] = i < R * T ? sum[i] : 0.0f;
    ws_tree32_steps<NP>(sg, lane, a);
    const unsigned j = lane / T, t = lane % T;
    if (lane < R * T && r0 + j < rows && t < mt) y[t * ys + r0 + j] = a[0];
}
// Q8_0 packed rows (GemvQ8P's layout). rowt<T, R, XW, LOOP>: rows r0 .. r0 + R - 1 (a row past `rows` reads row r0
// and is not stored), tokens x + t * xs -> y + t * ys, t < T (t >= mt computed, not stored).
//   XW: quant words per activation block read (2: vec8 = 256 columns)
//   LOOP = 0: unrolled, the rows' chunk scales loaded up front (as rowgr); LOOP = 1: a loop over segments of 8 words
//   (32 chunks), each segment's 32 scales loaded with its words one segment ahead (C % 32 == 0)
template <unsigned C> struct WsQ8 {
    unsigned rows, xn;
    static constexpr size_t RB = ((size_t)C * 34 + 15) & ~(size_t)15;
    template <unsigned R, unsigned T, unsigned XW>
    [[gnu::always_inline]] static inline void word_group(sycl::sub_group sg, const uint32_t (&q)[R][XW],
                                                         const float (&dsc)[R], unsigned c0lane, const float *xw,
                                                         size_t xs, float (&sum)[R * T]) {
        // q[j][mm]: row j's word of chunks 4 mm .. +3 (from c0lane); chunk c's scale is lane c0lane + c of dsc[j]
        float e[R][4 * XW];
#pragma unroll
        for (unsigned mm = 0; mm < XW; ++mm)
#pragma unroll
            for (unsigned k = 0; k < 4; ++k)
#pragma unroll
                for (unsigned j = 0; j < R; ++j) {
                    const float d = sycl::select_from_group(sg, dsc[j], c0lane + 4 * mm + k);
                    e[j][4 * mm + k] = d * float(int8_t(uint8_t(q[j][mm] >> (8 * k)))); // iq3::decode Q8_0
                }
#pragma unroll
        for (unsigned t = 0; t < T; ++t) {
            const auto xv = sg_bloadN<4 * XW>(sg, xw + t * xs);
#pragma unroll
            for (unsigned i = 0; i < 4 * XW; ++i)
#pragma unroll
                for (unsigned j = 0; j < R; ++j) sum[j * T + t] = sum[j * T + t] + e[j][i] * xv[i];
        }
    }
    template <unsigned T, unsigned R, unsigned XW, unsigned LOOP>
    [[gnu::always_inline]] inline void rowt(sycl::sub_group sg, unsigned lane, unsigned r0, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        constexpr unsigned NQ = C / 4, ND = (C + 31) / 32;
        static_assert(32 % (4 * XW) == 0 && NQ % XW == 0);
        const float *xr = xn ? x + (size_t)(r0 / xn) * C * 32 : x; // (xn % R == 0: the R rows read one group)
        const uint8_t *rowp[R];
#pragma unroll
        for (unsigned j = 0; j < R; ++j) rowp[j] = w + (size_t)(r0 + j < rows ? r0 + j : r0) * RB;
        float sum[R * T];
#pragma unroll
        for (unsigned i = 0; i < R * T; ++i) sum[i] = 0;
        if constexpr (LOOP == 0) {
            constexpr unsigned SEGQ = Q8Seg<C>::v; // quant words loaded ahead
            static_assert(NQ % SEGQ == 0 && SEGQ % XW == 0);
            float dv[R][ND];
#pragma unroll
            for (unsigned j = 0; j < R; ++j) {
                const uint16_t *dp = reinterpret_cast<const uint16_t *>(rowp[j] + (size_t)C * 32);
#pragma unroll
                for (unsigned k = 0; k < ND; ++k) dv[j][k] = 32 * k + lane < C ? iq3::half(dp[32 * k + lane]) : 0.0f;
            }
#pragma unroll
            for (unsigned s0 = 0; s0 < NQ; s0 += SEGQ) {
                uint32_t q[R][SEGQ];
#pragma unroll
                for (unsigned j = 0; j < R; ++j)
#pragma unroll
                    for (unsigned m = 0; m < SEGQ; ++m)
                        q[j][m] = sg_bload(sg, reinterpret_cast<const uint32_t *>(rowp[j]) + (size_t)(s0 + m) * 32);
#pragma unroll
                for (unsigned m0 = 0; m0 < SEGQ; m0 += XW) {
                    const unsigned c0 = (s0 + m0) * 4; // 4 * XW chunks never cross a 32-chunk scale register
                    uint32_t qq[R][XW];
                    float ds[R];
#pragma unroll
                    for (unsigned j = 0; j < R; ++j) {
                        ds[j] = dv[j][c0 / 32];
#pragma unroll
                        for (unsigned mm = 0; mm < XW; ++mm) qq[j][mm] = q[j][m0 + mm];
                    }
                    word_group<R, T, XW>(sg, qq, ds, c0 % 32, xr + (size_t)(s0 + m0) * 128, xs, sum);
                }
            }
        } else {
            static_assert(C % 32 == 0);
            constexpr unsigned NS = NQ / 8; // segments of 8 words = 32 chunks
            uint32_t q[R][8];
            float ds[R];
            auto load = [&](unsigned s, uint32_t (&qd)[R][8], float (&dd)[R]) {
#pragma unroll
                for (unsigned j = 0; j < R; ++j) {
                    const uint32_t *qw = reinterpret_cast<const uint32_t *>(rowp[j]) + (size_t)s * 256;
#pragma unroll
                    for (unsigned m = 0; m < 8; ++m) qd[j][m] = sg_bload(sg, qw + m * 32);
                    dd[j] = iq3::half(reinterpret_cast<const uint16_t *>(rowp[j] + (size_t)C * 32)[s * 32 + lane]);
                }
            };
            load(0, q, ds);
#pragma nounroll
            for (unsigned s = 0; s < NS; ++s) {
                uint32_t qn[R][8];
                float dn[R];
                if (s + 1 < NS) load(s + 1, qn, dn);
#pragma unroll
                for (unsigned m0 = 0; m0 < 8; m0 += XW) {
                    uint32_t qq[R][XW];
#pragma unroll
                    for (unsigned j = 0; j < R; ++j)
#pragma unroll
                        for (unsigned mm = 0; mm < XW; ++mm) qq[j][mm] = q[j][m0 + mm];
                    word_group<R, T, XW>(sg, qq, ds, m0 * 4, xr + (size_t)(s * 8 + m0) * 128, xs, sum);
                }
#pragma unroll
                for (unsigned j = 0; j < R; ++j) {
                    ds[j] = dn[j];
#pragma unroll
                    for (unsigned m = 0; m < 8; ++m) q[j][m] = qn[j][m];
                }
            }
        }
        ws_reduce_store<R, T>(sg, lane, sum, r0, rows, y, ys, mt);
    }
};
// Q6_K packed rows (GemvQ6KP's layout and value (d * scale) * float(code - 32)): per block and lane one ql word and
// one qh pair; the R rows' 8 values are decoded once, then the T tokens' vec8 activation blocks run past them
template <unsigned NB> struct WsQ6 {
    unsigned rows, xn;
    static constexpr size_t RB = ((size_t)NB * 210 + 15) & ~(size_t)15;
    template <unsigned T, unsigned R, unsigned XW, unsigned LOOP>
    [[gnu::always_inline]] inline void rowt(sycl::sub_group sg, unsigned lane, unsigned r0, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        static_assert(XW == 1 && LOOP == 0);
        constexpr unsigned NS = NB * 16, NSR = (NS + 31) / 32, SEG = KSeg<NB>::v;
        static_assert(NB % SEG == 0);
        const float *xr = xn ? x + (size_t)(r0 / xn) * NB * 256 : x;
        const uint32_t *ql[R];
        const uint16_t *qh[R];
        float dbs[R][NSR];
#pragma unroll
        for (unsigned j = 0; j < R; ++j) {
            const uint8_t *row = w + (size_t)(r0 + j < rows ? r0 + j : r0) * RB;
            ql[j] = reinterpret_cast<const uint32_t *>(row);
            qh[j] = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 128);
            const int8_t *scl = reinterpret_cast<const int8_t *>(row + (size_t)NB * 192);
            const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 208);
#pragma unroll
            for (unsigned k = 0; k < NSR; ++k) {
                const unsigned si = 32 * k + lane < NS ? 32 * k + lane : NS - 1;
                dbs[j][k] = iq3::half(dp[si >> 4]) * float(int(scl[si]));
            }
        }
        float sum[R * T];
#pragma unroll
        for (unsigned i = 0; i < R * T; ++i) sum[i] = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NB; s0 += SEG) {
            uint32_t qa[R][SEG], qb[R][SEG];
#pragma unroll
            for (unsigned j = 0; j < R; ++j)
#pragma unroll
                for (unsigned m = 0; m < SEG; ++m) {
                    qa[j][m] = sg_bload(sg, ql[j] + (size_t)(s0 + m) * 32);
                    qb[j][m] = qh[j][(size_t)(s0 + m) * 32 + lane];
                }
#pragma unroll
            for (unsigned m = 0; m < SEG; ++m) {
                const unsigned b = s0 + m;
                float v[R][8];
#pragma unroll
                for (unsigned c = 0; c < 8; ++c) {
                    const unsigned h = c >> 2, cc = c & 3u;
                    const unsigned si = b * 16 + 2 * c;
#pragma unroll
                    for (unsigned j = 0; j < R; ++j) {
                        const unsigned low = (qa[j][m] >> (8 * (2 * h + (cc & 1u)) + 4 * (cc >> 1))) & 15u;
                        const unsigned high = (qb[j][m] >> (8 * h + 2 * cc)) & 3u;
                        const float d0 = sycl::select_from_group(sg, dbs[j][si / 32], si % 32);
                        const float d1 = sycl::select_from_group(sg, dbs[j][si / 32], si % 32 + 1);
                        v[j][c] = (lane < 16 ? d0 : d1) * float(int(low | (high << 4)) - 32);
                    }
                }
#pragma unroll
                for (unsigned t = 0; t < T; ++t) {
                    const auto xv = sg_bloadN<8>(sg, xr + t * xs + (size_t)b * 256);
#pragma unroll
                    for (unsigned c = 0; c < 8; ++c)
#pragma unroll
                        for (unsigned j = 0; j < R; ++j) sum[j * T + t] = sum[j * T + t] + v[j][c] * xv[c];
                }
            }
        }
        ws_reduce_store<R, T>(sg, lane, sum, r0, rows, y, ys, mt);
    }
};
// Q5_K packed rows (GemvQ5KP's layout and value f * float(code) - o)
template <unsigned NB> struct WsQ5 {
    unsigned rows, xn;
    static constexpr size_t RB = ((size_t)NB * 176 + 15) & ~(size_t)15;
    template <unsigned T, unsigned R, unsigned XW, unsigned LOOP>
    [[gnu::always_inline]] inline void rowt(sycl::sub_group sg, unsigned lane, unsigned r0, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        static_assert(XW == 1 && LOOP == 0);
        constexpr unsigned NG = NB * 8, NGR = (NG + 31) / 32, SEG = KSeg<NB>::v;
        static_assert(NB % SEG == 0);
        const float *xr = xn ? x + (size_t)(r0 / xn) * NB * 256 : x;
        const uint32_t *qs[R];
        const uint8_t *qh[R];
        float fac[R][NGR], off[R][NGR];
#pragma unroll
        for (unsigned j = 0; j < R; ++j) {
            const uint8_t *row = w + (size_t)(r0 + j < rows ? r0 + j : r0) * RB;
            qs[j] = reinterpret_cast<const uint32_t *>(row);
            qh[j] = row + (size_t)NB * 128;
            const uint8_t *hd = row + (size_t)NB * 160;
#pragma unroll
            for (unsigned k = 0; k < NGR; ++k) {
                const unsigned gi = 32 * k + lane < NG ? 32 * k + lane : NG - 1, c = gi & 7u, c3 = c & 3u;
                const uint8_t *hb = hd + 16 * (gi >> 3), *s = hb + 4;
                const unsigned u0 = s[c3], u1 = s[4 + c3], u2 = s[8 + c3];
                const unsigned scale = c < 4 ? u0 & 63u : (u2 & 15u) | ((u0 >> 6) << 4);
                const unsigned minimum = c < 4 ? u1 & 63u : (u2 >> 4) | ((u1 >> 6) << 4);
                fac[j][k] = iq3::half(iq3::u16(hb)) * float(scale);
                off[j][k] = iq3::half(iq3::u16(hb + 2)) * float(minimum);
            }
        }
        float sum[R * T];
#pragma unroll
        for (unsigned i = 0; i < R * T; ++i) sum[i] = 0;
#pragma unroll
        for (unsigned s0 = 0; s0 < NB; s0 += SEG) {
            uint32_t qa[R][SEG], qb[R][SEG];
#pragma unroll
            for (unsigned j = 0; j < R; ++j)
#pragma unroll
                for (unsigned m = 0; m < SEG; ++m) {
                    qa[j][m] = sg_bload(sg, qs[j] + (size_t)(s0 + m) * 32);
                    qb[j][m] = qh[j][(size_t)(s0 + m) * 32 + lane];
                }
#pragma unroll
            for (unsigned m = 0; m < SEG; ++m) {
                const unsigned b = s0 + m;
                float v[R][8];
#pragma unroll
                for (unsigned c = 0; c < 8; ++c) {
                    const unsigned gi = b * 8 + c;
#pragma unroll
                    for (unsigned j = 0; j < R; ++j) {
                        const unsigned code = ((qa[j][m] >> (4 * c)) & 15u) | (((qb[j][m] >> c) & 1u) << 4);
                        const float f = sycl::select_from_group(sg, fac[j][gi / 32], gi % 32);
                        const float o = sycl::select_from_group(sg, off[j][gi / 32], gi % 32);
                        v[j][c] = f * float(code) - o;
                    }
                }
#pragma unroll
                for (unsigned t = 0; t < T; ++t) {
                    const auto xv = sg_bloadN<8>(sg, xr + t * xs + (size_t)b * 256);
#pragma unroll
                    for (unsigned c = 0; c < 8; ++c)
#pragma unroll
                        for (unsigned j = 0; j < R; ++j) sum[j * T + t] = sum[j * T + t] + v[j][c] * xv[c];
                }
            }
        }
        ws_reduce_store<R, T>(sg, lane, sum, r0, rows, y, ys, mt);
    }
};
// position p = (row block p / ng, token group p % ng), as DenseRowsGR; the last group's tokens past mt are computed
// on the buffers' spare rows and not stored
template <typename W, unsigned T, unsigned R, unsigned XW, unsigned LOOP> struct DenseRowsWS {
    W k; // WsQ8 / WsQ6 / WsQ5: rows and xn (xn % R == 0)
    const uint8_t *w;
    const float *x;
    size_t xs;
    float *y;
    size_t ys;
    unsigned mt, ng;
    unsigned n() const { return (k.rows + R - 1) / R * ng; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned p) const {
        const unsigned r0 = p / ng * R, t0 = (p % ng) * T;
        k.template rowt<T, R, XW, LOOP>(sg, lane, r0, w, x + t0 * xs, xs, y + t0 * ys, ys, mt - t0);
    }
};
// the weight-stationary kernel of a packed dense kernel (void: none) and its format / columns
template <typename DK> struct WsOf { using type = void; static constexpr unsigned fmt = 0, cols = 0; };
template <unsigned C, typename A> struct WsOf<GemvQ8P<C, A>> { using type = WsQ8<C>; static constexpr unsigned fmt = 8, cols = 32 * C; };
template <unsigned NB, typename A> struct WsOf<GemvQ6KP<NB, A>> { using type = WsQ6<NB>; static constexpr unsigned fmt = 6, cols = 256 * NB; };
template <unsigned NB, typename A> struct WsOf<GemvQ5KP<NB, A>> { using type = WsQ5<NB>; static constexpr unsigned fmt = 5, cols = 256 * NB; };
// a form: T tokens x R rows per sub-group, XW (Q8_0), LOOP (Q8_0); id 0 = the engine's form
template <unsigned T, unsigned R, unsigned XW = 1, unsigned LOOP = 0> struct WsF {
    static constexpr unsigned t = T, r = R, xw = XW, loop = LOOP, id = T | R << 8 | XW << 12 | LOOP << 14;
};
template <typename... Fs> struct WsList {};
// the launch a dense matrix runs in: alone (dense_m), with the stream mix's dot rows (dense_m's rider: q_a with
// OWN_MT_RIDE), or as the shared expert's gate + up pair in the router's launch (route_shared_m, OWN_MT_RFUSE; rows:
// one matrix's)
enum : unsigned { WS_PLAIN = 0, WS_DOTS = 1, WS_SHARED = 2 };
// block-size classes: 2 .. 6 (the guessing checks) as themselves, 9-16 -> 16, 17-32 -> 32, 33-64 -> 64,
// 65-128 -> 128, 129-256 -> 256; 1, 7, 8: none (the engine's forms)
constexpr unsigned ws_cls(unsigned mt) {
    return mt >= 2 && mt <= 6 ? mt
           : mt < 9           ? 0
           : mt <= 16         ? 16
           : mt <= 32         ? 32
           : mt <= 64         ? 64
           : mt <= 128        ? 128
           : mt <= 256        ? 256
                              : 0;
}
// WsTab<format, columns, launch kind>: forms = every form pick() can return; pick(rows on the card, tokens).
template <unsigned FMT, unsigned COLS, unsigned KIND> struct WsTab {
    using forms = WsList<>;
    static constexpr unsigned pick(unsigned, unsigned) { return 0; }
};
// one form id per block-size class (ws_cls): the checks' 2 .. 6 tokens, prompt blocks of 9-16, 17-32, 33-64,
// 65-128 and 129-256 tokens (0: the engine's form). A prompt class takes a form only where the bench measured it
// at least 3 % faster at every size tried in the class (9 / 12 / 16, 17 / 24 / 32, 33 / 48 / 64, 65 / 96 / 128,
// 129 / 192 / 256): the class's first size is a T-form's worst case (a group of mostly spare tokens)
struct WsPicks {
    unsigned c2, c3, c4, c5, c6, c16, c32, c64, c128, c256;
    constexpr unsigned at(unsigned mt) const {
        switch (ws_cls(mt)) {
        case 2: return c2;
        case 3: return c3;
        case 4: return c4;
        case 5: return c5;
        case 6: return c6;
        case 16: return c16;
        case 32: return c32;
        case 64: return c64;
        case 128: return c128;
        case 256: return c256;
        default: return 0;
        }
    }
};
// Q8_0 forms (XW = 2: vec8 activation reads; L: the segment loop), K-quant forms (XW = 1)
using WfX16R2 = WsF<16, 2, 2, 0>;
using WfX8R2L = WsF<8, 2, 2, 1>;
using WfX4R4 = WsF<4, 4, 2, 0>;
using WfX2R4 = WsF<2, 4, 2, 0>;
using WfX3R1 = WsF<3, 1, 2, 0>;
using WfX5R1 = WsF<5, 1, 2, 0>;
using WfX6R1 = WsF<6, 1, 2, 0>;
using WfK16R2 = WsF<16, 2>;
using WfK8R2 = WsF<8, 2>;
using WfK4R2 = WsF<4, 2>;
using WfK2R4 = WsF<2, 4>;
using WfK2R2 = WsF<2, 2>;
using WfK2R1 = WsF<2, 1>;
using WfK3R1 = WsF<3, 1>;
using WfK3R2 = WsF<3, 2>;
using WfK4R1 = WsF<4, 1>;
using WfK5R1 = WsF<5, 1>;
using WfK5R2 = WsF<5, 2>;
using WfK6R1 = WsF<6, 1>;
using WfK6R2 = WsF<6, 2>;
constexpr unsigned X16R2 = WfX16R2::id, X8R2L = WfX8R2L::id, X4R4 = WfX4R4::id, K16R2 = WfK16R2::id,
                   K8R2 = WfK8R2::id, K4R2 = WfK4R2::id;
// Tables (card 2 of six, 12 heads; us per launch, engine -> table form, cold weights). The engine: tg87 BEST
// (OWN_MT_TG=4, OWN_MT_W16 default, OWN_MT_TGR default 16:4 (and past 16) + 2..6:4 from 4,096 rows,
// OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3).
// Q8_0 q_b (1,280 columns; 4,096 rows on an 8-head card, 6,144 on a 12-head one; engine G4 R4, at 9-15 tokens G4):
// 16 tokens 99.6 -> 47.2, 256: 1562 -> 637 (2.45x; every class >= 1.66x); checks 27.0 -> 18.0, 27.2 -> 23.8,
// 37.0 -> 26.9, 49.3 -> 29.5, 49.3 -> 32.6
template <> struct WsTab<8, 1280, WS_PLAIN> {
    using forms = WsList<WfX16R2, WfX2R4, WfX3R1, WfX4R4, WfX5R1, WfX6R1>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows >= 4096 && rows <= 8192)
            return WsPicks{WfX2R4::id, WfX3R1::id, WfX4R4::id, WfX5R1::id, WfX6R1::id, X16R2, X16R2, X16R2, X16R2, X16R2}.at(mt);
        return 0;
    }
};
// Q8_0 5,120 columns alone: q_a (1,280 rows) and kv (512) keep 9-16 (q_a 0.97x at best, kv 0.75x) and the checks;
// q_a 17-32 >= 1.18x, 33-64 >= 1.18x, 65-128 >= 1.49x, 256: 1418 -> 580; kv 17-128 >= 1.10x, 256: 544 -> 239
template <> struct WsTab<8, 5120, WS_PLAIN> {
    using forms = WsList<WfX8R2L, WfX4R4>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows == 1280 || rows == 512) return WsPicks{0, 0, 0, 0, 0, 0, X8R2L, X8R2L, X8R2L, X4R4}.at(mt);
        return 0;
    }
};
// q_a with the stream mix's dot rows: 9-32 kept (16: 106 us, 0.84-0.91x; 17: <= 0.99x), 33-64 >= 1.19x,
// 65-128 >= 1.46x, 256: 2282 -> 1501
template <> struct WsTab<8, 5120, WS_DOTS> {
    using forms = WsList<WfX4R4>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows == 1280) return WsPicks{0, 0, 0, 0, 0, 0, 0, X4R4, X4R4, X4R4}.at(mt);
        return 0;
    }
};
// the shared expert's gate + up (384 + 384 rows) in the router's launch: 16: 38.5 -> 37.1 (9-16 >= 1.03x), 17-32
// kept (17: 0.77x), 33-64 >= 1.37x, 65-128 >= 1.60x, 256: 857 -> 352
template <> struct WsTab<8, 5120, WS_SHARED> {
    using forms = WsList<WfX8R2L, WfX4R4>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows == 384) return WsPicks{0, 0, 0, 0, 0, X8R2L, 0, X8R2L, X8R2L, X4R4}.at(mt);
        return 0;
    }
};
// Q8_0 output-a (4,096 columns; engine G4; checks kept, 0.6-0.8x): a whole group (1,024 rows) 16: 37.8 -> 31.1,
// 17-64 >= 1.11x, 65-128 >= 1.47x, 256: 871 -> 357; 768 rows 16: 1.35x, 17-32 >= 1.08x, 33-64 >= 1.29x, 256: 2.44x;
// half a group (512) 9-16 kept (0.85-0.93x), 17-32 >= 1.25x, 33-64 >= 1.15x, 256: 436 -> 179
template <> struct WsTab<8, 4096, WS_PLAIN> {
    using forms = WsList<WfX4R4, WfX8R2L>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows > 896 && rows <= 1024) return WsPicks{0, 0, 0, 0, 0, X4R4, X8R2L, X8R2L, X4R4, X4R4}.at(mt);
        if (rows > 639 && rows <= 896) return WsPicks{0, 0, 0, 0, 0, X4R4, X4R4, X8R2L, X4R4, X4R4}.at(mt);
        if (rows >= 384 && rows <= 639) return WsPicks{0, 0, 0, 0, 0, 0, X4R4, X8R2L, X4R4, X4R4}.at(mt);
        return 0;
    }
};
// Q8_0 output-b (8,192 columns, ~864 rows; engine G8 R2): 9-32 kept (<= 1.02x), 33-128 >= 1.09x, 256: 877 -> 657
template <> struct WsTab<8, 8192, WS_PLAIN> {
    using forms = WsList<WfX8R2L, WfX4R4>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows >= 768 && rows <= 1024) return WsPicks{0, 0, 0, 0, 0, 0, 0, X8R2L, X8R2L, X4R4}.at(mt);
        return 0;
    }
};
// Q8_0 shared down (2,304 columns, ~864 rows; engine G4 R2): 16: 23.3 -> 15.7, every class >= 1.35x, 256: 313 -> 195
template <> struct WsTab<8, 2304, WS_PLAIN> {
    using forms = WsList<WfX4R4>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows >= 768 && rows <= 1024) return WsPicks{0, 0, 0, 0, 0, X4R4, X4R4, X4R4, X4R4, X4R4}.at(mt);
        return 0;
    }
};
// Q6_K q_b (1,280 columns, 4,096-8,192 rows; engine G4, checks G R4): 16: 105 -> 47.6, 256: 1763 -> 705, every class
// >= 1.55x; checks 30.2 -> 18.3, 33.8 -> 22.1, 48.2 -> 24.8, 48.1 -> 27.6, 48.1 -> 29.5
template <> struct WsTab<6, 1280, WS_PLAIN> {
    using forms = WsList<WfK16R2, WfK2R4, WfK3R1, WfK4R1, WfK5R1, WfK6R1>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows >= 4096 && rows <= 8192)
            return WsPicks{WfK2R4::id, WfK3R1::id, WfK4R1::id, WfK5R1::id, WfK6R1::id, K16R2, K16R2, K16R2, K16R2, K16R2}.at(mt);
        return 0;
    }
};
// Q6_K 5,120 columns alone (engine G4 R2; checks kept): q_a (1,280 rows) 9-64 >= 1.13x, 65-128 >= 1.14x,
// 256: 945 -> 758; kv (512) 9-128 >= 1.09x, 256: 386 -> 306. The head (>= 16,384 rows; checks only, engine G R4):
// 320 -> 177, 299 -> 193, 326 -> 211, 385 -> 232, 385 -> 262
template <> struct WsTab<6, 5120, WS_PLAIN> {
    using forms = WsList<WfK4R2, WfK8R2, WfK16R2, WfK2R1, WfK3R2, WfK5R2, WfK6R2>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows == 1280) return WsPicks{0, 0, 0, 0, 0, K4R2, K4R2, K4R2, K16R2, K8R2}.at(mt);
        if (rows == 512) return WsPicks{0, 0, 0, 0, 0, K4R2, K4R2, K4R2, K4R2, K8R2}.at(mt);
        if (rows >= 16384) return WsPicks{WfK2R1::id, WfK3R2::id, K4R2, WfK5R2::id, WfK6R2::id, 0, 0, 0, 0, 0}.at(mt);
        return 0;
    }
};
// Q6_K q_a with the mix's dot rows (1,280 rows): checks 25.0 -> 20.2, 36.1 -> 31.5, (4 kept: 0.86x), 50.7 -> 40.3,
// 54.9 -> 50.2; prompt 16: 121 -> 111, every class >= 1.08x, 256: 1857 -> 1659
template <> struct WsTab<6, 5120, WS_DOTS> {
    using forms = WsList<WfK2R1, WfK3R1, WfK5R2, WfK6R2, WfK4R2, WfK8R2, WfK16R2>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows == 1280) return WsPicks{WfK2R1::id, WfK3R1::id, 0, WfK5R2::id, WfK6R2::id, K4R2, K4R2, K8R2, K16R2, K16R2}.at(mt);
        return 0;
    }
};
// Q6_K output-a (4,096 columns; engine G4 R2, checks G3 at 3 / 5 tokens): 1,024 rows 16: 40.7 -> 32.7, every class
// >= 1.22x, 256: 619 -> 470, checks 3: 20.6 -> 14.3, 5: 24.3 -> 22.1 (2 / 4 / 6 kept); 768 rows every class
// >= 1.26x; 512 rows every class >= 1.14x
template <> struct WsTab<6, 4096, WS_PLAIN> {
    using forms = WsList<WfK3R2, WfK5R2, WfK4R2, WfK8R2>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows > 896 && rows <= 1024) return WsPicks{0, WfK3R2::id, 0, WfK5R2::id, 0, K4R2, K4R2, K8R2, K8R2, K8R2}.at(mt);
        if (rows > 639 && rows <= 896) return WsPicks{0, 0, 0, 0, 0, K8R2, K4R2, K8R2, K8R2, K8R2}.at(mt);
        if (rows >= 384 && rows <= 639) return WsPicks{0, 0, 0, 0, 0, K4R2, K4R2, K4R2, K8R2, K8R2}.at(mt);
        return 0;
    }
};
// Q6_K output-b (8,192 columns, ~864 rows; engine G4 R2): 16: 70.0 -> 53.6, every class >= 1.05x, 256: 995 -> 848;
// checks 3: 66.9 -> 26.6, 5: 73.1 -> 41.9, 6: 73.0 -> 46.4 (2 / 4 kept)
template <> struct WsTab<6, 8192, WS_PLAIN> {
    using forms = WsList<WfK3R2, WfK5R2, WfK6R2, WfK8R2, WfK4R2>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows >= 768 && rows <= 1024) return WsPicks{0, WfK3R2::id, 0, WfK5R2::id, WfK6R2::id, K8R2, K8R2, K4R2, K8R2, K8R2}.at(mt);
        return 0;
    }
};
// Q6_K engram_kv (6,144 columns, ~4,266 rows; engine G R4, at 9-15 tokens G4): checks 85.4 -> 57.9, 108 -> 65.9,
// 107 -> 72.2, 136 -> 94.8, 136 -> 99.4; 16: 246 -> 162, 9-64 >= 1.22x, 65-128 >= 1.36x, 129-256 kept (<= 1.01x)
template <> struct WsTab<6, 6144, WS_PLAIN> {
    using forms = WsList<WfK2R2, WfK3R2, WfK4R2, WfK5R2, WfK6R2, WfK8R2, WfK16R2>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows >= 4096 && rows <= 4608)
            return WsPicks{WfK2R2::id, WfK3R2::id, K4R2, WfK5R2::id, WfK6R2::id, K8R2, K8R2, K8R2, K16R2, 0}.at(mt);
        return 0;
    }
};
// Q5_K shared gate + up (384 + 384 rows) in the router's launch (engine G4, checks G1 at 2 tokens): 16: 86.6 -> 40.6,
// every class >= 1.53x, 256: 918 -> 490; check 2: 15.2 -> 13.0 (3-6 kept)
template <> struct WsTab<5, 5120, WS_SHARED> {
    using forms = WsList<WfK2R1, WfK4R2, WfK8R2>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows == 384) return WsPicks{WfK2R1::id, 0, 0, 0, 0, K8R2, K4R2, K8R2, K8R2, K8R2}.at(mt);
        return 0;
    }
};
// Q5_K shared down (2,304 columns, ~864 rows; engine G4): 16: 43.9 -> 19.1, every class >= 1.72x, 256: 499 -> 241
template <> struct WsTab<5, 2304, WS_PLAIN> {
    using forms = WsList<WfK8R2>;
    static constexpr unsigned pick(unsigned rows, unsigned mt) {
        if (rows >= 768 && rows <= 1024) return WsPicks{0, 0, 0, 0, 0, K8R2, K8R2, K8R2, K8R2, K8R2}.at(mt);
        return 0;
    }
};
// ws_rows<DK, KIND>: f(DenseRowsWS rows) when WsTab picks a form for this launch; false: none (the engine's form).
// cap: the tokens the activation buffers hold (a last group's tokens past mt are read: T * ng <= cap)
template <typename... Fs, typename G> inline bool ws_each(WsList<Fs...>, G &&g) { return (g(Fs{}) || ...); }
template <typename DK, unsigned KIND, typename F>
inline bool ws_rows(const DK &dk, const uint8_t *w, const float *x, size_t xs, float *y, size_t ys, unsigned mt,
                    unsigned cap, F &&f) {
    using O = WsOf<DK>;
    using Tab = WsTab<O::fmt, O::cols, KIND>;
    if constexpr (O::fmt == 0) return false;
    else {
        const unsigned id = Tab::pick(dk.rows, mt);
        if (!id) return false;
        return ws_each(typename Tab::forms{}, [&](auto fm) {
            using FM = decltype(fm);
            if (FM::id != id || dk.xn % FM::r || (mt + FM::t - 1) / FM::t * FM::t > cap) return false;
            using WK = typename O::type;
            f(DenseRowsWS<WK, FM::t, FM::r, FM::xw, FM::loop>{WK{dk.rows, dk.xn}, w, x, xs, y, ys, mt,
                                                               (mt + FM::t - 1) / FM::t});
            return true;
        });
    }
}

// F32 rows (no packing; rows are 16-byte aligned when cols % 4 == 0): lane l
// sums w[k] * x[k], k = l, l + 32, ... ascending (GemvT<F32> order), C chunks.
template <unsigned C, typename A> struct GemvF32P {
    static_assert(sizeof(typename A::T) == 4, "packed kernels take f32 activations");
    static_assert(C % 8 == 0);
    unsigned rows;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, float *y) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned r = packed_row_id(it);
        if (r >= rows) return;
        row(sg, sg.get_local_linear_id(), r, w, x, y);
    }
    // one row on one sub-group (also run inside fused launches: DenseRows)
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                           const float *x, float *y) const {
        const float *row = reinterpret_cast<const float *>(w) + (size_t)r * C * 32;
        float sum = 0;
#pragma unroll
        for (unsigned s = 0; s < C / 8; ++s) {
            const auto wv = sg_bloadN<8>(sg, row + (size_t)s * 256);
            const auto xv = sg_bloadN<8>(sg, x + (size_t)s * 256);
#pragma unroll
            for (unsigned m = 0; m < 8; ++m) sum = sum + wv[m] * xv[m];
        }
        sum = sg_tree32(sg, sum);
        if (lane == 0) y[r] = sum;
    }
    // M tokens (see "multi-token rows" at lane_sum_tm): token t reads x + t * xs and writes
    // y[t * ys + r] when t < mt; xs % 4 == 0 (block reads).
    static constexpr unsigned MTG = 8;
    template <unsigned MT, unsigned G = MTG, unsigned T0 = 0>
    [[gnu::always_inline]] inline void rowm(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        if constexpr (T0 < MT) {
            constexpr unsigned NT = MT - T0 < G ? MT - T0 : G;
            if (T0 < mt) rowg<NT>(sg, lane, r, w, x + T0 * xs, xs, y + T0 * ys, ys, mt - T0);
            rowm<MT, G, T0 + NT>(sg, lane, r, w, x, xs, y, ys, mt);
        }
    }
    template <unsigned NT>
    [[gnu::always_inline]] inline void rowg(sycl::sub_group sg, unsigned lane, unsigned r, const uint8_t *w,
                                            const float *x, size_t xs, float *y, size_t ys, unsigned mt) const {
        const float *row = reinterpret_cast<const float *>(w) + (size_t)r * C * 32;
        float sum[NT];
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) sum[t] = 0;
#pragma unroll
        for (unsigned s = 0; s < C / 8; ++s) {
            const auto wv = sg_bloadN<8>(sg, row + (size_t)s * 256);
            sycl::vec<float, 8> xv[NT];
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) xv[t] = sg_bloadN<8>(sg, x + t * xs + (size_t)s * 256);
#pragma unroll
            for (unsigned m = 0; m < 8; ++m)
#pragma unroll
                for (unsigned t = 0; t < NT; ++t) sum[t] = sum[t] + wv[m] * xv[t][m];
        }
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) sum[t] = sg_tree32(sg, sum[t]);
        if (lane == 0) {
#pragma unroll
            for (unsigned t = 0; t < NT; ++t)
                if (t < mt) y[t * ys + r] = sum[t];
        }
    }
};

// ---- small per-layer ops, latency-bound forms (2026-11-09) -------------------
// Same float/double operations in the same order as the kernels they replace
// (RmsNormA, HcMixDots32A, HcMixFinishSeg, SparseScoreA, SparseSoftmax,
// SparseOut); the old forms waited on one dependent load at a time (a
// 160-element lane loop took ~45 us even in float) and ran the Sinkhorn
// normalisation in a single work-item. Gated bitwise in
// planning/dsv41-fixtures/test_small_v41_device.cpp. f32 activations only.

// RmsNormA, N % 256 == 0, one sub-group. x and w are read with 8-wide
// sub-group block reads (16-byte aligned pointers: the backend checks and
// falls back to RmsNormA): plain per-lane loads in a lane loop were issued one
// at a time (~290 ns each, 160 per lane at N = 5120).
template <unsigned N> struct RmsNormP {
    static_assert(N % 256 == 0);
    static constexpr unsigned C = N / 256;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *x, const float *w, float *y) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        double acc = 0;
#pragma unroll
        for (unsigned c = 0; c < C; ++c) {
            const auto xv = sg_bloadN<8>(sg, x + c * 256);
#pragma unroll
            for (unsigned m = 0; m < 8; ++m) acc += double(xv[m]) * xv[m];
        }
        for (int w_ = 16; w_; w_ >>= 1) acc += sycl::select_from_group(sg, acc, (int)lane ^ w_);
        const float rs = float(1.0 / sycl::sqrt(acc / N + 1e-20));
#pragma unroll
        for (unsigned c = 0; c < C; ++c) {
            const auto xv = sg_bloadN<8>(sg, x + c * 256);
            const auto wv = sg_bloadN<8>(sg, w + c * 256);
#pragma unroll
            for (unsigned m = 0; m < 8; ++m) y[c * 256 + m * 32 + lane] = wv[m] * (xv[m] * rs);
        }
    }
};

// RmsNormP on a work-group of S sub-groups: every sub-group computes the same
// statistic (same loads, same serial lane sums, same tree), then writes the
// 256-element chunks c with c % S == its index (block stores). Not in place.
// OWN_NORM_FF (host, read when a norm kernel is built; round 18 n1-n5, tools/bench/bench_norm_ff.cpp): the RMS
// norm's scale from a fast bracket of the double chain; same values bit for bit by construction (below), 1.44 M
// bench vectors identical. Alone about as fast as the chain; beside the stream-mix dots in work-groups of 4 rows
// (OWN_NORM_WG=128) the launch is 9.9 -> 6.0 us, because the four sub-groups no longer queue for the double unit
inline bool g_norm_ff = true;
// a norm built in device code (benches) takes the chain
inline bool norm_ff_default() {
#ifdef __SYCL_DEVICE_ONLY__
    return false;
#else
    return g_norm_ff;
#endif
}
template <unsigned N, unsigned S> struct RmsNormPS {
    static_assert(N % 256 == 0);
    static constexpr unsigned C = N / 256;
    bool ff = norm_ff_default();
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *x, const float *w, float *y) const {
        sycl::sub_group sg = it.get_sub_group();
        part(sg, sg.get_local_linear_id(), sg.get_group_linear_id(), x, w, y, ff);
    }
    static inline float rs_of(double acc) { return float(1.0 / sycl::sqrt(acc / N + 1e-20)); }
    // the chain: acc = sum of double(x) * x, per lane C * 8 terms in order, then the xor tree
    [[gnu::always_inline]] static inline double acc_chain(sycl::sub_group sg, unsigned lane, const float *x) {
        double acc = 0;
#pragma unroll
        for (unsigned c = 0; c < C; ++c) {
            const auto xv = sg_bloadN<8>(sg, x + c * 256);
#pragma unroll
            for (unsigned m = 0; m < 8; ++m) acc += double(xv[m]) * xv[m];
        }
        for (int w_ = 16; w_; w_ >>= 1) acc += sycl::select_from_group(sg, acc, (int)lane ^ w_);
        return acc;
    }
    // The fast bracket. rs_of is a composition of correctly rounded monotone operations, so the chain's scale is
    // float(D_chain) with D_chain = 1 / sqrt(acc_chain / N + 1e-20) in double. Estimate s: per lane blocks of 16
    // terms in float-float (p = x * x, e = fma(x, x, -p) exact; TwoSum of the p, the low parts summed in float),
    // each block's (hi, lo) added in double, the same xor tree. All terms >= 0 with exact sum E (u = 2^-24,
    // v = 2^-53): a block's low sum rounds by <= k(k + 1) u^2 E_b (9.7e-13 E_b at k = 16), the double adds and
    // tree by <= 25 v E, the chain by <= 165 v E: |acc_chain - s| < 1.0e-12 E. That moves D by at most
    // 0.5e-12 D plus four double roundings, so D (from s) farther than 4e-12 D from both midpoints between
    // float(D) and its float neighbours means float(D_chain) == float(D). Needs 1e-25 < s < 1e30 (no float
    // overflow, flushes far under the bound); otherwise, or near a midpoint (~6e-5 of the bench vectors), ok =
    // false and the chain runs.
    [[gnu::always_inline]] static inline float rs_fast(sycl::sub_group sg, unsigned lane, const float *x, bool &ok) {
        double acc = 0;
#pragma unroll
        for (unsigned c2 = 0; c2 < C; c2 += 2) {
            float hi = 0, lo = 0;
#pragma unroll
            for (unsigned h = 0; h < 2 && c2 + h < C; ++h) {
                const auto xv = sg_bloadN<8>(sg, x + (c2 + h) * 256);
#pragma unroll
                for (unsigned m = 0; m < 8; ++m) {
                    const float a = xv[m];
                    const float p = a * a;
                    const float e = sycl::fma(a, a, -p);
                    const float t = hi + p;
                    const float z = t - hi;
                    const float er = (hi - (t - z)) + (p - z);
                    hi = t;
                    lo = lo + (er + e);
                }
            }
            acc = acc + double(hi);
            acc = acc + double(lo);
        }
        for (int w_ = 16; w_; w_ >>= 1) acc += sycl::select_from_group(sg, acc, (int)lane ^ w_);
        const double D = 1.0 / sycl::sqrt(acc / N + 1e-20);
        const float f = float(D);
        const double fd = f, up = sycl::nextafter(f, INFINITY), dn = sycl::nextafter(f, 0.0f);
        ok = acc > 1e-25 && acc < 1e30 && D * (1 + 4e-12) < fd + (up - fd) * 0.5 && D * (1 - 4e-12) > fd - (fd - dn) * 0.5;
        return f;
    }
    // sub-group sgi of S: the whole sum (every sub-group forms it alike), then its share of the outputs;
    // no barrier between sub-groups, so the parts also run as rows of a fused launch (NormRows). ff: the fast
    // bracket first (N >= 1280; the same scale bit for bit)
    [[gnu::always_inline]] static inline void part(sycl::sub_group sg, unsigned lane, unsigned sgi, const float *x,
                                                   const float *w, float *y, bool ff = false) {
        float rs = 0;
        bool ok = false;
        if constexpr (N >= 1280)
            if (ff) rs = rs_fast(sg, lane, x, ok);
        if (!ok) rs = rs_of(acc_chain(sg, lane, x));
#pragma unroll
        for (unsigned c = 0; c < C; ++c) {
            if (c % S != sgi) continue;
            const auto xv = sg_bloadN<8>(sg, x + c * 256);
            const auto wv = sg_bloadN<8>(sg, w + c * 256);
            sycl::vec<float, 8> o;
#pragma unroll
            for (unsigned m = 0; m < 8; ++m) o[m] = wv[m] * (xv[m] * rs);
            sg.store<8>(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                            y + c * 256), o);
        }
    }
};

// HcMixDots32A for 4*H columns in SEG segments (one sub-group per (row, segment))
template <unsigned H, unsigned SEG> struct HcMixDotsP {
    static constexpr unsigned N = 4 * H, LEN = N / SEG, K = LEN / 32;
    static_assert(LEN % 32 == 0);
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *streams, const float *fn, double *out) const {
        sycl::sub_group sg = it.get_sub_group();
        row(sg, sg.get_local_linear_id(), it.get_group_linear_id(), streams, fn, out);
    }
    // partial grp (= dot r, segment sgi) on one sub-group (also inside fused launches: HcDotsRows)
    [[gnu::always_inline]] static inline void row(sycl::sub_group sg, unsigned l, unsigned grp, const float *streams,
                                                  const float *fn, double *out) {
        const unsigned r = grp / SEG, sgi = grp % SEG;
        // 8-wide block reads (16-byte aligned streams and fn: checked by the backend)
        static_assert(LEN % 256 == 0);
        const float *sv = streams + (size_t)sgi * LEN;
        const float *f = fn + (size_t)(r < 24 ? r : 0) * N + (size_t)sgi * LEN;
        double acc = 0;
#pragma unroll
        for (unsigned c = 0; c < LEN / 256; ++c) {
            const auto a = sg_bloadN<8>(sg, sv + c * 256);
            const auto b = sg_bloadN<8>(sg, f + c * 256);
#pragma unroll
            for (unsigned m = 0; m < 8; ++m) acc += double(r < 24 ? b[m] : a[m]) * a[m];
        }
        for (unsigned w = 1; w < 32; w *= 2) {
            double o = sycl::select_from_group(sg, acc, (l + w) % 32);
            if (l % (2 * w) == 0) acc = acc + o;
        }
        if (l == 0) out[grp] = acc;
    }
    // M tokens (see "multi-token rows" at lane_sum_tm): token t reads streams + t * ss and writes
    // out[t * os + grp] when t < mt; the fn values are read once per chunk for a group's tokens, and
    // each token keeps row()'s products, sums and tree. ss % 4 == 0 (block reads).
    static constexpr unsigned MTG = 4;
    template <unsigned MT, unsigned G = MTG, unsigned T0 = 0>
    [[gnu::always_inline]] static inline void rowm(sycl::sub_group sg, unsigned l, unsigned grp, const float *streams,
                                                   size_t ss, const float *fn, double *out, size_t os, unsigned mt) {
        if constexpr (T0 < MT) {
            constexpr unsigned NT = MT - T0 < G ? MT - T0 : G;
            if (T0 < mt) rowg<NT>(sg, l, grp, streams + T0 * ss, ss, fn, out + T0 * os, os, mt - T0);
            rowm<MT, G, T0 + NT>(sg, l, grp, streams, ss, fn, out, os, mt);
        }
    }
    template <unsigned NT>
    [[gnu::always_inline]] static inline void rowg(sycl::sub_group sg, unsigned l, unsigned grp, const float *streams,
                                                   size_t ss, const float *fn, double *out, size_t os, unsigned mt) {
        const unsigned r = grp / SEG, sgi = grp % SEG;
        static_assert(LEN % 256 == 0);
        const float *sv = streams + (size_t)sgi * LEN; // token t: sv + t * ss
        const float *f = fn + (size_t)(r < 24 ? r : 0) * N + (size_t)sgi * LEN;
        double acc[NT];
#pragma unroll
        for (unsigned t = 0; t < NT; ++t) acc[t] = 0;
#pragma unroll
        for (unsigned c = 0; c < LEN / 256; ++c) {
            const auto b = sg_bloadN<8>(sg, f + c * 256);
            sycl::vec<float, 8> a[NT];
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) a[t] = sg_bloadN<8>(sg, sv + t * ss + c * 256);
#pragma unroll
            for (unsigned m = 0; m < 8; ++m)
#pragma unroll
                for (unsigned t = 0; t < NT; ++t) acc[t] += double(r < 24 ? b[m] : a[t][m]) * a[t][m];
        }
        for (unsigned w = 1; w < 32; w *= 2) {
#pragma unroll
            for (unsigned t = 0; t < NT; ++t) {
                double o = sycl::select_from_group(sg, acc[t], (l + w) % 32);
                if (l % (2 * w) == 0) acc[t] = acc[t] + o;
            }
        }
        if (l == 0) {
#pragma unroll
            for (unsigned t = 0; t < NT; ++t)
                if (t < mt) out[t * os + grp] = acc[t];
        }
    }
};
// HcMixDotsP for MT tokens as its own launch (launch_sg, 25 * SEG work-groups of one sub-group)
template <unsigned H, unsigned SEG, unsigned MT, unsigned G = HcMixDotsP<H, SEG>::MTG> struct HcMixDotsPM {
    size_t ss, os; // per-token strides of streams (floats) and out (doubles)
    unsigned mt;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *streams, const float *fn, double *out) const {
        sycl::sub_group sg = it.get_sub_group();
        HcMixDotsP<H, SEG>::template rowm<MT, G>(sg, sg.get_local_linear_id(), (unsigned)it.get_group_linear_id(), streams,
                                               ss, fn, out, os, mt);
    }
};

// HcMixFinishSeg on one sub-group: lane r sums its 8 segment partials, lanes
// 0..3 / 4..7 / 8..23 hold pre / post / comb, each comb row's max and sums are
// formed from its four lanes in the original order (row j = lanes 8+4j..11+4j).
struct HcMixFinishSG {
    int h, seg;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const double *d, const float *scale, const float *base,
                                     float *pre, float *post, float *comb) const {
        run(it.get_sub_group(), d, scale, base, pre, post, comb);
    }
    int form = 0; // 1: run_bc (the row / column sums from constant-lane broadcasts; same values)
    // the whole finish on one sub-group (also inside fused launches: HcFinishRows)
    [[gnu::always_inline]] inline void run(sycl::sub_group sg, const double *d, const float *scale, const float *base,
                                           float *pre, float *post, float *comb) const {
        if (form == 1) return run_bc(sg, d, scale, base, pre, post, comb);
        run0(sg, d, scale, base, pre, post, comb);
    }
    // run0 with every row(k) / col(j) read (a lane-dependent shuffle) replaced by the 16 comb lanes' values
    // broadcast from constant lanes: each lane forms all four row (column) sums in run0's order and keeps its
    // own; the same expressions on the same values, so the same results bit for bit
    [[gnu::always_inline]] inline void run_bc(sycl::sub_group sg, const double *d, const float *scale, const float *base,
                                              float *pre, float *post, float *comb) const {
        const int l = (int)sg.get_local_linear_id();
        const int N = 4 * h;
        double t = 0;
        if (l < 25)
            for (int k = 0; k < seg; ++k) t += d[l * seg + k];
        const double t24 = sycl::select_from_group(sg, t, 24);
        const float rsqrt = float(1.0 / sycl::sqrt(t24 / N + 1e-20));
        const float m = float(t) * rsqrt;
        auto sig = [](float v) { return 1.0f / (1.0f + sycl::exp(-v)); };
        const float eps = 1e-6f;
        if (l < 4) pre[l] = sig(m * scale[0] + base[l]) + eps;
        else if (l < 8) post[l - 4] = 2.0f * sig(m * scale[1] + base[l]);
        const int q = l - 8;
        const bool in = q >= 0 && q < 16;
        const int rr = in ? q >> 2 : 0, cc = in ? q & 3 : 0;
        float c = in ? m * scale[2] + base[l] : 0.0f;
        float v[16];
        auto gather = [&]() {
#pragma unroll
            for (int i = 0; i < 16; ++i) v[i] = sycl::select_from_group(sg, c, 8 + i);
        };
        auto pick = [](const float (&s)[4], int i) { return i == 0 ? s[0] : i == 1 ? s[1] : i == 2 ? s[2] : s[3]; };
        auto rowsums = [&](float (&s)[4]) {
#pragma unroll
            for (int r = 0; r < 4; ++r) {
                float sm = 0;
#pragma unroll
                for (int k = 0; k < 4; ++k) sm += v[4 * r + k];
                s[r] = sm;
            }
        };
        auto colsums = [&](float (&s)[4]) {
#pragma unroll
            for (int j0 = 0; j0 < 4; ++j0) {
                float sm = 0;
#pragma unroll
                for (int j = 0; j < 4; ++j) sm += v[j0 + 4 * j];
                s[j0] = sm;
            }
        };
        {
            gather();
            float mxs[4];
#pragma unroll
            for (int r = 0; r < 4; ++r) {
                float mx = v[4 * r];
#pragma unroll
                for (int k = 1; k < 4; ++k) { const float u = v[4 * r + k]; mx = u > mx ? u : mx; }
                mxs[r] = mx;
            }
            c = sycl::exp(c - pick(mxs, rr));
            gather();
            float s[4];
            rowsums(s);
            c = c / pick(s, rr) + eps;
        }
        for (int it2 = 0; it2 < 20; ++it2) {
            float s[4];
            if (it2 > 0) {
                gather();
                rowsums(s);
                c = c / (pick(s, rr) + eps);
            }
            gather();
            colsums(s);
            c = c / (pick(s, cc) + eps);
        }
        if (in) comb[q] = c;
    }
    [[gnu::always_inline]] inline void run0(sycl::sub_group sg, const double *d, const float *scale, const float *base,
                                            float *pre, float *post, float *comb) const {
        const int l = (int)sg.get_local_linear_id();
        const int N = 4 * h;
        double t = 0;
        if (l < 25)
            for (int k = 0; k < seg; ++k) t += d[l * seg + k];
        const double t24 = sycl::select_from_group(sg, t, 24);
        const float rsqrt = float(1.0 / sycl::sqrt(t24 / N + 1e-20));
        const float m = float(t) * rsqrt; // m24[l] for l < 24
        auto sig = [](float v) { return 1.0f / (1.0f + sycl::exp(-v)); };
        const float eps = 1e-6f;
        if (l < 4) pre[l] = sig(m * scale[0] + base[l]) + eps;
        else if (l < 8) post[l - 4] = 2.0f * sig(m * scale[1] + base[l]);
        const int q = l - 8;                         // comb index for lanes 8..23
        const int rb = 8 + 4 * ((q >= 0 && q < 16 ? q : 0) >> 2), cb = 8 + (q >= 0 && q < 16 ? q & 3 : 0);
        float c = (q >= 0 && q < 16) ? m * scale[2] + base[l] : 0.0f;
        auto row = [&](int k) { return sycl::select_from_group(sg, c, rb + k); };
        auto col = [&](int j) { return sycl::select_from_group(sg, c, cb + 4 * j); };
        {
            float mx = row(0);
            for (int k = 1; k < 4; ++k) { const float v = row(k); mx = v > mx ? v : mx; }
            c = sycl::exp(c - mx);
            float sm = 0;
            for (int k = 0; k < 4; ++k) sm += row(k);
            c = c / sm + eps;
        }
        for (int it2 = 0; it2 < 20; ++it2) {
            if (it2 > 0) {
                float sm = 0;
                for (int k = 0; k < 4; ++k) sm += row(k);
                c = c / (sm + eps);
            }
            float sm = 0;
            for (int j = 0; j < 4; ++j) sm += col(j);
            c = c / (sm + eps);
        }
        if (q >= 0 && q < 16) comb[q] = c;
    }
};

// The stream mix's results (pre/post/comb) are first read at the end of the
// sublayer (hc_post) or by the next sublayer's pre-norm, so its two launches
// can ride as extra sub-groups in matrix launches that follow: the 200 dot
// partials (HcDotsRows) in one, the one-sub-group finish (HcFinishRows) in a
// later one. Same per-sub-group code as HcMixDotsP / HcMixFinishSG.
template <unsigned H, unsigned SEG> struct HcDotsRows {
    const float *streams, *fn;
    double *out;
    unsigned n() const { return 25 * SEG; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r) const {
        HcMixDotsP<H, SEG>::row(sg, lane, r, streams, fn, out);
    }
};
// HcDotsRows for MT tokens (HcMixDotsP::rowm<MT>): token t's streams at streams + t * ss, its 25 * SEG
// partials at out + t * os; tokens t >= mt are not stored
template <unsigned H, unsigned SEG, unsigned MT, unsigned G = HcMixDotsP<H, SEG>::MTG> struct HcDotsRowsM {
    const float *streams;
    size_t ss;
    const float *fn;
    double *out;
    size_t os;
    unsigned mt;
    unsigned n() const { return 25 * SEG; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r) const {
        HcMixDotsP<H, SEG>::template rowm<MT, G>(sg, lane, r, streams, ss, fn, out, os, mt);
    }
};
struct HcFinishRows {
    HcMixFinishSG k;
    const double *d;
    const float *scale, *base;
    float *pre, *post, *comb;
    unsigned n() const { return 1; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned, unsigned) const {
        k.run(sg, d, scale, base, pre, post, comb);
    }
};
// RmsNormPS<N, S>'s S sub-group parts as rows
template <unsigned N, unsigned S> struct NormRows {
    const float *x, *w;
    float *y;
    bool ff = norm_ff_default(); // OWN_NORM_FF: the fast bracket (same values)
    unsigned n() const { return S; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r) const {
        RmsNormPS<N, S>::part(sg, lane, r, x, w, y, ff);
    }
};
// RopePairsA with rdim 64 (32 pairs = one sub-group per row) as rows; same expressions
template <typename A> struct RopeRows {
    typename A::T *x;
    const float *cosb, *sinb;
    unsigned rows, d;
    bool inverse;
    unsigned n() const { return rows; }
    [[gnu::always_inline]] inline void row(sycl::sub_group, unsigned lane, unsigned r) const {
        const unsigned i = lane;
        typename A::T *rw = x + (size_t)r * d + (d - 64);
        float re = A::rd(rw[2 * i]), im = A::rd(rw[2 * i + 1]);
        float c = cosb[i], s = inverse ? -sinb[i] : sinb[i];
        rw[2 * i] = A::wr(re * c - im * s);
        rw[2 * i + 1] = A::wr(re * s + im * c);
    }
};
// rows of R, one per sub-group (16 per 512-item work-group), in launch order
template <typename R> struct RowsP {
    R rows;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it) const {
        const unsigned r = packed_row_id(it);
        if (r >= rows.n()) return;
        sycl::sub_group sg = it.get_sub_group();
        rows.row(sg, sg.get_local_linear_id(), r);
    }
};

// SparseScoreA: work-group = one sub-group of 32 consecutive (head, idx)
// items (n_idx % 32 == 0, so the head is uniform); each lane reads its
// key row 8 bf16 at a time and the query uniformly; same serial j order.
template <unsigned HD> struct SparseScoreP {
    int n_idx, heads, win_rows, hd; // hd == HD, kept at run time: the scale is 1 / sqrt(float(hd)) on the card as before
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *q, const uint16_t *kvw, const uint16_t *kvc,
                                     const int32_t *idxs, float *score) const {
        run(it.get_sub_group(), (unsigned)it.get_group_linear_id(), q, kvw, kvc, idxs, score);
    }
    // work-group (= sub-group) grp of the launch (also the multi-token form, SparseAttnM)
    [[gnu::always_inline]] inline void run(sycl::sub_group sg, unsigned grp, const float *q, const uint16_t *kvw,
                                           const uint16_t *kvc, const int32_t *idxs, float *score) const {
        const size_t g = (size_t)grp * 32 + sg.get_local_linear_id();
        const int h = (int)((size_t)grp * 32 / n_idx), i = (int)(g % n_idx);
        if (h >= heads) return;
        const int slot = idxs[i];
        const int s0 = slot < 0 ? 0 : slot;
        const float scale = 1.0f / sycl::sqrt(float(hd));
        const float *qh = q + (size_t)h * HD;
        const uint16_t *k = s0 < win_rows ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - win_rows) * HD;
        const sycl::vec<uint16_t, 8> *k8 = reinterpret_cast<const sycl::vec<uint16_t, 8> *>(k);
        float acc = 0;
#pragma unroll 8
        for (unsigned j0 = 0; j0 < HD / 8; ++j0) {
            const sycl::vec<uint16_t, 8> kv = k8[j0];
#pragma unroll
            for (int m = 0; m < 8; ++m) acc += qh[8 * j0 + m] * ops41::bf16(kv[m]);
        }
        if (slot >= 0) score[g] = acc * scale;
    }
};

// SparseSoftmax: one sub-group per head, NI = n_idx (% 32 == 0). The max is
// order-free (any NaN is never selected either way; a +0/-0 tie gives the
// same exp arguments); the sum keeps the serial i order via broadcasts.
template <int NI> struct SparseSoftmaxP {
    int heads;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *sinks, const int32_t *idxs, float *score) const {
        run(it.get_sub_group(), (unsigned)it.get_group_linear_id(), sinks, idxs, score);
    }
    [[gnu::always_inline]] inline void run(sycl::sub_group sg, unsigned grp, const float *sinks, const int32_t *idxs,
                                           float *score) const {
        const int lane = (int)sg.get_local_linear_id();
        const int h = (int)grp;
        if (h >= heads) return;
        constexpr int K = NI / 32;
        float *s = score + (size_t)h * NI;
        float v[K];
        int ok[K];
        const float sk = sinks[h];
        float mx = sk;
#pragma unroll
        for (int k = 0; k < K; ++k) {
            ok[k] = idxs[32 * k + lane] >= 0 ? 1 : 0;
            v[k] = s[32 * k + lane];
            if (ok[k]) mx = v[k] > mx ? v[k] : mx;
        }
        for (int w_ = 16; w_; w_ >>= 1) {
            const float o = sycl::select_from_group(sg, mx, lane ^ w_);
            mx = o > mx ? o : mx;
        }
        // element order; a skipped slot adds +0, which leaves the sum (>= +0: exp terms) unchanged, so the
        // chain is one add per element instead of an add and a select
        float sum = sycl::exp(sk - mx);
        float e0[K];
#pragma unroll
        for (int k = 0; k < K; ++k) {
            if (ok[k]) v[k] = sycl::exp(v[k] - mx);
            e0[k] = ok[k] ? v[k] : 0.0f;
        }
#pragma unroll
        for (int k = 0; k < K; ++k)
#pragma unroll
            for (int l2 = 0; l2 < 32; ++l2) sum += sycl::select_from_group(sg, e0[k], l2);
#pragma unroll
        for (int k = 0; k < K; ++k)
            if (ok[k]) s[32 * k + lane] = v[k] / sum;
    }
};

// SparseSoftmaxP<NI> over the first n slots (n a multiple of 32, <= NI; a head's slots at stride n): the slots
// [n, NI) it leaves out are all skipped ones (index -1, OWN_ATT_TRIM), which take no part in the maximum and add
// +0 to the sum chain in SparseSoftmaxP, so every kept slot's weight is the same.
template <int NI> struct SparseSoftmaxPN {
    int heads, n;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *sinks, const int32_t *idxs, float *score) const {
        run(it.get_sub_group(), (unsigned)it.get_group_linear_id(), sinks, idxs, score);
    }
    [[gnu::always_inline]] inline void run(sycl::sub_group sg, unsigned grp, const float *sinks, const int32_t *idxs,
                                           float *score) const {
        const int lane = (int)sg.get_local_linear_id();
        const int h = (int)grp;
        if (h >= heads) return;
        constexpr int K = NI / 32;
        const int kn = n / 32;
        float *s = score + (size_t)h * n;
        float v[K];
        int ok[K];
        const float sk = sinks[h];
        float mx = sk;
#pragma unroll
        for (int k = 0; k < K; ++k) {
            ok[k] = 0;
            v[k] = 0;
            if (k < kn) {
                ok[k] = idxs[32 * k + lane] >= 0 ? 1 : 0;
                v[k] = s[32 * k + lane];
            }
            if (ok[k]) mx = v[k] > mx ? v[k] : mx;
        }
        for (int w_ = 16; w_; w_ >>= 1) {
            const float o = sycl::select_from_group(sg, mx, lane ^ w_);
            mx = o > mx ? o : mx;
        }
        float sum = sycl::exp(sk - mx);
        float e0[K];
#pragma unroll
        for (int k = 0; k < K; ++k) {
            if (ok[k]) v[k] = sycl::exp(v[k] - mx);
            e0[k] = ok[k] ? v[k] : 0.0f;
        }
#pragma unroll
        for (int k = 0; k < K; ++k)
            if (k < kn)
#pragma unroll
                for (int l2 = 0; l2 < 32; ++l2) sum += sycl::select_from_group(sg, e0[k], l2);
#pragma unroll
        for (int k = 0; k < K; ++k)
            if (ok[k]) s[32 * k + lane] = v[k] / sum;
    }
};

// SparseOut: same item mapping (h, j); 16 index rows fetched per round
template <unsigned HD> struct SparseOutP {
    int n_idx, heads, win_rows;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out) const {
        const size_t g = it.get_global_linear_id();
        const int h = (int)(g / HD), j = (int)(g % HD);
        if (h >= heads) return;
        const float *wh = w + (size_t)h * n_idx;
        float o = 0;
        for (int i0 = 0; i0 < n_idx; i0 += 16) {
            int sl[16];
            float kv[16], wv[16];
#pragma unroll
            for (int u = 0; u < 16; ++u) { sl[u] = idxs[i0 + u]; wv[u] = wh[i0 + u]; }
#pragma unroll
            for (int u = 0; u < 16; ++u) {
                const int s0 = sl[u] < 0 ? 0 : sl[u];
                const uint16_t *k = s0 < win_rows ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - win_rows) * HD;
                kv[u] = ops41::bf16(k[j]);
            }
#pragma unroll
            for (int u = 0; u < 16; ++u)
                if (sl[u] >= 0) o += wv[u] * kv[u];
        }
        out[g] = o;
    }
};

// SparseScoreA, head-grouped: one sub-group = 32 consecutive indices x HG
// heads; each lane reads its key row 32 values at a time (once for all HG
// heads), the queries for that j-chunk arrive one per lane and are broadcast.
// Per (head, index) the same serial j order and float operations.
template <unsigned HD, unsigned HG> struct SparseScoreHG {
    int n_idx, heads, win_rows, hd; // hd == HD at run time (scale as before)
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *q, const uint16_t *kvw, const uint16_t *kvc,
                                     const int32_t *idxs, float *score) const {
        run(it.get_sub_group(), (unsigned)it.get_group_linear_id(), q, kvw, kvc, idxs, score);
    }
    [[gnu::always_inline]] inline void run(sycl::sub_group sg, unsigned grp, const float *q, const uint16_t *kvw,
                                           const uint16_t *kvc, const int32_t *idxs, float *score) const {
        const unsigned lane = sg.get_local_linear_id();
        const unsigned nib = (unsigned)n_idx / 32;
        const unsigned h0 = (grp / nib) * HG, i = (grp % nib) * 32 + lane;
        if (h0 >= (unsigned)heads) return;
        const int slot = idxs[i];
        const int s0 = slot < 0 ? 0 : slot;
        const float scale = 1.0f / sycl::sqrt(float(hd));
        const uint16_t *k = s0 < win_rows ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - win_rows) * HD;
        const sycl::vec<uint16_t, 8> *k8 = reinterpret_cast<const sycl::vec<uint16_t, 8> *>(k);
        float acc[HG];
#pragma unroll
        for (unsigned hh = 0; hh < HG; ++hh) acc[hh] = 0;
        for (unsigned c = 0; c < HD / 32; ++c) {
            float qv[HG];
#pragma unroll
            for (unsigned hh = 0; hh < HG; ++hh) qv[hh] = q[(size_t)(h0 + hh) * HD + 32 * c + lane];
            sycl::vec<uint16_t, 8> kv[4];
#pragma unroll
            for (unsigned u = 0; u < 4; ++u) kv[u] = k8[4 * c + u];
#pragma unroll
            for (unsigned jj = 0; jj < 32; ++jj) {
                const float kf = ops41::bf16(kv[jj / 8][jj % 8]);
#pragma unroll
                for (unsigned hh = 0; hh < HG; ++hh) acc[hh] += sycl::select_from_group(sg, qv[hh], jj) * kf;
            }
        }
        if (slot >= 0)
#pragma unroll
            for (unsigned hh = 0; hh < HG; ++hh) score[(size_t)(h0 + hh) * n_idx + i] = acc[hh] * scale;
    }
};

// SparseOut, head-grouped: one sub-group = 32 consecutive j x HG heads; per
// index the key value is read once (coalesced) for all HG heads; weights and
// slots for 32 indices arrive one per lane and are broadcast. Per (head, j)
// the same serial index order and float operations.
template <unsigned HD, unsigned HG> struct SparseOutHG {
    int n_idx, heads, win_rows;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const unsigned grp = it.get_group_linear_id();
        const unsigned h0 = (grp / (HD / 32)) * HG, j = (grp % (HD / 32)) * 32 + lane;
        if (h0 >= (unsigned)heads) return;
        float o[HG];
#pragma unroll
        for (unsigned hh = 0; hh < HG; ++hh) o[hh] = 0;
        for (int i0 = 0; i0 < n_idx; i0 += 32) {
            const int sl = idxs[i0 + lane];
            float wv[HG];
#pragma unroll
            for (unsigned hh = 0; hh < HG; ++hh) wv[hh] = w[(size_t)(h0 + hh) * n_idx + i0 + lane];
#pragma unroll 8
            for (int u = 0; u < 32; ++u) {
                const int slot = sycl::select_from_group(sg, sl, u);
                if (slot < 0) continue;
                const uint16_t *k = slot < win_rows ? kvw + (size_t)slot * HD : kvc + (size_t)(slot - win_rows) * HD;
                const float kf = ops41::bf16(k[j]);
#pragma unroll
                for (unsigned hh = 0; hh < HG; ++hh) o[hh] += sycl::select_from_group(sg, wv[hh], u) * kf;
            }
        }
#pragma unroll
        for (unsigned hh = 0; hh < HG; ++hh) out[(size_t)(h0 + hh) * HD + j] = o[hh];
    }
};

// SparseOut: same item mapping (h, j). Per round of 32 indices the slots and
// weights arrive one per lane (one coalesced load each, next round's issued
// before this round's sums) and are broadcast from constant lanes; the 32
// key reads go out together. Same serial index order per (h, j).
template <unsigned HD> struct SparseOutP2 {
    int n_idx, heads, win_rows;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const size_t g = it.get_global_linear_id();
        const int h = (int)((size_t)it.get_group_linear_id() * 32 / HD), j = (int)(g % HD);
        if (h >= heads) return;
        const float *wh = w + (size_t)h * n_idx;
        float o = 0;
        int sl = idxs[lane];
        float wl = wh[lane];
        for (int i0 = 0; i0 < n_idx; i0 += 32) {
            const int sl_n = i0 + 32 < n_idx ? idxs[i0 + 32 + lane] : 0;
            const float wl_n = i0 + 32 < n_idx ? wh[i0 + 32 + lane] : 0.0f;
            float kv[32];
#pragma unroll
            for (int u = 0; u < 32; ++u) {
                const int slot = sycl::select_from_group(sg, sl, u);
                const int s0 = slot < 0 ? 0 : slot;
                const uint16_t *k = s0 < win_rows ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - win_rows) * HD;
                kv[u] = ops41::bf16(k[j]);
            }
#pragma unroll
            for (int u = 0; u < 32; ++u) {
                const int slot = sycl::select_from_group(sg, sl, u);
                const float wu = sycl::select_from_group(sg, wl, u);
                if (slot >= 0) o += wu * kv[u];
            }
            sl = sl_n;
            wl = wl_n;
        }
        out[g] = o;
    }
};

// SparseOutP2 with JP consecutive outputs per lane (one JP x bf16 load per
// index): the slot broadcast and row address are shared by JP outputs. Each
// output (h, j) still sums its products in serial index order.
template <unsigned HD, unsigned JP> struct SparseOutJ {
    static_assert(JP == 1 || JP == 2 || JP == 4 || JP == 8);
    int n_idx, heads, win_rows;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        constexpr unsigned SPAN = 32 * JP, PER_HEAD = HD / SPAN;
        const unsigned grp = it.get_group_linear_id();
        const int h = (int)(grp / PER_HEAD);
        const unsigned j0 = (grp % PER_HEAD) * SPAN + JP * lane;
        if (h >= heads) return;
        using V = sycl::vec<uint16_t, JP>;
        const float *wh = w + (size_t)h * n_idx;
        float o[JP];
#pragma unroll
        for (unsigned e = 0; e < JP; ++e) o[e] = 0;
        int sl = idxs[lane];
        float wl = wh[lane];
        for (int i0 = 0; i0 < n_idx; i0 += 32) {
            const int sl_n = i0 + 32 < n_idx ? idxs[i0 + 32 + lane] : 0;
            const float wl_n = i0 + 32 < n_idx ? wh[i0 + 32 + lane] : 0.0f;
#pragma unroll
            for (int u0 = 0; u0 < 32; u0 += 8) {
                V kv[8];
#pragma unroll
                for (int u = 0; u < 8; ++u) {
                    const int slot = sycl::select_from_group(sg, sl, u0 + u);
                    const int s0 = slot < 0 ? 0 : slot;
                    const uint16_t *k = s0 < win_rows ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - win_rows) * HD;
                    kv[u] = *reinterpret_cast<const V *>(k + j0);
                }
#pragma unroll
                for (int u = 0; u < 8; ++u) {
                    const int slot = sycl::select_from_group(sg, sl, u0 + u);
                    const float wu = sycl::select_from_group(sg, wl, u0 + u);
                    if (slot >= 0)
#pragma unroll
                        for (unsigned e = 0; e < JP; ++e) o[e] += wu * ops41::bf16(kv[u][e]);
                }
            }
            sl = sl_n;
            wl = wl_n;
        }
#pragma unroll
        for (unsigned e = 0; e < JP; ++e) out[(size_t)h * HD + j0 + e] = o[e];
    }
};

// SparseOutJ with the key loads software-pipelined: U loads per batch, the
// next batch's loads issued before this batch's sums (the next round's slots
// and weights at the round start). SparseOutJ waited for each batch of 8
// gathers in turn (~35 us at 640 indices, the add chain alone is ~6 us).
// Each output (h, j) still sums its products in serial index order; a masked
// slot (-1) still loads row 0 and adds nothing.
template <unsigned HD, unsigned JP, unsigned U> struct SparseOutJP {
    static_assert(JP == 1 || JP == 2 || JP == 4);
    static_assert(32 % U == 0);
    int n_idx, heads, win_rows;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        constexpr unsigned SPAN = 32 * JP, PER_HEAD = HD / SPAN, NBT = 32 / U;
        const unsigned grp = it.get_group_linear_id();
        const int h = (int)(grp / PER_HEAD);
        const unsigned j0 = (grp % PER_HEAD) * SPAN + JP * lane;
        if (h >= heads) return;
        using V = sycl::vec<uint16_t, JP>;
        const int wr = win_rows;
        auto ld = [&](int slot) {
            const int s0 = slot < 0 ? 0 : slot;
            const uint16_t *k = s0 < wr ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - wr) * HD;
            return *reinterpret_cast<const V *>(k + j0);
        };
        const float *wh = w + (size_t)h * n_idx;
        float o[JP];
#pragma unroll
        for (unsigned e = 0; e < JP; ++e) o[e] = 0;
        int sl = idxs[lane];
        float wl = wh[lane];
        V cur[U];
#pragma unroll
        for (unsigned u = 0; u < U; ++u) cur[u] = ld(sycl::select_from_group(sg, sl, u));
        for (int i0 = 0; i0 < n_idx; i0 += 32) {
            const bool more = i0 + 32 < n_idx;
            const int sl_n = more ? idxs[i0 + 32 + lane] : -1;
            const float wl_n = more ? wh[i0 + 32 + lane] : 0.0f;
#pragma unroll
            for (unsigned b = 0; b < NBT; ++b) {
                V nxt[U];
#pragma unroll
                for (unsigned u = 0; u < U; ++u)
                    nxt[u] = ld(b + 1 < NBT ? sycl::select_from_group(sg, sl, (b + 1) * U + u)
                                            : sycl::select_from_group(sg, sl_n, u));
#pragma unroll
                for (unsigned u = 0; u < U; ++u) {
                    const int slot = sycl::select_from_group(sg, sl, b * U + u);
                    const float wu = sycl::select_from_group(sg, wl, b * U + u);
                    if (slot >= 0)
#pragma unroll
                        for (unsigned e = 0; e < JP; ++e) o[e] += wu * ops41::bf16(cur[u][e]);
                }
#pragma unroll
                for (unsigned u = 0; u < U; ++u) cur[u] = nxt[u];
            }
            sl = sl_n;
            wl = wl_n;
        }
#pragma unroll
        for (unsigned e = 0; e < JP; ++e) out[(size_t)h * HD + j0 + e] = o[e];
    }
};

// SparseOutJ with the row addresses formed once per round: lane u computes the
// byte address of index i0 + u's row (window or compressed, masked -> row 0)
// and the per-index work is a broadcast plus the lane's column offset. The
// pipelined form (SparseOutJP) was no faster: the per-index address
// arithmetic, not load latency, was the cost. Same serial index order and
// float operations per output.
template <unsigned HD, unsigned JP> struct SparseOutJQ {
    static_assert(JP == 1 || JP == 2 || JP == 4 || JP == 8);
    int n_idx, heads, win_rows;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        constexpr unsigned SPAN = 32 * JP, PER_HEAD = HD / SPAN;
        const unsigned grp = it.get_group_linear_id();
        const int h = (int)(grp / PER_HEAD);
        const unsigned j0 = (grp % PER_HEAD) * SPAN + JP * lane;
        if (h >= heads) return;
        using V = sycl::vec<uint16_t, JP>;
        const float *wh = w + (size_t)h * n_idx;
        float o[JP];
#pragma unroll
        for (unsigned e = 0; e < JP; ++e) o[e] = 0;
        const int wr = win_rows;
        auto row_addr = [&](int slot) {
            const int s0 = slot < 0 ? 0 : slot;
            const uint16_t *k = s0 < wr ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - wr) * HD;
            return reinterpret_cast<uintptr_t>(k);
        };
        const uintptr_t coff = (uintptr_t)j0 * 2;
        for (int i0 = 0; i0 < n_idx; i0 += 32) {
            const int sl = idxs[i0 + lane];
            const float wl = wh[i0 + lane];
            const uintptr_t ra = row_addr(sl);
#pragma unroll
            for (int u0 = 0; u0 < 32; u0 += 8) {
                V kv[8];
#pragma unroll
                for (int u = 0; u < 8; ++u)
                    kv[u] = *reinterpret_cast<const V *>(sycl::select_from_group(sg, ra, u0 + u) + coff);
#pragma unroll
                for (int u = 0; u < 8; ++u) {
                    const int slot = sycl::select_from_group(sg, sl, u0 + u);
                    const float wu = sycl::select_from_group(sg, wl, u0 + u);
                    if (slot >= 0)
#pragma unroll
                        for (unsigned e = 0; e < JP; ++e) o[e] += wu * ops41::bf16(kv[u][e]);
                }
            }
        }
#pragma unroll
        for (unsigned e = 0; e < JP; ++e) out[(size_t)h * HD + j0 + e] = o[e];
    }
};

// SparseOutJQ with sub-group block reads: per index the row address is
// uniform (a scalar add, no per-lane 64-bit address) and one block read of NW
// dwords gives lane l the bf16 pairs at columns base + 64k + 2l + {0, 1}
// (dword k). An output's column is only a label for its lane: each output
// (h, j) still sums its products in serial index order with the same float
// operations (bf16 -> f32 is the same bit shift). Rows 16-byte aligned (HD %
// 8 == 0 and 16-byte aligned ring and cache: the backend checks).
template <unsigned HD, unsigned NW, unsigned U = 8, bool PIPE = false> struct SparseOutJB {
    static_assert(NW == 1 || NW == 2 || NW == 4);
    static_assert(32 % U == 0);
    static constexpr unsigned SPAN = 64 * NW, PER_HEAD = HD / SPAN, NBT = 32 / U;
    static_assert(HD % SPAN == 0);
    int n_idx, heads, win_rows;
    // ToActRopeA (f32, rdim 64, inverse) on the way out when ry is set: ry gets the head row with its last 64
    // dims rotated back (pair i = lane of the last span: same expressions), out keeps the plain row
    float *ry = nullptr;
    const float *cosb = nullptr, *sinb = nullptr;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out) const {
        run(it.get_sub_group(), (unsigned)it.get_group_linear_id(), kvw, kvc, idxs, w, out);
    }
    [[gnu::always_inline]] inline void run(sycl::sub_group sg, unsigned grp, const uint16_t *kvw, const uint16_t *kvc,
                                           const int32_t *idxs, const float *w, float *out) const {
        const unsigned lane = sg.get_local_linear_id();
        const int h = (int)(grp / PER_HEAD);
        const unsigned base = (grp % PER_HEAD) * SPAN;
        if (h >= heads) return;
        const float *wh = w + (size_t)h * n_idx;
        float o[2 * NW];
#pragma unroll
        for (unsigned e = 0; e < 2 * NW; ++e) o[e] = 0;
        const int wr = win_rows;
        auto row_addr = [&](int slot) {
            const int s0 = slot < 0 ? 0 : slot;
            const uint16_t *k = s0 < wr ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - wr) * HD;
            return reinterpret_cast<uintptr_t>(k + base);
        };
        using KV = sycl::vec<uint32_t, NW>;
        auto bl = [&](uintptr_t ra, unsigned u) {
            return sg_bloadN<NW>(sg, reinterpret_cast<const uint32_t *>(sycl::select_from_group(sg, ra, u)));
        };
        auto acc = [&](const KV &kv, int slot, float wu) {
            if (slot >= 0)
#pragma unroll
                for (unsigned k = 0; k < NW; ++k) {
                    o[2 * k] += wu * sycl::bit_cast<float>(kv[k] << 16);
                    o[2 * k + 1] += wu * sycl::bit_cast<float>(kv[k] & 0xFFFF0000u);
                }
        };
        if constexpr (!PIPE) {
            for (int i0 = 0; i0 < n_idx; i0 += 32) {
                const int sl = idxs[i0 + lane];
                const float wl = wh[i0 + lane];
                const uintptr_t ra = row_addr(sl);
#pragma unroll
                for (unsigned u0 = 0; u0 < 32; u0 += U) {
                    KV kv[U];
#pragma unroll
                    for (unsigned u = 0; u < U; ++u) kv[u] = bl(ra, u0 + u);
#pragma unroll
                    for (unsigned u = 0; u < U; ++u)
                        acc(kv[u], sycl::select_from_group(sg, sl, u0 + u), sycl::select_from_group(sg, wl, u0 + u));
                }
            }
        } else {
            // next batch's block reads issued before this batch's sums; the next
            // round's slots / weights / addresses at the round start
            int sl = idxs[lane];
            float wl = wh[lane];
            uintptr_t ra = row_addr(sl);
            KV cur[U];
#pragma unroll
            for (unsigned u = 0; u < U; ++u) cur[u] = bl(ra, u);
            for (int i0 = 0; i0 < n_idx; i0 += 32) {
                const bool more = i0 + 32 < n_idx;
                const int sl_n = more ? idxs[i0 + 32 + lane] : -1;
                const float wl_n = more ? wh[i0 + 32 + lane] : 0.0f;
                const uintptr_t ra_n = row_addr(sl_n);
#pragma unroll
                for (unsigned b = 0; b < NBT; ++b) {
                    KV nxt[U];
#pragma unroll
                    for (unsigned u = 0; u < U; ++u) nxt[u] = b + 1 < NBT ? bl(ra, (b + 1) * U + u) : bl(ra_n, u);
#pragma unroll
                    for (unsigned u = 0; u < U; ++u)
                        acc(cur[u], sycl::select_from_group(sg, sl, b * U + u), sycl::select_from_group(sg, wl, b * U + u));
#pragma unroll
                    for (unsigned u = 0; u < U; ++u) cur[u] = nxt[u];
                }
                sl = sl_n;
                wl = wl_n;
                ra = ra_n;
            }
        }
        float *oh = out + (size_t)h * HD + base;
#pragma unroll
        for (unsigned k = 0; k < NW; ++k) {
            oh[64 * k + 2 * lane] = o[2 * k];
            oh[64 * k + 2 * lane + 1] = o[2 * k + 1];
        }
        if (ry) {
            float *yh = ry + (size_t)h * HD + base;
#pragma unroll
            for (unsigned k = 0; k < NW; ++k) {
                float a0 = o[2 * k], a1 = o[2 * k + 1];
                if (base + 64 * k == HD - 64) {
                    const float re = a0, im = a1, cs = cosb[lane], sn = -sinb[lane];
                    a0 = re * cs - im * sn;
                    a1 = re * sn + im * cs;
                }
                yh[64 * k + 2 * lane] = a0;
                yh[64 * k + 2 * lane + 1] = a1;
            }
        }
    }
};

// SparseOutJB<HD, 1, U>'s sums from local memory, one column per lane (OWN_ATT_OUT_C). Work-group = HG sub-groups of
// 32 = heads hg * HG .. + HG - 1 of one 32-column span (group = hg * (HD / 32) + span). The list goes chunk by
// chunk (CH slots): the work-group's sub-groups load the chunk's 64-byte row pieces (sub-group g the pieces
// g * CH / HG .., all issued before any is waited for) into local memory as f32 (bf16 << 16: the same values), the
// next chunk's loads issued before this one is summed; sub-group g then sums head hg * HG + g over the chunk in slot
// order, lane l column base + l. A skipped slot (< 0) adds -0.0f instead of being branched around: x + -0 == x for
// every float, +0 and -0 included, so each output is SparseOutJB's (the slot's product, from row 0 and whatever
// weight the softmax left there, is formed and dropped). The rope epilogue's pairs (2i, 2i + 1) are lanes
// (2m, 2m + 1), the partner's value by a shuffle, the same expressions. n_idx % 32 == 0; rows 16-byte aligned.
// Round 18 s1-s4 (tools/bench/bench_sparse_out.cpp, one card): 21.8-22.9 -> 11.9-12.8 us at 640 slots (8 or 16
// heads), 6.0 -> 4.0-4.5 at 160, 4.8-5.1 -> 2.7-3.6 at 128, out and ry bitwise equal. Without the local memory the
// added -0.0f alone gains nothing; 16-lane sub-groups, 4 or 8 heads per work-group, more loads in flight: slower.
template <unsigned HD, unsigned HG_, unsigned CH, unsigned U = 16> struct SparseOutJC {
    static constexpr unsigned HG = HG_, PER_HEAD = HD / 32, LP = CH / HG, NK = CH / 32;
    static constexpr size_t SLM = 2 * (size_t)CH * 32, WG = 32 * (size_t)HG; // 32-bit words: two chunk buffers
    static_assert(HD % 32 == 0 && CH % 32 == 0 && CH % HG == 0 && LP >= 1 && LP <= 32 && 32 % U == 0);
    int n_idx, heads, win_rows;
    // ToActRopeA (f32, rdim 64, inverse) on the way out when ry is set, as SparseOutJB
    float *ry = nullptr;
    const float *cosb = nullptr, *sinb = nullptr;
    static size_t groups(int heads) { return (size_t)PER_HEAD * (size_t)((heads + (int)HG - 1) / (int)HG); }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out, uint32_t *lm) const {
        run(it, (unsigned)it.get_group_linear_id(), kvw, kvc, idxs, w, out, lm);
    }
    [[gnu::always_inline]] inline void run(sycl::nd_item<1> it, unsigned grp, const uint16_t *kvw, const uint16_t *kvc,
                                           const int32_t *idxs, const float *w, float *out, uint32_t *lm) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), g = sg.get_group_linear_id();
        const unsigned base = (grp % PER_HEAD) * 32;
        const int h = (int)((grp / PER_HEAD) * HG + g);
        const bool act = h < heads;
        const int n = n_idx, wr = win_rows, nch = (n + (int)CH - 1) / (int)CH;
        const float *wh = w + (size_t)(act ? h : 0) * n;
        auto row_addr = [&](int slot) {
            const int s0 = slot < 0 ? 0 : slot;
            return (s0 < wr ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - wr) * HD) + base;
        };
        // loader slots of chunk c: lane u < LP holds slot c * CH + g * LP + u
        auto lslots = [&](int c) {
            const int i = c * (int)CH + (int)(g * LP + lane);
            return lane < LP && i < n ? idxs[i] : -1;
        };
        uint16_t pc[LP];
        auto issue = [&](int c, int ls) {
#pragma unroll
            for (unsigned u = 0; u < LP; ++u)
                if (c * (int)CH + (int)(g * LP + u) < n) pc[u] = sg_bloadN<1>(sg, row_addr(sycl::select_from_group(sg, ls, u)))[0];
        };
        auto put = [&](int c) {
            uint32_t *b = lm + (size_t)(c & 1) * CH * 32;
#pragma unroll
            for (unsigned u = 0; u < LP; ++u)
                if (c * (int)CH + (int)(g * LP + u) < n) b[(g * LP + u) * 32 + lane] = (uint32_t)pc[u] << 16;
        };
        // this head's slots and weights of chunk c (lane l of k: slot c * CH + 32 k + l)
        int csl[NK], nsl[NK];
        float cwl[NK], nwl[NK];
        auto lw = [&](int c, int (&s)[NK], float (&x)[NK]) {
#pragma unroll
            for (unsigned k = 0; k < NK; ++k) {
                const int i = c * (int)CH + (int)(32 * k + lane);
                const bool in = c * (int)CH + (int)(32 * k) < n;
                s[k] = in ? idxs[i] : -1;
                x[k] = in ? wh[i] : 0.0f;
            }
        };
        float o = 0;
        int ls = lslots(0);
        issue(0, ls);
        lw(0, csl, cwl);
        if (nch > 1) ls = lslots(1);
        put(0);
        sycl::group_barrier(it.get_group());
        for (int c = 0; c < nch; ++c) {
            const bool more = c + 1 < nch;
            if (more) {
                issue(c + 1, ls);
                lw(c + 1, nsl, nwl);
                if (c + 2 < nch) ls = lslots(c + 2);
            }
            if (act) {
                const uint32_t *b = lm + (size_t)(c & 1) * CH * 32;
#pragma unroll
                for (unsigned k = 0; k < NK; ++k) {
                    if (c * (int)CH + (int)(32 * k) >= n) break;
#pragma unroll
                    for (unsigned u0 = 0; u0 < 32; u0 += U) {
                        uint32_t x[U];
#pragma unroll
                        for (unsigned u = 0; u < U; ++u) x[u] = b[(32 * k + u0 + u) * 32 + lane];
#pragma unroll
                        for (unsigned u = 0; u < U; ++u) {
                            const bool ok = sycl::select_from_group(sg, csl[k], u0 + u) >= 0;
                            const float p0 = sycl::select_from_group(sg, cwl[k], u0 + u) * sycl::bit_cast<float>(x[u]);
                            o += ok ? p0 : -0.0f;
                        }
                    }
                }
            }
            if (more) {
                put(c + 1);
#pragma unroll
                for (unsigned k = 0; k < NK; ++k) {
                    csl[k] = nsl[k];
                    cwl[k] = nwl[k];
                }
            }
            sycl::group_barrier(it.get_group());
        }
        const float pr = sycl::select_from_group(sg, o, lane ^ 1u);
        if (!act) return;
        out[(size_t)h * HD + base + lane] = o;
        if (ry) {
            float a = o;
            if (base >= HD - 64) {
                const unsigned i = (base - (HD - 64) + lane) / 2;
                const float cs = cosb[i], sn = -sinb[i];
                if (lane & 1) {
                    const float re = pr, im = o;
                    a = re * sn + im * cs;
                } else {
                    const float re = o, im = pr;
                    a = re * cs - im * sn;
                }
            }
            ry[(size_t)h * HD + base + lane] = a;
        }
    }
};

// EngramGateA on 4 sub-groups (row j = group): lanes load 32 elements at a
// time and form the double products; the three sums run serially in element
// order on every lane from broadcast products (the same adds in the same
// order as the one-work-item loops); the final update is elementwise.
// OWN_ENG_FF (host, read when the gate kernel is built; round 18 eg1-, tools/bench/bench_engram_ff.cpp): the
// three serial double chains (hsq, ksq, dot: h - 1 dependent adds each, ~116 us per launch at h = 5,120) are
// bracketed instead of replayed. Every term is formed exactly as the chain forms it; the fast sums add them per
// lane in four interleaved accumulators (h / 128 terms each), the accumulators in pairs, then the lanes by an xor
// tree: every leaf-to-root path has at most h / 128 + 7 adds, so with A = the sum of |terms| (no term can overflow
// or be subnormal: products of two or three floats in double) |fast - exact| <= gamma(h/128 + 7) A and
// |chain - exact| <= gamma(h - 1) A, and |chain - fast| < (h + 64) * 1.2e-16 * A_fast (A_fast the fast sum of
// |terms|, >= (1 - gamma) A). rstd is a composition of correctly rounded monotone operations, non-increasing in
// hsq and ksq: when the two corners of the bracket give the same float bits, so does the chain; float(dot) the
// same with dot's bracket. Otherwise (or any sum not finite, or h % 128 != 0) the chains run as before. The tail
// (d, g, the stream update) is the same code on the same values.
inline bool g_eng_ff = true;
inline bool eng_ff_default() {
#ifdef __SYCL_DEVICE_ONLY__
    return false;
#else
    return g_eng_ff;
#endif
}
struct EngramGateP {
    int h; // % 32 == 0
    bool ff = eng_ff_default();
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, float *streams, const float *kvbuf, const float *gate_w) const {
        sycl::sub_group sg = it.get_sub_group();
        const int j = (int)it.get_group_linear_id();
        if (j >= 4) return;
        run(sg, (int)sg.get_local_linear_id(), j, streams, kvbuf, gate_w);
    }
    static inline float rstd_of(double hsq, double ksq, int h, float eps) {
        return float(1.0 / sycl::sqrt(hsq / h + eps) * (1.0 / sycl::sqrt(ksq / h + eps)));
    }
    // the bracket; true when rstd and float(dot) are proven equal to the chains'
    [[gnu::always_inline]] inline bool fast(sycl::sub_group sg, int lane, const float *sr, const float *kr,
                                            const float *gr, float eps, float &rstd, float &fd) const {
        double ah[4] = {0, 0, 0, 0}, ak[4] = {0, 0, 0, 0}, ad[4] = {0, 0, 0, 0}, aa[4] = {0, 0, 0, 0};
        for (int i0 = 0; i0 < h; i0 += 128) {
#pragma unroll
            for (int u = 0; u < 4; ++u) {
                const int ix = i0 + 32 * u + lane;
                const float hv = sr[ix], kvv = kr[ix], gw = gr[ix];
                const double ph = double(hv) * hv, pk = double(kvv) * kvv, pd = double(hv) * gw * kvv;
                ah[u] += ph;
                ak[u] += pk;
                ad[u] += pd;
                aa[u] += sycl::fabs(pd);
            }
        }
        double sh = (ah[0] + ah[1]) + (ah[2] + ah[3]), sk = (ak[0] + ak[1]) + (ak[2] + ak[3]);
        double sd = (ad[0] + ad[1]) + (ad[2] + ad[3]), sa = (aa[0] + aa[1]) + (aa[2] + aa[3]);
#pragma unroll
        for (int w = 16; w; w >>= 1) { // commutative adds: every lane ends with the same sums
            sh += sycl::select_from_group(sg, sh, lane ^ w);
            sk += sycl::select_from_group(sg, sk, lane ^ w);
            sd += sycl::select_from_group(sg, sd, lane ^ w);
            sa += sycl::select_from_group(sg, sa, lane ^ w);
        }
        bool ok = sycl::isfinite(sh) && sycl::isfinite(sk) && sycl::isfinite(sd) && sycl::isfinite(sa);
        if (ok) {
            const double c = (double(h) + 64.0) * 1.2e-16;
            const double wh = c * sh, wk = c * sk, wd = c * sa;
            const float r0 = rstd_of(sh + wh, sk + wk, h, eps), r1 = rstd_of(sycl::fmax(sh - wh, 0.0), sycl::fmax(sk - wk, 0.0), h, eps);
            const float d0 = float(sd - wd), d1 = float(sd + wd);
            ok = sycl::bit_cast<uint32_t>(r0) == sycl::bit_cast<uint32_t>(r1) &&
                 sycl::bit_cast<uint32_t>(d0) == sycl::bit_cast<uint32_t>(d1);
            rstd = r0;
            fd = d0;
        }
        return sycl::select_from_group(sg, ok ? 1 : 0, 0) != 0;
    }
    // stream j on one sub-group (also the multi-token form, EngramGatePM)
    [[gnu::always_inline]] inline void run(sycl::sub_group sg, int lane, int j, float *streams, const float *kvbuf,
                                           const float *gate_w) const {
        const float eps = 1e-20f, clamp_v = 1e-6f;
        const float *sr = streams + (size_t)j * h, *kr = kvbuf + (size_t)j * h, *gr = gate_w + (size_t)j * h;
        float rstd = 0, fd = 0;
        if (!(ff && h % 128 == 0 && fast(sg, lane, sr, kr, gr, eps, rstd, fd))) {
            double hsq = 0, ksq = 0, dot = 0;
            for (int i0 = 0; i0 < h; i0 += 32) {
                const float hv = sr[i0 + lane], kvv = kr[i0 + lane], gw = gr[i0 + lane];
                const double ph = double(hv) * hv, pk = double(kvv) * kvv, pd = double(hv) * gw * kvv;
#pragma unroll
                for (int l2 = 0; l2 < 32; ++l2) {
                    hsq += sycl::select_from_group(sg, ph, l2);
                    ksq += sycl::select_from_group(sg, pk, l2);
                }
#pragma unroll
                for (int l2 = 0; l2 < 32; ++l2) dot += sycl::select_from_group(sg, pd, l2);
            }
            rstd = rstd_of(hsq, ksq, h, eps);
            fd = float(dot);
        }
        const float d = fd * rstd / sycl::sqrt(float(h));
        const float g = 1.0f / (1.0f + sycl::exp(-sycl::copysign(sycl::sqrt(sycl::fmax(sycl::fabs(d), clamp_v)), d)));
        float *so = streams + (size_t)j * h;
        const float *vr = kvbuf + (size_t)4 * h;
        for (int i = lane; i < h; i += 32) so[i] = so[i] + g * vr[i];
    }
    // stream j on a work-group of S sub-groups (EngramGateW / EngramGateWM): the bracket's sums split over the
    // sub-groups (element t * 32 S + 32 sgi + lane; h / (32 S) terms per lane, one accumulator each, then the xor
    // tree, then the S partial sums in a fixed pairwise tree from local memory: every path <= h / (32 S) + 9 adds,
    // within fast()'s bound when h / (32 S) <= 48); when the bracket cannot decide, sub-group 0 runs the chains
    // and hands rstd and float(dot) over in local memory. Then d, g and the update as run(), spread over the
    // work-group. lm: 8 S + 2 words.
    template <unsigned S>
    [[gnu::always_inline]] inline void run_wg(sycl::nd_item<1> it, int j, float *streams, const float *kvbuf,
                                              const float *gate_w, uint32_t *lm) const {
        static_assert(S == 4 || S == 8 || S == 16, "S: 4, 8 or 16 sub-groups");
        sycl::sub_group sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
        const float eps = 1e-20f, clamp_v = 1e-6f;
        const float *sr = streams + (size_t)j * h, *kr = kvbuf + (size_t)j * h, *gr = gate_w + (size_t)j * h;
        const int per = h / (32 * (int)S);
        const bool try_ff = ff && h % (32 * (int)S) == 0 && per <= 48;
        auto put = [&](int w, double v) {
            const uint64_t b = sycl::bit_cast<uint64_t>(v);
            lm[2 * w] = (uint32_t)b;
            lm[2 * w + 1] = (uint32_t)(b >> 32);
        };
        auto get = [&](int w) { return sycl::bit_cast<double>((uint64_t)lm[2 * w] | ((uint64_t)lm[2 * w + 1] << 32)); };
        if (try_ff) {
            double sh = 0, sk = 0, sd = 0, sa = 0;
            for (int t = 0; t < per; ++t) {
                const int ix = t * 32 * (int)S + 32 * sgi + lane;
                const float hv = sr[ix], kvv = kr[ix], gw = gr[ix];
                const double ph = double(hv) * hv, pk = double(kvv) * kvv, pd = double(hv) * gw * kvv;
                sh += ph;
                sk += pk;
                sd += pd;
                sa += sycl::fabs(pd);
            }
#pragma unroll
            for (int w = 16; w; w >>= 1) {
                sh += sycl::select_from_group(sg, sh, lane ^ w);
                sk += sycl::select_from_group(sg, sk, lane ^ w);
                sd += sycl::select_from_group(sg, sd, lane ^ w);
                sa += sycl::select_from_group(sg, sa, lane ^ w);
            }
            if (lane == 0) {
                put(4 * sgi, sh);
                put(4 * sgi + 1, sk);
                put(4 * sgi + 2, sd);
                put(4 * sgi + 3, sa);
            }
        }
        sycl::group_barrier(it.get_group());
        float rstd = 0, fd = 0;
        bool ok = false;
        if (try_ff) {
            // lane l: sum q = l & 3 of sub-groups l >> 2 (and (l >> 2) + 8 when S == 16), then xor levels 4, 8, 16:
            // a fixed pairwise tree of depth log2(S) (+0.0 for missing sub-groups: no partial sum is -0.0)
            const int q = lane & 3, s0 = lane >> 2;
            double a = s0 < (int)S ? get(4 * s0 + q) : 0.0;
            if constexpr (S == 16) a = a + get(4 * (s0 + 8) + q);
#pragma unroll
            for (int w = 4; w <= 16; w *= 2) a += sycl::select_from_group(sg, a, lane ^ w);
            const double sh = sycl::select_from_group(sg, a, 0), sk = sycl::select_from_group(sg, a, 1),
                         sd = sycl::select_from_group(sg, a, 2), sa = sycl::select_from_group(sg, a, 3);
            ok = sycl::isfinite(sh) && sycl::isfinite(sk) && sycl::isfinite(sd) && sycl::isfinite(sa);
            if (ok) {
                const double c = (double(h) + 64.0) * 1.2e-16;
                const double wh = c * sh, wk = c * sk, wd = c * sa;
                const float r0 = rstd_of(sh + wh, sk + wk, h, eps),
                            r1 = rstd_of(sycl::fmax(sh - wh, 0.0), sycl::fmax(sk - wk, 0.0), h, eps);
                const float d0 = float(sd - wd), d1 = float(sd + wd);
                ok = sycl::bit_cast<uint32_t>(r0) == sycl::bit_cast<uint32_t>(r1) &&
                     sycl::bit_cast<uint32_t>(d0) == sycl::bit_cast<uint32_t>(d1);
                rstd = r0;
                fd = d0;
            }
        }
        // every lane holds the same sums, so the same verdict; the barrier below is unconditional
        if (!ok && sgi == 0) {
            double hsq = 0, ksq = 0, dot = 0;
            for (int i0 = 0; i0 < h; i0 += 32) {
                const float hv = sr[i0 + lane], kvv = kr[i0 + lane], gw = gr[i0 + lane];
                const double ph = double(hv) * hv, pk = double(kvv) * kvv, pd = double(hv) * gw * kvv;
#pragma unroll
                for (int l2 = 0; l2 < 32; ++l2) {
                    hsq += sycl::select_from_group(sg, ph, l2);
                    ksq += sycl::select_from_group(sg, pk, l2);
                }
#pragma unroll
                for (int l2 = 0; l2 < 32; ++l2) dot += sycl::select_from_group(sg, pd, l2);
            }
            if (lane == 0) {
                lm[8 * S] = sycl::bit_cast<uint32_t>(rstd_of(hsq, ksq, h, eps));
                lm[8 * S + 1] = sycl::bit_cast<uint32_t>(float(dot));
            }
        }
        sycl::group_barrier(it.get_group());
        if (!ok) {
            rstd = sycl::bit_cast<float>(lm[8 * S]);
            fd = sycl::bit_cast<float>(lm[8 * S + 1]);
        }
        const float d = fd * rstd / sycl::sqrt(float(h));
        const float g = 1.0f / (1.0f + sycl::exp(-sycl::copysign(sycl::sqrt(sycl::fmax(sycl::fabs(d), clamp_v)), d)));
        float *so = streams + (size_t)j * h;
        const float *vr = kvbuf + (size_t)4 * h;
        for (int i = 32 * sgi + lane; i < h; i += 32 * (int)S) so[i] = so[i] + g * vr[i];
    }
};
// EngramGateP's four streams on four work-groups of S sub-groups (run_wg; launch_wgl with 8 S + 2 words)
template <unsigned S> struct EngramGateW {
    EngramGateP k;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, float *streams, const float *kvbuf, const float *gate_w,
                                     uint32_t *lm) const {
        const int j = (int)it.get_group_linear_id();
        if (j >= 4) return;
        k.run_wg<S>(it, j, streams, kvbuf, gate_w, lm);
    }
};

// Argmax with Argmax's result (the smallest index among the elements equal
// to the largest non-NaN value; n when there is none), which does not depend
// on the scan order: pass 1, G sub-groups over contiguous spans (CH per
// sub-group); pass 2, one sub-group over the G candidates.
struct ArgmaxP1 {
    int n, ch;
    void operator()(sycl::nd_item<1> it, const float *logits, float *bvs, int32_t *bis) const {
        sycl::sub_group sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id();
        const int gi = (int)it.get_group_linear_id();
        const int i0 = gi * ch, i1 = sycl::min(n, i0 + ch);
        float bv = -INFINITY;
        int bi = n;
        for (int i = i0 + lane; i < i1; i += 32) {
            const float v = logits[i];
            if (v > bv) { bv = v; bi = i; }
        }
        for (int w = 16; w; w >>= 1) {
            const float ov = sycl::select_from_group(sg, bv, lane ^ w);
            const int oi = sycl::select_from_group(sg, bi, lane ^ w);
            if (ov > bv || (ov == bv && oi < bi)) { bv = ov; bi = oi; }
        }
        if (lane == 0) { bvs[gi] = bv; bis[gi] = bi; }
    }
};
struct ArgmaxP2 {
    int groups;
    void operator()(sycl::nd_item<1> it, const float *bvs, const int32_t *bis, int32_t *out) const {
        sycl::sub_group sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id();
        float bv = -INFINITY;
        int bi = 0x7fffffff;
        for (int k = lane; k < groups; k += 32) {
            const float ov = bvs[k];
            const int oi = bis[k];
            if (ov > bv || (ov == bv && oi < bi)) { bv = ov; bi = oi; }
        }
        for (int w = 16; w; w >>= 1) {
            const float ov = sycl::select_from_group(sg, bv, lane ^ w);
            const int oi = sycl::select_from_group(sg, bi, lane ^ w);
            if (ov > bv || (ov == bv && oi < bi)) { bv = ov; bi = oi; }
        }
        if (lane == 0) *out = bi;
    }
};

// WindowAppendA spread over work-items (it ran on ONE item, ~42 us per layer),
// and the attention's index list built in the same launch (it was two queue
// copies): cat[0, win) = the window indices, cat[win, win + nc) = cidx.
// Pure stores of the same values. Launch max(d, win, nc) items.
template <typename A> struct WindowAppendP {
    int win, d, start_pos, nc;
    void operator()(sycl::nd_item<1> it, uint16_t *ring, const typename A::T *kv, int32_t *widx, int32_t *cat,
                    const int32_t *cidx) const {
        const int i = (int)it.get_global_linear_id();
        if (i < d) ring[(size_t)(start_pos % win) * d + i] = ops41::bf16b(A::rd(kv[i]));
        if (i < win) {
            const int j = ((start_pos % win + 1) % win + i) % win; // WindowAppendA's j after i steps
            const int32_t v = j > start_pos ? -1 : j;
            widx[i] = v;
            cat[i] = v;
        }
        if (i < nc) cat[win + i] = cidx[i];
    }
};

// RouteScore + RouteRank + RouteNorm in one work-group of >= experts items
// (one launch instead of three; the rank loop reads local memory instead of
// 256 global loads per item). Same expressions, same comparisons, same sum
// order. lm: local memory, 2 * experts + topk floats.
// OWN_ROUTE_Q (host, read when a router kernel is built; round 18 rt1-rt5, tools/bench/bench_route_rows.cpp): RouteP's
// picks in two stages (run_two below), the same ids and probabilities for every input without NaN scores (36,864
// bench sets: random, ties, +-inf, signed zeros); with NaN scores RouteP's rank writes collide and race (RouteP
// against itself: 265 of 4,096 sets differ), so both forms leave that case undefined. The pick 21.5 -> 8.8 us, the
// router launch with the shared rows 23.3 -> 11.7 us.
inline bool g_route_q = true;
inline bool route_q_default() {
#ifdef __SYCL_DEVICE_ONLY__
    return false;
#else
    return g_route_q;
#endif
}
struct RouteP {
    int experts, topk;
    bool two = route_q_default();
    // Two stages. Order: a before b when a > b, or a == b and a's index is lower (a strict total order on non-NaN
    // floats). Stage 1: each lane's rank among its sub-group's 32 scores (broadcasts); the topk best of every
    // sub-group are the candidates (a slot each in local memory). Stage 2: each candidate's rank among the
    // candidates (loaded 32 at a time, broadcast). Every element that comes before a global top-k element is itself
    // global top-k, so it is a candidate: a top-k element's rank among the candidates is its global rank; any other
    // element has the k global best before it, all candidates, so its candidate rank is >= k too. A NaN score in any
    // sub-group: RouteP's loop (below). Needs experts % 32 == 0, experts <= 512, a work-group of >= experts items,
    // topk * experts / 32 <= 96 and 1,248 floats of local memory (RouteP's 2 * 512 + 6, then candidates and flags).
    // NC: the candidate count when known at compile time (0: experts / 32 * topk at run time). The order tests are
    // written without short-circuit branches ((w > v) | ((w == v) & (wi < i)), the same truth value): round 18
    // rp1-rp3 (tools/bench/bench_route_pick.cpp), the pick 8.5 -> 2.7 us with NC = 72 (384 experts, top 6).
    template <int NC = 0>
    [[gnu::always_inline]] inline void run_two(sycl::nd_item<1> it, const float *logits, const float *bias,
                                               uint32_t *ids, float *prob, float *lm) const {
        float *lsb = lm + experts, *lp = lm + 2 * experts;
        float *cv = lm + 1040;
        int *ci = reinterpret_cast<int *>(lm + 1136);
        int *nanf = reinterpret_cast<int *>(lm + 1232);
        const int i = (int)it.get_local_linear_id();
        sycl::sub_group sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
        const bool live = sgi * 32 < experts;
        if (i < topk) lp[i] = prob[i]; // RouteNorm reads what is there for a rank nobody took (NaN scores)
        float v = 0, s0 = 0;
        if (live) {
            s0 = sycl::sqrt(sycl::log1p(sycl::exp(logits[i])));
            v = s0 + bias[i];
            lsb[i] = v;
        }
        int r1 = 0;
        if (live) {
#pragma unroll
            for (int k = 0; k < 32; ++k) {
                const float w = sycl::select_from_group(sg, v, k);
                r1 += (int)(w > v) | ((int)(w == v) & (int)(k < lane));
            }
        }
        const bool anynan = live && sycl::any_of_group(sg, sycl::isnan(v));
        if (lane == 0) nanf[sgi] = anynan ? 1 : 0;
        const bool cand = live && r1 < topk;
        if (cand) {
            cv[sgi * topk + r1] = v;
            ci[sgi * topk + r1] = i;
        }
        sycl::group_barrier(it.get_group());
        int nan_any = 0;
        for (int k = 0; k < (int)(it.get_local_range(0) / 32); ++k) nan_any |= nanf[k];
        if (live) {
            int rank = 0;
            if (nan_any) {
                for (int jb = 0; jb < experts; jb += 32) {
                    const float u = lsb[jb + lane];
#pragma unroll
                    for (int k = 0; k < 32; ++k) {
                        const float w = sycl::select_from_group(sg, u, k);
                        rank += (w > v || (w == v && jb + k < i)) ? 1 : 0;
                    }
                }
            } else if constexpr (NC > 0) {
#pragma unroll
                for (int jb = 0; jb < NC; jb += 32) {
                    const bool in = jb + lane < NC;
                    const float u = in ? cv[jb + lane] : 0.0f;
                    const int ui = in ? ci[jb + lane] : 0;
#pragma unroll
                    for (int k = 0; k < 32; ++k) {
                        if (jb + k >= NC) break;
                        const float w = sycl::select_from_group(sg, u, k);
                        const int wi = sycl::select_from_group(sg, ui, k);
                        rank += (int)(w > v) | ((int)(w == v) & (int)(wi < i));
                    }
                }
            } else {
                const int nc = experts / 32 * topk;
                for (int jb = 0; jb < nc; jb += 32) {
                    const bool in = jb + lane < nc;
                    const float u = in ? cv[jb + lane] : 0.0f;
                    const int ui = in ? ci[jb + lane] : 0;
#pragma unroll
                    for (int k = 0; k < 32; ++k) {
                        const float w = sycl::select_from_group(sg, u, k);
                        const int wi = sycl::select_from_group(sg, ui, k);
                        rank += (int)(jb + k < nc) & ((int)(w > v) | ((int)(w == v) & (int)(wi < i)));
                    }
                }
            }
            if ((nan_any || cand) && rank < topk) {
                ids[rank] = (uint32_t)i;
                lp[rank] = s0;
            }
        }
        sycl::group_barrier(it.get_group());
        if (i < topk) {
            float sum = 0;
            for (int t = 0; t < topk; ++t) sum += lp[t];
            prob[i] = lp[i] / (sum + 1e-20f) * 1.5f;
        }
    }
    void operator()(sycl::nd_item<1> it, const float *logits, const float *bias, uint32_t *ids, float *prob,
                    float *lm) const {
        if (two && experts % 32 == 0 && experts <= 512 && (int)it.get_local_range(0) >= experts &&
            topk * (experts / 32) <= 96 && topk <= 32) {
            if (experts == 384 && topk == 6) return run_two<72>(it, logits, bias, ids, prob, lm);
            return run_two(it, logits, bias, ids, prob, lm);
        }
        float *ls = lm, *lsb = lm + experts, *lp = lm + 2 * experts;
        const int i = (int)it.get_local_linear_id();
        if (i < topk) lp[i] = prob[i]; // RouteNorm reads what is there for a rank nobody took (NaN scores)
        if (i < experts) {
            const float v = sycl::sqrt(sycl::log1p(sycl::exp(logits[i])));
            ls[i] = v;
            lsb[i] = v + bias[i];
        }
        sycl::group_barrier(it.get_group());
        if (experts % 32 == 0) { // 32 scores per local load, broadcast from constant lanes
            sycl::sub_group sg = it.get_sub_group();
            const int lane = (int)sg.get_local_linear_id();
            const float v = lsb[i];
            int rank = 0;
            for (int jb = 0; jb < experts; jb += 32) {
                const float u = lsb[jb + lane];
#pragma unroll
                for (int k = 0; k < 32; ++k) {
                    const float w = sycl::select_from_group(sg, u, k);
                    rank += (w > v || (w == v && jb + k < i)) ? 1 : 0;
                }
            }
            if (i < experts && rank < topk) { // i >= experts: a larger work-group (RoutePRows)
                ids[rank] = (uint32_t)i;
                lp[rank] = ls[i];
            }
        } else if (i < experts) {
            const float v = lsb[i];
            int rank = 0;
            for (int j = 0; j < experts; ++j) rank += (lsb[j] > v || (lsb[j] == v && j < i)) ? 1 : 0;
            if (rank < topk) {
                ids[rank] = (uint32_t)i;
                lp[rank] = ls[i];
            }
        }
        sycl::group_barrier(it.get_group());
        if (i < topk) {
            float sum = 0;
            for (int t = 0; t < topk; ++t) sum += lp[t];
            prob[i] = lp[i] / (sum + 1e-20f) * 1.5f;
        }
    }
};

// RouteP in work-group 0 (>= experts items, local memory as RouteP) while the
// other work-groups run dense rows (the shared expert's gate and up rows: the
// router is one work-group of serial work, the rows are memory-bound). Each
// part computes exactly what its own launch computes.
template <typename R> struct RoutePRows {
    RouteP rp;
    R rows;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *logits, const float *bias, uint32_t *ids,
                                     float *prob, float *lm) const {
        const unsigned g = (unsigned)it.get_group_linear_id();
        if (g == 0) {
            rp(it, logits, bias, ids, prob, lm);
            return;
        }
        sycl::sub_group sg = it.get_sub_group();
        const unsigned r = (g - 1) * (unsigned)(it.get_local_range(0) / 32) + sg.get_group_linear_id();
        if (r < rows.n()) rows.row(sg, sg.get_local_linear_id(), r);
    }
};

// SwigluProbA on the routed rows then SwigluA on the shared expert's n
// elements, one launch (items [0, rows*n) and [rows*n, rows*n + n)).
template <typename A> struct SwigluBothA {
    int rows, n; float lim;
    void operator()(sycl::nd_item<1> it, const typename A::T *gate, const typename A::T *up, typename A::T *out,
                    const float *prob, const typename A::T *sgate, const typename A::T *sup, typename A::T *sout) const {
        const int g_ = (int)it.get_global_linear_id();
        if (g_ < rows * n) {
            const int r = g_ / n;
            float g = sycl::fmin(A::rd(gate[g_]), lim);
            float u = sycl::clamp(A::rd(up[g_]), -lim, lim);
            const typename A::T v = A::wr(g / (1.0f + sycl::exp(-g)) * u);
            out[g_] = A::wr(prob[r] * A::rd(v));
        } else if (g_ < (rows + 1) * n) {
            const int i = g_ - rows * n;
            float g = sycl::fmin(A::rd(sgate[i]), lim);
            float u = sycl::clamp(A::rd(sup[i]), -lim, lim);
            sout[i] = A::wr(g / (1.0f + sycl::exp(-g)) * u);
        }
    }
};

// CompressPoolA on one sub-group: the per-channel softmax pool is
// independent per channel (lane-parallel, same expressions); the RMS
// statistic keeps CompressPoolA's serial double sum in channel order (every
// lane runs it on the same values). tmp: local memory, hd floats.
template <typename A> struct CompressPoolP {
    int r, hd;
    void operator()(sycl::nd_item<1> it, const float *kv_state, const float *score_state, const float *nw,
                    typename A::T *out, float *tmp) const {
        const int lane = (int)it.get_local_linear_id();
        for (int i = lane; i < hd; i += 32) {
            float mx = score_state[i];
            for (int j = 1; j < r; ++j) mx = score_state[j * hd + i] > mx ? score_state[j * hd + i] : mx;
            float sum = 0, acc = 0;
            for (int j = 0; j < r; ++j) sum += sycl::exp(score_state[j * hd + i] - mx);
            for (int j = 0; j < r; ++j)
                acc += kv_state[j * hd + i] * (sycl::exp(score_state[j * hd + i] - mx) / sum);
            tmp[i] = acc;
        }
        sycl::group_barrier(it.get_group());
        double sq = 0;
        for (int i = 0; i < hd; ++i) sq += double(tmp[i]) * tmp[i];
        const float rs = float(1.0 / sycl::sqrt(sq / hd + 1e-20));
        for (int i = lane; i < hd; i += 32) out[i] = A::wr(nw[i] * (tmp[i] * rs));
    }
};

// ---- smallk (2026-11-11; benches /home/steve/dsv41-work/smallk/bench_smallk.cpp): one-work-group forms of four
// latency-bound one-token launches. Each gives the production bits: the proofs below; bench-checked bit for bit on
// real-shaped data including near-midpoint, inf / NaN / subnormal / zero inputs and every fallback forced.
// OWN_SMALLK=1 selects them (backend o.smallk). Every kernel here is a 128-register kernel (no mode switch).
[[gnu::always_inline]] inline void sk_put(uint32_t *lm, int w, double v) {
    const uint64_t b = sycl::bit_cast<uint64_t>(v);
    lm[2 * w] = (uint32_t)b;
    lm[2 * w + 1] = (uint32_t)(b >> 32);
}
[[gnu::always_inline]] inline double sk_get(const uint32_t *lm, int w) {
    return sycl::bit_cast<double>((uint64_t)lm[2 * w] | ((uint64_t)lm[2 * w + 1] << 32));
}
// RmsNormPS's scale with rs_fast's bracket split over the S sub-groups of ONE work-group: chunk c (256 elements)
// on sub-group c % S, the float-float blocks of two chunks (<= 16 terms per lane) as rs_fast, the block (hi, lo)
// added in double, the lane xor tree, the S partials in a fixed xor tree through local memory, then rs_fast's own
// check. rs_fast's proof bounds |acc_chain - s| < 1.0e-12 E from (a) per block of k <= 16 terms the low sum's
// rounding <= k (k + 1) u^2 E_b and (b) <= 25 double adds on any leaf-to-root path; it does not use which terms
// share a block or the order of the double adds. Here a block still has <= 16 terms per lane and a path has
// <= 2 ceil(ceil(C / S) / 2) + 5 + log2(S) <= 13 double adds: the same bound, the same check. When it fails (or s
// is out of range) every sub-group runs RmsNormPS::acc_chain (the production chain). Output: the production
// expression w * (x * rs). Only the chunks being summed are live; x and w are reloaded for the output (L1).
template <unsigned N, unsigned S> struct SkNormSplit {
    static_assert(N % 256 == 0 && S >= 1 && S <= 16);
    static constexpr unsigned C = N / 256, MY = (C + S - 1) / S;
    using PS = RmsNormPS<N, 4>; // rs_of / acc_chain do not depend on PS's S
    [[gnu::always_inline]] static inline double partial(sycl::sub_group sg, unsigned lane, unsigned sgi,
                                                         const sycl::vec<float, 8> *xv) {
        double acc = 0;
#pragma unroll
        for (unsigned k2 = 0; k2 < MY; k2 += 2) {
            float hi = 0, lo = 0;
#pragma unroll
            for (unsigned h = 0; h < 2; ++h) {
                const unsigned k = k2 + h;
                if (k >= MY || sgi + k * S >= C) continue;
#pragma unroll
                for (unsigned m = 0; m < 8; ++m) {
                    const float a = xv[k][m];
                    const float p = a * a;
                    const float e = sycl::fma(a, a, -p);
                    const float t = hi + p;
                    const float z = t - hi;
                    const float er = (hi - (t - z)) + (p - z);
                    hi = t;
                    lo = lo + (er + e);
                }
            }
            acc = acc + double(hi);
            acc = acc + double(lo);
        }
        for (int w_ = 16; w_; w_ >>= 1) acc += sycl::select_from_group(sg, acc, (int)lane ^ w_);
        return acc;
    }
    // the S partials at lm words [w0, w0 + S) (lanes >= S add +0.0; no partial is -0.0), then rs_fast's check
    [[gnu::always_inline]] static inline float finish(sycl::sub_group sg, unsigned lane, const uint32_t *lm, int w0,
                                                      bool &ok) {
        double a = lane < S ? sk_get(lm, w0 + (int)lane) : 0.0;
#pragma unroll
        for (unsigned w_ = 1; w_ < S; w_ <<= 1) a += sycl::select_from_group(sg, a, (int)(lane ^ w_));
        const double acc = sycl::select_from_group(sg, a, 0);
        const double D = 1.0 / sycl::sqrt(acc / N + 1e-20);
        const float f = float(D);
        const double fd = f, up = sycl::nextafter(f, INFINITY), dn = sycl::nextafter(f, 0.0f);
        ok = acc > 1e-25 && acc < 1e30 && D * (1 + 4e-12) < fd + (up - fd) * 0.5 &&
             D * (1 - 4e-12) > fd - (fd - dn) * 0.5;
        return f;
    }
    // the whole norm on the S sub-groups of one work-group (every sub-group calls it: one barrier inside)
    [[gnu::always_inline]] static inline void run(sycl::nd_item<1> it, unsigned sgi, uint32_t *lm, int w0, const float *x,
                                                  const float *w, float *y) {
        namespace ex = sycl::ext::oneapi::experimental;
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
#pragma unroll
        for (unsigned k = 0; k < MY; ++k)
            if (sgi + k * S < C)
                ex::prefetch((void *)(w + (sgi + k * S) * 256 + lane * 8), ex::properties{ex::prefetch_hint_L1});
        double p;
        {
            sycl::vec<float, 8> xv[MY];
#pragma unroll
            for (unsigned k = 0; k < MY; ++k)
                if (sgi + k * S < C) xv[k] = sg_bloadN<8>(sg, x + (sgi + k * S) * 256);
            p = partial(sg, lane, sgi, xv);
        }
        if (lane == 0) sk_put(lm, w0 + (int)sgi, p);
        sycl::group_barrier(it.get_group());
        bool ok;
        float rs = finish(sg, lane, lm, w0, ok);
        if (!ok) rs = PS::rs_of(PS::acc_chain(sg, lane, x));
#pragma unroll
        for (unsigned k = 0; k < MY; ++k)
            if (sgi + k * S < C) {
                const auto xv = sg_bloadN<8>(sg, x + (sgi + k * S) * 256);
                const auto wv = sg_bloadN<8>(sg, w + (sgi + k * S) * 256);
                sycl::vec<float, 8> o;
#pragma unroll
                for (unsigned m = 0; m < 8; ++m) o[m] = wv[m] * (xv[m] * rs);
                sg.store<8>(sycl::address_space_cast<sycl::access::address_space::global_space,
                                                     sycl::access::decorated::yes>(y + (sgi + k * S) * 256),
                            o);
            }
    }
};
// RmsNormPS<N, *> as one work-group of S sub-groups (launch_wgl<2 S>(tile, 1, 32 S, ...); not in place).
// N = 5120, S = 16: 7.3 -> 2.9 us (bench G1, after an 8 MB writer, cold weights)
template <unsigned N, unsigned S> struct SkNormW {
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *x, const float *w, float *y, uint32_t *lm) const {
        SkNormSplit<N, S>::run(it, it.get_sub_group().get_group_linear_id(), lm, 0, x, w, y);
    }
};
// the query-a 1280 norm and the key-value 512 norm in one work-group of 8 sub-groups (launch_wgl<16>(c, 1, 256, ...);
// replaces RowsP<RowsPair<NormRows<1280, 4>, NormRows<512, 2>>> @wg64): sub-groups 0..4 the 1280 norm (one chunk
// each, SkNormSplit<1280, 5>), 5..6 the 512 norm (SkNormSplit<512, 2>; production runs the 512 norm's chain, the
// bracket gives the same scale by the proof above, chain fallback), 7 idle; one barrier. 4.1 -> 2.7 us (bench G3)
struct SkNormPairW {
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *qa, const float *wq, float *qn, const float *kv,
                                     const float *wk, float *kvn, uint32_t *lm) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), sgi = sg.get_group_linear_id();
        const bool is1 = sgi < 5, is2 = sgi >= 5 && sgi < 7;
        const unsigned ch = is1 ? sgi : sgi - 5;
        const float *x = is1 ? qa : kv, *w = is1 ? wq : wk;
        float *y = is1 ? qn : kvn;
        sycl::vec<float, 8> xv[1], wv[1];
        if (is1 || is2) {
            xv[0] = sg_bloadN<8>(sg, x + ch * 256);
            wv[0] = sg_bloadN<8>(sg, w + ch * 256);
            if (is1) sk_put(lm, (int)sgi, SkNormSplit<1280, 5>::partial(sg, lane, sgi, xv));
            else sk_put(lm, (int)sgi, SkNormSplit<512, 2>::partial(sg, lane, ch, xv));
        }
        sycl::group_barrier(it.get_group());
        if (!(is1 || is2)) return;
        float rs;
        bool ok = false;
        if (is1) {
            rs = SkNormSplit<1280, 5>::finish(sg, lane, lm, 0, ok);
            if (!ok) rs = RmsNormPS<1280, 4>::rs_of(RmsNormPS<1280, 4>::acc_chain(sg, lane, qa));
        } else {
            rs = SkNormSplit<512, 2>::finish(sg, lane, lm, 5, ok);
            if (!ok) rs = RmsNormPS<512, 2>::rs_of(RmsNormPS<512, 2>::acc_chain(sg, lane, kv));
        }
        sycl::vec<float, 8> o;
#pragma unroll
        for (unsigned m = 0; m < 8; ++m) o[m] = wv[0][m] * (xv[0][m] * rs);
        sg.store<8>(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                        y + ch * 256),
                    o);
    }
};
// The stream mix's 25 dot rows (HcMixDotsP<5120, 8>: 24 fn rows + the streams' sum of squares, 8 segment partials
// each) by a proven fast sum, one row per work-group of 16 sub-groups. The finish (HcMixFinishSG, both forms) sums
// row r's partials in order, t_r = 0 + d0 + ... + d7, and uses only float(t_r) (r < 24) and
// float(1 / sqrt(t_24 / N + 1e-20)) (r = 24), N = 20480.
// Fast sum: every lane sums its products (chunk g = sgi + 16 k of the row's 80 chunks of 256) in float-float blocks
// of K terms (p = b a, e = fma(b, a, -p) exact; TwoSum into (hi, lo), the low parts summed in float), each block's
// (hi, lo) added in double, the lane xor tree, the 16 partials in a second xor tree through local memory: T;
// E = the float sum of |p|. Bound for any data without overflow (u = 2^-24, v = 2^-53, E the exact sum of |b a|):
// a block's low sum rounds by <= K (K + 1) u^2 E_b; <= 2 * 10 + 10 double adds on any path: <= gamma_30 E; the
// production chain (80 terms per lane, 5 tree levels, 8 segment adds) has <= 79 + 5 + 7 roundings on any path:
// |t_chain - s| <= gamma_91 E = 1.0103e-14 E; underflow adds < 6e-41 in all. So |T - t_chain| < CK E_up + 1e-38,
// CK = 9.0e-14 (K = 4) / 2.8e-13 (K = 8), E_up = E_float (1 + 1e-5) (E_float is within 90 u of the sum of |p|).
// Check (r < 24): |T| > 1e-30, E_up < 1e30 and (T - B, T + B) strictly between the two float midpoints around
// float(T): then float(t_chain) == float(T). r = 24: RmsNormPS::rs_fast's check on D = 1 / sqrt(T / N + 1e-20)
// (all terms >= 0 and E_up < 2 T, so D moves by < 3.5e-13 relative: inside the check's 4e-12).
// Proven: the row writes d[8 r] = T, d[8 r + 1 .. 7] = +0.0 (then the finish's sum is exactly T, T != 0);
// otherwise sub-groups 0..7 run HcMixDotsP::row (the production partials). The 200 partials then differ from
// production's, the finish's outputs do not (bench: 0 of 91,200 outputs over 95 adversarial sets incl. exact
// float ties, near-midpoint rows at 1e-6..1e-3 ulp, cancelling rows, inf / NaN / subnormal / huge; forced
// fallbacks give the production partials bit for bit). Fallback rows: ~1 % of launches on real-ish data
// (K = 8; 0.6 % at K = 4), 9 % (2.5 %) on N(0, 1) streams; a launch with one costs ~+6 us.
template <unsigned K> struct SkDotsFF {
    static constexpr unsigned SGS = 16, SEG = 8, N = 4 * 5120, NCH = N / 256, MY = (NCH + SGS - 1) / SGS;
    static_assert(K == 4 || K == 8);
    static constexpr double CK = K == 4 ? 9.0e-14 : 2.8e-13;
    [[gnu::always_inline]] static inline bool check(unsigned r, double T, float E) {
        const double Eu = double(E) * (1 + 1e-5);
        if (!(Eu < 1e30)) return false; // also NaN / inf
        const double B = CK * Eu + 1e-38;
        if (r < 24) {
            if (!(sycl::fabs(T) > 1e-30)) return false;
            const float f = float(T);
            const double fd = f;
            const double mu = (fd + double(sycl::nextafter(f, INFINITY))) * 0.5;
            const double md = (fd + double(sycl::nextafter(f, -INFINITY))) * 0.5;
            return T - B > md && T + B < mu;
        }
        if (!(T > 1e-25 && T < 1e30 && Eu < 2 * T)) return false;
        const double D = 1.0 / sycl::sqrt(T / N + 1e-20);
        const float f = float(D);
        const double fd = f, up = sycl::nextafter(f, INFINITY), dn = sycl::nextafter(f, 0.0f);
        return D * (1 + 4e-12) < fd + (up - fd) * 0.5 && D * (1 - 4e-12) > fd - (fd - dn) * 0.5;
    }
    // row r on the 16 sub-groups of one work-group (one barrier); lm: 48 words
    [[gnu::always_inline]] static inline void run(sycl::nd_item<1> it, unsigned sgi, uint32_t *lm, unsigned r,
                                                  const float *streams, const float *fn, double *out) {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const float *fr = fn + (size_t)(r < 24 ? r : 0) * N;
        double acc = 0;
        float ef = 0;
#pragma unroll
        for (unsigned k = 0; k < MY; ++k) {
            const unsigned g = sgi + k * SGS;
            if (g < NCH) {
                const auto a = sg_bloadN<8>(sg, streams + g * 256);
                const auto b = r < 24 ? sg_bloadN<8>(sg, fr + g * 256) : a;
#pragma unroll
                for (unsigned h0 = 0; h0 < 8; h0 += K) {
                    float hi = 0, lo = 0;
#pragma unroll
                    for (unsigned m = h0; m < h0 + K; ++m) {
                        const float p = b[m] * a[m];
                        const float e = sycl::fma(b[m], a[m], -p);
                        const float t = hi + p;
                        const float z = t - hi;
                        const float er = (hi - (t - z)) + (p - z);
                        hi = t;
                        lo = lo + (er + e);
                        ef = ef + sycl::fabs(p);
                    }
                    acc = acc + double(hi);
                    acc = acc + double(lo);
                }
            }
        }
        for (int w = 16; w; w >>= 1) {
            acc += sycl::select_from_group(sg, acc, (int)lane ^ w);
            ef += sycl::select_from_group(sg, ef, (int)lane ^ w);
        }
        if (lane == 0) {
            sk_put(lm, (int)sgi, acc);
            lm[2 * SGS + sgi] = sycl::bit_cast<uint32_t>(ef);
        }
        sycl::group_barrier(it.get_group());
        double T = lane < SGS ? sk_get(lm, (int)lane) : 0.0;
        float E = lane < SGS ? sycl::bit_cast<float>(lm[2 * SGS + lane]) : 0.0f;
        for (int w = 1; w < 32; w <<= 1) {
            T += sycl::select_from_group(sg, T, (int)lane ^ w);
            E += sycl::select_from_group(sg, E, (int)lane ^ w);
        }
        T = sycl::select_from_group(sg, T, 0);
        E = sycl::select_from_group(sg, E, 0);
        if (check(r, T, E)) {
            if (sgi == 0 && lane < SEG) out[r * SEG + lane] = lane == 0 ? T : 0.0;
            return;
        }
        if (sgi < SEG) HcMixDotsP<5120, 8>::row(sg, lane, r * SEG + sgi, streams, fn, out);
    }
};
// the 5,120 pre-norm and the stream mix's dot rows in one launch (replaces RowsP<RowsPair<NormRows<5120, 4>,
// HcDotsRows<5120, 8>>> @wg64): work-group 0 the norm (SkNormSplit<5120, 16>), work-groups 1..25 a dot row each.
// launch_wgl<64>(c, 26, 512, ...). 7.7 -> 6.4 us (bench, K = 8, after an 8 MB writer, cold fn rows)
template <unsigned K> struct SkNormDotsW {
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *x, const float *w, float *y, const float *streams,
                                     const float *fn, double *out, uint32_t *lm) const {
        const unsigned g = (unsigned)it.get_group_linear_id(), sgi = it.get_sub_group().get_group_linear_id();
        if (g == 0) {
            SkNormSplit<5120, 16>::run(it, sgi, lm, 0, x, w, y);
            return;
        }
        SkDotsFF<K>::run(it, sgi, lm, g - 1, streams, fn, out);
    }
};
// CompressPoolP (r = 2, hd = 512) on one work-group of 512 items, one channel per item (launch_local<1024>(c, 512,
// ...)): the per-channel softmax pool is CompressPoolP's expression (it is per channel already); the RMS
// statistic's fast sum: one exact term double(t) t per item, the lane xor tree, the 16 partials in a fixed xor tree
// (9 double adds on any path: |s - E| <= 9 v E, v = 2^-53; the production chain in channel order <= 511 v E), so
// |chain - s| < 6e-14 E, far inside the norm check's 4e-12 margin (built for 1.0e-12 E); the check is rs_fast's
// with N = hd; when it fails sub-group 0 runs the production chain from local memory and hands rs over.
// tmp: 1024 floats (hd channels, then the partials' words, then rs). 37 -> 2.4 us (bench CP).
template <typename A> struct SkCompressPoolW {
    int r, hd; // 2, 512 (the host checks)
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *kv_state, const float *score_state, const float *nw,
                                     typename A::T *out, float *tmp) const {
        sycl::sub_group sg = it.get_sub_group();
        const int i = (int)it.get_local_linear_id(), lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
        constexpr int R = 2, NSG = 16;
        uint32_t *lm = reinterpret_cast<uint32_t *>(tmp + 512);
        float mx = score_state[i];
        for (int j = 1; j < R; ++j) mx = score_state[j * hd + i] > mx ? score_state[j * hd + i] : mx;
        float sum = 0, a = 0;
        for (int j = 0; j < R; ++j) sum += sycl::exp(score_state[j * hd + i] - mx);
        for (int j = 0; j < R; ++j) a += kv_state[j * hd + i] * (sycl::exp(score_state[j * hd + i] - mx) / sum);
        tmp[i] = a;
        double acc = double(a) * double(a);
        for (int w_ = 16; w_; w_ >>= 1) acc += sycl::select_from_group(sg, acc, lane ^ w_);
        if (lane == 0) sk_put(lm, sgi, acc);
        sycl::group_barrier(it.get_group());
        double s2 = lane < NSG ? sk_get(lm, lane) : 0.0;
#pragma unroll
        for (int w_ = 1; w_ < NSG; w_ <<= 1) s2 += sycl::select_from_group(sg, s2, lane ^ w_);
        s2 = sycl::select_from_group(sg, s2, 0);
        const double D = 1.0 / sycl::sqrt(s2 / hd + 1e-20);
        float rs = float(D);
        const double fd = rs, up = sycl::nextafter(rs, INFINITY), dn = sycl::nextafter(rs, 0.0f);
        const bool ok = s2 > 1e-25 && s2 < 1e30 && D * (1 + 4e-12) < fd + (up - fd) * 0.5 &&
                        D * (1 - 4e-12) > fd - (fd - dn) * 0.5;
        if (!ok) { // uniform: every item holds the same s2
            if (sgi == 0) {
                double sq = 0;
                for (int k = 0; k < hd; ++k) sq += double(tmp[k]) * tmp[k];
                if (lane == 0) lm[2 * NSG] = sycl::bit_cast<uint32_t>(float(1.0 / sycl::sqrt(sq / hd + 1e-20)));
            }
            sycl::group_barrier(it.get_group());
            rs = sycl::bit_cast<float>(lm[2 * NSG]);
        }
        out[i] = A::wr(nw[i] * (a * rs));
    }
};
// EngramGateW<S> (EngramGateP::run_wg<S>) at h = 5120 with (a) the per-lane term count a constant (the loops
// unrolled; the same terms in the same order), (b) the sums of squares as fma(dh, dh, s): the product of two floats
// is exact in double, so RN(s + dh dh) is the production's s + ph bit for bit (the same fast sums, the same verdict),
// (c) the update's kv rows prefetched into L1 at the start (the same loads, earlier). The check, the chains
// (fallback) and the update expressions: run_wg's code. lm: 8 S + 2 words. 11.4 -> 8.7 us (bench EG, S = 16).
template <unsigned S> struct SkEngramGateW {
    int h; // 5120 (the host checks)
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, float *streams, const float *kvbuf, const float *gate_w,
                                     uint32_t *lm) const {
        static_assert(S == 8 || S == 16);
        const int j = (int)it.get_group_linear_id();
        if (j >= 4) return;
        sycl::sub_group sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
        const float eps = 1e-20f, clamp_v = 1e-6f;
        const float *sr = streams + (size_t)j * h, *kr = kvbuf + (size_t)j * h, *gr = gate_w + (size_t)j * h;
        const float *vr = kvbuf + (size_t)4 * h;
        constexpr int PER = 5120 / (32 * (int)S);
        namespace ex = sycl::ext::oneapi::experimental;
#pragma unroll
        for (int t = 0; t < PER; ++t)
            ex::prefetch((void *)(vr + t * 32 * (int)S + 32 * sgi + lane), ex::properties{ex::prefetch_hint_L1});
        double sh = 0, sk = 0, sd = 0, sa = 0;
#pragma unroll
        for (int t = 0; t < PER; ++t) {
            const int ix = t * 32 * (int)S + 32 * sgi + lane;
            const float hvt = sr[ix];
            const float kvv = kr[ix], gw = gr[ix];
            const double dh = double(hvt), dk = double(kvv);
            const double pd = double(hvt) * gw * kvv;
            sh = sycl::fma(dh, dh, sh);
            sk = sycl::fma(dk, dk, sk);
            sd += pd;
            sa += sycl::fabs(pd);
        }
#pragma unroll
        for (int w = 16; w; w >>= 1) {
            sh += sycl::select_from_group(sg, sh, lane ^ w);
            sk += sycl::select_from_group(sg, sk, lane ^ w);
            sd += sycl::select_from_group(sg, sd, lane ^ w);
            sa += sycl::select_from_group(sg, sa, lane ^ w);
        }
        if (lane == 0) {
            sk_put(lm, 4 * sgi, sh);
            sk_put(lm, 4 * sgi + 1, sk);
            sk_put(lm, 4 * sgi + 2, sd);
            sk_put(lm, 4 * sgi + 3, sa);
        }
        sycl::group_barrier(it.get_group());
        float rstd = 0, fd = 0;
        bool ok;
        {
            const int q = lane & 3, s0 = lane >> 2;
            double a = s0 < (int)S ? sk_get(lm, 4 * s0 + q) : 0.0;
            if constexpr (S == 16) a = a + sk_get(lm, 4 * (s0 + 8) + q);
#pragma unroll
            for (int w = 4; w <= 16; w *= 2) a += sycl::select_from_group(sg, a, lane ^ w);
            const double sh2 = sycl::select_from_group(sg, a, 0), sk2 = sycl::select_from_group(sg, a, 1),
                         sd2 = sycl::select_from_group(sg, a, 2), sa2 = sycl::select_from_group(sg, a, 3);
            ok = sycl::isfinite(sh2) && sycl::isfinite(sk2) && sycl::isfinite(sd2) && sycl::isfinite(sa2);
            if (ok) {
                const double c = (double(h) + 64.0) * 1.2e-16;
                const double wh = c * sh2, wk = c * sk2, wd = c * sa2;
                const float r0 = EngramGateP::rstd_of(sh2 + wh, sk2 + wk, h, eps),
                            r1 = EngramGateP::rstd_of(sycl::fmax(sh2 - wh, 0.0), sycl::fmax(sk2 - wk, 0.0), h, eps);
                const float d0 = float(sd2 - wd), d1 = float(sd2 + wd);
                ok = sycl::bit_cast<uint32_t>(r0) == sycl::bit_cast<uint32_t>(r1) &&
                     sycl::bit_cast<uint32_t>(d0) == sycl::bit_cast<uint32_t>(d1);
                rstd = r0;
                fd = d0;
            }
        }
        if (!ok && sgi == 0) { // the production chains
            double hsq = 0, ksq = 0, dot = 0;
            for (int i0 = 0; i0 < h; i0 += 32) {
                const float hv2 = sr[i0 + lane], kvv = kr[i0 + lane], gw = gr[i0 + lane];
                const double ph = double(hv2) * hv2, pk = double(kvv) * kvv, pd = double(hv2) * gw * kvv;
#pragma unroll
                for (int l2 = 0; l2 < 32; ++l2) {
                    hsq += sycl::select_from_group(sg, ph, l2);
                    ksq += sycl::select_from_group(sg, pk, l2);
                }
#pragma unroll
                for (int l2 = 0; l2 < 32; ++l2) dot += sycl::select_from_group(sg, pd, l2);
            }
            if (lane == 0) {
                lm[8 * S] = sycl::bit_cast<uint32_t>(EngramGateP::rstd_of(hsq, ksq, h, eps));
                lm[8 * S + 1] = sycl::bit_cast<uint32_t>(float(dot));
            }
        }
        sycl::group_barrier(it.get_group());
        if (!ok) {
            rstd = sycl::bit_cast<float>(lm[8 * S]);
            fd = sycl::bit_cast<float>(lm[8 * S + 1]);
        }
        const float d = fd * rstd / sycl::sqrt(float(h));
        const float g = 1.0f / (1.0f + sycl::exp(-sycl::copysign(sycl::sqrt(sycl::fmax(sycl::fabs(d), clamp_v)), d)));
        float *so = streams + (size_t)j * h;
#pragma unroll
        for (int t = 0; t < PER; ++t) {
            const int ix = t * 32 * (int)S + 32 * sgi + lane;
            so[ix] = so[ix] + g * vr[ix];
        }
    }
};

// ---- fused elementwise steps (fewer launches; each output keeps the exact
// expression sequence of the kernels it replaces) ----------------------------

// HcPostA without the stream copy: one item per position i reads the four old
// stream values first, then writes the four new ones (HcPostA needed `old` =
// a copy because its items each wrote one stream). pre_src/pre_dst, if set,
// also copy the 4 pre-mix floats (the queue copy that followed the FFN post).
template <typename A> struct HcPostP {
    int h;
    void operator()(sycl::nd_item<1> it, typename A::T *streams, const typename A::T *x, const float *post,
                    const float *comb, const float *pre_src, float *pre_dst) const {
        const int i = (int)it.get_global_linear_id();
        if (pre_dst && i < 4) pre_dst[i] = pre_src[i];
        if (i >= h) return;
        float o[4];
        for (int k = 0; k < 4; ++k) o[k] = A::rd(streams[(size_t)k * h + i]);
        const float xi = A::rd(x[i]);
        float r[4];
        for (int j = 0; j < 4; ++j) {
            float acc = post[j] * xi;
            for (int k = 0; k < 4; ++k) acc += comb[k * 4 + j] * o[k];
            r[j] = acc;
        }
        for (int j = 0; j < 4; ++j) streams[(size_t)j * h + i] = A::wr(r[j]);
    }
};
// HcPostP then the next sublayer's HcPreA in one launch (both elementwise in i): the new streams as
// stored, collapsed with mix into out. mix must not be pre_dst (the copy races with the readers): the
// attention after an FFN passes the FFN pre-mix itself (pre_src), the FFN passes pre_a.
template <typename A> struct HcPostPreP {
    int h;
    void operator()(sycl::nd_item<1> it, typename A::T *streams, const typename A::T *x, const float *post,
                    const float *comb, const float *pre_src, float *pre_dst, const float *mix,
                    typename A::T *out) const {
        const int i = (int)it.get_global_linear_id();
        if (pre_dst && i < 4) pre_dst[i] = pre_src[i];
        if (i >= h) return;
        float o[4];
        for (int k = 0; k < 4; ++k) o[k] = A::rd(streams[(size_t)k * h + i]);
        const float xi = A::rd(x[i]);
        float r[4];
        for (int j = 0; j < 4; ++j) {
            float acc = post[j] * xi;
            for (int k = 0; k < 4; ++k) acc += comb[k * 4 + j] * o[k];
            r[j] = acc;
        }
        typename A::T sv[4];
        for (int j = 0; j < 4; ++j) {
            sv[j] = A::wr(r[j]);
            streams[(size_t)j * h + i] = sv[j];
        }
        float acc = 0;
        for (int j = 0; j < 4; ++j) acc += mix[j] * A::rd(sv[j]);
        out[i] = A::wr(acc);
    }
};

// SwigluA then ProbScaleA (rows x n): the activation is rounded to the
// activation type in between, as when it was stored.
template <typename A> struct SwigluProbA {
    int rows, n; float lim;
    void operator()(sycl::nd_item<1> it, const typename A::T *gate, const typename A::T *up, typename A::T *out,
                    const float *prob) const {
        const int g_ = (int)it.get_global_linear_id();
        const int r = g_ / n;
        if (r >= rows) return;
        float g = sycl::fmin(A::rd(gate[g_]), lim);
        float u = sycl::clamp(A::rd(up[g_]), -lim, lim);
        const typename A::T v = A::wr(g / (1.0f + sycl::exp(-g)) * u);
        out[g_] = A::wr(prob[r] * A::rd(v));
    }
};

// ToActA (f32 -> activation) then RopePairsA in place on the result: one item
// per element; the first item of each rotated pair writes both outputs.
template <typename A> struct ToActRopeA {
    unsigned rows, d, rdim; bool inverse;
    void operator()(sycl::nd_item<1> it, const float *x, typename A::T *y, const float *cosb, const float *sinb) const {
        const unsigned e = (unsigned)it.get_global_linear_id();
        const unsigned r = e / d, c = e % d;
        if (r >= rows) return;
        if (c < d - rdim) { y[e] = A::wr(x[e]); return; }
        const unsigned q = c - (d - rdim);
        if (q & 1u) return;
        const unsigned i = q / 2;
        float re = A::rd(A::wr(x[e])), im = A::rd(A::wr(x[e + 1]));
        float cs = cosb[i], sn = inverse ? -sinb[i] : sinb[i];
        y[e] = A::wr(re * cs - im * sn);
        y[e + 1] = A::wr(re * sn + im * cs);
    }
};

// HcPreA then RmsNormPS on S sub-groups, f32 activations: every sub-group
// recomputes the collapsed row x_i = ((0 + m0*s0_i) + m1*s1_i) + ... (HcPreA)
// for the statistic, then normalizes its chunks. x is not stored.
template <unsigned N, unsigned S> struct HcPreNormPS {
    static_assert(N % 256 == 0);
    static constexpr unsigned C = N / 256;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *streams, const float *mix, const float *w,
                                     float *y) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), sgi = sg.get_group_linear_id();
        const float m0 = mix[0], m1 = mix[1], m2 = mix[2], m3 = mix[3];
        auto xrow = [&](unsigned c) {
            const auto a0 = sg_bloadN<8>(sg, streams + c * 256), a1 = sg_bloadN<8>(sg, streams + N + c * 256);
            const auto a2 = sg_bloadN<8>(sg, streams + 2 * N + c * 256), a3 = sg_bloadN<8>(sg, streams + 3 * N + c * 256);
            sycl::vec<float, 8> xv;
#pragma unroll
            for (unsigned m = 0; m < 8; ++m) {
                float acc = 0;
                acc += m0 * a0[m];
                acc += m1 * a1[m];
                acc += m2 * a2[m];
                acc += m3 * a3[m];
                xv[m] = acc;
            }
            return xv;
        };
        double acc = 0;
#pragma unroll
        for (unsigned c = 0; c < C; ++c) {
            const auto xv = xrow(c);
#pragma unroll
            for (unsigned m = 0; m < 8; ++m) acc += double(xv[m]) * xv[m];
        }
        for (int w_ = 16; w_; w_ >>= 1) acc += sycl::select_from_group(sg, acc, (int)lane ^ w_);
        const float rs = float(1.0 / sycl::sqrt(acc / N + 1e-20));
#pragma unroll
        for (unsigned c = 0; c < C; ++c) {
            if (c % S != sgi) continue;
            const auto xv = xrow(c);
            const auto wv = sg_bloadN<8>(sg, w + c * 256);
            sycl::vec<float, 8> o;
#pragma unroll
            for (unsigned m = 0; m < 8; ++m) o[m] = wv[m] * (xv[m] * rs);
            sg.store<8>(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                            y + c * 256), o);
        }
    }
};

// ---- tensor-parallel pieces (Backend41 Options::tp > 1) ---------------------

// All-gather of row slices between the cards of a tensor-parallel group, card
// to card through Level Zero IPC-mapped arenas (one work-group). Card `me`
// copies its rows [r0, r1) of each of `nslot` slots (slot stride `stride`
// floats, from float offset `off` of the arena) out of its own arena into every
// peer's arena at the same place, fences at system scope, then stores `seq`
// into its flag in every peer's arena (uint32 index 16 * me, me < 6); it then waits
// until every peer's flag in its own arena has reached `seq`. Pure copies: the
// gathered values are the producer's bits. r0, r1 and stride are multiples of 4
// and the arenas 16-byte aligned. A wait that runs past `spin` polls (~175 ns
// each) records 1 + peer in err[0] (host memory) and lets the queue go on: the
// host checks err after every step and fails the run.
// The six arena pointers are separate kernel arguments, never fields of a
// struct passed by value: the driver tracks only direct pointer arguments, and
// a pointer inside a by-value struct marks the kernel "indirect access", which
// costs every launch a driver-wide lock shared by all cards' threads (and,
// with DisableIndirectAccess=1, a peer arena reached only that way would
// never be made resident on this card).
// K's work-groups [0, nmain) exactly as launched alone; the work-groups after them pull a byte range into
// the card's cache (prefetch: nothing is returned or written) for a matrix launch that comes later, while K
// itself is latency-bound and the memory is idle. K's arithmetic is untouched.
template <typename K> struct WithPf {
    K k;
    unsigned nmain;
    const uint8_t *pf; // 64-byte lines from here
    unsigned lines;
    template <typename... A> [[gnu::flatten]] void operator()(sycl::nd_item<1> it, A... a) const {
        const unsigned g = (unsigned)it.get_group_linear_id();
        if (g < nmain) {
            k(it, a...);
            return;
        }
        namespace ex = sycl::ext::oneapi::experimental;
        const unsigned L = (unsigned)it.get_local_range(0), np = (unsigned)it.get_group_range(0) - nmain;
        for (unsigned i = (g - nmain) * L + (unsigned)it.get_local_linear_id(); i < lines; i += np * L)
            ex::prefetch((void *)(pf + (size_t)i * 64), ex::properties{ex::prefetch_hint_L3});
    }
};

struct XchgP {
    int n, me;
    unsigned off, stride, nslot, r0, r1;
    uint32_t seq;
    long spin;
    int mode = 0; // 0 push + wait, 1 push only, 2 wait only (see Backend41::xchg)
    static float *pick(int d, float *p0, float *p1, float *p2, float *p3, float *p4, float *p5) {
        return d == 0 ? p0 : d == 1 ? p1 : d == 2 ? p2 : d == 3 ? p3 : d == 4 ? p4 : p5;
    }
    void operator()(sycl::nd_item<1> it, float *p0, float *p1, float *p2, float *p3, float *p4, float *p5,
                    uint32_t *err) const {
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        const unsigned t = (unsigned)it.get_local_linear_id(), T = (unsigned)it.get_local_range(0);
        float *mine = pick(me, p0, p1, p2, p3, p4, p5);
        const float *own = mine + off;
        const unsigned n4 = (r1 - r0) / 4;
        if (mode != 2) {
            for (unsigned k = t; k < nslot * n4; k += T) {
                const size_t o = (size_t)(k / n4) * stride + r0 + (k % n4) * 4;
                const sycl::vec<float, 4> v = *reinterpret_cast<const sycl::vec<float, 4> *>(own + o);
                for (int d = 0; d < n; ++d)
                    if (d != me)
                        *reinterpret_cast<sycl::vec<float, 4> *>(pick(d, p0, p1, p2, p3, p4, p5) + off + o) = v;
            }
            sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
            sycl::group_barrier(it.get_group());
            if ((int)t < n && (int)t != me)
                AR(reinterpret_cast<uint32_t *>(pick((int)t, p0, p1, p2, p3, p4, p5))[16 * me]).store(seq);
        }
        if (mode == 1) return;
        if ((int)t < n && (int)t != me) {
            // after one timeout this card stops waiting (poison word, uint32 index 96 of its own arena):
            // the step is already failed, and a stalled peer must not cost 0.9 s per exchange
            AR poison(reinterpret_cast<uint32_t *>(mine)[96]);
            AR f(reinterpret_cast<uint32_t *>(mine)[16 * t]);
            long s = 0;
            if (!poison.load())
                while (f.load() < seq && ++s < spin) {}
            if (s >= spin) {
                poison.store(1u);
                err[0] = 1u + t;
            }
        }
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
    }
};

#ifdef OWN41_XWAIT
// ---- OWN_XWAIT (diagnostic build, -DOWN41_XWAIT): XchgP / XchgPull with a wait record (Backend41::xchg launches
// XchgPW / XchgPullW instead of XchgP / XchgPull only when OWN_XWAIT is set). Their bodies are the plain kernels'
// with clock reads added; the plain kernels and xchg_tail are not changed. Compiled only on request: any of these
// kernels in the module changed the plain XchgPull's register allocation (HYBRID_BC_RA -> GRAPH_COLORING_FF_BC_RA,
// 3,230 -> 3,158 instructions, small test unit, 2026-11-11), so the normal build carries none of them. Slot xk of the card's per-step ring xw, 16 words:
//   [t]      flag polls until peer t's flag was seen (0: it was there first)
//   [6 + t]  clock ticks from the start of the wait until that poll (the clock is read after every poll, so each
//            lane keeps its own exit time; one read after the loop would give every peer the slowest one's time)
//   [12]     1 (written)
//   [13]     ticks from the kernel's entry to the start of the wait (the push / publish part)
//   [14]     ticks from the entry to the end of the kernel's work (waiting work-group, lane 0)
// The peer the others wait longest for arrived last. XchgPullW records in work-group 0 only.
// The clock is the SPIR-V builtin (IGC: a read of the EU timestamp register tm0), not
// sycl::ext::oneapi::experimental::clock: that one tags the kernel with aspect ext_oneapi_clock_sub_group, and
// the ahead-of-time build for intel_gpu_bmg_g31 then leaves the kernel out of the binary without an error
// (icpx 2026.1, checked 2026-11-11; the tag spreads to every caller). The tick rate is not documented:
// tools/perf/dsv41_timeline.py fits it against the timeline's kernel times ([14]).
inline uint64_t xw_clock() {
#ifdef __SYCL_DEVICE_ONLY__
    return __spirv_ReadClockKHR(3); // sub-group scope
#else
    return 0;
#endif
}
inline uint32_t xw_u32(uint64_t d) { return d > 0xffffffffull ? 0xffffffffu : (uint32_t)d; }
struct XchgPW {
    XchgP x;
    uint32_t *xw;
    unsigned xk;
    void operator()(sycl::nd_item<1> it, float *p0, float *p1, float *p2, float *p3, float *p4, float *p5,
                    uint32_t *err) const {
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        const uint64_t ce = xw_clock();
        const int n = x.n, me = x.me;
        const unsigned t = (unsigned)it.get_local_linear_id(), T = (unsigned)it.get_local_range(0);
        float *mine = XchgP::pick(me, p0, p1, p2, p3, p4, p5);
        const float *own = mine + x.off;
        const unsigned n4 = (x.r1 - x.r0) / 4;
        if (x.mode != 2) {
            for (unsigned k = t; k < x.nslot * n4; k += T) {
                const size_t o = (size_t)(k / n4) * x.stride + x.r0 + (k % n4) * 4;
                const sycl::vec<float, 4> v = *reinterpret_cast<const sycl::vec<float, 4> *>(own + o);
                for (int d = 0; d < n; ++d)
                    if (d != me)
                        *reinterpret_cast<sycl::vec<float, 4> *>(XchgP::pick(d, p0, p1, p2, p3, p4, p5) + x.off + o) = v;
            }
            sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
            sycl::group_barrier(it.get_group());
            if ((int)t < n && (int)t != me)
                AR(reinterpret_cast<uint32_t *>(XchgP::pick((int)t, p0, p1, p2, p3, p4, p5))[16 * me]).store(x.seq);
        }
        if (x.mode == 1) return;
        uint32_t *xr = xw + (size_t)xk * 16;
        if (t == 0) xr[13] = xw_u32(xw_clock() - ce);
        if ((int)t < n && (int)t != me) {
            AR poison(reinterpret_cast<uint32_t *>(mine)[96]);
            AR f(reinterpret_cast<uint32_t *>(mine)[16 * t]);
            long s = 0;
            const uint64_t c0 = xw_clock();
            uint64_t c1 = c0;
            if (!poison.load())
                for (;;) { // XchgP's polls, the clock after each one
                    const bool ok = f.load() >= x.seq;
                    c1 = xw_clock();
                    if (ok || ++s >= x.spin) break;
                }
            xr[t] = (uint32_t)s;
            xr[6 + t] = xw_u32(c1 - c0);
            xr[12] = 1u;
            if (s >= x.spin) {
                poison.store(1u);
                err[0] = 1u + t;
            }
        }
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
        if (t == 0) xr[14] = xw_u32(xw_clock() - ce);
    }
};
#endif // OWN41_XWAIT

// The exchange at the end of the launch that produced its rows (no launch between them): every work-group
// releases its writes and counts itself done; the work-group that brings the count to the group count
// resets it, acquires, and runs XchgP's body (push, flags, wait) with its own items.
inline void xchg_tail(sycl::nd_item<1> it, const XchgP &x, uint32_t *cnt, float *p0, float *p1, float *p2, float *p3,
                      float *p4, float *p5, uint32_t *err) {
    using ARD = sycl::atomic_ref<uint32_t, sycl::memory_order::acq_rel, sycl::memory_scope::device,
                                 sycl::access::address_space::global_space>;
    sycl::group_barrier(it.get_group());
    uint32_t last = 0;
    if (it.get_local_linear_id() == 0) { // after the barrier, one release covers the group's writes
        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::device);
        ARD c(*cnt);
        last = c.fetch_add(1u) + 1u == (uint32_t)it.get_group_range(0) ? 1u : 0u;
        if (last) c.store(0u, sycl::memory_order::relaxed); // the next tail launch comes after this one ends
    }
    last = sycl::group_broadcast(it.get_group(), last, 0);
    if (!last) return;
    sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::device);
    x(it, p0, p1, p2, p3, p4, p5, err);
}

// SwigluBothA with the routed outputs at a row stride: routed row r, element i
// -> out[r * ostride + i] (a card's slice of the full [rows][ostride] layout);
// shared -> sout[i]. Same expressions as SwigluBothA.
template <typename A> struct SwigluBothS {
    int rows, n; float lim; int ostride;
    void operator()(sycl::nd_item<1> it, const typename A::T *gate, const typename A::T *up, typename A::T *out,
                    const float *prob, const typename A::T *sgate, const typename A::T *sup, typename A::T *sout) const {
        const int g_ = (int)it.get_global_linear_id();
        if (g_ < rows * n) {
            const int r = g_ / n, i = g_ % n;
            float g = sycl::fmin(A::rd(gate[g_]), lim);
            float u = sycl::clamp(A::rd(up[g_]), -lim, lim);
            const typename A::T v = A::wr(g / (1.0f + sycl::exp(-g)) * u);
            out[(size_t)r * ostride + i] = A::wr(prob[r] * A::rd(v));
        } else if (g_ < (rows + 1) * n) {
            const int i = g_ - rows * n;
            float g = sycl::fmin(A::rd(sgate[i]), lim);
            float u = sycl::clamp(A::rd(sup[i]), -lim, lim);
            sout[i] = A::wr(g / (1.0f + sycl::exp(-g)) * u);
        }
    }
};

// A published compressor row appended on the card (tensor parallel: every
// card publishes for itself): the same BF16 rounding as the host path
// (ops41::bf16b of the activation value), into row `row` of the mirrors.
template <typename A> struct PubAppendA {
    int hd, ik, row;
    void operator()(sycl::nd_item<1> it, const typename A::T *latent, const typename A::T *kk, uint16_t *ckv,
                    uint16_t *ikm) const {
        const int i = (int)it.get_global_linear_id();
        if (i < hd) ckv[(size_t)row * hd + i] = ops41::bf16b(A::rd(latent[i]));
        if (i < ik) ikm[(size_t)row * ik + i] = ops41::bf16b(A::rd(kk[i]));
    }
};
// The indexer's choice while a source has at most n rows: all of them, in
// order (Backend41::index, len <= 512): cidx[j] = j + 128 for j < len, else -1.
struct CidxFill {
    int len, n;
    void operator()(sycl::nd_item<1> it, int32_t *cidx) const {
        const int i = (int)it.get_global_linear_id();
        if (i < n) cidx[i] = i < len ? i + 128 : -1;
    }
};

// Exact top-k of n float scores in the host index()'s order: score descending,
// the lower index first among equal scores, -0 equal to +0 (scores are never
// NaN). One work-group of WG items: a radix select over order keys finds the
// k-th key T, then one pass in index order keeps every key above T and the
// first (by index) of the keys equal to T, which is the host's
// partial_sort + sort set exactly. Two forms:
//  - rows (BLOCK false): keys are the rows' scores; with a candidate mask, rows
//    j < cand_n with cand[j] == 0 count as -inf. Writes the kept rows as
//    out[i] = j + add in ascending j, then -1 up to outn.
//  - blocks (BLOCK true, select_candidate_blocks): keys are each block's
//    largest score over bs rows of `rows`, the newest block +inf. Writes
//    cand[r] = 1 for the rows of the kept blocks whose largest score is above
//    -inf and 0 for every other row.
// Local memory: NSG * 256 + 8 words.
template <bool BLOCK> struct TopKSelP {
    static constexpr int WG = 1024, NSG = WG / 32;
    int n, k, add, outn, cand_n, bs, rows;
    static uint32_t okey(float f) {
        uint32_t u = sycl::bit_cast<uint32_t>(f);
        if (u == 0x80000000u) u = 0u;
        return (u & 0x80000000u) ? ~u : (u | 0x80000000u);
    }
    float val(const float *sc, const uint8_t *cand, int j) const {
        if constexpr (BLOCK) {
            if (j == n - 1) return INFINITY;
            float m = -INFINITY; // std::max(m, v) per row, as the host folds it
            const int a = j * bs, b = sycl::min(a + bs, rows);
            for (int r = a; r < b; ++r) {
                const float v = sc[r];
                m = m < v ? v : m;
            }
            return m;
        } else {
            if (cand && j < cand_n && !cand[j]) return -INFINITY;
            return sc[j];
        }
    }
    void operator()(sycl::nd_item<1> it, const float *sc, const uint8_t *cand_in, int32_t *out, uint8_t *cand_out,
                    float *lm) const {
        auto g = it.get_group();
        const int lid = (int)it.get_local_linear_id();
        const int sgi = (int)it.get_sub_group().get_group_linear_id();
        uint32_t *hist = reinterpret_cast<uint32_t *>(lm), *misc = hist + NSG * 256;
        const bool all = k >= n;
        uint32_t T = 0, rem = 0;
        if (!all) {
            uint32_t prefix = 0, pmask = 0;
            rem = (uint32_t)k;
            for (int pass = 0; pass < 4; ++pass) {
                const int shift = 24 - 8 * pass;
                for (int i = lid; i < NSG * 256; i += WG) hist[i] = 0;
                sycl::group_barrier(g);
                for (int j = lid; j < n; j += WG) {
                    const uint32_t kk = okey(val(sc, cand_in, j));
                    if ((kk & pmask) == prefix)
                        sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::work_group,
                                         sycl::access::address_space::local_space>(
                            hist[sgi * 256 + ((kk >> shift) & 255u)])
                            .fetch_add(1u);
                }
                sycl::group_barrier(g);
                uint32_t tot = 0; // item i < 256 holds bin 255 - i: the scan runs from the top bin down
                if (lid < 256)
                    for (int s = 0; s < NSG; ++s) tot += hist[s * 256 + (255 - lid)];
                const uint32_t inc = sycl::inclusive_scan_over_group(g, tot, sycl::plus<uint32_t>());
                const uint32_t exc = inc - tot;
                if (lid < 256 && exc < rem && rem <= inc) {
                    misc[0] = 255u - (uint32_t)lid;
                    misc[1] = exc;
                }
                sycl::group_barrier(g);
                prefix |= misc[0] << shift;
                pmask |= 255u << shift;
                rem -= misc[1];
                sycl::group_barrier(g);
            }
            T = prefix;
        }
        const uint32_t KNEG = okey(-INFINITY);
        uint32_t base = 0, eqseen = 0;
        for (int c0 = 0; c0 < n; c0 += WG) {
            const int j = c0 + lid;
            const bool in = j < n;
            const uint32_t kk = in ? okey(val(sc, cand_in, j)) : 0u;
            const bool gt = in && (all || kk > T), eq = in && !all && kk == T;
            const uint32_t e = eq ? 1u : 0u;
            const uint32_t einc = sycl::inclusive_scan_over_group(g, e, sycl::plus<uint32_t>());
            const uint32_t etot = sycl::group_broadcast(g, einc, WG - 1);
            const bool sel = gt || (eq && eqseen + einc - e < rem);
            if constexpr (BLOCK) {
                if (in) {
                    const uint8_t f = (sel && kk > KNEG) ? 1 : 0;
                    const int a = j * bs, b = sycl::min(a + bs, rows);
                    for (int r = a; r < b; ++r) cand_out[r] = f;
                }
                if (out) { // OWN_IDX_CAND: the flagged blocks in order, out[0] = their count, out[1 + i] = block
                    const uint32_t s1 = (in && sel && kk > KNEG) ? 1u : 0u;
                    const uint32_t sinc = sycl::inclusive_scan_over_group(g, s1, sycl::plus<uint32_t>());
                    const uint32_t stot = sycl::group_broadcast(g, sinc, WG - 1);
                    if (s1) out[1 + base + sinc - 1] = j;
                    base += stot;
                }
            } else {
                const uint32_t s1 = sel ? 1u : 0u;
                const uint32_t sinc = sycl::inclusive_scan_over_group(g, s1, sycl::plus<uint32_t>());
                const uint32_t stot = sycl::group_broadcast(g, sinc, WG - 1);
                if (sel && base + sinc - 1 < (uint32_t)outn) out[base + sinc - 1] = j + add;
                base += stot;
            }
            eqseen += etot;
        }
        if constexpr (!BLOCK)
            for (int i = (int)base + lid; i < outn; i += WG) out[i] = -1;
        if constexpr (BLOCK)
            if (out && lid == 0) out[0] = (int32_t)base;
    }
};
// TopKSelP with the final walk by ranges (OWN_TOPK_R): the same threshold passes, then item i takes the
// positions [i c, (i + 1) c), c = ceil(n / WG): it counts its values above the threshold and equal to it, two
// group scans give its place in the list and the equal values before it, and a second walk writes its entries.
// The same entries in the same (ascending) order with the same ties (the lowest positions equal to the
// threshold) as TopKSelP's walk in steps of WG, which takes 2 group scans per WG positions. BLOCK: the same mask
// rows; its block list (out) needs the flagged count, so when the threshold is not above -inf (flags and
// selection can differ) a third scan counts the flags.
template <bool BLOCK> struct TopKSelR {
    using KP = TopKSelP<BLOCK>;
    static constexpr int WG = KP::WG, NSG = KP::NSG;
    KP p;
    void operator()(sycl::nd_item<1> it, const float *sc, const uint8_t *cand_in, int32_t *out, uint8_t *cand_out,
                    float *lm) const {
        auto g = it.get_group();
        const int lid = (int)it.get_local_linear_id();
        const int sgi = (int)it.get_sub_group().get_group_linear_id();
        uint32_t *hist = reinterpret_cast<uint32_t *>(lm), *misc = hist + NSG * 256;
        const int n = p.n;
        const bool all = p.k >= n;
        uint32_t T = 0, rem = 0;
        if (!all) {
            uint32_t prefix = 0, pmask = 0;
            rem = (uint32_t)p.k;
            for (int pass = 0; pass < 4; ++pass) {
                const int shift = 24 - 8 * pass;
                for (int i = lid; i < NSG * 256; i += WG) hist[i] = 0;
                sycl::group_barrier(g);
                for (int j = lid; j < n; j += WG) {
                    const uint32_t kk = KP::okey(p.val(sc, cand_in, j));
                    if ((kk & pmask) == prefix)
                        sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::work_group,
                                         sycl::access::address_space::local_space>(
                            hist[sgi * 256 + ((kk >> shift) & 255u)])
                            .fetch_add(1u);
                }
                sycl::group_barrier(g);
                uint32_t tot = 0;
                if (lid < 256)
                    for (int s2 = 0; s2 < NSG; ++s2) tot += hist[s2 * 256 + (255 - lid)];
                const uint32_t inc = sycl::inclusive_scan_over_group(g, tot, sycl::plus<uint32_t>());
                const uint32_t exc = inc - tot;
                if (lid < 256 && exc < rem && rem <= inc) {
                    misc[0] = 255u - (uint32_t)lid;
                    misc[1] = exc;
                }
                sycl::group_barrier(g);
                prefix |= misc[0] << shift;
                pmask |= 255u << shift;
                rem -= misc[1];
                sycl::group_barrier(g);
            }
            T = prefix;
        }
        const uint32_t KNEG = KP::okey(-INFINITY);
        const int c = (n + WG - 1) / WG, j0 = sycl::min(n, lid * c), j1 = sycl::min(n, j0 + c);
        uint32_t ngt = 0, neq = 0;
        for (int j = j0; j < j1; ++j) {
            const uint32_t kk = KP::okey(p.val(sc, cand_in, j));
            ngt += (all || kk > T) ? 1u : 0u;
            neq += (!all && kk == T) ? 1u : 0u;
        }
        const uint32_t gtb = sycl::exclusive_scan_over_group(g, ngt, sycl::plus<uint32_t>());
        const uint32_t eqb = sycl::exclusive_scan_over_group(g, neq, sycl::plus<uint32_t>());
        if constexpr (BLOCK) {
            // flagged = selected and above -inf; with T > -inf every selected block is above it
            const bool flags_eq_sel = all ? false : T > KNEG;
            uint32_t fb = 0;
            if (out && !flags_eq_sel) { // count the flags per range first
                uint32_t eqs = eqb, nf = 0;
                for (int j = j0; j < j1; ++j) {
                    const uint32_t kk = KP::okey(p.val(sc, cand_in, j));
                    const bool gt = all || kk > T, eq = !all && kk == T;
                    const bool sel = gt || (eq && eqs < rem);
                    if (eq) ++eqs;
                    nf += (sel && kk > KNEG) ? 1u : 0u;
                }
                fb = sycl::exclusive_scan_over_group(g, nf, sycl::plus<uint32_t>());
            } else {
                fb = gtb + sycl::min(eqb, rem);
            }
            uint32_t eqs = eqb, nf = 0;
            for (int j = j0; j < j1; ++j) {
                const uint32_t kk = KP::okey(p.val(sc, cand_in, j));
                const bool gt = all || kk > T, eq = !all && kk == T;
                const bool sel = gt || (eq && eqs < rem);
                if (eq) ++eqs;
                const bool f = sel && kk > KNEG;
                const int a = j * p.bs, b = sycl::min(a + p.bs, p.rows);
                for (int r = a; r < b; ++r) cand_out[r] = f ? 1 : 0;
                if (out && f) out[1 + fb + nf] = j;
                nf += f ? 1u : 0u;
            }
            const uint32_t tot = sycl::reduce_over_group(g, nf, sycl::plus<uint32_t>());
            if (out && lid == 0) out[0] = (int32_t)tot;
        } else {
            uint32_t base = gtb + sycl::min(eqb, rem), eqs = eqb;
            for (int j = j0; j < j1; ++j) {
                const uint32_t kk = KP::okey(p.val(sc, cand_in, j));
                const bool gt = all || kk > T, eq = !all && kk == T;
                const bool sel = gt || (eq && eqs < rem);
                if (eq) ++eqs;
                if (sel) {
                    if (base < (uint32_t)p.outn) out[base] = j + p.add;
                    ++base;
                }
            }
            const uint32_t tot = sycl::reduce_over_group(g, ngt, sycl::plus<uint32_t>()) +
                                 sycl::min(sycl::reduce_over_group(g, neq, sycl::plus<uint32_t>()), rem);
            for (int i = (int)tot + lid; i < p.outn; i += WG) out[i] = -1;
        }
    }
};
// TopKSelP<false> with the layer-20 mask, over the candidate rows only (OWN_IDX_CAND): bl[0] = the number of
// flagged blocks of bs rows, bl[1 + i] the blocks in ascending order (TopKSelP<true> with out). Every other row
// of [0, rows) is -inf in the masked select, so when at least k candidate rows score above -inf the threshold,
// the ties taken (lowest rows first) and the list are the same; otherwise this runs the masked TopKSelP<false>
// over all rows itself. cand / rows as TopKSelP's cand_in / n (cand_n == rows). Same local memory.
struct TopKSelC {
    static constexpr int WG = 1024, NSG = WG / 32;
    int rows, k, add, outn, bs;
    bool rwalk = false; // OWN_TOPK_R: the final walk by ranges of positions (as TopKSelR), the same list
    void operator()(sycl::nd_item<1> it, const float *sc, const uint8_t *cand, const int32_t *bl, int32_t *out,
                    float *lm) const {
        using KP = TopKSelP<false>;
        auto g = it.get_group();
        const int lid = (int)it.get_local_linear_id();
        const int sgi = (int)it.get_sub_group().get_group_linear_id();
        uint32_t *hist = reinterpret_cast<uint32_t *>(lm), *misc = hist + NSG * 256;
        const uint32_t KNEG = KP::okey(-INFINITY);
        const int n = bl[0] * bs; // candidate positions; position p is row bl[1 + p / bs] * bs + p % bs
        uint32_t c = 0;
        for (int p = lid; p < n; p += WG) {
            const int j = bl[1 + p / bs] * bs + p % bs;
            if (j < rows && KP::okey(sc[j]) > KNEG) ++c;
        }
        c = sycl::reduce_over_group(g, c, sycl::plus<uint32_t>());
        if (c < (uint32_t)k) { // too few: the masked select over all rows
            if (rwalk) TopKSelR<false>{KP{rows, k, add, outn, rows, 0, 0}}(it, sc, cand, out, nullptr, lm);
            else KP{rows, k, add, outn, rows, 0, 0}(it, sc, cand, out, nullptr, lm);
            return;
        }
        uint32_t prefix = 0, pmask = 0, rem = (uint32_t)k;
        for (int pass = 0; pass < 4; ++pass) {
            const int shift = 24 - 8 * pass;
            for (int i = lid; i < NSG * 256; i += WG) hist[i] = 0;
            sycl::group_barrier(g);
            for (int p = lid; p < n; p += WG) {
                const int j = bl[1 + p / bs] * bs + p % bs;
                if (j >= rows) continue;
                const uint32_t kk = KP::okey(sc[j]);
                if ((kk & pmask) == prefix)
                    sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::work_group,
                                     sycl::access::address_space::local_space>(hist[sgi * 256 + ((kk >> shift) & 255u)])
                        .fetch_add(1u);
            }
            sycl::group_barrier(g);
            uint32_t tot = 0; // item i < 256 holds bin 255 - i: the scan runs from the top bin down
            if (lid < 256)
                for (int s2 = 0; s2 < NSG; ++s2) tot += hist[s2 * 256 + (255 - lid)];
            const uint32_t inc = sycl::inclusive_scan_over_group(g, tot, sycl::plus<uint32_t>());
            const uint32_t exc = inc - tot;
            if (lid < 256 && exc < rem && rem <= inc) {
                misc[0] = 255u - (uint32_t)lid;
                misc[1] = exc;
            }
            sycl::group_barrier(g);
            prefix |= misc[0] << shift;
            pmask |= 255u << shift;
            rem -= misc[1];
            sycl::group_barrier(g);
        }
        const uint32_t T = prefix;
        if (rwalk) { // positions [lid c, (lid + 1) c): counts, two scans, then the entries in order
            const int c = (n + WG - 1) / WG, p0 = sycl::min(n, lid * c), p1 = sycl::min(n, p0 + c);
            uint32_t ngt = 0, neq = 0;
            for (int p = p0; p < p1; ++p) {
                const int j = bl[1 + p / bs] * bs + p % bs;
                if (j >= rows) continue;
                const uint32_t kk = KP::okey(sc[j]);
                ngt += kk > T ? 1u : 0u;
                neq += kk == T ? 1u : 0u;
            }
            const uint32_t gtb = sycl::exclusive_scan_over_group(g, ngt, sycl::plus<uint32_t>());
            const uint32_t eqb = sycl::exclusive_scan_over_group(g, neq, sycl::plus<uint32_t>());
            uint32_t base = gtb + sycl::min(eqb, rem), eqs = eqb;
            for (int p = p0; p < p1; ++p) {
                const int j = bl[1 + p / bs] * bs + p % bs;
                if (j >= rows) continue;
                const uint32_t kk = KP::okey(sc[j]);
                const bool gt = kk > T, eq = kk == T;
                const bool sel = gt || (eq && eqs < rem);
                if (eq) ++eqs;
                if (sel) {
                    if (base < (uint32_t)outn) out[base] = j + add;
                    ++base;
                }
            }
            const uint32_t tot = sycl::reduce_over_group(g, ngt, sycl::plus<uint32_t>()) +
                                 sycl::min(sycl::reduce_over_group(g, neq, sycl::plus<uint32_t>()), rem);
            for (int i = (int)tot + lid; i < outn; i += WG) out[i] = -1;
            return;
        }
        uint32_t base = 0, eqseen = 0;
        for (int c0 = 0; c0 < n; c0 += WG) {
            const int p = c0 + lid;
            int j = rows;
            if (p < n) j = bl[1 + p / bs] * bs + p % bs;
            const bool in = j < rows;
            const uint32_t kk = in ? KP::okey(sc[j]) : 0u;
            const bool gt = in && kk > T, eq = in && kk == T;
            const uint32_t e = eq ? 1u : 0u;
            const uint32_t einc = sycl::inclusive_scan_over_group(g, e, sycl::plus<uint32_t>());
            const uint32_t etot = sycl::group_broadcast(g, einc, WG - 1);
            const bool sel = gt || (eq && eqseen + einc - e < rem);
            const uint32_t s1 = sel ? 1u : 0u;
            const uint32_t sinc = sycl::inclusive_scan_over_group(g, s1, sycl::plus<uint32_t>());
            const uint32_t stot = sycl::group_broadcast(g, sinc, WG - 1);
            if (sel && base + sinc - 1 < (uint32_t)outn) out[base + sinc - 1] = j + add;
            base += stot;
            eqseen += etot;
        }
        for (int i = (int)base + lid; i < outn; i += WG) out[i] = -1;
    }
};

// The top-k selects with every key loaded once into registers (OWN_TOPK_Q): item i takes the positions
// [i c, (i + 1) c), c = ceil(n / 1,024) rounded up to a multiple of 8 (at most MAXC), loads them 8 at a time and
// runs TopKSelP's four radix passes and TopKSelR's walk by ranges from its registers. The same threshold, the
// same ties (the lowest positions equal to it) and the same lists as TopKSelP / TopKSelR / TopKSelC, without
// TopKSelR's five passes over the scores in memory (2x faster from ~5,000 positions; slower below ~4,000:
// tools/bench/test_topk_q.cpp). qsel_span(n) <= MAXC must hold.
inline int qsel_span(int n) { return ((n + 1023) / 1024 + 7) / 8 * 8; }
// TopKSelP's threshold over the keys kr[m], m < MAXC with ok(m) (T = the k-th key, rem = how many keys equal to
// T are taken); hist / misc as TopKSelP's local memory
template <int MAXC, typename OK>
[[gnu::always_inline]] inline void qsel_threshold(sycl::nd_item<1> it, const uint32_t (&kr)[MAXC], OK ok, uint32_t k,
                                                  uint32_t *hist, uint32_t *misc, uint32_t &T, uint32_t &rem) {
    constexpr int WG = 1024, NSG = WG / 32;
    auto g = it.get_group();
    const int lid = (int)it.get_local_linear_id();
    const int sgi = (int)it.get_sub_group().get_group_linear_id();
    uint32_t prefix = 0, pmask = 0;
    rem = k;
    for (int pass = 0; pass < 4; ++pass) {
        const int shift = 24 - 8 * pass;
        for (int i = lid; i < NSG * 256; i += WG) hist[i] = 0;
        sycl::group_barrier(g);
#pragma unroll
        for (int m = 0; m < MAXC; ++m)
            if (ok(m) && (kr[m] & pmask) == prefix)
                sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::work_group,
                                 sycl::access::address_space::local_space>(hist[sgi * 256 + ((kr[m] >> shift) & 255u)])
                    .fetch_add(1u);
        sycl::group_barrier(g);
        uint32_t tot = 0; // item i < 256 holds bin 255 - i: the scan runs from the top bin down
        if (lid < 256)
            for (int s = 0; s < NSG; ++s) tot += hist[s * 256 + (255 - lid)];
        const uint32_t inc = sycl::inclusive_scan_over_group(g, tot, sycl::plus<uint32_t>());
        const uint32_t exc = inc - tot;
        if (lid < 256 && exc < rem && rem <= inc) {
            misc[0] = 255u - (uint32_t)lid;
            misc[1] = exc;
        }
        sycl::group_barrier(g);
        prefix |= misc[0] << shift;
        pmask |= 255u << shift;
        rem -= misc[1];
        sycl::group_barrier(g);
    }
    T = prefix;
}
// TopKSelR<false> (plain or masked rows) from registers
template <int MAXC> struct TopKSelQ {
    using KP = TopKSelP<false>;
    static constexpr int WG = KP::WG, NSG = KP::NSG, V = 8;
    KP p;
    void operator()(sycl::nd_item<1> it, const float *sc, const uint8_t *cand_in, int32_t *out, uint8_t *, float *lm) const {
        auto g = it.get_group();
        const int lid = (int)it.get_local_linear_id();
        uint32_t *hist = reinterpret_cast<uint32_t *>(lm), *misc = hist + NSG * 256;
        const int n = p.n;
        const bool all = p.k >= n;
        const int c = qsel_span(n), j0 = sycl::min(n, lid * c), cnt = sycl::min(n, j0 + c) - j0;
        const uint32_t KNEG = KP::okey(-INFINITY);
        const bool masked = cand_in != nullptr && p.cand_n > 0;
        uint32_t kr[MAXC];
#pragma unroll
        for (int v = 0; v < MAXC / V; ++v) {
            const int m0 = v * V;
            if (m0 < cnt) {
                if (m0 + V <= cnt) {
                    const auto x = *reinterpret_cast<const sycl::vec<float, V> *>(sc + j0 + m0);
                    sycl::vec<uint8_t, V> f(1);
                    if (masked) {
                        if (j0 + m0 + V <= p.cand_n) f = *reinterpret_cast<const sycl::vec<uint8_t, V> *>(cand_in + j0 + m0);
                        else
#pragma unroll
                            for (int u = 0; u < V; ++u) f[u] = j0 + m0 + u < p.cand_n ? cand_in[j0 + m0 + u] : 1;
                    }
#pragma unroll
                    for (int u = 0; u < V; ++u) kr[m0 + u] = f[u] ? KP::okey(x[u]) : KNEG;
                } else {
#pragma unroll
                    for (int u = 0; u < V; ++u) kr[m0 + u] = m0 + u < cnt ? KP::okey(p.val(sc, cand_in, j0 + m0 + u)) : 0u;
                }
            }
        }
        auto ok = [&](int m) { return m < cnt; };
        uint32_t T = 0, rem = 0;
        if (!all) qsel_threshold<MAXC>(it, kr, ok, (uint32_t)p.k, hist, misc, T, rem);
        uint32_t ngt = 0, neq = 0;
#pragma unroll
        for (int m = 0; m < MAXC; ++m)
            if (ok(m)) {
                ngt += (all || kr[m] > T) ? 1u : 0u;
                neq += (!all && kr[m] == T) ? 1u : 0u;
            }
        const uint32_t gtb = sycl::exclusive_scan_over_group(g, ngt, sycl::plus<uint32_t>());
        const uint32_t eqb = sycl::exclusive_scan_over_group(g, neq, sycl::plus<uint32_t>());
        uint32_t base = gtb + sycl::min(eqb, rem), eqs = eqb;
#pragma unroll
        for (int m = 0; m < MAXC; ++m)
            if (ok(m)) {
                const bool gt = all || kr[m] > T, eq = !all && kr[m] == T;
                const bool sel = gt || (eq && eqs < rem);
                if (eq) ++eqs;
                if (sel) {
                    if (base < (uint32_t)p.outn) out[base] = j0 + m + p.add;
                    ++base;
                }
            }
        const uint32_t tot = sycl::reduce_over_group(g, ngt, sycl::plus<uint32_t>()) +
                             sycl::min(sycl::reduce_over_group(g, neq, sycl::plus<uint32_t>()), rem);
        for (int i = (int)tot + lid; i < p.outn; i += WG) out[i] = -1;
    }
};
// TopKSelC (rwalk) from registers: position q = row bl[1 + q / 8] * 8 + q % 8 (bs = 8), c a multiple of 8, so
// item i's positions are whole blocks (one 8-float load each); rows at or past `rows` take no part. The same
// count of candidates above -inf first, and with fewer than k the same fallback (the masked TopKSelR<false> over
// all rows). Same local memory.
template <int MAXC> struct TopKSelCQ {
    static constexpr int WG = 1024, NSG = WG / 32, V = 8;
    int rows, k, add, outn;
    void operator()(sycl::nd_item<1> it, const float *sc, const uint8_t *cand, const int32_t *bl, int32_t *out,
                    float *lm) const {
        using KP = TopKSelP<false>;
        auto g = it.get_group();
        const int lid = (int)it.get_local_linear_id();
        uint32_t *hist = reinterpret_cast<uint32_t *>(lm), *misc = hist + NSG * 256;
        const uint32_t KNEG = KP::okey(-INFINITY);
        const int n = bl[0] * V; // candidate positions
        const int c = qsel_span(n), q0 = sycl::min(n, lid * c), cnt = sycl::min(n, q0 + c) - q0;
        uint32_t kr[MAXC];
        int nok[MAXC / V]; // block v of this item's range: its rows below `rows` (r0 .. r0 + nok[v])
#pragma unroll
        for (int v = 0; v < MAXC / V; ++v) {
            nok[v] = 0;
            if (v * V < cnt) {
                const int r0 = bl[1 + (q0 + v * V) / V] * V;
                nok[v] = sycl::clamp(rows - r0, 0, V);
                if (nok[v] == V) {
                    const auto x = *reinterpret_cast<const sycl::vec<float, V> *>(sc + r0);
#pragma unroll
                    for (int u = 0; u < V; ++u) kr[v * V + u] = KP::okey(x[u]);
                } else {
#pragma unroll
                    for (int u = 0; u < V; ++u) kr[v * V + u] = u < nok[v] ? KP::okey(sc[r0 + u]) : 0u;
                }
            }
        }
        auto ok = [&](int m) { return m % V < nok[m / V]; };
        uint32_t ca = 0;
#pragma unroll
        for (int m = 0; m < MAXC; ++m) ca += (ok(m) && kr[m] > KNEG) ? 1u : 0u;
        ca = sycl::reduce_over_group(g, ca, sycl::plus<uint32_t>());
        if (ca < (uint32_t)k) { // too few: the masked select over all rows (TopKSelC's fallback)
            TopKSelR<false>{KP{rows, k, add, outn, rows, 0, 0}}(it, sc, cand, out, nullptr, lm);
            return;
        }
        uint32_t T = 0, rem = 0;
        qsel_threshold<MAXC>(it, kr, ok, (uint32_t)k, hist, misc, T, rem);
        uint32_t ngt = 0, neq = 0;
#pragma unroll
        for (int m = 0; m < MAXC; ++m)
            if (ok(m)) {
                ngt += kr[m] > T ? 1u : 0u;
                neq += kr[m] == T ? 1u : 0u;
            }
        const uint32_t gtb = sycl::exclusive_scan_over_group(g, ngt, sycl::plus<uint32_t>());
        const uint32_t eqb = sycl::exclusive_scan_over_group(g, neq, sycl::plus<uint32_t>());
        uint32_t base = gtb + sycl::min(eqb, rem), eqs = eqb;
#pragma unroll
        for (int m = 0; m < MAXC; ++m)
            if (ok(m)) {
                const bool gt = kr[m] > T, eq = kr[m] == T;
                const bool sel = gt || (eq && eqs < rem);
                if (eq) ++eqs;
                if (sel) {
                    if (base < (uint32_t)outn) out[base] = bl[1 + (q0 + m) / V] * V + m % V + add;
                    ++base;
                }
            }
        const uint32_t tot = sycl::reduce_over_group(g, ngt, sycl::plus<uint32_t>()) +
                             sycl::min(sycl::reduce_over_group(g, neq, sycl::plus<uint32_t>()), rem);
        for (int i = (int)tot + lid; i < outn; i += WG) out[i] = -1;
    }
};
// TopKSelP<true> (the block select: block keys = the largest score of each block of 8 rows, folded in row
// order, the newest block +inf; mask rows and, with out, the flagged blocks in order) from registers: item i's
// blocks [i c, (i + 1) c), one 8-float load per block. TopKSelR<true>'s walk (with the flag count when the
// threshold is not above -inf). Same local memory.
template <int MAXC> struct TopKSelBQ {
    using KP = TopKSelP<true>;
    static constexpr int WG = KP::WG, NSG = KP::NSG, BS = 8;
    KP p; // n blocks, k, bs = 8, rows
    void operator()(sycl::nd_item<1> it, const float *sc, const uint8_t *, int32_t *out, uint8_t *cand_out, float *lm) const {
        auto g = it.get_group();
        const int lid = (int)it.get_local_linear_id();
        uint32_t *hist = reinterpret_cast<uint32_t *>(lm), *misc = hist + NSG * 256;
        const int n = p.n;
        const bool all = p.k >= n;
        const int c = qsel_span(n), j0 = sycl::min(n, lid * c), cnt = sycl::min(n, j0 + c) - j0;
        const uint32_t KNEG = KP::okey(-INFINITY);
        uint32_t kr[MAXC];
#pragma unroll
        for (int m = 0; m < MAXC; ++m)
            if (m < cnt) {
                const int j = j0 + m;
                float mx;
                if (j == n - 1) mx = INFINITY;
                else {
                    const int a = j * BS;
                    mx = -INFINITY; // std::max(m, v) per row, as the host folds it
                    if (a + BS <= p.rows) {
                        const auto x = *reinterpret_cast<const sycl::vec<float, BS> *>(sc + a);
#pragma unroll
                        for (int u = 0; u < BS; ++u) mx = mx < x[u] ? x[u] : mx;
                    } else {
                        for (int r = a; r < sycl::min(a + BS, p.rows); ++r) {
                            const float v = sc[r];
                            mx = mx < v ? v : mx;
                        }
                    }
                }
                kr[m] = KP::okey(mx);
            }
        auto ok = [&](int m) { return m < cnt; };
        uint32_t T = 0, rem = 0;
        if (!all) qsel_threshold<MAXC>(it, kr, ok, (uint32_t)p.k, hist, misc, T, rem);
        uint32_t ngt = 0, neq = 0;
#pragma unroll
        for (int m = 0; m < MAXC; ++m)
            if (ok(m)) {
                ngt += (all || kr[m] > T) ? 1u : 0u;
                neq += (!all && kr[m] == T) ? 1u : 0u;
            }
        const uint32_t gtb = sycl::exclusive_scan_over_group(g, ngt, sycl::plus<uint32_t>());
        const uint32_t eqb = sycl::exclusive_scan_over_group(g, neq, sycl::plus<uint32_t>());
        // flagged = selected and above -inf; with T > -inf every selected block is above it
        const bool flags_eq_sel = all ? false : T > KNEG;
        uint32_t fb = 0;
        if (out && !flags_eq_sel) { // count the flags per range first
            uint32_t eqs = eqb, nf = 0;
#pragma unroll
            for (int m = 0; m < MAXC; ++m)
                if (ok(m)) {
                    const bool gt = all || kr[m] > T, eq = !all && kr[m] == T;
                    const bool sel = gt || (eq && eqs < rem);
                    if (eq) ++eqs;
                    nf += (sel && kr[m] > KNEG) ? 1u : 0u;
                }
            fb = sycl::exclusive_scan_over_group(g, nf, sycl::plus<uint32_t>());
        } else {
            fb = gtb + sycl::min(eqb, rem);
        }
        uint32_t eqs = eqb, nf = 0;
#pragma unroll
        for (int m = 0; m < MAXC; ++m)
            if (ok(m)) {
                const int j = j0 + m;
                const bool gt = all || kr[m] > T, eq = !all && kr[m] == T;
                const bool sel = gt || (eq && eqs < rem);
                if (eq) ++eqs;
                const bool f = sel && kr[m] > KNEG;
                const int a = j * BS;
                if (a + BS <= p.rows) *reinterpret_cast<sycl::vec<uint8_t, BS> *>(cand_out + a) = sycl::vec<uint8_t, BS>(f ? 1 : 0);
                else
                    for (int r = a; r < sycl::min(a + BS, p.rows); ++r) cand_out[r] = f ? 1 : 0;
                if (out && f) out[1 + fb + nf] = j;
                nf += f ? 1u : 0u;
            }
        const uint32_t tot = sycl::reduce_over_group(g, nf, sycl::plus<uint32_t>());
        if (out && lid == 0) out[0] = (int32_t)tot;
    }
};

// ArgmaxP1 over a card's slice of the logits: indices are reported as
// off + i, and `none` (the full vocabulary size) when the span has no
// non-NaN value above -inf, exactly as ArgmaxP1 would for the full vector.
struct ArgmaxP1O {
    int n, ch, off, none;
    void operator()(sycl::nd_item<1> it, const float *logits, float *bvs, int32_t *bis) const {
        run(it.get_sub_group(), (int)it.get_group_linear_id(), logits, bvs, bis);
    }
    // span gi on one sub-group (also the multi-token form, ArgmaxP1OM)
    [[gnu::always_inline]] inline void run(sycl::sub_group sg, int gi, const float *logits, float *bvs, int32_t *bis) const {
        const int lane = (int)sg.get_local_linear_id();
        const int i0 = gi * ch, i1 = sycl::min(n, i0 + ch);
        float bv = -INFINITY;
        int bi = none;
        for (int i = i0 + lane; i < i1; i += 32) {
            const float v = logits[i];
            if (v > bv) { bv = v; bi = off + i; }
        }
        for (int w = 16; w; w >>= 1) {
            const float ov = sycl::select_from_group(sg, bv, lane ^ w);
            const int oi = sycl::select_from_group(sg, bi, lane ^ w);
            if (ov > bv || (ov == bv && oi < bi)) { bv = ov; bi = oi; }
        }
        if (lane == 0) { bvs[gi] = bv; bis[gi] = bi; }
    }
};

// ---- multi-token forms of the per-token small launches (backend_sycl_v41_mt.inc) ------------------
// Token t's pointers are the one-token pointers + t * stride (the block's per-token buffers are laid
// out at fixed strides); every item runs the one-token kernel's code on them, so every value is the
// one-token step's value. Tokens at or past m do nothing.
template <unsigned N, unsigned S> inline NormRows<N, S> tok_at(NormRows<N, S> r, unsigned t, const size_t *st) {
    r.x += t * st[0];
    r.y += t * st[1];
    return r;
}
template <typename A> inline RopeRows<A> tok_at(RopeRows<A> r, unsigned t, const size_t *st) {
    r.x += t * st[0];
    r.cosb += t * st[1]; // consecutive positions: 32 table entries apart
    r.sinb += t * st[1];
    return r;
}
template <unsigned H, unsigned SEG> inline HcDotsRows<H, SEG> tok_at(HcDotsRows<H, SEG> r, unsigned t, const size_t *st) {
    r.streams += t * st[0];
    r.out += t * st[1];
    return r;
}
inline HcFinishRows tok_at(HcFinishRows r, unsigned t, const size_t *st) {
    r.d += t * st[0];
    r.pre += t * st[1];
    r.post += t * st[2];
    r.comb += t * st[3];
    return r;
}
// m tokens of a rows type R (token-major: rows t * R::n() .. (t + 1) * R::n() - 1 are token t's)
template <typename R> struct TokRows {
    R r;
    unsigned m;
    size_t st[4];
    unsigned n() const { return m * r.n(); }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned i) const {
        const unsigned n0 = r.n();
        tok_at(r, i / n0, st).row(sg, lane, i % n0);
    }
};
// HcPostPreP for m tokens: items t * h .. (t + 1) * h - 1 are token t's (pre_src / pre_dst may be null)
template <typename A> struct HcPostPrePM {
    int h;
    unsigned m;
    size_t ss, xs, ps, cs, pss, pds, mxs, os; // per-token strides of the arguments, in order
    void operator()(sycl::nd_item<1> it, typename A::T *streams, const typename A::T *x, const float *post,
                    const float *comb, const float *pre_src, float *pre_dst, const float *mix,
                    typename A::T *out) const {
        const size_t g = it.get_global_linear_id();
        const unsigned t = (unsigned)(g / (size_t)h);
        if (t >= m) return;
        const int i = (int)(g % (size_t)h);
        streams += t * ss;
        x += t * xs;
        post += t * ps;
        comb += t * cs;
        if (pre_src) pre_src += t * pss;
        if (pre_dst) pre_dst += t * pds;
        mix += t * mxs;
        out += t * os;
        // HcPostPreP's expressions
        if (pre_dst && i < 4) pre_dst[i] = pre_src[i];
        float o[4];
        for (int k = 0; k < 4; ++k) o[k] = A::rd(streams[(size_t)k * h + i]);
        const float xi = A::rd(x[i]);
        float r[4];
        for (int j = 0; j < 4; ++j) {
            float acc = post[j] * xi;
            for (int k = 0; k < 4; ++k) acc += comb[k * 4 + j] * o[k];
            r[j] = acc;
        }
        typename A::T sv[4];
        for (int j = 0; j < 4; ++j) {
            sv[j] = A::wr(r[j]);
            streams[(size_t)j * h + i] = sv[j];
        }
        float acc = 0;
        for (int j = 0; j < 4; ++j) acc += mix[j] * A::rd(sv[j]);
        out[i] = A::wr(acc);
    }
};
// HcPostP for m tokens (HcPostP's expressions)
template <typename A> struct HcPostPM {
    int h;
    unsigned m;
    size_t ss, xs, ps, cs, pss, pds;
    void operator()(sycl::nd_item<1> it, typename A::T *streams, const typename A::T *x, const float *post,
                    const float *comb, const float *pre_src, float *pre_dst) const {
        const size_t g = it.get_global_linear_id();
        const unsigned t = (unsigned)(g / (size_t)h);
        if (t >= m) return;
        const int i = (int)(g % (size_t)h);
        streams += t * ss;
        x += t * xs;
        post += t * ps;
        comb += t * cs;
        if (pre_src) pre_src += t * pss;
        if (pre_dst) pre_dst += t * pds;
        if (pre_dst && i < 4) pre_dst[i] = pre_src[i];
        float o[4];
        for (int k = 0; k < 4; ++k) o[k] = A::rd(streams[(size_t)k * h + i]);
        const float xi = A::rd(x[i]);
        float r[4];
        for (int j = 0; j < 4; ++j) {
            float acc = post[j] * xi;
            for (int k = 0; k < 4; ++k) acc += comb[k * 4 + j] * o[k];
            r[j] = acc;
        }
        for (int j = 0; j < 4; ++j) streams[(size_t)j * h + i] = A::wr(r[j]);
    }
};
// HcPreA for m tokens
template <typename A> struct HcPreAM {
    int h;
    unsigned m;
    size_t ss, ms, os;
    void operator()(sycl::nd_item<1> it, const typename A::T *streams, const float *mix, typename A::T *out) const {
        const size_t g = it.get_global_linear_id();
        const unsigned t = (unsigned)(g / (size_t)h);
        if (t >= m) return;
        const int i = (int)(g % (size_t)h);
        streams += t * ss;
        mix += t * ms;
        out += t * os;
        float acc = 0;
        for (int j = 0; j < 4; ++j) acc += mix[j] * A::rd(streams[(size_t)j * h + i]);
        out[i] = A::wr(acc);
    }
};
// MoeCombineA for m tokens
template <typename A> struct MoeCombineAM {
    int top, h;
    unsigned m;
    size_t es, ss, os;
    void operator()(sycl::nd_item<1> it, const typename A::T *exps, const typename A::T *shared, typename A::T *out) const {
        const size_t g = it.get_global_linear_id();
        const unsigned t = (unsigned)(g / (size_t)h);
        if (t >= m) return;
        const int i = (int)(g % (size_t)h);
        exps += t * es;
        shared += t * ss;
        out += t * os;
        float acc = A::rd(shared[i]);
        for (int r = 0; r < top; ++r) acc += A::rd(exps[(size_t)r * h + i]);
        out[i] = A::wr(acc);
    }
};
// SwigluBothS for m tokens: items t * (rows + 1) * n .. are token t's
template <typename A> struct SwigluBothSM {
    int rows, n; float lim; int ostride;
    unsigned m;
    size_t gs, os, ps, sgs, sos; // gate / up, out, prob, shared gate / up, shared out
    void operator()(sycl::nd_item<1> it, const typename A::T *gate, const typename A::T *up, typename A::T *out,
                    const float *prob, const typename A::T *sgate, const typename A::T *sup, typename A::T *sout) const {
        const size_t per = (size_t)(rows + 1) * n, gg = it.get_global_linear_id();
        const unsigned t = (unsigned)(gg / per);
        if (t >= m) return;
        const int g_ = (int)(gg % per);
        gate += t * gs;
        up += t * gs;
        out += t * os;
        prob += t * ps;
        sgate += t * sgs;
        sup += t * sgs;
        sout += t * sos;
        if (g_ < rows * n) {
            const int r = g_ / n, i = g_ % n;
            float g = sycl::fmin(A::rd(gate[g_]), lim);
            float u = sycl::clamp(A::rd(up[g_]), -lim, lim);
            const typename A::T v = A::wr(g / (1.0f + sycl::exp(-g)) * u);
            out[(size_t)r * ostride + i] = A::wr(prob[r] * A::rd(v));
        } else {
            const int i = g_ - rows * n;
            float g = sycl::fmin(A::rd(sgate[i]), lim);
            float u = sycl::clamp(A::rd(sup[i]), -lim, lim);
            sout[i] = A::wr(g / (1.0f + sycl::exp(-g)) * u);
        }
    }
};
// RouteP for m tokens: work-group t (of 512 items) routes token t
struct RoutePM {
    RouteP k;
    size_t ls; // logits stride
    void operator()(sycl::nd_item<1> it, const float *logits, const float *bias, uint32_t *ids, float *prob,
                    float *lm) const {
        const size_t t = it.get_group_linear_id();
        k(it, logits + t * ls, bias, ids + t * (size_t)k.topk, prob + t * (size_t)k.topk, lm);
    }
};
// RoutePRows for m tokens: work-group t < m runs RouteP on token t (logits t * ls, ids / prob t * topk), the
// other work-groups run the sub-group rows (the FFN mix's finish and the shared expert's gate and up rows)
template <typename R> struct RoutePMRows {
    RouteP rp;
    size_t ls;
    unsigned m;
    R rows;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *logits, const float *bias, uint32_t *ids,
                                     float *prob, float *lm) const {
        const unsigned g = (unsigned)it.get_group_linear_id();
        if (g < m) {
            rp(it, logits + g * ls, bias, ids + (size_t)g * rp.topk, prob + (size_t)g * rp.topk, lm);
            return;
        }
        sycl::sub_group sg = it.get_sub_group();
        const unsigned r = (g - m) * (unsigned)(it.get_local_range(0) / 32) + sg.get_group_linear_id();
        if (r < rows.n()) rows.row(sg, sg.get_local_linear_id(), r);
    }
};
// EngramGateW for m tokens: work-group 4 * t + j is token t's stream j
template <unsigned S> struct EngramGateWM {
    EngramGateP k;
    unsigned m;
    size_t ss, ks;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, float *streams, const float *kvbuf, const float *gate_w,
                                     uint32_t *lm) const {
        const unsigned g = (unsigned)it.get_group_linear_id(), t = g / 4;
        if (t >= m) return;
        k.run_wg<S>(it, (int)(g % 4), streams + t * ss, kvbuf + t * ks, gate_w, lm);
    }
};
// EngramGateP for m tokens: sub-group (work-group) 4 * t + j is token t's stream j
struct EngramGatePM {
    EngramGateP k;
    unsigned m;
    size_t ss, ks;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, float *streams, const float *kvbuf, const float *gate_w) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned g = (unsigned)it.get_group_linear_id(), t = g / 4;
        if (t >= m) return;
        k.run(sg, (int)sg.get_local_linear_id(), (int)(g % 4), streams + t * ss, kvbuf + t * ks, gate_w);
    }
};

// The block's window rows and attention lists. Token t (position P = pos0 + t) stores its key row in the
// block area, ring row win + t (RingCommitM moves it to its ring slot after the layer's attention), and
// its list cat + t * cst names positions P - win + 1 .. P oldest first (WindowAppendP's order; -1 before
// position 0): rows before pos0 at their ring slot q % win, the block's in the block area; then the
// compressed list with its rows moved past the block area (+ mtx; the attention runs with win_rows =
// win + mtx). The same rows in the same order as the one-token lists.
template <typename A> struct WindowAppendM {
    int win, d, pos0, nc, m, mtx;
    size_t ks, cs, cst; // per-token strides: key row, compressed list, attention list
    void operator()(sycl::nd_item<1> it, uint16_t *ring, const typename A::T *kv, int32_t *cat,
                    const int32_t *cidx) const {
        const int per = sycl::max(d, win + nc);
        const int g = (int)it.get_global_linear_id(), t = g / per, i = g % per;
        if (t >= m) return;
        if (i < d) ring[(size_t)(win + t) * d + i] = ops41::bf16b(A::rd(kv[(size_t)t * ks + i]));
        int32_t *ct = cat + (size_t)t * cst;
        if (i < win) {
            const long q = (long)pos0 + t - (win - 1) + i;
            ct[i] = q < 0 ? -1 : (q >= pos0 ? win + (int)(q - pos0) : (int)(q % win));
        } else if (i < win + nc) {
            const int32_t v = cidx[(size_t)t * cs + (i - win)];
            ct[i] = v < 0 ? v : v + mtx;
        }
    }
};
// the block area's rows to their ring slots (after every token's attention of the layer). A block of more than
// win tokens commits its last win only: token t and t + win share slot (pos0 + t) % win, which one-token steps
// leave holding the later position (both writing it would race).
struct RingCommitM {
    int win, d, pos0, m;
    void operator()(sycl::nd_item<1> it, uint16_t *ring) const {
        const int g = (int)it.get_global_linear_id(), t = g / d, i = g % d;
        if (t >= m || t + win < m) return;
        ring[(size_t)((pos0 + t) % win) * d + i] = ring[(size_t)(win + t) * d + i];
    }
};
// RingCommitM for up to MAXR rings of the same shape in ONE launch (commit_pending, OWN_RING_ONE=1): items
// k * m * d .. (k + 1) * m * d - 1 move ring k's rows exactly as RingCommitM moves them (a copy: no arithmetic)
struct RingCommitN {
    static constexpr int MAXR = 48;
    int win, d, pos0, m, nr;
    uint16_t *r[MAXR];
    void operator()(sycl::nd_item<1> it) const {
        const size_t g = it.get_global_linear_id(), per = (size_t)m * (size_t)d;
        const int k = (int)(g / per);
        if (k >= nr) return;
        const int gg = (int)(g % per), t = gg / d, i = gg % d;
        if (t + win < m) return;
        uint16_t *ring = r[k];
        ring[(size_t)((pos0 + t) % win) * d + i] = ring[(size_t)(win + t) * d + i];
    }
};
// the attention kernels for m tokens: work-groups t * gpt .. (t + 1) * gpt - 1 run token t's groups of the
// one-token launch on token t's arrays (the one-token pointers + t * strides)
template <typename K> struct ScoreM {
    K k;
    unsigned gpt, m;
    size_t qs, is, ss;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *q, const uint16_t *kvw, const uint16_t *kvc,
                                     const int32_t *idxs, float *score) const {
        const unsigned grp = (unsigned)it.get_group_linear_id(), t = grp / gpt;
        if (t >= m) return;
        k.run(it.get_sub_group(), grp % gpt, q + t * qs, kvw, kvc, idxs + t * is, score + t * ss);
    }
};
template <typename K> struct SoftmaxM {
    K k;
    unsigned gpt, m;
    size_t is, ss;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *sinks, const int32_t *idxs, float *score) const {
        const unsigned grp = (unsigned)it.get_group_linear_id(), t = grp / gpt;
        if (t >= m) return;
        k.run(it.get_sub_group(), grp % gpt, sinks, idxs + t * is, score + t * ss);
    }
};
template <typename K> struct OutM {
    K k;
    unsigned gpt, m;
    size_t is, ws, os, rs; // lists, weights, out, ry (the rope tables move 32 per token)
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out) const {
        const unsigned grp = (unsigned)it.get_group_linear_id(), t = grp / gpt;
        if (t >= m) return;
        K k2 = k;
        if (k2.ry) {
            k2.ry += t * rs;
            k2.cosb += t * 32;
            k2.sinb += t * 32;
        }
        k2.run(it.get_sub_group(), grp % gpt, kvw, kvc, idxs + t * is, w + t * ws, out + t * os);
    }
};

// OutM for SparseOutJC (local memory; work-groups t * gpt .. are token t's, a whole work-group returns together)
template <typename K> struct OutMC {
    K k;
    unsigned gpt, m;
    size_t is, ws, os, rs;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out, uint32_t *lm) const {
        const unsigned grp = (unsigned)it.get_group_linear_id(), t = grp / gpt;
        if (t >= m) return;
        K k2 = k;
        if (k2.ry) {
            k2.ry += t * rs;
            k2.cosb += t * 32;
            k2.sinb += t * 32;
        }
        k2.run(it, grp % gpt, kvw, kvc, idxs + t * is, w + t * ws, out + t * os, lm);
    }
};

// ---- the block's index lists (backend_sycl_v41_mt.inc tpm_index): per-token row counts lens[t] ----------
// CidxFill for the tokens with lens[t] in [0, 512] (others: lens[t] < 0, left alone): list t at out + t * 512
struct CidxFillM {
    int lens[MT_MAX];
    unsigned m;
    void operator()(sycl::nd_item<1> it, int32_t *out) const {
        const unsigned g = (unsigned)it.get_global_linear_id(), t = g / 512, i = g % 512;
        if (t >= m || lens[t] < 0) return;
        out[(size_t)t * 512 + i] = (int)i < lens[t] ? (int)i + 128 : -1;
    }
};
// IndexerScoreB for every token with lens[t] > 0: work-groups t * gpt .. are token t's (rows j = (group %
// gpt) * WG + local id); its query, weights and scores at the one-token pointers + t * strides
template <typename A> struct IndexerScoreBM {
    int lens[MT_MAX];
    unsigned m, gpt;
    size_t qs, ws, ss;
    void operator()(sycl::nd_item<1> it, const typename A::T *q, const uint16_t *k, const typename A::T *w,
                    float *score, float *lq) const {
        const unsigned grp = (unsigned)it.get_group_linear_id(), t = grp / gpt;
        if (t >= m || lens[t] <= 0) return; // the whole work-group: before the kernel's barrier
        const int len = lens[t];
        const IndexerScoreB<A> kk{len, (len + 31) / 32 * 32};
        const int j = (int)((grp % gpt) * (unsigned)it.get_local_range(0) + (unsigned)it.get_local_linear_id());
        kk.run(it, j, q + t * qs, k, w + t * ws, score + t * ss, lq);
    }
};
// IndexerScoreBM with R rows per item (rows j, j + WG, ..., j + (R-1) WG of the group's R * WG): every query
// value read from shared memory serves R rows (IndexerScoreB reads one per product). Each row's 32 head sums
// take the same products in the same order (dims 0..127), then the same weighted sum over the heads: the same
// scores bit for bit. gpt = groups per token over R * WG rows.
template <typename A, int R> struct IndexerScoreBMR {
    static constexpr int H = 32, DK = 128, CH = 16;
    int lens[MT_MAX];
    unsigned m, gpt;
    size_t qs, ws, ss;
    void operator()(sycl::nd_item<1> it, const typename A::T *q, const uint16_t *k, const typename A::T *w,
                    float *score, float *lq) const {
        const unsigned grp = (unsigned)it.get_group_linear_id(), t = grp / gpt;
        if (t >= m || lens[t] <= 0) return; // the whole work-group: before the barrier
        const int len = lens[t], T_ = (len + 31) / 32 * 32;
        const int lid = (int)it.get_local_linear_id(), nl = (int)it.get_local_range(0);
        const typename A::T *qt = q + t * qs, *wt = w + t * ws;
        for (int i = lid; i < H * DK; i += nl) lq[i] = A::rd(qt[i]);
        for (int i = lid; i < H; i += nl) lq[H * DK + i] = A::rd(wt[i]);
        sycl::group_barrier(it.get_group());
        float *sc = score + t * ss;
        const int j0 = (int)(grp % gpt) * nl * R + lid;
        float d[R][H];
#pragma unroll
        for (int r = 0; r < R; ++r)
#pragma unroll
            for (int hh = 0; hh < H; ++hh) d[r][hh] = 0;
        for (int i0 = 0; i0 < DK; i0 += CH) {
            float kf[R][CH];
#pragma unroll
            for (int r = 0; r < R; ++r) {
                const int j = j0 + r * nl;
                const uint16_t *kr = k + (size_t)(j < len ? j : 0) * DK + i0;
#pragma unroll
                for (int ii = 0; ii < CH; ++ii) kf[r][ii] = ops41::bf16(kr[ii]);
            }
#pragma unroll
            for (int hh = 0; hh < H; ++hh)
#pragma unroll
                for (int ii = 0; ii < CH; ++ii) {
                    const float qv = lq[hh * DK + i0 + ii];
#pragma unroll
                    for (int r = 0; r < R; ++r) d[r][hh] += qv * kf[r][ii];
                }
        }
#pragma unroll
        for (int r = 0; r < R; ++r) {
            const int j = j0 + r * nl;
            if (j >= len) {
                if (j < T_) sc[j] = -INFINITY;
                continue;
            }
            float s = 0;
#pragma unroll
            for (int hh = 0; hh < H; ++hh) s += (d[r][hh] > 0 ? d[r][hh] : 0) * lq[H * DK + hh];
            sc[j] = s;
        }
    }
};
// TopKSelP for every token with lens[t] > 0, one work-group each. BLOCK (layer 20): n = blocks of 8 of
// lens[t] rows, the candidate mask to cand + t * cs. Else: n = lens[t], top 512 (+128) to out + t * 512,
// masked by cand + t * cs (cand_n = lens[t]) when mask.
template <bool BLOCK> struct TopKSelM {
    int lens[MT_MAX];
    unsigned m;
    bool mask;
    size_t ss, cs;
    size_t bls = 0; // BLOCK with out (OWN_IDX_CAND): token t's block list at out + t * bls (TopKSelP<true>'s out)
    bool rwalk = false; // OWN_TOPK_R, the plain / masked select only: TopKSelR (the final walk by ranges, the same lists)
    void operator()(sycl::nd_item<1> it, const float *sc, uint8_t *cand, int32_t *out, float *lm) const {
        const unsigned t = (unsigned)it.get_group_linear_id();
        if (t >= m || lens[t] <= 0) return;
        const int len = lens[t];
        if constexpr (BLOCK) {
            const TopKSelP<true> k{(len + 7) / 8, 2048, 0, 0, 0, 8, len};
            int32_t *o2 = out ? out + t * bls : (int32_t *)nullptr;
            k(it, sc + t * ss, (const uint8_t *)nullptr, o2, cand + t * cs, lm); // (TopKSelR<true> measured slower)
        } else {
            const TopKSelP<false> k{len, 512, 128, 512, mask ? len : 0, 0, 0};
            const uint8_t *ci = mask ? (const uint8_t *)(cand + t * cs) : (const uint8_t *)nullptr;
            if (rwalk) TopKSelR<false>{k}(it, sc + t * ss, ci, out + (size_t)t * 512, (uint8_t *)nullptr, lm);
            else k(it, sc + t * ss, ci, out + (size_t)t * 512, (uint8_t *)nullptr, lm);
        }
    }
};
// TopKSelM<false> with the mask, over each token's candidate rows (TopKSelC; OWN_IDX_CAND): token t's block list
// at bl + t * bls, its scores at sc + t * ss, its mask at cand + t * cs (cand_n == its rows), its list at out + 512 t
struct TopKSelMC {
    int lens[MT_MAX];
    unsigned m;
    size_t ss, cs, bls;
    bool rwalk = false; // OWN_TOPK_R (TopKSelC::rwalk)
    void operator()(sycl::nd_item<1> it, const float *sc, const uint8_t *cand, const int32_t *bl, int32_t *out,
                    float *lm) const {
        const unsigned t = (unsigned)it.get_group_linear_id();
        if (t >= m || lens[t] <= 0) return;
        const TopKSelC k{lens[t], 512, 128, 512, 8, rwalk};
        k(it, sc + t * ss, cand + t * cs, bl + t * bls, out + (size_t)t * 512, lm);
    }
};
// TopKSelM / TopKSelMC with the register selects (OWN_TOPK_Q; ss and cs multiples of 8): the plain / masked
// select by TopKSelQ<MAXC> (MAXC >= qsel_span of every token's rows), the block select by TopKSelBQ<MAXC> (of its
// blocks), the candidate select by TopKSelCQ<16>. The same lists.
template <int MAXC> struct TopKSelMQ {
    int lens[MT_MAX];
    unsigned m;
    bool mask;
    size_t ss, cs;
    void operator()(sycl::nd_item<1> it, const float *sc, uint8_t *cand, int32_t *out, float *lm) const {
        const unsigned t = (unsigned)it.get_group_linear_id();
        if (t >= m || lens[t] <= 0) return;
        const int len = lens[t];
        const TopKSelP<false> k{len, 512, 128, 512, mask ? len : 0, 0, 0};
        const uint8_t *ci = mask ? (const uint8_t *)(cand + t * cs) : (const uint8_t *)nullptr;
        TopKSelQ<MAXC>{k}(it, sc + t * ss, ci, out + (size_t)t * 512, (uint8_t *)nullptr, lm);
    }
};
template <int MAXC> struct TopKSelMBQ {
    int lens[MT_MAX];
    unsigned m;
    size_t ss, cs, bls = 0;
    void operator()(sycl::nd_item<1> it, const float *sc, uint8_t *cand, int32_t *out, float *lm) const {
        const unsigned t = (unsigned)it.get_group_linear_id();
        if (t >= m || lens[t] <= 0) return;
        const int len = lens[t];
        const TopKSelP<true> k{(len + 7) / 8, 2048, 0, 0, 0, 8, len};
        int32_t *o2 = out ? out + t * bls : (int32_t *)nullptr;
        TopKSelBQ<MAXC>{k}(it, sc + t * ss, (const uint8_t *)nullptr, o2, cand + t * cs, lm);
    }
};
struct TopKSelMCQ {
    int lens[MT_MAX];
    unsigned m;
    size_t ss, cs, bls;
    void operator()(sycl::nd_item<1> it, const float *sc, const uint8_t *cand, const int32_t *bl, int32_t *out,
                    float *lm) const {
        const unsigned t = (unsigned)it.get_group_linear_id();
        if (t >= m || lens[t] <= 0) return;
        TopKSelCQ<16>{lens[t], 512, 128, 512}(it, sc + t * ss, cand + t * cs, bl + t * bls, out + (size_t)t * 512, lm);
    }
};
// IndexerScoreBM over each token's layer-20 candidate rows (OWN_IDX_CAND): token t's gpt work-groups score its
// rows bl[t * bls + 1 + i / 8] * 8 + i % 8 with IndexerScoreB::run (IndexerScoreBC per token)
template <typename A> struct IndexerScoreBCM {
    int lens[MT_MAX];
    unsigned m, gpt;
    size_t qs, ws, ss, bls;
    void operator()(sycl::nd_item<1> it, const typename A::T *q, const uint16_t *k, const typename A::T *w,
                    float *score, const int32_t *bl, float *lq) const {
        const unsigned grp = (unsigned)it.get_group_linear_id(), t = grp / gpt;
        if (t >= m || lens[t] <= 0) return; // the whole work-group: before the kernel's barrier
        const int len = lens[t], T_ = (len + 31) / 32 * 32;
        const IndexerScoreB<A> kk{len, T_};
        const int i = (int)((grp % gpt) * (unsigned)it.get_local_range(0) + (unsigned)it.get_local_linear_id());
        const int32_t *b = bl + t * bls;
        int j = T_; // no row: run() writes nothing at or past T_
        if ((i >> 3) < b[0]) {
            const int r = b[1 + (i >> 3)] * 8 + (i & 7);
            if (r < len) j = r;
        }
        kk.run(it, j, q + t * qs, k, w + t * ws, score + t * ss, lq);
    }
};

// XchgP's push spread over many work-groups (a block of tokens moves nslot = M or 7M slots: one
// work-group pushing alone took most of the step); the same stores. XchgP with nslot 0 then releases,
// raises the flags and waits: the in-order queue starts it after every push here has been issued.
// The exchange by LOADS (2026-11-10): on this host a kernel's stores into a peer card's memory run at ~1 GB/s
// per card whatever the shape, while loads from a peer's memory run at 25-37 GB/s (all six cards at once,
// 20-64 work-groups; tools/bench/xchg_bw_bench.cpp). Every card leaves its rows in its own arena; the
// exchange publishes them (system-scope release, flag seq into every peer's flag word 16 * me, as XchgP),
// waits for every peer's flag, then copies each peer's rows [b0[d], b1[d]) of every slot from the peer's
// arena into its own (same offsets). Work-group 0 publishes; every work-group waits (one item polls) and
// copies a share. A card overwrites an exchange region only after a later exchange completed, and every
// peer raises that later flag only after its copy of the earlier rows (in-order queue), so no row is
// overwritten before all peers have read it. mode 0 publish + wait + copy, 1 publish only, 2 wait + copy.
struct XchgPull {
    int n, me;
    unsigned off, stride, nslot;
    unsigned b0[6], b1[6]; // every card's rows (multiples of 4)
    uint32_t seq;
    long spin;
    int mode = 0;
    void operator()(sycl::nd_item<1> it, float *p0, float *p1, float *p2, float *p3, float *p4, float *p5,
                    uint32_t *err) const {
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        const unsigned t = (unsigned)it.get_local_linear_id();
        float *mine = XchgP::pick(me, p0, p1, p2, p3, p4, p5);
        if (mode != 2 && it.get_group_linear_id() == 0) {
            sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
            sycl::group_barrier(it.get_group());
            if ((int)t < n && (int)t != me)
                AR(reinterpret_cast<uint32_t *>(XchgP::pick((int)t, p0, p1, p2, p3, p4, p5))[16 * me]).store(seq);
        }
        if (mode == 1) return;
        if ((int)t < n && (int)t != me) {
            AR poison(reinterpret_cast<uint32_t *>(mine)[96]);
            AR f(reinterpret_cast<uint32_t *>(mine)[16 * t]);
            long s = 0;
            if (!poison.load())
                while (f.load() < seq && ++s < spin) {}
            if (s >= spin) {
                poison.store(1u);
                err[0] = 1u + t;
            }
        }
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
        if (lb) copy_lb(it, n, me, off, stride, nslot, b0, b1, p0, p1, p2, p3, p4, p5);
        else copy_seq(it, n, me, off, stride, nslot, b0, b1, p0, p1, p2, p3, p4, p5);
    }
    int lb = 0; // copy_lb (OWN_XPULL_LB=1) or copy_seq (default: copy_lb measured slower, 8.1-9.5 vs 7.4-8.7 us, e81d)
    // copy: items over (peer, slot, vec4); peers in order 0..n-1 without me; item gid takes the indices k of peer d
    // with (base_d + k) % T == gid (base_d: the counts of the peers before d)
    // copy_seq: peer after peer (the default)
    static void copy_seq(sycl::nd_item<1> it, int n, int me, unsigned off, unsigned stride, unsigned nslot,
                         const unsigned *b0, const unsigned *b1, float *p0, float *p1, float *p2, float *p3,
                         float *p4, float *p5) {
        float *mine = XchgP::pick(me, p0, p1, p2, p3, p4, p5);
        const size_t T = it.get_global_range(0);
        size_t base = 0;
        for (int d = 0; d < n; ++d) {
            if (d == me) continue;
            const unsigned n4 = (b1[d] - b0[d]) / 4;
            const size_t cnt = (size_t)nslot * n4;
            const float *src = XchgP::pick(d, p0, p1, p2, p3, p4, p5) + off;
            float *dst = mine + off;
            const size_t gid = it.get_global_linear_id();
            size_t k0 = (gid + T - base % T) % T;
            for (size_t k = k0; k < cnt; k += T) {
                const size_t o = (size_t)(k / n4) * stride + b0[d] + (k % n4) * 4;
                *reinterpret_cast<sycl::vec<float, 4> *>(dst + o) = *reinterpret_cast<const sycl::vec<float, 4> *>(src + o);
            }
            base += cnt;
        }
    }
    // copy_lb: the same elements on the same items, in rounds: round r loads index k0_d + r * T of every peer
    // first, then stores them (tried 2026-11-10: slower; the copy's cost is one PCIe read round trip either way)
    static void copy_lb(sycl::nd_item<1> it, int n, int me, unsigned off, unsigned stride, unsigned nslot,
                        const unsigned *b0, const unsigned *b1, float *p0, float *p1, float *p2, float *p3,
                        float *p4, float *p5) {
        float *dst = XchgP::pick(me, p0, p1, p2, p3, p4, p5) + off;
        const size_t T = it.get_global_range(0), gid = it.get_global_linear_id();
        size_t k0[6], cnt[6];
        unsigned n4[6];
        size_t base = 0;
#pragma unroll
        for (int d = 0; d < 6; ++d) {
            const bool on = d < n && d != me;
            n4[d] = on ? (b1[d] - b0[d]) / 4 : 1u;
            cnt[d] = on ? (size_t)nslot * n4[d] : 0;
            k0[d] = (gid + T - base % T) % T;
            base += cnt[d];
        }
        for (size_t r = 0;; ++r) {
            sycl::vec<float, 4> v[6];
            size_t o[6];
            bool h[6], any = false;
#pragma unroll
            for (int d = 0; d < 6; ++d) {
                const size_t k = k0[d] + r * T;
                h[d] = k < cnt[d];
                o[d] = h[d] ? (size_t)(k / n4[d]) * stride + b0[d] + (k % n4[d]) * 4 : 0;
                if (h[d]) {
                    v[d] = *reinterpret_cast<const sycl::vec<float, 4> *>(XchgP::pick(d, p0, p1, p2, p3, p4, p5) + off + o[d]);
                    any = true;
                }
            }
            if (!any) break;
#pragma unroll
            for (int d = 0; d < 6; ++d)
                if (h[d]) *reinterpret_cast<sycl::vec<float, 4> *>(dst + o[d]) = v[d];
        }
    }
};

#ifdef OWN41_XWAIT
// XchgPull with the OWN_XWAIT record (see XchgPW; work-group 0 records)
struct XchgPullW {
    XchgPull x;
    uint32_t *xw;
    unsigned xk;
    void operator()(sycl::nd_item<1> it, float *p0, float *p1, float *p2, float *p3, float *p4, float *p5,
                    uint32_t *err) const {
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        const uint64_t ce = xw_clock();
        const int n = x.n, me = x.me;
        const unsigned t = (unsigned)it.get_local_linear_id();
        const bool rec = it.get_group_linear_id() == 0;
        float *mine = XchgP::pick(me, p0, p1, p2, p3, p4, p5);
        if (x.mode != 2 && it.get_group_linear_id() == 0) {
            sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
            sycl::group_barrier(it.get_group());
            if ((int)t < n && (int)t != me)
                AR(reinterpret_cast<uint32_t *>(XchgP::pick((int)t, p0, p1, p2, p3, p4, p5))[16 * me]).store(x.seq);
        }
        if (x.mode == 1) return;
        uint32_t *xr = xw + (size_t)xk * 16;
        if (rec && t == 0) xr[13] = xw_u32(xw_clock() - ce);
        if ((int)t < n && (int)t != me) {
            AR poison(reinterpret_cast<uint32_t *>(mine)[96]);
            AR f(reinterpret_cast<uint32_t *>(mine)[16 * t]);
            long s = 0;
            const uint64_t c0 = xw_clock();
            uint64_t c1 = c0;
            if (!poison.load())
                for (;;) { // XchgPull's polls, the clock after each one
                    const bool ok = f.load() >= x.seq;
                    c1 = xw_clock();
                    if (ok || ++s >= x.spin) break;
                }
            if (rec) {
                xr[t] = (uint32_t)s;
                xr[6 + t] = xw_u32(c1 - c0);
                xr[12] = 1u;
            }
            if (s >= x.spin) {
                poison.store(1u);
                err[0] = 1u + t;
            }
        }
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
        // XchgPull::copy_seq's copy, written out: a second caller of copy_seq / copy_lb changes the plain
        // XchgPull's machine code (checked 2026-11-11); copy_lb (OWN_XPULL_LB=1) is not recorded (Backend41::xchg)
        const size_t T = it.get_global_range(0), gid = it.get_global_linear_id();
        size_t base = 0;
        for (int d = 0; d < n; ++d) {
            if (d == me) continue;
            const unsigned n4 = (x.b1[d] - x.b0[d]) / 4;
            const size_t cnt = (size_t)x.nslot * n4;
            const float *src = XchgP::pick(d, p0, p1, p2, p3, p4, p5) + x.off;
            float *dst = mine + x.off;
            for (size_t k = (gid + T - base % T) % T; k < cnt; k += T) {
                const size_t o = (size_t)(k / n4) * x.stride + x.b0[d] + (k % n4) * 4;
                *reinterpret_cast<sycl::vec<float, 4> *>(dst + o) = *reinterpret_cast<const sycl::vec<float, 4> *>(src + o);
            }
            base += cnt;
        }
        if (rec && t == 0) xr[14] = xw_u32(xw_clock() - ce);
    }
};
#endif // OWN41_XWAIT

// XchgPull between a card and its one or two partners only (split attention groups, Backend41::oa_run): publish
// seq into each partner's flag word 16 * me, wait for each partner's flag, copy partner k's floats [b0[k], b1[k])
// of every slot (stride floats apart) from its arena into mine (same offsets). The other cards count the same
// exchange number without a launch, so every card's flags stay in step. Overwrite safety as XchgPull: a partner
// raises its next all-card flag only after its copy (in-order queue), and this card rewrites the rows only
// after that flag. mode 0 publish + wait + copy, 1 publish only, 2 wait + copy.
struct XchgPair {
    int np, me;
    int pd[2];
    unsigned b0[2], b1[2];
    unsigned off, stride, nslot;
    uint32_t seq;
    long spin;
    int mode = 0;
    void operator()(sycl::nd_item<1> it, float *p0, float *p1, float *p2, float *p3, float *p4, float *p5,
                    uint32_t *err) const {
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        const unsigned t = (unsigned)it.get_local_linear_id();
        float *mine = XchgP::pick(me, p0, p1, p2, p3, p4, p5);
        if (mode != 2 && it.get_group_linear_id() == 0) {
            sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
            sycl::group_barrier(it.get_group());
            if ((int)t < np)
                AR(reinterpret_cast<uint32_t *>(XchgP::pick(pd[t], p0, p1, p2, p3, p4, p5))[16 * me]).store(seq);
        }
        if (mode == 1) return;
        if ((int)t < np) {
            AR poison(reinterpret_cast<uint32_t *>(mine)[96]);
            AR f(reinterpret_cast<uint32_t *>(mine)[16 * pd[t]]);
            long s = 0;
            if (!poison.load())
                while (f.load() < seq && ++s < spin) {}
            if (s >= spin) {
                poison.store(1u);
                err[0] = 1u + (unsigned)pd[t];
            }
        }
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
        const size_t T = it.get_global_range(0), gid = it.get_global_linear_id();
        size_t base = 0;
        for (int k = 0; k < np; ++k) {
            const unsigned n4 = (b1[k] - b0[k]) / 4;
            const size_t cnt = (size_t)nslot * n4;
            const float *src = XchgP::pick(pd[k], p0, p1, p2, p3, p4, p5) + off;
            float *dst = mine + off;
            for (size_t i = (gid + T - base % T) % T; i < cnt; i += T) {
                const size_t o = (size_t)(i / n4) * stride + b0[k] + (i % n4) * 4;
                *reinterpret_cast<sycl::vec<float, 4> *>(dst + o) = *reinterpret_cast<const sycl::vec<float, 4> *>(src + o);
            }
            base += cnt;
        }
    }
};

struct XchgPushM {
    int n, me;
    unsigned off, stride, nslot, r0, r1;
    void operator()(sycl::nd_item<1> it, float *p0, float *p1, float *p2, float *p3, float *p4, float *p5) const {
        const float *own = XchgP::pick(me, p0, p1, p2, p3, p4, p5) + off;
        const unsigned n4 = (r1 - r0) / 4;
        const size_t T = it.get_global_range(0);
        for (size_t k = it.get_global_linear_id(); k < (size_t)nslot * n4; k += T) {
            const size_t o = (size_t)(k / n4) * stride + r0 + (k % n4) * 4;
            const sycl::vec<float, 4> v = *reinterpret_cast<const sycl::vec<float, 4> *>(own + o);
            for (int d = 0; d < n; ++d)
                if (d != me) *reinterpret_cast<sycl::vec<float, 4> *>(XchgP::pick(d, p0, p1, p2, p3, p4, p5) + off + o) = v;
        }
        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system); // as XchgP before its flags
    }
};
// XchgPushM with each work-group writing to one peer only (long runs of stores to one card): group g sends to
// peer g % (n - 1) (skipping me), chunk g / (n - 1) of gpp chunks; one release per work-group after a barrier
struct XchgPushD {
    int n, me;
    unsigned off, stride, nslot, r0, r1, gpp;
    void operator()(sycl::nd_item<1> it, float *p0, float *p1, float *p2, float *p3, float *p4, float *p5) const {
        const unsigned grp = (unsigned)it.get_group_linear_id(), np = (unsigned)n - 1;
        const unsigned di = grp % np, gi = grp / np, d = di < (unsigned)me ? di : di + 1;
        const float *own = XchgP::pick(me, p0, p1, p2, p3, p4, p5) + off;
        float *dst = XchgP::pick((int)d, p0, p1, p2, p3, p4, p5) + off;
        const unsigned n4 = (r1 - r0) / 4;
        const size_t L = it.get_local_range(0);
        for (size_t k = (size_t)gi * L + it.get_local_linear_id(); k < (size_t)nslot * n4; k += (size_t)gpp * L) {
            const size_t o = (size_t)(k / n4) * stride + r0 + (k % n4) * 4;
            *reinterpret_cast<sycl::vec<float, 4> *>(dst + o) = *reinterpret_cast<const sycl::vec<float, 4> *>(own + o);
        }
        sycl::group_barrier(it.get_group());
        if (it.get_local_linear_id() == 0) sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
    }
};

// ---- the block's compressor publish (backend_sycl_v41_mt.inc tpm_publish) -----------------------------
// ratio-2 states of the block: row 1 + t = token t's (f32, ToF32A's values), row 0 = the carried even state
// (kv_state / score_state slot 0) for a block that starts at an odd position
template <typename A> struct StatePackM {
    int hd;
    unsigned m;
    void operator()(sycl::nd_item<1> it, const typename A::T *cw, const typename A::T *scg, const float *kv0,
                    const float *sc0, float *mkv, float *msc) const {
        const size_t g = it.get_global_linear_id();
        const unsigned r = (unsigned)(g / (size_t)hd), i = (unsigned)(g % (size_t)hd);
        if (r > m) return;
        if (r == 0) {
            mkv[i] = kv0[i];
            msc[i] = sc0[i];
        } else {
            mkv[(size_t)r * hd + i] = A::rd(cw[(size_t)(r - 1) * hd + i]);
            msc[(size_t)r * hd + i] = A::rd(scg[(size_t)(r - 1) * hd + i]);
        }
    }
};
// CompressPoolP for the block's odd positions: work-group g pools state rows t, t + 1 (t = t0 + 2 g: token t's
// row and the one before it) into out + g * hd
template <typename A> struct CompressPoolPM {
    CompressPoolP<A> k;
    unsigned t0, np;
    void operator()(sycl::nd_item<1> it, const float *mkv, const float *msc, const float *nw, typename A::T *out,
                    float *tmp) const {
        const unsigned g = (unsigned)it.get_group_linear_id();
        if (g >= np) return;
        const size_t t = t0 + 2 * g;
        k(it, mkv + t * k.hd, msc + t * k.hd, nw, out + (size_t)g * k.hd, tmp);
    }
};
// PubAppendA for n published rows at rows row0 .. row0 + n - 1 (latent g at latent + g * hd, key at kk + g * ik)
template <typename A> struct PubAppendAM {
    int hd, ik, row0;
    unsigned n;
    void operator()(sycl::nd_item<1> it, const typename A::T *latent, const typename A::T *kk, uint16_t *ckv,
                    uint16_t *ikm) const {
        const int per = sycl::max(hd, ik);
        const size_t gg = it.get_global_linear_id();
        const unsigned g = (unsigned)(gg / (size_t)per);
        if (g >= n) return;
        const int i = (int)(gg % (size_t)per), row = row0 + (int)g;
        if (i < hd) ckv[(size_t)row * hd + i] = ops41::bf16b(A::rd(latent[(size_t)g * hd + i]));
        if (i < ik) ikm[(size_t)row * ik + i] = ops41::bf16b(A::rd(kk[(size_t)g * ik + i]));
    }
};

// ArgmaxP1O for m tokens: groups t * G .. (t + 1) * G - 1 scan token t's logits (logits + t * ls) into bvs /
// bis + t * G (the block's head for every token: draft checking)
struct ArgmaxP1OM {
    ArgmaxP1O k;
    unsigned G, m;
    size_t ls;
    void operator()(sycl::nd_item<1> it, const float *logits, float *bvs, int32_t *bis) const {
        const unsigned grp = (unsigned)it.get_group_linear_id(), t = grp / G;
        if (t >= m) return;
        k.run(it.get_sub_group(), (int)(grp % G), logits + t * ls, bvs + (size_t)t * G, bis + (size_t)t * G);
    }
};

// ==== expert-major routed rows (multi-token step, 2026-11-09) ============================================
// In a step of M tokens the routed kernels run 6M slots, and in blocks of 16 tokens only about half of the
// (block, layer) picks are distinct experts. The packed routed kernels (RoutedIQ2XXSP ... RoutedIQ1SP) are
// ALU-bound on decoding the IQ weights, so here a work item is (expert group u, row r [, matrix 2]): the
// sub-group decodes each block of the row once and runs every slot of the group through its own accumulator.
// Bit-identity with the slot-major kernels, slot by slot: the dequantized value v of (lane, block, element)
// does not depend on x and is formed by the same expression as there (RUFmt*::decode, copied operation for
// operation); each slot keeps its own accumulator `sum = sum + v * x` in the same block / element order on
// the same x values (the same addresses: x + (slot / 6) * xtok [+ (slot % 6) * NB * 256 when per_slot_x]),
// then the same xor butterfly, and lane 0 stores om[slot * rows + r].
//
// grp (uint32, RUGrp::WORDS words), written by ExpertGroupM from the slots' expert ids:
//   grp[0] = nu, the number of groups
//   grp[RUGrp::EXP + u] = the expert of group u, grp[RUGrp::CNT + u] = its slot count (1 .. cap)
//   grp[RUGrp::SLOT + 16 u + i] = its i-th slot (ascending), i < count
// An expert picked by more than cap slots gets ceil(count / cap) groups (cap = the MT of the kernel that reads
// grp; a token picks distinct experts, so with cap >= M every expert is one group). Group order: ascending first
// slot, or with ExpertGroupM::heavy slot count descending, then ascending first slot (the long groups first, so
// they do not form the tail of the routed kernels' position loop). The order does not change any output: every
// slot's output is written by exactly one group, and a slot's sum does not depend on its group.
struct RUGrp {
    // groups (>= the slots of the largest block: 6 per token, MT_MAX tokens; 128 as before up to 21 tokens),
    // slots per group. Only the word offsets below follow MAXU (the writer and every reader use them).
    static constexpr unsigned MAXU = 6 * MT_MAX > 128 ? 6 * MT_MAX : 128, CAP = 16;
    static constexpr unsigned EXP = 4, CNT = EXP + MAXU, SLOT = CNT + MAXU, WORDS = SLOT + MAXU * CAP;
};
// One work-group (launch: nd_range(items(nsl), items(nsl)), LM floats of local memory as the last argument, e.g.
// launch_local<ExpertGroupM::LM>(c, ExpertGroupM::items(nsl), ExpertGroupM{nsl, cap}, ids, grp)). Item i takes
// slots i, i + items, ... (SPI at most; one each up to 1,024 slots). Per slot one O(nsl) scan of the ids staged
// in local memory gives its occurrence index among the slots of its expert (before), the expert's total and the
// first slot of its chunk (head); per chunk head a second O(nsl) scan of the heads' counts gives its rank.
struct ExpertGroupM {
    // SMAX: the slots of the largest block (6 per token, MT_MAX tokens; 128 as before up to 21 tokens). Slots
    // >= nsl and items past them take no part, so the groups and their order depend on neither WG nor the items.
    static constexpr unsigned SMAX = 6 * MT_MAX > 128 ? 6 * MT_MAX : 128;
    static constexpr unsigned WG = SMAX <= 1024 ? (SMAX + 31) / 32 * 32 : 1024, SPI = (SMAX + WG - 1) / WG;
    static constexpr unsigned LM = 3 * SMAX; // ids, chunk counts (0: not a chunk head), head ranks
    static_assert(SMAX <= RUGrp::MAXU && SPI * WG >= SMAX, "a block's 6 M slots, at most one group each");
    unsigned nsl;        // slots, 1 .. SMAX
    unsigned cap = 16;   // slots per group at most, 1 .. RUGrp::CAP
    bool heavy = false;  // the group order (RUGrp): false = ascending first slot (as before); true = heaviest first
    // work-group size to launch for nsl slots: 128 up to 128 slots (the launch before blocks past 21 tokens),
    // else nsl in whole sub-groups, at most WG (local memory stays LM)
    static size_t items(unsigned nsl) {
        return nsl <= 128 ? 128 : (size_t)((nsl + 31) / 32 * 32 < WG ? (nsl + 31) / 32 * 32 : WG);
    }
    void operator()(sycl::nd_item<1> it, const uint32_t *ids, uint32_t *grp, float *lm) const {
        uint32_t *le = reinterpret_cast<uint32_t *>(lm), *lc = le + SMAX, *lr = lc + SMAX;
        const unsigned li = (unsigned)it.get_local_linear_id(), nl = (unsigned)it.get_local_range(0);
        const unsigned cap = this->cap < 1 ? 1u : this->cap > RUGrp::CAP ? RUGrp::CAP : this->cap;
        const unsigned ns = nsl < SMAX ? nsl : SMAX;
        for (unsigned s = li; s < ns; s += nl) le[s] = ids[s];
        sycl::group_barrier(it.get_group());
        unsigned before[SPI], head[SPI];
#pragma unroll
        for (unsigned k = 0; k < SPI; ++k) {
            const unsigned s = li + k * nl;
            before[k] = 0;
            head[k] = s;
            if (s >= ns) continue;
            const uint32_t e = le[s];
            unsigned bf = 0, total = 0, hd = s;
            for (unsigned j = 0; j < ns; ++j) {
                const bool eq = le[j] == e;
                if (eq && j < s) {
                    if (bf % cap == 0) hd = j; // occurrence `bf` of e starts a chunk
                    ++bf;
                }
                total += eq ? 1u : 0u;
            }
            if (bf % cap == 0) hd = s;
            const unsigned left = total - bf;
            lc[s] = bf % cap == 0 ? (left < cap ? left : cap) : 0u; // a chunk head: its group's slot count
            before[k] = bf;
            head[k] = hd;
        }
        sycl::group_barrier(it.get_group());
        unsigned mine = 0;
#pragma unroll
        for (unsigned k = 0; k < SPI; ++k) {
            const unsigned s = li + k * nl;
            if (s >= ns || lc[s] == 0) continue;
            const unsigned n = lc[s];
            unsigned rank = 0;
            for (unsigned j = 0; j < ns; ++j) {
                const unsigned cj = lc[j];
                rank += heavy ? (unsigned)(cj > n) | ((unsigned)(cj == n) & (unsigned)(j < s))
                              : (unsigned)(cj != 0) & (unsigned)(j < s);
            }
            lr[s] = rank;
            ++mine;
        }
        const unsigned nu = sycl::reduce_over_group(it.get_group(), mine, sycl::plus<unsigned>());
        sycl::group_barrier(it.get_group());
#pragma unroll
        for (unsigned k = 0; k < SPI; ++k) {
            const unsigned s = li + k * nl;
            if (s >= ns) continue;
            const unsigned u = lr[head[k]], i = before[k] % cap;
            grp[RUGrp::SLOT + u * RUGrp::CAP + i] = s;
            if (i == 0) {
                grp[RUGrp::EXP + u] = le[s];
                grp[RUGrp::CNT + u] = lc[s];
            }
        }
        if (li == 0) grp[0] = nu;
    }
};

// Per-format decode of one packed row for the expert-major kernels (used by RoutedU only). fill() = the
// original kernel's table fill; the constructor = its per-lane constants; load() = its per-row words and
// scales; decode(sg, blk, v) = v[g] for the 8 element groups g of block blk, the value the original
// multiplies by xv[g] (same operations in the same order).
template <unsigned NB_> struct RUFmtIQ2XXS { // RoutedIQ2XXSP
    static constexpr unsigned NB = NB_, TAB = 2048;
    static constexpr size_t RB = ((size_t)NB * 70 + 15) & ~(size_t)15;
    static constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NC = NB * 8, NCR = (NC + 31) / 32;
    static void fill(const sycl::nd_item<1> &it, float *tab) {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_xxs_grid, k >> 3, k & 7));
    }
    const char *tb;
    unsigned ssh, rot, j4;
    uint32_t wd[NR];
    float dbc[NCR];
    RUFmtIQ2XXS(unsigned lane, float *tab) {
        const unsigned l8 = lane >> 3, j = lane & 7u;
        ssh = 31u - 8u * l8 - j;
        rot = (37u - 8u * l8) & 31u;
        j4 = j << 2;
        tb = reinterpret_cast<const char *>(tab);
    }
    [[gnu::always_inline]] inline void load(sycl::sub_group sg, unsigned lane, const uint8_t *row) {
        const uint32_t *rw = reinterpret_cast<const uint32_t *>(row);
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) wd[k] = row_words<NW>(sg, rw, k, lane);
        chunk_scales<NB>(sg, lane, reinterpret_cast<const uint16_t *>(row + (size_t)NB * 68),
                         reinterpret_cast<const uint32_t *>(row + (size_t)NB * 64), 0.25f, dbc);
    }
    [[gnu::always_inline]] inline void decode(sycl::sub_group sg, unsigned blk, float (&v)[8]) const {
#pragma unroll
        for (unsigned g = 0; g < 8; ++g) {
            const unsigned wl = blk * 16 + 2 * g, wh = wl + 1, c = blk * 8 + g;
            const uint32_t lo = sycl::select_from_group(sg, wd[wl / 32], wl % 32);
            const uint32_t es = sycl::select_from_group(sg, wd[wh / 32], wh % 32);
            const float db = sycl::select_from_group(sg, dbc[c / 32], c % 32);
            const float mag = *reinterpret_cast<const float *>(tb + ((sycl::rotate(lo, rot) & 0x1FE0u) | j4));
            const uint32_t sb = (es << ssh) & 0x80000000u;
            v[g] = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ sb);
        }
    }
};
template <unsigned NB_> struct RUFmtIQ2S { // RoutedIQ2SP
    static constexpr unsigned NB = NB_, TAB = 8192;
    static constexpr size_t RB = ((size_t)NB * 82 + 15) & ~(size_t)15;
    static constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NC = NB * 8, NCR = (NC + 31) / 32;
    static void fill(const sycl::nd_item<1> &it, float *tab) {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_s_grid, k >> 3, k & 7));
    }
    const char *tb;
    unsigned lane, rot, qsh, j4, ssh;
    uint32_t wd[NR];
    float dbl[NCR], dbh[NCR];
    uint32_t qhc[NCR];
    RUFmtIQ2S(unsigned lane_, float *tab) : lane(lane_) {
        const unsigned l8 = lane >> 3, j = lane & 7u;
        rot = (37u - 8u * l8) & 31u;
        qsh = 13u - 2u * l8;
        j4 = j << 2;
        tb = reinterpret_cast<const char *>(tab);
        ssh = 31u - 8u * l8 - j;
    }
    [[gnu::always_inline]] inline void load(sycl::sub_group sg, unsigned, const uint8_t *row) {
        const uint32_t *rw = reinterpret_cast<const uint32_t *>(row);
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) wd[k] = row_words<NW>(sg, rw, k, lane);
        const uint8_t *meta = row + (size_t)NB * 64; // per block: qh[8], scales[8]
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 80);
#pragma unroll
        for (unsigned k = 0; k < NCR; ++k) {
            const unsigned c = 32 * k + lane < NC ? 32 * k + lane : NC - 1, b = c >> 3, g = c & 7u;
            const float d = iq3::half(dp[b]);
            const unsigned scb = meta[16 * b + 8 + g];
            qhc[k] = meta[16 * b + g];
            dbl[k] = (d * (0.5f + float(scb & 15u))) * 0.25f;
            dbh[k] = (d * (0.5f + float(scb >> 4))) * 0.25f;
        }
    }
    [[gnu::always_inline]] inline void decode(sycl::sub_group sg, unsigned blk, float (&v)[8]) const {
#pragma unroll
        for (unsigned g = 0; g < 8; ++g) {
            const unsigned c = blk * 8 + g, wl = blk * 16 + 2 * g, wh = wl + 1;
            const uint32_t lo = sycl::select_from_group(sg, wd[wl / 32], wl % 32);
            const uint32_t hi = sycl::select_from_group(sg, wd[wh / 32], wh % 32);
            const float dlo = sycl::select_from_group(sg, dbl[c / 32], c % 32);
            const float dhi = sycl::select_from_group(sg, dbh[c / 32], c % 32);
            const uint32_t qhb = sycl::select_from_group(sg, qhc[c / 32], c % 32);
            const float db = lane < 16 ? dlo : dhi;
            const float mag =
                *reinterpret_cast<const float *>(tb + ((sycl::rotate(lo, rot) & 0x1FE0u) | ((qhb << qsh) & 0x6000u) | j4));
            const uint32_t sb = (hi << ssh) & 0x80000000u;
            v[g] = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ sb);
        }
    }
};
// The group scale is kept per element group (dbg[NC / 32]: 5 registers at NB 20) instead of RoutedIQ3XXSP's
// per word (dbw[NR], valid only at the scale/sign words: 15 registers), so MT = 16 accumulators fit in 128
// registers. Same value: (half(d of block b) * (0.5 + (scale/sign word >> 28))) * 0.5 from the same word bits
// (read from the row by a per-lane load instead of picked out of wd).
template <unsigned NB_> struct RUFmtIQ3XXS { // RoutedIQ3XXSP
    static constexpr unsigned NB = NB_, TAB = 1024;
    static constexpr size_t RB = ((size_t)NB * 98 + 15) & ~(size_t)15;
    static constexpr unsigned NW = NB * 24, NR = (NW + 31) / 32, NC = NB * 8, NCR = (NC + 31) / 32;
    static void fill(const sycl::nd_item<1> &it, float *tab) {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float((iq3::iq3_grid[k >> 2] >> (8 * (k & 3))) & 255);
    }
    const char *tb;
    unsigned lane, rot, jj4;
    uint32_t smask;
    uint32_t wd[NR];
    float dbg[NCR]; // group c = 8 b + g: the scale of its scale/sign word 24 b + 3 g + 2
    RUFmtIQ3XXS(unsigned lane_, float *tab) : lane(lane_) {
        const unsigned l8 = lane >> 3, j = lane & 7u;
        rot = (36u - 8u * ((lane >> 2) & 3u)) & 31u;
        smask = j == 7 ? (127u << (7 * l8)) : (1u << (7 * l8 + j));
        jj4 = (lane & 3u) << 2;
        tb = reinterpret_cast<const char *>(tab);
    }
    [[gnu::always_inline]] inline void load(sycl::sub_group sg, unsigned, const uint8_t *row) {
        const uint32_t *rw = reinterpret_cast<const uint32_t *>(row);
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) wd[k] = row_words<NW>(sg, rw, k, lane);
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 96);
#pragma unroll
        for (unsigned k = 0; k < NCR; ++k) {
            const unsigned c = 32 * k + lane < NC ? 32 * k + lane : NC - 1, b = c >> 3, ws = b * 24 + 3 * (c & 7u) + 2;
            dbg[k] = (iq3::half(dp[b]) * (0.5f + float(rw[ws] >> 28))) * 0.5f;
        }
    }
    [[gnu::always_inline]] inline void decode(sycl::sub_group sg, unsigned blk, float (&v)[8]) const {
#pragma unroll
        for (unsigned g = 0; g < 8; ++g) {
            const unsigned w0 = blk * 24 + 3 * g, w1 = w0 + 1, ws = w0 + 2;
            const uint32_t q0 = sycl::select_from_group(sg, wd[w0 / 32], w0 % 32);
            const uint32_t q1 = sycl::select_from_group(sg, wd[w1 / 32], w1 % 32);
            const uint32_t sw = sycl::select_from_group(sg, wd[ws / 32], ws % 32);
            const unsigned c = blk * 8 + g;
            const float db = sycl::select_from_group(sg, dbg[c / 32], c % 32);
            const uint32_t q = lane < 16 ? q0 : q1;
            const float mag = *reinterpret_cast<const float *>(tb + ((sycl::rotate(q, rot) & 0xFF0u) | jj4));
            const uint32_t sb = uint32_t(sycl::popcount(sw & smask)) << 31;
            v[g] = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ sb);
        }
    }
};
template <unsigned NB_> struct RUFmtIQ2XS { // RoutedIQ2XSP
    static constexpr unsigned NB = NB_, TAB = 4096;
    static constexpr size_t RB = ((size_t)NB * 74 + 15) & ~(size_t)15;
    static constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NC = NB * 8, NCR = (NC + 31) / 32;
    static void fill(const sycl::nd_item<1> &it, float *tab) {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_xs_grid, k >> 3, k & 7));
    }
    const char *tb;
    unsigned lane, rot, j4;
    uint32_t smask;
    uint32_t wd[NR];
    float dbl[NCR], dbh[NCR];
    RUFmtIQ2XS(unsigned lane_, float *tab) : lane(lane_) {
        const unsigned l8 = lane >> 3, j = lane & 7u, hs = 16u * (l8 & 1u);
        rot = (5u - hs) & 31u;
        j4 = j << 2;
        tb = reinterpret_cast<const char *>(tab);
        smask = j == 7 ? (127u << (hs + 9)) : (1u << (hs + 9 + j));
    }
    [[gnu::always_inline]] inline void load(sycl::sub_group sg, unsigned, const uint8_t *row) {
        const uint32_t *rw = reinterpret_cast<const uint32_t *>(row);
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) wd[k] = row_words<NW>(sg, rw, k, lane);
        const uint8_t *scl = row + (size_t)NB * 64;
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 72);
#pragma unroll
        for (unsigned k = 0; k < NCR; ++k) {
            const unsigned c = 32 * k + lane < NC ? 32 * k + lane : NC - 1;
            const float d = iq3::half(dp[c >> 3]);
            const unsigned scb = scl[c]; // block c >> 3, group c & 7
            dbl[k] = (d * (0.5f + float(scb & 15u))) * 0.25f;
            dbh[k] = (d * (0.5f + float(scb >> 4))) * 0.25f;
        }
    }
    [[gnu::always_inline]] inline void decode(sycl::sub_group sg, unsigned blk, float (&v)[8]) const {
#pragma unroll
        for (unsigned g = 0; g < 8; ++g) {
            const unsigned c = blk * 8 + g, w0 = blk * 16 + 2 * g, w1 = w0 + 1;
            const uint32_t a0 = sycl::select_from_group(sg, wd[w0 / 32], w0 % 32);
            const uint32_t a1 = sycl::select_from_group(sg, wd[w1 / 32], w1 % 32);
            const float dlo = sycl::select_from_group(sg, dbl[c / 32], c % 32);
            const float dhi = sycl::select_from_group(sg, dbh[c / 32], c % 32);
            const uint32_t a = lane < 16 ? a0 : a1;
            const float db = lane < 16 ? dlo : dhi;
            const float mag = *reinterpret_cast<const float *>(tb + ((sycl::rotate(a, rot) & 0x3FE0u) | j4));
            const uint32_t sb = uint32_t(sycl::popcount(a & smask)) << 31;
            v[g] = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ sb);
        }
    }
};
// IQ1_S: v = dl * (code + delta), the factor RoutedIQ1SP multiplies by xv[g]
template <unsigned NB_, bool BYTES = true> struct RUFmtIQ1S { // RoutedIQ1SP<NB, A, BYTES>
    static constexpr unsigned NB = NB_, TAB = BYTES ? 4096 : 16384;
    static constexpr size_t RB = ((size_t)NB * 50 + 15) & ~(size_t)15;
    static constexpr unsigned NG = NB * 8, NW = NG, NR = (NW + 31) / 32;
    static void fill(const sycl::nd_item<1> &it, float *tab) {
        int8_t *btab = reinterpret_cast<int8_t *>(tab);
        for (unsigned k = it.get_local_linear_id(); k < 16384; k += (unsigned)it.get_local_range(0)) {
            const int8_t c = int8_t(uint8_t(grid64_byte(iq3::iq1_s_grid, k >> 3, k & 7)));
            if constexpr (BYTES) btab[k] = c;
            else tab[k] = float(int(c));
        }
    }
    const float *ftab;
    const int8_t *btab;
    unsigned lane, j, rot, qsh;
    uint32_t wd[NR]; // qs word of group k (block k >> 3)
    float dlr[NR], der[NR];
    uint32_t qhr[NR];
    RUFmtIQ1S(unsigned lane_, float *tab) : lane(lane_) {
        const unsigned l8 = lane >> 3;
        j = lane & 7u;
        rot = (35u - 8u * l8) & 31u; // qs byte l8 -> bits 3..10
        qsh = 11u - 3u * l8;         // qh bits 3*l8 .. 3*l8+2 -> bits 11..13
        ftab = tab;
        btab = reinterpret_cast<const int8_t *>(tab);
    }
    [[gnu::always_inline]] inline void load(sycl::sub_group sg, unsigned, const uint8_t *row) {
        const uint32_t *rw = reinterpret_cast<const uint32_t *>(row);
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) wd[k] = row_words<NW>(sg, rw, k, lane);
        const uint16_t *qh16 = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 32);
        const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 48);
#pragma unroll
        for (unsigned k = 0; k < NR; ++k) {
            const unsigned gi = 32 * k + lane < NG ? 32 * k + lane : NG - 1;
            const uint32_t qh = qh16[gi];
            qhr[k] = qh;
            dlr[k] = iq3::half(dp[gi >> 3]) * float(2 * ((qh >> 12) & 7) + 1);
            der[k] = (qh & 0x8000) ? -0.125f : 0.125f;
        }
    }
    [[gnu::always_inline]] inline void decode(sycl::sub_group sg, unsigned blk, float (&v)[8]) const {
#pragma unroll
        for (unsigned g = 0; g < 8; ++g) {
            const unsigned gi = blk * 8 + g;
            const uint32_t qs = sycl::select_from_group(sg, wd[gi / 32], gi % 32);
            const uint32_t qh = sycl::select_from_group(sg, qhr[gi / 32], gi % 32);
            const float dl = sycl::select_from_group(sg, dlr[gi / 32], gi % 32);
            const float de = sycl::select_from_group(sg, der[gi / 32], gi % 32);
            const unsigned a = (sycl::rotate(qs, rot) & 0x7F8u) | ((qh << qsh) & 0x3800u) | j;
            float code;
            if constexpr (BYTES) code = float(int(btab[a]));
            else code = ftab[a];
            v[g] = dl * (code + de);
        }
    }
};

// The expert-major routed kernel for format F (RUFmt*), up to MT slots per group (MT >= the cap ExpertGroupM
// was run with; MT <= 16). Members as the slot-major kernels: rows, per_slot_x, ex (extra rows spread through
// the launch as there), w2 / out2 (a second matrix of the same shape on the same groups: positions nu * rows ..
// 2 nu * rows - 1), xtok; nsl is not read (the positions come from grp[0]). Launch as the slot-major kernel,
// with grp in place of ids (the experts are in grp): launch_rows<K::TAB>(c, (w2 ? 2 : 1) * nsl * rows +
// ex.n(), maxwg, k, w, x, grp, out) (512 items, 16 sub-groups per work-group, TAB floats of local memory last;
// the sub-groups loop over the positions, so any grid size is correct).
// Per position: the row's words and scales once (F::load), then per block the 8 values once (F::decode) and
// for every slot i < count of the group that slot's 8 x values (the same sg_bloadN<8> of the same address as
// the slot-major kernel) into its own accumulator. Registers (AOT for BMG at 128 GRF, 2026-11-09): no spill
// at MT 6 and 8 for any format and NB, nor at MT 16 except IQ2_S NB 20 (320 B; slot-major IQ3_XXS NB 20: 256 B).
// SPT: slots per token (the target 6; the DSpark draft 3). A format with F::SGR sums each slot's lanes by
// sycl::reduce_over_group (the draft's RoutedMXFP4 sum) instead of the xor tree; with F::CLAMP_EXP an expert id
// at or past nexp reads expert 0 (as RoutedMXFP4: no read past the bank).
template <typename F, unsigned MT, typename EX = NoRows, unsigned SPT = 6> struct RoutedU {
    static_assert(MT >= 1 && MT <= RUGrp::CAP, "1 .. 16 slots per group");
    static constexpr unsigned TAB = F::TAB, NB = F::NB;
    unsigned rows; // per-expert rows
    bool per_slot_x;
    EX ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    unsigned nexp = 0; // F::CLAMP_EXP only
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *grp,
                                     float *out, float *tab) const {
        F::fill(it, tab);
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        F f(lane, tab);
        const unsigned nu = grp[0];
        const unsigned stride = (unsigned)(it.get_global_range(0) / 32);
        const unsigned nr_ = (w2 ? 2 : 1) * nu * rows, ne_ = ex.n(), nt_ = nr_ + ne_;
        for (unsigned p_ = packed_row_id(it); p_ < nt_; p_ += stride) {
            unsigned q_ = p_;
            if (ne_) { // extra rows spread as OWN41_ROUTED_ROWS_BEGIN
                const unsigned d0 = (unsigned)(((uint64_t)p_ * ne_ + nt_ - 1) / nt_);
                const unsigned d1 = (unsigned)(((uint64_t)(p_ + 1) * ne_ + nt_ - 1) / nt_);
                if (d1 > d0) {
                    ex.row(sg, lane, d0);
                    continue;
                }
                q_ = p_ - d1;
            }
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
            // lane i < cnt: slot i of the group and its x offset (broadcast per use)
            const uint32_t sl = lane < cnt ? grp[RUGrp::SLOT + u * RUGrp::CAP + lane] : 0u;
            const uint32_t xo = (sl / SPT) * xtok + (per_slot_x ? (sl % SPT) * (NB * 256) : 0u);
            unsigned eid = grp[RUGrp::EXP + u];
            if constexpr (requires { F::CLAMP_EXP; }) eid = eid < nexp ? eid : 0u;
            f.load(sg, lane, wm + ((size_t)eid * rows + r) * F::RB);
            float sum[MT];
#pragma unroll
            for (unsigned i = 0; i < MT; ++i) sum[i] = 0;
#pragma unroll
            for (unsigned blk = 0; blk < NB; ++blk) {
                float v[8];
                f.decode(sg, blk, v);
#pragma unroll
                for (unsigned i = 0; i < MT; ++i) {
                    if (i < cnt) {
                        const float *xs = x + sycl::select_from_group(sg, xo, i);
                        const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
#pragma unroll
                        for (unsigned g = 0; g < 8; ++g) sum[i] = sum[i] + v[g] * xv[g];
                    }
                }
            }
#pragma unroll
            for (unsigned i = 0; i < MT; ++i) {
                if (i < cnt) {
                    float s = sum[i];
                    if constexpr (requires { F::SGR; })
                        s = sycl::reduce_over_group(sg, s, sycl::plus<float>());
                    else
                        for (int w_ = 16; w_; w_ >>= 1) s += sycl::select_from_group(sg, s, (int)lane ^ w_);
                    const unsigned slot = sycl::select_from_group(sg, sl, i);
                    if (lane == 0) om[slot * rows + r] = s;
                }
            }
        }
    }
};
// The five packed formats (f32 activations, as the slot-major *P kernels). The backend runs RoutedIQ2XXSU ...
// RoutedIQ1SU (sycl_v41_routed_r2.hpp: RoutedU3 mostly, the same outputs bit for bit); these are RoutedU's own forms.
template <unsigned NB, unsigned MT> using RoutedIQ2XXSU0 = RoutedU<RUFmtIQ2XXS<NB>, MT>;
template <unsigned NB, unsigned MT> using RoutedIQ2SU0 = RoutedU<RUFmtIQ2S<NB>, MT>;
template <unsigned NB, unsigned MT> using RoutedIQ3XXSU0 = RoutedU<RUFmtIQ3XXS<NB>, MT>;
template <unsigned NB, unsigned MT> using RoutedIQ2XSU0 = RoutedU<RUFmtIQ2XS<NB>, MT>;
template <unsigned NB, unsigned MT, bool BYTES = true> using RoutedIQ1SU0 = RoutedU<RUFmtIQ1S<NB, BYTES>, MT>;

} // namespace ops41sycl
#endif
