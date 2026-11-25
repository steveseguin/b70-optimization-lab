// DSpark drafter for Inkling-2 (Unsloth's dspark-Inkling-2-Mini-Q8_0.gguf) on the target's card: guesses the next
// tokens for Engine::check. Its numbers only decide how many guesses the target keeps, never the text (every guess
// is checked against the target's own choice). Graph from the reference source, with file:line references:
// /home/steve/inkling-work/notes/dspark-spec.md.
//   target taps (Engine::feat): the stream entering visits 5, 23, 41 (before the depth mix) and the final normed row
//   inject(pos0, n): per processed row p: c_l = RMSNorm(sum_j A[l][j] f_j) * dflare_norm[l] (l < 3), context K/V of
//     drafter layer l at p (K: per-head RMSNorm * k_ctx_norm, NeoX RoPE theta 1e6), r(p) = the 4th mixture's norm
//   draft(P0, t0, n): block [t0, mask x 7] at P0..P0+7 through 3 layers (non-causal; layers 0 and 2 see the 1024
//     positions before P0, layer 1 all of them, all see the 8 block keys), then the chained head per guess:
//     u = Wj [s; w1[prev]; y_i; r(P0-1)] + bj, s = g s + (1-g) tanh(u1), z = tanh(u2), guess = argmax over the
//     real tokens of 30 tanh(W_lm (y_i + Wh z + bh) / 30)
#pragma once
#include "engine.hpp"
#include "dsp_vocab.hpp"
#include <cstring>
#include <fstream>
#include <set>

namespace ink {

// the drafter's attention of its 24 rows per key head (8 block slots x 3 query heads) by key spans, register tiles:
// a work-group of 128 threads per (key head, span); scores: lane = key (16 per sub-group), the 24 rows' queries come
// in as 16-lane reads per 16 dimensions and each product takes its value with a constant-index select; P.V: thread =
// dimension for all 24 rows, the rows' probabilities come in 16 keys at a time the same way. Keys j < nctx are cache
// positions lo + j (& km), the 8 after them the block's own rows (k, v). Writes each span's running max / sum / P.V
// to pM / pL / pO for the combine. VAR bit 1: the pass's cache values are staged in local memory before its scores
// (their reads overlap the score products); VAR bit 2: fused multiply-adds (the build turns contraction off). The
// drafter's numbers only pick guesses, so its arithmetic may change; the variant is fixed per run (deterministic)
template <int VAR>
inline sycl::event dsp_attn_span(sycl::queue &dq, const float *q_, const float *k_, const float *v_, const sycl::half *K,
                                 const sycl::half *Vv, int lo, int nctx, int km, int kd_, int span, int nch, float *pO_, float *pM_,
                                 float *pL_) {
    constexpr int B = 8, HQ = 24, HKV = 8, HD = 128, CH = 128, NR = B * (HQ / HKV);
    constexpr int G = HQ / HKV, WG = 128, NSG = WG / SG;
    static_assert(WG == HD && CH == NSG * SG);
    const int nk = nctx + B;
    const float scale = 1.0f / std::sqrt((float)HD);
    return dq.submit([&](sycl::handler &hd) {
            sycl::local_accessor<float, 1> qs(NR * HD, hd), ps(NR * CH, hd), rs(3 * NR, hd);
            sycl::local_accessor<sycl::half, 1> vs((VAR & 1) ? CH * HD : 1, hd);
            hd.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)HKV * nch * WG), sycl::range<1>(WG)),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                const int gi = (int)it.get_group(0), kvh = gi / nch, c = gi % nch, li = (int)it.get_local_id(0);
                const auto sg = it.get_sub_group();
                const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
                for (int i = li; i < NR * HD; i += WG) {
                    const int r = i / HD, dd = i % HD;
                    qs[i] = q_[((size_t)(r / G) * HQ + kvh * G + r % G) * HD + dd] * scale;
                }
                if (li < NR) { rs[li] = -INFINITY; rs[NR + li] = 0.0f; }
                float acc[NR];
#pragma unroll
                for (int r = 0; r < NR; ++r) acc[r] = 0.0f;
                const int j0 = c * span, j1 = sycl::min(nk, j0 + span);
                for (int sb = j0; sb < j1; sb += CH) {
                    const int nkc = sycl::min(CH, j1 - sb);
                    sycl::group_barrier(it.get_group());
                    if constexpr ((VAR & 1) != 0) { // thread li stages key sb + li's 128 values (16-byte reads)
                        const int j = sb + sycl::min(li, nkc - 1);
                        using HV = sycl::vec<sycl::half, 8>;
                        HV vv[HD / 8];
                        if (j < nctx) { // the block's own rows are read in fp32 by the P.V loop
                            const sycl::half *vp = Vv + (size_t)((lo + j) & km) * kd_ + kvh * HD;
#pragma unroll
                            for (int u = 0; u < HD / 8; ++u) vv[u] = *reinterpret_cast<const HV *>(vp + 8 * u);
#pragma unroll
                            for (int u = 0; u < HD / 8; ++u) *reinterpret_cast<HV *>(&vs[li * HD + 8 * u]) = vv[u];
                        }
                    }
                    { // scores: this lane's key sb + 16 sgi + ln for the 24 rows
                        const int kk = SG * sgi + ln, j = sb + sycl::min(kk, nkc - 1);
                        const bool cache = j < nctx;
                        const sycl::half *kp = K + (size_t)((lo + j) & km) * kd_ + kvh * HD;
                        const float *kf = k_ + ((size_t)(cache ? 0 : j - nctx) * HKV + kvh) * HD;
                        float sv[NR];
#pragma unroll
                        for (int r = 0; r < NR; ++r) sv[r] = 0.0f;
#pragma unroll
                        for (int d0 = 0; d0 < HD; d0 += SG) {
                            float kv[SG];
                            if (cache) {
                                const sycl::vec<sycl::half, 8> h0 = *reinterpret_cast<const sycl::vec<sycl::half, 8> *>(kp + d0);
                                const sycl::vec<sycl::half, 8> h1 = *reinterpret_cast<const sycl::vec<sycl::half, 8> *>(kp + d0 + 8);
#pragma unroll
                                for (int w = 0; w < 8; ++w) { kv[w] = (float)h0[w]; kv[8 + w] = (float)h1[w]; }
                            } else {
#pragma unroll
                                for (int w = 0; w < SG; ++w) kv[w] = kf[d0 + w];
                            }
                            float qv[NR];
#pragma unroll
                            for (int r = 0; r < NR; ++r) qv[r] = qs[r * HD + d0 + ln];
#pragma unroll
                            for (int u = 0; u < SG; ++u)
#pragma unroll
                                for (int r = 0; r < NR; ++r) {
                                    if constexpr ((VAR & 2) != 0) sv[r] = sycl::fma(sycl::select_from_group(sg, qv[r], u), kv[u], sv[r]);
                                    else sv[r] += sycl::select_from_group(sg, qv[r], u) * kv[u];
                                }
                        }
#pragma unroll
                        for (int r = 0; r < NR; ++r) ps[r * CH + kk] = kk < nkc ? sv[r] : -INFINITY;
                    }
                    sycl::group_barrier(it.get_group());
                    for (int r = sgi; r < NR; r += NSG) { // running max and sum per row
                        float m = -INFINITY;
                        for (int i = ln; i < CH; i += SG) m = sycl::max(m, ps[r * CH + i]);
                        m = sycl::reduce_over_group(sg, m, sycl::maximum<float>());
                        const float mo = rs[r], mn = sycl::max(mo, m);
                        float su = 0.0f;
                        for (int i = ln; i < CH; i += SG) {
                            const float pv = sycl::exp(ps[r * CH + i] - mn);
                            ps[r * CH + i] = pv;
                            su += pv;
                        }
                        su = sycl::reduce_over_group(sg, su, sycl::plus<float>());
                        if (ln == 0) {
                            const float f = sycl::exp(mo - mn);
                            rs[r] = mn; rs[NR + r] = rs[NR + r] * f + su; rs[2 * NR + r] = f;
                        }
                    }
                    sycl::group_barrier(it.get_group());
                    // P.V: dimension li for the 24 rows
#pragma unroll
                    for (int r = 0; r < NR; ++r) acc[r] *= rs[2 * NR + r];
                    for (int k0 = 0; k0 < nkc; k0 += SG) {
                        float pv[NR];
#pragma unroll
                        for (int r = 0; r < NR; ++r) pv[r] = ps[r * CH + k0 + ln];
#pragma unroll
                        for (int u = 0; u < SG; ++u) {
                            const int j = sb + sycl::min(k0 + u, nkc - 1);
                            float vv;
                            if constexpr ((VAR & 1) != 0)
                                vv = j < nctx ? (float)vs[sycl::min(k0 + u, nkc - 1) * HD + li] : v_[((size_t)(j - nctx) * HKV + kvh) * HD + li];
                            else vv = j < nctx ? (float)Vv[(size_t)((lo + j) & km) * kd_ + kvh * HD + li]
                                               : v_[((size_t)(j - nctx) * HKV + kvh) * HD + li];
#pragma unroll
                            for (int r = 0; r < NR; ++r) {
                                if constexpr ((VAR & 2) != 0) acc[r] = sycl::fma(sycl::select_from_group(sg, pv[r], u), vv, acc[r]);
                                else acc[r] += sycl::select_from_group(sg, pv[r], u) * vv;
                            }
                        }
                    }
                }
#pragma unroll
                for (int r = 0; r < NR; ++r) pO_[(((size_t)kvh * NR + r) * nch + c) * HD + li] = acc[r];
                if (li < NR) { pM_[((size_t)kvh * NR + li) * nch + c] = rs[li]; pL_[((size_t)kvh * NR + li) * nch + c] = rs[NR + li]; }
            });
        });
}


// the drafter's full-context layer (no window) on the matrix engines (DPAS, fp16 inputs, fp32 sums): the block's 8
// key / value rows must sit in the cache at positions nctx .. nctx + 7 (dsp_block_to_cache), and the cache must hold
// CH zeroed rows past them (the last pass reads whole 128-key tiles; masked keys get probability 0, the rows past
// them are finite). Work-group (key head, span), 8 sub-groups: scores S^T = K Q^T (a sub-group = 16 keys, A = two
// 8-key tiles from the cache, B = Q^T in local memory, rows padded to 32), the running max / sum per row as
// dsp_attn_span, P (fp16, local memory) times V (B = 16 keys x 16 dims from the cache; a sub-group = 16 dims, the
// 24 rows as three 8-row accumulators rescaled per row each pass). Same partial layout as dsp_attn_span
inline sycl::event dsp_block_to_cache(sycl::queue &dq, const float *k_, const float *v_, sycl::half *K, sycl::half *Vv, int pos, int kd_,
                                      int km = 0x7fffffff) {
    constexpr int B = 8;
    return dq.parallel_for(sycl::range<1>((size_t)B * kd_), [=](sycl::id<1> i) {
        const size_t r = i[0] / kd_, cc = i[0] % kd_;
        K[(size_t)((pos + (int)r) & km) * kd_ + cc] = (sycl::half)k_[i[0]];
        Vv[(size_t)((pos + (int)r) & km) * kd_ + cc] = (sycl::half)v_[i[0]];
    });
}
// keys j at cache slot (lo + j) & km: lo a multiple of 128 and the ring (km + 1) a multiple of 128, so no 128-key pass wraps
inline sycl::event dsp_attn_span_x(sycl::queue &dq, const float *q_, const sycl::half *K, const sycl::half *Vv, int nk, int kd_,
                                   int span, int nch, float *pO_, float *pM_, float *pL_, int lo = 0, int km = 0x7fffffff) {
    namespace jm = sycl::ext::oneapi::experimental::matrix;
    namespace jmi = sycl::ext::intel::experimental::matrix;
    using hf = sycl::half;
    constexpr int HQ = 24, HKV = 8, HD = 128, CH = 128, NR = 24, G = 3, WG = 128, NSG = WG / 16, NP = 32;
    const float scale = 1.0f / std::sqrt((float)HD);
    return dq.submit([&](sycl::handler &h) {
        sycl::local_accessor<hf, 1> qT(HD * NP, h), Ph(NR * CH, h);
        sycl::local_accessor<float, 1> S(CH * NP, h), rs(3 * NR, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)HKV * nch * WG), sycl::range<1>(WG)),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
            const int gi = (int)it.get_group(0), kvh = gi / nch, c = gi % nch, li = (int)it.get_local_id(0);
            const auto sg = it.get_sub_group();
            const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
            auto lp = [](auto &acc, size_t off) { return acc.template get_multi_ptr<sycl::access::decorated::no>() + off; };
            auto gp = [](const hf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
            for (int i = li; i < HD * NP; i += WG) {
                const int dd = i / NP, r = i % NP;
                qT[i] = r < NR ? (hf)(q_[((size_t)(r / G) * HQ + kvh * G + r % G) * HD + dd] * scale) : (hf)0.0f;
            }
            if (li < NR) { rs[li] = -INFINITY; rs[NR + li] = 0.0f; }
            jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16> acc[3];
#pragma unroll
            for (int mt = 0; mt < 3; ++mt) jm::joint_matrix_fill(sg, acc[mt], 0.0f);
            const int j0 = c * span, j1 = sycl::min(nk, j0 + span);
            for (int sb = j0; sb < j1; sb += CH) {
                const int nkc = sycl::min(CH, j1 - sb);
                sycl::group_barrier(it.get_group());
#pragma unroll
                for (int mt = 0; mt < 2; ++mt) { // keys sb + 16 sgi + 8 mt .. +7 against rows 0-15 and 16-31
                    jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16> s0, s1;
                    jm::joint_matrix_fill(sg, s0, 0.0f);
                    jm::joint_matrix_fill(sg, s1, 0.0f);
                    const hf *kr = K + (size_t)((lo + sb + 16 * sgi + 8 * mt) & km) * kd_ + kvh * HD;
#pragma unroll
                    for (int k = 0; k < HD / 16; ++k) {
                        jm::joint_matrix<sycl::sub_group, hf, jm::use::a, 8, 16, jm::layout::row_major> a;
                        jm::joint_matrix<sycl::sub_group, hf, jm::use::b, 16, 16, jm::layout::row_major> b0, b1;
                        jm::joint_matrix_load(sg, a, gp(kr + 16 * k), kd_);
                        jm::joint_matrix_load(sg, b0, lp(qT, (size_t)16 * k * NP), NP);
                        jm::joint_matrix_load(sg, b1, lp(qT, (size_t)16 * k * NP + 16), NP);
                        jm::joint_matrix_mad(sg, s0, a, b0, s0);
                        jm::joint_matrix_mad(sg, s1, a, b1, s1);
                    }
                    jm::joint_matrix_store(sg, s0, lp(S, (size_t)(16 * sgi + 8 * mt) * NP), NP, jm::layout::row_major);
                    jm::joint_matrix_store(sg, s1, lp(S, (size_t)(16 * sgi + 8 * mt) * NP + 16), NP, jm::layout::row_major);
                }
                sycl::group_barrier(it.get_group());
                for (int r = sgi; r < NR; r += NSG) { // running max and sum per row (keys past nkc: probability 0)
                    float m = -INFINITY;
                    for (int i = ln; i < CH; i += 16) if (i < nkc) m = sycl::max(m, S[i * NP + r]);
                    m = sycl::reduce_over_group(sg, m, sycl::maximum<float>());
                    const float mo = rs[r], mn = sycl::max(mo, m);
                    float su = 0.0f;
                    for (int i = ln; i < CH; i += 16) {
                        const hf pv = i < nkc ? (hf)sycl::exp(S[i * NP + r] - mn) : (hf)0.0f;
                        Ph[r * CH + i] = pv;
                        su += (float)pv;
                    }
                    su = sycl::reduce_over_group(sg, su, sycl::plus<float>());
                    if (ln == 0) {
                        const float f = sycl::exp(mo - mn);
                        rs[r] = mn; rs[NR + r] = rs[NR + r] * f + su; rs[2 * NR + r] = f;
                    }
                }
                sycl::group_barrier(it.get_group());
#pragma unroll
                for (int mt = 0; mt < 3; ++mt)
                    jmi::joint_matrix_apply(sg, acc[mt], [&](float &x, size_t row, size_t) { x *= rs[2 * NR + mt * 8 + (int)row]; });
                const hf *vr = Vv + (size_t)((lo + sb) & km) * kd_ + kvh * HD + 16 * sgi;
#pragma unroll
                for (int k0 = 0; k0 < CH; k0 += 16) {
                    jm::joint_matrix<sycl::sub_group, hf, jm::use::b, 16, 16, jm::layout::row_major> vb;
                    jm::joint_matrix_load(sg, vb, gp(vr + (size_t)k0 * kd_), kd_);
#pragma unroll
                    for (int mt = 0; mt < 3; ++mt) {
                        jm::joint_matrix<sycl::sub_group, hf, jm::use::a, 8, 16, jm::layout::row_major> pa;
                        jm::joint_matrix_load(sg, pa, lp(Ph, (size_t)mt * 8 * CH + k0), CH);
                        jm::joint_matrix_mad(sg, acc[mt], pa, vb, acc[mt]);
                    }
                }
            }
#pragma unroll
            for (int mt = 0; mt < 3; ++mt)
                jm::joint_matrix_store(sg, acc[mt],
                                       sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(
                                           pO_ + (((size_t)kvh * NR + mt * 8) * nch + c) * HD + 16 * sgi),
                                       (size_t)nch * HD, jm::layout::row_major);
            if (li < NR) {
                pM_[((size_t)kvh * NR + li) * nch + c] = rs[li];
                pL_[((size_t)kvh * NR + li) * nch + c] = rs[NR + li];
            }
        });
    });
}


// The drafter's 8-slot products on the matrix engines: y[t][n] = sum_k W[n][k] x[t][k] for the 8 slots, W in Q8_0
// repacked by dsp_x8_repack into tiles of 16 rows x 32 columns (544 bytes: the 16 rows' 32 int8 values, then their 16
// fp16 scales), so a sub-group's reads are contiguous. A sub-group = 16 output rows; lane r decodes row r's 32 values
// (int8 x scale, fp16) into local memory as two 16 x 16 B tiles, the 8 x 16 A tiles are the slots' inputs in fp16.
// KS sub-groups of a work-group split the column blocks of one 16-row tile range and add their 8 x 16 sums in order.
// XG = false: x is fp32 in lane order (xlane.hpp, rows ldx apart) and is converted into local memory (K <= 4096);
// XG = true: x is fp16, row-major [8][K], read directly. Only the drafter's guesses depend on these numbers.
inline std::vector<uint8_t> dsp_x8_repack(const uint8_t *raw, int N, int K) {
    const int KB = K / 32;
    std::vector<uint8_t> out((size_t)N / 16 * KB * 544);
    for (int nt = 0; nt < N / 16; ++nt)
        for (int b = 0; b < KB; ++b) {
            uint8_t *o = out.data() + ((size_t)nt * KB + b) * 544;
            for (int r = 0; r < 16; ++r) {
                const uint8_t *blk = raw + ((size_t)(nt * 16 + r) * KB + b) * 34;
                std::memcpy(o + r * 32, blk + 2, 32);
                std::memcpy(o + 512 + 2 * r, blk, 2);
            }
        }
    return out;
}
// PK: the decoded weights go to local memory as fp16 pairs in the engines' packed order (one 32-bit write per pair,
// tiles double-buffered so one sub-group barrier per block; the next block's bytes are read before this one's math)
template <int KS, bool XG, bool PK = false>
inline sycl::event dsp_mm_x(sycl::queue &dq, const uint8_t *Wx, int N, int K, const void *xin, int ldx, float *y) {
    namespace jm = sycl::ext::oneapi::experimental::matrix;
    using hf = sycl::half;
    constexpr int T = 8, NSG = 8, NTW = NSG / KS; // slots, sub-groups per work-group, 16-row tiles per work-group
    const int KB = K / 32, ntiles = N / 16, nwg = (ntiles + NTW - 1) / NTW, kbs = KB / KS;
    if (N % 16 || K % 32 || KB % KS || (!XG && K > 4096)) throw std::runtime_error("dsp_mm_x: unsupported shape");
    return dq.submit([&](sycl::handler &h) {
        sycl::local_accessor<hf, 1> xs(XG ? 1 : T * K, h), bs(NSG * 512 * (PK ? 2 : 1), h);
        sycl::local_accessor<float, 1> red(KS > 1 ? NSG * 128 : 1, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)nwg * NSG * 16), sycl::range<1>(NSG * 16)),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
            const auto sg = it.get_sub_group();
            const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id(), li = (int)it.get_local_id(0);
            const int nt = (int)it.get_group(0) * NTW + sgi / KS, ks = sgi % KS;
            auto lp = [](auto &acc, size_t off) { return acc.template get_multi_ptr<sycl::access::decorated::no>() + off; };
            if constexpr (!XG) {
                const float *xf = (const float *)xin;
                for (int i = li; i < T * K; i += NSG * 16) {
                    const int t = i / K, kk = i % K;
                    xs[i] = (hf)xf[(size_t)t * ldx + xlane_at(kk)];
                }
                sycl::group_barrier(it.get_group());
            }
            jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16> acc;
            jm::joint_matrix_fill(sg, acc, 0.0f);
            if (PK && nt < ntiles) {
                const uint8_t *wt = Wx + ((size_t)nt * KB + (size_t)ks * kbs) * 544;
                const int b0 = ks * kbs;
                uint32_t *bw = reinterpret_cast<uint32_t *>(&bs[0]) + sgi * 512; // 2 buffers x 2 tiles x 128 words
                sycl::vec<int8_t, 16> q0 = *reinterpret_cast<const sycl::vec<int8_t, 16> *>(wt + ln * 32);
                sycl::vec<int8_t, 16> q1 = *reinterpret_cast<const sycl::vec<int8_t, 16> *>(wt + ln * 32 + 16);
                float dsc = (float)*reinterpret_cast<const hf *>(wt + 512 + 2 * ln);
                for (int b = 0; b < kbs; ++b) {
                    const int bb = b + 1 < kbs ? b + 1 : b; // the next block's bytes first
                    const uint8_t *nx = wt + (size_t)bb * 544;
                    const sycl::vec<int8_t, 16> n0 = *reinterpret_cast<const sycl::vec<int8_t, 16> *>(nx + ln * 32);
                    const sycl::vec<int8_t, 16> n1 = *reinterpret_cast<const sycl::vec<int8_t, 16> *>(nx + ln * 32 + 16);
                    const float nd = (float)*reinterpret_cast<const hf *>(nx + 512 + 2 * ln);
                    uint32_t *buf = bw + (b & 1) * 256;
#pragma unroll
                    for (int kk = 0; kk < 16; kk += 2) { // element (k, n) of a packed 16 x 16 tile: word (k / 2) * 16 + n
                        const sycl::vec<hf, 2> p0((hf)((float)q0[kk] * dsc), (hf)((float)q0[kk + 1] * dsc));
                        const sycl::vec<hf, 2> p1((hf)((float)q1[kk] * dsc), (hf)((float)q1[kk + 1] * dsc));
                        buf[(kk / 2) * 16 + ln] = sycl::bit_cast<uint32_t>(p0);
                        buf[128 + (kk / 2) * 16 + ln] = sycl::bit_cast<uint32_t>(p1);
                    }
                    sycl::group_barrier(sg);
                    jm::joint_matrix<sycl::sub_group, hf, jm::use::b, 16, 16, jm::layout::ext_intel_packed> w0, w1;
                    jm::joint_matrix<sycl::sub_group, hf, jm::use::a, 8, 16, jm::layout::row_major> a0, a1;
                    jm::joint_matrix_load(sg, w0, lp(bs, (size_t)sgi * 1024 + (b & 1) * 512), 32);
                    jm::joint_matrix_load(sg, w1, lp(bs, (size_t)sgi * 1024 + (b & 1) * 512 + 256), 32);
                    const int kc = 32 * (b0 + b);
                    if constexpr (XG) {
                        const hf *xh = (const hf *)xin;
                        auto gp = sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(xh + kc);
                        jm::joint_matrix_load(sg, a0, gp, K);
                        jm::joint_matrix_load(sg, a1, gp + 16, K);
                    } else {
                        jm::joint_matrix_load(sg, a0, lp(xs, (size_t)kc), K);
                        jm::joint_matrix_load(sg, a1, lp(xs, (size_t)kc + 16), K);
                    }
                    jm::joint_matrix_mad(sg, acc, a0, w0, acc);
                    jm::joint_matrix_mad(sg, acc, a1, w1, acc);
                    q0 = n0; q1 = n1; dsc = nd;
                }
            } else if (!PK && nt < ntiles) {
                const uint8_t *wt = Wx + ((size_t)nt * KB + (size_t)ks * kbs) * 544;
                const int b0 = ks * kbs;
                for (int b = 0; b < kbs; ++b) {
                    const uint8_t *ch = wt + (size_t)b * 544;
                    const sycl::vec<int8_t, 16> q0 = *reinterpret_cast<const sycl::vec<int8_t, 16> *>(ch + ln * 32);
                    const sycl::vec<int8_t, 16> q1 = *reinterpret_cast<const sycl::vec<int8_t, 16> *>(ch + ln * 32 + 16);
                    const float dsc = (float)*reinterpret_cast<const hf *>(ch + 512 + 2 * ln);
                    sycl::group_barrier(sg); // the previous block's tiles are read
#pragma unroll
                    for (int kk = 0; kk < 16; ++kk) {
                        bs[sgi * 512 + kk * 16 + ln] = (hf)((float)q0[kk] * dsc);
                        bs[sgi * 512 + 256 + kk * 16 + ln] = (hf)((float)q1[kk] * dsc);
                    }
                    sycl::group_barrier(sg);
                    jm::joint_matrix<sycl::sub_group, hf, jm::use::b, 16, 16, jm::layout::row_major> w0, w1;
                    jm::joint_matrix<sycl::sub_group, hf, jm::use::a, 8, 16, jm::layout::row_major> a0, a1;
                    jm::joint_matrix_load(sg, w0, lp(bs, (size_t)sgi * 512), 16);
                    jm::joint_matrix_load(sg, w1, lp(bs, (size_t)sgi * 512 + 256), 16);
                    const int kc = 32 * (b0 + b);
                    if constexpr (XG) {
                        const hf *xh = (const hf *)xin;
                        auto gp = sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(xh + kc);
                        jm::joint_matrix_load(sg, a0, gp, K);
                        jm::joint_matrix_load(sg, a1, gp + 16, K);
                    } else {
                        jm::joint_matrix_load(sg, a0, lp(xs, (size_t)kc), K);
                        jm::joint_matrix_load(sg, a1, lp(xs, (size_t)kc + 16), K);
                    }
                    jm::joint_matrix_mad(sg, acc, a0, w0, acc);
                    jm::joint_matrix_mad(sg, acc, a1, w1, acc);
                }
            }
            if constexpr (KS == 1) {
                if (nt < ntiles)
                    jm::joint_matrix_store(sg, acc, sycl::address_space_cast<sycl::access::address_space::global_space,
                                                                                sycl::access::decorated::no>(y + (size_t)nt * 16),
                                           (size_t)N, jm::layout::row_major);
            } else {
                jm::joint_matrix_store(sg, acc, lp(red, (size_t)sgi * 128), 16, jm::layout::row_major);
                sycl::group_barrier(it.get_group());
                // thread li: tile li / 128 of this work-group, element li % 128 (slot e / 16, row e % 16); slices in order
                for (int e = li; e < NTW * 128; e += NSG * 16) {
                    const int tw = e / 128, el = e % 128, ntt = (int)it.get_group(0) * NTW + tw;
                    if (ntt >= ntiles) continue;
                    float v = 0.0f;
                    for (int k2 = 0; k2 < KS; ++k2) v += red[(tw * KS + k2) * 128 + el];
                    y[(size_t)(el / 16) * N + ntt * 16 + el % 16] = v;
                }
            }
        });
    });
}

// a guess's keep chance by its probability in tenths (Drafter::QK)
struct KeepTable { float v[10]; };
// the chain's keep chance before guess n0 + 1 is below thr: the products of qk over gp[0..n0) in order from 1.0f
inline bool keep_chain_below(const float *gp, int n0, float thr, const KeepTable &qk) {
    float pr = 1.0f;
    for (int j = 0; j < n0; ++j) { const int b = (int)(gp[j] * 10.0f); pr *= qk.v[b < 9 ? b : 9]; }
    return pr < thr;
}

struct Drafter {
    static constexpr int B = 8, NL = 3, R = 256, HQ = 24, HKV = 8, HD = 128, WIN = 1024, AWG = 256;
    Engine &e;
    Device &d;
    GGUF g;
    Weights w;
    std::map<std::string, WView> views;
    struct DL { W attn_norm, wq, wk, wv, q_norm, k_norm, wo, k_ctx, v_ctx, k_ctx_norm, dflare_norm, ffn_norm, gate, up, down; };
    DL L[NL];
    W dnorm, mask, onorm, w1, jp, jpb, ho, hob;
    float A[16];  // softmax of each dspark_fuse row (row l < 3: drafter layer l's context, row 3: the head context)
    int E, Vp, V, cap, T, kd;
    // The head computes only a token list (default: dsp_vocab.hpp's 47,912 tokens seen in ~18M tokens of local text),
    // the prompt's own tokens (the constructor's `extra`) and the ids >= 199,990 (special tokens): its output-layer rows
    // and correction columns are copied at load, so each head read is ~1/4 of the full vocabulary's. Only the guesses
    // can change (a token outside the list is never guessed); every guess is still checked. INK_DSP_VOCAB=0: the full
    // vocabulary; =<file>: token ids from a file (a line's first number, most frequent first), the first
    // INK_DSP_VOCAB_K (default all) of them. Needs the folded int8 table (the default).
    std::vector<int32_t> extra_ids;
    size_t head_nx = 0;          // tokens the prompt added to the list
    int Vh = 0, Vs = 0;          // the head's columns (padded) and real entries (Vp and V without a list)
    int32_t *hmap = nullptr;     // head column -> token id (null: the identity)
    Tensor hsub_t;               // the list's output-layer rows (shape of output.weight with Vh rows)
    uint8_t *hsub = nullptr;
    WView hv;                    // the head's output-layer view (e.m.output's, or the list's rows)
    float eps, theta;
    sycl::half *Kc[NL] = {}, *Vc[NL] = {};
    int kmask[NL];
    bool full_l[NL] = {}; // the layer without a window (it sees every position, or the last win_full of them)
    // INK_DSP_WIN: the full layer keeps only the last win_full positions in a ring (0: all of them; default what a
    // 16,384-slot ring holds beside a step, ~15K). Only the guesses change past that many positions (the drafter's
    // numbers never reach the text)
    int win_full = 0;
    int lo_of(int l, int P0) const {
        if (!full_l[l]) return std::max(0, P0 - WIN);
        return win_full ? std::max(0, P0 - win_full) / 128 * 128 : 0;
    }
    float *cb = nullptr, *kc = nullptr, *vc = nullptr, *rrows = nullptr;
    float *x, *hh, *q, *k, *v, *att, *ao, *gt, *upb, *y, *sc, *cat, *uu, *s, *z, *eh, *hs, *lgd;
    float *Xt = nullptr;    // the tile kernels' gathered inputs (one tile of 16 slots, up to the widest input)
    float *base = nullptr;  // W_lm y_i of the guess slots [B - 1][Vp]
    float *cvec = nullptr;  // W_lm bh [Vp]
    sycl::ext::oneapi::bfloat16 *Pt = nullptr; // (W_lm Wh)^T [R][Vp]: the correction of latent z is sum_j z_j Pt[j]
    // INK_DSP_PT8 (default 1): the table as int8 with one scale per vocabulary column (Pt8[j][r] * Ps[r]): half the
    // bytes of the per-guess read (103 -> 51 MB); it only moves the drafter's guesses
    bool pt8 = true;
    int8_t *Pt8 = nullptr;
    // INK_DSP_MMX (default 1): the 8-slot products (q, k, v, o, gate, up, down) on the matrix engines (dsp_mm_x) from
    // repacked copies X8 of the Q8_0 weights; their inputs as fp16 rows (xh16: the norms, ah: the attention, gh: SiLU)
    bool mmx = true;
    uint8_t *X8[NL][7] = {};
    sycl::half *xh16 = nullptr, *ah = nullptr, *gh = nullptr;
    float *Ps = nullptr;
    int32_t *gids;
    float *yl = nullptr, *amv = nullptr, *ams = nullptr, *gp = nullptr; int32_t *ami = nullptr; // argmax scratch; guess probabilities
    std::vector<float> probs; // the last draft's guess probabilities (the drafter's own softmax)
    // keep chance of a guess by its probability in tenths (measured 2026-11-23 on code, haiku and a 3K prompt: 0.9+
    // kept 283 of 304, 0.8+ 35 of 57, ...): ink_run's choice of how many guesses to check, and the stop below
    static constexpr KeepTable QK{{0.10f, 0.10f, 0.12f, 0.20f, 0.33f, 0.36f, 0.44f, 0.53f, 0.61f, 0.93f}};
    // INK_DSP_STOP (default 0.1; 0 = never): guess i's correction pass (its 51 MB table read) is skipped once the
    // product of the keep chances of guesses 1..i-1 is below this, and draft() returns only the guesses before that
    // (each guess costs ~0.2 ms; a check past such a chain is never worth its cost)
    float stop_thr = 0.1f;
    // stop_hi > 0 and n >= 5: slots 1-3 take one read of the output layer (bench_gemv card 3: 776 us); the host then
    // reads guesses 1-3's probabilities and submits slots 4..n (a second read, 4 slots 855 us) and guesses 4..n only
    // when their chain is at least stop_hi (one read of 7 slots took 1,219 us every round, and the ~20 launches of 4
    // skipped guesses ~0.25 ms). ink_run sets it each round from its step costs.
    float stop_hi = 0.0f;
    float stop_at(int i, bool late) const { return late && i >= 4 && stop_hi > stop_thr ? stop_hi : stop_thr; }
    static int keep_bucket(float p) { const int b = (int)(p * 10.0f); return b < 9 ? b : 9; }
    // split attention (INK_DSP_SPLIT=0: one work-group per query row): work-groups of (key head, key span) for all
    // 24 rows of a key head, partial softmax sums combined by a second launch
    int split = 2; // 2: attend_split2, 1: attend_split, 0: one work-group per row
    static constexpr int NR = B * (HQ / HKV), CH = 128, NCH_MAX = 1024; // rows per key head; keys per pass
    int NCH = 64; // spans per head at most (INK_DSP_NCH, up to NCH_MAX)
    // INK_DSP_AVAR: 4 = the full layer on the matrix engines (dsp_attn_span_x; bench_dsp card 3 100K 2.59 -> 0.88 ms),
    // the windowed layers as 3; 3 = fma + staged values (100K 3.65 -> 2.59 ms); 2 fma; 1 staged; 0 the first
    int attn_var = 4;
    float *pO = nullptr, *pM = nullptr, *pL = nullptr;
    float *hl = nullptr, *attl = nullptr, *gl = nullptr; // the 8 slots' product inputs in lane order (xlane.hpp)
    bool fold = true;       // INK_DSP_FOLD=0: each guess passes y_i + Wh z + bh through W_lm (the reference's way)
    int r_last = -1; // the row of rrows that holds r(P0 - 1)
    size_t sc_keys;  // score scratch per (slot, head)

    static W wof(const WView &v) { W r; r.t = v.t; r.p = v.p; r.rb = v.rb; r.kind = v.kind; return r; }
    W get(const std::string &n) const {
        auto it = views.find(n);
        if (it == views.end()) throw std::runtime_error("dspark: missing tensor " + n);
        return wof(it->second);
    }
    const float *f32(const W &t) const { return e.f32(t); }

    Drafter(Engine &eng, const std::string &path, const std::vector<int32_t> *extra = nullptr) : e(eng), d(eng.d), g(path) {
        if (extra) extra_ids = *extra;
        if (g.s("general.architecture") != "dflash") throw std::runtime_error("dspark: not a dflash file");
        const HParams &h = e.m.hp;
        E = h.n_embd; Vp = h.vocab_padded; V = h.vocab; cap = e.cap; T = e.T; kd = HKV * HD;
        Vh = Vp; Vs = V; hv = e.m.output.view();
        if (E > 2304) throw std::runtime_error("dspark: the mixture kernel holds 2304 values per row");
        if (g.i("dflash.embedding_length") != E || g.i("dflash.block_count") != NL || g.i("dflash.block_size") != B ||
            g.i("dflash.attention.head_count") != HQ || g.i("dflash.attention.head_count_kv") != HKV ||
            g.i("dflash.dspark.markov_rank") != R || g.i("dflash.attention.sliding_window") != WIN)
            throw std::runtime_error("dspark: unexpected shape");
        eps = (float)g.f("dflash.attention.layer_norm_rms_epsilon");
        theta = (float)g.f("dflash.rope.freq_base");
        const auto &tl = g.arr<std::vector<int64_t>>("dflash.target_layers");
        if (tl.size() != 4 || tl[3] != h.n_app) throw std::runtime_error("dspark: target layers");
        for (int j = 0; j < 3; ++j) e.feat_vis[j] = (int)tl[j];
        // the 8-slot products' weights go on the card only as dsp_mm_x's repacked copies (INK_DSP_MMX)
        if (const char *ev = std::getenv("INK_DSP_MMX")) mmx = std::atoi(ev) != 0;
        if (const char *ev = std::getenv("INK_DSP_SPLIT")) split = std::atoi(ev);
        static const char *const pw[7] = {"attn_q", "attn_k", "attn_v", "attn_output", "ffn_gate", "ffn_up", "ffn_down"};
        std::set<std::string> mine;
        for (int l = 0; l < NL; ++l)
            for (int m = 0; m < 7; ++m) mine.insert("blk." + std::to_string(l) + "." + pw[m] + ".weight");
        for (auto &t : g.tensors)
            if (mine.count(t.name) && (t.type != G_Q8_0 || t.rows() % 16 || t.ne[0] % 256)) mmx = false;
        auto own = [&](const Tensor &t) { // the output product stays in the file layout too for splits 0/1 (lmm)
            return mmx && mine.count(t.name) && !(split != 2 && t.name.find(".attn_output.") != std::string::npos);
        };
        w.upload(d, g, false, own);
        views = planarize(d, g, w, false, own);
        for (int l = 0; l < NL; ++l) {
            const std::string p = "blk." + std::to_string(l) + ".";
            DL &a = L[l];
            a.attn_norm = get(p + "attn_norm.weight"); a.wq = get(p + "attn_q.weight"); a.wk = get(p + "attn_k.weight");
            a.wv = get(p + "attn_v.weight"); a.q_norm = get(p + "attn_q_norm.weight"); a.k_norm = get(p + "attn_k_norm.weight");
            a.wo = get(p + "attn_output.weight"); a.k_ctx = get(p + "attn_k_ctx.weight"); a.v_ctx = get(p + "attn_v_ctx.weight");
            a.k_ctx_norm = get(p + "attn_k_ctx_norm.weight"); a.dflare_norm = get(p + "dflare_norm.weight");
            a.ffn_norm = get(p + "ffn_norm.weight"); a.gate = get(p + "ffn_gate.weight"); a.up = get(p + "ffn_up.weight");
            a.down = get(p + "ffn_down.weight");
        }
        if (mmx) {
            size_t tot = 0;
            for (int l = 0; l < NL; ++l) {
                const W *ws[7] = {&L[l].wq, &L[l].wk, &L[l].wv, &L[l].wo, &L[l].gate, &L[l].up, &L[l].down};
                for (int m = 0; m < 7; ++m) {
                    if (m == 3 && !o_mx()) continue; // splits 0/1: the output product reads the uploaded copy
                    const Tensor &t = *ws[m]->t;
                    std::vector<uint8_t> raw(t.bytes);
                    g.read_at(raw.data(), t.bytes, g.data_off + t.off);
                    const std::vector<uint8_t> rp = dsp_x8_repack(raw.data(), (int)t.rows(), (int)t.ne[0]);
                    X8[l][m] = d.alloc<uint8_t>(rp.size());
                    d.put(X8[l][m], rp.data(), rp.size());
                    tot += rp.size();
                }
            }
            std::fprintf(stderr, "[dspark] 8-slot products on the matrix engines (%.0f MB of repacked weights)\n", tot / 1e6);
        }
        dnorm = get("dspark_norm.weight"); mask = get("mask_embd.weight"); onorm = get("output_norm.weight");
        w1 = get("markov_w1.weight"); jp = get("joint_proj.weight"); jpb = get("joint_proj.bias");
        ho = get("dspark_hidden_out.weight"); hob = get("dspark_hidden_out.bias");
        { // the mixtures' softmax (fixed weights)
            const W fw = get("dspark_fuse.weight");
            float raw[16];
            d.get(raw, (const float *)fw.p, 16);
            for (int r = 0; r < 4; ++r) {
                float m = raw[4 * r];
                for (int j = 1; j < 4; ++j) m = std::max(m, raw[4 * r + j]);
                float sum = 0.0f;
                for (int j = 0; j < 4; ++j) sum += std::exp(raw[4 * r + j] - m);
                for (int j = 0; j < 4; ++j) A[4 * r + j] = std::exp(raw[4 * r + j] - m) / sum;
            }
        }
        // context caches: layer 1 every position, layers 0 and 2 a ring (a window plus a step and more)
        const char *pat = "dflash.attention.sliding_window_pattern";
        const auto &swp = g.arr<std::vector<int64_t>>(pat);
        // default: a ring of 16,384 slots (64 MiB) once the full cache would be larger (100K prompt, 256 tokens with
        // guessing: 2.54 tokens per check seeing every position, 2.49 / 2.46 / 2.53 with 64K / 32K / 8K; drafting 0.32 ->
        // 0.24 s with 8K; the text identical, as always)
        win_full = cap + B + CH > 16384 ? 16384 - (128 + T + B + CH) : 0;
        if (const char *ev = std::getenv("INK_DSP_WIN")) win_full = std::max(0, std::atoi(ev));
        if (win_full >= cap) win_full = 0;
        for (int l = 0; l < NL; ++l) {
            const bool win = swp.at(l) != 0;
            full_l[l] = !win;
            int ring = 1; // a power of two holding the window, a step and a block
            while (ring < WIN + T + B) ring *= 2;
            int ringf = 128; // the full layer's ring: the window from a multiple of 128, a step, a block and one pass past
            while (ringf < win_full + 128 + T + B + CH) ringf *= 2;
            const int slots = win ? ring : win_full ? ringf : cap + B + CH; // the full layer: room for the block rows and one pass past them
            kmask[l] = win ? ring - 1 : win_full ? ringf - 1 : 0x7fffffff;
            Kc[l] = d.alloc_zero<sycl::half>((size_t)slots * kd);
            Vc[l] = d.alloc_zero<sycl::half>((size_t)slots * kd);
        }
        e.feat = d.alloc<float>((size_t)4 * T * E);
        cb = d.alloc<float>((size_t)3 * T * E);
        kc = d.alloc<float>((size_t)T * kd); vc = d.alloc<float>((size_t)T * kd);
        rrows = d.alloc<float>((size_t)T * E);
        x = d.alloc<float>((size_t)B * E); hh = d.alloc<float>((size_t)B * E); y = d.alloc<float>((size_t)B * E);
        q = d.alloc<float>((size_t)B * HQ * HD); k = d.alloc<float>((size_t)B * kd); v = d.alloc<float>((size_t)B * kd);
        att = d.alloc<float>((size_t)B * HQ * HD); ao = d.alloc<float>((size_t)B * E);
        const int F = (int)L[0].gate.t->rows();
        gt = d.alloc<float>((size_t)B * F); upb = d.alloc<float>((size_t)B * F);
        sc_keys = (size_t)cap + B; // (attend(): INK_DSP_SPLIT=0 only)
        sc = split == 0 ? d.alloc<float>((size_t)B * HQ * sc_keys) : nullptr;
        cat = d.alloc<float>((size_t)2 * R + 2 * E); uu = d.alloc<float>(3 * R); s = d.alloc<float>(R); z = d.alloc<float>(R);
        eh = d.alloc<float>(E); hs = d.alloc<float>(E); lgd = d.alloc<float>(Vp);
        gids = d.alloc<int32_t>(B);
        int widest = 0;
        for (int l = 0; l < NL; ++l) for (const W *t : {&L[l].wq, &L[l].wo, &L[l].gate, &L[l].down}) widest = std::max(widest, (int)t->t->ne[0]);
        Xt = d.alloc<float>((size_t)widest * MOE_TS);
        base = d.alloc<float>((size_t)(B - 1) * Vp);
        yl = d.alloc<float>((size_t)B * xlane_floats(E));
        hl = d.alloc<float>((size_t)B * xlane_floats(E));
        attl = d.alloc<float>((size_t)B * xlane_floats(HQ * HD));
        gl = d.alloc<float>((size_t)B * xlane_floats((int)L[0].gate.t->rows()));
        if (mmx) {
            xh16 = d.alloc<sycl::half>((size_t)B * E);
            ah = d.alloc<sycl::half>((size_t)B * HQ * HD);
            gh = d.alloc<sycl::half>((size_t)B * L[0].gate.t->rows());
        }
        amv = d.alloc<float>(ops::ARGMAX_G); ami = d.alloc<int32_t>(ops::ARGMAX_G); ams = d.alloc<float>(ops::ARGMAX_G);
        gp = d.alloc<float>(B);
        if (const char *ev = std::getenv("INK_DSP_FOLD")) fold = std::atoi(ev) != 0;
        if (const char *ev = std::getenv("INK_DSP_STOP")) stop_thr = (float)std::atof(ev);
        if (const char *ev = std::getenv("INK_DSP_SPLIT")) split = std::atoi(ev);
        if (const char *ev = std::getenv("INK_DSP_AVAR")) attn_var = std::atoi(ev);
        if (const char *ev = std::getenv("INK_DSP_NCH")) NCH = std::max(1, std::min(NCH_MAX, std::atoi(ev)));
        pO = d.alloc<float>((size_t)HKV * NR * (NCH + 1) * HD);
        pM = d.alloc<float>((size_t)HKV * NR * (NCH + 1)); pL = d.alloc<float>((size_t)HKV * NR * (NCH + 1));
        if (fold) make_fold();
        e.on_step = [this](int pos0, int n) { inject(pos0, n); };
    }

    // the head's correction through W_lm, folded: W_lm (y + Wh z + bh) = W_lm y + (W_lm Wh) z + W_lm bh. (W_lm Wh)^T is
    // W_lm applied to Wh's 256 columns (the engine's own products, 256 vectors), kept as BF16
    void make_fold() {
        const double t0 = now_s();
        const int E_ = E;
        float *cols = d.alloc<float>((size_t)R * E), *Y = d.alloc<float>((size_t)R * Vp);
        const sycl::ext::oneapi::bfloat16 *wh = (const sycl::ext::oneapi::bfloat16 *)ho.p; // [E rows][R]
        d.q.parallel_for(sycl::range<2>(R, (size_t)E), [=](sycl::id<2> id) {
            cols[(size_t)id[0] * E_ + id[1]] = (float)wh[(size_t)id[1] * R + id[0]];
        }).wait();
        for (int j0 = 0; j0 < R; j0 += e.T) e.mm(e.m.output, cols + (size_t)j0 * E, Y + (size_t)j0 * Vp, std::min(e.T, R - j0));
        if (const char *ev = std::getenv("INK_DSP_PT8")) pt8 = std::atoi(ev) != 0;
        const int32_t *sel = nullptr; // the list's token ids (device), or null
        const char *vf = std::getenv("INK_DSP_VOCAB");
        if (pt8 && !(vf && !std::strcmp(vf, "0"))) {
            std::set<int32_t> ids;
            if (vf && std::strcmp(vf, "1")) {
                const int K = std::getenv("INK_DSP_VOCAB_K") ? std::atoi(std::getenv("INK_DSP_VOCAB_K")) : V;
                std::ifstream f(vf);
                if (!f) throw std::runtime_error(std::string("dspark: cannot read ") + vf);
                std::string line;
                while ((int)ids.size() < K && std::getline(f, line)) {
                    const long v = std::strtol(line.c_str(), nullptr, 10);
                    if (v >= 0 && v < V) ids.insert((int32_t)v);
                }
            } else {
                if (DSP_VOCAB_BITS < V) throw std::runtime_error("dspark: built-in token list is for a smaller vocabulary");
                for (int v = 0; v < V; ++v) if (dsp_vocab_bits[v >> 5] >> (v & 31) & 1u) ids.insert(v);
            }
            const size_t nl = ids.size();
            for (const int32_t v : extra_ids) if (v >= 0 && v < V) ids.insert(v);
            head_nx = ids.size() - nl;
            for (int v = 199990; v < V; ++v) ids.insert(v);
            std::vector<int32_t> hs(ids.begin(), ids.end()); // ascending: ties go to the lower id, as over the full vocabulary
            Vs = (int)hs.size(); Vh = (Vs + 63) / 64 * 64;
            hs.resize(Vh, hs.back()); // padding columns (never chosen: the argmax reads Vs)
            hmap = d.alloc<int32_t>(Vh);
            d.put(hmap, hs.data(), hs.size());
            const WView ov = e.m.output.view();
            if (ov.rb % 4) throw std::runtime_error("dspark: output rows not a multiple of 4 bytes");
            hsub = d.alloc<uint8_t>((size_t)Vh * ov.rb);
            const uint32_t *src = (const uint32_t *)ov.p;
            uint32_t *dst = (uint32_t *)hsub;
            const int32_t *hm = hmap;
            const size_t rw = ov.rb / 4;
            d.q.parallel_for(sycl::range<2>((size_t)Vh, rw), [=](sycl::id<2> id) {
                dst[id[0] * rw + id[1]] = src[(size_t)hm[id[0]] * rw + id[1]];
            }).wait();
            hsub_t = *ov.t;
            hsub_t.name = "output.weight.dsp_subset";
            hsub_t.ne = {ov.t->ne[0], (int64_t)Vh, 1, 1};
            hv = WView{&hsub_t, hsub, ov.rb, ov.kind};
            sel = hmap;
        }
        if (pt8) { // column i of the table is token sel[i] (or i)
            Pt8 = d.alloc<int8_t>((size_t)R * Vh);
            Ps = d.alloc<float>(Vh);
            int8_t *q8 = Pt8;
            float *ps = Ps;
            const int Vp_ = Vp, Vh_ = Vh;
            d.q.parallel_for(sycl::range<1>((size_t)Vh), [=](sycl::id<1> i) {
                const size_t c = i[0], r = sel ? (size_t)sel[c] : c;
                float mx = 0.0f;
                for (int j = 0; j < R; ++j) mx = sycl::fmax(mx, sycl::fabs(Y[(size_t)j * Vp_ + r]));
                const float sc = mx > 0.0f ? mx / 127.0f : 1.0f;
                ps[c] = sc;
                for (int j = 0; j < R; ++j) q8[(size_t)j * Vh_ + c] = (int8_t)sycl::rint(Y[(size_t)j * Vp_ + r] / sc);
            }).wait();
        } else {
            Pt = d.alloc<sycl::ext::oneapi::bfloat16>((size_t)R * Vp);
            auto *pt = Pt;
            d.q.parallel_for(sycl::range<1>((size_t)R * Vp), [=](sycl::id<1> i) { pt[i] = sycl::ext::oneapi::bfloat16(Y[i]); }).wait();
        }
        cvec = d.alloc<float>(Vp);
        e.mm(e.m.output, f32(hob), cvec, 1);
        d.q.wait();
        if (sel) { // the list's entries, in column order (Vh <= Vp: in place, ascending ids never overtake their column)
            float *cv = cvec;
            const int Vh_ = Vh;
            d.q.single_task([=]() { for (int c = 0; c < Vh_; ++c) cv[c] = cv[sel[c]]; }).wait();
            std::fprintf(stderr, "[dspark] head over %d tokens (%d columns; list %s, %zu from the prompt): %.0f MB of output rows\n",
                         Vs, Vh, vf && std::strcmp(vf, "1") ? vf : "built-in", head_nx, (double)Vh * hv.rb / 1e6);
        }
        d.release(Y); d.release(cols);
        e.prof.rows.clear(); e.prof.busy_ms = e.prof.span_ms = 0; e.prof.steps = 0;
        std::fprintf(stderr, "[dspark] folded head table (%.0f MB%s) in %.2f s\n", (double)R * Vh * (pt8 ? 1 : 2) / 1e6, pt8 ? ", int8" : "", now_s() - t0);
    }

    // y[t] = W x[t] for the 8 slots, x in lane order (rows xlane_floats(cols) apart): blocks of 8 vectors per sub-group
    // (bench_gemv card 3, 8 vectors: ffn_gate 75 us, ffn_down 88; the tile kernels 123 and 225)
    // the output product on the matrix engines (its input from attn_combine as fp16 rows): split 2 only; splits 0/1
    // write attl themselves (split 1 also through attn_combine, which then writes attl too)
    bool o_mx() const { return mmx && split == 2; }
    // product m of layer l (0 q, 1 k, 2 v, 3 o, 4 gate, 5 up, 6 down): the matrix engines from the fp16 rows xh, else lmm
    void mm(int l, int m, const W &wt, const float *xl, const sycl::half *xh, float *yout, const char *label) {
        if (!mmx || (m == 3 && !o_mx())) { lmm(wt, xl, yout, label); return; }
        const int N = (int)wt.t->rows(), K = (int)wt.t->ne[0];
        if (N >= 8192) e.pr(label, dsp_mm_x<2, true, true>(d.q, X8[l][m], N, K, xh, 0, yout));
        else e.pr(label, dsp_mm_x<8, true, true>(d.q, X8[l][m], N, K, xh, 0, yout));
    }
    // RMSNorm of the 8 slots into fp16 rows (the matrix-engine products' input; only the guesses depend on it)
    void norm_h(const float *xin, const W &wn, sycl::half *out) {
        const float *w_ = f32(wn);
        const int E_ = E;
        const float ep = eps;
        e.pr("dsp_norm", d.q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)B * 256), sycl::range<1>(256)), [=](sycl::nd_item<1> it) {
            const int t = (int)it.get_group(0), li = (int)it.get_local_id(0);
            const float *xr = xin + (size_t)t * E_;
            float ss = 0.0f;
            for (int i = li; i < E_; i += 256) ss += xr[i] * xr[i];
            ss = sycl::reduce_over_group(it.get_group(), ss, sycl::plus<float>());
            const float rs = 1.0f / sycl::sqrt(ss / E_ + ep);
            for (int i = li; i < E_; i += 256) out[(size_t)t * E_ + i] = (sycl::half)(xr[i] * rs * w_[i]);
        }));
    }
    void lmm(const W &wt, const float *xin, float *yout, const char *label) {
        const int cols = (int)wt.t->ne[0], rows = (int)wt.t->rows();
        e.pr(label, gemv_v(d.q, wt.view(), xin, (int)xlane_floats(cols), yout, rows, B, Tune{1, 1, false, 8, false}, true));
    }
    // y[t] = W x[t] for the n <= 16 slots through the token-parallel tile kernels (one weight read for all slots)
    void tmm(const W &wt, const float *xin, float *yout, int n, const char *label) {
        const int cols = (int)wt.t->ne[0], rows = (int)wt.t->rows();
        e.pr("dsp_gather", dense_gather(d.q, xin, cols, n, cols, Xt));
        e.pr(label, dense_t(d.q, wt.view(), n, Xt, yout, rows, DTune{1, 1}));
    }

    // RMSNorm over 128 values per head (weight wn), then NeoX RoPE at position pos (pairs j, j + 64)
    static inline void head_norm_rope(sycl::nd_item<1> it, float xv, const float *wn, int pos, float theta, float eps, float *slm,
                                      float &out) {
        const int dd = (int)it.get_local_id(0);
        const float ss = ops::wg_sum<HD>(it, xv * xv, slm);
        const float xn = xv * (1.0f / sycl::sqrt(ss / HD + eps)) * wn[dd];
        slm[HD / SG + dd] = xn;
        sycl::group_barrier(it.get_group());
        const int j = dd & (HD / 2 - 1);
        const float fr = sycl::pow(theta, -2.0f * (float)j / (float)HD) * (float)pos;
        const float c = sycl::cos(fr), sn = sycl::sin(fr);
        const float a = slm[HD / SG + j], b = slm[HD / SG + j + HD / 2];
        out = dd < HD / 2 ? a * c - b * sn : a * sn + b * c;
    }

    // after every target step: the rows' context K/V (3 layers) and head-context rows r(p)
    void inject(int pos0, int n) {
        const float *feat = e.feat;
        const int E_ = E, T_ = T;
        float Am[16];
        std::memcpy(Am, A, sizeof(Am));
        struct NW { const float *p[4]; } nw{{f32(L[0].dflare_norm), f32(L[1].dflare_norm), f32(L[2].dflare_norm), f32(dnorm)}};
        float *cb_ = cb, *rr = rrows;
        const float ep = eps;
        e.pr("dsp_mix", d.q.submit([&](sycl::handler &hd) {
            sycl::local_accessor<float, 1> slm(ops::OPS_WG / SG, hd);
            hd.parallel_for(ops::rows_range(4 * n), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                const int gi = (int)it.get_group(0), l = gi / n, t = gi % n, li = (int)it.get_local_id(0);
                float mv[(2304 + ops::OPS_WG - 1) / ops::OPS_WG];
                float ss = 0.0f;
                int u = 0;
                for (int i = li; i < E_; i += ops::OPS_WG, ++u) {
                    float m = 0.0f;
                    for (int j = 0; j < 4; ++j) m += Am[4 * l + j] * feat[((size_t)j * T_ + t) * E_ + i];
                    mv[u] = m;
                    ss += m * m;
                }
                const float tot = ops::wg_sum<ops::OPS_WG>(it, ss, &slm[0]);
                const float scale = 1.0f / sycl::sqrt(tot / E_ + ep);
                float *out = l < 3 ? cb_ + ((size_t)l * T_ + t) * E_ : rr + (size_t)t * E_;
                u = 0;
                for (int i = li; i < E_; i += ops::OPS_WG, ++u) out[i] = mv[u] * scale * nw.p[l][i];
            });
        }));
        for (int l = 0; l < NL; ++l) {
            e.mm(L[l].k_ctx, cb + (size_t)l * T * E, kc, n);
            e.mm(L[l].v_ctx, cb + (size_t)l * T * E, vc, n);
            sycl::half *K = Kc[l], *Vv = Vc[l];
            const float *kn = f32(L[l].k_ctx_norm), *kc_ = kc, *vc_ = vc;
            const int km = kmask[l], kd_ = kd;
            const float th = theta;
            e.pr("dsp_ctx_kv", d.q.submit([&](sycl::handler &hd) {
                sycl::local_accessor<float, 1> slm(HD / SG + HD, hd);
                hd.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)n * HKV * HD), sycl::range<1>(HD)),
                                [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                    const int gi = (int)it.get_group(0), t = gi / HKV, hh_ = gi % HKV, dd = (int)it.get_local_id(0);
                    const size_t i = (size_t)t * kd_ + hh_ * HD + dd;
                    float ko;
                    head_norm_rope(it, kc_[i], kn, pos0 + t, th, ep, &slm[0], ko);
                    const size_t o = (size_t)((pos0 + t) & km) * kd_ + hh_ * HD + dd;
                    K[o] = sycl::half(ko);
                    Vv[o] = sycl::half(vc_[i]);
                });
            }));
        }
        r_last = n - 1;
    }

    // n guesses (n <= B - 1) for positions P0 + 1.. after the token t0 (on the card) at P0; returns them
    // (t0h: the same token on the host, for an engine whose embedding table stays in host memory)
    std::vector<int32_t> draft(int P0, const int32_t *t0, int n, int32_t t0h = -1) {
        if (n < 1 || n > B - 1) throw std::runtime_error("dspark: 1 to 7 guesses");
        if (r_last < 0) throw std::runtime_error("dspark: no context row (nothing injected)");
        if (P0 + B > cap) throw std::runtime_error("dspark: context full");
        const HParams &h = e.m.hp;
        const int E_ = E, F = (int)L[0].gate.t->rows();
        // slot 0: the target's normed embedding of t0; slots 1..7: the mask embedding
        if (e.m.tok_embd.p) e.pr("dsp_embd", ops::get_rows(d.q, *e.m.tok_embd.t, e.m.tok_embd.p, t0, x, 1));
        else {
            if (t0h < 0) throw std::runtime_error("dspark: the engine's embedding table is in host memory: pass t0 on the host");
            e.embed(&t0h, 1, x);
        }
        e.pr("dsp_embd", ops::rms_norm(d.q, x, x, e.f32(e.m.tok_norm), E, 1, h.eps));
        {
            float *x_ = x;
            const float *me = f32(mask);
            e.pr("dsp_mask", d.q.parallel_for(sycl::range<2>(B - 1, (size_t)E), [=](sycl::id<2> id) {
                x_[(size_t)(id[0] + 1) * E_ + id[1]] = me[id[1]];
            }));
        }
        for (int l = 0; l < NL; ++l) {
            const DL &a = L[l];
            if (mmx) norm_h(x, a.attn_norm, xh16);
            else e.pr("dsp_norm", ops::rms_norm(d.q, x, nullptr, f32(a.attn_norm), E, B, eps, -1, -1, hl));
            mm(l, 0, a.wq, hl, xh16, q, "dsp_q");
            mm(l, 1, a.wk, hl, xh16, k, "dsp_k");
            mm(l, 2, a.wv, hl, xh16, v, "dsp_v");
            { // q and k: per-head norm and RoPE at P0 + slot
                float *q_ = q, *k_ = k;
                const float *qn = f32(a.q_norm), *kn = f32(a.k_norm);
                const float th = theta, ep = eps;
                e.pr("dsp_qk", d.q.submit([&](sycl::handler &hd) {
                    sycl::local_accessor<float, 1> slm(HD / SG + HD, hd);
                    hd.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)B * (HQ + HKV) * HD), sycl::range<1>(HD)),
                                    [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                        const int gi = (int)it.get_group(0), dd = (int)it.get_local_id(0);
                        const int t = gi / (HQ + HKV), hh_ = gi % (HQ + HKV);
                        const bool isq = hh_ < HQ;
                        float *p = isq ? q_ + ((size_t)t * HQ + hh_) * HD : k_ + ((size_t)t * HKV + (hh_ - HQ)) * HD;
                        const float xv = p[dd];
                        float o;
                        head_norm_rope(it, xv, isq ? qn : kn, P0 + t, th, ep, &slm[0], o);
                        sycl::group_barrier(it.get_group());
                        p[dd] = o;
                    });
                }));
            }
            attend(l, P0);
            mm(l, 3, a.wo, attl, ah, ao, "dsp_o");
            add(x, ao, (size_t)B * E);
            if (mmx) norm_h(x, a.ffn_norm, xh16);
            else e.pr("dsp_norm", ops::rms_norm(d.q, x, nullptr, f32(a.ffn_norm), E, B, eps, -1, -1, hl));
            mm(l, 4, a.gate, hl, xh16, gt, "dsp_gate_w");
            mm(l, 5, a.up, hl, xh16, upb, "dsp_up_w");
            {
                const float *g_ = gt, *u_ = upb;
                float *gl_ = gl;
                sycl::half *gh_ = gh;
                const bool toh = mmx;
                const size_t lf = xlane_floats(F);
                e.pr("dsp_silu", d.q.parallel_for(sycl::range<2>(B, (size_t)F), [=](sycl::id<2> id) {
                    const size_t i = id[0] * (size_t)F + id[1];
                    const float gv = g_[i];
                    const float o = gv / (1.0f + sycl::exp(-gv)) * u_[i];
                    if (toh) gh_[i] = (sycl::half)o;
                    else gl_[id[0] * lf + xlane_at((int)id[1])] = o;
                }));
            }
            mm(l, 6, a.down, gl, gh, ao, "dsp_down_w");
            add(x, ao, (size_t)B * E);
        }
        e.pr("dsp_norm", ops::rms_norm(d.q, x, y, f32(onorm), E, B, eps, -1, -1, yl));
        // the chained head
        d.q.memset(s, 0, sizeof(float) * R);
        const float *ctx = rrows + (size_t)r_last * E;
        const bool late = fold && pt8 && stop_hi > 0.0f && n >= 5; // slots 4..n read later, if the chain holds
        const int lx = (int)xlane_floats(E);
        if (late) {
            MultiJobs mj;
            multi_add(mj, hv, yl + (size_t)1 * lx, base, 1, lx, Vh);
            e.pr("dsp_base", gemv_multi_m(d.q, mj, 3, true, 1));
        } else if (fold) { // W_lm y_i of slots 1..n, one read of W_lm (lane-order rows: multi_m, bench_gemv card 3 3 rows 777 us)
            for (int i0 = 0; i0 < n; i0 += 8) { // up to 8 rows per read (gemv_multi_m)
                const int ni = std::min(8, n - i0);
                const float *xi = yl + (size_t)(1 + i0) * lx;
                float *bi = base + (size_t)i0 * Vh;
                if (ni == 1) e.pr("dsp_base", gemv_v(d.q, hv, xi, lx, bi, Vh, 1, Tune{1, 1}, true));
                else {
                    MultiJobs mj;
                    multi_add(mj, hv, xi, bi, 1, lx, Vh);
                    e.pr("dsp_base", gemv_multi_m(d.q, mj, ni, true, 1));
                }
            }
        }
        int nd = n; // guesses submitted
        for (int i = 1; i <= nd; ++i) {
            if (late && i == 4) { // guesses 4..n only if the chain of guesses 1-3 holds (read on the host)
                float p3[3];
                d.get(p3, gp, 3);
                if (keep_chain_below(p3, 3, stop_at(4, true), QK)) { nd = 3; break; }
                MultiJobs mj;
                multi_add(mj, hv, yl + (size_t)4 * lx, base + (size_t)3 * Vh, 1, lx, Vh);
                e.pr("dsp_base_late", gemv_multi_m(d.q, mj, n - 3, true, 1));
            }
            {
                float *c = cat;
                const float *s_ = s, *yi = y + (size_t)i * E, *cx = ctx;
                const sycl::ext::oneapi::bfloat16 *w1p = (const sycl::ext::oneapi::bfloat16 *)w1.p;
                const int32_t *prev = i == 1 ? t0 : gids + (i - 2);
                e.pr("dsp_cat", d.q.parallel_for(sycl::range<1>((size_t)2 * R + 2 * E_), [=](sycl::id<1> id) {
                    const int j = (int)id[0];
                    float vv;
                    if (j < R) vv = s_[j];
                    else if (j < 2 * R) vv = (float)w1p[(size_t)prev[0] * R + (j - R)];
                    else if (j < 2 * R + E_) vv = yi[j - 2 * R];
                    else vv = cx[j - 2 * R - E_];
                    c[j] = vv;
                }));
            }
            e.mm(jp, cat, uu, 1);
            {
                const float *u_ = uu, *bj = f32(jpb);
                float *s_ = s, *z_ = z;
                e.pr("dsp_gate", d.q.parallel_for(sycl::range<1>(R), [=](sycl::id<1> id) {
                    const int j = (int)id[0];
                    const float ga = 1.0f / (1.0f + sycl::exp(-(u_[j] + bj[j])));
                    const float cand = sycl::tanh(u_[R + j] + bj[R + j]);
                    z_[j] = sycl::tanh(u_[2 * R + j] + bj[2 * R + j]);
                    s_[j] = ga * s_[j] + (1.0f - ga) * cand;
                }));
            }
            const float *gp_ = gp, thr = stop_at(i, late);
            const int ii = i;
            const KeepTable qk = QK;
            // the chain's keep chance before guess i (the same float products as draft()'s count at the end)
            auto stopped = [=]() { return keep_chain_below(gp_, ii - 1, thr, qk); };
            if (fold && pt8) { // 4 columns per thread, one 4-byte read per latent
                const float *b_ = base + (size_t)(i - 1) * Vh, *c_ = cvec, *z_ = z, *ps = Ps;
                const int8_t *q8 = Pt8;
                float *lg_ = lgd;
                const int Vp_ = Vh, n4 = (Vh + 3) / 4;
                e.pr("dsp_corr", d.q.submit([&](sycl::handler &hd) {
                    sycl::local_accessor<float, 1> zs(R, hd);
                    hd.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)(n4 + 255) / 256 * 256), sycl::range<1>(256)), [=](sycl::nd_item<1> it) {
                        if (ii > 1 && stopped()) return; // the whole work-group (before its barrier)
                        const int li = (int)it.get_local_id(0);
                        zs[li] = z_[li];
                        sycl::group_barrier(it.get_group());
                        const int t4 = (int)it.get_global_id(0);
                        if (t4 >= n4) return;
                        float acc[4] = {0.0f, 0.0f, 0.0f, 0.0f};
#pragma unroll 8
                        for (int j = 0; j < R; ++j) {
                            const sycl::vec<int8_t, 4> qv = *reinterpret_cast<const sycl::vec<int8_t, 4> *>(q8 + (size_t)j * Vp_ + 4 * t4);
#pragma unroll
                            for (int k = 0; k < 4; ++k) acc[k] = sycl::fma(zs[j], (float)qv[k], acc[k]);
                        }
#pragma unroll
                        for (int k = 0; k < 4; ++k) {
                            const int r = 4 * t4 + k;
                            if (r < Vp_) lg_[r] = sycl::tanh((b_[r] + (acc[k] * ps[r] + c_[r])) * (1.0f / 30.0f)) * 30.0f;
                        }
                    });
                }));
            } else if (fold) {
                const float *b_ = base + (size_t)(i - 1) * Vp, *c_ = cvec, *z_ = z;
                const sycl::ext::oneapi::bfloat16 *pt = Pt;
                float *lg_ = lgd;
                const int Vp_ = Vp;
                e.pr("dsp_corr", d.q.submit([&](sycl::handler &hd) {
                    sycl::local_accessor<float, 1> zs(R, hd);
                    hd.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)(Vp + 255) / 256 * 256), sycl::range<1>(256)), [=](sycl::nd_item<1> it) {
                        const int li = (int)it.get_local_id(0);
                        zs[li] = z_[li];
                        sycl::group_barrier(it.get_group());
                        const int r = (int)it.get_global_id(0);
                        if (r >= Vp_) return;
                        float acc = 0.0f;
                        for (int j = 0; j < R; ++j) acc += zs[j] * (float)pt[(size_t)j * Vp_ + r];
                        lg_[r] = sycl::tanh((b_[r] + (acc + c_[r])) * (1.0f / 30.0f)) * 30.0f;
                    });
                }));
            } else {
                e.mm(ho, z, eh, 1);
                {
                    const float *yi = y + (size_t)i * E, *e_ = eh, *bh = f32(hob);
                    float *hs_ = hs;
                    e.pr("dsp_hsum", d.q.parallel_for(sycl::range<1>((size_t)E), [=](sycl::id<1> id) { hs_[id] = yi[id] + (e_[id] + bh[id]); }));
                }
                e.mm(e.m.output, hs, lgd, 1);
                e.pr("dsp_softcap", ops::softcap(d.q, lgd, (size_t)Vp, 30.0f));
            }
            e.pr("dsp_argmax", ops::argmax_p_rows(d.q, lgd, Vh, Vs, 1, gids + (i - 1), gp + (i - 1), amv, ami, ams, hmap));
        }
        std::vector<int32_t> r(nd);
        d.get(r.data(), gids, nd);
        probs.resize(nd);
        d.get(probs.data(), gp, nd);
        if (fold && pt8) { // the guesses computed (stop_at: guess m + 1 needs the chain of guesses 1..m)
            float pr = 1.0f;
            int m = 0;
            for (; m < nd && !(pr < stop_at(m + 1, late)); ++m) pr *= QK.v[keep_bucket(probs[m])];
            r.resize(m);
            probs.resize(m);
        }
        return r;
    }

    void add(float *a, const float *b, size_t n) {
        e.pr("dsp_add", d.q.parallel_for(sycl::range<1>(n), [=](sycl::id<1> i) { a[i] += b[i]; }));
    }

    // non-causal attention of the 8 block slots of layer l: context keys lo..P0-1 (cache) then the 8 block keys
    void attend(int l, int P0) {
        if (split == 2) { attend_split2(l, P0); return; }
        if (split == 1) { attend_split(l, P0); return; }
        const int lo = lo_of(l, P0);
        const int nctx = P0 - lo, nk = nctx + B;
        const sycl::half *K = Kc[l], *Vv = Vc[l];
        const float *q_ = q, *k_ = k, *v_ = v;
        float *sc_ = sc, *att_ = attl;
        const size_t la = xlane_floats(HQ * HD);
        const size_t sk = sc_keys;
        const int km = kmask[l], kd_ = kd;
        const float scale = 1.0f / std::sqrt((float)HD);
        e.pr(full_l[l] ? "dsp_attn_full" : "dsp_attn", d.q.submit([&](sycl::handler &hd) {
            sycl::local_accessor<float, 1> slm(HD, hd);
            hd.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)B * HQ * AWG), sycl::range<1>(AWG)),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                const int gi = (int)it.get_group(0), t = gi / HQ, hq = gi % HQ, kvh = hq / (HQ / HKV), li = (int)it.get_local_id(0);
                float *qs = &slm[0];
                if (li < HD) qs[li] = q_[((size_t)t * HQ + hq) * HD + li];
                sycl::group_barrier(it.get_group());
                float *srow = sc_ + (size_t)gi * sk;
                float mx = -INFINITY;
                for (int j = li; j < nk; j += AWG) {
                    float dot = 0.0f;
                    if (j < nctx) {
                        const sycl::half *kp = K + (size_t)((lo + j) & km) * kd_ + kvh * HD;
                        for (int dd = 0; dd < HD; ++dd) dot += qs[dd] * (float)kp[dd];
                    } else {
                        const float *kp = k_ + ((size_t)(j - nctx) * HKV + kvh) * HD;
                        for (int dd = 0; dd < HD; ++dd) dot += qs[dd] * kp[dd];
                    }
                    const float sv = dot * scale;
                    srow[j] = sv;
                    mx = sycl::max(mx, sv);
                }
                mx = sycl::reduce_over_group(it.get_group(), mx, sycl::maximum<float>());
                float sum = 0.0f;
                for (int j = li; j < nk; j += AWG) {
                    const float p = sycl::exp(srow[j] - mx);
                    srow[j] = p;
                    sum += p;
                }
                sum = sycl::reduce_over_group(it.get_group(), sum, sycl::plus<float>());
                sycl::group_barrier(it.get_group());
                // P.V: thread li takes dimension li % HD, keys of parity li / HD
                const int dd = li % HD, half = li / HD;
                float acc = 0.0f;
                for (int j = half; j < nk; j += AWG / HD) {
                    const float vv = j < nctx ? (float)Vv[(size_t)((lo + j) & km) * kd_ + kvh * HD + dd]
                                              : v_[((size_t)(j - nctx) * HKV + kvh) * HD + dd];
                    acc += srow[j] * vv;
                }
                sycl::group_barrier(it.get_group());
                float *pv = &slm[0]; // q is no longer needed
                if (half == 1) pv[dd] = acc;
                sycl::group_barrier(it.get_group());
                if (half == 0) att_[(size_t)t * la + xlane_at(hq * HD + dd)] = (acc + pv[dd]) / sum;
            });
        }));
    }

    // merge the spans per row into attl (lane order)
    void attn_combine(int nch) {
        constexpr int G = HQ / HKV;
        const float *pO_ = pO, *pM_ = pM, *pL_ = pL;
        float *att_ = attl;
        sycl::half *ah_ = o_mx() ? ah : nullptr;
        const size_t la = xlane_floats(HQ * HD);
        e.pr("dsp_attn_comb", d.q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)HKV * NR * HD), sycl::range<1>(HD)),
                                                [=](sycl::nd_item<1> it) {
            const int gi = (int)it.get_group(0), kvh = gi / NR, r = gi % NR, dd = (int)it.get_local_id(0);
            const float *m = pM_ + (size_t)gi * nch, *lsum = pL_ + (size_t)gi * nch, *o = pO_ + (size_t)gi * nch * HD;
            float mx = -INFINITY;
            for (int cc = 0; cc < nch; ++cc) mx = sycl::max(mx, m[cc]);
            float su = 0.0f, ov = 0.0f;
            for (int cc = 0; cc < nch; ++cc) {
                const float f = sycl::exp(m[cc] - mx);
                su += lsum[cc] * f;
                ov += o[(size_t)cc * HD + dd] * f;
            }
            if (ah_) ah_[(size_t)(r / G) * HQ * HD + (kvh * G + r % G) * HD + dd] = (sycl::half)(ov / su);
            else att_[(size_t)(r / G) * la + xlane_at((kvh * G + r % G) * HD + dd)] = ov / su;
        }));
    }

    // attend_split with register tiles (as the model's attention kernels): a work-group of 128 threads per (key head,
    // span); scores: lane = key (16 per sub-group), the 24 rows' queries come in as 16-lane reads per 16 dimensions and
    // each product takes its value with a constant-index select; P.V: thread = dimension for all 24 rows, the rows'
    // probabilities come in 16 keys at a time the same way. Running max / sum per row as attend_split, same combine
    void attend_split2(int l, int P0) {
        const int lo = lo_of(l, P0);
        const int nctx = P0 - lo, nk = nctx + B;
        const int span = CH * std::max(1, (nk + CH * NCH - 1) / (CH * NCH)), nch = (nk + span - 1) / span;
        if (attn_var == 4 && full_l[l]) { // the matrix engines (the full layer)
            e.pr("dsp_block_kv", dsp_block_to_cache(d.q, k, v, Kc[l], Vc[l], P0, kd, kmask[l]));
            e.pr("dsp_attn_full", dsp_attn_span_x(d.q, q, Kc[l], Vc[l], nk, kd, span, nch, pO, pM, pL, lo, kmask[l]));
            attn_combine(nch);
            return;
        }
        auto go = [&](auto f) { return f(d.q, q, k, v, Kc[l], Vc[l], lo, nctx, kmask[l], kd, span, nch, pO, pM, pL); };
        e.pr(full_l[l] ? "dsp_attn_full" : "dsp_attn",
             attn_var >= 3 ? go(dsp_attn_span<3>) : attn_var == 2 ? go(dsp_attn_span<2>) : attn_var == 1 ? go(dsp_attn_span<1>)
                                                                                         : go(dsp_attn_span<0>));
        attn_combine(nch);
    }

    // attend() by key spans: work-group (key head kvh, span c) scores the NR = 24 rows of kvh (row r = slot r / 3,
    // query head kvh * 3 + r % 3) against its keys in passes of CH, keeping a running max / sum / P.V per row; thread
    // (key or dimension li % 128, rows 12 * (li / 128) ..+12). The combine launch merges the spans per row.
    void attend_split(int l, int P0) {
        constexpr int G = HQ / HKV, WG = 256, RH = NR / 2;
        const int lo = lo_of(l, P0);
        const int nctx = P0 - lo, nk = nctx + B;
        const int span = CH * std::max(1, (nk + CH * NCH - 1) / (CH * NCH)), nch = (nk + span - 1) / span;
        const sycl::half *K = Kc[l], *Vv = Vc[l];
        const float *q_ = q, *k_ = k, *v_ = v;
        float *pO_ = pO, *pM_ = pM, *pL_ = pL, *att_ = attl;
        const size_t la = xlane_floats(HQ * HD);
        const int km = kmask[l], kd_ = kd;
        const float scale = 1.0f / std::sqrt((float)HD);
        e.pr(full_l[l] ? "dsp_attn_full" : "dsp_attn", d.q.submit([&](sycl::handler &hd) {
            sycl::local_accessor<float, 1> qs(NR * HD, hd), ps(NR * CH, hd), rs(3 * NR, hd);
            hd.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)HKV * nch * WG), sycl::range<1>(WG)),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                const int gi = (int)it.get_group(0), kvh = gi / nch, c = gi % nch, li = (int)it.get_local_id(0);
                const int ki = li % CH, rg = li / CH;
                const auto sg = it.get_sub_group();
                const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id(), nsg = WG / SG;
                for (int i = li; i < NR * HD; i += WG) {
                    const int r = i / HD, dd = i % HD;
                    qs[i] = q_[((size_t)(r / G) * HQ + kvh * G + r % G) * HD + dd] * scale;
                }
                if (li < NR) { rs[li] = -INFINITY; rs[NR + li] = 0.0f; }
                float acc[RH];
#pragma unroll
                for (int r = 0; r < RH; ++r) acc[r] = 0.0f;
                const int j0 = c * span, j1 = sycl::min(nk, j0 + span);
                for (int sb = j0; sb < j1; sb += CH) {
                    const int nkc = sycl::min(CH, j1 - sb);
                    sycl::group_barrier(it.get_group());
                    // scores of key sb + ki for rows rg * 12 ..+12
                    {
                        float sv[RH];
#pragma unroll
                        for (int r = 0; r < RH; ++r) sv[r] = 0.0f;
                        if (ki < nkc) {
                            const int j = sb + ki;
                            const bool cache = j < nctx;
                            const sycl::half *kp = K + (size_t)((lo + j) & km) * kd_ + kvh * HD;
                            const float *kf = k_ + ((size_t)(j - nctx) * HKV + kvh) * HD;
                            for (int d0 = 0; d0 < HD; d0 += 32) {
                                float kv[32];
                                if (cache) {
#pragma unroll
                                    for (int u = 0; u < 4; ++u) {
                                        const sycl::vec<sycl::half, 8> h8 = *reinterpret_cast<const sycl::vec<sycl::half, 8> *>(kp + d0 + 8 * u);
#pragma unroll
                                        for (int w = 0; w < 8; ++w) kv[8 * u + w] = (float)h8[w];
                                    }
                                } else {
#pragma unroll
                                    for (int w = 0; w < 32; ++w) kv[w] = kf[d0 + w];
                                }
#pragma unroll
                                for (int r = 0; r < RH; ++r) {
                                    const float *qr = &qs[(rg * RH + r) * HD + d0];
#pragma unroll
                                    for (int w = 0; w < 32; ++w) sv[r] += qr[w] * kv[w];
                                }
                            }
                        }
#pragma unroll
                        for (int r = 0; r < RH; ++r) ps[(rg * RH + r) * CH + ki] = ki < nkc ? sv[r] : -INFINITY;
                    }
                    sycl::group_barrier(it.get_group());
                    // running max and sum per row; rs[2 NR + r] = the factor for the P.V sums so far
                    for (int r = sgi; r < NR; r += nsg) {
                        float m = -INFINITY;
                        for (int i = ln; i < CH; i += SG) m = sycl::max(m, ps[r * CH + i]);
                        m = sycl::reduce_over_group(sg, m, sycl::maximum<float>());
                        const float mo = rs[r], mn = sycl::max(mo, m);
                        float su = 0.0f;
                        for (int i = ln; i < CH; i += SG) {
                            const float pv = sycl::exp(ps[r * CH + i] - mn);
                            ps[r * CH + i] = pv;
                            su += pv;
                        }
                        su = sycl::reduce_over_group(sg, su, sycl::plus<float>());
                        if (ln == 0) {
                            const float f = sycl::exp(mo - mn);
                            rs[r] = mn; rs[NR + r] = rs[NR + r] * f + su; rs[2 * NR + r] = f;
                        }
                    }
                    sycl::group_barrier(it.get_group());
                    // P.V for dimension ki, rows rg * 12 ..+12
#pragma unroll
                    for (int r = 0; r < RH; ++r) acc[r] *= rs[2 * NR + rg * RH + r];
                    for (int kk = 0; kk < nkc; ++kk) {
                        const int j = sb + kk;
                        const float vv = j < nctx ? (float)Vv[(size_t)((lo + j) & km) * kd_ + kvh * HD + ki]
                                                  : v_[((size_t)(j - nctx) * HKV + kvh) * HD + ki];
#pragma unroll
                        for (int r = 0; r < RH; ++r) acc[r] += ps[(rg * RH + r) * CH + kk] * vv;
                    }
                }
#pragma unroll
                for (int r = 0; r < RH; ++r) pO_[(((size_t)kvh * NR + rg * RH + r) * nch + c) * HD + ki] = acc[r];
                if (li < NR) { pM_[((size_t)kvh * NR + li) * nch + c] = rs[li]; pL_[((size_t)kvh * NR + li) * nch + c] = rs[NR + li]; }
            });
        }));
        attn_combine(nch);
    }
};

} // namespace ink
