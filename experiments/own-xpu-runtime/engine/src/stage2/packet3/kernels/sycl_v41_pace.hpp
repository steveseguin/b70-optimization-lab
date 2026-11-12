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

// OWN_MT_PACE: the check sizes M (bit M - 2; default 0 = off); OWN_MT_PACE_ROLES: 1 q_b Q8_0, 2 q_b Q6_K, 4 output-a
// Q8_0 (default all)
inline unsigned g_pace_mask = 0, g_pace_roles = 7;
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
// a pick: form P at GRF registers
template <typename P, unsigned GRF> struct PaceSel {
    using p = P;
    static constexpr unsigned grf = GRF;
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
        } else return false;
    }
}
} // namespace ops41sycl
