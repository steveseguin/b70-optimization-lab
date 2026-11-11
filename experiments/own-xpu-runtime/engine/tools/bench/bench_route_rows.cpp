// What sets the router launch's time (RoutePRows: 21.6 us per call in the answer steps, 40 per step)? The engine
// launch runs RouteP (the expert pick, one work-group of 512) in work-group 0 and, in the others, the stream mix's
// finish (HcFinishRows, one sub-group, serial) and the shared expert's gate + up rows (Q8_0, 2 x 384 rows of 5,120
// columns: a 12-head card's slice). Forms, timed back to back (interleaved), outputs compared BITWISE with A's:
//   A  the engine launch: RoutePRows<RowsPair<HcFinishRows, RowsPair<rows, rows>>>, 1 + 49 work-groups of 512
//   B  RouteP alone          C  HcFinishRows alone (RowsP, one sub-group)
//   D  the shared rows alone (RowsP, 48 work-groups)
//   E  A without the finish (RoutePRows<RowsPair<rows, rows>>)
//   F  A with the finish alone in work-group 1 (a NoRows-padded pair: the finish's core is not shared with rows)
//   G  RouteP alone in a work-group of 384 items (one per expert)
//   H  the scores only (timing)   I / J  this file's two-stage RouteQ alone / in A
//   K / L  the engine's RouteP with two = true (OWN_ROUTE_Q) alone / in A; every RouteP above is two = false
// Sweep: 4,096 sets per pattern (random, ties, all equal, NaN, +-inf, huge negative, signed zeros, ...), RouteQ and
// the engine's two-stage form against RouteP, ids and probabilities bitwise (NaN: RouteP against itself too).
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_route_rows.cpp -o $S/bench_route_rows
//   ONEAPI_DEVICE_SELECTOR=level_zero:1 $S/bench_route_rows
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

static constexpr unsigned H = 5120, E = 384, SR = 384, C = 160;
static constexpr size_t RB = ((size_t)C * 34 + 15) & ~(size_t)15;

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
// n sub-groups that do nothing (pads the finish to a whole work-group in F)
struct PadRows {
    unsigned k;
    unsigned n() const { return k; }
    [[gnu::always_inline]] inline void row(sycl::sub_group, unsigned, unsigned) const {}
};

// T: RouteP's scores only (the transcendentals, no ranks; timing only)
struct RouteT {
    int experts, topk;
    void operator()(sycl::nd_item<1> it, const float *logits, const float *bias, uint32_t *ids, float *prob, float *lm) const {
        float *ls = lm;
        const int i = (int)it.get_local_linear_id();
        if (i < experts) ls[i] = sycl::sqrt(sycl::log1p(sycl::exp(logits[i]))) + bias[i];
        sycl::group_barrier(it.get_group());
        if (i < topk) { ids[i] = (uint32_t)i; prob[i] = ls[i]; }
    }
};
// Q: RouteP's picks in two stages, the same ids and probabilities for every input without NaN scores (NaN anywhere:
// RouteP's loop). Order: a before b when a > b, or a == b and a's index is lower (a strict total order on
// non-NaN floats). Stage 1: each lane's rank among its sub-group's 32 scores (broadcasts); the 6 best of every
// sub-group are the candidates (a slot each in local memory). Stage 2: each candidate's rank among the candidates
// (loaded 32 at a time, broadcast). Every element that comes before a global top-6 element is itself global top-6,
// so it is a candidate: a top-6 element's rank among the candidates is its global rank; any other element has the
// 6 global best before it, all candidates, so its candidate rank is >= 6 too. Two barriers, as RouteP.
struct RouteQ {
    int experts, topk;
    void operator()(sycl::nd_item<1> it, const float *logits, const float *bias, uint32_t *ids, float *prob, float *lm) const {
        float *lsb = lm + experts, *lp = lm + 2 * experts;
        // past RouteP's 2 * 512 + 6 floats: candidate scores and indices (<= 16 sub-groups x 6), NaN flags per sub-group
        float *cv = lm + 1040;
        int *ci = reinterpret_cast<int *>(lm + 1136);
        int *nanf = reinterpret_cast<int *>(lm + 1232);
        const int i = (int)it.get_local_linear_id();
        sycl::sub_group sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
        const bool live = sgi * 32 < experts; // whole sub-groups (experts % 32 == 0)
        if (i < topk) lp[i] = prob[i];
        float v = 0, s0 = 0;
        if (live) {
            s0 = sycl::sqrt(sycl::log1p(sycl::exp(logits[i])));
            v = s0 + bias[i];
            lsb[i] = v;
        }
        int r1 = 0;
        if (live) {
#pragma unroll
            for (int k = 0; k < 32; ++k) {
                const float w = sycl::select_from_group(sg, v, k);
                r1 += (w > v || (w == v && k < lane)) ? 1 : 0;
            }
        }
        const bool anynan = live && sycl::any_of_group(sg, sycl::isnan(v));
        if (lane == 0) nanf[sgi] = anynan ? 1 : 0;
        const bool cand = live && r1 < topk;
        if (cand) { cv[sgi * topk + r1] = v; ci[sgi * topk + r1] = i; }
        sycl::group_barrier(it.get_group());
        int nan_any = 0;
        for (int k = 0; k < (int)(it.get_local_range(0) / 32); ++k) nan_any |= nanf[k];
        if (live) {
            int rank = 0;
            if (nan_any) { // RouteP's loop
                for (int jb = 0; jb < experts; jb += 32) {
                    const float u = lsb[jb + lane];
#pragma unroll
                    for (int k = 0; k < 32; ++k) {
                        const float w = sycl::select_from_group(sg, u, k);
                        rank += (w > v || (w == v && jb + k < i)) ? 1 : 0;
                    }
                }
            } else {
                const int nc = experts / 32 * topk;
                for (int jb = 0; jb < nc; jb += 32) {
                    const bool in = jb + lane < nc;
                    const float u = in ? cv[jb + lane] : 0.0f;
                    const int ui = in ? ci[jb + lane] : 0;
#pragma unroll
                    for (int k = 0; k < 32; ++k) {
                        const float w = sycl::select_from_group(sg, u, k);
                        const int wi = sycl::select_from_group(sg, ui, k);
                        rank += (jb + k < nc && (w > v || (w == v && wi < i))) ? 1 : 0;
                    }
                }
            }
            if ((nan_any || cand) && rank < topk) { ids[rank] = (uint32_t)i; lp[rank] = s0; }
        }
        sycl::group_barrier(it.get_group());
        if (i < topk) {
            float sum = 0;
            for (int t = 0; t < topk; ++t) sum += lp[t];
            prob[i] = lp[i] / (sum + 1e-20f) * 1.5f;
        }
    }
};
// many sets, one work-group each (the correctness sweep)
template <typename RK> struct RouteSets {
    RK rk;
    void operator()(sycl::nd_item<1> it, const float *logits, const float *bias, uint32_t *ids, float *prob, float *lm) const {
        const size_t g = it.get_group_linear_id();
        rk(it, logits + g * rk.experts, bias + g * rk.experts, ids + g * 8, prob + g * 8, lm);
    }
};

template <typename R> struct RoutePRowsQ {
    RouteQ rp;
    R rows;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *logits, const float *bias, uint32_t *ids,
                                     float *prob, float *lm) const {
        const unsigned g = (unsigned)it.get_group_linear_id();
        if (g == 0) { rp(it, logits, bias, ids, prob, lm); return; }
        sycl::sub_group sg = it.get_sub_group();
        const unsigned r = (g - 1) * (unsigned)(it.get_local_range(0) / 32) + sg.get_group_linear_id();
        if (r < rows.n()) rows.row(sg, sg.get_local_linear_id(), r);
    }
};

struct Outs {
    uint32_t *ids;
    float *prob, *pre, *post, *comb, *shg, *shu;
};

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    std::mt19937 rng(11);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::uniform_int_distribution<int> ub(0, 255);
    // inputs
    std::vector<float> hl(E), hb(E), hx(H), hsc(3), hba(24);
    std::vector<double> hd(25 * 8);
    for (auto &v : hl) v = nd(rng) * 2.0f;
    for (auto &v : hb) v = nd(rng) * 0.1f;
    for (auto &v : hx) v = nd(rng);
    for (auto &v : hsc) v = 0.5f + 0.1f * nd(rng);
    for (auto &v : hba) v = 0.2f * nd(rng);
    for (unsigned l = 0; l < 24; ++l)
        for (unsigned k = 0; k < 8; ++k) hd[l * 8 + k] = 3.0 * nd(rng);
    for (unsigned k = 0; k < 8; ++k) hd[24 * 8 + k] = 2560.0 * (1.0 + 0.1 * nd(rng));
    std::vector<uint8_t> hw(2 * (size_t)SR * RB);
    for (size_t r = 0; r < 2 * (size_t)SR; ++r) {
        uint8_t *row = &hw[r * RB];
        for (unsigned i = 0; i < C * 32; ++i) row[i] = (uint8_t)ub(rng);
        uint16_t *dp = reinterpret_cast<uint16_t *>(row + C * 32);
        for (unsigned i = 0; i < C; ++i) dp[i] = (uint16_t)(0x1800 + (ub(rng) & 0x3ff)); // half scales ~1e-4..2e-4
    }
    float *logits = sycl::malloc_device<float>(E, q), *bias = sycl::malloc_device<float>(E, q);
    float *x = sycl::malloc_device<float>(H, q), *scale = sycl::malloc_device<float>(3, q), *base = sycl::malloc_device<float>(24, q);
    double *d = sycl::malloc_device<double>(25 * 8, q);
    uint8_t *w = sycl::malloc_device<uint8_t>(hw.size(), q);
    q.memcpy(logits, hl.data(), E * 4);
    q.memcpy(bias, hb.data(), E * 4);
    q.memcpy(x, hx.data(), H * 4);
    q.memcpy(scale, hsc.data(), 12);
    q.memcpy(base, hba.data(), 96);
    q.memcpy(d, hd.data(), hd.size() * 8);
    q.memcpy(w, hw.data(), hw.size()).wait();
    const uint8_t *wg = w, *wu = w + (size_t)SR * RB;
    constexpr int NF = 12;
    Outs o[NF];
    for (auto &oo : o) {
        oo.ids = sycl::malloc_device<uint32_t>(8, q);
        oo.prob = sycl::malloc_device<float>(8, q);
        oo.pre = sycl::malloc_device<float>(4, q);
        oo.post = sycl::malloc_device<float>(4, q);
        oo.comb = sycl::malloc_device<float>(16, q);
        oo.shg = sycl::malloc_device<float>(SR, q);
        oo.shu = sycl::malloc_device<float>(SR, q);
    }
    using DK = GemvQ8P<C, ActF32>;
    using R1 = DenseRows<DK>;
    using RR = RowsPair<R1, R1>;
    HcMixFinishSG fk{(int)H, 8};
    fk.form = 1;
    const char *names[NF] = {"A engine: route + finish + shared rows", "B route alone (512 items)",
                             "C finish alone (one sub-group)", "D shared rows alone", "E A without the finish",
                             "F A, finish alone in work-group 1", "G route alone (384 items)",
                             "H scores only (no ranks; timing)", "I two-stage route (RouteQ) alone", "J A with RouteQ",
                             "K engine RouteP two = true alone", "L A with the engine's two = true"};
    auto run = [&](int v) -> sycl::event {
        const Outs oo = o[v];
        const RR rr{R1{DK{SR, 0}, wg, x, oo.shg}, R1{DK{SR, 0}, wu, x, oo.shu}};
        const HcFinishRows fr{fk, d, scale, base, oo.pre, oo.post, oo.comb};
        float *prob = oo.prob;
        uint32_t *ids = oo.ids;
        auto rp_launch = [&](auto k, size_t ng, size_t wgi) {
            return q.submit([&](sycl::handler &hh) {
                sycl::local_accessor<float, 1> lt(2 * 1024 + 6, hh);
                hh.parallel_for(sycl::nd_range<1>(ng * wgi, wgi), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                    k(it, logits, bias, ids, prob, &lt[0]);
                });
            });
        };
        auto rows_launch = [&](auto k, size_t rows) {
            const size_t nwg = (rows + 15) / 16;
            return q.parallel_for(sycl::nd_range<1>(nwg * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it); });
        };
        switch (v) {
        case 0: {
            using RX = RowsPair<HcFinishRows, RR>;
            const RX rx{fr, rr};
            return rp_launch(RoutePRows<RX>{RouteP{(int)E, 6, false}, rx}, 1 + (rx.n() + 15) / 16, 512);
        }
        case 1: return rp_launch(RoutePRows<NoRows>{RouteP{(int)E, 6, false}, NoRows{}}, 1, 512);
        case 2: return rows_launch(RowsP<HcFinishRows>{fr}, 1);
        case 3: return rows_launch(RowsP<RR>{rr}, rr.n());
        case 4: return rp_launch(RoutePRows<RR>{RouteP{(int)E, 6, false}, rr}, 1 + (rr.n() + 15) / 16, 512);
        case 5: {
            using FP = RowsPair<HcFinishRows, PadRows>;
            using RX = RowsPair<FP, RR>;
            const RX rx{FP{fr, PadRows{15}}, rr};
            return rp_launch(RoutePRows<RX>{RouteP{(int)E, 6, false}, rx}, 1 + (rx.n() + 15) / 16, 512);
        }
        case 6: return rp_launch(RoutePRows<NoRows>{RouteP{(int)E, 6, false}, NoRows{}}, 1, 384);
        case 7: return rp_launch(RouteT{(int)E, 6}, 1, 512);
        case 8: return rp_launch(RouteQ{(int)E, 6}, 1, 512);
        case 9: {
            using RX = RowsPair<HcFinishRows, RR>;
            const RX rx{fr, rr};
            return rp_launch(RoutePRowsQ<RX>{RouteQ{(int)E, 6}, rx}, 1 + (rx.n() + 15) / 16, 512);
        }
        case 10: return rp_launch(RoutePRows<NoRows>{RouteP{(int)E, 6, true}, NoRows{}}, 1, 512);
        default: {
            using RX = RowsPair<HcFinishRows, RR>;
            const RX rx{fr, rr};
            return rp_launch(RoutePRows<RX>{RouteP{(int)E, 6, true}, rx}, 1 + (rx.n() + 15) / 16, 512);
        }
        }
    };
    std::vector<double> tm[NF];
    for (int set = 0; set < 8; ++set) {
        // probabilities are inputs of the route (lp[i] = prob[i] for unpicked ranks): reset them alike
        for (auto &oo : o) q.fill(oo.prob, 0.0f, 8);
        q.wait();
        std::vector<std::pair<int, sycl::event>> evs;
        for (int r = 0; r < 26; ++r)
            for (int v = 0; v < NF; ++v) {
                auto e = run(v);
                if (r) evs.push_back({v, e});
            }
        q.wait();
        for (auto &[v, e] : evs) tm[v].push_back(ev_us(e));
    }
    long bad = 0;
    auto cmpv = [&](const void *a, const void *b, size_t n, const char *what, int v) {
        std::vector<uint8_t> ha(n), hb2(n);
        q.memcpy(ha.data(), a, n);
        q.memcpy(hb2.data(), b, n).wait();
        if (std::memcmp(ha.data(), hb2.data(), n)) { ++bad; std::printf("%s: %s DIFFERS\n", names[v], what); }
    };
    for (int v : {1, 4, 5, 6, 8, 9, 10, 11}) { cmpv(o[0].ids, o[v].ids, 24, "ids", v); cmpv(o[0].prob, o[v].prob, 24, "prob", v); }
    for (int v : {9, 11}) { cmpv(o[0].shg, o[v].shg, SR * 4, "shared gate", v); cmpv(o[0].pre, o[v].pre, 16, "pre", v); }
    for (int v : {2, 5}) { cmpv(o[0].pre, o[v].pre, 16, "pre", v); cmpv(o[0].post, o[v].post, 16, "post", v); cmpv(o[0].comb, o[v].comb, 64, "comb", v); }
    for (int v : {3, 4, 5}) { cmpv(o[0].shg, o[v].shg, SR * 4, "shared gate", v); cmpv(o[0].shu, o[v].shu, SR * 4, "shared up", v); }
    // sweep: NS sets per pattern, RouteQ against RouteP (ids and probabilities, bitwise)
    {
        constexpr unsigned NS = 4096;
        float *sl = sycl::malloc_device<float>((size_t)NS * E, q), *sb = sycl::malloc_device<float>((size_t)NS * E, q);
        uint32_t *i0 = sycl::malloc_device<uint32_t>(NS * 8, q), *i1 = sycl::malloc_device<uint32_t>(NS * 8, q);
        float *p0 = sycl::malloc_device<float>(NS * 8, q), *p1 = sycl::malloc_device<float>(NS * 8, q);
        std::vector<float> hl2((size_t)NS * E), hb2((size_t)NS * E), hp(NS * 8);
        std::uniform_real_distribution<float> uu(0.f, 1.f);
        const char *pats[10] = {"random", "quantized ties", "all equal", "some NaN", "some +inf", "some -inf", "huge negative",
                                "zero scores, signed-zero bias", "bias ties only", "two values"};
        long sweep_bad = 0;
        for (int pat = 0; pat < 10; ++pat) {
            for (unsigned g = 0; g < NS; ++g)
                for (unsigned e = 0; e < E; ++e) {
                    float l = nd(rng) * 2.0f, bb = nd(rng) * 0.1f;
                    if (pat == 1) { l = std::round(l * 2) / 2; bb = std::round(bb * 20) / 20; }
                    if (pat == 2) { l = 0.5f; bb = 0.0f; }
                    if (pat == 3 && uu(rng) < 0.01f) l = NAN;
                    if (pat == 4 && uu(rng) < 0.02f) l = INFINITY;
                    if (pat == 5 && uu(rng) < 0.5f) l = -INFINITY;
                    if (pat == 6) l = -100.0f - 10.0f * uu(rng);
                    if (pat == 7) { l = -INFINITY; bb = uu(rng) < 0.5f ? 0.0f : -0.0f; }
                    if (pat == 8) { l = 1.0f; bb = std::round(bb * 10) / 10; }
                    if (pat == 9) { l = uu(rng) < 0.3f ? 2.0f : 1.0f; bb = 0.0f; }
                    hl2[(size_t)g * E + e] = l;
                    hb2[(size_t)g * E + e] = bb;
                }
            for (auto &v : hp) v = uu(rng); // the unpicked-rank inputs
            q.memcpy(sl, hl2.data(), hl2.size() * 4);
            q.memcpy(sb, hb2.data(), hb2.size() * 4);
            q.memcpy(p0, hp.data(), hp.size() * 4);
            q.memcpy(p1, hp.data(), hp.size() * 4);
            q.fill(i0, 0xFFFFFFFFu, NS * 8);
            q.fill(i1, 0xFFFFFFFFu, NS * 8).wait();
            auto sweep = [&](auto k, uint32_t *ii, float *pp) {
                q.submit([&](sycl::handler &hh) {
                    sycl::local_accessor<float, 1> lt(2 * 1024 + 6, hh);
                    hh.parallel_for(sycl::nd_range<1>((size_t)NS * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                        k(it, sl, sb, ii, pp, &lt[0]);
                    });
                }).wait();
            };
            sweep(RouteSets<RouteP>{RouteP{(int)E, 6, false}}, i0, p0);
            if (pat == 3) { // NaN scores: RouteP against itself (its rank writes collide, so the winner is a race)
                uint32_t *i2 = sycl::malloc_device<uint32_t>(NS * 8, q);
                float *p2 = sycl::malloc_device<float>(NS * 8, q);
                q.memcpy(p2, hp.data(), hp.size() * 4);
                q.fill(i2, 0xFFFFFFFFu, NS * 8).wait();
                sweep(RouteSets<RouteP>{RouteP{(int)E, 6, false}}, i2, p2);
                std::vector<uint32_t> a0(NS * 8), a2(NS * 8);
                q.memcpy(a0.data(), i0, NS * 32);
                q.memcpy(a2.data(), i2, NS * 32).wait();
                long d2 = 0, coll = 0;
                for (unsigned g = 0; g < NS; ++g) {
                    d2 += std::memcmp(&a0[g * 8], &a2[g * 8], 24) != 0;
                    for (int r = 0; r < 6; ++r) coll += a0[g * 8 + r] == 0xFFFFFFFFu; // a rank nobody wrote
                }
                std::printf("sweep %-30s RouteP vs RouteP: %ld of %u sets differ; %ld ranks never written\n", "some NaN", d2, NS, coll);
                sycl::free(i2, q);
                sycl::free(p2, q);
            }
            sweep(RouteSets<RouteQ>{RouteQ{(int)E, 6}}, i1, p1);
            { // the engine's RouteP with two = true (sycl_v41.hpp run_two) against the same reference
                uint32_t *i3 = sycl::malloc_device<uint32_t>(NS * 8, q);
                float *p3 = sycl::malloc_device<float>(NS * 8, q);
                q.memcpy(p3, hp.data(), hp.size() * 4);
                q.fill(i3, 0xFFFFFFFFu, NS * 8).wait();
                sweep(RouteSets<RouteP>{RouteP{(int)E, 6, true}}, i3, p3);
                std::vector<uint32_t> a0(NS * 8), a3(NS * 8);
                std::vector<float> b0(NS * 8), b3(NS * 8);
                q.memcpy(a0.data(), i0, NS * 32);
                q.memcpy(a3.data(), i3, NS * 32);
                q.memcpy(b0.data(), p0, NS * 32);
                q.memcpy(b3.data(), p3, NS * 32).wait();
                long d3 = 0;
                for (unsigned g = 0; g < NS; ++g)
                    if (std::memcmp(&a0[g * 8], &a3[g * 8], 24) || std::memcmp(&b0[g * 8], &b3[g * 8], 24)) ++d3;
                std::printf("sweep %-30s engine two-stage: %ld of %u sets differ\n", pats[pat], d3, NS);
                if (pat != 3) bad += d3;
                sycl::free(i3, q);
                sycl::free(p3, q);
            }
            std::vector<uint32_t> a0(NS * 8), a1(NS * 8);
            std::vector<float> b0(NS * 8), b1(NS * 8);
            q.memcpy(a0.data(), i0, NS * 32);
            q.memcpy(a1.data(), i1, NS * 32);
            q.memcpy(b0.data(), p0, NS * 32);
            q.memcpy(b1.data(), p1, NS * 32).wait();
            long d = 0;
            for (unsigned g = 0; g < NS; ++g)
                if (std::memcmp(&a0[g * 8], &a1[g * 8], 24) || std::memcmp(&b0[g * 8], &b1[g * 8], 24)) ++d;
            std::printf("sweep %-30s %u sets: %ld differ (first set ids %u %u %u %u %u %u)\n", pats[pat], NS, d,
                        a0[0], a0[1], a0[2], a0[3], a0[4], a0[5]);
            if (pat != 3) sweep_bad += d; // NaN: no defined result (above)
        }
        bad += sweep_bad;
    }
    std::printf("%-42s %10s %10s %10s %10s\n", "form", "median us", "min us", "p10 us", "p90 us");
    for (int v = 0; v < NF; ++v) {
        auto t = tm[v];
        std::sort(t.begin(), t.end());
        std::printf("%-42s %10.2f %10.2f %10.2f %10.2f\n", names[v], t[t.size() / 2], t[0], t[t.size() / 10], t[t.size() * 9 / 10]);
    }
    std::printf(bad ? "FAIL (%ld)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
