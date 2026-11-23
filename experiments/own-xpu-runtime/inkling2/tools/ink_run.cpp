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
        // INK_PLANAR=0: keep every weight in the file layout (the first version's kernels)
        bool planar = !std::getenv("INK_PLANAR") || std::atoi(std::getenv("INK_PLANAR"));
        // expert tensors with a decode copy (layers 20-23) stay off the card in the file layout (planarize makes the copy)
        if (planar && dec_on()) w.upload(d, g, true, [](const Tensor &t) { return dec_target(t); });
        else w.upload(d, g);
        bool dumping = std::getenv("INK_DUMP") != nullptr;
        std::map<std::string, WView> views;
        if (planar) views = planarize(d, g, w);
        Engine e(d, g, w, ctx, ub, dumping, planar ? &views : nullptr);
        std::fprintf(stderr, "[ink] context %d positions, card memory in use %.2f of %.2f GiB (score rows %d)\n", ctx,
                     d.allocated / 1073741824.0, d.total_mem() / 1073741824.0, e.prow);
        // INK_BENCH_REAL=1 with INK_BENCH_STEP: the steps take the prompt's last 8 tokens (fed without them), each repeat
        // at the same positions: consecutive real tokens choose their experts as in a check of guesses
        const bool bench_real = std::getenv("INK_BENCH_STEP") && std::getenv("INK_BENCH_REAL") && std::atoi(std::getenv("INK_BENCH_REAL"));
        std::vector<int32_t> tail;
        if (bench_real) {
            if (tok.size() < 16) throw std::runtime_error("INK_BENCH_REAL needs a prompt of at least 16 tokens");
            tail.assign(tok.end() - 8, tok.end());
            tok.resize(tok.size() - 8);
        }
        double t0 = now_s();
        e.feed(tok);
        double t1 = now_s();
        if (const char *sp = std::getenv("INK_SAVE_LOGITS")) { // the prompt's last logits row, F32
            std::ofstream o(sp, std::ios::binary);
            const int V = e.m.hp.vocab;
            o.write((const char *)(e.logits.data() + e.logits.size() - V), (std::streamsize)V * 4);
        }
        e.prof.collect(); // the prompt
        e.prof.rows.clear(); e.prof.busy_ms = e.prof.span_ms = 0; e.prof.steps = 0;
        if (const char *bs = std::getenv("INK_BENCH_STEP")) { // time steps of k tokens after the prompt: "k1,k2,..."
            e.host_logits = false;
            std::string list = bs;
            size_t p0 = 0;
            while (p0 < list.size()) {
                size_t p1 = list.find(',', p0);
                if (p1 == std::string::npos) p1 = list.size();
                int k = std::atoi(list.substr(p0, p1 - p0).c_str());
                p0 = p1 + 1;
                std::vector<int32_t> tk(k, tok.back());
                if (bench_real) {
                    if (k > 8) throw std::runtime_error("INK_BENCH_REAL: steps of at most 8 tokens");
                    tk.assign(tail.begin(), tail.begin() + k);
                }
                const int reps = 6, base = e.n_past;
                e.step(tk.data(), k); d.q.wait(); // warm
                if (bench_real) e.n_past = base;
                e.prof.collect(); e.prof.rows.clear(); e.prof.busy_ms = e.prof.span_ms = 0; e.prof.steps = 0;
                double a0 = now_s(), host = 0;
                for (int r = 0; r < reps; ++r) {
                    const double h0 = now_s();
                    e.step(tk.data(), k);
                    host += now_s() - h0; // the host's time to submit the step's launches
                    d.q.wait(); e.prof.collect();
                    if (bench_real) e.n_past = base;
                }
                double ms = (now_s() - a0) / reps * 1e3;
                std::fprintf(stderr, "[bench] step of %d tokens: %.2f ms (%.2f ms per token), at position %d; host submits in %.2f ms\n", k, ms,
                             ms / k, e.n_past, host / reps * 1e3);
                if (e.prof.on) { e.prof.report(stderr); e.prof.rows.clear(); e.prof.busy_ms = e.prof.span_ms = 0; e.prof.steps = 0; }
            }
            return 0;
        }
        std::vector<int> out;
        // INK_HOST_ARGMAX=1: copy every step's logits to the host and choose there (the first version's loop)
        const bool host_argmax = std::getenv("INK_HOST_ARGMAX") && std::atoi(std::getenv("INK_HOST_ARGMAX"));
        e.host_logits = host_argmax;
        // INK_SAVE_GEN=<file>: every step's last logits row (the prompt's, then each generated token's), F32, appended
        std::ofstream gen_out;
        std::vector<float> gen_row;
        if (const char *gp = std::getenv("INK_SAVE_GEN")) { gen_out.open(gp, std::ios::binary); gen_row.resize(e.m.hp.vocab); }
        for (int i = 0; i < n_gen; ++i) {
            if (gen_out.is_open()) {
                d.q.wait();
                d.get(gen_row.data(), e.lg + (size_t)(e.n_logit_rows - 1) * e.m.hp.vocab_padded, gen_row.size());
                gen_out.write((const char *)gen_row.data(), (std::streamsize)gen_row.size() * 4);
            }
            int b = host_argmax ? e.argmax_last() : e.next_token();
            out.push_back(b);
            if (b == e.m.hp.eos) break;
            if (i + 1 == n_gen) break;
            e.all_logits = false;
            if (host_argmax) e.feed({b});
            else e.step_next();
            e.prof.collect();
        }
        double t2 = now_s();
        std::printf("ids:");
        for (int t : out) std::printf(" %d", t);
        std::printf("\n");
        std::fprintf(stderr, "[ink] prompt %zu tokens %.3f s (%.1f tok/s); generated %zu in %.3f s (%.2f tok/s)\n", tok.size(),
                     t1 - t0, tok.size() / (t1 - t0), out.size(), t2 - t1, out.size() > 1 ? (out.size() - 1) / (t2 - t1) : 0.0);
        e.prof.report(stderr);
    } catch (std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
