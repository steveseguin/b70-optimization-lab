// Host launch cost on N B70 cards, one host thread per card (each card its own SYCL context) vs one
// thread for all. Shows the Level Zero driver's per-launch "indirect access" bookkeeping: a kernel the
// compiler marks indirect (a pointer inside a by-value struct, a pointer loaded from memory, a program-
// scope table, or simply a data-dependent address such as p[ix[i]]) makes every launch re-register all
// allocations under one lock shared by all threads, so six threads stop scaling.
// usage: l0_launch_lock_bench NCARDS LAUNCHES ARGS [EXTRA_ALLOCS]
//   ARGS 0/1 plain lambdas, 2 struct of named pointers, 3 struct holding a pointer array, 4 six named
//   pointer fields + select, 5 pointer array with constant indices, 6 nested struct of pointers,
//   7 pointer loaded from memory, 8 program-scope table, 9 data-dependent index into an argument.
// TURIND8 (six B70, oneAPI 2026.1, libze_intel_gpu 1.15.38646), us per launch-round, thread per card:
//   2/4: 2.5   3: 10.5   5: 7.5   6: 10.8   7: 11.2   8: 10.2   9: 10.4   (one thread: ~12 for all)
//   with NEOReadDebugKeys=1 DisableIndirectAccess=1:  3: 2.4   7: 2.5   9: 2.4
// Build: icpx -fsycl -O2 l0_launch_lock_bench.cpp -o l0_launch_lock_bench
#include <sycl/sycl.hpp>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>
struct F2 { float *p, *p1, *p2, *p3, *p4, *p5, *p6, *p7; float s;
    void operator()(sycl::nd_item<1> it) const { const size_t g = it.get_global_linear_id();
        p[g] = p[g] * s + p1[0] + p2[0] + p3[0] + p4[0] + p5[0] + p6[0] + p7[0]; } };
struct P6 { float *p[6]; };
struct F3 { P6 P; float s;
    void operator()(sycl::nd_item<1> it) const { const size_t g = it.get_global_linear_id();
        P.p[0][g] = P.p[0][g] * s + P.p[1][0] + P.p[2][0] + P.p[3][0] + P.p[4][0] + P.p[5][0]; } };
struct F4 { float *p0, *p1, *p2, *p3, *p4, *p5; float s;
    float *sel(int d) const { return d == 0 ? p0 : d == 1 ? p1 : d == 2 ? p2 : d == 3 ? p3 : d == 4 ? p4 : p5; }
    void operator()(sycl::nd_item<1> it) const { const size_t g = it.get_global_linear_id();
        float a = 0; for (int d = 1; d < 6; ++d) a += sel(d)[0];
        p0[g] = p0[g] * s + a; } };
struct F5 { P6 P; float s;
    void operator()(sycl::nd_item<1> it) const { const size_t g = it.get_global_linear_id();
        float a = 0;
        #pragma unroll
        for (int d = 1; d < 6; ++d) a += P.p[d][0];
        P.p[0][g] = P.p[0][g] * s + a; } };
struct In2 { float *a, *b; };
struct F6 { In2 x; float *p; float s;
    void operator()(sycl::nd_item<1> it) const { const size_t g = it.get_global_linear_id();
        p[g] = p[g] * s + x.a[0] + x.b[0]; } };
struct F7 { float *p; float **pp; float s;   // pointer loaded from memory (indirect stateless)
    void operator()(sycl::nd_item<1> it) const { const size_t g = it.get_global_linear_id();
        p[g] = p[g] * s + pp[0][0]; } };
static const sycl::ext::oneapi::experimental::device_global<float[64]> gtab;
struct F8 { float *p; float s;   // program-scope table read (global_base)
    void operator()(sycl::nd_item<1> it) const { const size_t g = it.get_global_linear_id();
        p[g] = p[g] * s + gtab[g & 63]; } };
struct F9 { float *p; const int *ix; float s;   // data-dependent index into an arg pointer
    void operator()(sycl::nd_item<1> it) const { const size_t g = it.get_global_linear_id();
        p[g] = p[g] * s + p[ix[g & 7] & 1023]; } };
static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
int main(int argc, char **argv) {
    const int N = argc > 1 ? atoi(argv[1]) : 6;
    const int K = argc > 2 ? atoi(argv[2]) : 3000;
    const int ARGS = argc > 3 ? atoi(argv[3]) : 0; // 1: kernel with 8 pointer args (like ours)
    const int EXTRA = argc > 4 ? atoi(argv[4]) : 0; // extra small device allocations per card
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    std::vector<sycl::queue> q;
    std::vector<float *> b;
    for (int c = 0; c < N; ++c) {
        sycl::context cx(l0.at(c));
        q.emplace_back(cx, l0.at(c), sycl::property::queue::in_order{});
        b.push_back(sycl::malloc_device<float>(4096, q.back()));
        q.back().memset(b.back(), 0, 4096 * 4).wait();
        { float *pv = b.back(); q.back().memcpy(b.back() + 1024, &pv, sizeof pv).wait(); }
        for (int e = 0; e < EXTRA; ++e) (void)sycl::malloc_device<float>(1024 + e, q.back());
    }
    auto sub = [&](int c, int i) {
        float *p = b[c];
        const float s = 1.0f + i * 1e-7f;
        if (ARGS == 2) { // pointers inside a struct passed by value (like the engine's functors)
            F2 f{p, p + 64, p + 128, p + 192, p + 256, p + 320, p + 384, p + 448, s};
            q[c].parallel_for(sycl::nd_range<1>(512, 64), f);
        } else if (ARGS == 3) { // struct holding an array of pointers (like XchgPeers)
            F3 f{{{p, p + 64, p + 128, p + 192, p + 256, p + 320}}, s};
            q[c].parallel_for(sycl::nd_range<1>(512, 64), f);
        } else if (ARGS == 4) {
            F4 f{p, p + 64, p + 128, p + 192, p + 256, p + 320, s};
            q[c].parallel_for(sycl::nd_range<1>(512, 64), f);
        } else if (ARGS == 5) {
            F5 f{{{p, p + 64, p + 128, p + 192, p + 256, p + 320}}, s};
            q[c].parallel_for(sycl::nd_range<1>(512, 64), f);
        } else if (ARGS == 6) {
            F6 f{{p + 64, p + 128}, p, s};
            q[c].parallel_for(sycl::nd_range<1>(512, 64), f);
        } else if (ARGS == 7) {
            F7 f{p, (float **)(p + 1024), s};
            q[c].parallel_for(sycl::nd_range<1>(512, 64), f);
        } else if (ARGS == 8) {
            F8 f{p, s};
            q[c].parallel_for(sycl::nd_range<1>(512, 64), f);
        } else if (ARGS == 9) {
            F9 f{p, (const int *)(p + 2048), s};
            q[c].parallel_for(sycl::nd_range<1>(512, 64), f);
        } else if (ARGS) {
            float *p1 = p + 64, *p2 = p + 128, *p3 = p + 192, *p4 = p + 256, *p5 = p + 320, *p6 = p + 384, *p7 = p + 448;
            q[c].parallel_for(sycl::nd_range<1>(512, 64), [=](sycl::nd_item<1> it) {
                const size_t g = it.get_global_linear_id();
                p[g] = p[g] * s + p1[0] + p2[0] + p3[0] + p4[0] + p5[0] + p6[0] + p7[0];
            });
        } else {
            q[c].parallel_for(sycl::nd_range<1>(512, 64), [=](sycl::nd_item<1> it) {
                const size_t g = it.get_global_linear_id();
                p[g] = p[g] * s + 1.0f;
            });
        }
    };
    for (int c = 0; c < N; ++c) { for (int i = 0; i < 50; ++i) sub(c, i); q[c].wait(); }
    for (int mode = 0; mode < 2; ++mode) {
        double best_sub = 1e9, best_all = 1e9;
        for (int r = 0; r < 3; ++r) {
            double t0 = now();
            if (mode == 0) {
                for (int i = 0; i < K; ++i)
                    for (int c = 0; c < N; ++c) sub(c, i);
            } else {
                std::vector<std::thread> th;
                for (int c = 0; c < N; ++c) th.emplace_back([&, c] { for (int i = 0; i < K; ++i) sub(c, i); });
                for (auto &t : th) t.join();
            }
            double t1 = now();
            for (int c = 0; c < N; ++c) q[c].wait();
            double t2 = now();
            best_sub = std::min(best_sub, t1 - t0);
            best_all = std::min(best_all, t2 - t0);
        }
        std::printf("extra %d N %d K %d %s args %d: submit %.2f us per launch (all cards), %.2f us per launch-round; total %.2f us per round\n", EXTRA, N, K,
                    mode ? "thread per card" : "one thread", ARGS, best_sub / (K * N) * 1e6, best_sub / K * 1e6, best_all / K * 1e6);
    }
    return 0;
}
