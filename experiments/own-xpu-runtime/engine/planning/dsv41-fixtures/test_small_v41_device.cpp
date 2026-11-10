// Gate + timing for the latency-bound small-op kernels (sycl_v41.hpp
// "small per-layer ops"): each new form against the kernel it replaces, on
// the same inputs, BITWISE on every output it writes, plus the GPU time of
// both (event profiling). Exit status = number of failed checks.
//
//   $ICPX -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -I planning/dsv41-fixtures -I src planning/dsv41-fixtures/test_small_v41_device.cpp -o /tmp/test_small41
//   LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib /tmp/test_small41 [CARD]
#include <sycl/sycl.hpp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

static int g_fail = 0;
template <typename T> static size_t ndiff(const std::vector<T> &a, const std::vector<T> &b) {
    size_t n = 0;
    for (size_t i = 0; i < a.size(); ++i) n += std::memcmp(&a[i], &b[i], sizeof(T)) != 0;
    return n;
}
static void report(const char *name, size_t diff, size_t n, double t0, double t1) {
    g_fail += diff != 0;
    std::printf("%s %-28s old %8.2f us  new %8.2f us  x%5.2f | differ %zu of %zu\n", diff ? "FAIL" : "ok  ", name, t0, t1,
                t0 / t1, diff, n);
    std::fflush(stdout);
}

int main(int argc, char **argv) {
    int card = argc > 1 ? atoi(argv[1]) : 0;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    sycl::device dev = l0.at(card);
    sycl::context ctx(dev);
    sycl::queue q(ctx, dev, sycl::property_list{sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    std::printf("card %d %s\n", card, dev.get_info<sycl::info::device::name>().c_str());
    std::mt19937 rng(5);
    auto U = [&](float a, float b) { return std::uniform_real_distribution<float>(a, b)(rng); };
    // GPU time per launch: 40 launches back to back (the card stays busy and
    // clocked up), span from the first start to the last end
    auto gpu_us = [&](auto submit) {
        for (int i = 0; i < 5; ++i) submit();
        q.wait();
        sycl::event a = submit();
        for (int i = 0; i < 38; ++i) submit();
        sycl::event b = submit();
        b.wait();
        return (b.get_profiling_info<sycl::info::event_profiling::command_end>() -
                a.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3 / 40;
    };
    auto dev_vec = [&](const auto &h) {
        using T = typename std::decay_t<decltype(h)>::value_type;
        T *p = sycl::malloc_device<T>(h.size(), q);
        q.memcpy(p, h.data(), h.size() * sizeof(T)).wait();
        return p;
    };
    auto host = [&](const auto *p, size_t n) {
        using T = std::remove_const_t<std::remove_pointer_t<decltype(p)>>;
        std::vector<T> h(n);
        q.memcpy(h.data(), p, n * sizeof(T)).wait();
        return h;
    };
    auto sg32 = [&](size_t groups, auto k) {
        return q.parallel_for(sycl::nd_range<1>(groups * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it); });
    };

    // ---- RmsNorm --------------------------------------------------------------
    auto rms = [&](auto NC) {
        constexpr unsigned N = decltype(NC)::value;
        std::vector<float> hx(N), hw(N);
        for (auto &v : hx) v = U(-3, 3);
        for (auto &v : hw) v = U(0.2f, 2.0f);
        float *x = dev_vec(hx), *w = dev_vec(hw), *y0 = sycl::malloc_device<float>(N, q), *y1 = sycl::malloc_device<float>(N, q);
        RmsNormA<ActF32> k0{(int)N};
        RmsNormP<N> k1{};
        double t0 = gpu_us([&] { return sg32(1, [=](sycl::nd_item<1> it) { k0(it, x, w, y0); }); });
        double t1 = gpu_us([&] { return sg32(1, [=](sycl::nd_item<1> it) { k1(it, x, w, y1); }); });
        char nm[64];
        std::snprintf(nm, sizeof nm, "RmsNorm n=%u", N);
        report(nm, ndiff(host(y0, N), host(y1, N)), N, t0, t1);
    };
    rms(std::integral_constant<unsigned, 512>{});
    rms(std::integral_constant<unsigned, 1280>{});
    rms(std::integral_constant<unsigned, 5120>{});

    // ---- hc mix: dots + finish -----------------------------------------------
    {
        const int H = 5120, SEG = 8, N = 4 * H;
        std::vector<float> hs(N), hfn((size_t)24 * N), hsc(3), hb(24);
        for (auto &v : hs) v = U(-2, 2);
        for (auto &v : hfn) v = U(-0.02f, 0.02f);
        for (auto &v : hsc) v = U(0.5f, 2.0f);
        for (auto &v : hb) v = U(-1, 1);
        float *st = dev_vec(hs), *fn = dev_vec(hfn), *sc = dev_vec(hsc), *bs = dev_vec(hb);
        double *d0 = sycl::malloc_device<double>(25 * SEG, q), *d1 = sycl::malloc_device<double>(25 * SEG, q);
        HcMixDots32A<ActF32> k0{H, SEG};
        HcMixDotsP<5120, 8> k1{};
        double t0 = gpu_us([&] { return sg32(25 * SEG, [=](sycl::nd_item<1> it) { k0(it, st, fn, d0); }); });
        double t1 = gpu_us([&] { return sg32(25 * SEG, [=](sycl::nd_item<1> it) { k1(it, st, fn, d1); }); });
        report("HcMixDots", ndiff(host(d0, 25 * SEG), host(d1, 25 * SEG)), 25 * SEG, t0, t1);
        float *o0 = sycl::malloc_device<float>(24, q), *o1 = sycl::malloc_device<float>(24, q);
        HcMixFinishSeg f0{H, SEG};
        HcMixFinishSG f1{H, SEG};
        t0 = gpu_us([&] {
            return q.parallel_for(sycl::nd_range<1>(1, 1), [=](sycl::nd_item<1> it) { f0(it, d0, sc, bs, o0, o0 + 4, o0 + 8); });
        });
        t1 = gpu_us([&] { return sg32(1, [=](sycl::nd_item<1> it) { f1(it, d0, sc, bs, o1, o1 + 4, o1 + 8); }); });
        report("HcMixFinish (pre/post/comb)", ndiff(host(o0, 24), host(o1, 24)), 24, t0, t1);
    }

    // ---- engram gate -------------------------------------------------------------
    {
        const int H = 5120;
        std::vector<float> hs(4 * H), hk(5 * H), hg(4 * H);
        for (auto &v : hs) v = U(-2, 2);
        for (auto &v : hk) v = U(-1, 1);
        for (auto &v : hg) v = U(-0.5f, 0.5f);
        float *s0 = dev_vec(hs), *s1 = dev_vec(hs), *kv = dev_vec(hk), *gw = dev_vec(hg);
        EngramGateA<ActF32> e0{H};
        EngramGateP e1{H};
        q.parallel_for(sycl::nd_range<1>(4, 4), [=](sycl::nd_item<1> it) { e0(it, s0, kv, gw); });
        sg32(4, [=](sycl::nd_item<1> it) { e1(it, s1, kv, gw); });
        q.wait();
        const size_t d = ndiff(host(s0, 4 * H), host(s1, 4 * H));
        double t0 = gpu_us([&] { return q.parallel_for(sycl::nd_range<1>(4, 4), [=](sycl::nd_item<1> it) { e0(it, s0, kv, gw); }); });
        double t1 = gpu_us([&] { return sg32(4, [=](sycl::nd_item<1> it) { e1(it, s1, kv, gw); }); });
        report("EngramGate", d, 4 * H, t0, t1);
    }
    // ---- argmax (ties of the maximum planted, +0/-0, NaN) -----------------------
    for (int trial = 0; trial < 3; ++trial) {
        const int V = 129280;
        std::vector<float> hl(V);
        for (auto &v : hl) v = U(-10, 10);
        if (trial == 0) { hl[70001] = 50.0f; hl[123] = 50.0f; hl[129279] = 50.0f; }
        if (trial == 1) { for (auto &v : hl) v = v > 0 ? -v : v; hl[777] = -0.0f; hl[500] = 0.0f; hl[9000] = NAN; }
        if (trial == 2) { for (auto &v : hl) v = -INFINITY; hl[64] = NAN; }
        float *lg = dev_vec(hl), *bv = sycl::malloc_device<float>(1024, q);
        int32_t *bi = sycl::malloc_device<int32_t>(1024, q), *r0 = sycl::malloc_device<int32_t>(1, q), *r1 = sycl::malloc_device<int32_t>(1, q);
        Argmax a0{V};
        const int CH = 512, G = (V + CH - 1) / CH;
        ArgmaxP1 p1{V, CH};
        ArgmaxP2 p2{G};
        auto run1 = [&] {
            sg32(G, [=](sycl::nd_item<1> it) { p1(it, lg, bv, bi); });
            return sg32(1, [=](sycl::nd_item<1> it) { p2(it, bv, bi, r1); });
        };
        double t0 = gpu_us([&] { return sg32(1, [=](sycl::nd_item<1> it) { a0(it, lg, r0, (float *)nullptr); }); });
        double t1 = gpu_us(run1) * 2; // two launches per call
        const auto x0 = host(r0, 1), x1 = host(r1, 1);
        char nm[64];
        std::snprintf(nm, sizeof nm, "Argmax trial %d (idx %d)", trial, x0[0]);
        report(nm, ndiff(x0, x1), 1, t0, t1);
    }

    // ---- sparse attention ------------------------------------------------------
    for (int n_idx : {128, 640}) {
        const int HEADS = 64, HD = 512, WIN = 128, NC = 700;
        std::vector<float> hq((size_t)HEADS * HD), hsk(HEADS);
        for (auto &v : hq) v = U(-1, 1);
        for (auto &v : hsk) v = U(-2, 2);
        std::vector<uint16_t> hkw((size_t)WIN * HD), hkc((size_t)NC * HD);
        for (auto &v : hkw) v = ops41::bf16b(U(-1, 1));
        for (auto &v : hkc) v = ops41::bf16b(U(-1, 1));
        std::vector<int32_t> hid(n_idx);
        for (int i = 0; i < n_idx; ++i) {
            const int r = int(rng() % 10);
            hid[i] = r == 0 ? -1 : (i < 128 ? i : WIN + int(rng() % NC)); // window slots, then compressed, ~10 % masked
        }
        float *qd = dev_vec(hq), *sk = dev_vec(hsk);
        uint16_t *kw = dev_vec(hkw), *kc = dev_vec(hkc);
        int32_t *id = dev_vec(hid);
        const size_t ns = (size_t)HEADS * n_idx;
        float *s0 = sycl::malloc_device<float>(ns, q), *s1 = sycl::malloc_device<float>(ns, q);
        q.memset(s0, 0, ns * 4);
        q.memset(s1, 0, ns * 4).wait();
        SparseScoreA<ActF32> a0{n_idx, HEADS, HD, WIN};
        SparseScoreP<512> a1{n_idx, HEADS, WIN, HD};
        double t0 = gpu_us([&] {
            return q.parallel_for(sycl::nd_range<1>(ns, 32), [=](sycl::nd_item<1> it) { a0(it, qd, kw, kc, id, s0); });
        });
        double t1 = gpu_us([&] { return sg32(ns / 32, [=](sycl::nd_item<1> it) { a1(it, qd, kw, kc, id, s1); }); });
        char nm[64];
        std::snprintf(nm, sizeof nm, "SparseScore n_idx=%d", n_idx);
        report(nm, ndiff(host(s0, ns), host(s1, ns)), ns, t0, t1);
        auto score_hg = [&](auto HGC) {
            constexpr unsigned HG = decltype(HGC)::value;
            q.memset(s1, 0, ns * 4).wait();
            SparseScoreHG<512, HG> a2{n_idx, HEADS, WIN, HD};
            double t2 = gpu_us([&] {
                return sg32((size_t)(HEADS / HG) * (n_idx / 32), [=](sycl::nd_item<1> it) { a2(it, qd, kw, kc, id, s1); });
            });
            char nm2[64];
            std::snprintf(nm2, sizeof nm2, "SparseScoreHG%u n_idx=%d", HG, n_idx);
            report(nm2, ndiff(host(s0, ns), host(s1, ns)), ns, t0, t2);
        };
        score_hg(std::integral_constant<unsigned, 4>{});
        score_hg(std::integral_constant<unsigned, 8>{});
        // softmax on copies of the same scores (in place), timed on scratch copies
        float *c0 = sycl::malloc_device<float>(ns, q), *c1 = sycl::malloc_device<float>(ns, q);
        SparseSoftmax m0{n_idx, HEADS};
        auto run_sm1 = [&](float *p) {
            if (n_idx == 128) {
                SparseSoftmaxP<128> m1{HEADS};
                return sg32(HEADS, [=](sycl::nd_item<1> it) { m1(it, sk, id, p); });
            }
            SparseSoftmaxP<640> m1{HEADS};
            return sg32(HEADS, [=](sycl::nd_item<1> it) { m1(it, sk, id, p); });
        };
        q.memcpy(c0, s0, ns * 4);
        q.memcpy(c1, s0, ns * 4).wait();
        t0 = gpu_us([&] { return q.parallel_for(sycl::nd_range<1>(HEADS, 8), [=](sycl::nd_item<1> it) { m0(it, sk, id, c0); }); });
        t1 = gpu_us([&] { return run_sm1(c1); });
        q.memcpy(c0, s0, ns * 4);
        q.memcpy(c1, s0, ns * 4).wait();
        q.parallel_for(sycl::nd_range<1>(HEADS, 8), [=](sycl::nd_item<1> it) { m0(it, sk, id, c0); });
        run_sm1(c1);
        q.wait();
        std::snprintf(nm, sizeof nm, "SparseSoftmax n_idx=%d", n_idx);
        report(nm, ndiff(host(c0, ns), host(c1, ns)), ns, t0, t1);
        float *w0 = c0; // softmax weights
        float *o0 = sycl::malloc_device<float>((size_t)HEADS * HD, q), *o1 = sycl::malloc_device<float>((size_t)HEADS * HD, q);
        SparseOut u0{n_idx, HEADS, HD, WIN};
        SparseOutP<512> u1{n_idx, HEADS, WIN};
        t0 = gpu_us([&] {
            return q.parallel_for(sycl::nd_range<1>((size_t)HEADS * HD, 32), [=](sycl::nd_item<1> it) { u0(it, kw, kc, id, w0, o0); });
        });
        t1 = gpu_us([&] {
            return q.parallel_for(sycl::nd_range<1>((size_t)HEADS * HD, 32), [=](sycl::nd_item<1> it) { u1(it, kw, kc, id, w0, o1); });
        });
        std::snprintf(nm, sizeof nm, "SparseOut n_idx=%d", n_idx);
        report(nm, ndiff(host(o0, (size_t)HEADS * HD), host(o1, (size_t)HEADS * HD)), (size_t)HEADS * HD, t0, t1);
        auto out_hg = [&](auto HGC) {
            constexpr unsigned HG = decltype(HGC)::value;
            q.memset(o1, 0, (size_t)HEADS * HD * 4).wait();
            SparseOutHG<512, HG> u2{n_idx, HEADS, WIN};
            double t2 = gpu_us([&] {
                return sg32((size_t)(HEADS / HG) * (HD / 32), [=](sycl::nd_item<1> it) { u2(it, kw, kc, id, w0, o1); });
            });
            char nm2[64];
            std::snprintf(nm2, sizeof nm2, "SparseOutHG%u n_idx=%d", HG, n_idx);
            report(nm2, ndiff(host(o0, (size_t)HEADS * HD), host(o1, (size_t)HEADS * HD)), (size_t)HEADS * HD, t0, t2);
        };
        {
            q.memset(o1, 0, (size_t)HEADS * HD * 4).wait();
            SparseOutP2<512> u3{n_idx, HEADS, WIN};
            double t3 = gpu_us([&] { return sg32((size_t)HEADS * HD / 32, [=](sycl::nd_item<1> it) { u3(it, kw, kc, id, w0, o1); }); });
            std::snprintf(nm, sizeof nm, "SparseOutP2 n_idx=%d", n_idx);
            report(nm, ndiff(host(o0, (size_t)HEADS * HD), host(o1, (size_t)HEADS * HD)), (size_t)HEADS * HD, t0, t3);
        }
        auto out_j = [&](auto JPC) {
            constexpr unsigned JP = decltype(JPC)::value;
            q.memset(o1, 0, (size_t)HEADS * HD * 4).wait();
            SparseOutJ<512, JP> u4{n_idx, HEADS, WIN};
            double t4 = gpu_us([&] { return sg32((size_t)HEADS * HD / 32 / JP, [=](sycl::nd_item<1> it) { u4(it, kw, kc, id, w0, o1); }); });
            char nm2[64];
            std::snprintf(nm2, sizeof nm2, "SparseOutJ%u n_idx=%d", JP, n_idx);
            report(nm2, ndiff(host(o0, (size_t)HEADS * HD), host(o1, (size_t)HEADS * HD)), (size_t)HEADS * HD, t0, t4);
        };
        out_j(std::integral_constant<unsigned, 1>{});
        out_j(std::integral_constant<unsigned, 2>{});
        out_j(std::integral_constant<unsigned, 4>{});
        out_j(std::integral_constant<unsigned, 8>{});
        if (getenv("ALL_VARIANTS")) {
            out_hg(std::integral_constant<unsigned, 2>{});
            out_hg(std::integral_constant<unsigned, 4>{});
            out_hg(std::integral_constant<unsigned, 8>{});
        }
    }

    // ---- window append + index list (positions around the ring wrap) ------------
    for (int sp : {0, 5, 126, 127, 128, 129, 300, 4095}) {
        const int WIN = 128, D = 512, NC = 512;
        std::vector<float> hkv(D);
        for (auto &v : hkv) v = U(-3, 3);
        std::vector<int32_t> hci(NC);
        for (auto &v : hci) v = (int32_t)(rng() % 1000) - 1;
        std::vector<uint16_t> hring((size_t)WIN * D);
        for (auto &v : hring) v = uint16_t(rng());
        float *kv = dev_vec(hkv);
        int32_t *ci = dev_vec(hci);
        uint16_t *ring0 = dev_vec(hring), *ring1 = dev_vec(hring);
        int32_t *w0 = sycl::malloc_device<int32_t>(WIN, q), *w1 = sycl::malloc_device<int32_t>(WIN, q);
        int32_t *c0 = sycl::malloc_device<int32_t>(WIN + NC, q), *c1 = sycl::malloc_device<int32_t>(WIN + NC, q);
        WindowAppendA<ActF32> k0{WIN, D, sp};
        WindowAppendP<ActF32> k1{WIN, D, sp, NC};
        auto run0 = [&] {
            q.parallel_for(sycl::nd_range<1>(1, 1), [=](sycl::nd_item<1> it) { k0(it, ring0, kv, w0); });
            q.memcpy(c0, w0, WIN * 4);
            return q.memcpy(c0 + WIN, ci, NC * 4);
        };
        auto run1 = [&] { return q.parallel_for(sycl::nd_range<1>(512, 64), [=](sycl::nd_item<1> it) { k1(it, ring1, kv, w1, c1, ci); }); };
        run0();
        run1();
        q.wait();
        size_t d = ndiff(host(ring0, (size_t)WIN * D), host(ring1, (size_t)WIN * D)) + ndiff(host(w0, WIN), host(w1, WIN)) +
                   ndiff(host(c0, WIN + NC), host(c1, WIN + NC));
        double t0 = gpu_us(run0) * 3, t1 = gpu_us(run1); // old: one launch + two copies per call
        char nm[64];
        std::snprintf(nm, sizeof nm, "WindowAppend+idx pos=%d", sp);
        report(nm, d, (size_t)WIN * D + WIN + WIN + NC, t0, t1);
    }

    // ---- router: score + rank + normalize (ties planted) -------------------------
    for (int trial = 0; trial < 4; ++trial) {
        const int E = 256, K = 6;
        std::vector<float> hl(E), hb(E), hp0(K, 0.25f);
        for (auto &v : hl) v = U(-4, 4);
        for (auto &v : hb) v = U(-0.5f, 0.5f);
        if (trial >= 1) { hl[17] = hl[200] = 9.0f; hb[17] = hb[200] = 0.1f; }        // exact tie at the top
        if (trial >= 2) { hl[3] = hl[4] = hl[5] = 7.5f; hb[3] = hb[4] = hb[5] = 0.0f; } // three-way tie inside top 6
        if (trial == 3) for (auto &v : hl) v = std::round(v);                           // many ties
        float *lg = dev_vec(hl), *bs = dev_vec(hb), *rs = sycl::malloc_device<float>(E, q), *rsb = sycl::malloc_device<float>(E, q);
        float *p0 = dev_vec(hp0), *p1 = dev_vec(hp0);
        uint32_t *i0 = sycl::malloc_device<uint32_t>(K, q), *i1 = sycl::malloc_device<uint32_t>(K, q);
        RouteScore a{E};
        RouteRank b{E, K};
        RouteNorm c{K};
        RouteP r1{E, K};
        auto run0 = [&] {
            q.parallel_for(sycl::nd_range<1>(E, 32), [=](sycl::nd_item<1> it) { a(it, lg, bs, rs, rsb); });
            q.parallel_for(sycl::nd_range<1>(E, 32), [=](sycl::nd_item<1> it) { b(it, rs, rsb, i0, p0); });
            return q.parallel_for(sycl::nd_range<1>(1, 1), [=](sycl::nd_item<1> it) { c(it, p0); });
        };
        auto run1 = [&] {
            return q.submit([&](sycl::handler &h) {
                sycl::local_accessor<float, 1> lm(2 * E + K, h);
                h.parallel_for(sycl::nd_range<1>(E, E), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                    r1(it, lg, bs, i1, p1, &lm[0]);
                });
            });
        };
        run0();
        run1();
        q.wait();
        const auto ia = host(i0, K), ib = host(i1, K);
        size_t d = ndiff(ia, ib) + ndiff(host(p0, K), host(p1, K));
        double t0 = gpu_us(run0) * 3, t1 = gpu_us(run1);
        char nm[64];
        std::snprintf(nm, sizeof nm, "Route trial %d (top %u %u)", trial, ia[0], ia[1]);
        report(nm, d, 2 * K, t0, t1);
    }

    // ---- compressor pool + RMS norm ------------------------------------------------
    for (int R : {2, 4}) {
        const int HD = 512;
        std::vector<float> hkv((size_t)R * HD), hsc((size_t)R * HD), hw(HD);
        for (auto &v : hkv) v = U(-3, 3);
        for (auto &v : hsc) v = U(-6, 6);
        for (auto &v : hw) v = U(0.2f, 2.0f);
        float *kv = dev_vec(hkv), *sc = dev_vec(hsc), *w = dev_vec(hw);
        float *o0 = sycl::malloc_device<float>(HD, q), *o1 = sycl::malloc_device<float>(HD, q);
        CompressPoolA<ActF32> k0{R, HD};
        CompressPoolP<ActF32> k1{R, HD};
        auto run0 = [&] { return q.parallel_for(sycl::nd_range<1>(1, 1), [=](sycl::nd_item<1> it) { k0(it, kv, sc, w, o0); }); };
        auto run1 = [&] {
            return q.submit([&](sycl::handler &h) {
                sycl::local_accessor<float, 1> lm(HD, h);
                h.parallel_for(sycl::nd_range<1>(32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                    k1(it, kv, sc, w, o1, &lm[0]);
                });
            });
        };
        run0();
        run1();
        q.wait();
        double t0 = gpu_us(run0), t1 = gpu_us(run1);
        char nm[64];
        std::snprintf(nm, sizeof nm, "CompressPool r=%d", R);
        report(nm, ndiff(host(o0, HD), host(o1, HD)), HD, t0, t1);
    }
    std::printf("%s: %d failed check(s)\n", g_fail ? "FAIL" : "PASS", g_fail);
    return g_fail;
}
