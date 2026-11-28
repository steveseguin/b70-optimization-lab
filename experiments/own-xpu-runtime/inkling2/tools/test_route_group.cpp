// Host-only model of moe_route_sg + moe_group versus the fixed-eight-subgroup moe_route_group.
// Build: g++ -std=c++20 -O1 -g -ffp-contract=off -fsanitize=address,undefined -fno-omit-frame-pointer tools/test_route_group.cpp -o /tmp/test_route_group && /tmp/test_route_group
// The device proof is source identity for the subgroup body; this test models the 128-lane packed scan and scatter, then
// checks every output byte, including poisoned tails that the two-launch reference does not write.
#include "../src/live_plan.hpp"
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <random>
#include <string>
#include <vector>

namespace {
constexpr int SG = 16, PER = 8, MAXTOK = 8, MAXPICK = 8, MOE_TS = 16;
constexpr int32_t POISON = 0x51a7c0de;
int fails = 0, configurations = 0;

#define CHECK(c, ...) do { if (!(c)) { ++fails; std::printf("FAIL %s:%d: ", __FILE__, __LINE__); std::printf(__VA_ARGS__); std::printf("\n"); } } while (0)

struct Groups {
    std::vector<int32_t> count, exp, off, slots, ecount, ntiles, tile_exp, tile_s0, tile_n, sloc;
    Groups(int ne, int K, bool with_sloc)
        : count(1, POISON), exp(ne, POISON), off(ne + 1, POISON), slots(K, POISON), ecount(ne, POISON),
          ntiles(1, POISON), tile_exp(ne + K / MOE_TS, POISON), tile_s0(ne + K / MOE_TS, POISON),
          tile_n(ne + K / MOE_TS, POISON), sloc(with_sloc ? K : 0, POISON) {}
};
struct RouteResult {
    std::vector<int32_t> ids;
    std::vector<float> wts;
    Groups g;
    RouteResult(int ne, int K, bool with_sloc)
        : ids(K, POISON), wts(K, std::numeric_limits<float>::quiet_NaN()), g(ne, K, with_sloc) {}
};
struct Lane {
    float p[PER], sel[PER], lg[PER], bs[PER];
};

// The host mirror uses one fixed reduction order. Finite max/min are order-independent; the all-NaN case also checks
// the sentinel path and, importantly, that grouping never indexes a mask with that sentinel.
static float maximum(float a, float b) { return a < b ? b : a; }
static int minimum(int a, int b) { return b < a ? b : a; }
static std::vector<uint32_t> float_bits(const std::vector<float> &v) {
    std::vector<uint32_t> r;
    r.reserve(v.size());
    for (float x : v) r.push_back(std::bit_cast<uint32_t>(x));
    return r;
}

static Groups group_reference(const int32_t *ids, int K, int ne, bool with_sloc) {
    Groups g(ne, K, with_sloc);
    for (int e = 0; e < ne; ++e) {
        int c = 0;
        for (int s = 0; s < K; ++s) c += ids[s] == e;
        g.ecount[e] = c;
    }
    int start = 0, a = 0, t0 = 0;
    for (int e = 0; e < ne; ++e) {
        const int cnt = g.ecount[e];
        if (!cnt) continue;
        g.exp[a] = e;
        g.off[a] = start;
        const int nt = (cnt + MOE_TS - 1) / MOE_TS;
        int r = 0;
        for (int s = 0; s < K; ++s) {
            if (ids[s] != e) continue;
            g.slots[start + r] = s;
            if (with_sloc) g.sloc[s] = ((t0 + r / MOE_TS) << 4) | (r % MOE_TS);
            ++r;
        }
        for (int tile = 0; tile < nt; ++tile) {
            g.tile_exp[t0 + tile] = e;
            g.tile_s0[t0 + tile] = start + tile * MOE_TS;
            g.tile_n[t0 + tile] = std::min(MOE_TS, cnt - tile * MOE_TS);
        }
        start += cnt;
        ++a;
        t0 += nt;
    }
    g.count[0] = a;
    g.off[a] = K; // the reference uses K, not the number of matched ids (they differ for sentinel ids)
    g.ntiles[0] = t0;
    return g;
}

// Mirror the 128 private expert lanes, eight inclusive subgroup scans, the subgroup-totals barrier, and parallel scatter.
// The host loop order is only a simulation device: every lane's offsets come from scan/sums, never from another e's writes.
static Groups group_fused(const int32_t *selected, int K, int ne, bool with_sloc) {
    Groups g(ne, K, with_sloc);
    std::array<uint64_t, PER * SG> masks{};
    std::array<int, PER * SG> counts{}, tiles{}, scans{};
    std::array<int, MAXTOK> sums{};
    for (int e = 0; e < PER * SG; ++e) {
        if (e < ne)
            for (int s = 0; s < K; ++s)
                if (selected[s] == e) masks[e] |= uint64_t{1} << s;
        const int cnt = std::popcount(masks[e]);
        counts[e] = cnt;
        tiles[e] = (cnt + MOE_TS - 1) / MOE_TS;
        if (e < ne) g.ecount[e] = cnt;
        const int active = cnt > 0 ? 1 : 0;
        const int mine = active | (cnt << 7) | (tiles[e] << 14);
        scans[e] = (e % SG ? scans[e - 1] : 0) + mine;
        if (e % SG == SG - 1) sums[e / SG] = scans[e];
    }
    // The device has its second and last work-group barrier here.
    for (int e = 0; e < PER * SG; ++e) {
        int prefix = scans[e];
        for (int j = 0; j < e / SG; ++j) prefix += sums[j];
        const int cnt = counts[e], nt = tiles[e];
        const int a = (prefix & 127) - (cnt > 0 ? 1 : 0);
        const int start = ((prefix >> 7) & 127) - cnt;
        const int t0 = ((prefix >> 14) & 127) - nt;
        if (e == PER * SG - 1) {
            const int total_active = prefix & 127;
            g.count[0] = total_active;
            g.off[total_active] = K;
            g.ntiles[0] = (prefix >> 14) & 127;
        }
        if (!cnt) continue;
        g.exp[a] = e;
        g.off[a] = start;
        for (int tile = 0; tile < nt; ++tile) {
            g.tile_exp[t0 + tile] = e;
            g.tile_s0[t0 + tile] = start + tile * MOE_TS;
            g.tile_n[t0 + tile] = std::min(MOE_TS, cnt - tile * MOE_TS);
        }
        uint64_t m = masks[e];
        int r = 0;
        while (m) {
            const int s = std::countr_zero(m);
            g.slots[start + r] = s;
            if (with_sloc) g.sloc[s] = ((t0 + (r >> 4)) << 4) | (r & 15);
            ++r;
            m &= m - 1;
        }
    }
    return g;
}

// Independent reference layout: all 16 lanes are explicit, as in moe_route_sg's one-token work-group.
static RouteResult route_reference(const float *logits, const float *bias, int ne, int nu, float wscale, int ntok,
                                   bool with_sloc) {
    const int K = ntok * nu;
    RouteResult r(ne, K, with_sloc);
    for (int t = 0; t < ntok; ++t) {
        Lane v[SG];
        for (int lane = 0; lane < SG; ++lane) {
            for (int u = 0; u < PER; ++u) {
                const int e = std::min(lane + SG * u, ne - 1);
                v[lane].lg[u] = logits[(size_t)t * ne + e];
                v[lane].bs[u] = bias ? bias[e] : 0.0f;
            }
            for (int u = 0; u < PER; ++u) {
                const int e = lane + SG * u;
                v[lane].p[u] = 0.0f;
                v[lane].sel[u] = -INFINITY;
                if (e < ne) {
                    v[lane].p[u] = 1.0f / (1.0f + std::exp(-v[lane].lg[u]));
                    v[lane].sel[u] = bias ? v[lane].p[u] + v[lane].bs[u] : v[lane].p[u];
                }
            }
        }
        int pick[16];
        for (int k = 0; k < nu; ++k) {
            float lm[SG];
            int le[SG];
            for (int lane = 0; lane < SG; ++lane) {
                lm[lane] = v[lane].sel[0];
                int lu = 0;
                for (int u = 1; u < PER; ++u) {
                    if (v[lane].sel[u] > lm[lane]) { lm[lane] = v[lane].sel[u]; lu = u; }
                }
                le[lane] = lane + SG * lu;
            }
            float m = lm[0];
            for (int lane = 1; lane < SG; ++lane) m = maximum(m, lm[lane]);
            int bv[SG];
            for (int lane = 0; lane < SG; ++lane) bv[lane] = le[lane] < ne && lm[lane] == m ? le[lane] : PER * SG;
            int b = bv[0];
            for (int lane = 1; lane < SG; ++lane) b = minimum(b, bv[lane]);
            for (int lane = 0; lane < SG; ++lane)
                for (int u = 0; u < PER; ++u)
                    if (lane + SG * u == b) v[lane].sel[u] = -INFINITY;
            pick[k] = b;
        }
        float w[16], sum = 0.0f;
        for (int k = 0; k < nu; ++k) {
            const int b = pick[k], bu = b / SG, source = b % SG;
            float pv = v[source].p[0];
            for (int u = 1; u < PER; ++u) if (u == bu) pv = v[source].p[u];
            w[k] = pv;
            r.ids[t * nu + k] = b;
            sum += w[k];
        }
        sum = sum * 1.0f + 1e-20f;
        for (int k = 0; k < nu; ++k) r.wts[t * nu + k] = (w[k] / sum) * wscale;
    }
    r.g = group_reference(r.ids.data(), K, ne, with_sloc);
    return r;
}

// Fixed-eight-subgroup mirror. Inactive tokens execute no routing body; selected ids are the SLM handoff.
static RouteResult route_fused(const float *logits, const float *bias, int ne, int nu, float wscale, int ntok,
                               bool with_sloc) {
    const int K = ntok * nu;
    RouteResult r(ne, K, with_sloc);
    std::array<int32_t, MAXTOK * MAXPICK> selected;
    selected.fill(POISON);
    for (int t = 0; t < MAXTOK; ++t) {
        if (t >= ntok) continue;
        Lane v[SG];
        for (int lane = 0; lane < SG; ++lane) {
            for (int u = 0; u < PER; ++u) {
                const int e = std::min(lane + SG * u, ne - 1);
                v[lane].lg[u] = logits[(size_t)t * ne + e];
                v[lane].bs[u] = bias ? bias[e] : 0.0f;
            }
            for (int u = 0; u < PER; ++u) {
                const int e = lane + SG * u;
                v[lane].p[u] = 0.0f;
                v[lane].sel[u] = -INFINITY;
                if (e < ne) {
                    v[lane].p[u] = 1.0f / (1.0f + std::exp(-v[lane].lg[u]));
                    v[lane].sel[u] = bias ? v[lane].p[u] + v[lane].bs[u] : v[lane].p[u];
                }
            }
        }
        int pick[16];
        for (int k = 0; k < nu; ++k) {
            float lm[SG];
            int le[SG];
            for (int lane = 0; lane < SG; ++lane) {
                lm[lane] = v[lane].sel[0];
                int lu = 0;
                for (int u = 1; u < PER; ++u) {
                    if (v[lane].sel[u] > lm[lane]) { lm[lane] = v[lane].sel[u]; lu = u; }
                }
                le[lane] = lane + SG * lu;
            }
            float m = lm[0];
            for (int lane = 1; lane < SG; ++lane) m = maximum(m, lm[lane]);
            int bv[SG];
            for (int lane = 0; lane < SG; ++lane) bv[lane] = le[lane] < ne && lm[lane] == m ? le[lane] : PER * SG;
            int b = bv[0];
            for (int lane = 1; lane < SG; ++lane) b = minimum(b, bv[lane]);
            for (int lane = 0; lane < SG; ++lane)
                for (int u = 0; u < PER; ++u)
                    if (lane + SG * u == b) v[lane].sel[u] = -INFINITY;
            pick[k] = b;
        }
        float w[16], sum = 0.0f;
        for (int k = 0; k < nu; ++k) {
            const int b = pick[k], bu = b / SG, source = b % SG;
            float pv = v[source].p[0];
            for (int u = 1; u < PER; ++u) if (u == bu) pv = v[source].p[u];
            w[k] = pv;
            r.ids[t * nu + k] = b;
            selected[t * nu + k] = b;
            sum += w[k];
        }
        sum = sum * 1.0f + 1e-20f;
        for (int k = 0; k < nu; ++k) r.wts[t * nu + k] = (w[k] / sum) * wscale;
    }
    r.g = group_fused(selected.data(), K, ne, with_sloc);
    return r;
}

static void check_groups(const Groups &a, const Groups &b, const std::string &name, int ntok) {
#define CHECK_MEMBER(member) CHECK(a.member == b.member, "%s ntok=%d: " #member " differs", name.c_str(), ntok)
    CHECK_MEMBER(count);
    CHECK_MEMBER(exp);
    CHECK_MEMBER(off);
    CHECK_MEMBER(slots);
    CHECK_MEMBER(ecount);
    CHECK_MEMBER(ntiles);
    CHECK_MEMBER(tile_exp);
    CHECK_MEMBER(tile_s0);
    CHECK_MEMBER(tile_n);
    CHECK_MEMBER(sloc);
#undef CHECK_MEMBER
}

static void run_case(const std::string &name, int ntok, int ne, int nu, float wscale, const std::vector<float> &logits,
                     const std::vector<float> *bias, bool with_sloc) {
    CHECK((int)logits.size() == ntok * ne, "%s: bad logits size", name.c_str());
    CHECK(!bias || (int)bias->size() == ne, "%s: bad bias size", name.c_str());
    RouteResult a = route_reference(logits.data(), bias ? bias->data() : nullptr, ne, nu, wscale, ntok, with_sloc);
    RouteResult b = route_fused(logits.data(), bias ? bias->data() : nullptr, ne, nu, wscale, ntok, with_sloc);
    ++configurations;
    CHECK(a.ids == b.ids, "%s: eids differ", name.c_str());
    CHECK(float_bits(a.wts) == float_bits(b.wts), "%s: normalized weight bits differ", name.c_str());
    check_groups(a.g, b.g, name, ntok);
}

template <class F> static bool throws(F f) {
    try { f(); } catch (const std::exception &) { return true; }
    return false;
}

} // namespace

int main() {
    const float nan = std::numeric_limits<float>::quiet_NaN();
    const float inf = std::numeric_limits<float>::infinity();
    for (int ntok = 2; ntok <= 8; ++ntok) {
        const int ne = 128, nu = 8;
        std::vector<float> logits(ntok * ne), bias(ne);
        for (int e = 0; e < ne; ++e) bias[e] = (e % 9 - 4) * 0.03125f;
        for (int t = 0; t < ntok; ++t)
            for (int e = 0; e < ne; ++e) logits[t * ne + e] = ((e * 37 + 11) % 41 - 20) * 0.125f;
        run_case("identical routes/bias/sloc", ntok, ne, nu, 1.0f, logits, &bias, true);

        std::fill(logits.begin(), logits.end(), -20.0f);
        for (int t = 0; t < ntok; ++t)
            for (int k = 0; k < nu; ++k) logits[t * ne + t * nu + k] = 8.0f - k * 0.125f;
        run_case("disjoint routes/no bias", ntok, ne, nu, 1.0f, logits, nullptr, false);

        std::fill(logits.begin(), logits.end(), -12.0f);
        for (int t = 0; t < ntok; ++t) {
            for (int e = 0; e < 4; ++e) logits[t * ne + e] = 10.0f - e * 0.25f;
            for (int k = 0; k < 4; ++k) logits[t * ne + 8 + t * 4 + k] = 7.0f - k * 0.25f;
        }
        run_case("heavily shared routes", ntok, ne, nu, 1.5f, logits, nullptr, true);

        std::fill(logits.begin(), logits.end(), 0.25f);
        std::fill(bias.begin(), bias.end(), 0.0f);
        run_case("all tied/lower id", ntok, ne, nu, 1.0f, logits, &bias, true);

        for (int t = 0; t < ntok; ++t) {
            for (int e = 0; e < ne; ++e) logits[t * ne + e] = (e % 13 - 6) * 0.25f;
            logits[t * ne + (t * 7 + 1) % ne] = nan;
            logits[t * ne + (t * 7 + 2) % ne] = inf;
            logits[t * ne + (t * 7 + 3) % ne] = -inf;
        }
        run_case("NaN and infinity logits", ntok, ne, nu, 1.0f, logits, nullptr, true);

        for (int t = 0; t < ntok; ++t) {
            for (int e = 0; e < ne; ++e) logits[t * ne + e] = t == 0 ? nan : (e % 17 - 8) * 0.125f;
        }
        run_case("all-NaN token/sentinel ids", ntok, ne, nu, 1.0f, logits, nullptr, true);
    }

    // Non-power-of-two expert counts, partial PER tiles, varying pick counts, null/non-null bias, both sloc modes.
    std::mt19937 rng(7319);
    std::uniform_real_distribution<float> dist(-8.0f, 8.0f);
    for (int ne : {8, 9, 16, 17, 31, 64, 127, 128}) {
        for (int nu : {1, 3, 8}) {
            if (nu > ne) continue;
            for (int ntok = 2; ntok <= 8; ++ntok) {
                std::vector<float> logits(ntok * ne), bias(ne);
                for (float &x : logits) x = dist(rng);
                for (float &x : bias) x = dist(rng) * 0.0625f;
                const bool use_bias = (ne + nu + ntok) % 3 != 0;
                run_case("random ne=" + std::to_string(ne) + " nu=" + std::to_string(nu) + " ntok=" + std::to_string(ntok),
                         ntok, ne, nu, 1.25f, logits, use_bias ? &bias : nullptr, (ne + ntok) & 1);
            }
        }
    }

    // Direct grouping arms cover multiple 16-slot tiles and arbitrary invalid ids, beyond what valid top-8 routes make.
    std::array<int32_t, 64> ids;
    ids.fill(5);
    Groups a = group_reference(ids.data(), 64, 128, true), b = group_fused(ids.data(), 64, 128, true);
    ++configurations;
    check_groups(a, b, "64 slots/one expert/four tiles", 8);
    for (int s = 0; s < 64; ++s) ids[s] = s % 5 == 0 ? 128 : (s % 7 == 0 ? -1 : (s * 19) % 128);
    a = group_reference(ids.data(), 64, 128, true);
    b = group_fused(ids.data(), 64, 128, true);
    ++configurations;
    check_groups(a, b, "invalid and valid mixed ids", 8);

    // Packed-scan edges: no active lanes, an active physical last lane, and tile totals split across subgroups.
    for (int s = 0; s < 64; ++s) ids[s] = s & 1 ? -1 : 128;
    a = group_reference(ids.data(), 64, 128, true);
    b = group_fused(ids.data(), 64, 128, true);
    ++configurations;
    check_groups(a, b, "all invalid ids/off[0] sentinel", 8);
    ids.fill(127);
    a = group_reference(ids.data(), 64, 128, true);
    b = group_fused(ids.data(), 64, 128, true);
    ++configurations;
    check_groups(a, b, "active last lane/four tiles", 8);
    const int owners[4] = {3, 17, 31, 127}, counts[4] = {17, 16, 15, 16};
    for (int group = 0, s = 0; group < 4; ++group)
        for (int j = 0; j < counts[group]; ++j, ++s) ids[s] = owners[group];
    a = group_reference(ids.data(), 64, 128, false);
    b = group_fused(ids.data(), 64, 128, false);
    ++configurations;
    check_groups(a, b, "17/16/15/16 counts/cross-subgroup tiles", 8);

    // Smallest legal route: one expert, one pick, two tokens; every other lane must retain zero packed fields.
    const std::vector<float> one_expert(2, 0.0f);
    run_case("minimum ne=1 nu=1 ntok=2", 2, 1, 1, 1.0f, one_expert, nullptr, true);

    CHECK(ink::live_parse_flag("INK_ROUTE_GROUP", nullptr, true), "default toggle is not on");
    CHECK(!ink::live_parse_flag("INK_ROUTE_GROUP", "0", true), "toggle 0 is not off");
    CHECK(ink::live_parse_flag("INK_ROUTE_GROUP", "1", false), "toggle 1 is not on");
    for (const char *s : {"", "00", "2", "-1", "true", " 1", "1 "})
        CHECK(throws([&] { ink::live_parse_flag("INK_ROUTE_GROUP", s, true); }), "toggle accepted invalid value '%s'", s);

    if (fails) std::printf("route_group: %d checks failed\n", fails);
    else std::printf("route_group: PASS (%d configurations, every width 2..8, all output bytes)\n", configurations);
    return fails != 0;
}
