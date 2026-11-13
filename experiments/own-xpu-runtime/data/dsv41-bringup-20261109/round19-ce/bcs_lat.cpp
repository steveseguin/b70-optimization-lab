// bcs_lat (2026-11-12 21:20): one-way latency of a small card-to-card hand-off, pairs (0,1) (2,3) (4,5) ping-pong at once.
//  bcs  : kernel writes payload locally -> SYCL event -> copy engine copies payload + flag into the peer (posted writes)
//  eu   : kernel stores payload + flag straight into the peer (system fence), as the decode pushes do
//  pull : kernel publishes locally; the peer polls the REMOTE flag and reads the payload remotely
// The waiting side spins on a flag (bounded). One-way latency = time / (2 R). Payload P bytes.
// Build: icpx -fsycl -O2 -std=c++20 -fsycl-targets=intel_gpu_bmg_g31 bcs_lat.cpp -o bcs_lat -lze_loader
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
using AR = sycl::atomic_ref<unsigned, sycl::memory_order::relaxed, sycl::memory_scope::system, sycl::access::address_space::global_space>;
int main(int argc, char **argv) {
    setvbuf(stdout, nullptr, _IONBF, 0);
    const int R = argc > 1 ? atoi(argv[1]) : 1000;
    const int MODES = argc > 3 ? atoi(argv[3]) : 7; // bit mask of modes to run
    const unsigned P = argc > 2 ? (unsigned)atoi(argv[2]) : 4096;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const int N = (int)l0.size() / 2 * 2;
    // arena layout (unsigned words): [0..P/4) payload in, [P/4..2P/4) payload out (local staging), flag at 2P/4 + 64,
    // seq table (R + 2 words) after that, err word at the end
    const size_t FL = 2 * P / 4 + 64, SQ = FL + 64, ER = SQ + R + 64, W = ER + 64;
    std::vector<sycl::context> ctx; std::vector<sycl::queue> q; std::vector<unsigned *> ar(N);
    std::vector<ze_context_handle_t> zx(N); std::vector<ze_device_handle_t> zd(N); std::vector<ze_command_list_handle_t> bcs(N);
    for (int c = 0; c < N; ++c) {
        ctx.emplace_back(l0[c]); q.emplace_back(ctx[c], l0[c], sycl::property::queue::in_order{});
        ar[c] = sycl::malloc_device<unsigned>(W, q[c]);
        zx[c] = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[c]);
        zd[c] = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(l0[c]);
        ze_command_queue_desc_t qd = {ZE_STRUCTURE_TYPE_COMMAND_QUEUE_DESC, nullptr, 1u, 0, 0, ZE_COMMAND_QUEUE_MODE_ASYNCHRONOUS, ZE_COMMAND_QUEUE_PRIORITY_NORMAL};
        ZC(zeCommandListCreateImmediate(zx[c], zd[c], &qd, &bcs[c]));
    }
    std::vector<unsigned *> pr(N); // partner's arena mapped in my context
    for (int c = 0; c < N; ++c) {
        const int p = c ^ 1; ze_ipc_mem_handle_t h; ZC(zeMemGetIpcHandle(zx[p], ar[p], &h));
        void *m = nullptr; ZC(zeMemOpenIpcHandle(zx[c], zd[c], h, 0, &m)); pr[c] = (unsigned *)m;
    }
    for (int mode = 0; mode < 3; ++mode) {
        if (!(MODES >> mode & 1)) continue;
        std::printf("mode %d start\n", mode);
        for (int c = 0; c < N; ++c) {
            q[c].memset(ar[c], 0, W * 4).wait();
            std::vector<unsigned> sq(R + 2); for (int i = 0; i < R + 2; ++i) sq[i] = (unsigned)i;
            q[c].memcpy(ar[c] + SQ, sq.data(), (R + 2) * 4).wait();
        }
        std::barrier sync(N); std::vector<double> t(N);
        auto body = [&](int c) {
            unsigned *me = ar[c], *pe = pr[c];
            const bool first = (c & 1) == 0; // even card serves first
            auto wait_k = [&](unsigned v) { // spin until my flag (or the partner's flag for pull) reaches v; pull also reads
                q[c].single_task([=]() {
                    unsigned *f = mode == 2 ? pe + FL : me + FL;
                    unsigned n = 0;
                    if (AR(me[ER]).load()) return; // an earlier wait timed out: skip (poison)
                    while (AR(*f).load() < v) { if (++n > (1u << 22)) { AR(me[ER]).store(v); return; } }
                    if (mode == 2) { // read the payload remotely into my input
                        for (unsigned i = 0; i < P / 4; ++i) me[i] = pe[P / 4 + i];
                    }
                });
            };
            auto send_k = [&](unsigned v) { // produce payload v
                if (mode == 1) {
                    q[c].parallel_for(sycl::nd_range<1>(P / 16 < 256 ? 256 : P / 16, 256), [=](sycl::nd_item<1> it) {
                        const unsigned i = (unsigned)it.get_global_linear_id();
                        if (i < P / 16) reinterpret_cast<sycl::vec<unsigned, 4> *>(pe)[i] = sycl::vec<unsigned, 4>(v);
                        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
                        sycl::group_barrier(it.get_group());
                        if (i == 0) AR(pe[FL]).store(v);
                    });
                    return;
                }
                auto ev = q[c].parallel_for(sycl::nd_range<1>(P / 16 < 256 ? 256 : P / 16, 256), [=](sycl::nd_item<1> it) {
                    const unsigned i = (unsigned)it.get_global_linear_id();
                    if (i < P / 16) reinterpret_cast<sycl::vec<unsigned, 4> *>(me + P / 4)[i] = sycl::vec<unsigned, 4>(v);
                    if (mode == 2) {
                        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
                        sycl::group_barrier(it.get_group());
                        if (i == 0) AR(me[FL]).store(v); // publish locally; partner pulls
                    }
                });
                if (mode == 0) {
                    ze_event_handle_t ze = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ev);
                    ZC(zeCommandListAppendMemoryCopy(bcs[c], pe, me + P / 4, P, nullptr, 1, &ze));
                    ZC(zeCommandListAppendMemoryCopy(bcs[c], pe + FL, me + SQ + v, 4, nullptr, 0, nullptr));
                    if (v == 1) {
                        ze_result_t rs = zeCommandListHostSynchronize(bcs[c], 2000000000ull);
                        std::printf("card %d first copy after the kernel event: %s\n", c, rs == ZE_RESULT_SUCCESS ? "done" : "NOT DONE in 2 s");
                        if (rs != ZE_RESULT_SUCCESS) std::exit(3);
                    }
                }
            };
            sync.arrive_and_wait();
            const double t0 = now();
            for (int r = 1; r <= R; ++r) {
                if (c == 0 && (r == 1 || r % 500 == 0)) std::printf("  card 0 enqueued round %d at %.3f s\n", r, now() - t0);
                if (first) { send_k((unsigned)r); wait_k((unsigned)r); }
                else { wait_k((unsigned)r); send_k((unsigned)r); }
                if (mode == 2) { // pull: my flag is read by the partner; the next round needs the partner's flag > r
                }
            }
            q[c].wait(); if (mode == 0) ZC(zeCommandListHostSynchronize(bcs[c], UINT64_MAX));
            t[c] = now() - t0;
            sync.arrive_and_wait();
        };
        std::vector<std::thread> th; for (int c = 0; c < N; ++c) th.emplace_back(body, c); for (auto &x : th) x.join();
        double mx = 0; for (double v : t) mx = std::max(mx, v);
        unsigned err = 0, bad = 0;
        for (int c = 0; c < N; ++c) {
            unsigned e = 0; q[c].memcpy(&e, ar[c] + ER, 4).wait(); err += e != 0;
            std::vector<unsigned> in(P / 4); q[c].memcpy(in.data(), ar[c], P).wait();
            for (unsigned x : in) bad += x != (unsigned)R;
        }
        const char *nm[] = {"bcs", "eu-push", "pull"};
        std::printf("%-8s P=%6u B  R=%d  one-way %7.2f us  (timeouts %u, last payload wrong words %u)\n", nm[mode], P, R, mx / (2.0 * R) * 1e6, err, bad);
    }
    for (int c = 0; c < N; ++c) { zeMemCloseIpcHandle(zx[c], pr[c]); zeCommandListDestroy(bcs[c]); }
    return 0;
}
