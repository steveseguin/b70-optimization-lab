// The sparse attention's softmax folded into the output step: SparseSoftmaxP<640> / SparseSoftmaxPN<640> (one
// sub-group per head: the maximum, exp, the serial sum, the division; 6.5 us per layer in the engine at 640 slots,
// plus a launch) and SparseOutJC<512, 16, 128> (sycl_v41.hpp, OWN_ATT_OUT_C) against one kernel that does both:
//   X  SparseOutJCS<512, 16, CH>: SparseOutJC whose sub-group g first forms head g's weights exactly as the softmax
//      does (the same maximum, exp arguments, serial sum and division; every span's work-group forms them again for
//      itself) into local memory, while the first chunk's row pieces load; then SparseOutJC's sums.
// One card, GPU time of each launch; out and ry compared BITWISE with softmax + SparseOutJB<512, 1, 16> (the engine
// before OWN_ATT_OUT_C). Raw scores: normal * 2 (and signed with -1 slots, NaN scores on some of them, or a -1
// tail); sinks normal; 640 / 160 / 128 slots (128: SparseSoftmaxP<128>); 16 and 8 heads.
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_sparse_out_fused.cpp -o bench_sparse_out_fused
//   ONEAPI_DEVICE_SELECTOR=level_zero:1 ./bench_sparse_out_fused
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

template <unsigned HD, unsigned HG_, unsigned CH, unsigned MAXI = 640, unsigned U = 16> struct SparseOutJCS {
    static constexpr unsigned HG = HG_, PER_HEAD = HD / 32, LP = CH / HG, NK = CH / 32, KI = MAXI / 32;
    static constexpr size_t RW = 2 * (size_t)CH * 32, SLM = RW + (size_t)HG * MAXI, WG = 32 * (size_t)HG;
    static_assert(HD % 32 == 0 && CH % 32 == 0 && CH % HG == 0 && LP >= 1 && LP <= 32 && 32 % U == 0 && MAXI % 32 == 0);
    int n_idx, heads, win_rows; // n_idx % 32 == 0, <= MAXI
    float *ry = nullptr;
    const float *cosb = nullptr, *sinb = nullptr;
    static size_t groups(int heads) { return (size_t)PER_HEAD * (size_t)((heads + (int)HG - 1) / (int)HG); }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *score, const float *sinks, float *out, uint32_t *lm) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned grp = (unsigned)it.get_group_linear_id(), lane = sg.get_local_linear_id(), g = sg.get_group_linear_id();
        const unsigned base = (grp % PER_HEAD) * 32;
        const int h = (int)((grp / PER_HEAD) * HG + g);
        const bool act = h < heads;
        const int n = n_idx, wr = win_rows, nch = (n + (int)CH - 1) / (int)CH;
        float *wts = reinterpret_cast<float *>(lm + RW) + (size_t)g * MAXI;
        auto row_addr = [&](int slot) {
            const int s0 = slot < 0 ? 0 : slot;
            return (s0 < wr ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - wr) * HD) + base;
        };
        auto lslots = [&](int c) {
            const int i = c * (int)CH + (int)(g * LP + lane);
            return lane < LP && i < n ? idxs[i] : -1;
        };
        uint16_t pc[LP];
        auto issue = [&](int c, int ls) {
#pragma unroll
            for (unsigned u = 0; u < LP; ++u)
                if (c * (int)CH + (int)(g * LP + u) < n) pc[u] = sg_bloadN<1>(sg, row_addr(sycl::select_from_group(sg, ls, u)))[0];
        };
        auto put = [&](int c) {
            uint32_t *b = lm + (size_t)(c & 1) * CH * 32;
#pragma unroll
            for (unsigned u = 0; u < LP; ++u)
                if (c * (int)CH + (int)(g * LP + u) < n) b[(g * LP + u) * 32 + lane] = (uint32_t)pc[u] << 16;
        };
        int csl[NK], nsl[NK];
        float cwl[NK], nwl[NK];
        auto lw = [&](int c, int (&s)[NK], float (&x)[NK]) {
#pragma unroll
            for (unsigned k = 0; k < NK; ++k) {
                const int i = c * (int)CH + (int)(32 * k + lane);
                const bool in = c * (int)CH + (int)(32 * k) < n;
                s[k] = in ? idxs[i] : -1;
                x[k] = in ? wts[i] : 0.0f;
            }
        };
        int ls = lslots(0);
        issue(0, ls);
        if (act) { // SparseSoftmaxPN<MAXI>'s arithmetic (= SparseSoftmaxP<n> when n == MAXI or 128)
            const int kn = n / 32;
            const float *s = score + (size_t)h * n;
            float v[KI];
            int ok[KI];
            const float sk = sinks[h];
            float mx = sk;
#pragma unroll
            for (unsigned k = 0; k < KI; ++k) {
                ok[k] = 0;
                v[k] = 0;
                if ((int)k < kn) {
                    ok[k] = idxs[32 * k + lane] >= 0 ? 1 : 0;
                    v[k] = s[32 * k + lane];
                }
                if (ok[k]) mx = v[k] > mx ? v[k] : mx;
            }
            for (int w_ = 16; w_; w_ >>= 1) {
                const float o = sycl::select_from_group(sg, mx, (int)lane ^ w_);
                mx = o > mx ? o : mx;
            }
            float sum = sycl::exp(sk - mx);
            float e0[KI];
#pragma unroll
            for (unsigned k = 0; k < KI; ++k) {
                if (ok[k]) v[k] = sycl::exp(v[k] - mx);
                e0[k] = ok[k] ? v[k] : 0.0f;
            }
#pragma unroll
            for (unsigned k = 0; k < KI; ++k)
                if ((int)k < kn)
#pragma unroll
                    for (int l2 = 0; l2 < 32; ++l2) sum += sycl::select_from_group(sg, e0[k], l2);
#pragma unroll
            for (unsigned k = 0; k < KI; ++k)
                if ((int)k < kn) wts[32 * k + lane] = ok[k] ? v[k] / sum : 0.0f;
        }
        if (nch > 1) ls = lslots(1);
        put(0);
        sycl::group_barrier(it.get_group());
        lw(0, csl, cwl);
        float o = 0;
        for (int c = 0; c < nch; ++c) {
            const bool more = c + 1 < nch;
            if (more) {
                issue(c + 1, ls);
                lw(c + 1, nsl, nwl);
                if (c + 2 < nch) ls = lslots(c + 2);
            }
            if (act) {
                const uint32_t *b = lm + (size_t)(c & 1) * CH * 32;
#pragma unroll
                for (unsigned k = 0; k < NK; ++k) {
                    if (c * (int)CH + (int)(32 * k) >= n) break;
#pragma unroll
                    for (unsigned u0 = 0; u0 < 32; u0 += U) {
                        uint32_t x[U];
#pragma unroll
                        for (unsigned u = 0; u < U; ++u) x[u] = b[(32 * k + u0 + u) * 32 + lane];
#pragma unroll
                        for (unsigned u = 0; u < U; ++u) {
                            const bool ok = sycl::select_from_group(sg, csl[k], u0 + u) >= 0;
                            const float p0 = sycl::select_from_group(sg, cwl[k], u0 + u) * sycl::bit_cast<float>(x[u]);
                            o += ok ? p0 : -0.0f;
                        }
                    }
                }
            }
            if (more) {
                put(c + 1);
#pragma unroll
                for (unsigned k = 0; k < NK; ++k) {
                    csl[k] = nsl[k];
                    cwl[k] = nwl[k];
                }
            }
            sycl::group_barrier(it.get_group());
        }
        const float pr = sycl::select_from_group(sg, o, lane ^ 1u);
        if (!act) return;
        out[(size_t)h * HD + base + lane] = o;
        if (ry) {
            float a = o;
            if (base >= HD - 64) {
                const unsigned i = (base - (HD - 64) + lane) / 2;
                const float cs = cosb[i], sn = -sinb[i];
                if (lane & 1) {
                    const float re = pr, im = o;
                    a = re * sn + im * cs;
                } else {
                    const float re = o, im = pr;
                    a = re * cs - im * sn;
                }
            }
            ry[(size_t)h * HD + base + lane] = a;
        }
    }
};

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    constexpr unsigned HD = 512, W = 128, CROWS = 24000, MAXH = 16, MAXI = 640;
    uint16_t *kvw = sycl::malloc_device<uint16_t>((size_t)W * HD, q), *kvc = sycl::malloc_device<uint16_t>((size_t)CROWS * HD, q);
    int32_t *ix = sycl::malloc_device<int32_t>(MAXI, q);
    float *sc = sycl::malloc_device<float>((size_t)MAXH * MAXI, q), *wt = sycl::malloc_device<float>((size_t)MAXH * MAXI, q);
    float *sk = sycl::malloc_device<float>(MAXH, q), *cs = sycl::malloc_device<float>(64, q);
    constexpr int NF = 4;
    float *ob[NF], *yb[NF];
    for (int f = 0; f < NF; ++f) {
        ob[f] = sycl::malloc_device<float>((size_t)MAXH * HD, q);
        yb[f] = sycl::malloc_device<float>((size_t)MAXH * HD, q);
    }
    std::mt19937 rng(13);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::uniform_int_distribution<int> ue(-12, 8);
    auto bf = [](float f) { uint32_t u; std::memcpy(&u, &f, 4); return (uint16_t)(u >> 16); };
    {
        std::vector<uint16_t> hw((size_t)W * HD), hc((size_t)CROWS * HD);
        for (auto &v : hw) v = bf(nd(rng) * std::ldexp(1.0f, ue(rng)));
        for (auto &v : hc) v = bf(nd(rng) * std::ldexp(1.0f, ue(rng)));
        q.memcpy(kvw, hw.data(), hw.size() * 2);
        q.memcpy(kvc, hc.data(), hc.size() * 2).wait();
        std::vector<float> hcs(64), hs(MAXH);
        for (auto &v : hcs) v = nd(rng);
        for (auto &v : hs) v = nd(rng);
        q.memcpy(cs, hcs.data(), 64 * 4);
        q.memcpy(sk, hs.data(), MAXH * 4).wait();
    }
    auto sgl = [&](auto k, size_t groups, auto... a) {
        return q.parallel_for(sycl::nd_range<1>(groups * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, a...); });
    };
    auto wgl = [&](auto k, size_t groups, auto... a) {
        using K = decltype(k);
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<uint32_t, 1> lt(K::SLM, h);
            h.parallel_for(sycl::nd_range<1>(groups * K::WG, K::WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k(it, a..., &lt[0]);
            });
        });
    };
    auto set = [&](auto k, int f) {
        k.ry = yb[f];
        k.cosb = cs;
        k.sinb = cs + 32;
        return k;
    };
    // the softmax as the engine launches it (in place on wt)
    auto smx = [&](int n, int heads) -> sycl::event {
        if (n == 640) return sgl(SparseSoftmaxP<640>{heads}, (size_t)heads, (const float *)sk, (const int32_t *)ix, wt);
        if (n == 128) return sgl(SparseSoftmaxP<128>{heads}, (size_t)heads, (const float *)sk, (const int32_t *)ix, wt);
        return sgl(SparseSoftmaxPN<640>{heads, n}, (size_t)heads, (const float *)sk, (const int32_t *)ix, wt);
    };
    const char *names[NF] = {"A softmax + SparseOutJB<512,1,16> (engine before OWN_ATT_OUT_C)", "C softmax + SparseOutJC<512,16,128>",
                             "X SparseOutJCS<512,16,128> (softmax inside)", "X SparseOutJCS<512,16,64>"};
    auto run = [&](int f, int n, int heads) -> sycl::event { // the output launch (forms 0, 1 read wt)
        using C128 = SparseOutJC<HD, 16, 128>;
        switch (f) {
        case 0: return sgl(set(SparseOutJB<HD, 1, 16>{n, heads, (int)W}, 0), (size_t)heads * HD / 64, (const uint16_t *)kvw, (const uint16_t *)kvc, (const int32_t *)ix, (const float *)wt, ob[0]);
        case 1: return wgl(set(C128{n, heads, (int)W}, 1), C128::groups(heads), (const uint16_t *)kvw, (const uint16_t *)kvc, (const int32_t *)ix, (const float *)wt, ob[1]);
        case 2: return wgl(set(SparseOutJCS<HD, 16, 128>{n, heads, (int)W}, 2), SparseOutJCS<HD, 16, 128>::groups(heads), (const uint16_t *)kvw, (const uint16_t *)kvc, (const int32_t *)ix, (const float *)sc, (const float *)sk, ob[2]);
        default: return wgl(set(SparseOutJCS<HD, 16, 64>{n, heads, (int)W}, 3), SparseOutJCS<HD, 16, 64>::groups(heads), (const uint16_t *)kvw, (const uint16_t *)kvc, (const int32_t *)ix, (const float *)sc, (const float *)sk, ob[3]);
        }
    };
    q.fill(ix, 5, MAXI);
    q.fill(sc, 0.5f, (size_t)MAXH * MAXI);
    q.fill(wt, 0.001f, (size_t)MAXH * MAXI).wait();
    for (int r = 0; r < 400; ++r) run(r % NF, 640, 16); // warm-up (valid slots)
    q.wait();
    const char *kinds[3] = {"scores", "signed, -1 slots, NaNs", "list tail -1"};
    long bad = 0;
    std::printf("%-24s %4s %5s | %7s | %13s | %13s | %13s %13s\n", "list", "n", "heads", "softmax", "A: + JB", "C: + JC",
                "X128", "X64");
    for (int kind = 0; kind < 3; ++kind)
        for (int n : {640, 160, 128})
            for (int heads : {16, 8}) {
                std::vector<int32_t> hi(MAXI);
                for (int i = 0; i < 128; ++i) hi[i] = i;
                {
                    std::vector<int> rows(CROWS);
                    for (int r = 0; r < (int)CROWS; ++r) rows[r] = r;
                    std::shuffle(rows.begin(), rows.end(), rng);
                    std::sort(rows.begin(), rows.begin() + 512);
                    for (int i = 0; i < 512; ++i) hi[128 + i] = 128 + rows[i];
                }
                if (n == 160) for (int i = 128 + 25; i < 160; ++i) hi[i] = -1;
                if (kind == 1) for (int i = 0; i < n; ++i) if (rng() % 5 == 0) hi[i] = -1;
                if (kind == 2 && n == 640) for (int i = 640 - 97; i < 640; ++i) hi[i] = -1;
                std::vector<float> hs((size_t)MAXH * MAXI);
                for (int h = 0; h < heads; ++h)
                    for (int i = 0; i < n; ++i) {
                        float v = 2.0f * nd(rng);
                        if (kind == 1 && hi[i] < 0 && i % 3 == 0) v = std::nanf("");
                        hs[(size_t)h * n + i] = v;
                    }
                q.memcpy(ix, hi.data(), MAXI * 4);
                q.memcpy(sc, hs.data(), hs.size() * 4).wait();
                for (int f = 0; f < NF; ++f) {
                    q.fill(ob[f], -7.0f, (size_t)MAXH * HD);
                    q.fill(yb[f], -7.0f, (size_t)MAXH * HD);
                }
                q.wait();
                const int REP = kind == 0 ? 60 : 6;
                std::vector<double> ts;
                std::vector<std::vector<double>> t(NF);
                for (int r = 0; r <= REP; ++r) {
                    q.memcpy(wt, sc, (size_t)MAXH * MAXI * 4).wait();
                    auto e = smx(n, heads);
                    e.wait();
                    if (r) ts.push_back(ev_us(e));
                    for (int f = 0; f < NF; ++f) {
                        auto e2 = run(f, n, heads);
                        e2.wait();
                        if (r) t[f].push_back(ev_us(e2));
                    }
                }
                auto med = [](std::vector<double> v) { std::sort(v.begin(), v.end()); return v[v.size() / 2]; };
                std::vector<float> ro((size_t)heads * HD), ryr((size_t)heads * HD), x((size_t)heads * HD), yy((size_t)heads * HD);
                q.memcpy(ro.data(), ob[0], ro.size() * 4);
                q.memcpy(ryr.data(), yb[0], ryr.size() * 4).wait();
                bool same[NF] = {true, true, true, true};
                for (int f = 1; f < NF; ++f) {
                    q.memcpy(x.data(), ob[f], x.size() * 4);
                    q.memcpy(yy.data(), yb[f], yy.size() * 4).wait();
                    same[f] = !std::memcmp(x.data(), ro.data(), x.size() * 4) && !std::memcmp(yy.data(), ryr.data(), yy.size() * 4);
                    bad += !same[f];
                }
                const double s0 = med(ts);
                std::printf("%-24s %4d %5d | %7.1f | %5.1f (%5.1f) | %5.1f (%5.1f) %s | %5.1f %s     %5.1f %s\n", kinds[kind], n, heads, s0,
                            med(t[0]), s0 + med(t[0]), med(t[1]), s0 + med(t[1]), same[1] ? "y" : "NO", med(t[2]), same[2] ? "y" : "NO",
                            med(t[3]), same[3] ? "y" : "NO");
            }
    std::printf("(median us per launch; in brackets with the softmax launch; y = out and ry bitwise = A)\nforms:\n");
    for (int f = 0; f < NF; ++f) std::printf("  %s\n", names[f]);
    std::printf(bad ? "FAIL (%ld differ)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
