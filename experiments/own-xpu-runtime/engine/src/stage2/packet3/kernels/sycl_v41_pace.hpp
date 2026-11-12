// pace-1 (2026-11-11, OWN_MT_PACE; /home/steve/dsv41-work/attn/pace/README.txt): the pace cards' attention rows at the
// guessing checks (2-6 tokens). The cards with two head groups (16 heads) run q_b (8,192 x 1,280) and output-a (2,048 x
// 4,096 in two groups of 1,024) on twice the rows of the other cards, which wait for them at the output-a exchange.
// These forms run the same sums in persistent, pipelined launches: one resident wave of sub-groups (the card's compute
// units x 8 at 128 registers, x 4 at 256), each walking its row blocks in segments of SW quant words (Q8_0) or SB
// blocks (Q6_K) and loading the next segment (or the next row block's first) into a second register set before it
// multiplies the current one. The attention mix's finish (TokRows<HcFinishRows>, q_b below 4 tokens) gets a work-group
// of its own at the front of the launch, so it never delays a share of the rows.
//
// Bit for bit: every (row, token) output is WsQ8 / WsQ6's rowt sum: the same word_group / block decode on the same
// values in the same order, the same ws_reduce_store (sg_tree32); only when the weights are loaded and which sub-group
// runs a row block change. bench_pace.cpp (attn/pace): memcmp of the whole output buffer (stray writes included) and of
// the rider's pre / post / comb against the production launch (dense_m's ws_rows pick), every candidate form at M = 2-6:
// 635 compares, 0 differ (plus the patch-header check of pace_rows itself).
//
// Card 3 (B70, 256 compute units), real GGUF rows (blk.2 Q8_0, blk.30 Q6_K), the module's private arrays in global
// memory as in the engine, us per launch back to back over 205-256 MB of weight copies (production -> this):
//            q_b Q8_0        q_b Q6_K        output-a Q8_0
//   M = 2    25.4 -> 21.4    (kept, 22.1)    17.4 -> 16.5
//   M = 3    29.2 -> 21.9    (kept, 24.2)    (kept, 16.7)
//   M = 4    28.4 -> 20.9    26.8 -> 22.9    17.7 -> 16.8
//   M = 5    32.6 -> 21.6    28.8 -> 25.1    19.4 -> 17.1
//   M = 6    34.4 -> 23.0    31.2 -> 27.2    19.7 -> 17.7
// Q6_K output-a keeps its forms (no segment form within 1 %). Weight floor at ~600 GB/s: 18.5 us (q_b Q8_0).
#pragma once
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>
namespace ops41sycl {

// OWN_MT_PACE: the check sizes M (bit M - 2; default 0x1f since tp103, 0 = off); OWN_MT_PACE_ROLES: 1 q_b Q8_0, 2 q_b Q6_K, 4 output-a
// Q8_0 (default 7: these); pace-2 (every card, opt-in by role): 8 the q_a + kv pair, 16 output-b, 32 shared down, 64
// the shared expert's gate + up with the router (127: all)
inline unsigned g_pace_mask = 0x1f, g_pace_roles = 7; // pace-1 on at every check size since tp103 (tg102: -0.27 to -0.58 ms at 4-6 tokens); OWN_MT_PACE=0: off
inline bool pace_on(unsigned mt) { return mt >= 2 && mt <= 6 && (g_pace_mask >> (mt - 2) & 1u); }

// Q8_0 (WsQ8<C>'s layout): T tokens x R rows per position, rowt LOOP 0's products (XW words per word_group) in
// segments of SW quant words; the R rows' chunk scales come with segment 0 and are kept for the row block.
template <unsigned C, unsigned T, unsigned R, unsigned XW, unsigned SW> struct PaceSQ8 {
    using WK = WsQ8<C>;
    static constexpr unsigned NQ = C / 4, ND = (C + 31) / 32, NS = NQ / SW, t = T, r = R;
    static constexpr bool odd = NS % 2 != 0;
    static_assert(NQ % SW == 0 && SW % XW == 0 && 32 % (4 * XW) == 0);
    struct Seg {
        uint32_t q[R][SW];
        float dv[R][ND];
    };
    WK k;
    const uint8_t *w;
    const float *x;
    size_t xs;
    float *y;
    size_t ys;
    unsigned mt, ng;
    unsigned n() const { return (k.rows + R - 1) / R * ng; }
    template <unsigned S> [[gnu::always_inline]] inline void fetch(sycl::sub_group sg, unsigned lane, unsigned p, Seg &g) const {
        const unsigned r0 = p / ng * R;
#pragma unroll
        for (unsigned j = 0; j < R; ++j) {
            const uint8_t *rowp = w + (size_t)(r0 + j < k.rows ? r0 + j : r0) * WK::RB;
            if constexpr (S == 0) {
                const uint16_t *dp = reinterpret_cast<const uint16_t *>(rowp + (size_t)C * 32);
#pragma unroll
                for (unsigned kk = 0; kk < ND; ++kk) g.dv[j][kk] = 32 * kk + lane < C ? iq3::half(dp[32 * kk + lane]) : 0.0f;
            }
#pragma unroll
            for (unsigned m = 0; m < SW; ++m)
                g.q[j][m] = sg_bload(sg, reinterpret_cast<const uint32_t *>(rowp) + (size_t)(S * SW + m) * 32);
        }
    }
    // segment S of position p in buffer (S + F) % 2 (F: the position's segment 0 sits in b1 when NS is odd and the
    // position is the sub-group's 2nd, 4th, ...); the next segment (or the next position's segment 0) into the other
    template <unsigned S, bool F>
    [[gnu::always_inline]] inline void steps(sycl::sub_group sg, unsigned lane, unsigned p, unsigned nsg, unsigned n, Seg &b0,
                                             Seg &b1, const float (&dvr)[R][ND], const float *xr, float (&sum)[R * T]) const {
        Seg &cur = (S % 2 == 0) != F ? b0 : b1;
        Seg &nxt = (S % 2 == 0) != F ? b1 : b0;
        if constexpr (S + 1 < NS) fetch<S + 1>(sg, lane, p, nxt);
        else if (p + nsg < n) fetch<0>(sg, lane, p + nsg, nxt);
#pragma unroll
        for (unsigned m0 = 0; m0 < SW; m0 += XW) {
            const unsigned c0 = (S * SW + m0) * 4;
            uint32_t qq[R][XW];
            float ds[R];
#pragma unroll
            for (unsigned j = 0; j < R; ++j) {
                ds[j] = dvr[j][c0 / 32];
#pragma unroll
                for (unsigned mm = 0; mm < XW; ++mm) qq[j][mm] = cur.q[j][m0 + mm];
            }
            WK::template word_group<R, T, XW>(sg, qq, ds, c0 % 32, xr + (size_t)(S * SW + m0) * 128, xs, sum);
        }
        if constexpr (S + 1 < NS) steps<S + 1, F>(sg, lane, p, nsg, n, b0, b1, dvr, xr, sum);
    }
    template <bool F>
    [[gnu::always_inline]] inline void pos(sycl::sub_group sg, unsigned lane, unsigned p, unsigned nsg, unsigned n, Seg &b0,
                                           Seg &b1) const {
        const unsigned r0 = p / ng * R, t0 = (p % ng) * T;
        const float *xb = x + t0 * xs;
        const float *xr = k.xn ? xb + (size_t)(r0 / k.xn) * C * 32 : xb;
        const Seg &s0 = F ? b1 : b0;
        float dvr[R][ND];
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
#pragma unroll
            for (unsigned kk = 0; kk < ND; ++kk) dvr[j][kk] = s0.dv[j][kk];
        float sum[R * T];
#pragma unroll
        for (unsigned i = 0; i < R * T; ++i) sum[i] = 0;
        steps<0, F>(sg, lane, p, nsg, n, b0, b1, dvr, xr, sum);
        ws_reduce_store<R, T>(sg, lane, sum, r0, k.rows, y + t0 * ys, ys, mt - t0);
    }
    [[gnu::always_inline]] inline void go(sycl::sub_group sg, unsigned lane, unsigned s0, unsigned nsg) const {
        const unsigned n = this->n();
        if (s0 >= n) return;
        Seg b0, b1;
        fetch<0>(sg, lane, s0, b0);
        for (unsigned p = s0; p < n; p += 2 * nsg) {
            pos<false>(sg, lane, p, nsg, n, b0, b1);
            if (p + nsg >= n) break;
            pos<odd>(sg, lane, p + nsg, nsg, n, b0, b1);
        }
    }
};
// Q6_K: segments of SB blocks (WsQ6's per-block decode and products, blocks ascending); the scales with segment 0
template <unsigned NB, unsigned T, unsigned R, unsigned SB> struct PaceSQ6 {
    using WK = WsQ6<NB>;
    static constexpr unsigned NSB = NB * 16, NSR = (NSB + 31) / 32, NS = NB / SB, t = T, r = R;
    static constexpr bool odd = NS % 2 != 0;
    static_assert(NB % SB == 0);
    struct Seg {
        uint32_t qa[R][SB], qb[R][SB];
        float dbs[R][NSR];
    };
    WK k;
    const uint8_t *w;
    const float *x;
    size_t xs;
    float *y;
    size_t ys;
    unsigned mt, ng;
    unsigned n() const { return (k.rows + R - 1) / R * ng; }
    template <unsigned S> [[gnu::always_inline]] inline void fetch(sycl::sub_group sg, unsigned lane, unsigned p, Seg &g) const {
        const unsigned r0 = p / ng * R;
#pragma unroll
        for (unsigned j = 0; j < R; ++j) {
            const uint8_t *row = w + (size_t)(r0 + j < k.rows ? r0 + j : r0) * WK::RB;
            if constexpr (S == 0) {
                const int8_t *scl = reinterpret_cast<const int8_t *>(row + (size_t)NB * 192);
                const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 208);
#pragma unroll
                for (unsigned kk = 0; kk < NSR; ++kk) {
                    const unsigned si = 32 * kk + lane < NSB ? 32 * kk + lane : NSB - 1;
                    g.dbs[j][kk] = iq3::half(dp[si >> 4]) * float(int(scl[si]));
                }
            }
            const uint32_t *ql = reinterpret_cast<const uint32_t *>(row);
            const uint16_t *qh = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 128);
#pragma unroll
            for (unsigned m = 0; m < SB; ++m) {
                g.qa[j][m] = sg_bload(sg, ql + (size_t)(S * SB + m) * 32);
                g.qb[j][m] = qh[(size_t)(S * SB + m) * 32 + lane];
            }
        }
    }
    // (buffer parity as PaceSQ8's)
    template <unsigned S, bool F>
    [[gnu::always_inline]] inline void steps(sycl::sub_group sg, unsigned lane, unsigned p, unsigned nsg, unsigned n, Seg &b0,
                                             Seg &b1, const float (&dbs)[R][NSR], const float *xr, float (&sum)[R * T]) const {
        Seg &cur = (S % 2 == 0) != F ? b0 : b1;
        Seg &nxt = (S % 2 == 0) != F ? b1 : b0;
        if constexpr (S + 1 < NS) fetch<S + 1>(sg, lane, p, nxt);
        else if (p + nsg < n) fetch<0>(sg, lane, p + nsg, nxt);
#pragma unroll
        for (unsigned m = 0; m < SB; ++m) {
            const unsigned b = S * SB + m;
            float v[R][8];
#pragma unroll
            for (unsigned c = 0; c < 8; ++c) {
                const unsigned h = c >> 2, cc = c & 3u;
                const unsigned si = b * 16 + 2 * c;
#pragma unroll
                for (unsigned j = 0; j < R; ++j) {
                    const unsigned low = (cur.qa[j][m] >> (8 * (2 * h + (cc & 1u)) + 4 * (cc >> 1))) & 15u;
                    const unsigned high = (cur.qb[j][m] >> (8 * h + 2 * cc)) & 3u;
                    const float d0 = sycl::select_from_group(sg, dbs[j][si / 32], si % 32);
                    const float d1 = sycl::select_from_group(sg, dbs[j][si / 32], si % 32 + 1);
                    v[j][c] = (lane < 16 ? d0 : d1) * float(int(low | (high << 4)) - 32);
                }
            }
#pragma unroll
            for (unsigned tt = 0; tt < T; ++tt) {
                const auto xv = sg_bloadN<8>(sg, xr + tt * xs + (size_t)b * 256);
#pragma unroll
                for (unsigned c = 0; c < 8; ++c)
#pragma unroll
                    for (unsigned j = 0; j < R; ++j) sum[j * T + tt] = sum[j * T + tt] + v[j][c] * xv[c];
            }
        }
        if constexpr (S + 1 < NS) steps<S + 1, F>(sg, lane, p, nsg, n, b0, b1, dbs, xr, sum);
    }
    template <bool F>
    [[gnu::always_inline]] inline void pos(sycl::sub_group sg, unsigned lane, unsigned p, unsigned nsg, unsigned n, Seg &b0,
                                           Seg &b1) const {
        const unsigned r0 = p / ng * R, t0 = (p % ng) * T;
        const float *xb = x + t0 * xs;
        const float *xr = k.xn ? xb + (size_t)(r0 / k.xn) * NB * 256 : xb;
        const Seg &s0 = F ? b1 : b0;
        float dbs[R][NSR];
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
#pragma unroll
            for (unsigned kk = 0; kk < NSR; ++kk) dbs[j][kk] = s0.dbs[j][kk];
        float sum[R * T];
#pragma unroll
        for (unsigned i = 0; i < R * T; ++i) sum[i] = 0;
        steps<0, F>(sg, lane, p, nsg, n, b0, b1, dbs, xr, sum);
        ws_reduce_store<R, T>(sg, lane, sum, r0, k.rows, y + t0 * ys, ys, mt - t0);
    }
    [[gnu::always_inline]] inline void go(sycl::sub_group sg, unsigned lane, unsigned s0, unsigned nsg) const {
        const unsigned n = this->n();
        if (s0 >= n) return;
        Seg b0, b1;
        fetch<0>(sg, lane, s0, b0);
        for (unsigned p = s0; p < n; p += 2 * nsg) {
            pos<false>(sg, lane, p, nsg, n, b0, b1);
            if (p + nsg >= n) break;
            pos<odd>(sg, lane, p + nsg, nsg, n, b0, b1);
        }
    }
};
// the launch: P::go runs sub-group s's positions s, s + nsg, ... With a rider, work-group 0 runs it (sub-group s <
// rd.n(): rider position s, as RowsPair<RD, D> puts the rider first) and the pace positions start at work-group 1.
template <typename RD, typename P, unsigned GRF> struct PaceK {
    RD rd;
    P k;
    unsigned nsg;
    void operator()(sycl::nd_item<1> it) const {
        sycl::sub_group sg = it.get_sub_group();
        unsigned s = packed_row_id(it);
        const unsigned lane = sg.get_local_linear_id();
        if constexpr (!std::is_same_v<RD, NoRows>) {
            if (s < 16) {
                if (s < rd.n()) rd.row(sg, lane, s);
                return;
            }
            s -= 16;
        }
        k.go(sg, lane, s, nsg);
    }
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>,
                                                           sycl::ext::oneapi::experimental::sub_group_size<32>};
    }
};
// ---- pace-2 (2026-11-11, OWN_MT_PACE_ROLES 8 / 16 / 32 / 64; /home/steve/dsv41-work/attn/pace2/README.txt): the
// check rows every card runs, at 2-6 tokens, in the same persistent pipelined launches: the q_a + kv pair (one launch,
// the mix's dot rows riding at 2-3 tokens), output-b and shared down (the mix's finish riding at 4-6), the shared
// expert's gate + up (with the router's top-k, route_shared_m). Differences from the forms above:
//   * NM matrices per launch (2: the pair, gate + up), positions concatenated, matrix 0's first (as RowsPair);
//   * the chunk / block scales are prefetched as raw bits and converted when the row block starts (the prefetch
//     never waits on a load; iq3::half of the same bits, the same products), Q5_K too (WsQ5's fac / off);
//   * the rider on ceil(rd.n() / 16) work-groups of its own (the pair's dot rows: 200 rows per token);
//   * spread (SP): with fewer positions than sub-groups, every work-group gets a share.
// Every (row, token) output is WsQ8 / WsQ6 / WsQ5's rowt sum, bit for bit (bench_pace2: memcmp of every output, the
// rider's and the router's against the production launch).
// one matrix of a launch: rows, output, positions (= ceil(rows / R) * ng)
struct PaceMat {
    const uint8_t *w;
    float *y;
    size_t ys;
    unsigned rows, np;
};
// position p -> matrix (0 / 1) and its local position
template <unsigned NM> struct PaceAt {
    unsigned mi, pl;
    [[gnu::always_inline]] inline PaceAt(const PaceMat (&m)[NM], unsigned p) {
        if constexpr (NM == 1) mi = 0, pl = p;
        else mi = p < m[0].np ? 0u : 1u, pl = p < m[0].np ? p : p - m[0].np;
    }
};
template <unsigned NM> [[gnu::always_inline]] inline const uint8_t *pm_w(const PaceMat (&m)[NM], unsigned mi) {
    if constexpr (NM == 1) return m[0].w;
    else return mi ? m[1].w : m[0].w;
}
template <unsigned NM> [[gnu::always_inline]] inline unsigned pm_rows(const PaceMat (&m)[NM], unsigned mi) {
    if constexpr (NM == 1) return m[0].rows;
    else return mi ? m[1].rows : m[0].rows;
}
template <unsigned NM> [[gnu::always_inline]] inline float *pm_y(const PaceMat (&m)[NM], unsigned mi) {
    if constexpr (NM == 1) return m[0].y;
    else return mi ? m[1].y : m[0].y;
}
template <unsigned NM> [[gnu::always_inline]] inline size_t pm_ys(const PaceMat (&m)[NM], unsigned mi) {
    if constexpr (NM == 1) return m[0].ys;
    else return mi ? m[1].ys : m[0].ys;
}

// the segment loop shared by the formats: F::NS segments per row block, buffers b0 / b1 alternating (F: this
// position's segment 0 sits in b1), the next segment or the next position's segment 0 fetched before the current runs
#define PACE_GO_BODY                                                                                                    \
    [[gnu::always_inline]] inline void go(sycl::sub_group sg, unsigned lane, unsigned s0, unsigned nsg) const {        \
        const unsigned n = this->n();                                                                                \
        if (s0 >= n) return;                                                                                         \
        Seg b0, b1;                                                                                                  \
        fetch<0>(sg, lane, s0, b0);                                                                                  \
        for (unsigned p = s0; p < n; p += 2 * nsg) {                                                                 \
            pos<false>(sg, lane, p, nsg, n, b0, b1);                                                                 \
            if (p + nsg >= n) break;                                                                                 \
            pos<odd>(sg, lane, p + nsg, nsg, n, b0, b1);                                                             \
        }                                                                                                            \
    }

// Q8_0 (WsQ8<C>): T tokens x R rows, word_group of XW words, segments of SW quant words; chunk scales raw with seg 0
template <unsigned C, unsigned T, unsigned R, unsigned XW, unsigned SW, unsigned NM = 1> struct PaceSQ8N {
    using WK = WsQ8<C>;
    static constexpr unsigned NQ = C / 4, ND = (C + 31) / 32, NS = NQ / SW, t = T, r = R;
    static constexpr bool odd = NS % 2 != 0;
    static_assert(NQ % SW == 0 && SW % XW == 0 && 32 % (4 * XW) == 0);
    struct Seg {
        uint32_t q[R][SW];
        uint32_t dr[R][ND]; // raw half bits (0: lanes past C)
    };
    PaceMat m[NM];
    const float *x;
    size_t xs;
    unsigned xn, mt, ng;
    unsigned n() const {
        unsigned s = 0;
#pragma unroll
        for (unsigned i = 0; i < NM; ++i) s += m[i].np;
        return s;
    }
    template <unsigned S> [[gnu::always_inline]] inline void fetch(sycl::sub_group sg, unsigned lane, unsigned p, Seg &g) const {
        const PaceAt<NM> a(m, p);
        const unsigned r0 = a.pl / ng * R, rows = pm_rows(m, a.mi);
        const uint8_t *w = pm_w(m, a.mi);
#pragma unroll
        for (unsigned j = 0; j < R; ++j) {
            const uint8_t *rowp = w + (size_t)(r0 + j < rows ? r0 + j : r0) * WK::RB;
            if constexpr (S == 0) {
                const uint16_t *dp = reinterpret_cast<const uint16_t *>(rowp + (size_t)C * 32);
#pragma unroll
                for (unsigned kk = 0; kk < ND; ++kk) g.dr[j][kk] = 32 * kk + lane < C ? dp[32 * kk + lane] : 0u;
            }
#pragma unroll
            for (unsigned mm = 0; mm < SW; ++mm)
                g.q[j][mm] = sg_bload(sg, reinterpret_cast<const uint32_t *>(rowp) + (size_t)(S * SW + mm) * 32);
        }
    }
    template <unsigned S, bool F>
    [[gnu::always_inline]] inline void steps(sycl::sub_group sg, unsigned lane, unsigned p, unsigned nsg, unsigned n, Seg &b0,
                                             Seg &b1, const float (&dvr)[R][ND], const float *xr, float (&sum)[R * T]) const {
        Seg &cur = (S % 2 == 0) != F ? b0 : b1;
        Seg &nxt = (S % 2 == 0) != F ? b1 : b0;
        if constexpr (S + 1 < NS) fetch<S + 1>(sg, lane, p, nxt);
        else if (p + nsg < n) fetch<0>(sg, lane, p + nsg, nxt);
#pragma unroll
        for (unsigned m0 = 0; m0 < SW; m0 += XW) {
            const unsigned c0 = (S * SW + m0) * 4;
            uint32_t qq[R][XW];
            float ds[R];
#pragma unroll
            for (unsigned j = 0; j < R; ++j) {
                ds[j] = dvr[j][c0 / 32];
#pragma unroll
                for (unsigned mm = 0; mm < XW; ++mm) qq[j][mm] = cur.q[j][m0 + mm];
            }
            WK::template word_group<R, T, XW>(sg, qq, ds, c0 % 32, xr + (size_t)(S * SW + m0) * 128, xs, sum);
        }
        if constexpr (S + 1 < NS) steps<S + 1, F>(sg, lane, p, nsg, n, b0, b1, dvr, xr, sum);
    }
    template <bool F>
    [[gnu::always_inline]] inline void pos(sycl::sub_group sg, unsigned lane, unsigned p, unsigned nsg, unsigned n, Seg &b0,
                                           Seg &b1) const {
        const PaceAt<NM> a(m, p);
        const unsigned r0 = a.pl / ng * R, t0 = (a.pl % ng) * T;
        const float *xb = x + t0 * xs;
        const float *xr = xn ? xb + (size_t)(r0 / xn) * C * 32 : xb;
        const Seg &s0 = F ? b1 : b0;
        float dvr[R][ND];
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
#pragma unroll
            for (unsigned kk = 0; kk < ND; ++kk) dvr[j][kk] = 32 * kk + lane < C ? iq3::half((uint16_t)s0.dr[j][kk]) : 0.0f;
        float sum[R * T];
#pragma unroll
        for (unsigned i = 0; i < R * T; ++i) sum[i] = 0;
        steps<0, F>(sg, lane, p, nsg, n, b0, b1, dvr, xr, sum);
        const size_t ys = pm_ys(m, a.mi);
        ws_reduce_store<R, T>(sg, lane, sum, r0, pm_rows(m, a.mi), pm_y(m, a.mi) + t0 * ys, ys, mt - t0);
    }
    PACE_GO_BODY
};

// Q6_K (WsQ6<NB>): segments of SB blocks; the 6-bit scale terms d * scale raw with segment 0 (d bits | scale << 16)
template <unsigned NB, unsigned T, unsigned R, unsigned SB, unsigned NM = 1> struct PaceSQ6N {
    using WK = WsQ6<NB>;
    static constexpr unsigned NSB = NB * 16, NSR = (NSB + 31) / 32, NS = NB / SB, t = T, r = R;
    static constexpr bool odd = NS % 2 != 0;
    static_assert(NB % SB == 0);
    struct Seg {
        uint32_t qa[R][SB], qb[R][SB];
        uint32_t sr[R][NSR];
    };
    PaceMat m[NM];
    const float *x;
    size_t xs;
    unsigned xn, mt, ng;
    unsigned n() const {
        unsigned s = 0;
#pragma unroll
        for (unsigned i = 0; i < NM; ++i) s += m[i].np;
        return s;
    }
    template <unsigned S> [[gnu::always_inline]] inline void fetch(sycl::sub_group sg, unsigned lane, unsigned p, Seg &g) const {
        const PaceAt<NM> a(m, p);
        const unsigned r0 = a.pl / ng * R, rows = pm_rows(m, a.mi);
        const uint8_t *w = pm_w(m, a.mi);
#pragma unroll
        for (unsigned j = 0; j < R; ++j) {
            const uint8_t *row = w + (size_t)(r0 + j < rows ? r0 + j : r0) * WK::RB;
            if constexpr (S == 0) {
                const uint8_t *scl = row + (size_t)NB * 192;
                const uint16_t *dp = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 208);
#pragma unroll
                for (unsigned kk = 0; kk < NSR; ++kk) {
                    const unsigned si = 32 * kk + lane < NSB ? 32 * kk + lane : NSB - 1;
                    g.sr[j][kk] = (uint32_t)dp[si >> 4] | (uint32_t)scl[si] << 16;
                }
            }
            const uint32_t *ql = reinterpret_cast<const uint32_t *>(row);
            const uint16_t *qh = reinterpret_cast<const uint16_t *>(row + (size_t)NB * 128);
#pragma unroll
            for (unsigned mm = 0; mm < SB; ++mm) {
                g.qa[j][mm] = sg_bload(sg, ql + (size_t)(S * SB + mm) * 32);
                g.qb[j][mm] = qh[(size_t)(S * SB + mm) * 32 + lane];
            }
        }
    }
    template <unsigned S, bool F>
    [[gnu::always_inline]] inline void steps(sycl::sub_group sg, unsigned lane, unsigned p, unsigned nsg, unsigned n, Seg &b0,
                                             Seg &b1, const float (&dbs)[R][NSR], const float *xr, float (&sum)[R * T]) const {
        Seg &cur = (S % 2 == 0) != F ? b0 : b1;
        Seg &nxt = (S % 2 == 0) != F ? b1 : b0;
        if constexpr (S + 1 < NS) fetch<S + 1>(sg, lane, p, nxt);
        else if (p + nsg < n) fetch<0>(sg, lane, p + nsg, nxt);
#pragma unroll
        for (unsigned mm = 0; mm < SB; ++mm) {
            const unsigned b = S * SB + mm;
            float v[R][8];
#pragma unroll
            for (unsigned c = 0; c < 8; ++c) {
                const unsigned h = c >> 2, cc = c & 3u;
                const unsigned si = b * 16 + 2 * c;
#pragma unroll
                for (unsigned j = 0; j < R; ++j) {
                    const unsigned low = (cur.qa[j][mm] >> (8 * (2 * h + (cc & 1u)) + 4 * (cc >> 1))) & 15u;
                    const unsigned high = (cur.qb[j][mm] >> (8 * h + 2 * cc)) & 3u;
                    const float d0 = sycl::select_from_group(sg, dbs[j][si / 32], si % 32);
                    const float d1 = sycl::select_from_group(sg, dbs[j][si / 32], si % 32 + 1);
                    v[j][c] = (lane < 16 ? d0 : d1) * float(int(low | (high << 4)) - 32);
                }
            }
#pragma unroll
            for (unsigned tt = 0; tt < T; ++tt) {
                const auto xv = sg_bloadN<8>(sg, xr + tt * xs + (size_t)b * 256);
#pragma unroll
                for (unsigned c = 0; c < 8; ++c)
#pragma unroll
                    for (unsigned j = 0; j < R; ++j) sum[j * T + tt] = sum[j * T + tt] + v[j][c] * xv[c];
            }
        }
        if constexpr (S + 1 < NS) steps<S + 1, F>(sg, lane, p, nsg, n, b0, b1, dbs, xr, sum);
    }
    template <bool F>
    [[gnu::always_inline]] inline void pos(sycl::sub_group sg, unsigned lane, unsigned p, unsigned nsg, unsigned n, Seg &b0,
                                           Seg &b1) const {
        const PaceAt<NM> a(m, p);
        const unsigned r0 = a.pl / ng * R, t0 = (a.pl % ng) * T;
        const float *xb = x + t0 * xs;
        const float *xr = xn ? xb + (size_t)(r0 / xn) * NB * 256 : xb;
        const Seg &s0 = F ? b1 : b0;
        float dbs[R][NSR];
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
#pragma unroll
            for (unsigned kk = 0; kk < NSR; ++kk) {
                const uint32_t v = s0.sr[j][kk];
                dbs[j][kk] = iq3::half((uint16_t)(v & 0xffffu)) * float(int(int8_t(uint8_t(v >> 16))));
            }
        float sum[R * T];
#pragma unroll
        for (unsigned i = 0; i < R * T; ++i) sum[i] = 0;
        steps<0, F>(sg, lane, p, nsg, n, b0, b1, dbs, xr, sum);
        const size_t ys = pm_ys(m, a.mi);
        ws_reduce_store<R, T>(sg, lane, sum, r0, pm_rows(m, a.mi), pm_y(m, a.mi) + t0 * ys, ys, mt - t0);
    }
    PACE_GO_BODY
};

// Q5_K (WsQ5<NB>): segments of SB blocks; each 8-block group's d / dmin bits and its three scale bytes raw with seg 0
template <unsigned NB, unsigned T, unsigned R, unsigned SB, unsigned NM = 1> struct PaceSQ5N {
    using WK = WsQ5<NB>;
    static constexpr unsigned NG = NB * 8, NGR = (NG + 31) / 32, NS = NB / SB, t = T, r = R;
    static constexpr bool odd = NS % 2 != 0;
    static_assert(NB % SB == 0);
    struct Seg {
        uint32_t qa[R][SB], qb[R][SB];
        uint32_t dd[R][NGR], su[R][NGR]; // d | dmin << 16; u0 | u1 << 8 | u2 << 16
    };
    PaceMat m[NM];
    const float *x;
    size_t xs;
    unsigned xn, mt, ng;
    unsigned n() const {
        unsigned s = 0;
#pragma unroll
        for (unsigned i = 0; i < NM; ++i) s += m[i].np;
        return s;
    }
    template <unsigned S> [[gnu::always_inline]] inline void fetch(sycl::sub_group sg, unsigned lane, unsigned p, Seg &g) const {
        const PaceAt<NM> a(m, p);
        const unsigned r0 = a.pl / ng * R, rows = pm_rows(m, a.mi);
        const uint8_t *w = pm_w(m, a.mi);
#pragma unroll
        for (unsigned j = 0; j < R; ++j) {
            const uint8_t *row = w + (size_t)(r0 + j < rows ? r0 + j : r0) * WK::RB;
            if constexpr (S == 0) {
                const uint8_t *hd = row + (size_t)NB * 160;
#pragma unroll
                for (unsigned k = 0; k < NGR; ++k) {
                    const unsigned gi = 32 * k + lane < NG ? 32 * k + lane : NG - 1, c3 = gi & 3u;
                    const uint8_t *hb = hd + 16 * (gi >> 3), *s = hb + 4;
                    g.dd[j][k] = (uint32_t)iq3::u16(hb) | (uint32_t)iq3::u16(hb + 2) << 16;
                    g.su[j][k] = (uint32_t)s[c3] | (uint32_t)s[4 + c3] << 8 | (uint32_t)s[8 + c3] << 16;
                }
            }
            const uint32_t *qs = reinterpret_cast<const uint32_t *>(row);
            const uint8_t *qh = row + (size_t)NB * 128;
#pragma unroll
            for (unsigned mm = 0; mm < SB; ++mm) {
                g.qa[j][mm] = sg_bload(sg, qs + (size_t)(S * SB + mm) * 32);
                g.qb[j][mm] = qh[(size_t)(S * SB + mm) * 32 + lane];
            }
        }
    }
    template <unsigned S, bool F>
    [[gnu::always_inline]] inline void steps(sycl::sub_group sg, unsigned lane, unsigned p, unsigned nsg, unsigned n, Seg &b0,
                                             Seg &b1, const float (&fac)[R][NGR], const float (&off)[R][NGR], const float *xr,
                                             float (&sum)[R * T]) const {
        Seg &cur = (S % 2 == 0) != F ? b0 : b1;
        Seg &nxt = (S % 2 == 0) != F ? b1 : b0;
        if constexpr (S + 1 < NS) fetch<S + 1>(sg, lane, p, nxt);
        else if (p + nsg < n) fetch<0>(sg, lane, p + nsg, nxt);
#pragma unroll
        for (unsigned mm = 0; mm < SB; ++mm) {
            const unsigned b = S * SB + mm;
            float v[R][8];
#pragma unroll
            for (unsigned c = 0; c < 8; ++c) {
                const unsigned gi = b * 8 + c;
#pragma unroll
                for (unsigned j = 0; j < R; ++j) {
                    const unsigned code = ((cur.qa[j][mm] >> (4 * c)) & 15u) | (((cur.qb[j][mm] >> c) & 1u) << 4);
                    const float f = sycl::select_from_group(sg, fac[j][gi / 32], gi % 32);
                    const float o = sycl::select_from_group(sg, off[j][gi / 32], gi % 32);
                    v[j][c] = f * float(code) - o;
                }
            }
#pragma unroll
            for (unsigned tt = 0; tt < T; ++tt) {
                const auto xv = sg_bloadN<8>(sg, xr + tt * xs + (size_t)b * 256);
#pragma unroll
                for (unsigned c = 0; c < 8; ++c)
#pragma unroll
                    for (unsigned j = 0; j < R; ++j) sum[j * T + tt] = sum[j * T + tt] + v[j][c] * xv[c];
            }
        }
        if constexpr (S + 1 < NS) steps<S + 1, F>(sg, lane, p, nsg, n, b0, b1, fac, off, xr, sum);
    }
    template <bool F>
    [[gnu::always_inline]] inline void pos(sycl::sub_group sg, unsigned lane, unsigned p, unsigned nsg, unsigned n, Seg &b0,
                                           Seg &b1) const {
        const PaceAt<NM> a(m, p);
        const unsigned r0 = a.pl / ng * R, t0 = (a.pl % ng) * T;
        const float *xb = x + t0 * xs;
        const float *xr = xn ? xb + (size_t)(r0 / xn) * NB * 256 : xb;
        const Seg &s0 = F ? b1 : b0;
        float fac[R][NGR], off[R][NGR];
#pragma unroll
        for (unsigned j = 0; j < R; ++j)
#pragma unroll
            for (unsigned k = 0; k < NGR; ++k) {
                const unsigned gi = 32 * k + lane < NG ? 32 * k + lane : NG - 1, c = gi & 7u;
                const uint32_t su = s0.su[j][k], dd = s0.dd[j][k];
                const unsigned u0 = su & 255u, u1 = (su >> 8) & 255u, u2 = (su >> 16) & 255u;
                const unsigned scale = c < 4 ? u0 & 63u : (u2 & 15u) | ((u0 >> 6) << 4);
                const unsigned minimum = c < 4 ? u1 & 63u : (u2 >> 4) | ((u1 >> 6) << 4);
                fac[j][k] = iq3::half((uint16_t)(dd & 0xffffu)) * float(scale);
                off[j][k] = iq3::half((uint16_t)(dd >> 16)) * float(minimum);
            }
        float sum[R * T];
#pragma unroll
        for (unsigned i = 0; i < R * T; ++i) sum[i] = 0;
        steps<0, F>(sg, lane, p, nsg, n, b0, b1, fac, off, xr, sum);
        const size_t ys = pm_ys(m, a.mi);
        ws_reduce_store<R, T>(sg, lane, sum, r0, pm_rows(m, a.mi), pm_y(m, a.mi) + t0 * ys, ys, mt - t0);
    }
    PACE_GO_BODY
};
#undef PACE_GO_BODY

// SP (spread): pace sub-group s (work-group w = s / 16, sub-group l = s % 16 of nsg / 16) takes positions from
// l * (nsg / 16) + w on, so a launch with fewer positions than sub-groups keeps every work-group (every core) evenly
// busy instead of filling the first work-groups (which positions a sub-group computes changes, never how)
template <bool SP> [[gnu::always_inline]] inline unsigned pace_slot(unsigned s, unsigned nsg) {
    if constexpr (SP) return (s % 16u) * (nsg / 16u) + s / 16u;
    else return s;
}
// the launch: work-groups 0 .. rw / 16 - 1 run the rider (sub-group s < rd.n(): rider position s), the rest P's
// positions (sub-group s - rw), nsg sub-groups in all
template <typename RD, typename P, unsigned GRF, bool SP = false> struct PaceKN {
    RD rd;
    P k;
    unsigned nsg, rw;
    void operator()(sycl::nd_item<1> it) const {
        sycl::sub_group sg = it.get_sub_group();
        unsigned s = packed_row_id(it);
        const unsigned lane = sg.get_local_linear_id();
        if constexpr (!std::is_same_v<RD, NoRows>) {
            if (s < rw) {
                if (s < rd.n()) rd.row(sg, lane, s);
                return;
            }
            s -= rw;
        }
        k.go(sg, lane, pace_slot<SP>(s, nsg), nsg);
    }
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>,
                                                           sycl::ext::oneapi::experimental::sub_group_size<32>};
    }
};
// the shared expert's gate + up (route_shared_m's RoutePMRows): work-groups 0 .. m - 1 the router's top-k (one per
// token, RouteP, RoutePM's 2 * 1024 + 6 floats of local memory), then the rider's rw sub-groups, then P's positions
// (nsg sub-groups); 512-item work-groups (RouteP needs one of >= experts items). The local memory is the kernel's own
// (group_local_memory_for_overwrite, not an accessor member: a functor's local_accessor gets a zero-initialized
// function-scope copy in the kernel's entry, gp-a's module-placement trigger)
template <typename RD, typename P, unsigned GRF, bool SP = false> struct RoutePaceK {
    RouteP rp;
    size_t ls;
    unsigned m;
    RD rd;
    P k;
    unsigned nsg, rw;
    const float *logits, *bias;
    uint32_t *ids;
    float *prob;
    void operator()(sycl::nd_item<1> it) const {
        float *lm = *sycl::ext::oneapi::group_local_memory_for_overwrite<float[2 * 1024 + 6]>(it.get_group());
        const unsigned g = (unsigned)it.get_group_linear_id();
        if (g < m) {
            rp(it, logits + g * ls, bias, ids + (size_t)g * rp.topk, prob + (size_t)g * rp.topk, lm);
            return;
        }
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        unsigned s = (g - m) * (unsigned)(it.get_local_range(0) / 32) + sg.get_group_linear_id();
        if constexpr (!std::is_same_v<RD, NoRows>) {
            if (s < rw) {
                if (s < rd.n()) rd.row(sg, lane, s);
                return;
            }
            s -= rw;
        }
        k.go(sg, lane, pace_slot<SP>(s, nsg), nsg);
    }
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>,
                                                           sycl::ext::oneapi::experimental::sub_group_size<32>};
    }
};
// a pick: form P at GRF registers
template <typename P, unsigned GRF> struct PaceSel {
    using p = P;
    static constexpr unsigned grf = GRF;
};
// a pace-2 pick: form P at GRF registers; MODE 0: positions packed from sub-group 0 (one resident wave of sub-groups
// after the front work-groups); 1: spread over the wave; 2 (fit): spread over the wave minus the front work-groups
// (the rider's, the router's), so the whole launch is one resident wave and no work-group with positions waits for a
// front one to finish
template <typename P, unsigned GRF, int MODE> struct PaceSel2 {
    using p = P;
    static constexpr unsigned grf = GRF;
    static constexpr bool sp = MODE != 0;
    static constexpr int mode = MODE;
};
// pace_rows<DK>(...): the pick for this matrix shape and block size, launched through f(kernel, work-groups of 512);
// false: none (ws_rows / the engine's forms as before). cu: the card's compute units (EUs).
template <typename DK, typename RD, typename F>
inline bool pace_rows(const DK &dk, const uint8_t *w, const float *x, size_t xs, float *y, size_t ys, unsigned mt,
                      const RD &rd, unsigned cu, F &&f) {
    constexpr bool rd_ok = std::is_same_v<RD, NoRows> || std::is_same_v<RD, TokRows<HcFinishRows>>;
    using O = WsOf<DK>;
    if constexpr (!rd_ok || O::fmt == 0) return false;
    else {
        if constexpr (!std::is_same_v<RD, NoRows>)
            if (rd.n() > 16) return false;
        const unsigned xn = ws_xn(dk);
        auto go = [&](auto pick) -> bool {
            using P = typename decltype(pick)::p;
            constexpr unsigned GRF = decltype(pick)::grf;
            if (xn % P::r) return false;
            const unsigned nsg = cu * (GRF == 256 ? 4u : 8u) / 16 * 16;
            const unsigned ng = (mt + P::t - 1) / P::t;
            const P p{typename P::WK{dk.rows, xn}, w, x, xs, y, ys, mt, ng};
            f(PaceK<RD, P, GRF>{rd, p, nsg}, (size_t)(nsg / 16 + (std::is_same_v<RD, NoRows> ? 0 : 1)));
            return true;
        };
        auto go2 = [&](auto pick) -> bool { // pace-2's forms: one matrix, the rider on work-groups of its own
            using P = typename decltype(pick)::p;
            constexpr unsigned GRF = decltype(pick)::grf;
            const unsigned ng = (mt + P::t - 1) / P::t;
            P p{};
            p.m[0] = PaceMat{w, y, ys, dk.rows, (dk.rows + P::r - 1) / P::r * ng};
            p.x = x, p.xs = xs, p.xn = 0, p.mt = mt, p.ng = ng;
            unsigned rw = 0;
            if constexpr (!std::is_same_v<RD, NoRows>) rw = (rd.n() + 15) / 16 * 16;
            const unsigned wave = cu * (GRF == 256 ? 4u : 8u) / 16 * 16, nsg = decltype(pick)::mode == 2 ? wave - rw : wave;
            f(PaceKN<RD, P, GRF, decltype(pick)::sp>{rd, p, nsg, rw}, (size_t)(rw + nsg) / 16);
            return true;
        };
        if constexpr (O::fmt == 8 && O::cols == 1280) { // q_b, 16 heads
            if (!(g_pace_roles & 1u) || dk.rows != 8192 || xn) return false;
            switch (mt) {
            case 2: return go(PaceSel<PaceSQ8<40, 2, 3, 1, 2>, 256>{});
            case 3: return go(PaceSel<PaceSQ8<40, 3, 3, 1, 1>, 256>{});
            case 4: return go(PaceSel<PaceSQ8<40, 4, 1, 1, 1>, 128>{});
            case 5: return go(PaceSel<PaceSQ8<40, 5, 1, 1, 1>, 128>{});
            case 6: return go(PaceSel<PaceSQ8<40, 6, 1, 1, 1>, 128>{});
            default: return false;
            }
        } else if constexpr (O::fmt == 6 && O::cols == 1280) { // q_b, 16 heads (2 and 3 tokens: kept)
            if (!(g_pace_roles & 2u) || dk.rows != 8192 || xn) return false;
            switch (mt) {
            case 4: return go(PaceSel<PaceSQ6<5, 4, 2, 1>, 256>{});
            case 5: return go(PaceSel<PaceSQ6<5, 5, 2, 1>, 256>{});
            case 6: return go(PaceSel<PaceSQ6<5, 6, 2, 1>, 256>{});
            default: return false;
            }
        } else if constexpr (O::fmt == 8 && O::cols == 4096) { // output-a, two groups of 1,024 rows (3 tokens: kept)
            if (!(g_pace_roles & 4u) || dk.rows != 2048 || xn != 1024) return false;
            switch (mt) {
            case 2: return go(PaceSel<PaceSQ8<128, 2, 1, 1, 1>, 128>{});
            case 4: return go(PaceSel<PaceSQ8<128, 4, 1, 1, 1>, 128>{});
            case 5: return go(PaceSel<PaceSQ8<128, 5, 1, 1, 1>, 128>{});
            case 6: return go(PaceSel<PaceSQ8<128, 6, 2, 1, 1>, 256>{});
            default: return false;
            }
        } else if constexpr (O::cols == 8192 && (O::fmt == 8 || O::fmt == 6)) { // output-b (pace-2: 848 / 864 rows)
            if (!(g_pace_roles & 16u) || xn || dk.rows < 768 || dk.rows > 1024) return false;
            if constexpr (O::fmt == 8) {
                switch (mt) {
                case 2: return go2(PaceSel2<PaceSQ8N<256, 2, 1, 2, 4>, 256, 1>{});
                case 3: return go2(PaceSel2<PaceSQ8N<256, 3, 1, 2, 2>, 256, 1>{});
                case 4: return go2(PaceSel2<PaceSQ8N<256, 4, 1, 2, 2>, 256, 2>{});
                case 5: return go2(PaceSel2<PaceSQ8N<256, 5, 1, 2, 2>, 256, 2>{});
                case 6: return go2(PaceSel2<PaceSQ8N<256, 6, 1, 1, 1>, 256, 2>{});
                default: return false;
                }
            } else {
                switch (mt) {
                case 2: return go2(PaceSel2<PaceSQ6N<32, 2, 1, 2>, 256, 1>{});
                case 3: return go2(PaceSel2<PaceSQ6N<32, 3, 1, 1>, 256, 1>{});
                case 4: return go2(PaceSel2<PaceSQ6N<32, 4, 1, 1>, 256, 2>{});
                case 5: return go2(PaceSel2<PaceSQ6N<32, 5, 1, 1>, 256, 2>{});
                default: return false;
                }
            }
        } else if constexpr (O::cols == 2304 && (O::fmt == 8 || O::fmt == 5)) { // shared down (pace-2: 848 / 864 rows)
            if (!(g_pace_roles & 32u) || xn || dk.rows < 768 || dk.rows > 1024) return false;
            if constexpr (O::fmt == 8) {
                switch (mt) {
                case 2: return go2(PaceSel2<PaceSQ8N<72, 2, 1, 1, 3>, 256, 1>{});
                case 3: return go2(PaceSel2<PaceSQ8N<72, 3, 1, 1, 3>, 256, 1>{});
                case 4: return go2(PaceSel2<PaceSQ8N<72, 4, 1, 1, 1>, 128, 0>{});
                case 5: return go2(PaceSel2<PaceSQ8N<72, 5, 1, 1, 1>, 256, 2>{});
                case 6: return go2(PaceSel2<PaceSQ8N<72, 6, 1, 1, 1>, 256, 2>{});
                default: return false;
                }
            } else {
                switch (mt) {
                case 2: return go2(PaceSel2<PaceSQ5N<9, 2, 1, 1>, 256, 1>{});
                case 3: return go2(PaceSel2<PaceSQ5N<9, 3, 1, 1>, 256, 1>{});
                case 4: return go2(PaceSel2<PaceSQ5N<9, 4, 1, 3>, 256, 2>{});
                case 5: return go2(PaceSel2<PaceSQ5N<9, 3, 2, 1>, 256, 2>{});
                case 6: return go2(PaceSel2<PaceSQ5N<9, 3, 2, 1>, 256, 2>{});
                default: return false;
                }
            }
        } else return false;
    }
}
// pace-2: the q_a + kv pair in one launch (gemv_pair_m; OWN_MT_PACE_ROLES & 8), the mix's dot rows riding (2-3 tokens)
// on work-groups of their own, through f(kernel, work-groups of 512). False: none (ws_pair_rows / the engine's forms).
template <typename DK, typename RD, typename F>
inline bool pace_pair_rows(const DK &dk, unsigned nra, unsigned nrb, const uint8_t *wa, const uint8_t *wb, const float *x,
                           size_t xs, float *ya, size_t ysa, float *yb, size_t ysb, unsigned mt, const RD &rd, unsigned cu,
                           F &&f) {
    using O = WsOf<DK>;
    constexpr bool rd_ok = std::is_same_v<RD, NoRows> || std::is_same_v<RD, TokRows<HcDotsRows<5120, 8>>>;
    if constexpr (!rd_ok || O::cols != 5120 || (O::fmt != 8 && O::fmt != 6)) return false;
    else {
        if (!(g_pace_roles & 8u) || !pace_on(mt) || nra != 1280 || nrb != 512 || ws_xn(dk)) return false;
        auto go = [&](auto pick) -> bool {
            using P = typename decltype(pick)::p;
            constexpr unsigned GRF = decltype(pick)::grf;
            const unsigned ng = (mt + P::t - 1) / P::t;
            P p{};
            p.m[0] = PaceMat{wa, ya, ysa, nra, (nra + P::r - 1) / P::r * ng};
            p.m[1] = PaceMat{wb, yb, ysb, nrb, (nrb + P::r - 1) / P::r * ng};
            p.x = x, p.xs = xs, p.xn = 0, p.mt = mt, p.ng = ng;
            unsigned rw = 0;
            if constexpr (!std::is_same_v<RD, NoRows>) rw = (rd.n() + 15) / 16 * 16;
            const unsigned wave = cu * (GRF == 256 ? 4u : 8u) / 16 * 16, nsg = decltype(pick)::mode == 2 ? wave - rw : wave;
            f(PaceKN<RD, P, GRF, decltype(pick)::sp>{rd, p, nsg, rw}, (size_t)(rw + nsg) / 16);
            return true;
        };
        if constexpr (O::fmt == 8) {
            switch (mt) {
            case 4: return go(PaceSel2<PaceSQ8N<160, 4, 2, 1, 1, 2>, 256, 0>{});
            case 5: return go(PaceSel2<PaceSQ8N<160, 5, 2, 1, 1, 2>, 256, 2>{});
            case 6: return go(PaceSel2<PaceSQ8N<160, 6, 2, 1, 1, 2>, 256, 0>{});
            default: return false;
            }
        } else {
            switch (mt) {
            case 4: return go(PaceSel2<PaceSQ6N<20, 4, 1, 1, 2>, 256, 1>{});
            case 5: return go(PaceSel2<PaceSQ6N<20, 5, 1, 1, 2>, 256, 2>{});
            case 6: return go(PaceSel2<PaceSQ6N<20, 6, 1, 1, 2>, 256, 1>{});
            default: return false;
            }
        }
    }
}
// pace-2: the shared expert's gate + up with the router's top-k (route_shared_m; OWN_MT_PACE_ROLES & 64): RoutePaceK,
// work-groups 0 .. mt - 1 the router, then the finish's (when it rides), then the rows, through f(kernel, work-groups of
// 512; the kernel holds RoutePM's local memory itself).
template <typename DK, typename F>
inline bool pace_gu_rows(const DK &dk, unsigned rows, const uint8_t *wg, const uint8_t *wu, const float *x, size_t xs,
                         float *yg, float *yu, size_t ys, unsigned mt, const TokRows<HcFinishRows> &fin, const RouteP &rp,
                         size_t ls, const float *logits, const float *bias, uint32_t *ids, float *prob, unsigned cu, F &&f) {
    using O = WsOf<DK>;
    if constexpr (O::cols != 5120 || (O::fmt != 8 && O::fmt != 5)) return false;
    else {
        if (!(g_pace_roles & 64u) || !pace_on(mt) || rows != 384 || ws_xn(dk) || fin.n() > 16) return false;
        auto go = [&](auto pick) -> bool {
            using P = typename decltype(pick)::p;
            constexpr unsigned GRF = decltype(pick)::grf;
            const unsigned ng = (mt + P::t - 1) / P::t;
            P p{};
            p.m[0] = PaceMat{wg, yg, ys, rows, (rows + P::r - 1) / P::r * ng};
            p.m[1] = PaceMat{wu, yu, ys, rows, (rows + P::r - 1) / P::r * ng};
            p.x = x, p.xs = xs, p.xn = 0, p.mt = mt, p.ng = ng;
            const unsigned rw = (fin.n() + 15) / 16 * 16;
            const unsigned wave = cu * (GRF == 256 ? 4u : 8u) / 16 * 16,
                           nsg = decltype(pick)::mode == 2 ? wave - rw - 16 * mt : wave;
            f(RoutePaceK<TokRows<HcFinishRows>, P, GRF, decltype(pick)::sp>{rp, ls, mt, fin, p, nsg, rw, logits, bias, ids,
                                                                            prob},
              (size_t)mt + (rw + nsg) / 16);
            return true;
        };
        if constexpr (O::fmt == 8) {
            switch (mt) {
            case 2: return go(PaceSel2<PaceSQ8N<160, 2, 2, 1, 1, 2>, 256, 2>{});
            case 3: return go(PaceSel2<PaceSQ8N<160, 3, 1, 1, 1, 2>, 256, 2>{});
            case 4: return go(PaceSel2<PaceSQ8N<160, 4, 1, 1, 1, 2>, 256, 2>{});
            case 5: return go(PaceSel2<PaceSQ8N<160, 5, 1, 1, 1, 2>, 256, 2>{});
            default: return false;
            }
        } else {
            switch (mt) {
            case 2: return go(PaceSel2<PaceSQ5N<20, 2, 1, 1, 2>, 256, 2>{});
            case 3: return go(PaceSel2<PaceSQ5N<20, 3, 1, 2, 2>, 256, 2>{});
            case 4: return go(PaceSel2<PaceSQ5N<20, 4, 1, 1, 2>, 256, 2>{});
            case 5: return go(PaceSel2<PaceSQ5N<20, 5, 1, 2, 2>, 256, 2>{});
            case 6: return go(PaceSel2<PaceSQ5N<20, 6, 1, 2, 2>, 256, 2>{});
            default: return false;
            }
        }
    }
}
} // namespace ops41sycl
