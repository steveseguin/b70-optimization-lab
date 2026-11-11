// XchgPull2 (pcd-1, OWN_MT_DSPLIT: XchgPull with a second region, sycl_v41.hpp) on all six cards: correctness under
// changing data at the prompt blocks' shapes, and the time per exchange against XchgPull alone.
// Region 1 is the engine's output-a pull (8,192 rows per token, the cards' rows by the 12,12,12,12,8,8 head layout)
// or its expert-act pull (2,304 rows x 7 slots per token, split16); region 2 is the stream mix's partials, 400 floats
// per token, every card's tokens by ds_split (attention: weights 1,1,1,1,4,4 with the output-a pull; FFN: 1 each with
// the act pull). Every iteration: each card writes its region-1 rows of every slot and its region-2 tokens with
// values that depend on (iteration, card, slot, row), then the exchange, then a check kernel compares every value
// of both regions on every card with the owner's value and counts mismatches on the card (no host wait between
// iterations: the queues run ahead as in the engine; two arena areas used in turn, as xchg_pull_test). Then the
// exchanges back to back without producer and check, XchgPull alone vs XchgPull2, for the time, in the engine's
// launch forms (work-groups clamp((nv + 511) / 512, 4, 64); the 128-register functor XPullK128x2 and the lambda).
// Pointers are direct kernel arguments only (the engine runs with DisableIndirectAccess=1); XchgPull2 holds scalars
// only. No host-pinned memory (the error words are device memory, read back at the end).
//
//   cd engine; icpx -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src \
//     tools/bench/xchg_pull2_test.cpp -o $S/xchg_pull2_test -lze_loader
//   NEOReadDebugKeys=1 DisableIndirectAccess=1 $S/xchg_pull2_test [iterations, default 2000]
// Exit status 1 on any mismatch or timeout.
#include <sycl/sycl.hpp>
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>
#include <level_zero/ze_api.h>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <algorithm>
#include <barrier>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <tuple>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;
static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }

// backend_sycl_v41.hpp's XPullK128x2 (copied: the backend header is not included here)
struct XPullK128x2 {
    XchgPull2 x;
    float *p0, *p1, *p2, *p3, *p4, *p5;
    uint32_t *err;
    void operator()(sycl::nd_item<1> it) const { x(it, p0, p1, p2, p3, p4, p5, err); }
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<128>,
                                                           sycl::ext::oneapi::experimental::sub_group_size<32>};
    }
};
struct XPullK128 {
    XchgPull x;
    float *p0, *p1, *p2, *p3, *p4, *p5;
    uint32_t *err;
    void operator()(sycl::nd_item<1> it) const { x(it, p0, p1, p2, p3, p4, p5, err); }
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<128>,
                                                           sycl::ext::oneapi::experimental::sub_group_size<32>};
    }
};

static constexpr unsigned TOKF = 400; // region 2: 25 * 8 doubles per token
struct Shape {
    char name[48];
    unsigned stride, nslot, M;
    unsigned b0[6], b1[6]; // region 1 rows
    unsigned c0[6], c1[6]; // region 2 rows (tokens * TOKF)
};
static void split16(unsigned n, unsigned *b0, unsigned *b1) { // backend tp_setup's split(n, c, 16)
    const unsigned u = n / 16;
    for (int c = 0; c < 6; ++c) {
        b0[c] = (unsigned)(u * c / 6) * 16;
        b1[c] = c == 5 ? n : (unsigned)(u * (c + 1) / 6) * 16;
    }
}
static void ds_split(unsigned M, const long *w, unsigned *t0, unsigned *t1) { // backend_sycl_v41_mt.inc's ds_split
    long W = 0, cw = 0;
    for (int d = 0; d < 6; ++d) W += w[d];
    unsigned prev = 0;
    for (int d = 0; d < 6; ++d) {
        cw += w[d];
        const unsigned e = d == 5 ? M : (unsigned)std::min<long>(M, ((long)M * cw + W / 2) / W);
        t0[d] = prev;
        t1[d] = prev = std::max(prev, e);
    }
}
static inline float expect(uint32_t it, uint32_t card, uint32_t slot, uint32_t row) {
    return (float)((it * 2654435761u ^ card * 40503u ^ slot * 977u ^ row * 31u) & 0xFFFFFFu);
}
static inline uint32_t owner(const unsigned (&b)[7], uint32_t r) { // b: the six starts and the end
    return r >= b[5] ? 5 : r >= b[4] ? 4 : r >= b[3] ? 3 : r >= b[2] ? 2 : r >= b[1] ? 1 : 0;
}

int main(int argc, char **argv) {
    const int ITER = argc > 1 ? atoi(argv[1]) : 2000;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const int N = (int)l0.size();
    if (N != 6) { std::printf("needs six cards, found %d\n", N); return 1; }
    const long WA[6] = {1, 1, 1, 1, 4, 4}, WF[6] = {1, 1, 1, 1, 1, 1};
    const unsigned oa0[6] = {0, 1536, 3072, 4608, 6144, 7168}, oa1[6] = {1536, 3072, 4608, 6144, 7168, 8192};
    std::vector<Shape> shapes;
    for (const unsigned M : {16u, 64u, 256u}) {
        unsigned t0[6], t1[6];
        Shape s{};
        std::snprintf(s.name, sizeof s.name, "oa %u (8192 x %u) + mix %u", M, M, M);
        s.stride = 8192, s.nslot = M, s.M = M;
        for (int d = 0; d < 6; ++d) s.b0[d] = oa0[d], s.b1[d] = oa1[d];
        ds_split(M, WA, t0, t1);
        for (int d = 0; d < 6; ++d) s.c0[d] = t0[d] * TOKF, s.c1[d] = t1[d] * TOKF;
        shapes.push_back(s);
        Shape a{};
        std::snprintf(a.name, sizeof a.name, "act %u (2304 x %u) + mix %u", M, 7 * M, M);
        a.stride = 2304, a.nslot = 7 * M, a.M = M;
        split16(2304, a.b0, a.b1);
        ds_split(M, WF, t0, t1);
        for (int d = 0; d < 6; ++d) a.c0[d] = t0[d] * TOKF, a.c1[d] = t1[d] * TOKF;
        shapes.push_back(a);
    }
    size_t maxf = 0, max2 = 0;
    for (auto &s : shapes) maxf = std::max(maxf, (size_t)s.stride * s.nslot), max2 = std::max(max2, (size_t)s.M * TOKF);
    maxf = (maxf + 3) & ~(size_t)3;
    const unsigned OFF = 1024;
    const size_t OFF2 = OFF + 2 * maxf, AF = OFF2 + 2 * max2 + 64;
    std::vector<sycl::context> ctx;
    std::vector<sycl::queue> q;
    std::vector<float *> arena(N);
    std::vector<uint32_t *> err(N), bad(N);
    for (int c = 0; c < N; ++c) {
        ctx.emplace_back(l0[c]);
        q.emplace_back(ctx[c], l0[c], sycl::property::queue::in_order{});
        arena[c] = sycl::malloc_device<float>(AF, q[c]);
        bad[c] = sycl::malloc_device<uint32_t>(1, q[c]);
        err[c] = sycl::malloc_device<uint32_t>(4, q[c]);
        q[c].memset(arena[c], 0, AF * 4).wait();
        q[c].memset(bad[c], 0, 4).wait();
        q[c].memset(err[c], 0, 16).wait();
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
    // form: 0 XchgPull alone, 1 XchgPull2 (lambda), 2 XchgPull2 (XPullK128x2), 3 XchgPull (XPullK128)
    auto launch_x = [&](int c, const Shape &s, int form, unsigned off, unsigned off2) {
        float *P0 = peer[c][0], *P1 = peer[c][1], *P2 = peer[c][2], *P3 = peer[c][3], *P4 = peer[c][4], *P5 = peer[c][5];
        uint32_t *e = err[c];
        const uint32_t sq = ++seq[c];
        XchgPull x{N, c, off, s.stride, s.nslot, {}, {}, sq, SPIN, 0};
        for (int d = 0; d < 6; ++d) x.b0[d] = s.b0[d], x.b1[d] = s.b1[d];
        size_t nv = 0;
        for (int d = 0; d < 6; ++d)
            if (d != c) nv += (size_t)s.nslot * ((s.b1[d] - s.b0[d]) / 4);
        XchgPull2 x2{x, off2, 0, 1, {}, {}};
        for (int d = 0; d < 6; ++d) x2.c0[d] = s.c0[d], x2.c1[d] = s.c1[d];
        if (form == 1 || form == 2)
            for (int d = 0; d < 6; ++d)
                if (d != c) nv += (size_t)((s.c1[d] - s.c0[d]) / 4);
        const size_t nwg = std::clamp<size_t>((nv + 511) / 512, 4, 64);
        const sycl::nd_range<1> xr(nwg * 256, 256);
        if (form == 0)
            q[c].parallel_for(xr, [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { x(it, P0, P1, P2, P3, P4, P5, e); });
        else if (form == 1)
            q[c].parallel_for(xr, [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { x2(it, P0, P1, P2, P3, P4, P5, e); });
        else if (form == 2) q[c].parallel_for(xr, XPullK128x2{x2, P0, P1, P2, P3, P4, P5, e});
        else q[c].parallel_for(xr, XPullK128{x, P0, P1, P2, P3, P4, P5, e});
    };
    auto run = [&](const Shape &s, int form, bool check, int iters) {
        std::barrier sync(N);
        std::vector<double> t(N);
        auto body = [&](int c) {
            float *a = arena[c];
            uint32_t *bd = bad[c];
            const unsigned stride = s.stride, nslot = s.nslot, r0 = s.b0[c], r1 = s.b1[c], q0 = s.c0[c], q1 = s.c1[c];
            const unsigned M = s.M;
            unsigned ob[7], oc[7];
            for (int d = 0; d < 6; ++d) ob[d] = s.b0[d], oc[d] = s.c0[d];
            ob[6] = s.stride, oc[6] = M * TOKF;
            // zero-share cards: owner() picks the last card whose start <= r, which is the card that owns r
            const bool two = form == 1 || form == 2;
            sync.arrive_and_wait();
            const double t0 = now();
            for (int i = 0; i < iters; ++i) {
                const uint32_t iv = (uint32_t)i + 1;
                const unsigned off = OFF + (unsigned)(i % 2) * (unsigned)maxf, off2 = (unsigned)(OFF2 + (size_t)(i % 2) * max2);
                if (check) {
                    q[c].parallel_for(sycl::range<1>((size_t)nslot * (r1 - r0)), [=](sycl::id<1> k) {
                        const uint32_t sl = (uint32_t)(k[0] / (r1 - r0)), r = r0 + (uint32_t)(k[0] % (r1 - r0));
                        a[off + (size_t)sl * stride + r] = expect(iv, (uint32_t)c, sl, r);
                    });
                    if (two && q1 > q0)
                        q[c].parallel_for(sycl::range<1>(q1 - q0), [=](sycl::id<1> k) {
                            const uint32_t r = q0 + (uint32_t)k[0];
                            a[off2 + r] = expect(iv, (uint32_t)c, 7777u, r);
                        });
                }
                launch_x(c, s, form, off, off2);
                if (check) {
                    q[c].parallel_for(sycl::range<1>((size_t)nslot * stride), [=](sycl::id<1> k) {
                        const uint32_t sl = (uint32_t)(k[0] / stride), r = (uint32_t)(k[0] % stride);
                        unsigned b[7];
                        for (int d = 0; d < 7; ++d) b[d] = ob[d];
                        if (a[off + (size_t)sl * stride + r] != expect(iv, owner(b, r), sl, r))
                            sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                                             sycl::access::address_space::global_space>(*bd).fetch_add(1u);
                    });
                    if (two)
                        q[c].parallel_for(sycl::range<1>((size_t)M * TOKF), [=](sycl::id<1> k) {
                            const uint32_t r = (uint32_t)k[0];
                            unsigned b[7];
                            for (int d = 0; d < 7; ++d) b[d] = oc[d];
                            if (a[off2 + r] != expect(iv, owner(b, r), 7777u, r))
                                sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                                                 sycl::access::address_space::global_space>(*bd).fetch_add(1u);
                        });
                }
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
            uint32_t b = 0, e4[4] = {};
            q[c].memcpy(&b, bad[c], 4).wait();
            q[c].memcpy(e4, err[c], 16).wait();
            q[c].memset(bad[c], 0, 4).wait();
            q[c].memset(err[c], 0, 16).wait();
            nb += b;
            ne += e4[0] != 0;
        }
        return std::tuple<double, uint32_t, uint32_t>{mx / iters * 1e6, nb, ne};
    };
    for (auto &s : shapes) {
        std::printf("%-34s tokens per card %u,%u,%u,%u,%u,%u\n", s.name, (s.c1[0] - s.c0[0]) / TOKF, (s.c1[1] - s.c0[1]) / TOKF,
                    (s.c1[2] - s.c0[2]) / TOKF, (s.c1[3] - s.c0[3]) / TOKF, (s.c1[4] - s.c0[4]) / TOKF, (s.c1[5] - s.c0[5]) / TOKF);
        for (int form : {2, 1}) {
            auto [tc, nb, ne] = run(s, form, true, ITER);
            std::printf("   %s check %d iters: %u wrong values, %u timeouts (%.1f us/iter incl. producer + check)\n",
                        form == 2 ? "XPullK128x2" : "lambda     ", ITER, nb, ne, tc);
            if (nb || ne) fail = 1;
        }
        double t1 = 0, t2 = 0;
        for (int rep = 0; rep < 2; ++rep) { // alternated: alone, with region 2
            auto [ta, a1, a2] = run(s, 3, false, 500);
            auto [tb, b1, b2] = run(s, 2, false, 500);
            if (a2 || b2) fail = 1;
            t1 += ta / 2, t2 += tb / 2;
        }
        std::printf("   time: XchgPull %7.1f us/exchange, XchgPull2 %7.1f (+%.1f us for %u tokens' partials)\n", t1, t2, t2 - t1, s.M);
        std::fflush(stdout);
    }
    for (int c = 0; c < N; ++c)
        for (int d = 0; d < N; ++d)
            if (c != d) zeMemCloseIpcHandle(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[c]), peer[c][d]);
    std::printf(fail ? "FAIL\n" : "PASS\n");
    return fail;
}
