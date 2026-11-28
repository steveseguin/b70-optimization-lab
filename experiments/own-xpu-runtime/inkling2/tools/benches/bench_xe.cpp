// bench_xe: the ESIMD Q8_0 kernels (xmx_esimd.hpp) alone on random Q8_0 weights of the five attention-input shapes
// (q 3072, k 1024, v 1024, gate 3072, rel 384 rows x 2304; 10 copies so the card's cache does not hold them): one launch
// of the five, one token with the input split inside (XS) against PE parts made by splite, 2-8 tokens on PE parts;
// bits of XS against the parts path.  bench_xe <card>
#include "../../src/xmx_esimd.hpp"
#include <random>
#include <array>
#include <cmath>
using namespace ink;
int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_xe <card>\n"); return 2; }
    Device d(std::atoi(argv[1]));
    const int cols = 2304, rws[5] = {3072, 1024, 1024, 3072, 384}, NL = 10;
    const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 200;
    std::mt19937 rng(3);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    int off[6] = {0};
    for (int k = 0; k < 5; ++k) off[k + 1] = off[k] + rws[k];
    std::vector<std::array<uint8_t *, 5>> W(NL);
    size_t bytes = 0;
    for (int k = 0; k < 5; ++k) bytes += (size_t)rws[k] * cols * 34 / 32;
    for (int l = 0; l < NL; ++l)
        for (int k = 0; k < 5; ++k) {
            const size_t rb = (size_t)cols * 34 / 32, n = rb * rws[k];
            std::vector<uint8_t> h(n);
            for (int r = 0; r < rws[k]; ++r) {
                for (int c = 0; c < cols; ++c) h[r * rb + c] = (uint8_t)(int8_t)((int)(rng() % 255) - 127);
                for (int b = 0; b < cols / 32; ++b) { const uint16_t s = 0x1800 + (uint16_t)(rng() % 0x400); std::memcpy(&h[r * rb + cols + 2 * b], &s, 2); }
            }
            uint8_t *src = d.alloc<uint8_t>(n), *dst = d.alloc<uint8_t>(n);
            d.put(src, h.data(), n);
            xd::repack_q8e(d.q, src, rb, rws[k], cols, dst);
            W[l][k] = dst;
        }
    std::vector<float> hx((size_t)8 * cols);
    for (auto &v : hx) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
    float *x = d.alloc<float>(hx.size()), *Y1 = d.alloc<float>((size_t)8 * off[5]), *Y2 = d.alloc<float>((size_t)8 * off[5]);
    d.put(x, hx.data(), hx.size());
    uint16_t *Pe = d.alloc<uint16_t>((size_t)3 * 8 * cols);
    auto timeit = [&](auto &&launch) {
        for (int i = 0; i < 3; ++i) launch(i);
        d.q.wait();
        const double t0 = now_s();
        for (int i = 0; i < iters; ++i) launch(i + 1);
        d.q.wait();
        return (now_s() - t0) / iters * 1e6;
    };
    auto jobs = [&](int l, const uint16_t *P, float *Y) {
        xd::EJobs jb;
        for (int k = 0; k < 5; ++k) xd::ejob_add(jb, W[l % NL][k], rws[k], P, Y + off[k], off[5]);
        return jb;
    };
    std::printf("five attention inputs, %.1f MB per launch, %d copies\n", bytes / 1e6, NL);
    if (std::getenv("BENCH_FOLLOW")) { // (INK_PROF=1) a plain SYCL read of 16 MB timed right after: the ESIMD launch, a
        // plain read of 21 MB, or itself; does the ESIMD kernel slow the kernels after it?
        const size_t FN = (size_t)4 << 20, LN = bytes / 4 / 4096 * 4096; // uint32 values
        std::vector<uint32_t *> fb(4), lb(4);
        for (auto &b : fb) { b = d.alloc<uint32_t>(FN); d.q.memset(b, 1, FN * 4).wait(); }
        for (auto &b : lb) { b = d.alloc<uint32_t>(LN); d.q.memset(b, 1, LN * 4).wait(); }
        float *fo = d.alloc<float>(1 << 16);
        auto rd = [&](uint32_t *buf, size_t n) {
            return d.q.parallel_for(sycl::nd_range<1>(sycl::range<1>(n / 16), sycl::range<1>(256)), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                auto sg = it.get_sub_group();
                const size_t base = (it.get_group(0) * 256 + sg.get_group_id()[0] * 16) * 16;
                sycl::vec<uint32_t, 16> v;
                uint32_t acc = 0;
                for (int k = 0; k < 16; ++k) acc += buf[base + k * 16 + sg.get_local_id()[0]];
                acc = sycl::reduce_over_group(sg, acc, sycl::plus<uint32_t>());
                if (it.get_local_id(0) == 0) fo[it.get_group(0) % (1 << 16)] = (float)acc;
            });
        };
        auto ns = [](sycl::event &e) { return (e.get_profiling_info<sycl::info::event_profiling::command_end>() - e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3; };
        for (int rep = 0; rep < 2; ++rep)
            for (int lead = 0; lead < 4; ++lead) {
                double tf = 0, tl = 0;
                const int N = 300;
                for (int i = 0; i < N + 5; ++i) {
                    sycl::event el;
                    if (lead == 0) el = xd::dgroupej<1, 128, true, true>(d.q, jobs(i, (const uint16_t *)x, Y2), cols, 1);
                    else if (lead == 1) el = rd(lb[i % 4], LN);
                    else if (lead == 2) el = rd(fb[(i + 2) % 4], FN);
                    else el = xd::dgroupej<1>(d.q, jobs(i, Pe, Y1), cols, 1);
                    sycl::event ef = rd(fb[i % 4], FN);
                    ef.wait();
                    if (i >= 5) { tf += ns(ef); tl += ns(el); }
                }
                const char *nm[4] = {"ESIMD five inputs (split inside)", "plain read of 21 MB", "plain read of 16 MB", "ESIMD five inputs (parts)"};
                std::printf("  after %-34s: lead %.2f us, follower (16 MB read) %.2f us\n", nm[lead], tl / N, tf / N);
            }
        return 0;
    }
    for (int rep = 0; rep < 3; ++rep) {
        const double us_p = timeit([&](int i) { xd::dgroupej<1>(d.q, jobs(i, Pe, Y1), cols, 1); });
        const double us_sp = timeit([&](int i) { xd::splite<1>(d.q, x, cols, 1, cols, Pe); xd::dgroupej<1>(d.q, jobs(i, Pe, Y1), cols, 1); });
        const double us_x = timeit([&](int i) { xd::dgroupej<1, 128, true, true>(d.q, jobs(i, (const uint16_t *)x, Y2), cols, 1); });
        xd::splite<1>(d.q, x, cols, 1, cols, Pe);
        xd::dgroupej<1>(d.q, jobs(0, Pe, Y1), cols, 1);
        xd::dgroupej<1, 128, true, true>(d.q, jobs(0, (const uint16_t *)x, Y2), cols, 1);
        d.q.wait();
        std::vector<float> a(off[5]), b(off[5]);
        d.get(a.data(), Y1, a.size());
        d.get(b.data(), Y2, b.size());
        std::printf("  1 token: parts %.2f us, split + parts %.2f us, split inside %.2f us  %s\n", us_p, us_sp, us_x,
                    std::memcmp(a.data(), b.data(), a.size() * 4) ? "DIFF" : "same bits");
    }
    auto multi = [&]<int MR>(int r) {
        xd::splite<MR>(d.q, x, cols, r, cols, Pe);
        const double us = timeit([&](int i) { xd::dgroupej<MR>(d.q, jobs(i, Pe, Y1), cols, r); });
        const double usp = timeit([&](int i) { xd::splite<MR>(d.q, x, cols, r, cols, Pe); xd::dgroupej<MR>(d.q, jobs(i, Pe, Y1), cols, r); });
        std::printf("  %d tokens: parts %.2f us, split + parts %.2f us (one input)\n", r, us, usp);
    };
    multi.template operator()<2>(2);
    multi.template operator()<4>(3);
    multi.template operator()<4>(4);
    multi.template operator()<8>(5);
    multi.template operator()<8>(8);
    { // the attention output's shape: 2304 rows x 3072 inputs (12 groups per row block), one job
        const int oc = 3072, orow = 2304;
        const size_t rb = (size_t)oc * 34 / 32, n = rb * orow;
        std::vector<uint8_t *> Wo(NL);
        std::vector<uint8_t> h(n);
        for (int l = 0; l < NL; ++l) {
            for (int r = 0; r < orow; ++r) {
                for (int c = 0; c < oc; ++c) h[r * rb + c] = (uint8_t)(int8_t)((int)(rng() % 255) - 127);
                for (int b = 0; b < oc / 32; ++b) { const uint16_t sc = 0x1800 + (uint16_t)(rng() % 0x400); std::memcpy(&h[r * rb + oc + 2 * b], &sc, 2); }
            }
            uint8_t *src = d.alloc<uint8_t>(n);
            Wo[l] = d.alloc<uint8_t>(n);
            d.put(src, h.data(), n);
            xd::repack_q8e(d.q, src, rb, orow, oc, Wo[l]);
        }
        std::vector<float> hxo((size_t)8 * oc);
        for (auto &v : hxo) v = nd(rng);
        float *xo = d.alloc<float>(hxo.size()), *Yo = d.alloc<float>((size_t)8 * orow);
        d.put(xo, hxo.data(), hxo.size());
        uint16_t *Po = d.alloc<uint16_t>((size_t)3 * 8 * oc);
        xd::splite<1>(d.q, xo, oc, 1, oc, Po);
        auto one = [&](int l, const uint16_t *P) { xd::EJobs jb; xd::ejob_add(jb, Wo[l % NL], orow, P, Yo, orow); return jb; };
        for (int rep = 0; rep < 2; ++rep) {
            const double ux = timeit([&](int i) { xd::dgroupej<1, 128, true, true>(d.q, one(i, (const uint16_t *)xo), oc, 1); });
            const double up = timeit([&](int i) { xd::dgroupej<1>(d.q, one(i, Po), oc, 1); });
            const double u2 = timeit([&](int i) { xd::dgroupej<2>(d.q, one(i, Po), oc, 1); });
            std::printf("  attention output shape, 1 token: split inside %.2f us, parts %.2f us, (MR2 code on parts %.2f us)\n", ux, up, u2);
        }
    }
    if (std::getenv("BENCH_BIAS")) { // signed error against double: prompt kernel (BF, bf16 weights) over 256 rows x 64
        // tokens, err / (2^-24 sum |w x|): mean (bias), mean |.|, and the mean of err * sign(exact) (toward zero < 0)
        const int rows = 256, M = 64;
        std::vector<uint16_t> hw((size_t)rows * cols);
        for (auto &v : hw) { float f = nd(rng) * 0.05f; uint32_t u; std::memcpy(&u, &f, 4); v = (uint16_t)(u >> 16); }
        uint16_t *src = d.alloc<uint16_t>(hw.size()), *bw = d.alloc<uint16_t>((size_t)rows * cols);
        d.put(src, hw.data(), hw.size());
        xd::repack_bfe(d.q, src, rows, cols, rows, bw);
        for (int mode = 0; mode < 2; ++mode) { // 0: inputs around 0; 1: inputs with a positive mean (sums far from 0)
            std::vector<float> hx2((size_t)M * cols);
            for (auto &v : hx2) v = nd(rng) + (mode ? 1.0f : 0.0f);
            float *x2 = d.alloc<float>(hx2.size()), *Yb = d.alloc<float>((size_t)M * rows);
            d.put(x2, hx2.data(), hx2.size());
            uint16_t *P = d.alloc<uint16_t>((size_t)3 * M * cols);
            xd::split(d.q, x2, cols, M, M, cols, P, (size_t)M * cols);
            xd::dense<4, 1, 2, 2, 4, false, 8, false, false, true>(d.q, (const uint8_t *)bw, rows, cols, P, (size_t)M * cols, M, M, Yb, rows, nullptr, 0, rows);
            d.q.wait();
            std::vector<float> yb((size_t)M * rows);
            d.get(yb.data(), Yb, yb.size());
            double sm = 0, sa = 0, sz = 0, sf = 0, sfz = 0;
            for (int t = 0; t < M; ++t)
                for (int r = 0; r < rows; ++r) {
                    double ex = 0, ab = 0; float f32 = 0.0f;
                    for (int k = 0; k < cols; ++k) {
                        uint32_t u = (uint32_t)hw[(size_t)r * cols + k] << 16; float wv; std::memcpy(&wv, &u, 4);
                        const float xv = hx2[(size_t)t * cols + k];
                        ex += (double)wv * xv; ab += std::fabs((double)wv * xv);
                        f32 = std::fma(wv, xv, f32); // a plain FP32 running sum, for scale
                    }
                    const double u = ab * std::ldexp(1.0, -24), e = (yb[(size_t)t * rows + r] - ex) / u, ef = (f32 - ex) / u;
                    sm += e; sa += std::fabs(e); sz += e * (ex < 0 ? -1 : 1); sf += std::fabs(ef); sfz += ef * (ex < 0 ? -1 : 1);
                }
            const double n = (double)M * rows;
            std::printf("  bias, inputs %s: G8 mean %+.4f mean|.| %.4f toward-zero %+.4f; CPU FP32 running fma mean|.| %.4f toward-zero %+.4f\n",
                        mode ? "mean 1" : "mean 0", sm / n, sa / n, sz / n, sf / n, sfz / n);
        }
        return 0;
    }
    { // bf16 matrices (24 and 32 rows, like the sink and conv projections): ESIMD jobs at 1, 2, 8 tokens against the prompt
      // kernel (XDense BF, 64 tokens), and the prompt kernel against double
        for (int rows : {24, 32}) {
            const int rp = (rows + 31) / 32 * 32, M = 64;
            std::vector<uint16_t> hw((size_t)rows * cols);
            for (auto &v : hw) { float f = nd(rng) * 0.05f; uint32_t u; std::memcpy(&u, &f, 4); v = (uint16_t)(u >> 16); }
            uint16_t *src = d.alloc<uint16_t>(hw.size()), *bw = d.alloc<uint16_t>((size_t)rp * cols);
            d.put(src, hw.data(), hw.size());
            xd::repack_bfe(d.q, src, rows, cols, rp, bw);
            std::vector<float> hx2((size_t)M * cols);
            for (auto &v : hx2) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
            float *x2 = d.alloc<float>(hx2.size()), *Yb = d.alloc<float>((size_t)M * rows), *Ye = d.alloc<float>((size_t)8 * rows + 64);
            d.put(x2, hx2.data(), hx2.size());
            uint16_t *P = d.alloc<uint16_t>((size_t)3 * M * cols);
            xd::split(d.q, x2, cols, M, M, cols, P, (size_t)M * cols);
            d.q.memset(Ye, 0xff, ((size_t)8 * rows + 64) * 4).wait();
            xd::dense<4, 1, 2, 2, 4, false, 8, false, false, true>(d.q, (const uint8_t *)bw, rp, cols, P, (size_t)M * cols, M, M, Yb, rows, nullptr, 0, rows);
            d.q.wait();
            std::vector<float> yb((size_t)M * rows);
            d.get(yb.data(), Yb, yb.size());
            double emax = 0, esum = 0;
            for (int t = 0; t < M; ++t)
                for (int r = 0; r < rows; ++r) {
                    double ex = 0, ab = 0;
                    for (int k = 0; k < cols; ++k) {
                        uint32_t u = (uint32_t)hw[(size_t)r * cols + k] << 16; float wv; std::memcpy(&wv, &u, 4);
                        ex += (double)wv * hx2[(size_t)t * cols + k]; ab += std::fabs((double)wv * hx2[(size_t)t * cols + k]);
                    }
                    const double e = std::fabs(yb[(size_t)t * rows + r] - ex) / (ab * std::ldexp(1.0, -24));
                    emax = std::max(emax, e); esum += e;
                }
            std::printf("  bf16 %d rows: prompt kernel error vs double mean %.4f max %.4f (2^-24 sum |w x|)\n", rows, esum / (M * rows), emax);
            auto chk = [&]<int MR>(int r) {
                xd::EJobs jb;
                if (r == 1) xd::ejob_add(jb, (const uint8_t *)bw, rows, (const uint16_t *)x2, Ye, rows, true);
                else { xd::splite<MR>(d.q, x2, cols, r, cols, Pe); xd::ejob_add(jb, (const uint8_t *)bw, rows, Pe, Ye, rows, true); }
                if (r == 1) xd::dgroupej<1, 128, true, true>(d.q, jb, cols, 1);
                else xd::dgroupej<MR>(d.q, jb, cols, r);
                d.q.wait();
                std::vector<float> ye((size_t)8 * rows + 64);
                d.get(ye.data(), Ye, ye.size());
                bool tail = true;
                for (size_t i = (size_t)r * rows; i < ye.size(); ++i) { uint32_t u; std::memcpy(&u, &ye[i], 4); if (u != 0xffffffffu) tail = false; }
                std::printf("    %d tokens (ESIMD): %s, nothing written past them: %s\n", r,
                            std::memcmp(ye.data(), yb.data(), (size_t)r * rows * 4) ? "DIFF vs the prompt kernel" : "same bits as the prompt kernel", tail ? "yes" : "NO");
            };
            chk.template operator()<1>(1);
            chk.template operator()<2>(2);
            chk.template operator()<8>(5);
            chk.template operator()<8>(8);
        }
    }
    return 0;
}
