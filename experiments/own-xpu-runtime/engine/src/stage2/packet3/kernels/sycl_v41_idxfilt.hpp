// idxfilt-1 (2026-11-17): a proven-bound pre-filter for the index scores at long context, on the matrix engines.
//
// The exact index score of a key row k for a token (IndexerScoreB's FP32 order) is
//     s = sum_h w_h * relu(d_h),   d_h = sum_i q_hi * k_i   (h = 0..31 heads, i = 0..127 dims),
// with every product and sum rounded to FP32 in a fixed order. The selects keep each token's top 512 rows (and at
// layer 20 the top 2048 blocks of 8 rows by their largest row score). Scoring every row exactly is ~4,096 FP32
// multiply-adds per row and token on the vector engines (the long-context cost). This file computes instead, on the
// matrix engines (DPAS), an approximate score s~ with the query split in two BF16 parts (q = hi + lo + r,
// |r| <= 2^-16 |q|; the key rows are BF16 already, so every product is exact) and a bound E with
//     |s(exact, FP32 order) - s~| <= E = C * ||k||_2 * ||a||_2,   a_i = sum_h |w_h| |q_hi|,
// C = 2e-4 (the FP32 rounding of the exact order: <= (gamma_129 + gamma_33) * B; the BF16 split: 2^-16 B; the
// matrix engine's sums taken as 4x worse than FP32's: 257 * 2^-22 B; the head sum of s~: gamma_33 B; total
// < 9e-5 B with B = sum_i |k_i| a_i <= ||k||_2 ||a||_2 (Cauchy-Schwarz); C = 2e-4 leaves a 2.2x margin, and the
// norms' own FP32 rounding (~1e-5 relative) is inside it).
//
// Why the picks stay the same, bit for bit: let LO = s~ - E <= s and HI = s~ + E >= s per row. Take L = the
// K-th largest LO (K = 512 rows, or 2048 block keys). At least K rows have s >= LO >= L, so the K-th largest exact
// score s_K >= L. A row with s >= s_K has HI >= s >= s_K >= L. So scoring exactly every row with HI >= L and leaving
// LO in the others (LO <= HI < L <= s_K: strictly below every row the select can keep, never tied with it) gives
// the select the same set (and the same ties) as all rows scored exactly. For blocks (key = largest row value):
// a block whose largest HI is below L_b (the 2048-th largest block LO key) has every row's value (LO or exact) and
// its exact key below s_2048; the blocks with a larger HI key get all 8 rows scored exactly, so their keys are exact.
//
// IdxFiltQ: per token (one work-group of 128 items), the query's BF16 hi / lo parts as the B matrices (row-major
// [128 dims][32 heads]) and the token's bound factor ac = C * ||a||_2 * (1 + 1e-4).
// IdxFiltS<RT>: rows [0, nr) of m tokens; each sub-group takes RT tiles of 8 rows (A: the key rows, 8 x 128 BF16 in
// eight 8 x 16 tiles kept in registers), per token two accumulators (heads 0-15, 16-31) of 8 k-steps x (hi, lo);
// the accumulators go through local memory to the lanes, which form s~ for the 8 rows; LO into the token's score
// row (rows past the token's length: -inf, as the exact kernels; rows past its next multiple of 32 untouched), the
// row norms (||k||_2, FP32) into n2 once (token 0).
// IdxFiltX: per token, after a select over the LO values (the unchanged select kernels; their outputs are rewritten
// by the second select): L = the smallest LO among the rows that select kept (the 512th largest LO), at layer 20
// Lb = the smallest block LO key among the flagged blocks (the block list; the newest block, kept at +inf, only
// lowers Lb: more rows scored, never fewer); then every row with HI >= L, and at layer 20 every row of a block with
// its largest HI >= Lb, gets its exact score (IndexerScoreB::run's sums in its order, bit for bit) in place of LO.
// Then the unchanged selects run again on the scores.
#pragma once
#include <sycl/sycl.hpp>
#include <cstdint>
#include "stage2/packet3/kernels/sycl_v41.hpp"

namespace ops41sycl {
namespace idxfilt {
namespace jm = sycl::ext::oneapi::experimental::matrix;
using bf16 = sycl::ext::oneapi::bfloat16;
inline constexpr float C2 = 2e-4f; // two BF16 passes (hi + lo)
inline constexpr float C1 = 1.0f / 128.0f; // one pass (hi only): 2^-8 + the rest, rounded up to 2^-7
// an absolute floor added to every bound: covers products or sums the matrix engines may flush to zero below 2^-126
// (at most 257 per head sum, each < 1.2e-38), far below any score that decides a select
inline constexpr float EABS = 1e-30f;
// nearest-even BF16 bits of a finite float
[[gnu::always_inline]] inline uint16_t bf16_rne(float f) {
    const uint32_t u = sycl::bit_cast<uint32_t>(f);
    return (uint16_t)((u + 0x7fffu + ((u >> 16) & 1u)) >> 16);
}
[[gnu::always_inline]] inline float bf16_f(uint16_t b) { return sycl::bit_cast<float>((uint32_t)b << 16); }
} // namespace idxfilt

// One work-group of 128 items per token t: item i = dim i. bh / bl: per token 128 x 32 BF16 words (row-major,
// [dim][head]); ac[t] = C * ||a||_2 * (1 + 1e-4) (C2 with two passes, C1 with one). q: token t at q + t * qs (head h's
// 128 values at h * 128), w: t * ws.
template <typename A> struct IdxFiltQ {
    static constexpr unsigned WG = 128;
    size_t qs = 4096, ws = 32;
    bool two = true;
    void operator()(sycl::nd_item<1> it, const typename A::T *q, const typename A::T *w, uint16_t *bh, uint16_t *bl,
                    float *ac) const {
        using namespace idxfilt;
        const unsigned t = (unsigned)it.get_group_linear_id(), i = (unsigned)it.get_local_linear_id();
        const typename A::T *qt = q + t * qs, *wt = w + t * ws;
        uint16_t *ht = bh + (size_t)t * 4096, *lt = bl + (size_t)t * 4096;
        float a = 0;
        for (unsigned h = 0; h < 32; ++h) {
            const float v = A::rd(qt[h * 128 + i]);
            const uint16_t hb = bf16_rne(v);
            const float r = v - bf16_f(hb); // exact (Sterbenz: hb within a factor 2 of v, same sign)
            ht[i * 32 + h] = hb;
            lt[i * 32 + h] = two ? bf16_rne(r) : (uint16_t)0;
            a += sycl::fabs(A::rd(wt[h])) * sycl::fabs(v);
        }
        const float a2 = sycl::reduce_over_group(it.get_group(), a * a, sycl::plus<float>());
        if (i == 0) ac[t] = (two ? C2 : C1) * sycl::sqrt(a2) * (1.0f + 1e-4f);
    }
};

// RT tiles of 8 rows per sub-group, 16 sub-groups per work-group (WG items); work-group g takes rows
// [g * 128 RT, (g + 1) * 128 RT). lens[t]: token t's rows (row >= lens[t]: -inf); the token's score row at
// sco + t * ss, written for rows < its next multiple of 32 only. n2: ||k||_2 per row (rows < nr; nr a multiple of 8).
// Local memory: 16 sub-groups x 2 x 128 floats (SLM floats). cm (optional): token t's largest LO of rows [8 i, 8 i + 8)
// at cm + t * cms + i (rows < nr; rows past the token's length count as -inf).
template <typename A, unsigned RT = 1> struct IdxFiltS {
    static constexpr unsigned WG = 256, NSG = WG / 16, ROWS = NSG * 8 * RT;
    static constexpr size_t SLM = (size_t)NSG * 2 * 128;
    LensT lens;
    unsigned m = 1, nr = 0;
    size_t ss = 0, ws = 32, cms = 0;
    bool two = true;
    float *cm = nullptr;
    void operator()(sycl::nd_item<1> it, const uint16_t *keys, const uint16_t *bh, const uint16_t *bl, const float *ac,
                    const typename A::T *w, float *sco, float *n2, float *lm) const {
        using namespace idxfilt;
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), g = sg.get_group_linear_id();
        float *cs = lm + (size_t)g * 256; // this sub-group's two 8 x 16 accumulators
        auto lcs = sycl::address_space_cast<sycl::access::address_space::local_space, sycl::access::decorated::no>(cs);
        const bf16 *kb = reinterpret_cast<const bf16 *>(keys);
        const bf16 *hb = reinterpret_cast<const bf16 *>(bh), *lb = reinterpret_cast<const bf16 *>(bl);
        const unsigned r = lane & 7u, hf = lane >> 3;
#pragma unroll 1
        for (unsigned rt = 0; rt < RT; ++rt) {
            const unsigned row0 = (unsigned)it.get_group_linear_id() * ROWS + (g * RT + rt) * 8u;
            if (row0 >= nr) break; // (uniform per sub-group)
            jm::joint_matrix<sycl::sub_group, bf16, jm::use::a, 8, 16, jm::layout::row_major> ma[8];
#pragma unroll
            for (unsigned k = 0; k < 8; ++k)
                jm::joint_matrix_load(sg, ma[k],
                                      sycl::address_space_cast<sycl::access::address_space::global_space,
                                                               sycl::access::decorated::no>(kb + (size_t)row0 * 128 + 16 * k),
                                      128);
            // ||k||_2 of row row0 + r: lanes r and r + 8 take 64 dims each
            const uint16_t *kr = keys + (size_t)(row0 + r) * 128 + 64 * hf;
            float sq = 0;
#pragma unroll 8
            for (unsigned i = 0; i < 64; ++i) {
                const float v = bf16_f(kr[i]);
                sq += v * v;
            }
            sq += sycl::permute_group_by_xor(sg, sq, 8u);
            const float nrm = sycl::sqrt(sq);
            if (hf == 0) n2[row0 + r] = nrm; // (every token's pass writes the same value; token 0's would do)
#pragma unroll 1
            for (unsigned t = 0; t < m; ++t) {
                const bf16 *ht = hb + (size_t)t * 4096, *lt = lb + (size_t)t * 4096;
#pragma unroll
                for (unsigned nt = 0; nt < 2; ++nt) {
                    jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16> acc;
                    jm::joint_matrix_fill(sg, acc, 0.0f);
#pragma unroll
                    for (unsigned k = 0; k < 8; ++k) {
                        jm::joint_matrix<sycl::sub_group, bf16, jm::use::b, 16, 16, jm::layout::row_major> mb;
                        jm::joint_matrix_load(sg, mb,
                                              sycl::address_space_cast<sycl::access::address_space::global_space,
                                                                       sycl::access::decorated::no>(ht + (size_t)k * 16 * 32 + 16 * nt),
                                              32);
                        jm::joint_matrix_mad(sg, acc, ma[k], mb, acc);
                        if (two) {
                            jm::joint_matrix_load(sg, mb,
                                                  sycl::address_space_cast<sycl::access::address_space::global_space,
                                                                           sycl::access::decorated::no>(lt + (size_t)k * 16 * 32 + 16 * nt),
                                                  32);
                            jm::joint_matrix_mad(sg, acc, ma[k], mb, acc);
                        }
                    }
                    jm::joint_matrix_store(sg, acc, lcs + 128 * nt, 16, jm::layout::row_major);
                }
                sycl::group_barrier(sg);
                // lane (r, hf): heads 8 hf .. 8 hf + 7 of both accumulators for row r
                const typename A::T *wt = w + t * ws;
                float part = 0;
#pragma unroll
                for (unsigned nt = 0; nt < 2; ++nt)
#pragma unroll
                    for (unsigned c = 0; c < 8; ++c) {
                        const float d = cs[128 * nt + r * 16 + 8 * hf + c];
                        part += (d > 0 ? d : 0.0f) * A::rd(wt[16 * nt + 8 * hf + c]);
                    }
                part += sycl::permute_group_by_xor(sg, part, 8u);
                const unsigned row = row0 + r;
                const int ln = lens[t];
                const unsigned len = ln > 0 ? (unsigned)ln : 0u, T32 = (len + 31u) / 32u * 32u;
                const float lo = row < len ? part - (ac[t] * nrm + EABS) : -INFINITY;
                if (hf == 0 && row < T32) sco[t * ss + row] = lo;
                if (cm) {
                    const float mx = sycl::reduce_over_group(sg, lo, sycl::maximum<float>());
                    if (lane == 0) cm[t * cms + row0 / 8u] = mx;
                }
                sycl::group_barrier(sg); // (the accumulators' local memory is rewritten next token)
            }
        }
    }
};

// One work-group per token t (WG items); local memory: the query and head weights as IndexerScoreB (32 x 128 + 32
// floats) + 64. list: the first row select's lists (token t's 512 entries at list + 512 t; v >= 128: row v - 128),
// bl: layer 20's first block select's lists (token t's at bl + t * bls: [0] count, [1 + i] block), else null.
template <typename A> struct IdxFiltX {
    static constexpr unsigned WG = 512, H = 32, DK = 128, CH = 16;
    static constexpr size_t SLM = (size_t)H * DK + H + 64;
    LensT lens;
    unsigned m = 1;
    size_t ss = 0, qs = 4096, ws = 32, bls = 2048 + 64;
    void operator()(sycl::nd_item<1> it, const typename A::T *q, const uint16_t *keys, const typename A::T *w,
                    const float *ac, const float *n2, const int32_t *list, const int32_t *bl, float *sco, float *lq) const {
        const unsigned t = (unsigned)it.get_group_linear_id(), lid = (unsigned)it.get_local_linear_id();
        if (t >= m) return;
        const int len = lens[t];
        if (len <= 0) return; // (uniform per work-group)
        auto grp = it.get_group();
        const typename A::T *qt = q + t * qs, *wt = w + t * ws;
        for (unsigned i = lid; i < H * DK; i += WG) lq[i] = A::rd(qt[i]);
        for (unsigned i = lid; i < H; i += WG) lq[H * DK + i] = A::rd(wt[i]);
        float *sc = sco + t * ss;
        // 1. L (the 512th largest LO) and Lb (the 2048th largest block LO key, layer 20)
        float mn = INFINITY;
        for (unsigned i = lid; i < 512; i += WG) {
            const int v = list[(size_t)t * 512 + i];
            if (v >= 128) mn = sycl::fmin(mn, sc[v - 128]);
        }
        const float L = sycl::reduce_over_group(grp, mn, sycl::minimum<float>());
        float mb = INFINITY;
        if (bl) {
            const int32_t *bt = bl + t * bls;
            const int nb = sycl::clamp((int)bt[0], 0, 2048);
            for (int i = (int)lid; i < nb; i += (int)WG) {
                const int b = bt[1 + i];
                float k = -INFINITY;
                for (int j = 0; j < 8; ++j)
                    if (8 * b + j < len) k = sycl::fmax(k, sc[8 * b + j]);
                mb = sycl::fmin(mb, k);
            }
        }
        const float Lb = bl ? sycl::reduce_over_group(grp, mb, sycl::minimum<float>()) : INFINITY;
        sycl::group_barrier(grp); // (every LO read above before any exact score replaces one)
        // 2. lane: blocks of 8 rows; a row with HI >= L, or a row of a block with its largest HI >= Lb: exact
        const float a2 = 2.0f * ac[t], e2 = 2.0f * idxfilt::EABS;
        for (int b = (int)lid; 8 * b < len; b += (int)WG) {
            float hi[8];
            float bm = -INFINITY;
#pragma unroll
            for (int j = 0; j < 8; ++j) {
                const int r = 8 * b + j;
                hi[j] = r < len ? sc[r] + (a2 * n2[r] + e2) : -INFINITY;
                bm = sycl::fmax(bm, hi[j]);
            }
            const bool blk = bm >= Lb;
#pragma unroll 1
            for (int j = 0; j < 8; ++j) {
                const int r = 8 * b + j;
                float hj = hi[0];
#pragma unroll
                for (int x = 1; x < 8; ++x) hj = j == x ? hi[x] : hj; // (constant indices only)
                if (r < len && (blk || hj >= L)) sc[r] = exact(keys + (size_t)r * DK, lq);
            }
        }
    }
    // IndexerScoreB::run's sums for one key row (heads in order, each head's 128 products in order; then the
    // weighted sum over heads in order), bit for bit
    [[gnu::always_inline]] static inline float exact(const uint16_t *kr, const float *lq) {
        float d[H];
#pragma unroll
        for (int hh = 0; hh < (int)H; ++hh) d[hh] = 0;
        for (int i0 = 0; i0 < (int)DK; i0 += CH) {
            float kf[CH];
#pragma unroll
            for (int ii = 0; ii < (int)CH; ++ii) kf[ii] = ops41::bf16(kr[i0 + ii]);
#pragma unroll
            for (int hh = 0; hh < (int)H; ++hh)
#pragma unroll
                for (int ii = 0; ii < (int)CH; ++ii) d[hh] += lq[hh * DK + i0 + ii] * kf[ii];
        }
        float s = 0;
#pragma unroll
        for (int hh = 0; hh < (int)H; ++hh) s += (d[hh] > 0 ? d[hh] : 0) * lq[H * DK + hh];
        return s;
    }
};

// idxfilt-2: the thresholds without a select on LO. One work-group (WG items, sub-groups of 32) per token t, over the
// token's n = ceil(len / 8) per-8-row maxima of LO (IdxFiltS's cm; each is the LO of one row, and the largest LO of one
// block of 8): thr[2 t] = the K-th largest of them, thr[2 t + 1] = the KB-th largest (blk; else +inf); -inf when n is
// below K (KB). Valid thresholds: the K-th largest of a subset of the rows' LO is at most the K-th largest LO of all
// rows, so at least K rows have LO >= thr[2 t] (and at least KB blocks a largest LO >= thr[2 t + 1]: the maxima of
// distinct 8-row groups are the keys' lower bounds of distinct blocks). The radix select is TopKSelP's (order keys,
// 4 passes of 8 bits, per-sub-group histograms); the threshold float is the order key's inverse (-0 comes back as +0,
// the same value). Local memory: NSG * 256 + 8 words.
template <unsigned K = 512, unsigned KB = 2048> struct IdxFiltT {
    static constexpr int WG = 1024, NSG = WG / 32;
    static constexpr size_t SLM = (size_t)NSG * 256 + 8;
    LensT lens;
    unsigned m = 1;
    size_t cms = 0;
    bool blk = false;
    static uint32_t okey(float f) {
        uint32_t u = sycl::bit_cast<uint32_t>(f);
        if (u == 0x80000000u) u = 0u;
        return (u & 0x80000000u) ? ~u : (u | 0x80000000u);
    }
    static float fkey(uint32_t k) { return sycl::bit_cast<float>((k & 0x80000000u) ? (k & 0x7fffffffu) : ~k); }
    static uint32_t kth(sycl::nd_item<1> it, const float *v, int n, uint32_t k, uint32_t *hist, uint32_t *misc) {
        auto g = it.get_group();
        const int lid = (int)it.get_local_linear_id();
        const int sgi = (int)it.get_sub_group().get_group_linear_id();
        uint32_t prefix = 0, pmask = 0, rem = k;
        for (int pass = 0; pass < 4; ++pass) {
            const int shift = 24 - 8 * pass;
            for (int i = lid; i < NSG * 256; i += WG) hist[i] = 0;
            sycl::group_barrier(g);
            for (int j = lid; j < n; j += WG) {
                const uint32_t kk = okey(v[j]);
                if ((kk & pmask) == prefix)
                    sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::work_group,
                                     sycl::access::address_space::local_space>(hist[sgi * 256 + ((kk >> shift) & 255u)])
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
        return prefix;
    }
    void operator()(sycl::nd_item<1> it, const float *cm, float *thr, float *lm) const {
        const unsigned t = (unsigned)it.get_group_linear_id();
        if (t >= m) return;
        const int len = lens[t];
        const int n = len > 0 ? (len + 7) / 8 : 0;
        uint32_t *hist = reinterpret_cast<uint32_t *>(lm), *misc = hist + NSG * 256;
        const float *v = cm + t * cms;
        float L = -INFINITY, Lb = blk ? -INFINITY : INFINITY;
        if (n >= (int)K) L = fkey(kth(it, v, n, K, hist, misc));
        if (blk && n >= (int)KB) Lb = fkey(kth(it, v, n, KB, hist, misc));
        if (it.get_local_linear_id() == 0) thr[2 * t] = L, thr[2 * t + 1] = Lb;
    }
};

// idxfilt-2: the exact scores where they can matter, spread over the card. Work-group (t, s) = token t's rows
// [s SR, (s + 1) SR), SR = 2048 BPL (WG 256; item i takes the blocks of 8 rows s SR / 8 + i + WG j, j < BPL). Row r <
// len[t] gets its exact score (IndexerScoreB::run's sums, bit for bit) when
//  - HI_r >= thr[2 t]: it may be among the kept rows (every row it could displace has s >= thr[2 t]), or
//  - its block's largest HI >= thr[2 t + 1] (the block may be kept) and HI_r >= the block's largest LO: it may hold
//    the block's largest score (that row has s >= its own LO >= ... >= the largest LO of the block). The block's key
//    (the largest of its 8 values) is then exact: every row that may reach it has its exact score, every other row
//    keeps LO <= HI < the largest LO <= the key.
// Every other row keeps LO, strictly below every value the selects can keep, so they keep the same rows, blocks and
// marks. The work-group gathers its rows (a group scan, row offsets as 16-bit words in local memory), loads the query
// as [dim][head] and the head weights, then each sub-group of 16 scores one listed row at a time: lane l the heads l
// and 16 + l, each over the 128 dims in order (the key values by shuffles), then the weighted sum over the 32 heads in
// order. ns: the slices per token (>= ceil(the longest row count / SR)). Local memory: SLM floats.
template <typename A, unsigned BPL = 2> struct IdxFiltX2 {
    static constexpr unsigned WG = 256, NSG = WG / 16, SR = 2048 * BPL, H = 32, DK = 128;
    static constexpr size_t SLM = (size_t)H * DK + H + SR / 2 + 8;
    static_assert(BPL >= 1 && BPL <= 4, "BPL: 1 to 4 (32 flag bits per item)");
    LensT lens;
    unsigned m = 1, ns = 1;
    size_t ss = 0, qs = 4096, ws = 32;
    void operator()(sycl::nd_item<1> it, const typename A::T *q, const uint16_t *keys, const typename A::T *w,
                    const float *ac, const float *n2, const float *thr, float *sco, float *lm) const {
        auto grp = it.get_group();
        const unsigned gi = (unsigned)it.get_group_linear_id(), t = gi / ns, s = gi % ns;
        const unsigned lid = (unsigned)it.get_local_linear_id();
        if (t >= m) return;
        const int len = lens[t];
        const int r0 = (int)(s * SR);
        if (len <= r0) return; // (uniform per work-group)
        float *sc = sco + t * ss;
        const float Lr = thr[2 * t], Lb = thr[2 * t + 1], a2 = 2.0f * ac[t], e2 = 2.0f * idxfilt::EABS;
        uint32_t fl = 0;
#pragma unroll
        for (unsigned j = 0; j < BPL; ++j) {
            const int base = r0 + 8 * (int)(lid + WG * j);
            float lo[8], hi[8];
            float bm = -INFINITY, bl = -INFINITY;
#pragma unroll
            for (int i = 0; i < 8; ++i) {
                const int r = base + i;
                lo[i] = r < len ? sc[r] : -INFINITY;
                hi[i] = r < len ? lo[i] + (a2 * n2[r] + e2) : -INFINITY;
                bm = sycl::fmax(bm, hi[i]);
                bl = sycl::fmax(bl, lo[i]);
            }
            const bool blk = bm >= Lb;
#pragma unroll
            for (int i = 0; i < 8; ++i)
                if (base + i < len && (hi[i] >= Lr || (blk && hi[i] >= bl))) fl |= 1u << (8 * j + i);
        }
        const uint32_t cnt = (uint32_t)sycl::popcount(fl);
        const uint32_t pos = sycl::exclusive_scan_over_group(grp, cnt, sycl::plus<uint32_t>());
        const uint32_t tot = sycl::reduce_over_group(grp, cnt, sycl::plus<uint32_t>());
        if (tot == 0) return; // (uniform)
        uint16_t *lst = reinterpret_cast<uint16_t *>(lm + H * DK + H);
        uint32_t p = pos;
#pragma unroll
        for (unsigned j = 0; j < BPL; ++j)
#pragma unroll
            for (unsigned i = 0; i < 8; ++i)
                if ((fl >> (8 * j + i)) & 1u) lst[p++] = (uint16_t)(8 * (lid + WG * j) + i);
        const typename A::T *qt = q + t * qs, *wt = w + t * ws;
        for (unsigned x = lid; x < H * DK; x += WG) lm[(x & (DK - 1)) * H + (x / DK)] = A::rd(qt[x]);
        for (unsigned x = lid; x < H; x += WG) lm[H * DK + x] = A::rd(wt[x]);
        sycl::group_barrier(grp);
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), sgi = sg.get_group_linear_id();
        for (unsigned e = sgi; e < tot; e += NSG) {
            const int r = r0 + (int)lst[e];
            const uint16_t *kr = keys + (size_t)r * DK;
            float d0 = 0, d1 = 0;
            for (unsigned i0 = 0; i0 < DK; i0 += 16) {
                const float kv = ops41::bf16(kr[i0 + lane]);
                const float *l0 = lm + (size_t)i0 * H + lane;
#pragma unroll
                for (unsigned ii = 0; ii < 16; ++ii) {
                    const float kf = sycl::select_from_group(sg, kv, ii);
                    d0 += l0[ii * H] * kf;
                    d1 += l0[ii * H + 16] * kf;
                }
            }
            float sum = 0;
#pragma unroll
            for (unsigned hh = 0; hh < H; ++hh) {
                const float v = sycl::select_from_group(sg, hh < 16 ? d0 : d1, hh & 15u);
                sum += (v > 0 ? v : 0) * lm[H * DK + hh];
            }
            if (lane == 0) sc[r] = sum;
        }
    }
};
// idxfilt-3 (OWN_IDX_FILT_SEL): TopKSelP over only the rows (layer 20's blocks: block keys) whose stored value is at
// least the filter's threshold, thr[2 t] (blocks: thr[2 t + 1]), after IdxFiltX2. The same lists, marks and block
// lists, bit for bit: every stored value is a row's exact score or its LO; a row left at LO has LO <= HI < thr <= s_K
// (the K-th largest exact score, IdxFiltT), and a rescored row below thr is below s_K too. So the K largest stored
// values are the K largest exact scores, all >= thr: the k-th key T, the number of keys above it and the keys equal
// to it are the same over these rows as over all rows, and no other row is above or equal to T. Blocks: a block left
// unrefined (largest HI < thr[2 t + 1]) has a stored key <= its largest HI below the threshold; the KB blocks with the
// largest exact keys were refined (their keys exact, >= the threshold). The walk keeps TopKSelP's order (ascending
// index, the first by index of the keys equal to T), since the entries are gathered in index order.
// Pass 1 reads the token's values once (coalesced: sub-group s of a span of WG PER takes 32 PER consecutive rows,
// lane l row 32 q + l of them) and gathers (order key, index) of the passing rows into local memory (CAP entries;
// sub-group scans and one group scan per span keep index order); then TopKSelP's four radix passes and its final walk
// run over the entries. Blocks: the kept blocks as bits in local memory (the histogram's words), then every row's mark
// written once from them. More than CAP passing rows (or k >= n, fewer than k entries, which the bound rules out, or
// more blocks than the bits hold): the full TopKSelP. Sub-groups of 32 (as TopKSelP). Local memory: SLM words.
template <bool BLOCK, unsigned CAP = 4096> struct TopKSelF {
    static constexpr int WG = 1024, NSG = WG / 32, SGS = 32;
    static constexpr size_t SLM = (size_t)NSG * 256 + 8 + 2 * (size_t)CAP;
    LensT lens;
    unsigned m = 1;
    size_t ss = 0, cs = 0;
    size_t bls = 0; // BLOCK with out (OWN_IDX_CAND): token t's block list at out + t * bls
    static uint32_t okey(float f) { return TopKSelP<BLOCK>::okey(f); }
    void operator()(sycl::nd_item<1> it, const float *sc, const float *thr, uint8_t *cand, int32_t *out, float *lm) const {
        const unsigned t = (unsigned)it.get_group_linear_id();
        if (t >= m || lens[t] <= 0) return;
        const int len = lens[t];
        auto g = it.get_group();
        auto sg = it.get_sub_group();
        const int lid = (int)it.get_local_linear_id();
        const int sgi = (int)sg.get_group_linear_id(), sl = (int)sg.get_local_linear_id();
        const float *s = sc + t * ss;
        uint8_t *cd = BLOCK ? cand + t * cs : (uint8_t *)nullptr;
        int32_t *o = BLOCK ? (out ? out + t * bls : (int32_t *)nullptr) : out + (size_t)t * 512;
        const TopKSelP<BLOCK> p = BLOCK ? TopKSelP<BLOCK>{(len + 7) / 8, 2048, 0, 0, 0, 8, len}
                                        : TopKSelP<BLOCK>{len, 512, 128, 512, 0, 0, 0};
        const int n = p.n;
        const float th = thr[2 * t + (BLOCK ? 1 : 0)];
        uint32_t *hist = reinterpret_cast<uint32_t *>(lm), *misc = hist + NSG * 256, *ek = misc + 8;
        int32_t *ej = reinterpret_cast<int32_t *>(ek + CAP);
        if (p.k >= n || (BLOCK && n > NSG * 256 * 32)) return p(it, s, (const uint8_t *)nullptr, o, cd, lm);
        // pass 1: the rows (blocks) with a value >= th, in index order
        constexpr int PER = BLOCK ? 4 : 16;
        uint32_t ne = 0; // (the same in every item)
        for (int c0 = 0; c0 < n; c0 += WG * PER) {
            const int sb = c0 + sgi * (SGS * PER);
            float v[PER];
            uint32_t off[PER], cnt = 0;
#pragma unroll
            for (int q = 0; q < PER; ++q) {
                const int j = sb + q * SGS + sl;
                v[q] = j < n ? p.val(s, (const uint8_t *)nullptr, j) : -INFINITY;
                const uint32_t f = (j < n && v[q] >= th) ? 1u : 0u;
                const uint32_t ex = sycl::exclusive_scan_over_group(sg, f, sycl::plus<uint32_t>());
                off[q] = f ? cnt + ex : 0xffffffffu;
                cnt += sycl::reduce_over_group(sg, f, sycl::plus<uint32_t>());
            }
            const uint32_t mine = sl == 0 ? cnt : 0u; // the sub-groups' entries before this one: one group scan
            const uint32_t inc = sycl::inclusive_scan_over_group(g, mine, sycl::plus<uint32_t>());
            const uint32_t tot = sycl::group_broadcast(g, inc, WG - 1);
            const uint32_t sbase = ne + sycl::group_broadcast(sg, inc - mine, 0);
#pragma unroll
            for (int q = 0; q < PER; ++q)
                if (off[q] != 0xffffffffu && sbase + off[q] < CAP) {
                    ek[sbase + off[q]] = okey(v[q]);
                    ej[sbase + off[q]] = sb + q * SGS + sl;
                }
            ne += tot;
        }
        if (ne > CAP || ne < (uint32_t)p.k) { // (uniform) the full select
            sycl::group_barrier(g);
            return p(it, s, (const uint8_t *)nullptr, o, cd, lm);
        }
        // TopKSelP's radix passes over the entries
        uint32_t prefix = 0, pmask = 0, rem = (uint32_t)p.k;
        for (int pass = 0; pass < 4; ++pass) {
            const int shift = 24 - 8 * pass;
            for (int i = lid; i < NSG * 256; i += WG) hist[i] = 0;
            sycl::group_barrier(g);
            for (int e = lid; e < (int)ne; e += WG) {
                const uint32_t kk = ek[e];
                if ((kk & pmask) == prefix)
                    sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::work_group,
                                     sycl::access::address_space::local_space>(hist[sgi * 256 + ((kk >> shift) & 255u)])
                        .fetch_add(1u);
            }
            sycl::group_barrier(g);
            uint32_t tot = 0; // item i < 256 holds bin 255 - i: the scan runs from the top bin down
            if (lid < 256)
                for (int q = 0; q < NSG; ++q) tot += hist[q * 256 + (255 - lid)];
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
        const uint32_t KNEG = okey(-INFINITY);
        if constexpr (BLOCK) { // the kept blocks' bits
            for (int i = lid; i < (n + 31) / 32; i += WG) hist[i] = 0;
            sycl::group_barrier(g);
        }
        uint32_t base = 0, eqseen = 0;
        for (int c0 = 0; c0 < (int)ne; c0 += WG) {
            const int e = c0 + lid;
            const bool in = e < (int)ne;
            const uint32_t kk = in ? ek[e] : 0u;
            const int j = in ? ej[e] : 0;
            const bool gt = in && kk > T, eq = in && kk == T;
            const uint32_t q = eq ? 1u : 0u;
            const uint32_t einc = sycl::inclusive_scan_over_group(g, q, sycl::plus<uint32_t>());
            const uint32_t etot = sycl::group_broadcast(g, einc, WG - 1);
            const bool sel = gt || (eq && eqseen + einc - q < rem);
            if constexpr (BLOCK) {
                const uint32_t s1 = (in && sel && kk > KNEG) ? 1u : 0u;
                if (s1)
                    sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::work_group,
                                     sycl::access::address_space::local_space>(hist[j >> 5])
                        .fetch_or(1u << (j & 31));
                if (o) {
                    const uint32_t sinc = sycl::inclusive_scan_over_group(g, s1, sycl::plus<uint32_t>());
                    const uint32_t stot = sycl::group_broadcast(g, sinc, WG - 1);
                    if (s1) o[1 + base + sinc - 1] = j;
                    base += stot;
                }
            } else {
                const uint32_t s1 = sel ? 1u : 0u;
                const uint32_t sinc = sycl::inclusive_scan_over_group(g, s1, sycl::plus<uint32_t>());
                const uint32_t stot = sycl::group_broadcast(g, sinc, WG - 1);
                if (sel && base + sinc - 1 < 512u) o[base + sinc - 1] = j + 128;
                base += stot;
            }
            eqseen += etot;
        }
        if constexpr (!BLOCK)
            for (int i = (int)base + lid; i < 512; i += WG) o[i] = -1;
        if constexpr (BLOCK) {
            if (o && lid == 0) o[0] = (int32_t)base;
            sycl::group_barrier(g);
            for (int r = lid; r < len; r += WG) cd[r] = (uint8_t)((hist[r >> 8] >> ((r >> 3) & 31)) & 1u);
        }
    }
};
// ---- idxfilt-4 (OWN_IDX_FILT_BC): the pre-filter for the index layers past 20 (24 / 28 / 32 / 36), which score only
// each token's layer-20 candidate rows (OWN_IDX_CAND: IndexerScoreBCM + TopKSelMC). bl + t * bls is token t's block
// list (bl[0] the count, bl[1 + i] block i in ascending order, rows 8 bl[1 + i] .. + 7); a candidate row is a row of a
// listed block below lens[t]. The argument is idxfilt-1's over the candidate rows: thr = the K-th largest LO among
// them (IdxFiltTC) is at most the K-th largest exact candidate score; every candidate row with HI >= thr gets its exact
// score (IdxFiltXC), every other one keeps LO <= HI < thr: strictly below every row TopKSelC can keep. TopKSelC
// counts the candidate rows above -inf (LO and exact scores are finite: the same count) and selects among them: the
// same list, bit for bit.

// IdxFiltS over candidate blocks: work-group (t, s), sub-group g takes token t's candidate blocks s BPG + g RT + rt;
// per block the 8 key rows as A tiles, token t's query parts (IdxFiltQ) as B, s~ per row with IdxFiltS's accumulators,
// order and bound. LO into the token's score row for its candidate rows below lens[t] (other rows untouched, as
// IndexerScoreBCM); the row norms into n2 (tokens sharing a row write the same value). gpt: work-groups per token
// (>= ceil(2048 / BPG)). Local memory: SLM floats.
template <typename A, unsigned RT = 1> struct IdxFiltSC {
    static constexpr unsigned WG = 256, NSG = WG / 16, BPG = NSG * RT;
    static constexpr size_t SLM = (size_t)NSG * 2 * 128;
    LensT lens;
    unsigned m = 1, gpt = 1;
    size_t ss = 0, ws = 32, bls = 0;
    void operator()(sycl::nd_item<1> it, const uint16_t *keys, const uint16_t *bh, const uint16_t *bl, const float *ac,
                    const typename A::T *w, const int32_t *blk, float *sco, float *n2, float *lm) const {
        using namespace idxfilt;
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), g = sg.get_group_linear_id();
        const unsigned gi = (unsigned)it.get_group_linear_id(), t = gi / gpt, s = gi % gpt;
        if (t >= m) return;
        const int len = lens[t];
        if (len <= 0) return;
        const int32_t *b = blk + t * bls;
        const int nb = b[0];
        float *cs = lm + (size_t)g * 256; // this sub-group's two 8 x 16 accumulators
        auto lcs = sycl::address_space_cast<sycl::access::address_space::local_space, sycl::access::decorated::no>(cs);
        const bf16 *kb = reinterpret_cast<const bf16 *>(keys);
        const bf16 *ht = reinterpret_cast<const bf16 *>(bh) + (size_t)t * 4096, *lt = reinterpret_cast<const bf16 *>(bl) + (size_t)t * 4096;
        const typename A::T *wt = w + t * ws;
        const unsigned r = lane & 7u, hf = lane >> 3;
#pragma unroll 1
        for (unsigned rt = 0; rt < RT; ++rt) {
            const int bi = (int)(s * BPG + g * RT + rt);
            if (bi >= nb) break; // (uniform per sub-group)
            const unsigned row0 = (unsigned)b[1 + bi] * 8u;
            jm::joint_matrix<sycl::sub_group, bf16, jm::use::a, 8, 16, jm::layout::row_major> ma[8];
#pragma unroll
            for (unsigned k = 0; k < 8; ++k)
                jm::joint_matrix_load(sg, ma[k],
                                      sycl::address_space_cast<sycl::access::address_space::global_space,
                                                               sycl::access::decorated::no>(kb + (size_t)row0 * 128 + 16 * k),
                                      128);
            const uint16_t *kr = keys + (size_t)(row0 + r) * 128 + 64 * hf;
            float sq = 0;
#pragma unroll 8
            for (unsigned i = 0; i < 64; ++i) {
                const float v = bf16_f(kr[i]);
                sq += v * v;
            }
            sq += sycl::permute_group_by_xor(sg, sq, 8u);
            const float nrm = sycl::sqrt(sq);
#pragma unroll
            for (unsigned nt = 0; nt < 2; ++nt) {
                jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16> acc;
                jm::joint_matrix_fill(sg, acc, 0.0f);
#pragma unroll
                for (unsigned k = 0; k < 8; ++k) {
                    jm::joint_matrix<sycl::sub_group, bf16, jm::use::b, 16, 16, jm::layout::row_major> mb;
                    jm::joint_matrix_load(sg, mb,
                                          sycl::address_space_cast<sycl::access::address_space::global_space,
                                                                   sycl::access::decorated::no>(ht + (size_t)k * 16 * 32 + 16 * nt),
                                          32);
                    jm::joint_matrix_mad(sg, acc, ma[k], mb, acc);
                    jm::joint_matrix_load(sg, mb,
                                          sycl::address_space_cast<sycl::access::address_space::global_space,
                                                                   sycl::access::decorated::no>(lt + (size_t)k * 16 * 32 + 16 * nt),
                                          32);
                    jm::joint_matrix_mad(sg, acc, ma[k], mb, acc);
                }
                jm::joint_matrix_store(sg, acc, lcs + 128 * nt, 16, jm::layout::row_major);
            }
            sycl::group_barrier(sg);
            float part = 0;
#pragma unroll
            for (unsigned nt = 0; nt < 2; ++nt)
#pragma unroll
                for (unsigned c = 0; c < 8; ++c) {
                    const float d = cs[128 * nt + r * 16 + 8 * hf + c];
                    part += (d > 0 ? d : 0.0f) * A::rd(wt[16 * nt + 8 * hf + c]);
                }
            part += sycl::permute_group_by_xor(sg, part, 8u);
            const unsigned row = row0 + r;
            if (hf == 0 && (int)row < len) {
                sco[t * ss + row] = part - (ac[t] * nrm + EABS);
                n2[row] = nrm;
            }
            sycl::group_barrier(sg); // (the accumulators' local memory is rewritten next block)
        }
    }
};

// One work-group per token: thr[2 t] = the K-th largest stored value (LO) over token t's candidate rows (IdxFiltSC's
// positions; rows at or past lens[t] count as -inf), -inf when there are fewer than K positions; thr[2 t + 1] = +inf.
// IdxFiltT's radix select (order keys, 4 passes of 8 bits, per-sub-group histograms) over the positions.
template <unsigned K = 512> struct IdxFiltTC {
    static constexpr int WG = 1024, NSG = WG / 32;
    static constexpr size_t SLM = (size_t)NSG * 256 + 8;
    LensT lens;
    unsigned m = 1;
    size_t ss = 0, bls = 0;
    void operator()(sycl::nd_item<1> it, const float *sco, const int32_t *blk, float *thr, float *lm) const {
        using KT = IdxFiltT<K>;
        const unsigned t = (unsigned)it.get_group_linear_id();
        if (t >= m) return;
        auto g = it.get_group();
        const int lid = (int)it.get_local_linear_id();
        const int sgi = (int)it.get_sub_group().get_group_linear_id();
        const int len = lens[t];
        const int32_t *b = blk + t * bls;
        const int n = len > 0 ? 8 * b[0] : 0;
        const float *sc = sco + t * ss;
        uint32_t *hist = reinterpret_cast<uint32_t *>(lm), *misc = hist + NSG * 256;
        float L = -INFINITY;
        if (n >= (int)K) {
            uint32_t prefix = 0, pmask = 0, rem = K;
            for (int pass = 0; pass < 4; ++pass) {
                const int shift = 24 - 8 * pass;
                for (int i = lid; i < NSG * 256; i += WG) hist[i] = 0;
                sycl::group_barrier(g);
                for (int p = lid; p < n; p += WG) {
                    const int row = b[1 + p / 8] * 8 + p % 8;
                    const uint32_t kk = KT::okey(row < len ? sc[row] : -INFINITY);
                    if ((kk & pmask) == prefix)
                        sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::work_group,
                                         sycl::access::address_space::local_space>(hist[sgi * 256 + ((kk >> shift) & 255u)])
                            .fetch_add(1u);
                }
                sycl::group_barrier(g);
                uint32_t tot = 0; // item i < 256 holds bin 255 - i: the scan runs from the top bin down
                if (lid < 256)
                    for (int q = 0; q < NSG; ++q) tot += hist[q * 256 + (255 - lid)];
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
            L = KT::fkey(prefix);
        }
        if (lid == 0) thr[2 * t] = L, thr[2 * t + 1] = INFINITY;
    }
};

// The exact scores (IndexerScoreB::run's sums, bit for bit: IdxFiltX2's scoring) of token t's candidate rows with
// HI >= thr[2 t] (HI = LO + 2 (ac[t] n2[row] + EABS)). Work-group (t, s) = candidate blocks [s WG BPL, (s + 1) WG BPL)
// (item i: blocks s WG BPL + i + WG j, j < BPL); ns: work-groups per token (>= ceil(2048 / (WG BPL))). Local memory:
// SLM floats.
template <typename A, unsigned BPL = 2> struct IdxFiltXC {
    static constexpr unsigned WG = 256, NSG = WG / 16, SB = WG * BPL, H = 32, DK = 128;
    static constexpr size_t SLM = (size_t)H * DK + H + SB * 8 / 2 + 8;
    static_assert(BPL >= 1 && BPL <= 4, "BPL: 1 to 4 (32 flag bits per item)");
    LensT lens;
    unsigned m = 1, ns = 1;
    size_t ss = 0, qs = 4096, ws = 32, bls = 0;
    void operator()(sycl::nd_item<1> it, const typename A::T *q, const uint16_t *keys, const typename A::T *w,
                    const float *ac, const float *n2, const float *thr, const int32_t *blk, float *sco, float *lm) const {
        auto grp = it.get_group();
        const unsigned gi = (unsigned)it.get_group_linear_id(), t = gi / ns, s = gi % ns;
        const unsigned lid = (unsigned)it.get_local_linear_id();
        if (t >= m) return;
        const int len = lens[t];
        const int32_t *b = blk + t * bls;
        const int nb = len > 0 ? b[0] : 0, b0 = (int)(s * SB);
        if (nb <= b0) return; // (uniform per work-group)
        float *sc = sco + t * ss;
        const float Lr = thr[2 * t], a2 = 2.0f * ac[t], e2 = 2.0f * idxfilt::EABS;
        uint32_t fl = 0;
#pragma unroll
        for (unsigned j = 0; j < BPL; ++j) {
            const int bi = b0 + (int)(lid + WG * j);
            if (bi >= nb) continue;
            const int base = b[1 + bi] * 8;
#pragma unroll
            for (int i = 0; i < 8; ++i) {
                const int r = base + i;
                if (r < len && sc[r] + (a2 * n2[r] + e2) >= Lr) fl |= 1u << (8 * j + i);
            }
        }
        const uint32_t cnt = (uint32_t)sycl::popcount(fl);
        const uint32_t pos = sycl::exclusive_scan_over_group(grp, cnt, sycl::plus<uint32_t>());
        const uint32_t tot = sycl::reduce_over_group(grp, cnt, sycl::plus<uint32_t>());
        if (tot == 0) return; // (uniform)
        uint16_t *lst = reinterpret_cast<uint16_t *>(lm + H * DK + H);
        uint32_t p = pos;
#pragma unroll
        for (unsigned j = 0; j < BPL; ++j)
#pragma unroll
            for (unsigned i = 0; i < 8; ++i)
                if ((fl >> (8 * j + i)) & 1u) lst[p++] = (uint16_t)(8 * (lid + WG * j) + i);
        const typename A::T *qt = q + t * qs, *wt = w + t * ws;
        for (unsigned x = lid; x < H * DK; x += WG) lm[(x & (DK - 1)) * H + (x / DK)] = A::rd(qt[x]);
        for (unsigned x = lid; x < H; x += WG) lm[H * DK + x] = A::rd(wt[x]);
        sycl::group_barrier(grp);
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), sgi = sg.get_group_linear_id();
        for (unsigned e = sgi; e < tot; e += NSG) {
            const unsigned pp = lst[e];
            const int r = b[1 + b0 + (int)(pp >> 3)] * 8 + (int)(pp & 7u);
            const uint16_t *kr = keys + (size_t)r * DK;
            float d0 = 0, d1 = 0;
            for (unsigned i0 = 0; i0 < DK; i0 += 16) {
                const float kv = ops41::bf16(kr[i0 + lane]);
                const float *l0 = lm + (size_t)i0 * H + lane;
#pragma unroll
                for (unsigned ii = 0; ii < 16; ++ii) {
                    const float kf = sycl::select_from_group(sg, kv, ii);
                    d0 += l0[ii * H] * kf;
                    d1 += l0[ii * H + 16] * kf;
                }
            }
            float sum = 0;
#pragma unroll
            for (unsigned hh = 0; hh < H; ++hh) {
                const float v = sycl::select_from_group(sg, hh < 16 ? d0 : d1, hh & 15u);
                sum += (v > 0 ? v : 0) * lm[H * DK + hh];
            }
            if (lane == 0) sc[r] = sum;
        }
    }
};
} // namespace ops41sycl
