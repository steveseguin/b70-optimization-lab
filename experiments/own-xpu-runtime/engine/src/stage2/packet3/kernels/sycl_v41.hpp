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
template <iq3::Type T>
[[gnu::always_inline]] inline float lane_sum_t(const uint8_t *row, const uint16_t *x, unsigned cols, unsigned lane) {
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
            const uint16_t *xb = x + (size_t)blk * 256 + lane;
            for (unsigned g = 0; g < 8; ++g) {
                const uint32_t lo = u32(b + 2 + 8 * g), hi = u32(b + 6 + 8 * g);
                const float db = (d * (0.5f + float(hi >> 28))) * 0.25f;
                const uint32_t mag = grid64_byte(iq3::iq2_xxs_grid, (lo >> (8 * l8)) & 255, j);
                const int sign = sign7_bit((hi >> (7 * l8)) & 127, j) ? -1 : 1;
                sum = sum + ((db * float(mag)) * float(sign)) * ops41::bf16(xb[g * 32]);
            }
        }
    } else if constexpr (T == iq3::Type::IQ2_XS) {
        for (unsigned blk = 0; blk < cols / 256; ++blk) {
            const uint8_t *b = row + (size_t)blk * 74;
            const float d = half(u16(b));
            const uint16_t *xb = x + (size_t)blk * 256 + lane;
            for (unsigned g = 0; g < 8; ++g) {
                const uint32_t a0 = u32(b + 2 + 8 * g), a1 = u32(b + 6 + 8 * g);
                const uint32_t aux = ((l8 < 2 ? a0 : a1) >> (16 * (l8 & 1))) & 0xffffu;
                const unsigned sc = (b[66 + g] >> (4 * (l8 >> 1))) & 15;
                const uint32_t mag = grid64_byte(iq3::iq2_xs_grid, aux & 511, j);
                const int sign = sign7_bit(aux >> 9, j) ? -1 : 1;
                sum = sum + ((((d * (0.5f + float(sc))) * 0.25f) * float(mag)) * float(sign)) * ops41::bf16(xb[g * 32]);
            }
        }
    } else if constexpr (T == iq3::Type::IQ1_S) {
        for (unsigned blk = 0; blk < cols / 256; ++blk) {
            const uint8_t *b = row + (size_t)blk * 50;
            const float d = half(u16(b));
            const uint16_t *xb = x + (size_t)blk * 256 + lane;
            for (unsigned g = 0; g < 8; ++g) {
                const uint32_t qh = u16(b + 34 + 2 * g);
                const float dl = d * float(2 * ((qh >> 12) & 7) + 1);
                const float delta = (qh & 0x8000) ? -0.125f : 0.125f;
                const uint32_t qs = u32(b + 2 + 4 * g);
                const unsigned ix = ((qs >> (8 * l8)) & 255) | (((qh >> (3 * l8)) & 7) << 8);
                const int code = int(int8_t(uint8_t(grid64_byte(iq3::iq1_s_grid, ix, j))));
                sum = sum + (dl * (float(code) + delta)) * ops41::bf16(xb[g * 32]);
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
            sum = sum + ((((d * (0.5f + float(sc))) * 0.25f) * float(mag)) * float(sign)) * ops41::bf16(x[(c << 5) | lane]);
        }
    } else if constexpr (T == iq3::Type::IQ3_XXS) {
        const unsigned l4 = lane >> 2;
        for (unsigned blk = 0; blk < cols / 256; ++blk) {
            const uint8_t *b = row + (size_t)blk * 98;
            const float d = half(u16(b));
            const uint16_t *xb = x + (size_t)blk * 256 + lane;
            for (unsigned g = 0; g < 8; ++g) {
                const uint32_t word = u32(b + 66 + 4 * g);
                const uint32_t code = (word >> (7 * l8)) & 127;
                const int sign = sign7_bit(code, j) ? -1 : 1;
                const uint32_t w0 = u32(b + 2 + 8 * g), w1 = u32(b + 6 + 8 * g);
                const unsigned gi = ((l4 < 4 ? w0 : w1) >> (8 * (l4 & 3))) & 255;
                const uint32_t mag = (iq3::iq3_grid[gi] >> (8 * (lane & 3))) & 255;
                sum = sum + ((((d * (0.5f + float(word >> 28))) * 0.5f) * float(mag)) * float(sign)) * ops41::bf16(xb[g * 32]);
            }
        }
    } else if constexpr (L.elements >= 32) {
        constexpr unsigned CPB = L.elements / 32; // chunks per block
        const unsigned chunks = cols / 32;
        for (unsigned c = 0; c < chunks; ++c) {
            const uint8_t *blk = row + (size_t)(c / CPB) * L.bytes;
            const unsigned i = ((c % CPB) << 5) | lane;
            sum = sum + dec_t<T>(blk, i) * ops41::bf16(x[(c << 5) | lane]);
        }
    } else {
        for (unsigned k = lane; k < cols; k += 32)
            sum = sum + dec_t<T>(row + (size_t)(k / L.elements) * L.bytes, k % L.elements) * ops41::bf16(x[k]);
    }
    return sum;
}
// reference form of the same lane sum (per-element iq3::decode); gates and benches compare against it
template <iq3::Type T>
[[gnu::always_inline]] inline float lane_sum_ref(const uint8_t *row, const uint16_t *x, unsigned cols, unsigned lane) {
    constexpr auto L = iq3::layout(T);
    float sum = 0;
    for (unsigned k = lane; k < cols; k += 32)
        sum = sum + iq3::decode(T, row + (size_t)(k / L.elements) * L.bytes, k % L.elements) * ops41::bf16(x[k]);
    return sum;
}
template <iq3::Type T> struct GemvT {
    unsigned rows, cols;
    bool f32out = false;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const uint16_t *x, void *yv) const {
        constexpr auto L = iq3::layout(T);
        const size_t rb = (size_t)(cols / L.elements) * L.bytes;
        auto sg = it.get_sub_group();
        unsigned l = sg.get_local_linear_id();
        unsigned r = it.get_group_linear_id();
        const uint8_t *row = w + (size_t)r * rb;
        float sum = lane_sum_t<T>(row, x, cols, l);
        sum = sg_tree32(sg, sum);
        if (l == 0) {
            if (f32out) reinterpret_cast<float *>(yv)[r] = sum;
            else reinterpret_cast<uint16_t *>(yv)[r] = ops41::bf16b(sum);
        }
    }
};
template <iq3::Type T> struct GemvGroupedQT {
    unsigned n, k;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const uint16_t *o, uint16_t *out) const {
        constexpr auto L = iq3::layout(T);
        const size_t rb = (size_t)(k / L.elements) * L.bytes;
        auto sg = it.get_sub_group();
        unsigned l = sg.get_local_linear_id();
        unsigned r = it.get_group_linear_id();
        const uint8_t *row = w + (size_t)r * rb;
        const uint16_t *xg = o + (size_t)(r / n) * k;
        float sum = lane_sum_t<T>(row, xg, k, l);
        sum = sg_tree32(sg, sum);
        if (l == 0) out[r] = ops41::bf16b(sum);
    }
};
template <iq3::Type T> struct RoutedGemvT {
    unsigned rows, cols; // per-expert matrix shape
    bool per_slot_x = false;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const uint16_t *x,
                                     const uint32_t *ids, uint16_t *out) const {
        constexpr auto L = iq3::layout(T);
        const size_t rb = (size_t)(cols / L.elements) * L.bytes;
        // slot/row from the GROUP id: uniform across the sub-group, so the row
        // pointer and everything loaded through it stays uniform (deriving
        // them from the global id made every load a per-lane gather)
        const unsigned grp = it.get_group_linear_id();
        const unsigned slot = grp / rows, r = grp % rows;
        if (slot >= 6) return;
        const uint8_t *row = w + ((size_t)ids[slot] * rows + r) * rb;
        sycl::sub_group sg = it.get_sub_group();
        int lane = it.get_local_linear_id();
        const uint16_t *xs = per_slot_x ? x + (size_t)slot * cols : x;
        float a = lane_sum_t<T>(row, xs, cols, (unsigned)lane);
        for (int w_ = 16; w_; w_ >>= 1)
            a += sycl::select_from_group(sg, a, lane ^ w_);
        if (lane == 0) out[slot * rows + r] = ops41::bf16b(a);
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

} // namespace ops41sycl
#endif
