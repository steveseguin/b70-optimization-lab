// Compile-only probe (2026-11-10): does select_from_group(sg, v, k + (lane >> 3)) compile to a free register
// region on the B70? Answer: no (indirect-register moves r[a0.0] and extra ALU). Build with
//   IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir=d icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 \
//     -fp-model=precise -ffp-contract=off probe_lane_group_region.cpp -o /dev/null   and read d/*simd32*.asm
#include <sycl/sycl.hpp>
#include <cstdint>
#include <cstdio>
int main() {
    sycl::queue q;
    uint32_t *w = sycl::malloc_device<uint32_t>(1 << 20, q);
    uint16_t *w16 = sycl::malloc_device<uint16_t>(1 << 20, q);
    float *x = sycl::malloc_device<float>(1 << 20, q), *y = sycl::malloc_device<float>(1 << 16, q);
    // A: 16-bit pre-shifted indices, lane group l8 takes element 4g + l8 of a 32-lane register of uint16 pairs
    q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> lt(2048, h);
        h.parallel_for(sycl::nd_range<1>(4096, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            float *tab = &lt[0];
            for (unsigned k = it.get_local_linear_id(); k < 2048; k += 512) tab[k] = float(k & 63);
            sycl::group_barrier(it.get_group());
            auto sg = it.get_sub_group();
            const unsigned lane = sg.get_local_linear_id(), l8 = lane >> 3, j4 = (lane & 7) << 2;
            const unsigned r = it.get_global_linear_id() / 32;
            const uint32_t wv = sg.load(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(w + r * 32));
            const uint32_t sv = sg.load(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(w + 65536 + r * 32));
            const float dv = x[r * 32 + lane];
            const char *tb = reinterpret_cast<const char *>(tab);
            const unsigned ssh = 31u - 8u * l8 - (lane & 7);
            float sum = 0;
#pragma unroll
            for (unsigned g = 0; g < 8; ++g) {
                // the low / high 16 bits of word 2g + (l8 >> 1): index of lane group l8 (pre-shifted by 5)
                const uint32_t wsel = sycl::select_from_group(sg, wv, 2 * g + (l8 >> 1));
                const uint32_t idx = (l8 & 1) ? (wsel >> 16) : (wsel & 0xFFFFu);
                const float mag = *reinterpret_cast<const float *>(tb + (idx | j4));
                const uint32_t es = sycl::select_from_group(sg, sv, g);
                const float db = sycl::select_from_group(sg, dv, g);
                const uint32_t sb = (es << ssh) & 0x80000000u;
                const float v = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ sb);
                sum = sum + v * x[g * 32 + lane];
            }
            y[it.get_global_linear_id()] = sum;
        });
    });
    // B: byte region (index byte l8 of a broadcast word)
    q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> lt(2048, h);
        h.parallel_for(sycl::nd_range<1>(4096, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            float *tab = &lt[0];
            for (unsigned k = it.get_local_linear_id(); k < 2048; k += 512) tab[k] = float(k & 63);
            sycl::group_barrier(it.get_group());
            auto sg = it.get_sub_group();
            const unsigned lane = sg.get_local_linear_id(), l8 = lane >> 3, j4 = (lane & 7) << 2;
            const unsigned r = it.get_global_linear_id() / 32;
            const uint16_t hv = w16[r * 32 + lane];
            const char *tb = reinterpret_cast<const char *>(tab);
            float sum = 0;
#pragma unroll
            for (unsigned g = 0; g < 8; ++g) {
                const uint32_t idx = sycl::select_from_group(sg, hv, 4 * g + l8);
                const float mag = *reinterpret_cast<const float *>(tb + ((uint32_t(idx) << 5) | j4));
                sum = sum + mag * x[g * 32 + lane];
            }
            y[it.get_global_linear_id()] = sum;
        });
    });
    q.wait();
    std::printf("ok\n");
}
