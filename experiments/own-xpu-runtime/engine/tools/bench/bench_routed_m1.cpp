// The one-token routed expert kernels (slot-major RoutedIQ2XXSP ... RoutedIQ1SP, the plain decode step's
// expert gate + up and down launches at the six-card shapes) timed against their work-group count, and a
// candidate form that computes R rows per sub-group so each activation value is read once for R rows
// (RoutedIQ2XXSR), BITWISE against the production kernel. One card.
//   pair: gate + up in one launch (w2 / out2), 384 rows per expert (2304 / 6), 20 blocks (5120 columns)
//   down: per-slot x, 864 rows per expert (card 2's slice of 5120), 9 blocks (2304 columns)
// Experts in the bank: 384 (the model's count); each timed launch uses 6 distinct random experts, 16 id sets
// interleaved, mean over 5 passes of the 16 (the weights come from card memory, not the cache).
//
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_routed_m1.cpp -o $S/bench_routed_m1 -lze_loader
//   LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib $S/bench_routed_m1 [CARD]
//   ONLY=xxs,iq2s,iq3,iq2xs,iq1 selects formats for the sweep. Exit status 1 on any mismatch.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <numeric>
#include <random>
#include <string>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
using namespace ops41sycl;
using Ty = iq3::Type;

static constexpr unsigned NEXP = 384, NSET = 16, PASSES = 5, PAIR_ROWS = 384, DOWN_ROWS = 864;
static int g_fail = 0;

// ---- candidate: R rows of one (matrix, slot) per sub-group, x read once per block for all R ---------------
// Row j's sum is the production kernel's: the same element expressions ((db * mag) ^ sign) * x added in
// the same order (blocks, then groups g), then the same xor butterfly. Units u = (matrix, slot, row group);
// rows past `rows` in the last group are computed on row r0 and not stored.
template <unsigned NB, unsigned R> struct RoutedIQ2XXSR {
    static constexpr unsigned TAB = 2048;
    unsigned rows;
    bool per_slot_x;
    const uint8_t *w2 = nullptr;
    float *out2 = nullptr;
    unsigned nsl = 6, xtok = 0;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint8_t *w, const float *x, const uint32_t *ids,
                                     float *out, float *tab) const {
        for (unsigned k = it.get_local_linear_id(); k < TAB; k += (unsigned)it.get_local_range(0))
            tab[k] = float(grid64_byte(iq3::iq2_xxs_grid, k >> 3, k & 7));
        sycl::group_barrier(it.get_group());
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), l8 = lane >> 3, j = lane & 7u;
        const unsigned ssh = 31u - 8u * l8 - j;
        const unsigned rot = (37u - 8u * l8) & 31u, j4 = j << 2;
        const char *tb = reinterpret_cast<const char *>(tab);
        constexpr size_t RB = ((size_t)NB * 70 + 15) & ~(size_t)15;
        constexpr unsigned NW = NB * 16, NR = (NW + 31) / 32, NC = NB * 8, NCR = (NC + 31) / 32;
        const unsigned stride = (unsigned)(it.get_global_range(0) / 32);
        const unsigned ngr = (rows + R - 1) / R, nu = (w2 ? 2 : 1) * nsl * ngr;
        for (unsigned u = packed_row_id(it); u < nu; u += stride) {
            unsigned slot = u / ngr;
            const unsigned r0 = (u % ngr) * R;
            const uint8_t *wm = w;
            float *om = out;
            if (slot >= nsl) {
                slot -= nsl;
                wm = w2;
                om = out2;
            }
            const float *xs = x + (size_t)(slot / 6) * xtok + (per_slot_x ? (size_t)(slot % 6) * NB * 256 : 0);
            uint32_t wd[R][NR];
            float dbc[R][NCR];
            float sum[R];
#pragma unroll
            for (unsigned q = 0; q < R; ++q) {
                const unsigned r = r0 + q < rows ? r0 + q : r0;
                const uint8_t *row = wm + ((size_t)ids[slot] * rows + r) * RB;
                const uint32_t *rw = reinterpret_cast<const uint32_t *>(row);
#pragma unroll
                for (unsigned k = 0; k < NR; ++k) wd[q][k] = row_words<NW>(sg, rw, k, lane);
                chunk_scales<NB>(sg, lane, reinterpret_cast<const uint16_t *>(row + (size_t)NB * 68),
                                 reinterpret_cast<const uint32_t *>(row + (size_t)NB * 64), 0.25f, dbc[q]);
                sum[q] = 0;
            }
#pragma unroll
            for (unsigned blk = 0; blk < NB; ++blk) {
                const auto xv = sg_bloadN<8>(sg, xs + (size_t)blk * 256);
#pragma unroll
                for (unsigned g = 0; g < 8; ++g) {
                    const unsigned wl = blk * 16 + 2 * g, wh = wl + 1, c = blk * 8 + g;
#pragma unroll
                    for (unsigned q = 0; q < R; ++q) {
                        const uint32_t lo = sycl::select_from_group(sg, wd[q][wl / 32], wl % 32);
                        const uint32_t es = sycl::select_from_group(sg, wd[q][wh / 32], wh % 32);
                        const float db = sycl::select_from_group(sg, dbc[q][c / 32], c % 32);
                        const float mag = *reinterpret_cast<const float *>(tb + ((sycl::rotate(lo, rot) & 0x1FE0u) | j4));
                        const uint32_t sb = (es << ssh) & 0x80000000u;
                        const float v = sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(db * mag) ^ sb);
                        sum[q] = sum[q] + v * xv[g];
                    }
                }
            }
#pragma unroll
            for (unsigned q = 0; q < R; ++q) {
                float s = sum[q];
                for (int w_ = 16; w_; w_ >>= 1) s += sycl::select_from_group(sg, s, (int)lane ^ w_);
                if (lane == 0 && r0 + q < rows) om[slot * rows + r0 + q] = s;
            }
        }
    }
};

// ---- harness ----------------------------------------------------------------------------------------------
static uint64_t sm64(uint64_t &s) {
    uint64_t z = (s += 0x9E3779B97F4A7C15ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}
template <Ty TY> uint8_t *packed_bank(sycl::queue &q, unsigned cols, size_t nrow, uint64_t seed) {
    constexpr auto L = iq3::layout(TY);
    const size_t nb = cols / L.elements, rb = nb * L.bytes, prb = pk41::packed_row_bytes(TY, cols);
    uint8_t *d = sycl::malloc_device<uint8_t>(nrow * prb, q);
    if (!d) {
        std::printf("FAIL cannot allocate %.0f MB of card memory\n", nrow * prb / 1e6);
        std::exit(1);
    }
    constexpr size_t CH = 4096;
    std::vector<uint8_t> src(rb), dst(CH * prb);
    for (size_t r0 = 0; r0 < nrow; r0 += CH) {
        const size_t n = std::min(CH, nrow - r0);
        for (size_t r = 0; r < n; ++r) {
            for (size_t i = 0; i < rb; i += 8) {
                const uint64_t v = sm64(seed);
                std::memcpy(&src[i], &v, std::min<size_t>(8, rb - i));
            }
            for (size_t b = 0; b < nb; ++b) {
                const uint16_t h = 0x1400 + (sm64(seed) & 0x3ff);
                src[b * L.bytes] = h & 255;
                src[b * L.bytes + 1] = h >> 8;
            }
            pk41::pack_row(TY, src.data(), dst.data() + r * prb, cols);
        }
        q.memcpy(d + r0 * prb, dst.data(), n * prb).wait();
    }
    return d;
}
static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
// as Backend41::launch_rows: 512 items (16 sub-groups) per work-group, positions / 16 work-groups capped at maxwg
template <typename K>
static sycl::event launch(sycl::queue &q, size_t npos, size_t maxwg, const K &k, const uint8_t *w, const float *x,
                          const uint32_t *ids, float *y) {
    size_t nwg = (npos + 15) / 16;
    if (maxwg && nwg > maxwg) nwg = maxwg;
    const K kk = k;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> lt(K::TAB, h);
        h.parallel_for(sycl::nd_range<1>(nwg * 512, 512),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kk(it, w, x, ids, y, &lt[0]); });
    });
}
struct Bank {
    const uint8_t *w1, *w2;
    const float *x;
    const uint32_t *ids; // NSET x 6
    float *o1, *o2;
    unsigned rows;
    bool down;
};
template <typename K> static K make(const Bank &b) {
    K k{b.rows, b.down};
    if (!b.down) {
        k.w2 = b.w2;
        k.out2 = b.o2;
    }
    return k;
}
// mean us per launch over PASSES x NSET launches (sets interleaved)
template <typename K> static double time_k(sycl::queue &q, const Bank &b, size_t npos, size_t maxwg) {
    const K k = make<K>(b);
    for (unsigned s = 0; s < NSET; ++s) launch(q, npos, maxwg, k, b.w1, b.x, b.ids + 6 * s, b.o1);
    q.wait();
    double sum = 0;
    for (unsigned p = 0; p < PASSES; ++p)
        for (unsigned s = 0; s < NSET; ++s) {
            auto e = launch(q, npos, maxwg, k, b.w1, b.x, b.ids + 6 * s, b.o1);
            e.wait();
            sum += ev_us(e);
        }
    return sum / (PASSES * NSET);
}
template <typename K> static std::vector<float> run_out(sycl::queue &q, const Bank &b, size_t npos, size_t maxwg, unsigned set) {
    const size_t n = (size_t)6 * b.rows;
    q.memset(b.o1, 0xff, n * 4);
    q.memset(b.o2, 0xff, n * 4).wait();
    launch(q, npos, maxwg, make<K>(b), b.w1, b.x, b.ids + 6 * set, b.o1).wait();
    std::vector<float> h(2 * n);
    q.memcpy(h.data(), b.o1, n * 4);
    q.memcpy(h.data() + n, b.o2, n * 4).wait();
    return h;
}

static const size_t WGS[] = {64, 72, 96, 112, 128, 144, 160, 192, 256, 0};

template <Ty TY, typename KP, typename KD> static void sweep(sycl::queue &q, const char *name, const float *x,
                                                             const uint32_t *ids, float *o1, float *o2) {
    uint8_t *g = packed_bank<TY>(q, 5120, (size_t)NEXP * PAIR_ROWS, 11);
    uint8_t *u = packed_bank<TY>(q, 5120, (size_t)NEXP * PAIR_ROWS, 12);
    Bank bp{g, u, x, ids, o1, o2, PAIR_ROWS, false};
    std::printf("%-7s pair (12 x %u rows, 20 blocks):", name, PAIR_ROWS);
    for (size_t wg : WGS) std::printf(" wg%zu %.1f", wg, time_k<KP>(q, bp, (size_t)12 * PAIR_ROWS, wg));
    std::printf(" us\n");
    sycl::free(g, q);
    sycl::free(u, q);
    uint8_t *d = packed_bank<TY>(q, 2304, (size_t)NEXP * DOWN_ROWS, 13);
    Bank bd{d, nullptr, x, ids, o1, o2, DOWN_ROWS, true};
    std::printf("%-7s down (6 x %u rows, 9 blocks): ", name, DOWN_ROWS);
    for (size_t wg : WGS) std::printf(" wg%zu %.1f", wg, time_k<KD>(q, bd, (size_t)6 * DOWN_ROWS, wg));
    std::printf(" us\n");
    std::fflush(stdout);
    sycl::free(d, q);
}

template <unsigned NB, unsigned R> static void cand(sycl::queue &q, const Bank &b, size_t base_wg) {
    using KP = RoutedIQ2XXSP<NB, ActF32>;
    using KR = RoutedIQ2XXSR<NB, R>;
    const size_t mats = b.down ? 1 : 2, npos = mats * 6 * b.rows, nunit = mats * 6 * ((b.rows + R - 1) / R);
    size_t bad = 0, tot = 0;
    for (unsigned s = 0; s < 4; ++s) {
        const auto a = run_out<KP>(q, b, npos, base_wg, s), c = run_out<KR>(q, b, nunit, 0, s);
        const size_t n = (size_t)6 * b.rows * mats;
        for (size_t i = 0; i < n; ++i) bad += std::memcmp(&a[i], &c[i], 4) != 0;
        tot += n;
    }
    std::printf("  R %u %s: %s %zu of %zu differ |", R, b.down ? "down" : "pair", bad ? "FAIL" : "PASS", bad, tot);
    g_fail += bad != 0;
    std::printf(" prod wg%zu %.1f |", base_wg, time_k<KP>(q, b, npos, base_wg));
    for (size_t wg : WGS) std::printf(" wg%zu %.1f", wg, time_k<KR>(q, b, nunit, wg));
    std::printf(" us\n");
    std::fflush(stdout);
}

int main(int argc, char **argv) {
    const int card = argc > 1 ? std::atoi(argv[1]) : 0;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const sycl::device dev = l0.at(card);
    const sycl::context ctx(dev);
    sycl::queue q(ctx, dev, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    std::printf("card %d %s\n", card, dev.get_info<sycl::info::device::name>().c_str());
    const std::string only = getenv("ONLY") ? getenv("ONLY") : "xxs,iq2s,iq3,iq2xs,iq1";
    auto want = [&](const char *f) { return ("," + only + ",").find(std::string(",") + f + ",") != std::string::npos; };

    std::mt19937 rng(5);
    std::uniform_real_distribution<float> ux(-1.f, 1.f);
    std::vector<float> hx(6 * 5120 + 64);
    for (auto &v : hx) v = ux(rng);
    std::vector<uint32_t> hid(NSET * 6);
    for (unsigned s = 0; s < NSET; ++s) {
        std::vector<uint32_t> all(NEXP);
        std::iota(all.begin(), all.end(), 0u);
        std::shuffle(all.begin(), all.end(), rng);
        std::copy(all.begin(), all.begin() + 6, hid.begin() + 6 * s);
    }
    float *x = sycl::malloc_device<float>(hx.size(), q);
    uint32_t *ids = sycl::malloc_device<uint32_t>(hid.size(), q);
    const size_t on = (size_t)6 * DOWN_ROWS + 256;
    float *o1 = sycl::malloc_device<float>(on, q), *o2 = sycl::malloc_device<float>(on, q);
    q.memcpy(x, hx.data(), hx.size() * 4);
    q.memcpy(ids, hid.data(), hid.size() * 4).wait();

    // candidate first (IQ2_XXS), then the production sweep
    if (want("xxs")) {
        uint8_t *g = packed_bank<Ty::IQ2_XXS>(q, 5120, (size_t)NEXP * PAIR_ROWS, 11);
        uint8_t *u = packed_bank<Ty::IQ2_XXS>(q, 5120, (size_t)NEXP * PAIR_ROWS, 12);
        Bank bp{g, u, x, ids, o1, o2, PAIR_ROWS, false};
        std::printf("IQ2_XXS candidate, rows per sub-group:\n");
        cand<20, 2>(q, bp, 128);
        cand<20, 3>(q, bp, 128);
        cand<20, 4>(q, bp, 128);
        sycl::free(g, q);
        sycl::free(u, q);
        uint8_t *d = packed_bank<Ty::IQ2_XXS>(q, 2304, (size_t)NEXP * DOWN_ROWS, 13);
        Bank bd{d, nullptr, x, ids, o1, o2, DOWN_ROWS, true};
        cand<9, 2>(q, bd, 128);
        cand<9, 4>(q, bd, 128);
        sycl::free(d, q);
    }
    std::printf("production kernels, work-groups (wg0 = one sub-group per row, no cap):\n");
    if (want("xxs")) sweep<Ty::IQ2_XXS, RoutedIQ2XXSP<20, ActF32>, RoutedIQ2XXSP<9, ActF32>>(q, "IQ2_XXS", x, ids, o1, o2);
    if (want("iq2s")) sweep<Ty::IQ2_S, RoutedIQ2SP<20, ActF32>, RoutedIQ2SP<9, ActF32>>(q, "IQ2_S", x, ids, o1, o2);
    if (want("iq3")) sweep<Ty::IQ3_XXS, RoutedIQ3XXSP<20, ActF32>, RoutedIQ3XXSP<9, ActF32>>(q, "IQ3_XXS", x, ids, o1, o2);
    if (want("iq2xs")) sweep<Ty::IQ2_XS, RoutedIQ2XSP<20, ActF32>, RoutedIQ2XSP<9, ActF32>>(q, "IQ2_XS", x, ids, o1, o2);
    if (want("iq1")) sweep<Ty::IQ1_S, RoutedIQ1SP<20, ActF32, true>, RoutedIQ1SP<9, ActF32, true>>(q, "IQ1_S", x, ids, o1, o2);
    sycl::free(x, q);
    sycl::free(ids, q);
    sycl::free(o1, q);
    sycl::free(o2, q);
    std::printf("%s\n", g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
