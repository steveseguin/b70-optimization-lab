// B70 SYCL device probe: gemv over a real IQ2_XXS tensor slice, host
// comparison, bandwidth measure. Proves device decode path and sizes the
// decode-bound design.
#include <sycl/sycl.hpp>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
#include "stage2/packet2/kernels/math.hpp"

int main(int argc, char **argv) {
    const char *shard = "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-00002-of-00006.gguf";
    // token_embd.weight: IQ2_XXS [5120, 129280] in shard 2; offset from placement
    // usage: probe OFFSET [NROWS] [TYPE_ID] [COLS]
    long data_start = 24032;
    long offset = -1, rows = 129280, cols = 5120;
    iq3::Type ttype = iq3::Type::IQ2_XXS;
    if (argc > 1) offset = atol(argv[1]);
    if (argc > 3) ttype = (iq3::Type)atoi(argv[3]);
    if (argc > 4) cols = atol(argv[4]);
    if (offset < 0) { std::fprintf(stderr, "need placement offset\n"); return 2; }

    int fd = open(shard, O_RDONLY);
    struct stat st; fstat(fd, &st);
    auto *file = (const uint8_t *)mmap(nullptr, st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    auto lay = iq3::layout(ttype);
    size_t rb = (size_t)(cols / lay.elements) * lay.bytes;
    const uint8_t *base = file + data_start + offset;

    int nrows = argc > 2 ? atoi(argv[2]) : 4096; // rows to test
    std::vector<float> x(cols);
    for (int i = 0; i < cols; ++i) x[i] = std::sin(i * 0.01f);

    // host reference
    std::vector<float> href(nrows);
    auto t0 = std::chrono::steady_clock::now();
    for (int r = 0; r < nrows; ++r) {
        const uint8_t *row = base + (size_t)r * rb;
        float acc = 0;
        for (int c = 0; c < cols; ++c)
            acc += iq3::decode(ttype, row + (size_t)(c / lay.elements) * lay.bytes, c % lay.elements) * x[c];
        href[r] = acc;
    }
    auto t1 = std::chrono::steady_clock::now();
    double host_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

    sycl::queue q(sycl::gpu_selector_v);
    std::printf("device: %s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    size_t bytes = (size_t)nrows * rb;
    uint8_t *dw = sycl::malloc_device<uint8_t>(bytes, q);
    float *dx = sycl::malloc_device<float>(cols, q);
    float *dy = sycl::malloc_device<float>(nrows, q);
    q.memcpy(dw, base, bytes).wait();
    q.memcpy(dx, x.data(), cols * 4).wait();

    auto launch = [&](int iters) {
        auto ev = q.submit([&](sycl::handler &h) {
            h.parallel_for(sycl::range<1>(nrows), [=](sycl::id<1> id) {
                int r = id[0];
                const uint8_t *row = dw + (size_t)r * rb;
                float acc = 0;
                for (int c = 0; c < cols; ++c)
                    acc += iq3::decode(ttype, row + (size_t)(c / lay.elements) * lay.bytes,
                                       c % lay.elements) * dx[c];
                dy[r] = acc;
            });
        });
        return ev;
    };
    auto t2 = std::chrono::steady_clock::now();
    launch(1).wait();
    auto t3 = std::chrono::steady_clock::now();
    double dev_ms = std::chrono::duration<double, std::milli>(t3 - t2).count();

    std::vector<float> out(nrows);
    q.memcpy(out.data(), dy, nrows * 4).wait();
    double max_rel = 0;
    for (int r = 0; r < nrows; ++r) {
        double rel = std::fabs(out[r] - href[r]) / std::max(1e-6, (double)std::fabs(href[r]));
        max_rel = std::max(max_rel, rel);
    }
    // bandwidth over 10 iters
    auto t4 = std::chrono::steady_clock::now();
    for (int i = 0; i < 10; ++i) launch(1);
    q.wait();
    auto t5 = std::chrono::steady_clock::now();
    double ms10 = std::chrono::duration<double, std::milli>(t5 - t4).count() / 10;
    double gb = (double)bytes / 1e9;
    std::printf("rows=%d bytes=%.3fGB host=%.1fms dev=%.2fms steady=%.2fms bw=%.1fGB/s max_rel=%.3g\n",
                nrows, gb, host_ms, dev_ms, ms10, gb / (ms10 / 1000), max_rel);
    sycl::free(dw, q); sycl::free(dx, q); sycl::free(dy, q);
    return max_rel < 1e-3 ? 0 : 1;
}
