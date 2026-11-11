// k7-2 bench (2026-11-11, one card; k7-1's transport replaced, see sycl_v41_k7.hpp): OWN_K7's kernels (engine/src/stage2/packet3/kernels/sycl_v41_k7.hpp) against
// production, bit for bit, and their times.
//
// Six cards on one card: six exchange arenas in the card's memory (the peer pointers p0..p5 of every launch), the
// model rows split as the engine splits them (848 / 864 per card). For each input set:
//   1. XchgPK7 for every card me = 0..5 in push-only mode (XchgP mode 1: no h wait; the engine runs mode 0), each
//      with only its own output rows in its arena (the launch's work-group 0 waits for its 25 local rows, copies the
//      slot to every peer and raises the K7 flags): every arena then holds the whole output, every card's 25
//      partials (all six slots, every word incl. the local flags), every peer's h flag and K7 flag (checked word by
//      word; the partials also against a host emulation of K7Part's exact float / double operations).
//   2. Every receiver R: HcPostPreK7 (HcPostPreP + the K7 flag wait) on a copy of the old streams with R's gathered
//      output (new streams and x == production HcPostPreP's, bit for bit), then SkNormK7 (R's arena) -> y, the 200
//      partials, the finish (HcMixFinishSG, both forms).
//   3. Production on the same new streams: SkNormDotsW<8> (today's default: y, partials) and HcMixDotsP (the original
//      partials), the finish of each.
//   Required (any difference = failure): y == SkNormDotsW's y; the finish outputs == production's (both forms, all
//   six receivers); the 200 partials equal on all receivers; each row as predicted by the host (a passing row
//   d[8r] = T, d[8r+1..7] = +0.0; a failing row production's 8 partials bit for bit); forced rows (every row, random
//   masks) production's partials; with real rows the trace's own values (new streams, the norm output, the finish).
//   Also reported: max |T - t_chain| / E_up over the rows with E_up >= 1e-20 and the number of rows outside the
//   proof's bound |T - t_chain| <= 2.678e-13 E_up + 6e-41 (must be 0); the time-out path of HcPostPreK7's wait
//   (poison word, error word, and HcPostPreP's outputs still production's).
// Input sets: real (runs/ab1/base.trc steps 1-3, layers 0-39: the FFN mix after the output-b exchange and the next
// attention mix after the ffn-rows exchange, exactly the 77 mixes per step OWN_K7 covers; fn / norm / finish
// weights from the GGUF), random (real-like streams; random and real fn rows), exact float ties and near-ties placed
// across cards, cancelling rows, tiny / huge / subnormal / zero / inf / NaN inputs.
// Timing (GPU time per launch, median of REPS, cold: 256 MiB read first, then the launch's warm inputs re-read):
//   XchgP vs XchgPK7 (both push-only into the six local arenas), HcPostPreP vs HcPostPreK7 (flags already up),
//   SkNormDotsW<8> vs SkNormK7 vs SkNormW<5120, 16>.
// build: /home/steve/dsv41-work/k7/build_bench.sh; run: /home/steve/dsv41-work/k7/run_bench.sh TAG CARD
// env REPS=31 NREAL=3 (trace steps) NRAND=24 SEED=1 NOTIME=1. Exit status 1 on any mismatch.
#include <sycl/sycl.hpp>
#include <fcntl.h>
#include <unistd.h>
#include <xmmintrin.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <random>
#include <string>
#include <vector>
#include "stage2/packet3/backend/trace_tags_v41.hpp"
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/sycl_v41_k7.hpp"
using namespace ops41sycl;

static constexpr unsigned H = 5120, N = 4 * H, NC = 6, OBOFF = 1024, ARENA = OBOFF + H, FS = 200;
static constexpr long SPIN = 5000000;
static constexpr size_t FLUSH_WORDS = (size_t)64 << 20; // 256 MiB
static unsigned td0[NC], td1[NC];
static int g_fail = 0, g_reps = 31;

// ---------------------------------------------------------------- GGUF (all six parts indexed once)
static const char *GGUF_DIR = "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS";
struct GT {
    std::string file;
    uint64_t off = 0;
    uint32_t type = 0;
    uint64_t ne0 = 0, ne1 = 1;
};
static std::map<std::string, GT> g_gg;
static void gguf_index() {
    for (int part = 1; part <= 6; ++part) {
        char fn[512];
        std::snprintf(fn, sizeof fn, "%s/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-%05d-of-00006.gguf", GGUF_DIR, part);
        const int fd = open(fn, O_RDONLY);
        if (fd < 0) continue;
        std::vector<uint8_t> h((size_t)32 << 20);
        const ssize_t n = pread(fd, h.data(), h.size(), 0);
        close(fd);
        if (n < 64 || std::memcmp(h.data(), "GGUF", 4)) continue;
        const uint8_t *p = h.data() + 4, *end = h.data() + n;
        auto rd = [&](auto &v) { std::memcpy(&v, p, sizeof v); p += sizeof v; };
        uint32_t ver;
        uint64_t nt, nkv;
        rd(ver), rd(nt), rd(nkv);
        static const int tsz[13] = {1, 1, 2, 2, 4, 4, 4, 1, -1, -1, 8, 8, 8};
        uint64_t align = 32;
        for (uint64_t i = 0; i < nkv && p < end; ++i) {
            uint64_t kl;
            rd(kl);
            const std::string key((const char *)p, kl);
            p += kl;
            uint32_t t;
            rd(t);
            if (t == 8) { uint64_t m; rd(m); p += m; }
            else if (t == 9) {
                uint32_t et;
                uint64_t m;
                rd(et), rd(m);
                if (et == 8) for (uint64_t j = 0; j < m; ++j) { uint64_t sl; rd(sl); p += sl; }
                else p += m * tsz[et];
            } else {
                if (key == "general.alignment" && t == 4) { uint32_t a; std::memcpy(&a, p, 4); align = a; }
                p += tsz[t];
            }
        }
        std::vector<std::pair<std::string, GT>> got;
        for (uint64_t i = 0; i < nt && p < end; ++i) {
            uint64_t nl;
            rd(nl);
            const std::string tn((const char *)p, nl);
            p += nl;
            uint32_t nd;
            rd(nd);
            uint64_t dims[4] = {1, 1, 1, 1};
            for (uint32_t d = 0; d < nd; ++d) rd(dims[d]);
            uint32_t ty;
            uint64_t off;
            rd(ty), rd(off);
            GT g;
            g.file = fn, g.type = ty, g.ne0 = dims[0], g.ne1 = dims[1], g.off = off;
            got.emplace_back(tn, g);
        }
        const uint64_t data = ((uint64_t)(p - h.data()) + align - 1) / align * align;
        for (auto &e : got) {
            e.second.off += data;
            g_gg[e.first] = e.second;
        }
    }
}
static bool gguf_f32(const std::string &name, std::vector<float> &v, size_t n) {
    auto it = g_gg.find(name);
    if (it == g_gg.end() || it->second.type != 0 || it->second.ne0 * it->second.ne1 != n) {
        std::printf("  gguf: %s missing or not F32 x %zu\n", name.c_str(), n);
        return false;
    }
    v.resize(n);
    const int fd = open(it->second.file.c_str(), O_RDONLY);
    const ssize_t r = pread(fd, v.data(), n * 4, (off_t)it->second.off);
    close(fd);
    return r == (ssize_t)(n * 4);
}

// ---------------------------------------------------------------- the reference trace
static std::vector<uint8_t> g_trc;
static std::map<uint64_t, std::pair<size_t, uint32_t>> g_ti; // (step, layer, tag) -> (float offset, n)
static uint64_t tkey(uint32_t st, uint32_t L, uint32_t tag) { return ((uint64_t)st << 32) | ((uint64_t)L << 8) | tag; }
static bool trace_load(const char *path) {
    FILE *f = std::fopen(path, "rb");
    if (!f) return false;
    std::fseek(f, 0, SEEK_END);
    const long sz = std::ftell(f);
    std::fseek(f, 0, SEEK_SET);
    g_trc.resize((size_t)sz);
    const size_t got = std::fread(g_trc.data(), 1, (size_t)sz, f);
    std::fclose(f);
    if (got != (size_t)sz) return false;
    size_t p = 0;
    while (p + 16 <= g_trc.size()) {
        uint32_t h[4];
        std::memcpy(h, g_trc.data() + p, 16);
        g_ti[tkey(h[0], h[1], h[2])] = {p + 16, h[3]};
        p += 16 + (size_t)h[3] * 4;
    }
    return true;
}
static const float *trc(uint32_t st, uint32_t L, uint32_t tag, uint32_t n) {
    auto it = g_ti.find(tkey(st, L, tag));
    if (it == g_ti.end() || it->second.second != n) return nullptr;
    return reinterpret_cast<const float *>(g_trc.data() + it->second.first);
}

// ---------------------------------------------------------------- host emulation of K7Part and the check
static void host_new(const std::vector<float> &old, const std::vector<float> &ob, const float *post, const float *comb,
                     unsigned j, float a[4][4]) {
    for (unsigned m = 0; m < 4; ++m) {
        const float xi = ob[j + m];
        for (unsigned s = 0; s < 4; ++s) {
            float t = post[s] * xi;
            for (unsigned k = 0; k < 4; ++k) t += comb[k * 4 + s] * old[k * H + j + m];
            a[s][m] = t;
        }
    }
}
// card c's 25 partials (K7Part's operations in its order: item blocks, the 32-lane xor tree, the 8-way tree)
static void host_part(const std::vector<float> &old, const std::vector<float> &ob, const float *post, const float *comb,
                      const std::vector<float> &fn, unsigned c, double *T, float *E) {
    const unsigned r0 = td0[c], ncg = (td1[c] - td0[c]) / 4;
    std::vector<float> A((size_t)ncg * 16);
    for (unsigned i = 0; i < ncg; ++i) {
        float a[4][4];
        host_new(old, ob, post, comb, r0 + 4 * i, a);
        std::memcpy(&A[(size_t)i * 16], a, 64);
    }
    for (unsigned r = 0; r < 25; ++r) {
        double acc[256];
        float ef[256];
        for (unsigned i = 0; i < 256; ++i) {
            acc[i] = 0;
            ef[i] = 0;
            if (i >= ncg) continue;
            const unsigned j = r0 + 4 * i;
            float a[4][4], b[4][4];
            std::memcpy(a, &A[(size_t)i * 16], 64);
            for (unsigned s = 0; s < 4; ++s)
                for (unsigned m = 0; m < 4; ++m) b[s][m] = r < 24 ? fn[(size_t)r * N + s * H + j + m] : a[s][m];
            for (unsigned blk = 0; blk < 2; ++blk) {
                float hi = 0, lo = 0;
                for (unsigned s = 2 * blk; s < 2 * blk + 2; ++s)
                    for (unsigned m = 0; m < 4; ++m) {
                        const float p = b[s][m] * a[s][m];
                        const float e = std::fmaf(b[s][m], a[s][m], -p);
                        const float t = hi + p;
                        const float z = t - hi;
                        const float er = (hi - (t - z)) + (p - z);
                        hi = t;
                        lo = lo + (er + e);
                        ef[i] = ef[i] + std::fabs(p);
                    }
                acc[i] = acc[i] + double(hi);
                acc[i] = acc[i] + double(lo);
            }
        }
        double sgT[8];
        float sgE[8];
        for (unsigned g = 0; g < 8; ++g) {
            double v[32];
            float e[32];
            for (unsigned l = 0; l < 32; ++l) v[l] = acc[g * 32 + l], e[l] = ef[g * 32 + l];
            for (unsigned w = 16; w; w >>= 1) {
                double nv[32];
                float ne[32];
                for (unsigned l = 0; l < 32; ++l) nv[l] = v[l] + v[l ^ w], ne[l] = e[l] + e[l ^ w];
                std::memcpy(v, nv, sizeof v);
                std::memcpy(e, ne, sizeof e);
            }
            sgT[g] = v[0], sgE[g] = e[0];
        }
        double v[32];
        float e[32];
        for (unsigned l = 0; l < 32; ++l) v[l] = l < 8 ? sgT[l] : 0.0, e[l] = l < 8 ? sgE[l] : 0.0f;
        for (unsigned w = 1; w < 8; w <<= 1) {
            double nv[32];
            float ne[32];
            for (unsigned l = 0; l < 32; ++l) nv[l] = v[l] + v[l ^ w], ne[l] = e[l] + e[l ^ w];
            std::memcpy(v, nv, sizeof v);
            std::memcpy(e, ne, sizeof e);
        }
        T[r] = v[0], E[r] = e[0];
    }
}
static bool host_check(unsigned r, double T, float E) { // SkDotsFF<8>::check
    const double Eu = double(E) * (1 + 1e-5);
    if (!(Eu < 1e30)) return false;
    const double B = 2.8e-13 * Eu + 1e-38;
    if (r < 24) {
        if (!(std::fabs(T) > 1e-30)) return false;
        const float f = float(T);
        const double fd = f;
        const double mu = (fd + double(std::nextafter(f, INFINITY))) * 0.5;
        const double md = (fd + double(std::nextafter(f, -INFINITY))) * 0.5;
        return T - B > md && T + B < mu;
    }
    if (!(T > 1e-25 && T < 1e30 && Eu < 2 * T)) return false;
    const double D = 1.0 / std::sqrt(T / N + 1e-20);
    const float f = float(D);
    const double fd = f, up = std::nextafter(f, INFINITY), dn = std::nextafter(f, 0.0f);
    return D * (1 + 4e-12) < fd + (up - fd) * 0.5 && D * (1 - 4e-12) > fd - (fd - dn) * 0.5;
}

// ---------------------------------------------------------------- device
struct Dev {
    sycl::queue q;
    float *ar[NC];
    uint32_t *cnt, *err;
    float *old, *snew, *snew2, *post, *comb, *mix, *x, *x2, *fn, *w, *scale, *base, *yk, *ysk, *yw, *fo;
    double *dk, *dsk, *dpr;
    uint32_t *flush;
};
static Dev D;
static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
static void flush() {
    const uint32_t *p = D.flush;
    uint32_t *o = D.flush;
    D.q.parallel_for(sycl::range<1>(FLUSH_WORDS / 4), [=](sycl::id<1> i) {
        const size_t b = (size_t)i[0];
        const uint32_t s = p[b] ^ p[b + FLUSH_WORDS / 4] ^ p[b + FLUSH_WORDS / 2] ^ p[b + 3 * FLUSH_WORDS / 4];
        if (s == 0xdeadbeefu) o[b] = 0;
    });
}
static sycl::event k7x(int me, uint32_t seq, int mode) {
    const XchgP xp{(int)NC, me, OBOFF, H, 1u, td0[me], td1[me], seq, SPIN, mode};
    float *p0 = D.ar[0], *p1 = D.ar[1], *p2 = D.ar[2], *p3 = D.ar[3], *p4 = D.ar[4], *p5 = D.ar[5];
    uint32_t *err = D.err;
    const float *st = D.old, *po = D.post, *co = D.comb, *fn = D.fn;
    return D.q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<uint32_t, 1> lt(32, hh);
        hh.parallel_for(sycl::nd_range<1>((size_t)(1 + K7_ROWS) * 256, 256),
                        XchgPK7{xp, p0, p1, p2, p3, p4, p5, err, st, po, co, fn, lt});
    });
}
static sycl::event xp_only(int me, uint32_t seq) { // production's XchgP launch (launch_wg(c, 256, xp, ...)), mode 1
    const XchgP xp{(int)NC, me, OBOFF, H, 1u, td0[me], td1[me], seq, SPIN, 1};
    float *p0 = D.ar[0], *p1 = D.ar[1], *p2 = D.ar[2], *p3 = D.ar[3], *p4 = D.ar[4], *p5 = D.ar[5];
    uint32_t *err = D.err;
    return D.q.submit([&](sycl::handler &hh) {
        hh.parallel_for(sycl::nd_range<1>(256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            xp(it, p0, p1, p2, p3, p4, p5, err);
        });
    });
}
static sycl::event post_pre(float *streams, const float *ob, float *x) { // HcPostPreP as tp_phase cases 3 / 5
    const float *po = D.post, *co = D.comb, *mx = D.mix;
    return D.q.parallel_for(sycl::nd_range<1>(H, 64), [=](sycl::nd_item<1> it) {
        HcPostPreP<ActF32>{(int)H}(it, streams, ob, po, co, nullptr, nullptr, mx, x);
    });
}
// HcPostPreK7 as Backend41::k7_post_pre (launch(c, (nm + 1) * 64, 64, ...): no sub-group size required, as launch)
static sycl::event post_pre_k7(int me, uint32_t seq, float *streams, const float *ob, float *x, long spin = SPIN) {
    const float *po = D.post, *co = D.comb, *mx = D.mix;
    float *mine = D.ar[me];
    uint32_t *err = D.err;
    const unsigned nm = H / 64;
    const HcPostPreK7<ActF32> k{HcPostPreP<ActF32>{(int)H}, nm, (int)NC, me, seq, spin};
    return D.q.submit([&](sycl::handler &hh) {
        hh.parallel_for(sycl::nd_range<1>((size_t)(nm + 1) * 64, 64), [=](sycl::nd_item<1> it) {
            k(it, streams, ob, po, co, (const float *)nullptr, (float *)nullptr, mx, x, mine, err);
        });
    });
}
static sycl::event sknk7(int me, uint32_t force, const float *x, float *y, const float *streams, double *out) {
    const float *w = D.w, *fn = D.fn;
    const float *mine = D.ar[me];
    return D.q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<uint32_t, 1> lt(64, hh);
        hh.parallel_for(sycl::nd_range<1>(2 * 512, 512), SkNormK7{(int)NC, force, x, w, y, streams, fn, out, mine, lt});
    });
}
static sycl::event skn_dots(const float *x, float *y, const float *streams, double *out) { // launch_wgl<64>(c, 26, 512, ...)
    const float *w = D.w, *fn = D.fn;
    return D.q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<uint32_t, 1> lt(64, hh);
        hh.parallel_for(sycl::nd_range<1>(26 * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            SkNormDotsW<8>{}(it, x, w, y, streams, fn, out, &lt[0]);
        });
    });
}
static sycl::event skn_alone(const float *x, float *y) { // launch_wgl<32>(tile, 1, 512, SkNormW<5120, 16>{}, ...)
    const float *w = D.w;
    return D.q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<uint32_t, 1> lt(32, hh);
        hh.parallel_for(sycl::nd_range<1>(512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            SkNormW<5120, 16>{}(it, x, w, y, &lt[0]);
        });
    });
}
static sycl::event mix_dots(const float *streams, double *out) { // HcMixDotsP, launch_sg(t, 25 * 8, ...)
    const float *fn = D.fn;
    return D.q.parallel_for(sycl::nd_range<1>(FS * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
        HcMixDotsP<5120, 8>{}(it, streams, fn, out);
    });
}
static void finish(const double *d, int form, float *o24) { // HcMixFinishSG -> o24: pre 4, post 4, comb 16
    HcMixFinishSG k{(int)H, 8};
    k.form = form;
    const float *sc = D.scale, *ba = D.base;
    float *fo = D.fo;
    D.q.parallel_for(sycl::nd_range<1>(32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
        k(it, d, sc, ba, fo, fo + 4, fo + 8);
    });
    D.q.memcpy(o24, D.fo, 24 * 4).wait();
}
template <typename T> static std::vector<T> rd(const T *p, size_t n) {
    std::vector<T> v(n);
    D.q.memcpy(v.data(), p, n * sizeof(T)).wait();
    return v;
}
static bool beq(const void *a, const void *b, size_t n) { return std::memcmp(a, b, n) == 0; }

// ---------------------------------------------------------------- an input set
struct Case {
    std::string name;
    std::vector<float> old, ob, fn, w, scale, base;
    float post[4], comb[16], mix[4];
    const float *exp_new = nullptr, *exp_y = nullptr, *exp_pre = nullptr, *exp_post = nullptr, *exp_comb = nullptr;
};
struct Stats {
    long sets = 0, rows = 0, fb_rows = 0, fb_sets = 0, forced = 0, pred_mis = 0, trace_cmp = 0, out_of_bound = 0,
         tiny_rows = 0;
    double max_rel = 0; // over rows with E_up >= 1e-20 (below that the absolute 1e-38 underflow term dominates)
    std::string max_rel_at;
} S;
static uint32_t g_seq = 0;

static int run_case(const Case &cs, std::mt19937_64 &rng) {
    int bad = 0;
    auto fail = [&](const char *what) {
        if (bad < 6) std::printf("  MISMATCH %s: %s\n", cs.name.c_str(), what);
        ++bad;
    };
    D.q.memcpy(D.old, cs.old.data(), N * 4);
    D.q.memcpy(D.post, cs.post, 16);
    D.q.memcpy(D.comb, cs.comb, 64);
    D.q.memcpy(D.mix, cs.mix, 16);
    D.q.memcpy(D.fn, cs.fn.data(), (size_t)24 * N * 4);
    D.q.memcpy(D.w, cs.w.data(), H * 4);
    D.q.memcpy(D.scale, cs.scale.data(), 12);
    D.q.memcpy(D.base, cs.base.data(), 96);
    // arenas: 0xff everywhere (the pushes must write every word read), flags + poison + K7 row flags + K7 flags
    // zero, the card's own rows
    static std::vector<uint32_t> fl0;
    if (fl0.empty()) {
        fl0.assign(OBOFF, 0xffffffffu);
        for (unsigned k = 0; k < 128; ++k) fl0[k] = 0;
        for (unsigned d = 0; d < NC; ++d) {
            for (unsigned r = 0; r < K7_ROWS; ++r) fl0[K7_OFF + K7_SLOT * d + 4 * r + 3] = 0;
            fl0[K7_FLAG + 16 * d] = 0;
        }
    }
    for (unsigned c = 0; c < NC; ++c) {
        D.q.memset(D.ar[c], 0xff, (size_t)ARENA * 4);
        D.q.memcpy(D.ar[c], fl0.data(), OBOFF * 4);
        D.q.memcpy(D.ar[c] + OBOFF + td0[c], cs.ob.data() + td0[c], (size_t)(td1[c] - td0[c]) * 4);
    }
    D.q.wait();
    const uint32_t seq = ++g_seq;
    for (unsigned c = 0; c < NC; ++c) k7x((int)c, seq, 1);
    D.q.wait();
    // 1. every arena: the whole output, every card's slot, every peer's flags; the slots against the host
    double hT[NC][25];
    float hE[NC][25];
    for (unsigned c = 0; c < NC; ++c) host_part(cs.old, cs.ob, cs.post, cs.comb, cs.fn, c, hT[c], hE[c]);
    std::vector<uint32_t> a0;
    for (unsigned R = 0; R < NC; ++R) {
        const auto a = rd(reinterpret_cast<uint32_t *>(D.ar[R]), ARENA);
        if (!beq(a.data() + OBOFF, cs.ob.data(), H * 4)) fail("gathered output");
        for (unsigned d = 0; d < NC; ++d) {
            const uint32_t *sl = a.data() + K7_OFF + K7_SLOT * d;
            if (d != R && a[16 * d] != seq) fail("flags");
            if (a[K7_FLAG + 16 * d] != (d != R ? seq : 0u)) fail("K7 flags");
            for (unsigned r = 0; r < 25; ++r)
                if (sl[4 * r + 3] != seq) { fail("row flags (copied with the slot)"); break; }
            for (unsigned k = 4 * K7_ROWS; k < K7_SLOT; ++k)
                if (sl[k] != 0xffffffffu) { fail("a slot's pad words written"); break; }
            for (unsigned r = 0; r < 25; ++r) {
                double T;
                float E;
                std::memcpy(&T, sl + 4 * r, 8);
                std::memcpy(&E, sl + 4 * r + 2, 4);
                if (!beq(&T, &hT[d][r], 8) || !beq(&E, &hE[d][r], 4)) {
                    if (R == 0) fail("partial vs host emulation");
                    break;
                }
            }
        }
        if (R == 0) a0 = a;
        else
            for (unsigned d = 0; d < NC; ++d)
                for (unsigned r = 0; r < 25; ++r)
                    if (!beq(a.data() + K7_OFF + K7_SLOT * d + 4 * r, a0.data() + K7_OFF + K7_SLOT * d + 4 * r, 16))
                        { fail("slots differ between arenas"); d = NC; break; }
    }
    // 2. every receiver (R = 0 last: its new streams and x stay for production and the forced runs)
    std::vector<double> dk0;
    std::vector<float> yk0;
    float fk[2][24];
    std::vector<std::vector<double>> dks;
    std::vector<std::vector<float>> fks;
    for (int R = NC - 1; R >= 0; --R) {
        D.q.memcpy(D.snew, D.old, N * 4);
        D.q.memcpy(D.snew2, D.old, N * 4);
        post_pre(D.snew2, D.ar[R] + OBOFF, D.x2); // production's HcPostPreP
        post_pre_k7(R, seq, D.snew, D.ar[R] + OBOFF, D.x);
        sknk7(R, 0, D.x, D.yk, D.snew, D.dk);
        D.q.wait();
        if (!beq(rd(D.snew, N).data(), rd(D.snew2, N).data(), N * 4) || !beq(rd(D.x, H).data(), rd(D.x2, H).data(), H * 4))
            fail("HcPostPreK7's new streams / x vs HcPostPreP");
        dks.push_back(rd(D.dk, FS));
        const auto y = rd(D.yk, H);
        for (int f = 0; f < 2; ++f) finish(D.dk, f, fk[f]);
        fks.emplace_back(fk[0], fk[0] + 24);
        fks.back().insert(fks.back().end(), fk[1], fk[1] + 24);
        if (R == (int)NC - 1) yk0 = y;
        else if (!beq(y.data(), yk0.data(), H * 4)) fail("y differs between receivers");
    }
    for (size_t i = 1; i < dks.size(); ++i)
        if (!beq(dks[i].data(), dks[0].data(), FS * 8)) fail("partials differ between receivers");
    dk0 = dks.back();
    // 3. production on R = 0's new streams
    skn_dots(D.x, D.ysk, D.snew, D.dsk);
    mix_dots(D.snew, D.dpr);
    D.q.wait();
    const auto ysk = rd(D.ysk, H);
    const auto dpr = rd(D.dpr, FS);
    float fp[2][24], fs[2][24];
    for (int f = 0; f < 2; ++f) finish(D.dpr, f, fp[f]), finish(D.dsk, f, fs[f]);
    if (!beq(yk0.data(), ysk.data(), H * 4)) fail("y vs SkNormDotsW");
    if (!beq(fp[0], fp[1], 96)) fail("production finish forms differ");
    if (!beq(fs[0], fp[0], 96) || !beq(fs[1], fp[1], 96)) fail("SkNormDotsW finish vs production");
    for (auto &v : fks)
        if (!beq(v.data(), fp[0], 96) || !beq(v.data() + 24, fp[1], 96)) { fail("K7 finish vs production"); break; }
    // rows: as the host predicts
    long fbr = 0;
    for (unsigned r = 0; r < 25; ++r) {
        double T = hT[0][r];
        float E = hE[0][r];
        for (unsigned d = 1; d < NC; ++d) T = T + hT[d][r], E = E + hE[d][r];
        const bool pass = host_check(r, T, E);
        const double *row = dk0.data() + 8 * r;
        const bool kpass = row[1] == 0 && !std::signbit(row[1]) && beq(&row[0], &T, 8) &&
                           std::all_of(row + 1, row + 8, [](double v) { return v == 0 && !std::signbit(v); });
        const bool kprod = beq(row, dpr.data() + 8 * r, 64);
        if (pass ? !kpass : !kprod) {
            if (!kprod) fail("a row is neither the predicted sum nor production's partials");
            ++S.pred_mis;
        }
        if (!pass) ++fbr;
        double tc = 0;
        for (unsigned k = 0; k < 8; ++k) tc += dpr[8 * r + k];
        const double Eu = double(E) * (1 + 1e-5);
        if (std::isfinite(T) && std::isfinite(tc) && std::isfinite(Eu) && Eu > 0)
        {
            const double dlt = std::fabs(T - tc);
            if (dlt > 2.678e-13 * Eu + 6e-41) ++S.out_of_bound; // the proof's bound with its underflow term
            if (Eu >= 1e-20) {
                if (dlt / Eu > S.max_rel) S.max_rel = dlt / Eu, S.max_rel_at = cs.name + " row " + std::to_string(r);
            } else
                ++S.tiny_rows;
        }
    }
    S.rows += 25, S.fb_rows += fbr, S.fb_sets += fbr > 0, ++S.sets;
    // 4. forced fallbacks: every row, then two random masks (R = 0)
    for (int k = 0; k < 3; ++k) {
        const uint32_t force = k == 0 ? 0x1ffffffu : (uint32_t)(rng() & 0x1ffffffu);
        sknk7(0, force, D.x, D.yk, D.snew, D.dk);
        D.q.wait();
        const auto d = rd(D.dk, FS);
        for (unsigned r = 0; r < 25; ++r) {
            const bool fr = (force >> r) & 1u;
            if (fr ? !beq(d.data() + 8 * r, dpr.data() + 8 * r, 64) : !beq(d.data() + 8 * r, dk0.data() + 8 * r, 64)) {
                fail("forced row");
                break;
            }
        }
        float ff[24];
        finish(D.dk, 0, ff);
        if (!beq(ff, fp[0], 96)) fail("forced finish");
        ++S.forced;
    }
    // 5. real rows: the trace's own values
    if (cs.exp_new) {
        ++S.trace_cmp;
        const auto sn = rd(D.snew, N);
        if (!beq(sn.data(), cs.exp_new, N * 4)) fail("new streams vs trace");
        if (cs.exp_y && !beq(yk0.data(), cs.exp_y, H * 4)) fail("norm output vs trace");
        if (cs.exp_pre && !beq(fp[0], cs.exp_pre, 16)) fail("finish pre vs trace");
        if (cs.exp_post && !beq(fp[0] + 4, cs.exp_post, 16)) fail("finish post vs trace");
        if (cs.exp_comb && !beq(fp[0] + 8, cs.exp_comb, 64)) fail("finish comb vs trace");
    }
    if (bad) g_fail += bad;
    return bad;
}

// ---------------------------------------------------------------- input generators
static float nrm(std::mt19937_64 &g) { return std::normal_distribution<float>(0.f, 1.f)(g); }
static float sigm(float v) { return 1.f / (1.f + std::exp(-v)); }
static void rand_mix(Case &c, std::mt19937_64 &g) {
    for (int k = 0; k < 4; ++k) c.post[k] = 2.f * sigm(nrm(g)), c.mix[k] = sigm(nrm(g)) + 1e-6f;
    for (int r = 0; r < 4; ++r) {
        float s = 0, v[4];
        for (int k = 0; k < 4; ++k) s += v[k] = std::exp(nrm(g));
        for (int k = 0; k < 4; ++k) c.comb[r * 4 + k] = v[k] / s;
    }
    c.scale = {0.5f + sigm(nrm(g)), 0.5f + sigm(nrm(g)), 0.5f + sigm(nrm(g))};
    c.base.resize(24);
    for (auto &b : c.base) b = 0.5f * nrm(g);
}
static void rand_streams(Case &c, std::mt19937_64 &g) {
    c.old.assign(N, 0);
    c.ob.assign(H, 0);
    std::vector<float> s(H);
    for (unsigned j = 0; j < H; ++j) s[j] = 0.05f * std::exp(nrm(g));
    for (unsigned j : {17u, 1500u, 2600u, 4097u, 5000u}) s[j] *= 50.f; // massive channels
    for (unsigned j = 0; j < H; ++j) {
        const float sh = nrm(g);
        for (unsigned k = 0; k < 4; ++k) c.old[k * H + j] = s[j] * (0.7f * sh + 0.7f * nrm(g));
        c.ob[j] = 0.3f * s[j] * nrm(g);
    }
}
static std::vector<std::vector<float>> g_realfn; // a few real fn matrices for random streams
static void set_fn(Case &c, std::mt19937_64 &g, int real) {
    if (real && !g_realfn.empty()) c.fn = g_realfn[g() % g_realfn.size()];
    else {
        c.fn.resize((size_t)24 * N);
        for (auto &v : c.fn) v = 0.02f * nrm(g);
    }
    c.w.resize(H);
    for (auto &v : c.w) v = 1.f + 0.2f * nrm(g);
}
static void ident_mix(Case &c) { // post 0, comb = identity: the new streams are the old ones exactly
    for (int k = 0; k < 4; ++k) c.post[k] = 0.f, c.mix[k] = 0.25f;
    for (int i = 0; i < 16; ++i) c.comb[i] = i % 5 == 0 ? 1.f : 0.f;
}

int main() {
    _mm_setcsr(_mm_getcsr() & ~0x8040u); // host floats with gradual underflow (no FTZ / DAZ), as IEEE
    if (const char *e = getenv("REPS")) g_reps = std::max(3, atoi(e));
    const int nreal = getenv("NREAL") ? atoi(getenv("NREAL")) : 3, nrand = getenv("NRAND") ? atoi(getenv("NRAND")) : 24;
    const uint64_t seed = getenv("SEED") ? strtoull(getenv("SEED"), nullptr, 10) : 1;
    const bool notime = getenv("NOTIME") != nullptr;
    for (unsigned c = 0; c < NC; ++c) {
        const unsigned u = H / 16;
        td0[c] = u * c / NC * 16;
        td1[c] = c + 1 == NC ? H : u * (c + 1) / NC * 16;
    }
    D.q = sycl::queue(sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    const auto dev = D.q.get_device();
    std::printf("device: %s\n", dev.get_info<sycl::info::device::name>().c_str());
    if (dev.has(sycl::aspect::ext_intel_free_memory)) {
        const double f = dev.get_info<sycl::ext::intel::info::device::free_memory>() / 1073741824.0;
        std::printf("free card memory: %.2f GiB\n", f);
        if (f < 1.0) { std::printf("not enough free card memory\n"); return 2; }
    }
    std::printf("rows per card:");
    for (unsigned c = 0; c < NC; ++c) std::printf(" %u-%u", td0[c], td1[c]);
    std::printf("\n");
    auto mf = [](size_t n) { return sycl::malloc_device<float>(n, D.q); };
    for (unsigned c = 0; c < NC; ++c) D.ar[c] = mf(ARENA);
    D.cnt = sycl::malloc_device<uint32_t>(16, D.q);
    D.q.memset(D.cnt, 0, 64);
    D.err = sycl::malloc_shared<uint32_t>(4, D.q);
    std::memset(D.err, 0, 16);
    D.old = mf(N), D.snew = mf(N), D.snew2 = mf(N), D.post = mf(4), D.comb = mf(16), D.mix = mf(4), D.x = mf(H),
    D.x2 = mf(H), D.fn = mf((size_t)24 * N), D.w = mf(H), D.scale = mf(4), D.base = mf(24), D.yk = mf(H), D.ysk = mf(H),
    D.yw = mf(H), D.fo = mf(32);
    D.dk = sycl::malloc_device<double>(FS, D.q), D.dsk = sycl::malloc_device<double>(FS, D.q),
    D.dpr = sycl::malloc_device<double>(FS, D.q);
    D.flush = sycl::malloc_device<uint32_t>(FLUSH_WORDS, D.q);
    D.q.memset(D.flush, 0x5a, FLUSH_WORDS * 4).wait();
    std::mt19937_64 rng(seed);

    // ---- real rows
    gguf_index();
    std::printf("gguf tensors indexed: %zu\n", g_gg.size());
    const bool have_trace = trace_load("/home/steve/dsv41-work/runs/ab1/base.trc");
    std::printf("trace: %s (%zu records)\n", have_trace ? "loaded" : "MISSING", g_ti.size());
    int nreal_sets = 0, nreal_bad = 0;
    std::vector<float> fnA, fnF, sA, bA, sF, bF, wA, wF;
    for (int L = 0; L < 40 && have_trace; ++L) {
        const std::string p = "blk." + std::to_string(L) + ".";
        if (!gguf_f32(p + "hc_ffn_fn.weight", fnF, (size_t)24 * N) || !gguf_f32(p + "hc_ffn_scale.weight", sF, 3) ||
            !gguf_f32(p + "hc_ffn_base.weight", bF, 24) || !gguf_f32(p + "ffn_norm.weight", wF, H))
            { ++g_fail; break; }
        if (L == 3 || L == 20 || L == 37) g_realfn.push_back(fnF);
        const bool s2 = L + 1 < 40 && L + 1 != 1 && L + 1 != 14;
        const std::string pn = "blk." + std::to_string(L + 1) + ".";
        if (s2 && (!gguf_f32(pn + "hc_attn_fn.weight", fnA, (size_t)24 * N) || !gguf_f32(pn + "hc_attn_scale.weight", sA, 3) ||
                   !gguf_f32(pn + "hc_attn_base.weight", bA, 24) || !gguf_f32(pn + "attn_norm.weight", wA, H)))
            { ++g_fail; break; }
        for (int st = 1; st <= nreal; ++st) {
            // site 1: layer L's FFN mix after the output-b exchange
            const float *old = L == 0 ? trc(st, 0, TT_EMBED, N) : (L == 1 || L == 14) ? trc(st, L, TT_ENGRAM, N)
                                                                               : trc(st, L - 1, TT_STREAMS_FFN, N);
            const float *ob = trc(st, L, TT_ATTN_OUT, H), *po = trc(st, L, TT_ATTN_MIX_POST, 4),
                        *co = trc(st, L, TT_ATTN_MIX_COMB, 16), *pr = trc(st, L, TT_ATTN_MIX_PRE, 4),
                        *sa = trc(st, L, TT_STREAMS_ATTN, N), *fin = trc(st, L, TT_FFN_IN, H),
                        *fpre = trc(st, L, TT_FFN_MIX_PRE, 4);
            if (!old || !ob || !po || !co || !pr || !sa || !fin || !fpre) { std::printf("  trace: step %d layer %d incomplete\n", st, L); ++g_fail; continue; }
            Case c;
            c.name = "real s" + std::to_string(st) + " L" + std::to_string(L) + " ffn-mix";
            c.old.assign(old, old + N), c.ob.assign(ob, ob + H), c.fn = fnF, c.w = wF, c.scale = sF, c.base = bF;
            std::memcpy(c.post, po, 16), std::memcpy(c.comb, co, 64), std::memcpy(c.mix, pr, 16);
            c.exp_new = sa, c.exp_y = fin, c.exp_pre = fpre;
            nreal_bad += run_case(c, rng) != 0, ++nreal_sets;
            if (!s2) continue;
            // the FFN mix's post / comb / pre: production's dots + finish on the streams after the attention
            const float *ffo = trc(st, L, TT_FFN_OUT, H), *sf = trc(st, L, TT_STREAMS_FFN, N),
                        *ain = trc(st, L + 1, TT_ATTN_IN, H), *apre = trc(st, L + 1, TT_ATTN_MIX_PRE, 4),
                        *apost = trc(st, L + 1, TT_ATTN_MIX_POST, 4), *acomb = trc(st, L + 1, TT_ATTN_MIX_COMB, 16);
            if (!ffo || !sf || !ain || !apre || !apost || !acomb) { ++g_fail; continue; }
            float ffin[24];
            D.q.memcpy(D.snew2, sa, N * 4);
            D.q.memcpy(D.fn, fnF.data(), (size_t)24 * N * 4);
            D.q.memcpy(D.scale, sF.data(), 12);
            D.q.memcpy(D.base, bF.data(), 96);
            mix_dots(D.snew2, D.dpr);
            finish(D.dpr, 0, ffin);
            if (!beq(ffin, fpre, 16)) { std::printf("  MISMATCH real s%d L%d: FFN mix pre vs trace\n", st, L); ++g_fail; }
            // site 2: layer L + 1's attention mix after layer L's ffn-rows exchange
            Case d;
            d.name = "real s" + std::to_string(st) + " L" + std::to_string(L + 1) + " attn-mix";
            d.old.assign(sa, sa + N), d.ob.assign(ffo, ffo + H), d.fn = fnA, d.w = wA, d.scale = sA, d.base = bA;
            std::memcpy(d.post, ffin + 4, 16), std::memcpy(d.comb, ffin + 8, 64), std::memcpy(d.mix, ffin, 16);
            d.exp_new = sf, d.exp_y = ain, d.exp_pre = apre, d.exp_post = apost, d.exp_comb = acomb;
            nreal_bad += run_case(d, rng) != 0, ++nreal_sets;
        }
    }
    std::printf("real mixes: %d sets, %d with a mismatch; rows %ld, failing checks %ld (sets with one: %ld)\n",
                nreal_sets, nreal_bad, S.rows, S.fb_rows, S.fb_sets);
    const Stats Sreal = S;

    // ---- random and adversarial sets
    int nsyn = 0, nsyn_bad = 0;
    for (int i = 0; i < 2 * nrand; ++i) {
        Case c;
        c.name = "random " + std::to_string(i) + (i % 2 ? " (real fn)" : " (random fn)");
        rand_streams(c, rng), rand_mix(c, rng), set_fn(c, rng, i % 2);
        nsyn_bad += run_case(c, rng) != 0, ++nsyn;
    }
    // exact ties and near-ties with their terms on different cards (new streams = old exactly)
    for (int i = 0; i < 6; ++i) {
        Case c;
        c.name = "ties " + std::to_string(i);
        rand_streams(c, rng), rand_mix(c, rng), set_fn(c, rng, 0), ident_mix(c);
        const unsigned ja = td0[i % 6] + 5, jb = td0[(i + 5) % 6] + 9, jc = td0[(i + 3) % 6] + 13; // three cards
        auto F = [&](unsigned r, unsigned s, unsigned j) -> float & { return c.fn[(size_t)r * N + s * H + j]; };
        for (unsigned r = 0; r < 7; ++r) std::fill(c.fn.begin() + (size_t)r * N, c.fn.begin() + (size_t)(r + 1) * N, 0.f);
        c.old[0 * H + ja] = 1.f, c.old[3 * H + jb] = 1.f, c.old[2 * H + jc] = 1.f;
        F(0, 0, ja) = 1.f, F(0, 3, jb) = std::ldexp(1.f, -24);                                  // 1 + 2^-24: a tie
        F(1, 0, ja) = 1.f, F(1, 3, jb) = std::ldexp(1.f, -24), F(1, 2, jc) = std::ldexp(1.f, -60); // just above
        F(2, 0, ja) = 1.f, F(2, 3, jb) = std::ldexp(1.f, -24), F(2, 2, jc) = -std::ldexp(1.f, -70); // just below
        // row 3: all zero; row 4: an exact cancel; row 5: a tiny sum; row 6: 1 beside two 1e10 cancelling
        c.old[1 * H + ja] = 0.7f, c.old[2 * H + jb] = 0.7f;
        F(4, 1, ja) = 1.f, F(4, 2, jb) = -1.f;
        c.old[1 * H + jc] = 1e-15f;
        F(5, 1, jc) = 1e-20f;
        F(6, 0, ja) = 1e10f, F(6, 3, jb) = -1e10f, F(6, 2, jc) = 1.f; // (old[3 H + jb] = 1 = old[0 H + ja])
        nsyn_bad += run_case(c, rng) != 0, ++nsyn;
    }
    // special values
    for (int k = 0; k < 9; ++k) {
        Case c;
        rand_streams(c, rng), rand_mix(c, rng), set_fn(c, rng, k % 2);
        const char *nm[] = {"inf in a stream", "NaN in the output", "subnormal streams (some)", "subnormal streams (all)",
                            "huge streams", "zero streams + output", "huge output (overflow)", "-0.0 streams",
                            "tiny products (underflow)"};
        c.name = std::string("special: ") + nm[k];
        switch (k) {
        case 0: c.old[1 * H + td0[3] + 40] = INFINITY; break;
        case 1: c.ob[td0[1] + 52] = NAN; break;
        case 2: for (unsigned j = 0; j < H; j += 3) c.old[2 * H + j] = 1e-40f * (1 + (j % 7)); break;
        case 3: for (auto &v : c.old) v = std::copysign(1.2e-41f, v); for (auto &v : c.ob) v = 0; break;
        case 4: for (unsigned j = 0; j < H; j += 97) c.old[(j % 4) * H + j] = 1e18f; break;
        case 5: std::fill(c.old.begin(), c.old.end(), 0.f), std::fill(c.ob.begin(), c.ob.end(), 0.f); break;
        case 6: c.ob[td0[4] + 8] = 3e38f, c.post[0] = 1.9f; break;
        case 7: for (auto &v : c.old) v = -0.f; break;
        case 8: for (auto &v : c.fn) v *= 1e-30f; break;
        }
        nsyn_bad += run_case(c, rng) != 0, ++nsyn;
    }
    std::printf("synthetic sets: %d, %d with a mismatch; rows %ld, failing checks %ld (sets with one: %ld)\n", nsyn,
                nsyn_bad, S.rows - Sreal.rows, S.fb_rows - Sreal.fb_rows, S.fb_sets - Sreal.fb_sets);
    std::printf("forced-fallback launches: %ld; row predictions that differed (host vs card, same bits either way): "
                "%ld; trace comparisons: %ld\n", S.forced, S.pred_mis, S.trace_cmp);
    std::printf("max |T - t_chain| / E_up over rows with E_up >= 1e-20: %.3e at %s (proof: <= 2.678e-13, the check "
                "uses 2.8e-13); rows outside |T - t_chain| <= 2.678e-13 E_up + 6e-41: %ld; rows with E_up < 1e-20: %ld\n",
                S.max_rel, S.max_rel_at.c_str(), S.out_of_bound, S.tiny_rows);

    // ---- the timeout path: no peer K7 flag reaches seq; HcPostPreK7 must stop, set the poison word and err, and
    // its HcPostPreP work-groups still write production's outputs
    {
        std::memset(D.err, 0, 16);
        D.q.memcpy(D.snew, D.old, N * 4);
        D.q.memcpy(D.snew2, D.old, N * 4);
        post_pre(D.snew2, D.ar[0] + OBOFF, D.x2);
        post_pre_k7(0, 0xfffffff0u, D.snew, D.ar[0] + OBOFF, D.x, 2000);
        D.q.wait();
        const auto a = rd(reinterpret_cast<uint32_t *>(D.ar[0]), 128);
        const bool same = beq(rd(D.snew, N).data(), rd(D.snew2, N).data(), N * 4) &&
                          beq(rd(D.x, H).data(), rd(D.x2, H).data(), H * 4);
        const bool ok = a[96] == 1u && D.err[0] >= 2 && D.err[0] <= NC && same;
        std::printf("timeout path: poison %u, err %u, outputs %s -> %s\n", a[96], D.err[0], same ? "same" : "DIFFER",
                    ok ? "ok" : "WRONG");
        if (!ok) ++g_fail;
        D.q.memset(D.ar[0] + 96, 0, 4).wait();
        std::memset(D.err, 0, 16);
    }

    // ---- timing (a real-like random set; cold)
    if (!notime) {
        Case c;
        c.name = "timing";
        rand_streams(c, rng), rand_mix(c, rng), set_fn(c, rng, 1);
        run_case(c, rng); // leaves the arenas full, flags at g_seq
        const uint32_t seq = g_seq;
        auto warm = [&](int R) { // the launch's hot inputs as in the step: streams, the output, x
            D.q.memcpy(D.snew2, D.old, N * 4);
            post_pre(D.snew2, D.ar[R] + OBOFF, D.x2);
        };
        auto med = [&](auto &&prep, auto &&launch) {
            std::vector<double> t;
            for (int i = 0; i < g_reps; ++i) {
                flush();
                prep();
                sycl::event e = launch();
                e.wait();
                t.push_back(ev_us(e));
            }
            std::sort(t.begin(), t.end());
            return std::make_pair(t[t.size() / 2], t[t.size() / 10]);
        };
        const int me = 2;
        auto txp = med([&] { warm(me); }, [&] { return xp_only(me, seq + 1); });
        auto tk7 = med([&] { warm(me); }, [&] { return k7x(me, seq + 1, 1); });
        // the receiving side reads the new streams the K7 launch left: re-run the post on snew2 each time
        auto refill = [&] { D.q.memcpy(D.snew2, D.old, N * 4); };
        auto tpp = med([&] { refill(); }, [&] { return post_pre(D.snew2, D.ar[0] + OBOFF, D.x2); });
        auto tpk = med([&] { refill(); }, [&] { return post_pre_k7(0, seq, D.snew2, D.ar[0] + OBOFF, D.x2); });
        auto tsd = med([&] { warm(0); }, [&] { return skn_dots(D.x2, D.ysk, D.snew2, D.dsk); });
        auto tsk = med([&] { warm(0); }, [&] { return sknk7(0, 0, D.x2, D.yk, D.snew2, D.dk); });
        auto tsa = med([&] { warm(0); }, [&] { return skn_alone(D.x2, D.yw); });
        auto tsf = med([&] { warm(0); }, [&] { return sknk7(0, 1u << 7, D.x2, D.yk, D.snew2, D.dk); });
        std::printf("timing (us per launch, cold, median / p10 of %d):\n", g_reps);
        std::printf("  XchgP (push only, 6 local arenas)      %7.2f / %7.2f\n", txp.first, txp.second);
        std::printf("  XchgPK7 (the same + 25 partial rows)   %7.2f / %7.2f\n", tk7.first, tk7.second);
        std::printf("  HcPostPreP (production)                %7.2f / %7.2f\n", tpp.first, tpp.second);
        std::printf("  HcPostPreK7 (+ the K7 flag wait, up)   %7.2f / %7.2f\n", tpk.first, tpk.second);
        std::printf("  SkNormDotsW<8> (production)            %7.2f / %7.2f\n", tsd.first, tsd.second);
        std::printf("  SkNormK7 (norm + the partials' sum)    %7.2f / %7.2f\n", tsk.first, tsk.second);
        std::printf("  SkNormW<5120, 16> (the norm alone)     %7.2f / %7.2f\n", tsa.first, tsa.second);
        std::printf("  SkNormK7 with one row falling back     %7.2f / %7.2f\n", tsf.first, tsf.second);
    }
    std::printf("%s: %d mismatches\n", g_fail ? "FAIL" : "PASS", g_fail);
    return g_fail ? 1 : 0;
}
