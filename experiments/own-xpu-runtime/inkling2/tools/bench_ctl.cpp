// bench_ctl: the loop controls' gain|forget output kernel (ctl_out_r64) at prompt shapes, and its parts left out on
// purpose (ABL; wrong values, timing only). bench_ctl <card> [tokens]
#include "../src/device.hpp"
#include "../src/tok_tiles.hpp"
#include <cstdio>
#include <random>
#include <vector>

using namespace ink;

int main(int argc, char **argv) {
    Device d(argc > 1 ? std::atoi(argv[1]) : 1);
    const int M = argc > 2 ? std::atoi(argv[2]) : 1024, E = 2304, K = 64;
    std::mt19937 rng(7);
    std::uniform_real_distribution<float> u(-1.0f, 1.0f);
    auto up = [&](size_t n, float sc) {
        std::vector<float> h(n);
        for (auto &v : h) v = u(rng) * sc;
        float *p = d.alloc<float>(n);
        d.q.memcpy(p, h.data(), n * 4).wait();
        return p;
    };
    float *z = up((size_t)M * K, 1.0f), *wg = up((size_t)E * K, 0.2f), *wf = up((size_t)E * K, 0.2f);
    float *cur = up((size_t)M * E, 1.0f), *msg = up((size_t)M * E, 1.0f), *y = d.alloc<float>((size_t)M * E);
    const CtlOp op{cur, msg, y, E};
    std::vector<float> ref((size_t)M * E), got((size_t)M * E);
    auto time = [&](const char *name, auto launch) {
        launch(); d.q.wait();
        const int reps = 200;
        const double t0 = now_s();
        for (int r = 0; r < reps; ++r) launch();
        d.q.wait();
        const double us = (now_s() - t0) / reps * 1e6;
        d.q.memcpy(got.data(), y, got.size() * 4).wait();
        std::printf("%-34s %8.2f us  %s\n", name, us, std::memcmp(got.data(), ref.data(), got.size() * 4) ? "values differ" : "same values");
    };
    ctl_out_r64(d.q, wg, wf, E, z, M, op).wait();
    d.q.memcpy(ref.data(), y, ref.size() * 4).wait();
    for (int rep = 0; rep < 2; ++rep) {
        time("ctl_out_r64", [&] { ctl_out_r64(d.q, wg, wf, E, z, M, op); });
        time("no tanh", [&] { ctl_out_r64<1>(d.q, wg, wf, E, z, M, op); });
        time("no products", [&] { ctl_out_r64<2>(d.q, wg, wf, E, z, M, op); });
        time("no op reads", [&] { ctl_out_r64<4>(d.q, wg, wf, E, z, M, op); });
        time("none of the three", [&] { ctl_out_r64<7>(d.q, wg, wf, E, z, M, op); });
    }
    return 0;
}
