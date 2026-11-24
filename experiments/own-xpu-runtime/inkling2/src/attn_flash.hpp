// attn_flash.hpp: attention of layers without a window in blocks of PVB keys with a running maximum, so the scores
// never go to memory (study 2026-11-24; a different rounding from attn_tiles.hpp / fused.hpp, so a new baseline).
//
// The definition, for a row (token t at position p, head h) and every path that computes it:
//  s_j = (q . k_j) * scale (+ the relative bias when p - j < ext), as attn_scores_g / attn_scores_tile.
//  For each block b of PVB positions [b PVB, b PVB + PVB) with keys j <= p:
//    m_b = max of its s_j;  e_j = exp(s_j - m_b);
//    l_b: lane l (0..15) adds e_j for j = b PVB + l + 16 g, g ascending, from 0.0f (keys past p add nothing), then
//         x = x + xor-shuffle(x, 8), then 4, 2, 1 (every lane holds the same bits);
//    a_b[c] = mac over the block's keys ascending from 0.0f of e_j and v_j[c].
//  State (M, L, A[c]) starts at (sink, 1, 0); blocks ascending: Mn = fmax(M, m_b), al = exp(M - Mn),
//    be = exp(m_b - Mn), L = mac(L * al, l_b, be), A[c] = mac(A[c] * al, a_b[c], be), M = Mn.
//  out[c] = (A[c] * (1 / L)) * (1 / (1 + exp(-gate[c]))).
#pragma once
#include "fused.hpp"

namespace ink::fz {

// a work-group = MT queries x the G heads of one KV head (NR rows) x all 128 channels (CPL per lane, NSG sub-groups);
// per block: the sub-groups compute the scores of KG / NSG groups of 16 keys each (lane = key) into local memory, the
// row maxima per sub-group beside them; then sub-group s turns rows [s RS, s RS + RS) into exponentials, l_b and the
// state's factors; then every sub-group does P.V for its channels (lane = channel, exponentials selected from local
// memory as attn_pv_tile_xs does). Three barriers per block.
// VAR (same arithmetic, same order; code shape only): 1 = Q by sub-group block loads (one scalar address per query, the
// rest constant offsets), 16 = Q per lane with constant offsets from one base per query, 2 = P.V of
// full blocks unrolled, 4 = the next key group's exponentials loaded one group ahead, 8 = local-memory reads of the
// exponentials as sub-group block loads
template <int MT, int G, int CPL, int VAR = 0>
inline sycl::event attn_flash_tile(sycl::queue &q, const float *Q, const sycl::half *K, const float *Rc, const float *rel_bias,
                                   int nr, const float *sink, const sycl::half *Vt, int vld, int pos0, int ntok, int nh, int nkvh,
                                   int hd, int ext, float scale, const float *gate, float *out, int km = 0x7fffffff) {
    constexpr int PW = 16, NR = MT * G, HD = 128, NL = HD / CPL, NSG = NL / PW, RS = NR / NSG, NRL = 16, KG = PVB / PW;
    static_assert(HD % (PW * CPL) == 0 && NR % NSG == 0 && KG % NSG == 0, "attn_flash_tile: shape");
    constexpr int GPS = KG / NSG;
    using HV = sycl::vec<sycl::half, 8>;
    if (hd != HD || nh != nkvh * G || nr != NRL || vld % 16) throw std::runtime_error("attn_flash_tile: unsupported shape");
    const int nqb = (ntok + MT - 1) / MT;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> sx(NR * PVB, h), smx(NR * NSG, h), sab(3 * NR, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nqb * nkvh, (size_t)NL), sycl::range<2>(1, (size_t)NL)),
                       [=](sycl::nd_item<2> it) [[sycl::reqd_sub_group_size(PW)]] {
            auto sg = it.get_sub_group();
            const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
            const int qb = (int)it.get_group(0) / nkvh, kvh = (int)it.get_group(0) % nkvh, c0 = (int)it.get_local_id(1);
            const int t0 = qb * MT, tn = sycl::min(MT, ntok - t0);
            const int pf = pos0 + t0, pl = pf + tn - 1;
            const sycl::half *vrow[CPL];
#pragma unroll
            for (int k = 0; k < CPL; ++k) vrow[k] = Vt + (size_t)(kvh * HD + c0 + k * NL) * vld;
            float A[CPL][NR];
#pragma unroll
            for (int k = 0; k < CPL; ++k)
#pragma unroll
                for (int a = 0; a < NR; ++a) A[k][a] = 0.0f;
            float M[RS], L[RS];
#pragma unroll
            for (int r = 0; r < RS; ++r) {
                const int a = sgi * RS + r;
                M[r] = sink[(size_t)(t0 + sycl::min(a / G, tn - 1)) * nh + kvh * G + a % G];
                L[r] = 1.0f;
            }
            const int nb = pl / PVB + 1;
            for (int b = 0; b < nb; ++b) {
                const int jb = b * PVB;
                // scores of this sub-group's key groups, all rows
                float rmx[NR];
#pragma unroll
                for (int a = 0; a < NR; ++a) rmx[a] = -INFINITY;
#pragma unroll
                for (int gg = 0; gg < GPS; ++gg) {
                    const int g = sgi * GPS + gg, j = jb + g * PW + lane;
                    if (jb + g * PW > pl) {
#pragma unroll
                        for (int a = 0; a < NR; ++a) sx[a * PVB + g * PW + lane] = -INFINITY;
                        continue;
                    }
                    const int jc = sycl::min(j, pl);
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
                            const float *qm = Q + ((size_t)t * nh + kvh * G) * HD + d0; // one row base per query
#pragma unroll
                            for (int gi = 0; gi < G; ++gi) {
                                if constexpr (VAR & 1)
                                    ql[m * G + gi] = sg.load(sycl::address_space_cast<sycl::access::address_space::global_space,
                                                                                      sycl::access::decorated::yes>(
                                        const_cast<float *>(qm + gi * HD)));
                                else if constexpr (VAR & 16) ql[m * G + gi] = qm[gi * HD + lane];
                                else ql[m * G + gi] = Q[((size_t)t * nh + kvh * G + gi) * hd + d0 + lane];
                            }
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
                        const int t = t0 + m, p = pos0 + t;
                        const bool in = m < tn && j <= p;
                        const int dist = p - j;
                        const bool rel = in && dist < ext;
                        sycl::vec<float, 4> bb[NRL / 4];
                        if (rel) {
                            const float *br = rel_bias + (size_t)dist * NRL;
#pragma unroll
                            for (int i = 0; i < NRL / 4; ++i) bb[i] = *(const sycl::vec<float, 4> *)(br + 4 * i);
                        }
#pragma unroll
                        for (int gi = 0; gi < G; ++gi) {
                            const int a = m * G + gi;
                            float s = acc[a] * scale;
                            if (rel) {
                                const float *rc = Rc + ((size_t)t * nh + kvh * G + gi) * NRL;
                                float tb = 0.0f;
#pragma unroll
                                for (int i = 0; i < NRL / 4; ++i) {
                                    const sycl::vec<float, 4> r = *(const sycl::vec<float, 4> *)(rc + 4 * i);
#pragma unroll
                                    for (int k = 0; k < 4; ++k) tb = mac(tb, bb[i][k], r[k]);
                                }
                                s = s + tb;
                            }
                            s = in ? s : -INFINITY;
                            sx[a * PVB + g * PW + lane] = s;
                            rmx[a] = sycl::fmax(rmx[a], s);
                        }
                    }
                }
#pragma unroll
                for (int a = 0; a < NR; ++a) {
                    const float mg = sycl::reduce_over_group(sg, rmx[a], sycl::maximum<float>());
                    if (lane == 0) smx[a * NSG + sgi] = mg;
                }
                sycl::group_barrier(it.get_group());
                // this sub-group's rows: exponentials, l_b, the state
#pragma unroll
                for (int r = 0; r < RS; ++r) {
                    const int a = sgi * RS + r;
                    float mb = -INFINITY;
#pragma unroll
                    for (int i = 0; i < NSG; ++i) mb = sycl::fmax(mb, smx[a * NSG + i]);
                    float ls = 0.0f;
#pragma unroll
                    for (int g = 0; g < KG; ++g) {
                        const float s = sx[a * PVB + g * PW + lane];
                        const float e = s == -INFINITY ? 0.0f : sycl::exp(s - mb);
                        sx[a * PVB + g * PW + lane] = e;
                        ls = ls + e;
                    }
                    ls = ls + sycl::permute_group_by_xor(sg, ls, 8);
                    ls = ls + sycl::permute_group_by_xor(sg, ls, 4);
                    ls = ls + sycl::permute_group_by_xor(sg, ls, 2);
                    ls = ls + sycl::permute_group_by_xor(sg, ls, 1);
                    float al = 1.0f, be = 0.0f;
                    if (mb != -INFINITY) {
                        const float mn = sycl::fmax(M[r], mb);
                        al = sycl::exp(M[r] - mn);
                        be = sycl::exp(mb - mn);
                        L[r] = mac(L[r] * al, ls, be);
                        M[r] = mn;
                    }
                    if (lane == 0) { sab[a] = al; sab[NR + a] = be; }
                }
                sycl::group_barrier(it.get_group());
                // P.V of the block for this lane's channels
                float ab[CPL][NR];
#pragma unroll
                for (int k = 0; k < CPL; ++k)
#pragma unroll
                    for (int a = 0; a < NR; ++a) ab[k][a] = 0.0f;
                const int kend = sycl::min(PVB, pl - jb + 1), gfull = kend / PW;
                auto ldx = [&](int a, int g) -> float {
                    if constexpr (VAR & 8)
                        return sg.load(sycl::address_space_cast<sycl::access::address_space::local_space, sycl::access::decorated::yes>(
                            &sx[a * PVB + g * PW]));
                    else return sx[a * PVB + g * PW + lane];
                };
                auto pv_group = [&](int g, const float *pv) {
                    HV v0[CPL], v1[CPL];
#pragma unroll
                    for (int k = 0; k < CPL; ++k) {
                        v0[k] = *(const HV *)(vrow[k] + ((jb + g * PW) & km));
                        v1[k] = *(const HV *)(vrow[k] + ((jb + g * PW) & km) + 8);
                    }
#pragma unroll
                    for (int u = 0; u < PW; ++u) {
#pragma unroll
                        for (int k = 0; k < CPL; ++k) {
                            const float vf = (float)(u < 8 ? v0[k][u] : v1[k][u - 8]);
#pragma unroll
                            for (int a = 0; a < NR; ++a) ab[k][a] = mac(ab[k][a], sycl::select_from_group(sg, pv[a], u), vf);
                        }
                    }
                };
                if constexpr (VAR & 4) {
                    float pv[NR];
                    if (gfull > 0)
#pragma unroll
                        for (int a = 0; a < NR; ++a) pv[a] = ldx(a, 0);
                    for (int g = 0; g < gfull; ++g) {
                        float pn[NR];
                        const int gn = sycl::min(g + 1, gfull - 1);
#pragma unroll
                        for (int a = 0; a < NR; ++a) pn[a] = ldx(a, gn);
                        pv_group(g, pv);
#pragma unroll
                        for (int a = 0; a < NR; ++a) pv[a] = pn[a];
                    }
                } else if ((VAR & 2) && gfull == KG) {
#pragma unroll
                    for (int g = 0; g < KG; ++g) {
                        float pv[NR];
#pragma unroll
                        for (int a = 0; a < NR; ++a) pv[a] = ldx(a, g);
                        pv_group(g, pv);
                    }
                } else {
                    for (int g = 0; g < gfull; ++g) {
                        float pv[NR];
#pragma unroll
                        for (int a = 0; a < NR; ++a) pv[a] = ldx(a, g);
                        pv_group(g, pv);
                    }
                }
                if (gfull * PW < kend) { // the last keys present one at a time (no value past the step's last position read)
                    float pv[NR];
#pragma unroll
                    for (int a = 0; a < NR; ++a) pv[a] = sx[a * PVB + gfull * PW + lane];
                    for (int u = 0; u < kend - gfull * PW; ++u) {
#pragma unroll
                        for (int k = 0; k < CPL; ++k) {
                            const float vf = (float)vrow[k][(jb + gfull * PW + u) & km];
#pragma unroll
                            for (int a = 0; a < NR; ++a) ab[k][a] = mac(ab[k][a], sycl::select_from_group(sg, pv[a], u), vf);
                        }
                    }
                }
#pragma unroll
                for (int a = 0; a < NR; ++a) {
                    const float al = sab[a], be = sab[NR + a];
#pragma unroll
                    for (int k = 0; k < CPL; ++k) A[k][a] = mac(A[k][a] * al, ab[k][a], be);
                }
                sycl::group_barrier(it.get_group());
            }
#pragma unroll
            for (int r = 0; r < RS; ++r)
                if (lane == 0) sab[2 * NR + sgi * RS + r] = L[r];
            sycl::group_barrier(it.get_group());
#pragma unroll
            for (int m = 0; m < MT; ++m) {
                if (m >= tn) break;
#pragma unroll
                for (int gi = 0; gi < G; ++gi) {
                    const float iv = 1.0f / sab[2 * NR + m * G + gi];
#pragma unroll
                    for (int k = 0; k < CPL; ++k) {
                        const size_t i = ((size_t)(t0 + m) * nh + kvh * G + gi) * HD + c0 + k * NL;
                        out[i] = (A[k][m * G + gi] * iv) * (1.0f / (1.0f + sycl::exp(-gate[i])));
                    }
                }
            }
        });
    });
}

// the writing steps (and prompt chunks of few rows at long contexts): the scores in P (attn_scores_g / _gt /
// attn_scores_tile, raw), then per block: attn_flash_part writes a_b to part[((t nh + h) nblk + b) hd + c] and
// (m_b, l_b) to pml[((t nh + h) nblk + b) 2 + {0, 1}]; attn_flash_sum folds the blocks into the state and writes out.
// A work-group = NT tokens x the G heads of one KV head x one block, lane = channel; every sub-group computes the
// block maximum and the exponentials itself (P from the cache, as attn_pv_bo_part_t reads it).
template <int G, int NT>
inline sycl::event attn_flash_part(sycl::queue &q, const float *P, int ldp, const sycl::half *Vt, int vld, int pos0, int ntok, int nh,
                                   int nkvh, int hd, float *part, float *pml, int nblk, int km = 0x7fffffff) {
    constexpr int PW = 16, KG = PVB / PW;
    using HV = sycl::vec<sycl::half, 16>;
    if (nh != nkvh * G || vld % 16) throw std::runtime_error("attn_flash_part: unsupported shape");
    const int nrg = (ntok + NT - 1) / NT;
    return q.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nrg * nkvh * nblk, (size_t)hd), sycl::range<2>(1, (size_t)hd)),
                          [=](sycl::nd_item<2> it) [[sycl::reqd_sub_group_size(PW)]] {
        auto sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id(), c = (int)it.get_local_id(1);
        const int gid = (int)it.get_group(0), b = gid % nblk, kvh = (gid / nblk) % nkvh, rg = gid / nblk / nkvh;
        const int kb = b * PVB, pmax = pos0 + ntok - 1;
        const sycl::half *vrow = Vt + (size_t)(kvh * hd + c) * vld;
        int pp[NT];
        const float *pr[NT][G];
        float mb[NT][G], ls[NT][G], acc[NT][G];
#pragma unroll
        for (int t = 0; t < NT; ++t) {
            const int tt = rg * NT + t;
            pp[t] = tt < ntok ? pos0 + tt : -1; // rows past the step, or without keys in this block, take no keys
#pragma unroll
            for (int gi = 0; gi < G; ++gi) {
                pr[t][gi] = P + ((size_t)sycl::min(tt, ntok - 1) * nh + kvh * G + gi) * ldp;
                float mx = -INFINITY;
#pragma unroll
                for (int g = 0; g < KG; ++g) {
                    const int j = kb + g * PW + lane;
                    if (j <= pp[t]) mx = sycl::fmax(mx, pr[t][gi][j]);
                }
                mb[t][gi] = sycl::reduce_over_group(sg, mx, sycl::maximum<float>());
                ls[t][gi] = 0.0f;
                acc[t][gi] = 0.0f;
            }
        }
        for (int g = 0; g < KG; ++g) {
            const int g0 = kb + g * PW, j = g0 + lane;
            if (g0 > pmax) break;
            float ev[NT][G];
#pragma unroll
            for (int t = 0; t < NT; ++t)
#pragma unroll
                for (int gi = 0; gi < G; ++gi) {
                    const float e = j <= pp[t] ? sycl::exp(pr[t][gi][j] - mb[t][gi]) : 0.0f;
                    ev[t][gi] = e;
                    ls[t][gi] = ls[t][gi] + e;
                }
            if (g0 + PW - 1 <= pmax) {
                const HV v = *(const HV *)(vrow + (g0 & km));
#pragma unroll
                for (int u = 0; u < PW; ++u) {
                    const float vf = (float)v[u];
#pragma unroll
                    for (int t = 0; t < NT; ++t)
#pragma unroll
                        for (int gi = 0; gi < G; ++gi) acc[t][gi] = mac(acc[t][gi], sycl::select_from_group(sg, ev[t][gi], u), vf);
                }
            } else {
                for (int u = 0; u <= pmax - g0; ++u) {
                    const float vf = (float)vrow[(g0 + u) & km];
#pragma unroll
                    for (int t = 0; t < NT; ++t)
#pragma unroll
                        for (int gi = 0; gi < G; ++gi) acc[t][gi] = mac(acc[t][gi], sycl::select_from_group(sg, ev[t][gi], u), vf);
                }
            }
        }
#pragma unroll
        for (int t = 0; t < NT; ++t) {
            if (pp[t] < kb) continue;
#pragma unroll
            for (int gi = 0; gi < G; ++gi) {
                float x = ls[t][gi];
                x = x + sycl::permute_group_by_xor(sg, x, 8);
                x = x + sycl::permute_group_by_xor(sg, x, 4);
                x = x + sycl::permute_group_by_xor(sg, x, 2);
                x = x + sycl::permute_group_by_xor(sg, x, 1);
                const size_t r = ((size_t)(rg * NT + t) * nh + kvh * G + gi) * nblk + b;
                part[r * hd + c] = acc[t][gi];
                if (c == 0) { pml[2 * r] = mb[t][gi]; pml[2 * r + 1] = x; }
            }
        }
    });
}

// attn_flash_part with the block's scores computed in the work-group (local memory) instead of read from P: the
// writing steps and steps without prompt tiles, whose scores attn_scores_gt / attn_scores_g give as (d ascending from
// 0.0f) * scale, plus tab[row][dist] within ext (the relative-bias table attn_prep fills when there are no tiles). P is
// then neither written nor read (keys and values each read once per block; the same values). Sub-group s computes the
// scores of keys kb + 16 s + lane for the NT x G rows, then every sub-group runs attn_flash_part's code on them.
template <int G, int NT>
inline sycl::event attn_flash_dec(sycl::queue &q, const float *Q, const sycl::half *K, const float *tab, const sycl::half *Vt, int vld,
                                  int pos0, int ntok, int nh, int nkvh, int hd, int ext, float scale, float *part, float *pml, int nblk,
                                  int km = 0x7fffffff) {
    constexpr int PW = 16, KG = PVB / PW, NR = NT * G, HD = 128;
    using HV8 = sycl::vec<sycl::half, 8>;
    using HV = sycl::vec<sycl::half, 16>;
    if (hd != HD || nh != nkvh * G || vld % 16 || HD / PW != KG) throw std::runtime_error("attn_flash_dec: unsupported shape");
    const int nrg = (ntok + NT - 1) / NT;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> sx(NR * PVB, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nrg * nkvh * nblk, (size_t)HD), sycl::range<2>(1, (size_t)HD)),
                       [=](sycl::nd_item<2> it) [[sycl::reqd_sub_group_size(PW)]] {
            auto sg = it.get_sub_group();
            const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id(), c = (int)it.get_local_id(1);
            const int gid = (int)it.get_group(0), b = gid % nblk, kvh = (gid / nblk) % nkvh, rg = gid / nblk / nkvh;
            const int kb = b * PVB, pmax = pos0 + ntok - 1;
            int pp[NT];
#pragma unroll
            for (int t = 0; t < NT; ++t) {
                const int tt = rg * NT + t;
                pp[t] = tt < ntok ? pos0 + tt : -1;
            }
            { // the scores of this sub-group's 16 keys (attn_scores_gt's expressions)
                const int g0 = kb + sgi * PW, j = g0 + lane;
                if (g0 <= pmax) {
                    const int jc = sycl::min(j, pmax);
                    const sycl::half *kr = K + (size_t)(jc & km) * nkvh * HD + kvh * HD;
                    float s[NT][G];
#pragma unroll
                    for (int t = 0; t < NT; ++t)
#pragma unroll
                        for (int gi = 0; gi < G; ++gi) s[t][gi] = 0.0f;
#pragma unroll
                    for (int d0 = 0; d0 < HD; d0 += PW) {
                        const HV8 k0 = *(const HV8 *)(kr + d0), k1 = *(const HV8 *)(kr + d0 + 8);
                        float qv[NT][G];
#pragma unroll
                        for (int t = 0; t < NT; ++t) {
                            const int tt = sycl::min(rg * NT + t, ntok - 1);
#pragma unroll
                            for (int gi = 0; gi < G; ++gi) qv[t][gi] = Q[((size_t)tt * nh + kvh * G + gi) * HD + d0 + lane];
                        }
#pragma unroll
                        for (int u = 0; u < PW; ++u) {
                            const float kf = (float)(u < 8 ? k0[u] : k1[u - 8]);
#pragma unroll
                            for (int t = 0; t < NT; ++t)
#pragma unroll
                                for (int gi = 0; gi < G; ++gi) s[t][gi] = mac(s[t][gi], sycl::select_from_group(sg, qv[t][gi], u), kf);
                        }
                    }
#pragma unroll
                    for (int t = 0; t < NT; ++t) {
                        const int dist = pp[t] - j;
#pragma unroll
                        for (int gi = 0; gi < G; ++gi) {
                            const size_t row = (size_t)(rg * NT + t) * nh + kvh * G + gi;
                            float v = s[t][gi] * scale;
                            if (j <= pp[t] && dist < ext) v = v + tab[row * ext + dist];
                            sx[(t * G + gi) * PVB + sgi * PW + lane] = v; // read only where j <= pp[t]
                        }
                    }
                }
            }
            sycl::group_barrier(it.get_group());
            const sycl::half *vrow = Vt + (size_t)(kvh * HD + c) * vld;
            float mb[NT][G], ls[NT][G], acc[NT][G];
#pragma unroll
            for (int t = 0; t < NT; ++t)
#pragma unroll
                for (int gi = 0; gi < G; ++gi) {
                    float mx = -INFINITY;
#pragma unroll
                    for (int g = 0; g < KG; ++g) {
                        const int j = kb + g * PW + lane;
                        if (j <= pp[t]) mx = sycl::fmax(mx, sx[(t * G + gi) * PVB + g * PW + lane]);
                    }
                    mb[t][gi] = sycl::reduce_over_group(sg, mx, sycl::maximum<float>());
                    ls[t][gi] = 0.0f;
                    acc[t][gi] = 0.0f;
                }
            for (int g = 0; g < KG; ++g) {
                const int g0 = kb + g * PW, j = g0 + lane;
                if (g0 > pmax) break;
                float ev[NT][G];
#pragma unroll
                for (int t = 0; t < NT; ++t)
#pragma unroll
                    for (int gi = 0; gi < G; ++gi) {
                        const float e = j <= pp[t] ? sycl::exp(sx[(t * G + gi) * PVB + g * PW + lane] - mb[t][gi]) : 0.0f;
                        ev[t][gi] = e;
                        ls[t][gi] = ls[t][gi] + e;
                    }
                if (g0 + PW - 1 <= pmax) {
                    const HV v = *(const HV *)(vrow + (g0 & km));
#pragma unroll
                    for (int u = 0; u < PW; ++u) {
                        const float vf = (float)v[u];
#pragma unroll
                        for (int t = 0; t < NT; ++t)
#pragma unroll
                            for (int gi = 0; gi < G; ++gi) acc[t][gi] = mac(acc[t][gi], sycl::select_from_group(sg, ev[t][gi], u), vf);
                    }
                } else {
                    for (int u = 0; u <= pmax - g0; ++u) {
                        const float vf = (float)vrow[(g0 + u) & km];
#pragma unroll
                        for (int t = 0; t < NT; ++t)
#pragma unroll
                            for (int gi = 0; gi < G; ++gi) acc[t][gi] = mac(acc[t][gi], sycl::select_from_group(sg, ev[t][gi], u), vf);
                    }
                }
            }
#pragma unroll
            for (int t = 0; t < NT; ++t) {
                if (pp[t] < kb) continue;
#pragma unroll
                for (int gi = 0; gi < G; ++gi) {
                    float x = ls[t][gi];
                    x = x + sycl::permute_group_by_xor(sg, x, 8);
                    x = x + sycl::permute_group_by_xor(sg, x, 4);
                    x = x + sycl::permute_group_by_xor(sg, x, 2);
                    x = x + sycl::permute_group_by_xor(sg, x, 1);
                    const size_t r = ((size_t)(rg * NT + t) * nh + kvh * G + gi) * nblk + b;
                    part[r * HD + c] = acc[t][gi];
                    if (c == 0) { pml[2 * r] = mb[t][gi]; pml[2 * r + 1] = x; }
                }
            }
        });
    });
}

// attn_flash_part's blocks folded into the state, a work-group per row (lane = channel, hd = 128 lanes): in chunks of
// 128 blocks, a work-group scan gives each block the state's maximum before and after it (a maximum is exact in any
// order, so these are the values the blocks one after another give), lane b computes block b's two factors, then every
// lane folds the chunk's blocks in order (L the same in every lane)
inline sycl::event attn_flash_sum(sycl::queue &q, const float *part, const float *pml, int nblk, int pos0, int ntok, int nh, int hd,
                                  const float *sink, const float *gate, float *out) {
    constexpr int NB = 128;
    if (hd != NB) throw std::runtime_error("attn_flash_sum: head_dim 128 only");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> sl(NB, h), sal(NB, h), sbe(NB, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * nh * NB), sycl::range<1>((size_t)NB)),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
            const int row = (int)it.get_group(0), c = (int)it.get_local_id(0), t = row / nh, p = pos0 + t, nb = p / PVB + 1;
            const float *pr = part + (size_t)row * nblk * NB + c, *pm = pml + (size_t)row * nblk * 2;
            float M = sink[row], L = 1.0f, A = 0.0f;
            for (int c0 = 0; c0 < nb; c0 += NB) {
                const int cnt = sycl::min(NB, nb - c0);
                const bool ok = c < cnt;
                const float mb = ok ? pm[2 * (c0 + c)] : -INFINITY;
                if (ok) sl[c] = pm[2 * (c0 + c) + 1];
                const float mn = sycl::fmax(M, sycl::inclusive_scan_over_group(it.get_group(), mb, sycl::maximum<float>()));
                const float mp = sycl::fmax(M, sycl::exclusive_scan_over_group(it.get_group(), mb, sycl::maximum<float>()));
                if (ok) { sal[c] = sycl::exp(mp - mn); sbe[c] = sycl::exp(mb - mn); }
                const float mlast = sycl::group_broadcast(it.get_group(), mn, cnt - 1);
                sycl::group_barrier(it.get_group());
                int i = 0;
                for (; i + 7 < cnt; i += 8) {
                    float v[8];
#pragma unroll
                    for (int u = 0; u < 8; ++u) v[u] = pr[(size_t)(c0 + i + u) * NB];
#pragma unroll
                    for (int u = 0; u < 8; ++u) {
                        const float al = sal[i + u], be = sbe[i + u];
                        L = mac(L * al, sl[i + u], be);
                        A = mac(A * al, v[u], be);
                    }
                }
                for (; i < cnt; ++i) {
                    const float al = sal[i], be = sbe[i];
                    L = mac(L * al, sl[i], be);
                    A = mac(A * al, pr[(size_t)(c0 + i) * NB], be);
                }
                M = mlast;
                sycl::group_barrier(it.get_group());
            }
            const size_t o = (size_t)row * NB + c;
            out[o] = (A * (1.0f / L)) * (1.0f / (1.0f + sycl::exp(-gate[o])));
        });
    });
}

// the definition computed plainly (one sub-group per row, every key and channel in order): the reference attn_flash_tile
// must equal bit for bit. The scores as attn_scores_g's (d ascending from 0.0f with mac, then the scale, then the bias).
inline sycl::event attn_flash_ref(sycl::queue &q, const float *Q, const sycl::half *K, const float *Rc, const float *rel_bias, int nr,
                                  const float *sink, const sycl::half *Vt, int vld, int pos0, int ntok, int nh, int nkvh, int hd,
                                  int ext, float scale, const float *gate, float *out) {
    constexpr int PW = 16, KG = PVB / PW;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> ex(PVB, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * nh * PW), sycl::range<1>(PW)),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(PW)]] {
            auto sg = it.get_sub_group();
            const int lane = (int)sg.get_local_linear_id(), row = (int)it.get_group(0), t = row / nh, hh = row % nh;
            const int kvh = hh / (nh / nkvh), p = pos0 + t;
            const float *qr = Q + (size_t)row * hd, *rc = Rc + (size_t)row * nr;
            float M = sink[row], L = 1.0f, A[8];
            for (int i = 0; i < 8; ++i) A[i] = 0.0f;
            for (int b = 0; b <= p / PVB; ++b) {
                float sv[KG], mb = -INFINITY;
                for (int g = 0; g < KG; ++g) {
                    const int j = b * PVB + g * PW + lane;
                    float s = -INFINITY;
                    if (j <= p) {
                        const sycl::half *kr = K + (size_t)j * nkvh * hd + kvh * hd;
                        float acc = 0.0f;
                        for (int d = 0; d < hd; ++d) acc = mac(acc, qr[d], (float)kr[d]);
                        s = acc * scale;
                        if (p - j < ext) {
                            float tb = 0.0f;
                            for (int i = 0; i < nr; ++i) tb = mac(tb, rel_bias[(size_t)(p - j) * nr + i], rc[i]);
                            s = s + tb;
                        }
                    }
                    sv[g] = s;
                    mb = sycl::fmax(mb, s);
                }
                mb = sycl::reduce_over_group(sg, mb, sycl::maximum<float>());
                float ls = 0.0f;
                for (int g = 0; g < KG; ++g) {
                    const float e = sv[g] == -INFINITY ? 0.0f : sycl::exp(sv[g] - mb);
                    sv[g] = e;
                    ls = ls + e;
                }
                ls = ls + sycl::permute_group_by_xor(sg, ls, 8);
                ls = ls + sycl::permute_group_by_xor(sg, ls, 4);
                ls = ls + sycl::permute_group_by_xor(sg, ls, 2);
                ls = ls + sycl::permute_group_by_xor(sg, ls, 1);
                const float mn = sycl::fmax(M, mb), al = sycl::exp(M - mn), be = sycl::exp(mb - mn);
                L = mac(L * al, ls, be);
                M = mn;
                for (int i = 0; i < 8; ++i) { // channels c = lane + 16 i
                    const int c = lane + 16 * i;
                    float a = 0.0f;
                    for (int j = b * PVB; j <= sycl::min(p, b * PVB + PVB - 1); ++j) {
                        const int jj = j - b * PVB;
                        const float e = sycl::select_from_group(sg, sv[jj / PW], jj % PW);
                        a = mac(a, e, (float)Vt[(size_t)(kvh * hd + c) * vld + j]);
                    }
                    A[i] = mac(A[i] * al, a, be);
                }
            }
            const float iv = 1.0f / L;
            for (int i = 0; i < 8; ++i) {
                const size_t o = (size_t)row * hd + lane + 16 * i;
                out[o] = (A[i] * iv) * (1.0f / (1.0f + sycl::exp(-gate[o])));
            }
        });
    });
}

} // namespace ink::fz
