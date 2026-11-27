// bench_tp_expert: one-token NVFP4 gate|up + down with balanced whole-expert TP2. Card A computes routing slots
// 0-3 and card B slots 4-7 with the unchanged full_prod arithmetic, then each sends its four complete E-float down
// outputs to the other through ordinary host memory. Both directions' device reads (and then writes) are submitted
// before waiting. An unchanged one-card eight-slot run is the timing and bit-for-bit output control.
//   bench_tp_expert <model.gguf> <cardA> <cardB>
#include "../src/xmx_moe.hpp"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>

using namespace ink;

int main(int argc, char **argv) {
    if (argc < 4) {
        std::fprintf(stderr, "usage: bench_tp_expert <model.gguf> <cardA> <cardB>\n");
        return 2;
    }
    const int card_a = std::atoi(argv[2]), card_b = std::atoi(argv[3]);
    if (card_a == card_b) {
        std::fprintf(stderr, "cardA and cardB must be different physical cards\n");
        return 2;
    }
    try {
        GGUF gf(argv[1]);
        Device a(card_a), b(card_b);
        Weights wa, wb;
        wa.upload(a, gf, false);
        wb.upload(b, gf, false);
        auto views_a = planarize(a, gf, wa, false);
        auto views_b = planarize(b, gf, wb, false);
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 200;
        const int NL = std::getenv("BENCH_NL") ? std::atoi(std::getenv("BENCH_NL")) : 4;
        constexpr int NE = 128, KU = 8, HALF = 4, E = 2304, NFF = 1152;
        if (iters < 1 || NL < 1 || NL > 20) throw std::runtime_error("BENCH_ITERS >= 1, BENCH_NL 1-20");

        std::vector<WView> gua(NL), dna(NL), gub(NL), dnb(NL);
        for (int l = 0; l < NL; ++l) {
            const std::string gs = "blk." + std::to_string(l) + ".ffn_gate_up_exps.weight";
            const std::string ds = "blk." + std::to_string(l) + ".ffn_down_exps.weight";
            gua[l] = views_a.at(gs); dna[l] = views_a.at(ds);
            gub[l] = views_b.at(gs); dnb[l] = views_b.at(ds);
            if (gua[l].kind != K_NVFP4P || dna[l].kind != K_NVFP4P || gub[l].kind != K_NVFP4P || dnb[l].kind != K_NVFP4P)
                throw std::runtime_error("layer " + std::to_string(l) + " is not NVFP4");
        }
        const size_t gu_es = gua[0].rb * (size_t)gua[0].t->ne[1];
        const size_t dn_es = dna[0].rb * (size_t)dna[0].t->ne[1];
        if (gu_es != gub[0].rb * (size_t)gub[0].t->ne[1] || dn_es != dnb[0].rb * (size_t)dnb[0].t->ne[1])
            throw std::runtime_error("the cards' weight layouts differ");
        { // full_prod's tile layout, in place on each card
            uint8_t *tmpa = a.alloc<uint8_t>(std::max(gu_es, dn_es));
            uint8_t *tmpb = b.alloc<uint8_t>(std::max(gu_es, dn_es));
            for (int l = 0; l < NL; ++l) {
                xm::repack_tiles(a.q, const_cast<uint8_t *>(gua[l].p), gua[l].rb, 2 * NFF, E, NE, tmpa);
                xm::repack_tiles(a.q, const_cast<uint8_t *>(dna[l].p), dna[l].rb, E, NFF, NE, tmpa);
                xm::repack_tiles(b.q, const_cast<uint8_t *>(gub[l].p), gub[l].rb, 2 * NFF, E, NE, tmpb);
                xm::repack_tiles(b.q, const_cast<uint8_t *>(dnb[l].p), dnb[l].rb, E, NFF, NE, tmpb);
            }
            sycl::free(tmpa, a.q);
            sycl::free(tmpb, b.q);
        }

        // One token and eight distinct experts. The two TP2 routes are exact prefixes/suffixes of the control route.
        std::vector<int32_t> ids(KU);
        for (int k = 0; k < KU; ++k) ids[k] = (k * 37 + 5) % NE;
        int32_t *ids1 = a.alloc<int32_t>(KU), *idsa = a.alloc<int32_t>(HALF), *idsb = b.alloc<int32_t>(HALF);
        a.put(ids1, ids.data(), KU);
        a.put(idsa, ids.data(), HALF);
        b.put(idsb, ids.data() + HALF, HALF);
        MoeGroups group1, groupa, groupb;
        group1.alloc(a, NE, KU);
        groupa.alloc(a, NE, HALF);
        groupb.alloc(b, NE, HALF);
        moe_group(a.q, ids1, KU, NE, group1);
        moe_group(a.q, idsa, HALF, NE, groupa).wait();
        moe_group(b.q, idsb, HALF, NE, groupb).wait();
        const int tiles1 = MoeGroups::max_tiles(NE, KU), tiles2 = MoeGroups::max_tiles(NE, HALF);

        std::mt19937 rng(11);
        std::normal_distribution<float> nd(0.0f, 1.0f);
        std::vector<float> hx(E);
        for (auto &v : hx) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
        std::vector<uint16_t> px(3 * E);
        for (int i = 0; i < E; ++i) split3_store(hx[i], px.data() + i, E);
        uint16_t *pxa = a.alloc<uint16_t>(px.size()), *pxb = b.alloc<uint16_t>(px.size());
        a.put(pxa, px.data(), px.size());
        b.put(pxb, px.data(), px.size());

        const size_t hpp1 = (size_t)KU * NFF, hpp2 = (size_t)HALF * NFF;
        uint16_t *hp1 = a.alloc<uint16_t>(3 * hpp1);
        uint16_t *hpa = a.alloc<uint16_t>(3 * hpp2), *hpb = b.alloc<uint16_t>(3 * hpp2);
        float *y1 = a.alloc<float>((size_t)KU * E);
        float *ya = a.alloc<float>((size_t)HALF * E), *yb = b.alloc<float>((size_t)HALF * E);
        float *a_from_b = a.alloc<float>((size_t)HALF * E), *b_from_a = b.alloc<float>((size_t)HALF * E);
        const xm::ActOp op{nullptr, 8.0f, 4.0f};

        auto one_card_layer = [&](int i) {
            const int l = i % NL;
            xm::full_prod<1, 0, 4, 2, 128, 8, 1>(a.q, gua[l].p, gu_es, E, NFF, 2 * NFF, group1, tiles1,
                                                 pxa, (size_t)E, true, op, hp1, hpp1, nullptr, 0);
            xm::full_prod<1, 1, 4, 2, 128, 8, 1>(a.q, dna[l].p, dn_es, NFF, NFF, E, group1, tiles1,
                                                 hp1, hpp1, false, op, nullptr, 0, y1, E);
        };
        constexpr size_t copy_count = (size_t)HALF * E, copy_bytes = copy_count * sizeof(float);
        std::vector<float> host_a(copy_count), host_b(copy_count); // deliberately ordinary host memory
        auto tp2_layer = [&](int i) {
            const int l = i % NL;
            // Submit both cards' complete expert chains before waiting for either card.
            xm::full_prod<1, 0, 4, 2, 128, 8, 1>(a.q, gua[l].p, gu_es, E, NFF, 2 * NFF, groupa, tiles2,
                                                 pxa, (size_t)E, true, op, hpa, hpp2, nullptr, 0);
            xm::full_prod<1, 1, 4, 2, 128, 8, 1>(a.q, dna[l].p, dn_es, NFF, NFF, E, groupa, tiles2,
                                                 hpa, hpp2, false, op, nullptr, 0, ya, E);
            xm::full_prod<1, 0, 4, 2, 128, 8, 1>(b.q, gub[l].p, gu_es, E, NFF, 2 * NFF, groupb, tiles2,
                                                 pxb, (size_t)E, true, op, hpb, hpp2, nullptr, 0);
            xm::full_prod<1, 1, 4, 2, 128, 8, 1>(b.q, dnb[l].p, dn_es, NFF, NFF, E, groupb, tiles2,
                                                 hpb, hpp2, false, op, nullptr, 0, yb, E);
            // A -> host A and B -> host B are both in flight before either wait.
            a.q.memcpy(host_a.data(), ya, copy_bytes);
            b.q.memcpy(host_b.data(), yb, copy_bytes);
            a.q.wait();
            b.q.wait();
            // Pair the opposite-direction writes too. These waits make both host buffers safe to reuse and both
            // received device outputs complete before the next layer or the final comparison.
            a.q.memcpy(a_from_b, host_b.data(), copy_bytes);
            b.q.memcpy(b_from_a, host_a.data(), copy_bytes);
            a.q.wait();
            b.q.wait();
        };

        for (int i = 0; i < 8; ++i) one_card_layer(i);
        a.q.wait();
        double t0 = now_s();
        for (int i = 0; i < iters; ++i) one_card_layer(i);
        a.q.wait();
        const double one_ms = (now_s() - t0) / iters * 1e3;

        for (int i = 0; i < 8; ++i) tp2_layer(i);
        t0 = now_s();
        for (int i = 0; i < iters; ++i) tp2_layer(i);
        const double tp2_ms = (now_s() - t0) / iters * 1e3;

        // Produce both final results from layer 0, then compare every float on both cards after the exchange.
        one_card_layer(0);
        a.q.wait();
        tp2_layer(0);
        std::vector<float> ref((size_t)KU * E), got_ya(copy_count), got_yb(copy_count);
        std::vector<float> got_a_from_b(copy_count), got_b_from_a(copy_count);
        a.get(ref.data(), y1, ref.size());
        a.get(got_ya.data(), ya, copy_count);
        a.get(got_a_from_b.data(), a_from_b, copy_count);
        b.get(got_yb.data(), yb, copy_count);
        b.get(got_b_from_a.data(), b_from_a, copy_count);
        size_t different = 0;
        auto compare = [&](const std::vector<float> &got, int first_slot) {
            for (size_t i = 0; i < got.size(); ++i) {
                const size_t ri = (size_t)(first_slot + (int)(i / E)) * E + i % E;
                different += std::memcmp(&got[i], &ref[ri], sizeof(float)) != 0;
            }
        };
        compare(got_ya, 0);
        compare(got_a_from_b, HALF);
        compare(got_b_from_a, 0);
        compare(got_yb, HALF);

        std::printf("one token, cards %d+%d, layers 0-%d in turn, %d iterations\n", card_a, card_b, NL - 1, iters);
        std::printf("one-card 8 slots: %.3f ms; TP2 4+4 slots + host exchange: %.3f ms; expert+transport speedup: %.3fx\n",
                    one_ms, tp2_ms, one_ms / tp2_ms);
        std::printf("copy correctness: %s (%zu of %zu post-exchange floats differ from the one-card control)\n",
                    different ? "DIFFER" : "same bits", different, 2 * ref.size());
        return different ? 1 : 0;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "error: %s\n", e.what());
        return 1;
    }
}
