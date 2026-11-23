// bench_gemv: time matrix-vector kernel variants (gemv2.hpp) on real tensors of the model and check every variant
// against gemv.hpp (the first kernels) bit for bit.   bench_gemv <model.gguf> <card> <tensor>...
// Timing reads from memory, not from the cache: each variant cycles through copies of the weight (at least 256 MB in
// all), and expert tensors cycle through 16 sets of 8 experts (all 128 once). 3-D expert tensors are timed in the
// routed form (8 experts, one token). BENCH_ITERS (default 200); BENCH_FILE=1 also times the file layout.
#include "../src/tok_tiles.hpp"
#include "../src/multi.hpp"
#include <random>

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 4) { std::fprintf(stderr, "usage: bench_gemv <model.gguf> <card> <tensor>...\n"); return 2; }
    try {
        GGUF g(argv[1]);
        Device d(std::atoi(argv[2]));
        Weights w;
        w.upload(d, g, false);
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 200;
        const bool file_too = std::getenv("BENCH_FILE") && std::atoi(std::getenv("BENCH_FILE"));
        const int BM = std::getenv("BENCH_M") ? std::atoi(std::getenv("BENCH_M")) : 1; // vectors per product (dense)
        std::mt19937 rng(7);
        for (int a = 3; a < argc; ++a) {
            const Tensor *t = g.find(argv[a]);
            if (!t) { std::fprintf(stderr, "no tensor %s\n", argv[a]); continue; }
            const bool routed = t->ne[2] > 1;
            const int cols = (int)t->ne[0], rows = (int)t->ne[1], K = routed ? 8 : BM;
            // BENCH_NS: expert sets cycled (default 16 = all 128 experts once; 1 = the same 8, read from the cache)
            const int NS = routed ? (std::getenv("BENCH_NS") ? std::atoi(std::getenv("BENCH_NS")) : 16) : 1;
            const size_t nrows = (size_t)t->rows();
            const size_t bytes = t->row_bytes() * (size_t)rows * (routed ? K : 1); // bytes read per product
            std::vector<float> hx((size_t)cols * (routed ? 1 : K));
            std::normal_distribution<float> nd(0.0f, 1.0f);
            for (auto &v : hx) v = nd(rng);
            std::vector<int32_t> hid((size_t)K * NS);
            for (int s = 0; s < NS; ++s)
                for (int k = 0; k < K; ++k) hid[(size_t)s * K + k] = routed ? (int)(((s * K + k) * 37 + 11) % t->ne[2]) : 0;
            float *x = d.alloc<float>(hx.size()), *y0 = d.alloc<float>((size_t)rows * K), *y1 = d.alloc<float>((size_t)rows * K);
            int32_t *ids = d.alloc<int32_t>(hid.size());
            d.put(x, hx.data(), hx.size());
            d.put(ids, hid.data(), hid.size());
            const uint8_t *Wraw = w[t->name];
            // copies of the weight in each layout: dense tensors get enough copies for 256 MB
            const size_t tb = t->bytes;
            const bool hot = std::getenv("BENCH_HOT") && std::atoi(std::getenv("BENCH_HOT")); // one copy: reads hit the cache
            const int ncopy = (routed || hot) ? 1 : (int)std::min<size_t>(64, std::max<size_t>(1, ((size_t)256 << 20) / tb + 1));
            WView vr{t, Wraw, t->row_bytes(), K_RAW}, vp = vr;
            std::vector<const uint8_t *> raw_copies{Wraw}, pl_copies;
            for (int c = 1; c < ncopy && file_too; ++c) {
                uint8_t *b = d.alloc<uint8_t>(tb);
                d.q.memcpy(b, Wraw, tb).wait();
                raw_copies.push_back(b);
            }
            const bool use_dec = std::getenv("BENCH_DEC") && std::atoi(std::getenv("BENCH_DEC")) && dec_kind(*t) != K_RAW;
            if (planar_kind(*t) != K_RAW || use_dec) {
                vp.kind = use_dec ? dec_kind(*t) : planar_kind(*t);
                vp.rb = use_dec ? dec_stride(*t) : planar_stride(*t);
                for (int c = 0; c < ncopy; ++c) {
                    uint8_t *b = d.alloc<uint8_t>(vp.rb * nrows);
                    if (use_dec) dec_repack(d.q, *t, Wraw, b).wait();
                    else planar_repack(d.q, *t, Wraw, b).wait();
                    pl_copies.push_back(b);
                }
                vp.p = pl_copies[0];
            } else {
                for (int c = 1; c < ncopy; ++c) {
                    uint8_t *b = d.alloc<uint8_t>(tb);
                    d.q.memcpy(b, Wraw, tb).wait();
                    raw_copies.push_back(b);
                }
                pl_copies = raw_copies;
            }
            std::vector<float> h0((size_t)rows * K), h1((size_t)rows * K);
            // launch(i): the i-th product (copy i % ncopy, expert set i % NS); the check uses i = 0
            auto timeit = [&](auto &&launch) {
                for (int i = 0; i < 4; ++i) launch(i);
                d.q.wait();
                double t0 = now_s();
                for (int i = 0; i < iters; ++i) launch(i + 1);
                d.q.wait();
                double us = (now_s() - t0) / iters * 1e6;
                launch(0);
                d.q.wait();
                return us;
            };
            auto idp = [&](int i) { return ids + (size_t)(i % NS) * K; };
            // more than 8 vectors: the reference is the engine's multi-vector path (GemvMR, 8 vectors per block; checked
            // bit-identical to gemv for blocks of 1-8), on the planar layout when there is one
            const Tune tbase{2, 2, false, 8, vp.kind == K_Q6_KP};
            double us0 = routed ? timeit([&](int i) { gemv_routed(d.q, *t, Wraw, idp(i), K, x, cols, 0, y0, rows); })
                         : K <= 8 ? timeit([&](int i) { gemv(d.q, *t, raw_copies[i % raw_copies.size()], x, cols, y0, rows, K); })
                                  : timeit([&](int i) { WView u = vp; u.p = pl_copies[i % pl_copies.size()]; gemv_v(d.q, u, x, cols, y0, rows, K, tbase); });
            d.get(h0.data(), y0, h0.size());
            std::printf("%-30s %-6s %6d x %-5d x%d %7.2f MB  %2d copies  base       %8.2f us %6.1f GB/s\n", t->name.c_str(),
                        type_name(t->type), rows, cols, K, bytes / 1e6, ncopy, us0, bytes / us0 / 1e3);
            auto run = [&](const char *lname, WView v, const std::vector<const uint8_t *> &copies, Tune tu) {
                d.q.memset(y1, 0, h1.size() * 4).wait();
                double us;
                try {
                    us = routed ? timeit([&](int i) { WView u = v; gemv_routed_v(d.q, u, idp(i), K, x, cols, 0, y1, rows, tu); })
                                : timeit([&](int i) { WView u = v; u.p = copies[i % copies.size()]; gemv_v(d.q, u, x, cols, y1, rows, K, tu); });
                } catch (std::exception &ex) { std::printf("%-30s %s: %s\n", "", lname, ex.what()); return; }
                d.get(h1.data(), y1, h1.size());
                long bad = -1;
                for (size_t r = 0; r < h1.size(); ++r) if (std::memcmp(&h0[r], &h1[r], 4)) { bad = (long)r; break; }
                std::printf("%-30s %-11s R%d sg%d mr%d %28s %8.2f us %6.1f GB/s  %s\n", "", lname, tu.R, tu.sgw, tu.mr, "", us,
                            bytes / us / 1e3, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
            };
            if (!routed && K == 1 && std::getenv("BENCH_XONLY")) { // one vector: plain vs lane-order x (gemv_v)
                std::vector<float> hxl(xlane_floats(cols), 0.0f);
                for (int i = 0; i < cols; ++i) hxl[xlane_at(i)] = hx[i];
                float *xl = d.alloc<float>(hxl.size());
                d.put(xl, hxl.data(), hxl.size());
                for (int rep = 0; rep < 2; ++rep)
                    for (int R : {1, 2, 4}) for (int sgw : {1, 2, 4}) {
                        const Tune tu{R, sgw};
                        d.q.memset(y1, 0, h1.size() * 4).wait();
                        double up = timeit([&](int i) { WView u = vp; u.p = pl_copies[i % pl_copies.size()]; gemv_v(d.q, u, x, cols, y1, rows, 1, tu); });
                        double ux = timeit([&](int i) { WView u = vp; u.p = pl_copies[i % pl_copies.size()]; gemv_v(d.q, u, xl, cols, y1, rows, 1, tu, true); });
                        d.get(h1.data(), y1, h1.size());
                        long bad = -1;
                        for (size_t r = 0; r < h1.size(); ++r) if (std::memcmp(&h0[r], &h1[r], 4)) { bad = (long)r; break; }
                        std::printf("%-30s R%d sg%d: plain x %8.2f us %6.1f GB/s, lane-order x %8.2f us %6.1f GB/s  %s\n", "", R, sgw,
                                    up, bytes / up / 1e3, ux, bytes / ux / 1e3, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
                    }
                if (t->type == G_F32) { // F32 weights in lane order too (pl::F32L)
                    const size_t lx = xlane_floats(cols);
                    std::vector<float *> lc;
                    for (size_t c = 0; c < raw_copies.size(); ++c) {
                        float *b = d.alloc<float>(lx * nrows);
                        f32_lane_repack(d.q, (const float *)raw_copies[c], b, (int)nrows, cols).wait();
                        lc.push_back(b);
                    }
                    WView vl{t, (const uint8_t *)lc[0], lx * 4, K_F32L};
                    for (int R : {1, 2}) for (int sgw : {1, 2, 4}) {
                        const Tune tu{R, sgw};
                        d.q.memset(y1, 0, h1.size() * 4).wait();
                        double ul = timeit([&](int i) { WView u = vl; u.p = (const uint8_t *)lc[i % lc.size()]; gemv_v(d.q, u, xl, cols, y1, rows, 1, tu, true); });
                        d.get(h1.data(), y1, h1.size());
                        long bad = -1;
                        for (size_t r = 0; r < h1.size(); ++r) if (std::memcmp(&h0[r], &h1[r], 4)) { bad = (long)r; break; }
                        std::printf("%-30s R%d sg%d: lane-order x and weights %8.2f us %6.1f GB/s  %s\n", "", R, sgw, ul, bytes / ul / 1e3,
                                    bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
                    }
                    for (float *b : lc) d.release(b);
                }
                d.release(xl);
                continue;
            }
            if (!routed && K > 1) { // vector blocks
                { // token-parallel tiles (tok_tiles.hpp)
                    float *Xd = d.alloc<float>((size_t)((K + 15) / 16) * cols * 16);
                    double ug = timeit([&](int) { dense_gather(d.q, x, cols, K, cols, Xd); });
                    std::printf("%-30s dense_gather %8.2f us\n", "", ug);
                    for (int R : {1, 2, 4}) for (int sgw : {1, 2}) {
                        d.q.memset(y1, 0, h1.size() * 4).wait();
                        double us = timeit([&](int i) { WView u = vp; u.p = pl_copies[i % pl_copies.size()]; dense_t(d.q, u, K, Xd, y1, rows, DTune{R, sgw}); });
                        d.get(h1.data(), y1, h1.size());
                        long bad = -1;
                        for (size_t r = 0; r < h1.size(); ++r) if (std::memcmp(&h0[r], &h1[r], 4)) { bad = (long)r; break; }
                        std::printf("%-30s %-11s R%d sg%d     %28s %8.2f us %6.1f GB/s  %s\n", "", "tiles", R, sgw, "", us,
                                    bytes / us / 1e3, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
                    }
                    d.release(Xd);
                }
                if (K > 8) continue;
                if (vp.kind != K_RAW) { // vector blocks with each vector in lane order (xlane.hpp), against the plain kernel
                    const size_t lxl = xlane_floats(cols);
                    std::vector<float> hxl(lxl * K, 0.0f);
                    for (int k = 0; k < K; ++k) for (int i = 0; i < cols; ++i) hxl[k * lxl + xlane_at(i)] = hx[(size_t)k * cols + i];
                    float *xl = d.alloc<float>(hxl.size());
                    d.put(xl, hxl.data(), hxl.size());
                    for (int rep = 0; rep < 2; ++rep)
                        for (int mr : {1, 2, 4, 8}) {
                            if (K % mr) continue;
                            for (int R : {1, 2, 4}) for (int sgw : {1, 2}) {
                                const Tune tu{R, sgw, false, mr};
                                d.q.memset(y1, 0, h1.size() * 4).wait();
                                double ul;
                                try {
                                    ul = timeit([&](int i) { WView u = vp; u.p = pl_copies[i % pl_copies.size()]; gemv_v(d.q, u, xl, (int)lxl, y1, rows, K, tu, true); });
                                } catch (std::exception &ex) { std::printf("%-30s lane: %s\n", "", ex.what()); continue; }
                                d.get(h1.data(), y1, h1.size());
                                long bad = -1;
                                for (size_t r = 0; r < h1.size(); ++r) if (std::memcmp(&h0[r], &h1[r], 4)) { bad = (long)r; break; }
                                std::printf("%-30s %-11s R%d sg%d mr%d %28s %8.2f us %6.1f GB/s  %s\n", "", "lane-x", R, sgw, mr, "", ul,
                                            bytes / ul / 1e3, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
                            }
                        }
                    if (K <= 4 && multi_ok(vp)) { // the multi-matrix kernel (multi.hpp gemv_multi_m) with this matrix alone
                        for (int rep = 0; rep < 2; ++rep)
                            for (int R : {1, 2}) for (int sgw : {1, 2}) {
                                d.q.memset(y1, 0, h1.size() * 4).wait();
                                double ul = timeit([&](int i) {
                                    WView u = vp; u.p = pl_copies[i % pl_copies.size()];
                                    MultiJobs mj;
                                    multi_add(mj, u, xl, y1, R, (int)lxl, rows);
                                    gemv_multi_m(d.q, mj, K, true, sgw);
                                });
                                d.get(h1.data(), y1, h1.size());
                                long bad = -1;
                                for (size_t r = 0; r < h1.size(); ++r) if (std::memcmp(&h0[r], &h1[r], 4)) { bad = (long)r; break; }
                                std::printf("%-30s %-11s R%d sg%d     %28s %8.2f us %6.1f GB/s  %s\n", "", "multi_m", R, sgw, "", ul,
                                            bytes / ul / 1e3, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
                            }
                    }
                    d.release(xl);
                    if (std::getenv("BENCH_XONLY")) continue;
                }
                run(vp.kind ? "planar" : "file", vp, pl_copies, Tune{1, 4, false, 0});
                for (int mr : {2, 4, 8}) {
                    if (K % mr) continue;
                    for (int R : {1, 2, 4}) for (int sgw : {2, 4}) run(vp.kind ? "planar" : "file", vp, pl_copies, Tune{R, sgw, false, mr});
                    for (int R : {1, 2}) for (int sgw : {2, 4}) run(vp.kind ? "planar-il" : "file-il", vp, pl_copies, Tune{R, sgw, false, mr, true});
                }
                continue;
            }
            if (routed && vp.kind != K_RAW) { // x in lane order (xlane.hpp), interleaved with the plain kernel
                // BENCH_XDIV=1: each slot its own vector (copies of x), as the engine's down product
                const int xd = std::getenv("BENCH_XDIV") ? std::atoi(std::getenv("BENCH_XDIV")) : 0;
                const size_t lxl = xlane_floats(cols);
                std::vector<float> hxl(lxl * K, 0.0f), hxp((size_t)cols * K);
                for (int k = 0; k < K; ++k)
                    for (int i = 0; i < cols; ++i) { hxl[k * lxl + xlane_at(i)] = hx[i]; hxp[(size_t)k * cols + i] = hx[i]; }
                float *xl = d.alloc<float>(hxl.size()), *xp = d.alloc<float>(hxp.size());
                d.put(xl, hxl.data(), hxl.size());
                d.put(xp, hxp.data(), hxp.size());
                for (int rep = 0; rep < 2; ++rep)
                    for (int R : {1, 2, 4}) for (int sgw : {1, 2, 4}) {
                        const Tune tu{R, sgw};
                        d.q.memset(y1, 0, h1.size() * 4).wait();
                        double up = timeit([&](int i) { gemv_routed_v(d.q, vp, idp(i), K, xp, cols, xd, y1, rows, tu); });
                        double ux = timeit([&](int i) { gemv_routed_v(d.q, vp, idp(i), K, xl, (int)lxl, xd, y1, rows, tu, true); });
                        d.get(h1.data(), y1, h1.size());
                        long bad = -1;
                        for (size_t r = 0; r < h1.size(); ++r) if (std::memcmp(&h0[r], &h1[r], 4)) { bad = (long)r; break; }
                        std::printf("%-30s R%d sg%d: plain x %8.2f us %6.1f GB/s, lane-order x %8.2f us %6.1f GB/s  %s\n", "", R, sgw,
                                    up, bytes / up / 1e3, ux, bytes / ux / 1e3, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
                    }
                if (rows % 2 == 0) { // the gate|up pair kernel, plain and lane-order x
                    struct StoreOp2 { float *y; int n; void operator()(int k, int r, float a, float b) const { y[(size_t)k * 2 * n + r] = a; y[(size_t)k * 2 * n + n + r] = b; } };
                    const int half = rows / 2;
                    const size_t es = vp.rb * (size_t)rows;
                    std::vector<float> hp((size_t)rows * K);
                    for (int rep = 0; rep < 2; ++rep)
                        for (int sgw : {1, 2}) {
                            double up = timeit([&](int i) { gemv_pair(d.q, vp, vp.p + (size_t)half * vp.rb, es, half, idp(i), K, x, cols, K, StoreOp2{y1, half}, sgw); });
                            d.get(hp.data(), y1, hp.size());
                            double ux = timeit([&](int i) { gemv_pair(d.q, vp, vp.p + (size_t)half * vp.rb, es, half, idp(i), K, xl, 0, K, StoreOp2{y1, half}, sgw, true); });
                            d.get(h1.data(), y1, h1.size());
                            const bool same = !std::memcmp(hp.data(), h1.data(), hp.size() * 4);
                            std::printf("%-30s pair sg%d: plain x %8.2f us %6.1f GB/s, lane-order x %8.2f us %6.1f GB/s  %s\n", "", sgw,
                                        up, bytes / up / 1e3, ux, bytes / ux / 1e3, same ? "same" : "DIFF");
                        }
                }
                d.release(xl);
                d.release(xp);
                if (std::getenv("BENCH_XONLY")) continue;
            }
            if (routed && rows % 2 == 0 && vp.kind != K_RAW) { // the engine's gate|up pair kernel: rows r and r + rows/2
                // (far, the file's order) or rows 2r and 2r + 1 (adjacent, an interleaved layout); timing only
                struct StoreOp { float *y; int n; void operator()(int k, int r, float a, float b) const { y[(size_t)k * 2 * n + r] = a; y[(size_t)k * 2 * n + n + r] = b; } };
                const int half = rows / 2;
                const size_t es = vp.rb * (size_t)rows;
                for (int sgw : {1, 2, 4}) {
                    double uf = timeit([&](int i) { gemv_pair(d.q, vp, vp.p + (size_t)half * vp.rb, es, half, idp(i), K, x, cols, K, StoreOp{y1, half}, sgw); });
                    WView va = vp; va.rb = 2 * vp.rb;
                    double ua = timeit([&](int i) { gemv_pair(d.q, va, vp.p + vp.rb, es, half, idp(i), K, x, cols, K, StoreOp{y1, half}, sgw); });
                    std::printf("%-30s pair sg%d: rows far %8.2f us %6.1f GB/s, adjacent %8.2f us %6.1f GB/s\n", "", sgw, uf, bytes / uf / 1e3, ua, bytes / ua / 1e3);
                }
                float *esc = d.alloc<float>(t->ne[2]);
                d.q.fill(esc, 1.0f, t->ne[2]).wait();
                for (int sgw : {1, 2}) {
                    double us = timeit([&](int i) { gemv_pair(d.q, vp, vp.p + (size_t)half * vp.rb, es, half, idp(i), K, x, cols, K,
                                                              SituOp{esc, idp(i), 10.0f, 10.0f, y1, half}, sgw); });
                    std::printf("%-30s pair sg%d with SITU: %8.2f us %6.1f GB/s\n", "", sgw, us, bytes / us / 1e3);
                }
                struct CheapOp { // SituOp's reads and store with a product for the math (timing only)
                    const float *escale; const int32_t *ids; float *hout; int nff;
                    float pre(int k) const { return escale[ids[k]]; }
                    void post(sycl::sub_group, int lane, int k, int i, float g, float u, float s) const {
                        if (lane == 0) hout[(size_t)k * nff + i] = (g * s) * (u * s);
                    }
                };
                for (int sgw : {1, 2}) {
                    double us = timeit([&](int i) { gemv_pair(d.q, vp, vp.p + (size_t)half * vp.rb, es, half, idp(i), K, x, cols, K,
                                                              CheapOp{esc, idp(i), y1, half}, sgw); });
                    std::printf("%-30s pair sg%d, product for SITU: %8.2f us %6.1f GB/s\n", "", sgw, us, bytes / us / 1e3);
                }
                struct NoReadOp { // the product without the scale read
                    float *hout; int nff;
                    void operator()(int k, int i, float g, float u) const { hout[(size_t)k * nff + i] = g * u; }
                };
                struct ReadStoreOp { // StoreOp's two stores plus the scale read
                    const float *escale; const int32_t *ids; float *y; int n;
                    float pre(int k) const { return escale[ids[k]]; }
                    void post(sycl::sub_group, int lane, int k, int r, float a, float b, float s) const {
                        if (lane == 0) { y[(size_t)k * 2 * n + r] = a * s; y[(size_t)k * 2 * n + n + r] = b; }
                    }
                };
                {
                    double u1 = timeit([&](int i) { gemv_pair(d.q, vp, vp.p + (size_t)half * vp.rb, es, half, idp(i), K, x, cols, K, NoReadOp{y1, half}, 1); });
                    double u2 = timeit([&](int i) { gemv_pair(d.q, vp, vp.p + (size_t)half * vp.rb, es, half, idp(i), K, x, cols, K, ReadStoreOp{esc, idp(i), y1, half}, 1); });
                    std::printf("%-30s pair sg1: product, no scale read %8.2f us; two stores + scale read %8.2f us\n", "", u1, u2);
                    for (int rep = 0; rep < 2; ++rep) {
                        double u3 = timeit([&](int i) { gemv_pair(d.q, vp, vp.p + (size_t)half * vp.rb, es, half, idp(i), K, x, cols, K, StoreOp{y1, half}, 1); });
                        double u4 = timeit([&](int i) { gemv_pair(d.q, vp, vp.p + (size_t)half * vp.rb, es, half, idp(i), K, x, cols, K,
                                                                  SituOp{esc, idp(i), 10.0f, 10.0f, y1, half}, 1); });
                        double u5 = timeit([&](int i) { gemv_pair(d.q, vp, vp.p + (size_t)half * vp.rb, es, half, idp(i), K, x, cols, K, NoReadOp{y1, half}, 1); });
                        std::printf("%-30s pair sg1 again: two stores %8.2f us, SITU %8.2f us, product %8.2f us\n", "", u3, u4, u5);
                    }
                }
            }
            if (file_too && vp.kind != K_RAW)
                for (int R : {1, 2, 4}) for (int sgw : {2, 4}) run("file", vr, raw_copies, Tune{R, sgw});
            for (int R : {1, 2, 4}) for (int sgw : {2, 4}) run(vp.kind ? "planar" : "file", vp, pl_copies, Tune{R, sgw});
            if (vp.kind == K_Q8_0P || vp.kind == K_NVFP4P)
                for (int R : {1, 2}) for (int sgw : {1, 2, 4, 8}) run("planar-pre", vp, pl_copies, Tune{R, sgw, true});
        }
    } catch (std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
