// bench_wo: the one-token attention output (2304 rows x 3072 inputs, Q8E) and its convolution tail, the three engine
// paths of INK_WO_TAIL: 0 = the general ESIMD launch (xd::dgroupej, one job) + fz::attn_tail, 1 = xd::wo_q8<false> +
// attn_tail, 2 = xd::wo_q8<true> (the tail inside, ob not written). Bits (exit 1 on a DIFF): wo's output (1 against 0),
// attn_out, ffn_inp and the whole state buffer (1 and 2 against 0), with the residual and at a block start (ffn_inp
// left as it was), on random values and on crafted channels (signed zeros, subnormal taps, states and residuals); the
// state buffer's words outside the tail's 2304 x 3 must stay as they were. Path 0's tail is also recomputed on the host
// in IEEE single precision (formats.hpp's mac, the build's arithmetic), for reading a DIFF. Built with INK_CFLAGS=
// -DINK_NO_FMA it checks path 2 in that arithmetic (the engine runs 2 as 1 there until it has). Speed: 10 weight copies
// (75 MB, more than the cache holds), each path back to back, in rotating order; INK_PROF=1 also gives each launch's
// own time, the pair's span and a plain 16 MB read timed right after each path (does a path slow the kernel after it?).
//   bench_wo <card>  (BENCH_ITERS: 300)
#include <cmath>
#include <cstring>
#include <random>
#include <string>
#include "../../src/xmx_esimd.hpp"
#include "../../src/fused.hpp"
using namespace ink;
int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_wo <card>\n"); return 2; }
    char *ep = nullptr;
    const long card_l = std::strtol(argv[1], &ep, 10);
    if (!argv[1][0] || *ep || card_l < 0 || card_l > 15) { std::fprintf(stderr, "bench_wo: bad card '%s'\n", argv[1]); return 2; }
    Device d((int)card_l);
    const int cols = xd::WO_COLS, rows = 2304, NL = 10, off = 2 * 1024; // the tail's states at 2 kd (8 KV heads x 128)
    int iters = 300;
    if (const char *iv = std::getenv("BENCH_ITERS")) {
        char *ie = nullptr;
        const long il = std::strtol(iv, &ie, 10);
        if (!iv[0] || *ie || il <= 0 || il > 100000) { std::fprintf(stderr, "bench_wo: bad BENCH_ITERS '%s'\n", iv); return 2; }
        iters = (int)il;
    }
    std::mt19937 rng(11);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    const size_t rb = (size_t)cols * 34 / 32, wn = rb * rows;
    std::vector<uint8_t *> Wq(NL);
    {
        std::vector<uint8_t> h(wn);
        uint8_t *src = d.alloc<uint8_t>(wn);
        for (int l = 0; l < NL; ++l) {
            for (int r = 0; r < rows; ++r) {
                for (int c = 0; c < cols; ++c)
                    h[(size_t)r * rb + c] = (l == 0 && r < 4) ? 0 : (uint8_t)(int8_t)((int)(rng() % 255) - 127);
                for (int b = 0; b < cols / 32; ++b) {
                    const uint16_t s = (l == 0 && r < 4) ? 0 : (0x1800 + (uint16_t)(rng() % 0x400));
                    std::memcpy(&h[(size_t)r * rb + cols + 2 * b], &s, 2);
                }
            }
            Wq[l] = d.alloc<uint8_t>(wn);
            d.put(src, h.data(), wn);
            xd::repack_q8e(d.q, src, rb, rows, cols, Wq[l]);
        }
    }
    const size_t sn = (size_t)(off + rows + 16) * 3; // states: the tail's 2304 x 3 at 3 off, guard words before and after
    std::vector<float> hx(cols), hcv((size_t)rows * 4), hst(sn), hres(rows);
    for (auto &v : hx) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
    for (auto &v : hcv) v = nd(rng) * 0.5f;
    for (auto &v : hst) v = nd(rng);
    for (auto &v : hres) v = nd(rng);
    // crafted channels: where a flushed subnormal, lost zero sign, or split vs FMA would show
    const float sub = std::ldexp(1.0f, -140), nz = -0.0f;
    std::vector<char> craft(rows, 0);
    // Rows 0..3 have zero Q8 weights on copy 0 so tot == +0.0f (Codex witness rows):
    for (int r = 0; r < 4; ++r) {
        craft[r] = 1;
        float *t = &hcv[(size_t)r * 4], *s = &hst[(size_t)(off + r) * 3];
        t[0] = t[1] = t[2] = t[3] = 0.0f; s[0] = s[1] = s[2] = 0.0f; hres[r] = 0.0f;
    }
    // Row 0: subnormal input * normal = 2^-140 * 2^120 = 2^-20 -> expected attn_out 0x34e4f92e
    hst[(size_t)(off + 0) * 3 + 0] = std::ldexp(1.0f, -140); hcv[0 * 4 + 0] = std::ldexp(1.0f, 120);
    // Row 1: nonzero subnormal output = 2^-140 * 1 -> expected attn_out 0x000000e5
    hst[(size_t)(off + 1) * 3 + 0] = std::ldexp(1.0f, -140); hcv[1 * 4 + 0] = 1.0f;
    // Row 2: negative underflow to signed zero = -2^-149 * 1 -> expected attn_out 0x80000000
    hst[(size_t)(off + 2) * 3 + 0] = -std::ldexp(1.0f, -149); hcv[2 * 4 + 0] = 1.0f;
    // Row 3: FMA vs split (-1 + (1+2^-23)*(1-2^-23)) -> FMA 0xa7e4f92e, split 0x00000000
    hst[(size_t)(off + 3) * 3 + 0] = -1.0f; hcv[3 * 4 + 0] = 1.0f;
    hst[(size_t)(off + 3) * 3 + 1] = 1.0f + std::ldexp(1.0f, -23); hcv[3 * 4 + 1] = 1.0f - std::ldexp(1.0f, -23);
    int ncraft = 0;
    for (int c = 19; c < rows; c += 61, ++ncraft) {
        float *t = &hcv[(size_t)c * 4], *s = &hst[(size_t)(off + c) * 3];
        craft[c] = 1;
        switch (ncraft % 5) {
        case 0: t[0] = nz; t[1] = 0.0f; t[2] = nz; s[0] = 0.0f; s[1] = nz; s[2] = 1.0f; break;
        case 1: t[0] = sub; t[1] = -sub; t[2] = 0.25f * sub; s[0] = 1.0f; s[1] = 0.5f; s[2] = 3.0f; hres[c] = nz; break;
        case 2: s[0] = sub; s[1] = -sub; s[2] = 4.0f * sub; t[3] = 0.0f; hres[c] = sub; break;
        case 3: t[0] = t[1] = t[2] = t[3] = 0.0f; s[0] = s[1] = s[2] = nz; hres[c] = nz; break;
        default: t[3] = nz; s[0] = std::ldexp(1.0f, 100); s[1] = -std::ldexp(1.0f, 100); hres[c] = std::ldexp(1.0f, -126); break;
        }
    }
    float *x = d.alloc<float>(cols), *cv = d.alloc<float>((size_t)rows * 4), *st = d.alloc<float>(sn), *res = d.alloc<float>(rows);
    d.put(x, hx.data(), hx.size());
    d.put(cv, hcv.data(), hcv.size());
    d.put(st, hst.data(), hst.size());
    d.put(res, hres.data(), hres.size());
    constexpr size_t RZ = 16; // 64-byte aligned red zones before and after ob/ao/fi
    float *ob_raw[3], *ao_raw[3], *fi_raw[3], *ob[3], *ao[3], *fi[3], *so[3];
    for (int p = 0; p < 3; ++p) {
        ob_raw[p] = d.alloc<float>(rows + 2 * RZ); ob[p] = ob_raw[p] + RZ;
        ao_raw[p] = d.alloc<float>(rows + 2 * RZ); ao[p] = ao_raw[p] + RZ;
        fi_raw[p] = d.alloc<float>(rows + 2 * RZ); fi[p] = fi_raw[p] + RZ;
        so[p] = d.alloc<float>(sn);
    }
    const float scale = fz::conv_scale(false);
    struct Ev { sycl::event wo, tail; bool two = false; };
    // path p on weight copy l; bs: a block start (no residual)
    auto run = [&](int p, int l, bool bs) {
        const uint8_t *w = Wq[l % NL];
        const float *r = bs ? nullptr : res;
        Ev e;
        if (p == 2) {
            e.wo = xd::wo_q8<true>(d.q, w, rows, x, ao[2], cv, st + (size_t)3 * off, so[2] + (size_t)3 * off, r, fi[2], scale);
            return e;
        }
        if (p == 1) e.wo = xd::wo_q8<false>(d.q, w, rows, x, ob[1]);
        else {
            xd::EJobs jb;
            xd::ejob_add(jb, w, rows, (const uint16_t *)x, ob[0], rows);
            e.wo = xd::dgroupej<1, 128, true, true>(d.q, jb, cols, 1);
        }
        e.tail = fz::attn_tail(d.q, ob[p], st, so[p], off, cv, scale, ao[p], r, fi[p], rows, 1);
        e.two = true;
        return e;
    };
    auto words = [&](const float *p, size_t n) {
        std::vector<float> v(n);
        d.get(v.data(), p, n);
        std::vector<uint32_t> u(n);
        std::memcpy(u.data(), v.data(), n * 4);
        return u;
    };
    auto fbits = [](float f) { uint32_t u; std::memcpy(&u, &f, 4); return u; };
    int ndiff = 0;
    for (const bool bs : {false, true}) {
        for (int p = 0; p < 3; ++p) {
            d.q.memset(ob_raw[p], 0xff, (rows + 2 * RZ) * 4);
            d.q.memset(ao_raw[p], 0xff, (rows + 2 * RZ) * 4);
            d.q.memset(fi_raw[p], 0xff, (rows + 2 * RZ) * 4);
            d.q.memset(so[p], 0xff, sn * 4);
        }
        d.q.wait_and_throw();
        for (int p = 0; p < 3; ++p) run(p, 0, bs);
        d.q.wait_and_throw();
        std::vector<uint32_t> O[3], A[3], F[3], S[3];
        int rz_bad = 0;
        for (int p = 0; p < 3; ++p) {
            auto check_rz = [&](const float *raw, std::vector<uint32_t> &dst) {
                auto full = words(raw, rows + 2 * RZ);
                for (size_t i = 0; i < RZ; ++i) rz_bad += (full[i] != 0xffffffffu) + (full[RZ + rows + i] != 0xffffffffu);
                dst.assign(full.begin() + RZ, full.begin() + RZ + rows);
            };
            check_rz(ob_raw[p], O[p]);
            check_rz(ao_raw[p], A[p]);
            check_rz(fi_raw[p], F[p]);
            S[p] = words(so[p], sn);
        }
        d.q.wait_and_throw();
        if (rz_bad) { std::printf("  %-12s RED ZONE CORRUPTED: %d words\n", bs ? "block start" : "residual", rz_bad); ndiff += rz_bad; }
        // Verify active reference outputs are finite & overwritten, and saved states equal {old_s1, old_s2, ref_ob}
        int nonfin = 0, st_bad = 0;
        for (int c = 0; c < rows; ++c) {
            float o0, a0, f0;
            std::memcpy(&o0, &O[0][c], 4); std::memcpy(&a0, &A[0][c], 4); std::memcpy(&f0, &F[0][c], 4);
            if (!std::isfinite(o0) || !std::isfinite(a0) || (!bs && !std::isfinite(f0))) ++nonfin;
            const size_t si = (size_t)(off + c) * 3;
            if (S[0][si + 0] != fbits(hst[si + 1]) || S[0][si + 1] != fbits(hst[si + 2]) || S[0][si + 2] != O[0][c]) ++st_bad;
        }
        if (nonfin || st_bad) {
            std::printf("  %-12s REF CONTRACT FAIL: nonfinite=%d state_mismatch=%d\n", bs ? "block start" : "residual", nonfin, st_bad);
            ndiff += nonfin + st_bad;
        }
        // Print Codex witness rows 0..3
        const uint32_t exp_w[4] = {0x34e4f92eu, 0x000000e5u, 0x80000000u,
#ifdef INK_NO_FMA
                                   0x00000000u
#else
                                   0xa7e4f92eu
#endif
        };
        if (!bs) {
            for (int r = 0; r < 4; ++r)
                std::printf("  witness row %d: ob0=0x%08x ref=0x%08x path2=0x%08x expected_ieee=0x%08x (%s)\n",
                            r, O[0][r], A[0][r], A[2][r], exp_w[r],
                            (A[0][r] == A[2][r] && A[2][r] == exp_w[r]) ? "EXACT+IEEE"
                            : (A[0][r] == A[2][r] ? "MATCH_REF_DIFF_IEEE" : "DIFF"));
        }
        // n words of a and b that differ, and how many of them belong to crafted channels (ch: word -> channel or -1)
        auto cmp = [&](const char *what, const std::vector<uint32_t> &a, const std::vector<uint32_t> &b, auto ch) {
            int n = 0, nc = 0;
            for (size_t i = 0; i < a.size(); ++i)
                if (a[i] != b[i]) { ++n; const int c = ch(i); nc += c >= 0 && craft[c]; }
            std::printf("  %-12s %-44s %s", bs ? "block start" : "residual", what, n ? "" : "same bits\n");
            if (n) std::printf("%d DIFF (%d on crafted channels)\n", n, nc);
            ndiff += n;
        };
        auto row = [](size_t i) { return (int)i; };
        auto stc = [&](size_t i) { const long c = (long)(i / 3) - off; return c >= 0 && c < rows ? (int)c : -1; };
        cmp("wo output, wo_q8 vs dgroupej", O[1], O[0], row);
        int ow = 0;
        for (uint32_t u : O[2]) ow += u != 0xffffffffu;
        std::printf("  %-12s %-44s %s\n", bs ? "block start" : "residual", "wo_q8<true> leaves ob alone", ow ? "NO" : "yes");
        ndiff += ow;
        for (int p = 1; p < 3; ++p) {
            const std::string pn = p == 1 ? "path 1" : "path 2";
            cmp((pn + " attn_out vs path 0").c_str(), A[p], A[0], row);
            cmp((pn + " ffn_inp vs path 0").c_str(), F[p], F[0], row);
            cmp((pn + " state buffer vs path 0").c_str(), S[p], S[0], stc);
        }
        int untouched = 0, fin = 0; // path 0's own contract: guard states untouched; at a block start ffn_inp untouched
        for (size_t i = 0; i < sn; ++i) if (stc(i) < 0) untouched += S[0][i] != 0xffffffffu;
        if (bs) for (uint32_t u : F[0]) fin += u != 0xffffffffu;
        std::printf("  %-12s path 0 writes outside the tail's states: %d, ffn_inp at a block start: %d\n", bs ? "block start" : "residual",
                    untouched, fin);
        ndiff += untouched + fin;
        // path 0's tail again on the host, IEEE single precision, from its own wo output (reading a DIFF: which side
        // follows IEEE on the crafted channels)
        int h0 = 0, h2 = 0;
        for (int c = 0; c < rows; ++c) {
            float xo; std::memcpy(&xo, &O[0][c], 4);
            const float *t = &hcv[(size_t)c * 4], *s = &hst[(size_t)(off + c) * 3];
            float sm = 0.0f;
            sm = mac(sm, s[0], t[0]);
            sm = mac(sm, s[1], t[1]);
            sm = mac(sm, s[2], t[2]);
            sm = mac(sm, xo, t[3]);
            const float o = (xo + sm) * scale;
            h0 += fbits(o) != A[0][c]; h2 += fbits(o) != A[2][c];
            if (!bs) { const float f = hres[c] + o; h0 += fbits(f) != F[0][c]; h2 += fbits(f) != F[2][c]; }
        }
        std::printf("  %-12s host IEEE tail: path 0 differs in %d words, path 2 in %d (information)\n", bs ? "block start" : "residual", h0, h2);
    }
    if (ndiff) { std::printf("bench_wo: %d DIFF\n", ndiff); return 1; }
    auto timeit = [&](auto &&launch) {
        for (int i = 0; i < 5; ++i) launch(i);
        d.q.wait_and_throw();
        const double t0 = now_s();
        for (int i = 0; i < iters; ++i) launch(i + 1);
        d.q.wait_and_throw();
        return (now_s() - t0) / iters * 1e6;
    };
    const char *nm[3] = {"0  dgroupej + attn_tail", "1  wo_q8 + attn_tail", "2  wo_q8 with the tail"};
    std::printf("back to back, %d iterations, us per application (wall clock):\n", iters);
    for (int rep = 0; rep < 3; ++rep)
        for (int k = 0; k < 3; ++k) {
            const int p = (rep + k) % 3;
            std::printf("  order %d  path %-24s %.2f\n", rep, nm[p], timeit([&](int i) { run(p, i, false); }));
        }
    for (int rep = 0; rep < 2; ++rep) {
        const double ug = timeit([&](int i) {
            xd::EJobs jb;
            xd::ejob_add(jb, Wq[i % NL], rows, (const uint16_t *)x, ob[0], rows);
            xd::dgroupej<1, 128, true, true>(d.q, jb, cols, 1);
        });
        const double us = timeit([&](int i) { xd::wo_q8<false>(d.q, Wq[i % NL], rows, x, ob[1]); });
        const double ut = timeit([&](int i) { fz::attn_tail(d.q, ob[1], st, so[1], off, cv, scale, ao[1], res, fi[1], rows, 1); (void)i; });
        std::printf("  alone: dgroupej %.2f us, wo_q8 %.2f us, attn_tail %.2f us\n", ug, us, ut);
    }
    if (std::getenv("INK_PROF") && std::atoi(std::getenv("INK_PROF"))) {
        const size_t FN = (size_t)4 << 20; // a 16 MB plain read (uint32 values) right after each path
        std::vector<uint32_t *> fb(4);
        for (auto &b : fb) { b = d.alloc<uint32_t>(FN); d.q.memset(b, 1, FN * 4).wait_and_throw(); }
        const size_t nsg_tot = (FN / 16) / 16; // 16,384 subgroups across all 16 MiB
        uint32_t *fo = d.alloc<uint32_t>(nsg_tot);
        auto rd = [&](uint32_t *buf, size_t n) {
            return d.q.parallel_for(sycl::nd_range<1>(sycl::range<1>(n / 16), sycl::range<1>(256)), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                auto sg = it.get_sub_group();
                const size_t base = (it.get_group(0) * 256 + sg.get_group_id()[0] * 16) * 16;
                uint32_t acc = 0;
                for (int k = 0; k < 16; ++k) acc += buf[base + k * 16 + sg.get_local_id()[0]];
                acc = sycl::reduce_over_group(sg, acc, sycl::plus<uint32_t>());
                if (sg.leader()) fo[it.get_group(0) * 16 + sg.get_group_linear_id()] = acc;
            });
        };
        // Verify all 16,384 subgroup checksums outside the timed region (all 16 MiB truly live!)
        d.q.memset(fo, 0, nsg_tot * 4).wait_and_throw();
        rd(fb[0], FN).wait_and_throw();
        std::vector<uint32_t> hfo(nsg_tot);
        d.get(hfo.data(), fo, nsg_tot);
        d.q.wait_and_throw();
        const uint32_t exp_sum = 0x01010101u * 256u;
        int fbad = 0;
        for (uint32_t v : hfo) fbad += (v != exp_sum);
        if (fbad) { std::printf("bench_wo: follower 16 MiB checksum FAIL (%d / %zu)\n", fbad, nsg_tot); return 1; }
        namespace ep = sycl::info::event_profiling;
        auto us = [](sycl::event &a, sycl::event &b) { return (b.get_profiling_info<ep::command_end>() - a.get_profiling_info<ep::command_start>()) * 1e-3; };
        std::printf("INK_PROF: us per launch (event start to end), the pair's first start to last end, then a 16 MB read (16384/16384 checksums OK):\n");
        for (int rep = 0; rep < 2; ++rep)
            for (int k = 0; k < 3; ++k) {
                const int p = (rep + k) % 3, N = 300;
                double tw = 0, tt = 0, tp = 0, tf = 0;
                for (int i = 0; i < N + 5; ++i) {
                    Ev e = run(p, i, false);
                    sycl::event ef = rd(fb[i % 4], FN);
                    ef.wait_and_throw();
                    if (i < 5) continue;
                    tw += us(e.wo, e.wo);
                    if (e.two) { tt += us(e.tail, e.tail); tp += us(e.wo, e.tail); }
                    else tp += us(e.wo, e.wo);
                    tf += us(ef, ef);
                }
                std::printf("  path %-24s wo %.2f  tail %.2f  pair %.2f  then 16 MB read %.2f\n", nm[p], tw / N, tt / N, tp / N, tf / N);
            }
    }
    return 0;
}
