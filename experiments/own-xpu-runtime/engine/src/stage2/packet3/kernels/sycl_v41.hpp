// SYCL device kernels for the DeepSeek V4.1 op set (plan_v41.hpp /
// ops_v41.hpp). Each kernel mirrors its ops41:: host anchor's equation and
// reduction order; pure mul/add paths are bit-exact vs host, paths through
// exp/sigmoid/silu admit +-1 bf16 ulp (device vs host libm), same rule as
// the SC117 identity-v2 gates.
#pragma once
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#include "stage2/packet2/kernels/math.hpp"
#include "stage2/packet3/kernels/ops_v41.hpp"
#include <sycl/ext/oneapi/experimental/prefetch.hpp>

namespace ops41sycl {
using iq3::Type;

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
template <typename A> struct EmbedRowA {
    iq3::Type t; int cols;
    void operator()(sycl::nd_item<1> it, const uint8_t *row, typename A::T *out) const {
        int i = it.get_global_linear_id();
        if (i >= cols) return;
        auto l = iq3::layout(t);
        out[i] = A::wr(iq3::decode(t, row + (size_t)(i / l.elements) * l.bytes, i % l.elements));
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
template <unsigned C> struct Q8Seg { static constexpr unsigned NQ = C / 4, v = NQ % 8 == 0 ? 8 : (NQ <= 10 ? NQ : 6); };
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
        constexpr unsigned NQ = C / 4, SEGQ = Q8Seg<C>::v, ND = (C + 31) / 32;
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
// most of the card idle). Tokens >= mt run on in-bounds data (G * ng <= MTX) and are not stored.
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
        constexpr unsigned NS = NB * 16, NSR = (NS + 31) / 32, SEG = KSeg<NB>::v;
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
        constexpr unsigned NS = NB * 16, NSR = (NS + 31) / 32, SEG = KSeg<NB>::v;
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
template <unsigned N, unsigned S> struct RmsNormPS {
    static_assert(N % 256 == 0);
    static constexpr unsigned C = N / 256;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *x, const float *w, float *y) const {
        sycl::sub_group sg = it.get_sub_group();
        part(sg, sg.get_local_linear_id(), sg.get_group_linear_id(), x, w, y);
    }
    // sub-group sgi of S: the whole sum (every sub-group forms it alike), then its share of the outputs;
    // no barrier between sub-groups, so the parts also run as rows of a fused launch (NormRows)
    [[gnu::always_inline]] static inline void part(sycl::sub_group sg, unsigned lane, unsigned sgi, const float *x,
                                                   const float *w, float *y) {
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
    unsigned n() const { return S; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r) const {
        RmsNormPS<N, S>::part(sg, lane, r, x, w, y);
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

// EngramGateA on 4 sub-groups (row j = group): lanes load 32 elements at a
// time and form the double products; the three sums run serially in element
// order on every lane from broadcast products (the same adds in the same
// order as the one-work-item loops); the final update is elementwise.
struct EngramGateP {
    int h; // % 32 == 0
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, float *streams, const float *kvbuf, const float *gate_w) const {
        sycl::sub_group sg = it.get_sub_group();
        const int j = (int)it.get_group_linear_id();
        if (j >= 4) return;
        run(sg, (int)sg.get_local_linear_id(), j, streams, kvbuf, gate_w);
    }
    // stream j on one sub-group (also the multi-token form, EngramGatePM)
    [[gnu::always_inline]] inline void run(sycl::sub_group sg, int lane, int j, float *streams, const float *kvbuf,
                                           const float *gate_w) const {
        const float eps = 1e-20f, clamp_v = 1e-6f;
        const float *sr = streams + (size_t)j * h, *kr = kvbuf + (size_t)j * h, *gr = gate_w + (size_t)j * h;
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
        const float rstd = float(1.0 / sycl::sqrt(hsq / h + eps) * (1.0 / sycl::sqrt(ksq / h + eps)));
        const float d = float(dot) * rstd / sycl::sqrt(float(h));
        const float g = 1.0f / (1.0f + sycl::exp(-sycl::copysign(sycl::sqrt(sycl::fmax(sycl::fabs(d), clamp_v)), d)));
        float *so = streams + (size_t)j * h;
        const float *vr = kvbuf + (size_t)4 * h;
        for (int i = lane; i < h; i += 32) so[i] = so[i] + g * vr[i];
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
struct RouteP {
    int experts, topk;
    void operator()(sycl::nd_item<1> it, const float *logits, const float *bias, uint32_t *ids, float *prob,
                    float *lm) const {
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
// the block area's rows to their ring slots (after every token's attention of the layer)
struct RingCommitM {
    int win, d, pos0, m;
    void operator()(sycl::nd_item<1> it, uint16_t *ring) const {
        const int g = (int)it.get_global_linear_id(), t = g / d, i = g % d;
        if (t >= m) return;
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

// ---- the block's index lists (backend_sycl_v41_mt.inc tpm_index): per-token row counts lens[t] ----------
// CidxFill for the tokens with lens[t] in [0, 512] (others: lens[t] < 0, left alone): list t at out + t * 512
struct CidxFillM {
    int lens[16];
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
    int lens[16];
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
// TopKSelP for every token with lens[t] > 0, one work-group each. BLOCK (layer 20): n = blocks of 8 of
// lens[t] rows, the candidate mask to cand + t * cs. Else: n = lens[t], top 512 (+128) to out + t * 512,
// masked by cand + t * cs (cand_n = lens[t]) when mask.
template <bool BLOCK> struct TopKSelM {
    int lens[16];
    unsigned m;
    bool mask;
    size_t ss, cs;
    void operator()(sycl::nd_item<1> it, const float *sc, uint8_t *cand, int32_t *out, float *lm) const {
        const unsigned t = (unsigned)it.get_group_linear_id();
        if (t >= m || lens[t] <= 0) return;
        const int len = lens[t];
        if constexpr (BLOCK) {
            const TopKSelP<true> k{(len + 7) / 8, 2048, 0, 0, 0, 8, len};
            k(it, sc + t * ss, (const uint8_t *)nullptr, (int32_t *)nullptr, cand + t * cs, lm);
        } else {
            const TopKSelP<false> k{len, 512, 128, 512, mask ? len : 0, 0, 0};
            k(it, sc + t * ss, mask ? (const uint8_t *)(cand + t * cs) : (const uint8_t *)nullptr, out + (size_t)t * 512,
              (uint8_t *)nullptr, lm);
        }
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
        // copy: items over (peer, slot, vec4); peers in order 0..n-1 without me
        const size_t T = it.get_global_range(0);
        size_t base = 0;
        for (int d = 0; d < n; ++d) {
            if (d == me) continue;
            const unsigned n4 = (b1[d] - b0[d]) / 4;
            const size_t cnt = (size_t)nslot * n4;
            const float *src = XchgP::pick(d, p0, p1, p2, p3, p4, p5) + off;
            float *dst = mine + off;
            // this item's indices k in [0, cnt) with (base + k) % T == global id
            const size_t gid = it.get_global_linear_id();
            size_t k0 = (gid + T - base % T) % T;
            for (size_t k = k0; k < cnt; k += T) {
                const size_t o = (size_t)(k / n4) * stride + b0[d] + (k % n4) * 4;
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
// grp; a token picks distinct experts, so with cap >= M every expert is one group). Group order is ascending
// first slot (it does not matter: every slot's output is written by exactly one group).
struct RUGrp {
    static constexpr unsigned MAXU = 128, CAP = 16; // groups (>= slots), slots per group
    static constexpr unsigned EXP = 4, CNT = EXP + MAXU, SLOT = CNT + MAXU, WORDS = SLOT + MAXU * CAP;
};
// One work-group of WG items (launch: nd_range(WG, WG), LM floats of local memory as the last argument, e.g.
// launch_local<ExpertGroupM::LM>(c, ExpertGroupM::WG, ExpertGroupM{nsl, cap}, ids, grp)). Item s = slot s:
// one O(nsl) scan of the ids staged in local memory gives its occurrence index among the slots of its expert
// (before), the expert's total and the first slot of its chunk (head); a work-group scan ranks the heads.
struct ExpertGroupM {
    static constexpr unsigned WG = 128, LM = 2 * WG;
    unsigned nsl;      // slots, 1 .. WG
    unsigned cap = 16; // slots per group at most, 1 .. RUGrp::CAP
    void operator()(sycl::nd_item<1> it, const uint32_t *ids, uint32_t *grp, float *lm) const {
        uint32_t *le = reinterpret_cast<uint32_t *>(lm), *lr = le + WG;
        const unsigned s = (unsigned)it.get_local_linear_id();
        const unsigned cap = this->cap < 1 ? 1u : this->cap > RUGrp::CAP ? RUGrp::CAP : this->cap;
        const bool on = s < nsl;
        const uint32_t e = on ? ids[s] : 0u;
        le[s] = e;
        sycl::group_barrier(it.get_group());
        unsigned before = 0, total = 0, head = s;
        if (on) {
            for (unsigned j = 0; j < nsl; ++j) {
                const bool eq = le[j] == e;
                if (eq && j < s) {
                    if (before % cap == 0) head = j; // occurrence `before` of e starts a chunk
                    ++before;
                }
                total += eq ? 1u : 0u;
            }
            if (before % cap == 0) head = s;
        }
        const bool first = on && before % cap == 0;
        const unsigned rank = sycl::exclusive_scan_over_group(it.get_group(), first ? 1u : 0u, sycl::plus<unsigned>());
        const unsigned nu = sycl::reduce_over_group(it.get_group(), first ? 1u : 0u, sycl::plus<unsigned>());
        if (first) lr[s] = rank;
        sycl::group_barrier(it.get_group());
        if (on) {
            const unsigned u = lr[head], i = before % cap;
            grp[RUGrp::SLOT + u * RUGrp::CAP + i] = s;
            if (first) {
                const unsigned left = total - before;
                grp[RUGrp::EXP + u] = e;
                grp[RUGrp::CNT + u] = left < cap ? left : cap;
            }
        }
        if (s == 0) grp[0] = nu;
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
template <typename F, unsigned MT, typename EX = NoRows> struct RoutedU {
    static_assert(MT >= 1 && MT <= RUGrp::CAP, "1 .. 16 slots per group");
    static constexpr unsigned TAB = F::TAB, NB = F::NB;
    unsigned rows; // per-expert rows
    bool per_slot_x;
    EX ex{};
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
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
            const uint32_t xo = (sl / 6) * xtok + (per_slot_x ? (sl % 6) * (NB * 256) : 0u);
            f.load(sg, lane, wm + ((size_t)grp[RUGrp::EXP + u] * rows + r) * F::RB);
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
                    for (int w_ = 16; w_; w_ >>= 1) s += sycl::select_from_group(sg, s, (int)lane ^ w_);
                    const unsigned slot = sycl::select_from_group(sg, sl, i);
                    if (lane == 0) om[slot * rows + r] = s;
                }
            }
        }
    }
};
// The five packed formats (f32 activations, as the slot-major *P kernels)
template <unsigned NB, unsigned MT> using RoutedIQ2XXSU = RoutedU<RUFmtIQ2XXS<NB>, MT>;
template <unsigned NB, unsigned MT> using RoutedIQ2SU = RoutedU<RUFmtIQ2S<NB>, MT>;
template <unsigned NB, unsigned MT> using RoutedIQ3XXSU = RoutedU<RUFmtIQ3XXS<NB>, MT>;
template <unsigned NB, unsigned MT> using RoutedIQ2XSU = RoutedU<RUFmtIQ2XS<NB>, MT>;
template <unsigned NB, unsigned MT, bool BYTES = true> using RoutedIQ1SU = RoutedU<RUFmtIQ1S<NB, BYTES>, MT>;

} // namespace ops41sycl
#endif
