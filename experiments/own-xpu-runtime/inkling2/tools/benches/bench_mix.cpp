// bench_mix: fz::mix_fused (the depth mix and its norm; engine labels mix_norm, mix_out, mix_save) with INK_MIX_FAST
// off and on in one binary (mix_fused's fast argument 0 / 1), and the two-launch form the table form must equal
// (fz::mix_scores + ops::mix_out / fz::mix_out_norm, the engine's INK_MIX_TAB=0 path).
// Bits (exit 1 on a DIFF): every output word of fast 1 against fast 0 and of fast 0 against the two-launch form (out,
// y, the lane-order copy yl, the three bf16 parts yp; red zones around each must stay as filled), the saved-state table
// (role B in the mix launch, and alone as mix_save, against each other and against mix_scores' scale and scores) and
// the warm sink, for 1-12 states (the fast path takes 1-5, the others its fallback), 1-3 queries, 1-4 tokens at first
// row t0 0 or 2, rows of 2304 values (the engine's), 3072, 2300, 2048, 1152, 512 and 2302 (no 4-wide reads), row
// stride n or n + 4, a state or the output 4 bytes off 16-byte alignment, with and without warm work-groups, on random
// values with crafted channels (signed zeros, subnormal states and products, zero and subnormal norm weights).
// Speed (n 2304, the engine's one-token mixes, then 2 and 4 tokens): each launch's own time (event start to end) with
// the states cold (a 64 MB read before every launch) and then the 21 MB read after it (the next matrix; its first 3 MB
// are what the warm work-groups read), fast 0 and 1 in alternating order; then back to back (wall clock). Each shape's
// w is its count in a one-token plain step (96 mixes); the step lines are the sums of w x time.
//   bench_mix <card>  (BENCH_ITERS: 200; BENCH_MIX_SWEEP=0: only the engine shapes' bits before the speed part)
#include <cmath>
#include <cstring>
#include <map>
#include <random>
#include <string>
#include "../../src/fused.hpp"
using namespace ink;

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_mix <card>\n"); return 2; }
    char *ep = nullptr;
    const long card_l = std::strtol(argv[1], &ep, 10);
    if (!argv[1][0] || *ep || card_l < 0 || card_l > 15) { std::fprintf(stderr, "bench_mix: bad card '%s'\n", argv[1]); return 2; }
    int iters = 200;
    if (const char *iv = std::getenv("BENCH_ITERS")) {
        char *ie = nullptr;
        const long il = std::strtol(iv, &ie, 10);
        if (!iv[0] || *ie || il <= 0 || il > 100000) { std::fprintf(stderr, "bench_mix: bad BENCH_ITERS '%s'\n", iv); return 2; }
        iters = (int)il;
    }
    const bool sweep = live_env_flag("BENCH_MIX_SWEEP", true);
    Device d((int)card_l);
    // every launch on one in-order queue with timestamps (d.q has them only under INK_PROF)
    sycl::queue pq(d.ctx, d.dev, sycl::property_list{sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    using fz::MIX_MAX;
    constexpr int NMAX = 3072, T = 8, NQA = 56, NSLOT = MIX_MAX + 2, MK = MIX_MAX + 1, RZ = 16;
    constexpr size_t LDMAX = NMAX + 4, STN = (size_t)T * LDMAX + 8; // floats per state buffer (+8: a copy 1 float in)
    const float eps = 1e-6f;
    std::mt19937 rng(23);
    std::normal_distribution<float> nd(0.0f, 1.0f);

    // ---- buffers -------------------------------------------------------------------------------------------------
    std::vector<float *> stb(MIX_MAX);
    for (auto &p : stb) p = d.alloc<float>(STN);
    float *qrows = d.alloc<float>((size_t)NQA * NMAX), *wts = d.alloc<float>((size_t)3 * NMAX);
    uint64_t *qall = d.alloc<uint64_t>(NQA);
    float *tinv = d.alloc<float>((size_t)NSLOT * T), *tsc = d.alloc<float>((size_t)NSLOT * T * NQA);
    float *tinv0 = d.alloc<float>((size_t)NSLOT * T), *tsc0 = d.alloc<float>((size_t)NSLOT * T * NQA);
    float *rinv = d.alloc<float>((size_t)T * MIX_MAX), *rsc = d.alloc<float>((size_t)T * 3 * MIX_MAX);
    const size_t XLF = xlane_floats(NMAX);
    const size_t OUTN = (size_t)3 * T * NMAX + 2 * RZ + 4, YN = (size_t)T * NMAX + 2 * RZ + 4, YLN = (size_t)T * XLF + 2 * RZ,
                 YPN = (size_t)3 * NMAX + 2 * RZ * 2;
    float *outr = d.alloc<float>(OUTN), *yr[3], *ylr[3];
    uint16_t *ypr[3];
    for (int k = 0; k < 3; ++k) { yr[k] = d.alloc<float>(YN); ylr[k] = d.alloc<float>(YLN); ypr[k] = d.alloc<uint16_t>(YPN); }
    uint32_t *sink = d.alloc<uint32_t>(4);
    // the next matrix (21 MB, the attention inputs' size) and the cold-state flush (64 MB), read by rd()
    const size_t FOLN = (size_t)21 << 18, FLN = (size_t)64 << 18; // uint32 words
    uint32_t *fol = d.alloc<uint32_t>(FOLN), *fl = d.alloc<uint32_t>(FLN), *rdo = d.alloc<uint32_t>(FLN / 256);
    pq.memset(fol, 1, FOLN * 4);
    pq.memset(fl, 1, FLN * 4);
    pq.wait_and_throw();
    auto rd = [&](const uint32_t *buf, size_t n) { // n / 256 sub-groups of 16 lanes x 16 words
        return pq.parallel_for(sycl::nd_range<1>(sycl::range<1>(n / 16), sycl::range<1>(256)), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
            auto sg = it.get_sub_group();
            const size_t s = it.get_group(0) * 16 + sg.get_group_linear_id(), base = s * 256;
            uint32_t acc = 0;
            for (int k = 0; k < 16; ++k) acc += buf[base + k * 16 + sg.get_local_linear_id()];
            acc = sycl::reduce_over_group(sg, acc, sycl::plus<uint32_t>());
            if (sg.leader()) rdo[s] = acc;
        });
    };
    fz::WarmSet wset;
    wset.add((const uint8_t *)fol, (size_t)3 << 20);

    // ---- inputs for (n, ld) --------------------------------------------------------------------------------------
    int cur_n = -1, cur_ld = -1;
    std::vector<std::vector<float>> hs(MIX_MAX);
    std::vector<float> hq, hw;
    auto load = [&](int n, int ld) {
        if (n == cur_n && ld == cur_ld) return;
        cur_n = n; cur_ld = ld;
        const float sub = std::ldexp(1.0f, -140), dn = std::ldexp(1.0f, -149), tn = 1.5f * std::ldexp(1.0f, -126);
        for (int s = 0; s < MIX_MAX; ++s) {
            hs[s].assign(STN, 0.0f);
            const float sc = 0.25f + 0.5f * (float)(s % 5); // states of different sizes: varied scales and scores
            for (int r = 0; r < T; ++r)
                for (int c = 0; c < n; ++c) {
                    float v = nd(rng) * sc;
                    switch (c % 97) { // crafted channels
                    case 5: v = -0.0f; break;                                   // every state -0
                    case 17: v = (s + r) % 2 ? -0.0f : 0.0f; break;             // +0 / -0
                    case 29: v = (s % 3 == 0 ? sub : -sub) * (float)(1 + r); break; // subnormal states
                    case 41: v = (s % 2 ? tn : -tn); break;                      // products x * scale subnormal
                    case 53: v = s % 4 == 0 ? dn : (s % 4 == 1 ? -dn : 0.0f); break; // the smallest subnormal
                    default: break;
                    }
                    hs[s][(size_t)r * ld + c] = v; // (past n, up to ld: zero)
                }
        }
        // (a state 4 bytes in, st_mis, reads these words one float later: other values, the same in every arm)
        for (int s = 0; s < MIX_MAX; ++s) pq.memcpy(stb[s], hs[s].data(), STN * 4);
        hq.resize((size_t)NQA * n);
        for (auto &v : hq) v = nd(rng); // scores of order 1 after the 1/sqrt(n) scale: softmax weights far from even
        hw.resize((size_t)3 * n);
        for (size_t i = 0; i < hw.size(); ++i) hw[i] = i % 89 == 7 ? -0.0f : (i % 89 == 13 ? std::ldexp(1.0f, -130) : 1.0f + 0.1f * nd(rng));
        pq.memcpy(qrows, hq.data(), hq.size() * 4);
        pq.memcpy(wts, hw.data(), hw.size() * 4);
        std::vector<uint64_t> ha(NQA);
        for (int k = 0; k < NQA; ++k) ha[k] = (uint64_t)(uintptr_t)(qrows + (size_t)k * n);
        pq.memcpy(qall, ha.data(), NQA * 8);
        pq.wait_and_throw();
    };

    // ---- one mix -------------------------------------------------------------------------------------------------
    enum Mode { M_OUT, M_OUT_NULL, M_NY, M_NFFN, M_NALL, M_NNOW, M_COUNT };
    static const char *mname[M_COUNT] = {"out", "no output", "norm y", "norm yl+yp", "norm all+out", "norm no weight"};
    struct Cfg { int n, ld, ns, nq, ntok, t0, mk, qi0, mode; bool warm, st_mis, out_mis; };
    auto stp = [&](const Cfg &c, int s) -> const float * { return stb[s] + ((c.st_mis && s == 0) ? 1 : 0); };
    auto has_out = [](const Cfg &c) { return c.mode == M_OUT || c.mode == M_NALL; };
    auto outp = [&](const Cfg &c) -> float * { return has_out(c) ? outr + RZ + (c.out_mis ? 1 : 0) : nullptr; };
    auto normed = [](const Cfg &c) { return c.mode >= M_NY; };
    auto normout = [&](const Cfg &c) {
        fz::NormOut no{};
        for (int j = 0; j < c.nq; ++j) {
            no.w[j] = c.mode == M_NNOW ? nullptr : wts + (size_t)j * c.n;
            if (c.mode != M_NFFN) no.y[j] = yr[j] + RZ;
            if (c.mode == M_NFFN || c.mode == M_NALL) {
                no.yl[j] = ylr[j] + RZ;
                if (c.ntok == 1) no.yp[j] = ypr[j] + 2 * RZ; // (the parts have no row offset: one row only)
            }
        }
        return no;
    };
    auto mixf = [&](const Cfg &c) {
        fz::MixF a{};
        const int nb = c.ns - 1;
        for (int s = 0; s < nb; ++s) { a.st[s] = stp(c, s); a.slot[s] = s + 1; }
        a.st[nb] = stp(c, nb);
        a.ns = c.ns;
        a.query = qrows + (size_t)c.qi0 * c.n; a.nq = c.nq; a.qi0 = c.qi0;
        a.tinv = tinv; a.tsc = tsc; a.T = T; a.NQA = NQA; a.mk_slot = c.mk; a.qall = qall; a.t0 = c.t0;
        return a;
    };
    auto warm_of = [&](const Cfg &c) { return c.warm ? fz::Warm{wset, 12, sink} : fz::Warm{}; };
    auto launch = [&](const Cfg &c, int fast) {
        const fz::MixF a = mixf(c);
        const fz::NormOut no = normout(c);
        return fz::mix_fused(pq, a, c.ld, outp(c), normed(c) ? &no : nullptr, eps, c.n, c.ntok, warm_of(c), fast);
    };
    // the blocks' table rows t0 .. t0 + ntok - 1 (role B alone, as the engine's save_state), slot s + 1 for block s
    auto save_blocks = [&](const Cfg &c, int fast) {
        for (int s = 0; s + 1 < c.ns; ++s) {
            fz::MixF b{};
            b.st[0] = stp(c, s); b.ns = 1; b.nq = 0;
            b.tinv = tinv; b.tsc = tsc; b.T = T; b.NQA = NQA; b.mk_slot = s + 1; b.qall = qall; b.t0 = c.t0;
            fz::mix_fused(pq, b, c.ld, nullptr, nullptr, eps, c.n, c.ntok, fz::Warm{}, fast);
        }
    };
    auto fill = [&](void *p, size_t bytes) { pq.memset(p, 0xff, bytes); };
    auto reset_out = [&]() {
        fill(outr, OUTN * 4);
        for (int k = 0; k < 3; ++k) { fill(yr[k], YN * 4); fill(ylr[k], YLN * 4); fill(ypr[k], YPN * 2); }
        pq.memset(sink, 0, 16);
    };
    auto words = [&](const void *p, size_t bytes) {
        std::vector<uint32_t> v((bytes + 3) / 4, 0);
        pq.memcpy(v.data(), p, bytes).wait_and_throw();
        return v;
    };
    struct Snap { std::vector<uint32_t> out, y[3], yl[3], yp[3], tinv, tsc, sink; };
    auto snap = [&](const Cfg &) {
        Snap s;
        s.out = words(outr, OUTN * 4);
        for (int k = 0; k < 3; ++k) {
            s.y[k] = words(yr[k], YN * 4);
            s.yl[k] = words(ylr[k], YLN * 4);
            s.yp[k] = words(ypr[k], YPN * 2);
        }
        s.tinv = words(tinv, (size_t)NSLOT * T * 4);
        s.tsc = words(tsc, (size_t)NSLOT * T * NQA * 4);
        s.sink = words(sink, 16);
        return s;
    };
    // the two-launch form: mix_scores, then mix_out (no norm) or mix_out_norm, states from row t0 (MixArgs)
    auto reference = [&](const Cfg &c) {
        ops::MixArgs m{};
        for (int s = 0; s < c.ns; ++s) m.st[s] = stp(c, s) + (size_t)c.t0 * c.ld;
        m.ns = c.ns;
        const float *query = qrows + (size_t)c.qi0 * c.n;
        fz::mix_scores(pq, m, c.ld, query, c.nq, rinv, rsc, c.n, c.ntok);
        if (normed(c)) {
            const fz::NormOut no = normout(c);
            fz::mix_out_norm(pq, m, c.ld, c.nq, rinv, rsc, has_out(c) ? outp(c) : nullptr, no, eps, c.n, c.ntok);
        } else if (c.mode == M_OUT) {
            ops::mix_out(pq, m, c.ld, c.nq, rinv, rsc, outp(c), c.n, c.ntok);
        }
    };

    // ---- bits ----------------------------------------------------------------------------------------------------
    long ndiff = 0, nrz = 0, ncfg = 0, nfast = 0, ndirect = 0, cov[3] = {0, 0, 0}; // cov: +0, -0, subnormal words written
    auto covw = [&](const std::vector<uint32_t> &v) {
        for (uint32_t u : v) {
            if (u == 0xffffffffu) continue;
            if (u == 0u) ++cov[0];
            else if (u == 0x80000000u) ++cov[1];
            else if ((u & 0x7f800000u) == 0) ++cov[2];
        }
    };
    std::map<std::string, long> per;
    auto cmpv = [&](const std::string &what, const std::vector<uint32_t> &a, const std::vector<uint32_t> &b) {
        long n = 0;
        for (size_t i = 0; i < a.size() && i < b.size(); ++i) n += a[i] != b[i];
        if (a.size() != b.size()) n += 1;
        if (n) per[what] += n;
        return n;
    };
    // red zones: the words before and after the part a launch may write must keep the fill
    auto rz = [&](const std::vector<uint32_t> &v, size_t lo, size_t used) {
        long n = 0;
        for (size_t i = 0; i < v.size(); ++i)
            if ((i < lo || i >= lo + used) && v[i] != 0xffffffffu) ++n;
        return n;
    };
    auto check = [&](const Cfg &c) {
        load(c.n, c.ld);
        ++ncfg;
        const bool v4 = c.n % 4 == 0 && c.ld % 4 == 0 && !c.st_mis;
        const bool fv = v4 && c.ns <= fz::MIX_LIVE;
        nfast += fv;
        ndirect += fv && c.mode == M_OUT && !c.out_mis;
        // the blocks' table, by role B alone with fast 0, then with fast 1 (the two must be the same words)
        fill(tinv, (size_t)NSLOT * T * 4); fill(tsc, (size_t)NSLOT * T * NQA * 4);
        save_blocks(c, 1);
        pq.wait_and_throw();
        const std::vector<uint32_t> ti1 = words(tinv, (size_t)NSLOT * T * 4), ts1 = words(tsc, (size_t)NSLOT * T * NQA * 4);
        fill(tinv, (size_t)NSLOT * T * 4); fill(tsc, (size_t)NSLOT * T * NQA * 4);
        save_blocks(c, 0);
        pq.memcpy(tinv0, tinv, (size_t)NSLOT * T * 4);
        pq.memcpy(tsc0, tsc, (size_t)NSLOT * T * NQA * 4);
        pq.wait_and_throw();
        long n = cmpv("mix_save table, fast 1 vs 0", ti1, words(tinv, (size_t)NSLOT * T * 4)) +
                 cmpv("mix_save table, fast 1 vs 0", ts1, words(tsc, (size_t)NSLOT * T * NQA * 4));
        Snap S[3]; // 0: fast 0, 1: fast 1, 2: the two-launch form
        for (int arm = 0; arm < 3; ++arm) {
            reset_out();
            pq.memcpy(tinv, tinv0, (size_t)NSLOT * T * 4);
            pq.memcpy(tsc, tsc0, (size_t)NSLOT * T * NQA * 4);
            if (arm < 2) launch(c, arm);
            else reference(c);
            pq.wait_and_throw();
            S[arm] = snap(c);
        }
        covw(S[1].out);
        for (int j = 0; j < 3; ++j) covw(S[1].y[j]);
        const std::string k = std::string(mname[c.mode]);
        n += cmpv("fast 1 vs 0: out (" + k + ")", S[1].out, S[0].out);
        for (int j = 0; j < 3; ++j) {
            n += cmpv("fast 1 vs 0: y (" + k + ")", S[1].y[j], S[0].y[j]);
            n += cmpv("fast 1 vs 0: yl (" + k + ")", S[1].yl[j], S[0].yl[j]);
            n += cmpv("fast 1 vs 0: yp (" + k + ")", S[1].yp[j], S[0].yp[j]);
        }
        n += cmpv("fast 1 vs 0: table after the mix", S[1].tinv, S[0].tinv) + cmpv("fast 1 vs 0: table after the mix", S[1].tsc, S[0].tsc);
        n += cmpv("fast 1 vs 0: warm sink", S[1].sink, S[0].sink);
        // fast 0 against the two-launch form (its outputs; the reference writes no table)
        n += cmpv("fast 0 vs two-launch: out (" + k + ")", S[0].out, S[2].out);
        for (int j = 0; j < 3; ++j) {
            n += cmpv("fast 0 vs two-launch: y (" + k + ")", S[0].y[j], S[2].y[j]);
            n += cmpv("fast 0 vs two-launch: yl (" + k + ")", S[0].yl[j], S[2].yl[j]);
            n += cmpv("fast 0 vs two-launch: yp (" + k + ")", S[0].yp[j], S[2].yp[j]);
        }
        // role B in the mix launch (mk): the current state's scale and its scores with this call's queries, against
        // mix_scores' (rinv, rsc still hold the reference's)
        if (c.mk >= 0) {
            const std::vector<uint32_t> ri = words(rinv, (size_t)T * MIX_MAX * 4), rs = words(rsc, (size_t)T * 3 * MIX_MAX * 4);
            long nb = 0;
            for (int t = 0; t < c.ntok; ++t) {
                const size_t row = (size_t)c.mk * T + c.t0 + t;
                nb += S[0].tinv[row] != ri[(size_t)t * MIX_MAX + c.ns - 1];
                for (int j = 0; j < c.nq; ++j)
                    nb += S[0].tsc[row * NQA + c.qi0 + j] != rs[((size_t)t * c.nq + j) * MIX_MAX + c.ns - 1];
            }
            if (nb) per["role B in the launch vs mix_scores"] += nb;
            n += nb;
        }
        // red zones and untouched rows (every arm)
        const size_t on = (size_t)c.nq * c.ntok * c.n, o0 = RZ + (c.out_mis ? 1 : 0);
        long r = 0;
        for (int arm = 0; arm < 3; ++arm) {
            r += rz(S[arm].out, o0, has_out(c) ? on : 0);
            for (int j = 0; j < 3; ++j) {
                const fz::NormOut no = normout(c);
                const bool live = normed(c) && j < c.nq;
                r += rz(S[arm].y[j], RZ, live && no.y[j] ? (size_t)c.ntok * c.n : 0);
                r += rz(S[arm].yl[j], RZ, live && no.yl[j] ? (size_t)c.ntok * xlane_floats(c.n) : 0);
                std::vector<uint32_t> h(S[arm].yp[j].size() * 2); // the parts as 16-bit words
                for (size_t i = 0; i < S[arm].yp[j].size(); ++i) { h[2 * i] = S[arm].yp[j][i] & 0xffff; h[2 * i + 1] = S[arm].yp[j][i] >> 16; }
                long rp = 0;
                const size_t lo = 2 * RZ, used = live && no.yp[j] ? (size_t)3 * c.n : 0;
                for (size_t i = 0; i < h.size(); ++i) if ((i < lo || i >= lo + used) && h[i] != 0xffffu) ++rp;
                r += rp;
            }
        }
        if (r) per["red zone or untouched row written"] += r;
        nrz += r;
        ndiff += n;
        if (n || r)
            std::printf("  DIFF n %d ld %d ns %d nq %d ntok %d t0 %d mk %d qi0 %d %s%s%s%s: %ld words, %ld red-zone\n", c.n, c.ld,
                        c.ns, c.nq, c.ntok, c.t0, c.mk, c.qi0, mname[c.mode], c.warm ? " warm" : "", c.st_mis ? " st+4B" : "",
                        c.out_mis ? " out+4B" : "", n, r);
    };
    // the engine's shapes: n 2304, one token, 1-12 states, 1 or 3 queries, every output mode, warm and a saved state
    // on and off
    int rot = 0;
    for (int ns = 1; ns <= MIX_MAX; ++ns)
        for (int nq : {1, 3})
            for (int mode = 0; mode < M_COUNT; ++mode)
                for (int wm = 0; wm < 2; ++wm)
                    for (int mk : {-1, MK}) {
                        const int qi0 = (rot++ * 7) % (NQA - nq + 1);
                        check(Cfg{2304, 2304, ns, nq, 1, 0, mk, qi0, mode, wm == 1, false, false});
                    }
    std::printf("engine shapes (n 2304, 1 token, 1-12 states): %ld configurations, %ld on the short path (%ld direct), %s\n",
                ncfg, nfast, ndirect, ndiff + nrz ? "DIFF" : "same bits");
    if (sweep) {
        const long c0 = ncfg;
        // other row lengths and strides, 1-4 tokens, t0, alignment (each combination rotated over the states)
        const int ns_list[] = {3072, 2300, 2048, 1152, 512, 2302};
        for (int n : ns_list)
            for (int ldx = 0; ldx < 2; ++ldx)
                for (int ns = 1; ns <= MIX_MAX; ++ns) {
                    const int k = rot++;
                    static const int tk[3] = {1, 2, 4};
                    const int nq = 1 + k % 3, ntok = tk[k % 3 == 0 ? 0 : (k % 2 ? 1 : 2)], t0 = (k / 3) % 2 ? 2 : 0;
                    const int mode = k % M_COUNT, qi0 = (k * 11) % (NQA - nq + 1);
                    check(Cfg{n, n + 4 * ldx, ns, nq, ntok, t0, k % 4 == 1 ? MK : -1, qi0, mode, k % 5 == 2, k % 7 == 3, k % 6 == 4});
                }
        // n 2304 with 2 and 4 tokens (DSpark checks), every mode, t0 0 and 2
        for (int ntok : {2, 4})
            for (int t0 : {0, 2})
                for (int ns = 1; ns <= MIX_MAX; ++ns) {
                    const int k = rot++;
                    check(Cfg{2304, 2304, ns, 1 + k % 3, ntok, t0, k % 3 == 1 ? MK : -1, (k * 5) % 50, k % M_COUNT, false, false, false});
                }
        // Codex named cases: misaligned plain out, ns=5 direct multi-query multi-token with t0>0, and widths 5-8
        check(Cfg{2304, 2304, 4, 1, 1, 0, -1, 0, M_OUT, false, false, true});
        check(Cfg{2304, 2304, 5, 3, 4, 2, -1, 3, M_OUT, false, false, false});
        check(Cfg{2304, 2304, 4, 3, 6, 2, -1, 5, M_OUT, false, false, false});
        check(Cfg{2304, 2304, 5, 1, 8, 0, -1, 1, M_OUT, false, false, false});
        check(Cfg{2304, 2306, 4, 1, 1, 0, -1, 0, M_OUT, false, false, false});
        std::printf("shape sweep: %ld configurations, %s\n", ncfg - c0, ndiff + nrz ? "DIFF" : "same bits");
    }
    for (auto &[what, n] : per) std::printf("  %-48s %ld words differ\n", what.c_str(), n);
    if (ndiff || nrz) { std::printf("bench_mix: %ld DIFF words, %ld red-zone words, in %ld configurations\n", ndiff, nrz, ncfg); return 1; }
    std::printf("bench_mix: %ld configurations, every word the same (fast 1 = fast 0 = two-launch); outputs seen: %ld +0, %ld -0, "
                "%ld subnormal\n", ncfg, cov[0], cov[1], cov[2]);

    // ---- speed ---------------------------------------------------------------------------------------------------
    struct Shape { const char *name; Cfg c; int w; }; // w: launches of this shape in a one-token plain step
    std::vector<Shape> shapes;
    auto add = [&](const char *nm, int ns, int nq, int mode, bool warm, int mk, int w, int ntok = 1) {
        shapes.push_back({nm, Cfg{2304, 2304, ns, nq, ntok, 0, mk, 0, mode, warm, false, false}, w});
    };
    // the one-token step's 96 mixes (inkling2-forward.md 3.6: 3 queries at il % 6 == 5; no norm in loop passes 1-2,
    // il 18-41; the current state saved at il 6, 12, 42 and 18, 24, 30, 36), then DSpark's steps (w 0)
    for (int ns = 2; ns <= 5; ++ns) add("attn mix_norm, 1 query (warm)", ns, 1, M_NY, true, -1, 4);
    for (int ns = 2; ns <= 5; ++ns) add("attn mix_norm, 3 queries (warm)", ns, 3, M_NY, true, -1, 1);
    for (int ns = 2; ns <= 4; ++ns) add("attn mix_norm + saved state (warm)", ns, 1, M_NY, true, MK, 1);
    for (int ns = 3; ns <= 4; ++ns) add("attn mix_out, 1 query (warm)", ns, 1, M_OUT, true, -1, 8);
    for (int ns = 2; ns <= 3; ++ns) add("attn mix_out + saved state (warm)", ns, 1, M_OUT, true, MK, 2);
    for (int ns = 3; ns <= 4; ++ns) add("attn mix_out, 3 queries (warm)", ns, 3, M_OUT, true, -1, 2);
    for (int ns = 2; ns <= 5; ++ns) add("ffn mix_norm (yl + yp)", ns, 1, M_NFFN, false, -1, 6);
    for (int ns = 3; ns <= 4; ++ns) add("ffn mix_out", ns, 1, M_OUT, false, -1, 12);
    add("output mix_norm", 5, 1, M_NY, false, -1, 1);
    add("ffn mix_norm, 2 tokens", 4, 1, M_NFFN, false, -1, 0, 2);
    add("ffn mix_norm, 4 tokens", 4, 1, M_NFFN, false, -1, 0, 4);
    add("attn mix_out, 2 tokens", 3, 1, M_OUT, false, -1, 0, 2);
    add("attn mix_out, 4 tokens", 3, 3, M_OUT, false, -1, 0, 4);
    {
        int wsum = 0;
        for (const Shape &sh : shapes) wsum += sh.w;
        if (wsum != 96) { std::fprintf(stderr, "bench_mix: the step's shapes count %d mixes, not 96\n", wsum); return 2; }
    }
    namespace epi = sycl::info::event_profiling;
    auto dur = [](const sycl::event &e) { return (e.get_profiling_info<epi::command_end>() - e.get_profiling_info<epi::command_start>()) * 1e-3; };
    std::printf("speed: us per launch (event start to end), states cold, then the 21 MB read after it; %d launches per arm and order\n", iters);
    std::printf("  %-38s %2s %5s %2s | %8s %8s %8s | %8s %8s\n", "shape", "ns", "mode", "w", "fast 0", "fast 1", "1 - 0", "next 0",
                "next 1");
    double tot_mix[2] = {0, 0}, tot_fol[2] = {0, 0}, step_mix[2] = {0, 0}, step_fol[2] = {0, 0};
    for (const Shape &sh : shapes) {
        const Cfg &c = sh.c;
        load(c.n, c.ld);
        fill(tinv, (size_t)NSLOT * T * 4); fill(tsc, (size_t)NSLOT * T * NQA * 4);
        save_blocks(c, 0);
        pq.wait_and_throw();
        double tm[2] = {0, 0}, tf[2] = {0, 0};
        for (int order = 0; order < 2; ++order)
            for (int k = 0; k < 2; ++k) {
                const int fast = order == 0 ? k : 1 - k;
                std::vector<sycl::event> em, ef;
                em.reserve(iters); ef.reserve(iters);
                for (int i = 0; i < iters + 3; ++i) {
                    rd(fl, FLN);
                    sycl::event e = launch(c, fast);
                    sycl::event f = rd(fol, FOLN);
                    if (i >= 3) { em.push_back(e); ef.push_back(f); }
                }
                pq.wait_and_throw();
                for (auto &e : em) tm[fast] += dur(e);
                for (auto &e : ef) tf[fast] += dur(e);
            }
        for (int f = 0; f < 2; ++f) {
            tm[f] /= 2.0 * iters; tf[f] /= 2.0 * iters;
            tot_mix[f] += tm[f]; tot_fol[f] += tf[f];
            step_mix[f] += sh.w * tm[f]; step_fol[f] += sh.w * tf[f];
        }
        std::printf("  %-38s %2d %5s %2d | %8.2f %8.2f %+8.2f | %8.2f %8.2f\n", sh.name, c.ns, c.mode == M_OUT ? "out" : "norm",
                    sh.w, tm[0], tm[1], tm[1] - tm[0], tf[0], tf[1]);
    }
    std::printf("  %-38s             | %8.2f %8.2f %+8.2f | %8.2f %8.2f  (sum over the shapes)\n", "all", tot_mix[0], tot_mix[1],
                tot_mix[1] - tot_mix[0], tot_fol[0], tot_fol[1]);
    std::printf("  one-token plain step, the 96 mixes (sum of w x time), ms: fast 0 %.4f, fast 1 %.4f, 1 - 0 %+.4f; the reads "
                "after them %.4f, %.4f, %+.4f\n", step_mix[0] * 1e-3, step_mix[1] * 1e-3, (step_mix[1] - step_mix[0]) * 1e-3,
                step_fol[0] * 1e-3, step_fol[1] * 1e-3, (step_fol[1] - step_fol[0]) * 1e-3);
    // back to back (warm caches, wall clock): what one more or one less barrier and batch cost when nothing waits
    std::printf("back to back, us per launch (wall clock, %d launches):\n", iters);
    double step_b2b[2] = {0, 0};
    for (const Shape &sh : shapes) {
        const Cfg &c = sh.c;
        fill(tinv, (size_t)NSLOT * T * 4); fill(tsc, (size_t)NSLOT * T * NQA * 4);
        save_blocks(c, 0);
        pq.wait_and_throw();
        double us[2] = {0, 0};
        for (int order = 0; order < 2; ++order)
            for (int k = 0; k < 2; ++k) {
                const int fast = order == 0 ? k : 1 - k;
                for (int i = 0; i < 5; ++i) launch(c, fast);
                pq.wait_and_throw();
                const double t0 = now_s();
                for (int i = 0; i < iters; ++i) launch(c, fast);
                pq.wait_and_throw();
                us[fast] += (now_s() - t0) / iters * 1e6 / 2.0;
            }
        for (int f = 0; f < 2; ++f) step_b2b[f] += sh.w * us[f];
        std::printf("  %-38s %2d %5s %2d | %8.2f %8.2f %+8.2f\n", sh.name, c.ns, c.mode == M_OUT ? "out" : "norm", sh.w, us[0], us[1],
                    us[1] - us[0]);
    }
    std::printf("  one-token plain step, the 96 mixes back to back, ms: fast 0 %.4f, fast 1 %.4f, 1 - 0 %+.4f\n", step_b2b[0] * 1e-3,
                step_b2b[1] * 1e-3, (step_b2b[1] - step_b2b[0]) * 1e-3);
    // mix_save (role B alone, the barrier left out of its scale sum)
    {
        Cfg c{2304, 2304, 1, 0, 1, 0, MK, 0, M_OUT_NULL, false, false, false};
        double tm[2] = {0, 0};
        for (int order = 0; order < 2; ++order)
            for (int k = 0; k < 2; ++k) {
                const int fast = order == 0 ? k : 1 - k;
                std::vector<sycl::event> em;
                for (int i = 0; i < iters + 3; ++i) {
                    rd(fl, FLN);
                    fz::MixF b;
                    b.st[0] = stb[0]; b.ns = 1; b.nq = 0;
                    b.tinv = tinv; b.tsc = tsc; b.T = T; b.NQA = NQA; b.mk_slot = MK; b.qall = qall; b.t0 = 0;
                    sycl::event e = fz::mix_fused(pq, b, c.ld, nullptr, nullptr, eps, c.n, 1, fz::Warm{}, fast);
                    if (i >= 3) em.push_back(e);
                }
                pq.wait_and_throw();
                for (auto &e : em) tm[fast] += dur(e) / (2.0 * iters);
            }
        std::printf("  %-38s    %5s    | %8.2f %8.2f %+8.2f  (cold, event time)\n", "mix_save (role B alone, 56 queries)", "", tm[0], tm[1], tm[1] - tm[0]);
    }
    return 0;
}
