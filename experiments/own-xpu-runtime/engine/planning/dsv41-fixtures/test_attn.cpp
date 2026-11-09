// Differential fixtures for the attention units (A1 sparse_attn core,
// A2 compressor pooling, A3 indexer, A4 window idxs).
// Dumps: data/attn/ (generator gen_attn_ref.py). A4 is bit-exact (ints);
// A1/A2/A3 tolerance-gated vs torch f64 anchor (1e-9) and f32 (5e-4);
// A3 topk/candidates are int/bool exact.
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include "attn_ops.hpp"

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
static std::vector<int32_t> loadi32(const std::string &p, size_t n) {
    std::vector<int32_t> v(n);
    FILE *f = std::fopen(p.c_str(), "rb");
    if (!f || std::fread(v.data(), 4, n, f) != n) { std::fprintf(stderr, "read %s\n", p.c_str()); std::exit(1); }
    std::fclose(f); return v;
}
template <typename A, typename B>
static double maxdiff(const A &a, const B &b) {
    double m = 0;
    for (size_t i = 0; i < a.size(); ++i) m = std::max(m, std::fabs((double)a[i] - (double)b[i]));
    return m;
}
static bool gate(const char *what, double err, double tol) {
    std::printf("%s %-34s max|diff| = %.3e (tol %.0e)\n", err <= tol ? "OK  " : "FAIL", what, err, tol);
    return err <= tol;
}

int main(int argc, char **argv) {
    const std::string dir = argc > 1 ? argv[1] : "data/attn";
    bool ok = true;

    // A1 sparse_attn core
    {
        int m = 6, h = 4, d = 32, n = 20, topk = 8;
        auto q = loadf(dir + "/attn_q.bin", m * h * d), kv = loadf(dir + "/attn_kv.bin", n * d);
        auto sink = loadf(dir + "/attn_sink.bin", h);
        auto idxs = loadi32(dir + "/attn_idxs.bin", m * topk);
        auto o64 = loadd(dir + "/attn_o_f64.bin", m * h * d);
        std::vector<double> qd(q.begin(), q.end()), kvd(kv.begin(), kv.end()), sd(sink.begin(), sink.end());
        std::vector<double> my64(m * h * d);
        dsv41::sparse_attn_core<double>(qd.data(), kvd.data(), sd.data(), idxs.data(), 1.0 / std::sqrt((double)d), my64.data(), m, h, d, topk);
        std::vector<float> my32(m * h * d);
        dsv41::sparse_attn_core<float>(q.data(), kv.data(), sink.data(), idxs.data(), 1.0f / std::sqrt((float)d), my32.data(), m, h, d, topk);
        ok &= gate("A1 sparse_attn f64", maxdiff(my64, o64), 1e-9);
        ok &= gate("A1 sparse_attn f32", maxdiff(my32, o64), 5e-4);
        // all-invalid row (t=3) must be exactly zero
        bool z = true;
        for (int hh = 0; hh < h; ++hh) for (int i = 0; i < d; ++i) z &= my32[(3 * h + hh) * d + i] == 0.f;
        std::printf("%s A1 all-invalid row -> zero output\n", z ? "OK  " : "FAIL");
        ok &= z;
    }

    // A2 compressor pooling
    {
        int hd = 48, ratio = 2, L = 8;
        auto kv = loadf(dir + "/comp_kv.bin", L * hd), sc = loadf(dir + "/comp_score.bin", L * hd);
        auto nw = loadf(dir + "/comp_nw.bin", hd);
        auto y64 = loadd(dir + "/comp_y_f64.bin", (L / ratio) * hd);
        std::vector<double> kvd(kv.begin(), kv.end()), sd(sc.begin(), sc.end()), nd(nw.begin(), nw.end());
        std::vector<double> my64((L / ratio) * hd);
        dsv41::compress_pool<double>(kvd.data(), sd.data(), nd.data(), my64.data(), L / ratio, ratio, hd, 1e-20);
        std::vector<float> my32((L / ratio) * hd);
        dsv41::compress_pool<float>(kv.data(), sc.data(), nw.data(), my32.data(), L / ratio, ratio, hd, 1e-20f);
        ok &= gate("A2 compressor f64", maxdiff(my64, y64), 1e-9);
        ok &= gate("A2 compressor f32", maxdiff(my32, y64), 5e-4);
    }

    // A3 indexer
    {
        int m = 5, H = 4, dk = 16, T = 40, k = 7;
        auto q3 = loadf(dir + "/idx_q.bin", m * H * dk), k3 = loadf(dir + "/idx_k.bin", T * dk);
        auto w3 = loadf(dir + "/idx_w.bin", m * H);
        auto score_ref = loadf(dir + "/idx_score.bin", m * T);
        auto topk_ref = loadi32(dir + "/idx_topk.bin", m * k);
        std::vector<int64_t> lens(m);
        {
            FILE *f = std::fopen((dir + "/idx_lens.bin").c_str(), "rb");
            if (!f || std::fread(lens.data(), 8, m, f) != (size_t)m) { std::fprintf(stderr, "read lens\n"); return 1; }
            std::fclose(f);
        }
        std::vector<uint8_t> cand_ref(m * T);
        FILE *f = std::fopen((dir + "/idx_cand.bin").c_str(), "rb");
        if (!f || std::fread(cand_ref.data(), 1, m * T, f) != (size_t)(m * T)) { std::fprintf(stderr, "read cand\n"); return 1; }
        std::fclose(f);
        std::vector<float> myscore(m * T);
        dsv41::indexer_score<float>(q3.data(), k3.data(), w3.data(), m, H, dk, T, lens.data(), myscore.data());
        ok &= gate("A3 index score f32", maxdiff(myscore, score_ref), 5e-4);
        std::vector<int32_t> mytopk(m * k);
        dsv41::indexer_topk(myscore.data(), m, T, k, lens.data(), 7, mytopk.data());
        // topk: compare as sorted sets (order after sort is positional)
        long long bad = 0;
        for (int t = 0; t < m; ++t)
            for (int i = 0; i < k; ++i)
                if (mytopk[t * k + i] != topk_ref[t * k + i]) ++bad;
        std::printf("%s A3 topk idxs exact (%lld mismatches)\n", bad ? "FAIL" : "OK  ", bad);
        ok &= bad == 0;
        std::vector<uint8_t> mycand(m * T);
        dsv41::select_candidate_blocks(myscore.data(), m, T, lens.data(), 3, 4, mycand.data());
        bad = 0;
        for (int i = 0; i < m * T; ++i) if ((mycand[i] != 0) != (cand_ref[i] != 0)) ++bad;
        std::printf("%s A3 candidate mask exact (%lld mismatches)\n", bad ? "FAIL" : "OK  ", bad);
        ok &= bad == 0;
    }

    // A4 window idxs (bit-exact)
    {
        struct { const char *tag; int win, sl, sp, cols; } cases[4] = {
            {"p_s3w5", 5, 3, 0, 3}, {"p_s10w4", 4, 10, 0, 4}, {"d_p7w4", 4, 1, 7, 4}, {"d_p3w4", 4, 1, 3, 4}};
        for (auto &c : cases) {
            auto ref = loadi32(dir + "/win_" + c.tag + ".bin", (size_t)c.sl * c.cols);
            std::vector<int32_t> mine(c.sl * c.cols);
            dsv41::window_topk_idxs(c.win, c.sl, c.sp, mine.data());
            long long bad = 0;
            for (size_t i = 0; i < ref.size(); ++i) if (mine[i] != ref[i]) ++bad;
            std::printf("%s A4 %s exact (%lld mismatches)\n", bad ? "FAIL" : "OK  ", c.tag, bad);
            ok &= bad == 0;
        }
    }

    if (ok) std::printf("FIXTURE_PASS attn_units\n");
    return ok ? 0 : 1;
}
