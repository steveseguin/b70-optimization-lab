// ink_run: greedy generation with our Inkling-2 engine on one card.
//   ink_run <model.gguf> <card> <tokens.txt> [n_gen] [ctx]
// Prints "ids: ..." (generated ids, stops at the end-of-turn token) like tools/ref_gen.cpp, timings on stderr.
// INK_DUMP=<dir> saves the reference's named tensors for the prompt (one step: prompt <= INK_UBATCH tokens).
#include "../src/dspark.hpp"
#include <memory>
#include <cstring>
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
        // prompt step size (the same bits for every size), by context. Bigger steps fill the expert tiles better; at long
        // contexts the attention takes most of the time and they stop paying (2026-11-25, logits identical; tok/s for
        // steps of 1,024 / 2,048 / 4,096 tokens: 3K 869-884 / 941-945 / 965-967 on card 2, 31K 935-943 / 956-966 /
        // 969-971 on card 3, 100K 712-718 / 719-723 / 717-718 on cards 1 and 5, 200K 559-563 / 553-554 / - on cards 1
        // and 5). Card memory at 100K: 19.46 / 20.70 / 23.79 GiB; past 300K positions 512 (one card holds 521K; 1,024
        // was slower at 403K). INK_UBATCH=<n>: that size only.
        const bool ub_fixed = std::getenv("INK_UBATCH") != nullptr;
        int ub = ub_fixed ? std::atoi(std::getenv("INK_UBATCH"))
                          : ctx <= 65536 ? 4096 : ctx <= 131072 ? 2048 : ctx <= 300000 ? 1024 : 512;
        Weights w;
        // INK_PLANAR=0: keep every weight in the file layout (the first version's kernels)
        bool planar = !std::getenv("INK_PLANAR") || std::atoi(std::getenv("INK_PLANAR"));
        // expert tensors with a decode copy (layers 20-23) stay off the card in the file layout (planarize makes the copy)
        // Q6_K weights stay off too (only their padded planar copy goes on the card; INK_Q6K_SKIP=0: both, as before)
        const bool q6skip = !std::getenv("INK_Q6K_SKIP") || std::atoi(std::getenv("INK_Q6K_SKIP"));
        // the token embedding table stays in host memory (0.49 GB; Engine::embed decodes each step's rows on the host with
        // the kernel's expressions; INK_EMBD_HOST=0: on the card)
        const bool embd_host = planar && (!std::getenv("INK_EMBD_HOST") || std::atoi(std::getenv("INK_EMBD_HOST")));
        const auto host_t = [embd_host](const Tensor &t) { return embd_host && t.name == "token_embd.weight"; };
        if (planar && dec_on())
            w.upload(d, g, true, [q6skip, host_t](const Tensor &t) { return dec_target(t) || (q6skip && q6k_target(t)) || host_t(t); });
        else if (embd_host) w.upload(d, g, true, host_t);
        else w.upload(d, g);
        bool dumping = std::getenv("INK_DUMP") != nullptr;
        std::map<std::string, WView> views;
        if (planar) views = planarize(d, g, w, true, host_t);
        // a step size that does not fit is halved down to 512; above 512 it must leave 1 GiB for the drafter (which takes
        // ~0.55 GiB), so a context that fits only with 512 keeps it as before
        const bool drafting = std::getenv("INK_DRAFT") != nullptr;
        std::unique_ptr<Engine> ep;
        for (;;) {
            const size_t mk = d.mark();
            d.hold = drafting && ub > 512 ? (size_t)1 << 30 : 0;
            try {
                ep = std::make_unique<Engine>(d, g, w, ctx, ub, dumping, planar ? &views : nullptr);
                break;
            } catch (const std::runtime_error &ex) {
                if (ub_fixed || ub <= 512 || !std::strstr(ex.what(), "would pass the card's memory")) throw;
                d.release_to(mk);
                std::fprintf(stderr, "[ink] steps of %d tokens do not fit beside %d positions: %d\n", ub, ctx, ub / 2);
                ub /= 2;
            }
        }
        d.hold = 0;
        Engine &e = *ep;
        // every kernel program loaded now (INK_PRELOAD=0: each on its first launch, as before). The runtime otherwise
        // loads them inside the first prompt step: the card waited 145 ms before the first attention-input product and
        // 25 ms after the first embedding copy (INK_PROF_GAPS). 2026-11-25, card 2: 0.2 s at load, 3K prompt 3.23 -> 3.06 s
        // (968 -> 1,021 tok/s), same values; card memory the same, host peak +53 MB
        if (!std::getenv("INK_PRELOAD") || std::atoi(std::getenv("INK_PRELOAD"))) {
            const double tp = now_s();
            auto kb = sycl::get_kernel_bundle<sycl::bundle_state::executable>(d.ctx, {d.dev});
            std::fprintf(stderr, "[ink] kernel programs loaded in %.3f s (%zu kernels)\n", now_s() - tp, kb.get_kernel_ids().size());
        }
        std::fprintf(stderr, "[ink] context %d positions, steps of %d tokens, card memory in use %.2f of %.2f GiB (score rows %d; driver: %.2f GiB free)\n",
                     ctx, ub, d.allocated / 1073741824.0, d.total_mem() / 1073741824.0, e.prow, d.free_mem() / 1073741824.0);
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
            std::fprintf(stderr, "[ink] DSpark drafter loaded in %.2f s, card memory in use %.2f GiB\n", now_s() - tl,
                         d.allocated / 1073741824.0);
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
        if (e.prof.on && std::getenv("INK_PROF_PROMPT")) { std::fprintf(stderr, "[prof] the prompt:\n"); e.prof.report(stderr); }
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
        // INK_SPEC=<k> (1-7): guess up to k tokens by prompt lookup (the most recent earlier occurrence of the last
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
            // INK_SPEC_COST (ms, steps of 1..8 tokens at a short context) plus, per position of context, INK_SPEC_KV
            // (ms; the cache read of a step) and INK_SPEC_KVX (ms, each further token's attention), so long contexts
            // check more guesses (2026-11-24, card 3 profile at 200K: 1 token 12.5 ms of attention, 4 tokens 14.8)
            const bool adapt = dr && (!std::getenv("INK_SPEC_ADAPT") || std::atoi(std::getenv("INK_SPEC_ADAPT")));
            const float *qk = Drafter::QK.v; // (dspark.hpp)
            double cost0[8] = {11.4, 14.9, 17.4, 20.4, 23.9, 27.5, 30.5, 33.1}, cost[8]; // (5-8: card 3 2026-11-24 + 4 tokens)
            if (const char *ce = std::getenv("INK_SPEC_COST"))
                std::sscanf(ce, "%lf,%lf,%lf,%lf,%lf,%lf,%lf,%lf", &cost0[0], &cost0[1], &cost0[2], &cost0[3], &cost0[4], &cost0[5], &cost0[6],
                            &cost0[7]);
            const double kv1 = std::getenv("INK_SPEC_KV") ? std::atof(std::getenv("INK_SPEC_KV")) : 6.2e-5,
                         kvx = std::getenv("INK_SPEC_KVX") ? std::atof(std::getenv("INK_SPEC_KVX")) : 3.85e-6;
            long kchose[8] = {};
            long pb_n[10] = {}, pb_k[10] = {}; // guesses and kept guesses by the drafter's probability (tenths), first rejection ends a check
            double tdraft = 0;
            // INK_DRAFT_LOG=<file> with INK_ORACLE=<ids of the plain run>: draft 7 guesses each round and log their
            // probabilities and how many lead the plain text, then check as usual (study of longer checks)
            std::vector<int> oracle;
            FILE *dlog = nullptr;
            if (dr && std::getenv("INK_DRAFT_LOG") && std::getenv("INK_ORACLE")) {
                std::ifstream of(std::getenv("INK_ORACLE"));
                std::string w;
                of >> w; // "ids:"
                for (int v; of >> v;) oracle.push_back(v);
                dlog = std::fopen(std::getenv("INK_DRAFT_LOG"), "w");
                dr->stop_thr = 0.0f; // every guess computed for the study
            }
            while (x != e.m.hp.eos && (int)out.size() < n_gen) {
                std::vector<int32_t> g;
                const int H = (int)hist.size();
                const int room = n_gen - (int)out.size() - 1; // guesses past the end would never be shown
                if (adapt) {
                    for (int k = 0; k < 8; ++k) // (a check of more rows than the engine's dec_rows reads the cache again)
                        cost[k] = cost0[k] + e.n_past * (kv1 * ((k + e.dec_rows) / e.dec_rows) + kvx * k);
                    // the drafter's slots 4-7 are worth reading only if a 4th guess could be checked: with r the 5-token
                    // step's extra cost over 4 tokens, that needs the chain c of guesses 1-3 above r / (0.93 - 3 r)
                    // (0.93 c > (1 + 3 c) r: the 4th guess adds at most 0.93 c expected tokens, the 3 before at least c each)
                    const double r = cost[4] / cost[3] - 1.0, den = 0.93 - 3.0 * r;
                    if (!dlog) dr->stop_hi = den > 0.0 ? (float)(r / den) : 1.0f;
                }
                if (dr) {
                    if (room > 0) {
                        const double td = now_s();
                        if (dlog) {
                            const int o0 = (int)out.size(), nd = std::min(7, (int)oracle.size() - o0);
                            if (nd > 0) {
                                g = dr->draft(e.n_past, xdev, nd, x);
                                int m = 0;
                                while (m < nd && g[m] == oracle[o0 + m]) ++m;
                                std::fprintf(dlog, "%d", m);
                                for (int j = 0; j < nd; ++j) std::fprintf(dlog, " %.4f", dr->probs[j]);
                                std::fprintf(dlog, "\n");
                                g.resize(std::min(spec, (int)g.size()));
                            }
                        } else
                            g = dr->draft(e.n_past, xdev, std::min(spec, room), x);
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
                if (adapt) {
                    std::fprintf(stderr, "[spec] guesses checked per round:");
                    for (int k = 0; k <= std::min(7, spec); ++k) std::fprintf(stderr, " %d x%ld", k, kchose[k]);
                    std::fprintf(stderr, "\n");
                }
                std::fprintf(stderr, "[spec] kept by the drafter's probability:");
                for (int b = 0; b < 10; ++b) if (pb_n[b]) std::fprintf(stderr, " 0.%d+ %ld/%ld", b, pb_k[b], pb_n[b]);
                std::fprintf(stderr, "\n");
            }
            if (dlog) std::fclose(dlog);
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
        std::fprintf(stderr, "[ink] at the end: driver reports %.2f GiB free (card memory in use %.2f GiB)\n", d.free_mem() / 1073741824.0,
                     d.allocated / 1073741824.0);
    } catch (std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
