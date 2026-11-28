// bench_wo_mr: the engine's INK_WO_MR_PE and INK_WO_MR_TAIL (Engine::wo_mr; steps of 2-8 tokens of one sequence) on
// the card, bit for bit against the kernels they replace, then timed. Exit 1 on any DIFF.
//  A. producers: fz::attn_win_fused<3, 3, 2> / <3, 3, 1> and fz::attn_flash_sum (the default INK_SUM_U form and
//     <8, false>) given a PeOut write the PE parts xd::splite<MP> makes from their own stored rows: every halfword of
//     the 3 x 3072 x MP parts (rows ntok..MP-1 zero, poisoned guards untouched), steps of 1-8 rows, three positions; the
//     fp32 rows the same words as a launch without parts. attn_flash_sum also as two launches (the second's rows from
//     t0 > 0) and as 128-block chunks with the fold's state carried (the state-only chunks write no parts, the last all).
//  B. the product: xd::dgroupej<MP> with an EjTail (2304 x 3072 Q8E) against splite + dgroupej<MP> + fz::attn_tail for
//     2-8 tokens: attn_out, ffn_inp, the state buffer and every per-token state row as words (red zones, a block start,
//     no per-token rows), ob left alone, the four R10c IEEE witness channels (token 0) and crafted channels (signed
//     zeros, subnormal taps, states and residuals); dgroupej's stores with a default EjTail against the plain call.
//  C. speed: per step size, the four arms 0 = split + dgroupej + attn_tail (before), 1 = PE parts + dgroupej +
//     attn_tail, 2 = split + dgroupej with the tail, 3 = PE parts + dgroupej with the tail, each after its windowed
//     producer (attn_win_fused without / with parts) and before a 16 MB plain read (the follower), weights cycled over
//     10 copies, the arms in rotating order; wall clock per application, and with INK_PROF=1 each launch's event time
//     and the chain's span. Then the producers alone with and without parts.
//   bench_wo_mr <card>  (BENCH_ITERS: 200)
#include <cmath>
#include <cstring>
#include <random>
#include <string>
#include "../../src/xmx_esimd.hpp"
#include "../../src/attn_flash.hpp"
using namespace ink;
namespace {
template <class F> void with_mp(int n, F &&f) { // Engine::with_mp
    if (n == 1) f.template operator()<1>();
    else if (n == 2) f.template operator()<2>();
    else if (n <= 4) f.template operator()<4>();
    else f.template operator()<8>();
}
uint32_t fbits(float f) { uint32_t u; std::memcpy(&u, &f, 4); return u; }
} // namespace

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_wo_mr <card>\n"); return 2; }
    char *ep = nullptr;
    const long card_l = std::strtol(argv[1], &ep, 10);
    if (!argv[1][0] || *ep || card_l < 0 || card_l > 15) { std::fprintf(stderr, "bench_wo_mr: bad card '%s'\n", argv[1]); return 2; }
    int iters = 200;
    if (const char *iv = std::getenv("BENCH_ITERS")) {
        char *ie = nullptr;
        const long il = std::strtol(iv, &ie, 10);
        if (!iv[0] || *ie || il <= 0 || il > 100000) { std::fprintf(stderr, "bench_wo_mr: bad BENCH_ITERS '%s'\n", iv); return 2; }
        iters = (int)il;
    }
    const bool prof = std::getenv("INK_PROF") && std::atoi(std::getenv("INK_PROF"));
    try {
        Device d((int)card_l);
        constexpr int nh = 24, nkvh = 8, hd = 128, kd = nkvh * hd, cols = xd::WO_COLS, rows = 2304, NL = 10;
        static_assert(nh * hd == cols, "the attention output is the product's input");
        const int off = 2 * kd; // the tail's states at 2 kd, as the engine's
        std::mt19937 rng(20261128);
        std::normal_distribution<float> nd(0.0f, 1.0f);
        int ndiff = 0;
        // ---- the PE parts buffer (the engine's slot 3) with poisoned guards ----
        constexpr size_t PG = 64, PN = (size_t)3 * cols * 8; // halfwords
        uint16_t *Pe_raw = d.alloc<uint16_t>(PN + 2 * PG), *Pe = Pe_raw + PG, *Pr = d.alloc<uint16_t>(PN);
        auto pe_words = [&](const uint16_t *p, size_t n) { std::vector<uint16_t> v(n); d.get(v.data(), p, n); return v; };
        // the parts xd::splite<MP> makes from rows x (ntok of them) against the parts a producer wrote into Pe
        auto cmp_pe = [&](const char *what, const float *x, int nt) {
            const int mp = pe_mp(nt);
            with_mp(nt, [&]<int MP>() { xd::splite<MP>(d.q, x, cols, nt, cols, Pr); });
            d.q.wait_and_throw();
            const size_t n = (size_t)3 * cols * mp;
            const auto a = pe_words(Pr, n), raw = pe_words(Pe_raw, PN + 2 * PG);
            int bad = 0, pad = 0, guard = 0;
            for (size_t i = 0; i < n; ++i) bad += a[i] != raw[PG + i];
            for (int p = 0; p < 3; ++p)
                for (int t = nt; t < mp; ++t)
                    for (int k = 0; k < cols; ++k) pad += raw[PG + p * (size_t)cols * mp + pe_index(mp, t, k)] != 0;
            for (size_t i = 0; i < PG; ++i) guard += raw[i] != 0xa5a5u;
            for (size_t i = PG + n; i < PN + 2 * PG; ++i) guard += raw[i] != 0xa5a5u;
            std::printf("  %-40s %d token(s), MP %d: %s", what, nt, mp, bad + pad + guard ? "" : "same parts as splite\n");
            if (bad + pad + guard) std::printf("%d DIFF halfwords, %d nonzero padded, %d guards written\n", bad, pad, guard);
            ndiff += bad + pad + guard;
        };
        auto poison_pe = [&] { d.q.memset(Pe_raw, 0xa5, (PN + 2 * PG) * 2).wait_and_throw(); };
        auto cmp_f = [&](const char *what, const float *a, const float *b, size_t n) {
            std::vector<float> x(n), y(n);
            d.get(x.data(), a, n); d.get(y.data(), b, n);
            int bad = 0;
            for (size_t i = 0; i < n; ++i) bad += fbits(x[i]) != fbits(y[i]);
            if (bad) std::printf("  %-40s %d DIFF words\n", what, bad);
            ndiff += bad;
        };

        // ---- A. producers ----
        constexpr int ext = 1024, RW = 2048, km = RW - 1, win = 1024;
        const float kscale = 1.0f / std::sqrt((float)hd);
        std::vector<float> hq((size_t)8 * nh * hd), htb((size_t)8 * nh * ext), hsk((size_t)8 * nh), hgt((size_t)8 * nh * hd);
        for (auto &x : hq) x = nd(rng) * 0.3f;
        for (auto &x : htb) x = nd(rng) * 0.3f;
        for (auto &x : hsk) x = nd(rng) * 1.2f;
        for (auto &x : hgt) x = nd(rng) * 0.9f;
        std::vector<sycl::half> hk((size_t)RW * kd), hvt((size_t)kd * RW);
        for (auto &x : hk) x = (sycl::half)(nd(rng) * 0.3f);
        for (auto &x : hvt) x = (sycl::half)(nd(rng) * 0.9f);
        float *Qd = d.alloc<float>(hq.size()), *Tb = d.alloc<float>(htb.size()), *Sk = d.alloc<float>(hsk.size()), *Gt = d.alloc<float>(hgt.size());
        d.put(Qd, hq.data(), hq.size()); d.put(Tb, htb.data(), htb.size()); d.put(Sk, hsk.data(), hsk.size()); d.put(Gt, hgt.data(), hgt.size());
        sycl::half *Kx = d.alloc<sycl::half>(hk.size()), *Vx = d.alloc<sycl::half>(hvt.size());
        d.put(Kx, hk.data(), hk.size()); d.put(Vx, hvt.data(), hvt.size());
        float *o0 = d.alloc<float>((size_t)8 * cols), *o1 = d.alloc<float>((size_t)8 * cols);
        auto winf = [&](int pos, int nt, float *out, PeOut pe) {
            if (nt <= 2) return fz::attn_win_fused<3, 3, 2>(d.q, Qd, Kx, Tb, Vx, RW, Sk, Gt, pos, nt, nh, nkvh, hd, ext, win, kscale, km, out, 0, nullptr, true, pe);
            return fz::attn_win_fused<3, 3, 1>(d.q, Qd, Kx, Tb, Vx, RW, Sk, Gt, pos, nt, nh, nkvh, hd, ext, win, kscale, km, out, 0, nullptr, true, pe);
        };
        std::printf("A. producers: their PE parts against xd::splite of their stored rows\n");
        for (int pos : {5, 700, 3134})
            for (int nt = 1; nt <= 8; ++nt) {
                d.q.memset(o0, 0xff, (size_t)8 * cols * 4); d.q.memset(o1, 0xff, (size_t)8 * cols * 4);
                poison_pe();
                winf(pos, nt, o0, PeOut{});
                winf(pos, nt, o1, PeOut{Pe, pe_mp(nt), nt, 0, cols});
                d.q.wait_and_throw();
                cmp_f("attn_win_fused rows with / without parts", o0, o1, (size_t)nt * cols);
                const std::string w = "attn_win_fused, position " + std::to_string(pos);
                cmp_pe(w.c_str(), o1, nt);
            }
        { // attn_flash_sum: random block parts (the fold reads only part, pml, sink and gate)
            const int pos = 40000, nbmax = (pos + 7) / fz::PVB + 1, NB = 128;
            std::vector<float> hpart((size_t)8 * nh * nbmax * NB), hpml((size_t)8 * nh * nbmax * 2);
            for (auto &x : hpart) x = nd(rng);
            for (size_t i = 0; i < hpml.size(); i += 2) { hpml[i] = nd(rng) * 3.0f; hpml[i + 1] = 1.0f + std::fabs(nd(rng)) * 40.0f; }
            float *part = d.alloc<float>(hpart.size()), *pml = d.alloc<float>(hpml.size());
            float *cpart = d.alloc<float>((size_t)8 * nh * NB * NB), *cpml = d.alloc<float>((size_t)8 * nh * NB * 2);
            float *fst = d.alloc<float>((size_t)8 * nh * (NB + 2));
            d.put(part, hpart.data(), hpart.size()); d.put(pml, hpml.data(), hpml.size());
            for (int nt = 1; nt <= 8; ++nt) {
                const int nblk = (pos + nt - 1) / fz::PVB + 1;
                std::vector<float> lp((size_t)nt * nh * nblk * NB), lm((size_t)nt * nh * nblk * 2);
                for (size_t r = 0; r < (size_t)nt * nh; ++r) {
                    std::memcpy(&lp[r * nblk * NB], &hpart[r * nbmax * NB], sizeof(float) * nblk * NB);
                    std::memcpy(&lm[r * nblk * 2], &hpml[r * nbmax * 2], sizeof(float) * nblk * 2);
                }
                d.put(part, lp.data(), lp.size()); d.put(pml, lm.data(), lm.size());
                const PeOut whole{Pe, pe_mp(nt), nt, 0, cols};
                for (int form = 0; form < 2; ++form) {
                    d.q.memset(o0, 0xff, (size_t)8 * cols * 4); d.q.memset(o1, 0xff, (size_t)8 * cols * 4);
                    poison_pe();
                    if (form == 0) {
                        fz::attn_flash_sum(d.q, part, pml, nblk, pos, nt, nh, hd, Sk, Gt, o0);
                        fz::attn_flash_sum(d.q, part, pml, nblk, pos, nt, nh, hd, Sk, Gt, o1, 0, nullptr, 0, 0, nullptr, whole);
                    } else {
                        fz::attn_flash_sum_u<8, false>(d.q, part, pml, nblk, pos, nt, nh, hd, Sk, Gt, o0);
                        fz::attn_flash_sum_u<8, false>(d.q, part, pml, nblk, pos, nt, nh, hd, Sk, Gt, o1, 0, nullptr, 0, 0, nullptr, whole);
                    }
                    d.q.wait_and_throw();
                    cmp_f("attn_flash_sum rows with / without parts", o0, o1, (size_t)nt * cols);
                    cmp_pe(form == 0 ? "attn_flash_sum (INK_SUM_U form)" : "attn_flash_sum_u<8, false>", o1, nt);
                }
                if (nt >= 2) { // two launches: rows [0, a) and [a, nt), the second's parts at t0 = a
                    const int a = nt / 2;
                    d.q.memset(o0, 0xff, (size_t)8 * cols * 4);
                    d.q.memset(o1, 0xff, (size_t)8 * cols * 4);
                    poison_pe();
                    fz::attn_flash_sum(d.q, part, pml, nblk, pos, a, nh, hd, Sk, Gt, o0);
                    fz::attn_flash_sum(d.q, part + (size_t)a * nh * nblk * NB, pml + (size_t)a * nh * nblk * 2, nblk, pos + a, nt - a, nh, hd,
                                       Sk + (size_t)a * nh, Gt + (size_t)a * nh * hd, o0 + (size_t)a * cols);
                    fz::attn_flash_sum(d.q, part, pml, nblk, pos, a, nh, hd, Sk, Gt, o1, 0, nullptr, 0, 0, nullptr, whole);
                    PeOut second = whole;
                    second.t0 = a;
                    fz::attn_flash_sum(d.q, part + (size_t)a * nh * nblk * NB, pml + (size_t)a * nh * nblk * 2, nblk, pos + a, nt - a, nh, hd,
                                       Sk + (size_t)a * nh, Gt + (size_t)a * nh * hd, o1 + (size_t)a * cols, 0, nullptr, 0, 0, nullptr, second);
                    d.q.wait_and_throw();
                    cmp_f("attn_flash_sum in two launches", o0, o1, (size_t)nt * cols);
                    cmp_pe("attn_flash_sum in two launches (t0 > 0)", o1, nt);
                }
                { // 128-block chunks with the fold's state carried (the engine's chunked checks): parts from the last only
                    d.q.memset(o0, 0xff, (size_t)8 * cols * 4);
                    d.q.memset(o1, 0xff, (size_t)8 * cols * 4);
                    poison_pe();
                    int nch = 0;
                    for (int b0 = 0; b0 < nblk; b0 += NB, ++nch) {
                        const int nbc = std::min(NB, nblk - b0);
                        std::vector<float> cp((size_t)nt * nh * nbc * NB), cm((size_t)nt * nh * nbc * 2);
                        for (size_t r = 0; r < (size_t)nt * nh; ++r) {
                            std::memcpy(&cp[r * nbc * NB], &lp[(r * nblk + b0) * NB], sizeof(float) * nbc * NB);
                            std::memcpy(&cm[r * nbc * 2], &lm[(r * nblk + b0) * 2], sizeof(float) * nbc * 2);
                        }
                        d.put(cpart, cp.data(), cp.size()); d.put(cpml, cm.data(), cm.size());
                        const bool last = b0 + nbc >= nblk;
                        fz::attn_flash_sum(d.q, cpart, cpml, nbc, pos, nt, nh, hd, Sk, Gt, o1, b0, fst, b0 > 0, !last, nullptr, last ? whole : PeOut{});
                        if (!last) { // a state-only chunk: no parts yet
                            d.q.wait_and_throw();
                            const auto raw = pe_words(Pe_raw, PN + 2 * PG);
                            int w = 0;
                            for (uint16_t u : raw) w += u != 0xa5a5u;
                            if (w) { std::printf("  attn_flash_sum state-only chunk %d wrote %d halfwords\n", nch, w); ndiff += w; }
                        }
                    }
                    fz::attn_flash_sum(d.q, part, pml, nblk, pos, nt, nh, hd, Sk, Gt, o0);
                    d.q.wait_and_throw();
                    cmp_f("attn_flash_sum in chunks", o0, o1, (size_t)nt * cols);
                    const std::string w = "attn_flash_sum, " + std::to_string(nch) + " chunks";
                    cmp_pe(w.c_str(), o1, nt);
                }
            }
            d.release(part); d.release(pml); d.release(cpart); d.release(cpml); d.release(fst);
        }

        // ---- B. the product with the tail inside ----
        const size_t rb = (size_t)cols * 34 / 32, wn = rb * rows;
        std::vector<uint8_t *> Wq(NL);
        {
            std::vector<uint8_t> h(wn);
            uint8_t *src = d.alloc<uint8_t>(wn);
            for (int l = 0; l < NL; ++l) {
                for (int r = 0; r < rows; ++r) {
                    for (int c = 0; c < cols; ++c) h[(size_t)r * rb + c] = (l == 0 && r < 5) ? 0 : (uint8_t)(int8_t)((int)(rng() % 255) - 127);
                    for (int b = 0; b < cols / 32; ++b) {
                        const uint16_t s = (l == 0 && r < 5) ? 0 : (0x1800 + (uint16_t)(rng() % 0x400));
                        std::memcpy(&h[(size_t)r * rb + cols + 2 * b], &s, 2);
                    }
                }
                Wq[l] = d.alloc<uint8_t>(wn);
                d.put(src, h.data(), wn);
                xd::repack_q8e(d.q, src, rb, rows, cols, Wq[l]);
            }
            d.release(src);
        }
        const size_t sn = (size_t)(off + rows + 16) * 3, sst = sn + 7; // states with guard words; per-token rows sst apart
        std::vector<float> hx((size_t)8 * cols), hcv((size_t)rows * 4), hst(sn), hres((size_t)8 * rows);
        for (auto &v : hx) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
        for (auto &v : hcv) v = nd(rng) * 0.5f;
        for (auto &v : hst) v = nd(rng);
        for (auto &v : hres) v = nd(rng);
        const float sub = std::ldexp(1.0f, -140), nz = -0.0f;
        std::vector<char> craft(rows, 0);
        for (int r = 0; r < 5; ++r) { // weight copy 0, rows 0..4: zero codes and scales, so every token's total is +0
            craft[r] = 1;
            float *t = &hcv[(size_t)r * 4], *s = &hst[(size_t)(off + r) * 3];
            t[0] = t[1] = t[2] = t[3] = 0.0f; s[0] = s[1] = s[2] = 0.0f;
            for (int u = 0; u < 8; ++u) hres[(size_t)u * rows + r] = 0.0f;
        }
        hst[(size_t)(off + 0) * 3 + 0] = std::ldexp(1.0f, -140); hcv[0 * 4 + 0] = std::ldexp(1.0f, 120); // 0x34e4f92e
        hst[(size_t)(off + 1) * 3 + 0] = std::ldexp(1.0f, -140); hcv[1 * 4 + 0] = 1.0f;                  // 0x000000e5
        hst[(size_t)(off + 2) * 3 + 0] = -std::ldexp(1.0f, -149); hcv[2 * 4 + 0] = 1.0f;                 // 0x80000000
        hst[(size_t)(off + 3) * 3 + 0] = -1.0f; hcv[3 * 4 + 0] = 1.0f;                                    // fma 0xa7e4f92e
        hst[(size_t)(off + 3) * 3 + 1] = 1.0f + std::ldexp(1.0f, -23); hcv[3 * 4 + 1] = 1.0f - std::ldexp(1.0f, -23);
        // Codex 5th witness: direct residual-contraction test (exact ffn_inp 0x00000000 vs contracted VC mad 0xb1d83690)
        {
            uint32_t u_st = 0x3f800001u, u_res = 0xbee4f930u;
            std::memcpy(&hst[(size_t)(off + 4) * 3 + 0], &u_st, 4);
            hcv[4 * 4 + 0] = 1.0f;
            std::memcpy(&hres[0 * rows + 4], &u_res, 4);
        }
        int ncraft = 0;
        for (int c = 19; c < rows; c += 61, ++ncraft) {
            float *t = &hcv[(size_t)c * 4], *s = &hst[(size_t)(off + c) * 3];
            const int u = ncraft % 8;
            craft[c] = 1;
            switch (ncraft % 5) {
            case 0: t[0] = nz; t[1] = 0.0f; t[2] = nz; s[0] = 0.0f; s[1] = nz; s[2] = 1.0f; break;
            case 1: t[0] = sub; t[1] = -sub; t[2] = 0.25f * sub; s[0] = 1.0f; s[1] = 0.5f; s[2] = 3.0f; hres[(size_t)u * rows + c] = nz; break;
            case 2: s[0] = sub; s[1] = -sub; s[2] = 4.0f * sub; t[3] = 0.0f; hres[(size_t)u * rows + c] = sub; break;
            case 3: t[0] = t[1] = t[2] = t[3] = 0.0f; s[0] = s[1] = s[2] = nz; hres[(size_t)u * rows + c] = nz; break;
            default: t[3] = nz; s[0] = std::ldexp(1.0f, 100); s[1] = -std::ldexp(1.0f, 100); hres[(size_t)u * rows + c] = std::ldexp(1.0f, -126); break;
            }
        }
        float *x = d.alloc<float>(hx.size()), *cv = d.alloc<float>(hcv.size()), *st = d.alloc<float>(sn), *res = d.alloc<float>(hres.size());
        d.put(x, hx.data(), hx.size()); d.put(cv, hcv.data(), hcv.size()); d.put(st, hst.data(), sn); d.put(res, hres.data(), hres.size());
        constexpr size_t RZ = 16; // 64-byte red zones around ob / attn_out / ffn_inp
        const size_t on = (size_t)8 * rows;
        float *ob_raw[2], *ao_raw[2], *fi_raw[2], *ob[2], *ao[2], *fi[2], *so[2], *tk[2];
        for (int p = 0; p < 2; ++p) {
            ob_raw[p] = d.alloc<float>(on + 2 * RZ); ob[p] = ob_raw[p] + RZ;
            ao_raw[p] = d.alloc<float>(on + 2 * RZ); ao[p] = ao_raw[p] + RZ;
            fi_raw[p] = d.alloc<float>(on + 2 * RZ); fi[p] = fi_raw[p] + RZ;
            so[p] = d.alloc<float>(sn); tk[p] = d.alloc<float>((size_t)8 * sst);
        }
        float *ob1 = d.alloc<float>(on);
        const float scale = fz::conv_scale(false);
        auto jobs = [&](int l, float *y) { xd::EJobs jb{}; xd::ejob_add(jb, Wq[l % NL], rows, Pe, y, rows); return jb; };
        auto tail_of = [&](bool bs, bool keep, float *so_, float *tk_, float *fi_) {
            return xd::EjTail{cv, st + (size_t)3 * off, so_ + (size_t)3 * off, keep ? tk_ + (size_t)3 * off : nullptr, bs ? nullptr : res, fi_,
                              sst, scale};
        };
        auto words = [&](const float *p, size_t n) {
            std::vector<float> v(n);
            d.get(v.data(), p, n);
            std::vector<uint32_t> u(n);
            std::memcpy(u.data(), v.data(), n * 4);
            return u;
        };
        std::printf("B. dgroupej<MP> with the tail against splite + dgroupej<MP> + attn_tail (ntok 2..4; MR=8 keeps zero-spill standalone tail)\n");
        for (int nt = 2; nt <= 4; ++nt)
            for (const bool bs : {false, true})
                for (const bool keep : {true, false}) {
                    for (int p = 0; p < 2; ++p) {
                        d.q.memset(ob_raw[p], 0xff, (on + 2 * RZ) * 4); d.q.memset(ao_raw[p], 0xff, (on + 2 * RZ) * 4);
                        d.q.memset(fi_raw[p], 0xff, (on + 2 * RZ) * 4); d.q.memset(so[p], 0xff, sn * 4);
                        d.q.memset(tk[p], 0xff, (size_t)8 * sst * 4);
                    }
                    d.q.wait_and_throw();
                    with_mp(nt, [&]<int MP>() {
                        xd::splite<MP>(d.q, x, cols, nt, cols, Pe);
                        xd::dgroupej<MP>(d.q, jobs(0, ob[0]), cols, nt);
                        fz::attn_tail(d.q, ob[0], st, so[0], off, cv, scale, ao[0], bs ? nullptr : res, fi[0], rows, nt, keep ? tk[0] : nullptr, sst);
                        xd::dgroupej<MP>(d.q, jobs(0, ao[1]), cols, nt, tail_of(bs, keep, so[1], tk[1], fi[1]));
                        xd::dgroupej<MP>(d.q, jobs(0, ob1), cols, nt, xd::EjTail{}); // the stores with a default EjTail
                    });
                    d.q.wait_and_throw();
                    const auto O0 = words(ob_raw[0], on + 2 * RZ), O1 = words(ob_raw[1], on + 2 * RZ), Ob1 = words(ob1, on);
                    const auto A0 = words(ao_raw[0], on + 2 * RZ), A1 = words(ao_raw[1], on + 2 * RZ);
                    const auto F0 = words(fi_raw[0], on + 2 * RZ), F1 = words(fi_raw[1], on + 2 * RZ);
                    const auto S0 = words(so[0], sn), S1 = words(so[1], sn), T0 = words(tk[0], 8 * sst), T1 = words(tk[1], 8 * sst);
                    auto ndw = [](const std::vector<uint32_t> &a, const std::vector<uint32_t> &b) {
                        int n = 0;
                        for (size_t i = 0; i < a.size(); ++i) n += a[i] != b[i];
                        return n;
                    };
                    int ow = 0, sd = 0;
                    for (uint32_t u : O1) ow += u != 0xffffffffu; // the tail leaves ob alone
                    for (size_t i = 0; i < (size_t)nt * rows; ++i) sd += O0[RZ + i] != Ob1[i];
                    const int da = ndw(A0, A1), df = ndw(F0, F1), ds = ndw(S0, S1), dt = ndw(T0, T1);
                    int crafted = 0;
                    for (size_t i = 0; i < (size_t)nt * rows; ++i)
                        if (A0[RZ + i] != A1[RZ + i] && craft[i % rows]) ++crafted;
                    int ffw = 0;
                    if (bs) for (uint32_t u : F1) ffw += u != 0xffffffffu;
                    const int bad = da + df + ds + dt + ow + sd + ffw;
                    std::printf("  %d tokens, %-11s %-15s: %s", nt, bs ? "block start" : "residual", keep ? "per-token rows" : "no per-token",
                                bad ? "" : "attn_out, ffn_inp, states, per-token rows the same words; ob untouched; stores the same\n");
                    if (bad)
                        std::printf("DIFF attn_out %d (%d crafted), ffn_inp %d, st_out %d, per-token %d, ob written %d, stores %d, "
                                    "ffn_inp at a block start %d\n", da, crafted, df, ds, dt, ow, sd, ffw);
                    ndiff += bad;
                    if (!bs && keep) {
                        const uint32_t want[4] = {0x34e4f92eu, 0x000000e5u, 0x80000000u,
#ifdef INK_NO_FMA
                                                  0x00000000u
#else
                                                  0xa7e4f92eu
#endif
                        };
                        for (int r = 0; r < 4; ++r) {
                            const bool ok = A1[RZ + r] == want[r] && A0[RZ + r] == want[r];
                            if (nt == 2 || !ok)
                                std::printf("    witness channel %d, token 0: attn_tail 0x%08x, tail inside 0x%08x, IEEE 0x%08x %s\n", r, A0[RZ + r],
                                            A1[RZ + r], want[r], ok ? "EXACT+IEEE" : "DIFF");
                            ndiff += !ok;
                        }
                        {
                            const bool ok5 = A1[RZ + 4] == 0x3ee4f930u && A0[RZ + 4] == 0x3ee4f930u && F1[RZ + 4] == 0x00000000u && F0[RZ + 4] == 0x00000000u;
                            if (nt == 2 || !ok5)
                                std::printf("    witness channel 4 (VC residual mad guard): ao 0x%08x/0x%08x (want 0x3ee4f930), fi 0x%08x/0x%08x (want 0x00000000) %s\n",
                                            A0[RZ + 4], A1[RZ + 4], F0[RZ + 4], F1[RZ + 4], ok5 ? "EXACT+NO_MAD" : "DIFF");
                            ndiff += !ok5;
                        }
                    }
                }
        if (ndiff) { std::printf("bench_wo_mr: %d DIFF\n", ndiff); return 1; }

        // ---- C. speed ----
        const size_t FN = (size_t)4 << 20; // the follower: a 16 MB plain read (uint32 values)
        std::vector<uint32_t *> fb(4);
        for (auto &b : fb) { b = d.alloc<uint32_t>(FN); d.q.memset(b, 1, FN * 4).wait_and_throw(); }
        uint32_t *fo = d.alloc<uint32_t>(FN / 256);
        auto rd = [&](uint32_t *buf) {
            return d.q.parallel_for(sycl::nd_range<1>(sycl::range<1>(FN / 16), sycl::range<1>(256)), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                auto sg = it.get_sub_group();
                const size_t base = (it.get_group(0) * 256 + sg.get_group_id()[0] * 16) * 16;
                uint32_t acc = 0;
                for (int k = 0; k < 16; ++k) acc += buf[base + k * 16 + sg.get_local_id()[0]];
                acc = sycl::reduce_over_group(sg, acc, sycl::plus<uint32_t>());
                if (sg.leader()) fo[it.get_group(0) * 16 + sg.get_group_linear_id()] = acc;
            });
        };
        const char *arm[4] = {"0 split+dgroupej+attn_tail", "1 PE+dgroupej+attn_tail", "2 split+dgroupej-tail", "3 PE+dgroupej-tail"};
        // one application of arm a at step size nt on weight copy i: [producer] [split] product [attn_tail] [follower]
        auto chain = [&](int a, int nt, int i, std::vector<sycl::event> &ev) {
            const bool pe = a & 1, tl = a & 2;
            ev.clear();
            ev.push_back(winf(3134, nt, o1, pe ? PeOut{Pe, pe_mp(nt), nt, 0, cols} : PeOut{}));
            with_mp(nt, [&]<int MP>() {
                if (!pe) ev.push_back(xd::splite<MP>(d.q, o1, cols, nt, cols, Pe));
                if (tl) ev.push_back(xd::dgroupej<MP>(d.q, jobs(i, ao[1]), cols, nt, tail_of(false, true, so[1], tk[1], fi[1])));
                else {
                    ev.push_back(xd::dgroupej<MP>(d.q, jobs(i, ob[0]), cols, nt));
                    ev.push_back(fz::attn_tail(d.q, ob[0], st, so[0], off, cv, scale, ao[0], res, fi[0], rows, nt, tk[0], sst));
                }
            });
            ev.push_back(rd(fb[i % 4]));
        };
        auto timeit = [&](auto &&launch) {
            for (int i = 0; i < 5; ++i) launch(i);
            d.q.wait_and_throw();
            const double t0 = now_s();
            for (int i = 0; i < iters; ++i) launch(i + 1);
            d.q.wait_and_throw();
            return (now_s() - t0) / iters * 1e6;
        };
        namespace ep = sycl::info::event_profiling;
        auto us = [](const sycl::event &a, const sycl::event &b) {
            return (b.get_profiling_info<ep::command_end>() - a.get_profiling_info<ep::command_start>()) * 1e-3;
        };
        std::printf("C. per application (windowed producer at position 3134, product, tail, 16 MB follower), %d iterations\n", iters);
        for (int nt = 2; nt <= 8; ++nt) {
            std::vector<sycl::event> ev;
            const int narms = nt <= 4 ? 4 : 2; // MR=8 tests arms 0/1 (PE parts) without fused tail
            for (int rep = 0; rep < 2; ++rep)
                for (int k = 0; k < narms; ++k) {
                    const int a = (rep + k) % narms;
                    const double wall = timeit([&](int i) { chain(a, nt, i, ev); });
                    std::printf("  %d tokens, arm %-28s wall %8.2f us", nt, arm[a], wall);
                    if (prof) {
                        const int N = std::min(iters, 300);
                        std::vector<double> t(8, 0.0);
                        double span = 0.0, prod = 0.0;
                        size_t ne = 0;
                        for (int i = 0; i < N + 5; ++i) {
                            chain(a, nt, i, ev);
                            ev.back().wait_and_throw();
                            if (i < 5) continue;
                            ne = ev.size();
                            for (size_t e = 0; e < ne; ++e) t[e] += us(ev[e], ev[e]);
                            span += us(ev[0], ev[ne - 2]); // producer start to the last kernel before the follower
                            prod += us(ev[1], ev[ne - 2]); // after the producer
                        }
                        std::printf("  events:");
                        for (size_t e = 0; e < ne; ++e) std::printf(" %.2f", t[e] / N);
                        std::printf("  (follower last)  producer..tail span %.2f, after producer %.2f", span / N, prod / N);
                    }
                    std::printf("\n");
                }
        }
        std::printf("  producers alone, us per launch (wall clock):\n");
        {
            const int pos = 3134;
            for (int nt = 2; nt <= 8; ++nt) {
                const double u0 = timeit([&](int) { winf(pos, nt, o1, PeOut{}); });
                const double u1 = timeit([&](int) { winf(pos, nt, o1, PeOut{Pe, pe_mp(nt), nt, 0, cols}); });
                std::printf("    attn_win_fused %d tokens: %.2f without parts, %.2f with\n", nt, u0, u1);
            }
        }
        return 0;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "bench_wo_mr: %s\n", e.what());
        return 3;
    }
}
