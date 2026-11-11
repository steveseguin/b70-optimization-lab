// What bounds the 5,120-wide RMS norm's double chain (RmsNormPS<5120, 4>: ~10 us per launch in the engine's
// answer steps, 81 per step on the critical path)? One card, one launch at a time, GPU time of each form, and
// the outputs compared BITWISE with RmsNormPS<5120, 4> (exact forms only; F is the float floor, not exact):
//   A  RmsNormPS<5120, 4>: one work-group of four sub-groups of 32, each forms the whole sum (the engine)
//   B  the same part on one sub-group writing all 20 chunks (S = 1)
//   C  A with the 20 chunks of x loaded before the chain (all loads issued first)
//   D  sub-group of 16, two chains per lane (logical lanes h and h + 16: the same 160 terms each, in order), the
//      same tree (the w = 16 step adds the lane's two chains), all 20 chunks written
//   H  two sub-groups of 16 in one work-group: logical lanes 0-15 and 16-31 (one chain per lane), the partner's
//      sums through local memory (the w = 16 step), then the tree of 8 / 4 / 2 / 1 on each
//   F  B with a float accumulator (inexact: the floor without doubles)
//   E  an empty launch (one sub-group storing one value)
// x: normal values scaled by 2^k, k uniform in [-20, 20] (the sum rounds at most steps).
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_norm_dp.cpp -o $S/bench_norm_dp
//   ONEAPI_DEVICE_SELECTOR=level_zero:1 $S/bench_norm_dp
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

static constexpr unsigned N = 5120, C = N / 256;

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
inline void store8(sycl::sub_group sg, float *p, const sycl::vec<float, 8> &o) {
    sg.store<8>(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(p), o);
}
inline void store16(sycl::sub_group sg, float *p, const sycl::vec<float, 16> &o) {
    sg.store<16>(sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(p), o);
}

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    float *x = sycl::malloc_device<float>(N, q), *w = sycl::malloc_device<float>(N, q);
    float *y[8];
    for (auto &p : y) p = sycl::malloc_device<float>(N, q);
    std::mt19937 rng(3);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::uniform_int_distribution<int> ue(-20, 20);
    std::vector<float> hx(N), hw(N);
    const char *names[8] = {"A RmsNormPS<5120,4> (engine)", "B one sub-group, S = 1", "C loads first, S = 4",
                            "D sub-group 16, 2 chains / lane", "H two sub-groups of 16 + local memory",
                            "F float accumulator (inexact)", "E empty launch", ""};
    auto run = [&](int v) -> sycl::event {
        float *yo = y[v];
        switch (v) {
        case 0:
            return q.parallel_for(sycl::nd_range<1>(128, 128), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                RmsNormPS<N, 4>{}(it, x, w, yo);
            });
        case 1:
            return q.parallel_for(sycl::nd_range<1>(32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                RmsNormPS<N, 1>::part(it.get_sub_group(), it.get_sub_group().get_local_linear_id(), 0, x, w, yo);
            });
        case 2:
            return q.parallel_for(sycl::nd_range<1>(128, 128), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                sycl::sub_group sg = it.get_sub_group();
                const unsigned lane = sg.get_local_linear_id(), sgi = sg.get_group_linear_id();
                sycl::vec<float, 8> xv[C];
#pragma unroll
                for (unsigned c = 0; c < C; ++c) xv[c] = sg_bloadN<8>(sg, x + c * 256);
                double acc = 0;
#pragma unroll
                for (unsigned c = 0; c < C; ++c)
#pragma unroll
                    for (unsigned m = 0; m < 8; ++m) acc += double(xv[c][m]) * xv[c][m];
                for (int w_ = 16; w_; w_ >>= 1) acc += sycl::select_from_group(sg, acc, (int)lane ^ w_);
                const float rs = float(1.0 / sycl::sqrt(acc / N + 1e-20));
#pragma unroll
                for (unsigned c = 0; c < C; ++c) {
                    if (c % 4 != sgi) continue;
                    const auto wv = sg_bloadN<8>(sg, w + c * 256);
                    sycl::vec<float, 8> o;
#pragma unroll
                    for (unsigned m = 0; m < 8; ++m) o[m] = wv[m] * (xv[c][m] * rs);
                    store8(sg, yo + c * 256, o);
                }
            });
        case 3:
            return q.parallel_for(sycl::nd_range<1>(16, 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                sycl::sub_group sg = it.get_sub_group();
                const unsigned h = sg.get_local_linear_id();
                double a0 = 0, a1 = 0; // logical lanes h, h + 16
#pragma unroll
                for (unsigned c = 0; c < C; ++c) {
                    const auto xv = sg_bloadN<16>(sg, x + c * 256); // xv[2m + k] = x[c 256 + 32 m + 16 k + h]
#pragma unroll
                    for (unsigned m = 0; m < 8; ++m) {
                        a0 += double(xv[2 * m]) * xv[2 * m];
                        a1 += double(xv[2 * m + 1]) * xv[2 * m + 1];
                    }
                }
                double acc = a0 + a1; // the w = 16 step (a + b == b + a)
                for (int w_ = 8; w_; w_ >>= 1) acc += sycl::select_from_group(sg, acc, (int)h ^ w_);
                const float rs = float(1.0 / sycl::sqrt(acc / N + 1e-20));
#pragma unroll
                for (unsigned c = 0; c < C; ++c) {
                    const auto xv = sg_bloadN<16>(sg, x + c * 256);
                    const auto wv = sg_bloadN<16>(sg, w + c * 256);
                    sycl::vec<float, 16> o;
#pragma unroll
                    for (unsigned j = 0; j < 16; ++j) o[j] = wv[j] * (xv[j] * rs);
                    store16(sg, yo + c * 256, o);
                }
            });
        case 4:
            return q.submit([&](sycl::handler &hd) {
                sycl::local_accessor<double, 1> ls(32, hd);
                hd.parallel_for(sycl::nd_range<1>(32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                    sycl::sub_group sg = it.get_sub_group();
                    const unsigned h = sg.get_local_linear_id(), k = sg.get_group_linear_id(); // logical lane h + 16 k
                    double a = 0;
                    // per-lane loads (16 consecutive floats per m and sub-group)
#pragma unroll
                    for (unsigned c = 0; c < C; ++c)
#pragma unroll
                        for (unsigned m = 0; m < 8; ++m) {
                            const float v = x[c * 256 + 32 * m + 16 * k + h];
                            a += double(v) * v;
                        }
                    ls[16 * k + h] = a;
                    sycl::group_barrier(it.get_group());
                    double acc = a + ls[16 * (1 - k) + h]; // the w = 16 step
                    for (int w_ = 8; w_; w_ >>= 1) acc += sycl::select_from_group(sg, acc, (int)h ^ w_);
                    const float rs = float(1.0 / sycl::sqrt(acc / N + 1e-20));
                    for (unsigned c = k; c < C; c += 2) {
                        const auto xv = sg_bloadN<16>(sg, x + c * 256);
                        const auto wv = sg_bloadN<16>(sg, w + c * 256);
                        sycl::vec<float, 16> o;
#pragma unroll
                        for (unsigned j = 0; j < 16; ++j) o[j] = wv[j] * (xv[j] * rs);
                        store16(sg, yo + c * 256, o);
                    }
                });
            });
        case 5:
            return q.parallel_for(sycl::nd_range<1>(32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                sycl::sub_group sg = it.get_sub_group();
                const unsigned lane = sg.get_local_linear_id();
                float acc = 0;
#pragma unroll
                for (unsigned c = 0; c < C; ++c) {
                    const auto xv = sg_bloadN<8>(sg, x + c * 256);
#pragma unroll
                    for (unsigned m = 0; m < 8; ++m) acc += xv[m] * xv[m];
                }
                for (int w_ = 16; w_; w_ >>= 1) acc += sycl::select_from_group(sg, acc, (int)lane ^ w_);
                const float rs = 1.0f / sycl::sqrt(acc / N + 1e-20f);
#pragma unroll
                for (unsigned c = 0; c < C; ++c) {
                    const auto xv = sg_bloadN<8>(sg, x + c * 256);
                    const auto wv = sg_bloadN<8>(sg, w + c * 256);
                    sycl::vec<float, 8> o;
#pragma unroll
                    for (unsigned m = 0; m < 8; ++m) o[m] = wv[m] * (xv[m] * rs);
                    store8(sg, yo + c * 256, o);
                }
            });
        default:
            return q.parallel_for(sycl::nd_range<1>(32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                if (it.get_local_linear_id() == 0) yo[0] = 1.0f;
            });
        }
    };
    long bad = 0;
    const int REP = 200;
    std::vector<double> tm[7];
    for (int set = 0; set < 8; ++set) {
        for (unsigned i = 0; i < N; ++i) {
            hx[i] = nd(rng) * std::ldexp(1.0f, ue(rng));
            hw[i] = nd(rng);
        }
        q.memcpy(x, hx.data(), N * 4);
        q.memcpy(w, hw.data(), N * 4).wait();
        for (int v = 0; v < 7; ++v) q.fill(y[v], -7.0f, N);
        q.wait();
        for (int r = 0; r < REP / 8; ++r)
            for (int v = 0; v < 7; ++v) {
                auto e = run(v);
                e.wait();
                if (r) tm[v].push_back(ev_us(e));
            }
        std::vector<float> ref(N), o(N);
        q.memcpy(ref.data(), y[0], N * 4).wait();
        for (int v = 1; v < 5; ++v) {
            q.memcpy(o.data(), y[v], N * 4).wait();
            if (std::memcmp(ref.data(), o.data(), N * 4)) {
                ++bad;
                std::printf("set %d: %s DIFFERS\n", set, names[v]);
            }
        }
    }
    std::printf("%-42s %10s %10s\n", "form", "median us", "min us");
    for (int v = 0; v < 7; ++v) {
        auto t = tm[v];
        std::sort(t.begin(), t.end());
        std::printf("%-42s %10.2f %10.2f %s\n", names[v], t[t.size() / 2], t[0],
                    v >= 1 && v <= 4 ? (bad ? "" : "bitwise = A") : "");
    }
    std::printf(bad ? "FAIL (%ld differ)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
