// The register selects (OWN_TOPK_Q: TopKSelQ / TopKSelCQ / TopKSelBQ, sycl_v41.hpp) against the selects they
// replace, bit for bit, and GPU time of each, on one card, at the engine's lengths:
//   plain     top 512 of n (+128):          TopKSelP<false> (reference), TopKSelR<false>, TopKSelQ
//   masked    the same with the block mask: TopKSelP<false> (reference), TopKSelR<false>, TopKSelQ
//   block     block 8, top 2048, newest +inf; mask rows + block list: TopKSelP<true> (reference), TopKSelBQ
//   cand      the masked select over the candidate rows of that block list: TopKSelC (reference),
//             TopKSelC with rwalk, TopKSelCQ (and their fallback when fewer than 512 candidates are above -inf)
// Lengths up to 139,000 rows: past 131,072 rows the block select is TopKSelBQ<32>; past 98,304 the row selects
// fall back to TopKSelR (as the engine does). Score arrays: normal values, a few values (heavy ties), +0 / -0, mostly -inf, NaNs of both signs mixed in.
// (Round 18 q1-q3 also timed forms that keep TopKSelR's passes over memory: loads issued 8 at a time, and the
// local adds folded per sub-group with a ballot; both slower. The four passes' loads were ~55 % of TopKSelR's
// time at 69,000 rows, its walk's uncoalesced reads ~25 %, the local adds ~12 %.)
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/test_topk_q.cpp -o test_topk_q
//   ONEAPI_DEVICE_SELECTOR=level_zero:1 ./test_topk_q
#include <sycl/sycl.hpp>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    const int MAXN = 140000;
    float *sc = sycl::malloc_device<float>(MAXN + 64, q);
    uint8_t *cm[3];
    for (auto &p : cm) p = sycl::malloc_device<uint8_t>(MAXN + 64, q);
    int32_t *ls[3];
    for (auto &l : ls) l = sycl::malloc_device<int32_t>(2048 + 64, q);
    using KB = TopKSelP<true>;
    using KR = TopKSelP<false>;
    constexpr size_t SLM = (size_t)KR::NSG * 256 + 8;
    auto local = [&](auto k, auto... a) {
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(SLM, h);
            h.parallel_for(sycl::nd_range<1>(1024, 1024), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k(it, a..., &lt[0]);
            });
        });
    };
    auto us = [](sycl::event &e) {
        return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
    };
    std::mt19937 rng(5);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::vector<float> hs(MAXN);
    const char *kinds[5] = {"normal", "few values (ties)", "+0 / -0", "mostly -inf", "with NaNs"};
    auto fill = [&](int n, int kind) {
        for (int j = 0; j < n; ++j) {
            const float f = nd(rng);
            hs[j] = kind == 1 ? std::floor(f * 1.5f) : kind == 2 ? (f > 0 ? 0.0f : -0.0f) : kind == 3 ? -INFINITY : f;
        }
        if (kind == 3)
            for (int i = 0; i < 300; ++i) hs[(size_t)(rng() % n)] = nd(rng);
        if (kind == 4)
            for (int i = 0; i < 64; ++i) hs[(size_t)(rng() % n)] = (i & 1) ? std::nanf("") : -std::nanf("");
        q.memcpy(sc, hs.data(), (size_t)n * 4).wait();
    };
    auto rowsq = [&](const KR &k, const uint8_t *cand, int32_t *l) -> sycl::event {
        const int c = qsel_span(k.n);
        if (c <= 16) return local(TopKSelQ<16>{k}, (const float *)sc, cand, l, (uint8_t *)nullptr);
        if (c <= 32) return local(TopKSelQ<32>{k}, (const float *)sc, cand, l, (uint8_t *)nullptr);
        if (c <= 64) return local(TopKSelQ<64>{k}, (const float *)sc, cand, l, (uint8_t *)nullptr);
        if (c <= 96) return local(TopKSelQ<96>{k}, (const float *)sc, cand, l, (uint8_t *)nullptr);
        return local(TopKSelR<false>{k}, (const float *)sc, cand, l, (uint8_t *)nullptr); // the engine's fallback
    };
    auto blockq = [&](const KB &k, int32_t *l, uint8_t *co) -> sycl::event {
        if (qsel_span(k.n) <= 16) return local(TopKSelBQ<16>{k}, (const float *)sc, (const uint8_t *)nullptr, l, co);
        if (qsel_span(k.n) <= 32) return local(TopKSelBQ<32>{k}, (const float *)sc, (const uint8_t *)nullptr, l, co);
        return local(k, (const float *)sc, (const uint8_t *)nullptr, l, co); // the engine's fallback
    };
    std::vector<int32_t> bl(2049);
    auto candq = [&](int n, int32_t *l) -> sycl::event {
        if (qsel_span(bl[0] * 8) <= 16)
            return local(TopKSelCQ<16>{n, 512, 128, 512}, (const float *)sc, (const uint8_t *)cm[0], (const int32_t *)ls[2], l);
        return local(TopKSelCQ<32>{n, 512, 128, 512}, (const float *)sc, (const uint8_t *)cm[0], (const int32_t *)ls[2], l);
    };
    auto same_i = [&](int32_t *a, int32_t *b, size_t n) {
        std::vector<int32_t> x(n), y(n);
        q.memcpy(x.data(), a, n * 4);
        q.memcpy(y.data(), b, n * 4).wait();
        return x == y;
    };
    auto same_b = [&](uint8_t *a, uint8_t *b, size_t n) {
        std::vector<uint8_t> x(n), y(n);
        q.memcpy(x.data(), a, n);
        q.memcpy(y.data(), b, n).wait();
        return x == y;
    };
    long bad = 0;
    std::printf("%-18s %7s | %-27s | %-27s | %-17s | %-27s\n", "scores", "n", "plain P / R / Q us", "masked P / R / Q us",
                "block P / Q us", "cand C / C rwalk / Q us");
    for (int kind = 0; kind < 5; ++kind)
        for (int n : {600, 2300, 4700, 16391, 17000, 19000, 34000, 69000, 95497, 98304, 131080, 139000}) {
            fill(n, kind);
            const int nb = (n + 7) / 8;
            const KB kb{nb, 2048, 0, 0, 0, 8, n};
            const KR kp{n, 512, 128, 512, 0, 0, 0}, km{n, 512, 128, 512, n, 0, 0};
            double t[11] = {};
            bool s[5] = {true, true, true, true, true}; // plain, masked, block mask, block list, cand
            const int REP = kind == 0 ? 10 : 2;
            for (int r = 0; r <= REP; ++r) {
                // block select: reference into cm[0] / ls[2] (the block list the candidate selects read)
                for (auto p : cm) q.fill(p, (uint8_t)7, MAXN + 64);
                for (auto l : ls) q.fill(l, -5, 2048 + 64);
                q.wait();
                auto b0 = local(kb, (const float *)sc, (const uint8_t *)nullptr, ls[2], cm[0]); b0.wait();
                auto b1 = blockq(kb, ls[1], cm[1]); b1.wait();
                s[2] = s[2] && same_b(cm[0], cm[1], (size_t)n);
                s[3] = s[3] && same_i(ls[2], ls[1], 2049);
                q.memcpy(bl.data(), ls[2], 2049 * 4).wait();
                // plain and masked selects
                sycl::event e[6];
                for (int masked = 0; masked < 2; ++masked) {
                    const KR &k = masked ? km : kp;
                    const uint8_t *cand = masked ? cm[0] : nullptr;
                    q.fill(ls[0], -5, 2048 + 64); q.fill(ls[1], -5, 2048 + 64).wait();
                    e[3 * masked] = local(k, (const float *)sc, cand, ls[0], (uint8_t *)nullptr); e[3 * masked].wait();
                    e[3 * masked + 1] = local(TopKSelR<false>{k}, (const float *)sc, cand, ls[1], (uint8_t *)nullptr); e[3 * masked + 1].wait();
                    s[masked] = s[masked] && same_i(ls[0], ls[1], 512);
                    q.fill(ls[1], -5, 2048 + 64).wait();
                    e[3 * masked + 2] = rowsq(k, cand, ls[1]); e[3 * masked + 2].wait();
                    s[masked] = s[masked] && same_i(ls[0], ls[1], 512);
                }
                // candidate selects over the block list (ls[2]) and the mask (cm[0])
                int32_t *lo = sycl::malloc_device<int32_t>(512, q);
                q.fill(ls[0], -5, 2048 + 64); q.fill(ls[1], -5, 2048 + 64); q.fill(lo, -5, 512).wait();
                auto c0 = local(TopKSelC{n, 512, 128, 512, 8, false}, (const float *)sc, (const uint8_t *)cm[0], (const int32_t *)ls[2], ls[0]); c0.wait();
                auto c1 = local(TopKSelC{n, 512, 128, 512, 8, true}, (const float *)sc, (const uint8_t *)cm[0], (const int32_t *)ls[2], ls[1]); c1.wait();
                auto c2 = candq(n, lo); c2.wait();
                s[4] = s[4] && same_i(ls[0], ls[1], 512) && same_i(ls[0], lo, 512);
                sycl::free(lo, q);
                if (r) {
                    for (int i = 0; i < 6; ++i) t[i] += us(e[i]);
                    t[6] += us(b0); t[7] += us(b1); t[8] += us(c0); t[9] += us(c1); t[10] += us(c2);
                }
            }
            for (auto &x : t) x /= REP;
            for (bool x : s) bad += !x;
            std::printf("%-18s %7d | %7.1f %7.1f %7.1f %s | %7.1f %7.1f %7.1f %s | %6.1f %6.1f %s%s | %7.1f %7.1f %7.1f %s\n", kinds[kind], n,
                        t[0], t[1], t[2], s[0] ? "y" : "NO", t[3], t[4], t[5], s[1] ? "y" : "NO", t[6], t[7], s[2] ? "y" : "NO",
                        s[3] ? "y" : "NO", t[8], t[9], t[10], s[4] ? "y" : "NO");
        }
    std::printf(bad ? "FAIL (%ld differ)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
