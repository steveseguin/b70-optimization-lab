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

// a kernel body F launched with the large register file when BIG (256 registers per thread, half the threads per core)
template <class F, bool BIG> struct FlashK {
    F f;
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const { f(it); }
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        if constexpr (BIG) return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<256>};
        else return sycl::ext::oneapi::experimental::properties{};
    }
};

// a work-group = MT queries x the G heads of one KV head (NR rows) x all 128 channels (CPL per lane, NSG sub-groups);
// per block: the sub-groups compute the scores of KG / NSG groups of 16 keys each (lane = key) into local memory, the
// row maxima per sub-group beside them; then sub-group s turns rows [s RS, s RS + RS) into exponentials, l_b and the
// state's factors; then every sub-group does P.V for its channels (lane = channel, exponentials selected from local
// memory as attn_pv_tile_xs does). Three barriers per block.
// VAR (same arithmetic, same order; code shape only): 1 = Q by sub-group block loads (one scalar address per query, the
// rest constant offsets), 16 = Q per lane with constant offsets from one base per query, 2 = P.V of
// full blocks unrolled, 4 = the next key group's exponentials loaded one group ahead, 8 = local-memory reads of the
// exponentials as sub-group block loads, 32 = the large register file (256 per thread); timing only (wrong values,
// bench_attn BENCH_BUDGET): 64 = the query rows loaded once, 128 = no P.V multiply-adds, 256 = no score products,
// 512 = no exponentials; 1024 = each sub-group takes the block maximum of its own rows from the scores in local memory
// (3 sub-group reductions instead of 24; a maximum is the same in any order); 2048 = the query rows in local memory
// (loaded once per work-group); 4096 = the block's rescale factors as 3 lane loads (broadcast from lanes, not 48 loads);
// 8192 = blocks whose keys are all in the past and past the relative-bias distances skip the masks (the same values)
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
        sycl::local_accessor<float, 1> sx(NR * PVB, h), smx(NR * NSG, h), sab(3 * NR, h), sq((VAR & 2048) ? NR * HD : 1, h);
        auto body = [=](sycl::nd_item<2> it) {
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
            float qh[NR];
            if constexpr ((VAR & 64) != 0)
#pragma unroll
                for (int a = 0; a < NR; ++a) qh[a] = Q[((size_t)(t0 + sycl::min(a / G, tn - 1)) * nh + kvh * G + a % G) * hd + lane];
            if constexpr ((VAR & 2048) != 0) {
                for (int i = (int)it.get_local_id(1); i < NR * HD; i += NL) {
                    const int a = i / HD;
                    sq[i] = Q[((size_t)(t0 + sycl::min(a / G, tn - 1)) * nh + kvh * G + a % G) * hd + i % HD];
                }
                sycl::group_barrier(it.get_group());
            }
            for (int b = 0; b < nb; ++b) {
                const int jb = b * PVB;
                const bool far = (VAR & 8192) != 0 && jb + PVB - 1 + ext <= pf;
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
                        if constexpr ((VAR & 256) != 0) break;
                        const HV k0 = *(const HV *)(kr + d0), k1 = *(const HV *)(kr + d0 + 8);
                        float ql[NR];
                        if constexpr ((VAR & 64) != 0)
#pragma unroll
                            for (int a = 0; a < NR; ++a) ql[a] = qh[a];
                        else if constexpr ((VAR & 2048) != 0)
#pragma unroll
                            for (int a = 0; a < NR; ++a)
                                ql[a] = sg.load(sq.template get_multi_ptr<sycl::access::decorated::yes>() + a * HD + d0);
                        else
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
                    if (far) { // every key before every row and past the bias distances: in = m < tn, rel = false
#pragma unroll
                        for (int a = 0; a < NR; ++a) {
                            const float s = a / G < tn ? acc[a] * scale : -INFINITY;
                            sx[a * PVB + g * PW + lane] = s;
                            if constexpr ((VAR & 1024) == 0) rmx[a] = sycl::fmax(rmx[a], s);
                        }
                        continue;
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
                            if constexpr ((VAR & 1024) == 0) rmx[a] = sycl::fmax(rmx[a], s);
                        }
                    }
                }
                if constexpr ((VAR & 1024) == 0)
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
                    float mb = -INFINITY, sv[KG];
                    if constexpr ((VAR & 1024) != 0) {
#pragma unroll
                        for (int g = 0; g < KG; ++g) {
                            sv[g] = sx[a * PVB + g * PW + lane];
                            mb = sycl::fmax(mb, sv[g]);
                        }
                        mb = sycl::reduce_over_group(sg, mb, sycl::maximum<float>());
                    } else
#pragma unroll
                        for (int i = 0; i < NSG; ++i) mb = sycl::fmax(mb, smx[a * NSG + i]);
                    float ls = 0.0f;
#pragma unroll
                    for (int g = 0; g < KG; ++g) {
                        const float s = (VAR & 1024) ? sv[g] : sx[a * PVB + g * PW + lane];
                        const float e = s == -INFINITY ? 0.0f : (VAR & 512) ? s - mb : sycl::exp(s - mb);
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
                    if constexpr ((VAR & 128) != 0) return;
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
                constexpr int NXR = (2 * NR + PW - 1) / PW;
                float xr[NXR];
                if constexpr ((VAR & 4096) != 0)
#pragma unroll
                    for (int i = 0; i < NXR; ++i) xr[i] = sab[i * PW + lane];
#pragma unroll
                for (int a = 0; a < NR; ++a) {
                    const float al = (VAR & 4096) ? sycl::select_from_group(sg, xr[a / PW], a % PW) : sab[a];
                    const float be = (VAR & 4096) ? sycl::select_from_group(sg, xr[(NR + a) / PW], (NR + a) % PW) : sab[NR + a];
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
        };
        const sycl::nd_range<2> ndr(sycl::range<2>((size_t)nqb * nkvh, (size_t)NL), sycl::range<2>(1, (size_t)NL));
        h.parallel_for(ndr, FlashK<decltype(body), (VAR & 32) != 0>{body});
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
// 0.0f) * scale, plus tab[row][dist] within ext (the relative-bias table attn_prep fills when there are no tiles; with
// tab null, the same term from Rc and rel_bias as attn_flash_tile / attn_scores_tile compute it). P is
// then neither written nor read (keys and values each read once per block; the same values). Sub-group s computes the
// scores of keys kb + 16 s + lane for the NT x G rows, then every sub-group runs attn_flash_part's code on them.
// VAR 1: sub-group s also takes its keys' share of each row's block maximum (local memory, a maximum is the same in any
// order) and their exponentials, once, into local memory; the P.V loop reads them (was: every sub-group computed all
// NT x G x 128 exponentials and maxima itself). The same values (bench_attn card 3, 200K keys + attn_flash_sum: 4 rows
// 1,618-1,628 -> 1,579-1,595 us, 8 rows 2,854-2,876 -> 2,348-2,360, where two 4-row launches took 3,590-3,650).
template <int G, int NT, int VAR = 0>
inline sycl::event attn_flash_dec(sycl::queue &q, const float *Q, const sycl::half *K, const float *tab, const float *Rc,
                                  const float *rel_bias, int nr, const sycl::half *Vt, int vld,
                                  int pos0, int ntok, int nh, int nkvh, int hd, int ext, float scale, float *part, float *pml, int nblk,
                                  int km = 0x7fffffff, int b0 = 0, const SeqRow *mr = nullptr) { // b0: the first block (blocks b0..b0+nblk-1, parts at 0..nblk-1)
    // mr (NT = 1): rows of different sequences, row t at mr[t].pos with mr[t].Kc / Vc (K, Vt and pos0 unused); nblk = the
    // most blocks of any row (a row's blocks past its position write nothing), each row's parts those of a one-token launch
    constexpr int PW = 16, KG = PVB / PW, NR = NT * G, HD = 128, NRL = 16;
    if (mr && NT != 1) throw std::runtime_error("attn_flash_dec: rows of different sequences need NT = 1");
    using HV8 = sycl::vec<sycl::half, 8>;
    using HV = sycl::vec<sycl::half, 16>;
    if (hd != HD || nh != nkvh * G || vld % 16 || HD / PW != KG || (!tab && (nr != NRL || !Rc || !rel_bias)))
        throw std::runtime_error("attn_flash_dec: unsupported shape");
    const int nrg = (ntok + NT - 1) / NT;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> sx(NR * PVB, h), smx(VAR & 1 ? NR * KG : 1, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nrg * nkvh * nblk, (size_t)HD), sycl::range<2>(1, (size_t)HD)),
                       [=](sycl::nd_item<2> it) [[sycl::reqd_sub_group_size(PW)]] {
            auto sg = it.get_sub_group();
            const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id(), c = (int)it.get_local_id(1);
            float vv[NT][G]; // VAR 1: this lane's key's scores, kept for its exponentials
            const int gid = (int)it.get_group(0), b = gid % nblk, kvh = (gid / nblk) % nkvh, rg = gid / nblk / nkvh;
            const int kb = (b0 + b) * PVB, pmax = mr ? mr[rg].pos : pos0 + ntok - 1;
            const sycl::half *Kb = mr ? mr[rg].Kc : K, *Vb = mr ? mr[rg].Vc : Vt;
            int pp[NT];
#pragma unroll
            for (int t = 0; t < NT; ++t) {
                const int tt = rg * NT + t;
                pp[t] = tt < ntok ? (mr ? mr[tt].pos : pos0 + tt) : -1;
            }
            { // the scores of this sub-group's 16 keys (attn_scores_gt's expressions)
                const int g0 = kb + sgi * PW, j = g0 + lane;
                if constexpr ((VAR & 1) != 0)
                    if (g0 > pmax && lane == 0)
#pragma unroll
                        for (int a = 0; a < NR; ++a) smx[a * KG + sgi] = -INFINITY;
                if (g0 <= pmax) {
                    const int jc = sycl::min(j, pmax);
                    const sycl::half *kr = Kb + (size_t)(jc & km) * nkvh * HD + kvh * HD;
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
                            if (j <= pp[t] && dist < ext) {
                                if (tab) v = v + tab[row * ext + dist];
                                else {
                                    const float *br = rel_bias + (size_t)dist * NRL, *rc = Rc + row * NRL;
                                    float tb = 0.0f;
#pragma unroll
                                    for (int i = 0; i < NRL / 4; ++i) {
                                        const sycl::vec<float, 4> bb = *(const sycl::vec<float, 4> *)(br + 4 * i);
                                        const sycl::vec<float, 4> r = *(const sycl::vec<float, 4> *)(rc + 4 * i);
#pragma unroll
                                        for (int k = 0; k < 4; ++k) tb = mac(tb, bb[k], r[k]);
                                    }
                                    v = v + tb;
                                }
                            }
                            if constexpr ((VAR & 1) != 0) {
                                vv[t][gi] = v;
                                const float mg = sycl::reduce_over_group(sg, j <= pp[t] ? v : -INFINITY, sycl::maximum<float>());
                                if (lane == 0) smx[(t * G + gi) * KG + sgi] = mg;
                            } else sx[(t * G + gi) * PVB + sgi * PW + lane] = v; // read only where j <= pp[t]
                        }
                    }
                }
            }
            sycl::group_barrier(it.get_group());
            const sycl::half *vrow = Vb + (size_t)(kvh * HD + c) * vld;
            float mb[NT][G], ls[NT][G], acc[NT][G];
            if constexpr ((VAR & 1) != 0) {
                // each row's block maximum from the 8 key groups' shares (lanes 8-15 repeat lanes 0-7)
#pragma unroll
                for (int t = 0; t < NT; ++t)
#pragma unroll
                    for (int gi = 0; gi < G; ++gi) {
                        mb[t][gi] = sycl::reduce_over_group(sg, smx[(t * G + gi) * KG + (lane & (KG - 1))], sycl::maximum<float>());
                        ls[t][gi] = 0.0f;
                        acc[t][gi] = 0.0f;
                    }
                const int g0 = kb + sgi * PW, j = g0 + lane;
                if (g0 <= pmax) // this sub-group's keys: their exponentials, once
#pragma unroll
                    for (int t = 0; t < NT; ++t)
#pragma unroll
                        for (int gi = 0; gi < G; ++gi)
                            sx[(t * G + gi) * PVB + sgi * PW + lane] = j <= pp[t] ? sycl::exp(vv[t][gi] - mb[t][gi]) : 0.0f;
                sycl::group_barrier(it.get_group());
            } else
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
                        const float e = (VAR & 1) ? sx[(t * G + gi) * PVB + g * PW + lane]
                                                  : j <= pp[t] ? sycl::exp(sx[(t * G + gi) * PVB + g * PW + lane] - mb[t][gi]) : 0.0f;
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
// U: blocks whose partial values a thread loads together before folding them (in order; the same values for every U).
// SGS: each chunk's prefix maxima from 16-lane scans and the 8 sub-group maxima through local memory instead of two
// 128-wide scans and a broadcast (a maximum is the same in any order, so the same factors). INK_SUM_U (default 132 =
// U 32 + SGS; 8 = before; 1xx = xx with SGS). INK_PROF 100K + 16 steps, us per launch: 8 46.1-46.2, 108 42.8-43.6,
// 116 39.1-39.2, 132 36.4-38.9 (values the same). Two passes (all factors first, then one fold with the next loads
// ahead) were slower: 68-90 us.
// Chunks (b0 > 0 or a state buffer): the parts hold blocks b0..b0+nblk-1; st (rows x (128 + 2) floats: the partial
// sum A of each channel, then M and L) carries the fold from one chunk to the next: from = 1 starts from st instead of
// the sink, to = 1 saves the state there instead of writing out. b0 is a multiple of 128 blocks, so every group of 128
// blocks (one scan, one run of folds) is the one the whole fold takes, and the values are the same.
// pe (INK_WO_MR_PE, one sequence, the final fold only: to = 0): each written value's PE parts too (bfsplit.hpp pe_store,
// row t of this launch = row pe.t0 + t of the step, input k = head x 128 + channel); a state-only chunk (to) writes none.
template <int U, bool SGS>
inline sycl::event attn_flash_sum_u(sycl::queue &q, const float *part, const float *pml, int nblk, int pos0, int ntok, int nh, int hd,
                                    const float *sink, const float *gate, float *out, int b0 = 0, float *st = nullptr, int from = 0,
                                    int to = 0, const SeqRow *mr = nullptr, PeOut pe = {}) { // mr: row t at mr[t].pos (pos0 unused)
    constexpr int NB = 128;
    if (hd != NB) throw std::runtime_error("attn_flash_sum: head_dim 128 only");
    if (b0 % NB) throw std::runtime_error("attn_flash_sum: chunks start at a multiple of 128 blocks");
    if (pe.pe && (mr || to || !pe_shape_ok(pe, ntok, nh * NB))) throw std::runtime_error("attn_flash_sum: PE parts shape");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> sl(NB, h), sal(NB, h), sbe(NB, h), sgm(NB / 16, h);
        h.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ntok * nh * NB), sycl::range<1>((size_t)NB)),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
            const int row = (int)it.get_group(0), c = (int)it.get_local_id(0), t = row / nh, p = mr ? mr[t].pos : pos0 + t;
            const int nb = sycl::min(p / PVB + 1 - b0, nblk); // this row's blocks in the chunk (b0 relative)
            const float *pr = part + (size_t)row * nblk * NB + c, *pm = pml + (size_t)row * nblk * 2;
            float M = sink[row], L = 1.0f, A = 0.0f;
            if (from) {
                const float *sr = st + (size_t)row * (NB + 2);
                A = sr[c]; M = sr[NB]; L = sr[NB + 1];
            }
            for (int c0 = 0; c0 < nb; c0 += NB) {
                const int cnt = sycl::min(NB, nb - c0);
                const bool ok = c < cnt;
                const float mb = ok ? pm[2 * (c0 + c)] : -INFINITY;
                if (ok) sl[c] = pm[2 * (c0 + c) + 1];
                float mn, mp, mlast;
                if constexpr (SGS) {
                    auto sg = it.get_sub_group();
                    const int sid = (int)sg.get_group_linear_id();
                    const float si = sycl::inclusive_scan_over_group(sg, mb, sycl::maximum<float>());
                    const float se = sycl::exclusive_scan_over_group(sg, mb, sycl::maximum<float>());
                    if (sg.get_local_linear_id() == 15) sgm[sid] = si;
                    sycl::group_barrier(it.get_group());
                    float pre = -INFINITY, all = -INFINITY;
#pragma unroll
                    for (int k = 0; k < NB / 16; ++k) {
                        const float v = sgm[k];
                        if (k < sid) pre = sycl::fmax(pre, v);
                        all = sycl::fmax(all, v);
                    }
                    mn = sycl::fmax(M, sycl::fmax(pre, si));
                    mp = sycl::fmax(M, sycl::fmax(pre, se));
                    mlast = sycl::fmax(M, all);
                } else {
                    mn = sycl::fmax(M, sycl::inclusive_scan_over_group(it.get_group(), mb, sycl::maximum<float>()));
                    mp = sycl::fmax(M, sycl::exclusive_scan_over_group(it.get_group(), mb, sycl::maximum<float>()));
                    mlast = sycl::group_broadcast(it.get_group(), mn, cnt - 1);
                }
                if (ok) { sal[c] = sycl::exp(mp - mn); sbe[c] = sycl::exp(mb - mn); }
                sycl::group_barrier(it.get_group());
                int i = 0;
                for (; i + U - 1 < cnt; i += U) {
                    float v[U];
#pragma unroll
                    for (int u = 0; u < U; ++u) v[u] = pr[(size_t)(c0 + i + u) * NB];
#pragma unroll
                    for (int u = 0; u < U; ++u) {
                        const float al = sal[i + u], be = sbe[i + u];
                        L = mac(L * al, sl[i + u], be);
                        A = mac(A * al, v[u], be);
                    }
                }
                if (i < cnt) { // the rest: loads together as well, folds only of blocks that exist
                    float v[U];
#pragma unroll
                    for (int u = 0; u < U; ++u) v[u] = i + u < cnt ? pr[(size_t)(c0 + i + u) * NB] : 0.0f;
#pragma unroll
                    for (int u = 0; u < U; ++u)
                        if (i + u < cnt) {
                            const float al = sal[i + u], be = sbe[i + u];
                            L = mac(L * al, sl[i + u], be);
                            A = mac(A * al, v[u], be);
                        }
                }
                M = mlast;
                sycl::group_barrier(it.get_group());
            }
            if (to) {
                float *sr = st + (size_t)row * (NB + 2);
                sr[c] = A;
                if (c == 0) { sr[NB] = M; sr[NB + 1] = L; }
                return;
            }
            const size_t o = (size_t)row * NB + c;
            const float v = (A * (1.0f / L)) * (1.0f / (1.0f + sycl::exp(-gate[o])));
            out[o] = v;
            if (pe.pe) pe_store(pe, t, (row - t * nh) * NB + c, v); // (the stored word's parts)
        });
    });
}
inline int flash_sum_u() {
    static const int v = std::getenv("INK_SUM_U") ? std::atoi(std::getenv("INK_SUM_U")) : 132;
    return v;
}
inline sycl::event attn_flash_sum(sycl::queue &q, const float *part, const float *pml, int nblk, int pos0, int ntok, int nh, int hd,
                                  const float *sink, const float *gate, float *out, int b0 = 0, float *st = nullptr, int from = 0,
                                  int to = 0, const SeqRow *mr = nullptr, PeOut pe = {}) {
    switch (flash_sum_u()) {
    case 8: return attn_flash_sum_u<8, false>(q, part, pml, nblk, pos0, ntok, nh, hd, sink, gate, out, b0, st, from, to, mr, pe);
    case 16: return attn_flash_sum_u<16, false>(q, part, pml, nblk, pos0, ntok, nh, hd, sink, gate, out, b0, st, from, to, mr, pe);
    case 32: return attn_flash_sum_u<32, false>(q, part, pml, nblk, pos0, ntok, nh, hd, sink, gate, out, b0, st, from, to, mr, pe);
    case 108: return attn_flash_sum_u<8, true>(q, part, pml, nblk, pos0, ntok, nh, hd, sink, gate, out, b0, st, from, to, mr, pe);
    case 116: return attn_flash_sum_u<16, true>(q, part, pml, nblk, pos0, ntok, nh, hd, sink, gate, out, b0, st, from, to, mr, pe);
    default: return attn_flash_sum_u<32, true>(q, part, pml, nblk, pos0, ntok, nh, hd, sink, gate, out, b0, st, from, to, mr, pe);
    }
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
