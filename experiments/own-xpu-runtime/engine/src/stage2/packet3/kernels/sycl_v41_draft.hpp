// Kernels for the DSpark draft (DeepSeek V4.1 Flash's official dflash draft, Unsloth Q8_0 GGUF) on our engine.
// The draft only proposes tokens: the target checks every one (decode_verify_tp), so these kernels need to be
// right, not bit-identical to anything. They follow the draft's GGUF semantics (llama.cpp src/models/dflash.cpp,
// read for semantics only; credited in notes/2026-11-09-dsv41-multitoken-and-dspark-plan.md).
#pragma once
#include <sycl/sycl.hpp>
#include <cstdint>
#include "stage2/packet3/kernels/sycl_v41.hpp"

namespace ops41draft {

// MXFP4 block of 32: byte 0 = E8M0 scale, bytes 1..16 = nibbles (element j in the low nibble of byte 1 + j for
// j < 16, element j in the high nibble of byte 1 + j - 16). Value = d * e2m1(code) with the doubled e2m1 table
// (0,1,2,3,4,6,8,12) and the scale halved: d = 2^(e - 128), as packet2's math.hpp decode.
inline float mxfp4_d(unsigned e) {
    return sycl::bit_cast<float>(e < 2 ? 0x00200000u << e : (uint32_t)(e - 1) << 23);
}
inline float mxfp4_v(unsigned code) {
    const int mag = (int)((0xC8643210u >> (4 * (code & 7))) & 15);
    return (float)(code < 8 ? mag : (code > 8 ? -mag : 0));
}

// Routed experts in raw MXFP4 rows: one sub-group per (slot, row), lane l = element l of every block
// (coalesced 17-byte block reads, x[blk * 32 + l]); slots of a token: spt (the draft: 3), slot s reads
// x + (s / spt) * xtok (+ (s % spt) * cols when per_slot_x: the down projection's per-slot inputs).
// Rows of each expert on this card: rows (a tensor-parallel slice: the file rows [r0, r0 + rows) of every
// expert were uploaded, so expert e's slice starts at e * rows rows). w2/out2: a second matrix of the same
// shape in the same launch (positions nsl * rows .. 2 * nsl * rows - 1).
struct RoutedMXFP4 {
    unsigned rows, cols, nsl, spt, xtok;
    bool per_slot_x;
    unsigned nexp = 128; // ids at or past it (never from a sane router) read expert 0: no read past the bank
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids, float *out) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const unsigned nsg = (unsigned)(it.get_global_range(0) / 32);
        const unsigned nb = cols / 32;
        const size_t rb = (size_t)nb * 17;
        const unsigned np = (w2 ? 2u : 1u) * nsl * rows;
        for (unsigned p = (unsigned)(it.get_global_linear_id() / 32); p < np; p += nsg) {
            unsigned slot = p / rows;
            const unsigned r = p % rows;
            const uint8_t *wm = w;
            float *om = out;
            if (slot >= nsl) {
                slot -= nsl;
                wm = w2;
                om = out2;
            }
            const unsigned ex = ids[slot] < nexp ? ids[slot] : 0u;
            const uint8_t *row = wm + ((size_t)ex * rows + r) * rb;
            const float *xs = x + (size_t)(slot / spt) * xtok + (per_slot_x ? (size_t)(slot % spt) * cols : 0);
            const unsigned bi = 1u + (lane & 15u), sh = lane < 16 ? 0u : 4u;
            float sum = 0.0f;
            for (unsigned b = 0; b < nb; ++b) {
                const uint8_t *blk = row + (size_t)b * 17;
                const float d = mxfp4_d(blk[0]);
                const unsigned code = (blk[bi] >> sh) & 15u;
                sum += d * mxfp4_v(code) * xs[(size_t)b * 32 + lane];
            }
            sum = sycl::reduce_over_group(sg, sum, sycl::plus<float>());
            if (lane == 0) om[(size_t)slot * rows + r] = sum;
        }
    }
};

// The input feature of one target row for the draft: the mean of the 4 streams (weight 1/4 each, not the
// stream collapse) of the input of target layer L, written at feat + t * fs + li * h (li = 0, 1, 2 for
// layers 37, 38, 39). One item per element.
struct StreamMeanM {
    unsigned h, m, li;
    size_t ss, fs; // stream stride between tokens (4 h), feature stride (3 h)
    void operator()(sycl::nd_item<1> it, const float *streams, float *feat) const {
        const size_t g = it.get_global_linear_id();
        const unsigned t = (unsigned)(g / h), i = (unsigned)(g % h);
        if (t >= m) return;
        const float *s = streams + (size_t)t * ss;
        const float v = (s[i] + s[(size_t)h + i] + s[2 * (size_t)h + i] + s[3 * (size_t)h + i]) * 0.25f;
        feat[(size_t)t * fs + (size_t)li * h + i] = v;
    }
};

// The draft block's attention list: every block row sees the same keys, the stage's ring rows of positions
// pos0 - 128 .. pos0 - 1 (row p % 128; -1 before position 0), then the m block rows (ring rows 128 .. 128 + m
// - 1), then -1 up to n_idx. One list for all rows, written m times (the target's per-token list layout,
// stride ls).
struct DraftIdx {
    int pos0, m, n_idx;
    size_t ls;
    void operator()(sycl::nd_item<1> it, int32_t *idx) const {
        const int g = (int)it.get_global_linear_id(), t = g / n_idx, i = g % n_idx;
        if (t >= m) return;
        int v = -1;
        if (i < 128) {
            const int p = pos0 - 128 + i;
            v = p < 0 ? -1 : p % 128;
        } else if (i < 128 + m)
            v = i; // block row i - 128 at ring row i
        idx[(size_t)t * ls + i] = v;
    }
};

// The draft's key rows into a stage ring (BF16, rounded as the target's window rows): the block's rows at ring
// rows 128 + t (blk), injected target rows at their window slot (pos0 + t) % 128. One item per element.
template <typename A> struct DraftKvRows {
    unsigned hd, m;
    int pos0;
    bool blk;
    void operator()(sycl::nd_item<1> it, const typename A::T *kv, uint16_t *ring) const {
        const size_t g = it.get_global_linear_id();
        const unsigned t = (unsigned)(g / hd), i = (unsigned)(g % hd);
        if (t >= m) return;
        const size_t row = blk ? 128u + t : (size_t)((pos0 + (int)t) % 128);
        ring[row * hd + i] = ops41::bf16b(A::rd(kv[(size_t)t * hd + i]));
    }
};

// One draft row's best logit on this card from ArgmaxP1O's G candidates (largest value, then the smallest
// index, the same order-free comparison as the host's tp_argmax), as 4 floats [value, index bits, 0, 0] into
// this card's slot of a small exchange row. One sub-group.
struct DraftBest {
    unsigned G;
    void operator()(sycl::nd_item<1> it, const float *bvs, const int32_t *bis, float *slot) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        float bv = -INFINITY;
        int bi = 0x7fffffff;
        for (unsigned k = lane; k < G; k += 32) {
            const float ov = bvs[k];
            const int oi = bis[k];
            if (ov > bv || (ov == bv && oi < bi)) { bv = ov; bi = oi; }
        }
        for (unsigned w = 16; w; w >>= 1) {
            const float ov = sycl::select_from_group(sg, bv, lane ^ w);
            const int oi = sycl::select_from_group(sg, bi, lane ^ w);
            if (ov > bv || (ov == bv && oi < bi)) { bv = ov; bi = oi; }
        }
        if (lane == 0) {
            slot[0] = bv;
            slot[1] = sycl::bit_cast<float>(bi);
            slot[2] = slot[3] = 0.0f;
        }
    }
};
// The draft row's token from every card's slot (n cards, stride floats apart): prev[0] = the best index.
struct DraftPick {
    unsigned n, stride;
    void operator()(sycl::nd_item<1> it, const float *slots, int32_t *prev) const {
        if (it.get_global_linear_id() != 0) return;
        float bv = -INFINITY;
        int bi = 0x7fffffff;
        for (unsigned d = 0; d < n; ++d) {
            const float ov = slots[(size_t)d * stride];
            const int oi = sycl::bit_cast<int>(slots[(size_t)d * stride + 1]);
            if (ov > bv || (ov == bv && oi < bi)) { bv = ov; bi = oi; }
        }
        prev[0] = bi;
    }
};

// Markov bias for one draft row: y[r] = sum_k w2[r][k] * w1[prev][k] over this card's vocabulary rows (BF16
// rows of 256), added to the target head's logits row; one sub-group per row.
struct MarkovAdd {
    unsigned rows, vocab; // a token outside [0, vocab) (never from a sane chain) reads row 0
    void operator()(sycl::nd_item<1> it, const uint16_t *w2, const uint16_t *w1, const int32_t *prev, float *logits) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        const unsigned r = (unsigned)(it.get_global_linear_id() / 32);
        if (r >= rows) return;
        const int pv = prev[0];
        const uint16_t *a = w2 + (size_t)r * 256, *b = w1 + (size_t)(pv >= 0 && (unsigned)pv < vocab ? pv : 0) * 256;
        float sum = 0.0f;
        for (unsigned k = lane; k < 256; k += 32)
            sum += sycl::bit_cast<float>((uint32_t)a[k] << 16) * sycl::bit_cast<float>((uint32_t)b[k] << 16);
        sum = sycl::reduce_over_group(sg, sum, sycl::plus<float>());
        if (lane == 0) logits[r] += sum;
    }
};

} // namespace ops41draft
