// bcs_sync (2026-11-12 21:35): which producer -> copy-engine sync works on this runtime? One card, no spinning kernels.
// A: native handle of the kernel's SYCL event; B: own L0 event signalled on the SYCL queue's native immediate list;
// C: native handle of q.ext_oneapi_submit_barrier(). A ~1 ms kernel fills src; the copy engine copies src -> dst after
// the sync; host waits on the copy list with a 2 s timeout; dst must hold the kernel's values (proves the order).
#include <sycl/sycl.hpp>
#include <level_zero/ze_api.h>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <variant>
#include <vector>
static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
#define ZC(x) do { ze_result_t r_ = (x); if (r_ != ZE_RESULT_SUCCESS) { std::printf("ZE error 0x%x at line %d\n", (unsigned)r_, __LINE__); } } while (0)
int main(int argc, char **argv) {
    setvbuf(stdout, nullptr, _IONBF, 0);
    const int card = argc > 1 ? atoi(argv[1]) : 0;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    sycl::device dev = l0.at(card);
    sycl::context ctx(dev);
    sycl::queue q(ctx, dev, sycl::property::queue::in_order{});
    const size_t n = 1 << 20;
    unsigned *src = sycl::malloc_device<unsigned>(n, q), *dst = sycl::malloc_device<unsigned>(n, q);
    auto zx = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx);
    auto zd = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(dev);
    ze_command_queue_desc_t qd = {ZE_STRUCTURE_TYPE_COMMAND_QUEUE_DESC, nullptr, 1u, 0, 0, ZE_COMMAND_QUEUE_MODE_ASYNCHRONOUS, ZE_COMMAND_QUEUE_PRIORITY_NORMAL};
    ze_command_list_handle_t bcs; ZC(zeCommandListCreateImmediate(zx, zd, &qd, &bcs));
    auto nq = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(q);
    std::printf("queue native: %s\n", std::holds_alternative<ze_command_list_handle_t>(nq) ? "immediate command list" : "command queue");
    ze_event_pool_desc_t pd = {ZE_STRUCTURE_TYPE_EVENT_POOL_DESC, nullptr, ZE_EVENT_POOL_FLAG_HOST_VISIBLE, 64};
    ze_event_pool_handle_t pool; ZC(zeEventPoolCreate(zx, &pd, 1, &zd, &pool));
    for (int variant = 0; variant < 3; ++variant) {
        for (int rep = 0; rep < 3; ++rep) {
            const unsigned val = 1000u * (variant + 1) + rep;
            q.memset(src, 0, n * 4); q.memset(dst, 0, n * 4); q.wait();
            auto ev = q.parallel_for(sycl::range<1>(n), [=](sycl::id<1> i) {
                unsigned x = (unsigned)i[0];
                for (int k = 0; k < 20000; ++k) x = x * 1664525u + 1013904223u; // several ms of ALU
                src[i] = (x == 0x7FFFFFFFu && i[0] == 3u) ? 0u : val; });
            ze_event_handle_t w = nullptr, own = nullptr;
            if (variant == 0) w = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ev);
            else if (variant == 1) {
                ze_event_desc_t ed = {ZE_STRUCTURE_TYPE_EVENT_DESC, nullptr, (uint32_t)rep, ZE_EVENT_SCOPE_FLAG_DEVICE, ZE_EVENT_SCOPE_FLAG_HOST};
                ZC(zeEventCreate(pool, &ed, &own));
                if (std::holds_alternative<ze_command_list_handle_t>(nq)) ZC(zeCommandListAppendSignalEvent(std::get<ze_command_list_handle_t>(nq), own));
                else { std::printf("B: not an immediate list, skipped\n"); zeEventDestroy(own); break; }
                w = own;
            } else {
                auto bev = q.ext_oneapi_submit_barrier();
                w = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(bev);
            }
            const bool kdone = ev.get_info<sycl::info::event::command_execution_status>() == sycl::info::event_command_status::complete;
            const double t0 = now();
            ZC(zeCommandListAppendMemoryCopy(bcs, dst, src, n * 4, nullptr, 1, &w));
            ze_result_t rs = zeCommandListHostSynchronize(bcs, 2000000000ull);
            const double t1 = now();
            if (rs != ZE_RESULT_SUCCESS && own) { zeEventHostSignal(own); rs = zeCommandListHostSynchronize(bcs, 2000000000ull); std::printf("  (rescued by host signal)\n"); }
            q.wait();
            std::vector<unsigned> h(n); q.memcpy(h.data(), dst, n * 4).wait();
            size_t bad = 0; for (unsigned x : h) bad += x != val;
            std::printf("variant %c rep %d (kernel %s at append): copy %s after %.3f ms, dst wrong %zu of %zu\n", "ABC"[variant], rep, kdone ? "DONE" : "running",
                        rs == ZE_RESULT_SUCCESS ? "done" : "NOT DONE (2 s)", (t1 - t0) * 1e3, bad, n);
            if (own) zeEventDestroy(own);
            if (rs != ZE_RESULT_SUCCESS) break;
        }
    }
    zeEventPoolDestroy(pool); zeCommandListDestroy(bcs);
    return 0;
}
