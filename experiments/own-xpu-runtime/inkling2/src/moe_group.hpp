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
    int32_t *ntiles = nullptr;                                    // [1] tiles T
    int32_t *tile_exp = nullptr, *tile_s0 = nullptr, *tile_n = nullptr; // [ne + K / 16] expert, first slot index, slots
    void alloc(Device &d, int ne, int kmax) {
        count = d.alloc<int32_t>(1); exp = d.alloc<int32_t>(ne); off = d.alloc<int32_t>(ne + 1); slots = d.alloc<int32_t>(kmax);
        int tmax = max_tiles(ne, kmax);
        ntiles = d.alloc<int32_t>(1); tile_exp = d.alloc<int32_t>(tmax); tile_s0 = d.alloc<int32_t>(tmax); tile_n = d.alloc<int32_t>(tmax);
    }
    static int max_tiles(int ne, int k) { return ne + k / MOE_TS; }
};

// one work-group, one thread per expert (ne <= 128)
inline sycl::event moe_group(sycl::queue &q, const int32_t *ids, int K, int ne, MoeGroups g) {
    constexpr int GW = 128;
    if (ne > GW) throw std::runtime_error("moe_group: more than 128 experts");
    return q.parallel_for(sycl::nd_range<1>(sycl::range<1>(GW), sycl::range<1>(GW)), [=](sycl::nd_item<1> it) {
        int e = (int)it.get_local_id(0);
        auto grp = it.get_group();
        int cnt = 0;
        if (e < ne)
            for (int s = 0; s < K; ++s) cnt += ids[s] == e;
        int start = sycl::exclusive_scan_over_group(grp, cnt, sycl::plus<int>());
        int act = cnt > 0 ? 1 : 0;
        int a = sycl::exclusive_scan_over_group(grp, act, sycl::plus<int>());
        int na = sycl::reduce_over_group(grp, act, sycl::plus<int>());
        if (act) { g.exp[a] = e; g.off[a] = start; }
        if (e == 0) { g.count[0] = na; g.off[na] = K; }
        if (cnt) {
            int j = start;
            for (int s = 0; s < K; ++s)
                if (ids[s] == e) g.slots[j++] = s;
        }
        // tiles of up to 16 slots of one expert
        int nt = (cnt + MOE_TS - 1) / MOE_TS;
        int t0 = sycl::exclusive_scan_over_group(grp, nt, sycl::plus<int>());
        int ntt = sycl::reduce_over_group(grp, nt, sycl::plus<int>());
        for (int t = 0; t < nt; ++t) {
            g.tile_exp[t0 + t] = e;
            g.tile_s0[t0 + t] = start + t * MOE_TS;
            g.tile_n[t0 + t] = sycl::min(MOE_TS, cnt - t * MOE_TS);
        }
        if (e == 0) g.ntiles[0] = ntt;
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
                        for (int i = 0; i < 32; ++i) s += o[j][i] * xs[i];
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
                        for (int i = 0; i < 32; ++i) s += o[j][i] * xs[i];
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
                            for (int i = 0; i < 8; ++i) s[j][m] += o[j][i] * xs[i];
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
                            for (int i = 0; i < 8; ++i) s[j][m] += o[j][i] * xs[i];
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
                for (int j = 0; j < NR; ++j) s[j] += sycl::select_from_group(sg, lo[j], i) * xs[i];
            for (int i = 0; i < 16; ++i)
                for (int j = 0; j < NR; ++j) s[j] += sycl::select_from_group(sg, hi[j], i) * xs[16 + i];
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
                        s[j] += sycl::select_from_group(sg, ((i >> 3) & 1) ? hi[j] : lo[j], 8 * (i >> 4) + (i & 7)) * xs[i];
            } else {
                for (int j = 0; j < NR; ++j)
                    for (int i = 0; i < 32; ++i)
                        s[j] += sycl::select_from_group(sg, ((i >> 3) & 1) ? hi[j] : lo[j], 8 * (i >> 4) + (i & 7)) * xs[i];
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
