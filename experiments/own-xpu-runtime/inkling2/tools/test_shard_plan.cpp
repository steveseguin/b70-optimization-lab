// test_shard_plan: host checks of src/shard_plan.hpp (no card, no SYCL; any C++20 compiler:
//   g++ -std=c++20 -O2 -ffp-contract=off tools/test_shard_plan.cpp -o /tmp/test_shard_plan && /tmp/test_shard_plan)
// 1. the layouts the lab runs (2-6 engines at the 200K and 1M prompts), against the expected lengths and the uniform
//    layout before 2026-11-28 (two-card-run.sh: s = round(n / engines) in whole groups);
// 2. for every n in a sweep and 2-8 engines: whole groups, in order, below the context by the relative extent, the
//    longest scan the least any whole-group layout gives (all S), the fewest groups among those, the room limit kept;
// 3. the fold's arithmetic (attn_flash_sum_u, one row, a few channels, FMA as mac()) over random block parts: one
//    pass over all blocks against the shared order (each partner's slice in pieces from the state before it, then the
//    owner), for uniform, balanced and given layouts: the same bits;
// 4. the checks before any offset or buffer (shard_check_lengths, shard_offsets: 64-bit sums, int overflow refused),
//    the switches parsed whole (shard_parse_int / shard_parse_split / shard_env_from: empty, malformed, signed,
//    overflowing and out-of-range values throw; INK_SHARD_PARTNERS=0 shares nothing), the layout and mode each
//    selects (shard_plan), and the room bisection (shard_max_groups);
// 5. room (shard_room_need / shard_room_search, a host model of Engine::shard_copy_room): Codex's counterexample (four
//    groups held on a card past its reserve: the reuse check accepts 1, 2 and 4 groups and refuses 3 and 5, so a
//    bisection over it gives 2 at a capacity of 10 groups, missing the held 4, and 4 at 8, letting the planner take an
//    unaffordable 3), and random chains: the sizes a plan may take are exactly the ones the room check accepts, and the
//    plan is the best of those.
#include "../src/shard_plan.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <climits>
#include <random>
#include <string>

using namespace ink;
static int fails = 0;
#define CHECK(c, ...) do { if (!(c)) { ++fails; std::printf("FAIL %s:%d: ", __FILE__, __LINE__); std::printf(__VA_ARGS__); std::printf("\n"); } } while (0)

static std::vector<int> uniform(long n, int N) { // two-card-run.sh's s, then N - 1 slices of it
    const int s = (int)((n / N + SHARD_Q / 2) / SHARD_Q * SHARD_Q);
    return s > 0 ? std::vector<int>(N - 1, s) : std::vector<int>();
}
template <class F> static bool throws(F f) {
    try { f(); } catch (std::exception &) { return true; }
    return false;
}
static long longest(const std::vector<int> &l, long n) {
    long m = n - shard_sum(l);
    for (int v : l) m = std::max<long>(m, v);
    return m;
}

// ---- 3: the fold (attn_flash_sum_u's arithmetic for one row; C channels stand in for 128) ----
constexpr int C = 4, NB = 128;
struct Part { float mb, l, v[C]; };
struct State { float A[C], M, L; };
static float mac(float acc, float a, float b) { return std::fma(a, b, acc); }
// blocks b0 .. b0 + nblk - 1 folded from st (from) or the sink, in chunks of 128 from b0 (b0 % 128 == 0)
static void fold(const std::vector<Part> &p, int b0, int nblk, float sink, State &st, bool from) {
    if (b0 % NB) { std::printf("fold: b0 %% 128\n"); std::exit(2); }
    float A[C], M = sink, L = 1.0f;
    for (int c = 0; c < C; ++c) A[c] = 0.0f;
    if (from) { std::memcpy(A, st.A, sizeof A); M = st.M; L = st.L; }
    for (int c0 = 0; c0 < nblk; c0 += NB) {
        const int cnt = std::min(NB, nblk - c0);
        float al[NB], be[NB], run = -INFINITY, mlast = M;
        for (int i = 0; i < cnt; ++i) { // (exclusive and inclusive prefix maxima with M: exact in any order)
            const float mb = p[b0 + c0 + i].mb, mp = std::fmax(M, run);
            run = std::fmax(run, mb);
            const float mn = std::fmax(M, run);
            al[i] = std::exp(mp - mn); be[i] = std::exp(mb - mn); mlast = mn;
        }
        for (int i = 0; i < cnt; ++i) {
            const Part &q = p[b0 + c0 + i];
            L = mac(L * al[i], q.l, be[i]);
            for (int c = 0; c < C; ++c) A[c] = mac(A[c] * al[i], q.v[c], be[i]);
        }
        M = mlast;
    }
    std::memcpy(st.A, A, sizeof A); st.M = M; st.L = L;
}
static std::vector<uint32_t> out_bits(const State &s) {
    std::vector<uint32_t> o(C);
    for (int c = 0; c < C; ++c) { const float x = s.A[c] * (1.0f / s.L); std::memcpy(&o[c], &x, 4); }
    return o;
}
// the shared order: partner r's blocks off[r] / 128 .. off[r + 1] / 128 - 1 in pieces of cy blocks from the state before
// it (partner 0 from the sink), then the owner's in pieces of co from the last partner's state
static std::vector<uint32_t> shared(const std::vector<Part> &p, const std::vector<int> &len, int cy, int co, float sink) {
    const std::vector<int> off = shard_offsets(len);
    const int nblk = (int)p.size(), PB = 128; // positions per block
    State st{};
    for (size_t r = 0; r + 1 < off.size(); ++r) {
        const int lo = off[r] / PB, hi = off[r + 1] / PB;
        for (int b0 = lo; b0 < hi; b0 += cy) fold(p, b0, std::min(cy, hi - b0), sink, st, b0 > 0);
    }
    const int SB = off.back() / PB;
    for (int b0 = SB; b0 < nblk; b0 += co) fold(p, b0, std::min(co, nblk - b0), sink, st, b0 > 0);
    return out_bits(st);
}

int main() {
    const int ext = 1024; // Inkling-2-Mini attention.relative_extent
    // ---- 1: the lab's layouts ----
    struct Want { long n; int N; std::vector<int> bal; long own; };
    const int G = SHARD_Q;
    const std::vector<Want> want = {
        {200001, 2, {6 * G}, 101697},
        {200001, 3, {4 * G, 4 * G}, 68929},
        {200001, 4, {3 * G, 3 * G, 3 * G}, 52545},
        {200001, 5, {3 * G, 3 * G, 2 * G, 2 * G}, 36161},
        {200001, 6, {2 * G, 2 * G, 2 * G, 2 * G, 2 * G}, 36161},
        {1042081, 2, {32 * G}, 517793},
        {1042081, 3, {21 * G, 21 * G}, 353953},
        {1042081, 4, {16 * G, 16 * G, 16 * G}, 255649},
        {1042081, 5, {13 * G, 13 * G, 13 * G, 12 * G}, 206497},
        {1042081, 6, {11 * G, 11 * G, 11 * G, 10 * G, 10 * G}, 173729},
    };
    for (const Want &w : want) {
        const std::vector<int> b = shard_plan_balanced(w.n, w.N, ext, 1), u = uniform(w.n, w.N);
        CHECK(b == w.bal, "n %ld N %d: %s", w.n, w.N, shard_layout_str(b, w.n, "balanced").c_str());
        CHECK(w.n - shard_sum(b) == w.own, "n %ld N %d: owner %ld", w.n, w.N, w.n - shard_sum(b));
        CHECK(longest(b, w.n) <= longest(u, w.n), "n %ld N %d: longer than uniform", w.n, w.N);
        std::printf("n %7ld, %d engines: balanced %-62s longest %6ld | uniform %-58s longest %6ld\n", w.n, w.N,
                    shard_layout_str(b, w.n, "bal").c_str(), longest(b, w.n), shard_layout_str(u, w.n, "uni").c_str(), longest(u, w.n));
    }
    // INK_SHARD_PARTNERS=3 on five or six engines: balanced over four (the four-card layout), owner 52,544 at 200,000
    CHECK((shard_plan_balanced(200000, 4, ext, 1) == std::vector<int>{3 * G, 3 * G, 3 * G}), "3 partners");
    CHECK((shard_plan_balanced(200000, 5, ext, 1) == std::vector<int>{3 * G, 3 * G, 2 * G, 2 * G}), "200,000 on 5");
    // mode 2: the same lengths, the extra groups last
    CHECK((shard_plan_balanced(200001, 5, ext, 2) == std::vector<int>{2 * G, 2 * G, 3 * G, 3 * G}), "mode 2");
    // room: at most 9 groups at 5 engines / 200K: 3+2+2+2, owner 52,545
    CHECK((shard_plan_balanced(200001, 5, ext, 1, 9) == std::vector<int>{3 * G, 2 * G, 2 * G, 2 * G}), "gmax 9");
    CHECK(shard_plan_balanced(200001, 5, ext, 1, 0).empty(), "gmax 0");
    // below the relative extent: nothing; one group: only partner 0
    CHECK(shard_plan_balanced(16384 + 1023, 5, ext, 1).empty(), "n below a group + ext");
    CHECK((shard_plan_balanced(40000, 5, ext, 1) == std::vector<int>{G, G}), "40000 on 5: %s",
          shard_layout_str(shard_plan_balanced(40000, 5, ext, 1), 40000, "").c_str());
    // INK_SHARD_SPLIT
    CHECK((shard_parse_split("49152,49152,32768,32768", 5) == std::vector<int>{3 * G, 3 * G, 2 * G, 2 * G}), "split");
    for (const char *bad : {"49152,49152,32768,32768,16384", "1000", "0", "16384,x", ""}) {
        bool threw = false;
        try { shard_parse_split(bad, 5); } catch (std::exception &) { threw = true; }
        CHECK(threw, "split '%s' accepted", bad);
    }
    // ---- 2: properties over a sweep ----
    long checked = 0;
    for (int N = 2; N <= 8; ++N)
        for (long n = 1; n <= 1100000; n += (n < 70000 ? 97 : 4099)) {
            for (int mode = 1; mode <= 2; ++mode)
                for (long gmax : {-1L, 3L, 17L}) {
                    const std::vector<int> l = shard_plan_balanced(n, N, ext, mode, gmax);
                    const long S = shard_sum(l) / G;
                    CHECK((int)l.size() <= N - 1, "n %ld N %d: %zu partners", n, N, l.size());
                    for (int v : l) CHECK(v > 0 && v % G == 0, "n %ld N %d: length %d", n, N, v);
                    CHECK(l.empty() || shard_sum(l) + ext <= n, "n %ld N %d: past the extent", n, N);
                    CHECK(gmax < 0 || S <= gmax, "n %ld N %d: room", n, N);
                    if (!l.empty()) {
                        const int mx = *std::max_element(l.begin(), l.end()), mn = *std::min_element(l.begin(), l.end());
                        CHECK(mx - mn <= G, "n %ld N %d: partners differ by more than a group", n, N);
                    }
                    // the least longest scan of any S (whole groups as evenly as they go), the fewest groups for it
                    long smax = n - ext >= 0 ? (n - ext) / G : 0;
                    if (gmax >= 0) smax = std::min(smax, gmax);
                    long best = n, bs = 0;
                    for (long s = 1; s <= smax; ++s) {
                        const long c = std::max((s + N - 2) / (N - 1) * G, n - s * G);
                        if (c < best) { best = c; bs = s; }
                    }
                    CHECK(longest(l, n) == best && S == bs, "n %ld N %d: longest %ld, best %ld (S %ld / %ld)", n, N, longest(l, n), best, S, bs);
                    ++checked;
                }
        }
    std::printf("sweep: %ld layouts checked\n", checked);
    // ---- 3: the fold, bit for bit ----
    std::mt19937 rng(20261128);
    std::normal_distribution<float> nd(0.0f, 3.0f);
    for (long n : {200001L, 1042081L}) {
        const int nblk = (int)((n + 127) / 128);
        std::vector<Part> p(nblk);
        for (Part &q : p) {
            q.mb = nd(rng); q.l = std::fabs(nd(rng)) + 0.5f;
            for (float &v : q.v) v = nd(rng);
        }
        const float sink = nd(rng);
        State one{};
        fold(p, 0, nblk, sink, one, false); // one card: one launch over every block
        const std::vector<uint32_t> ref = out_bits(one);
        for (int N = 2; N <= 6; ++N)
            for (int mode = 0; mode <= 2; ++mode) {
                const std::vector<int> l = mode == 0 ? uniform(n, N) : shard_plan_balanced(n, N, ext, mode);
                for (int cy : {128, 256, 1152, 1 << 20})
                    CHECK(shared(p, l, cy, 1536, sink) == ref, "fold n %ld N %d mode %d pieces %d: bits differ", n, N, mode, cy);
            }
        for (const char *g : {"49152,49152,32768,32768", "32768,32768,49152,49152", "16384", "65536,16384,16384"})
            CHECK(shared(p, shard_parse_split(g, 5), 384, 512, sink) == ref, "fold n %ld split %s: bits differ", n, g);
    }
    std::printf("fold: shared orders against one pass checked\n");
    // ---- 4: validation and parsing ----
    long cases = 0;
    auto expect_throw = [&](bool t, const char *what) { CHECK(t, "accepted: %s", what); ++cases; };
    // lengths: aligned, individually valid, but their int sum wraps (3 x 2^30 = -2^30 in 32 bits; 2 x 2^30 = INT_MIN)
    const int H = 1 << 30; // (a multiple of 16384)
    expect_throw(throws([&] { shard_check_lengths({H, H, H}, 5, 200001, ext); }), "3 x 2^30 at 200,001");
    expect_throw(throws([&] { shard_check_lengths({H, H}, 5, 200001, ext); }), "2 x 2^30 at 200,001");
    expect_throw(throws([&] { shard_check_lengths({H, H, H, H}, 5, (int64_t)1 << 40, ext); }), "4 x 2^30 past INT_MAX (offsets are ints)");
    expect_throw(throws([&] { shard_offsets({H, H}); }), "shard_offsets 2 x 2^30");
    expect_throw(throws([&] { shard_offsets({G, -G}); }), "shard_offsets negative");
    expect_throw(throws([&] { shard_check_lengths({3 * G, 3 * G, 3 * G, 3 * G}, 5, 4 * 3 * G + ext - 1, ext); }), "one position short");
    CHECK((shard_check_lengths({3 * G, 3 * G, 3 * G, 3 * G}, 5, 4 * 3 * G + ext, ext) == std::vector<int>{0, 3 * G, 6 * G, 9 * G, 12 * G}),
          "exactly n - ext");
    ++cases;
    expect_throw(throws([&] { shard_check_lengths({}, 5, 200001, ext); }), "no slices");
    expect_throw(throws([&] { shard_check_lengths({G, G, G, G, G}, 5, 1042081, ext); }), "5 slices on 5 engines");
    expect_throw(throws([&] { shard_check_lengths({G}, 1, 1042081, ext); }), "one engine");
    expect_throw(throws([&] { shard_check_lengths({0}, 5, 200001, ext); }), "a zero slice");
    expect_throw(throws([&] { shard_check_lengths({G + 128}, 5, 200001, ext); }), "a slice off the group grid");
    expect_throw(throws([&] { shard_check_lengths({-G}, 5, 200001, ext); }), "a negative slice");
    expect_throw(throws([&] { shard_check_lengths({G}, 5, 500, ext); }), "n below ext");
    // whole-token integers
    for (const char *bad : {"", " 1", "1 ", "+1", "-1", "1x", "0x10", "1e3", "1.0", "99999999999999999999", "9223372036854775808"})
        expect_throw(throws([&] { shard_parse_int("X", bad, 0, 2); }), bad);
    CHECK(shard_parse_int("X", "2", 0, 2) == 2 && shard_parse_int("X", "0", 0, 2) == 0 && shard_parse_int("X", "01", 0, 2) == 1, "ints");
    expect_throw(throws([&] { shard_parse_int("X", "3", 0, 2); }), "3 of 0..2");
    // INK_SHARD_SPLIT: empty fields, signs, spaces, overflow (2^32 + 16384 is 16384 once cast to int)
    for (const char *bad : {"16384,,16384", "16384,", ",16384", ",", " 16384", "16384 ", "+16384", "-16384", "16384;16384",
                            "2147483648", "4294983680", "99999999999999999999999", "1073741824,1073741824,x"})
        expect_throw(throws([&] { shard_parse_split(bad, 5); }), bad);
    CHECK((shard_parse_split("16384", 2) == std::vector<int>{G}), "split one");
    ++cases;
    // the switches
    for (const char *bad : {"", "x", "3", "-1", "1 ", "4294967297"})
        expect_throw(throws([&] { shard_env_from(bad, nullptr, nullptr, 5, true); }), bad);
    for (const char *bad : {"", "x", "5", "-1", "2147483647", "4294967296", "18446744073709551617"})
        expect_throw(throws([&] { shard_env_from(nullptr, bad, nullptr, 5, true); }), bad);
    expect_throw(throws([&] { shard_env_from(nullptr, "2", "16384", 5, true); }), "SPLIT with PARTNERS");
    expect_throw(throws([&] { shard_env_from(nullptr, nullptr, "", 5, true); }), "SPLIT empty");
    expect_throw(throws([&] { shard_env_from(nullptr, nullptr, nullptr, 1, true); }), "one engine");
    {
        const ShardEnv e = shard_env_from(nullptr, nullptr, nullptr, 5, true);
        CHECK(e.bal == 1 && e.partners == -1 && !e.split_set && !e.split_ignored, "defaults");
        const ShardPlan p = shard_plan(e, 200001, 5, ext, 0);
        CHECK((p.len == std::vector<int>{3 * G, 3 * G, 2 * G, 2 * G}) && p.mode == "balanced", "default plan: %s", p.mode.c_str());
        cases += 2;
    }
    {   // PARTNERS=0: nothing, in every mode, and no stale all-partner layout
        for (const char *b : {"0", "1", "2"}) {
            const ShardEnv e = shard_env_from(b, "0", nullptr, 5, false);
            CHECK(e.partners == 0, "partners 0");
            const ShardPlan p = shard_plan(e, 1042081, 5, ext, 212992);
            CHECK(p.len.empty() && p.mode.find("INK_SHARD_PARTNERS=0") != std::string::npos, "PARTNERS=0 BAL=%s: %s", b, p.mode.c_str());
            cases += 2;
        }
        CHECK(shard_plan(shard_env_from(nullptr, "0", nullptr, 2, true), 200001, 2, ext, 98304).len.empty(), "PARTNERS=0 two engines");
        ++cases;
    }
    {   // PARTNERS=3 on five / six engines: the four-engine balanced layout; PARTNERS=N-1 the same as unset
        for (int N : {5, 6}) {
            const ShardPlan p = shard_plan(shard_env_from(nullptr, "3", nullptr, N, true), 200000, N, ext, 0);
            CHECK((p.len == std::vector<int>{3 * G, 3 * G, 3 * G}) && p.mode == "balanced, 3 partners", "PARTNERS=3 N %d: %s", N, p.mode.c_str());
            const ShardPlan all = shard_plan(shard_env_from(nullptr, std::to_string(N - 1).c_str(), nullptr, N, true), 1042081, N, ext, 0);
            CHECK(all.len == shard_plan_balanced(1042081, N, ext, 1), "PARTNERS=N-1 N %d", N);
            cases += 2;
        }
    }
    {   // BAL=0: the uniform slices of s, PARTNERS of them when set; s <= 0 none
        const ShardPlan u = shard_plan(shard_env_from("0", nullptr, nullptr, 5, true), 200001, 5, ext, 2 * G);
        CHECK((u.len == std::vector<int>(4, 2 * G)) && u.mode == "uniform", "uniform: %s", u.mode.c_str());
        const ShardPlan u2 = shard_plan(shard_env_from("0", "2", nullptr, 5, true), 200001, 5, ext, 2 * G);
        CHECK((u2.len == std::vector<int>(2, 2 * G)), "uniform 2 partners");
        CHECK(shard_plan(shard_env_from("0", nullptr, nullptr, 5, true), 200001, 5, ext, 0).len.empty(), "uniform s 0");
        cases += 3;
    }
    {   // BAL=2, SPLIT (given; serving: ignored, even malformed), room
        CHECK(shard_plan(shard_env_from("2", nullptr, nullptr, 5, true), 200001, 5, ext, 0).mode == "balanced, last", "mode 2 name");
        const ShardPlan g = shard_plan(shard_env_from("0", nullptr, "65536,16384,16384", 5, true), 200001, 5, ext, 2 * G);
        CHECK((g.len == std::vector<int>{4 * G, G, G}) && g.mode == "given", "given: %s", g.mode.c_str());
        const ShardEnv sv = shard_env_from(nullptr, nullptr, "not,a,split", 5, false);
        CHECK(sv.split_ignored && !sv.split_set, "serving ignores SPLIT");
        CHECK((shard_plan(sv, 200001, 5, ext, 0).len == std::vector<int>{3 * G, 3 * G, 2 * G, 2 * G}), "serving plan without SPLIT");
        const ShardPlan r9 = shard_plan(sv, 200001, 5, ext, 0, 9), r0 = shard_plan(sv, 200001, 5, ext, 0, 0);
        CHECK((r9.len == std::vector<int>{3 * G, 2 * G, 2 * G, 2 * G}) && r9.mode == "balanced, room-limited", "room 9: %s", r9.mode.c_str());
        CHECK(r0.len.empty() && r0.mode == "balanced: no room", "room 0: %s", r0.mode.c_str());
        CHECK(shard_plan(sv, 200001, 5, ext, 0, 50).mode == "balanced", "room enough");
        CHECK(shard_plan(sv, 16384 + 1023, 5, ext, 0).mode == "balanced: no group below the context", "below a group");
        cases += 8;
    }
    // room bisection: the most groups that fit, for every capacity and threshold, in about log2 calls
    for (int64_t gcap = 0; gcap <= 80; ++gcap)
        for (int64_t t = -1; t <= gcap + 1; ++t) {
            int calls = 0;
            const int64_t g = shard_max_groups(gcap, [&](int64_t x) { ++calls; return x <= t; });
            CHECK(g == std::max<int64_t>(0, std::min(t, gcap)), "bisection gcap %ld t %ld: %ld", (long)gcap, (long)t, (long)g);
            CHECK(calls <= 8, "bisection gcap %ld: %d calls", (long)gcap, calls);
            ++cases;
        }
    std::printf("validation and parsing: %ld cases checked\n", cases);
    // ---- 5: room ----
    {
        // a host model of Engine::shard_copy_room: engines on cards (allocated, held, reserve, limit), each holding hf
        // copy buffers of hpos positions (value stride hvld) and missing step-buffer bytes
        struct Card { long long alloc, hold, spare, limit; };
        struct Eng { int card; int64_t hpos; size_t hf; int64_t hvld; size_t missing; };
        struct Chain {
            std::vector<Card> cards; std::vector<Eng> engs; size_t f; int kd;
            bool fits(int64_t cpos, bool reuse) const { // (shard_copy_room(cpos, reuse) < 0)
                std::vector<long long> add(cards.size(), 0);
                std::vector<char> chk(cards.size(), 0);
                for (const Eng &x : engs) {
                    const ShardRoomNeed r = shard_room_need(cpos, f, kd, x.hpos, x.hf, x.hvld, x.missing, reuse);
                    if (r.check) { add[x.card] += r.add; chk[x.card] = 1; }
                }
                for (size_t c = 0; c < cards.size(); ++c)
                    if (chk[c] && cards[c].alloc + cards[c].hold + cards[c].spare + add[c] > cards[c].limit) return false;
                return true;
            }
            int64_t held() const { // (Engine::shard_room_groups: whole groups, the same on every engine)
                const int64_t h = engs[0].hpos;
                int64_t g = h > 0 && h % SHARD_Q == 0 ? h / SHARD_Q : -1;
                for (const Eng &x : engs) if (x.hpos != h || x.hf != f) g = -1;
                return g;
            }
            ShardRoom room(int64_t gcap) const {
                const int64_t h = held();
                return shard_room_search(gcap, [&](int64_t g) { return fits(g * SHARD_Q, false); }, h, [&] { return fits(h * SHARD_Q, true); });
            }
        };
        const long long MiB = 1 << 20;
        const int kd = 1024; // (f = 2 buffers of 2 x 16384 x 1024 halves: 128 MiB a group)
        const int64_t g4 = 4 * (int64_t)G;
        // Codex's counterexample: four groups held everywhere, step buffers allocated, every card past its 256 MiB reserve
        // (allocated + reserve = limit + 192 MiB): new buffers of g groups need 128 (g - 4) MiB more, so they fit up to 2
        Chain cx;
        cx.f = 2; cx.kd = kd;
        for (int c = 0; c < 4; ++c) {
            cx.cards.push_back({20480 * MiB, 0, 256 * MiB, 20480 * MiB + 64 * MiB});
            cx.engs.push_back({c, g4, 2, g4, 0});
        }
        CHECK(shard_copy_bytes(G, 2, kd, G) == (size_t)(128 * MiB), "group bytes");
        std::string pat;
        for (int64_t g = 0; g <= 10; ++g) pat += cx.fits(g * G, true) ? '1' : '0';
        CHECK(pat == "11101000000", "the reuse check accepts 0-2 and 4: %s", pat.c_str()); // (the defect's premise)
        auto old_fits = [&](int64_t g) { return cx.fits(g * G, true); };
        CHECK(shard_max_groups(10, old_fits) == 2, "old bisection at 10 groups: the held 4 missed");
        CHECK(shard_max_groups(8, old_fits) == 4, "old bisection at 8 groups: 4, so 3 looks affordable");
        for (int64_t gcap : {8, 10}) {
            const ShardRoom r = cx.room(gcap);
            CHECK(r.g_replace == 2 && r.g_exact == 4, "room at %ld groups: %ld / %ld", (long)gcap, (long)r.g_replace, (long)r.g_exact);
            cases++;
        }
        const ShardEnv de = shard_env_from(nullptr, nullptr, nullptr, 4, false);
        // capacity 8, four engines, 73,728 positions (4.5 groups): the old cached 4 let the planner pick 3 (cost 1.5
        // groups), which the room check refuses; the new candidates 1, 2, 4 give 4, the held copies reused
        {
            const int64_t n = 73728;
            const std::vector<int> old = shard_plan_balanced(n, 4, ext, 1, shard_max_groups(8, old_fits));
            CHECK(shard_sum(old) == 3 * G && !cx.fits(3 * G, true), "old plan at capacity 8: %s", shard_layout_str(old, n, "old").c_str());
            const ShardRoom r = cx.room(8);
            const ShardPlan p = shard_plan(de, n, 4, ext, 0, r.g_replace, r.g_exact);
            CHECK(shard_sum(p.len) == 4 * G && cx.fits(shard_sum(p.len), true), "new plan at capacity 8: %s",
                  shard_layout_str(p.len, n, p.mode).c_str());
            cases += 2;
        }
        // capacity 10, three engines, 6 groups + the extent: the old cached 2 (owner 4 groups) missed the held 4 (cost
        // 2 groups + 1,024); the new search finds it
        {
            const int64_t n = 6 * (int64_t)G + ext;
            Chain c3 = cx;
            c3.cards.resize(3); c3.engs.resize(3);
            const std::vector<int> old = shard_plan_balanced(n, 3, ext, 1, shard_max_groups(10, [&](int64_t g) { return c3.fits(g * G, true); }));
            CHECK(shard_sum(old) == 2 * G, "old plan at capacity 10: %s", shard_layout_str(old, n, "old").c_str());
            const ShardRoom r = c3.room(10);
            const ShardPlan p = shard_plan(shard_env_from(nullptr, nullptr, nullptr, 3, false), n, 3, ext, 0, r.g_replace, r.g_exact);
            CHECK((p.len == std::vector<int>{2 * G, 2 * G}) && c3.fits(shard_sum(p.len), true), "new plan at capacity 10: %s",
                  shard_layout_str(p.len, n, p.mode).c_str());
            cases += 2;
        }
        // the held copies need a missing step buffer the card has no room for: no exact reuse either
        {
            Chain cm = cx;
            cm.engs[2].missing = MiB;
            const ShardRoom r = cm.room(10);
            CHECK(r.g_replace == 2 && r.g_exact == -1, "missing step bytes: %ld / %ld", (long)r.g_replace, (long)r.g_exact);
            CHECK(!cm.fits(g4, true), "held 4 with a missing step buffer refused");
            cases += 2;
        }
        // random chains: the replacement check is monotone, the candidates are exactly the accepted sizes, and the
        // plan is the best accepted layout (fewest groups among equal longest scans)
        std::mt19937 rr(20261128 + 6);
        long chains = 0, plans = 0, reused = 0;
        for (int t = 0; t < 4000; ++t) {
            Chain ch;
            const int N = 2 + (int)(rr() % 5);
            ch.f = 1 + rr() % 3; ch.kd = kd;
            const int64_t hg = (int64_t)(rr() % 10) - 1; // (-1: no copies held)
            const int ncard = rr() % 3 == 0 ? std::max(1, N / 2) : N; // (sometimes two engines on a card)
            for (int c = 0; c < ncard; ++c) {
                const long long lim = (long long)(8192 + rr() % 24576) * MiB;
                ch.cards.push_back({lim - (long long)(rr() % 4096) * MiB + 1024 * MiB, (long long)(rr() % 3) * 64 * MiB,
                                    (long long)(rr() % 2 ? 256 : 0) * MiB, lim});
            }
            for (int k = 0; k < N; ++k) {
                const int64_t hp = hg > 0 ? hg * G : 0;
                ch.engs.push_back({k % ncard, hp, hg > 0 ? ch.f : 0, hp, rr() % 4 == 0 ? (size_t)(rr() % 64) * MiB : 0});
            }
            const int64_t gcap = rr() % 14;
            bool prev = true;
            for (int64_t g = 0; g <= gcap; ++g) {
                const bool f = ch.fits(g * G, false);
                CHECK(!f || prev, "replacement check not monotone at %ld", (long)g);
                prev = f;
            }
            const ShardRoom r = ch.room(gcap);
            std::vector<int64_t> acc, cand;
            for (int64_t g = 1; g <= gcap; ++g) {
                if (ch.fits(g * G, true)) acc.push_back(g);
                if (g <= r.g_replace || g == r.g_exact) cand.push_back(g);
            }
            CHECK(acc == cand, "chain %d: the candidates differ from the accepted sizes (%ld / %ld)", t, (long)r.g_replace, (long)r.g_exact);
            reused += r.g_exact >= 0;
            ++chains;
            const ShardEnv env = shard_env_from(nullptr, nullptr, nullptr, N, false);
            for (int64_t n : {(int64_t)20000, (int64_t)70001, (int64_t)140000, (int64_t)200001}) {
                const ShardPlan p = shard_plan(env, n, N, ext, 0, r.g_replace, r.g_exact);
                const int64_t S = shard_sum(p.len) / G;
                int64_t best = n, bs = 0;
                for (int64_t g : acc) {
                    if (g * G + ext > n) continue;
                    const int64_t c = std::max<int64_t>((g + N - 2) / (N - 1) * G, n - g * G);
                    if (c < best) { best = c; bs = g; }
                }
                CHECK(S == bs, "chain %d n %ld: plan %ld groups, best accepted %ld", t, (long)n, (long)S, (long)bs);
                CHECK(S == 0 || ch.fits(S * G, true), "chain %d n %ld: the plan's %ld groups do not fit", t, (long)n, (long)S);
                ++plans;
            }
        }
        std::printf("room: Codex's counterexample (capacities 8 and 10) and %ld random chains (%ld with held copies reused past the "
                    "budget), %ld plans checked\n", chains, reused, plans);
    }
    std::printf(fails ? "test_shard_plan: %d FAILED\n" : "test_shard_plan: all passed\n", fails);
    return fails != 0;
}
