// XchgPull (exchange by loads, sycl_v41.hpp) on all six cards: correctness under changing data, and time per
// exchange against XchgP (stores into the peers) at the engine's shapes.
// Every iteration: each card writes its rows of every slot with values that depend on (iteration, card,
// slot, row), then the exchange, then a check kernel compares every row of every slot on every card with
// the expected value and counts mismatches on the card (no host wait between iterations: the queues run
// ahead as in the engine). Then the same exchanges back to back without producer and check, for the time.
// Pointers are direct kernel arguments only (the engine runs with DisableIndirectAccess=1).
//
//   icpx -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src \
//     tools/bench/xchg_pull_test.cpp -o xchg_pull_test -lze_loader
//   NEOReadDebugKeys=1 DisableIndirectAccess=1 ./xchg_pull_test [iterations]
// Exit status 1 on any mismatch or timeout.
#include <sycl/sycl.hpp>
#include <level_zero/ze_api.h>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <barrier>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;
static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }

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
static inline float expect(uint32_t it, uint32_t card, uint32_t slot, uint32_t row) {
    return (float)((it * 2654435761u ^ card * 40503u ^ slot * 977u ^ row * 31u) & 0xFFFFFFu);
}

int main(int argc, char **argv) {
    const int ITER = argc > 1 ? atoi(argv[1]) : 2000;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const int N = (int)l0.size();
    if (N != 6) { std::printf("needs six cards, found %d\n", N); return 1; }
    std::vector<Shape> shapes;
    { Shape s{"decode h (5120 x 1)", 5120, 1, {}, {}}; split16(5120, s.b0, s.b1); shapes.push_back(s); }
    { Shape s{"decode act (2304 x 7)", 2304, 7, {}, {}}; split16(2304, s.b0, s.b1); shapes.push_back(s); }
    { Shape s{"decode oa (8192 x 1)", 8192, 1, {0, 1024, 2048, 4096, 5120, 6144}, {1024, 2048, 4096, 5120, 6144, 8192}}; shapes.push_back(s); }
    { Shape s{"block6 act (2304 x 42)", 2304, 42, {}, {}}; split16(2304, s.b0, s.b1); shapes.push_back(s); }
    { Shape s{"block16 h (5120 x 16)", 5120, 16, {}, {}}; split16(5120, s.b0, s.b1); shapes.push_back(s); }
    { Shape s{"block16 act (2304 x 112)", 2304, 112, {}, {}}; split16(2304, s.b0, s.b1); shapes.push_back(s); }
    { Shape s{"block16 oa (8192 x 16)", 8192, 16, {0, 1024, 2048, 4096, 5120, 6144}, {1024, 2048, 4096, 5120, 6144, 8192}}; shapes.push_back(s); }
    size_t maxf = 0;
    for (auto &s : shapes) maxf = std::max(maxf, (size_t)s.stride * s.nslot);
    const unsigned OFF = 1024;
    const size_t AF = OFF + 2 * maxf + 64; // two regions used in turn (as the engine's regions: a region is
    // written again only after a later exchange, which every peer completes after reading the earlier rows)
    std::vector<sycl::context> ctx;
    std::vector<sycl::queue> q;
    std::vector<float *> arena(N);
    std::vector<uint32_t *> err(N), bad(N);
    for (int c = 0; c < N; ++c) {
        ctx.emplace_back(l0[c]);
        q.emplace_back(ctx[c], l0[c], sycl::property::queue::in_order{});
        arena[c] = sycl::malloc_device<float>(AF, q[c]);
        bad[c] = sycl::malloc_device<uint32_t>(1, q[c]);
        err[c] = sycl::malloc_host<uint32_t>(4, ctx[c]);
        q[c].memset(arena[c], 0, AF * 4).wait();
        q[c].memset(bad[c], 0, 4).wait();
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
    int fail = 0;
    const long SPIN = 5000000;
    auto launch_x = [&](int c, const Shape &s, bool pull, int nwg, unsigned off) {
        float *P0 = peer[c][0], *P1 = peer[c][1], *P2 = peer[c][2], *P3 = peer[c][3], *P4 = peer[c][4], *P5 = peer[c][5];
        uint32_t *e = err[c];
        const uint32_t sq = ++seq[c];
        if (pull) {
            XchgPull x{N, c, off, s.stride, s.nslot, {}, {}, sq, SPIN, 0};
            for (int d = 0; d < 6; ++d) { x.b0[d] = s.b0[d]; x.b1[d] = s.b1[d]; }
            q[c].parallel_for(sycl::nd_range<1>((size_t)nwg * 256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                x(it, P0, P1, P2, P3, P4, P5, e);
            });
        } else {
            XchgP x{N, c, off, s.stride, s.nslot, s.b0[c], s.b1[c], sq, SPIN, 0};
            q[c].parallel_for(sycl::nd_range<1>(256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                x(it, P0, P1, P2, P3, P4, P5, e);
            });
        }
    };
    auto run = [&](const Shape &s, bool pull, int nwg, bool check, int iters) {
        std::barrier sync(N);
        std::vector<double> t(N);
        auto body = [&](int c) {
            float *a = arena[c];
            uint32_t *bd = bad[c];
            const unsigned stride = s.stride, nslot = s.nslot, r0 = s.b0[c], r1 = s.b1[c];
            unsigned own[7];
            for (int d = 0; d < 6; ++d) own[d] = s.b0[d];
            own[6] = s.stride;
            const unsigned o0 = own[0], o1 = own[1], o2 = own[2], o3 = own[3], o4 = own[4], o5 = own[5];
            sync.arrive_and_wait();
            const double t0 = now();
            for (int i = 0; i < iters; ++i) {
                const uint32_t iv = (uint32_t)i + 1;
                const unsigned off = OFF + (unsigned)(i % 2) * (unsigned)maxf;
                if (check)
                    q[c].parallel_for(sycl::range<1>((size_t)nslot * (r1 - r0)), [=](sycl::id<1> k) {
                        const uint32_t sl = (uint32_t)(k[0] / (r1 - r0)), r = r0 + (uint32_t)(k[0] % (r1 - r0));
                        a[off + (size_t)sl * stride + r] = expect(iv, (uint32_t)c, sl, r);
                    });
                launch_x(c, s, pull, nwg, off);
                if (check)
                    q[c].parallel_for(sycl::range<1>((size_t)nslot * stride), [=](sycl::id<1> k) {
                        const uint32_t sl = (uint32_t)(k[0] / stride), r = (uint32_t)(k[0] % stride);
                        const uint32_t ow = r >= o5 ? 5 : r >= o4 ? 4 : r >= o3 ? 3 : r >= o2 ? 2 : r >= o1 ? 1 : 0;
                        (void)o0;
                        if (a[off + (size_t)sl * stride + r] != expect(iv, ow, sl, r))
                            sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                                             sycl::access::address_space::global_space>(*bd).fetch_add(1u);
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
        for (double v : t) mx = std::max(mx, v);
        uint32_t nb = 0, ne = 0;
        for (int c = 0; c < N; ++c) {
            uint32_t b = 0;
            q[c].memcpy(&b, bad[c], 4).wait();
            q[c].memset(bad[c], 0, 4).wait();
            nb += b;
            ne += err[c][0] != 0;
        }
        return std::tuple<double, uint32_t, uint32_t>{mx / iters * 1e6, nb, ne};
    };
    for (auto &s : shapes) {
        size_t bytes = 0;
        for (int d = 0; d < 6; ++d) bytes = std::max<size_t>(bytes, (size_t)(s.b1[d] - s.b0[d]) * s.nslot * 4);
        auto [tc, nb, ne] = run(s, true, 16, true, ITER);
        std::printf("%-26s largest slice %7zu B | pull check %d iters: %u wrong values, %u timeouts (%.1f us/iter incl. producer + check)\n",
                    s.name, bytes, ITER, nb, ne, tc);
        if (nb || ne) fail = 1;
        auto [tpc, nbp, nep] = run(s, false, 1, true, ITER / 4);
        std::printf("%-26s                          | push check %d iters: %u wrong values, %u timeouts\n", "", ITER / 4, nbp, nep);
        for (int nwg : {1, 4, 16, 64}) {
            auto [tp, a1, a2] = run(s, true, nwg, false, 500);
            std::printf("%-26s   pull nwg %2d: %7.1f us/exchange%s\n", "", nwg, tp, a2 ? " TIMEOUT" : "");
            if (a2) fail = 1;
        }
        auto [tq, b1, b2] = run(s, false, 1, false, 500);
        std::printf("%-26s   push (XchgP) : %7.1f us/exchange%s\n", "", tq, b2 ? " TIMEOUT" : "");
    }
    for (int c = 0; c < N; ++c)
        for (int d = 0; d < N; ++d)
            if (c != d) zeMemCloseIpcHandle(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[c]), peer[c][d]);
    std::printf(fail ? "FAIL\n" : "PASS\n");
    return fail;
}
