#pragma once
// Partner slice lengths for shared cache copies (Engine::shard_copy_start; notes/2026-11-28-balanced-shard-layout.md).
// Host arithmetic only, no SYCL: tools/test_shard_plan.cpp checks it with any C++20 compiler.
//
// A chain of N engines shares a context of n positions: partner r of an owner's ring folds positions
// [off[r], off[r + 1]) of its full-context applications, the owner itself [off[P], n). Every boundary is a whole group
// of SHARD_Q = 16,384 positions (128 blocks of 128 keys), the boundary at which the chunked fold carries its state
// (attn_flash_sum b0 % 128 == 0), and the slices follow one another in position order, so the fold takes the same
// 128-block groups in the same order as one card and gives the same bits whatever the lengths.
//
// The card memory is the same for every partner whatever the lengths: each engine is partner r of exactly one owner
// for every r (the ring is a rotation), so every engine holds copies of positions [0, off[P]) once, one owner's slice
// at each offset. Room therefore limits off[P] only.
#include <algorithm>
#include <climits>
#include <cstdint>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>

namespace ink {

constexpr int SHARD_Q = 16384; // positions of a fold group (128 blocks x 128 keys)

inline int64_t shard_sum(const std::vector<int> &l) {
    int64_t c = 0;
    for (int v : l) c += v;
    return c;
}

// cumulative offsets of lengths l (off[0] = 0, off[l.size()] = their sum), summed in 64 bits: throws on a negative
// length or a sum past INT_MAX (the offsets index int positions)
inline std::vector<int> shard_offsets(const std::vector<int> &l) {
    std::vector<int> off(l.size() + 1, 0);
    int64_t c = 0;
    for (size_t r = 0; r < l.size(); ++r) {
        if (l[r] < 0) throw std::runtime_error("shard: a negative slice length");
        c += l[r];
        if (c > INT_MAX) throw std::runtime_error("shard: the slices together past " + std::to_string(INT_MAX) + " positions");
        off[r + 1] = (int)c;
    }
    return off;
}

// The checks shard_copy_start makes before it forms offsets or allocates: 1 to N - 1 slices, each a positive whole
// number of groups, together (summed in 64 bits) at most n - ext (the rows past the shared positions by the
// relative-bias extent). Returns the offsets
inline std::vector<int> shard_check_lengths(const std::vector<int> &len, int N, int64_t n, int ext) {
    const int P = (int)len.size();
    if (N < 2) throw std::runtime_error("INK_SHARD_COPY: a chain of engines");
    if (P < 1 || P > N - 1) throw std::runtime_error("INK_SHARD_COPY: 1 to engines - 1 partner slices");
    int64_t c = 0;
    for (int v : len) {
        if (v <= 0 || v % SHARD_Q) throw std::runtime_error("INK_SHARD_COPY: slices of whole 16384-position groups");
        c += v;
    }
    if (ext < 0 || n - ext < 0 || c > n - ext)
        throw std::runtime_error("INK_SHARD_COPY: the slices together (" + std::to_string(c) + ") past the context less the relative extent (" +
                                 std::to_string(n) + " - " + std::to_string(ext) + ")");
    return shard_offsets(len);
}

// Balanced lengths for n positions on N engines (N - 1 partners): the S groups copied in total minimise the longest
// scan, max(ceil(S / (N - 1)) groups on a partner, n - S x 16,384 on the owner), the fewest copied groups among equal
// longest scans (less to copy at setup and fewer partner hand-offs). Constraints: S x 16,384 + ext <= n (the rows
// past the shared positions by at least the relative-bias extent, Engine::step) and S <= gmax when gmax >= 0 (room).
// gextra >= 0: S = gextra is allowed too even past gmax (room: the copies the cards hold now, reused as they are,
// shard_room_search). The S groups go floor(S / P) to each partner and one more to S mod P of them: the first ones
// (mode 1) or the last ones (mode 2). Partners without a group are left out (a shorter ring). Empty: nothing to copy.
inline std::vector<int> shard_plan_balanced(int64_t n, int N, int ext, int mode, int64_t gmax = -1, int64_t gextra = -1) {
    const int64_t Q = SHARD_Q;
    const int P = N - 1;
    if (P < 1 || n <= 0) return {};
    int64_t smax = n - ext >= 0 ? (n - ext) / Q : 0;
    if (smax > INT_MAX / Q) smax = INT_MAX / Q; // (the offsets are ints)
    if (gmax >= 0) smax = std::min(smax, std::max(gmax, gextra));
    int64_t best_s = 0, best_c = n;
    for (int64_t S = 1; S <= smax; ++S) {
        if (gmax >= 0 && S > gmax && S != gextra) continue; // (past the room for new buffers, and not the ones held)
        const int64_t part = (S + P - 1) / P * Q, own = n - S * Q, c = part > own ? part : own;
        if (c < best_c) { best_c = c; best_s = S; } // (strictly less: the smallest S of equal cost)
    }
    std::vector<int> l;
    if (!best_s) return l;
    const int64_t q = best_s / P, rem = best_s % P;
    for (int r = 0; r < P; ++r) {
        const bool extra = mode == 2 ? r >= P - rem : r < rem;
        const int64_t g = q + (extra ? 1 : 0);
        if (g) l.push_back((int)(g * Q));
    }
    return l;
}

// The most groups g in 0 .. gcap with fits(g), fits true up to some g and false past it (room grows with the
// positions), by bisection: about log2(gcap) calls of fits. 0 when not even one group fits
template <class F> inline int64_t shard_max_groups(int64_t gcap, F fits) {
    int64_t lo = 0, hi = gcap < 0 ? 0 : gcap;
    while (lo < hi) {
        const int64_t mid = lo + (hi - lo + 1) / 2;
        if (fits(mid)) lo = mid;
        else hi = mid - 1;
    }
    return lo;
}

// Room for copies (Engine::shard_copy_room, which applies this to every engine of a chain and sums it per card): the
// bytes engine x's card needs for copies of cpos positions, f buffers each of keys [cpos][kd] and values [kd][cvld]
// (cvld: cpos rounded up to 16) of halves, in place of the hf buffers of hpos positions (value stride hvld) it holds,
// plus its shared-step buffers not allocated yet (missing). check: whether that card is checked against its limit
// at all. reuse true: held buffers of exactly this size are kept, so only the missing step bytes are new, and a card
// with none missing is not checked (the reserve is not asked of memory already held). reuse false: every size counts
// as new buffers replacing the held ones and every card is checked; that need only grows with cpos (the budget
// shard_room_search bisects), where the reuse form does not: with 4 groups held and the card past its reserve, 1, 2 and
// 4 groups pass and 3 fails (tools/test_shard_plan.cpp)
constexpr size_t SHARD_HALF = 2; // (bytes of a sycl::half)
inline size_t shard_copy_bytes(int64_t cpos, size_t f, int kd, int64_t vld) {
    return f * ((size_t)cpos * (size_t)kd + (size_t)kd * (size_t)vld) * SHARD_HALF;
}
struct ShardRoomNeed {
    long long add = 0;
    bool check = false;
};
inline ShardRoomNeed shard_room_need(int64_t cpos, size_t f, int kd, int64_t hpos, size_t hf, int64_t hvld, size_t missing, bool reuse) {
    const bool chg = !reuse || hpos != cpos || hf != f;
    ShardRoomNeed r;
    r.add = (long long)missing;
    if (chg) r.add += (long long)shard_copy_bytes(cpos, f, kd, (cpos + 15) / 16 * 16) - (long long)shard_copy_bytes(hpos, hf, kd, hvld);
    r.check = chg || r.add != 0;
    return r;
}

// The groups a plan may take: 1 .. g_replace as new buffers (the most whose replacement need fits: monotone, so a
// bisection), and g_exact (-1: none) when every engine holds whole copy buffers of g_exact groups that fit as they are
// and g_exact is past g_replace. Every other size needs new buffers and fails the replacement check that g_replace
// bounds, so these are exactly the sizes the room check accepts (a smaller layout than the held one does not always
// fit: its buffers are new, and a card past its reserve refuses them)
struct ShardRoom {
    int64_t g_replace = 0;
    int64_t g_exact = -1;
};
template <class F, class H> inline ShardRoom shard_room_search(int64_t gcap, F fits_replace, int64_t held_g, H fits_held) {
    ShardRoom r;
    r.g_replace = shard_max_groups(gcap, fits_replace);
    if (held_g > r.g_replace && held_g <= gcap && fits_held()) r.g_exact = held_g;
    return r;
}

// A whole-token unsigned decimal (digits only: no sign, space, or suffix; at most 18 digits, so no overflow) in
// lo .. hi; anything else throws, naming the variable
inline int64_t shard_parse_int(const char *name, const char *v, int64_t lo, int64_t hi) {
    const std::string s = v ? v : "";
    auto bad = [&](const char *why) {
        return std::runtime_error(std::string(name) + "='" + s + "': " + why + " (a whole number " + std::to_string(lo) + " to " +
                                  std::to_string(hi) + ")");
    };
    if (s.empty()) throw bad("empty");
    if (s.size() > 18 || s.find_first_not_of("0123456789") != std::string::npos) throw bad("not a number");
    int64_t x = 0;
    for (char ch : s) x = x * 10 + (ch - '0');
    if (x < lo || x > hi) throw bad("out of range");
    return x;
}

// INK_SHARD_SPLIT=<l0,l1,...>: lengths given in ring order (a screen of other layouts; 1 to N - 1 of them, each a
// positive multiple of 16384). Every field must be a whole number: empty fields ("a,,b", "a,", ",a") and "" throw
inline std::vector<int> shard_parse_split(const char *v, int N) {
    const std::string s = v ? v : "";
    std::vector<int> l;
    size_t p = 0;
    for (;;) {
        size_t c = s.find(',', p);
        if (c == std::string::npos) c = s.size();
        const std::string t = s.substr(p, c - p);
        const int64_t x = shard_parse_int("INK_SHARD_SPLIT field", t.c_str(), SHARD_Q, INT_MAX / SHARD_Q * SHARD_Q);
        if (x % SHARD_Q) throw std::runtime_error("INK_SHARD_SPLIT='" + s + "': " + t + " is not a multiple of 16384");
        l.push_back((int)x);
        if (c == s.size()) break;
        p = c + 1;
    }
    if (N < 2 || (int)l.size() > N - 1)
        throw std::runtime_error("INK_SHARD_SPLIT='" + s + "': 1 to " + std::to_string(N - 1) + " lengths on " + std::to_string(N) + " engines");
    return l;
}

// The sharing switches, read once and checked whole:
//   INK_SHARD_BAL       0 the uniform slices of s (as before 2026-11-28), 1 (unset) balanced, extra groups on the first
//                       partners, 2 on the last
//   INK_SHARD_PARTNERS  k = 0 .. N - 1: over the owner and its first k partners only; 0 shares nothing (no copies and
//                       no moved fallback); unset: all N - 1
//   INK_SHARD_SPLIT     given lengths (screen runs only: INK_SHARD_COPY in ink_run; serving ignores it, split_ignored)
// Malformed, empty or out-of-range values throw; SPLIT together with PARTNERS throws (two layouts asked for)
struct ShardEnv {
    int bal = 1;
    int partners = -1;          // (-1: unset, every engine)
    bool split_set = false;     // (screen: split holds the lengths)
    bool split_ignored = false; // (not a screen: INK_SHARD_SPLIT is set and not used)
    std::vector<int> split;
};
inline ShardEnv shard_env_from(const char *bal, const char *partners, const char *split, int N, bool screen) {
    ShardEnv e;
    if (N < 2) throw std::runtime_error("shard: a chain of engines");
    if (bal) e.bal = (int)shard_parse_int("INK_SHARD_BAL", bal, 0, 2);
    if (partners) e.partners = (int)shard_parse_int("INK_SHARD_PARTNERS", partners, 0, N - 1);
    if (split) {
        if (!screen) e.split_ignored = true;
        else {
            if (partners) throw std::runtime_error("INK_SHARD_SPLIT and INK_SHARD_PARTNERS: set one of them");
            e.split = shard_parse_split(split, N);
            e.split_set = true;
        }
    }
    return e;
}
inline ShardEnv shard_env(int N, bool screen) {
    return shard_env_from(std::getenv("INK_SHARD_BAL"), std::getenv("INK_SHARD_PARTNERS"), std::getenv("INK_SHARD_SPLIT"), N, screen);
}

// The layout the switches select at n positions on N engines (ext the relative extent): s the uniform slice (mode 0;
// s <= 0: none), gfit the most groups that fit on the cards as new buffers (-1: no limit) and gheld the held ones that
// fit as they are (-1: none; ShardRoom), the balanced modes only: the uniform and given layouts are taken as asked and
// shard_copy_start throws when they do not fit. mode: what was selected, for the logs. Empty len: nothing to copy
// (mode says why)
struct ShardPlan {
    std::vector<int> len;
    std::string mode;
};
inline ShardPlan shard_plan(const ShardEnv &e, int64_t n, int N, int ext, int s, int64_t gfit = -1, int64_t gheld = -1) {
    ShardPlan p;
    if (e.partners == 0) { p.mode = "off: INK_SHARD_PARTNERS=0"; return p; }
    if (e.split_set) { p.len = e.split; p.mode = "given"; return p; }
    const std::string ks = e.partners > 0 ? ", " + std::to_string(e.partners) + " partners" : std::string();
    if (e.bal == 0) {
        const int P = e.partners > 0 ? e.partners : N - 1;
        if (s > 0) p.len.assign((size_t)P, s);
        p.mode = "uniform" + ks + (s > 0 ? std::string() : ": no slice");
        return p;
    }
    const int Ne = e.partners > 0 ? e.partners + 1 : N;
    p.mode = std::string(e.bal == 2 ? "balanced, last" : "balanced") + ks;
    p.len = shard_plan_balanced(n, Ne, ext, e.bal, gfit, gheld);
    if (gfit >= 0 && shard_sum(p.len) < shard_sum(shard_plan_balanced(n, Ne, ext, e.bal)))
        p.mode += p.len.empty() ? ": no room" : ", room-limited";
    else if (p.len.empty()) p.mode += ": no group below the context";
    return p;
}

// "l0+l1+...+owner o (mode)": a layout for the logs
inline std::string shard_layout_str(const std::vector<int> &l, int64_t n, const std::string &mode) {
    std::string r;
    for (size_t i = 0; i < l.size(); ++i) r += (i ? "+" : "") + std::to_string(l[i]);
    return r + " + owner " + std::to_string(n - shard_sum(l)) + " (" + mode + ")";
}

} // namespace ink
