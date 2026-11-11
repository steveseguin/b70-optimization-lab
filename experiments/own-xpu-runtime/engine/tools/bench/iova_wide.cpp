// Moves each card's IOMMU address allocations above 4 GiB for the rest of the boot (the kernel's
// "xe 0000:..: Using 46-bit DMA addresses" line), by mapping a peer allocation larger than the 32-bit space.
// The kernel's DMA layer first allocates a device's I/O virtual addresses below 4 GiB (the PCI 32-bit
// workaround); the first allocation that does not fit there turns that off for the device until it is
// re-probed, and from then on every new mapping (peer card memory, host memory) is placed below 2^46.
// In the boot before the 2026-11-10 15:16 reset this had happened at 15:32 on 2026-11-09 for five cards; after
// the reset it had not, and the card-to-card exchanges ran 10-20 % slower (round 18 r1 vs e83 profiles).
//
// For each card c: GIB GiB on card (c + 1) % 6, opened in card c's context through its IPC handle (card c's
// DMA mapping of the peer's memory), one kernel on card c reading its first and last float, then closed and freed.
// Prints, per card, whether the kernel log has the line afterwards (reads `journalctl -k`).
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -Wno-deprecated-declarations \
//     tools/bench/iova_wide.cpp -o iova_wide -lze_loader
//   ./iova_wide [GiB, default 5]
#include <sycl/sycl.hpp>
#include <level_zero/ze_api.h>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

int main(int argc, char **argv) {
    const size_t GIB = argc > 1 ? (size_t)atol(argv[1]) : 5;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const int N = (int)l0.size();
    if (N < 2) { std::printf("needs two or more cards, found %d\n", N); return 1; }
    std::vector<sycl::context> ctx;
    std::vector<sycl::queue> q;
    std::vector<std::string> pci;
    for (int c = 0; c < N; ++c) {
        ctx.emplace_back(l0[c]);
        q.emplace_back(ctx[c], l0[c], sycl::property::queue::in_order{});
        pci.push_back(l0[c].get_info<sycl::ext::intel::info::device::pci_address>());
    }
    const size_t n = GIB << 28; // floats
    int fail = 0;
    for (int c = 0; c < N; ++c) {
        const int d = (c + 1) % N;
        float *big = sycl::malloc_device<float>(n, q[d]);
        if (!big) { std::printf("card %s: %zu GiB allocation failed\n", pci[d].c_str(), GIB); return 1; }
        q[d].fill(big, 1.0f, n).wait();
        ze_ipc_mem_handle_t h;
        void *p = nullptr;
        if (zeMemGetIpcHandle(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[d]), big, &h) != ZE_RESULT_SUCCESS ||
            zeMemOpenIpcHandle(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[c]),
                               sycl::get_native<sycl::backend::ext_oneapi_level_zero>(l0[c]), h, 0, &p) != ZE_RESULT_SUCCESS || !p) {
            std::printf("card %s <- %s: IPC open failed\n", pci[c].c_str(), pci[d].c_str());
            sycl::free(big, q[d]);
            ++fail;
            continue;
        }
        float *r = sycl::malloc_host<float>(2, ctx[c]);
        const float *pp = (const float *)p;
        q[c].single_task([=] { r[0] = pp[0]; r[1] = pp[n - 1]; }).wait();
        std::printf("card %s read %zu GiB of card %s: %g %g\n", pci[c].c_str(), GIB, pci[d].c_str(), r[0], r[1]);
        if (r[0] != 1.0f || r[1] != 1.0f) ++fail;
        sycl::free(r, ctx[c]);
        zeMemCloseIpcHandle(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[c]), p);
        sycl::free(big, q[d]);
    }
    std::fflush(stdout);
    for (int c = 0; c < N; ++c) {
        const std::string cmd = "journalctl -b -k -o cat | grep -q '" + pci[c] + ": Using 46-bit DMA addresses'";
        std::printf("card %s: %s\n", pci[c].c_str(), std::system(cmd.c_str()) == 0 ? "46-bit DMA addresses" : "still 32-bit first");
    }
    return fail ? 1 : 0;
}
