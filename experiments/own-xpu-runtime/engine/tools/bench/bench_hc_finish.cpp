// HcMixFinishSG form 1 (run_bc: constant-lane broadcasts) against form 0 (run0), BITWISE on pre / post / comb
// for 4096 random input sets, and the single-sub-group latency of each form (the finish runs alone on the
// critical path). One card. Exit status 1 on any mismatch.
//
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src \
//     tools/bench/bench_hc_finish.cpp -o $S/bench_hc_finish
//   LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib $S/bench_hc_finish [CARD]
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
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
    constexpr unsigned SETS = 4096, SEG = 8, H = 5120;
    std::mt19937 rng(7);
    std::uniform_real_distribution<double> ud(-3.0, 3.0), us(0.5, 4.0);
    std::uniform_real_distribution<float> uf(-1.5f, 1.5f), uc(0.2f, 2.0f);
    std::vector<double> hd((size_t)SETS * 25 * SEG);
    std::vector<float> hsc((size_t)SETS * 3), hb((size_t)SETS * 24);
    for (unsigned s = 0; s < SETS; ++s) {
        for (unsigned i = 0; i < 24 * SEG; ++i) hd[(size_t)s * 25 * SEG + i] = ud(rng) * 100.0;
        for (unsigned i = 0; i < SEG; ++i) hd[(size_t)s * 25 * SEG + 24 * SEG + i] = us(rng) * 4 * H / SEG; // sum of squares
        for (unsigned i = 0; i < 3; ++i) hsc[(size_t)s * 3 + i] = uc(rng) * (s % 3 ? 1.0f : 8.0f);
        for (unsigned i = 0; i < 24; ++i) hb[(size_t)s * 24 + i] = uf(rng) * (s % 5 ? 1.0f : 6.0f);
    }
    double *dd = sycl::malloc_device<double>(hd.size(), q);
    float *dsc = sycl::malloc_device<float>(hsc.size(), q), *db = sycl::malloc_device<float>(hb.size(), q);
    float *o0 = sycl::malloc_device<float>((size_t)SETS * 24, q), *o1 = sycl::malloc_device<float>((size_t)SETS * 24, q);
    q.memcpy(dd, hd.data(), hd.size() * 8);
    q.memcpy(dsc, hsc.data(), hsc.size() * 4);
    q.memcpy(db, hb.data(), hb.size() * 4).wait();
    auto run = [&](int form, float *o, unsigned sets) {
        HcMixFinishSG k{(int)H, (int)SEG};
        k.form = form;
        return q.parallel_for(sycl::nd_range<1>((size_t)sets * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            const size_t s = it.get_group_linear_id();
            k.run(it.get_sub_group(), dd + s * 25 * SEG, dsc + s * 3, db + s * 24, o + s * 24, o + s * 24 + 4, o + s * 24 + 8);
        });
    };
    q.memset(o0, 0xff, (size_t)SETS * 24 * 4);
    q.memset(o1, 0xff, (size_t)SETS * 24 * 4).wait();
    run(0, o0, SETS).wait();
    run(1, o1, SETS).wait();
    std::vector<float> r0((size_t)SETS * 24), r1((size_t)SETS * 24);
    q.memcpy(r0.data(), o0, r0.size() * 4);
    q.memcpy(r1.data(), o1, r1.size() * 4).wait();
    size_t differ = 0, nonfinite = 0;
    for (size_t i = 0; i < r0.size(); ++i) {
        differ += std::memcmp(&r0[i], &r1[i], 4) != 0;
        nonfinite += !std::isfinite(r0[i]);
    }
    std::printf("%s form 1 vs form 0: %zu of %zu values differ (%zu non-finite in form 0)\n", differ ? "FAIL" : "PASS",
                differ, r0.size(), nonfinite);
    for (int form = 0; form < 2; ++form) {
        for (int i = 0; i < 200; ++i) run(form, form ? o1 : o0, 1);
        q.wait();
        double best = 1e30, sum = 0;
        for (int i = 0; i < 50; ++i) {
            auto e = run(form, form ? o1 : o0, 1);
            e.wait();
            best = std::min(best, ev_us(e));
            sum += ev_us(e);
        }
        std::printf("form %d: one sub-group %.2f us (min of 50), mean %.2f us\n", form, best, sum / 50);
    }
    sycl::free(dd, q);
    sycl::free(dsc, q);
    sycl::free(db, q);
    sycl::free(o0, q);
    sycl::free(o1, q);
    return differ ? 1 : 0;
}
