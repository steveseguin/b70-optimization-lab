// RMS norm with a fast bracket of the double chain (round 18 n1): RmsNormPS<5120, 4>::part forms
// acc = sum of double(x) * x in double, per lane 160 terms in order then the xor tree, and rs = float(1.0 /
// sqrt(acc / N + 1e-20)). Its launch with the stream-mix dots is 14.6 us per call in the engine's answer steps (77
// per step). Found here (n5, back-to-back timing): alone the chain costs ~1 us over the launch's floor, but in the
// engine's launch the double-precision work of 16 rows per work-group sits on 13 of the 32 cores; in smaller
// work-groups the norm's four redundant chains then set the pace, and the fast form removes them (9.9 -> 6.0 us).
// rs_of(acc) = float(1.0 / sqrt(acc / N + 1e-20)) is a
// composition of correctly rounded monotone operations, so it is monotone (non-increasing) in acc: if a fast
// estimate s with a proven bound |acc - s| <= B gives rs_of(s - B) == rs_of(s + B), that float IS the chain's rs.
// Otherwise (rare) the double chain runs. Same outputs bit for bit by construction; this bench checks it.
// Fast estimate per lane: blocks of 16 terms in float-float (TwoProduct by fma, TwoSum, the low parts summed in
// float), each block's (hi, lo) added in double (10 per lane), then the same xor tree in double.
// Bound (all terms >= 0, E = the exact sum, u = 2^-24, v = 2^-53): per block of k = 16 terms the low sum's
// rounding <= k(k+1) u^2 E_b (9.7e-13 E_b at k = 16); block sums in double <= 22 v E (21 adds incl. conversions); tree <= 5 v E; the
// chain itself <= 165 v E. Total < 1.0e-12 E; the bracket uses 4e-12 s + 1e-30 and needs 1e-25 < s < 1e30
// (else the chain runs: no float overflow / underflow in the terms).
//   A  engine launch: RowsP<RowsPair<NormRows<5120, 4>, HcDotsRows<5120, 8>>> (204 rows, 13 work-groups of 16)
//   B  RowsP<NormRows<5120, 4>> alone        C  RowsP<HcDotsRows<5120, 8>> alone
//   D  A with the fast norm (this file's copy, V1)
//   E0-E3  the fast norm alone: V0 (two roots), V1, V1 without the fallback, the fast sum without a check (floor)
//   F / G  B / A with the ENGINE's RmsNormPS::part(ff = true) (sycl_v41.hpp)   H / I  1,280 wide, chain / engine ff
//   J-O  A, G and C in work-groups of 4 or 2 rows (launch_rows<0, 128 / 64>): the same rows on the same sub-group code
// Timing: forms interleaved back to back (the card busy, as in the engine); medians are stable then, and only then
// (a wait after every launch let the card idle and the medians moved by up to 2x between runs).
// Bulk check: 2^16 random vectors per round (one sub-group each), V1 and V0 against the chain's rs, bitwise, with
// the fallback counts; plus edge sets (tiny, huge, sparse, one big value, constant vectors, mixed tiny). NOBULK=1
// skips it.
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_norm_ff.cpp -o $S/bench_norm_ff
//   ONEAPI_DEVICE_SELECTOR=level_zero:1 $S/bench_norm_ff
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

static constexpr unsigned N = 5120, C = N / 256;

// the fast part (same interface as RmsNormPS<N, S>::part); fb (optional) counts fallbacks
// V = 0: both ends of the bracket through rs_of (two double square roots and divisions); V = 1: one rs_of at s,
// then s's double D = 1 / sqrt(s / N + 1e-20) must lie farther than 4e-12 D from the midpoints between float(D) and
// its float neighbours (the bracket moves D by at most 0.5 * 4e-12 D plus four double roundings, so the chain's D
// rounds to the same float); V = 2: V = 1 without the fallback (timing only); V = 3: the fast sum, no check
// (timing floor, not exact).
template <unsigned NN, unsigned S, unsigned V = 1> struct RmsNormFF {
    static constexpr unsigned CC = NN / 256;
    static inline float rs_of(double acc) { return float(1.0 / sycl::sqrt(acc / NN + 1e-20)); }
    [[gnu::always_inline]] static inline float rs_fast(sycl::sub_group sg, unsigned lane, const float *x, bool &ok) {
        double acc = 0;
#pragma unroll
        for (unsigned c2 = 0; c2 < CC; c2 += 2) { // blocks of 16 terms: chunks c2, c2 + 1
            float hi = 0, lo = 0;
#pragma unroll
            for (unsigned h = 0; h < 2 && c2 + h < CC; ++h) {
                const auto xv = sg_bloadN<8>(sg, x + (c2 + h) * 256);
#pragma unroll
                for (unsigned m = 0; m < 8; ++m) {
                    const float a = xv[m];
                    const float p = a * a;
                    const float e = sycl::fma(a, a, -p);
                    const float t = hi + p;
                    const float z = t - hi;
                    const float er = (hi - (t - z)) + (p - z);
                    hi = t;
                    lo = lo + (er + e);
                }
            }
            acc = acc + double(hi);
            acc = acc + double(lo);
        }
        for (int w_ = 16; w_; w_ >>= 1) acc += sycl::select_from_group(sg, acc, (int)lane ^ w_);
        if constexpr (V == 3) {
            ok = true;
            return rs_of(acc);
        } else if constexpr (V == 0) {
            ok = acc > 1e-25 && acc < 1e30;
            const double b = acc * 4e-12 + 1e-30;
            const float r0 = rs_of(acc - b), r1 = rs_of(acc + b);
            ok = ok && r0 == r1;
            return r0;
        } else {
            const double D = 1.0 / sycl::sqrt(acc / NN + 1e-20);
            const float f = float(D);
            const double fd = f, up = sycl::nextafter(f, INFINITY), dn = sycl::nextafter(f, 0.0f);
            ok = acc > 1e-25 && acc < 1e30 && D * (1 + 4e-12) < fd + (up - fd) * 0.5 && D * (1 - 4e-12) > fd - (fd - dn) * 0.5;
            return f;
        }
    }
    [[gnu::always_inline]] static inline float rs_chain(sycl::sub_group sg, unsigned lane, const float *x) {
        double acc = 0;
#pragma unroll
        for (unsigned c = 0; c < CC; ++c) {
            const auto xv = sg_bloadN<8>(sg, x + c * 256);
#pragma unroll
            for (unsigned m = 0; m < 8; ++m) acc += double(xv[m]) * xv[m];
        }
        for (int w_ = 16; w_; w_ >>= 1) acc += sycl::select_from_group(sg, acc, (int)lane ^ w_);
        return rs_of(acc);
    }
    [[gnu::always_inline]] static inline void part(sycl::sub_group sg, unsigned lane, unsigned sgi, const float *x,
                                                   const float *w, float *y, unsigned *fb = nullptr) {
        bool ok;
        float rs = rs_fast(sg, lane, x, ok);
        if constexpr (V < 2)
            if (!ok) {
                rs = rs_chain(sg, lane, x);
                if (fb && lane == 0) sycl::atomic_ref<unsigned, sycl::memory_order::relaxed, sycl::memory_scope::device>(*fb)++;
            }
#pragma unroll
        for (unsigned c = 0; c < CC; ++c) {
            if (c % S != sgi) continue;
            const auto xv = sg_bloadN<8>(sg, x + c * 256);
            const auto wv = sg_bloadN<8>(sg, w + c * 256);
            sycl::vec<float, 8> o;
#pragma unroll
            for (unsigned m = 0; m < 8; ++m) o[m] = wv[m] * (xv[m] * rs);
            sg.store<8>(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                            y + c * 256), o);
        }
    }
};
template <unsigned NN, unsigned S, unsigned V = 1> struct NormRowsFF {
    const float *x, *w;
    float *y;
    unsigned n() const { return S; }
    [[gnu::always_inline]] inline void row(sycl::sub_group sg, unsigned lane, unsigned r) const {
        RmsNormFF<NN, S, V>::part(sg, lane, r, x, w, y);
    }
};

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
// the engine's launch_rows: WG items per work-group (512 = 16 rows); rows map to sub-groups in the same order
template <size_t WG = 512, typename K> static sycl::event rows_launch(sycl::queue &q, K k, size_t rows) {
    constexpr size_t PER = WG / 32;
    const size_t nwg = (rows + PER - 1) / PER;
    return q.parallel_for(sycl::nd_range<1>(nwg * WG, WG),
                          [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it); });
}

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    constexpr unsigned SEG = 8;
    float *x = sycl::malloc_device<float>(N, q), *w = sycl::malloc_device<float>(N, q);
    float *streams = sycl::malloc_device<float>(4 * N, q), *fn = sycl::malloc_device<float>(24 * 4 * N, q);
    constexpr int NF = 18;
    float *y[NF];
    double *d[NF];
    for (auto &p : y) p = sycl::malloc_device<float>(N, q);
    for (auto &p : d) p = sycl::malloc_device<double>(25 * SEG, q);
    std::mt19937 rng(5);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::uniform_int_distribution<int> ue(-20, 20);
    std::vector<float> hx(N), hw(N), hs(4 * N), hf(24 * 4 * N);
    for (auto &v : hs) v = nd(rng);
    for (auto &v : hf) v = nd(rng) * 0.01f;
    q.memcpy(streams, hs.data(), hs.size() * 4);
    q.memcpy(fn, hf.data(), hf.size() * 4).wait();
    const char *names[NF] = {"A engine: norm + stream-mix dots", "B norm alone", "C stream-mix dots alone",
                             "D A with the fast norm (V1)", "E0 fast norm alone, two rs (V0)", "E1 fast norm alone (V1)",
                             "E2 V1 without fallback (timing)", "E3 fast sum, no check (floor)",
                             "F engine NormRows, ff (alone)", "G engine fused launch, ff", "H 1280 wide, chain", "I 1280 wide, engine ff",
                             "J A in work-groups of 4 rows", "K A in work-groups of 2 rows", "L G in work-groups of 4 rows",
                             "M G in work-groups of 2 rows", "N C in work-groups of 4 rows", "O C in work-groups of 2 rows"};
    auto run = [&](int v) -> sycl::event {
        HcDotsRows<N, SEG> hd{streams, fn, d[v]};
        switch (v) {
        case 0: return rows_launch(q, RowsP<RowsPair<NormRows<N, 4>, HcDotsRows<N, SEG>>>{{NormRows<N, 4>{x, w, y[0]}, hd}}, 4 + 25 * SEG);
        case 1: return rows_launch(q, RowsP<NormRows<N, 4>>{NormRows<N, 4>{x, w, y[1]}}, 4);
        case 2: return rows_launch(q, RowsP<HcDotsRows<N, SEG>>{hd}, 25 * SEG);
        case 3: return rows_launch(q, RowsP<RowsPair<NormRowsFF<N, 4>, HcDotsRows<N, SEG>>>{{NormRowsFF<N, 4>{x, w, y[3]}, hd}}, 4 + 25 * SEG);
        case 4: return rows_launch(q, RowsP<NormRowsFF<N, 4, 0>>{NormRowsFF<N, 4, 0>{x, w, y[4]}}, 4);
        case 5: return rows_launch(q, RowsP<NormRowsFF<N, 4, 1>>{NormRowsFF<N, 4, 1>{x, w, y[5]}}, 4);
        case 6: return rows_launch(q, RowsP<NormRowsFF<N, 4, 2>>{NormRowsFF<N, 4, 2>{x, w, y[6]}}, 4);
        case 7: return rows_launch(q, RowsP<NormRowsFF<N, 4, 3>>{NormRowsFF<N, 4, 3>{x, w, y[7]}}, 4);
        case 8: return rows_launch(q, RowsP<NormRows<N, 4>>{NormRows<N, 4>{x, w, y[8], true}}, 4);
        case 9: return rows_launch(q, RowsP<RowsPair<NormRows<N, 4>, HcDotsRows<N, SEG>>>{{NormRows<N, 4>{x, w, y[9], true}, hd}}, 4 + 25 * SEG);
        case 10: return rows_launch(q, RowsP<NormRows<1280, 4>>{NormRows<1280, 4>{x, w, y[10], false}}, 4);
        case 11: return rows_launch(q, RowsP<NormRows<1280, 4>>{NormRows<1280, 4>{x, w, y[11], true}}, 4);
        case 12: return rows_launch<128>(q, RowsP<RowsPair<NormRows<N, 4>, HcDotsRows<N, SEG>>>{{NormRows<N, 4>{x, w, y[12], false}, hd}}, 4 + 25 * SEG);
        case 13: return rows_launch<64>(q, RowsP<RowsPair<NormRows<N, 4>, HcDotsRows<N, SEG>>>{{NormRows<N, 4>{x, w, y[13], false}, hd}}, 4 + 25 * SEG);
        case 14: return rows_launch<128>(q, RowsP<RowsPair<NormRows<N, 4>, HcDotsRows<N, SEG>>>{{NormRows<N, 4>{x, w, y[14], true}, hd}}, 4 + 25 * SEG);
        case 15: return rows_launch<64>(q, RowsP<RowsPair<NormRows<N, 4>, HcDotsRows<N, SEG>>>{{NormRows<N, 4>{x, w, y[15], true}, hd}}, 4 + 25 * SEG);
        case 16: return rows_launch<128>(q, RowsP<HcDotsRows<N, SEG>>{hd}, 25 * SEG);
        default: return rows_launch<64>(q, RowsP<HcDotsRows<N, SEG>>{hd}, 25 * SEG);
        }
    };
    long bad = 0;
    std::vector<double> tm[NF];
    for (int set = 0; set < 8; ++set) {
        for (unsigned i = 0; i < N; ++i) {
            hx[i] = nd(rng) * std::ldexp(1.0f, ue(rng));
            hw[i] = nd(rng);
        }
        q.memcpy(x, hx.data(), N * 4);
        q.memcpy(w, hw.data(), N * 4).wait();
        for (int v = 0; v < NF; ++v) q.fill(y[v], -7.0f, N);
        q.wait();
        // back to back (the card stays busy, as in the engine), forms interleaved; GPU time of each launch
        std::vector<std::pair<int, sycl::event>> evs;
        for (int r = 0; r < 26; ++r)
            for (int v = 0; v < NF; ++v) {
                auto e = run(v);
                if (r) evs.push_back({v, e});
            }
        q.wait();
        for (auto &[v, e] : evs) tm[v].push_back(ev_us(e));
        std::vector<float> ref(N), o(N);
        q.memcpy(ref.data(), y[0], N * 4).wait();
        for (int v : {1, 3, 4, 5, 8, 9, 12, 13, 14, 15}) {
            q.memcpy(o.data(), y[v], N * 4).wait();
            if (std::memcmp(ref.data(), o.data(), N * 4)) { ++bad; std::printf("set %d: %s norm DIFFERS\n", set, names[v]); }
        }
        {
            std::vector<float> r1(1280), o1(1280);
            q.memcpy(r1.data(), y[10], 1280 * 4);
            q.memcpy(o1.data(), y[11], 1280 * 4).wait();
            if (std::memcmp(r1.data(), o1.data(), 1280 * 4)) { ++bad; std::printf("set %d: 1280 ff norm DIFFERS\n", set); }
        }
        std::vector<double> dr(25 * SEG), dv(25 * SEG);
        q.memcpy(dr.data(), d[0], dr.size() * 8).wait();
        for (int v : {2, 3, 9, 12, 13, 14, 15, 16, 17}) {
            q.memcpy(dv.data(), d[v], dv.size() * 8).wait();
            if (std::memcmp(dr.data(), dv.data(), dr.size() * 8)) { ++bad; std::printf("set %d: %s dots DIFFER\n", set, names[v]); }
        }
    }
    std::printf("%-42s %10s %10s %10s %10s\n", "form", "median us", "min us", "p10 us", "p90 us");
    for (int v = 0; v < NF; ++v) {
        auto t = tm[v];
        std::sort(t.begin(), t.end());
        std::printf("%-42s %10.2f %10.2f %10.2f %10.2f\n", names[v], t[t.size() / 2], t[0], t[t.size() / 10], t[t.size() * 9 / 10]);
    }

    if (std::getenv("NOBULK")) { // timing only
        std::printf(bad ? "FAIL (%ld)\n" : "PASS (no bulk check)\n", bad);
        return bad ? 1 : 0;
    }
    // bulk: NV vectors, one sub-group each; rs of the fast part (with fallback) against the chain, bitwise
    constexpr unsigned NV = 1u << 16, ROUNDS = 16;
    float *bx = sycl::malloc_device<float>((size_t)NV * N, q);
    float *rf = sycl::malloc_device<float>(NV, q), *rc = sycl::malloc_device<float>(NV, q);
    float *rf0 = sycl::malloc_device<float>(NV, q);
    unsigned *fb = sycl::malloc_device<unsigned>(2, q);
    long total = 0, mism = 0, fbs = 0, fbs0 = 0;
    std::vector<float> hb((size_t)NV * N), h1(NV), h2(NV);
    for (unsigned round = 0; round < ROUNDS + 6; ++round) {
        // rounds 0..15: random magnitudes (spread 2^-k..2^k, k by round); then edge kinds
        const int spread = round < ROUNDS ? (int)(round % 8) * 4 : 0;
        std::uniform_int_distribution<int> ur(-spread, spread);
        for (size_t i = 0; i < (size_t)NV * N; ++i) hb[i] = nd(rng) * std::ldexp(1.0f, ur(rng));
        if (round >= ROUNDS) {
            const unsigned kind = round - ROUNDS;
            for (unsigned vct = 0; vct < NV; ++vct) {
                float *p = &hb[(size_t)vct * N];
                if (kind == 0) for (unsigned i = 0; i < N; ++i) p[i] *= 1e-22f;             // tiny: fallback
                if (kind == 1) for (unsigned i = 0; i < N; ++i) p[i] *= 1e17f;              // huge
                if (kind == 2) for (unsigned i = 0; i < N; ++i) p[i] = (i % 97 == 0) ? p[i] : 0.0f; // sparse
                if (kind == 3) { for (unsigned i = 0; i < N; ++i) p[i] *= 1e-3f; p[vct % N] = 50.0f; } // one big
                if (kind == 4) { const float cst = 1.0f + (float)vct * 1e-6f; for (unsigned i = 0; i < N; ++i) p[i] = cst; }
                if (kind == 5) for (unsigned i = 0; i < N; ++i) p[i] = (vct & 1) ? p[i] * 1e-8f : p[i]; // small terms
            }
        }
        q.memcpy(bx, hb.data(), hb.size() * 4);
        q.fill(fb, 0u, 2).wait();
        q.parallel_for(sycl::nd_range<1>((size_t)NV * 32, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            sycl::sub_group sg = it.get_sub_group();
            const unsigned lane = sg.get_local_linear_id();
            const size_t vct = it.get_global_linear_id() / 32;
            const float *xp = bx + vct * N;
            bool ok, ok0;
            float r = RmsNormFF<N, 4, 1>::rs_fast(sg, lane, xp, ok);
            float r0 = RmsNormFF<N, 4, 0>::rs_fast(sg, lane, xp, ok0);
            const float rr = RmsNormFF<N, 4>::rs_chain(sg, lane, xp);
            if (!ok) {
                r = rr;
                if (lane == 0) sycl::atomic_ref<unsigned, sycl::memory_order::relaxed, sycl::memory_scope::device>(fb[0])++;
            }
            if (!ok0) {
                r0 = rr;
                if (lane == 0) sycl::atomic_ref<unsigned, sycl::memory_order::relaxed, sycl::memory_scope::device>(fb[1])++;
            }
            if (lane == 0) { rf[vct] = r; rc[vct] = rr; rf0[vct] = r0; }
        }).wait();
        unsigned hfb2[2] = {0, 0};
        q.memcpy(hfb2, fb, 8);
        std::vector<float> h0(NV);
        q.memcpy(h0.data(), rf0, NV * 4);
        q.memcpy(h1.data(), rf, NV * 4);
        q.memcpy(h2.data(), rc, NV * 4).wait();
        long mm = 0, mm0 = 0;
        for (unsigned i = 0; i < NV; ++i) { mm += std::memcmp(&h1[i], &h2[i], 4) != 0; mm0 += std::memcmp(&h0[i], &h2[i], 4) != 0; }
        total += NV; mism += mm + mm0; fbs += hfb2[0]; fbs0 += hfb2[1];
        std::printf("bulk round %2u (%s %d): %u vectors, V1 rs differs %ld, fallbacks %u; V0 differs %ld, fallbacks %u\n", round,
                    round < ROUNDS ? "spread 2^" : "edge kind", round < ROUNDS ? spread : (int)(round - ROUNDS), NV, mm, hfb2[0], mm0, hfb2[1]);
    }
    std::printf("bulk: %ld vectors, %ld differ (V1 + V0), V1 fallbacks %ld, V0 fallbacks %ld\n", total, mism, fbs, fbs0);
    bad += mism;
    std::printf(bad ? "FAIL (%ld)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
