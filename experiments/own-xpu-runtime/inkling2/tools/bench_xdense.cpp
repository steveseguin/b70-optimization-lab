// bench_xdense: Q8_0 dense matrices on the matrix engines (xmx_dense.hpp) against today's kernels (dense_t for steps
// of many tokens, gemv_v for one token), on the model's attention matrices of layers 6-17 (each timed launch uses the
// next layer): time per launch, the bits of every step size against the many-token kernel, and the sums' error against
// double on a sample, in units of 2^-24 x sum |w x|.
//   bench_xdense <model.gguf> <card> <tokens>
#include "../src/tok_tiles.hpp"
#include "../src/xmx_dense.hpp"
#include "../src/xmx_esimd.hpp"
#include "../src/multi.hpp"
#include "../src/xlane.hpp"
#include <random>
#include <array>
using namespace ink;
int main(int argc, char **argv) {
    if (argc < 4) { std::fprintf(stderr, "usage: bench_xdense <model.gguf> <card> <tokens>\n"); return 2; }
    try {
        GGUF gf(argv[1]);
        Device d(std::atoi(argv[2]));
        Weights w;
        w.upload(d, gf, false);
        auto views = planarize(d, gf, w, false);
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 50;
        const int M = std::atoi(argv[3]), Mpad = (M + 63) / 64 * 64;
        const char *names[] = {"attn_q", "attn_output", "attn_k"};
        const char *only = std::getenv("BENCH_ONLY");
        std::mt19937 rng(7);
        std::normal_distribution<float> nd(0.0f, 1.0f);
        constexpr int CMAX = 3072, RMAX = 3072;
        std::vector<float> hx((size_t)Mpad * CMAX);
        for (auto &v : hx) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
        float *x = d.alloc<float>(hx.size());
        d.put(x, hx.data(), hx.size());
        float *Xd = d.alloc<float>((size_t)Mpad * CMAX), *Y = d.alloc<float>((size_t)Mpad * RMAX), *Y1 = d.alloc<float>((size_t)8 * RMAX);
        uint16_t *P = d.alloc<uint16_t>((size_t)3 * Mpad * CMAX);
        uint8_t *tmp = d.alloc<uint8_t>((size_t)RMAX * CMAX * 34 / 32);
        xd::bf *zbf = d.alloc<xd::bf>(256);
        d.q.memset(zbf, 0, 512).wait();
        auto timeit = [&](auto &&launch) {
            for (int i = 0; i < 2; ++i) launch(i);
            d.q.wait();
            const double t0 = now_s();
            for (int i = 0; i < iters; ++i) launch(i + 1);
            d.q.wait();
            const double us = (now_s() - t0) / iters * 1e6;
            launch(0);
            d.q.wait();
            return us;
        };
        for (const char *nm : names) {
            if (only && std::strcmp(only, nm)) continue;
            std::vector<WView> v;
            for (int l = 6; l < 18; ++l) {
                WView a = views.at("blk." + std::to_string(l) + "." + nm + ".weight");
                if (a.kind == K_Q8_0P) v.push_back(a);
            }
            const int NL = (int)v.size(), cols = (int)v[0].t->ne[0], rows = (int)v[0].t->rows();
            const double macs = (double)M * rows * cols;
            std::printf("%s: %d x %d, %d Q8_0 layers, %d tokens\n", nm, cols, rows, NL, M);
            // today's kernels
            const double ug = timeit([&](int) { dense_gather(d.q, x, cols, M, cols, Xd); });
            const double ut = timeit([&](int i) { dense_t(d.q, v[i % NL], M, Xd, Y, rows, DTune{4, 32}); });
            std::vector<float> yt((size_t)M * rows);
            d.get(yt.data(), Y, yt.size());
            const double u1 = timeit([&](int i) { gemv_v(d.q, v[i % NL], x, cols, Y1, rows, 1, rows <= 1024 ? Tune{1, 4} : Tune{2, 2}); });
            std::printf("  today: gather %.1f us, dense_t %.1f us (%.2f T MAC/s); one token gemv_v %.2f us (%.0f GB/s)\n", ug, ut, macs / ut / 1e6, u1,
                        (double)v[0].rb * rows / u1 / 1e3);
            // samples for the error (layer 0 of the list = the last launch's... take v[0]), read before the repack
            constexpr int NS = 2000;
            std::mt19937 rs(3);
            std::vector<int> st(NS), sr(NS);
            std::vector<uint8_t> srow((size_t)NS * v[0].rb);
            for (int i = 0; i < NS; ++i) {
                st[i] = (int)(rs() % M); sr[i] = (int)(rs() % rows);
                d.get(srow.data() + (size_t)i * v[0].rb, v[0].p + (size_t)sr[i] * v[0].rb, v[0].rb);
            }
            auto err_of = [&](const std::vector<float> &y) {
                double s = 0, mx = 0;
                for (int i = 0; i < NS; ++i) {
                    const uint8_t *row = srow.data() + (size_t)i * v[0].rb;
                    double ref = 0, ab = 0;
                    for (int c = 0; c < cols; ++c) {
                        const double wv = (double)(int8_t)row[c] * (double)fmt::h2f(row + cols + 2 * (c / 32));
                        const double p = wv * hx[(size_t)st[i] * cols + c];
                        ref += p; ab += std::fabs(p);
                    }
                    const double e = ab > 0 ? std::fabs(y[(size_t)st[i] * rows + sr[i]] - ref) / (std::ldexp(1.0, -24) * ab) : 0;
                    s += e; mx = std::max(mx, e);
                }
                char b[64];
                std::snprintf(b, sizeof b, "mean %.4f max %.4f", s / NS, mx);
                return std::string(b);
            };
            // today's error: dense_t on layer v[0] (the last launch of timeit was i = 0)
            std::printf("  today's error vs double: %s\n", err_of(yt).c_str());
            std::vector<WView> v0p(NL);
            for (int l = 0; l < NL; ++l) { v0p[l] = v[l]; uint8_t *cp = d.alloc<uint8_t>(v[l].rb * rows); d.q.memcpy(cp, v[l].p, v[l].rb * rows).wait(); v0p[l].p = cp; }
            std::vector<uint8_t *> vg(NL);
            for (int l = 0; l < NL; ++l) { vg[l] = d.alloc<uint8_t>(v[l].rb * rows); xd::repack_q8g(d.q, v[l].p, v[l].rb, rows, cols, vg[l]); }
            for (int l = 0; l < NL; ++l) xd::repack_q8t(d.q, const_cast<uint8_t *>(v[l].p), v[l].rb, rows, cols, tmp);
            const double us_s = timeit([&](int) { xd::split(d.q, x, cols, M, Mpad, cols, P, (size_t)Mpad * cols); });
            std::printf("  xmx: split %.1f us\n", us_s);
            std::vector<float> y0;
            auto big = [&]<int SM, int SR, int NM, int NB, int KC, bool C23 = true, int G = 0, bool XS = false>(bool first = false) {
                if (cols % (16 * KC) || rows % (16 * NB * SR) || Mpad % (8 * NM * SM)) { std::printf("  (skip SM%d SR%d NM%d NB%d KC%d)\n", SM, SR, NM, NB, KC); return; }
                d.q.memset(Y, 0, (size_t)M * rows * 4).wait();
                const double us = timeit([&](int i) { xd::dense<SM, SR, NM, NB, KC, C23, G, XS>(d.q, v[i % NL].p, rows, cols, P, (size_t)Mpad * cols, Mpad, M, Y, rows, x, cols); });
                std::vector<float> y((size_t)M * rows);
                d.get(y.data(), Y, y.size());
                const char *same = "";
                if (first) y0 = y;
                else same = std::memcmp(y.data(), y0.data(), y.size() * 4) ? "  DIFF vs first" : "  same as first";
                std::printf("  xmx dense SM%d SR%d NM%d NB%d KC%d %s G%d%s: %8.1f us (%.2f T exact MAC/s)%s\n", SM, SR, NM, NB, KC, C23 ? "c1|c23" : "one chain", G, XS ? " split inside" : "", us,
                            macs / us / 1e6, same);
                if (first) std::printf("    error vs double: %s\n", err_of(y).c_str());
            };
            big.template operator()<4, 4, 2, 2, 4>(true);
            big.template operator()<4, 4, 2, 2, 4, false, 8>(true); // the chosen arithmetic: the reference of what follows
            big.template operator()<4, 2, 2, 2, 4, false, 8>();
            big.template operator()<4, 4, 2, 2, 4, false, 8>();
            // small steps: the first r tokens, bits against the many-token kernel's rows
            auto small = [&]<int MR, int PF, int SGW>(int r) {
                if (cols % (16 * PF) || rows % (16 * SGW)) return;
                const double us = timeit([&](int i) { xd::dsmall<MR, PF, SGW>(d.q, v[i % NL].p, rows, cols, P, (size_t)Mpad * cols, r, Y1, rows); });
                std::vector<float> y((size_t)r * rows);
                d.get(y.data(), Y1, y.size());
                const bool same = !std::memcmp(y.data(), y0.data(), y.size() * 4);
                std::printf("  xmx small MR%d PF%d SGW%d, %d tokens: %7.2f us (%.0f GB/s)  %s\n", MR, PF, SGW, r, us, (double)v[0].rb * rows / us / 1e3,
                            same ? "same bits as many-token" : "DIFF");
            };
            auto grp = [&]<int MR, bool C23>(int r) {
                const double us = timeit([&](int i) { xd::dgroup<MR, 8, C23>(d.q, v[i % NL].p, rows, cols, P, (size_t)Mpad * cols, r, Y1, rows); });
                std::vector<float> y((size_t)r * rows);
                d.get(y.data(), Y1, y.size());
                const bool same = !std::memcmp(y.data(), y0.data(), y.size() * 4);
                std::printf("  xmx grouped MR%d %s, %d tokens: %7.2f us (%.0f GB/s)  %s\n", MR, C23 ? "c1|c23" : "one chain", r, us,
                            (double)v[0].rb * rows / us / 1e3, same ? "same bits as many-token" : "DIFF");
            };
            auto grpx = [&]<int MR>(int r) {
                const double us = timeit([&](int i) { xd::dgroupx<MR, 8>(d.q, v[i % NL].p, rows, cols, x, cols, r, Y1, rows); });
                std::vector<float> y((size_t)r * rows);
                d.get(y.data(), Y1, y.size());
                const bool same = !std::memcmp(y.data(), y0.data(), y.size() * 4);
                std::printf("  xmx grouped, split inside, MR%d, %d tokens: %7.2f us (%.0f GB/s)  %s\n", MR, r, us, (double)v[0].rb * rows / us / 1e3,
                            same ? "same bits as many-token" : "DIFF");
            };
            grpx.template operator()<1>(1);
            grpx.template operator()<2>(2);
            grpx.template operator()<4>(4);
            grpx.template operator()<8>(8);
            grpx.template operator()<8>(5);
            grp.template operator()<1, false>(1);
            auto grpb = [&]<int MR, int GRF>(int r) {
                const double us = timeit([&](int i) { xd::dgroupb<MR, GRF>(d.q, v[i % NL].p, rows, cols, x, cols, r, Y1, rows); });
                std::vector<float> y((size_t)r * rows);
                d.get(y.data(), Y1, y.size());
                const bool same = !std::memcmp(y.data(), y0.data(), y.size() * 4);
                std::printf("  xmx grouped, inputs read at the start, MR%d GRF%d, %d tokens: %7.2f us (%.0f GB/s)  %s\n", MR, GRF, r, us,
                            (double)v[0].rb * rows / us / 1e3, same ? "same bits as many-token" : "DIFF");
            };
            auto grpc = [&]<int MR, int GRF>(int r) {
                const double us = timeit([&](int i) { xd::dgroupc<MR, GRF>(d.q, vg[i % NL], rows, cols, x, cols, r, Y1, rows, zbf); });
                std::vector<float> y((size_t)r * rows);
                d.get(y.data(), Y1, y.size());
                const bool same = !std::memcmp(y.data(), y0.data(), y.size() * 4);
                std::printf("  xmx grouped Q8G, MR%d GRF%d, %d tokens: %7.2f us (%.0f GB/s)  %s\n", MR, GRF, r, us,
                            (double)v[0].rb * rows / us / 1e3, same ? "same bits as many-token" : "DIFF");
            };
            grpc.template operator()<1, 128>(1);
            if (!std::getenv("BENCH_NO_ESIMD")) { // the ESIMD kernel on Q8E (inputs as parts), against the same reference
                std::vector<uint8_t *> ve(NL);
                for (int l = 0; l < NL; ++l) { ve[l] = d.alloc<uint8_t>(v[l].rb * rows); xd::repack_q8e(d.q, v0p[l].p, v[l].rb, rows, cols, ve[l]); }
                uint16_t *Pe = d.alloc<uint16_t>((size_t)3 * 8 * cols);
                auto ese = [&]<int MR>(int r) {
                    d.q.memset(Pe, 0, (size_t)3 * 8 * cols * 2).wait();
                    xd::split(d.q, x, cols, r, 8, cols, Pe, (size_t)8 * cols);
                    d.q.wait();
                    const double us = timeit([&](int i) { xd::dgroupe<MR>(d.q, ve[i % NL], rows, cols, Pe, cols, (size_t)8 * cols, r, Y1, rows); });
                    std::vector<float> y((size_t)r * rows);
                    d.get(y.data(), Y1, y.size());
                    const bool same = !std::memcmp(y.data(), y0.data(), y.size() * 4);
                    const double gv = timeit([&](int i) { gemv_v(d.q, v0p[i % NL], x, cols, Y1, rows, 1, rows <= 1024 ? Tune{1, 4} : Tune{2, 2}); });
                    std::printf("  ESIMD Q8E MR%d, %d tokens: %7.2f us (%.0f GB/s)  %s; today's gemv_v (1 token) same moment %.2f us\n", MR, r, us,
                                (double)v[0].rb * rows / us / 1e3, same ? "same bits as many-token" : "DIFF", gv);
                };
                ese.template operator()<1>(1);
                // 2-8 tokens: PE parts, against today's gemv_multi_m (one job, inputs in lane order)
                const int lx = (int)xlane_floats(cols);
                float *xl = d.alloc<float>((size_t)8 * lx);
                d.q.parallel_for(sycl::range<2>(8, (size_t)cols), [=](sycl::id<2> i) { xl[i[0] * lx + xlane_at((int)i[1])] = x[i[0] * cols + i[1]]; }).wait();
                auto es2 = [&]<int MR, int GRF>(int r) {
                    xd::splite<MR>(d.q, x, cols, r, cols, Pe);
                    d.q.wait();
                    const double us = timeit([&](int i) { xd::dgroupe2<MR, GRF>(d.q, ve[i % NL], rows, cols, Pe, r, Y1, rows); });
                    std::vector<float> y((size_t)r * rows);
                    d.get(y.data(), Y1, y.size());
                    const bool same = !std::memcmp(y.data(), y0.data(), y.size() * 4);
                    const double usp = timeit([&](int) { xd::splite<MR>(d.q, x, cols, r, cols, Pe); });
                    const double um = r < 2 ? 0.0 : timeit([&](int i) {
                        MultiJobs mj;
                        multi_add(mj, v0p[i % NL], xl, Y1, 2, lx, rows);
                        gemv_multi_m(d.q, mj, r, true, 2, true);
                    });
                    std::printf("  ESIMD PE MR%d GRF%d, %d tokens: %7.2f us  %s (split %.2f us); today's gemv_multi_m %.2f us\n", MR, GRF, r, us,
                                same ? "same bits as many-token" : "DIFF", usp, um);
                };
                es2.template operator()<1, 128>(1);
                es2.template operator()<2, 128>(2);
                es2.template operator()<4, 128>(4);
                es2.template operator()<4, 256>(4);
                es2.template operator()<8, 128>(8);
                es2.template operator()<8, 256>(8);
                { // the prompt kernel on Q8E, against Q8T at the same moment
                    d.q.memset(Y, 0, (size_t)M * rows * 4).wait();
                    const double ue = timeit([&](int i) { xd::dense<4, 4, 2, 2, 4, false, 8, false, true>(d.q, ve[i % NL], rows, cols, P, (size_t)Mpad * cols, Mpad, M, Y, rows); });
                    std::vector<float> y((size_t)M * rows);
                    d.get(y.data(), Y, y.size());
                    const double ut = timeit([&](int i) { xd::dense<4, 4, 2, 2, 4, false, 8>(d.q, v[i % NL].p, rows, cols, P, (size_t)Mpad * cols, Mpad, M, Y, rows); });
                    std::printf("  xmx dense on Q8E: %.1f us (on Q8T %.1f us)  %s\n", ue, ut, std::memcmp(y.data(), y0.data(), y.size() * 4) ? "DIFF" : "same bits as on Q8T");
                }
            }
            {
                std::vector<float> y8 = y0;
                big.template operator()<4, 4, 2, 2, 4, false, 4>(true); // groups of 4 blocks: reference for the G4 kernels
                auto grph = [&]<int MR, int GRF>(int r) {
                    const double us = timeit([&](int i) { xd::dgrouph<MR, GRF, 4>(d.q, vg[i % NL], rows, cols, x, cols, r, Y1, rows, zbf); });
                    std::vector<float> y((size_t)r * rows);
                    d.get(y.data(), Y1, y.size());
                    const bool same = !std::memcmp(y.data(), y0.data(), y.size() * 4);
                    std::printf("  xmx G4 Q8G MR%d GRF%d, %d tokens: %7.2f us (%.0f GB/s)  %s\n", MR, GRF, r, us, (double)v[0].rb * rows / us / 1e3,
                                same ? "same bits as many-token G4" : "DIFF");
                };
                grph.template operator()<1, 128>(1);
                grph.template operator()<2, 128>(2);
                grph.template operator()<4, 128>(4);
                grph.template operator()<8, 128>(8);
                grph.template operator()<8, 256>(8);
                grph.template operator()<8, 128>(5);
                const double g8 = timeit([&](int i) { xd::dgrouph<1, 128, 8>(d.q, vg[i % NL], rows, cols, x, cols, 1, Y1, rows, zbf); });
                const double gv = timeit([&](int i) { gemv_v(d.q, v0p[i % NL], x, cols, Y1, rows, 1, rows <= 1024 ? Tune{1, 4} : Tune{2, 2}); });
                std::printf("  again, same moment: G8 MR1 %.2f us, today's gemv_v %.2f us\n", g8, gv);
                y0 = y8;
            }
            auto grpp = [&]<int MR, int GRF, int NP>(int r) {
                if (rows % (16 * NP)) return;
                const double us = timeit([&](int i) { xd::dgroupp<MR, GRF, NP>(d.q, vg[i % NL], rows, cols, x, cols, r, Y1, rows, zbf); });
                std::vector<float> y((size_t)r * rows);
                d.get(y.data(), Y1, y.size());
                const bool same = !std::memcmp(y.data(), y0.data(), y.size() * 4);
                std::printf("  xmx grouped Q8G in phases NP%d, MR%d GRF%d, %d tokens: %7.2f us (%.0f GB/s)  %s\n", NP, MR, GRF, r, us,
                            (double)v[0].rb * rows / us / 1e3, same ? "same bits as many-token" : "DIFF");
            };
            grpp.template operator()<1, 256, 2>(1);
            grpp.template operator()<1, 256, 4>(1);
            grpp.template operator()<2, 256, 4>(2);
            {
                const double u1 = timeit([&](int i) { xd::dgroupc<1, 128, 1>(d.q, vg[i % NL], rows, cols, x, cols, 1, Y1, rows, zbf); });
                const double u2 = timeit([&](int i) { xd::dgroupc<1, 128, 2>(d.q, vg[i % NL], rows, cols, x, cols, 1, Y1, rows, zbf); });
                const double u0 = timeit([&](int) { d.q.single_task([=]() { Y1[0] = 0.0f; }); });
                const double ud = timeit([&](int i) { xd::dgroupc<1, 128, 0, 0>(d.q, vg[i % NL], rows, cols, x, cols, 1, Y1, rows, zbf); });
                std::printf("  old decode (shifts): %.2f us\n", ud);
                std::printf("  ablations Q8G MR1: loads only %.2f us (%.0f GB/s), no DPAS %.2f us; an empty kernel %.2f us\n", u1, (double)v[0].rb * rows / u1 / 1e3, u2, u0);
            }
            grpc.template operator()<2, 128>(2);
            grpc.template operator()<4, 256>(4);
            grpc.template operator()<8, 256>(8);
            grpb.template operator()<1, 128>(1);
            grpb.template operator()<2, 128>(2);
            grpb.template operator()<4, 128>(4);
            grpb.template operator()<4, 256>(4);
            grpb.template operator()<8, 256>(8);
            grpb.template operator()<8, 256>(5);
        }
        // one token's attention inputs in one launch: q, k, v, gate, rel of the layers where all five are Q8_0
        if (!only || !std::strcmp(only, "fused")) {
            const char *fn[5] = {"attn_q", "attn_k", "attn_v", "attn_gate", "attn_rel"};
            struct L { WView v[5]; uint8_t *g[5]; };
            std::vector<L> ls;
            for (int l = 6; l < 18; ++l) {
                L a;
                bool ok = true;
                for (int k = 0; k < 5; ++k) { a.v[k] = views.at("blk." + std::to_string(l) + "." + fn[k] + ".weight"); ok = ok && a.v[k].kind == K_Q8_0P; }
                if (!ok) continue;
                for (int k = 0; k < 5; ++k) {
                    const int rows = (int)a.v[k].t->rows();
                    a.g[k] = d.alloc<uint8_t>(a.v[k].rb * rows);
                    xd::repack_q8g(d.q, a.v[k].p, a.v[k].rb, rows, 2304, a.g[k]);
                }
                ls.push_back(a);
            }
            const int NLf = (int)ls.size();
            size_t bytes = 0;
            int off[6] = {0};
            for (int k = 0; k < 5; ++k) { bytes += ls[0].v[k].rb * ls[0].v[k].t->rows(); off[k + 1] = off[k] + (int)ls[0].v[k].t->rows(); }
            float *Yf = d.alloc<float>(8 * off[5]), *Yg = d.alloc<float>(8 * off[5]);
            std::printf("fused attention inputs: %d layers, %d rows, %.1f MB per layer\n", NLf, off[5], bytes / 1e6);
            const double ut = timeit([&](int i) {
                MultiJobs mj;
                for (int k = 0; k < 5; ++k) multi_add(mj, ls[i % NLf].v[k], x, Yf + off[k], ls[0].v[k].t->rows() <= 1024 ? 1 : 2);
                gemv_multi(d.q, mj, 2);
            });
            auto fx = [&]<int MR, int GRF>(int r) {
                const double us = timeit([&](int i) {
                    xd::XJobs jb;
                    for (int k = 0; k < 5; ++k) xd::xjob_add(jb, ls[i % NLf].g[k], (int)ls[0].v[k].t->rows(), x, Yg + off[k]);
                    xd::dgroupj<MR, GRF>(d.q, jb, 2304, x, 2304, r, off[5], zbf);
                });
                // bits: each job against the single-matrix kernel
                bool same = true;
                std::vector<float> a((size_t)r * off[5]), b((size_t)r * off[5]);
                d.get(a.data(), Yg, a.size());
                for (int k = 0; k < 5; ++k) xd::dgroupc<MR, GRF>(d.q, ls[0].g[k], (int)ls[0].v[k].t->rows(), 2304, x, 2304, r, Yf + off[k], off[5], zbf);
                d.q.wait();
                d.get(b.data(), Yf, b.size());
                same = !std::memcmp(a.data(), b.data(), a.size() * 4);
                std::printf("  xmx fused MR%d GRF%d, %d tokens: %7.2f us (%.0f GB/s)  %s\n", MR, GRF, r, us, bytes / us / 1e3, same ? "same bits as one by one" : "DIFF");
            };
            std::printf("  today (cold): gemv_multi %.2f us (%.0f GB/s)\n", ut, bytes / ut / 1e3);
            for (int rep = 0; rep < 3; ++rep) {
                const double u = timeit([&](int i) {
                    MultiJobs mj;
                    for (int k = 0; k < 5; ++k) multi_add(mj, ls[i % NLf].v[k], x, Yf + off[k], ls[0].v[k].t->rows() <= 1024 ? 1 : 2);
                    gemv_multi(d.q, mj, 2);
                });
                std::printf("  today: gemv_multi %.2f us (%.0f GB/s)\n", u, bytes / u / 1e3);
                fx.template operator()<1, 128>(1);
            }
            for (int ah : {100, 160, 227, 300}) {
                const double us = timeit([&](int i) {
                    xd::XJobs jb;
                    for (int k = 0; k < 5; ++k) xd::xjob_add(jb, ls[i % NLf].g[k], (int)ls[0].v[k].t->rows(), x, Yg + off[k]);
                    xd::dgroupj<1, 128>(d.q, jb, 2304, x, 2304, 1, off[5], zbf, 0, ah);
                });
                std::printf("  xmx fused MR1, prefetch %d work-groups ahead: %.2f us\n", ah, us);
            }
            { // ESIMD, one launch for the five, Q8E weights, PE parts; 1-8 tokens against today's kernels at the same moment
                std::vector<std::array<uint8_t *, 5>> le(NLf);
                for (int l = 0; l < NLf; ++l)
                    for (int k = 0; k < 5; ++k) {
                        const int rows = (int)ls[l].v[k].t->rows();
                        le[l][k] = d.alloc<uint8_t>(ls[l].v[k].rb * rows);
                        xd::repack_q8e(d.q, ls[l].v[k].p, ls[l].v[k].rb, rows, 2304, le[l][k]);
                    }
                uint16_t *Pq = d.alloc<uint16_t>((size_t)3 * 8 * 2304);
                const int lx = (int)xlane_floats(2304);
                float *xl = d.alloc<float>((size_t)8 * lx);
                d.q.parallel_for(sycl::range<2>(8, 2304), [=](sycl::id<2> i) { xl[i[0] * lx + xlane_at((int)i[1])] = x[i[0] * 2304 + i[1]]; }).wait();
                auto fe = [&]<int MR, int GRF>(int r) {
                    xd::splite<MR>(d.q, x, 2304, r, 2304, Pq);
                    d.q.wait();
                    auto run = [&](int i) {
                        xd::EJobs jb;
                        for (int k = 0; k < 5; ++k) xd::ejob_add(jb, le[i % NLf][k], (int)ls[0].v[k].t->rows(), Pq, Yg + off[k], off[5]);
                        xd::dgroupej<MR, GRF>(d.q, jb, 2304);
                    };
                    const double us = timeit(run);
                    const double uw = timeit([&](int i) { xd::splite<MR>(d.q, x, 2304, r, 2304, Pq); run(i); });
                    double ut2;
                    if (r == 1)
                        ut2 = timeit([&](int i) {
                            MultiJobs mj;
                            for (int k = 0; k < 5; ++k) multi_add(mj, ls[i % NLf].v[k], x, Yf + off[k], ls[0].v[k].t->rows() <= 1024 ? 1 : 2);
                            gemv_multi(d.q, mj, 2);
                        });
                    else
                        ut2 = timeit([&](int i) {
                            MultiJobs mj;
                            for (int k = 0; k < 5; ++k) multi_add(mj, ls[i % NLf].v[k], xl, Yf + off[k], r > 4 ? 2 : 2, lx, off[5]);
                            gemv_multi_m(d.q, mj, r, true, 2, true);
                        });
                    // bits: against the single-matrix Q8G kernel of the same arithmetic (one by one)
                    std::vector<float> a((size_t)r * off[5]), b((size_t)r * off[5]);
                    run(0);
                    d.q.wait();
                    d.get(a.data(), Yg, a.size());
                    for (int k = 0; k < 5; ++k) xd::dgroupc<MR, 256>(d.q, ls[0].g[k], (int)ls[0].v[k].t->rows(), 2304, x, 2304, r, Yf + off[k], off[5], zbf);
                    d.q.wait();
                    d.get(b.data(), Yf, b.size());
                    std::printf("  ESIMD fused MR%d GRF%d, %d tokens: %7.2f us, with its split %7.2f us; today %7.2f us  %s\n", MR, GRF, r, us, uw, ut2,
                                std::memcmp(a.data(), b.data(), a.size() * 4) ? "DIFF" : "same bits as one by one");
                };
                for (int rep = 0; rep < 2; ++rep) {
                    fe.template operator()<1, 128>(1);
                    fe.template operator()<2, 128>(2);
                    fe.template operator()<2, 256>(2);
                    fe.template operator()<4, 128>(4);
                    fe.template operator()<4, 256>(4);
                    fe.template operator()<8, 128>(8);
                    fe.template operator()<8, 256>(8);
                }
            }
            if (std::getenv("BENCH_ESIMD_ONLY")) return 0;
            // steps of 2-8 tokens: today's gemv_multi_m (inputs in lane order, big rows) against the parts + 2D loads
            const int lx = (int)xlane_floats(2304);
            float *xl = d.alloc<float>((size_t)8 * lx);
            d.q.memcpy(xl, x, (size_t)8 * lx * 4).wait();
            uint16_t *Pf = d.alloc<uint16_t>((size_t)3 * 8 * 2304);
            for (int r : {2, 4, 8}) {
                const double um = timeit([&](int i) {
                    MultiJobs mj;
                    for (int k = 0; k < 5; ++k) multi_add(mj, ls[i % NLf].v[k], xl, Yf + off[k], 2, lx, off[5]);
                    gemv_multi_m(d.q, mj, r, true, 2, true);
                });
                const double usp = timeit([&](int) { xd::split(d.q, x, 2304, r, 8, 2304, Pf, (size_t)8 * 2304); });
                auto fp = [&]<int MR, int GRF>() {
                    return timeit([&](int i) {
                        xd::XJobs jb;
                        for (int k = 0; k < 5; ++k) xd::xjob_add(jb, ls[i % NLf].g[k], (int)ls[0].v[k].t->rows(), reinterpret_cast<const float *>(Pf), Yg + off[k]);
                        xd::dgroupj<MR, GRF, true>(d.q, jb, 2304, nullptr, 2304, r, off[5], zbf, (size_t)8 * 2304);
                    });
                };
                double u1 = 0, u2 = 0;
                if (r == 2) { u1 = fp.template operator()<2, 128>(); u2 = fp.template operator()<2, 256>(); }
                if (r == 4) { u1 = fp.template operator()<4, 128>(); u2 = fp.template operator()<4, 256>(); }
                if (r == 8) { u1 = fp.template operator()<8, 128>(); u2 = fp.template operator()<8, 256>(); }
                std::vector<float> a((size_t)r * off[5]), b((size_t)r * off[5]);
                d.get(a.data(), Yg, a.size());
                if (r == 2) fx.template operator()<2, 128>(2);
                if (r == 4) fx.template operator()<4, 256>(4);
                if (r == 8) fx.template operator()<8, 256>(8);
                d.get(b.data(), Yg, b.size());
                std::printf("  %d tokens: today gemv_multi_m %.2f us; parts: split %.2f + fused GRF128 %.2f / GRF256 %.2f us  %s\n", r, um, usp, u1, u2,
                            std::memcmp(a.data(), b.data(), a.size() * 4) ? "DIFF vs split inside" : "same bits as split inside");
            }
            const double ut2 = timeit([&](int i) {
                MultiJobs mj;
                for (int k = 0; k < 5; ++k) multi_add(mj, ls[i % NLf].v[k], x, Yf + off[k], ls[0].v[k].t->rows() <= 1024 ? 1 : 2);
                gemv_multi(d.q, mj, 2);
            });
            std::printf("  today again: gemv_multi %.2f us\n", ut2);
        }
    } catch (const std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
