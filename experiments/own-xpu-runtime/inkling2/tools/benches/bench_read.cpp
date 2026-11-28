// bench_read <card>: how fast one launch can read N MB on this card (the floor for the writing step's products).
// Back-to-back launches on the in-order queue (as in the engine), each reading a different buffer so the reads come
// from memory, not L2. Variants: work-groups of 256 threads, NWG groups, each thread loading U 16-byte values per round
// (grid stride: round r, slot u -> element (r * U + u) * threads + id). Prints µs per launch and GB/s.
#include <cmath>
#include "../../src/device.hpp"

using namespace ink;

template <int U>
static sycl::event rd(sycl::queue &q, const sycl::uint4 *p, size_t n, int nwg, unsigned *out) {
    constexpr int WG = 256;
    const size_t T = (size_t)nwg * WG;
    return q.parallel_for(sycl::nd_range<1>(T, WG), [=](sycl::nd_item<1> it) {
        const size_t id = it.get_global_id(0);
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
        if (a == 0x9e3779b9u) out[id % 1024] = a; // keeps the loads; never true for the zero-filled buffers
    });
}

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_read <card>\n"); return 2; }
    try {
        Device d(std::atoi(argv[1]));
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 100;
        const double sizes[] = {2, 4, 8, 12, 16, 21, 24, 32, 64, 380};
        unsigned *out = d.alloc<unsigned>(1024);
        for (double mb : sizes) {
            const size_t bytes = (size_t)(mb * 1e6) / 16 * 16, n = bytes / 16;
            const int nbuf = (int)std::max<size_t>(2, (size_t)(512e6 / bytes)) > 24 ? 24 : (int)std::max<size_t>(2, (size_t)(512e6 / bytes));
            std::vector<sycl::uint4 *> bufs;
            for (int b = 0; b < nbuf; ++b) {
                bufs.push_back(d.alloc<sycl::uint4>(n));
                d.q.memset(bufs.back(), 0, bytes);
            }
            d.q.wait();
            std::printf("%6.0f MB (%d buffers):", mb, nbuf);
            for (int nwg : {128, 256, 512, 1024, 2048}) {
                for (int U : {1, 4, 8}) {
                    auto launch = [&](int k) {
                        const sycl::uint4 *p = bufs[k % nbuf];
                        if (U == 1) rd<1>(d.q, p, n, nwg, out);
                        else if (U == 4) rd<4>(d.q, p, n, nwg, out);
                        else rd<8>(d.q, p, n, nwg, out);
                    };
                    for (int k = 0; k < 3; ++k) launch(k);
                    d.q.wait();
                    const int it2 = mb > 100 ? std::max(4, iters / 20) : iters;
                    const double t0 = now_s();
                    for (int k = 0; k < it2; ++k) launch(k);
                    d.q.wait();
                    const double us = (now_s() - t0) / it2 * 1e6;
                    std::printf("  %d/%d %.1f us %.0f GB/s", nwg, U, us, bytes / us / 1e3);
                }
            }
            std::printf("\n");
            for (auto *b : bufs) d.release(b);
        }
        return 0;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "bench_read: %s\n", e.what());
        return 1;
    }
}
