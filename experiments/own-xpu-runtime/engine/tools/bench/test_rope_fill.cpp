// test_rope_fill (ropedev-1, 2026-11-16): can a card fill the rope window itself, bit for bit as the host does?
// The host (build_rope_tables / rope_fill) stores (float)std::cos(p * f[i]) and (float)std::sin(p * f[i]) for 32 pair
// slots per position, p an int, f the 32 double frequencies (yarn: theta 160000, factor 16, beta 32 / 1, orig 65536;
// base: theta 10000). Here the card computes the same expression in double (sycl::cos / sycl::sin) for every position
// of the model's 1,048,576 and both frequency sets, and every float is compared with glibc's. Prints the number of
// differing floats (and the first few); last line "PASS (0 of N differ)" or "FAIL (k of N differ)".
// Why: a window refresh copies 8 MiB from ordinary host memory, and the runtime then shares a temporary host
// allocation with the five other cards (dma-buf attaches, PCI config reads) in the middle of a run.
// Build as the other benches (build124.sh): icpx -fsycl ... -fp-model=precise -ffp-contract=off ...
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>

static std::vector<double> freqs(int yarn) { // copy of build_rope_tables' fill (backend_sycl_v41.hpp)
    const int dim = 64;
    double base = yarn ? 160000.0 : 10000.0;
    std::vector<double> f(dim / 2);
    for (int i = 0; i < dim / 2; ++i) f[i] = 1.0 / std::pow(base, (2.0 * i) / dim);
    if (yarn) {
        double orig = 65536.0, factor = 16.0, beta_fast = 32.0, beta_slow = 1.0;
        auto corrected = [&](double rot) { return dim * std::log(orig / (rot * 2 * M_PI)) / (2 * std::log(base)); };
        double low = std::max(std::floor(corrected(beta_fast)), 0.0);
        double high = std::min(std::ceil(corrected(beta_slow)), (double)dim - 1);
        for (int i = 0; i < dim / 2; ++i) {
            double ramp = std::clamp((i - low) / std::max(high - low, 1e-3), 0.0, 1.0);
            double smooth = 1 - ramp;
            f[i] = f[i] / factor * (1 - smooth) + f[i] * smooth;
        }
    }
    return f;
}

int main(int argc, char **argv) {
    const long P = argc > 1 ? atol(argv[1]) : 1048576;
    constexpr long CH = 16384; // one window
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}}};
    std::printf("device: %s, fp64 %d, positions %ld\n", q.get_device().get_info<sycl::info::device::name>().c_str(),
                (int)q.get_device().has(sycl::aspect::fp64), P);
    if (!q.get_device().has(sycl::aspect::fp64)) {
        std::printf("FAIL (no fp64)\n");
        return 2;
    }
    double *df = sycl::malloc_device<double>(64, q);
    float *dc = sycl::malloc_device<float>((size_t)CH * 32, q), *ds = sycl::malloc_device<float>((size_t)CH * 32, q);
    std::vector<float> hc((size_t)CH * 32), hs((size_t)CH * 32);
    long bad = 0, total = 0, shown = 0;
    for (int yarn = 0; yarn < 2; ++yarn) {
        const std::vector<double> f = freqs(yarn);
        q.memcpy(df, f.data(), 32 * sizeof(double)).wait();
        for (long p0 = 0; p0 < P; p0 += CH) {
            const long n = std::min(CH, P - p0);
            const int pb = (int)p0;
            q.parallel_for(sycl::range<1>((size_t)n * 32), [=](sycl::id<1> id) {
                 const size_t k = id[0];
                 const int p = pb + (int)(k / 32);
                 const double x = p * df[k % 32];
                 dc[k] = (float)sycl::cos(x);
                 ds[k] = (float)sycl::sin(x);
             }).wait();
            q.memcpy(hc.data(), dc, (size_t)n * 32 * 4);
            q.memcpy(hs.data(), ds, (size_t)n * 32 * 4).wait();
            for (long qq = 0; qq < n; ++qq) {
                const int p = (int)(p0 + qq);
                for (int i = 0; i < 32; ++i) {
                    const float c = (float)std::cos(p * f[i]), s = (float)std::sin(p * f[i]);
                    const size_t k = (size_t)qq * 32 + i;
                    total += 2;
                    const bool bc = std::memcmp(&c, &hc[k], 4) != 0, bs = std::memcmp(&s, &hs[k], 4) != 0;
                    if (bc || bs) {
                        bad += bc + bs;
                        if (shown++ < 12)
                            std::printf("differ: %s p %d i %d: cos host %.9g card %.9g, sin host %.9g card %.9g\n",
                                        yarn ? "yarn" : "base", p, i, c, hc[k], s, hs[k]);
                    }
                }
            }
        }
    }
    if (bad) std::printf("FAIL (%ld of %ld differ)\n", bad, total);
    else std::printf("PASS (0 of %ld differ)\n", total);
    return bad ? 1 : 0;
}
