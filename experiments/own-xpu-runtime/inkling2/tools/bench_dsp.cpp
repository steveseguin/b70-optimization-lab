// bench_dsp: time the drafter's span attention (dspark.hpp dsp_attn_span variants) on random data with nctx context
// keys, and compare every variant's partials with variant 0.   bench_dsp <card> [nctx] [nch_max]
#include "../src/dspark.hpp"
#include <random>

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 2) { std::fprintf(stderr, "usage: bench_dsp <card> [nctx] [nch_max]\n"); return 2; }
    try {
        Device d(std::atoi(argv[1]));
        const int nctx = std::getenv("BENCH_MM") ? 1000 : argc > 2 ? std::atoi(argv[2]) : 100000, NCH = argc > 3 ? std::atoi(argv[3]) : 64;
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
        if (std::getenv("BENCH_MM")) { // the 8-slot products: gemv_v-shaped reference in fp64 on the host vs dsp_mm_x
            const int shapes[][2] = {{9216, 2304}, {2304, 9216}, {3072, 2304}, {1024, 2304}, {2304, 3072}};
            for (auto &sh : shapes) {
                const int N = sh[0], Kd = sh[1], KB = Kd / 32;
                std::vector<uint8_t> raw((size_t)N * KB * 34);
                std::uniform_int_distribution<int> qd(-127, 127);
                std::vector<float> wf((size_t)N * Kd);
                for (int n = 0; n < N; ++n)
                    for (int b = 0; b < KB; ++b) {
                        uint8_t *blk = raw.data() + ((size_t)n * KB + b) * 34;
                        const sycl::half dh = (sycl::half)(0.001f + 0.0001f * (float)((n + b) % 7));
                        std::memcpy(blk, &dh, 2);
                        for (int i = 0; i < 32; ++i) { const int8_t qv = (int8_t)qd(rng); blk[2 + i] = (uint8_t)qv; wf[(size_t)n * Kd + b * 32 + i] = (float)dh * qv; }
                    }
                const std::vector<uint8_t> rp = dsp_x8_repack(raw.data(), N, Kd);
                const int nc = std::max(2, (int)(256e6 / rp.size()));
                std::vector<uint8_t *> Wd;
                for (int c = 0; c < nc; ++c) { Wd.push_back(d.alloc<uint8_t>(rp.size())); d.put(Wd.back(), rp.data(), rp.size()); }
                const size_t ldx = xlane_floats(Kd);
                std::vector<float> xp((size_t)8 * Kd), xl((size_t)8 * ldx, 0.0f);
                std::vector<sycl::half> xh((size_t)8 * Kd);
                for (int t = 0; t < 8; ++t) for (int i = 0; i < Kd; ++i) {
                    const float vv = nd(rng); xp[(size_t)t * Kd + i] = vv; xl[(size_t)t * ldx + xlane_at(i)] = vv; xh[(size_t)t * Kd + i] = (sycl::half)vv; }
                float *xd = d.alloc<float>(xl.size()), *yd = d.alloc<float>((size_t)8 * N);
                sycl::half *xhd = d.alloc<sycl::half>(xh.size());
                d.put(xd, xl.data(), xl.size()); d.put(xhd, xh.data(), xh.size());
                std::vector<double> yr((size_t)8 * N);
                double big = 0;
                for (int t = 0; t < 8; ++t) for (int n = 0; n < N; ++n) {
                    double a2 = 0; for (int i = 0; i < Kd; ++i) a2 += (double)wf[(size_t)n * Kd + i] * xp[(size_t)t * Kd + i];
                    yr[(size_t)t * N + n] = a2; big = std::max(big, std::fabs(a2)); }
                auto mm = [&](const char *name, auto f) {
                    for (int i = 0; i < 3; ++i) f(i);
                    d.q.wait();
                    double t0 = now_s();
                    for (int i = 0; i < iters * 5; ++i) f(i + 1);
                    d.q.wait();
                    const double us = (now_s() - t0) / (iters * 5) * 1e6;
                    f(0); d.q.wait();
                    std::vector<float> yo((size_t)8 * N);
                    d.get(yo.data(), yd, yo.size());
                    double err = 0; for (size_t i = 0; i < yo.size(); ++i) err = std::max(err, std::fabs(yo[i] - yr[i]));
                    std::printf("  %5d x %5d %-22s %8.2f us %6.1f GB/s  max diff %.3g of %.3g\n", N, Kd, name, us, rp.size() / us * 1e-3, err, big);
                };
                if (Kd <= 4096 && std::getenv("BENCH_MM_LANE")) {
                    mm("KS1 x fp32 lane", [&](int i) { dsp_mm_x<1, false>(d.q, Wd[i % nc], N, Kd, xd, (int)ldx, yd); });
                    mm("KS2 x fp32 lane", [&](int i) { dsp_mm_x<2, false>(d.q, Wd[i % nc], N, Kd, xd, (int)ldx, yd); });
                    mm("KS4 x fp32 lane", [&](int i) { dsp_mm_x<4, false>(d.q, Wd[i % nc], N, Kd, xd, (int)ldx, yd); });
                    mm("KS8 x fp32 lane", [&](int i) { dsp_mm_x<8, false>(d.q, Wd[i % nc], N, Kd, xd, (int)ldx, yd); });
                }
                mm("KS1 x fp16", [&](int i) { dsp_mm_x<1, true>(d.q, Wd[i % nc], N, Kd, xhd, 0, yd); });
                mm("KS4 x fp16", [&](int i) { dsp_mm_x<4, true>(d.q, Wd[i % nc], N, Kd, xhd, 0, yd); });
                mm("KS8 x fp16", [&](int i) { dsp_mm_x<8, true>(d.q, Wd[i % nc], N, Kd, xhd, 0, yd); });
                mm("KS4 x fp16 packed", [&](int i) { dsp_mm_x<4, true, true>(d.q, Wd[i % nc], N, Kd, xhd, 0, yd); });
                mm("KS8 x fp16 packed", [&](int i) { dsp_mm_x<8, true, true>(d.q, Wd[i % nc], N, Kd, xhd, 0, yd); });
                mm("KS2 x fp16 packed", [&](int i) { dsp_mm_x<2, true, true>(d.q, Wd[i % nc], N, Kd, xhd, 0, yd); });
                for (auto *p : Wd) d.release(p);
                d.release(xd); d.release(yd); d.release(xhd);
            }
            return 0;
        }
    } catch (const std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
