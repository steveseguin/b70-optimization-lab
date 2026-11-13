// fl-1 (2026-11-11): fewer launches on the one-token step, bit for bit (OWN_FL, backend_sycl_v41.hpp "fl-1"; bench
// /home/steve/dsv41-work/fl: bench_fl.cpp for every form tried, bench_fl_ship.cpp for these).
//
// 1. FlNormK: a norm folded into the launch that consumes it. Today the one-token step runs the FFN's 5,120 pre-norm
//    and the stream mix's 25 dot rows as their own launch (SkNormDotsW<8>: work-group 0 the norm, 1..25 the dot rows)
//    between HcPostPreP and the router rows (GemvH16P<160>). Here the router launch does it: work-groups 0..24 run
//    SkDotsFF<8>::run unchanged (SkNormDotsW's work-groups 1..25, the same rows: the same partial words); every router
//    work-group forms the norm's scale itself (SkNormSplit<5120, 16>'s partial sums on its 16 sub-groups, one
//    barrier, SkNormSplit::finish on every sub-group, the production chain where the check fails: SkNormW's code,
//    so the same float rs), writes x * rs * w (RmsNormPS's expression w * (x * rs)) into its local memory once
//    (MODE 0; MODE 1 forms it at every load, the same floats) and runs its rows on those values. fl_h16_sum is
//    GemvH16P::row with only the activation's source changed: sub_group::load<8> from local memory has the global
//    block read's layout (element i * 32 + lane), so the same products in the same order, the same tree. The first
//    router work-group also stores the normalized vector (the shared and routed experts read it).
//    Measured (bench, card 1, cold rows): FFN chain 24.6 -> 22.2 us (Q8_0 layer), 25.3 -> 22.8 us (Q5_K layer).
//    The same fold into q_a + kv or q_b is SLOWER (+0.8..+2.3 / +12..+14 us): there every matrix work-group's
//    prologue (3.5-5 us before its first weight load) is not hidden by other work; see bench_fl.cpp.
// 2. FlDownComb: MoeCombineA as the epilogue of the shared expert's down rows: after its row, lane 0 reads back its
//    own stored shared value and adds the top expert values in MoeCombineA's order (acc = shared; acc += e_0 ..
//    e_{TOP-1}). 5.0 -> 4.2 us (Q8_0), 5.6 -> 5.0 us (Q5_K).
// All kernels build with -fp-model=precise -ffp-contract=off (no contraction appears or vanishes).
#pragma once
#include "stage2/packet3/kernels/sycl_v41.hpp"

namespace ops41sycl {

using FlLocalP = sycl::multi_ptr<float, sycl::access::address_space::local_space, sycl::access::decorated::yes>;

// activation sources for the copied row body: element o .. of the activation vector in sg_bloadN<N>'s layout
struct FlXL { // the work-group's local copy (FlNormK MODE 0)
    FlLocalP xs;
    template <int N> [[gnu::always_inline]] inline sycl::vec<float, N> ld(sycl::sub_group sg, size_t o) const {
        return sg.load<N>(xs + (std::ptrdiff_t)o);
    }
};
struct FlXF { // formed at each load: w * (x * rs) (FlNormK MODE 1)
    const float *x, *w;
    float rs;
    template <int N> [[gnu::always_inline]] inline sycl::vec<float, N> ld(sycl::sub_group sg, size_t o) const {
        const auto a = sg_bloadN<N>(sg, x + o);
        const auto b = sg_bloadN<N>(sg, w + o);
        sycl::vec<float, N> v;
#pragma unroll
        for (int k = 0; k < N; ++k) v[k] = b[k] * (a[k] * rs);
        return v;
    }
};

// GemvH16P<C, A>::row with x from xs; returns the reduced sum (every lane)
template <unsigned C, typename XS>
[[gnu::always_inline]] inline float fl_h16_sum(sycl::sub_group sg, unsigned r, const uint8_t *w, const XS &xs) {
    const uint16_t *row = reinterpret_cast<const uint16_t *>(w) + (size_t)r * C * 32;
    float sum = 0;
#pragma unroll
    for (unsigned s = 0; s < C / 8; ++s) {
        const auto wv = sg_bloadN<8>(sg, row + (size_t)s * 256);
        const auto xv = xs.template ld<8>(sg, (size_t)s * 256);
#pragma unroll
        for (unsigned m = 0; m < 8; ++m) sum = sum + sycl::bit_cast<float>(uint32_t(wv[m]) << 16) * xv[m];
    }
    return sg_tree32(sg, sum);
}
// the 16-bit packed rows (the router, GemvH16P<C>'s layout) as rows of a folded launch; y[r] = the row's sum (lane 0)
template <unsigned C> struct FlH16Rows {
    unsigned rows;
    const uint8_t *w;
    float *y;
    unsigned n() const { return rows; }
    template <typename XS>
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r, const XS &xs) const {
        const float s = fl_h16_sum<C>(sg, r, w, xs);
        if (lane == 0) y[r] = s;
    }
};

// RmsNormPS<N, *>'s scale (the production chain's float(1 / sqrt(acc_chain / N + 1e-20))) on one work-group of
// >= S sub-groups: SkNormSplit<N, S>::partial on sub-groups 0 .. S - 1 (SkNormSplit::run's code), one barrier,
// SkNormSplit::finish on every sub-group (each forms the same rs from the same S partials), the chain on every
// sub-group where the check fails (as SkNormSplit::run). lm: words [0, 2 S).
template <unsigned N, unsigned S>
[[gnu::always_inline]] inline float fl_norm_scale(sycl::nd_item<1> it, unsigned sgi, uint32_t *lm, const float *x) {
    using SP = SkNormSplit<N, S>;
    sycl::sub_group sg = it.get_sub_group();
    const unsigned lane = sg.get_local_linear_id();
    if (sgi < S) {
        double p;
        {
            sycl::vec<float, 8> xv[SP::MY];
#pragma unroll
            for (unsigned k = 0; k < SP::MY; ++k)
                if (sgi + k * S < SP::C) xv[k] = sg_bloadN<8>(sg, x + (sgi + k * S) * 256);
            p = SP::partial(sg, lane, sgi, xv);
        }
        if (lane == 0) sk_put(lm, (int)sgi, p);
    }
    sycl::group_barrier(it.get_group());
    bool ok;
    float rs = SP::finish(sg, lane, lm, 0, ok);
    if (!ok) rs = SP::PS::rs_of(SP::PS::acc_chain(sg, lane, x));
    return rs;
}

// The consumer launch of a norm (see the top). launch: the backend's fl_norm_launch (work-groups of 512 items = 16
// sub-groups, lm 64 words, xs N floats for MODE 0). Work-groups [0, ND): SkDotsFF<K> row g (streams, fn -> dout);
// [ND, ...): position p = (g - ND) * 16 + sub-group: rider rows RI first (p < ri.n()), then the matrix rows RW.
// x: the norm's input, nw its weight, y the normalized vector (stored by work-group ND).
template <unsigned N, unsigned S, unsigned ND, unsigned K, unsigned MODE, typename RI, typename RW> struct FlNormK {
    static_assert(N % 256 == 0 && S >= 1 && S <= 16 && (MODE == 0 || MODE == 1));
    static constexpr unsigned C = N / 256, SGS = 16;
    const float *x, *nw;
    float *y;
    const float *streams, *fn;
    double *dout;
    RI ri;
    RW rw;
    size_t groups() const { return ND + (ri.n() + rw.n() + SGS - 1) / SGS; }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, uint32_t *lm, FlLocalP xs) const {
        const unsigned g = (unsigned)it.get_group_linear_id();
        sycl::sub_group sg = it.get_sub_group();
        const unsigned sgi = sg.get_group_linear_id(), lane = sg.get_local_linear_id();
        if constexpr (ND > 0) {
            if (g < ND) {
                SkDotsFF<K>::run(it, sgi, lm, g, streams, fn, dout);
                return;
            }
        }
        const unsigned wg = g - ND;
        const float rs = fl_norm_scale<N, S>(it, sgi, lm, x);
#pragma unroll
        for (unsigned k = 0; k < (C + SGS - 1) / SGS; ++k) {
            const unsigned c = sgi + k * SGS;
            if (c < C && (MODE == 0 || wg == 0)) {
                const auto xv = sg_bloadN<8>(sg, x + c * 256);
                const auto wv = sg_bloadN<8>(sg, nw + c * 256);
                sycl::vec<float, 8> o;
#pragma unroll
                for (unsigned m = 0; m < 8; ++m) o[m] = wv[m] * (xv[m] * rs);
                if constexpr (MODE == 0) sg.store<8>(xs + (std::ptrdiff_t)(c * 256), o);
                if (wg == 0)
                    sg.store<8>(sycl::address_space_cast<sycl::access::address_space::global_space,
                                                         sycl::access::decorated::yes>(y + c * 256),
                                o);
            }
        }
        if constexpr (MODE == 0) sycl::group_barrier(it.get_group());
        const unsigned p = wg * SGS + sgi, ni = ri.n();
        if (p < ni) {
            ri.row(sg, lane, p);
            return;
        }
        if (p - ni >= rw.n()) return;
        if constexpr (MODE == 0) rw.row(sg, lane, p - ni, FlXL{xs});
        else rw.row(sg, lane, p - ni, FlXF{x, nw, rs});
    }
};

// D's rows (the shared expert's down slice, GemvQ8P<72> / GemvQ5KP<9>; launch_rows: one row per sub-group) with
// MoeCombineA<A>{TOP, rows}'s output after each row: out[r] = shared[r] + exps[0 * rows + r] + ... (MoeCombineA's
// order; shared[r] is the value the row just stored, read back by the lane that stored it). The TOP expert values
// are loaded by lanes 0 .. TOP - 1 before the row and broadcast after it.
template <typename D, unsigned TOP> struct FlDownComb {
    static_assert(TOP >= 1 && TOP <= 32);
    D k;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, float *y, const float *exps,
                                     float *out) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned r = packed_row_id(it);
        if (r >= k.rows) return;
        const unsigned lane = sg.get_local_linear_id();
        const float e = lane < TOP ? exps[(size_t)lane * k.rows + r] : 0.0f;
        k.row(sg, lane, r, w, x, y);
        float ev[TOP];
#pragma unroll
        for (unsigned t = 0; t < TOP; ++t) ev[t] = sycl::select_from_group(sg, e, (int)t);
        if (lane == 0) {
            float acc = y[r];
#pragma unroll
            for (unsigned t = 0; t < TOP; ++t) acc += ev[t];
            out[r] = acc;
        }
    }
};

} // namespace ops41sycl
