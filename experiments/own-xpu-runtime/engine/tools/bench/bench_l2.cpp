// Does a dense GEMV run faster when its weights were pulled into the card's cache first?
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/experimental/prefetch.hpp>
#include <algorithm>
#include <cstdio>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
using namespace ops41sycl;
namespace syclex = sycl::ext::oneapi::experimental;

int main(int argc, char **argv) {
    int card = argc > 1 ? atoi(argv[1]) : 0;
    unsigned rows = argc > 2 ? atoi(argv[2]) : 1024;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    sycl::device dev = l0.at(card);
    sycl::context ctx(dev);
    sycl::queue q(ctx, dev, sycl::property_list{sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    std::printf("card %d: global mem cache %zu KiB, line %u\n", card, (size_t)dev.get_info<sycl::info::device::global_mem_cache_size>() / 1024,
                dev.get_info<sycl::info::device::global_mem_cache_line_size>());
    const size_t prb = pk41::packed_row_bytes(iq3::Type::Q8_0, 5120);
    const size_t wb = prb * rows;
    uint8_t *w = sycl::malloc_device<uint8_t>(wb, q);
    q.memset(w, 0x11, wb).wait();
    float *x = sycl::malloc_device<float>(5120, q), *y = sycl::malloc_device<float>(rows, q);
    q.memset(x, 0, 5120 * 4).wait();
    const size_t EV = (size_t)512 << 20;
    uint32_t *ev = sycl::malloc_device<uint32_t>(EV / 4, q), *sink = sycl::malloc_device<uint32_t>(1024, q);
    q.memset(ev, 1, EV).wait();
    auto evict = [&] {
        return q.parallel_for(sycl::nd_range<1>(4096 * 256, 256), [=](sycl::nd_item<1> it) {
            uint32_t a = 0;
            for (size_t i = it.get_global_linear_id(); i < EV / 4; i += 4096 * 256) a ^= ev[i];
            if (a == 0x12345678u) sink[0] = a;
        });
    };
    auto gemv = [&] {
        const size_t nwg = (rows + 15) / 16;
        return q.parallel_for(sycl::nd_range<1>(nwg * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            GemvQ8P<160, ActF32>{rows, 0}(it, w, x, y);
        });
    };
    auto touch = [&](int nwg) { // plain loads, 16 B per item per step
        return q.parallel_for(sycl::nd_range<1>((size_t)nwg * 256, 256), [=](sycl::nd_item<1> it) {
            const sycl::uint4 *p = reinterpret_cast<const sycl::uint4 *>(w);
            uint32_t a = 0;
            for (size_t i = it.get_global_linear_id(); i < wb / 16; i += (size_t)nwg * 256) { auto v = p[i]; a ^= v.x() ^ v.w(); }
            if (a == 0x12345678u) sink[1] = a;
        });
    };
    auto pf = [&](int nwg) { // prefetch instruction, one 64 B line per item per step
        return q.parallel_for(sycl::nd_range<1>((size_t)nwg * 256, 256), [=](sycl::nd_item<1> it) {
            for (size_t i = it.get_global_linear_id(); i < wb / 64; i += (size_t)nwg * 256)
                syclex::prefetch((void *)(w + i * 64), syclex::properties{syclex::prefetch_hint_L3});
        });
    };
    auto dur = [](sycl::event e) {
        return (e.get_profiling_info<sycl::info::event_profiling::command_end>() - e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
    };
    auto med = [](std::vector<double> v) { std::sort(v.begin(), v.end()); return v[v.size() / 2]; };
    // warm the clocks
    for (int i = 0; i < 200; ++i) gemv();
    q.wait();
    std::vector<double> cold, warm, after_touch, after_pf, t_touch, t_pf, t_touch32;
    for (int r = 0; r < 15; ++r) {
        evict(); for (int i = 0; i < 20; ++i) gemv(); // keep busy, then
        evict(); cold.push_back(dur(gemv()));
        warm.push_back(dur(gemv()));
        evict(); auto e1 = touch(256); after_touch.push_back(dur(gemv())); t_touch.push_back(dur(e1));
        evict(); auto e3 = touch(32); after_touch.push_back(0); t_touch32.push_back(dur(e3)); gemv();
        evict(); auto e2 = pf(256); after_pf.push_back(dur(gemv())); t_pf.push_back(dur(e2));
        q.wait();
    }
    after_touch.erase(std::remove(after_touch.begin(), after_touch.end(), 0.0), after_touch.end());
    std::printf("rows %u (%.2f MB): gemv cold %.2f us, warm (again) %.2f us, after touch %.2f us, after prefetch %.2f us\n", rows, wb / 1e6,
                med(cold), med(warm), med(after_touch), med(after_pf));
    std::printf("touch kernel 256 wg %.2f us, 32 wg %.2f us; prefetch kernel 256 wg %.2f us\n", med(t_touch), med(t_touch32), med(t_pf));
    return 0;
}
