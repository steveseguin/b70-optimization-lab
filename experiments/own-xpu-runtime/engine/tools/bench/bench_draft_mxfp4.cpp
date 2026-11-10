// The DSpark draft's routed MXFP4 experts at the six-card shapes (5 block tokens x top 3 = 15 slots; gate + up
// 2 x 384 rows of 5120 columns per expert slice, down 864 rows of 2304 columns, 128 experts): the engine's
// RoutedMXFP4N (raw 17-byte blocks, one sub-group per slot and row) against RoutedMXFP4U (pk41 MXFP4 packed rows,
// slots grouped by expert with ExpertGroupM, ops41sycl::RoutedU). Every output must be BITWISE equal. Cold timing:
// the banks are evicted by READING 128 MiB before every launch. Expert patterns: all 15 slots on different
// experts, a draft-like block (the anchor's 3 experts, the 4 mask rows sharing most of theirs), and all 5 tokens on
// the same 3 experts.
// Run it on a 230 W card (tiles 1, 2, 4, 5: SYCL index 2 = 0000:43), never beside a six-card run.
//
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_draft_mxfp4.cpp -o $S/bench_draft_mxfp4 -lze_loader
//   LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib $S/bench_draft_mxfp4 [CARD]
// Exit status 1 on any mismatch.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/pack_v41.hpp"
#include "stage2/packet3/kernels/sycl_v41_draft.hpp"

static constexpr unsigned NEXP = 128, M = 5, SPT = 3, NSL = M * SPT, REPS = 16;
static constexpr size_t FLUSH_WORDS = (size_t)32 << 20;
static uint32_t *g_flush = nullptr;
static int g_fail = 0;

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
static void flush(sycl::queue &q, uint32_t v) {
    uint32_t *p = g_flush;
    q.parallel_for(sycl::nd_range<1>(FLUSH_WORDS / 64, 256), [=](sycl::nd_item<1> it) {
        const size_t i0 = it.get_global_linear_id() * 64;
        uint32_t s = 0;
        for (unsigned k = 0; k < 64; ++k) s ^= p[i0 + k];
        if (s == v + 0x9e3779b9u) p[0] = s;
    });
}
// as Backend41::launch_rows<SLM>: 16 sub-groups per 512-item work-group, at most max_wg work-groups
template <size_t SLM, typename K, typename... A>
static sycl::event launch_rows(sycl::queue &q, size_t rows, size_t max_wg, K k, A... args) {
    size_t nwg = (rows + 15) / 16;
    if (max_wg && nwg > max_wg) nwg = max_wg;
    return q.submit([&](sycl::handler &hh) {
        if constexpr (SLM > 0) {
            sycl::local_accessor<float, 1> lt(SLM, hh);
            hh.parallel_for(sycl::nd_range<1>(nwg * 512, 512),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, args..., &lt[0]); });
        } else {
            hh.parallel_for(sycl::nd_range<1>(nwg * 512, 512),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, args...); });
        }
    });
}
static sycl::event group(sycl::queue &q, const uint32_t *ids, uint32_t *grp) {
    using G = ops41sycl::ExpertGroupM;
    return q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<float, 1> lt(G::LM, hh);
        const G k{NSL, 6u};
        hh.parallel_for(sycl::nd_range<1>(G::WG, G::WG),
                        [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, ids, grp, &lt[0]); });
    });
}

struct Bank {
    uint8_t *raw = nullptr, *pk = nullptr;
};
static Bank make_bank(sycl::queue &q, unsigned rows, unsigned cols, std::mt19937 &rng) {
    const size_t nx = cols / 32, rb = nx * 17, prb = pk41::packed_row_bytes(iq3::Type::MXFP4, cols);
    const size_t nr = (size_t)NEXP * rows;
    std::vector<uint8_t> raw(nr * rb), pk(nr * prb);
    for (size_t r = 0; r < nr; ++r) {
        uint8_t *s = raw.data() + r * rb;
        for (size_t b = 0; b < nx; ++b) {
            s[b * 17] = uint8_t(118 + rng() % 9); // e8m0 scales 2^-10 .. 2^-2
            for (unsigned j = 0; j < 16; ++j) s[b * 17 + 1 + j] = uint8_t(rng());
        }
        pk41::pack_row(iq3::Type::MXFP4, s, pk.data() + r * prb, cols);
    }
    Bank b;
    b.raw = sycl::malloc_device<uint8_t>(raw.size(), q);
    b.pk = sycl::malloc_device<uint8_t>(pk.size() + 4096, q);
    q.memcpy(b.raw, raw.data(), raw.size());
    q.memcpy(b.pk, pk.data(), pk.size()).wait();
    return b;
}

template <unsigned NB>
static void run(sycl::queue &q, const char *name, unsigned rows, bool pair, bool per_slot, const Bank &w1,
                const Bank &w2, const float *x, size_t xtok, const uint32_t *ids, uint32_t *grp, unsigned ndist) {
    const size_t ny = (size_t)NSL * rows;
    float *ya = sycl::malloc_device<float>(ny, q), *yb = sycl::malloc_device<float>(ny, q);
    float *ya2 = sycl::malloc_device<float>(ny, q), *yb2 = sycl::malloc_device<float>(ny, q);
    const size_t np = (size_t)(pair ? 2 : 1) * NSL * rows;
    ops41draft::RoutedMXFP4N<NB * 8> ko{rows, NSL, SPT, (unsigned)xtok, per_slot}; // (its NB counts blocks of 32)
    ko.nexp = NEXP;
    ko.w2 = pair ? w2.raw : nullptr;
    ko.out2 = pair ? ya2 : nullptr;
    using KU = ops41draft::RoutedMXFP4U<NB, 6>;
    KU ku{rows, per_slot};
    ku.nsl = NSL;
    ku.xtok = (unsigned)xtok;
    ku.nexp = NEXP;
    ku.w2 = pair ? w2.pk : nullptr;
    ku.out2 = pair ? yb2 : nullptr;
    auto old_go = [&] { return launch_rows<0>(q, np, 1024, ko, (const uint8_t *)w1.raw, x, ids, ya); };
    auto new_go = [&] { return launch_rows<KU::TAB>(q, np, 1024, ku, (const uint8_t *)w1.pk, x, (const uint32_t *)grp, yb); };
    for (float *p : {ya, yb, ya2, yb2}) q.memset(p, 0xff, ny * 4);
    q.wait();
    group(q, ids, grp);
    old_go();
    new_go();
    q.wait();
    std::vector<float> a(ny), b(ny), a2(ny), b2(ny);
    q.memcpy(a.data(), ya, ny * 4);
    q.memcpy(b.data(), yb, ny * 4);
    q.memcpy(a2.data(), ya2, ny * 4);
    q.memcpy(b2.data(), yb2, ny * 4).wait();
    size_t bad = 0, nan = 0;
    for (size_t i = 0; i < ny; ++i) {
        bad += std::memcmp(&a[i], &b[i], 4) != 0;
        if (pair) bad += std::memcmp(&a2[i], &b2[i], 4) != 0;
        nan += a[i] != a[i];
    }
    std::printf("%s, %u different experts: %s %zu of %zu outputs differ (%zu not finite)\n", name, ndist,
                bad ? "FAIL" : "PASS", bad, (pair ? 2 : 1) * ny, nan);
    g_fail += bad != 0 || nan != 0;
    auto cold = [&](auto f) {
        for (int i = 0; i < 20; ++i) f();
        q.wait();
        double s = 0;
        for (unsigned i = 0; i < REPS; ++i) {
            flush(q, i);
            auto e = f();
            e.wait();
            s += ev_us(e);
        }
        return s / REPS;
    };
    const double to = cold(old_go), tn = cold(new_go);
    double tg = 0;
    for (unsigned i = 0; i < REPS; ++i) {
        auto e = group(q, ids, grp);
        e.wait();
        tg += ev_us(e) / REPS;
    }
    std::printf("  RoutedMXFP4N %8.2f us | RoutedMXFP4U %8.2f us (+ ExpertGroupM %.2f us, once per stage)\n", to, tn, tg);
    std::fflush(stdout);
    for (float *p : {ya, yb, ya2, yb2}) sycl::free(p, q);
}

int main(int argc, char **argv) {
    const int card = argc > 1 ? std::atoi(argv[1]) : 2;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const sycl::device dev = l0.at(card);
    const sycl::context ctx(dev);
    sycl::queue q(ctx, dev, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    std::printf("card %d %s (pci %s)\n", card, dev.get_info<sycl::info::device::name>().c_str(),
                dev.get_info<sycl::ext::intel::info::device::pci_address>().c_str());
    g_flush = sycl::malloc_device<uint32_t>(FLUSH_WORDS, q);
    q.memset(g_flush, 0, FLUSH_WORDS * 4).wait();
    std::mt19937 rng(7);
    const unsigned H = 5120, MID = 2304, RG = 384, RD = 864;
    const Bank gate = make_bank(q, RG, H, rng), up = make_bank(q, RG, H, rng), down = make_bank(q, RD, MID, rng);
    const size_t A7 = (size_t)7 * MID;
    std::uniform_real_distribution<float> u(-2.f, 2.f);
    std::vector<float> hx((size_t)M * A7 + 64);
    for (auto &v : hx) v = u(rng);
    float *x = sycl::malloc_device<float>(hx.size(), q);
    q.memcpy(x, hx.data(), hx.size() * 4).wait();
    uint32_t *ids = sycl::malloc_device<uint32_t>(64, q), *grp = sycl::malloc_device<uint32_t>(ops41sycl::RUGrp::WORDS, q);
    struct Pat { const char *name; uint32_t e[NSL]; };
    const Pat pats[] = {
        {"all different", {3, 17, 40, 5, 66, 91, 12, 101, 77, 23, 54, 120, 8, 99, 31}},
        {"draft-like", {3, 17, 40, 5, 66, 91, 5, 66, 12, 5, 91, 66, 5, 66, 91}},
        {"all on 3 experts", {3, 17, 40, 17, 40, 3, 40, 3, 17, 3, 17, 40, 17, 3, 40}},
    };
    for (const auto &p : pats) {
        q.memcpy(ids, p.e, sizeof p.e).wait();
        std::vector<uint32_t> s(p.e, p.e + NSL);
        std::sort(s.begin(), s.end());
        const unsigned nd = (unsigned)(std::unique(s.begin(), s.end()) - s.begin());
        std::printf("-- %s\n", p.name);
        run<20>(q, "gate + up (5120 columns, 2 x 384 rows)", RG, true, false, gate, up, x, H, ids, grp, nd);
        run<9>(q, "down (2304 columns, 864 rows, per-slot input)", RD, false, true, down, down, x, A7, ids, grp, nd);
    }
    std::printf("%s\n", g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
