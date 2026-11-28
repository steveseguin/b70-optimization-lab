// Host-only checks: g++ -std=c++20 -O2 tools/test_live_plan.cpp -o /tmp/test_live_plan && /tmp/test_live_plan
#include "../src/live_plan.hpp"
#include <cstdio>
#include <utility>
#include <vector>

using namespace ink;
static int fails = 0;
#define CHECK(c) do { if (!(c)) { ++fails; std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)

template <class F> static bool throws(F f) {
    try { f(); } catch (const std::exception &) { return true; }
    return false;
}

int main() {
    for (int n = 1; n <= 4096; ++n) {
        const int q0 = live_tail_q0(n);
        CHECK(q0 >= 0 && q0 < n);
        if (n < 15) CHECK(q0 == 0);
        else {
            CHECK(q0 % 8 == 0);
            CHECK(q0 <= n - 7);       // every live ffn_tail row has its full attention history
            CHECK(n - q0 >= 7 && n - q0 <= 14);
        }
    }
    CHECK(live_tail_q0(14) == 0);
    CHECK(live_tail_q0(15) == 8);
    CHECK(live_tail_q0(16) == 8);
    CHECK(live_tail_q0(22) == 8);
    CHECK(live_tail_q0(23) == 16);
    CHECK(live_tail_q0(1024) == 1016);

    CHECK(!dead_prompt_chunk(100, 0, 84, 0));
    CHECK(dead_prompt_chunk(100, 0, 84, 16));   // exactly ring tokens follow
    CHECK(!dead_prompt_chunk(100, 0, 85, 16));  // one token too few
    CHECK(!dead_prompt_chunk(100, 84, 16, 16)); // live suffix
    CHECK(!dead_prompt_chunk(100, 101, 0, 16));
    CHECK(!dead_prompt_chunk(100, 99, 2, 16));
    const std::vector<std::pair<std::size_t, std::size_t>> chunks = {{0, 37}, {37, 31}, {68, 32}};
    CHECK(dead_prompt_chunk(100, chunks[0].first, chunks[0].second, 33));
    CHECK(!dead_prompt_chunk(100, chunks[1].first, chunks[1].second, 33));
    CHECK(!dead_prompt_chunk(100, chunks[2].first, chunks[2].second, 33));

    const std::vector<int> required = {1, 4, 7}, extra = {2, 7, 99, -1};
    const int fv[3] = {3, 7, -1};
    CHECK(pipeline_carry_rows(required, extra, fv, true, true, 8) == (std::vector<int>{1, 2, 3, 4, 7}));
    CHECK(pipeline_carry_rows(required, extra, fv, true, false, 8) == required);
    CHECK(pipeline_carry_rows(required, extra, fv, false, true, 8) == (std::vector<int>{1, 2, 4, 7}));
    CHECK(pipeline_carry_rows({7, 1, 4, 7}, extra, fv, true, false, 8) == required);

    // relative-bias distances (attn_prep INK_BIAS_LIVE): the written segments hold every distance any row of the step
    // reads (keys j in [lo, p], lo >= 0, entries p - j below ext), whole segments, no segment more than needed
    for (int ext : {128, 1024, 2048})
        for (int pmax = -2; pmax <= 2 * ext + 300; ++pmax) {
            const int live = bias_live_dist(ext, pmax), segs = bias_segs(ext, live, 128);
            CHECK(live >= 1 && live <= ext);
            if (pmax >= 0) CHECK(live == std::min(ext, pmax + 1));
            else CHECK(live == ext);
            CHECK(segs >= 1 && segs <= ext / 128);
            CHECK(segs * 128 >= live && (segs - 1) * 128 < live);
            for (int win : {0, 1024})
                for (int p = std::max(0, pmax - 8); p <= pmax; ++p) { // a row's furthest key: lo = max(0, p - win + 1)
                    const int lo = win > 0 ? std::max(0, p - win + 1) : 0, far = std::min(p - lo, ext - 1);
                    CHECK(far < live && far < segs * 128);
                }
        }
    CHECK(bias_live_dist(1024, 0) == 1 && bias_segs(1024, 1, 128) == 1);
    CHECK(bias_live_dist(1024, 39) == 40 && bias_segs(1024, 40, 128) == 1);
    CHECK(bias_live_dist(1024, 127) == 128 && bias_segs(1024, 128, 128) == 1);
    CHECK(bias_live_dist(1024, 128) == 129 && bias_segs(1024, 129, 128) == 2);
    CHECK(bias_live_dist(1024, 293) == 294 && bias_segs(1024, 294, 128) == 3);
    CHECK(bias_live_dist(1024, 1022) == 1023 && bias_segs(1024, 1023, 128) == 8);
    CHECK(bias_live_dist(1024, 1023) == 1024 && bias_live_dist(1024, 1024) == 1024 && bias_live_dist(1024, 1 << 30) == 1024);
    CHECK(bias_segs(1024, 0, 128) == 8 && bias_segs(1024, -5, 128) == 8 && bias_segs(1024, 1024, 128) == 8 && bias_segs(1024, 5000, 128) == 8);

    CHECK(live_parse_flag("INK_TEST", nullptr, true));
    CHECK(!live_parse_flag("INK_TEST", "0", true));
    CHECK(live_parse_flag("INK_TEST", "1", false));
    for (const char *s : {"", "00", "2", "-1", "true", " 1", "1 "}) CHECK(throws([&] { live_parse_flag("INK_TEST", s, true); }));

    CHECK(wo_tail_parse(nullptr) == 2);
    CHECK(wo_tail_parse("0") == 0 && wo_tail_parse("1") == 1 && wo_tail_parse("2") == 2);
    for (const char *s : {"", "3", "-1", "00", "02", "2 ", " 1", "1x", "on", "true"}) CHECK(throws([&] { wo_tail_parse(s); }));

    if (fails) std::printf("%d checks failed\n", fails);
    else std::printf("live_plan: PASS\n");
    return fails != 0;
}
