// ck2-1 (2026-11-12, OWN_CK2; /home/steve/dsv41-work/ck2/README.md): the guessing checks' FFN chain at 2-3 tokens.
// Bench: ck2/src/bench_ck2.cpp (every output word compared against the engine's launches, real GGUF rows).
//   FlNormKM<M, RF, MODE>: the FFN pre-norm, the mix's dot rows and the router rows of an M-token block in ONE launch
//     (fl-1's FlNormK, which does this for one token, made M-token). The engine uses FlNormKM<2, 1, 1> (OWN_CK2_FORMS
//     bit 1): 13.0 us against today's 17.0 (SkNormWM 2.5 + router with HcDotsRows riding 14.4; card 3, bench).
//   RowsDotsK<D>: a rows launch with the mix's dot rows as SkDotsFF work-groups in place of the HcDotsRows sub-group
//     rows riding it (OWN_CK2_FORMS bit 2): router at 3 tokens 19.3 -> 14.0 us.
//
// Today a check block of 2-3 tokens runs, per layer, SkNormWM<5120, 16> (one work-group per token: the FFN pre-norm)
// and then the router rows DenseRowsG<GemvH16P<160>, G> with the mix's 25 dot rows riding as TokRows<HcDotsRows>
// sub-group rows (a serial double chain per (token, row, segment)); 2-3 us + 15-21 us on card 2 (tl105). FlNormKM:
//   work-groups [0, 25 nd): SkDotsFF<8>::run for (token g / 25, row g % 25) -- SkDotsWM<8>'s work-group code (the
//     one-token path's and the M >= 4 blocks' dot rows, OWN_MT_SKDOTS): its partial words differ from HcDotsRows'
//     where its proof holds, the finish's outputs do not (SkDotsFF's comment; the bench compares the finish outputs);
//     where the proof fails the row writes HcMixDotsP's production partials.
//   work-groups [25 nd, ...): every work-group forms the M tokens' norm scales itself (SkNormSplit<5120, 16>::partial
//     on its 16 sub-groups for each token, ONE barrier, SkNormSplit::finish per token on every sub-group, the
//     production chain RmsNormPS::acc_chain where the check fails: SkNormSplit::run's code per token, so the same
//     float rs as SkNormWM's work-group t), forms x * rs * w (w * (x * rs), SkNormSplit::run's expression) into local
//     memory (MODE 0) or at every load (MODE 1, FlXF), work-group 0 also stores the normalized vectors to y (the
//     shared / routed experts read them), then runs router positions:
//       RF 0: position p = (row p / M, token p % M): fl_h16_sum<160> (GemvH16P<160>::row's lane chain and sg_tree32 on
//             that token's normalized vector);
//       RF 1: position p = row p, the M tokens' chains side by side (GemvH16P::rowg<M>'s loop: one weight conversion,
//             then sum[t] = sum[t] + w * x_t[m] per token in the same order; sg_tree32 per token).
//     Either way every (row, token) logit is GemvH16P<160>::row's expression in its order: the production
//     DenseRowsG<GemvH16P<160>, G>'s rowg<G> (any G) gives the same per-token chain.
//   (rfirst = 1 numbers the router work-groups first; RF 0 / MODE 0 forms and M >= 3 lose in the bench: README.)
// Built with -fp-model=precise -ffp-contract=off as the engine (no contraction appears or vanishes).
#pragma once
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/sycl_v41_fl.hpp"

namespace ops41sycl {

template <unsigned M, unsigned RF, unsigned MODE> struct FlNormKM {
    static_assert(M >= 1 && M <= 6 && RF <= 1 && MODE <= 1);
    static constexpr unsigned N = 5120, S = 16, C = N / 256, SGS = 16, K = 8, RC = 160;
    using SP = SkNormSplit<N, S>;
    const float *x, *nw;      // the pre-norm's input (token t at x + t * xs) and weight
    float *y;                 // the normalized vectors (token t at y + t * ys)
    size_t xs, ys;
    const float *streams, *fn; // the mix's dot rows: nd tokens, token t's streams at streams + t * ss
    double *dout;              // token t's 25 * 8 partials at dout + t * os
    size_t ss, os;
    unsigned nd;
    const uint8_t *w; // the router's packed rows (GemvH16P<160>'s layout)
    float *ry;        // logits: token t's row r at ry[t * rys + r]
    size_t rys;
    unsigned rows;
    unsigned rfirst = 0; // 1: the router work-groups first, then the dot rows' (only the work-group numbering changes)
    static constexpr size_t lm_words() { return 2 * S * M > 64 ? 2 * S * M : 64; }
    static constexpr size_t xl_floats() { return MODE == 0 ? (size_t)M * N : 1; }
    size_t npos() const { return RF == 0 ? (size_t)rows * M : (size_t)rows; }
    size_t groups() const { return (size_t)nd * 25 + (npos() + SGS - 1) / SGS; }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, uint32_t *lm, FlLocalP xl) const {
        const unsigned g0 = (unsigned)it.get_group_linear_id(), nrw = (unsigned)((npos() + SGS - 1) / SGS);
        const unsigned g = rfirst ? (g0 < nrw ? g0 + nd * 25 : g0 - nrw) : g0; // (dot work-groups first in g)
        sycl::sub_group sg = it.get_sub_group();
        const unsigned sgi = sg.get_group_linear_id(), lane = sg.get_local_linear_id();
        if (g < nd * 25) {
            const unsigned t = g / 25;
            SkDotsFF<K>::run(it, sgi, lm, g % 25, streams + t * ss, fn, dout + t * os);
            return;
        }
        const unsigned wg = g - nd * 25;
        // the M scales: SkNormSplit::run's partial / finish / chain per token, one barrier for all M
#pragma unroll
        for (unsigned t = 0; t < M; ++t) {
            sycl::vec<float, 8> xv[SP::MY];
#pragma unroll
            for (unsigned k = 0; k < SP::MY; ++k)
                if (sgi + k * S < C) xv[k] = sg_bloadN<8>(sg, x + t * xs + (sgi + k * S) * 256);
            const double p = SP::partial(sg, lane, sgi, xv);
            if (lane == 0) sk_put(lm, (int)(t * S + sgi), p);
        }
        sycl::group_barrier(it.get_group());
        float rs[M];
#pragma unroll
        for (unsigned t = 0; t < M; ++t) {
            bool ok;
            rs[t] = SP::finish(sg, lane, lm, (int)(t * S), ok);
            if (!ok) rs[t] = SP::PS::rs_of(SP::PS::acc_chain(sg, lane, x + t * xs));
        }
#pragma unroll
        for (unsigned t = 0; t < M; ++t)
#pragma unroll
            for (unsigned k = 0; k < (C + SGS - 1) / SGS; ++k) {
                const unsigned c = sgi + k * SGS;
                if (c < C && (MODE == 0 || wg == 0)) {
                    const auto xv = sg_bloadN<8>(sg, x + t * xs + c * 256);
                    const auto wv = sg_bloadN<8>(sg, nw + c * 256);
                    sycl::vec<float, 8> o;
#pragma unroll
                    for (unsigned m = 0; m < 8; ++m) o[m] = wv[m] * (xv[m] * rs[t]);
                    if constexpr (MODE == 0) sg.store<8>(xl + (std::ptrdiff_t)(t * N + c * 256), o);
                    if (wg == 0)
                        sg.store<8>(sycl::address_space_cast<sycl::access::address_space::global_space,
                                                             sycl::access::decorated::yes>(y + t * ys + c * 256),
                                    o);
                }
            }
        if constexpr (MODE == 0) sycl::group_barrier(it.get_group());
        const size_t p = (size_t)wg * SGS + sgi;
        if (p >= npos()) return;
        if constexpr (RF == 0) {
            const unsigned r = (unsigned)(p / M), t = (unsigned)(p % M);
            float s;
            if constexpr (MODE == 0) s = fl_h16_sum<RC>(sg, r, w, FlXL{xl + (std::ptrdiff_t)(t * N)});
            else {
                float rst = rs[0]; // (constant indices: rs stays in registers)
#pragma unroll
                for (unsigned k = 1; k < M; ++k) rst = t == k ? rs[k] : rst;
                s = fl_h16_sum<RC>(sg, r, w, FlXF{x + t * xs, nw, rst});
            }
            if (lane == 0) ry[t * rys + r] = s;
        } else {
            const unsigned r = (unsigned)p;
            const uint16_t *row = reinterpret_cast<const uint16_t *>(w) + (size_t)r * RC * 32;
            float sum[M];
#pragma unroll
            for (unsigned t = 0; t < M; ++t) sum[t] = 0;
#pragma unroll
            for (unsigned s = 0; s < RC / 8; ++s) {
                const auto wv = sg_bloadN<8>(sg, row + (size_t)s * 256);
                sycl::vec<float, 8> xv[M];
#pragma unroll
                for (unsigned t = 0; t < M; ++t) {
                    if constexpr (MODE == 0) xv[t] = FlXL{xl + (std::ptrdiff_t)(t * N)}.template ld<8>(sg, (size_t)s * 256);
                    else xv[t] = FlXF{x + t * xs, nw, rs[t]}.template ld<8>(sg, (size_t)s * 256);
                }
#pragma unroll
                for (unsigned m = 0; m < 8; ++m) {
                    const float wf = sycl::bit_cast<float>(uint32_t(wv[m]) << 16);
#pragma unroll
                    for (unsigned t = 0; t < M; ++t) sum[t] = sum[t] + wf * xv[t][m];
                }
            }
#pragma unroll
            for (unsigned t = 0; t < M; ++t) sum[t] = sg_tree32(sg, sum[t]);
            if (lane == 0) {
#pragma unroll
                for (unsigned t = 0; t < M; ++t) ry[t * rys + r] = sum[t];
            }
        }
    }
};

// ck2-2: a rows launch (any RowsP rows D: today's router rows DenseRowsG<GemvH16P<160>, G>, the q_a + kv pair's
// RowsPair<DenseRowsWS, DenseRowsWS>, ...) with the mix's dot rows as SkDotsFF<8> work-groups (SkDotsWM<8>'s, the
// one-token path's) in place of the TokRows<HcDotsRows<5120, 8>> sub-group rows riding today (RowsP<RowsPair<HD, D>>).
// Work-groups [0, nrw) are RowsP<D>'s (16 rows each, the same packed_row_id mapping: every row runs D::row as in its
// own launch), work-groups [nrw, nrw + 25 nd) SkDotsWM<8>'s work-group q (token q / 25's row q % 25). The partial words
// of a dot row differ from HcDotsRows' where SkDotsFF's proof holds, the finish's outputs do not (SkDotsFF's comment;
// the engine's OWN_MT_SKDOTS path). The dot rows' inputs and the rows' inputs are written by launches before this one.
template <typename D> struct RowsDotsK {
    D d;
    const float *streams, *fn;
    double *dout;
    size_t ss, os; // per-token strides: streams (floats), partials (doubles)
    unsigned nd;   // tokens with dot rows (their streams / partials from token 0 of the pointers)
    static constexpr size_t lm_words() { return 64; }
    unsigned nrw() const { return (d.n() + 15) / 16; }
    size_t groups() const { return (size_t)nrw() + (size_t)nd * 25; }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, uint32_t *lm) const {
        const unsigned g = (unsigned)it.get_group_linear_id(), nr = nrw();
        sycl::sub_group sg = it.get_sub_group();
        if (g < nr) {
            const unsigned r = packed_row_id(it);
            if (r >= d.n()) return;
            d.row(sg, sg.get_local_linear_id(), r);
            return;
        }
        const unsigned q = g - nr, t = q / 25;
        SkDotsFF<8>::run(it, sg.get_group_linear_id(), lm, q % 25, streams + t * ss, fn, dout + t * os);
    }
};
// the RowsDotsK launch replacing RowsP<RowsPair<TokRows<HcDotsRows<5120, 8>>, D>>{{hd, d}}
template <typename D> inline RowsDotsK<D> rows_dots(const TokRows<HcDotsRows<5120, 8>> &hd, const D &d) {
    return RowsDotsK<D>{d, hd.r.streams, hd.r.fn, hd.r.out, hd.st[0], hd.st[1], hd.m};
}

} // namespace ops41sycl
