// ink_run: greedy generation with our Inkling-2 engine on one card.
//   ink_run <model.gguf> <card> <tokens.txt> [n_gen] [ctx]
// Prints "ids: ..." (generated ids, stops at the end-of-turn token) like tools/ref_gen.cpp, timings on stderr.
// INK_DUMP=<dir> saves the reference's named tensors for the prompt (one step: prompt <= INK_UBATCH tokens).
#include "../src/dspark.hpp"
#include <memory>
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
        // INK_DRAFT=<dspark gguf>: the DSpark drafter guesses for INK_SPEC (it reads every step's rows from here on)
        std::unique_ptr<Drafter> dr;
        if (const char *dp = std::getenv("INK_DRAFT")) {
            const double tl = now_s();
            dr = std::make_unique<Drafter>(e, dp);
            std::fprintf(stderr, "[ink] DSpark drafter loaded in %.2f s\n", now_s() - tl);
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
        // INK_SPEC=<k> (1-3): guess up to k tokens by prompt lookup (the most recent earlier occurrence of the last
        // INK_SPEC_MAXN .. INK_SPEC_MINN tokens of the text so far; the tokens that followed it) and check them in one
        // step with the chosen token (Engine::check / accept). The text is the one-token text: each row's scores are
        // bit-identical to a one-token step's.
        const int spec = std::getenv("INK_SPEC") ? std::atoi(std::getenv("INK_SPEC")) : 0;
        if (spec > 0 && !host_argmax && n_gen > 0) {
            if (spec > Engine::SB_MAX - 1) throw std::runtime_error("INK_SPEC: at most " + std::to_string(Engine::SB_MAX - 1));
            const int maxn = std::getenv("INK_SPEC_MAXN") ? std::atoi(std::getenv("INK_SPEC_MAXN")) : 4;
            const int minn = std::getenv("INK_SPEC_MINN") ? std::atoi(std::getenv("INK_SPEC_MINN")) : 2;
            std::vector<int32_t> hist = tok; // prompt, then every chosen token
            auto save_rows = [&](int nrows) {
                for (int r = 0; r < nrows; ++r) {
                    d.get(gen_row.data(), e.lg + (size_t)r * e.m.hp.vocab_padded, gen_row.size());
                    gen_out.write((const char *)gen_row.data(), (std::streamsize)gen_row.size() * 4);
                }
            };
            if (gen_out.is_open()) { d.q.wait(); d.get(gen_row.data(), e.lg + (size_t)(e.n_logit_rows - 1) * e.m.hp.vocab_padded, gen_row.size());
                                     gen_out.write((const char *)gen_row.data(), (std::streamsize)gen_row.size() * 4); }
            int x = e.next_token();
            const int32_t *xdev = e.ids; // the last chosen token on the card (the drafter's anchor)
            out.push_back(x); hist.push_back(x);
            long checks = 0, plain = 0, guessed = 0, kept = 0;
            // INK_SPEC_ADAPT (default 1 with the drafter): draft INK_SPEC guesses, then check the count k (0..INK_SPEC)
            // with the most expected tokens per ms: keep chance of guess j from the drafter's probability (tenths;
            // measured 2026-11-23 on code, haiku and a 3K prompt: 0.9+ kept 283 of 304, 0.8+ 35 of 57, ...), step costs
            // INK_SPEC_COST (ms, steps of 1..4 tokens; card 2 bench 11.4 / 14.9 / 17.4 / 20.4)
            const bool adapt = dr && (!std::getenv("INK_SPEC_ADAPT") || std::atoi(std::getenv("INK_SPEC_ADAPT")));
            const float qk[10] = {0.10f, 0.10f, 0.12f, 0.20f, 0.33f, 0.36f, 0.44f, 0.53f, 0.61f, 0.93f};
            double cost[4] = {11.4, 14.9, 17.4, 20.4};
            if (const char *ce = std::getenv("INK_SPEC_COST"))
                std::sscanf(ce, "%lf,%lf,%lf,%lf", &cost[0], &cost[1], &cost[2], &cost[3]);
            long kchose[4] = {};
            long pb_n[10] = {}, pb_k[10] = {}; // guesses and kept guesses by the drafter's probability (tenths), first rejection ends a check
            double tdraft = 0;
            while (x != e.m.hp.eos && (int)out.size() < n_gen) {
                std::vector<int32_t> g;
                const int H = (int)hist.size();
                const int room = n_gen - (int)out.size() - 1; // guesses past the end would never be shown
                if (dr) {
                    if (room > 0) {
                        const double td = now_s();
                        g = dr->draft(e.n_past, xdev, std::min(spec, room));
                        tdraft += now_s() - td;
                    }
                } else
                    for (int nn = std::min(maxn, H - 1); nn >= minn && g.empty(); --nn)
                        for (int st = H - nn - 1; st >= 0; --st) {
                            if (!std::equal(hist.begin() + st, hist.begin() + st + nn, hist.end() - nn)) continue;
                            for (int j = st + nn; j < H && (int)g.size() < spec; ++j) g.push_back(hist[j]);
                            break;
                        }
                if ((int)g.size() > room) g.resize(std::max(0, room));
                if (adapt && !g.empty()) {
                    double best = 1.0 / cost[0], ex = 1.0, pr = 1.0;
                    int bk = 0;
                    for (int j = 0; j < (int)g.size(); ++j) {
                        pr *= qk[std::min(9, (int)(dr->probs[j] * 10.0f))];
                        ex += pr;
                        if (ex / cost[j + 1] > best) { best = ex / cost[j + 1]; bk = j + 1; }
                    }
                    g.resize(bk);
                    ++kchose[bk];
                }
                if (g.empty()) {
                    e.step(&x, 1);
                    if (gen_out.is_open()) { d.q.wait(); save_rows(1); }
                    x = e.next_token();
                    xdev = e.ids;
                    out.push_back(x); hist.push_back(x);
                    ++plain;
                    continue;
                }
                std::vector<int32_t> tk(1, x);
                tk.insert(tk.end(), g.begin(), g.end());
                const std::vector<int32_t> y = e.check(tk.data(), (int)tk.size());
                int a = 0; // guesses that match the model's choices
                while (a < (int)g.size() && g[a] == y[a] && y[a] != e.m.hp.eos) ++a;
                if (dr)
                    for (int j = 0; j <= a && j < (int)g.size(); ++j) { // guesses the check decided (up to the first rejection)
                        const int b = std::min(9, (int)(dr->probs[j] * 10.0f));
                        ++pb_n[b];
                        if (j < a) ++pb_k[b];
                    }
                e.accept(a + 1);
                if (dr) dr->r_last = a; // r(P0') = the row of the last kept token
                xdev = e.cids + a;
                if (gen_out.is_open()) save_rows(a + 1);
                for (int r = 0; r <= a && (int)out.size() < n_gen; ++r) { out.push_back(y[r]); hist.push_back(y[r]); }
                x = out.back();
                ++checks; guessed += (long)g.size(); kept += a;
                e.prof.collect(); // one profile step per round (INK_PROF)
            }
            std::fprintf(stderr, "[spec] %ld checks (%ld guesses, %ld kept: %.1f %%), %ld plain steps; %.2f tokens per check; drafting %.3f s\n",
                         checks, guessed, kept, guessed ? 100.0 * kept / guessed : 0.0, plain, checks ? 1.0 + (double)kept / checks : 0.0, tdraft);
            if (dr) {
                if (adapt) std::fprintf(stderr, "[spec] guesses checked per round: 0 x%ld, 1 x%ld, 2 x%ld, 3 x%ld\n", kchose[0], kchose[1], kchose[2], kchose[3]);
                std::fprintf(stderr, "[spec] kept by the drafter's probability:");
                for (int b = 0; b < 10; ++b) if (pb_n[b]) std::fprintf(stderr, " 0.%d+ %ld/%ld", b, pb_k[b], pb_n[b]);
                std::fprintf(stderr, "\n");
            }
            n_gen = 0; // done: the loop below does nothing
        }
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
