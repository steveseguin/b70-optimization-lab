// bench_route_fused: one token, layer 0's real F32 router and routing bias. Compare the engine's
// gemv_v(Tune{1,4}, lane-order x) + ops::moe_route_sg with one kernel whose last finishing work-group routes.
// The GEMV calls gemv1_rows directly and the routing body follows moe_route_sg operation for operation.
//   bench_route_fused <model.gguf> <card>
// BENCH_ITERS (default 1000) sets the timed launch count. No Engine code is involved.
#include "../src/model.hpp"
#include "../src/ops.hpp"
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <stdexcept>
#include <vector>

namespace ink {

// R=1, four sub-groups per work-group, exactly as the one-token F32 router's Tune{1,4}. The completion counter
// selects the last work-group after every router row is visible; no work-group waits or spins for another one.
struct RouteFused {
    const uint8_t *W;
    size_t rb;
    int rows, cols;
    const float *x; // lane order
    float *logits;
    const float *bias;
    int ne, nu;
    float wscale;
    int32_t *ids;
    float *wts;
    int32_t *counter;
    int ngroups;

    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<1> it) const {
        auto sg = it.get_sub_group();
        constexpr int SGW = 4;
        const int r0 = (int)it.get_group(0) * SGW + (int)sg.get_group_linear_id();
        gemv1_rows<pl::Raw<fmt::F<G_F32>>, 1, true>(sg, W, rb, rows, cols, x, logits, r0);

        // FUSE=1's ordering in xmx_moe.hpp: release each work-item's writes, barrier, an acq_rel device counter,
        // then an acquire fence in the last group before its plain reads of all logits.
        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::device);
        const auto wg = it.get_group();
        sycl::group_barrier(wg);
        int last = 0;
        if ((int)it.get_local_linear_id() == 0) {
            sycl::atomic_ref<int32_t, sycl::memory_order::acq_rel, sycl::memory_scope::device,
                             sycl::access::address_space::global_space>
                a(*counter);
            last = a.fetch_add(1) == ngroups - 1;
            if (last) a.store(0); // the next application starts at zero, without a host-side reset launch
        }
        last = sycl::group_broadcast(wg, last, 0);
        if (!last) return;
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::device);
        if (sg.get_group_linear_id() != 0) return;

        // moe_route_sg, ntok=1. In particular p and sel use the same expressions, each strict scan/reduction is
        // unchanged, and the lane-0 normalization retains its operation order (including s * 1.0f + 1e-20f).
        constexpr int PER = 8;
        const int lane = (int)sg.get_local_linear_id();
        float p[PER], sel[PER], lg[PER], bs[PER];
#pragma unroll
        for (int u = 0; u < PER; ++u) {
            const int e = sycl::min(lane + SG * u, ne - 1);
            lg[u] = logits[e];
            bs[u] = bias ? bias[e] : 0.0f;
        }
#pragma unroll
        for (int u = 0; u < PER; ++u) {
            const int e = lane + SG * u;
            p[u] = 0.0f;
            sel[u] = -INFINITY;
            if (e < ne) {
                p[u] = 1.0f / (1.0f + sycl::exp(-lg[u]));
                sel[u] = bias ? p[u] + bs[u] : p[u];
            }
        }
        int pick[16];
        for (int k = 0; k < nu; ++k) {
            float lm = sel[0];
            int lu = 0;
            for (int u = 1; u < PER; ++u)
                if (sel[u] > lm) {
                    lm = sel[u];
                    lu = u;
                }
            const float m = sycl::reduce_over_group(sg, lm, sycl::maximum<float>());
            const int le = lane + SG * lu;
            const int b = sycl::reduce_over_group(sg, (le < ne && lm == m) ? le : PER * SG, sycl::minimum<int>());
            for (int u = 0; u < PER; ++u)
                if (lane + SG * u == b) sel[u] = -INFINITY;
            pick[k] = b;
        }
        float w[16];
        for (int k = 0; k < nu; ++k) {
            const int b = pick[k], bu = b / SG;
            float pv = p[0];
            for (int u = 1; u < PER; ++u)
                if (u == bu) pv = p[u];
            w[k] = sycl::select_from_group(sg, pv, b % SG);
        }
        if (lane == 0) {
            float s = 0.0f;
            for (int k = 0; k < nu; ++k) {
                ids[k] = pick[k];
                s += w[k];
            }
            s = s * 1.0f + 1e-20f;
            for (int k = 0; k < nu; ++k) wts[k] = (w[k] / s) * wscale;
        }
    }
};

inline sycl::event route_fused(sycl::queue &q, const WView &w, const float *xl, float *logits, const float *bias,
                               int ne, int nu, float wscale, int32_t *ids, float *wts, int32_t *counter) {
    constexpr int SGW = 4;
    const int rows = (int)w.t->rows(), cols = (int)w.t->ne[0];
    const int ngroups = (rows + SGW - 1) / SGW;
    const sycl::nd_range<1> nr(sycl::range<1>((size_t)ngroups * SGW * SG), sycl::range<1>(SGW * SG));
    return q.parallel_for(nr, RouteFused{w.p, w.rb, rows, cols, xl, logits, bias, ne, nu, wscale, ids, wts,
                                         counter, ngroups});
}

} // namespace ink

int main(int argc, char **argv) {
    using namespace ink;
    if (argc != 3) {
        std::fprintf(stderr, "usage: bench_route_fused <model.gguf> <card>\n");
        return 2;
    }
    try {
        GGUF g(argv[1]);
        Device d(std::atoi(argv[2]));
        HParams hp;
        hp.load(g);
        const Tensor &rt = g.at("blk.0.ffn_gate_inp.weight");
        const Tensor &bt = g.at("blk.0.exp_probs_b.bias");
        const int rows = (int)rt.rows(), cols = (int)rt.ne[0];
        if (rt.type != G_F32 || rt.n_dims != 2 || rows != 128 || cols != 2304 || rt.row_bytes() != (size_t)cols * 4)
            throw std::runtime_error("layer-0 router is not the expected row-major F32 [2304,128] tensor");
        if (bt.type != G_F32 || bt.n_dims != 1 || bt.ne[0] != rows || bt.row_bytes() != (size_t)rows * 4)
            throw std::runtime_error("layer-0 routing bias is not the expected F32 [128] tensor");
        if (hp.n_embd != cols || hp.n_expert != rows || hp.n_used != 8)
            throw std::runtime_error("benchmark requires one token, 128 experts and top 8");

        // Upload only the two real layer-0 tensors used here, rather than the complete multi-GB model.
        uint8_t *wr = d.alloc<uint8_t>(rt.bytes), *br = d.alloc<uint8_t>(bt.bytes);
        Weights weights;
        weights.copy_in(d, g, {{&rt, wr}, {&bt, br}});
        const WView rv{&rt, wr, rt.row_bytes(), K_RAW};
        const float *bias = (const float *)br;

        const size_t lx = xlane_floats(cols);
        std::vector<float> plain(cols), hx(lx, 0.0f);
        std::mt19937 rng(7);
        std::normal_distribution<float> nd(0.0f, 1.0f);
        for (float &v : plain) v = nd(rng);
        for (int i = 0; i < cols; ++i) hx[xlane_at(i)] = plain[i];
        float *xl = d.alloc<float>(lx);
        d.put(xl, hx.data(), lx);

        float *logits0 = d.alloc<float>(rows), *logits1 = d.alloc<float>(rows);
        float *wts0 = d.alloc<float>(hp.n_used), *wts1 = d.alloc<float>(hp.n_used);
        int32_t *ids0 = d.alloc<int32_t>(hp.n_used), *ids1 = d.alloc<int32_t>(hp.n_used);
        int32_t *counter = d.alloc_zero<int32_t>(1);
        auto router0 = [&] {
            gemv_v(d.q, rv, xl, (int)lx, logits0, rows, 1, Tune{1, 4}, true);
        };
        auto route0 = [&] {
            ops::moe_route_sg(d.q, logits0, bias, hp.n_expert, hp.n_used, hp.expert_scale, ids0, wts0, 1);
        };
        auto current = [&] {
            router0();
            route0();
        };
        auto fused = [&] {
            route_fused(d.q, rv, xl, logits1, bias, hp.n_expert, hp.n_used, hp.expert_scale, ids1, wts1, counter);
        };
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 1000;
        if (iters <= 0) throw std::runtime_error("BENCH_ITERS must be positive");
        auto timeit = [&](auto &&launch) {
            for (int i = 0; i < 8; ++i) launch();
            d.q.wait();
            const double t0 = now_s();
            for (int i = 0; i < iters; ++i) launch();
            d.q.wait();
            return (now_s() - t0) * 1e6 / iters;
        };

        const double router_us = timeit(router0);
        const double route_us = timeit(route0);
        double current_us = timeit(current);
        double fused_us = timeit(fused);
        for (int round = 0; round < 4; ++round) { // control/candidate in both time orders, so clock drift is visible
            if (round & 1) {
                fused_us = timeit(fused);
                current_us = timeit(current);
            } else {
                current_us = timeit(current);
                fused_us = timeit(fused);
            }
            std::printf("alternating round %d: current %.3f us, fused %.3f us\n", round, current_us, fused_us);
        }

        std::vector<float> hl0(rows), hl1(rows), hw0(hp.n_used), hw1(hp.n_used);
        std::vector<int32_t> hi0(hp.n_used), hi1(hp.n_used);
        d.get(hl0.data(), logits0, rows);
        d.get(hl1.data(), logits1, rows);
        d.get(hi0.data(), ids0, hp.n_used);
        d.get(hi1.data(), ids1, hp.n_used);
        d.get(hw0.data(), wts0, hp.n_used);
        d.get(hw1.data(), wts1, hp.n_used);
        auto first_diff = [](const auto &a, const auto &b) {
            for (size_t i = 0; i < a.size(); ++i)
                if (std::memcmp(&a[i], &b[i], sizeof(a[i]))) return (long)i;
            return -1L;
        };
        const long bad_logit = first_diff(hl0, hl1), bad_id = first_diff(hi0, hi1), bad_w = first_diff(hw0, hw1);

        std::printf("layer 0 F32 router: %d x %d, one token, top %d, lane-order x, R1 sg4\n", rows, cols, hp.n_used);
        std::printf("current router                         %9.3f us\n", router_us);
        std::printf("current moe_route_sg                   %9.3f us\n", route_us);
        std::printf("current router + moe_route_sg          %9.3f us\n", current_us);
        std::printf("fused last-workgroup router + route    %9.3f us\n", fused_us);
        std::printf("byte compare: logits %s", bad_logit < 0 ? "same" : "DIFF");
        if (bad_logit >= 0) std::printf(" at %d (0x%08x vs 0x%08x)", (int)bad_logit,
                                        *(const uint32_t *)&hl0[bad_logit], *(const uint32_t *)&hl1[bad_logit]);
        std::printf("; eids %s", bad_id < 0 ? "same" : "DIFF");
        if (bad_id >= 0) std::printf(" at %d (%d vs %d)", (int)bad_id, hi0[bad_id], hi1[bad_id]);
        std::printf("; normalized weights %s", bad_w < 0 ? "same" : "DIFF");
        if (bad_w >= 0) std::printf(" at %d (0x%08x vs 0x%08x)", (int)bad_w,
                                    *(const uint32_t *)&hw0[bad_w], *(const uint32_t *)&hw1[bad_w]);
        std::printf("\n");
        return bad_logit < 0 && bad_id < 0 && bad_w < 0 ? 0 : 1;
    } catch (const std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
}
