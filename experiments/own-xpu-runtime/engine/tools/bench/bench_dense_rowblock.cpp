// Row-blocked multi-token dense rows (GemvQ8P::rowgr<G, R>, DenseRowsGR) against the one-token kernel,
// BITWISE per token, and timed against the production adapter (DenseRowsG<GemvQ8P, G>) on one card, at the
// block step's Q8_0 shapes. Cold timing: a 128 MiB read before every launch (the matrix is evicted, as in a
// decode step; a written flush leaves dirty lines that are written back during the timed launch). Blocks of 5 and
// 6 tokens also as ONE token group (G5 / G6: the matrix read once, OWN_MT_TGW_ROWS). Exit status 1 on any mismatch.
//
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src \
//     tools/bench/bench_dense_rowblock.cpp -o $S/bench_dense_rowblock
//   LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib $S/bench_dense_rowblock [CARD]
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
using namespace ops41sycl;

static constexpr unsigned MTMAX = 8;

static constexpr size_t FLUSH_WORDS = (size_t)64 << 20; // 256 MiB
static uint32_t *g_flush = nullptr;
static int g_fail = 0;

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
// evict by READING 256 MiB (a written flush leaves dirty lines that are written back during the timed launch);
// the store never happens (the buffer holds no word equal to v + 0x80000000)
static void flush(sycl::queue &q, uint32_t v) {
    const uint32_t *p = g_flush;
    uint32_t *o = g_flush;
    q.parallel_for(sycl::range<1>(FLUSH_WORDS / 4), [=](sycl::id<1> i) {
        const size_t b = (size_t)i[0];
        const uint32_t s = p[b] ^ p[b + FLUSH_WORDS / 4] ^ p[b + FLUSH_WORDS / 2] ^ p[b + 3 * FLUSH_WORDS / 4];
        if (s == v + 0x80000000u) o[b] = 0;
    });
}
template <typename T> T *dev_copy(sycl::queue &q, const std::vector<T> &h) {
    T *d = sycl::malloc_device<T>(h.size(), q);
    q.memcpy(d, h.data(), h.size() * sizeof(T)).wait();
    return d;
}
static std::vector<float> rand_f(size_t n, unsigned seed, float lo, float hi) {
    std::mt19937 rng(seed);
    std::uniform_real_distribution<float> u(lo, hi);
    std::vector<float> v(n);
    for (auto &f : v) f = u(rng);
    return v;
}
template <iq3::Type T> static std::vector<uint8_t> packed_rows(unsigned cols, unsigned rows, unsigned seed) {
    constexpr auto L = iq3::layout(T);
    const size_t rb = (size_t)cols / L.elements * L.bytes, prb = pk41::packed_row_bytes(T, cols);
    std::mt19937 rng(seed);
    std::vector<uint8_t> hw((size_t)rows * rb);
    for (auto &b : hw) b = uint8_t(rng());
    for (size_t blk = 0; blk < hw.size() / L.bytes; ++blk) {
        uint8_t *bp = hw.data() + blk * L.bytes;
        auto put = [&](size_t off) { uint16_t h = 0x1400 + (rng() & 0x3ff); bp[off] = h & 255; bp[off + 1] = h >> 8; };
        if (T == iq3::Type::Q8_0) put(0);
        if (T == iq3::Type::Q6_K) put(208);
    }
    std::vector<uint8_t> hp((size_t)rows * prb);
    for (size_t r = 0; r < rows; ++r) pk41::pack_row(T, hw.data() + r * rb, hp.data() + r * prb, cols);
    return hp;
}

template <typename K_> struct Shape {
    using K = K_;
    K k;
    const uint8_t *w;
    const float *x;
    size_t xs, ys;
    float *yr, *ym;
    std::vector<float> ref;
    char name[48];
};

template <typename RW> static sycl::event launch(sycl::queue &q, const RW &rw, size_t wg) {
    const RowsP<RW> kr{rw};
    const size_t per = wg / 32, nwg = ((size_t)rw.n() + per - 1) / per;
    return q.parallel_for(sycl::nd_range<1>(nwg * wg, wg),
                          [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kr(it); });
}
template <typename RW> static double warm_us(sycl::queue &q, const RW &rw, size_t wg) {
    double best = 1e30;
    for (unsigned rep = 0; rep < 12; ++rep) {
        sycl::event e = launch(q, rw, wg);
        q.wait();
        best = std::min(best, ev_us(e));
    }
    return best;
}
template <typename RW> static double cold_us(sycl::queue &q, const RW &rw, size_t wg) {
    for (int i = 0; i < 30; ++i) launch(q, rw, wg);
    q.wait();
    double best = 1e30;
    for (unsigned rep = 0; rep < 12; ++rep) {
        flush(q, rep);
        sycl::event e = launch(q, rw, wg);
        q.wait();
        best = std::min(best, ev_us(e));
    }
    return best;
}
template <typename K, typename RW>
static void check_time(sycl::queue &q, Shape<K> &s, const RW &rw, unsigned M, const char *what, size_t wg,
                       double base) {
    const size_t n = (size_t)MTMAX * s.ys;
    q.memset(s.ym, 0xff, n * 4).wait();
    launch(q, rw, wg).wait();
    std::vector<float> got(n);
    q.memcpy(got.data(), s.ym, n * 4).wait();
    size_t differ = 0, stray = 0;
    for (unsigned t = 0; t < MTMAX; ++t)
        for (size_t i = 0; i < s.ys; ++i) {
            const float *g = &got[t * s.ys + i];
            if (t < M && i < s.k.rows) differ += std::memcmp(g, &s.ref[t * s.ys + i], 4) != 0;
            else {
                uint32_t u;
                std::memcpy(&u, g, 4);
                stray += u != 0xffffffffu;
            }
        }
    const bool ok = !differ && !stray;
    g_fail += !ok;
    const double us = cold_us(q, rw, wg), wu = warm_us(q, rw, wg);
    std::printf("%s %-22s M %u %-10s wg %3zu | differ %zu stray %zu | warm %6.1f us | cold %7.1f us%s", ok ? "PASS" : "FAIL",
                s.name, M, what, wg, differ, stray, wu, us, base > 0 ? "" : "\n");
    if (base > 0) std::printf(" (x%.2f)\n", base / us);
    std::fflush(stdout);
}
template <unsigned G, unsigned R, typename K> static DenseRowsGR<K, G, R> gr(Shape<K> &s, unsigned M) {
    return {s.k, s.w, s.x, s.xs, s.ym, s.ys, M, (M + G - 1) / G};
}
template <unsigned G, typename K> static DenseRowsG<K, G> g1(Shape<K> &s, unsigned M) {
    return {s.k, s.w, s.x, s.xs, s.ym, s.ys, M, (M + G - 1) / G};
}

template <typename K, iq3::Type T> static void run_shape(sycl::queue &q, const char *fmt, unsigned cols, unsigned rows, unsigned seed) {
    Shape<K> s{};
    s.k.rows = rows;
    s.k.xn = 0;
    std::snprintf(s.name, sizeof s.name, "%s %ux%u", fmt, cols, rows);
    s.xs = (size_t)cols + 32;
    s.ys = rows + 8;
    const auto hw = packed_rows<T>(cols, rows, seed);
    s.w = dev_copy(q, hw);
    s.x = dev_copy(q, rand_f(MTMAX * s.xs, seed + 1, -2.0f, 2.0f));
    const size_t n = (size_t)MTMAX * s.ys;
    s.yr = sycl::malloc_device<float>(n, q);
    s.ym = sycl::malloc_device<float>(n, q);
    q.memset(s.yr, 0xff, n * 4).wait();
    for (unsigned t = 0; t < MTMAX; ++t) {
        const auto kk = s.k;
        const uint8_t *ww = s.w;
        const float *xx = s.x + t * s.xs;
        float *yy = s.yr + t * s.ys;
        q.parallel_for(sycl::nd_range<1>(((size_t)rows + 15) / 16 * 512, 512),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kk(it, ww, xx, yy); });
    }
    q.wait();
    s.ref.resize(n);
    q.memcpy(s.ref.data(), s.yr, n * 4).wait();
    std::printf("-- %s: weights %.2f MB\n", s.name, hw.size() / 1e6);
    const double b4 = cold_us(q, g1<2>(s, 4), 512);
    check_time(q, s, g1<2>(s, 4), 4, "G2 prod", 512, 0);
    check_time(q, s, g1<4>(s, 4), 4, "G4", 512, b4);
    check_time(q, s, gr<2, 2>(s, 4), 4, "G2 R2", 512, b4);
    check_time(q, s, gr<2, 4>(s, 4), 4, "G2 R4", 512, b4);
    check_time(q, s, gr<4, 2>(s, 4), 4, "G4 R2", 512, b4);
    check_time(q, s, gr<4, 4>(s, 4), 4, "G4 R4", 512, b4);
    const double b3 = cold_us(q, g1<3>(s, 3), 512);
    check_time(q, s, g1<3>(s, 3), 3, "G3 prod", 512, 0);
    check_time(q, s, gr<3, 2>(s, 3), 3, "G3 R2", 512, b3);
    check_time(q, s, gr<3, 4>(s, 3), 3, "G3 R4", 512, b3);
    const double b2 = cold_us(q, g1<1>(s, 2), 512);
    check_time(q, s, g1<1>(s, 2), 2, "G1 prod", 512, 0);
    check_time(q, s, g1<2>(s, 2), 2, "G2", 512, b2);
    check_time(q, s, gr<2, 2>(s, 2), 2, "G2 R2", 512, b2);
    check_time(q, s, gr<2, 4>(s, 2), 2, "G2 R4", 512, b2);
    const double b6 = cold_us(q, g1<3>(s, 6), 512);
    check_time(q, s, g1<3>(s, 6), 6, "G3 prod", 512, 0);
    check_time(q, s, gr<3, 2>(s, 6), 6, "G3 R2", 512, b6);
    check_time(q, s, gr<3, 4>(s, 6), 6, "G3 R4", 512, b6);
    check_time(q, s, g1<6>(s, 6), 6, "G6", 512, b6); // one token group: the matrix read once (OWN_MT_TGW_ROWS)
    check_time(q, s, gr<6, 2>(s, 6), 6, "G6 R2", 512, b6);
    const double b5 = cold_us(q, g1<3>(s, 5), 512);
    check_time(q, s, g1<3>(s, 5), 5, "G3 prod", 512, 0);
    check_time(q, s, gr<3, 4>(s, 5), 5, "G3 R4", 512, b5);
    check_time(q, s, g1<5>(s, 5), 5, "G5", 512, b5);
    check_time(q, s, gr<5, 2>(s, 5), 5, "G5 R2", 512, b5);
    const double b1 = cold_us(q, g1<1>(s, 1), 512);
    check_time(q, s, g1<1>(s, 1), 1, "G1", 512, 0);
    check_time(q, s, gr<1, 2>(s, 1), 1, "G1 R2", 512, b1);
    check_time(q, s, gr<1, 4>(s, 1), 1, "G1 R4", 512, b1);
    sycl::free((void *)s.w, q);
    sycl::free((void *)s.x, q);
    sycl::free(s.yr, q);
    sycl::free(s.ym, q);
}

int main(int argc, char **argv) {
    const int card = argc > 1 ? std::atoi(argv[1]) : 0;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const sycl::device dev = l0.at(card);
    const sycl::context ctx(dev);
    sycl::queue q(ctx, dev, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    std::printf("card %d %s\n", card, dev.get_info<sycl::info::device::name>().c_str());
    g_flush = sycl::malloc_device<uint32_t>(FLUSH_WORDS, q);
    q.memset(g_flush, 0, FLUSH_WORDS * 4).wait();
    using T = iq3::Type;
    const char *only = std::getenv("ONLY");
    auto want = [&](const char *n) { return !only || std::strstr(only, n); };
    if (want("q8")) {
        run_shape<GemvQ8P<40, ActF32>, T::Q8_0>(q, "Q8", 1280, 8192, 11); // query up-projection, a two-group card
        run_shape<GemvQ8P<40, ActF32>, T::Q8_0>(q, "Q8", 1280, 4096, 12); // ... a one-group card
        run_shape<GemvQ8P<128, ActF32>, T::Q8_0>(q, "Q8", 4096, 864, 13);
        run_shape<GemvQ8P<160, ActF32>, T::Q8_0>(q, "Q8", 5120, 384, 14);
        run_shape<GemvQ8P<256, ActF32>, T::Q8_0>(q, "Q8", 8192, 1024, 15);
    }
    if (want("q6")) {
        run_shape<GemvQ6KP<5, ActF32>, T::Q6_K>(q, "Q6K", 1280, 8192, 21);
        run_shape<GemvQ6KP<5, ActF32>, T::Q6_K>(q, "Q6K", 1280, 4096, 22);
        run_shape<GemvQ6KP<20, ActF32>, T::Q6_K>(q, "Q6K", 5120, 1280, 23);
    }
    sycl::free(g_flush, q);
    std::printf("%s: %d failed check(s)\n", g_fail ? "FAIL" : "PASS", g_fail);
    return g_fail ? 1 : 0;
}
