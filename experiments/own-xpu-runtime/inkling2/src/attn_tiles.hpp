// attn_tiles.hpp: the attention scores and P.V of steps of many tokens (prompts) as register tiles. A work-group takes
// MT queries x the G query heads of one KV head (NR = MT*G rows); a lane keeps NR running sums, so every cache value
// it loads serves NR rows, and a row's values come in as one 16-lane load that each product takes with a
// constant-index select_from_group (a register region, no data movement). Every sum keeps the order of the
// writing-step kernels of fused.hpp (attn_scores: d ascending from 0.0f, then the scale, then the bias; P.V: the
// block order of attn_pv_bo_part / attn_pv_bo_sum: within a block of PVB key positions keys ascending from 0.0f,
// then the blocks ascending from 0.0f), so the results are the same bits.
//  - A block's rows cover slightly different key ranges (each query's window ends at its own position). Keys outside a
//    row's [lo, p] add a product of zero to that row (P.V) or are not stored (scores). A zero product leaves a sum
//    unchanged: the sums start at +0.0f and never become -0.0f (round to nearest gives +0 for x + (-x)), and the cache
//    values are finite, so 0 * v is +-0 and s + (+-0) == s.
//  - Only positions up to the step's last are read (the cache past it is not written yet). A position's cache slot is
//    position & km (windowed layers keep a ring; km + 1 is a multiple of PVB, so 16-key reads never wrap).
#pragma once
#include "fused.hpp"

namespace ink::fz {

// scores with the relative bias computed in place: P[(t*nh + h)*ldp + j - lo] = (q . k_j) * scale (+ the bias when
// p - j < ext), the bias = sum over i of rel_bias[(p - j)*nr + i] * Rc[(t*nh + h)*nr + i], i ascending from 0.0f (the
// table attn_prep builds, entry for entry). A work-group: one block of MT queries, one KV head, 16*SGW keys (a lane
// per key). wmax (layers without a window): also each row's maximum per 16 keys, wmax[row * nsgmax + j / 16], as
// attn_scores_g writes it for attn_softmax_sum (every row's keys start at 0, so a sub-group is one group of 16)
template <int MT, int G, int SGW>
inline sycl::event attn_scores_tile(sycl::queue &q, const float *Q, const sycl::half *K, const float *Rc, const float *rel_bias,
                                    int nr, int pos0, int ntok, int nh, int nkvh, int hd, int ext, int win, float scale, float *P,
                                    int ldp, int km = 0x7fffffff, float *wmax = nullptr, int nsgmax = 0) {
    if (wmax && win > 0) throw std::runtime_error("attn_scores_tile: group maxima only without a window");
    constexpr int PW = 16, NR = MT * G, KB = PW * SGW, NRL = 16;
    using HV = sycl::vec<sycl::half, 8>;
    if (hd != 128 || nh != nkvh * G || nr != NRL) throw std::runtime_error("attn_scores_tile: unsupported shape");
    const int nqb = (ntok + MT - 1) / MT;
    // keys of a block: from its first row's lo rounded down to 16 to its last row's position
    const int span = (win > 0 ? std::min(win, pos0 + ntok) + MT - 1 : pos0 + ntok) + 15;
    const int nkb = (span + KB - 1) / KB;
    const bool qfast = span >= 16384;
    return q.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nqb * nkvh, (size_t)nkb * KB), sycl::range<2>(1, KB)),
                          [=](sycl::nd_item<2> it) [[sycl::reqd_sub_group_size(PW)]] {
        auto sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
        // work-group order: from 16K keys, the query blocks of one (key block, KV head) run one after another, so a key
        // block is read from memory once and served from the L2 cache to the other query blocks (bench_attn 512
        // tokens: 100K keys 34.8 -> 31.8 ms; at 4K keys, keys fastest is faster). Only the order changes, not a value.
        const int lin = (int)(it.get_group(0) * it.get_group_range(1) + it.get_group(1));
        const int qb = qfast ? lin % nqb : lin / (nkb * nkvh), kvh = qfast ? (lin / nqb) % nkvh : (lin / nkb) % nkvh;
        const int kb = qfast ? lin / (nqb * nkvh) : lin % nkb;
        const int t0 = qb * MT, tn = sycl::min(MT, ntok - t0);
        const int pf = pos0 + t0, pl = pf + tn - 1;
        const int lof = win > 0 ? sycl::max(0, pf - win + 1) : 0;
        const int jb = (lof & ~15) + kb * KB + sgi * PW;
        if (jb > pl) return;
        const int j = jb + lane, jc = sycl::min(j, pl);
        const sycl::half *kr = K + (size_t)(jc & km) * nkvh * hd + kvh * hd;
        float acc[NR];
#pragma unroll
        for (int a = 0; a < NR; ++a) acc[a] = 0.0f;
#pragma unroll
        for (int d0 = 0; d0 < 128; d0 += PW) {
            const HV k0 = *(const HV *)(kr + d0), k1 = *(const HV *)(kr + d0 + 8);
            float ql[NR];
#pragma unroll
            for (int m = 0; m < MT; ++m) {
                const int t = t0 + sycl::min(m, tn - 1);
#pragma unroll
                for (int gi = 0; gi < G; ++gi) ql[m * G + gi] = Q[((size_t)t * nh + kvh * G + gi) * hd + d0 + lane];
            }
#pragma unroll
            for (int u = 0; u < PW; ++u) {
                const float kf = (float)(u < 8 ? k0[u] : k1[u - 8]);
#pragma unroll
                for (int a = 0; a < NR; ++a) acc[a] = mac(acc[a], sycl::select_from_group(sg, ql[a], u), kf);
            }
        }
#pragma unroll
        for (int m = 0; m < MT; ++m) {
            if (m >= tn) break;
            const int t = t0 + m, p = pos0 + t, lo = win > 0 ? sycl::max(0, p - win + 1) : 0;
            const bool in = j >= lo && j <= p;
            if (!wmax && !in) continue;
            const int dist = p - j;
            const bool rel = in && dist < ext;
            sycl::vec<float, 4> b[NRL / 4];
            if (rel) {
                const float *br = rel_bias + (size_t)dist * NRL;
#pragma unroll
                for (int i = 0; i < NRL / 4; ++i) b[i] = *(const sycl::vec<float, 4> *)(br + 4 * i);
            }
#pragma unroll
            for (int gi = 0; gi < G; ++gi) {
                const size_t g = (size_t)t * nh + kvh * G + gi;
                float s = acc[m * G + gi] * scale;
                if (rel) {
                    const float *rc = Rc + g * NRL;
                    float tb = 0.0f;
#pragma unroll
                    for (int i = 0; i < NRL / 4; ++i) {
                        const sycl::vec<float, 4> r = *(const sycl::vec<float, 4> *)(rc + 4 * i);
#pragma unroll
                        for (int k = 0; k < 4; ++k) tb = mac(tb, b[i][k], r[k]);
                    }
                    s = s + tb;
                }
                if (in) P[g * ldp + j - lo] = s;
                if (wmax) {
                    const float mxg = sycl::reduce_over_group(sg, in ? s : -INFINITY, sycl::maximum<float>());
                    if (lane == 0 && jb <= p) wmax[g * nsgmax + jb / PW] = mxg;
                }
            }
        }
    });
}

// P.V and the output gate on the transposed value cache Vt[(kvh*hd + c) * vld + j]: a work-group = one block of MT
// queries, one KV head, hd channels (lane = channel); keys in blocks of 16 ascending, the last ones one at a time.
// out = acc * (1 / (1 + exp(-gate))) as attn_pv_t
// inv: P holds exponentials and inv[row] = 1 / total (attn_softmax_sum); each value is P * inv as read (the normalized
// value attn_softmax_norm would store: the same product)
template <int MT, int G>
inline sycl::event attn_pv_tile(sycl::queue &q, const float *P, int ldp, const sycl::half *Vt, int vld, int pos0, int ntok, int nh,
                                int nkvh, int hd, int win, const float *gate, float *out, int km = 0x7fffffff, const float *inv = nullptr) {
    constexpr int PW = 16, NR = MT * G;
    using HV = sycl::vec<sycl::half, 8>;
    if (nh != nkvh * G || hd % PW || vld % 16) throw std::runtime_error("attn_pv_tile: unsupported shape");
    const int nqb = (ntok + MT - 1) / MT;
    return q.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nqb * nkvh, (size_t)hd), sycl::range<2>(1, (size_t)hd)),
                          [=](sycl::nd_item<2> it) [[sycl::reqd_sub_group_size(PW)]] {
        auto sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id();
        const int qb = (int)it.get_group(0) / nkvh, kvh = (int)it.get_group(0) % nkvh, c = (int)it.get_local_id(1);
        const int t0 = qb * MT, tn = sycl::min(MT, ntok - t0);
        const int pf = pos0 + t0, pl = pf + tn - 1;
        const int lof = win > 0 ? sycl::max(0, pf - win + 1) : 0;
        const sycl::half *row = Vt + (size_t)(kvh * hd + c) * vld;
        int lo[MT], pp[MT];
#pragma unroll
        for (int m = 0; m < MT; ++m) {
            pp[m] = m < tn ? pf + m : -1; // rows past the step take nothing
            lo[m] = win > 0 ? sycl::max(0, pf + m - win + 1) : 0;
        }
        float iv[NR];
#pragma unroll
        for (int a = 0; a < NR; ++a) iv[a] = inv ? inv[(size_t)(t0 + sycl::min(a / G, tn - 1)) * nh + kvh * G + a % G] : 1.0f;
        float acc[NR], tot[NR]; // acc: the current block of PVB positions; tot: the blocks so far, in order
#pragma unroll
        for (int a = 0; a < NR; ++a) { acc[a] = 0.0f; tot[a] = 0.0f; }
        auto flush = [&] {
#pragma unroll
            for (int a = 0; a < NR; ++a) { tot[a] += acc[a]; acc[a] = 0.0f; }
        };
        int j = lof & ~15;
        for (; j + 15 <= pl; j += 16) {
            if ((j & (PVB - 1)) == 0) flush();
            float pv[NR];
            const int jj = j + lane;
#pragma unroll
            for (int m = 0; m < MT; ++m) {
                const bool ok = jj >= lo[m] && jj <= pp[m];
#pragma unroll
                for (int gi = 0; gi < G; ++gi) {
                    const float *pr = P + ((size_t)(t0 + m) * nh + kvh * G + gi) * ldp;
                    pv[m * G + gi] = ok ? (inv ? pr[jj - lo[m]] * iv[m * G + gi] : pr[jj - lo[m]]) : 0.0f;
                }
            }
            const HV v0 = *(const HV *)(row + (j & km)), v1 = *(const HV *)(row + (j & km) + 8);
#pragma unroll
            for (int u = 0; u < PW; ++u) {
                const float vf = (float)(u < 8 ? v0[u] : v1[u - 8]);
#pragma unroll
                for (int a = 0; a < NR; ++a) acc[a] = mac(acc[a], sycl::select_from_group(sg, pv[a], u), vf);
            }
        }
        for (; j <= pl; ++j) {
            if ((j & (PVB - 1)) == 0) flush();
            const float vf = (float)row[j & km];
#pragma unroll
            for (int m = 0; m < MT; ++m) {
                const bool ok = j >= lo[m] && j <= pp[m];
#pragma unroll
                for (int gi = 0; gi < G; ++gi) {
                    const float *pr = P + ((size_t)(t0 + m) * nh + kvh * G + gi) * ldp;
                    acc[m * G + gi] = mac(acc[m * G + gi], (ok ? (inv ? pr[j - lo[m]] * iv[m * G + gi] : pr[j - lo[m]]) : 0.0f), vf);
                }
            }
        }
        flush();
#pragma unroll
        for (int m = 0; m < MT; ++m) {
            if (m >= tn) break;
#pragma unroll
            for (int gi = 0; gi < G; ++gi) {
                const size_t i = ((size_t)(t0 + m) * nh + kvh * G + gi) * hd + c;
                out[i] = tot[m * G + gi] * (1.0f / (1.0f + sycl::exp(-gate[i])));
            }
        }
    });
}

// attn_pv_tile split by key blocks (long contexts, where a few work-groups each walking every key leave the card
// idle): a work-group = one block of MT queries x one KV head x one block of PVB key positions; it writes each row's
// sum over that block (keys ascending from 0.0f, keys outside the row's range adding exact zeros) to part in
// attn_pv_bo_part's layout, part[((t*nh + h)*nblk + b)*hd + c] with b counted from the step's first row's lo / PVB;
// attn_pv_bo_sum then adds the blocks and applies the gate. Query blocks run fastest, so a value block is read from
// memory once for all of them. Same values as attn_pv_bo_part.
template <int MT, int G>
inline sycl::event attn_pv_tile_part(sycl::queue &q, const float *P, int ldp, const sycl::half *Vt, int vld, int pos0, int ntok,
                                     int nh, int nkvh, int hd, int win, float *part, int nblk, int km = 0x7fffffff,
                                     const float *inv = nullptr) {
    constexpr int PW = 16, NR = MT * G;
    using HV = sycl::vec<sycl::half, 8>;
    if (nh != nkvh * G || hd % PW || vld % 16) throw std::runtime_error("attn_pv_tile_part: unsupported shape");
    const int nqb = (ntok + MT - 1) / MT;
    const int b0 = (win > 0 ? std::max(0, pos0 - win + 1) : 0) / PVB;
    return q.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nqb * nkvh * nblk, (size_t)hd), sycl::range<2>(1, (size_t)hd)),
                          [=](sycl::nd_item<2> it) [[sycl::reqd_sub_group_size(PW)]] {
        auto sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id();
        const int gid = (int)it.get_group(0), qb = gid % nqb, kvh = (gid / nqb) % nkvh, b = gid / (nqb * nkvh);
        const int c = (int)it.get_local_id(1);
        const int t0 = qb * MT, tn = sycl::min(MT, ntok - t0);
        const int pf = pos0 + t0, pl = pf + tn - 1;
        const int lof = win > 0 ? sycl::max(0, pf - win + 1) : 0;
        const int kb = (b0 + b) * PVB;
        const int js = sycl::max(kb, lof & ~15), je = sycl::min(kb + PVB - 1, pl);
        const sycl::half *row = Vt + (size_t)(kvh * hd + c) * vld;
        int lo[MT], pp[MT];
#pragma unroll
        for (int m = 0; m < MT; ++m) {
            pp[m] = m < tn ? pf + m : -1;
            lo[m] = win > 0 ? sycl::max(0, pf + m - win + 1) : 0;
        }
        float iv[NR];
#pragma unroll
        for (int a = 0; a < NR; ++a) iv[a] = inv ? inv[(size_t)(t0 + sycl::min(a / G, tn - 1)) * nh + kvh * G + a % G] : 1.0f;
        float acc[NR];
#pragma unroll
        for (int a = 0; a < NR; ++a) acc[a] = 0.0f;
        int j = js;
        for (; j + 15 <= je; j += 16) {
            float pv[NR];
            const int jj = j + lane;
#pragma unroll
            for (int m = 0; m < MT; ++m) {
                const bool ok = jj >= lo[m] && jj <= pp[m];
#pragma unroll
                for (int gi = 0; gi < G; ++gi) {
                    const float *pr = P + ((size_t)(t0 + m) * nh + kvh * G + gi) * ldp;
                    pv[m * G + gi] = ok ? (inv ? pr[jj - lo[m]] * iv[m * G + gi] : pr[jj - lo[m]]) : 0.0f;
                }
            }
            const HV v0 = *(const HV *)(row + (j & km)), v1 = *(const HV *)(row + (j & km) + 8);
#pragma unroll
            for (int u = 0; u < PW; ++u) {
                const float vf = (float)(u < 8 ? v0[u] : v1[u - 8]);
#pragma unroll
                for (int a = 0; a < NR; ++a) acc[a] = mac(acc[a], sycl::select_from_group(sg, pv[a], u), vf);
            }
        }
        for (; j <= je; ++j) {
            const float vf = (float)row[j & km];
#pragma unroll
            for (int m = 0; m < MT; ++m) {
                const bool ok = j >= lo[m] && j <= pp[m];
#pragma unroll
                for (int gi = 0; gi < G; ++gi) {
                    const float *pr = P + ((size_t)(t0 + m) * nh + kvh * G + gi) * ldp;
                    acc[m * G + gi] = mac(acc[m * G + gi], (ok ? (inv ? pr[j - lo[m]] * iv[m * G + gi] : pr[j - lo[m]]) : 0.0f), vf);
                }
            }
        }
#pragma unroll
        for (int m = 0; m < MT; ++m) {
            if (m >= tn) break;
#pragma unroll
            for (int gi = 0; gi < G; ++gi)
                part[(((size_t)(t0 + m) * nh + kvh * G + gi) * nblk + b) * hd + c] = acc[m * G + gi];
        }
    });
}

} // namespace ink::fz
