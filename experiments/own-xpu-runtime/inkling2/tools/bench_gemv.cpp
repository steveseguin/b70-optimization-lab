// bench_gemv: time matrix-vector kernel variants (gemv2.hpp) on real tensors of the model, file layout and planar
// layout, and check every variant against gemv.hpp bit for bit.   bench_gemv <model.gguf> <card> <tensor>...
// 3-D expert tensors are timed in the routed form with 8 expert ids (one token's experts).
#include "../src/gemv2.hpp"
#include <random>

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 4) { std::fprintf(stderr, "usage: bench_gemv <model.gguf> <card> <tensor>...\n"); return 2; }
    try {
        GGUF g(argv[1]);
        Device d(std::atoi(argv[2]));
        Weights w;
        w.upload(d, g);
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 200;
        std::mt19937 rng(7);
        for (int a = 3; a < argc; ++a) {
            const Tensor *t = g.find(argv[a]);
            if (!t) { std::fprintf(stderr, "no tensor %s\n", argv[a]); continue; }
            const bool routed = t->ne[2] > 1;
            const int cols = (int)t->ne[0], rows = (int)t->ne[1], K = routed ? 8 : 1;
            size_t nrows = (size_t)t->rows();
            size_t bytes = t->row_bytes() * (size_t)rows * K; // bytes read per product
            std::vector<float> hx(cols);
            std::normal_distribution<float> nd(0.0f, 1.0f);
            for (auto &v : hx) v = nd(rng);
            std::vector<int32_t> hid(K);
            for (int k = 0; k < K; ++k) hid[k] = routed ? (int)((k * 37 + 11) % t->ne[2]) : 0;
            float *x = d.alloc<float>(cols), *y0 = d.alloc<float>((size_t)rows * K), *y1 = d.alloc<float>((size_t)rows * K);
            int32_t *ids = d.alloc<int32_t>(K);
            d.put(x, hx.data(), cols);
            d.put(ids, hid.data(), K);
            const uint8_t *Wraw = w[t->name];
            WView vr{t, Wraw, t->row_bytes(), K_RAW};
            WView vp = vr;
            if (planar_kind(*t) != K_RAW) {
                vp.kind = planar_kind(*t);
                vp.rb = planar_stride(*t);
                uint8_t *buf = d.alloc<uint8_t>(vp.rb * nrows);
                planar_repack(d.q, *t, Wraw, buf).wait();
                vp.p = buf;
            }
            std::vector<float> h0((size_t)rows * K), h1((size_t)rows * K);
            auto timeit = [&](auto &&launch) {
                launch(); d.q.wait();
                double t0 = now_s();
                for (int i = 0; i < iters; ++i) launch();
                d.q.wait();
                return (now_s() - t0) / iters * 1e6;
            };
            double us0 = routed ? timeit([&] { gemv_routed(d.q, *t, Wraw, ids, K, x, cols, 0, y0, rows); })
                                : timeit([&] { gemv(d.q, *t, Wraw, x, cols, y0, rows, 1); });
            d.get(h0.data(), y0, h0.size());
            std::printf("%-30s %-6s %6d x %-5d x%d %7.2f MB  base         %8.2f us %6.1f GB/s\n", t->name.c_str(),
                        type_name(t->type), rows, cols, K, bytes / 1e6, us0, bytes / us0 / 1e3);
            for (const WView *v : {&vr, &vp}) {
                if (v == &vp && vp.kind == K_RAW) break;
                for (int R : {1, 2, 4, 8})
                    for (int sgw : {2, 4, 8}) {
                        d.q.memset(y1, 0, h1.size() * 4).wait();
                        Tune tu{R, sgw};
                        double us = routed ? timeit([&] { gemv_routed_v(d.q, *v, ids, K, x, cols, 0, y1, rows, tu); })
                                           : timeit([&] { gemv_v(d.q, *v, x, cols, y1, rows, 1, tu); });
                        d.get(h1.data(), y1, h1.size());
                        long bad = -1;
                        for (size_t r = 0; r < h1.size(); ++r) if (std::memcmp(&h0[r], &h1[r], 4)) { bad = (long)r; break; }
                        std::printf("%-30s %-6s R%d sg%d %37s %8.2f us %6.1f GB/s  %s\n", "", v->kind ? "planar" : "file",
                                    R, sgw, "", us, bytes / us / 1e3, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
                    }
            }
        }
    } catch (std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
