// moe_group.hpp: expert products for several tokens with each chosen expert's rows decoded once per batch of up to
// MB slots that chose it (a slot = one token's k-th expert). Per (row, slot) the arithmetic is exactly GemvPair's /
// GemvRoutedR's (same decode, same chunk-per-lane sums, same butterfly), so results equal the one-slot-at-a-time
// kernels bit for bit; only the work layout changes.
//  moe_group: slots grouped by expert (ascending expert id, ascending slot inside a group).
//  GroupedPair: gate and up rows + SITU (as GemvPair<D, SituOp>); GroupedRows: R rows (as GemvRoutedR<D, R>).
#pragma once
#include "gemv2.hpp"

namespace ink {

constexpr int MOE_TS = 16; // slots per tile of the token-parallel kernels (one per lane)
struct MoeGroups {
    int32_t *count = nullptr; // [1] active experts A
    int32_t *exp = nullptr;   // [ne] expert of group a
    int32_t *off = nullptr;   // [ne + 1] first slot index (in slots) of group a; off[A] = K
    int32_t *slots = nullptr; // [K] slots, grouped
    int32_t *ecount = nullptr;                                    // [ne] slots per expert (scratch)
    int32_t *ntiles = nullptr;                                    // [1] tiles T
    int32_t *tile_exp = nullptr, *tile_s0 = nullptr, *tile_n = nullptr; // [ne + K / 16] expert, first slot index, slots
    void alloc(Device &d, int ne, int kmax) {
        count = d.alloc<int32_t>(1); exp = d.alloc<int32_t>(ne); off = d.alloc<int32_t>(ne + 1); slots = d.alloc<int32_t>(kmax);
        ecount = d.alloc<int32_t>(ne);
        int tmax = max_tiles(ne, kmax);
        ntiles = d.alloc<int32_t>(1); tile_exp = d.alloc<int32_t>(tmax); tile_s0 = d.alloc<int32_t>(tmax); tile_n = d.alloc<int32_t>(tmax);
    }
    static int max_tiles(int ne, int k) { return ne + k / MOE_TS; }
};

// Two passes, one work-group per expert in each. 1: the expert's slot count. 2: its offsets from the counts of the
// lower experts, its slots in ascending order (a work-group scan over blocks of slots), its group entry and tiles.
// Same output as the first one-work-group version: groups by ascending expert, ascending slots inside a group.
inline sycl::event moe_group(sycl::queue &q, const int32_t *ids, int K, int ne, MoeGroups g) {
    constexpr int GW = 256;
    q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ne * GW), sycl::range<1>(GW)), [=](sycl::nd_item<1> it) {
        const int e = (int)it.get_group(0), l = (int)it.get_local_id(0);
        int c = 0;
        for (int s = l; s < K; s += GW) c += ids[s] == e;
        c = sycl::reduce_over_group(it.get_group(), c, sycl::plus<int>());
        if (l == 0) g.ecount[e] = c;
    });
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)ne * GW), sycl::range<1>(GW)), [=](sycl::nd_item<1> it) {
        const int e = (int)it.get_group(0), l = (int)it.get_local_id(0);
        auto grp = it.get_group();
        int ps = 0, pa = 0, pt = 0, ta = 0, tt = 0;
        for (int f = l; f < ne; f += GW) {
            int c = g.ecount[f], act = c > 0 ? 1 : 0, nt = (c + MOE_TS - 1) / MOE_TS;
            if (f < e) { ps += c; pa += act; pt += nt; }
            ta += act; tt += nt;
        }
        const int start = sycl::reduce_over_group(grp, ps, sycl::plus<int>());
        const int a = sycl::reduce_over_group(grp, pa, sycl::plus<int>());
        const int t0 = sycl::reduce_over_group(grp, pt, sycl::plus<int>());
        const int na = sycl::reduce_over_group(grp, ta, sycl::plus<int>());
        const int ntt = sycl::reduce_over_group(grp, tt, sycl::plus<int>());
        const int cnt = g.ecount[e];
        if (l == 0) {
            if (cnt) { g.exp[a] = e; g.off[a] = start; }
            if (e == 0) { g.count[0] = na; g.off[na] = K; g.ntiles[0] = ntt; }
        }
        if (!cnt) return; // the same for the whole work-group
        int base = start;
        for (int s0 = 0; s0 < K; s0 += GW) {
            const int s = s0 + l;
            const int m = (s < K && ids[s] == e) ? 1 : 0;
            const int r = sycl::exclusive_scan_over_group(grp, m, sycl::plus<int>());
            if (m) g.slots[base + r] = s;
            base += sycl::reduce_over_group(grp, m, sycl::plus<int>());
        }
        const int nt = (cnt + MOE_TS - 1) / MOE_TS;
        for (int t = l; t < nt; t += GW) {
            g.tile_exp[t0 + t] = e;
            g.tile_s0[t0 + t] = start + t * MOE_TS;
            g.tile_n[t0 + t] = sycl::min(MOE_TS, cnt - t * MOE_TS);
        }
    });
}

constexpr int MOE_MB = 8; // slots per decode

// gate rows r and up rows r (+ rows of B) of the group's expert for every slot of the group, then op(slot, r, g, u)
template <class D, class Op> struct GroupedPair {
    const uint8_t *A, *B; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *x; int ldx, xdiv;
    Op op;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        int a = (int)it.get_group(0);
        if (a >= g.count[0]) return;
        auto sg = it.get_sub_group();
        int r = (int)it.get_group(1) * sgw + (int)sg.get_group_linear_id();
        if (r >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        size_t eo = (size_t)g.exp[a] * estride;
        const uint8_t *ra = A + eo + (size_t)r * rb, *rbp = B + eo + (size_t)r * rb;
        const int s0 = g.off[a], s1 = g.off[a + 1], nc = cols / 32;
        for (int b0 = s0; b0 < s1; b0 += MOE_MB) {
            const int cnt = sycl::min(MOE_MB, s1 - b0);
            int sl[MOE_MB];
            for (int m = 0; m < MOE_MB; ++m) sl[m] = m < cnt ? g.slots[b0 + m] : 0;
            float acc[2][MOE_MB];
            for (int j = 0; j < 2; ++j) for (int m = 0; m < MOE_MB; ++m) acc[j][m] = 0.0f;
            for (int c = lane; c < nc; c += SG) {
                float o[2][32];
                D::decode32(ra, cols, c, o[0]);
                D::decode32(rbp, cols, c, o[1]);
                for (int m = 0; m < MOE_MB; ++m) {
                    if (m >= cnt) break;
                    float xs[32];
                    load_x32(x + (size_t)(xdiv ? sl[m] / xdiv : sl[m]) * ldx + 32 * c, xs);
                    for (int j = 0; j < 2; ++j) {
                        float s = 0.0f;
                        for (int i = 0; i < 32; ++i) s = mac(s, o[j][i], xs[i]);
                        acc[j][m] += s;
                    }
                }
            }
            for (int m = 0; m < MOE_MB; ++m) {
                if (m >= cnt) break;
                float va = sg_sum(sg, acc[0][m]), vb = sg_sum(sg, acc[1][m]);
                if (lane == 0) op(sl[m], r, va, vb);
            }
        }
    }
};

// rows r0..r0+R-1 of the group's expert for every slot: y[slot * ldy + r] (x row = slot)
template <class D, int R> struct GroupedRows {
    const uint8_t *W; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *x; int ldx;
    float *y; int ldy;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        int a = (int)it.get_group(0);
        if (a >= g.count[0]) return;
        auto sg = it.get_sub_group();
        int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        const uint8_t *base = W + (size_t)g.exp[a] * estride;
        const int s0 = g.off[a], s1 = g.off[a + 1], nc = cols / 32;
        for (int b0 = s0; b0 < s1; b0 += MOE_MB) {
            const int cnt = sycl::min(MOE_MB, s1 - b0);
            int sl[MOE_MB];
            for (int m = 0; m < MOE_MB; ++m) sl[m] = m < cnt ? g.slots[b0 + m] : 0;
            float acc[R][MOE_MB];
            for (int j = 0; j < R; ++j) for (int m = 0; m < MOE_MB; ++m) acc[j][m] = 0.0f;
            for (int c = lane; c < nc; c += SG) {
                float o[R][32];
                for (int j = 0; j < R; ++j)
                    if (r0 + j < rows) D::decode32(base + (size_t)(r0 + j) * rb, cols, c, o[j]);
                for (int m = 0; m < MOE_MB; ++m) {
                    if (m >= cnt) break;
                    float xs[32];
                    load_x32(x + (size_t)sl[m] * ldx + 32 * c, xs);
                    for (int j = 0; j < R; ++j) {
                        if (r0 + j >= rows) break;
                        float s = 0.0f;
                        for (int i = 0; i < 32; ++i) s = mac(s, o[j][i], xs[i]);
                        acc[j][m] += s;
                    }
                }
            }
            for (int m = 0; m < MOE_MB; ++m) {
                if (m >= cnt) break;
                for (int j = 0; j < R; ++j) {
                    float v = sg_sum(sg, acc[j][m]);
                    if (lane == 0 && r0 + j < rows) y[(size_t)sl[m] * ldy + r0 + j] = v;
                }
            }
        }
    }
};

// ---- piecewise kernels: each 32-value chunk handled in four pieces of 8 values, so a loaded input piece feeds
// every row of the sub-group while only 8 decoded values per row are live. The per-(row, slot) chunk sum still
// runs over i = 0..31 in order (s starts at +0 and takes the pieces in order), then joins the lane sum: the same
// arithmetic as GroupedPair / GroupedRows.
template <class D> struct Piece { // generic: decode the whole chunk, pieces are slices of it
    struct C { float v[32]; };
    static void load(const uint8_t *row, int cols, int c, C &ch) { D::decode32(row, cols, c, ch.v); }
    static void get(const C &ch, int p, float *o) { for (int i = 0; i < 8; ++i) o[i] = ch.v[8 * p + i]; }
};
template <> struct Piece<pl::NVFP4P> { // the 16 code bytes and 2 scale bytes stay packed until a piece needs them
    struct C { uint32_t w[4]; uint16_t dd; };
    static void load(const uint8_t *row, int cols, int c, C &ch) {
        sycl::vec<uint32_t, 2> qa = *(const sycl::vec<uint32_t, 2> *)(row + 16 * c);
        sycl::vec<uint32_t, 2> qb = *(const sycl::vec<uint32_t, 2> *)(row + 16 * c + 8);
        ch.w[0] = qa[0]; ch.w[1] = qa[1]; ch.w[2] = qb[0]; ch.w[3] = qb[1];
        std::memcpy(&ch.dd, row + cols / 2 + 2 * c, 2);
    }
    // piece p = values 8p..8p+7 of the chunk: block k = p / 2, low codes (p even) or high codes (p odd); the same
    // expressions as NVFP4P::decode_words, so the same floats
    static void get(const C &ch, int p, float *o) {
        const int k = p >> 1;
        const float d = pl::ue4m3_bits((uint8_t)(ch.dd >> (8 * k))) * 32768.0f;
        for (int hh = 0; hh < 2; ++hh) {
            const uint32_t x = ch.w[2 * k + hh];
            const int j0 = 4 * hh;
            if (!(p & 1)) { pl::NVFP4P::pair(x, 9, d, o[j0 + 0], o[j0 + 2]); pl::NVFP4P::pair(x, 1, d, o[j0 + 1], o[j0 + 3]); }
            else { pl::NVFP4P::pair(x, 5, d, o[j0 + 0], o[j0 + 2]); pl::NVFP4P::pair(x, -3, d, o[j0 + 1], o[j0 + 3]); }
        }
    }
};
inline void load_x8(const float *xv, float *xs) {
    using V = sycl::vec<float, 4>;
    V a = *(const V *)xv, b = *(const V *)(xv + 4);
    for (int i = 0; i < 4; ++i) { xs[i] = a[i]; xs[4 + i] = b[i]; }
}
template <bool BIG> struct GrfProps {
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        if constexpr (BIG) return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<256>};
        else return sycl::ext::oneapi::experimental::properties{};
    }
};

// NP gate rows r0.. and the matching up rows per sub-group (2 NP rows), slots in batches of MB
template <class D, class Op, int NP, int MB, bool BIG> struct GroupedPairP : GrfProps<BIG> {
    const uint8_t *A, *B; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *x; int ldx, xdiv;
    Op op;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        constexpr int NR = 2 * NP;
        int a = (int)it.get_group(0);
        if (a >= g.count[0]) return;
        auto sg = it.get_sub_group();
        int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * NP;
        if (r0 >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        size_t eo = (size_t)g.exp[a] * estride;
        const uint8_t *rp[NR];
        for (int j = 0; j < NP; ++j) {
            int r = sycl::min(r0 + j, rows - 1); // rows past the end repeat the last row (results not stored)
            rp[j] = A + eo + (size_t)r * rb;
            rp[NP + j] = B + eo + (size_t)r * rb;
        }
        const int s0 = g.off[a], s1 = g.off[a + 1], nc = cols / 32;
        for (int b0 = s0; b0 < s1; b0 += MB) {
            const int cnt = sycl::min(MB, s1 - b0);
            const float *xr[MB];
            int sl[MB];
            for (int m = 0; m < MB; ++m) {
                sl[m] = m < cnt ? g.slots[b0 + m] : 0;
                xr[m] = x + (size_t)(xdiv ? sl[m] / xdiv : sl[m]) * ldx;
            }
            float acc[NR][MB];
            for (int j = 0; j < NR; ++j) for (int m = 0; m < MB; ++m) acc[j][m] = 0.0f;
            for (int c = lane; c < nc; c += SG) {
                typename Piece<D>::C ch[NR];
                for (int j = 0; j < NR; ++j) Piece<D>::load(rp[j], cols, c, ch[j]);
                float s[NR][MB];
                for (int j = 0; j < NR; ++j) for (int m = 0; m < MB; ++m) s[j][m] = 0.0f;
                for (int p = 0; p < 4; ++p) {
                    float o[NR][8];
                    for (int j = 0; j < NR; ++j) Piece<D>::get(ch[j], p, o[j]);
                    for (int m = 0; m < MB; ++m) {
                        if (m >= cnt) break;
                        float xs[8];
                        load_x8(xr[m] + 32 * c + 8 * p, xs);
                        for (int j = 0; j < NR; ++j)
                            for (int i = 0; i < 8; ++i) s[j][m] = mac(s[j][m], o[j][i], xs[i]);
                    }
                }
                for (int j = 0; j < NR; ++j) for (int m = 0; m < MB; ++m) acc[j][m] += s[j][m];
            }
            for (int m = 0; m < MB; ++m) {
                if (m >= cnt) break;
                for (int j = 0; j < NP; ++j) {
                    float va = sg_sum(sg, acc[j][m]), vb = sg_sum(sg, acc[NP + j][m]);
                    if (lane == 0 && r0 + j < rows) op(sl[m], r0 + j, va, vb);
                }
            }
        }
    }
};

// R rows r0.. per sub-group, slots in batches of MB: y[slot * ldy + r]
template <class D, int R, int MB, bool BIG> struct GroupedRowsP : GrfProps<BIG> {
    const uint8_t *W; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *x; int ldx;
    float *y; int ldy;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        int a = (int)it.get_group(0);
        if (a >= g.count[0]) return;
        auto sg = it.get_sub_group();
        int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        const uint8_t *base = W + (size_t)g.exp[a] * estride;
        const uint8_t *rp[R];
        for (int j = 0; j < R; ++j) rp[j] = base + (size_t)sycl::min(r0 + j, rows - 1) * rb;
        const int s0 = g.off[a], s1 = g.off[a + 1], nc = cols / 32;
        for (int b0 = s0; b0 < s1; b0 += MB) {
            const int cnt = sycl::min(MB, s1 - b0);
            const float *xr[MB];
            int sl[MB];
            for (int m = 0; m < MB; ++m) {
                sl[m] = m < cnt ? g.slots[b0 + m] : 0;
                xr[m] = x + (size_t)sl[m] * ldx;
            }
            float acc[R][MB];
            for (int j = 0; j < R; ++j) for (int m = 0; m < MB; ++m) acc[j][m] = 0.0f;
            for (int c = lane; c < nc; c += SG) {
                typename Piece<D>::C ch[R];
                for (int j = 0; j < R; ++j) Piece<D>::load(rp[j], cols, c, ch[j]);
                float s[R][MB];
                for (int j = 0; j < R; ++j) for (int m = 0; m < MB; ++m) s[j][m] = 0.0f;
                for (int p = 0; p < 4; ++p) {
                    float o[R][8];
                    for (int j = 0; j < R; ++j) Piece<D>::get(ch[j], p, o[j]);
                    for (int m = 0; m < MB; ++m) {
                        if (m >= cnt) break;
                        float xs[8];
                        load_x8(xr[m] + 32 * c + 8 * p, xs);
                        for (int j = 0; j < R; ++j)
                            for (int i = 0; i < 8; ++i) s[j][m] = mac(s[j][m], o[j][i], xs[i]);
                    }
                }
                for (int j = 0; j < R; ++j) for (int m = 0; m < MB; ++m) acc[j][m] += s[j][m];
            }
            for (int m = 0; m < MB; ++m) {
                if (m >= cnt) break;
                for (int j = 0; j < R; ++j) {
                    float v = sg_sum(sg, acc[j][m]);
                    if (lane == 0 && r0 + j < rows) y[(size_t)sl[m] * ldy + r0 + j] = v;
                }
            }
        }
    }
};

// ---- token-parallel kernels (steps of many tokens): a sub-group takes one tile (up to 16 slots of one expert), one
// slot per lane, and NR rows. Each lane computes its slot's full product for every row, replaying the fixed
// arithmetic of the lane-per-chunk kernels: for each of the 16 virtual lanes v, the chunks v, v + 16, ... (each
// chunk's 32 products summed in index order, the chunk sums added in order from +0), then the virtual lane sums
// combined exactly as sg_sum's xor butterfly pairs them (v with v + 8, then + 4, + 2, + 1; a + b = b + a exactly),
// built up in bit-reversed order of v with a 4-deep stack. The weights are decoded once per sub-group: lane l
// decodes values l and 16 + l of a chunk (the same expressions as NVFP4P::decode_words, so the same floats), and the
// products read them back by index from the sub-group.
inline constexpr int br4(int v) { return ((v & 1) << 3) | ((v & 2) << 1) | ((v & 4) >> 1) | ((v & 8) >> 3); }
inline float nvfp4_one(uint32_t byte, int nib, float d32768) {
    uint32_t c = (byte >> nib) & 15u;
    uint16_t bits = (uint16_t)(((c & 7u) << 9) | ((c & 8u) << 12));
    return (float)sycl::bit_cast<sycl::half>(bits) * d32768;
}
// chunk c of an NVFP4P row: this lane's values l and 16 + l
inline void nvfp4_lane2(const uint8_t *row, int cols, int c, int bl, int nib, float &lo, float &hi) {
    const uint8_t *q = row + 16 * c;
    uint16_t dd;
    std::memcpy(&dd, row + cols / 2 + 2 * c, 2);
    lo = nvfp4_one(q[bl], nib, pl::ue4m3_bits((uint8_t)dd) * 32768.0f);
    hi = nvfp4_one(q[8 + bl], nib, pl::ue4m3_bits((uint8_t)(dd >> 8)) * 32768.0f);
}
// row pointers rp[0..NR-1] x per-lane input xr: res[j] = the lane-per-chunk kernels' value for row j
template <int NR> inline void slot_dots(sycl::sub_group sg, const uint8_t *const *rp, int cols, const float *xr, int lane, float *res) {
    const int nc = cols / 32, bl = lane & 7, nib = (lane >> 3) * 4;
    float st[NR][4];
#pragma unroll
    for (int vi = 0; vi < 16; ++vi) {
        const int v = br4(vi);
        float acc[NR];
        for (int j = 0; j < NR; ++j) acc[j] = 0.0f;
        for (int c = v; c < nc; c += SG) {
            float xs[32];
            load_x32(xr + 32 * c, xs);
            float lo[NR], hi[NR], s[NR];
            for (int j = 0; j < NR; ++j) { nvfp4_lane2(rp[j], cols, c, bl, nib, lo[j], hi[j]); s[j] = 0.0f; }
            // the rows' sums interleaved (independent chains), each still over i = 0..31 in order
            for (int i = 0; i < 16; ++i)
                for (int j = 0; j < NR; ++j) s[j] = mac(s[j], sycl::select_from_group(sg, lo[j], i), xs[i]);
            for (int i = 0; i < 16; ++i)
                for (int j = 0; j < NR; ++j) s[j] = mac(s[j], sycl::select_from_group(sg, hi[j], i), xs[16 + i]);
            for (int j = 0; j < NR; ++j) acc[j] += s[j];
        }
        for (int j = 0; j < NR; ++j) {
            float val = acc[j];
            int lev = 0;
            for (int tt = vi; tt & 1; tt >>= 1) val = st[j][lev++] + val;
            if (lev < 4) st[j][lev] = val;
            else res[j] = val;
        }
    }
}
template <class Op, int NG, bool BIG> struct SlotPairNV : GrfProps<BIG> {
    const uint8_t *A, *B; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *x; int ldx, xdiv;
    Op op;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        auto sg = it.get_sub_group();
        const int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * NG;
        if (r0 >= rows) return;
        const int lane = (int)sg.get_local_linear_id();
        const int cnt = g.tile_n[t];
        const int slot = g.slots[g.tile_s0[t] + sycl::min(lane, cnt - 1)];
        const float *xr = x + (size_t)(xdiv ? slot / xdiv : slot) * ldx;
        const size_t eo = (size_t)g.tile_exp[t] * estride;
        const uint8_t *rp[2 * NG];
        for (int j = 0; j < NG; ++j) {
            int r = sycl::min(r0 + j, rows - 1);
            rp[j] = A + eo + (size_t)r * rb;
            rp[NG + j] = B + eo + (size_t)r * rb;
        }
        float res[2 * NG];
        slot_dots<2 * NG>(sg, rp, cols, xr, lane, res);
        if (lane < cnt)
            for (int j = 0; j < NG; ++j)
                if (r0 + j < rows) op(slot, r0 + j, res[j], res[NG + j]);
    }
};
template <int R, bool BIG> struct SlotRowsNV : GrfProps<BIG> {
    const uint8_t *W; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *x; int ldx;
    float *y; int ldy;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        auto sg = it.get_sub_group();
        const int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        const int lane = (int)sg.get_local_linear_id();
        const int cnt = g.tile_n[t];
        const int slot = g.slots[g.tile_s0[t] + sycl::min(lane, cnt - 1)];
        const float *xr = x + (size_t)slot * ldx;
        const uint8_t *base = W + (size_t)g.tile_exp[t] * estride;
        const uint8_t *rp[R];
        for (int j = 0; j < R; ++j) rp[j] = base + (size_t)sycl::min(r0 + j, rows - 1) * rb;
        float res[R];
        slot_dots<R>(sg, rp, cols, xr, lane, res);
        if (lane < cnt)
            for (int j = 0; j < R; ++j)
                if (r0 + j < rows) y[(size_t)slot * ldy + r0 + j] = res[j];
    }
};

// ---- token-parallel kernels over transposed tiles: the inputs of a tile are stored column-major across the 16 lanes
// (Xt[(t * cols + col) * 16 + lane]), so a sub-group's load of one column is one 64-byte line; lane l decodes byte l
// of a chunk (values 16k + b and 16k + 8 + b, k = l / 8, b = l % 8), one load per row and chunk. Same arithmetic.
// tile_gather: Xt from x (row of slot s = s / xdiv, or s when xdiv = 0); lanes past a tile's slots get zeros
inline sycl::event tile_gather(sycl::queue &q, MoeGroups g, int tiles, const float *x, int ldx, int xdiv, int cols, float *Xt) {
    constexpr int GW = 256; // 16 columns x 16 lanes
    const int ncb = (cols + 15) / 16;
    return q.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)tiles, (size_t)ncb * GW), sycl::range<2>(1, GW)), [=](sycl::nd_item<2> it) {
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        const int li = (int)it.get_local_id(1), lane = li & 15, col = (int)it.get_group(1) * 16 + (li >> 4);
        if (col >= cols) return;
        const int cnt = g.tile_n[t];
        float v = 0.0f;
        if (lane < cnt) {
            int s = g.slots[g.tile_s0[t] + lane];
            v = x[(size_t)(xdiv ? s / xdiv : s) * ldx + col];
        }
        Xt[((size_t)t * cols + col) * MOE_TS + lane] = v;
    });
}
template <int NR, bool IL>
inline void slot_dots_t(sycl::sub_group sg, const uint8_t *const *rp, int cols, const float *xt, int lane, float *res) {
    const int nc = cols / 32;
    float st[NR][4];
#pragma unroll
    for (int vi = 0; vi < 16; ++vi) {
        const int v = br4(vi);
        float acc[NR];
        for (int j = 0; j < NR; ++j) acc[j] = 0.0f;
        for (int c = v; c < nc; c += SG) {
            // the chunk's inputs for the 16 lanes are 2 KB in a row: four sub-group block reads (element k of lane l
            // = p[16 k + l])
            float xs[32];
            const float *xc = xt + (size_t)32 * MOE_TS * c;
            for (int q = 0; q < 4; ++q) {
                auto mp = sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(const_cast<float *>(xc + 128 * q));
                sycl::vec<float, 8> v8 = sg.load<8>(mp);
                for (int k = 0; k < 8; ++k) xs[8 * q + k] = v8[k];
            }
            float lo[NR], hi[NR], s[NR];
            for (int j = 0; j < NR; ++j) {
                const uint8_t *row = rp[j];
                uint32_t byte = row[16 * c + lane];
                float d = pl::ue4m3_bits(row[cols / 2 + 2 * c + (lane >> 3)]) * 32768.0f;
                lo[j] = nvfp4_one(byte, 0, d);
                hi[j] = nvfp4_one(byte, 4, d);
                s[j] = 0.0f;
            }
            // value i of the chunk sits in lane 8 (i / 16) + i % 8, low (i % 16 < 8) or high code
            if constexpr (IL) {
                for (int i = 0; i < 32; ++i)
                    for (int j = 0; j < NR; ++j)
                        s[j] = mac(s[j], sycl::select_from_group(sg, ((i >> 3) & 1) ? hi[j] : lo[j], 8 * (i >> 4) + (i & 7)), xs[i]);
            } else {
                for (int j = 0; j < NR; ++j)
                    for (int i = 0; i < 32; ++i)
                        s[j] = mac(s[j], sycl::select_from_group(sg, ((i >> 3) & 1) ? hi[j] : lo[j], 8 * (i >> 4) + (i & 7)), xs[i]);
            }
            for (int j = 0; j < NR; ++j) acc[j] += s[j];
        }
        for (int j = 0; j < NR; ++j) {
            float val = acc[j];
            int lev = 0;
            for (int tt = vi; tt & 1; tt >>= 1) val = st[j][lev++] + val;
            if (lev < 4) st[j][lev] = val;
            else res[j] = val;
        }
    }
}
// gate|up over Xt; TOUT: the activation goes to the transposed tile layout Ht[(t * rows + r) * 16 + lane] (the down
// kernel's input), else op(slot, r, g, u)
template <class Op, int NG, bool BIG, bool IL, bool TOUT> struct SlotPairT : GrfProps<BIG> {
    const uint8_t *A, *B; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *Xt;
    Op op;
    float *Ht;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        auto sg = it.get_sub_group();
        const int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * NG;
        if (r0 >= rows) return;
        const int lane = (int)sg.get_local_linear_id();
        const int cnt = g.tile_n[t];
        const size_t eo = (size_t)g.tile_exp[t] * estride;
        const uint8_t *rp[2 * NG];
        for (int j = 0; j < NG; ++j) {
            int r = sycl::min(r0 + j, rows - 1);
            rp[j] = A + eo + (size_t)r * rb;
            rp[NG + j] = B + eo + (size_t)r * rb;
        }
        float res[2 * NG];
        slot_dots_t<2 * NG, IL>(sg, rp, cols, Xt + (size_t)t * cols * MOE_TS, lane, res);
        const int slot = g.slots[g.tile_s0[t] + sycl::min(lane, cnt - 1)];
        for (int j = 0; j < NG; ++j) {
            if (r0 + j >= rows) break;
            if constexpr (TOUT) Ht[((size_t)t * rows + r0 + j) * MOE_TS + lane] = lane < cnt ? op.act(slot, res[j], res[NG + j]) : 0.0f;
            else if (lane < cnt) op(slot, r0 + j, res[j], res[NG + j]);
        }
    }
};
template <int R, bool BIG, bool IL> struct SlotRowsT : GrfProps<BIG> {
    const uint8_t *W; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *Xt;
    float *y; int ldy;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        auto sg = it.get_sub_group();
        const int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        const int lane = (int)sg.get_local_linear_id();
        const int cnt = g.tile_n[t];
        const uint8_t *base = W + (size_t)g.tile_exp[t] * estride;
        const uint8_t *rp[R];
        for (int j = 0; j < R; ++j) rp[j] = base + (size_t)sycl::min(r0 + j, rows - 1) * rb;
        float res[R];
        slot_dots_t<R, IL>(sg, rp, cols, Xt + (size_t)t * cols * MOE_TS, lane, res);
        if (lane < cnt) {
            const int slot = g.slots[g.tile_s0[t] + lane];
            for (int j = 0; j < R; ++j)
                if (r0 + j < rows) y[(size_t)slot * ldy + r0 + j] = res[j];
        }
    }
};
// (rows per sub-group, large register file, interleaved sums)
#define INK_TTP_COMBOS(X) X(1, false, false) X(2, false, false) X(4, false, false)
#define INK_TTR_COMBOS(X) X(2, false, false) X(4, false, false) X(8, false, false)
struct TTune { int ng = 2, sgw = 2; bool big = false, il = false; };
template <class Op>
inline sycl::event slot_pair_t(sycl::queue &q, const WView &a, const uint8_t *B, size_t estride, int rows, MoeGroups g, int tiles,
                               const float *Xt, Op op, float *Ht, TTune tt) {
    if (a.kind != K_NVFP4P) throw std::runtime_error("slot_pair_t: NVFP4 only");
    const int cols = (int)a.t->ne[0];
    sycl::event e;
    bool done = false;
#define INK_TT_CASE(NG, BIG, IL) \
    if (!done && tt.ng == NG && tt.big == BIG && tt.il == IL) { \
        int nsg = (rows + NG - 1) / NG, ngr = (nsg + tt.sgw - 1) / tt.sgw; \
        sycl::nd_range<2> nr(sycl::range<2>((size_t)tiles, (size_t)ngr * tt.sgw * SG), sycl::range<2>(1, (size_t)tt.sgw * SG)); \
        if (Ht) e = q.parallel_for(nr, SlotPairT<Op, NG, BIG, IL, true>{{}, a.p, B, a.rb, estride, rows, cols, g, Xt, op, Ht, tt.sgw}); \
        else e = q.parallel_for(nr, SlotPairT<Op, NG, BIG, IL, false>{{}, a.p, B, a.rb, estride, rows, cols, g, Xt, op, Ht, tt.sgw}); \
        done = true; }
    INK_TTP_COMBOS(INK_TT_CASE)
#undef INK_TT_CASE
    if (!done) throw std::runtime_error("slot_pair_t: no kernel for this tuning");
    return e;
}
inline sycl::event slot_rows_t(sycl::queue &q, const WView &w, MoeGroups g, int tiles, const float *Xt, float *y, int ldy, TTune tt) {
    if (w.kind != K_NVFP4P) throw std::runtime_error("slot_rows_t: NVFP4 only");
    const int cols = (int)w.t->ne[0], rows = (int)w.t->ne[1];
    const size_t estride = w.rb * (size_t)rows;
    sycl::event e;
    bool done = false;
#define INK_TT_CASE(R, BIG, IL) \
    if (!done && tt.ng == R && tt.big == BIG && tt.il == IL) { \
        int nsg = (rows + R - 1) / R, ngr = (nsg + tt.sgw - 1) / tt.sgw; \
        sycl::nd_range<2> nr(sycl::range<2>((size_t)tiles, (size_t)ngr * tt.sgw * SG), sycl::range<2>(1, (size_t)tt.sgw * SG)); \
        e = q.parallel_for(nr, SlotRowsT<R, BIG, IL>{{}, w.p, w.rb, estride, rows, cols, g, Xt, y, ldy, tt.sgw}); \
        done = true; }
    INK_TTR_COMBOS(INK_TT_CASE)
#undef INK_TT_CASE
    if (!done) throw std::runtime_error("slot_rows_t: no kernel for this tuning");
    return e;
}

// np = 0: the first kernels (GroupedPair/Rows); np > 0: the piecewise kernels; ts = true: the token-parallel kernels
// with np gate rows (pair) or np rows (down)
struct GTune { int np = 0, mb = 8, sgw = 2; bool big = false; bool ts = false; int tiles = 0; }; // tiles: bound (ne + K / 16)

template <class D, class Op, int NP, int MB, bool BIG>
inline sycl::event launch_pair_p(sycl::queue &q, const WView &a, const uint8_t *B, size_t estride, int rows, MoeGroups g, int amax,
                                 const float *x, int ldx, int xdiv, Op op, int sgw) {
    int cols = (int)a.t->ne[0];
    int nsg = (rows + NP - 1) / NP, ngr = (nsg + sgw - 1) / sgw;
    sycl::nd_range<2> nr(sycl::range<2>((size_t)amax, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
    return q.parallel_for(nr, GroupedPairP<D, Op, NP, MB, BIG>{{}, a.p, B, a.rb, estride, rows, cols, g, x, ldx, xdiv, op, sgw});
}
template <class D, int R, int MB, bool BIG>
inline sycl::event launch_rows_p(sycl::queue &q, const WView &w, MoeGroups g, int amax, const float *x, int ldx, float *y, int ldy, int sgw) {
    int cols = (int)w.t->ne[0], rows = (int)w.t->ne[1];
    size_t estride = w.rb * (size_t)rows;
    int nsg = (rows + R - 1) / R, ngr = (nsg + sgw - 1) / sgw;
    sycl::nd_range<2> nr(sycl::range<2>((size_t)amax, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
    return q.parallel_for(nr, GroupedRowsP<D, R, MB, BIG>{{}, w.p, w.rb, estride, rows, cols, g, x, ldx, y, ldy, sgw});
}
// the (np, mb, big) combinations that exist as kernels
#define INK_GP_COMBOS(X) X(1, 8, false) X(1, 16, false) X(2, 4, false) X(2, 8, false) X(2, 8, true) X(4, 4, false) X(4, 4, true) X(4, 8, true)
// Steps of 2-4 tokens (MB = the step's tokens; a token chooses an expert at most once, so a group has at most MB
// slots): each chosen expert's rows decoded once for all of its slots, inputs in lane order (xlane.hpp). Slots past
// the group's count repeat its last slot and are not stored (no branch around the reads). Per (row, slot) the sums
// are gemv_pair_row's / GemvRoutedR's (chunks l, l+16, ... per lane in order, the same butterfly), and the epilogue
// is GemvPair's (op.pre / op.post), so every slot gets the one-token values bit for bit.
// Steps of 5-8 tokens take the MB = 4 kernels: a group of more than MB slots runs in passes of MB (the weights read
// again, from the cache), each slot's sums the same.
template <class D, class Op, int MB> struct GroupedPairS {
    const uint8_t *A, *B; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *x; int ldx, xdiv; // slot k reads the lane-order row x + (k / xdiv) * ldx
    Op op;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        const int a = (int)it.get_group(0);
        if (a >= g.count[0]) return;
        auto sg = it.get_sub_group();
        const int r = (int)it.get_group(1) * sgw + (int)sg.get_group_linear_id();
        if (r >= rows) return;
        const int sa = g.off[a], na = g.off[a + 1] - sa;
        for (int o = 0; o < na; o += MB) pass(sg, a, r, sa + o, sycl::min(MB, na - o));
    }
    void pass(sycl::sub_group sg, int a, int r, int s0, int cnt) const {
        const int lane = (int)sg.get_local_linear_id();
        const size_t eo = (size_t)g.exp[a] * estride;
        const uint8_t *ra = A + eo + (size_t)r * rb, *rbp = B + eo + (size_t)r * rb;
        int sl[MB];
        const float *xv[MB];
#pragma unroll
        for (int m = 0; m < MB; ++m) {
            sl[m] = g.slots[s0 + sycl::min(m, cnt - 1)];
            xv[m] = x + (size_t)(sl[m] / xdiv) * ldx;
        }
        float pre[MB];
        if constexpr (requires { op.pre(0); })
#pragma unroll
            for (int m = 0; m < MB; ++m) pre[m] = op.pre(sl[m]);
        float acc[2][MB];
#pragma unroll
        for (int j = 0; j < 2; ++j)
#pragma unroll
            for (int m = 0; m < MB; ++m) acc[j][m] = 0.0f;
        const int nc = cols / 32;
        for (int c = lane; c < nc; c += SG) {
            float o[2][32];
            D::decode32(ra, cols, c, o[0]);
            D::decode32(rbp, cols, c, o[1]);
#pragma unroll
            for (int m = 0; m < MB; ++m) {
                float xs[32];
                load_x32_lane(xv[m], c, xs);
#pragma unroll
                for (int j = 0; j < 2; ++j) {
                    float sm = 0.0f;
                    for (int i = 0; i < 32; ++i) sm = mac(sm, o[j][i], xs[i]);
                    acc[j][m] += sm;
                }
            }
        }
#pragma unroll
        for (int m = 0; m < MB; ++m) {
            const float va = sg_sum(sg, acc[0][m]), vb = sg_sum(sg, acc[1][m]);
            if (m < cnt) { // the same for the whole sub-group
                if constexpr (requires { op.pre(0); }) op.post(sg, lane, sl[m], r, va, vb, pre[m]);
                else if (lane == 0) op(sl[m], r, va, vb);
            }
        }
    }
};
// one row of the group's expert for all of its slots: y[slot * ldy + r] (slot k reads the lane-order row x + k * ldx)
template <class D, int MB> struct GroupedRowsS {
    const uint8_t *W; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *x; int ldx;
    float *y; int ldy;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        const int a = (int)it.get_group(0);
        if (a >= g.count[0]) return;
        auto sg = it.get_sub_group();
        const int r = (int)it.get_group(1) * sgw + (int)sg.get_group_linear_id();
        if (r >= rows) return;
        const int sa = g.off[a], na = g.off[a + 1] - sa;
        for (int o = 0; o < na; o += MB) pass(sg, a, r, sa + o, sycl::min(MB, na - o));
    }
    void pass(sycl::sub_group sg, int a, int r, int s0, int cnt) const {
        const int lane = (int)sg.get_local_linear_id();
        const uint8_t *row = W + (size_t)g.exp[a] * estride + (size_t)r * rb;
        int sl[MB];
        const float *xv[MB];
#pragma unroll
        for (int m = 0; m < MB; ++m) {
            sl[m] = g.slots[s0 + sycl::min(m, cnt - 1)];
            xv[m] = x + (size_t)sl[m] * ldx;
        }
        float acc[MB];
#pragma unroll
        for (int m = 0; m < MB; ++m) acc[m] = 0.0f;
        const int nc = cols / 32;
        for (int c = lane; c < nc; c += SG) {
            float o[32];
            D::decode32(row, cols, c, o);
#pragma unroll
            for (int m = 0; m < MB; ++m) {
                float xs[32];
                load_x32_lane(xv[m], c, xs);
                float sm = 0.0f;
                for (int i = 0; i < 32; ++i) sm = mac(sm, o[i], xs[i]);
                acc[m] += sm;
            }
        }
#pragma unroll
        for (int m = 0; m < MB; ++m) {
            const float v = sg_sum(sg, acc[m]);
            if (m < cnt && lane == 0) y[(size_t)sl[m] * ldy + r] = v;
        }
    }
};
// The NVFP4 layers' small steps with NP gate|up row pairs (GroupedPairT) or R rows (GroupedRowsT) per sub-group, so
// each input value loaded serves several rows: a lane keeps its rows' raw words (16 bytes + 2 scale bytes per row)
// and decodes 8 values at a time (NVFP4P::dec8), each (row, slot) chunk sum still running over i = 0..31 in order.
// (GroupedRowsS at 4 tokens: input reads ~28x the weight bytes, down 114 us where one token takes 29.)
template <int NR> struct Nv4Rows { uint32_t w[NR][4]; uint16_t dd[NR]; };
template <int NR> inline void nv4_load(Nv4Rows<NR> &q, const uint8_t *const *row, int cols, int c) {
#pragma unroll
    for (int k = 0; k < NR; ++k) {
        const sycl::vec<uint32_t, 2> a = *(const sycl::vec<uint32_t, 2> *)(row[k] + 16 * c);
        const sycl::vec<uint32_t, 2> b = *(const sycl::vec<uint32_t, 2> *)(row[k] + 16 * c + 8);
        q.w[k][0] = a[0]; q.w[k][1] = a[1]; q.w[k][2] = b[0]; q.w[k][3] = b[1];
        std::memcpy(&q.dd[k], row[k] + cols / 2 + 2 * c, 2);
    }
}
// chunk c's sums of NR rows x MB lane-order inputs, added to acc (s per chunk from 0, i ascending, as decode32 + mac)
template <int NR, int MB> inline void nv4_chunk(const Nv4Rows<NR> &q, const float *const *xv, int c, float (&acc)[NR][MB]) {
    float s[NR][MB];
#pragma unroll
    for (int k = 0; k < NR; ++k)
#pragma unroll
        for (int m = 0; m < MB; ++m) s[k][m] = 0.0f;
#pragma unroll
    for (int b = 0; b < 4; ++b) {
        float xs[MB][8];
#pragma unroll
        for (int m = 0; m < MB; ++m) {
            const float *p = xv[m] + (size_t)(c >> 4) * 512 + (size_t)(c & 15) * 4 + 128 * b; // lane order: q = 2b, 2b+1
            const sycl::float4 v0 = *(const sycl::float4 *)p, v1 = *(const sycl::float4 *)(p + 64);
            xs[m][0] = v0[0]; xs[m][1] = v0[1]; xs[m][2] = v0[2]; xs[m][3] = v0[3];
            xs[m][4] = v1[0]; xs[m][5] = v1[1]; xs[m][6] = v1[2]; xs[m][7] = v1[3];
        }
#pragma unroll
        for (int k = 0; k < NR; ++k) {
            float o[8];
            pl::NVFP4P::dec8(q.w[k], q.dd[k], b, o);
#pragma unroll
            for (int m = 0; m < MB; ++m)
#pragma unroll
                for (int i = 0; i < 8; ++i) s[k][m] = mac(s[k][m], o[i], xs[m][i]);
        }
    }
#pragma unroll
    for (int k = 0; k < NR; ++k)
#pragma unroll
        for (int m = 0; m < MB; ++m) acc[k][m] += s[k][m];
}
// MAXS: the step's tokens (a group's most slots); each group runs the body for its own slot count (the same for the
// whole work-group, so the branch does not diverge): 4-token steps average 1.6 slots per chosen expert
template <class Op, int MAXS, int NP> struct GroupedPairT {
    const uint8_t *A, *B; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *x; int ldx, xdiv;
    Op op;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        const int a = (int)it.get_group(0);
        if (a >= g.count[0]) return;
        auto sg = it.get_sub_group();
        const int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * NP;
        if (r0 >= rows) return;
        const int sa = g.off[a], na = g.off[a + 1] - sa;
        if constexpr (MAXS > 4) { // steps of 5-8 tokens: passes of up to 4 slots (the weights read again, from the cache)
            for (int o = 0; o < na; o += 4) {
                const int s0 = sa + o, cnt = sycl::min(4, na - o);
                if (cnt <= 1) body<1>(sg, a, r0, s0, cnt);
                else if (cnt == 2) body<2>(sg, a, r0, s0, cnt);
                else if (cnt == 3) body<3>(sg, a, r0, s0, cnt);
                else body<4>(sg, a, r0, s0, cnt);
            }
        } else {
            const int s0 = sa, cnt = na;
            if (cnt <= 1) body<1>(sg, a, r0, s0, cnt);
            else if (MAXS == 2 || cnt == 2) body<(2 < MAXS ? 2 : MAXS)>(sg, a, r0, s0, cnt);
            else if (MAXS == 3 || cnt == 3) body<(3 < MAXS ? 3 : MAXS)>(sg, a, r0, s0, cnt);
            else body<MAXS>(sg, a, r0, s0, cnt);
        }
    }
    template <int MB> void body(sycl::sub_group sg, int a, int r0, int s0, int cnt) const {
        const int lane = (int)sg.get_local_linear_id();
        const size_t eo = (size_t)g.exp[a] * estride;
        const uint8_t *row[2 * NP]; // gate rows r0.., then up rows r0.. (clamped: rows past the end never stored)
#pragma unroll
        for (int p = 0; p < NP; ++p) {
            const size_t ro = eo + (size_t)sycl::min(r0 + p, rows - 1) * rb;
            row[p] = A + ro; row[NP + p] = B + ro;
        }
        int sl[MB];
        const float *xv[MB];
#pragma unroll
        for (int m = 0; m < MB; ++m) {
            sl[m] = g.slots[s0 + sycl::min(m, cnt - 1)];
            xv[m] = x + (size_t)(sl[m] / xdiv) * ldx;
        }
        float pre[MB];
        if constexpr (requires { op.pre(0); })
#pragma unroll
            for (int m = 0; m < MB; ++m) pre[m] = op.pre(sl[m]);
        float acc[2 * NP][MB];
#pragma unroll
        for (int k = 0; k < 2 * NP; ++k)
#pragma unroll
            for (int m = 0; m < MB; ++m) acc[k][m] = 0.0f;
        const int nc = cols / 32;
        for (int c = lane; c < nc; c += SG) {
            Nv4Rows<2 * NP> q;
            nv4_load<2 * NP>(q, row, cols, c);
            nv4_chunk<2 * NP, MB>(q, xv, c, acc);
        }
#pragma unroll
        for (int p = 0; p < NP; ++p)
#pragma unroll
            for (int m = 0; m < MB; ++m) {
                const float va = sg_sum(sg, acc[p][m]), vb = sg_sum(sg, acc[NP + p][m]);
                if (m < cnt && r0 + p < rows) { // the same for the whole sub-group
                    if constexpr (requires { op.pre(0); }) op.post(sg, lane, sl[m], r0 + p, va, vb, pre[m]);
                    else if (lane == 0) op(sl[m], r0 + p, va, vb);
                }
            }
    }
};
template <int MAXS, int R> struct GroupedRowsT {
    const uint8_t *W; size_t rb, estride; int rows, cols;
    MoeGroups g;
    const float *x; int ldx;
    float *y; int ldy;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        const int a = (int)it.get_group(0);
        if (a >= g.count[0]) return;
        auto sg = it.get_sub_group();
        const int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        const int sa = g.off[a], na = g.off[a + 1] - sa;
        if constexpr (MAXS > 4) { // steps of 5-8 tokens: passes of up to 4 slots (the weights read again, from the cache)
            for (int o = 0; o < na; o += 4) {
                const int s0 = sa + o, cnt = sycl::min(4, na - o);
                if (cnt <= 1) body<1>(sg, a, r0, s0, cnt);
                else if (cnt == 2) body<2>(sg, a, r0, s0, cnt);
                else if (cnt == 3) body<3>(sg, a, r0, s0, cnt);
                else body<4>(sg, a, r0, s0, cnt);
            }
        } else {
            const int s0 = sa, cnt = na;
            if (cnt <= 1) body<1>(sg, a, r0, s0, cnt);
            else if (MAXS == 2 || cnt == 2) body<(2 < MAXS ? 2 : MAXS)>(sg, a, r0, s0, cnt);
            else if (MAXS == 3 || cnt == 3) body<(3 < MAXS ? 3 : MAXS)>(sg, a, r0, s0, cnt);
            else body<MAXS>(sg, a, r0, s0, cnt);
        }
    }
    template <int MB> void body(sycl::sub_group sg, int a, int r0, int s0, int cnt) const {
        const int lane = (int)sg.get_local_linear_id();
        const uint8_t *row[R];
#pragma unroll
        for (int k = 0; k < R; ++k) row[k] = W + (size_t)g.exp[a] * estride + (size_t)sycl::min(r0 + k, rows - 1) * rb;
        int sl[MB];
        const float *xv[MB];
#pragma unroll
        for (int m = 0; m < MB; ++m) {
            sl[m] = g.slots[s0 + sycl::min(m, cnt - 1)];
            xv[m] = x + (size_t)sl[m] * ldx;
        }
        float acc[R][MB];
#pragma unroll
        for (int k = 0; k < R; ++k)
#pragma unroll
            for (int m = 0; m < MB; ++m) acc[k][m] = 0.0f;
        const int nc = cols / 32;
        for (int c = lane; c < nc; c += SG) {
            Nv4Rows<R> q;
            nv4_load<R>(q, row, cols, c);
            nv4_chunk<R, MB>(q, xv, c, acc);
        }
#pragma unroll
        for (int k = 0; k < R; ++k)
#pragma unroll
            for (int m = 0; m < MB; ++m) {
                const float v = sg_sum(sg, acc[k][m]);
                if (m < cnt && lane == 0 && r0 + k < rows) y[(size_t)sl[m] * ldy + r0 + k] = v;
            }
    }
};
template <class Op> inline sycl::event grouped_pair_t(sycl::queue &q, const WView &a, const uint8_t *B, size_t estride, int rows,
                                                      MoeGroups g, int amax, const float *xl, int ldx, int xdiv, Op op, int MB,
                                                      int NP, int sgw = 1) {
    if (a.kind != K_NVFP4P) throw std::runtime_error("grouped_pair_t: NVFP4 only");
    const int cols = (int)a.t->ne[0], nsg = (rows + NP - 1) / NP, ngr = (nsg + sgw - 1) / sgw;
    const sycl::nd_range<2> nr(sycl::range<2>((size_t)amax, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
#define INK_GPT(MM, PP) \
    if (MB == MM && NP == PP) return q.parallel_for(nr, GroupedPairT<Op, MM, PP>{a.p, B, a.rb, estride, rows, cols, g, xl, ldx, xdiv, op, sgw});
    INK_GPT(2, 1) INK_GPT(2, 2) INK_GPT(3, 1) INK_GPT(3, 2) INK_GPT(4, 1) INK_GPT(4, 2)
#undef INK_GPT
    if (MB >= 5 && MB <= 8) { // passes of up to 4 slots
        if (NP == 1) return q.parallel_for(nr, GroupedPairT<Op, 8, 1>{a.p, B, a.rb, estride, rows, cols, g, xl, ldx, xdiv, op, sgw});
        if (NP == 2) return q.parallel_for(nr, GroupedPairT<Op, 8, 2>{a.p, B, a.rb, estride, rows, cols, g, xl, ldx, xdiv, op, sgw});
    }
    throw std::runtime_error("grouped_pair_t: 2-8 slots, 1-2 row pairs");
}
inline sycl::event grouped_rows_t(sycl::queue &q, const WView &w, MoeGroups g, int amax, const float *xl, int ldx, float *y, int ldy,
                                  int MB, int R, int sgw = 1) {
    if (w.kind != K_NVFP4P) throw std::runtime_error("grouped_rows_t: NVFP4 only");
    const int cols = (int)w.t->ne[0], rows = (int)w.t->ne[1], nsg = (rows + R - 1) / R, ngr = (nsg + sgw - 1) / sgw;
    const size_t estride = w.rb * (size_t)rows;
    const sycl::nd_range<2> nr(sycl::range<2>((size_t)amax, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
#define INK_GRT(MM, RR) \
    if (MB == MM && R == RR) return q.parallel_for(nr, GroupedRowsT<MM, RR>{w.p, w.rb, estride, rows, cols, g, xl, ldx, y, ldy, sgw});
    INK_GRT(2, 1) INK_GRT(2, 2) INK_GRT(2, 4) INK_GRT(3, 2) INK_GRT(3, 4) INK_GRT(4, 2) INK_GRT(4, 4)
#undef INK_GRT
    if (MB >= 5 && MB <= 8) { // passes of up to 4 slots
        if (R == 2) return q.parallel_for(nr, GroupedRowsT<8, 2>{w.p, w.rb, estride, rows, cols, g, xl, ldx, y, ldy, sgw});
        if (R == 4) return q.parallel_for(nr, GroupedRowsT<8, 4>{w.p, w.rb, estride, rows, cols, g, xl, ldx, y, ldy, sgw});
    }
    throw std::runtime_error("grouped_rows_t: 2-8 slots, 1-4 rows");
}

template <class Op> inline sycl::event grouped_pair_s(sycl::queue &q, const WView &a, const uint8_t *B, size_t estride, int rows,
                                                      MoeGroups g, int amax, const float *xl, int ldx, int xdiv, Op op, int MB,
                                                      int sgw = 1) {
    sycl::event e;
    const int cols = (int)a.t->ne[0], ngr = (rows + sgw - 1) / sgw;
    const sycl::nd_range<2> nr(sycl::range<2>((size_t)amax, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
    with_decoder(a, [&]<class D>() {
        switch (MB) {
        case 2: e = q.parallel_for(nr, GroupedPairS<D, Op, 2>{a.p, B, a.rb, estride, rows, cols, g, xl, ldx, xdiv, op, sgw}); break;
        case 3: e = q.parallel_for(nr, GroupedPairS<D, Op, 3>{a.p, B, a.rb, estride, rows, cols, g, xl, ldx, xdiv, op, sgw}); break;
        case 4: case 5: case 6: case 7: case 8: // 5-8: passes of 4
            e = q.parallel_for(nr, GroupedPairS<D, Op, 4>{a.p, B, a.rb, estride, rows, cols, g, xl, ldx, xdiv, op, sgw}); break;
        default: throw std::runtime_error("grouped_pair_s: 2 to 8 slots per expert");
        }
    });
    return e;
}
inline sycl::event grouped_rows_s(sycl::queue &q, const WView &w, MoeGroups g, int amax, const float *xl, int ldx, float *y, int ldy,
                                  int MB, int sgw = 1) {
    sycl::event e;
    const int cols = (int)w.t->ne[0], rows = (int)w.t->ne[1], ngr = (rows + sgw - 1) / sgw;
    const size_t estride = w.rb * (size_t)rows;
    const sycl::nd_range<2> nr(sycl::range<2>((size_t)amax, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
    with_decoder(w, [&]<class D>() {
        switch (MB) {
        case 2: e = q.parallel_for(nr, GroupedRowsS<D, 2>{w.p, w.rb, estride, rows, cols, g, xl, ldx, y, ldy, sgw}); break;
        case 3: e = q.parallel_for(nr, GroupedRowsS<D, 3>{w.p, w.rb, estride, rows, cols, g, xl, ldx, y, ldy, sgw}); break;
        case 4: case 5: case 6: case 7: case 8: // 5-8: passes of 4
            e = q.parallel_for(nr, GroupedRowsS<D, 4>{w.p, w.rb, estride, rows, cols, g, xl, ldx, y, ldy, sgw}); break;
        default: throw std::runtime_error("grouped_rows_s: 2 to 8 slots per expert");
        }
    });
    return e;
}

// token-parallel: (rows per sub-group, large register file)
#define INK_TSP_COMBOS(X) X(2, false) X(4, false) X(4, true) X(8, true)
#define INK_TSR_COMBOS(X) X(4, false) X(8, false) X(8, true) X(16, true)
#define INK_GR_COMBOS(X) X(2, 8, false) X(2, 16, false) X(4, 4, false) X(4, 8, false) X(4, 8, true) X(8, 4, true) X(8, 8, true)

template <class Op> inline sycl::event grouped_pair(sycl::queue &q, const WView &a, const uint8_t *B, size_t estride, int rows,
                                                    MoeGroups g, int amax, const float *x, int ldx, int xdiv, Op op, int sgw = 2,
                                                    GTune gt = {}) {
    sycl::event e;
    int cols = (int)a.t->ne[0];
    if (gt.ts) {
        if (a.kind != K_NVFP4P) throw std::runtime_error("grouped_pair: token-parallel kernels are NVFP4 only");
        bool done = false;
#define INK_TS_CASE(NG, BIG) \
        if (!done && gt.np == NG && gt.big == BIG) { \
            int nsg = (rows + NG - 1) / NG, ngr = (nsg + gt.sgw - 1) / gt.sgw; \
            sycl::nd_range<2> nr(sycl::range<2>((size_t)gt.tiles, (size_t)ngr * gt.sgw * SG), sycl::range<2>(1, (size_t)gt.sgw * SG)); \
            e = q.parallel_for(nr, SlotPairNV<Op, NG, BIG>{{}, a.p, B, a.rb, estride, rows, cols, g, x, ldx, xdiv, op, gt.sgw}); done = true; }
        INK_TSP_COMBOS(INK_TS_CASE)
#undef INK_TS_CASE
        if (!done) throw std::runtime_error("grouped_pair: no token-parallel kernel for this tuning");
        return e;
    }
    if (gt.np) {
        bool done = false;
        with_decoder(a, [&]<class D>() {
            if constexpr (std::is_same_v<D, pl::NVFP4P>) {
#define INK_GP_CASE(NP, MB, BIG) \
            if (!done && gt.np == NP && gt.mb == MB && gt.big == BIG) { e = launch_pair_p<D, Op, NP, MB, BIG>(q, a, B, estride, rows, g, amax, x, ldx, xdiv, op, gt.sgw); done = true; }
            INK_GP_COMBOS(INK_GP_CASE)
#undef INK_GP_CASE
            }
        });
        if (!done) throw std::runtime_error("grouped_pair: no kernel for this tuning (piecewise kernels: NVFP4 only)");
        return e;
    }
    with_decoder(a, [&]<class D>() {
        int ngr = (rows + sgw - 1) / sgw;
        sycl::nd_range<2> nr(sycl::range<2>((size_t)amax, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
        e = q.parallel_for(nr, GroupedPair<D, Op>{a.p, B, a.rb, estride, rows, cols, g, x, ldx, xdiv, op, sgw});
    });
    return e;
}
inline sycl::event grouped_rows(sycl::queue &q, const WView &w, MoeGroups g, int amax, const float *x, int ldx, float *y,
                                int ldy, int sgw = 2, GTune gt = {}) {
    sycl::event e;
    int cols = (int)w.t->ne[0], rows = (int)w.t->ne[1];
    size_t estride = w.rb * (size_t)rows;
    if (gt.ts) {
        if (w.kind != K_NVFP4P) throw std::runtime_error("grouped_rows: token-parallel kernels are NVFP4 only");
        bool done = false;
#define INK_TS_CASE(R, BIG) \
        if (!done && gt.np == R && gt.big == BIG) { \
            int nsg = (rows + R - 1) / R, ngr = (nsg + gt.sgw - 1) / gt.sgw; \
            sycl::nd_range<2> nr(sycl::range<2>((size_t)gt.tiles, (size_t)ngr * gt.sgw * SG), sycl::range<2>(1, (size_t)gt.sgw * SG)); \
            e = q.parallel_for(nr, SlotRowsNV<R, BIG>{{}, w.p, w.rb, estride, rows, cols, g, x, ldx, y, ldy, gt.sgw}); done = true; }
        INK_TSR_COMBOS(INK_TS_CASE)
#undef INK_TS_CASE
        if (!done) throw std::runtime_error("grouped_rows: no token-parallel kernel for this tuning");
        return e;
    }
    if (gt.np) {
        bool done = false;
        with_decoder(w, [&]<class D>() {
            if constexpr (std::is_same_v<D, pl::NVFP4P>) {
#define INK_GR_CASE(R, MB, BIG) \
            if (!done && gt.np == R && gt.mb == MB && gt.big == BIG) { e = launch_rows_p<D, R, MB, BIG>(q, w, g, amax, x, ldx, y, ldy, gt.sgw); done = true; }
            INK_GR_COMBOS(INK_GR_CASE)
#undef INK_GR_CASE
            }
        });
        if (!done) throw std::runtime_error("grouped_rows: no kernel for this tuning (piecewise kernels: NVFP4 only)");
        return e;
    }
    with_decoder(w, [&]<class D>() {
        constexpr int R = 2;
        int nsg = (rows + R - 1) / R, ngr = (nsg + sgw - 1) / sgw;
        sycl::nd_range<2> nr(sycl::range<2>((size_t)amax, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
        e = q.parallel_for(nr, GroupedRows<D, R>{w.p, w.rb, estride, rows, cols, g, x, ldx, y, ldy, sgw});
    });
    return e;
}

} // namespace ink
