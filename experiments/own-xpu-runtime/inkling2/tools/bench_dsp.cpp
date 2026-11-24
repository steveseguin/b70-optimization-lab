// bench_dsp: time the drafter's span attention (dspark.hpp dsp_attn_span variants) on random data with nctx context
// keys, and compare every variant's partials with variant 0.   bench_dsp <card> [nctx] [nch_max]
#include "../src/dspark.hpp"
#include <random>

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 2) { std::fprintf(stderr, "usage: bench_dsp <card> [nctx] [nch_max]\n"); return 2; }
    try {
        Device d(std::atoi(argv[1]));
        const int nctx = argc > 2 ? std::atoi(argv[2]) : 100000, NCH = argc > 3 ? std::atoi(argv[3]) : 64;
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 20;
        const int ncopy = std::getenv("BENCH_NCOPY") ? std::atoi(std::getenv("BENCH_NCOPY")) : 8;
        constexpr int B = 8, HQ = 24, HKV = 8, HD = 128, CH = 128, NR = 24, kd = HKV * HD;
        const int nk = nctx + B;
        const int span = CH * std::max(1, (nk + CH * NCH - 1) / (CH * NCH)), nch = (nk + span - 1) / span;
        std::mt19937 rng(5);
        std::normal_distribution<float> nd(0.0f, 1.0f);
        std::vector<float> hq((size_t)B * HQ * HD), hk((size_t)B * kd), hv((size_t)B * kd);
        for (auto &x : hq) x = nd(rng);
        for (auto &x : hk) x = nd(rng);
        for (auto &x : hv) x = nd(rng);
        // the cache: nctx context rows, then the block's 8 rows (dsp_attn_span_x reads them from here), then 128 zeroed
        std::vector<sycl::half> hc((size_t)(nctx + B + CH) * kd, (sycl::half)0.0f);
        for (size_t i = 0; i < (size_t)nctx * kd; ++i) hc[i] = (sycl::half)nd(rng);
        float *q = d.alloc<float>(hq.size()), *k = d.alloc<float>(hk.size()), *v = d.alloc<float>(hv.size());
        d.put(q, hq.data(), hq.size()); d.put(k, hk.data(), hk.size()); d.put(v, hv.data(), hv.size());
        std::vector<sycl::half *> Kc, Vc;
        for (int c = 0; c < ncopy; ++c) {
            Kc.push_back(d.alloc<sycl::half>(hc.size())); d.put(Kc.back(), hc.data(), hc.size());
            Vc.push_back(d.alloc<sycl::half>(hc.size())); d.put(Vc.back(), hc.data(), hc.size());
            dsp_block_to_cache(d.q, k, v, Kc.back(), Vc.back(), nctx, kd).wait();
        }
        const size_t no = (size_t)HKV * NR * (nch + 1) * HD, nm = (size_t)HKV * NR * (nch + 1);
        float *O[2], *M[2], *L[2];
        for (int i = 0; i < 2; ++i) { O[i] = d.alloc<float>(no); M[i] = d.alloc<float>(nm); L[i] = d.alloc<float>(nm); }
        const double mb = 2.0 * nctx * kd * 2 / 1e6;
        std::printf("nctx %d spans %d (span %d keys): K+V %.1f MB\n", nctx, nch, span, mb);
        std::vector<float> ref, refout;
        // the combined attention output [kvh][row][dim] from a slot's partials (as attn_combine)
        auto combine = [&](int slot) {
            std::vector<float> o(no), m(nm), l(nm), out((size_t)HKV * NR * HD);
            d.get(o.data(), O[slot], no); d.get(m.data(), M[slot], nm); d.get(l.data(), L[slot], nm);
            for (int gi = 0; gi < HKV * NR; ++gi) {
                double mx = -1e300;
                for (int c = 0; c < nch; ++c) mx = std::max(mx, (double)m[(size_t)gi * nch + c]);
                for (int dd = 0; dd < HD; ++dd) {
                    double su = 0, ov = 0;
                    for (int c = 0; c < nch; ++c) {
                        const double f = std::exp((double)m[(size_t)gi * nch + c] - mx);
                        su += l[(size_t)gi * nch + c] * f;
                        ov += o[((size_t)gi * nch + c) * HD + dd] * f;
                    }
                    out[(size_t)gi * HD + dd] = (float)(ov / su);
                }
            }
            return out;
        };
        auto run = [&](const char *name, auto f, int slot) {
            for (int i = 0; i < 3; ++i) f(i, slot);
            d.q.wait();
            double t0 = now_s();
            for (int i = 0; i < iters; ++i) f(i + 1, slot);
            d.q.wait();
            double us = (now_s() - t0) / iters * 1e6;
            f(0, slot);
            d.q.wait();
            std::vector<float> h(no);
            d.get(h.data(), O[slot], no);
            const char *cmp = "";
            const std::vector<float> out = combine(slot);
            double err = 0, big = 0;
            if (ref.empty()) { ref = h; refout = out; }
            else {
                cmp = std::memcmp(ref.data(), h.data(), no * 4) ? "partials differ" : "same";
                for (size_t i = 0; i < out.size(); ++i) { err = std::max(err, (double)std::fabs(out[i] - refout[i])); big = std::max(big, (double)std::fabs(refout[i])); }
            }
            std::printf("  %-28s %9.2f us %7.1f GB/s  %s  output max diff %.3g (largest value %.3g)\n", name, us, mb / us * 1e3, cmp, err, big);
        };
        run("span v0", [&](int i, int s) { dsp_attn_span<0>(d.q, q, k, v, Kc[i % ncopy], Vc[i % ncopy], 0, nctx, 0x7fffffff, kd, span, nch, O[s], M[s], L[s]); }, 0);
        run("span v1 (V staged)", [&](int i, int s) { dsp_attn_span<1>(d.q, q, k, v, Kc[i % ncopy], Vc[i % ncopy], 0, nctx, 0x7fffffff, kd, span, nch, O[s], M[s], L[s]); }, 1);
        run("span v2 (fma)", [&](int i, int s) { dsp_attn_span<2>(d.q, q, k, v, Kc[i % ncopy], Vc[i % ncopy], 0, nctx, 0x7fffffff, kd, span, nch, O[s], M[s], L[s]); }, 1);
        run("span v3 (fma, V staged)", [&](int i, int s) { dsp_attn_span<3>(d.q, q, k, v, Kc[i % ncopy], Vc[i % ncopy], 0, nctx, 0x7fffffff, kd, span, nch, O[s], M[s], L[s]); }, 1);
        run("span x (matrix engines)", [&](int i, int s) { dsp_attn_span_x(d.q, q, Kc[i % ncopy], Vc[i % ncopy], nk, kd, span, nch, O[s], M[s], L[s]); }, 1);
        { // reference: a plain read of the same K and V
            float *sink = d.alloc<float>(1 << 20);
            const size_t n8 = (size_t)nctx * kd / 8;
            run("read K+V (16-byte loads)", [&](int i, int) {
                const sycl::vec<sycl::half, 8> *a = (const sycl::vec<sycl::half, 8> *)Kc[i % ncopy], *b = (const sycl::vec<sycl::half, 8> *)Vc[i % ncopy];
                float *sk = sink;
                d.q.parallel_for(sycl::nd_range<1>((n8 + 255) / 256 * 256, 256), [=](sycl::nd_item<1> it) {
                    const size_t g = it.get_global_id(0);
                    if (g >= n8) return;
                    const sycl::vec<sycl::half, 8> x = a[g], y = b[g];
                    float t = 0.0f;
                    for (int w = 0; w < 8; ++w) t += (float)x[w] + (float)y[w];
                    if (t == 12345.678f) sk[g & 1023] = t;
                });
            }, 1);
        }
    } catch (const std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
