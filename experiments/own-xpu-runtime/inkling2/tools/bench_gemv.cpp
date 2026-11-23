// bench_gemv: time matrix-vector kernel variants (gemv2.hpp) on real tensors of the model and check every variant
// against gemv.hpp (the first kernels) bit for bit.   bench_gemv <model.gguf> <card> <tensor>...
// Timing reads from memory, not from the cache: each variant cycles through copies of the weight (at least 256 MB in
// all), and expert tensors cycle through 16 sets of 8 experts (all 128 once). 3-D expert tensors are timed in the
// routed form (8 experts, one token). BENCH_ITERS (default 200); BENCH_FILE=1 also times the file layout.
#include "../src/tok_tiles.hpp"
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
            const int cols = (int)t->ne[0], rows = (int)t->ne[1], K = routed ? 8 : BM, NS = routed ? 16 : 1;
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
            const int ncopy = routed ? 1 : (int)std::min<size_t>(64, std::max<size_t>(1, ((size_t)256 << 20) / tb + 1));
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
                run(vp.kind ? "planar" : "file", vp, pl_copies, Tune{1, 4, false, 0});
                for (int mr : {2, 4, 8}) {
                    if (K % mr) continue;
                    for (int R : {1, 2, 4}) for (int sgw : {2, 4}) run(vp.kind ? "planar" : "file", vp, pl_copies, Tune{R, sgw, false, mr});
                    for (int R : {1, 2}) for (int sgw : {2, 4}) run(vp.kind ? "planar-il" : "file-il", vp, pl_copies, Tune{R, sgw, false, mr, true});
                }
                continue;
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
