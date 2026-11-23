// ink_run: greedy generation with our Inkling-2 engine on one card.
//   ink_run <model.gguf> <card> <tokens.txt> [n_gen] [ctx]
// Prints "ids: ..." (generated ids, stops at the end-of-turn token) like tools/ref_gen.cpp, timings on stderr.
// INK_DUMP=<dir> saves the reference's named tensors for the prompt (one step: prompt <= INK_UBATCH tokens).
#include "../src/engine.hpp"
#include <fstream>

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 4) { std::fprintf(stderr, "usage: ink_run <model.gguf> <card> <tokens.txt> [n_gen] [ctx]\n"); return 2; }
    try {
        GGUF g(argv[1]);
        Device d(std::atoi(argv[2]));
        std::vector<int32_t> tok;
        { std::ifstream f(argv[3]); long v; while (f >> v) tok.push_back((int32_t)v); }
        int n_gen = argc > 4 ? std::atoi(argv[4]) : 0;
        int ctx = argc > 5 ? std::atoi(argv[5]) : (int)(tok.size() + n_gen + 16);
        int ub = std::getenv("INK_UBATCH") ? std::atoi(std::getenv("INK_UBATCH")) : 512;
        Weights w;
        w.upload(d, g);
        bool dumping = std::getenv("INK_DUMP") != nullptr;
        Engine e(d, g, w, ctx, ub, dumping);
        double t0 = now_s();
        e.feed(tok);
        double t1 = now_s();
        std::vector<int> out;
        for (int i = 0; i < n_gen; ++i) {
            int b = e.argmax_last();
            out.push_back(b);
            if (b == e.m.hp.eos) break;
            if (i + 1 == n_gen) break;
            e.all_logits = false;
            e.feed({b});
        }
        double t2 = now_s();
        std::printf("ids:");
        for (int t : out) std::printf(" %d", t);
        std::printf("\n");
        std::fprintf(stderr, "[ink] prompt %zu tokens %.3f s (%.1f tok/s); generated %zu in %.3f s (%.2f tok/s)\n", tok.size(),
                     t1 - t0, tok.size() / (t1 - t0), out.size(), t2 - t1, out.size() > 1 ? (out.size() - 1) / (t2 - t1) : 0.0);
    } catch (std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
