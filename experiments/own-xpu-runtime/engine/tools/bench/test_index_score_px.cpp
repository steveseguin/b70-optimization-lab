// test_index_score_px (idxrp-1, 2026-11-16): the prompt halves' index scores on one card, as tpm_index launches
// them for one card's share of a half (43 tokens): IndexerScoreBM (today), the same with the groups numbered row
// group first (rmaj: the tokens of a row group run together and share the key rows in the caches), and
// IndexerScoreBMR<2> / <4> (2 / 4 rows per item), each also with rmaj. Every variant's scores bit for bit against
// IndexerScoreBM's (rows [0, len) and the -inf rows up to the next multiple of 32), and the GPU time of each, at the
// engine's lengths: layer 20 (ratio 1: token t sees len0 + t rows) and layers 2 / 8 / 14 (ratio 2: len0 / 2 + t / 2).
// Last line "PASS (N cases)" or "FAIL (N of M cases differ)". Build as the other benches (build122.sh):
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/test_index_score_px.cpp -o test_index_score_px
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("device: %s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    constexpr int M = 43;
    constexpr size_t WG = 128;
    const long MAXN = 993000 + M + 64;
    const size_t SS = (size_t)MAXN + 64;
    float *dq = sycl::malloc_device<float>((size_t)M * 4096, q), *dw = sycl::malloc_device<float>((size_t)M * 32, q);
    uint16_t *dk = sycl::malloc_device<uint16_t>((size_t)MAXN * 128, q);
    float *sa = sycl::malloc_device<float>((size_t)M * SS, q), *sb = sycl::malloc_device<float>((size_t)M * SS, q);
    int *dl = sycl::malloc_device<int>(M, q);
    if (!dq || !dw || !dk || !sa || !sb || !dl) {
        std::printf("FAIL (device allocation)\n");
        return 2;
    }
    std::mt19937 rng(11);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::vector<float> hq((size_t)M * 4096), hw((size_t)M * 32);
    for (auto &v : hq) v = nd(rng) * 0.1f;
    for (auto &v : hw) v = nd(rng);
    {
        std::vector<uint16_t> hk((size_t)1 << 20);
        for (long r0 = 0; r0 < MAXN * 128; r0 += (long)hk.size()) {
            const long n = std::min<long>((long)hk.size(), MAXN * 128 - r0);
            for (long i = 0; i < n; ++i) {
                // a few exact ties (repeated keys) and zero / negative zero keys among the normal ones
                const float f = (i % 977 == 0) ? 0.f : (i % 1499 == 0) ? -0.f : nd(rng);
                uint32_t u;
                std::memcpy(&u, &f, 4);
                hk[i] = (uint16_t)(u >> 16);
            }
            q.memcpy(dk + r0, hk.data(), (size_t)n * 2).wait();
        }
    }
    q.memcpy(dq, hq.data(), hq.size() * 4);
    q.memcpy(dw, hw.data(), hw.size() * 4).wait();
    auto ms = [](sycl::event &e) {
        return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-6;
    };
    int lens[M] = {};
    long lmax = 0;
    auto runBM = [&](unsigned rmaj, float *out) {
        IndexerScoreBM<ActF32> k{};
        k.lens.p = dl;
        k.m = (unsigned)M;
        k.gpt = (unsigned)((((lmax + 31) / 32 * 32) + WG - 1) / WG);
        k.qs = 4096, k.ws = 32, k.ss = SS;
        k.rmaj = rmaj;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(32 * 128 + 32, h);
            h.parallel_for(sycl::nd_range<1>((size_t)M * k.gpt * WG, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                k(it, dq, dk, dw, out, &lt[0]);
            });
        });
    };
    auto runR = [&](auto rc, unsigned rmaj, float *out) {
        constexpr int R = decltype(rc)::value;
        IndexerScoreBMR<ActF32, R> k{};
        k.lens.p = dl;
        k.m = (unsigned)M;
        k.gpt = (unsigned)((((lmax + 31) / 32 * 32) + WG * R - 1) / (WG * R));
        k.qs = 4096, k.ws = 32, k.ss = SS;
        k.rmaj = rmaj;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(32 * 128 + 32, h);
            h.parallel_for(sycl::nd_range<1>((size_t)M * k.gpt * WG, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                k(it, dq, dk, dw, out, &lt[0]);
            });
        });
    };
    std::vector<float> ha, hb;
    auto fetch = [&](std::vector<float> &h, const float *d) {
        h.resize((size_t)M * SS);
        for (int t = 0; t < M; ++t) {
            const size_t n = (size_t)(lens[t] + 31) / 32 * 32;
            q.memcpy(h.data() + (size_t)t * SS, d + (size_t)t * SS, n * 4);
        }
        q.wait();
    };
    auto same = [&]() {
        for (int t = 0; t < M; ++t) {
            const size_t n = (size_t)(lens[t] + 31) / 32 * 32;
            if (std::memcmp(ha.data() + (size_t)t * SS, hb.data() + (size_t)t * SS, n * 4)) return false;
        }
        return true;
    };
    const char *vn[6] = {"BM rmaj", "R2", "R2 rmaj", "R4", "R4 rmaj", "BM again"};
    std::printf("%-5s %8s | %9s | %9s %9s %9s %9s %9s %9s | ms, min of 5; Gop/s of the fastest\n", "ratio", "len0", "BM",
                vn[0], vn[1], vn[2], vn[3], vn[4], vn[5]);
    int cases = 0, bad = 0;
    for (int ratio : {1, 2}) {
        for (long n0 : {95000L, 189000L, 352000L, 705000L, 993000L}) {
            lmax = 0;
            double ops = 0;
            for (int t = 0; t < M; ++t) {
                lens[t] = ratio == 1 ? (int)(n0 + t) : (int)(n0 / 2 + t / 2);
                lmax = std::max<long>(lmax, lens[t]);
                ops += (double)lens[t] * (2.0 * 32 * 128 + 3 * 32);
            }
            q.memcpy(dl, lens, sizeof lens).wait();
            q.fill(sa, 1.0f, (size_t)M * SS).wait();
            double tb = 1e30;
            for (int r = 0; r < 5; ++r) { auto e = runBM(0, sa); e.wait(); tb = std::min(tb, ms(e)); }
            fetch(ha, sa);
            double tv[6];
            bool ok[6];
            for (int v = 0; v < 6; ++v) {
                q.fill(sb, 2.0f, (size_t)M * SS).wait();
                double tm = 1e30;
                for (int r = 0; r < 5; ++r) {
                    sycl::event e = v == 0 ? runBM(1, sb)
                                  : v == 1 ? runR(std::integral_constant<int, 2>{}, 0, sb)
                                  : v == 2 ? runR(std::integral_constant<int, 2>{}, 1, sb)
                                  : v == 3 ? runR(std::integral_constant<int, 4>{}, 0, sb)
                                  : v == 4 ? runR(std::integral_constant<int, 4>{}, 1, sb)
                                           : runBM(0, sb);
                    e.wait();
                    tm = std::min(tm, ms(e));
                }
                tv[v] = tm;
                fetch(hb, sb);
                ok[v] = same();
            }
            double best = tb;
            for (double x : tv) best = std::min(best, x);
            bool all = true;
            for (bool x : ok) all = all && x;
            ++cases;
            if (!all) ++bad;
            std::printf("%-5d %8ld | %9.2f | %8.2f%s %8.2f%s %8.2f%s %8.2f%s %8.2f%s %8.2f%s | %.0f\n", ratio, n0, tb,
                        tv[0], ok[0] ? " " : "!", tv[1], ok[1] ? " " : "!", tv[2], ok[2] ? " " : "!", tv[3], ok[3] ? " " : "!",
                        tv[4], ok[4] ? " " : "!", tv[5], ok[5] ? " " : "!", ops / best * 1e-6);
        }
    }
    std::printf("(! = scores differ from IndexerScoreBM's)\n");
    if (bad) std::printf("FAIL (%d of %d cases differ)\n", bad, cases);
    else std::printf("PASS (%d cases)\n", cases);
    return bad ? 1 : 0;
}
