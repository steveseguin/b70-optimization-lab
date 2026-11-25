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
// CPL: channels per lane (c and c + hd / CPL ...): every P value a lane loads and selects serves CPL channels' sums;
// each (row, channel) sum still takes its keys ascending, so the values are CPL 1's
// EX: P holds the raw scores (attn_softmax_sum with mout wrote only each row's maximum pmx and 1 / total inv): each
// value is exp(score - maximum) times inv as it is read, the softmax's own expression, so the same values as reading
// its exponentials (P written once less)
template <int MT, int G, int CPL = 1, bool EX = false>
inline sycl::event attn_pv_tile(sycl::queue &q, const float *P, int ldp, const sycl::half *Vt, int vld, int pos0, int ntok, int nh,
                                int nkvh, int hd, int win, const float *gate, float *out, int km = 0x7fffffff, const float *inv = nullptr,
                                const float *pmx = nullptr) {
    constexpr int PW = 16, NR = MT * G;
    using HV = sycl::vec<sycl::half, 8>;
    if (nh != nkvh * G || hd % (PW * CPL) || vld % 16) throw std::runtime_error("attn_pv_tile: unsupported shape");
    const int nqb = (ntok + MT - 1) / MT, nl = hd / CPL;
    return q.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nqb * nkvh, (size_t)nl), sycl::range<2>(1, (size_t)nl)),
                          [=](sycl::nd_item<2> it) [[sycl::reqd_sub_group_size(PW)]] {
        auto sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id();
        const int qb = (int)it.get_group(0) / nkvh, kvh = (int)it.get_group(0) % nkvh, c0 = (int)it.get_local_id(1);
        const int t0 = qb * MT, tn = sycl::min(MT, ntok - t0);
        const int pf = pos0 + t0, pl = pf + tn - 1;
        const int lof = win > 0 ? sycl::max(0, pf - win + 1) : 0;
        const sycl::half *rows[CPL];
#pragma unroll
        for (int k = 0; k < CPL; ++k) rows[k] = Vt + (size_t)(kvh * hd + c0 + k * nl) * vld;
        int lo[MT], pp[MT];
#pragma unroll
        for (int m = 0; m < MT; ++m) {
            pp[m] = m < tn ? pf + m : -1; // rows past the step take nothing
            lo[m] = win > 0 ? sycl::max(0, pf + m - win + 1) : 0;
        }
        float iv[NR], mr[NR];
#pragma unroll
        for (int a = 0; a < NR; ++a) {
            const size_t ia = (size_t)(t0 + sycl::min(a / G, tn - 1)) * nh + kvh * G + a % G;
            iv[a] = inv ? inv[ia] : 1.0f;
            mr[a] = EX ? pmx[ia] : 0.0f;
        }
        // the value of row a at P entry x (EX: the softmax's exponential first)
        auto pval = [&](float x, int a) {
            if constexpr (EX) x = sycl::exp(x - mr[a]);
            return inv ? x * iv[a] : x;
        };
        float acc[CPL][NR], tot[CPL][NR]; // acc: the current block of PVB positions; tot: the blocks so far, in order
#pragma unroll
        for (int k = 0; k < CPL; ++k)
#pragma unroll
            for (int a = 0; a < NR; ++a) { acc[k][a] = 0.0f; tot[k][a] = 0.0f; }
        auto flush = [&] {
#pragma unroll
            for (int k = 0; k < CPL; ++k)
#pragma unroll
                for (int a = 0; a < NR; ++a) { tot[k][a] += acc[k][a]; acc[k][a] = 0.0f; }
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
                    pv[m * G + gi] = ok ? pval(pr[jj - lo[m]], m * G + gi) : 0.0f;
                }
            }
            HV v0[CPL], v1[CPL];
#pragma unroll
            for (int k = 0; k < CPL; ++k) { v0[k] = *(const HV *)(rows[k] + (j & km)); v1[k] = *(const HV *)(rows[k] + (j & km) + 8); }
#pragma unroll
            for (int u = 0; u < PW; ++u) {
#pragma unroll
                for (int k = 0; k < CPL; ++k) {
                    const float vf = (float)(u < 8 ? v0[k][u] : v1[k][u - 8]);
#pragma unroll
                    for (int a = 0; a < NR; ++a) acc[k][a] = mac(acc[k][a], sycl::select_from_group(sg, pv[a], u), vf);
                }
            }
        }
        for (; j <= pl; ++j) {
            if ((j & (PVB - 1)) == 0) flush();
#pragma unroll
            for (int k = 0; k < CPL; ++k) {
                const float vf = (float)rows[k][j & km];
#pragma unroll
                for (int m = 0; m < MT; ++m) {
                    const bool ok = j >= lo[m] && j <= pp[m];
#pragma unroll
                    for (int gi = 0; gi < G; ++gi) {
                        const float *pr = P + ((size_t)(t0 + m) * nh + kvh * G + gi) * ldp;
                        acc[k][m * G + gi] = mac(acc[k][m * G + gi], (ok ? pval(pr[j - lo[m]], m * G + gi) : 0.0f), vf);
                    }
                }
            }
        }
        flush();
#pragma unroll
        for (int m = 0; m < MT; ++m) {
            if (m >= tn) break;
#pragma unroll
            for (int gi = 0; gi < G; ++gi)
#pragma unroll
                for (int k = 0; k < CPL; ++k) {
                    const size_t i = ((size_t)(t0 + m) * nh + kvh * G + gi) * hd + c0 + k * nl;
                    out[i] = tot[k][m * G + gi] * (1.0f / (1.0f + sycl::exp(-gate[i])));
                }
        }
    });
}

// windowed layers, prompt steps: attn_scores_tile + attn_softmax_norm + attn_pv_tile<MT, G, 1> in one work-group of
// 128 threads per MT queries x the G heads of one KV head. The rows' window scores go to the work-group's slice of
// scr (NR * span floats; query blocks [qb0, qb0 + nqbl)), written and read back by the same work-group, so mostly from
// the cache. (Keeping them in local memory instead: 50 KB per work-group at 4 queries, too few work-groups per core,
// 2,263 vs 621 us; 3K prompt profile, card 3.)
// Every value has those kernels' expression and order: a score = (q . k, d ascending from 0.0f) * scale + the bias
// (i ascending from 0.0f); the row maximum (any order) with the sink; the exponentials and their sum as
// attn_softmax_norm's 128 threads (thread l = 16 s + lane: keys lo + l + 128 k ascending from 0.0f; sg_sum over the
// 16 lanes; the 8 sums ascending from 0.0f; + exp(sink - maximum)) - here one sub-group per row, lane `lane` playing
// threads 16 s + lane; p = e * (1 / total); P.V per channel with the keys ascending within blocks of PVB positions
// and the blocks ascending from 0.0f (keys outside a row's window add 0 * v, as attn_pv_tile does), then the gate.
// The row maxima come from the score loop (any order gives the same maximum) and P.V multiplies each exponential by
// 1 / total as it reads it (the product attn_softmax_norm stores), so two passes over the rows are not needed.
// The same bits as the three kernels. span: floats per row (>= window + MT + 14, a multiple of 16).
template <int MT, int G>
inline sycl::event attn_win_tile(sycl::queue &q, const float *Q, const sycl::half *K, const float *Rc, const float *rel_bias, int nr,
                                 const float *sink, const sycl::half *Vt, int vld, int pos0, int ntok, int nh, int nkvh, int hd,
                                 int ext, int win, float scale, const float *gate, float *out, int km, int span, float *scr,
                                 int qb0, int nqbl) {
    constexpr int PW = 16, NR = MT * G, WG = 128, NSG = WG / PW, NRL = 16, AW = ops::ATT_WG;
    static_assert(AW == WG, "attn_win_tile: the softmax's work-group size");
    using HV = sycl::vec<sycl::half, 8>;
    if (hd != 128 || nh != nkvh * G || nr != NRL || win <= 0 || vld % 16 || span % 16 || span < win + MT + 14)
        throw std::runtime_error("attn_win_tile: unsupported shape");
    const int nqb = nqbl;
    if (!scr || qb0 < 0 || nqb <= 0) throw std::runtime_error("attn_win_tile: no scratch or no query blocks");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> Ml((size_t)NSG * NR + NR, h); // sub-group row maxima, then the rows' 1 / total
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)nqb * nkvh * WG), sycl::range<1>(WG)),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(PW)]] {
            auto sg = it.get_sub_group();
            const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
            const int qb = qb0 + (int)it.get_group(0) / nkvh, kvh = (int)it.get_group(0) % nkvh;
            float *gS = scr + (size_t)it.get_group(0) * NR * span;
            auto S = [&](size_t i) -> float & { return gS[i]; };
            const int t0 = qb * MT, tn = sycl::min(MT, ntok - t0);
            const int pf = pos0 + t0, pl = pf + tn - 1;
            const int lof = sycl::max(0, pf - win + 1), jb0 = lof & ~15;
            const int ngr = (pl - jb0) / PW + 1; // 16-key groups from jb0 to pl
            int lo[MT], pp[MT];
#pragma unroll
            for (int m = 0; m < MT; ++m) {
                pp[m] = m < tn ? pf + m : -1;
                lo[m] = sycl::max(0, pf + m - win + 1);
            }
            // scores (attn_scores_tile's lane-per-key sums); entries outside a row's window hold 0. Each lane keeps its
            // rows' maxima (a maximum is the same in any order), the sub-group's go to local memory
            float rmx[NR];
#pragma unroll
            for (int a = 0; a < NR; ++a) rmx[a] = -INFINITY;
            for (int gr = sgi; gr < ngr; gr += NSG) {
                const int j = jb0 + gr * PW + lane, jc = sycl::min(j, pl);
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
                    const int t = t0 + sycl::min(m, tn - 1), p = pos0 + t;
                    const bool in = m < tn && j >= lo[m] && j <= p;
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
                        S((size_t)(m * G + gi) * span + (j - jb0)) = in ? s : 0.0f;
                        if (in) rmx[m * G + gi] = sycl::fmax(rmx[m * G + gi], s);
                    }
                }
            }
#pragma unroll
            for (int a = 0; a < NR; ++a) {
                const float v = sycl::reduce_over_group(sg, rmx[a], sycl::maximum<float>());
                if (lane == 0) Ml[sgi * NR + a] = v;
            }
            sycl::group_barrier(it.get_group());
            // softmax (attn_softmax_norm): one sub-group per row; the exponentials stay in S, P.V multiplies them by
            // 1 / total as it reads them (the same products as attn_softmax_norm stores)
            for (int a = sgi; a < NR; a += NSG) {
                const int m = a / G;
                if (m >= tn) {
                    if (lane == 0) Ml[NSG * NR + a] = 0.0f;
                    continue;
                }
                const int t = t0 + m, p = pp[m], l0 = lo[m];
                const int base = a * span - jb0; // S(base + j) = key j of row a
                float mx = -INFINITY;
#pragma unroll
                for (int s8 = 0; s8 < NSG; ++s8) mx = sycl::fmax(mx, Ml[s8 * NR + a]);
                const float sk = sink[(size_t)t * nh + kvh * G + a % G];
                mx = sycl::fmax(mx, sk);
                float tot = 0.0f;
#pragma unroll
                for (int s8 = 0; s8 < AW / PW; ++s8) { // threads 16 s8 + lane of attn_softmax_norm
                    float acc = 0.0f;
                    for (int j = l0 + PW * s8 + lane; j <= p; j += AW) {
                        const float e = sycl::exp(S(base + j) - mx);
                        S(base + j) = e;
                        acc += e;
                    }
                    tot += sg_sum(sg, acc);
                }
                tot = tot + sycl::exp(sk - mx);
                if (lane == 0) Ml[NSG * NR + a] = 1.0f / tot;
            }
            sycl::group_barrier(it.get_group());
            // P.V (attn_pv_tile<MT, G, 1>): thread = channel
            const int c = (int)it.get_local_id(0);
            const sycl::half *vrow = Vt + (size_t)(kvh * hd + c) * vld;
            float acc[NR], tt[NR];
#pragma unroll
            for (int a = 0; a < NR; ++a) { acc[a] = 0.0f; tt[a] = 0.0f; }
            auto flush = [&] {
#pragma unroll
                for (int a = 0; a < NR; ++a) { tt[a] += acc[a]; acc[a] = 0.0f; }
            };
            int j = jb0;
            for (; j + 15 <= pl; j += PW) {
                if ((j & (PVB - 1)) == 0) flush();
                float pv[NR];
#pragma unroll
                for (int a = 0; a < NR; ++a) pv[a] = S((size_t)a * span + (j - jb0) + lane) * Ml[NSG * NR + a];
                const HV v0 = *(const HV *)(vrow + (j & km)), v1 = *(const HV *)(vrow + (j & km) + 8);
#pragma unroll
                for (int u = 0; u < PW; ++u) {
                    const float vf = (float)(u < 8 ? v0[u] : v1[u - 8]);
#pragma unroll
                    for (int a = 0; a < NR; ++a) acc[a] = mac(acc[a], sycl::select_from_group(sg, pv[a], u), vf);
                }
            }
            for (; j <= pl; ++j) {
                if ((j & (PVB - 1)) == 0) flush();
                const float vf = (float)vrow[j & km];
#pragma unroll
                for (int a = 0; a < NR; ++a) acc[a] = mac(acc[a], S((size_t)a * span + (j - jb0)) * Ml[NSG * NR + a], vf);
            }
            flush();
#pragma unroll
            for (int m = 0; m < MT; ++m) {
                if (m >= tn) break;
#pragma unroll
                for (int gi = 0; gi < G; ++gi) {
                    const size_t i = ((size_t)(t0 + m) * nh + kvh * G + gi) * hd + c;
                    out[i] = tt[m * G + gi] * (1.0f / (1.0f + sycl::exp(-gate[i])));
                }
            }
        });
    });
}
// INK_WIN_TILE=<queries per work-group>: 4 (default) or 8; 0 = the three kernels. 3K prompt profile (card 3), per
// layer-step: the three kernels 1,269 us, 2 queries 1,205, 4 827, 5 850, 6 906, 8 883
inline int win_tile_mt() {
    static const int v = std::getenv("INK_WIN_TILE") ? std::atoi(std::getenv("INK_WIN_TILE")) : 4;
    return v == 8 ? 8 : v > 0 ? 4 : 0;
}

// attn_pv_tile EX whose sub-groups share the exponentials: in each 16-key step sub-group s computes rows
// [s RS, (s + 1) RS) for its lane's key into local memory (two buffers, one barrier per step) and every sub-group reads
// all NR rows from there, so each exponential is computed once per work-group instead of once per sub-group. The same
// expression (exp(score - maximum) times 1 / total), so the same values as attn_pv_tile EX. hd 128 only.
template <int MT, int G, int CPL>
inline sycl::event attn_pv_tile_xs(sycl::queue &q, const float *P, int ldp, const sycl::half *Vt, int vld, int pos0, int ntok, int nh,
                                   int nkvh, int hd, int win, const float *gate, float *out, int km, const float *inv, const float *pmx) {
    constexpr int PW = 16, NR = MT * G, HD = 128, NL = HD / CPL, NSG = NL / PW, RS = NR / NSG;
    static_assert(HD % (PW * CPL) == 0 && NR % NSG == 0, "attn_pv_tile_xs: shape");
    using HV = sycl::vec<sycl::half, 8>;
    if (hd != HD || nh != nkvh * G || vld % 16 || !inv || !pmx) throw std::runtime_error("attn_pv_tile_xs: unsupported shape");
    const int nqb = (ntok + MT - 1) / MT;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> ex(2 * NR * PW, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nqb * nkvh, (size_t)NL), sycl::range<2>(1, (size_t)NL)),
                       [=](sycl::nd_item<2> it) [[sycl::reqd_sub_group_size(PW)]] {
            auto sg = it.get_sub_group();
            const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
            const int qb = (int)it.get_group(0) / nkvh, kvh = (int)it.get_group(0) % nkvh, c0 = (int)it.get_local_id(1);
            const int t0 = qb * MT, tn = sycl::min(MT, ntok - t0);
            const int pf = pos0 + t0, pl = pf + tn - 1;
            const int lof = win > 0 ? sycl::max(0, pf - win + 1) : 0;
            const sycl::half *rows[CPL];
#pragma unroll
            for (int k = 0; k < CPL; ++k) rows[k] = Vt + (size_t)(kvh * HD + c0 + k * NL) * vld;
            int lo[MT], pp[MT];
#pragma unroll
            for (int m = 0; m < MT; ++m) {
                pp[m] = m < tn ? pf + m : -1;
                lo[m] = win > 0 ? sycl::max(0, pf + m - win + 1) : 0;
            }
            float iv[NR], mr[NR];
#pragma unroll
            for (int a = 0; a < NR; ++a) {
                const size_t ia = (size_t)(t0 + sycl::min(a / G, tn - 1)) * nh + kvh * G + a % G;
                iv[a] = inv[ia];
                mr[a] = pmx[ia];
            }
            // this sub-group's rows of the shared exponentials: row a = sgi RS + r
            const float *xp[RS]; float xi[RS], xm[RS]; int xlo[RS], xpp[RS];
#pragma unroll
            for (int r = 0; r < RS; ++r) {
                const int a = sgi * RS + r, m = a / G, gi = a % G;
                const size_t ia = (size_t)(t0 + sycl::min(m, tn - 1)) * nh + kvh * G + gi;
                xi[r] = inv[ia]; xm[r] = pmx[ia];
                xpp[r] = m < tn ? pf + m : -1;
                xlo[r] = win > 0 ? sycl::max(0, pf + m - win + 1) : 0;
                xp[r] = P + ((size_t)(t0 + m) * nh + kvh * G + gi) * ldp - xlo[r];
            }
            float acc[CPL][NR], tot[CPL][NR];
#pragma unroll
            for (int k = 0; k < CPL; ++k)
#pragma unroll
                for (int a = 0; a < NR; ++a) { acc[k][a] = 0.0f; tot[k][a] = 0.0f; }
            auto flush = [&] {
#pragma unroll
                for (int k = 0; k < CPL; ++k)
#pragma unroll
                    for (int a = 0; a < NR; ++a) { tot[k][a] += acc[k][a]; acc[k][a] = 0.0f; }
            };
            int j = lof & ~15, buf = 0;
            for (; j + 15 <= pl; j += 16) {
                if ((j & (PVB - 1)) == 0) flush();
                const int jj = j + lane;
#pragma unroll
                for (int r = 0; r < RS; ++r) {
                    const bool ok = jj >= xlo[r] && jj <= xpp[r];
                    ex[(buf * NR + sgi * RS + r) * PW + lane] = ok ? sycl::exp(xp[r][jj] - xm[r]) * xi[r] : 0.0f;
                }
                sycl::group_barrier(it.get_group());
                float pv[NR];
#pragma unroll
                for (int a = 0; a < NR; ++a) pv[a] = ex[(buf * NR + a) * PW + lane];
                buf ^= 1;
                HV v0[CPL], v1[CPL];
#pragma unroll
                for (int k = 0; k < CPL; ++k) { v0[k] = *(const HV *)(rows[k] + (j & km)); v1[k] = *(const HV *)(rows[k] + (j & km) + 8); }
#pragma unroll
                for (int u = 0; u < PW; ++u) {
#pragma unroll
                    for (int k = 0; k < CPL; ++k) {
                        const float vf = (float)(u < 8 ? v0[k][u] : v1[k][u - 8]);
#pragma unroll
                        for (int a = 0; a < NR; ++a) acc[k][a] = mac(acc[k][a], sycl::select_from_group(sg, pv[a], u), vf);
                    }
                }
            }
            for (; j <= pl; ++j) { // the last keys one at a time, each lane computing its own (as attn_pv_tile EX)
                if ((j & (PVB - 1)) == 0) flush();
#pragma unroll
                for (int k = 0; k < CPL; ++k) {
                    const float vf = (float)rows[k][j & km];
#pragma unroll
                    for (int m = 0; m < MT; ++m) {
                        const bool ok = j >= lo[m] && j <= pp[m];
#pragma unroll
                        for (int gi = 0; gi < G; ++gi) {
                            const float *pr = P + ((size_t)(t0 + m) * nh + kvh * G + gi) * ldp;
                            const int a = m * G + gi;
                            acc[k][a] = mac(acc[k][a], (ok ? sycl::exp(pr[j - lo[m]] - mr[a]) * iv[a] : 0.0f), vf);
                        }
                    }
                }
            }
            flush();
#pragma unroll
            for (int m = 0; m < MT; ++m) {
                if (m >= tn) break;
#pragma unroll
                for (int gi = 0; gi < G; ++gi)
#pragma unroll
                    for (int k = 0; k < CPL; ++k) {
                        const size_t i = ((size_t)(t0 + m) * nh + kvh * G + gi) * HD + c0 + k * NL;
                        out[i] = tot[k][m * G + gi] * (1.0f / (1.0f + sycl::exp(-gate[i])));
                    }
            }
        });
    });
}

// attn_pv_tile split by key blocks (long contexts, where a few work-groups each walking every key leave the card
// idle): a work-group = one block of MT queries x one KV head x one block of PVB key positions; it writes each row's
// sum over that block (keys ascending from 0.0f, keys outside the row's range adding exact zeros) to part in
// attn_pv_bo_part's layout, part[((t*nh + h)*nblk + b)*hd + c] with b counted from the step's first row's lo / PVB;
// attn_pv_bo_sum then adds the blocks and applies the gate. Query blocks run fastest, so a value block is read from
// memory once for all of them. Same values as attn_pv_bo_part.
template <int MT, int G, int CPL = 1, bool EX = false>
inline sycl::event attn_pv_tile_part(sycl::queue &q, const float *P, int ldp, const sycl::half *Vt, int vld, int pos0, int ntok,
                                     int nh, int nkvh, int hd, int win, float *part, int nblk, int km = 0x7fffffff,
                                     const float *inv = nullptr, const float *pmx = nullptr) {
    constexpr int PW = 16, NR = MT * G;
    using HV = sycl::vec<sycl::half, 8>;
    if (nh != nkvh * G || hd % (PW * CPL) || vld % 16) throw std::runtime_error("attn_pv_tile_part: unsupported shape");
    const int nqb = (ntok + MT - 1) / MT, nl = hd / CPL;
    const int b0 = (win > 0 ? std::max(0, pos0 - win + 1) : 0) / PVB;
    return q.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nqb * nkvh * nblk, (size_t)nl), sycl::range<2>(1, (size_t)nl)),
                          [=](sycl::nd_item<2> it) [[sycl::reqd_sub_group_size(PW)]] {
        auto sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id();
        const int gid = (int)it.get_group(0), qb = gid % nqb, kvh = (gid / nqb) % nkvh, b = gid / (nqb * nkvh);
        const int c0 = (int)it.get_local_id(1);
        const int t0 = qb * MT, tn = sycl::min(MT, ntok - t0);
        const int pf = pos0 + t0, pl = pf + tn - 1;
        const int lof = win > 0 ? sycl::max(0, pf - win + 1) : 0;
        const int kb = (b0 + b) * PVB;
        const int js = sycl::max(kb, lof & ~15), je = sycl::min(kb + PVB - 1, pl);
        const sycl::half *rows[CPL];
#pragma unroll
        for (int k = 0; k < CPL; ++k) rows[k] = Vt + (size_t)(kvh * hd + c0 + k * nl) * vld;
        int lo[MT], pp[MT];
#pragma unroll
        for (int m = 0; m < MT; ++m) {
            pp[m] = m < tn ? pf + m : -1;
            lo[m] = win > 0 ? sycl::max(0, pf + m - win + 1) : 0;
        }
        float iv[NR], mr[NR];
#pragma unroll
        for (int a = 0; a < NR; ++a) {
            const size_t ia = (size_t)(t0 + sycl::min(a / G, tn - 1)) * nh + kvh * G + a % G;
            iv[a] = inv ? inv[ia] : 1.0f;
            mr[a] = EX ? pmx[ia] : 0.0f;
        }
        // the value of row a at P entry x (EX: the softmax's exponential first)
        auto pval = [&](float x, int a) {
            if constexpr (EX) x = sycl::exp(x - mr[a]);
            return inv ? x * iv[a] : x;
        };
        float acc[CPL][NR];
#pragma unroll
        for (int k = 0; k < CPL; ++k)
#pragma unroll
            for (int a = 0; a < NR; ++a) acc[k][a] = 0.0f;
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
                    pv[m * G + gi] = ok ? pval(pr[jj - lo[m]], m * G + gi) : 0.0f;
                }
            }
            HV v0[CPL], v1[CPL];
#pragma unroll
            for (int k = 0; k < CPL; ++k) { v0[k] = *(const HV *)(rows[k] + (j & km)); v1[k] = *(const HV *)(rows[k] + (j & km) + 8); }
#pragma unroll
            for (int u = 0; u < PW; ++u) {
#pragma unroll
                for (int k = 0; k < CPL; ++k) {
                    const float vf = (float)(u < 8 ? v0[k][u] : v1[k][u - 8]);
#pragma unroll
                    for (int a = 0; a < NR; ++a) acc[k][a] = mac(acc[k][a], sycl::select_from_group(sg, pv[a], u), vf);
                }
            }
        }
        for (; j <= je; ++j) {
#pragma unroll
            for (int k = 0; k < CPL; ++k) {
                const float vf = (float)rows[k][j & km];
#pragma unroll
                for (int m = 0; m < MT; ++m) {
                    const bool ok = j >= lo[m] && j <= pp[m];
#pragma unroll
                    for (int gi = 0; gi < G; ++gi) {
                        const float *pr = P + ((size_t)(t0 + m) * nh + kvh * G + gi) * ldp;
                        acc[k][m * G + gi] = mac(acc[k][m * G + gi], (ok ? pval(pr[j - lo[m]], m * G + gi) : 0.0f), vf);
                    }
                }
            }
        }
#pragma unroll
        for (int m = 0; m < MT; ++m) {
            if (m >= tn) break;
#pragma unroll
            for (int gi = 0; gi < G; ++gi)
#pragma unroll
                for (int k = 0; k < CPL; ++k)
                    part[(((size_t)(t0 + m) * nh + kvh * G + gi) * nblk + b) * hd + c0 + k * nl] = acc[k][m * G + gi];
        }
    });
}

} // namespace ink::fz
