#pragma once
// Host-testable planning for final-application live rows, DSpark pipeline carries, the relative-bias distances a
// step reads and the ESIMD kernels' PE parts layout. No device state or arithmetic.
#include <algorithm>
#include <cstddef>
#include <cstdint>
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

// The relative-bias distances a step reads (attn_prep INK_BIAS_LIVE): a row at position p adds table entry p - j for its
// keys j in [lo, p], lo >= 0, and only below ext, so every entry read is under min(ext, pmax + 1), pmax the furthest row
// position of the step (pmax < 0: all ext).
inline int bias_live_dist(int ext, int pmax) { return pmax < 0 || pmax >= ext ? ext : pmax + 1; }
// attn_prep's table segments of seg distances (ext a multiple of seg) that hold [0, live): at least one (the first one
// also writes the clipped R row); live <= 0 or >= ext: all ext / seg.
inline int bias_segs(int ext, int live, int seg) { return live <= 0 || live >= ext ? ext / seg : (live + seg - 1) / seg; }

// The ESIMD kernels' parts layout "PE" (xmx_esimd.hpp splite) for a step of n <= 8 rows: rows padded to pe_mp(n) =
// 1, 2, 4 or 8 (Engine::with_mp's choice), value (t, k) at pe_index(mp, t, k) in each part, the parts cols * mp apart.
// splite's ((((g * 8 + j) * 2 + s) * MP + t) * 16 + e with g = k / 256, j = k % 256 / 32, s = k % 32 / 16, e = k % 16:
// (g * 8 + j) * 2 + s = k / 16.
inline int pe_mp(int n) { return n <= 1 ? 1 : n == 2 ? 2 : n <= 4 ? 4 : 8; }
inline std::size_t pe_index(int mp, int t, int k) { return ((std::size_t)(k >> 4) * mp + t) * 16 + (k & 15); }
// PE parts written by the kernel that makes the values (bfsplit.hpp pe_store; engine INK_WO_MR_PE): a step of m rows
// (mp = pe_mp(m)), a launch's row t is the step's row t0 + t; rows m..mp-1 are written as zeros by the launch holding
// row 0. pe null: none. pe_shape_ok: the host's check of a launch of n rows of cols values each.
struct PeOut { std::uint16_t *pe = nullptr; int mp = 0, m = 0, t0 = 0, cols = 0; };
inline bool pe_shape_ok(const PeOut &o, int n, int cols) {
    return !o.pe || (o.m >= 1 && o.m <= 8 && o.mp == pe_mp(o.m) && n >= 1 && n <= o.m && o.t0 >= 0 && o.t0 <= o.m - n &&
                     o.cols == cols && cols >= 256 && cols % 256 == 0);
}

inline bool live_parse_flag(const char *name, const char *text, bool def) {
    if (!text) return def;
    if (std::strcmp(text, "0") == 0) return false;
    if (std::strcmp(text, "1") == 0) return true;
    throw std::runtime_error(std::string(name) + "='" + text + "': expected 0 or 1");
}
inline bool live_env_flag(const char *name, bool def) { return live_parse_flag(name, std::getenv(name), def); }
// INK_WO_TAIL (engine wo_tail): unset 2, else exactly "0", "1" or "2"
inline int wo_tail_parse(const char *text) {
    if (!text) return 2;
    for (int v = 0; v <= 2; ++v)
        if (text[0] == '0' + v && text[1] == '\0') return v;
    throw std::runtime_error(std::string("INK_WO_TAIL='") + text + "': expected 0, 1 or 2");
}

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
