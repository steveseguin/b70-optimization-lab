// Where the time of one card-to-card exchange (XchgPull, sycl_v41.hpp) goes, on all six cards at the engine's
// shapes: the same exchange back to back with parts switched off. Timing only: the variants without fences or
// flags can read stale rows, nothing is checked (xchg_pull_test.cpp checks the real kernel).
//   full     XchgPull as the engine launched it until 2026-11-10 (copy_seq; nwg = clamp(vec4 count / 512, 4, 64))
//   full_lb  the same with copy_lb (every peer's load of a round before the stores; OWN_XPULL_LB=1, slower)
//   nofence  neither fence
//   nocopy   publish + wait + fences, no copy
//   copy     copy only (no flags, no fences); copy_lb the same with copy_lb
//   empty    an empty kernel of the same size (launch floor of the in-order queue)
// (round 18 e81b also ran: norel / noacq, one fence off; flags, flag stores + wait only; wg1, one work-group)
// Pointers are direct kernel arguments only (the engine runs with DisableIndirectAccess=1).
//
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -Wno-deprecated-declarations -I src \
//     tools/bench/xchg_lat_bench.cpp -o xchg_lat_bench -lze_loader
//   NEOReadDebugKeys=1 DisableIndirectAccess=1 ./xchg_lat_bench [iterations]
#include <sycl/sycl.hpp>
#include <level_zero/ze_api.h>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <algorithm>
#include <barrier>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;
static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }

// XchgPull's body with switches (same publish / wait / copy code)
struct XchgPullV {
    int n, me;
    unsigned off, stride, nslot;
    unsigned b0[6], b1[6];
    uint32_t seq;
    long spin;
    int rel, acq, flags, copy, lb;
    void operator()(sycl::nd_item<1> it, float *p0, float *p1, float *p2, float *p3, float *p4, float *p5,
                    uint32_t *err) const {
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        const unsigned t = (unsigned)it.get_local_linear_id();
        float *mine = XchgP::pick(me, p0, p1, p2, p3, p4, p5);
        if (flags && it.get_group_linear_id() == 0) {
            if (rel) sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
            sycl::group_barrier(it.get_group());
            if ((int)t < n && (int)t != me)
                AR(reinterpret_cast<uint32_t *>(XchgP::pick((int)t, p0, p1, p2, p3, p4, p5))[16 * me]).store(seq);
        }
        if (flags && (int)t < n && (int)t != me) {
            AR poison(reinterpret_cast<uint32_t *>(mine)[96]);
            AR f(reinterpret_cast<uint32_t *>(mine)[16 * t]);
            long s = 0;
            if (!poison.load())
                while (f.load() < seq && ++s < spin) {}
            if (s >= spin) {
                poison.store(1u);
                err[0] = 1u + t;
            }
        }
        if (acq) sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
        if (!copy) return;
        if (lb) { XchgPull::copy_lb(it, n, me, off, stride, nslot, b0, b1, p0, p1, p2, p3, p4, p5); return; }
        const size_t T = it.get_global_range(0);
        size_t base = 0;
        for (int d = 0; d < n; ++d) {
            if (d == me) continue;
            const unsigned n4 = (b1[d] - b0[d]) / 4;
            const size_t cnt = (size_t)nslot * n4;
            const float *src = XchgP::pick(d, p0, p1, p2, p3, p4, p5) + off;
            float *dst = mine + off;
            const size_t gid = it.get_global_linear_id();
            size_t k0 = (gid + T - base % T) % T;
            for (size_t k = k0; k < cnt; k += T) {
                const size_t o = (size_t)(k / n4) * stride + b0[d] + (k % n4) * 4;
                *reinterpret_cast<sycl::vec<float, 4> *>(dst + o) = *reinterpret_cast<const sycl::vec<float, 4> *>(src + o);
            }
            base += cnt;
        }
    }
};

struct Shape {
    const char *name;
    unsigned stride, nslot;
    unsigned b0[6], b1[6];
};
static void split16(unsigned n, unsigned *b0, unsigned *b1) { // backend tp_setup's split(n, c, 16)
    const unsigned u = n / 16;
    for (int c = 0; c < 6; ++c) {
        b0[c] = (unsigned)(u * c / 6) * 16;
        b1[c] = c == 5 ? n : (unsigned)(u * (c + 1) / 6) * 16;
    }
}

int main(int argc, char **argv) {
    const int ITER = argc > 1 ? atoi(argv[1]) : 2000;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const int N = (int)l0.size();
    if (N != 6) { std::printf("needs six cards, found %d\n", N); return 1; }
    std::vector<Shape> shapes;
    for (unsigned m : {1u, 3u, 6u, 16u}) {
        static char nm[4][32];
        int k = m == 1 ? 0 : m == 3 ? 1 : m == 6 ? 2 : 3;
        std::snprintf(nm[k], sizeof nm[k], "h (5120 x %u)", m);
        Shape s{nm[k], 5120, m, {}, {}};
        split16(5120, s.b0, s.b1);
        shapes.push_back(s);
    }
    { Shape s{"act (2304 x 21)", 2304, 21, {}, {}}; split16(2304, s.b0, s.b1); shapes.push_back(s); }
    size_t maxf = 0;
    for (auto &s : shapes) maxf = std::max(maxf, (size_t)s.stride * s.nslot);
    const unsigned OFF = 1024;
    const size_t AF = OFF + 2 * maxf + 64;
    std::vector<sycl::context> ctx;
    std::vector<sycl::queue> q;
    std::vector<float *> arena(N);
    std::vector<uint32_t *> err(N);
    for (int c = 0; c < N; ++c) {
        ctx.emplace_back(l0[c]);
        q.emplace_back(ctx[c], l0[c], sycl::property::queue::in_order{});
        arena[c] = sycl::malloc_device<float>(AF, q[c]);
        err[c] = sycl::malloc_host<uint32_t>(4, ctx[c]);
        q[c].memset(arena[c], 0, AF * 4).wait();
        err[c][0] = 0;
    }
    std::vector<std::vector<float *>> peer(N, std::vector<float *>(N, nullptr));
    for (int d = 0; d < N; ++d) {
        ze_ipc_mem_handle_t h;
        if (zeMemGetIpcHandle(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[d]), arena[d], &h) != ZE_RESULT_SUCCESS) return 1;
        for (int c = 0; c < N; ++c) {
            if (c == d) { peer[c][d] = arena[d]; continue; }
            void *p = nullptr;
            if (zeMemOpenIpcHandle(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[c]),
                                   sycl::get_native<sycl::backend::ext_oneapi_level_zero>(l0[c]), h, 0, &p) != ZE_RESULT_SUCCESS || !p)
                return 1;
            peer[c][d] = (float *)p;
        }
    }
    std::vector<uint32_t> seq(N, 0);
    const long SPIN = 5000000;
    struct V { const char *name; int rel, acq, flags, copy, wg1, empty, lb; };
    const V vars[] = {{"full", 1, 1, 1, 1, 0, 0, 0},    {"full_lb", 1, 1, 1, 1, 0, 0, 1}, {"nocopy", 1, 1, 1, 0, 0, 0, 0},
                      {"copy", 0, 0, 0, 1, 0, 0, 0},    {"copy_lb", 0, 0, 0, 1, 0, 0, 1}, {"nofence", 0, 0, 1, 1, 0, 0, 0},
                      {"empty", 0, 0, 0, 0, 0, 1, 0}};
    int fail = 0;
    auto run = [&](const Shape &s, const V &v, int iters) {
        std::barrier sync(N);
        std::vector<double> t(N);
        auto body = [&](int c) {
            float *P0 = peer[c][0], *P1 = peer[c][1], *P2 = peer[c][2], *P3 = peer[c][3], *P4 = peer[c][4], *P5 = peer[c][5];
            uint32_t *e = err[c];
            size_t nv = 0;
            for (int d = 0; d < N; ++d)
                if (d != c) nv += (size_t)s.nslot * ((s.b1[d] - s.b0[d]) / 4);
            const size_t nwg = v.wg1 ? 1 : std::clamp<size_t>((nv + 511) / 512, 4, 64);
            sync.arrive_and_wait();
            const double t0 = now();
            for (int i = 0; i < iters; ++i) {
                const unsigned off = OFF + (unsigned)(i % 2) * (unsigned)maxf;
                if (v.empty) {
                    q[c].parallel_for(sycl::nd_range<1>(nwg * 256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                        if (it.get_global_linear_id() == (size_t)1 << 40) e[1] = 1u; // never
                    });
                    continue;
                }
                XchgPullV x{N, c, off, s.stride, s.nslot, {}, {}, ++seq[c], SPIN, v.rel, v.acq, v.flags, v.copy, v.lb};
                for (int d = 0; d < 6; ++d) { x.b0[d] = s.b0[d]; x.b1[d] = s.b1[d]; }
                q[c].parallel_for(sycl::nd_range<1>(nwg * 256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                    x(it, P0, P1, P2, P3, P4, P5, e);
                });
            }
            q[c].wait();
            t[c] = now() - t0;
            sync.arrive_and_wait();
        };
        std::vector<std::thread> th;
        for (int c = 0; c < N; ++c) th.emplace_back(body, c);
        for (auto &x : th) x.join();
        double mx = 0;
        for (double x : t) mx = std::max(mx, x);
        uint32_t ne = 0;
        for (int c = 0; c < N; ++c) ne += err[c][0] != 0;
        return std::pair<double, uint32_t>{mx / iters * 1e6, ne};
    };
    // warm-up (kernel builds, first touches)
    for (auto &v : vars) run(shapes[1], v, 50);
    std::printf("%-18s", "us per exchange");
    for (auto &v : vars) std::printf(" %8s", v.name);
    std::printf("\n");
    for (auto &s : shapes) {
        for (int rep = 0; rep < 2; ++rep) {
            std::printf("%-18s", s.name);
            for (auto &v : vars) {
                auto [us, ne] = run(s, v, ITER);
                std::printf(" %8.2f", us);
                if (ne) { std::printf("(TIMEOUT)"); fail = 1; }
            }
            std::printf("\n");
        }
    }
    for (int c = 0; c < N; ++c)
        for (int d = 0; d < N; ++d)
            if (c != d) zeMemCloseIpcHandle(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[c]), peer[c][d]);
    std::printf(fail ? "TIMEOUT\n" : "DONE\n");
    return fail;
}
