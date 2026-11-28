// bench_tanh: the cost of the card's strict tanh / exp (as the engine builds them) and exhaustive bit checks of other
// sequences against them over all 2^32 float inputs. bench_tanh <card>
#include "../../src/device.hpp"
#include <cstdio>
#include <cstring>

using namespace ink;

// out[i] = f(bits base + i); returns the number of inputs (non-NaN results) where f and g differ
template <class F, class G> long long diff_all(sycl::queue &q, F f, G g, unsigned long long *cnt, unsigned *first) {
    const size_t chunk = (size_t)1 << 28;
    q.memset(cnt, 0, 8).wait();
    q.memcpy(first, &(const unsigned &)0xffffffffu, 4).wait();
    for (unsigned long long base = 0; base < (1ull << 32); base += chunk) {
        q.parallel_for(sycl::range<1>(chunk), [=](sycl::id<1> i) {
            const unsigned b = (unsigned)(base + i[0]);
            const float x = sycl::bit_cast<float>(b);
            const float a = f(x), c = g(x);
            const unsigned ua = sycl::bit_cast<unsigned>(a), uc = sycl::bit_cast<unsigned>(c);
            if (ua != uc && !(sycl::isnan(a) && sycl::isnan(c))) {
                sycl::atomic_ref<unsigned long long, sycl::memory_order::relaxed, sycl::memory_scope::device> r(*cnt);
                r.fetch_add(1ull);
                sycl::atomic_ref<unsigned, sycl::memory_order::relaxed, sycl::memory_scope::device> fr(*first);
                fr.fetch_min(b);
            }
        });
    }
    q.wait();
    unsigned long long n; q.memcpy(&n, cnt, 8).wait();
    return (long long)n;
}

// MIX: each lane's arguments pseudo-random in [-1, 1] (lanes of a sub-group take different branches), else
// consecutive values in [-6, 6]
template <int MIX = 0, class F> double rate(sycl::queue &q, F f, float *out, const char *name) {
    const size_t n = (size_t)1 << 26;
    auto go = [&] {
        q.parallel_for(sycl::range<1>(n), [=](sycl::id<1> i) {
            unsigned hsh = (unsigned)i[0] * 2654435761u;
            hsh ^= hsh >> 15; hsh *= 2246822519u; hsh ^= hsh >> 13;
            float x = MIX ? (float)(hsh >> 8) * (2.0f / 16777216.0f) - 1.0f : -6.0f + (float)i[0] * (12.0f / (float)(1 << 26)), s = 0.0f;
#pragma unroll 1
            for (int k = 0; k < 16; ++k) { s += f(x); x = x + 1e-3f; }
            out[i[0]] = s;
        });
    };
    go(); q.wait();
    const double t0 = now_s();
    for (int r = 0; r < 5; ++r) go();
    q.wait();
    const double t = (now_s() - t0) / 5, g = (double)n * 16 / t / 1e9;
    std::printf("%-30s %8.2f G/s  (%.1f ps each card-wide)\n", name, g, 1e3 / g);
    return g;
}

int main(int argc, char **argv) {
    Device d(argc > 1 ? std::atoi(argv[1]) : 1);
    float *out = d.alloc<float>((size_t)1 << 26);
    rate(d.q, [](float x) { return x * 1.0001f; }, out, "multiply (loop floor)");
    rate(d.q, [](float x) { return sycl::tanh(x); }, out, "sycl::tanh");
    rate(d.q, [](float x) { return sycl::exp(x); }, out, "sycl::exp");
    rate(d.q, [](float x) { return 1.0f / (1.0f + x * x); }, out, "1 / (1 + x x) (strict div)");
    rate(d.q, [](float x) { return (sycl::tanh(x * (1.0f / 1.7f)) * 1.7f) * (1.0f / (1.0f + sycl::exp(-x))); }, out, "SITU gate part");
    rate<1>(d.q, [](float x) { return x * 1.0001f; }, out, "mixed: multiply (loop floor)");
    rate<1>(d.q, [](float x) { return sycl::tanh(x); }, out, "mixed: sycl::tanh");
    rate<1>(d.q, [](float x) { return sycl::exp(x); }, out, "mixed: sycl::exp");
    rate<1>(d.q, [](float x) { return (sycl::tanh(x * (1.0f / 1.7f)) * 1.7f) * (1.0f / (1.0f + sycl::exp(-x))); }, out, "mixed: SITU gate part");
    rate<1>(d.q, [](float x) { return sycl::tanh(x * 0.1f + 0.5f); }, out, "one branch: tanh(0.4..0.6)");
    rate<1>(d.q, [](float x) { return sycl::tanh(x * 0.3f); }, out, "one branch: tanh(-0.3..0.3)");
    return 0;
}
