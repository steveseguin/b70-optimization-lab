// bench_tlb <card>: does reading the same bytes from a larger region cost more (address translation misses)?
// Each launch reads 8 blocks of 3 MB (the 8 experts of a one-token gate|up product: 24 MB) at random 3 MB-aligned places
// inside the first F GB of one 12 GB allocation, the next launch other places (64 sets in turn, so the reads come from
// memory, not L2). Prints us per launch and GB/s for F from 0.1 to 12 GB, then the same inside a 2 MB-aligned and a
// 1 GB-aligned allocation (aligned_alloc_device), and the allocations' address alignment.
#include <cmath>
#include <random>
#include "../src/device.hpp"

using namespace ink;

static sycl::event rd(sycl::queue &q, const sycl::uint4 *base, const uint64_t *offs, size_t n, int wgpc, unsigned *out) {
    constexpr int WG = 256, U = 4;
    const size_t T = (size_t)wgpc * WG;
    return q.parallel_for(sycl::nd_range<2>(sycl::range<2>(8, T), sycl::range<2>(1, WG)), [=](sycl::nd_item<2> it) {
        const sycl::uint4 *p = base + offs[it.get_group(0)];
        const size_t id = it.get_global_id(1);
        unsigned a = 0;
        size_t i = id;
        for (; i + (U - 1) * T < n; i += U * T) {
            sycl::uint4 v[U];
#pragma unroll
            for (int u = 0; u < U; ++u) v[u] = p[i + u * T];
#pragma unroll
            for (int u = 0; u < U; ++u) a ^= v[u].x() ^ v[u].y() ^ v[u].z() ^ v[u].w();
        }
        for (; i < n; i += T) { const sycl::uint4 v = p[i]; a ^= v.x() ^ v.y() ^ v.z() ^ v.w(); }
        if (a == 0x9e3779b9u) out[id % 1024] = a;
    });
}

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_tlb <card>\n"); return 2; }
    try {
        Device d(std::atoi(argv[1]));
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 400;
        const size_t GB = 1ull << 30, total = 12 * GB, chunk = 3ull << 20, n = chunk / 16;
        constexpr int SETS = 64;
        unsigned *out = d.alloc<unsigned>(1024);
        uint64_t *offs = d.alloc<uint64_t>(SETS * 8);
        auto run = [&](const char *what, sycl::uint4 *base) {
            std::printf("%s (address %% 1 GB = %llu MB, %% 2 MB = %llu KB)\n", what,
                        (unsigned long long)(((uintptr_t)base % GB) >> 20), (unsigned long long)(((uintptr_t)base % (2u << 20)) >> 10));
            for (double F : {0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 12.0}) {
                const size_t region = (size_t)(F * GB), slots = region / chunk;
                std::mt19937_64 rng(5);
                std::vector<uint64_t> h(SETS * 8);
                for (auto &o : h) o = (rng() % slots) * (chunk / 16);
                d.put(offs, h.data(), h.size());
                for (int wgpc : {72}) {
                    auto launch = [&](int k) { rd(d.q, base, offs + (size_t)(k % SETS) * 8, n, wgpc, out); };
                    for (int k = 0; k < 16; ++k) launch(k);
                    d.q.wait();
                    const double t0 = now_s();
                    for (int k = 0; k < iters; ++k) launch(k);
                    d.q.wait();
                    const double us = (now_s() - t0) / iters * 1e6;
                    std::printf("  region %5.2f GB: %6.2f us per 24 MB launch, %5.0f GB/s\n", F, us, 8.0 * chunk / us / 1e3);
                }
            }
        };
        {
            sycl::uint4 *big = sycl::malloc_device<sycl::uint4>(total / 16, d.q);
            if (!big) throw std::runtime_error("no 12 GB allocation");
            d.q.memset(big, 0, total).wait();
            run("malloc_device 12 GB", big);
            sycl::free(big, d.q);
        }
        {
            sycl::uint4 *big = static_cast<sycl::uint4 *>(sycl::aligned_alloc_device(2u << 20, total, d.q));
            if (!big) throw std::runtime_error("no 12 GB allocation (2 MB aligned)");
            d.q.memset(big, 0, total).wait();
            run("aligned_alloc_device 2 MB, 12 GB", big);
            sycl::free(big, d.q);
        }
        {
            sycl::uint4 *big = static_cast<sycl::uint4 *>(sycl::aligned_alloc_device(GB, total, d.q));
            if (!big) throw std::runtime_error("no 12 GB allocation (1 GB aligned)");
            d.q.memset(big, 0, total).wait();
            run("aligned_alloc_device 1 GB, 12 GB", big);
            sycl::free(big, d.q);
        }
        return 0;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "bench_tlb: %s\n", e.what());
        return 1;
    }
}
