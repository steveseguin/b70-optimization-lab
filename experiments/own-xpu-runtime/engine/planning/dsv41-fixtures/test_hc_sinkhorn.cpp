// Differential fixture: independent HC split+Sinkhorn vs the torch reference
// dump (data/hc_sinkhorn/, generator gen_hc_ref.py; real blk.0.hc_attn
// scale/base from the verified GGUF, seeded synthetic mixes).
// Gates:
//   mine-f64 vs torch-f64  <= 1e-9   (semantic transcription anchor)
//   mine-f32 vs torch-f64  <= 5e-5   (fp32 quality bound after 20 iterations)
//   mine-f32 vs torch-f32  <= 5e-5   (independent fp32 implementations)
// Note: tolerance-based, unlike the dequant gates — exp()/sigmoid differ
// across libm/torch, so bit-exactness is not a meaningful target here.
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include "hc_sinkhorn.hpp"

static std::vector<float> loadf(const std::string &path, size_t n) {
    std::vector<float> v(n);
    FILE *f = std::fopen(path.c_str(), "rb");
    if (!f || std::fread(v.data(), 4, n, f) != n) { std::fprintf(stderr, "read %s\n", path.c_str()); std::exit(1); }
    std::fclose(f);
    return v;
}
static std::vector<double> loadd(const std::string &path, size_t n) {
    std::vector<double> v(n);
    FILE *f = std::fopen(path.c_str(), "rb");
    if (!f || std::fread(v.data(), 8, n, f) != n) { std::fprintf(stderr, "read %s\n", path.c_str()); std::exit(1); }
    std::fclose(f);
    return v;
}

template <typename A, typename B>
static double max_abs_diff(const A &a, const B &b) {
    double m = 0;
    for (size_t i = 0; i < a.size(); ++i) {
        double d = std::fabs((double)a[i] - (double)b[i]);
        if (d > m) m = d;
    }
    return m;
}

int main(int argc, char **argv) {
    const std::string dir = argc > 1 ? argv[1] : "data/hc_sinkhorn";
    const long long n = 64;
    auto mixes = loadf(dir + "/mixes.bin", n * 24);
    auto scale = loadf(dir + "/scale.bin", 3);
    auto base  = loadf(dir + "/base.bin", 24);
    auto pre64 = loadd(dir + "/pre_f64.bin", n * 4);
    auto post64 = loadd(dir + "/post_f64.bin", n * 4);
    auto comb64 = loadd(dir + "/comb_f64.bin", n * 16);
    auto pre32 = loadf(dir + "/pre_f32.bin", n * 4);
    auto post32 = loadf(dir + "/post_f32.bin", n * 4);
    auto comb32 = loadf(dir + "/comb_f32.bin", n * 16);

    // f64 mine
    std::vector<double> m64(mixes.begin(), mixes.end()), s64(scale.begin(), scale.end()), b64(base.begin(), base.end());
    std::vector<double> mypre64(n * 4), mypost64(n * 4), mycomb64(n * 16);
    dsv41::hc_split_sinkhorn<double>(m64.data(), s64.data(), b64.data(), n, 20, 1e-6,
                                     mypre64.data(), mypost64.data(), mycomb64.data());
    // f32 mine
    std::vector<float> mypre32(n * 4), mypost32(n * 4), mycomb32(n * 16);
    dsv41::hc_split_sinkhorn<float>(mixes.data(), scale.data(), base.data(), n, 20, 1e-6f,
                                    mypre32.data(), mypost32.data(), mycomb32.data());

    bool ok = true;
    auto gate = [&](const char *what, double err, double tol) {
        bool pass = err <= tol;
        std::printf("%s %-28s max|diff| = %.3e (tol %.0e)\n", pass ? "OK  " : "FAIL", what, err, tol);
        ok = ok && pass;
    };
    gate("f64 vs torch-f64 pre",  max_abs_diff(mypre64, pre64),  1e-9);
    gate("f64 vs torch-f64 post", max_abs_diff(mypost64, post64), 1e-9);
    gate("f64 vs torch-f64 comb", max_abs_diff(mycomb64, comb64), 1e-9);
    gate("f32 vs torch-f64 pre",  max_abs_diff(mypre32, pre64),  5e-5);
    gate("f32 vs torch-f64 post", max_abs_diff(mypost32, post64), 5e-5);
    gate("f32 vs torch-f64 comb", max_abs_diff(mycomb32, comb64), 5e-5);
    gate("f32 vs torch-f32 comb", max_abs_diff(mycomb32, comb32), 5e-5);
    if (ok) std::printf("FIXTURE_PASS hc_sinkhorn\n");
    return ok ? 0 : 1;
}
