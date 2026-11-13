// xchg2_lat_bench (xchg2 helper, 2026-11-12; built as xlat): latency of a DEPENDENT chain producer -> exchange -> consumer on six B70s, at the
// engine's decode / check payloads, for today's exchange forms and one-destination-at-a-time push forms.
// One SYCL context per card, Level Zero IPC peers (as the engine), peer pointers only as direct kernel arguments
// (functor top-level fields or lambda captures), flags at uint32 16 * sender in the RECEIVER's arena (polled locally),
// poison word 96: after one timeout every later wait is skipped. Every spin is bounded (SPIN polls).
// Each round on every card: producer (16 work-groups, a dependent arithmetic loop of `work` iterations, then this card's
// rows of every slot into its own arena), the exchange, consumer (reads every card's rows of every slot, checks every
// float against the round's value; mismatches counted). Regions alternate A / B per round (an exchange region is
// rewritten only after a later exchange completed: the engine's rule). Round time = slowest card's time / rounds.
// Kinds (engine one-token / check layouts, six cards, M tokens):
//   H   (XP_H, output-b / ffn rows):  stride 5120, rows 848/848/864/848/848/864, M slots
//   OA  (XP_OA, output-a):            stride 8192, rows 1024/1024/2048/1024/1024/2048 (8,8,16,8,8,16 heads), M slots
//   ACT (XP_ACT, expert activations): stride 2304, rows 384 each, 7 M slots
// Forms:
//   noex   no exchange (cards independent; consumer does not count): the chain's own cost
//   pull   XchgPull as the engine (XPullK128: 128 registers, SIMD32; clamp((nv + 511) / 512, 4, 64) work-groups)
//   xp     XchgP as the engine (one work-group of 256, every item writes its 16 bytes to all peers in turn)
//   pushm  XchgPushM (clamp((nv + 2047) / 2048, 1, 64) groups, all peers per item) + XchgP without slots (xchg_m)
//   s1b    one work-group of 256 walks the peers in order me+1 .. me+5, group barrier between peers
//   s1n    the same without the barriers
//   s1b1k  s1b with a work-group of 1024
//   sk4    four work-groups, peer phases kept in lockstep by an on-card counter, the last group raises the flags
//   lpp6   five launches (launch p writes to peer me + p), then a flags + wait launch
//   lpp5   five launches, the fifth's last work-group raises the flags and waits
//   tail   the producer's last work-group pushes in peer order (s1b's body), raises the flags and waits (no launch)
//   flag   XchgP without slots: flags + wait only, no data (the floor; consumer does not count)
//   sk2 / sk8  sk4 with 2 / 8 groups;  snk4  sk4 without the lockstep;  s1b512  s1b with a group of 512
// Usage: xlat [rounds] [kinds e.g. H,OA,ACT] [Ms e.g. 1,2,3,4,5,6] [forms] [passes]
// Build: icpx -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -fsycl-targets=intel_gpu_bmg_g31
//        -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" xlat.cpp -o xlat -lze_loader
// Run with NEOReadDebugKeys=1 DisableIndirectAccess=1 ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 (as the engine).
#include <sycl/sycl.hpp>
#include <level_zero/ze_api.h>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>
#include <algorithm>
#include <atomic>
#include <barrier>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

namespace sx = sycl::ext::oneapi::experimental;
namespace ix = sycl::ext::intel::experimental;
using u32 = uint32_t;
using V4 = sycl::vec<float, 4>;
using AR = sycl::atomic_ref<u32, sycl::memory_order::relaxed, sycl::memory_scope::system, sycl::access::address_space::global_space>;
using ARD = sycl::atomic_ref<u32, sycl::memory_order::relaxed, sycl::memory_scope::device, sycl::access::address_space::global_space>;
static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }

// own-arena control words (uint32 index); peers write only 16 * sender (< 96)
constexpr u32 W_POISON = 96, W_CNT = 512, W_DONE = 528, W_BAD = 600, W_TMO = 616, W_SINK = 700;
constexpr size_t REG0 = 1024;
constexpr long SPIN = 2000000; // ~0.35 s of polls
constexpr long LSPIN = 2000000;

struct Lay {
    u32 off, stride, nslot;
    u32 b0[6], b1[6];
};
static inline float *pick(int d, float *p0, float *p1, float *p2, float *p3, float *p4, float *p5) {
    return d == 0 ? p0 : d == 1 ? p1 : d == 2 ? p2 : d == 3 ? p3 : d == 4 ? p4 : p5;
}
#define PP float *p0, float *p1, float *p2, float *p3, float *p4, float *p5
#define PA p0, p1, p2, p3, p4, p5
#define PF float *p0, *p1, *p2, *p3, *p4, *p5
static inline float val(u32 seed, u32 slot, u32 row) { return float((seed * 977u + slot * 7919u + row * 3u) & 0xFFFFFFu); }

static inline void wait_flags(sycl::nd_item<1> it, int n, int me, u32 seq, float *mine) {
    const int t = (int)it.get_local_linear_id();
    if (t < n && t != me) {
        AR poison(reinterpret_cast<u32 *>(mine)[W_POISON]);
        AR f(reinterpret_cast<u32 *>(mine)[16 * t]);
        long s = 0;
        if (!poison.load())
            while (f.load() < seq && ++s < SPIN) {}
        if (s >= SPIN) {
            poison.store(1u);
            AR(reinterpret_cast<u32 *>(mine)[W_TMO]).store(1u + (u32)t);
        }
    }
    sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
    sycl::group_barrier(it.get_group());
}
// after the group's data stores: system release, barrier, then items t < n store seq into peer t's flag word 16 * me
static inline void pub_flags(sycl::nd_item<1> it, int n, int me, u32 seq, PP) {
    sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
    sycl::group_barrier(it.get_group());
    const int t = (int)it.get_local_linear_id();
    if (t < n && t != me) AR(reinterpret_cast<u32 *>(pick(t, PA))[16 * me]).store(seq);
}
// this card's rows of every slot to peer d (items k0, k0 + ks, ...)
static inline void store_to(const Lay &L, int me, int d, size_t k0, size_t ks, PP) {
    const float *own = pick(me, PA) + L.off;
    float *dst = pick(d, PA) + L.off;
    const u32 n4 = (L.b1[me] - L.b0[me]) / 4;
    const size_t tot = (size_t)L.nslot * n4;
    for (size_t k = k0; k < tot; k += ks) {
        const size_t o = (size_t)(k / n4) * L.stride + L.b0[me] + (k % n4) * 4;
        *reinterpret_cast<V4 *>(dst + o) = *reinterpret_cast<const V4 *>(own + o);
    }
}
// one group walks the peers me + 1 .. me + n - 1 (bar: barrier between peers), then release + barrier
static inline void push_seq(sycl::nd_item<1> it, const Lay &L, int n, int me, bool bar, PP) {
    const size_t t = it.get_local_linear_id(), T = it.get_local_range(0);
    for (int p = 1; p < n; ++p) {
        store_to(L, me, (me + p) % n, t, T, PA);
        if (bar && p + 1 < n) sycl::group_barrier(it.get_group());
    }
}

// ---- producer: dependent loop, then this card's rows of every slot (seed) into its own arena
static inline void prod_body(sycl::nd_item<1> it, const Lay &L, int me, u32 seed, u32 work, float *mine) {
    float a = (float)(it.get_global_linear_id() & 1023u);
    for (u32 i = 0; i < work; ++i) a = a * 0.9999f + 0.5f;
    if (a == 1234567.0f) mine[W_SINK] = a;
    const u32 nr = L.b1[me] - L.b0[me];
    const size_t T = it.get_global_range(0);
    for (size_t k = it.get_global_linear_id(); k < (size_t)L.nslot * nr; k += T) {
        const u32 s = (u32)(k / nr), r = L.b0[me] + (u32)(k % nr);
        mine[L.off + (size_t)s * L.stride + r] = val(seed, s, r);
    }
}
struct Prod {
    Lay L;
    int me;
    u32 seed, work;
    float *mine;
    void operator()(sycl::nd_item<1> it) const { prod_body(it, L, me, seed, work, mine); }
    auto get(sx::properties_tag) const { return sx::properties{ix::grf_size<128>, sx::sub_group_size<32>}; }
};
// producer + tail: the group that finishes last pushes in peer order, raises the flags, waits
struct ProdTail {
    Lay L;
    int n, me;
    u32 seed, work, seq;
    PF;
    void operator()(sycl::nd_item<1> it) const {
        float *mine = pick(me, PA);
        prod_body(it, L, me, seed, work, mine);
        sycl::group_barrier(it.get_group());
        u32 last = 0;
        if (it.get_local_linear_id() == 0) {
            sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::device);
            ARD c(reinterpret_cast<u32 *>(mine)[W_DONE]);
            last = c.fetch_add(1u) + 1u == (u32)it.get_group_range(0) ? 1u : 0u;
            if (last) c.store(0u);
        }
        last = sycl::group_broadcast(it.get_group(), last, 0);
        if (!last) return;
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::device);
        push_seq(it, L, n, me, true, PA);
        pub_flags(it, n, me, seq, PA);
        wait_flags(it, n, me, seq, mine);
    }
    auto get(sx::properties_tag) const { return sx::properties{ix::grf_size<128>, sx::sub_group_size<32>}; }
};
// ---- consumer: every card's rows of every slot, checked
struct Cons {
    Lay L;
    int n;
    u32 seed, check;
    float *mine;
    void operator()(sycl::nd_item<1> it) const {
        const u32 tot = L.b1[n - 1];
        const size_t T = it.get_global_range(0);
        u32 bad = 0;
        float acc = 0.f;
        for (size_t k = it.get_global_linear_id(); k < (size_t)L.nslot * tot; k += T) {
            const u32 s = (u32)(k / tot), r = (u32)(k % tot);
            const float v = mine[L.off + (size_t)s * L.stride + r];
            acc += v;
            bad += v != val(seed, s, r);
        }
        if (check && bad) ARD(reinterpret_cast<u32 *>(mine)[W_BAD]).fetch_add(bad);
        if (acc == -1.0f) mine[W_SINK] = acc;
    }
    auto get(sx::properties_tag) const { return sx::properties{ix::grf_size<128>, sx::sub_group_size<32>}; }
};

// ---- today's pull (ops41sycl::XchgPull, mode 0, copy_seq) at 128 registers (XPullK128)
struct XPull {
    Lay L;
    int n, me;
    u32 seq;
    PF;
    void operator()(sycl::nd_item<1> it) const {
        const int t = (int)it.get_local_linear_id();
        float *mine = pick(me, PA);
        if (it.get_group_linear_id() == 0) {
            sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
            sycl::group_barrier(it.get_group());
            if (t < n && t != me) AR(reinterpret_cast<u32 *>(pick(t, PA))[16 * me]).store(seq);
        }
        wait_flags(it, n, me, seq, mine);
        const size_t T = it.get_global_range(0);
        size_t base = 0;
        for (int d = 0; d < n; ++d) {
            if (d == me) continue;
            const u32 n4 = (L.b1[d] - L.b0[d]) / 4;
            const size_t cnt = (size_t)L.nslot * n4;
            const float *src = pick(d, PA) + L.off;
            float *dst = mine + L.off;
            const size_t gid = it.get_global_linear_id();
            for (size_t k = (gid + T - base % T) % T; k < cnt; k += T) {
                const size_t o = (size_t)(k / n4) * L.stride + L.b0[d] + (k % n4) * 4;
                *reinterpret_cast<V4 *>(dst + o) = *reinterpret_cast<const V4 *>(src + o);
            }
            base += cnt;
        }
    }
    auto get(sx::properties_tag) const { return sx::properties{ix::grf_size<128>, sx::sub_group_size<32>}; }
};
// ---- today's XchgP body (mode 0): one group, every item all peers in turn; nslot 0: flags + wait only
static inline void xp_body(sycl::nd_item<1> it, const Lay &L, int n, int me, u32 seq, PP) {
    const unsigned t = (unsigned)it.get_local_linear_id(), T = (unsigned)it.get_local_range(0);
    float *mine = pick(me, PA);
    const float *own = mine + L.off;
    const unsigned n4 = (L.b1[me] - L.b0[me]) / 4;
    for (unsigned k = t; k < L.nslot * n4; k += T) {
        const size_t o = (size_t)(k / n4) * L.stride + L.b0[me] + (k % n4) * 4;
        const V4 v = *reinterpret_cast<const V4 *>(own + o);
        for (int d = 0; d < n; ++d)
            if (d != me) *reinterpret_cast<V4 *>(pick(d, PA) + L.off + o) = v;
    }
    pub_flags(it, n, me, seq, PA);
    wait_flags(it, n, me, seq, mine);
}
// ---- today's XchgPushM (stores only, every item all peers in turn, release)
static inline void pushm_body(sycl::nd_item<1> it, const Lay &L, int n, int me, PP) {
    const float *own = pick(me, PA) + L.off;
    const unsigned n4 = (L.b1[me] - L.b0[me]) / 4;
    const size_t T = it.get_global_range(0);
    for (size_t k = it.get_global_linear_id(); k < (size_t)L.nslot * n4; k += T) {
        const size_t o = (size_t)(k / n4) * L.stride + L.b0[me] + (k % n4) * 4;
        const V4 v = *reinterpret_cast<const V4 *>(own + o);
        for (int d = 0; d < n; ++d)
            if (d != me) *reinterpret_cast<V4 *>(pick(d, PA) + L.off + o) = v;
    }
    sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
}
// ---- s1b / s1n / s1b1k: one group, peers in order
struct Seq1 {
    Lay L;
    int n, me;
    u32 seq, bar;
    PF;
    void operator()(sycl::nd_item<1> it) const {
        push_seq(it, L, n, me, bar != 0, PA);
        pub_flags(it, n, me, seq, PA);
        wait_flags(it, n, me, seq, pick(me, PA));
    }
    auto get(sx::properties_tag) const { return sx::properties{ix::grf_size<128>, sx::sub_group_size<32>}; }
};
// ---- sk: G groups, peer phases in lockstep (on-card counter), the last group raises the flags and waits
struct SeqK {
    Lay L;
    int n, me;
    u32 seq, lock;
    PF;
    void operator()(sycl::nd_item<1> it) const {
        float *mine = pick(me, PA);
        u32 *w = reinterpret_cast<u32 *>(mine);
        const size_t g = it.get_group_linear_id(), G = it.get_group_range(0), t = it.get_local_linear_id(),
                     T = it.get_local_range(0);
        for (int p = 1; p < n; ++p) {
            store_to(L, me, (me + p) % n, g * T + t, G * T, PA);
            if (lock && p + 1 < n) {
                sycl::group_barrier(it.get_group());
                if (t == 0) {
                    ARD c(w[W_CNT]);
                    AR poison(w[W_POISON]);
                    c.fetch_add(1u);
                    long s = 0;
                    if (!poison.load())
                        while (c.load() < (u32)(G * p) && ++s < LSPIN) {}
                    if (s >= LSPIN) {
                        poison.store(1u);
                        AR(w[W_TMO]).store(100u + (u32)p);
                    }
                }
                sycl::group_barrier(it.get_group());
            }
        }
        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
        u32 last = 0;
        if (t == 0) {
            ARD d(w[W_DONE]);
            last = d.fetch_add(1u) + 1u == (u32)G ? 1u : 0u;
            if (last) {
                d.store(0u);
                ARD(w[W_CNT]).store(0u);
            }
        }
        last = sycl::group_broadcast(it.get_group(), last, 0);
        if (!last) return;
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::device);
        const int ti = (int)t;
        if (ti < n && ti != me) AR(reinterpret_cast<u32 *>(pick(ti, PA))[16 * me]).store(seq);
        wait_flags(it, n, me, seq, mine);
    }
    auto get(sx::properties_tag) const { return sx::properties{ix::grf_size<128>, sx::sub_group_size<32>}; }
};
// ---- lpp: launch p writes to peer me + p; fin: the last group raises the flags and waits
struct Lpp {
    Lay L;
    int n, me, p;
    u32 seq, fin;
    PF;
    void operator()(sycl::nd_item<1> it) const {
        store_to(L, me, (me + p) % n, it.get_global_linear_id(), it.get_global_range(0), PA);
        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
        if (!fin) return;
        float *mine = pick(me, PA);
        u32 *w = reinterpret_cast<u32 *>(mine);
        sycl::group_barrier(it.get_group());
        u32 last = 0;
        if (it.get_local_linear_id() == 0) {
            ARD d(w[W_DONE]);
            last = d.fetch_add(1u) + 1u == (u32)it.get_group_range(0) ? 1u : 0u;
            if (last) d.store(0u);
        }
        last = sycl::group_broadcast(it.get_group(), last, 0);
        if (!last) return;
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::device);
        const int t = (int)it.get_local_linear_id();
        if (t < n && t != me) AR(reinterpret_cast<u32 *>(pick(t, PA))[16 * me]).store(seq);
        wait_flags(it, n, me, seq, mine);
    }
    auto get(sx::properties_tag) const { return sx::properties{ix::grf_size<128>, sx::sub_group_size<32>}; }
};

enum Form { F_NOEX, F_PULL, F_XP, F_PUSHM, F_S1B, F_S1N, F_S1B1K, F_SK4, F_LPP6, F_LPP5, F_TAIL, F_FLAG, F_SK2, F_SK8, F_SNK4, F_S1B512, F_N };
static const char *FN[F_N] = {"noex", "pull", "xp", "pushm", "s1b", "s1n", "s1b1k", "sk4", "lpp6", "lpp5", "tail", "flag", "sk2", "sk8", "snk4", "s1b512"};

int main(int argc, char **argv) {
    setvbuf(stdout, nullptr, _IONBF, 0);
    const int R = argc > 1 ? atoi(argv[1]) : 1000;
    auto split = [](const std::string &s) {
        std::vector<std::string> v;
        size_t p = 0;
        while (p <= s.size()) {
            size_t q = s.find(',', p);
            if (q == std::string::npos) q = s.size();
            if (q > p) v.push_back(s.substr(p, q - p));
            p = q + 1;
        }
        return v;
    };
    const auto kinds = split(argc > 2 ? argv[2] : "H,OA,ACT");
    std::vector<int> Ms;
    for (auto &x : split(argc > 3 ? argv[3] : "1,2,3,4,5,6")) Ms.push_back(atoi(x.c_str()));
    std::vector<int> forms;
    for (auto &x : split(argc > 4 ? argv[4] : "noex,pull,xp,pushm,s1b,s1n,s1b1k,sk4,lpp6,lpp5,tail"))
        for (int f = 0; f < F_N; ++f)
            if (x == FN[f]) forms.push_back(f);
    const int passes = argc > 5 ? atoi(argv[5]) : 2;

    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const int N = (int)l0.size();
    if (N != 6) { std::printf("need 6 cards, have %d\n", N); return 1; }
    const size_t RSZ = 7 * 6 * 2304; // the largest region (ACT, 6 tokens), floats; multiple of 16
    const size_t AW = REG0 + 2 * RSZ;
    std::vector<sycl::context> ctx;
    std::vector<sycl::queue> q;
    std::vector<float *> arena(N);
    for (int c = 0; c < N; ++c) {
        ctx.emplace_back(l0[c]);
        q.emplace_back(ctx[c], l0[c], sycl::property::queue::in_order{});
        arena[c] = sycl::malloc_device<float>(AW, q[c]);
        q[c].memset(arena[c], 0, AW * 4).wait();
    }
    std::vector<std::vector<float *>> peer(N, std::vector<float *>(N, nullptr));
    for (int d = 0; d < N; ++d) {
        ze_ipc_mem_handle_t h;
        auto zxd = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[d]);
        if (zeMemGetIpcHandle(zxd, arena[d], &h) != ZE_RESULT_SUCCESS) { std::printf("ipc get failed\n"); return 1; }
        for (int c = 0; c < N; ++c) {
            if (c == d) { peer[c][d] = arena[d]; continue; }
            void *p = nullptr;
            auto zxc = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[c]);
            auto zdc = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(l0[c]);
            if (zeMemOpenIpcHandle(zxc, zdc, h, 0, &p) != ZE_RESULT_SUCCESS || !p) { std::printf("ipc open failed\n"); return 1; }
            peer[c][d] = (float *)p;
        }
    }
    // make every peer mapping resident on every card once (direct pointer arguments)
    for (int c = 0; c < N; ++c)
        for (int d = 0; d < N; ++d) {
            float *pp = peer[c][d];
            const int z = 0;
            q[c].single_task([=] { if (z) pp[0] = 0.f; }).wait();
        }
    auto layout = [&](const std::string &k, int M, int X) {
        Lay L{};
        L.off = (u32)(REG0 + (size_t)X * RSZ);
        if (k == "H") {
            L.stride = 5120, L.nslot = M;
            const u32 b[7] = {0, 848, 1696, 2560, 3408, 4256, 5120};
            for (int d = 0; d < 6; ++d) L.b0[d] = b[d], L.b1[d] = b[d + 1];
        } else if (k == "OA") {
            L.stride = 8192, L.nslot = M;
            const u32 b[7] = {0, 1024, 2048, 4096, 5120, 6144, 8192};
            for (int d = 0; d < 6; ++d) L.b0[d] = b[d], L.b1[d] = b[d + 1];
        } else {
            L.stride = 2304, L.nslot = 7 * M;
            for (int d = 0; d < 6; ++d) L.b0[d] = 384 * d, L.b1[d] = 384 * (d + 1);
        }
        return L;
    };
    std::barrier sync(N);
    std::atomic<int> abort_all{0};
    u32 cfg_id = 0;
    struct Res { double us; u32 bad, tmo; };
    // run one configuration on every card; returns the slowest card's time per round
    auto run = [&](const std::string &kind, int M, int form, u32 work0, u32 workh, int rounds) -> Res {
        const u32 cid = ++cfg_id;
        std::vector<double> t(N, 0.0);
        std::vector<u32> bad(N, 0), tmo(N, 0);
        auto body = [&](int c) {
            float *p0 = peer[c][0], *p1 = peer[c][1], *p2 = peer[c][2], *p3 = peer[c][3], *p4 = peer[c][4], *p5 = peer[c][5];
            float *mine = arena[c];
            q[c].memset(mine, 0, REG0 * 4).wait(); // flags, poison, counters, error words
            sync.arrive_and_wait();
            const u32 work = (c == 2 || c == 5) ? workh : work0;
            u32 seq = 0;
            const int W = 50;
            double t0 = 0;
            for (int r = 0; r < W + rounds; ++r) {
                if (r == W) {
                    q[c].wait();
                    sync.arrive_and_wait();
                    t0 = now();
                }
                const Lay L = layout(kind, M, r & 1);
                const u32 seed = cid * 100003u + (u32)r + 1u;
                const u32 nr = L.b1[c] - L.b0[c], n4 = nr / 4;
                const size_t own4 = (size_t)L.nslot * n4;
                size_t nv = 0;
                for (int d = 0; d < N; ++d)
                    if (d != c) nv += (size_t)L.nslot * ((L.b1[d] - L.b0[d]) / 4);
                const sycl::nd_range<1> pr(16 * 256, 256);
                if (form == F_TAIL) {
                    ++seq;
                    q[c].parallel_for(pr, ProdTail{L, N, c, seed, work, seq, PA});
                } else {
                    q[c].parallel_for(pr, Prod{L, c, seed, work, mine});
                }
                switch (form) {
                case F_NOEX: case F_TAIL: break;
                case F_PULL: {
                    ++seq;
                    const size_t nwg = std::clamp<size_t>((nv + 511) / 512, 4, 64);
                    q[c].parallel_for(sycl::nd_range<1>(nwg * 256, 256), XPull{L, N, c, seq, PA});
                    break;
                }
                case F_XP: {
                    ++seq;
                    const int me = c, n = N;
                    const u32 s = seq;
                    q[c].submit([&](sycl::handler &h) {
                        h.parallel_for(sycl::nd_range<1>(256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                            xp_body(it, L, n, me, s, PA);
                        });
                    });
                    break;
                }
                case F_PUSHM: {
                    ++seq;
                    const int me = c, n = N;
                    const u32 s = seq;
                    const size_t nwg = std::max<size_t>(1, std::min<size_t>(64, (own4 + 2047) / 2048));
                    q[c].submit([&](sycl::handler &h) {
                        h.parallel_for(sycl::nd_range<1>(nwg * 256, 256), [=](sycl::nd_item<1> it) { pushm_body(it, L, n, me, PA); });
                    });
                    Lay L0 = L;
                    L0.nslot = 0;
                    q[c].submit([&](sycl::handler &h) {
                        h.parallel_for(sycl::nd_range<1>(256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                            xp_body(it, L0, n, me, s, PA);
                        });
                    });
                    break;
                }
                case F_FLAG: {
                    ++seq;
                    const int me = c, n = N;
                    const u32 s = seq;
                    Lay L0 = L;
                    L0.nslot = 0;
                    q[c].submit([&](sycl::handler &h) {
                        h.parallel_for(sycl::nd_range<1>(256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                            xp_body(it, L0, n, me, s, PA);
                        });
                    });
                    break;
                }
                case F_SK2: case F_SK8: case F_SNK4: {
                    ++seq;
                    const size_t g = form == F_SK2 ? 2 : form == F_SK8 ? 8 : 4;
                    q[c].parallel_for(sycl::nd_range<1>(g * 256, 256), SeqK{L, N, c, seq, form == F_SNK4 ? 0u : 1u, PA});
                    break;
                }
                case F_S1B: case F_S1N: case F_S1B1K: case F_S1B512: {
                    ++seq;
                    const size_t wg = form == F_S1B1K ? 1024 : form == F_S1B512 ? 512 : 256;
                    q[c].parallel_for(sycl::nd_range<1>(wg, wg), Seq1{L, N, c, seq, form == F_S1N ? 0u : 1u, PA});
                    break;
                }
                case F_SK4: {
                    ++seq;
                    q[c].parallel_for(sycl::nd_range<1>(4 * 256, 256), SeqK{L, N, c, seq, 1u, PA});
                    break;
                }
                case F_LPP6: case F_LPP5: {
                    ++seq;
                    const size_t g = std::clamp<size_t>((own4 + 255) / 256, 1, 16);
                    for (int p = 1; p < N; ++p)
                        q[c].parallel_for(sycl::nd_range<1>(g * 256, 256),
                                          Lpp{L, N, c, p, seq, (form == F_LPP5 && p == N - 1) ? 1u : 0u, PA});
                    if (form == F_LPP6) {
                        const int me = c, n = N;
                        const u32 s = seq;
                        Lay L0 = L;
                        L0.nslot = 0;
                        q[c].submit([&](sycl::handler &h) {
                            h.parallel_for(sycl::nd_range<1>(256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                                xp_body(it, L0, n, me, s, PA);
                            });
                        });
                    }
                    break;
                }
                }
                q[c].parallel_for(pr, Cons{L, N, seed, (form == F_NOEX || form == F_FLAG) ? 0u : 1u, mine});
            }
            q[c].wait();
            t[c] = now() - t0;
            u32 w[2];
            q[c].memcpy(&w[0], reinterpret_cast<u32 *>(mine) + W_BAD, 4).wait();
            q[c].memcpy(&w[1], reinterpret_cast<u32 *>(mine) + W_TMO, 4).wait();
            bad[c] = w[0], tmo[c] = w[1];
            sync.arrive_and_wait();
        };
        std::vector<std::thread> th;
        for (int c = 0; c < N; ++c) th.emplace_back(body, c);
        for (auto &x : th) x.join();
        Res r{0, 0, 0};
        for (int c = 0; c < N; ++c) r.us = std::max(r.us, t[c] / rounds * 1e6), r.bad += bad[c], r.tmo += tmo[c] != 0;
        return r;
    };
    // calibration: the producer loop's cost (noex, H, M = 1, all cards alike)
    const double c0 = run("H", 1, F_NOEX, 0, 0, 300).us, c1 = run("H", 1, F_NOEX, 4000, 4000, 300).us;
    const double per = (c1 - c0) / 4000.0; // us per iteration
    const u32 w0 = (u32)std::max(0.0, 6.0 / std::max(per, 1e-6)), wh = (u32)std::max(0.0, 18.0 / std::max(per, 1e-6));
    std::printf("calibration: noex round %.2f us at work 0, %.2f at 4000 -> %.5f us per iteration; base work %u (+6 us), "
                "heavy cards 2/5 work %u (+18 us)\n", c0, c1, per, w0, wh);
    std::printf("%-4s %2s %-5s %-6s %9s %9s %6s %4s\n", "kind", "M", "bal", "form", "us/round", "xchg_us", "bad", "tmo");
    for (int pass = 0; pass < passes && !abort_all; ++pass)
        for (auto &k : kinds)
            for (int M : Ms)
                for (int bal = 0; bal < 2 && !abort_all; ++bal) {
                    double base = -1;
                    for (int f : forms) {
                        const Res r = run(k, M, f, w0, bal ? wh : w0, R);
                        if (f == F_NOEX) base = r.us;
                        std::printf("%-4s %2d %-5s %-6s %9.2f %9.2f %6u %4u%s\n", k.c_str(), M, bal ? "heavy" : "even", FN[f], r.us,
                                    base >= 0 && f != F_NOEX ? r.us - base : 0.0, r.bad, r.tmo, pass ? "  (pass 2)" : "");
                        if (r.tmo) {
                            std::printf("TIMEOUT: stopping\n");
                            abort_all = 1;
                            break;
                        }
                    }
                }
    for (int c = 0; c < N; ++c)
        for (int d = 0; d < N; ++d)
            if (c != d) zeMemCloseIpcHandle(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctx[c]), peer[c][d]);
    return abort_all ? 3 : 0;
}
