// sq bench (2026-11-12 22:55): five peers one after another (peer-major) instead of at once.
// sg bench (2026-11-12 22:50): why are EU peer pushes ~1 GB/s here but 64 KiB in ~6 us in bcs_lat? Variants: sub-group
// size (-DSG=16/32), one peer only vs five, back-to-back vs waited reps.
// ce bench (2026-11-12 21:15): store cache hints for peer pushes + copy paths. Derived from pt/xchg_bw_bench.cpp.
// All-gather bandwidth across the six B70s (one SYCL context per card, Level Zero IPC peers, as the engine).
// Every card owns a slice of S bytes and sends it to the five peers; all six cards do it at the same time
// (one host thread per card), R times back to back. Reports the time per exchange (slowest card) and the
// bytes each card sends per second. Shapes:
//   push-mix  : nwg work-groups, every item writes its 16 bytes to all peers in turn (XchgP / XchgPushM)
//   push-dest : work-group g writes only to peer g % 5 (long runs to one peer)
//   pull      : every card reads its five peers' slices into its own memory
//   copy      : queue.memcpy own slice -> each peer (engine-chosen copy path)
//   fence-one : push-dest with one system fence per work-group (after a barrier) instead of one per item
// Usage: xchg_bw_bench [slice_KiB_list] [R]   e.g. xchg_bw_bench 16,64,160,640 50
// Build: icpx -fsycl -O2 -std=c++20 xchg_bw_bench.cpp -o xchg_bw_bench -lze_loader
// Run with NEOReadDebugKeys=1 DisableIndirectAccess=1 (as own_run_v41): peer pointers must be direct kernel
// arguments (below), never members of a by-value struct.
#include <sycl/sycl.hpp>
#include <level_zero/ze_api.h>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <sycl/ext/intel/experimental/cache_control_properties.hpp>
#include <barrier>
#ifndef SG
#define SG 32
#endif
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>
static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }

int main(int argc, char **argv) {
    std::vector<size_t> sizes;
    {
        std::string s = argc > 1 ? argv[1] : "16,64,160,640";
        size_t p = 0;
        while (p < s.size()) {
            size_t q = s.find(',', p);
            if (q == std::string::npos) q = s.size();
            sizes.push_back((size_t)atoll(s.substr(p, q - p).c_str()) * 1024);
            p = q + 1;
        }
    }
    const int R = argc > 2 ? atoi(argv[2]) : 50;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const int N = (int)l0.size();
    if (N < 2) { std::printf("need 2+ cards\n"); return 1; }
    size_t maxs = 0;
    for (size_t s : sizes) maxs = std::max(maxs, s);
    const size_t ARENA = maxs * N + 4096; // card c's slice at c * S; same layout everywhere
    std::vector<sycl::context> ctx;
    std::vector<sycl::queue> q;
    std::vector<float *> arena(N);
    for (int c = 0; c < N; ++c) {
        ctx.emplace_back(l0[c]);
        q.emplace_back(ctx[c], l0[c], sycl::property::queue::in_order{});
        arena[c] = sycl::malloc_device<float>(ARENA / 4, q[c]);
        q[c].memset(arena[c], 0, ARENA).wait();
    }
    std::vector<std::vector<float *>> peer(N, std::vector<float *>(N, nullptr));
    for (int d = 0; d < N; ++d) {
        ze_ipc_mem_handle_t h;
        auto zxd = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[d]);
        if (zeMemGetIpcHandle(zxd, arena[d], &h) != ZE_RESULT_SUCCESS) { std::printf("ipc get failed\n"); return 1; }
        for (int c = 0; c < N; ++c) {
            if (c == d) { peer[c][d] = arena[d]; continue; }
            void *p = nullptr;
            auto zxc = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[c]);
            auto zdc = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(l0[c]);
            if (zeMemOpenIpcHandle(zxc, zdc, h, 0, &p) != ZE_RESULT_SUCCESS || !p) { std::printf("ipc open failed\n"); return 1; }
            peer[c][d] = (float *)p;
        }
    }
    std::printf("%d cards\n", N);
    struct P6 { float *p[6]; };
    auto run = [&](const char *name, size_t S, int nwg, int mode, bool solo, int hint = 0, bool one = false, bool gap = false) {
        // mode 0 push-mix, 1 push-dest, 2 pull, 3 copy, 4 push-dest fence-one
        std::barrier sync(N);
        std::vector<double> t(N, 0.0);
        auto body = [&](int c) {
            P6 pp{};
            for (int d = 0; d < N && d < 6; ++d) pp.p[d] = peer[c][d];
            const unsigned n4 = (unsigned)(S / 16), me = (unsigned)c, nn = (unsigned)N;
            const size_t off = (size_t)c * S / 4;
            auto once1 = [&](int hint) {
                if (mode == 3) {
                    for (int d = 0; d < N; ++d)
                        if (d != c) q[c].memcpy(pp.p[d] + off, pp.p[c] + off, S);
                    return;
                }
                // every peer pointer is its own (direct) kernel argument: the engine runs with the driver's
                // indirect-access mode off (DisableIndirectAccess=1), so a pointer inside a by-value struct
                // would not be made resident and the kernel page-faults (it did, 2026-11-09 23:58)
                float *q0 = pp.p[0], *q1 = pp.p[1], *q2 = pp.p[2], *q3 = pp.p[3], *q4 = pp.p[4], *q5 = pp.p[5];
                q[c].parallel_for(sycl::nd_range<1>((size_t)nwg * 256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                    // a select chain, not an array: a pointer loaded from an indexed array counts as indirect too
                    auto pick = [=](unsigned d) { return d == 0 ? q0 : d == 1 ? q1 : d == 2 ? q2 : d == 3 ? q3 : d == 4 ? q4 : q5; };
                    const size_t T = it.get_global_range(0), g = it.get_global_linear_id();
                    if (mode == 0) {
                        const sycl::vec<float, 4> *own = reinterpret_cast<const sycl::vec<float, 4> *>(pick(me) + off);
                        for (size_t k = g; k < n4; k += T) {
                            const sycl::vec<float, 4> v = own[k];
                            for (unsigned d = 0; d < nn; ++d)
                                if (d != me) reinterpret_cast<sycl::vec<float, 4> *>(pick(d) + off)[k] = v;
                        }
                        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
                    } else if (mode == 5) {
                        // every work-group walks the five peers in the same order (me+1, me+2, ...): at any moment
                        // most of this card's stores go to ONE peer
                        const sycl::vec<float, 4> *own = reinterpret_cast<const sycl::vec<float, 4> *>(pick(me) + off);
                        for (unsigned p = 1; p < nn; ++p) {
                            sycl::vec<float, 4> *dst = reinterpret_cast<sycl::vec<float, 4> *>(pick((me + p) % nn) + off);
                            for (size_t k = g; k < n4; k += T) dst[k] = own[k];
                        }
                        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
                    } else if (mode == 6) {
                        const sycl::vec<float, 4> *own = reinterpret_cast<const sycl::vec<float, 4> *>(pick(me) + off);
                        sycl::vec<float, 4> *dst = reinterpret_cast<sycl::vec<float, 4> *>(pick((me + (unsigned)hint) % nn) + off);
                        for (size_t k = g; k < n4; k += T) dst[k] = own[k];
                        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
                    } else if (mode == 1 || mode == 4) {
                        const unsigned grp = (unsigned)it.get_group_linear_id(), ng = (unsigned)it.get_group_range(0);
                        const unsigned np = one ? 1u : nn - 1, gpp = std::max(1u, ng / np); // groups per peer
                        const unsigned di = grp % np, gi = grp / np;
                        if (gi < gpp) {
                            const unsigned d = di < me ? di : di + 1;
                            const sycl::vec<float, 4> *own = reinterpret_cast<const sycl::vec<float, 4> *>(pick(me) + off);
                            sycl::vec<float, 4> *dst = reinterpret_cast<sycl::vec<float, 4> *>(pick(d) + off);
                            namespace sx = sycl::ext::oneapi::experimental; namespace ix = sycl::ext::intel::experimental;
                            using V = sycl::vec<float, 4>;
                            const size_t k0 = (size_t)gi * 256 + it.get_local_linear_id(), ks = (size_t)gpp * 256;
                            if (hint == 0) { for (size_t k = k0; k < n4; k += ks) dst[k] = own[k]; }
                            else if (hint == 1) { sx::annotated_ptr<V, decltype(sx::properties(ix::write_hint<ix::cache_control<ix::cache_mode::uncached, sx::cache_level::L1, sx::cache_level::L3>>))> a(dst); for (size_t k = k0; k < n4; k += ks) a[k] = own[k]; }
                            else if (hint == 2) { sx::annotated_ptr<V, decltype(sx::properties(ix::write_hint<ix::cache_control<ix::cache_mode::streaming, sx::cache_level::L1>, ix::cache_control<ix::cache_mode::write_back, sx::cache_level::L3>>))> a(dst); for (size_t k = k0; k < n4; k += ks) a[k] = own[k]; }
                            else if (hint == 3) { sx::annotated_ptr<V, decltype(sx::properties(ix::write_hint<ix::cache_control<ix::cache_mode::uncached, sx::cache_level::L1>, ix::cache_control<ix::cache_mode::write_back, sx::cache_level::L3>>))> a(dst); for (size_t k = k0; k < n4; k += ks) a[k] = own[k]; }
                            else { sx::annotated_ptr<V, decltype(sx::properties(ix::write_hint<ix::cache_control<ix::cache_mode::write_through, sx::cache_level::L1>, ix::cache_control<ix::cache_mode::uncached, sx::cache_level::L3>>))> a(dst); for (size_t k = k0; k < n4; k += ks) a[k] = own[k]; }
                        }
                        if (mode == 1) sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
                        else {
                            sycl::group_barrier(it.get_group());
                            if (it.get_local_linear_id() == 0) sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
                        }
                    } else {
                        // pull: slices of all peers into my arena
                        for (unsigned d = 0; d < nn; ++d) {
                            if (d == me) continue;
                            const size_t o = (size_t)d * S / 4;
                            const sycl::vec<float, 4> *src = reinterpret_cast<const sycl::vec<float, 4> *>(pick(d) + o);
                            sycl::vec<float, 4> *dst = reinterpret_cast<sycl::vec<float, 4> *>(pick(me) + o);
                            for (size_t k = g; k < n4; k += T) dst[k] = src[k];
                        }
                    }
                });
            };
            auto once = [&]() { if (mode == 6) { for (int p = 1; p < N; ++p) once1(p); } else once1(hint); };
            once();
            q[c].wait();
            sync.arrive_and_wait();
            if (solo && c != 0) { sync.arrive_and_wait(); return; }
            const double t0 = now();
            for (int r = 0; r < R; ++r) { once(); if (gap) q[c].wait(); }
            q[c].wait();
            t[c] = now() - t0;
            sync.arrive_and_wait();
        };
        std::vector<std::thread> th;
        for (int c = 0; c < N; ++c) th.emplace_back(body, c);
        for (auto &x : th) x.join();
        double mx = 0;
        for (int c = 0; c < N; ++c) mx = std::max(mx, t[c]);
        const double per = mx / R;
        std::printf("%-10s %s S=%7zu B nwg=%3d  %8.1f us/exchange  %6.2f GB/s sent per card\n", name, solo ? "solo" : "all ",
                    S, nwg, per * 1e6, (double)S * (one ? 1 : N - 1) / per / 1e9);
    };
    for (size_t S : sizes) {
        run("pd-5peers", S, 20, 1, false);
        run("seq-5peers", S, 20, 5, false);
        run("seq-5peers", S, 64, 5, false);
        run("seq-5peers-solo", S, 64, 5, true);
        run("launch-per-peer", S, 20, 6, false);
        run("launch-per-peer", S, 64, 6, false);
        run("pull", S, 64, 2, false);
    }
    // values check per transport: fill own slices, clear the rest, exchange once (R reps), compare everything
    auto vcheck = [&](const char *name, int mode, int hint) {
        for (int c = 0; c < N; ++c) {
            q[c].memset(arena[c], 0, maxs * N).wait();
            std::vector<float> hv(maxs / 4);
            for (size_t i = 0; i < hv.size(); ++i) hv[i] = float(c * 1000003 + i);
            q[c].memcpy(arena[c] + (size_t)c * maxs / 4, hv.data(), maxs).wait();
        }
        run(name, maxs, mode == 3 ? 0 : 64, mode, false, hint);
        size_t bad = 0;
        for (int c = 0; c < N; ++c) {
            std::vector<float> got(maxs * N / 4);
            q[c].memcpy(got.data(), arena[c], maxs * N).wait();
            for (int d = 0; d < N; ++d)
                for (size_t i = 0; i < maxs / 4; ++i) bad += got[(size_t)d * maxs / 4 + i] != float(d * 1000003 + i);
        }
        std::printf("values after %s: %zu wrong\n", name, bad);
    };
    vcheck("seq-5peers", 5, 0);
    vcheck("launch-per-peer", 6, 0);
    for (int c = 0; c < N; ++c)
        for (int d = 0; d < N; ++d)
            if (c != d) zeMemCloseIpcHandle(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[c]), peer[c][d]);
    return 0;
}
