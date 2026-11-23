// test_gemv: gemv.hpp against a double-precision host product (ggml to_float rows), run-to-run identity, and
// M-independence (vector 0 alone equals vector 0 among 8), for a few tensors of each type.  test_gemv <gguf> <card>
#include "../src/gemv.hpp"
#include "ggml.h"
#include <cmath>
#include <cstdio>
#include <map>
#include <random>

int main(int argc, char **argv) {
    using namespace ink;
    { ggml_init_params ip = {(size_t)16 << 20, nullptr, false}; ggml_free(ggml_init(ip)); }
    GGUF g(argv[1]);
    Device d(std::atoi(argv[2]));
    std::map<uint32_t, int> seen;
    std::mt19937 rng(7);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    bool ok = true;
    for (auto &t : g.tensors) {
        if (t.ne.size() < 2 || t.ne[0] % 32 || t.type == G_I32) continue;
        if (++seen[t.type] > 2) continue;
        int cols = (int)t.ne[0], rows = (int)std::min<int64_t>(t.rows(), 4096); // first 4096 rows (an expert slice)
        size_t rb = t.row_bytes();
        std::vector<uint8_t> raw(rb * rows);
        g.read_at(raw.data(), raw.size(), g.data_off + t.off);
        std::vector<float> x(8 * (size_t)cols);
        for (auto &v : x) v = nd(rng);
        uint8_t *dW = d.alloc<uint8_t>(raw.size());
        float *dx = d.alloc<float>(x.size()), *y1 = d.alloc<float>(rows), *y8 = d.alloc<float>(8 * (size_t)rows), *y1b = d.alloc<float>(rows);
        d.put(dW, raw.data(), raw.size());
        d.put(dx, x.data(), x.size());
        Tensor tt = t; tt.ne = {cols, rows};
        gemv(d.q, tt, dW, dx, cols, y1, rows, 1).wait();
        gemv(d.q, tt, dW, dx, cols, y1b, rows, 1).wait();
        gemv(d.q, tt, dW, dx, cols, y8, rows, 8).wait();
        std::vector<float> h1(rows), h1b(rows), h8(8 * (size_t)rows);
        d.get(h1.data(), y1, rows); d.get(h1b.data(), y1b, rows); d.get(h8.data(), y8, h8.size());
        auto to_float = ggml_get_type_traits((ggml_type)t.type)->to_float;
        std::vector<float> wrow(cols);
        double maxrel = 0;
        for (int r = 0; r < rows; ++r) {
            if (t.type == G_F32) std::memcpy(wrow.data(), raw.data() + rb * r, 4 * cols); else to_float(raw.data() + rb * r, wrow.data(), cols);
            for (int m = 0; m < 8; m += 7) {
                double s = 0, sa = 0;
                for (int k = 0; k < cols; ++k) { s += (double)wrow[k] * x[(size_t)m * cols + k]; sa += std::fabs((double)wrow[k] * x[(size_t)m * cols + k]); }
                double got = m == 0 ? h1[r] : h8[(size_t)7 * rows + r];
                maxrel = std::max(maxrel, std::fabs(got - s) / (sa + 1e-30));
            }
        }
        bool same_run = std::memcmp(h1.data(), h1b.data(), 4 * rows) == 0;
        bool same_m = std::memcmp(h1.data(), h8.data(), 4 * rows) == 0;
        bool close = maxrel < 1e-5;
        ok &= same_run && same_m && close;
        std::printf("%-7s %-36s %5dx%-5d max err / sum|terms| %.2e  repeat %s  M=1 vs M=8 %s\n", type_name(t.type), t.name.c_str(), rows, cols, maxrel,
                    same_run ? "same" : "DIFF", same_m ? "same" : "DIFF");
    }
    std::printf("%s\n", ok ? "ALL PASS" : "FAILURES");
    return ok ? 0 : 1;
}
