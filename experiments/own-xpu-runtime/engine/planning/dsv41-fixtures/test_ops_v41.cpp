// Ops gate: ops41::* (engine host kernels, ops_v41.hpp) vs the independent
// fixture implementations (already proven against official reference dumps)
// on identical inputs. Integer/index outputs must match exactly; float
// outputs within bf16/f32 rounding tolerances.
#include <algorithm>
#include <cstdio>
#include <random>
#include "attn_ops.hpp"
#include "hc_sinkhorn.hpp"
#include "ops_misc.hpp"
#include "route_gate.hpp"
#include "stage2/packet3/kernels/ops_v41.hpp"

static std::mt19937 rng(42);
static float frand() { return std::uniform_real_distribution<float>(-2, 2)(rng); }

static int fails = 0;
static void report(const char *name, double maxdiff, double tol) {
    std::printf("%-14s maxdiff=%.3e %s\n", name, maxdiff,
                maxdiff <= tol ? "OK" : "FAIL");
    if (maxdiff > tol) fails++;
}

int main() {
    // sparse_attn: 4 heads x 16 dim, 12 slots, mixed -1 idxs
    {
        const int H = 4, D = 16, S = 12, K = 8;
        std::vector<uint16_t> q(H * D), kv(S * D);
        std::vector<float> qf(H * D), kvf(S * D), sink(H);
        for (int i = 0; i < H * D; ++i) qf[i] = frand() * 0.2f, q[i] = ops41::bf16b(qf[i]);
        for (int i = 0; i < S * D; ++i) kvf[i] = frand() * 0.2f, kv[i] = ops41::bf16b(kvf[i]);
        for (auto &v : sink) v = frand();
        int32_t idxs[K] = {0, 3, -1, 5, 7, -1, 11, 2};
        std::vector<float> o1(H * D), o2(H * D);
        ops41::sparse_attn(q.data(), kv.data(), sink.data(), idxs, K, H, D, o1.data());
        dsv41::sparse_attn_core(qf.data(), kvf.data(), sink.data(), idxs,
                                1.0f / std::sqrt(float(D)), o2.data(), 1, H, D, K);
        // ops41 reads bf16; recompute fixture on bf16-rounded inputs
        for (int i = 0; i < H * D; ++i) qf[i] = ops41::bf16(q[i]);
        for (int i = 0; i < S * D; ++i) kvf[i] = ops41::bf16(kv[i]);
        dsv41::sparse_attn_core(qf.data(), kvf.data(), sink.data(), idxs,
                                1.0f / std::sqrt(float(D)), o2.data(), 1, H, D, K);
        double md = 0;
        for (int i = 0; i < H * D; ++i) md = std::max(md, (double)std::fabs(o1[i] - o2[i]));
        report("sparse_attn", md, 2e-6);
    }
    // route: 384 experts top-6
    {
        const int E = 384;
        std::vector<float> logits(E), bias(E);
        for (auto &v : logits) v = frand() * 4;
        for (auto &v : bias) v = frand() * 0.5f;
        uint32_t ids1[6]; int32_t ids2[6];
        float p1[6], p2[6];
        ops41::route(logits.data(), bias.data(), E, 6, ids1, p1);
        dsv41::route_gate(logits.data(), bias.data(), 1, E, 6, 1.5f, ids2, p2);
        int exact = 1;
        double md = 0;
        for (int i = 0; i < 6; ++i) {
            exact &= (int32_t)ids1[i] == ids2[i];
            md = std::max(md, (double)std::fabs(p1[i] - p2[i]));
        }
        std::printf("%-14s idx %s, wdiff=%.3e\n", "route41", exact ? "EXACT" : "MISMATCH", md);
        if (!exact || md > 1e-5) fails++;
    }
    // swiglu_clamp bit-exact
    {
        const int n = 4096;
        std::vector<uint16_t> g(n), u(n), o1(n), o2b(n);
        std::vector<float> gf(n), uf(n), o2(n);
        for (int i = 0; i < n; ++i) {
            gf[i] = frand() * 12; uf[i] = frand() * 12;
            g[i] = ops41::bf16b(gf[i]); u[i] = ops41::bf16b(uf[i]);
            gf[i] = ops41::bf16(g[i]); uf[i] = ops41::bf16(u[i]);
        }
        ops41::swiglu_clamp(g.data(), u.data(), o1.data(), n);
        dsv41::swiglu_clamp(gf.data(), uf.data(), o2.data(), n, 10.0f);
        double md = 0;
        for (int i = 0; i < n; ++i) // impl output is bf16-rounded; round ref too
            md = std::max(md, (double)std::fabs(ops41::bf16(o1[i]) - ops41::bf16(ops41::bf16b(o2[i]))));
        report("swiglu_clamp", md, 1e-6);
    }
    // engram_gate
    {
        const int h = 64;
        std::vector<uint16_t> s(4 * h), kv(5 * h); std::vector<float> gw(4 * h);
        std::vector<float> sf(4 * h), kf(4 * h), qwf(4 * h), kwf(4 * h), vf(h), out(4 * h);
        for (int i = 0; i < 4 * h; ++i) { sf[i] = frand() * 0.1f; s[i] = ops41::bf16b(sf[i]); sf[i] = ops41::bf16(s[i]); }
        for (int i = 0; i < 5 * h; ++i) kv[i] = ops41::bf16b(frand() * 0.1f);
        for (int i = 0; i < 4 * h; ++i) {
            kf[i] = ops41::bf16(kv[i]);
            float qw = frand() * 0.5f, kw = frand() * 0.5f;
            qwf[i] = qw; kwf[i] = kw;
            gw[i] = qw * kw; // premultiplied store, F32 like the GGUF tensor
        }
        for (int i = 0; i < h; ++i) vf[i] = ops41::bf16(kv[4 * h + i]);
        uint8_t mask = 1;
        ops41::engram_gate(s.data(), kv.data(), gw.data(), h);
        dsv41::engram_gate(sf.data(), kf.data(), qwf.data(), kwf.data(), vf.data(),
                           &mask, out.data(), 1, 4, h, 1e-20f, 1e-6f);
        double md = 0;
        for (int i = 0; i < 4 * h; ++i)
            md = std::max(md, (double)std::fabs(ops41::bf16(s[i]) - out[i]));
        report("engram_gate", md, 2e-3); // bf16 io + premultiplied weight
    }
    // hc_mix (projection + sinkhorn) vs fixture sinkhorn over same mixes
    {
        const int h = 32;
        std::vector<uint16_t> s(4 * h);
        std::vector<float> fn(24 * 4 * h), scale(3), base(24), xf(4 * h);
        for (int i = 0; i < 4 * h; ++i) { s[i] = ops41::bf16b(frand() * 0.1f); xf[i] = ops41::bf16(s[i]); }
        for (auto &v : fn) v = frand() * 0.05f;
        for (auto &v : scale) v = 0.5f + frand() * 0.2f;
        for (auto &v : base) v = frand() * 0.3f;
        float pre1[4], post1[4], comb1[16];
        ops41::hc_mix(s.data(), fn.data(), scale.data(), base.data(), h, pre1, post1, comb1);
        // fixture path: same projection in f64, then f64 sinkhorn
        double sq = 0;
        for (float v : xf) sq += double(v) * v;
        double rsqrt = 1.0 / std::sqrt(sq / (4 * h) + 1e-20);
        double m[24];
        for (int j = 0; j < 24; ++j) {
            double acc = 0;
            for (int i = 0; i < 4 * h; ++i) acc += double(fn[j * 4 * h + i]) * xf[i];
            m[j] = acc * rsqrt;
        }
        double pre2[4], post2[4], comb2[16], sc[3], bs[24];
        for (int i = 0; i < 3; ++i) sc[i] = scale[i];
        for (int i = 0; i < 24; ++i) bs[i] = base[i];
        dsv41::hc_split_sinkhorn(m, sc, bs, 1, 20, 1e-6, pre2, post2, comb2);
        double md = 0;
        for (int i = 0; i < 4; ++i) md = std::max(md, (double)std::fabs(pre1[i] - pre2[i]));
        for (int i = 0; i < 4; ++i) md = std::max(md, (double)std::fabs(post1[i] - post2[i]));
        for (int i = 0; i < 16; ++i) md = std::max(md, (double)std::fabs(comb1[i] - comb2[i]));
        report("hc_mix41", md, 1e-4);
    }
    // window_append decode idxs
    {
        const int win = 8, d = 4;
        std::vector<uint16_t> ring(win * d, 0), kv(d);
        for (auto &v : kv) v = ops41::bf16b(1.0f);
        int32_t idxs[8];
        ops41::window_append(ring.data(), kv.data(), win, d, 3, idxs);
        int32_t ref[8];
        dsv41::window_topk_idxs(win, 1, 3, ref); // decode branch: [win] row
        int exact = 1;
        for (int i = 0; i < win; ++i) exact &= idxs[i] == ref[i];
        std::printf("%-14s idxs %s\n", "window_append", exact ? "EXACT" : "MISMATCH");
        if (!exact) fails++;
    }
    // rope_rotate vs fixture (in-place tail vs full-row variant)
    {
        const int rows = 3, d = 16, rd = 8;
        std::vector<uint16_t> x(rows * d);
        std::vector<float> xf(rows * rd), o2(rows * rd), cosb(rows * rd / 2), sinb(rows * rd / 2);
        for (int i = 0; i < rows * d; ++i) x[i] = ops41::bf16b(frand() * 0.5f);
        for (int r = 0; r < rows; ++r)
            for (int i = 0; i < rd; ++i) xf[r * rd + i] = ops41::bf16(x[r * d + (d - rd) + i]);
        for (int i = 0; i < rows * rd / 2; ++i) { cosb[i] = std::cos(0.1f * (i % (rd / 2))); sinb[i] = std::sin(0.1f * (i % (rd / 2))); }
        auto x_copy = x;
        ops41::rope_rotate(x_copy.data(), rows, d, rd, cosb.data(), sinb.data(), false);
        dsv41::rope_rotate(xf.data(), cosb.data(), sinb.data(), o2.data(), rows, 1, rd, false);
        double md = 0;
        for (int r = 0; r < rows; ++r)
            for (int i = 0; i < rd; ++i)
                md = std::max(md, (double)std::fabs(ops41::bf16(x_copy[r * d + (d - rd) + i]) - ops41::bf16(ops41::bf16b(o2[r * rd + i]))));
        report("rope_yarn", md, 1e-6); // both sides bf16-rounded
    }
    // hc_pre / hc_post / hc_mean / prob_scale / moe_combine / gemv_grouped
    // vs direct f64 semantic definitions
    {
        const int h = 64;
        std::vector<uint16_t> s(4 * h), x(h);
        for (int i = 0; i < 4 * h; ++i) s[i] = ops41::bf16b(frand() * 0.1f);
        for (auto &v : x) v = ops41::bf16b(frand() * 0.1f);
        float mix[4] = {0.4f, 0.3f, 0.2f, 0.1f}, post[4] = {1.0f, 0.8f, 0.6f, 0.4f};
        float comb[16]; for (auto &v : comb) v = frand() * 0.1f;
        std::vector<uint16_t> pre_o(h);
        ops41::hc_pre(s.data(), mix, pre_o.data(), h);
        double md = 0;
        for (int i = 0; i < h; ++i) {
            double ref = 0;
            for (int j = 0; j < 4; ++j) ref += double(mix[j]) * ops41::bf16(s[j * h + i]);
            md = std::max(md, (double)std::fabs(ops41::bf16(pre_o[i]) - float(ref)));
        }
        report("hc_pre", md, 2e-3);
        auto s2 = s;
        ops41::hc_post(s2.data(), x.data(), post, comb, h);
        md = 0;
        for (int j = 0; j < 4; ++j)
            for (int i = 0; i < h; ++i) {
                double ref = double(post[j]) * ops41::bf16(x[i]);
                for (int k = 0; k < 4; ++k) ref += double(comb[j * 4 + k]) * ops41::bf16(s[k * h + i]);
                md = std::max(md, (double)std::fabs(ops41::bf16(s2[j * h + i]) - float(ref)));
            }
        report("hc_post", md, 2e-3);
        std::vector<uint16_t> mean_o(h);
        ops41::hc_mean(s.data(), mean_o.data(), h);
        md = 0;
        for (int i = 0; i < h; ++i) {
            double ref = 0;
            for (int j = 0; j < 4; ++j) ref += ops41::bf16(s[j * h + i]);
            md = std::max(md, (double)std::fabs(ops41::bf16(mean_o[i]) - float(ref / 4)));
        }
        report("hc_mean", md, 2e-3);
        // gemv_grouped: 2 groups x 3 rows x 4 cols
        {
            std::vector<uint16_t> o(2 * 4), w(2 * 3 * 4), oo(2 * 3);
            for (auto &v : o) v = ops41::bf16b(frand());
            for (auto &v : w) v = ops41::bf16b(frand());
            ops41::gemv_grouped(o.data(), w.data(), 2, 3, 4, oo.data());
            double md2 = 0;
            for (int g = 0; g < 2; ++g)
                for (int r = 0; r < 3; ++r) {
                    double ref = 0;
                    for (int i = 0; i < 4; ++i)
                        ref += double(ops41::bf16(w[(g * 3 + r) * 4 + i])) * ops41::bf16(o[g * 4 + i]);
                    md2 = std::max(md2, (double)std::fabs(ops41::bf16(oo[g * 3 + r]) - ops41::bf16(ops41::bf16b(float(ref)))));
                }
            report("gemv_grouped", md2, 1e-6);
        }
    }
    if (!fails) std::printf("FIXTURE_PASS ops_v41\n");
    return fails ? 1 : 0;
}
