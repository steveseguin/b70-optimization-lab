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

    CHECK(live_parse_flag("INK_TEST", nullptr, true));
    CHECK(!live_parse_flag("INK_TEST", "0", true));
    CHECK(live_parse_flag("INK_TEST", "1", false));
    for (const char *s : {"", "00", "2", "-1", "true", " 1", "1 "}) CHECK(throws([&] { live_parse_flag("INK_TEST", s, true); }));

    if (fails) std::printf("%d checks failed\n", fails);
    else std::printf("live_plan: PASS\n");
    return fails != 0;
}
