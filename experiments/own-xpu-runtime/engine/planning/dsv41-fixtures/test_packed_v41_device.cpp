// Gate + timing for the packed-row kernels (pack_v41.hpp, ops41sycl::*P):
// every packed kernel at every production shape against the unpacked kernel it
// replaces (RoutedGemvT / GemvT / GemvGroupedQT, f32 activations), BITWISE on
// every output, plus each one's time. Exit status = number of failed shapes.
// Random rows with sane half scales; routed: 48-expert banks, 32 id sets.
//
//   $ICPX -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -I planning/dsv41-fixtures -I src planning/dsv41-fixtures/test_packed_v41_device.cpp -o /tmp/test_packed41
//   LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib /tmp/test_packed41 [CARD]
//   (ONLY=xxs,iq2s,iq3,iq2xs,iq1,q8,q6,q5,f32 selects tests; ROUTED_WG caps routed work-groups, default 128)
//
// 2026-11-09 history: the first IQ2_XXS 9-block kernel block-read 32 bytes past
// each row and faulted on the last row of a bank (row_words in sycl_v41.hpp).
#include <sycl/sycl.hpp>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"

using namespace ops41sycl;
static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
static unsigned g_cap = 128;
static int g_fail = 0;
template <unsigned NB, typename A> using IQ1B = RoutedIQ1SP<NB, A, true>;

template <iq3::Type T, template <unsigned, typename> class KP, unsigned NB>
void routed(sycl::queue &q, const char *name, unsigned rows, bool per_slot) {
    constexpr auto L = iq3::layout(T);
    const unsigned cols = NB * 256, E = 48;
    const size_t rb = (size_t)NB * L.bytes, prb = pk41::packed_row_bytes(T, cols);
    const size_t nrow = (size_t)E * rows;
    std::mt19937 rng(11 + (unsigned)T);
    std::vector<uint8_t> hw(nrow * rb);
    for (auto &b : hw) b = uint8_t(rng());
    for (size_t blk = 0; blk < nrow * NB; ++blk) {
        uint16_t h = 0x1400 + (rng() & 0x3ff); // half 1e-3 .. 2e-3
        hw[blk * L.bytes] = h & 255;
        hw[blk * L.bytes + 1] = h >> 8;
    }
    std::vector<uint8_t> hp(nrow * prb);
    for (size_t r = 0; r < nrow; ++r) pk41::pack_row(T, hw.data() + r * rb, hp.data() + r * prb, cols);
    const size_t nx = per_slot ? 6 * cols : cols;
    std::vector<float> hx(nx);
    for (auto &v : hx) v = std::uniform_real_distribution<float>(-2, 2)(rng);
    const int NSET = 32;
    std::vector<uint32_t> hids(NSET * 8);
    for (auto &v : hids) v = rng() % E;
    auto *dw = sycl::malloc_device<uint8_t>(hw.size(), q);
    auto *dp = sycl::malloc_device<uint8_t>(hp.size(), q);
    auto *dx = sycl::malloc_device<float>(nx, q);
    auto *di = sycl::malloc_device<uint32_t>(hids.size(), q);
    auto *o0 = sycl::malloc_device<float>(6 * rows, q);
    auto *o1 = sycl::malloc_device<float>(6 * rows, q);
    for (size_t o = 0; o < hw.size(); o += (64 << 20)) q.memcpy(dw + o, hw.data() + o, std::min<size_t>(64 << 20, hw.size() - o));
    for (size_t o = 0; o < hp.size(); o += (64 << 20)) q.memcpy(dp + o, hp.data() + o, std::min<size_t>(64 << 20, hp.size() - o));
    q.memcpy(dx, hx.data(), nx * 4);
    q.memcpy(di, hids.data(), hids.size() * 4).wait();
    const double el = 6.0 * rows * cols, by = 6.0 * rows * rb;
    auto timeit = [&](auto one) {
        for (int i = 0; i < 10; ++i) one(i);
        q.wait();
        const int N = 200;
        double t0 = now();
        for (int i = 0; i < N; ++i) one(i);
        q.wait();
        return (now() - t0) / N;
    };
    RoutedGemvT<T, ActF32> k0{rows, cols, per_slot};
    auto one0 = [&](int s) {
        const uint32_t *ip = di + (s % NSET) * 8;
        q.parallel_for(sycl::nd_range<1>((size_t)6 * rows * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            k0(it, dw, dx, ip, o0);
        });
    };
    using K = KP<NB, ActF32>;
    K k1{rows, per_slot};
    size_t nwg = ((size_t)6 * rows + 15) / 16;
    if (g_cap && nwg > g_cap) nwg = g_cap;
    auto one1 = [&](int s) {
        const uint32_t *ip = di + (s % NSET) * 8;
        q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(K::TAB, h);
            h.parallel_for(sycl::nd_range<1>(nwg * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k1(it, dp, dx, ip, o1, &lt[0]);
            });
        });
    };
    // equality over every id set
    size_t diff = 0;
    std::vector<float> a(6 * rows), b(6 * rows);
    for (int s = 0; s < NSET; ++s) {
        one0(s);
        q.wait();

        one1(s);
        q.wait();

        q.memcpy(a.data(), o0, a.size() * 4);
        q.memcpy(b.data(), o1, b.size() * 4).wait();
        for (size_t i = 0; i < a.size(); ++i) diff += std::memcmp(&a[i], &b[i], 4) != 0;
    }
    const double t0 = timeit(one0), t1 = timeit(one1);
    std::printf("%-10s %s cols %5u rows %5u slot_x %d | old %7.1f us %5.0f GB/s | packed %7.1f us %5.0f GB/s %5.0f Gel/s x%.2f | wg %zu | differ %zu of %zu\n",
                diff ? "FAIL" : "ok  ", name, cols, rows, (int)per_slot, t0 * 1e6, by / t0 / 1e9, t1 * 1e6, by / t1 / 1e9, el / t1 / 1e9, t0 / t1, nwg, diff,
                a.size() * NSET);
    g_fail += diff != 0;
    sycl::free(dw, q); sycl::free(dp, q); sycl::free(dx, q); sycl::free(di, q); sycl::free(o0, q); sycl::free(o1, q);
}

// K: packed kernel type (operator()(it, w, x, y)); xn > 0 = grouped (n rows per x group)
template <iq3::Type T, typename K>
void dense(sycl::queue &q, const char *name, unsigned cols, unsigned rows, unsigned xn, K kp) {
    constexpr auto L = iq3::layout(T);
    const size_t rb = (size_t)cols / L.elements * L.bytes;
    const bool pack = T != iq3::Type::F32;
    const size_t prb = pack ? pk41::packed_row_bytes(T, cols) : rb;
    std::mt19937 rng(17 + (unsigned)T + cols);
    std::vector<uint8_t> hw((size_t)rows * rb);
    if (T == iq3::Type::F32) {
        for (size_t i = 0; i < hw.size() / 4; ++i) {
            float f = std::uniform_real_distribution<float>(-0.05f, 0.05f)(rng);
            std::memcpy(&hw[i * 4], &f, 4);
        }
    } else {
        for (auto &b : hw) b = uint8_t(rng());
        const size_t nblk = hw.size() / L.bytes;
        for (size_t blk = 0; blk < nblk; ++blk) { // sane half scales
            uint8_t *bp = hw.data() + blk * L.bytes;
            auto put = [&](size_t off) { uint16_t h = 0x1400 + (rng() & 0x3ff); bp[off] = h & 255; bp[off + 1] = h >> 8; };
            if (T == iq3::Type::Q8_0) put(0);
            if (T == iq3::Type::Q6_K) put(208);
            if (T == iq3::Type::Q5_K) { put(0); put(2); }
        }
    }
    std::vector<uint8_t> hp((size_t)rows * prb);
    if (pack) for (size_t r = 0; r < rows; ++r) pk41::pack_row(T, hw.data() + r * rb, hp.data() + r * prb, cols);
    else hp = hw;
    const size_t nx = xn ? (size_t)rows / xn * cols : cols;
    std::vector<float> hx(nx);
    for (auto &v : hx) v = std::uniform_real_distribution<float>(-2, 2)(rng);
    auto *dw = sycl::malloc_device<uint8_t>(hw.size(), q);
    auto *dp = sycl::malloc_device<uint8_t>(hp.size(), q);
    auto *dx = sycl::malloc_device<float>(nx, q);
    auto *o0 = sycl::malloc_device<float>(rows, q);
    auto *o1 = sycl::malloc_device<float>(rows, q);
    for (size_t o = 0; o < hw.size(); o += (64 << 20)) q.memcpy(dw + o, hw.data() + o, std::min<size_t>(64 << 20, hw.size() - o));
    for (size_t o = 0; o < hp.size(); o += (64 << 20)) q.memcpy(dp + o, hp.data() + o, std::min<size_t>(64 << 20, hp.size() - o));
    q.memcpy(dx, hx.data(), nx * 4).wait();
    auto one0 = [&]() {
        if (xn) {
            GemvGroupedQT<T, ActF32> k0{xn, cols};
            q.parallel_for(sycl::nd_range<1>((size_t)rows * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k0(it, dw, dx, o0);
            });
        } else {
            GemvT<T, ActF32> k0{rows, cols, true};
            q.parallel_for(sycl::nd_range<1>((size_t)rows * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k0(it, dw, dx, o0);
            });
        }
    };
    auto one1 = [&]() {
        const size_t nwg = ((size_t)rows + 15) / 16;
        q.parallel_for(sycl::nd_range<1>(nwg * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            kp(it, dp, dx, o1);
        });
    };
    auto timeit = [&](auto one) {
        for (int i = 0; i < 10; ++i) one();
        q.wait();
        const int N = 200;
        double t0 = now();
        for (int i = 0; i < N; ++i) one();
        q.wait();
        return (now() - t0) / N;
    };
    one0(); one1(); q.wait();
    std::vector<float> a(rows), b(rows);
    q.memcpy(a.data(), o0, rows * 4);
    q.memcpy(b.data(), o1, rows * 4).wait();
    size_t diff = 0;
    for (size_t i = 0; i < rows; ++i) diff += std::memcmp(&a[i], &b[i], 4) != 0;
    const double t0 = timeit(one0), t1 = timeit(one1), by = (double)hw.size();
    std::printf("%-6s %s cols %5u rows %6u xn %4u | old %8.1f us %5.0f GB/s | packed %8.1f us %5.0f GB/s x%.2f | differ %zu of %u\n",
                diff ? "FAIL" : "ok  ", name, cols, rows, xn, t0 * 1e6, by / t0 / 1e9, t1 * 1e6, by / t1 / 1e9, t0 / t1, diff, rows);
    std::fflush(stdout);
    g_fail += diff != 0;
    sycl::free(dw, q); sycl::free(dp, q); sycl::free(dx, q); sycl::free(o0, q); sycl::free(o1, q);
}

int main(int argc, char **argv) {
    int card = argc > 1 ? atoi(argv[1]) : 0;
    if (const char *e = getenv("ROUTED_WG")) g_cap = (unsigned)atoi(e);
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    sycl::device dev = l0.at(card);
    sycl::context ctx(dev);
    sycl::queue q(ctx, dev, sycl::property::queue::in_order());
    std::printf("card %d %s\n", card, dev.get_info<sycl::info::device::name>().c_str());
    const char *only = getenv("ONLY");
    auto want = [&](const char *n) { return !only || strstr(only, n); };
    using T = iq3::Type;
    if (want("xxs")) routed<T::IQ2_XXS, RoutedIQ2XXSP, 20>(q, "IQ2_XXS", 2304, false);
    if (want("xxs")) routed<T::IQ2_XXS, RoutedIQ2XXSP, 9>(q, "IQ2_XXS", 5120, true);
    if (want("iq2s")) routed<T::IQ2_S, RoutedIQ2SP, 20>(q, "IQ2_S", 2304, false);
    if (want("iq2s")) routed<T::IQ2_S, RoutedIQ2SP, 9>(q, "IQ2_S", 5120, true);
    if (want("iq3")) routed<T::IQ3_XXS, RoutedIQ3XXSP, 9>(q, "IQ3_XXS", 5120, true);
    if (want("iq2xs")) routed<T::IQ2_XS, RoutedIQ2XSP, 9>(q, "IQ2_XS", 5120, true);
    if (want("iq1")) routed<T::IQ1_S, IQ1B, 20>(q, "IQ1_S", 2304, false);
    if (want("q8")) {
        dense<T::Q8_0>(q, "Q8_0", 1280, 32768, 0, GemvQ8P<40, ActF32>{32768, 0});
        dense<T::Q8_0>(q, "Q8_0", 4096, 8192, 1024, GemvQ8P<128, ActF32>{8192, 1024});
        dense<T::Q8_0>(q, "Q8_0", 8192, 5120, 0, GemvQ8P<256, ActF32>{5120, 0});
        dense<T::Q8_0>(q, "Q8_0", 5120, 2304, 0, GemvQ8P<160, ActF32>{2304, 0});
        dense<T::Q8_0>(q, "Q8_0", 2304, 5120, 0, GemvQ8P<72, ActF32>{5120, 0});
        dense<T::Q8_0>(q, "Q8_0", 5120, 512, 0, GemvQ8P<160, ActF32>{512, 0});
    }
    if (want("q6")) {
        dense<T::Q6_K>(q, "Q6_K", 1280, 32768, 0, GemvQ6KP<5, ActF32>{32768, 0});
        dense<T::Q6_K>(q, "Q6_K", 4096, 8192, 1024, GemvQ6KP<16, ActF32>{8192, 1024});
        dense<T::Q6_K>(q, "Q6_K", 8192, 5120, 0, GemvQ6KP<32, ActF32>{5120, 0});
        dense<T::Q6_K>(q, "Q6_K", 5120, 1280, 0, GemvQ6KP<20, ActF32>{1280, 0});
        dense<T::Q6_K>(q, "Q6_K", 5120, 512, 0, GemvQ6KP<20, ActF32>{512, 0});
        dense<T::Q6_K>(q, "Q6_K", 6144, 25600, 0, GemvQ6KP<24, ActF32>{25600, 0});
        dense<T::Q6_K>(q, "Q6_K", 5120, 129280, 0, GemvQ6KP<20, ActF32>{129280, 0});
    }
    if (want("q5")) {
        dense<T::Q5_K>(q, "Q5_K", 5120, 2304, 0, GemvQ5KP<20, ActF32>{2304, 0});
        dense<T::Q5_K>(q, "Q5_K", 2304, 5120, 0, GemvQ5KP<9, ActF32>{5120, 0});
    }
    if (want("f32")) dense<T::F32>(q, "F32", 5120, 384, 0, GemvF32P<160, ActF32>{384});
    std::printf("%s: %d failed shape(s)\n", g_fail ? "FAIL" : "PASS", g_fail);
    return g_fail;
}
