// Differential fixture: independent router (Gate) vs torch reference dump
// (data/route/, generator gen_route_ref.py; real blk.0.exp_probs_b.bias,
// seeded logits incl. an engineered 8-way exact tie at token 7).
// Gates per token:
//   - selected expert index SETS equal -> per-expert weight |diff| bounded
//     (f64 1e-12 anchor; f32 1e-5 quality)
//   - sets differ -> allowed only for tie-equivalent selection: sorted
//     selected raw scores must agree (f64 1e-12 / f32 1e-6) and sorted
//     weights must agree (f64 1e-12 / f32 1e-5)
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include "route_gate.hpp"

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
static std::vector<int32_t> loadi(const std::string &p, size_t n) {
    std::vector<int32_t> v(n);
    FILE *f = std::fopen(p.c_str(), "rb");
    if (!f || std::fread(v.data(), 4, n, f) != n) { std::fprintf(stderr, "read %s\n", p.c_str()); std::exit(1); }
    std::fclose(f); return v;
}

template <typename T>
static bool run(const std::string &dir, const char *tag, double tol_w, double tol_tie,
                const std::vector<float> &logits, const std::vector<float> &bias, long long n, int E, int k) {
    auto idx_t = loadi(dir + "/idx_" + tag + ".bin", n * k);
    std::vector<T> lg(logits.begin(), logits.end()), bs(bias.begin(), bias.end());
    std::vector<int32_t> idx_m(n * k);
    std::vector<T> w_m(n * k);
    dsv41::route_gate<T>(lg.data(), bs.data(), n, E, k, T(1.5), idx_m.data(), w_m.data());

    std::vector<double> w_t(n * k);
    if constexpr (std::is_same_v<T, double>) {
        auto v = loadd(dir + "/w_" + tag + ".bin", n * k); w_t.assign(v.begin(), v.end());
    } else {
        auto v = loadf(dir + "/w_" + tag + ".bin", n * k); w_t.assign(v.begin(), v.end());
    }

    long long set_mismatch = 0, bad = 0;
    double maxw = 0;
    for (long long t = 0; t < n; ++t) {
        std::vector<int32_t> a(idx_m.begin() + t * k, idx_m.begin() + t * k + k);
        std::vector<int32_t> b(idx_t.begin() + t * k, idx_t.begin() + t * k + k);
        std::vector<int32_t> as = a, bs2 = b;
        std::sort(as.begin(), as.end()); std::sort(bs2.begin(), bs2.end());
        if (as == bs2) {
            for (int i = 0; i < k; ++i) {  // compare by expert id
                double d = std::fabs((double)w_m[t * k + i] - w_t[t * k + i]);
                // find torch's weight for expert idx_m
                for (int j = 0; j < k; ++j)
                    if (idx_t[t * k + j] == idx_m[t * k + i]) {
                        d = std::fabs((double)w_m[t * k + i] - w_t[t * k + j]);
                        break;
                    }
                if (d > maxw) maxw = d;
                if (d > tol_w) { ++bad; std::fprintf(stderr, "FAIL %s t=%lld expert=%d wdiff=%.3e\n", tag, t, idx_m[t*k+i], d); }
            }
        } else {
            ++set_mismatch;
            // tie-equivalence: sorted selected raw scores and sorted weights must agree
            std::vector<double> sm, st, wm, wt;
            for (int i = 0; i < k; ++i) {
                sm.push_back((double)w_m[t * k + i]);  // weight includes norm+scale; compare weights
                wt.push_back(w_t[t * k + i]);
            }
            std::sort(sm.begin(), sm.end()); std::sort(wt.begin(), wt.end());
            for (int i = 0; i < k; ++i) {
                double d = std::fabs(sm[i] - wt[i]);
                if (d > tol_tie) { ++bad; std::fprintf(stderr, "FAIL %s t=%lld tie-weight diff=%.3e\n", tag, t, d); }
            }
        }
    }
    bool ok = bad == 0;
    std::printf("%s %s: set mismatches(tie-ok)=%lld, max same-set |wdiff|=%.3e, bad=%lld\n",
                ok ? "OK  " : "FAIL", tag, set_mismatch, maxw, bad);
    return ok;
}

int main(int argc, char **argv) {
    const std::string dir = argc > 1 ? argv[1] : "data/route";
    const long long n = 256; const int E = 384, k = 6;
    auto logits = loadf(dir + "/logits.bin", n * E);
    auto bias   = loadf(dir + "/bias.bin", E);
    bool ok = run<double>(dir, "f64", 1e-12, 1e-12, logits, bias, n, E, k);
    ok = run<float>(dir, "f32", 1e-5, 1e-5, logits, bias, n, E, k) && ok;
    if (ok) std::printf("FIXTURE_PASS route_gate\n");
    return ok ? 0 : 1;
}
