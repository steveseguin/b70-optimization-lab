// Differential fixtures: SwiGLU-clamp epilogue, engram gate, YaRN rope.
// Reference dumps: data/ops/ (generator gen_ops_ref.py; semantics from the
// official model.py, torch f64 anchor + f32). Tolerance gates (transcendental
// ops are not bit-exact across libm/torch):
//   f64 path vs torch-f64 <= 1e-9 ; f32 path vs torch-f64 <= 5e-4 (rope 1e-3)
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include "ops_misc.hpp"

static std::vector<float> loadf(const std::string &p, size_t n) {
    std::vector<float> v(n);
    FILE *f = std::fopen(p.c_str(), "rb");
    if (!f || std::fread(v.data(), 4, n, f) != n) { std::fprintf(stderr, "read %s\n", p.c_str()); std::exit(1); }
    std::fclose(f); return v;
}
static std::vector<double> loadd(const std::string &p, size_t n) {
    std::vector<double> v(n);
    FILE *f = std::fopen(p.c_str(), "rb");
    if (!f || std::fread(v.data(), 8, n, f) != n) { std::fprintf(stderr, "read %s\n", p.c_str()); std::exit(1); }
    std::fclose(f); return v;
}
template <typename A, typename B>
static double maxdiff(const A &a, const B &b) {
    double m = 0;
    for (size_t i = 0; i < a.size(); ++i) m = std::max(m, std::fabs((double)a[i] - (double)b[i]));
    return m;
}
static bool gate(const char *what, double err, double tol) {
    std::printf("%s %-30s max|diff| = %.3e (tol %.0e)\n", err <= tol ? "OK  " : "FAIL", what, err, tol);
    return err <= tol;
}

int main(int argc, char **argv) {
    const std::string dir = argc > 1 ? argv[1] : "data/ops";
    bool ok = true;

    // 1) swiglu clamp
    {
        long long n = 128 * 2304;
        auto g = loadf(dir + "/swiglu_gate.bin", n), u = loadf(dir + "/swiglu_up.bin", n);
        auto y64 = loadd(dir + "/swiglu_y_f64.bin", n);
        std::vector<double> gd(g.begin(), g.end()), ud(u.begin(), u.end()), o64(n);
        dsv41::swiglu_clamp<double>(gd.data(), ud.data(), o64.data(), n, 10.0);
        std::vector<float> o32(n);
        dsv41::swiglu_clamp<float>(g.data(), u.data(), o32.data(), n, 10.0f);
        ok &= gate("swiglu f64 vs torch-f64", maxdiff(o64, y64), 1e-9);
        ok &= gate("swiglu f32 vs torch-f64", maxdiff(o32, y64), 5e-4);
    }

    // 2) engram gate
    {
        int B = 64, hc = 4, dim = 5120;
        auto h = loadf(dir + "/eng_h.bin", B * hc * dim), key = loadf(dir + "/eng_key.bin", B * hc * dim);
        auto val = loadf(dir + "/eng_value.bin", B * dim);
        auto qw = loadf(dir + "/eng_qw.bin", hc * dim), kw = loadf(dir + "/eng_kw.bin", hc * dim);
        std::vector<uint8_t> mask(B);
        FILE *f = std::fopen((dir + "/eng_mask.bin").c_str(), "rb");
        if (!f || std::fread(mask.data(), 1, B, f) != (size_t)B) { std::fprintf(stderr, "read mask\n"); return 1; }
        std::fclose(f);
        auto y64 = loadd(dir + "/eng_y_f64.bin", B * hc * dim);
        std::vector<double> hd(h.begin(), h.end()), kd(key.begin(), key.end()), vd(val.begin(), val.end());
        std::vector<double> qd(qw.begin(), qw.end()), wd(kw.begin(), kw.end());
        std::vector<double> o64(B * hc * dim);
        dsv41::engram_gate<double>(hd.data(), kd.data(), qd.data(), wd.data(), vd.data(), mask.data(), o64.data(), B, hc, dim, 1e-20, 1e-6);
        std::vector<float> o32(B * hc * dim);
        dsv41::engram_gate<float>(h.data(), key.data(), qw.data(), kw.data(), val.data(), mask.data(), o32.data(), B, hc, dim, 1e-20f, 1e-6f);
        ok &= gate("engram gate f64 vs torch-f64", maxdiff(o64, y64), 1e-9);
        ok &= gate("engram gate f32 vs torch-f64", maxdiff(o32, y64), 5e-4);
    }

    // 3) yarn rope table + rotation (fwd and inverse)
    {
        int rdim = 64, seqlen = 4096, s = 17, h = 3;
        auto cos64 = loadd(dir + "/rope_cos.bin", seqlen * rdim / 2);
        auto sin64 = loadd(dir + "/rope_sin.bin", seqlen * rdim / 2);
        std::vector<double> fr(rdim / 2);
        dsv41::yarn_freqs<double>(fr.data(), rdim, 10000.0, 16.0, 32.0, 1.0, 65536);
        // angle table check at a few positions (cos/sin of pos*freq)
        double maxf = 0;
        for (int p : {0, 1, 777, 4095})
            for (int i = 0; i < rdim / 2; ++i) {
                double a = (double)p * fr[i];
                maxf = std::max(maxf, std::fabs(std::cos(a) - cos64[p * rdim / 2 + i]));
                maxf = std::max(maxf, std::fabs(std::sin(a) - sin64[p * rdim / 2 + i]));
            }
        ok &= gate("yarn table f64 vs torch", maxf, 1e-9);
        auto x = loadf(dir + "/rope_x.bin", s * h * rdim);
        auto xf = loadd(dir + "/rope_x_fwd.bin", s * h * rdim);
        auto xi = loadd(dir + "/rope_x_inv.bin", s * h * rdim);
        // build f64 cos/sin tables from my freqs for rotation check
        std::vector<double> ct(s * rdim / 2), stt(s * rdim / 2);
        for (int p = 0; p < s; ++p)
            for (int i = 0; i < rdim / 2; ++i) {
                ct[p * rdim / 2 + i] = std::cos((double)p * fr[i]);
                stt[p * rdim / 2 + i] = std::sin((double)p * fr[i]);
            }
        std::vector<double> xd(x.begin(), x.end()), of(s * h * rdim), oi(s * h * rdim);
        dsv41::rope_rotate<double>(xd.data(), ct.data(), stt.data(), of.data(), s, h, rdim, false);
        dsv41::rope_rotate<double>(xd.data(), ct.data(), stt.data(), oi.data(), s, h, rdim, true);
        ok &= gate("rope fwd f64 vs torch", maxdiff(of, xf), 1e-9);
        ok &= gate("rope inv f64 vs torch", maxdiff(oi, xi), 1e-9);
    }

    if (ok) std::printf("FIXTURE_PASS ops_misc\n");
    return ok ? 0 : 1;
}
