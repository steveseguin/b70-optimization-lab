// bench_r4.cpp (densews, 2026-11-17): bench_pb.cpp with PART_PICK's candidates replaced by the four-row forms
// (T8 x R4 (R x T <= 32, ws_reduce_store): one x read feeds 4 rows' multiply-adds, half the x bytes per pair of today's T16 R2 picks;
// densews/README.md) beside today's 256-token picks (X16R2, K16R2, K16R2S) for the timing comparison. Every candidate is
// compared byte for byte with the production form of the same launch; exit 1 on any difference.
// Original header (bench_pb.cpp, pb-1, 2026-11-11): one card. The prompt-block levers of pb-1 against the production forms of the same
// launches, every output compared byte for byte (memcmp of the whole output buffer, stray writes included), then
// timed back to back over cold copies of the weights (no cache flush, no host wait between launches; the forms
// alternate in rounds so clock drift hits both).
//   PART=eg     ExpertGroupPM vs ExpertGroupM: every grp word, many block sizes / caps / orders / id patterns
//   PART=dense  ws_rows(OWN_PB mask) vs ws_rows(0) (the engine's fallback where WsTab has no pick) on real GGUF rows
//               of card 2's shapes; MASKS=0x10,0x8,0x18 ... MS=64,128,256 ONLY=<name part> RANDOM=1 (random rows too)
//   PART=h16    candidate WsH16 forms (plain / chunked) vs DenseRowsG<GemvH16P, 4> (choose WsTab<16, ..>'s picks)
// env: REPS (timing rounds, 7), SEQMB (weight copies in MB, 256), NOTIME=1
// Build: pb256/build.sh NAME -DPART_EG / -DPART_DENSE / -DPART_H16 (against pb256/new/src). Exit 1 on any mismatch.
#include <sycl/sycl.hpp>
#include <fcntl.h>
#include <unistd.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
#ifdef PBFLIP
#include "pbflip.hpp"
#endif
#ifdef PART_DEC
#include <cxxabi.h>
#endif
using namespace ops41sycl;

static int g_fail = 0, g_reps = 7;
static bool g_notime = false;
static double g_seq_mb = 256;
static const char *g_only = nullptr;
// ONLY: comma-separated label parts ('+' = a space); a label runs when it contains one of them
static bool only_skip(const char *label) {
    if (!g_only) return false;
    std::string o(g_only);
    for (auto &ch : o) if (ch == '+') ch = ' ';
    size_t a = 0;
    while (a <= o.size()) {
        size_t b = o.find(',', a);
        if (b == std::string::npos) b = o.size();
        if (b > a && std::strstr(label, o.substr(a, b - a).c_str())) return false;
        a = b + 1;
    }
    return true;
}
static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
static std::vector<unsigned> env_list(const char *n, std::vector<unsigned> d) {
    const char *e = getenv(n);
    if (!e) return d;
    std::vector<unsigned> v;
    for (const char *p = e; *p;) {
        v.push_back((unsigned)strtoul(p, (char **)&p, 0));
        if (*p == ',') ++p;
    }
    return v;
}
static double median(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    return v.empty() ? 0 : v[v.size() / 2];
}
// the engine's launch_rows<0>: 512-item work-groups, 16 positions each
template <typename RW> static sycl::event launch(sycl::queue &q, const RW &rw) {
    const RowsP<RW> kr{rw};
    const size_t wg = 512, per = wg / 32, nwg = ((size_t)rw.n() + per - 1) / per;
    return q.parallel_for(sycl::nd_range<1>(nwg * wg, wg), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kr(it); });
}

// ---- GGUF rows ---------------------------------------------------------------------------------------------------
static const char *GGUF_DIR = "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS";
struct GgufT {
    std::string file;
    uint64_t off = 0;
    uint32_t type = 0;
    uint64_t ne0 = 0, ne1 = 0;
};
#include <map>
static std::map<std::string, GgufT> &idx_ref() {
    static std::map<std::string, GgufT> m;
    return m;
}
static void gguf_scan();
static bool gguf_find(const std::string &name, GgufT &out) { // (the six headers read once)
    static bool done = false;
    if (!done) done = true, gguf_scan();
    auto it = idx_ref().find(name);
    if (it == idx_ref().end()) return false;
    out = it->second;
    return true;
}
static void gguf_scan() {
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
        bool bad = false;
        for (uint64_t i = 0; i < nkv && !bad; ++i) {
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
            if (p > end) bad = true;
        }
        if (bad) continue;
        std::vector<std::pair<std::string, GgufT>> pend;
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
            GgufT t;
            t.file = fn, t.type = ty, t.ne0 = dims[0], t.ne1 = dims[1], t.off = off;
            pend.emplace_back(tn, t);
        }
        const size_t data = ((size_t)(p - h.data()) + align - 1) / align * align;
        for (auto &[tn, t] : pend) {
            t.off += data;
            idx_ref()[tn] = t;
        }
    }
}
// rows r0 .. r0 + rows - 1 of a tensor: packed (Q8_0 / Q6_K / Q5_K, pk41) or 16-bit halves (BF16 as is, F32 upper halves)
static bool real_rows(const std::string &name, unsigned cols, unsigned r0, unsigned rows, int fmt, std::vector<uint8_t> &out) {
    GgufT g;
    if (!gguf_find(name, g)) { std::printf("   real: %s not found\n", name.c_str()); return false; }
    if (g.ne0 != cols || g.ne1 < r0 + rows) { std::printf("   real: %s shape\n", name.c_str()); return false; }
    if (fmt == 16) {
        const size_t es = g.type == 0 ? 4 : 2; // F32 / BF16 (type 30)
        std::vector<uint8_t> hw((size_t)rows * cols * es);
        const int fd = open(g.file.c_str(), O_RDONLY);
        const ssize_t n = pread(fd, hw.data(), hw.size(), (off_t)(g.off + (uint64_t)r0 * cols * es));
        close(fd);
        if (n != (ssize_t)hw.size()) return false;
        out.resize((size_t)rows * cols * 2);
        size_t lowbits = 0;
        for (size_t i = 0; i < (size_t)rows * cols; ++i) {
            uint16_t h;
            if (es == 4) {
                uint32_t u;
                std::memcpy(&u, &hw[4 * i], 4);
                lowbits += (u & 0xffffu) != 0;
                h = uint16_t(u >> 16);
            } else std::memcpy(&h, &hw[2 * i], 2);
            std::memcpy(&out[2 * i], &h, 2);
        }
        if (lowbits) std::printf("   real: %s has %zu F32 values with low bits (bench uses the upper halves)\n", name.c_str(), lowbits);
        return true;
    }
    const iq3::Type t = fmt == 8 ? iq3::Type::Q8_0 : fmt == 6 ? iq3::Type::Q6_K : iq3::Type::Q5_K;
    if ((uint32_t)t != g.type) { std::printf("   real: %s type %u\n", name.c_str(), g.type); return false; }
    const auto L = iq3::layout(t);
    const size_t rb = (size_t)cols / L.elements * L.bytes, prb = pk41::packed_row_bytes(t, cols);
    std::vector<uint8_t> hw((size_t)rows * rb);
    const int fd = open(g.file.c_str(), O_RDONLY);
    const ssize_t n = pread(fd, hw.data(), hw.size(), (off_t)(g.off + (uint64_t)r0 * rb));
    close(fd);
    if (n != (ssize_t)hw.size()) return false;
    out.assign((size_t)rows * prb, 0);
    for (size_t r = 0; r < rows; ++r) pk41::pack_row(t, hw.data() + r * rb, out.data() + r * prb, cols);
    return true;
}
static std::vector<uint8_t> rand_rows(int fmt, unsigned cols, unsigned rows, unsigned seed) {
    std::mt19937 rng(seed);
    if (fmt == 16) {
        std::uniform_real_distribution<float> u(-0.5f, 0.5f);
        std::vector<uint8_t> hp((size_t)rows * cols * 2);
        for (size_t i = 0; i < (size_t)rows * cols; ++i) {
            const float f = u(rng);
            uint32_t b;
            std::memcpy(&b, &f, 4);
            const uint16_t h = uint16_t(b >> 16);
            std::memcpy(&hp[2 * i], &h, 2);
        }
        return hp;
    }
    const iq3::Type t = fmt == 8 ? iq3::Type::Q8_0 : fmt == 6 ? iq3::Type::Q6_K : iq3::Type::Q5_K;
    const auto L = iq3::layout(t);
    const size_t rb = (size_t)cols / L.elements * L.bytes, prb = pk41::packed_row_bytes(t, cols);
    std::vector<uint8_t> hw((size_t)rows * rb);
    for (auto &b : hw) b = uint8_t(rng());
    for (size_t blk = 0; blk < hw.size() / L.bytes; ++blk) {
        uint8_t *bp = hw.data() + blk * L.bytes;
        auto seth = [&](size_t o) {
            const uint16_t h = 0x1400 + (rng() & 0x3ff);
            bp[o] = h & 255;
            bp[o + 1] = h >> 8;
        };
        if (t == iq3::Type::Q8_0) seth(0);
        else if (t == iq3::Type::Q6_K) seth(208);
        else { seth(0); seth(2); }
    }
    std::vector<uint8_t> hp((size_t)rows * prb);
    for (size_t r = 0; r < rows; ++r) pk41::pack_row(t, hw.data() + r * rb, hp.data() + r * prb, cols);
    return hp;
}
static std::vector<float> rand_f(size_t n, unsigned seed) {
    std::mt19937 rng(seed);
    std::normal_distribution<float> u(0.f, 1.f);
    std::vector<float> v(n);
    for (auto &f : v) f = u(rng);
    return v;
}
static constexpr unsigned MMAX = 264; // the engine's MTA = MTX + 8 tokens in the activation buffers

// a launch under test: a form for (weights w) -> launches it; returns false when it has none
struct Buf {
    sycl::queue *q;
    std::vector<uint8_t *> wc; // weight copies (wc[0]: the checked one)
    size_t wbytes = 0;
    float *x = nullptr, *ya = nullptr, *yb = nullptr;
    size_t xs = 0, ys = 0;
    unsigned rows = 0;
};
static void setup(sycl::queue &q, Buf &b, const std::vector<uint8_t> &hw, unsigned rows, size_t xs, size_t ys, unsigned seed) {
    b.q = &q;
    b.rows = rows;
    b.wbytes = hw.size();
    const unsigned nc = (unsigned)std::min(64.0, std::max(2.0, std::ceil(g_seq_mb * 1e6 / (double)hw.size())));
    for (unsigned i = 0; i < nc; ++i) {
        uint8_t *d = sycl::malloc_device<uint8_t>(hw.size() + 4096, q);
        q.memcpy(d, hw.data(), hw.size()).wait();
        b.wc.push_back(d);
    }
    b.xs = xs, b.ys = ys;
    const auto xh = rand_f((size_t)MMAX * xs, seed);
    b.x = sycl::malloc_device<float>(xh.size(), q);
    q.memcpy(b.x, xh.data(), xh.size() * 4).wait();
    b.ya = sycl::malloc_device<float>((size_t)MMAX * ys, q);
    b.yb = sycl::malloc_device<float>((size_t)MMAX * ys, q);
}
static void release(Buf &b) {
    for (auto *p : b.wc) sycl::free(p, *b.q);
    sycl::free(b.x, *b.q), sycl::free(b.ya, *b.q), sycl::free(b.yb, *b.q);
    b.wc.clear();
}
// A, B: (w, y) -> sycl::event (launch one form). Bitwise on wc[0], then timing rounds.
template <typename FA, typename FB>
static void compare(Buf &b, const char *label, unsigned M, const char *na, const char *nb, FA &&fa, FB &&fb) {
    sycl::queue &q = *b.q;
    const size_t n = (size_t)MMAX * b.ys;
    q.memset(b.ya, 0xff, n * 4), q.memset(b.yb, 0xff, n * 4);
    q.wait();
    fa(b.wc[0], b.ya).wait();
    fb(b.wc[0], b.yb).wait();
    std::vector<float> ga(n), gb(n);
    q.memcpy(ga.data(), b.ya, n * 4), q.memcpy(gb.data(), b.yb, n * 4);
    q.wait();
    size_t differ = 0, written = 0;
    for (size_t i = 0; i < n; ++i) {
        differ += std::memcmp(&ga[i], &gb[i], 4) != 0;
        uint32_t u;
        std::memcpy(&u, &ga[i], 4);
        written += u != 0xffffffffu;
    }
    const bool ok = differ == 0 && written >= (size_t)M * b.rows;
    g_fail += !ok;
    double ta = 0, tb = 0;
    if (!g_notime) {
        for (int i = 0; i < 3; ++i) fa(b.wc[i % b.wc.size()], b.ya), fb(b.wc[i % b.wc.size()], b.yb);
        q.wait();
        std::vector<double> va, vb;
        std::vector<sycl::event> ea, eb;
        for (int r = 0; r < g_reps; ++r) {
            ea.clear(), eb.clear();
            for (auto *w : b.wc) ea.push_back(fa(w, b.ya));
            for (auto *w : b.wc) eb.push_back(fb(w, b.yb));
            q.wait();
            for (auto &e : ea) va.push_back(ev_us(e));
            for (auto &e : eb) vb.push_back(ev_us(e));
        }
        ta = median(va), tb = median(vb);
    }
    std::printf("%s %-28s M=%-3u %-26s %8.1f us | %-30s %8.1f us  x%.3f  (%zu differ, %zu written)\n",
                ok ? "bitwise" : "DIFFERS", label, M, na, ta, nb, tb, tb > 0 ? ta / tb : 0.0, differ, written);
    std::fflush(stdout);
}

// ================================================================================================================
#ifdef PART_EG
static void eg_case(sycl::queue &q, const char *pat, unsigned M, unsigned cap, bool heavy, unsigned seed, bool timeit,
                    uint32_t *dids, uint32_t *ga, uint32_t *gb) {
    const unsigned nsl = 6 * M;
    std::mt19937 rng(seed);
    std::vector<uint32_t> ids(nsl);
    const unsigned E = 384;
    std::vector<double> wgt(E);
    std::vector<unsigned> perm(E);
    for (unsigned e = 0; e < E; ++e) perm[e] = e;
    std::shuffle(perm.begin(), perm.end(), rng);
    for (unsigned e = 0; e < E; ++e) wgt[e] = std::string(pat) == "zipf" ? 1.0 / std::pow(e + 4.0, 1.1) : 1.0;
    std::discrete_distribution<unsigned> dd(wgt.begin(), wgt.end());
    for (unsigned t = 0; t < M; ++t) {
        std::vector<unsigned> pick;
        if (std::string(pat) == "same") pick = {perm[0], perm[1], perm[2], perm[3], perm[4], perm[5]};
        else if (std::string(pat) == "few" ) { // 12 experts in all
            while (pick.size() < 6) {
                const unsigned e = perm[rng() % 12];
                if (std::find(pick.begin(), pick.end(), e) == pick.end()) pick.push_back(e);
            }
        } else
            while (pick.size() < 6) {
                const unsigned e = perm[dd(rng)];
                if (std::find(pick.begin(), pick.end(), e) == pick.end()) pick.push_back(e);
            }
        for (unsigned k = 0; k < 6; ++k) ids[6 * t + k] = pick[k];
    }
    q.memcpy(dids, ids.data(), nsl * 4).wait();
    const size_t W = RUGrp::WORDS;
    q.fill(ga, 0xdeadbeefu, W), q.fill(gb, 0xdeadbeefu, W);
    q.wait();
    auto la = [&](uint32_t *g) {
        ExpertGroupM k{nsl, cap};
        k.heavy = heavy;
        const size_t it = ExpertGroupM::items(nsl);
        const uint32_t *di = dids;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(ExpertGroupM::LM, h);
            h.parallel_for(sycl::nd_range<1>(it, it), [=](sycl::nd_item<1> i) [[sycl::reqd_sub_group_size(32)]] { k(i, di, g, &lt[0]); });
        });
    };
    auto lb = [&](uint32_t *g) {
        ExpertGroupPM k{nsl, cap};
        k.heavy = heavy;
        const size_t it = ExpertGroupPM::items(nsl);
        const uint32_t *di = dids;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(ExpertGroupPM::LM, h);
            h.parallel_for(sycl::nd_range<1>(it, it), [=](sycl::nd_item<1> i) [[sycl::reqd_sub_group_size(32)]] { k(i, di, g, &lt[0]); });
        });
    };
    la(ga).wait();
    lb(gb).wait();
    std::vector<uint32_t> ha(W), hb(W);
    q.memcpy(ha.data(), ga, W * 4), q.memcpy(hb.data(), gb, W * 4);
    q.wait();
    size_t differ = 0;
    for (size_t i = 0; i < W; ++i) differ += ha[i] != hb[i];
    g_fail += differ != 0;
    double ta = 0, tb = 0;
    if (timeit && !g_notime) {
        std::vector<double> va, vb;
        for (int r = 0; r < 4 * g_reps; ++r) {
            sycl::event a = la(ga), b = lb(gb);
            q.wait();
            va.push_back(ev_us(a)), vb.push_back(ev_us(b));
        }
        ta = median(va), tb = median(vb);
    }
    if (differ || timeit)
        std::printf("%s eg %-5s M=%-3u cap=%-2u heavy=%d nu=%u | ExpertGroupM %7.1f us | ExpertGroupPM %6.1f us  x%.2f (%zu words differ)\n",
                    differ ? "DIFFERS" : "bitwise", pat, M, cap, (int)heavy, ha[0], ta, tb, tb > 0 ? ta / tb : 0.0, differ);
    std::fflush(stdout);
}
static void part_eg(sycl::queue &q) {
    uint32_t *dids = sycl::malloc_device<uint32_t>(6 * 256, q);
    uint32_t *ga = sycl::malloc_device<uint32_t>(RUGrp::WORDS, q), *gb = sycl::malloc_device<uint32_t>(RUGrp::WORDS, q);
    std::printf("ExpertGroupPM LM %u floats (%u B); device local memory %zu B\n", ExpertGroupPM::LM, ExpertGroupPM::LM * 4,
                (size_t)q.get_device().get_info<sycl::info::device::local_mem_size>());
    unsigned n = 0;
    const char *pats[] = {"zipf", "unif", "same", "few"};
    for (const char *pat : pats)
        for (unsigned M : {1u, 2u, 3u, 5u, 6u, 16u, 21u, 22u, 32u, 33u, 64u, 96u, 127u, 128u, 129u, 170u, 171u, 192u, 255u, 256u})
            for (unsigned cap : {6u, 1u, 3u, 8u, 16u})
                for (int heavy = 0; heavy < 2; ++heavy)
                    for (unsigned sd = 0; sd < 3; ++sd) {
                        eg_case(q, pat, M, cap, heavy, 1000 * M + 10 * cap + heavy + 7 * sd, false, dids, ga, gb);
                        ++n;
                    }
    std::printf("eg: %u cases checked, %d failed\n", n, g_fail);
    // production settings: blocks < 128 ascending first slot cap 6; >= 128 heavy, cap 6 (OWN_MT_RUX_CAP)
    for (const char *pat : {"zipf", "unif"})
        for (unsigned M : {16u, 32u, 64u, 128u, 256u}) eg_case(q, pat, M, 6, M >= 128, 77 + M, true, dids, ga, gb);
}
#endif

// ================================================================================================================
#if defined(PART_DENSE) || defined(PART_PICK) || defined(PART_DEC)
// the production form of a launch: ws_rows with g_pb_mask = 0, else the engine's fallback (dense_m's rules for these
// shapes under the tp98 defaults: H16 rows DenseRowsG<D, 4>; Q6_K engram rows past 128 tokens DenseRowsGR<D, 4, 4>)
template <unsigned KIND, typename DK>
static sycl::event run_form(sycl::queue &q, const DK &dk, unsigned mask, const uint8_t *w, const float *x, size_t xs,
                            float *y, size_t ys, unsigned M, std::string *name = nullptr) {
    g_pb_mask = mask;
    sycl::event ev;
    bool done = ws_rows<DK, KIND>(dk, w, x, xs, y, ys, M, MMAX, [&](const auto &d) {
        if (name) *name = typeid(d).name();
        if constexpr (KIND == WS_SHARED) { // the gate + up pair (the second half of the rows as "up")
            auto du = d;
            du.w = w + (size_t)0; // the same rows (bench: one matrix's rows twice)
            du.y = y + (size_t)dk.rows;
            ev = launch(q, RowsPair<std::decay_t<decltype(d)>, std::decay_t<decltype(d)>>{d, du});
        } else ev = launch(q, d);
    });
    g_pb_mask = 0;
    if (done) return ev;
    if (name) *name = "engine";
    if constexpr (requires { &DK::template rowgr<4, 4>; }) {
        if (dk.rows >= 4096) return launch(q, DenseRowsGR<DK, 4, 4>{dk, w, x, xs, y, ys, M, (M + 3) / 4});
    }
    if constexpr (KIND == WS_SHARED) {
        using D = DenseRowsG<DK, 4>;
        const D d{dk, w, x, xs, y, ys, M, (M + 3) / 4};
        D du = d;
        du.y = y + (size_t)dk.rows;
        return launch(q, RowsPair<D, D>{d, du});
    }
    return launch(q, DenseRowsG<DK, 4>{dk, w, x, xs, y, ys, M, (M + 3) / 4});
}
static std::string short_name(const std::string &mangled) {
    // the form's T / R / PF from the mangled type (rough; for the log only)
    std::string s = mangled;
    const bool c = s.find("DenseRowsWSC") != std::string::npos, seg = s.find("WsQ6S") != std::string::npos,
               h = s.find("WsH16") != std::string::npos;
    return std::string(c ? "WSC" : s == "engine" ? "engine" : "WS") + (seg ? " Q6S" : "") + (h ? " H16" : "");
}
template <unsigned KIND, typename DK>
static void dense_shape(sycl::queue &q, const char *label, const char *tensor, int fmt, unsigned cols, unsigned rows,
                        unsigned r0, DK dk, size_t xs, size_t ys, const std::vector<unsigned> &ms, const std::vector<unsigned> &masks) {
    if (only_skip(label)) return;
    std::vector<uint8_t> hw;
    const bool real = real_rows(tensor, cols, r0, rows, fmt, hw);
    if (!real || getenv("RANDOM")) {
        if (!real) std::printf("   %s: random rows\n", label);
        hw = rand_rows(fmt, cols, rows, 99 + rows);
    }
    Buf b;
    setup(q, b, hw, rows, xs, KIND == WS_SHARED ? 2 * ys : ys, 5 + rows);
    for (unsigned M : ms)
        for (unsigned mask : masks) {
            std::string na, nb;
            run_form<KIND>(q, dk, 0, b.wc[0], b.x, xs, b.ya, b.ys, M, &na).wait();
            run_form<KIND>(q, dk, mask, b.wc[0], b.x, xs, b.yb, b.ys, M, &nb).wait();
            char la[64], lb[64];
            std::snprintf(la, sizeof la, "prod %s", short_name(na).c_str());
            std::snprintf(lb, sizeof lb, "pb 0x%x %s", mask, short_name(nb).c_str());
            compare(b, label, M, la, lb,
                    [&](const uint8_t *w, float *y) { return run_form<KIND>(q, dk, 0, w, b.x, xs, y, b.ys, M); },
                    [&](const uint8_t *w, float *y) { return run_form<KIND>(q, dk, mask, w, b.x, xs, y, b.ys, M); });
        }
    release(b);
}
#endif
#ifdef PART_DENSE
static void part_dense(sycl::queue &q) {
    const auto ms = env_list("MS", {64, 128, 256});
    const auto masks = env_list("MASKS", {0x10, 0x8, 0x18});
    using A = ActF32;
    // Q8_0 layers (blk.2), card 2's slices (12 heads in prompt blocks)
    dense_shape<WS_PLAIN>(q, "q8 q_a 1280x5120", "blk.2.attn_q_a.weight", 8, 5120, 1280, 0, GemvQ8P<160, A>{1280, 0}, 5120, 1280, ms, masks);
    dense_shape<WS_PLAIN>(q, "q8 kv 512x5120", "blk.2.attn_kv.weight", 8, 5120, 512, 0, GemvQ8P<160, A>{512, 0}, 5120, 512, ms, masks);
    dense_shape<WS_PLAIN>(q, "q8 q_b 6144x1280", "blk.2.attn_q_b.weight", 8, 1280, 6144, 12288, GemvQ8P<40, A>{6144, 0}, 1280, 6144, ms, masks);
    dense_shape<WS_PLAIN>(q, "q8 o_a 1024x4096", "blk.2.attn_output_a.weight", 8, 4096, 1024, 2048, GemvQ8P<128, A>{1024, 0}, 4096, 1024, ms, masks);
    dense_shape<WS_PLAIN>(q, "q8 o_a 512x4096", "blk.2.attn_output_a.weight", 8, 4096, 512, 3072, GemvQ8P<128, A>{512, 0}, 4096, 512, ms, masks);
    dense_shape<WS_PLAIN>(q, "q8 o_b 864x8192", "blk.2.attn_output_b.weight", 8, 8192, 864, 1728, GemvQ8P<256, A>{864, 0}, 8192, 5120, ms, masks);
    dense_shape<WS_SHARED>(q, "q8 sh gate 384x5120 (pair)", "blk.2.ffn_gate_shexp.weight", 8, 5120, 384, 768, GemvQ8P<160, A>{384, 0}, 5120, 384, ms, masks);
    dense_shape<WS_PLAIN>(q, "q8 sh down 864x2304", "blk.2.ffn_down_shexp.weight", 8, 2304, 864, 1728, GemvQ8P<72, A>{864, 0}, 2304, 5120, ms, masks);
    // Q6_K / Q5_K layers (blk.30)
    dense_shape<WS_PLAIN>(q, "q6 q_a 1280x5120", "blk.30.attn_q_a.weight", 6, 5120, 1280, 0, GemvQ6KP<20, A>{1280, 0}, 5120, 1280, ms, masks);
    dense_shape<WS_PLAIN>(q, "q6 kv 512x5120", "blk.30.attn_kv.weight", 6, 5120, 512, 0, GemvQ6KP<20, A>{512, 0}, 5120, 512, ms, masks);
    dense_shape<WS_PLAIN>(q, "q6 q_b 6144x1280", "blk.30.attn_q_b.weight", 6, 1280, 6144, 12288, GemvQ6KP<5, A>{6144, 0}, 1280, 6144, ms, masks);
    dense_shape<WS_PLAIN>(q, "q6 o_a 1024x4096", "blk.30.attn_output_a.weight", 6, 4096, 1024, 2048, GemvQ6KP<16, A>{1024, 0}, 4096, 1024, ms, masks);
    dense_shape<WS_PLAIN>(q, "q6 o_a 512x4096", "blk.30.attn_output_a.weight", 6, 4096, 512, 3072, GemvQ6KP<16, A>{512, 0}, 4096, 512, ms, masks);
    dense_shape<WS_PLAIN>(q, "q6 o_b 864x8192", "blk.30.attn_output_b.weight", 6, 8192, 864, 1728, GemvQ6KP<32, A>{864, 0}, 8192, 5120, ms, masks);
    dense_shape<WS_PLAIN>(q, "q6 engram 4267x6144", "blk.1.engram_kv.weight", 6, 6144, 4267, 8534, GemvQ6KP<24, A>{4267, 0}, 6144, 4267, ms, masks);
    dense_shape<WS_SHARED>(q, "q5 sh gate 384x5120 (pair)", "blk.30.ffn_gate_shexp.weight", 5, 5120, 384, 768, GemvQ5KP<20, A>{384, 0}, 5120, 384, ms, masks);
    dense_shape<WS_PLAIN>(q, "q5 sh down 864x2304", "blk.30.ffn_down_shexp.weight", 5, 2304, 864, 1728, GemvQ5KP<9, A>{864, 0}, 2304, 5120, ms, masks);
    // H16 rows (bit 2)
    dense_shape<WS_PLAIN>(q, "h16 router 384x5120", "blk.2.ffn_gate_inp.weight", 16, 5120, 384, 0, GemvH16P<160, A>{384}, 5120, 384, ms, masks);
    dense_shape<WS_PLAIN>(q, "h16 cmp kv 512x5120", "blk.2.attn_compressor_kv.weight", 16, 5120, 512, 0, GemvH16P<160, A>{512}, 5120, 512, ms, masks);
    dense_shape<WS_PLAIN>(q, "h16 idx proj 32x5120", "blk.2.indexer.proj.weight", 16, 5120, 32, 0, GemvH16P<160, A>{32}, 5120, 32, ms, masks);
    dense_shape<WS_PLAIN>(q, "h16 idx q_b 4096x1280", "blk.2.indexer.attn_q_b.weight", 16, 1280, 4096, 0, GemvH16P<40, A>{4096}, 1280, 4096, ms, masks);
}
#endif

// ================================================================================================================
#ifdef PART_PICK
// PART=pick: the candidate forms of each card-2 role against its production form at M tokens (MS, default
// 128,256; CHUNKS per M: 0 = unchunked), every candidate's output memcmp'd. Picks the WsPb table (README-pb1.txt).
template <unsigned KIND, typename D> static sycl::event launch_kind(sycl::queue &q, const D &d, unsigned rows) {
    if constexpr (KIND == WS_SHARED) {
        D du = d;
        du.y = d.y + (size_t)rows;
        return launch(q, RowsPair<D, D>{d, du});
    } else return launch(q, d);
}
template <unsigned KIND, typename DK, typename FM>
static void pk_one(Buf &b, const DK &dk, const char *label, unsigned M, unsigned chunk) {
    using O = WsOf<DK>;
    using WK = typename WsWk<typename O::type, FM::pf>::type;
    constexpr unsigned T = FM::t, R = FM::r;
    const unsigned xn = ws_xn(dk), ng = (M + T - 1) / T;
    if (xn % R || ng * T > MMAX || (chunk && chunk < T) || (chunk && chunk >= M)) return;
    sycl::queue &q = *b.q;
    auto prod = [&](const uint8_t *w, float *y) { return run_form<KIND>(q, dk, 0, w, b.x, b.xs, y, b.ys, M); };
    auto cand = [&](const uint8_t *w, float *y) {
        const WK wk{dk.rows, xn};
        if (chunk)
            return launch_kind<KIND>(q, DenseRowsWSC<WK, T, R, FM::xw, FM::loop, FM::pf>{wk, w, b.x, b.xs, y, b.ys, M, ng, chunk / T}, dk.rows);
        return launch_kind<KIND>(q, DenseRowsWS<WK, T, R, FM::xw, FM::loop, FM::pf>{wk, w, b.x, b.xs, y, b.ys, M, ng}, dk.rows);
    };
    std::string pn;
    run_form<KIND>(q, dk, 0, b.wc[0], b.x, b.xs, b.ya, b.ys, M, &pn).wait();
    char nm[96];
    std::snprintf(nm, sizeof nm, "T%u R%u XW%u L%u PF%u ch%u", T, R, FM::xw, FM::loop, FM::pf, chunk);
    char pl[64];
    std::snprintf(pl, sizeof pl, "prod %s", short_name(pn).c_str());
    compare(b, label, M, pl, nm, prod, cand);
}
template <unsigned KIND, typename DK, typename... Fs>
static void pk_shape(sycl::queue &q, const char *label, const char *tensor, int fmt, unsigned cols, unsigned rows, unsigned r0,
                     DK dk, size_t xs, size_t ys, WsList<Fs...>) {
    if (only_skip(label)) return;
    std::vector<uint8_t> hw;
    const bool real = real_rows(tensor, cols, r0, rows, fmt, hw);
    if (!real || getenv("RANDOM")) {
        if (!real) std::printf("   %s: random rows\n", label);
        hw = rand_rows(fmt, cols, rows, 99 + rows);
    }
    Buf b;
    setup(q, b, hw, rows, xs, KIND == WS_SHARED ? 2 * ys : ys, 5 + rows);
    for (unsigned M : env_list("MS", {128, 256})) {
        std::vector<unsigned> chs = M >= 256 ? env_list("CH256", {0, 32, 64, 128}) : M >= 128 ? env_list("CH128", {0, 32, 64}) : env_list("CHS", {0});
        for (unsigned ch : chs) (pk_one<KIND, DK, Fs>(b, dk, label, M, ch), ...);
    }
    release(b);
}
static void part_pick(sycl::queue &q) {
    using A = ActF32;
    // today's picks first (X16R2 / K16R2 / K16R2S), then the R4 forms
#ifdef NO_R4 // (obpad: today's picks only; c131 closed the R4 forms)
    using Q8L = WsList<WfX16R2>;
    using Q8LS = WsList<WfX16R2>;
    using Q6L = WsList<WfK16R2, WfK16R2S>;
    using Q5L = WsList<WfK16R2>;
#else
    using Q8L = WsList<WfX16R2, WsF<8, 4, 2, 0>, WsF<8, 4, 1, 1>, WsF<8, 4, 1, 0>>; // (R x T <= 32: ws_reduce_store)
    using Q8LS = WsList<WfX16R2, WsF<8, 4, 2, 0>, WsF<8, 4, 1, 0>>; // (1,280 / 2,304 columns: no LOOP form)
    using Q6L = WsList<WfK16R2, WfK16R2S, WsF<8, 4>, WsF<8, 4, 1, 0, 100>>;
    using Q5L = WsList<WfK16R2, WsF<8, 4>>;
#endif
    using HL = WsList<WfH8R4>;
    pk_shape<WS_PLAIN>(q, "q8 q_a 1280x5120", "blk.2.attn_q_a.weight", 8, 5120, 1280, 0, GemvQ8P<160, A>{1280, 0}, 5120, 1280, Q8L{});
    pk_shape<WS_PLAIN>(q, "q8 kv 512x5120", "blk.2.attn_kv.weight", 8, 5120, 512, 0, GemvQ8P<160, A>{512, 0}, 5120, 512, Q8L{});
    pk_shape<WS_PLAIN>(q, "q8 q_b 6144x1280", "blk.2.attn_q_b.weight", 8, 1280, 6144, 12288, GemvQ8P<40, A>{6144, 0}, 1280, 6144, Q8LS{});
    pk_shape<WS_PLAIN>(q, "q8 o_a 1024x4096", "blk.2.attn_output_a.weight", 8, 4096, 1024, 2048, GemvQ8P<128, A>{1024, 0}, 4096, 1024, Q8L{});
    pk_shape<WS_PLAIN>(q, "q8 o_a 512x4096", "blk.2.attn_output_a.weight", 8, 4096, 512, 3072, GemvQ8P<128, A>{512, 0}, 4096, 512, Q8L{});
    // the engine's x stride for output-a: a token's head outputs qh * hd = 32,768 floats (128 KiB) apart (oa_m), not
    // packed: the same rows and forms with that stride (x groups of 1,024 rows read 4,096 columns at group offsets)
    pk_shape<WS_PLAIN>(q, "q8 o_a 1024x4096 xs32768", "blk.2.attn_output_a.weight", 8, 4096, 1024, 2048, GemvQ8P<128, A>{1024, 0}, 32768, 1024, Q8L{});
    // obpad-1: the same rows at padded strides (today's picks only)
    pk_shape<WS_PLAIN>(q, "q8 o_a 1024x4096 xs32784", "blk.2.attn_output_a.weight", 8, 4096, 1024, 2048, GemvQ8P<128, A>{1024, 0}, 32784, 1024, WsList<WfX16R2>{});
    pk_shape<WS_PLAIN>(q, "q8 o_a 1024x4096 xs32832", "blk.2.attn_output_a.weight", 8, 4096, 1024, 2048, GemvQ8P<128, A>{1024, 0}, 32832, 1024, WsList<WfX16R2>{});
    pk_shape<WS_PLAIN>(q, "q8 o_a 1024x4096 xs33024", "blk.2.attn_output_a.weight", 8, 4096, 1024, 2048, GemvQ8P<128, A>{1024, 0}, 33024, 1024, WsList<WfX16R2>{});
    pk_shape<WS_PLAIN>(q, "q8 o_a 512x4096 xs32768", "blk.2.attn_output_a.weight", 8, 4096, 512, 3072, GemvQ8P<128, A>{512, 0}, 32768, 512, WsList<WfX16R2>{});
    pk_shape<WS_PLAIN>(q, "q8 o_a 512x4096 xs32832", "blk.2.attn_output_a.weight", 8, 4096, 512, 3072, GemvQ8P<128, A>{512, 0}, 32832, 512, WsList<WfX16R2>{});
    pk_shape<WS_PLAIN>(q, "q8 o_b 864x8192", "blk.2.attn_output_b.weight", 8, 8192, 864, 1728, GemvQ8P<256, A>{864, 0}, 8192, 5120, Q8L{});
    // obpad: output-b's x (the gathered output-a rows, g.ototal = 8,192 floats = 32 KiB per token) at padded strides
    pk_shape<WS_PLAIN>(q, "q8 o_b 864x8192 xs8208", "blk.2.attn_output_b.weight", 8, 8192, 864, 1728, GemvQ8P<256, A>{864, 0}, 8208, 5120, WsList<WfX16R2>{});
    pk_shape<WS_PLAIN>(q, "q8 o_b 864x8192 xs8256", "blk.2.attn_output_b.weight", 8, 8192, 864, 1728, GemvQ8P<256, A>{864, 0}, 8256, 5120, WsList<WfX16R2>{});
    pk_shape<WS_SHARED>(q, "q8 sh gate 384x5120 (pair)", "blk.2.ffn_gate_shexp.weight", 8, 5120, 384, 768, GemvQ8P<160, A>{384, 0}, 5120, 384, Q8L{});
    pk_shape<WS_PLAIN>(q, "q8 sh down 864x2304", "blk.2.ffn_down_shexp.weight", 8, 2304, 864, 1728, GemvQ8P<72, A>{864, 0}, 2304, 5120, Q8LS{});
    pk_shape<WS_PLAIN>(q, "q6 q_a 1280x5120", "blk.30.attn_q_a.weight", 6, 5120, 1280, 0, GemvQ6KP<20, A>{1280, 0}, 5120, 1280, Q6L{});
    pk_shape<WS_PLAIN>(q, "q6 kv 512x5120", "blk.30.attn_kv.weight", 6, 5120, 512, 0, GemvQ6KP<20, A>{512, 0}, 5120, 512, Q6L{});
    pk_shape<WS_PLAIN>(q, "q6 q_b 6144x1280", "blk.30.attn_q_b.weight", 6, 1280, 6144, 12288, GemvQ6KP<5, A>{6144, 0}, 1280, 6144, Q5L{});
    pk_shape<WS_PLAIN>(q, "q6 o_a 1024x4096", "blk.30.attn_output_a.weight", 6, 4096, 1024, 2048, GemvQ6KP<16, A>{1024, 0}, 4096, 1024, Q6L{});
    pk_shape<WS_PLAIN>(q, "q6 o_a 512x4096", "blk.30.attn_output_a.weight", 6, 4096, 512, 3072, GemvQ6KP<16, A>{512, 0}, 4096, 512, Q6L{});
    pk_shape<WS_PLAIN>(q, "q6 o_a 1024x4096 xs32768", "blk.30.attn_output_a.weight", 6, 4096, 1024, 2048, GemvQ6KP<16, A>{1024, 0}, 32768, 1024, Q6L{});
    pk_shape<WS_PLAIN>(q, "q6 o_a 1024x4096 xs32784", "blk.30.attn_output_a.weight", 6, 4096, 1024, 2048, GemvQ6KP<16, A>{1024, 0}, 32784, 1024, WsList<WfK16R2S, WfK16R2>{});
    pk_shape<WS_PLAIN>(q, "q6 o_a 1024x4096 xs32832", "blk.30.attn_output_a.weight", 6, 4096, 1024, 2048, GemvQ6KP<16, A>{1024, 0}, 32832, 1024, WsList<WfK16R2S, WfK16R2>{});
    pk_shape<WS_PLAIN>(q, "q6 o_a 1024x4096 xs33024", "blk.30.attn_output_a.weight", 6, 4096, 1024, 2048, GemvQ6KP<16, A>{1024, 0}, 33024, 1024, WsList<WfK16R2S, WfK16R2>{});
    pk_shape<WS_PLAIN>(q, "q6 o_b 864x8192", "blk.30.attn_output_b.weight", 6, 8192, 864, 1728, GemvQ6KP<32, A>{864, 0}, 8192, 5120, Q6L{});
    // obpad: output-b's x (the gathered output-a rows, g.ototal = 8,192 floats = 32 KiB per token) at padded strides
    pk_shape<WS_PLAIN>(q, "q6 o_b 864x8192 xs8208", "blk.30.attn_output_b.weight", 6, 8192, 864, 1728, GemvQ6KP<32, A>{864, 0}, 8208, 5120, WsList<WfK16R2S, WfK16R2>{});
    pk_shape<WS_PLAIN>(q, "q6 o_b 864x8192 xs8256", "blk.30.attn_output_b.weight", 6, 8192, 864, 1728, GemvQ6KP<32, A>{864, 0}, 8256, 5120, WsList<WfK16R2S, WfK16R2>{});
    pk_shape<WS_PLAIN>(q, "q6 engram 4267x6144", "blk.1.engram_kv.weight", 6, 6144, 4267, 8534, GemvQ6KP<24, A>{4267, 0}, 6144, 4267, Q6L{});
    pk_shape<WS_SHARED>(q, "q5 sh gate 384x5120 (pair)", "blk.30.ffn_gate_shexp.weight", 5, 5120, 384, 768, GemvQ5KP<20, A>{384, 0}, 5120, 384, Q5L{});
    pk_shape<WS_PLAIN>(q, "q5 sh down 864x2304", "blk.30.ffn_down_shexp.weight", 5, 2304, 864, 1728, GemvQ5KP<9, A>{864, 0}, 2304, 5120, Q5L{});
}
#endif

// ================================================================================================================
#ifdef PART_H16
template <unsigned C, unsigned T, unsigned R, unsigned LOOP>
static void h16_form(Buf &b, const char *label, unsigned M, unsigned chunk) {
    sycl::queue &q = *b.q;
    const GemvH16P<C, ActF32> dk{b.rows};
    auto prod = [&](const uint8_t *w, float *y) {
        return launch(q, DenseRowsG<GemvH16P<C, ActF32>, 4>{dk, w, b.x, b.xs, y, b.ys, M, (M + 3) / 4});
    };
    const unsigned ng = (M + T - 1) / T;
    char nm[64];
    if (chunk) {
        std::snprintf(nm, sizeof nm, "H T%u R%u%s chunk %u", T, R, LOOP ? " L" : "", chunk);
        const unsigned cg = chunk / T ? chunk / T : 1;
        compare(b, label, M, "engine G4", nm, prod, [&](const uint8_t *w, float *y) {
            return launch(q, DenseRowsWSC<WsH16<C>, T, R, 1, LOOP>{WsH16<C>{b.rows, 0}, w, b.x, b.xs, y, b.ys, M, ng, cg});
        });
    } else {
        std::snprintf(nm, sizeof nm, "H T%u R%u%s", T, R, LOOP ? " L" : "");
        compare(b, label, M, "engine G4", nm, prod, [&](const uint8_t *w, float *y) {
            return launch(q, DenseRowsWS<WsH16<C>, T, R, 1, LOOP>{WsH16<C>{b.rows, 0}, w, b.x, b.xs, y, b.ys, M, ng});
        });
    }
}
template <unsigned C>
static void h16_shape(sycl::queue &q, const char *label, const char *tensor, unsigned rows) {
    if (only_skip(label)) return;
    std::vector<uint8_t> hw;
    if (!real_rows(tensor, 32 * C, 0, rows, 16, hw) || getenv("RANDOM")) hw = rand_rows(16, 32 * C, rows, 3 + rows);
    Buf b;
    setup(q, b, hw, rows, 32 * C, rows, 11 + rows);
    for (unsigned M : env_list("MS", {16, 64, 128, 256})) {
        const unsigned ch = M > 64 ? 64 : 0;
        h16_form<C, 8, 2, 0>(b, label, M, ch);
        h16_form<C, 8, 2, 1>(b, label, M, ch);
        h16_form<C, 4, 4, 0>(b, label, M, ch);
        h16_form<C, 8, 4, 0>(b, label, M, ch);
        h16_form<C, 16, 2, 0>(b, label, M, ch);
        h16_form<C, 4, 2, 0>(b, label, M, ch);
        if (ch) {
            h16_form<C, 8, 2, 0>(b, label, M, 0);
            h16_form<C, 8, 2, 0>(b, label, M, 32);
            h16_form<C, 4, 4, 0>(b, label, M, 32);
        }
    }
    release(b);
}
static void part_h16(sycl::queue &q) {
    h16_shape<160>(q, "h16 router 384x5120", "blk.2.ffn_gate_inp.weight", 384);
    h16_shape<160>(q, "h16 cmp kv 512x5120", "blk.2.attn_compressor_kv.weight", 512);
    h16_shape<160>(q, "h16 idx proj 32x5120", "blk.2.indexer.proj.weight", 32);
    h16_shape<40>(q, "h16 idx q_b 4096x1280", "blk.2.indexer.attn_q_b.weight", 4096);
}
#endif

#ifdef PART_DEC
// ---- gp-1 placement bench (2026-11-11): the decode / check kernels that carry private arrays, launched as the
// engine launches them (in-order queue, RowsP / RoutePRows work-groups of 512), timed over cold weight copies. Build
// twice with pbflip.hpp: -DPBFLIP=2048 (their modules keep private arrays in scratch) and -DPBFLIP=2240 (global, as in
// the engine's img5 / img7 / img8 since tp97). Same kernels and inputs in both builds; each line prints the median
// us per launch and an FNV hash of every output buffer after the first launch (must be equal across the builds).
//   ONLY=<label parts>  REPS  SEQMB  NOTIME=1  MS=2,4,6 (check token counts)
static uint64_t fnv(const void *p, size_t n, uint64_t h) {
    const uint8_t *b = (const uint8_t *)p;
    for (size_t i = 0; i < n; ++i) h = (h ^ b[i]) * 1099511628211ull;
    return h;
}
struct DecOut {
    void *p;
    size_t bytes;
};
static std::string dec_name(const char *mangled) {
    int st = 0;
    char *d = abi::__cxa_demangle(mangled, nullptr, nullptr, &st);
    std::string s = st == 0 && d ? d : mangled;
    std::free(d);
    for (const char *z : {"ops41sycl::", "ops41sycl::ActF32", "unsigned int", " >"}) {
        size_t i;
        const std::string zz(z);
        const std::string rep = zz == "ops41sycl::ActF32" ? "A" : zz == " >" ? ">" : zz == "unsigned int" ? "u" : "";
        while ((i = s.find(zz)) != std::string::npos) s.replace(i, zz.size(), rep);
    }
    return s;
}
// launch_copy(c): one launch on weight copy c (c < ncopy); outs: hashed after launch_copy(0)
template <typename L>
static void dec_one(sycl::queue &q, const std::string &label, unsigned ncopy, L &&launch_copy, const std::vector<DecOut> &outs) {
    if (only_skip(label.c_str())) return;
    for (auto &o : outs) q.memset(o.p, 0xff, o.bytes);
    q.wait();
    launch_copy(0u).wait();
    uint64_t h = 1469598103934665603ull;
    for (auto &o : outs) {
        std::vector<uint8_t> v(o.bytes);
        q.memcpy(v.data(), o.p, o.bytes).wait();
        h = fnv(v.data(), v.size(), h);
    }
    double med = 0, lo = 0;
    if (!g_notime) {
        for (int i = 0; i < 3; ++i) launch_copy((unsigned)i % ncopy);
        q.wait();
        std::vector<double> v;
        std::vector<sycl::event> ev;
        for (int r = 0; r < g_reps; ++r) {
            ev.clear();
            for (unsigned c = 0; c < ncopy; ++c) ev.push_back(launch_copy(c));
            q.wait();
            for (auto &e : ev) v.push_back(ev_us(e));
        }
        med = median(v);
        lo = *std::min_element(v.begin(), v.end());
    }
    std::printf("  %-96s %8.2f us (min %7.2f)  out %016llx\n", label.c_str(), med, lo, (unsigned long long)h);
    std::fflush(stdout);
}
static void part_dec(sycl::queue &q0) {
    sycl::queue q{q0.get_context(), q0.get_device(), {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    using A = ActF32;
    std::mt19937 rng(7);
    // the stream mix's finish inputs (as bench_routed_r2): 25 x 8 positive double partials per token, 3 scales + 24
    // bases; outputs pre / post / comb = o, o + 4, o + 8 per token (24 floats apart)
    std::vector<double> hd(8 * 25 * 8);
    std::uniform_real_distribution<double> ud(0.01, 4.0);
    for (auto &v : hd) v = ud(rng);
    std::normal_distribution<float> un(0.f, 1.f);
    std::vector<float> hs(3 + 24);
    for (auto &v : hs) v = un(rng);
    double *dd = sycl::malloc_device<double>(hd.size(), q);
    float *sb = sycl::malloc_device<float>(hs.size(), q), *fo = sycl::malloc_device<float>(8 * 24, q);
    q.memcpy(dd, hd.data(), hd.size() * 8), q.memcpy(sb, hs.data(), hs.size() * 4).wait();
    auto fin = [&](int form) {
        HcMixFinishSG k{5120, 8};
        k.form = form;
        return HcFinishRows{k, dd, sb, sb + 3, fo, fo + 4, fo + 8};
    };
    const DecOut ofin{fo, 8 * 24 * 4};
    // a rope rider's row (RopeRows: rows 1, d 512, the last 64 dims rotated) and its tables
    std::vector<float> hr(512 + 64);
    for (auto &v : hr) v = un(rng);
    float *rb = sycl::malloc_device<float>(hr.size(), q);
    q.memcpy(rb, hr.data(), hr.size() * 4).wait();
    const RopeRows<A> rope{rb, rb + 512, rb + 512 + 32, 1, 512, false};
    const DecOut orope{rb, 512 * 4};

    // 1. the finish alone (one sub-group): form 1 (the engine's, OWN_HC_FIN) and form 0; 6 tokens (TokRows). As in
    //    the engine, each launch follows a matrix launch (Q8 output-b rows, not timed): a lone one-sub-group kernel
    //    lets the card clock down and its time then depends on the clock, not on the code
    {
        std::vector<uint8_t> hw0;
        if (!real_rows("blk.2.attn_output_b.weight", 8192, 1728, 864, 8, hw0)) hw0 = rand_rows(8, 8192, 864, 3);
        Buf bw;
        setup(q, bw, hw0, 864, 8192, 864, 3);
        const unsigned nw = (unsigned)bw.wc.size();
        auto warm = [&](unsigned c) { launch(q, DenseRows<GemvQ8P<256, A>>{GemvQ8P<256, A>{864, 0}, bw.wc[c % nw], bw.x, bw.ya}); };
        for (int form : {1, 0}) {
            const HcFinishRows f = fin(form);
            dec_one(q, "finish alone RowsP<HcFinishRows> form " + std::to_string(form) + " (after a matrix launch)", nw,
                    [&](unsigned c) { warm(c); return launch(q, f); }, {ofin});
            const TokRows<HcFinishRows> tf{f, 6, {200, 24, 24, 24}};
            dec_one(q, "finish 6 tokens RowsP<TokRows<HcFinishRows>> form " + std::to_string(form) + " (after a matrix launch)", nw,
                    [&](unsigned c) { warm(c); return launch(q, tf); }, {ofin});
        }
        release(bw);
    }
#ifndef DEC_FIN_ONLY
    // 2. one-token matrix launches with the finish (+ rope) rider, and the same rows without a rider (control)
    auto one_tok = [&](const char *tag, const char *tensor, int fmt, unsigned cols, unsigned rows, unsigned r0, auto dk) {
        std::vector<uint8_t> hw;
        if (!real_rows(tensor, cols, r0, rows, fmt, hw)) hw = rand_rows(fmt, cols, rows, 99 + rows);
        Buf b;
        setup(q, b, hw, rows, cols, rows, 5 + rows);
        using DK = decltype(dk);
        const unsigned nc = (unsigned)b.wc.size();
        auto dr = [&](unsigned c) { return DenseRows<DK>{dk, b.wc[c], b.x, b.ya}; };
        const DecOut oy{b.ya, (size_t)rows * 4};
        const HcFinishRows f = fin(1);
        dec_one(q, std::string(tag) + " RowsP<RowsPair<RowsPair<HcFinishRows, RopeRows>, DenseRows>>", nc, [&](unsigned c) {
            return launch(q, RowsPair<RowsPair<HcFinishRows, RopeRows<A>>, DenseRows<DK>>{{f, rope}, dr(c)});
        }, {oy, ofin, orope});
        dec_one(q, std::string(tag) + " RowsP<RowsPair<HcFinishRows, DenseRows>>", nc, [&](unsigned c) {
            return launch(q, RowsPair<HcFinishRows, DenseRows<DK>>{f, dr(c)});
        }, {oy, ofin});
        dec_one(q, std::string(tag) + " control RowsP<DenseRows> (no private array)", nc, [&](unsigned c) { return launch(q, dr(c)); }, {oy});
        release(b);
    };
    one_tok("q8 q_b 6144x1280", "blk.2.attn_q_b.weight", 8, 1280, 6144, 12288, GemvQ8P<40, A>{6144, 0});
    one_tok("q6 q_b 6144x1280", "blk.30.attn_q_b.weight", 6, 1280, 6144, 12288, GemvQ6KP<5, A>{6144, 0});
    one_tok("q6 o_b 864x8192", "blk.30.attn_output_b.weight", 6, 8192, 864, 1728, GemvQ6KP<32, A>{864, 0});
    one_tok("q8 o_b 864x8192", "blk.2.attn_output_b.weight", 8, 8192, 864, 1728, GemvQ8P<256, A>{864, 0});
    // 3. route_with_shared: RouteP (384 experts, top 6) in work-group 0, the finish and the shared expert's gate + up
    //    rows (card 2's 384 of each) in the others; and without the finish (control)
    {
        std::vector<float> hl(2 * 384);
        for (auto &v : hl) v = un(rng);
        float *lg = sycl::malloc_device<float>(hl.size(), q), *prob = sycl::malloc_device<float>(64, q);
        uint32_t *ids = sycl::malloc_device<uint32_t>(64, q);
        q.memcpy(lg, hl.data(), hl.size() * 4).wait();
        auto rws = [&](const char *tag, const char *tg, const char *tu, int fmt, auto dk) {
            std::vector<uint8_t> hg, hu;
            if (!real_rows(tg, 5120, 768, 384, fmt, hg)) hg = rand_rows(fmt, 5120, 384, 11);
            if (!real_rows(tu, 5120, 768, 384, fmt, hu)) hu = rand_rows(fmt, 5120, 384, 12);
            std::vector<uint8_t> hw(hg);
            hw.insert(hw.end(), hu.begin(), hu.end()); // gate rows then up rows, one copy unit
            Buf b;
            setup(q, b, hw, 768, 5120, 768, 21);
            using DK = decltype(dk);
            using R1 = DenseRows<DK>;
            using RR = RowsPair<R1, R1>;
            const unsigned nc = (unsigned)b.wc.size();
            const size_t half = hg.size();
            auto rr = [&](unsigned c) { return RR{R1{dk, b.wc[c], b.x, b.ya}, R1{dk, b.wc[c] + half, b.x, b.ya + 384}}; };
            const DecOut oy{b.ya, 768 * 4}, oid{ids, 6 * 4}, opr{prob, 6 * 4};
            auto go = [&](const auto &rx) {
                using RX = std::decay_t<decltype(rx)>;
                const RoutePRows<RX> k{RouteP{384, 6}, rx};
                const size_t ng = 1 + (rx.n() + 15) / 16;
                const float *lo = lg, *bi = lg + 384;
                return q.submit([&](sycl::handler &hh) {
                    sycl::local_accessor<float, 1> lt(2 * 1024 + 6, hh);
                    hh.parallel_for(sycl::nd_range<1>(ng * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                        k(it, lo, bi, ids, prob, &lt[0]);
                    });
                });
            };
            const HcFinishRows f = fin(1);
            dec_one(q, std::string(tag) + " route_with_shared RoutePRows<RowsPair<HcFinishRows, gate+up>>", nc,
                    [&](unsigned c) { return go(RowsPair<HcFinishRows, RR>{f, rr(c)}); }, {oy, oid, opr, ofin});
            dec_one(q, std::string(tag) + " control RoutePRows<gate+up> (no finish)", nc, [&](unsigned c) { return go(rr(c)); }, {oy, oid, opr});
            release(b);
        };
        rws("q8 shared 2x384x5120", "blk.2.ffn_gate_shexp.weight", "blk.2.ffn_up_shexp.weight", 8, GemvQ8P<160, A>{384, 0});
        rws("q5 shared 2x384x5120", "blk.30.ffn_gate_shexp.weight", "blk.30.ffn_up_shexp.weight", 5, GemvQ5KP<20, A>{384, 0});
        sycl::free(lg, q), sycl::free(prob, q), sycl::free(ids, q);
    }
    // 4. check blocks of M tokens: (a) the engine's WS form for the shape (ws_rows, OWN_PB off), plain and with the 6
    //    tokens' finish as its rider; (b) DenseRowsGR<D, G, R> with the stream mix's dot rows (TokRows<HcDotsRows>, 0
    //    tokens: the dense part only; the private arrays are the dense part's) and alone
    const auto ms = env_list("MS", {2, 4, 6});
    auto ck = [&](const char *tag, const char *tensor, int fmt, unsigned cols, unsigned rows, unsigned r0, auto dk, bool gr) {
        std::vector<uint8_t> hw;
        if (!tensor || !real_rows(tensor, cols, r0, rows, fmt, hw)) hw = rand_rows(fmt, cols, rows, 99 + rows);
        Buf b;
        setup(q, b, hw, rows, cols, rows, 5 + rows);
        using DK = decltype(dk);
        const unsigned nc = (unsigned)b.wc.size();
        const DecOut oy{b.ya, (size_t)8 * rows * 4};
        for (unsigned M : ms) {
            std::string nm;
            run_form<WS_PLAIN>(q, dk, 0, b.wc[0], b.x, cols, b.ya, rows, M, &nm).wait();
            dec_one(q, std::string(tag) + " M=" + std::to_string(M) + " " + dec_name(nm.c_str()), nc,
                    [&](unsigned c) { return run_form<WS_PLAIN>(q, dk, 0, b.wc[c], b.x, cols, b.ya, rows, M); }, {oy});
            const TokRows<HcFinishRows> tf{fin(1), M, {200, 24, 24, 24}};
            g_pb_mask = 0;
            ws_rows<DK, WS_PLAIN>(dk, b.wc[0], b.x, cols, b.ya, rows, M, MMAX, [&](const auto &d0) {
                using D = std::decay_t<decltype(d0)>;
                dec_one(q, std::string(tag) + " M=" + std::to_string(M) + " with TokRows<HcFinishRows> rider", nc, [&](unsigned c) {
                    D d = d0;
                    d.w = b.wc[c];
                    return launch(q, RowsPair<TokRows<HcFinishRows>, D>{tf, d});
                }, {oy, ofin});
            });
            if constexpr (requires { &DK::template rowgr<2, 4>; }) {
                if (gr) {
                    using HD = TokRows<HcDotsRows<5120, 8>>;
                    const HD hz{HcDotsRows<5120, 8>{nullptr, nullptr, nullptr}, 0, {0, 0, 0, 0}};
                    auto grf = [&](auto gc, auto rc) {
                        constexpr unsigned G = decltype(gc)::value, R = decltype(rc)::value;
                        if (dk.xn % R) return;
                        const std::string l = std::string(tag) + " M=" + std::to_string(M) + " DenseRowsGR<G" + std::to_string(G) + " R" + std::to_string(R) + ">";
                        auto mk = [&](unsigned c) { return DenseRowsGR<DK, G, R>{dk, b.wc[c], b.x, cols, b.ya, rows, M, (M + G - 1) / G}; };
                        dec_one(q, l + " with dots rider (0 tokens)", nc, [&](unsigned c) { return launch(q, RowsPair<HD, DenseRowsGR<DK, G, R>>{hz, mk(c)}); }, {oy});
                        dec_one(q, l + " alone", nc, [&](unsigned c) { return launch(q, mk(c)); }, {oy});
                    };
                    using std::integral_constant;
                    if (M <= 2) grf(integral_constant<unsigned, 1>{}, integral_constant<unsigned, 4>{});
                    else if (M <= 4) grf(integral_constant<unsigned, 2>{}, integral_constant<unsigned, 4>{});
                    else {
                        grf(integral_constant<unsigned, 3>{}, integral_constant<unsigned, 4>{});
                        grf(integral_constant<unsigned, 3>{}, integral_constant<unsigned, 2>{});
                    }
                }
            }
        }
        release(b);
    };
    ck("q6 o_b 864x8192", "blk.30.attn_output_b.weight", 6, 8192, 864, 1728, GemvQ6KP<32, A>{864, 0}, true);
    ck("q6 q_a 1280x5120", "blk.30.attn_q_a.weight", 6, 5120, 1280, 0, GemvQ6KP<20, A>{1280, 0}, true);
    ck("q6 o_a 1024x4096", "blk.30.attn_output_a.weight", 6, 4096, 1024, 2048, GemvQ6KP<16, A>{1024, 0}, true);
    ck("q6 engram 4267x6144", "blk.1.engram_kv.weight", 6, 6144, 4267, 8534, GemvQ6KP<24, A>{4267, 0}, true);
    ck("q8 q_b 6144x1280", "blk.2.attn_q_b.weight", 8, 1280, 6144, 12288, GemvQ8P<40, A>{6144, 0}, false);
    ck("q8 o_b 864x8192", "blk.2.attn_output_b.weight", 8, 8192, 864, 1728, GemvQ8P<256, A>{864, 0}, true);
    ck("q8 15360 cols 2048 rows (random)", nullptr, 8, 15360, 2048, 0, GemvQ8P<480, A>{2048, 0}, true);
#endif
    sycl::free(dd, q), sycl::free(sb, q), sycl::free(fo, q), sycl::free(rb, q);
}
#endif

#ifdef PRIVQB
// PRIVQB (compile only, never launched): 1 = qb-off-2's QbmHeavyK (Q8 40-chunk T6 R4 rows) in the module, 2 = its pull
// alone (QbmPullK), 3 = a kernel with a system-scope atomic fence and spin only: which one moves the module's private
// arrays from scratch to global memory?
#include "stage2/packet3/kernels/sycl_v41_qboff.hpp"
static void privqb(sycl::queue &q) {
    if (!getenv("PRIVQB_RUN_NEVER")) return;
    float *f = nullptr;
    uint32_t *u = nullptr;
#if PRIVQB == 1
    using D = DenseRowsWS<WsQ8<40>, 6, 4, 1, 0, 0>;
    const QbmHeavyK<RowsPair<NoRows, D>> k{};
    q.parallel_for(sycl::nd_range<1>(512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, f, f, f, u); });
#elif PRIVQB == 2
    const QbmPullK k{};
    q.parallel_for(sycl::nd_range<1>(512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, f, f, f, u); });
#else
    q.parallel_for(sycl::nd_range<1>(512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
        sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system, sycl::access::address_space::global_space> a(u[0]);
        long n = 0;
        while (a.load() < 5 && ++n < 100) {}
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
        f[it.get_global_linear_id()] = (float)n;
    });
#endif
}
#endif
#ifdef PRIVGEN
// PRIVGEN (compile only, never launched): a kernel whose loads/stores go through a generic pointer the compiler cannot
// resolve to one address space: 1 = local or global (picked at run time), 2 = private or global. Does either move the
// module's other private arrays from scratch to global memory?
static void privgen(sycl::queue &q) {
    if (!getenv("PRIVGEN_RUN_NEVER")) return;
    float *g = nullptr;
    q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(sycl::range<1>(64), h);
        h.parallel_for(sycl::nd_range<1>(64, 64), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            const unsigned i = (unsigned)it.get_local_linear_id();
#if PRIVGEN == 0
            float *p = g;
#elif PRIVGEN == 1
            float *p = g[0] > 0 ? (float *)slm.get_multi_ptr<sycl::access::decorated::no>().get() : g;
#else
            float a[64];
            for (unsigned j = 0; j < 64; ++j) a[j] = g[j + i];
            float *p = g[0] > 0 ? a : g;
            slm[i] = 0;
#endif
            p[(unsigned)g[i] % 64] += 1.0f;
            g[i + 64] = p[i];
        });
    });
    // its module mate: a private array reached only directly (no generic pointer to it); scratch or global?
    q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> slm(sycl::range<1>(64), h);
        h.parallel_for(sycl::nd_range<1>(64, 64), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            const unsigned i = (unsigned)it.get_local_linear_id();
            float b[64];
            for (unsigned j = 0; j < 64; ++j) b[j] = g[j + i];
            slm[i] = b[(unsigned)g[i] % 64];
            g[i + 128] = slm[63 - i] + b[(unsigned)g[i + 1] % 64];
        });
    });
}
#endif
#ifdef PRIVTEST
// PRIVTEST=n: one more kernel in the module with n floats of private memory (a dynamically indexed array; qb-off-2's
// QbmHeavyK has 2,240 = 8,960 bytes): do the module's other private arrays move from scratch to global memory?
static void privtest(sycl::queue &q) {
    constexpr unsigned N = PRIVTEST;
    float *d = sycl::malloc_device<float>(64 * 32, q);
    const uint16_t *hp = sycl::malloc_device<uint16_t>(N, q);
    q.memset(d, 0, 64 * 32 * 4).wait();
    q.memset((void *)hp, 0, N * 2).wait();
    q.parallel_for(sycl::nd_range<1>(64 * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
         const unsigned g = (unsigned)it.get_global_linear_id();
         float a[N];
         for (unsigned i = 0; i < N; ++i) a[i] = iq3::half(hp[(i * 7 + g) % N]) + d[(i + g) % (64 * 32)];
         d[g] = a[(unsigned)d[(g * 13) % (64 * 32)] % N] + a[g % N];
     }).wait();
    sycl::free(d, q), sycl::free((void *)hp, q);
}
#endif
int main() {
    if (const char *e = getenv("REPS")) g_reps = std::max(1, atoi(e));
    if (const char *e = getenv("SEQMB")) g_seq_mb = atof(e);
    g_notime = getenv("NOTIME") != nullptr;
    g_only = getenv("ONLY");
    sycl::queue q{sycl::default_selector_v, sycl::property::queue::enable_profiling{}};
    const auto dev = q.get_device();
    std::printf("device %s", dev.get_info<sycl::info::device::name>().c_str());
    if (dev.has(sycl::aspect::ext_intel_pci_address))
        std::printf(" pci %s", dev.get_info<sycl::ext::intel::info::device::pci_address>().c_str());
    if (dev.has(sycl::aspect::ext_intel_free_memory)) {
        const double fg = (double)dev.get_info<sycl::ext::intel::info::device::free_memory>() / (1u << 30);
        std::printf(" free %.2f GiB", fg);
        if (fg < 4.0) { std::printf("\nless than 4 GiB free: not run\n"); return 2; }
    }
    std::printf("\n");
    std::fflush(stdout);
#ifdef PRIVTEST
    privtest(q);
#endif
#ifdef PRIVQB
    privqb(q);
#endif
#ifdef PRIVGEN
    privgen(q);
#endif
#ifdef PART_EG
    part_eg(q);
#endif
#ifdef PART_DENSE
    part_dense(q);
#endif
#ifdef PART_H16
    part_h16(q);
#endif
#ifdef PART_PICK
    part_pick(q);
#endif
#ifdef PART_DEC
    part_dec(q);
#endif
    std::printf("done: %d failed\n", g_fail);
    return g_fail ? 1 : 0;
}
