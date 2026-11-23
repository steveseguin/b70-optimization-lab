// test_formats: decode sample rows of every tensor type in a GGUF on the card (formats.hpp decode32) and compare,
// bit for bit, with ggml's own to_float from the reference library.  test_formats <model.gguf> <card> [rows]
#include "../src/device.hpp"
#include "../src/formats.hpp"
#include "ggml.h"
#include <cstdio>
#include <map>

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 3) { std::fprintf(stderr, "usage: test_formats <model.gguf> <card> [rows per tensor]\n"); return 2; }
    { ggml_init_params ip = {(size_t)16 << 20, nullptr, false}; ggml_free(ggml_init(ip)); } // ggml's tables
    GGUF g(argv[1]);
    Device d(std::atoi(argv[2]));
    int nrows = argc > 3 ? std::atoi(argv[3]) : 3;
    std::map<uint32_t, std::pair<long, long>> stats; // type -> (values compared, mismatches)
    std::map<uint32_t, int> tensors_per_type;
    for (auto &t : g.tensors) {
        if (t.type == G_I32) continue;
        if (++tensors_per_type[t.type] > 6) continue; // a few tensors per type is plenty
        int64_t n = t.ne[0], rows = t.rows();
        size_t rb = t.row_bytes();
        for (int k = 0; k < nrows; ++k) {
            int64_t r = k == 0 ? 0 : k == 1 ? rows - 1 : (rows * 7919 * k) % rows;
            std::vector<uint8_t> raw(rb);
            g.read_at(raw.data(), rb, g.data_off + t.off + (uint64_t)r * rb);
            std::vector<float> ref(n), got(n);
            auto to_float = ggml_get_type_traits((ggml_type)t.type)->to_float;
            if (t.type == G_F32) std::memcpy(ref.data(), raw.data(), 4 * n);
            else if (!to_float) { std::printf("skip %s: ggml has no to_float\n", t.name.c_str()); break; }
            else to_float(raw.data(), ref.data(), n);
            if (n % 32) { std::printf("skip %s: row of %lld\n", t.name.c_str(), (long long)n); break; }
            uint8_t *draw = d.alloc<uint8_t>(rb);
            float *dout = d.alloc<float>(n);
            d.put(draw, raw.data(), rb);
            int nc = (int)(n / 32);
            uint32_t ty = t.type;
            fmt::dispatch(ty, [&]<class FT>() {
                d.q.parallel_for(sycl::range<1>(nc), [=](sycl::id<1> c) {
                    float o[32];
                    FT::decode32(draw, (int)c[0], o);
                    for (int i = 0; i < 32; ++i) dout[32 * c[0] + i] = o[i];
                }).wait();
            });
            d.get(got.data(), dout, n);
            long bad = 0;
            for (int64_t i = 0; i < n; ++i) bad += std::memcmp(&ref[i], &got[i], 4) != 0;
            stats[t.type].first += n;
            stats[t.type].second += bad;
            if (bad) std::printf("MISMATCH %s row %lld: %ld of %lld (first ref %g got %g)\n", t.name.c_str(), (long long)r, bad, (long long)n, ref[0], got[0]);
        }
    }
    bool ok = true;
    for (auto &[ty, s] : stats) {
        std::printf("%-7s %9ld values, %ld different\n", type_name(ty), s.first, s.second);
        ok &= s.second == 0;
    }
    std::printf("%s\n", ok ? "ALL SAME" : "DIFFERENCES");
    return ok ? 0 : 1;
}
