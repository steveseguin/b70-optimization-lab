#pragma once
// Host-testable planning for final-application live rows and DSpark pipeline carries. No device state or arithmetic.
#include <algorithm>
#include <cstddef>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace ink {

// live_q0's geometry: the last seven rows cover both four-tap convolutions; round down to attention's eight-row tile.
inline int live_tail_q0(int ntok) {
    constexpr int NEED = 2 * (4 - 1) + 1, MT = 8;
    return ntok < NEED + MT ? 0 : (ntok - NEED) / MT * MT;
}

// [p, p+n) is overwritten in every bounded drafter ring before this feed returns when at least ring tokens follow it.
inline bool dead_prompt_chunk(std::size_t N, std::size_t p, std::size_t n, int ring) {
    return ring > 0 && p <= N && n <= N - p && N - p - n >= (std::size_t)ring;
}

inline bool live_parse_flag(const char *name, const char *text, bool def) {
    if (!text) return def;
    if (std::strcmp(text, "0") == 0) return false;
    if (std::strcmp(text, "1") == 0) return true;
    throw std::runtime_error(std::string(name) + "='" + text + "': expected 0 or 1");
}
inline bool live_env_flag(const char *name, bool def) { return live_parse_flag(name, std::getenv(name), def); }

// required is carry_slots(a0): every target block/current/bank row. Drafter rows are added only for a live carry.
// A required row is never removed, including one numerically equal to a drafter feature row.
inline std::vector<int> pipeline_carry_rows(const std::vector<int> &required, const std::vector<int> &drafter_extra,
                                            const int *feat_vis, bool has_feat, bool with_drafter, int a0) {
    std::vector<int> v = required;
    auto add = [&](int x) { if (x >= 0 && x < a0) v.push_back(x); };
    if (with_drafter) {
        for (int x : drafter_extra) add(x);
        if (has_feat) for (int j = 0; j < 3; ++j) add(feat_vis[j]);
    }
    std::sort(v.begin(), v.end());
    v.erase(std::unique(v.begin(), v.end()), v.end());
    return v;
}

} // namespace ink
