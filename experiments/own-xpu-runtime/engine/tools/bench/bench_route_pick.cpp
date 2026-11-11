// Where does the router's two-stage pick spend its ~9 us (RouteP::run_two, OWN_ROUTE_Q; the scores alone take
// ~0.9 us)? Variants of the pick, one work-group of 512 items, timed back to back (interleaved). Outputs of the
// full variants compared BITWISE with the engine's RouteP (two = false and true); the cut variants are timing only.
//   V0 the engine's RouteP, two = true          V1 this file's copy (same code)
//   V2 stage 1 + barrier only (timing)          V3 without the NaN flags (timing; the same values without NaN)
//   V4 stage 2 reads candidates from local memory uniformly instead of broadcasts
//   V5 scores only, no barrier                  V6 V1 without the leading prob read (timing)
//   V7 empty kernel (launch floor)
//   V8 stage 2 with the candidate count a constant (72, unrolled)   V9 stage 2 skipped (timing)
//   V10 the picks stored after the last barrier (no global store before it)
//   V11 stage 2's test without short-circuit branches ((w > v) | ((w == v) & (wi < i)))
//   V12 stage 2 on the candidates' lanes only: sub-groups 0-2 hold the 72 candidates, one per lane
//   V13 V8 + V11 + stage 1 branch-free   V14 V11 + stage 1 branch-free   V15 V13 with four rank counters
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_route_pick.cpp -o $S/bench_route_pick
//   ONEAPI_DEVICE_SELECTOR=level_zero:1 $S/bench_route_pick
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

static constexpr unsigned E = 384;
static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}

template <int V> struct PickV {
    int experts, topk;
    void operator()(sycl::nd_item<1> it, const float *logits, const float *bias, uint32_t *ids, float *prob, float *lm) const {
        float *lsb = lm + experts, *lp = lm + 2 * experts;
        float *cv = lm + 1040;
        int *ci = reinterpret_cast<int *>(lm + 1136);
        int *nanf = reinterpret_cast<int *>(lm + 1232);
        const int i = (int)it.get_local_linear_id();
        sycl::sub_group sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
        const bool live = sgi * 32 < experts;
        if (V != 6 && i < topk) lp[i] = prob[i];
        float v = 0, s0 = 0;
        if (live) {
            s0 = sycl::sqrt(sycl::log1p(sycl::exp(logits[i])));
            v = s0 + bias[i];
            lsb[i] = v;
        }
        if constexpr (V == 5) {
            if (i < topk) { ids[i] = (uint32_t)i; prob[i] = v; }
            return;
        }
        int r1 = 0;
        if (live) {
#pragma unroll
            for (int k = 0; k < 32; ++k) {
                const float w = sycl::select_from_group(sg, v, k);
                if constexpr (V >= 13) r1 += (int)(w > v) | ((int)(w == v) & (int)(k < lane));
                else r1 += (w > v || (w == v && k < lane)) ? 1 : 0;
            }
        }
        if constexpr (V != 3) {
            const bool anynan = live && sycl::any_of_group(sg, sycl::isnan(v));
            if (lane == 0) nanf[sgi] = anynan ? 1 : 0;
        }
        const bool cand = live && r1 < topk;
        if (cand) {
            cv[sgi * topk + r1] = v;
            ci[sgi * topk + r1] = i;
        }
        sycl::group_barrier(it.get_group());
        if constexpr (V == 2) {
            if (i < topk) { ids[i] = (uint32_t)ci[i]; prob[i] = cv[i]; }
            return;
        }
        int nan_any = 0;
        if constexpr (V != 3)
            for (int k = 0; k < (int)(it.get_local_range(0) / 32); ++k) nan_any |= nanf[k];
        if (live) {
            int rank = 0;
            if (nan_any) {
                for (int jb = 0; jb < experts; jb += 32) {
                    const float u = lsb[jb + lane];
#pragma unroll
                    for (int k = 0; k < 32; ++k) {
                        const float w = sycl::select_from_group(sg, u, k);
                        rank += (w > v || (w == v && jb + k < i)) ? 1 : 0;
                    }
                }
            } else if constexpr (V == 9) {
                rank = sgi == 0 ? r1 : 99;
            } else if constexpr (V == 8) {
                constexpr int NC = 72;
#pragma unroll
                for (int jb = 0; jb < NC; jb += 32) {
                    const bool in = jb + lane < NC;
                    const float u = in ? cv[jb + lane] : 0.0f;
                    const int ui = in ? ci[jb + lane] : 0;
#pragma unroll
                    for (int k = 0; k < 32; ++k) {
                        if (jb + k >= NC) break;
                        const float w = sycl::select_from_group(sg, u, k);
                        const int wi = sycl::select_from_group(sg, ui, k);
                        rank += (w > v || (w == v && wi < i)) ? 1 : 0;
                    }
                }
            } else if constexpr (V == 13 || V == 15) {
                constexpr int NC = 72;
                int rk[4] = {0, 0, 0, 0};
#pragma unroll
                for (int jb = 0; jb < NC; jb += 32) {
                    const bool in = jb + lane < NC;
                    const float u = in ? cv[jb + lane] : 0.0f;
                    const int ui = in ? ci[jb + lane] : 0;
#pragma unroll
                    for (int k = 0; k < 32; ++k) {
                        if (jb + k >= NC) break;
                        const float w = sycl::select_from_group(sg, u, k);
                        const int wi = sycl::select_from_group(sg, ui, k);
                        rk[V == 15 ? (k & 3) : 0] += (int)(w > v) | ((int)(w == v) & (int)(wi < i));
                    }
                }
                rank = (rk[0] + rk[1]) + (rk[2] + rk[3]);
            } else if constexpr (V == 11 || V == 14) {
                const int nc = experts / 32 * topk;
                for (int jb = 0; jb < nc; jb += 32) {
                    const bool in = jb + lane < nc;
                    const float u = in ? cv[jb + lane] : 0.0f;
                    const int ui = in ? ci[jb + lane] : 0;
#pragma unroll
                    for (int k = 0; k < 32; ++k) {
                        const float w = sycl::select_from_group(sg, u, k);
                        const int wi = sycl::select_from_group(sg, ui, k);
                        rank += (int)(jb + k < nc) & ((int)(w > v) | ((int)(w == v) & (int)(wi < i)));
                    }
                }
            } else if constexpr (V == 4) {
                const int nc = experts / 32 * topk;
                for (int c = 0; c < nc; ++c) {
                    const float w = cv[c];
                    const int wi = ci[c];
                    rank += (w > v || (w == v && wi < i)) ? 1 : 0;
                }
            } else {
                const int nc = experts / 32 * topk;
                for (int jb = 0; jb < nc; jb += 32) {
                    const bool in = jb + lane < nc;
                    const float u = in ? cv[jb + lane] : 0.0f;
                    const int ui = in ? ci[jb + lane] : 0;
#pragma unroll
                    for (int k = 0; k < 32; ++k) {
                        const float w = sycl::select_from_group(sg, u, k);
                        const int wi = sycl::select_from_group(sg, ui, k);
                        rank += (jb + k < nc && (w > v || (w == v && wi < i))) ? 1 : 0;
                    }
                }
            }
            if ((nan_any || cand) && rank < topk) {
                if constexpr (V == 10) reinterpret_cast<int *>(lm + 1248)[rank] = i;
                else ids[rank] = (uint32_t)i;
                lp[rank] = s0;
            }
        }
        sycl::group_barrier(it.get_group());
        if constexpr (V == 10)
            if (i < topk) ids[i] = (uint32_t)reinterpret_cast<int *>(lm + 1248)[i];
        if (i < topk) {
            float sum = 0;
            for (int t = 0; t < topk; ++t) sum += lp[t];
            prob[i] = lp[i] / (sum + 1e-20f) * 1.5f;
        }
    }
};
// V12: after stage 1, sub-groups 0-2 take candidate c = 32 * sgi + lane (c < 72) and rank it among the 72
template <int NC> struct PickC {
    int experts, topk;
    void operator()(sycl::nd_item<1> it, const float *logits, const float *bias, uint32_t *ids, float *prob, float *lm) const {
        float *lp = lm + 2 * experts;
        float *cv = lm + 1040;
        int *ci = reinterpret_cast<int *>(lm + 1136);
        int *nanf = reinterpret_cast<int *>(lm + 1232);
        float *cs = lm + 1260; // candidates' s0
        const int i = (int)it.get_local_linear_id();
        sycl::sub_group sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
        const bool live = sgi * 32 < experts;
        if (i < topk) lp[i] = prob[i];
        float v = 0, s0 = 0;
        if (live) {
            s0 = sycl::sqrt(sycl::log1p(sycl::exp(logits[i])));
            v = s0 + bias[i];
        }
        int r1 = 0;
        if (live) {
#pragma unroll
            for (int k = 0; k < 32; ++k) {
                const float w = sycl::select_from_group(sg, v, k);
                r1 += (w > v || (w == v && k < lane)) ? 1 : 0;
            }
        }
        const bool anynan = live && sycl::any_of_group(sg, sycl::isnan(v));
        if (lane == 0) nanf[sgi] = anynan ? 1 : 0;
        if (live && r1 < topk) {
            cv[sgi * topk + r1] = v;
            ci[sgi * topk + r1] = i;
            cs[sgi * topk + r1] = s0;
        }
        sycl::group_barrier(it.get_group());
        if (sgi < (NC + 31) / 32) {
            const int c = sgi * 32 + lane;
            const bool in = c < NC;
            const float cvv = in ? cv[c] : 0.0f;
            const int cii = in ? ci[c] : 0;
            int rank = 0;
#pragma unroll
            for (int jb = 0; jb < NC; jb += 32) {
                const bool in2 = jb + lane < NC;
                const float u = in2 ? cv[jb + lane] : 0.0f;
                const int ui = in2 ? ci[jb + lane] : 0;
#pragma unroll
                for (int k = 0; k < 32; ++k) {
                    if (jb + k >= NC) break;
                    const float w = sycl::select_from_group(sg, u, k);
                    const int wi = sycl::select_from_group(sg, ui, k);
                    rank += (w > cvv || (w == cvv && wi < cii)) ? 1 : 0;
                }
            }
            if (in && rank < topk) {
                ids[rank] = (uint32_t)cii;
                lp[rank] = cs[c];
            }
        }
        sycl::group_barrier(it.get_group());
        if (i < topk) {
            float sum = 0;
            for (int t = 0; t < topk; ++t) sum += lp[t];
            prob[i] = lp[i] / (sum + 1e-20f) * 1.5f;
        }
    }
};
struct Empty {
    int experts, topk;
    void operator()(sycl::nd_item<1> it, const float *, const float *, uint32_t *ids, float *, float *) const {
        if (it.get_local_linear_id() == 0) ids[7] = 0;
    }
};
template <typename RK> struct Sets {
    RK rk;
    void operator()(sycl::nd_item<1> it, const float *logits, const float *bias, uint32_t *ids, float *prob, float *lm) const {
        const size_t g = it.get_group_linear_id();
        rk(it, logits + g * rk.experts, bias + g * rk.experts, ids + g * 8, prob + g * 8, lm);
    }
};

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    std::mt19937 rng(5);
    std::normal_distribution<float> nd(0.f, 1.f);
    constexpr unsigned NS = 2048;
    std::vector<float> hl((size_t)NS * E), hb((size_t)NS * E);
    for (auto &v : hl) v = nd(rng) * 2.0f;
    for (auto &v : hb) v = nd(rng) * 0.1f;
    float *logits = sycl::malloc_device<float>(hl.size(), q), *bias = sycl::malloc_device<float>(hb.size(), q);
    q.memcpy(logits, hl.data(), hl.size() * 4);
    q.memcpy(bias, hb.data(), hb.size() * 4).wait();
    constexpr int NF = 16;
    const char *names[NF] = {"V0 engine RouteP two = true", "V1 copy of run_two", "V2 stage 1 + barrier only",
                             "V3 without NaN flags", "V4 stage 2 uniform local reads", "V5 scores only, no barrier",
                             "V6 V1 without the prob read", "V7 empty kernel", "V8 stage 2 constant count",
                             "V9 stage 2 skipped", "V10 picks stored after the barrier", "V11 branch-free test",
                             "V12 candidates' lanes only (no NaN path)", "V13 const + branch-free both stages",
                             "V14 branch-free both stages", "V15 V13 with four counters"};
    std::vector<uint32_t *> ids(NF);
    std::vector<float *> prob(NF);
    for (int v = 0; v < NF; ++v) {
        ids[v] = sycl::malloc_device<uint32_t>((size_t)NS * 8, q);
        prob[v] = sycl::malloc_device<float>((size_t)NS * 8, q);
        q.fill(prob[v], 0.0f, (size_t)NS * 8);
    }
    q.wait();
    auto launch = [&](auto k, int v, size_t ng) {
        uint32_t *ii = ids[v];
        float *pp = prob[v];
        return q.submit([&](sycl::handler &hh) {
            sycl::local_accessor<float, 1> lt(2 * 1024 + 6, hh);
            hh.parallel_for(sycl::nd_range<1>(ng * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k(it, logits, bias, ii, pp, &lt[0]);
            });
        });
    };
    auto run = [&](int v, size_t ng) -> sycl::event {
        switch (v) {
        case 0: return launch(Sets<RouteP>{RouteP{(int)E, 6, true}}, v, ng);
        case 1: return launch(Sets<PickV<1>>{PickV<1>{(int)E, 6}}, v, ng);
        case 2: return launch(Sets<PickV<2>>{PickV<2>{(int)E, 6}}, v, ng);
        case 3: return launch(Sets<PickV<3>>{PickV<3>{(int)E, 6}}, v, ng);
        case 4: return launch(Sets<PickV<4>>{PickV<4>{(int)E, 6}}, v, ng);
        case 5: return launch(Sets<PickV<5>>{PickV<5>{(int)E, 6}}, v, ng);
        case 6: return launch(Sets<PickV<6>>{PickV<6>{(int)E, 6}}, v, ng);
        case 7: return launch(Sets<Empty>{Empty{(int)E, 6}}, v, ng);
        case 8: return launch(Sets<PickV<8>>{PickV<8>{(int)E, 6}}, v, ng);
        case 9: return launch(Sets<PickV<9>>{PickV<9>{(int)E, 6}}, v, ng);
        case 10: return launch(Sets<PickV<10>>{PickV<10>{(int)E, 6}}, v, ng);
        case 11: return launch(Sets<PickV<11>>{PickV<11>{(int)E, 6}}, v, ng);
        case 12: return launch(Sets<PickC<72>>{PickC<72>{(int)E, 6}}, v, ng);
        case 13: return launch(Sets<PickV<13>>{PickV<13>{(int)E, 6}}, v, ng);
        case 14: return launch(Sets<PickV<14>>{PickV<14>{(int)E, 6}}, v, ng);
        default: return launch(Sets<PickV<15>>{PickV<15>{(int)E, 6}}, v, ng);
        }
    };
    // correctness on NS sets: V0, V1, V3, V4 against RouteP two = false
    uint32_t *ir = sycl::malloc_device<uint32_t>((size_t)NS * 8, q);
    float *pr = sycl::malloc_device<float>((size_t)NS * 8, q);
    q.fill(pr, 0.0f, (size_t)NS * 8).wait();
    q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<float, 1> lt(2 * 1024 + 6, hh);
        Sets<RouteP> k{RouteP{(int)E, 6, false}};
        hh.parallel_for(sycl::nd_range<1>((size_t)NS * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            k(it, logits, bias, ir, pr, &lt[0]);
        });
    }).wait();
    long bad = 0;
    std::vector<uint32_t> a0((size_t)NS * 8), a1((size_t)NS * 8);
    std::vector<float> b0((size_t)NS * 8), b1((size_t)NS * 8);
    q.memcpy(a0.data(), ir, NS * 32);
    q.memcpy(b0.data(), pr, NS * 32).wait();
    for (int v : {0, 1, 3, 4, 8, 10, 11, 12, 13, 14, 15}) {
        run(v, NS).wait();
        q.memcpy(a1.data(), ids[v], NS * 32);
        q.memcpy(b1.data(), prob[v], NS * 32).wait();
        long d = 0;
        for (unsigned g = 0; g < NS; ++g)
            if (std::memcmp(&a0[g * 8], &a1[g * 8], 24) || std::memcmp(&b0[g * 8], &b1[g * 8], 24)) ++d;
        std::printf("%-34s %u sets: %ld differ\n", names[v], NS, d);
        bad += d;
    }
    // timing: one work-group (set 0), back to back, interleaved
    std::vector<double> tm[NF];
    for (int set = 0; set < 8; ++set) {
        for (int v = 0; v < NF; ++v) q.fill(prob[v], 0.0f, 8);
        q.wait();
        std::vector<std::pair<int, sycl::event>> evs;
        for (int r = 0; r < 26; ++r)
            for (int v = 0; v < NF; ++v) {
                auto e = run(v, 1);
                if (r) evs.push_back({v, e});
            }
        q.wait();
        for (auto &[v, e] : evs) tm[v].push_back(ev_us(e));
    }
    std::printf("%-42s %10s %10s %10s %10s\n", "form", "median us", "min us", "p10 us", "p90 us");
    for (int v = 0; v < NF; ++v) {
        auto t = tm[v];
        std::sort(t.begin(), t.end());
        std::printf("%-42s %10.2f %10.2f %10.2f %10.2f\n", names[v], t[t.size() / 2], t[0], t[t.size() / 10], t[t.size() * 9 / 10]);
    }
    std::printf(bad ? "FAIL (%ld)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
