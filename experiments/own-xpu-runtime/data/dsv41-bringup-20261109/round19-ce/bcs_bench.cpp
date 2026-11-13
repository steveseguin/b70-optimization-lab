// bcs bench (2026-11-12 21:20): Level Zero copy-engine (BCS) immediate command lists for peer PUSH copies, six B70s,
// one SYCL context per card (as the engine), peer memory via IPC. Questions:
//  1. which queue groups does a card expose (compute / copy, how many engines)?
//  2. all-gather push speed on the copy engine (own slice -> 5 peers, all cards at once), vs memcpy on the SYCL queue
//  3. does a copy-engine push run beside a compute kernel without slowing it (true overlap)?
// Build: icpx -fsycl -O2 -std=c++20 -fsycl-targets=intel_gpu_bmg_g31 bcs_bench.cpp -o bcs_bench -lze_loader
#include <sycl/sycl.hpp>
#include <level_zero/ze_api.h>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <barrier>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>
static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
#define ZC(x) do { ze_result_t r_ = (x); if (r_ != ZE_RESULT_SUCCESS) { std::printf("ZE error 0x%x at %s:%d\n", (unsigned)r_, __FILE__, __LINE__); std::exit(2); } } while (0)

int main(int argc, char **argv) {
    const int R = argc > 1 ? atoi(argv[1]) : 20;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const int N = (int)l0.size();
    const size_t MAXS = 4u << 20, ARENA = MAXS * N + 4096, BUSY = 256u << 20;
    std::vector<sycl::context> ctx; std::vector<sycl::queue> q; std::vector<float *> arena(N), busy(N);
    std::vector<ze_context_handle_t> zx(N); std::vector<ze_device_handle_t> zd(N);
    std::vector<ze_command_list_handle_t> bcs(N);
    int copy_ord = -1, copy_n = 0;
    for (int c = 0; c < N; ++c) {
        ctx.emplace_back(l0[c]);
        q.emplace_back(ctx[c], l0[c], sycl::property::queue::in_order{});
        arena[c] = sycl::malloc_device<float>(ARENA / 4, q[c]);
        busy[c] = sycl::malloc_device<float>(BUSY / 4, q[c]);
        q[c].memset(arena[c], 0, ARENA).wait();
        q[c].memset(busy[c], 0, BUSY).wait();
        zx[c] = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[c]);
        zd[c] = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(l0[c]);
        uint32_t ng = 0; ZC(zeDeviceGetCommandQueueGroupProperties(zd[c], &ng, nullptr));
        std::vector<ze_command_queue_group_properties_t> gp(ng);
        for (auto &g : gp) g = {ZE_STRUCTURE_TYPE_COMMAND_QUEUE_GROUP_PROPERTIES};
        ZC(zeDeviceGetCommandQueueGroupProperties(zd[c], &ng, gp.data()));
        int co = -1;
        for (uint32_t i = 0; i < ng; ++i) {
            const bool comp = gp[i].flags & ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COMPUTE, cp = gp[i].flags & ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COPY;
            if (c == 0) std::printf("card0 group %u: %s%s engines %u\n", i, comp ? "compute " : "", cp ? "copy" : "", gp[i].numQueues);
            if (cp && !comp && co < 0) { co = (int)i; if (c == 0) copy_n = gp[i].numQueues; }
        }
        if (co < 0) { std::printf("no copy-only group\n"); return 1; }
        copy_ord = co;
        ze_command_queue_desc_t qd = {ZE_STRUCTURE_TYPE_COMMAND_QUEUE_DESC, nullptr, (uint32_t)co, 0, 0,
                                      ZE_COMMAND_QUEUE_MODE_ASYNCHRONOUS, ZE_COMMAND_QUEUE_PRIORITY_NORMAL};
        ZC(zeCommandListCreateImmediate(zx[c], zd[c], &qd, &bcs[c]));
    }
    std::printf("%d cards, copy group ordinal %d (%d engines)\n", N, copy_ord, copy_n);
    std::vector<std::vector<float *>> peer(N, std::vector<float *>(N, nullptr));
    for (int d = 0; d < N; ++d) {
        ze_ipc_mem_handle_t h; ZC(zeMemGetIpcHandle(zx[d], arena[d], &h));
        for (int c = 0; c < N; ++c) {
            if (c == d) { peer[c][d] = arena[d]; continue; }
            void *p = nullptr; ZC(zeMemOpenIpcHandle(zx[c], zd[c], h, 0, &p)); peer[c][d] = (float *)p;
        }
    }
    // a compute kernel that streams over 256 MiB of local memory K times (~ms); returns time alone
    auto busy_k = [&](int c, int K) {
        float *b = busy[c]; const size_t n4 = BUSY / 16;
        return q[c].parallel_for(sycl::nd_range<1>(160 * 1024, 1024), [=](sycl::nd_item<1> it) {
            sycl::vec<float, 4> *v = reinterpret_cast<sycl::vec<float, 4> *>(b);
            const size_t T = it.get_global_range(0);
            for (int k = 0; k < K; ++k)
                for (size_t i = it.get_global_linear_id(); i < n4; i += T) v[i] = v[i] * 0.5f + 1.0f;
        });
    };
    auto push = [&](int c, size_t S) { // own slice -> 5 peers on the copy engine
        const size_t off = (size_t)c * S / 4;
        for (int d = 0; d < N; ++d)
            if (d != c) ZC(zeCommandListAppendMemoryCopy(bcs[c], peer[c][d] + off, arena[c] + off, S, nullptr, 0, nullptr));
    };
    auto sq_copy = [&](int c, size_t S) {
        const size_t off = (size_t)c * S / 4;
        for (int d = 0; d < N; ++d) if (d != c) q[c].memcpy(peer[c][d] + off, arena[c] + off, S);
    };
    for (size_t S : {(size_t)64 << 10, (size_t)640 << 10, (size_t)4 << 20}) {
        // fill own slices, clear others, for the values check
        for (int c = 0; c < N; ++c) {
            q[c].memset(arena[c], 0, S * N).wait();
            std::vector<float> hv(S / 4); for (size_t i = 0; i < hv.size(); ++i) hv[i] = float(c * 1000003 + i);
            q[c].memcpy(arena[c] + (size_t)c * S / 4, hv.data(), S).wait();
        }
        // mode: 0 bcs push alone, 1 sycl memcpy alone, 2 busy kernel alone, 3 busy + bcs push together
        for (int mode = 0; mode < 4; ++mode) {
            std::barrier sync(N); std::vector<double> t(N);
            auto body = [&](int c) {
                const int K = 4;
                // warm
                if (mode == 0 || mode == 3) { push(c, S); ZC(zeCommandListHostSynchronize(bcs[c], UINT64_MAX)); }
                if (mode == 1) { sq_copy(c, S); q[c].wait(); }
                if (mode >= 2) { busy_k(c, K); q[c].wait(); }
                sync.arrive_and_wait();
                const double t0 = now();
                for (int r = 0; r < R; ++r) {
                    if (mode >= 2) busy_k(c, K);
                    if (mode == 0 || mode == 3) push(c, S);
                    if (mode == 1) sq_copy(c, S);
                }
                if (mode == 0 || mode == 3) ZC(zeCommandListHostSynchronize(bcs[c], UINT64_MAX));
                q[c].wait();
                t[c] = (now() - t0) / R;
                sync.arrive_and_wait();
            };
            std::vector<std::thread> th; for (int c = 0; c < N; ++c) th.emplace_back(body, c); for (auto &x : th) x.join();
            double mx = 0; for (double v : t) mx = std::max(mx, v);
            const char *nm[] = {"bcs-push", "sycl-memcpy", "busy-alone", "busy+bcs-push"};
            std::printf("%-14s S=%8zu B  %9.1f us per round  %6.2f GB/s sent per card\n", nm[mode], S, mx * 1e6,
                        mode == 2 ? 0.0 : (double)S * (N - 1) / mx / 1e9);
        }
        size_t bad = 0;
        for (int c = 0; c < N; ++c) {
            std::vector<float> got(S * N / 4); q[c].memcpy(got.data(), arena[c], S * N).wait();
            for (int d = 0; d < N; ++d) for (size_t i = 0; i < S / 4; ++i) bad += got[(size_t)d * S / 4 + i] != float(d * 1000003 + i);
        }
        std::printf("values S=%zu: %zu wrong\n", S, bad);
    }
    for (int c = 0; c < N; ++c) {
        for (int d = 0; d < N; ++d) if (c != d) zeMemCloseIpcHandle(zx[c], peer[c][d]);
        zeCommandListDestroy(bcs[c]);
    }
    return 0;
}
