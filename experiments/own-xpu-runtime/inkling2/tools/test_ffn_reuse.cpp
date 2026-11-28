// Host-only bit-exact model of ffn_tail and ffn_tail_reuse (same-sequence ntok = 2..8).
// Build: g++ -std=c++20 -O1 -g -Wall -Wextra -Werror -ffp-contract=off -fsanitize=address,undefined tools/test_ffn_reuse.cpp -o /tmp/test_ffn_reuse && /tmp/test_ffn_reuse
// The two phases below model the work-group barrier. Full buffers, guards and unused states are compared as FP32 words.
// A null residual is the requested zero-residual case; Engine's live calls always provide a residual pointer.
#include "../src/live_plan.hpp"
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

namespace {
constexpr int TC = 16, MAXTOK = 8, NU = 8, NS = 5, OFF = 5;
constexpr size_t GUARD = 7;
constexpr uint32_t POISON_BITS = 0x7fc5a17eu;
constexpr float POISON = std::bit_cast<float>(POISON_BITS);
int fails = 0, configurations = 0;
size_t compared_words = 0;

#define CHECK(c, ...) do { if (!(c)) { ++fails; std::printf("FAIL %s:%d: ", __FILE__, __LINE__); std::printf(__VA_ARGS__); std::printf("\n"); } } while (0)

struct YSeg {
    const float *ys = nullptr;
    const int32_t *sloc = nullptr;
    int nseg = 0, mmax = 0;
};

struct Case {
    int E = 0, ntok = 0;
    bool segmented = false, save_tokens = false, residual = false, with_escale = false;
    size_t sst = 0;
    float scale = 0;
    std::vector<float> y, ys, escale, w, cw, st_in, fi;
    std::vector<int32_t> ids, sloc;
};

struct Result {
    std::vector<float> ffn, out, st_out, st_tok;
    size_t combines = 0;
};

static float mac(float acc, float a, float b) {
#ifdef INK_NO_FMA
    const float p = a * b;
    return acc + p;
#else
    return std::fma(a, b, acc);
#endif
}

static float conv_out(const float *win, const float *w, int c, float scale) {
    float s = 0.0f;
    for (int i = 0; i < 4; ++i) s = mac(s, win[i], w[c * 4 + i]);
    return (win[3] + s) * scale;
}

static void conv_save(float *st, int off, int c, const float *win) {
    for (int k = 0; k < 3; ++k) st[(size_t)(off + c) * 3 + k] = win[1 + k];
}

// Verbatim arithmetic and read/order structure of fused.hpp's flat fast path (nu == 8).
static float combine(const float *y, const float *escale, const int32_t *ids, const float *w, int nu, int n, int t, int c) {
    float yv[8], wv[8], ev[8];
    int iv[8];
    for (int k = 0; k < 8; ++k) {
        const int s = t * nu + (k < nu ? k : 0);
        yv[k] = y[(size_t)s * n + c];
        wv[k] = w[s];
        iv[k] = ids[s];
    }
    for (int k = 0; k < 8; ++k) ev[k] = escale ? escale[iv[k]] : 1.0f;
    float acc = 0.0f;
    for (int k = 0; k < 8; ++k) {
        if (k >= nu) break;
        float v = yv[k];
        if (escale) v = v * ev[k];
        v = v * wv[k];
        acc = k == 0 ? v : acc + v;
    }
    return acc;
}

// Verbatim arithmetic and read/order structure of fused.hpp's specialized nu == 8, nseg == 5 path.
static float combine_seg(YSeg sg, const float *escale, const int32_t *ids, const float *w, int nu, int n, int t, int c) {
    if (nu == 8 && sg.nseg == 5) {
        int loc[8];
        float wv[8], ev[8], v[8][5];
        for (int k = 0; k < 8; ++k) {
            const int s = t * 8 + k;
            loc[k] = sg.sloc[s];
            wv[k] = w[s];
            ev[k] = escale ? escale[ids[s]] : 1.0f;
        }
        for (int k = 0; k < 8; ++k) {
            const int tl = loc[k] >> 4, r = loc[k] & 15;
            for (int g = 0; g < 5; ++g) v[k][g] = sg.ys[((size_t)(tl * 5 + g) * sg.mmax + r) * n + c];
        }
        float acc = 0.0f;
        for (int k = 0; k < 8; ++k) {
            float y = 0.0f;
            for (int g = 0; g < 5; ++g) y = y + v[k][g];
            if (escale) y = y * ev[k];
            y = y * wv[k];
            acc = k == 0 ? y : acc + y;
        }
        return acc;
    }
    std::printf("test only exercises nu = 8, nseg = 5 YSeg\n");
    std::abort();
}

static float generated(size_t i, uint32_t salt) {
    switch ((i + 3u * salt) % 37u) {
        case 0: return 0.0f;
        case 1: return -0.0f;
        case 2: return std::bit_cast<float>(0x00000001u); // positive subnormal
        case 3: return std::bit_cast<float>(0x80000001u); // negative subnormal
        case 4: return std::bit_cast<float>(0x00000002u);
        case 5: return std::bit_cast<float>(0x80000002u);
        case 6: return std::bit_cast<float>(0x00800000u); // minimum normal
        case 7: return std::bit_cast<float>(0x80800000u);
        case 8: return std::bit_cast<float>(0x00800002u);
        default: break;
    }
    uint32_t x = (uint32_t)i * 0x9e3779b9u + salt * 0x85ebca6bu;
    x ^= x >> 16;
    x *= 0x7feb352du;
    x ^= x >> 15;
    const int v = (int)(x % 2001u) - 1000;
    return (float)v / 257.0f;
}

static Case make_case(int E, int ntok, bool segmented, bool save_tokens, bool residual, bool with_escale) {
    Case c;
    c.E = E;
    c.ntok = ntok;
    c.segmented = segmented;
    c.save_tokens = save_tokens;
    c.residual = residual;
    c.with_escale = with_escale;
    c.sst = (size_t)(OFF + E) * 3 + 11; // padding catches stride mistakes
    c.scale = 1.0f / std::sqrt(5.0f);
    const int K = ntok * NU;
    c.y.resize((size_t)K * E);
    for (size_t i = 0; i < c.y.size(); ++i) c.y[i] = generated(i, 1);
    c.ids.resize(K);
    c.sloc.resize(K);
    c.w.resize(K);
    for (int t = 0; t < ntok; ++t)
        for (int k = 0; k < NU; ++k) {
            const int s = t * NU + k;
            c.ids[s] = (s * 11 + t * 3) % 16;
            c.sloc[s] = (s << 4) | t; // unique tile per slot, token row r; mmax = 8
            c.w[s] = generated((size_t)s, 2);
        }
    if (with_escale) {
        c.escale.resize(16);
        for (size_t i = 0; i < c.escale.size(); ++i) c.escale[i] = generated(i, 3);
    }
    if (segmented) {
        c.ys.resize((size_t)K * NS * MAXTOK * E);
        for (int s = 0; s < K; ++s)
            for (int g = 0; g < NS; ++g)
                for (int t = 0; t < MAXTOK; ++t)
                    for (int ch = 0; ch < E; ++ch) {
                        const size_t i = (((size_t)(s * NS + g) * MAXTOK + t) * E + ch);
                        c.ys[i] = generated(i, 4);
                    }
    }
    c.cw.resize((size_t)E * 4);
    for (size_t i = 0; i < c.cw.size(); ++i) c.cw[i] = generated(i, 5);
    c.st_in.resize((size_t)(OFF + E) * 3);
    for (size_t i = 0; i < c.st_in.size(); ++i) c.st_in[i] = generated(i, 6);
    if (residual) {
        c.fi.resize((size_t)ntok * E);
        for (size_t i = 0; i < c.fi.size(); ++i) c.fi[i] = generated(i, 7);
    }
    return c;
}

static YSeg yseg(const Case &c) {
    return c.segmented ? YSeg{c.ys.data(), c.sloc.data(), NS, MAXTOK} : YSeg{};
}

static Result make_result(const Case &c) {
    Result r;
    const size_t n = (size_t)c.ntok * c.E, ns = (size_t)(OFF + c.E) * 3;
    r.ffn.assign(GUARD + n + GUARD, POISON);
    r.out.assign(GUARD + n + GUARD, POISON);
    r.st_out.assign(GUARD + ns + GUARD, POISON);
    if (c.save_tokens) r.st_tok.assign(GUARD + (MAXTOK + 1) * c.sst + GUARD, POISON);
    return r;
}

static void tail_reference(const Case &c, Result &r) {
    const YSeg sg = yseg(c);
    const float *escale = c.with_escale ? c.escale.data() : nullptr;
    const float *fi = c.residual ? c.fi.data() : nullptr;
    float *st_tok = c.save_tokens ? r.st_tok.data() + GUARD : nullptr;
    auto comb = [&](int t, int ch) {
        ++r.combines;
        return sg.ys ? combine_seg(sg, escale, c.ids.data(), c.w.data(), NU, c.E, t, ch)
                     : combine(c.y.data(), escale, c.ids.data(), c.w.data(), NU, c.E, t, ch);
    };
    for (int t = 0; t < c.ntok; ++t)
        for (int ch = 0; ch < c.E; ++ch) {
            float win[4];
            for (int i = 0; i < 4; ++i) {
                const int tt = t - 3 + i;
                win[i] = tt >= 0 ? comb(tt, ch) : c.st_in[(size_t)(OFF + ch) * 3 + (3 + tt)];
            }
            const float o = conv_out(win, c.cw.data(), ch, c.scale);
            const size_t i = (size_t)t * c.E + ch;
            r.ffn[GUARD + i] = o;
            r.out[GUARD + i] = fi ? fi[i] + o : o;
            if (t == c.ntok - 1) conv_save(r.st_out.data() + GUARD, OFF, ch, win);
            else if (st_tok) conv_save(st_tok + (size_t)t * c.sst, OFF, ch, win);
        }
}

static void tail_reuse(const Case &c, Result &r) {
    const YSeg sg = yseg(c);
    const float *escale = c.with_escale ? c.escale.data() : nullptr;
    const float *fi = c.residual ? c.fi.data() : nullptr;
    float *st_tok = c.save_tokens ? r.st_tok.data() + GUARD : nullptr;
    for (int c0 = 0; c0 < c.E; c0 += TC) {
        std::array<float, MAXTOK * TC> comb;
        comb.fill(POISON);
        // Phase 1: all live (t, local channel) lanes store exactly one rounded combine.
        for (int t = 0; t < c.ntok; ++t)
            for (int lc = 0; lc < TC; ++lc) {
                const int ch = c0 + lc;
                if (ch >= c.E) continue; // channel-padding lanes still reach the modeled barrier
                ++r.combines;
                comb[(size_t)t * TC + lc] = sg.ys ? combine_seg(sg, escale, c.ids.data(), c.w.data(), NU, c.E, t, ch)
                                                  : combine(c.y.data(), escale, c.ids.data(), c.w.data(), NU, c.E, t, ch);
            }
        // The unconditional group barrier is here. No lane returned before it.
        for (int t = 0; t < c.ntok; ++t)
            for (int lc = 0; lc < TC; ++lc) {
                const int ch = c0 + lc;
                if (ch >= c.E) {
                    CHECK(std::bit_cast<uint32_t>(comb[(size_t)t * TC + lc]) == POISON_BITS,
                          "SLM padding written: E %d ntok %d c0 %d t %d lc %d", c.E, c.ntok, c0, t, lc);
                    continue;
                }
                float win[4];
                for (int i = 0; i < 4; ++i) {
                    const int tt = t - 3 + i;
                    win[i] = tt >= 0 ? comb[(size_t)tt * TC + lc] : c.st_in[(size_t)(OFF + ch) * 3 + (3 + tt)];
                }
                const float o = conv_out(win, c.cw.data(), ch, c.scale);
                const size_t i = (size_t)t * c.E + ch;
                r.ffn[GUARD + i] = o;
                r.out[GUARD + i] = fi ? fi[i] + o : o;
                if (t == c.ntok - 1) conv_save(r.st_out.data() + GUARD, OFF, ch, win);
                else if (st_tok) conv_save(st_tok + (size_t)t * c.sst, OFF, ch, win);
            }
    }
}

static void same_words(const char *name, const std::vector<float> &a, const std::vector<float> &b, const Case &c) {
    CHECK(a.size() == b.size(), "%s size: E %d ntok %d", name, c.E, c.ntok);
    if (a.size() != b.size()) return;
    for (size_t i = 0; i < a.size(); ++i) {
        ++compared_words;
        if (std::bit_cast<uint32_t>(a[i]) == std::bit_cast<uint32_t>(b[i])) continue;
        ++fails;
        std::printf("FAIL %s[%zu]: E %d ntok %d seg %d st_tok %d res %d escale %d: %08x != %08x\n", name, i, c.E,
                    c.ntok, c.segmented, c.save_tokens, c.residual, c.with_escale, std::bit_cast<uint32_t>(a[i]),
                    std::bit_cast<uint32_t>(b[i]));
        return;
    }
}

static void run_case(int E, int ntok, bool segmented, bool save_tokens, bool residual, bool with_escale) {
    ++configurations;
    const Case c = make_case(E, ntok, segmented, save_tokens, residual, with_escale);
    Result ref = make_result(c), got = make_result(c);
    tail_reference(c, ref);
    tail_reuse(c, got);
    same_words("ffn_out", ref.ffn, got.ffn, c);
    same_words("out", ref.out, got.out, c);
    same_words("st_out", ref.st_out, got.st_out, c);
    same_words("st_tok+untouched", ref.st_tok, got.st_tok, c);
    size_t ref_combines = 0;
    for (int t = 0; t < ntok; ++t) ref_combines += (size_t)E * std::min(t + 1, 4);
    CHECK(ref.combines == ref_combines, "reference combines: got %zu expected %zu", ref.combines, ref_combines);
    CHECK(got.combines == (size_t)ntok * E, "reuse combines: got %zu expected %d", got.combines, ntok * E);
}

template <class F> static bool throws(F f) {
    try { f(); } catch (const std::exception &) { return true; }
    return false;
}

static void test_flag() {
    CHECK(ink::live_parse_flag("INK_FFN_REUSE", nullptr, true), "unset default");
    CHECK(!ink::live_parse_flag("INK_FFN_REUSE", "0", true), "zero disables");
    CHECK(ink::live_parse_flag("INK_FFN_REUSE", "1", false), "one enables");
    for (const char *s : {"", "00", "01", "2", "-1", "true", " 1", "1 "})
        CHECK(throws([&] { ink::live_parse_flag("INK_FFN_REUSE", s, true); }), "accepted invalid flag '%s'", s);
    setenv("INK_FFN_REUSE", "0", 1);
    CHECK(!ink::live_env_flag("INK_FFN_REUSE", true), "live_env_flag zero");
    setenv("INK_FFN_REUSE", "1", 1);
    CHECK(ink::live_env_flag("INK_FFN_REUSE", false), "live_env_flag one");
    unsetenv("INK_FFN_REUSE");
    CHECK(ink::live_env_flag("INK_FFN_REUSE", true), "live_env_flag unset");
}

} // namespace

int main() {
    test_flag();
    for (int ntok = 2; ntok <= MAXTOK; ++ntok)
        for (int E : {1, 16, 19, 37})
            for (bool segmented : {false, true})
                for (bool save_tokens : {false, true})
                    for (bool residual : {false, true}) {
                        const bool with_escale = ((ntok + E + segmented + save_tokens + residual) & 1) != 0;
                        run_case(E, ntok, segmented, save_tokens, residual, with_escale);
                    }
    if (fails) std::printf("%d checks failed across %d configurations\n", fails, configurations);
    else std::printf("ffn_reuse: PASS (%d configurations, %zu bitwise words, FMA %s)\n", configurations, compared_words,
#ifdef INK_NO_FMA
                     "off"
#else
                     "on"
#endif
    );
    return fails != 0;
}
