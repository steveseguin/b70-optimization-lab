// IndexerScoreB (keys read once, 32 head sums side by side) against IndexerScoreA,
// bit for bit, and GPU time of each, for one token at several lengths.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

int main() {
    sycl::queue q{sycl::gpu_selector_v, sycl::property::queue::in_order{}};
    sycl::queue qp{q.get_context(), q.get_device(), {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    const int MAXN = 140000;
    float *dq = sycl::malloc_device<float>(4096, q), *dw = sycl::malloc_device<float>(32, q);
    uint16_t *dk = sycl::malloc_device<uint16_t>((size_t)MAXN * 128, q);
    float *sa = sycl::malloc_device<float>(MAXN + 64, q), *sb = sycl::malloc_device<float>(MAXN + 64, q);
    int64_t *lens = sycl::malloc_device<int64_t>(1, q);
    std::mt19937 rng(7);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::vector<float> hq(4096), hw(32);
    std::vector<uint16_t> hk((size_t)MAXN * 128);
    for (auto &v : hq) v = nd(rng) * 0.1f;
    for (auto &v : hw) v = nd(rng);
    for (auto &v : hk) {
        const float f = nd(rng);
        uint32_t u;
        std::memcpy(&u, &f, 4);
        v = (uint16_t)(u >> 16);
    }
    q.memcpy(dq, hq.data(), 4096 * 4);
    q.memcpy(dw, hw.data(), 32 * 4);
    q.memcpy(dk, hk.data(), hk.size() * 2).wait();
    long bad = 0;
    for (int len : {513, 600, 1700, 3400, 10000, 40000, 131072}) {
        const int T_ = (len + 31) / 32 * 32;
        const int64_t l64 = len;
        q.memcpy(lens, &l64, 8).wait();
        q.fill(sa, 1.0f, MAXN + 64);
        q.fill(sb, 1.0f, MAXN + 64).wait();
        double ta = 1e30, tb = 1e30;
        for (int r = 0; r < 10; ++r) {
            auto ea = qp.submit([&](sycl::handler &h) {
                IndexerScoreA<ActF32> k{32, 128, T_, 1};
                h.parallel_for(sycl::nd_range<1>(T_, 32), [=](sycl::nd_item<1> it) { k(it, dq, dk, dw, lens, sa); });
            });
            constexpr int WG = 128;
            const size_t n = (size_t)(T_ + WG - 1) / WG * WG;
            auto eb = qp.submit([&](sycl::handler &h) {
                sycl::local_accessor<float, 1> lt(32 * 128 + 32, h);
                IndexerScoreB<ActF32> k{len, T_};
                h.parallel_for(sycl::nd_range<1>(n, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                    k(it, dq, dk, dw, sb, &lt[0]);
                });
            });
            eb.wait();
            auto ns = [](sycl::event &e) {
                return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                        e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
            };
            ta = std::min(ta, ns(ea));
            tb = std::min(tb, ns(eb));
        }
        std::vector<float> a(T_), b(T_);
        q.memcpy(a.data(), sa, (size_t)T_ * 4);
        q.memcpy(b.data(), sb, (size_t)T_ * 4).wait();
        const bool same = std::memcmp(a.data(), b.data(), (size_t)T_ * 4) == 0;
        if (!same) ++bad;
        printf("len %6d: A %8.1f us  B %8.1f us  %s\n", len, ta, tb, same ? "bitwise identical" : "DIFFERENT");
    }
    return bad ? 1 : 0;
}
