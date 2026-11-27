// ink_run: greedy generation with our Inkling-2 engine on one card.
//   ink_run <model.gguf> <card> <tokens.txt> [n_gen] [ctx]
// Prints "ids: ..." (generated ids, stops at the end-of-turn token) like tools/ref_gen.cpp, timings on stderr.
// INK_DUMP=<dir> saves the reference's named tensors for the prompt (one step: prompt <= INK_UBATCH tokens).
#include "../src/cache_file.hpp"
#include "../src/snapshot.hpp"
#include "../src/vision.hpp"
#include <memory>
#include <cstring>
#include <fstream>
#include <sstream>
#include <unordered_map>
#include <thread>
#include <deque>
#include <poll.h>
#include <unistd.h>

// prompt lookup through an index: for n = 2..4, each n-gram's most recent start among the n-grams that end before the
// newest token (the guesses are the tokens after it). The same choice as scanning back from the end.
struct NgramIndex {
    std::unordered_map<uint64_t, int> m[3];
    int upto[3] = {0, 0, 0}; // n-grams with starts below this are in m[n - 2]
    static uint64_t key(const int32_t *p, int n) {
        uint64_t h = 1469598103934665603ull ^ (uint64_t)n;
        for (int i = 0; i < n; ++i) { h ^= (uint32_t)p[i]; h *= 1099511628211ull; }
        return h;
    }
    // index every n-gram with start + n <= H - 1
    void extend(const std::vector<int32_t> &hist, int H) {
        for (int n = 2; n <= 4; ++n) {
            auto &mm = m[n - 2];
            for (int s = upto[n - 2]; s + n <= H - 1; ++s) mm[key(hist.data() + s, n)] = s;
            upto[n - 2] = std::max(upto[n - 2], H - n);
        }
    }
    // the most recent start st with st + n <= H - 1 whose n tokens equal the last n of hist[0, H); -1 if none
    int find(const std::vector<int32_t> &hist, int H, int n) {
        if (n < 2 || n > 4 || H - 1 < n) return -1;
        extend(hist, H);
        auto &mm = m[n - 2];
        auto it = mm.find(key(hist.data() + H - n, n));
        if (it == mm.end()) return -1;
        const int st = it->second;
        return std::equal(hist.begin() + st, hist.begin() + st + n, hist.end() - n) ? st : -1;
    }
};

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 4) { std::fprintf(stderr, "usage: ink_run <model.gguf> <card> <tokens.txt> [n_gen] [ctx]\n"); return 2; }
    try {
        GGUF g(argv[1]);
        Device d(std::atoi(argv[2]));
        std::vector<int32_t> tok;
        {
            std::ifstream f(argv[3]);
            if (!f) throw std::runtime_error(std::string("cannot read the prompt file ") + argv[3]);
            long v;
            while (f >> v) tok.push_back((int32_t)v);
            // (a missing or misnamed token file used to run an empty prompt; serving reads its prompts from stdin)
            if (tok.empty() && !std::getenv("INK_SERVE") && !std::getenv("INK_LOAD_CACHE"))
                throw std::runtime_error(std::string("no token ids in ") + argv[3]);
        }
        int n_gen = argc > 4 ? std::atoi(argv[4]) : 0;
        // INK_TURNS=<file>: follow-up turns, one per line (token ids, e.g. <|message_user|><|content_text|>...<|end_message|>).
        // After an answer, its last token (the end token <|content_model_end_sampling|>, which the chat template keeps at
        // the end of the model's message, thinking included) and the next turn go through the cache as a prompt step,
        // then the turn is answered (n_gen tokens at most); one "ids:" line per turn. A fresh run of the whole
        // conversation as one prompt gives the same ids (every path computes the same values)
        std::vector<std::vector<int32_t>> turns;
        if (const char *tf = std::getenv("INK_TURNS")) {
            std::ifstream f(tf);
            if (!f) throw std::runtime_error(std::string("INK_TURNS: cannot read ") + tf);
            std::string line;
            while (std::getline(f, line)) {
                std::istringstream ls(line);
                std::vector<int32_t> t;
                for (long v; ls >> v;) t.push_back((int32_t)v);
                if (!t.empty()) turns.push_back(t);
            }
        }
        size_t turn_tok = 0;
        for (const auto &t : turns) turn_tok += t.size() + 1 + n_gen;
        int ctx = argc > 5 ? std::atoi(argv[5]) : (int)(tok.size() + n_gen + 16 + turn_tok);
        // prompt step size (the same bits for every size), by context. Bigger steps fill the expert tiles better; at long
        // contexts the attention takes most of the time and they stop paying (2026-11-25, logits identical; tok/s for
        // steps of 1,024 / 2,048 / 4,096 tokens: 3K 869-884 / 941-945 / 965-967 on card 2, 31K 935-943 / 956-966 /
        // 969-971 on card 3, 100K 712-718 / 719-723 / 717-718 on cards 1 and 5, 200K 559-563 / 553-554 / - on cards 1
        // and 5). Card memory at 100K: 19.46 / 20.70 / 23.79 GiB; past 300K positions 512 (one card holds 521K; 1,024
        // was slower at 403K). Again with the matrix-engine kernels (2026-11-26, ink_run_xd11, same card both orders,
        // ids identical): 31K 4,096 -> 8,192 1,487.1 / 1,483.0 -> 1,521.5 / 1,509.8 (card 3), 1,409.7 / 1,397.1 ->
        // 1,426.0 / 1,421.6 (card 1), card memory 20.60 -> 25.75 GiB; 100K 2,048 -> 4,096 978.8 / 978.6 -> 992.0 / 985.6
        // (card 5), 984.3 / 981.4 -> 986.2 / 984.7 (card 2), 20.21 -> 22.80 GiB; 200K 1,024 706.8 / 702.6, 2,048 700.1 /
        // 699.7 (card 4). Never more than the context needs (the next power of two from 512). INK_UBATCH=<n>: that size.
        const bool ub_fixed = std::getenv("INK_UBATCH") != nullptr;
        int ub = ub_fixed ? std::atoi(std::getenv("INK_UBATCH"))
                          : ctx <= 65536 ? 8192 : ctx <= 131072 ? 4096 : ctx <= 300000 ? 1024 : 512;
        if (!ub_fixed) {
            int need = 512;
            while (need < ctx && need < ub) need *= 2;
            ub = std::min(ub, need);
        }
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
        const size_t mw = d.mark(); // (a retry with a smaller step loads the weights again from here)
        std::map<std::string, WView> views;
        const auto load = [&]() {
            if (planar && dec_on())
                w.upload(d, g, true, [q6skip, host_t](const Tensor &t) { return dec_target(t) || (q6skip && q6k_target(t)) || host_t(t); });
            else if (embd_host) w.upload(d, g, true, host_t);
            else w.upload(d, g);
            if (planar) views = planarize(d, g, w, true, host_t);
        };
        if (!std::getenv("INK_SPLIT") || !std::atoi(std::getenv("INK_SPLIT"))) load(); // (INK_SPLIT: below, each engine's own)
        bool dumping = std::getenv("INK_DUMP") != nullptr;
        // a step size that does not fit is halved down to 256 (the same bits; 512 was the floor until 2026-11-26, when the
        // Q6E copies' 31 MiB more pushed 530K positions past the card at 512); above 512 it must leave 1 GiB for the
        // drafter (which takes ~0.55 GiB), so a context that fits only with 512 or 256 keeps it as before
        const bool drafting = std::getenv("INK_DRAFT") != nullptr;
        std::unique_ptr<Engine> ep;
        // INK_SPLIT=<S1>[,<S2>,...]: the model over a chain of engines (Engine::prev): applications 0 .. S1 - 1, S1 ..
        // S2 - 1, ... on the cards INK_SPLIT_CARDS=<c1>[,<c2>,...] (INK_SPLIT_CARD for one; default: this card), the last
        // range on this card; each engine holds only its layers' weights. Every step of this card's engine (the one the
        // rest of this driver uses) runs the earlier engines' parts first and takes their rows through host memory. The
        // same bits as one engine; prompts in a pipeline when every engine has its own card (Engine::feed). Saved
        // prompts are the same files as one engine's (each application's state from and to the engine that runs it) and
        // serving copies cover every engine; not with several sequences or pictures
        std::vector<int> cuts, ccards;
        auto ints = [](const char *v) {
            std::vector<int> r;
            for (const char *p = v; p && *p;) {
                r.push_back(std::atoi(p));
                p = std::strchr(p, ',');
                if (p) ++p;
            }
            return r;
        };
        if (const char *v = std::getenv("INK_SPLIT")) cuts = ints(v);
        if (cuts.size() == 1 && cuts[0] == 0) cuts.clear();
        const int split_at = cuts.empty() ? 0 : cuts[0];
        std::vector<std::unique_ptr<Device>> devs; // the other cards
        std::vector<std::unique_ptr<Engine>> chain; // the engines before this card's
        std::vector<std::unique_ptr<Weights>> wch;
        std::vector<std::unique_ptr<std::map<std::string, WView>>> vch;
        if (split_at) {
            HParams hp;
            hp.load(g);
            for (size_t i = 0; i < cuts.size(); ++i)
                if (cuts[i] < 1 || cuts[i] >= hp.n_app || (i && cuts[i] <= cuts[i - 1]))
                    throw std::runtime_error("INK_SPLIT: rising application numbers from 1 to " + std::to_string(hp.n_app - 1));
            if (!planar || !dec_on() || !q6skip || !embd_host) throw std::runtime_error("INK_SPLIT: the default weight layouts only");
            for (const char *v : {"INK_VISION", "INK_SEQS"})
                if (std::getenv(v)) throw std::runtime_error(std::string("INK_SPLIT: not with ") + v);
            if (const char *v = std::getenv("INK_SPLIT_CARDS")) ccards = ints(v);
            else if (const char *v1 = std::getenv("INK_SPLIT_CARD")) ccards = ints(v1);
            if (ccards.empty()) ccards.assign(cuts.size(), d.index);
            if (ccards.size() != cuts.size()) throw std::runtime_error("INK_SPLIT_CARDS: one card per engine before this card's");
            auto dev_of = [&](int c) -> Device & {
                if (c == d.index) return d;
                for (auto &x : devs) if (x->index == c) return *x;
                devs.push_back(std::make_unique<Device>(c));
                return *devs.back();
            };
            const auto own_of = [&](int lo, int hi) {
                return [&, lo, hi](const Tensor &t) { return host_t(t) || Engine::unused_tensor(hp, lo, hi, t); };
            };
            for (size_t i = 0; i <= cuts.size(); ++i) {
                const int lo = i ? cuts[i - 1] : 0, hi = i < cuts.size() ? cuts[i] : hp.n_app;
                const bool last = i == cuts.size();
                Device &dx = last ? d : dev_of(ccards[i]);
                Weights &wx = last ? w : *wch.emplace_back(std::make_unique<Weights>());
                std::map<std::string, WView> &vx = last ? views : *vch.emplace_back(std::make_unique<std::map<std::string, WView>>());
                const auto own = own_of(lo, hi);
                wx.upload(dx, g, true, [&](const Tensor &t) { return dec_target(t) || q6k_target(t) || own(t); });
                vx = planarize(dx, g, wx, true, own);
                if (last) d.hold = drafting && ub > 512 ? (size_t)1 << 30 : 0;
                auto ex = std::make_unique<Engine>(dx, g, wx, ctx, ub, last ? dumping : false, &vx, lo, last ? -1 : hi);
                if (!chain.empty()) { ex->prev = chain.back().get(); chain.back()->next = ex.get(); }
                std::fprintf(stderr, "[ink] split: applications %d-%d on card %d, card memory in use %.2f GiB (driver: %.2f GiB free)\n", lo,
                             hi - 1, dx.index, dx.allocated / 1073741824.0, dx.free_mem() / 1073741824.0);
                if (last) ep = std::move(ex);
                else chain.push_back(std::move(ex));
            }
            for (auto &x : devs) {
                auto kb = sycl::get_kernel_bundle<sycl::bundle_state::executable>(x->ctx, {x->dev});
                (void)kb;
            }
        }
        for (; !split_at;) {
            d.hold = drafting && ub > 512 ? (size_t)1 << 30 : 0;
            try {
                ep = std::make_unique<Engine>(d, g, w, ctx, ub, dumping, planar ? &views : nullptr);
                break;
            } catch (const std::runtime_error &ex) {
                if (ub_fixed || ub <= 256 || !std::strstr(ex.what(), "would pass the card's memory")) throw;
                // the failed constructor may have changed weights in place already (the NVFP4 tile, XQ and Q8E layouts; the
                // Q6E copies free their planar ones): a retry on them read freed memory (530K, 2026-11-26: device lost) or
                // would lay a layout out twice, so everything is loaded again (~3-4 s) before the smaller step
                d.release_to(mw);
                w = Weights();
                views.clear();
                std::fprintf(stderr, "[ink] steps of %d tokens do not fit beside %d positions: %d (weights loaded again)\n", ub, ctx, ub / 2);
                load();
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
            dr = std::make_unique<Drafter>(e, dp, &tok);
            // a split: the engines before this card's carry the drafter's feature rows of their applications along
            for (auto &c : chain) c->extra_rows = {e.feat_vis[0], e.feat_vis[1], e.feat_vis[2]};
            std::fprintf(stderr, "[ink] DSpark drafter loaded in %.2f s, card memory in use %.2f GiB\n", now_s() - tl,
                         d.allocated / 1073741824.0);
        }
        // the lookup index of the prompt (INK_SPEC_LOOKUP below) is built on a host thread while the card reads the prompt
        NgramIndex ngi;
        std::thread ngt;
        if (std::getenv("INK_SPEC") && std::atoi(std::getenv("INK_SPEC")) > 0 &&
            (!std::getenv("INK_SPEC_LOOKUP") || std::atoi(std::getenv("INK_SPEC_LOOKUP"))))
            ngt = std::thread([&] { ngi.extend(tok, (int)tok.size() + 1); });
        // INK_LOAD_CACHE=<file>: start from a prompt saved by INK_SAVE_CACHE (src/cache_file.hpp); this run's prompt must
        // start with the file's, and only the rest is read. INK_SAVE_CACHE=<file>: save the state after the prompt
        // the model file's size, with the top bit set for the matrix-engine experts' arithmetic (INK_XMX, baseline v5) and bit
        // 62 for the dense matrices' (INK_XMX_DENSE, baseline v6), bit 61 for the Q6_K ones' (INK_XMX_Q6, baseline v7; all on
        // by default), bit 60 for layers 20-23's experts' (INK_XMX_Q): a
        // file saved with the other arithmetic is refused ("saved by another model or engine"), as its continuation would
        // not equal a fresh read
        const uint64_t model_id = (uint64_t)std::filesystem::file_size(argv[1]) | (e.xmx ? 1ull << 63 : 0) | (e.xdense ? 1ull << 62 : 0) | (e.xq6 ? 1ull << 61 : 0) |
                                  (e.xq ? 1ull << 60 : 0);
        size_t loaded = 0;
        const bool serve = std::getenv("INK_SERVE") && std::atoi(std::getenv("INK_SERVE"));
        if (const char *lc = std::getenv("INK_LOAD_CACHE"); lc && !serve) {
            const double tl = now_s();
            size_t fb = 0;
            loaded = load_cache(lc, e, dr.get(), tok, model_id, &fb);
            const double dt = now_s() - tl;
            std::fprintf(stderr, "[ink] cache: %zu positions loaded from %s in %.3f s (%.2f GB/s)\n", loaded, lc, dt, fb / dt / 1e9);
        }
        double t0 = now_s();
        if (loaded < tok.size()) e.feed(std::vector<int32_t>(tok.begin() + (long)loaded, tok.end()));
        d.q.wait(); // (feed returns once its launches are queued; the prompt's time ends when the card is done)
        double t1 = now_s();
        // INK_SHARD=<S> (two engines, INK_SPLIT=<cut>): after the prompt, each engine also holds positions 0 .. S - 1 of the
        // other one's full-context applications and folds them for its writing steps (Engine::shard_start; the same values)
        if (const char *sh = std::getenv("INK_SHARD"); sh && std::atoi(sh) > 0) {
            if (serve || std::getenv("INK_TURNS") || std::getenv("INK_SEQS") || std::getenv("INK_SAVE_CACHE"))
                throw std::runtime_error("INK_SHARD: a prompt and its answer only (no serving, turns, sequences or saves yet)");
            const double ts = now_s();
            e.shard_start(std::atoi(sh));
            std::fprintf(stderr, "[ink] shard: positions 0-%d of each full-context application moved to the other engine in %.3f s\n",
                         std::atoi(sh) - 1, now_s() - ts);
            t0 += now_s() - ts; t1 += now_s() - ts;
        }
        // INK_SHARD_COPY=<s> (any number of engines): copies of each engine's oldest slices of s positions on the others
        // (Engine::shard_copy_start; nothing moves, the same values)
        if (const char *sh = std::getenv("INK_SHARD_COPY"); sh && std::atoi(sh) > 0) {
            if (serve || std::getenv("INK_SEQS")) throw std::runtime_error("INK_SHARD_COPY: not with serving (INK_SHARD_SERVE) or sequences");
            const double ts = now_s();
            e.shard_copy_start(std::atoi(sh));
            std::fprintf(stderr, "[ink] shard: positions 0-%d of each full-context application copied to the other engines (%zu, %d each) in %.3f s\n",
                         e.shard_S - 1, e.shard_ring.size(), e.shard_s, now_s() - ts);
            t0 += now_s() - ts; t1 += now_s() - ts;
        }
        if (const char *sc = std::getenv("INK_SAVE_CACHE")) {
            const double ts = now_s();
            const size_t fb = save_cache(sc, e, dr.get(), tok, model_id);
            const double dt = now_s() - ts;
            std::fprintf(stderr, "[ink] cache: %zu positions saved to %s in %.3f s (%.2f GB/s)\n", tok.size(), sc, dt, fb / dt / 1e9);
            t0 += now_s() - ts; t1 += now_s() - ts; // (the save is in neither the prompt's time nor the writing's)
        }
        if (ngt.joinable()) ngt.join(); // (every path past here; an index of 471K tokens takes ~0.2 s, the prompt minutes)
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
        std::vector<int32_t> conv = tok; // the conversation so far: every token fed, then each answer
        const int n_gen0 = n_gen;
        size_t fed_n = tok.size() - loaded;
        // INK_SERVE=1: requests on stdin, answers on stdout (the DeepSeek server's protocol; /home/steve/inkling-serve)
        //   in  G <id> <max_new> <nstop> <stop ids...> <n> <ids...>   the whole conversation so far as token ids
        //   in  S <id>                                               stop that request after the current round
        //   in  W <id> <file>                                        save the conversation read so far (src/cache_file.hpp)
        //   in  Q (or end of input)                                  quit
        //   out @@READY <context>; @@P <id> <read> <secs>; @@T <id> <tok>...; @@R <id> (a new conversation);
        //       @@D <id> <eos|max|stop> <read> <gen> <read_s> <gen_s> <rounds> <guessed> <kept> <context>;
        //       @@E <id> <reason> (refused, the state unchanged); @@W <id> <bytes> <secs>
        // The engine keeps the conversation it has read (the answer's last token is decided, not read). A request that
        // extends what was read is read from there; any other is a new conversation: the cache starts over, from the
        // longest saved prompt in INK_SERVE_CACHES=<dir> (*.inkc) that the request starts with, if any (a long document
        // loads in seconds instead of being read again). Stop tokens: the end token (the only one the engine stops at).
        // INK_LOAD_CACHE=<file> with INK_SERVE: start holding that saved prompt.
        std::string ibuf, rid;
        bool in_eof = false, stop_req = false;
        std::deque<std::string> lines;
        auto pump = [&](int ms) { // input bytes into lines; waits up to ms (-1: until something arrives)
            for (;;) {
                const size_t nl = ibuf.find('\n');
                if (nl != std::string::npos) { lines.push_back(ibuf.substr(0, nl)); ibuf.erase(0, nl + 1); continue; }
                if (in_eof) return;
                pollfd pf{0, POLLIN, 0};
                const int r = poll(&pf, 1, ms);
                if (r < 0 && errno == EINTR) continue;
                if (r <= 0) return;
                char b[65536];
                const ssize_t n = read(0, b, sizeof b);
                if (n <= 0) { in_eof = true; continue; }
                ibuf.append(b, (size_t)n);
                ms = 0;
            }
        };
        auto sout = [](const std::string &l) { std::fputs(l.c_str(), stdout); std::fputc('\n', stdout); std::fflush(stdout); };
        auto poll_stop = [&]() -> bool { // "S <rid>" among the lines that arrived (others stay queued)
            pump(0);
            for (auto it = lines.begin(); it != lines.end();) {
                std::istringstream is(*it);
                std::string c, id;
                is >> c >> id;
                if (c == "S" && id == rid) { stop_req = true; it = lines.erase(it); } else ++it;
            }
            return stop_req;
        };
        int pend_row = 0; // the logits row of the last decided token (W saves it)
        // INK_SAMPLE="<temperature> <top_p> <top_k> <min_p> <seed>" (runs outside serving): sample instead of choosing the
        // most likely token (ops::sample_rows; the same text with or without guessing)
        if (const char *sv = std::getenv("INK_SAMPLE"); sv && !serve) {
            std::istringstream ss(sv);
            unsigned long long sd = 0;
            ss >> e.samp.T >> e.samp.topp >> e.samp.topk >> e.samp.minp >> sd;
            if (!ss) throw std::runtime_error("INK_SAMPLE: <temperature> <top_p> <top_k> <min_p> <seed>");
            e.samp_seed = sd;
        }
        std::string samp_id; // the request id of the last P line (sampling settings), and those settings
        ops::SampleArgs samp_next;
        unsigned long long samp_seed_next = 0;
        long req_rounds = 0, req_guessed = 0, req_kept = 0;
        auto emit = [&](const std::vector<int> &o, size_t from) {
            if (!serve || from >= o.size()) return;
            std::string l = "@@T " + rid;
            for (size_t i = from; i < o.size(); ++i) l += " " + std::to_string(o[i]);
            sout(l);
        };
        // serving: a copy of the state at each request's start (src/snapshot.hpp), when it fits on the card
        // snap: at the start of the last request's last message; snapb (when a second copy fits): at the start of the
        // conversation's first message after the system messages, so a new conversation with the same system prompt
        // (and tools and effort) or another question after the same document continues from there
        Snapshot snap, snapb;
        if (serve && e.seqs.size() == 1) snap.init(e, dr.get()); // (several sequences: no copies)
        if (serve && snap.ok) snapb.init(e, dr.get());
        // INK_VISION=<mmproj.gguf>: the image encoder (src/vision.hpp), when it fits after the copies
        Vision vis(e);
        if (const char *vp = std::getenv("INK_VISION")) vis.init(vp);
        // INK_SEQS_TEST=<n>: several conversations in shared steps (Engine::step_rows) against each alone. INK_SEQS_PROMPTS
        // = token files, comma-separated, one per sequence (INK_SEQS of them); sequence s writes n - s * n / (2 * count)
        // tokens (so the shared steps shrink from all rows to one). Each prompt alone first (plain greedy writing), then
        // all prompts read on their own sequences and written together, the rows in turn in forward and reverse order.
        // Prints per sequence whether the ids and the logits row of every step are bit-identical, and the speeds
        if (const char *stv = std::getenv("INK_SEQS_TEST")) {
            const int ng = std::atoi(stv);
            std::vector<std::vector<int32_t>> pp;
            {
                std::string all = std::getenv("INK_SEQS_PROMPTS") ? std::getenv("INK_SEQS_PROMPTS") : "", f;
                std::istringstream ls(all);
                while (std::getline(ls, f, ',')) {
                    std::ifstream in(f);
                    if (!in) throw std::runtime_error("INK_SEQS_PROMPTS: cannot read " + f);
                    std::vector<int32_t> t;
                    for (long v; in >> v;) t.push_back((int32_t)v);
                    pp.push_back(t);
                }
            }
            const int ns = (int)pp.size();
            if (ns < 1 || ns != (int)e.seqs.size()) throw std::runtime_error("INK_SEQS_TEST: INK_SEQS must equal the number of prompts");
            const int V = e.m.hp.vocab, VP = e.m.hp.vocab_padded;
            std::vector<int> want(ns);
            const bool same_n = std::getenv("INK_SEQS_SAME") && std::atoi(std::getenv("INK_SEQS_SAME")); // every sequence n tokens
            for (int s = 0; s < ns; ++s) want[s] = same_n ? ng : std::max(1, ng - s * ng / (2 * ns));
            std::vector<std::vector<int32_t>> ia(ns), ib(ns);
            std::vector<std::vector<float>> ra(ns), rb(ns);
            e.host_logits = false;
            double alone_s = 0;
            long alone_tok = 0;
            for (int s = 0; s < ns; ++s) {
                e.bind(s); e.reset(); e.all_logits = false;
                e.feed(pp[s]);
                d.q.wait();
                const double t0 = now_s();
                for (int i = 0; i < want[s]; ++i) {
                    ra[s].resize((size_t)(i + 1) * V);
                    d.get(ra[s].data() + (size_t)i * V, e.lg + (size_t)(e.n_logit_rows - 1) * VP, V);
                    ia[s].push_back(e.next_token());
                    if (i + 1 < want[s]) e.step_next();
                }
                d.q.wait();
                alone_s += now_s() - t0; alone_tok += want[s] - 1;
            }
            for (int s = 0; s < ns; ++s) {
                e.bind(s); e.reset(); e.all_logits = false;
                e.feed(pp[s]);
                d.q.wait();
                rb[s].resize(V);
                d.get(rb[s].data(), e.lg + (size_t)(e.n_logit_rows - 1) * VP, V);
                ib[s].push_back(e.next_token());
            }
            e.prof.collect(); e.prof.rows.clear(); e.prof.busy_ms = e.prof.span_ms = 0; e.prof.steps = 0; // (the shared steps only)
            const double t0 = now_s();
            long tok_b = 0, steps = 0;
            std::vector<long> by_rows(Engine::SB_MAX + 1);
            for (;;) {
                std::vector<int> rs;
                std::vector<int32_t> tk;
                for (int k = 0; k < ns; ++k) {
                    const int s = steps % 2 ? ns - 1 - k : k;
                    if ((int)ib[s].size() < want[s]) { rs.push_back(s); tk.push_back(ib[s].back()); }
                }
                if (rs.empty()) break;
                const int n = (int)rs.size();
                e.step_rows(tk.data(), rs.data(), n);
                d.q.wait();
                for (int t = 0; t < n; ++t) {
                    std::vector<float> &r = rb[rs[t]];
                    r.resize(r.size() + V);
                    d.get(r.data() + r.size() - V, e.lg + (size_t)t * VP, V);
                }
                std::vector<int32_t> nx(n);
                e.next_rows(rs.data(), n, nx.data());
                for (int t = 0; t < n; ++t) ib[rs[t]].push_back(nx[t]);
                tok_b += n; ++steps; ++by_rows[n];
                if (e.prof.on) e.prof.collect();
            }
            const double tb = now_s() - t0;
            bool all = true;
            for (int s = 0; s < ns; ++s) {
                int same = 0;
                while (same < want[s] && ia[s][same] == ib[s][same]) ++same;
                int rsame = 0;
                while (rsame < want[s] && std::memcmp(ra[s].data() + (size_t)rsame * V, rb[s].data() + (size_t)rsame * V, sizeof(float) * V) == 0) ++rsame;
                const bool ok = same == want[s] && rsame == want[s];
                all &= ok;
                std::fprintf(stderr, "[seqs] sequence %d (prompt %zu tokens, %d written): ids %s (%d of %d), logits rows %s (%d of %d)\n", s,
                             pp[s].size(), want[s], same == want[s] ? "identical" : "DIFFER", same, want[s], rsame == want[s] ? "identical" : "DIFFER",
                             rsame, want[s]);
            }
            std::string hist;
            for (int k = 1; k <= Engine::SB_MAX; ++k) if (by_rows[k]) hist += " " + std::to_string(k) + ":" + std::to_string(by_rows[k]);
            std::fprintf(stderr, "[seqs] alone %.1f tok/s (%ld tokens, %.3f s); together %.1f tok/s (%ld tokens in %ld steps, %.3f s; steps by rows%s)\n",
                         alone_tok / alone_s, alone_tok, alone_s, tok_b / tb, tok_b, steps, tb, hist.c_str());
            std::fprintf(stderr, "[seqs] %s\n", all ? "ALL IDENTICAL" : "DIFFERENCES");
            if (e.prof.on) { e.prof.collect(); e.prof.report(stderr); }
            return all ? 0 : 1;
        }
        // INK_IMAGE_TEST=<rgb file>:<width>:<height>:<out file>: encode one picture (8-bit RGB rows), save its rows
        // (rows x 2304 floats) and stop
        if (const char *it = std::getenv("INK_IMAGE_TEST")) {
            std::string a(it);
            const size_t c1 = a.find(':'), c2 = a.find(':', c1 + 1), c3 = a.find(':', c2 + 1);
            if (c1 == std::string::npos || c2 == std::string::npos || c3 == std::string::npos)
                throw std::runtime_error("INK_IMAGE_TEST=<rgb file>:<width>:<height>:<out file>");
            const int w = std::atoi(a.substr(c1 + 1, c2 - c1 - 1).c_str()), hh = std::atoi(a.substr(c2 + 1, c3 - c2 - 1).c_str());
            std::ifstream f(a.substr(0, c1), std::ios::binary);
            std::vector<uint8_t> rgb((size_t)w * hh * 3);
            if (!f.read((char *)rgb.data(), (std::streamsize)rgb.size())) throw std::runtime_error("INK_IMAGE_TEST: short rgb file");
            int M = 0;
            for (int rep = 0; rep < 3; ++rep) {
                std::vector<float> rows = vis.encode(rgb.data(), w, hh, M);
                std::fprintf(stderr, "[vision] %d x %d -> %d rows in %.3f s\n", w, hh, M, vis.last_s);
                if (rep == 0) {
                    std::ofstream o(a.substr(c3 + 1), std::ios::binary);
                    o.write((const char *)rows.data(), (std::streamsize)(rows.size() * sizeof(float)));
                }
            }
            if (e.prof.on) { e.prof.collect(); e.prof.report(stderr); }
            return 0;
        }
        const bool lk_serve = serve && std::getenv("INK_SPEC") && std::atoi(std::getenv("INK_SPEC")) > 0 &&
                              (!std::getenv("INK_SPEC_LOOKUP") || std::atoi(std::getenv("INK_SPEC_LOOKUP")));
        if (serve) {
            if (const char *lc = std::getenv("INK_LOAD_CACHE")) {
                const double tl = now_s();
                size_t fb = 0;
                std::vector<int32_t> ft;
                load_cache(lc, e, dr.get(), {}, model_id, &fb, &ft);
                conv = ft;
                std::fprintf(stderr, "[serve] holding %zu tokens from %s (%.3f s)\n", ft.size(), lc, now_s() - tl);
            }
            sout("@@READY " + std::to_string(e.cap));
        }
        // INK_SHARD_SERVE=1 (serving a split, INK_SPLIT=<cuts>): shared caches (the same values) for long answers. Once an
        // answer has INK_SHARD_AFTER (default 448) tokens and the context holds INK_SHARD_MIN (default 32,768, measured) positions or
        // more, each engine's oldest full-context positions are folded by the others while it folds the rest: copies of
        // n_past / engines positions on each other engine (Engine::shard_copy_start), or with two engines and no room
        // for copies the oldest half moved (Engine::shard_start). They stay shared across turns: a read of up to
        // INK_SHARD_FEED (default 256) tokens goes in steps of dec_rows (any step size gives the same values); moved
        // positions go back first for a longer read or a save (Engine::shard_end; copies need nothing); a copy below
        // the shared positions drops or moves them back; a new conversation from position 0 drops them (Engine::reset)
        // INK_SHARD_MODE: copy (copies only), move (two engines, moved only) or auto (default: copies when they fit, which
        // also keeps them through long reads and saves; else moved with two engines). Copies are shared again, larger,
        // once the context has grown by half
        const bool shard_serve = serve && std::getenv("INK_SHARD_SERVE") && std::atoi(std::getenv("INK_SHARD_SERVE")) && e.prev;
        const std::string shard_mode = std::getenv("INK_SHARD_MODE") ? std::getenv("INK_SHARD_MODE") : "auto";
        bool shard_copy_fits = shard_mode != "move";
        auto env_int = [](const char *k, int dv) { const char *v = std::getenv(k); return v ? std::atoi(v) : dv; };
        const int shard_min = env_int("INK_SHARD_MIN", 32768), shard_after = env_int("INK_SHARD_AFTER", 448),
                  shard_feed = env_int("INK_SHARD_FEED", 256);
        if (shard_serve) std::fprintf(stderr, "[serve] shared caches (%s) past %d positions, after %d answer tokens, reads of up to %d tokens shared\n",
                                      shard_mode.c_str(), shard_min, shard_after, shard_feed);
        auto shard_back = [&](const char *why) { // (moved positions only: copies need nothing)
            if (!e.shard_S || e.shard_copy) return;
            const double ts = now_s();
            const int S = e.shard_S;
            e.shard_end();
            std::fprintf(stderr, "[serve] shared positions 0-%d back on their own engines (%s) in %.3f s\n", S - 1, why, now_s() - ts);
        };
        auto shard_try = [&] {
            if (!shard_serve || e.n_past < shard_min) return;
            if (e.shard_S && !(e.shard_copy && (long)e.n_past * 2 >= (long)e.shard_n0 * 3)) return;
            const int Q = 128 * fz::PVB, ext = e.m.hp.rel_extent, N = (int)e.chain_engines().size();
            if (shard_copy_fits) {
                int s = (e.n_past / N + Q / 2) / Q * Q;
                while (s >= Q && (long)(N - 1) * s + ext > e.n_past) s -= Q;
                if (e.shard_S && (s <= e.shard_s || e.shard_copy_room(s) >= 0)) return; // (not larger, or no room: the current ones stay)
                if (s >= Q) {
                    const bool again = e.shard_S > 0;
                    if (again) e.shard_end();
                    const double ts = now_s();
                    try {
                        e.shard_copy_start(s);
                        std::fprintf(stderr, "[serve] positions 0-%d of each full-context application copied to the other engines (%d each)%s in %.3f s (context %d)\n",
                                     e.shard_S - 1, s, again ? " again" : "", now_s() - ts, e.n_past);
                        return;
                    } catch (std::exception &ex) {
                        std::fprintf(stderr, "[serve] %s\n", ex.what());
                        shard_copy_fits = false;
                    }
                }
            }
            if (e.shard_S || shard_mode == "copy" || N != 2) return;
            int S = (e.n_past / 2 + Q / 2) / Q * Q;
            if (S + ext > e.n_past) S = (e.n_past - ext) / Q * Q;
            if (S < Q) return;
            const double ts = now_s();
            e.shard_start(S);
            std::fprintf(stderr, "[serve] positions 0-%d of each full-context application shared with the other engine in %.3f s (context %d)\n",
                         S - 1, now_s() - ts, e.n_past);
        };
        // a read: shared, in steps of dec_rows tokens
        auto feedx = [&](const std::vector<int32_t> &t) {
            if (!e.shard_S || t.size() > (size_t)shard_feed) { e.feed(t); return; } // (copies: long reads as usual)
            for (size_t p = 0; p < t.size(); p += (size_t)e.dec_rows) e.step(t.data() + p, (int)std::min<size_t>((size_t)e.dec_rows, t.size() - p));
        };
        const char *lib_dir = std::getenv("INK_SERVE_CACHES");
        // pictures (serving): V lines register a picture's rows under ids from Engine::XID0 + key (the server's 30-bit
        // hash of the picture), kept in host memory up to INK_VISION_HOST_MB (default 256) MiB; the least recently
        // used ones go first, never one registered since the last G line
        struct Pic { std::vector<float> rows; int M = 0, w = 0, h = 0; uint64_t used = 0; };
        std::map<uint32_t, Pic> pics;
        uint64_t pic_gen = 1;
        size_t pic_bytes = 0;
        const size_t pic_cap = (size_t)(std::getenv("INK_VISION_HOST_MB") ? std::atol(std::getenv("INK_VISION_HOST_MB")) : 256) << 20;
        constexpr uint32_t XSPAN = (1u << 30) - 1;
        auto pic_ids = [&](uint32_t key, int r) { return (int32_t)(Engine::XID0 + (int32_t)((key + (uint32_t)r) % XSPAN)); };
        std::function<bool(uint32_t)> pic_busy = [](uint32_t) { return false; }; // (a picture a request still has to read)
        auto handle_v = [&](std::istringstream &is, const std::string &id) {
            unsigned long key = 0;
            int w = 0, hh = 0;
            std::string path;
            is >> key >> w >> hh >> path;
            try {
                if (!is || w < 1 || hh < 1) throw std::runtime_error("bad-V-line");
                if (!vis.ok) throw std::runtime_error("no-image-encoder");
                const uint32_t k = (uint32_t)(key & ((1ul << 30) - 1));
                auto it = pics.find(k);
                char b[160];
                if (it != pics.end()) {
                    if (it->second.w != w || it->second.h != hh) throw std::runtime_error("image-id-collision");
                    it->second.used = pic_gen;
                    std::snprintf(b, sizeof b, "@@V %s %d 0.000 cached", id.c_str(), it->second.M);
                    sout(b);
                    return;
                }
                std::ifstream f(path, std::ios::binary);
                std::vector<uint8_t> rgb((size_t)w * hh * 3);
                if (!f.read((char *)rgb.data(), (std::streamsize)rgb.size())) throw std::runtime_error("short-rgb-file");
                Pic pc;
                pc.w = w; pc.h = hh; pc.used = pic_gen;
                pc.rows = vis.encode(rgb.data(), w, hh, pc.M);
                for (int r = 0; r < pc.M; ++r)
                    if (e.xrow.count(pic_ids(k, r))) throw std::runtime_error("image-id-collision");
                const size_t nb = pc.rows.size() * sizeof(float);
                while (pic_bytes + nb > pic_cap) { // least recently used first, never one of this request
                    auto lru = pics.end();
                    for (auto jt = pics.begin(); jt != pics.end(); ++jt)
                        if (jt->second.used < pic_gen && !pic_busy(jt->first) && (lru == pics.end() || jt->second.used < lru->second.used)) lru = jt;
                    if (lru == pics.end()) break;
                    for (int r = 0; r < lru->second.M; ++r) e.xrow.erase(pic_ids(lru->first, r));
                    pic_bytes -= lru->second.rows.size() * sizeof(float);
                    pics.erase(lru);
                }
                Pic &st = pics[k] = std::move(pc);
                for (int r = 0; r < st.M; ++r) e.xrow[pic_ids(k, r)] = st.rows.data() + (size_t)r * Vision::OUT;
                pic_bytes += nb;
                std::snprintf(b, sizeof b, "@@V %s %d %.3f", id.c_str(), st.M, vis.last_s);
                sout(b);
            } catch (std::exception &ex) { sout("@@E " + id + " image " + std::string(ex.what()).substr(0, 200)); }
        };
        // several conversations (INK_SEQS = n > 1): sequence s holds conversation s. "C <id> <s>" before a G line puts
        // that request on sequence s (default 0); a sequence takes one request at a time (else @@E <id> busy). A prompt
        // is read in steps of INK_SEQS_CHUNK tokens (default 512) while other sequences write, of the engine's step size
        // when none does; every writing sequence gets one token per shared step (Engine::step_rows: each row's values
        // are those of its sequence alone). No guessing, state copies, saved prompts or W lines here. Replies as above;
        // @@D's rounds = tokens written, guessed and kept 0
        if (serve && e.seqs.size() > 1) {
            const int ns = (int)e.seqs.size(), eos = e.m.hp.eos;
            const int chunk = std::getenv("INK_SEQS_CHUNK") ? std::max(16, std::atoi(std::getenv("INK_SEQS_CHUNK"))) : 512;
            struct Job {
                std::string rid;
                std::vector<int32_t> ids, out;
                size_t at = 0, fed = 0; // the next prompt token to read; tokens this request reads
                int max_new = 0;
                double t0 = 0, t1 = 0;
                bool live = false, reading = true, stop = false;
            };
            std::vector<Job> jobs(ns);
            std::vector<std::vector<int32_t>> convs(ns);
            std::map<std::string, int> seq_of;
            std::map<std::string, std::pair<ops::SampleArgs, uint64_t>> samp_of;
            int rr = 0;
            pic_busy = [&](uint32_t k) {
                const int32_t first = pic_ids(k, 0);
                for (const Job &j : jobs)
                    if (j.live && j.reading && std::find(j.ids.begin() + (long)j.at, j.ids.end(), first) != j.ids.end()) return true;
                return false;
            };
            auto tok_line = [&](const Job &j, int32_t t) { sout("@@T " + j.rid + " " + std::to_string(t)); };
            auto finish = [&](int s, const char *why) {
                Job &j = jobs[s];
                const double t2 = now_s();
                if (j.reading) { j.t1 = t2; convs[s].assign(j.ids.begin(), j.ids.begin() + (long)j.at); } // (stopped while reading)
                else { convs[s] = j.ids; convs[s].insert(convs[s].end(), j.out.begin(), j.out.end()); }
                char b[256];
                std::snprintf(b, sizeof b, "@@D %s %s %zu %zu %.3f %.3f %zu 0 0 %d", j.rid.c_str(), why, j.fed, j.out.size(), j.t1 - j.t0,
                              t2 - j.t1, j.out.size(), e.seq_past(s) + (j.reading ? 0 : 1));
                sout(b);
                std::fprintf(stderr, "[serve] %s (sequence %d): read %zu tokens in %.3f s, answered %zu in %.3f s (%.2f tok/s), %s, context %d\n",
                             j.rid.c_str(), s, j.fed, j.t1 - j.t0, j.out.size(), t2 - j.t1, j.out.size() > 1 ? (j.out.size() - 1) / (t2 - j.t1) : 0.0,
                             why, e.seq_past(s) + (j.reading ? 0 : 1));
                j = Job{};
            };
            bool quit = false;
            while (!quit) {
                bool busy = false;
                for (const Job &j : jobs) busy |= j.live;
                pump(busy ? 0 : -1);
                if (!busy && lines.empty() && in_eof) break;
                while (!lines.empty() && !quit) {
                    const std::string ln = lines.front();
                    lines.pop_front();
                    std::istringstream is(ln);
                    std::string cmd, id;
                    is >> cmd >> id;
                    if (cmd == "Q") { quit = true; break; }
                    if (cmd.empty()) continue;
                    if (cmd == "S") { for (Job &j : jobs) if (j.live && j.rid == id) j.stop = true; continue; }
                    if (cmd == "C") {
                        int sq = -1;
                        is >> sq;
                        if (!is || sq < 0 || sq >= ns) sout("@@E " + id + " no-sequence");
                        else seq_of[id] = sq;
                        continue;
                    }
                    if (cmd == "V") { handle_v(is, id); continue; }
                    if (cmd == "P") {
                        ops::SampleArgs a;
                        unsigned long long sd = 0;
                        is >> a.T >> a.topp >> a.topk >> a.minp >> sd;
                        if (!is || !(a.T >= 0.0f && a.T <= 100.0f) || !(a.topp > 0.0f && a.topp <= 1.0f) || a.topk < 0 ||
                            !(a.minp >= 0.0f && a.minp < 1.0f)) { sout("@@E " + id + " bad-sampling"); continue; }
                        samp_of[id] = {a, (uint64_t)sd};
                        continue;
                    }
                    if (cmd == "W") { sout("@@E " + id + " unsupported-with-several-sequences"); continue; }
                    if (cmd != "G") { sout("@@E - unknown-command"); continue; }
                    long mx = 0, nstop = 0, n = 0;
                    is >> mx >> nstop;
                    for (long i = 0; i < nstop && is; ++i) { long v; is >> v; }
                    is >> n;
                    std::vector<int32_t> ids;
                    for (long i = 0; i < n && is; ++i) { long v; is >> v; ids.push_back((int32_t)v); }
                    const int sq = seq_of.count(id) ? seq_of[id] : 0;
                    seq_of.erase(id);
                    auto sp = samp_of.find(id);
                    const ops::SampleArgs sa = sp != samp_of.end() ? sp->second.first : ops::SampleArgs{};
                    const uint64_t sseed = sp != samp_of.end() ? sp->second.second : 0;
                    if (sp != samp_of.end()) samp_of.erase(sp);
                    bool bad = !is || (long)ids.size() != n || n < 1 || mx < 1;
                    for (int32_t v : ids) bad |= v < 0 || (v >= e.m.hp.vocab && !(v >= Engine::XID0 && e.xrow.count(v)));
                    if (bad) { sout("@@E " + id + " bad-request"); continue; }
                    if ((long)ids.size() + mx + 8 > e.cap) { sout("@@E " + id + " context " + std::to_string(e.cap)); continue; }
                    if (jobs[sq].live) { sout("@@E " + id + " busy"); continue; }
                    ++pic_gen;
                    Job &j = jobs[sq];
                    j = Job{};
                    j.live = true; j.rid = id; j.ids = ids; j.max_new = (int)mx; j.t0 = now_s();
                    e.bind(sq);
                    e.samp = sa; e.samp_seed = sseed;
                    const size_t h = (size_t)e.n_past;
                    const bool ext = h > 0 && ids.size() > h && convs[sq].size() >= h && std::equal(convs[sq].begin(), convs[sq].begin() + (long)h, ids.begin());
                    if (!ext) {
                        if (h > 0 || !convs[sq].empty()) sout("@@R " + id);
                        e.reset();
                        convs[sq].clear();
                    }
                    j.at = (size_t)e.n_past;
                    j.fed = ids.size() - j.at;
                }
                if (quit) break;
                bool writers = false;
                for (const Job &j : jobs) writers |= j.live && !j.reading;
                int rd = -1; // reading: one piece of one sequence's prompt (in turn)
                for (int k = 0; k < ns && rd < 0; ++k) {
                    const int sq = (rr + k) % ns;
                    if (jobs[sq].live && jobs[sq].reading) rd = sq;
                }
                if (rd >= 0) {
                    rr = (rd + 1) % ns;
                    Job &j = jobs[rd];
                    if (j.stop) finish(rd, "stop");
                    else {
                        e.bind(rd);
                        e.all_logits = false; e.host_logits = false;
                        const size_t n = std::min(j.ids.size() - j.at, (size_t)(writers ? std::min(chunk, e.T) : e.T));
                        e.step(j.ids.data() + j.at, (int)n);
                        j.at += n;
                        if (j.at == j.ids.size()) {
                            d.q.wait();
                            j.t1 = now_s();
                            char b[160];
                            std::snprintf(b, sizeof b, "@@P %s %zu %.3f", j.rid.c_str(), j.fed, j.t1 - j.t0);
                            sout(b);
                            j.reading = false;
                            const int32_t x = e.next_token();
                            j.out.push_back(x);
                            tok_line(j, x);
                            if (x == eos || (int)j.out.size() >= j.max_new || j.stop) finish(rd, x == eos ? "eos" : j.stop ? "stop" : "max");
                        }
                    }
                }
                std::vector<int> wr; // writing: one token of every writing sequence
                std::vector<int32_t> tk;
                for (int sq = 0; sq < ns; ++sq) {
                    Job &j = jobs[sq];
                    if (!j.live || j.reading) continue;
                    if (j.stop) { finish(sq, "stop"); continue; }
                    wr.push_back(sq);
                    tk.push_back(j.out.back());
                }
                if (!wr.empty()) {
                    const int n = (int)wr.size();
                    e.step_rows(tk.data(), wr.data(), n);
                    std::vector<int32_t> nx(n);
                    e.next_rows(wr.data(), n, nx.data());
                    for (int t = 0; t < n; ++t) {
                        Job &j = jobs[wr[t]];
                        j.out.push_back(nx[t]);
                        tok_line(j, nx[t]);
                        if (nx[t] == eos || (int)j.out.size() >= j.max_new) finish(wr[t], nx[t] == eos ? "eos" : "max");
                    }
                }
            }
            return 0;
        }
        for (int turn = 0;; ++turn) {
        if (serve) {
            std::vector<int32_t> ids;
            int max_new = 0;
            bool got = false, quit = false;
            for (std::string ln; !got && !quit;) {
                if (lines.empty()) pump(-1);
                if (lines.empty()) { if (in_eof) quit = true; continue; }
                ln = lines.front(); lines.pop_front();
                std::istringstream is(ln);
                std::string cmd, id;
                is >> cmd >> id;
                if (cmd == "Q") { quit = true; break; }
                if (cmd == "S" || cmd.empty()) continue;
                if (cmd == "W") {
                    std::string path;
                    is >> path;
                    try {
                        const double ts = now_s();
                        shard_back("a save");
                        const std::vector<int32_t> fed(conv.begin(), conv.begin() + e.n_past);
                        const size_t fb = save_cache(path, e, dr.get(), fed, model_id, pend_row);
                        char b[160];
                        std::snprintf(b, sizeof b, "@@W %s %zu %.3f", id.c_str(), fb, now_s() - ts);
                        sout(b);
                    } catch (std::exception &ex) { sout("@@E " + id + " save " + std::string(ex.what()).substr(0, 200)); }
                    continue;
                }
                if (cmd == "V") { handle_v(is, id); continue; } // V <id> <key> <width> <height> <rgb file>
                if (cmd == "P") { // P <id> <temperature> <top_p> <top_k> <min_p> <seed>: sampling for the G of that id
                    ops::SampleArgs a;
                    unsigned long long sd = 0;
                    is >> a.T >> a.topp >> a.topk >> a.minp >> sd;
                    if (!is || !(a.T >= 0.0f && a.T <= 100.0f) || !(a.topp > 0.0f && a.topp <= 1.0f) || a.topk < 0 ||
                        !(a.minp >= 0.0f && a.minp < 1.0f)) { sout("@@E " + id + " bad-sampling"); continue; }
                    samp_id = id; samp_next = a; samp_seed_next = sd;
                    continue;
                }
                if (cmd != "G") { sout("@@E - unknown-command"); continue; }
                long mx = 0, nstop = 0, n = 0;
                is >> mx >> nstop;
                for (long i = 0; i < nstop && is; ++i) { long v; is >> v; }
                is >> n;
                ids.clear();
                for (long i = 0; i < n && is; ++i) { long v; is >> v; ids.push_back((int32_t)v); }
                bool bad = !is || (long)ids.size() != n || n < 1 || mx < 1;
                for (int32_t v : ids) bad |= v < 0 || (v >= e.m.hp.vocab && !(v >= Engine::XID0 && e.xrow.count(v)));
                if (bad) { sout("@@E " + id + " bad-request"); continue; }
                if ((long)ids.size() + mx + 8 > e.cap) { sout("@@E " + id + " context " + std::to_string(e.cap)); continue; }
                rid = id; max_new = (int)mx; got = true;
                ++pic_gen;
                // sampling when a P line for this id came first, else the most likely token
                e.samp = samp_id == id ? samp_next : ops::SampleArgs{};
                e.samp_seed = samp_id == id ? samp_seed_next : 0;
                samp_id.clear();
            }
            if (!got) break;
            const size_t h = (size_t)e.n_past;
            const bool ext = h > 0 && ids.size() > h && std::equal(conv.begin(), conv.begin() + (long)h, ids.begin());
            bool restored = false;
            if (!ext) { // a new conversation: from the copy of a request's start (src/snapshot.hpp) when this one continues
                // from it, else from the longest saved prompt it starts with, else from position 0
                const double tz = now_s();
                std::string best;
                size_t best_n = 0;
                if (lib_dir) {
                    std::error_code ec;
                    for (const auto &f : std::filesystem::directory_iterator(lib_dir, ec)) {
                        if (f.path().extension() != ".inkc") continue;
                        try {
                            const std::vector<int32_t> ft = cache_tokens(f.path().string(), d.q, model_id);
                            if (ft.size() > best_n && ft.size() < ids.size() && std::equal(ft.begin(), ft.end(), ids.begin())) {
                                best = f.path().string(); best_n = ft.size();
                            }
                        } catch (std::exception &) {}
                    }
                }
                ngi = NgramIndex();
                // the copy unless a saved prompt holds 4,096 or more tokens past it (a load takes ~0.2-3 s, a copy ~ms)
                Snapshot *from = snap.fits(ids) ? &snap : (snapb.fits(ids) ? &snapb : nullptr);
                if (from && best_n < (size_t)from->pos + 4096) {
                    if (e.shard_S && from->pos < (int64_t)e.shard_S + e.m.hp.rel_extent) {
                        if (e.shard_copy) { e.shard_end(); std::fprintf(stderr, "[serve] shared copies dropped (a copy below them)\n"); }
                        else shard_back("a copy below them");
                    }
                    from->restore(e, dr.get());
                    d.q.wait();
                    conv = from->tok;
                    restored = true;
                    if (from == &snapb) snap.pos = -1; // (the positions past it are written again)
                    std::fprintf(stderr, "[serve] continuing from the %s copy at %ld tokens (%.3f s)\n",
                                 from == &snap ? "last-message" : "first-message", (long)from->pos, now_s() - tz);
                } else {
                    if (h > 0 || conv.size() > 0) sout("@@R " + rid);
                    snap.pos = -1;
                    snapb.pos = -1;
                    e.reset();
                    if (dr) dr->r_last = -1;
                    conv.clear();
                    if (!best.empty()) {
                        try {
                            std::vector<int32_t> ft;
                            load_cache(best, e, dr.get(), ids, model_id, nullptr, &ft);
                            conv = ft;
                            std::fprintf(stderr, "[serve] new conversation: %zu tokens loaded from %s in %.3f s\n", ft.size(), best.c_str(), now_s() - tz);
                        } catch (std::exception &ex) {
                            std::fprintf(stderr, "[serve] %s not loaded (%s): reading from position 0\n", best.c_str(), ex.what());
                            e.reset();
                            if (dr) dr->r_last = -1;
                        }
                    }
                }
            } else if (conv.size() > h && ids[h] != conv[h])
                ngi = NgramIndex(); // (n-grams through the old last token)
            if (e.shard_S && ids.size() - (size_t)e.n_past > (size_t)shard_feed)
                shard_back(("a read of " + std::to_string(ids.size() - (size_t)e.n_past) + " tokens").c_str());
            const std::vector<int32_t> rest(ids.begin() + e.n_past, ids.end());
            stop_req = false;
            n_gen = max_new;
            // the copy (src/snapshot.hpp) is taken at the start of the request's last message (<|message_user|>,
            // <|message_model|>, <|message_system|> or <|message_tool|>), so a regenerated answer, an edited last message
            // or another question after the same messages continues from it; the read goes in two parts around it
            // (steps of any size give the same values)
            size_t mark = (size_t)e.n_past;
            for (size_t i = ids.size(); i-- > (size_t)e.n_past + 1;)
                if (ids[i] >= 200000 && ids[i] <= 200003) { mark = i; break; }
            // the first message after the system messages (<|message_user|>, <|message_model|> or <|message_tool|>)
            size_t markb = ids.size();
            for (size_t i = 0; i < ids.size(); ++i)
                if (ids[i] == 200000 || ids[i] == 200001 || ids[i] == 200003) { markb = i; break; }
            t0 = now_s();
            bool took_b = false;
            if (snapb.ok && markb >= (size_t)e.n_past && markb <= mark && markb > 0) {
                if (markb > (size_t)e.n_past) feedx(std::vector<int32_t>(ids.begin() + e.n_past, ids.begin() + (long)markb));
                if (!(restored && (size_t)snapb.pos == markb)) snapb.take(e, dr.get(), ids);
                took_b = true;
            }
            if (mark > (size_t)e.n_past) feedx(std::vector<int32_t>(ids.begin() + e.n_past, ids.begin() + (long)mark));
            // the conversation's only message is the last one (a document and its question in one message): the
            // first-message copy holds its start, so the last-message copy goes before the prompt's last token instead,
            // when that message is long (1,024 tokens or more): a follow-up whose answer part differs from ours (an
            // answer cut at its length limit, the client's own text) or a regenerated answer then reads only the rest
            size_t at = mark;
            if (took_b && mark == markb) {
                at = ids.size() - 1 >= mark + 1024 ? ids.size() - 1 : mark;
                if (at > mark) feedx(std::vector<int32_t>(ids.begin() + (long)mark, ids.begin() + (long)at));
            }
            if (took_b && at == markb) snap.pos = -1; // (the same state: the first-message copy serves)
            else if (!(restored && (size_t)snap.pos == at)) snap.take(e, dr.get(), ids); // (queued before the next feed)
            feedx(std::vector<int32_t>(ids.begin() + (long)at, ids.end()));
            if (lk_serve) ngi.extend(ids, (int)ids.size()); // (on the host while the card reads)
            d.q.wait();
            t1 = now_s();
            pend_row = e.n_logit_rows - 1;
            conv = ids;
            fed_n = rest.size();
            {
                char b[160];
                std::snprintf(b, sizeof b, "@@P %s %zu %.3f", rid.c_str(), fed_n, t1 - t0);
                sout(b);
            }
            e.prof.collect(); e.prof.rows.clear(); e.prof.busy_ms = e.prof.span_ms = 0; e.prof.steps = 0;
        } else if (turn > 0) { // the previous answer's last token (chosen, not yet fed) and the next turn, as a prompt step
            std::vector<int32_t> tt(1, conv.back());
            tt.insert(tt.end(), turns[turn - 1].begin(), turns[turn - 1].end());
            n_gen = n_gen0;
            t0 = now_s();
            e.feed(tt);
            d.q.wait();
            t1 = now_s();
            conv.insert(conv.end(), turns[turn - 1].begin(), turns[turn - 1].end());
            fed_n = tt.size();
            e.prof.collect(); e.prof.rows.clear(); e.prof.busy_ms = e.prof.span_ms = 0; e.prof.steps = 0;
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
            std::vector<int32_t> hist = conv; // the conversation, then every chosen token
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
            emit(out, 0);
            long checks = 0, plain = 0, guessed = 0, kept = 0;
            // INK_SPEC_ADAPT (default 1 with the drafter): draft INK_SPEC guesses, then check the count k (0..INK_SPEC)
            // with the most expected tokens per ms: keep chance of guess j from the drafter's probability (tenths;
            // measured 2026-11-23 on code, haiku and a 3K prompt: 0.9+ kept 283 of 304, 0.8+ 35 of 57, ...), step costs
            // INK_SPEC_COST (ms, steps of 1..8 tokens at a short context) plus, per position of context, INK_SPEC_KV
            // (ms; the cache read of a step) and INK_SPEC_KVX (ms, each further token's attention), so long contexts
            // check more guesses (2026-11-24, card 3 profile at 200K: 1 token 12.5 ms of attention, 4 tokens 14.8)
            const bool adapt = dr && (!std::getenv("INK_SPEC_ADAPT") || std::atoi(std::getenv("INK_SPEC_ADAPT")));
            float qk[10];
            for (int b = 0; b < 10; ++b) qk[b] = Drafter::QK.v[b];
            // INK_SPEC_QLEARN=0 disables the default calibration at >=131K context: update each probability bucket
            // from this request's checked guesses, with four prior observations. Short contexts keep the static table.
            const bool qlearn = adapt && (!std::getenv("INK_SPEC_QLEARN") || std::atoi(std::getenv("INK_SPEC_QLEARN")));
            double cost0[8] = {11.4, 14.9, 17.4, 20.4, 23.9, 27.5, 30.5, 33.1}, cost[8]; // (5-8: card 3 2026-11-24 + 4 tokens)
            if (const char *ce = std::getenv("INK_SPEC_COST"))
                std::sscanf(ce, "%lf,%lf,%lf,%lf,%lf,%lf,%lf,%lf", &cost0[0], &cost0[1], &cost0[2], &cost0[3], &cost0[4], &cost0[5], &cost0[6],
                            &cost0[7]);
            const double kv1 = std::getenv("INK_SPEC_KV") ? std::atof(std::getenv("INK_SPEC_KV")) : 6.2e-5,
                         kvx = std::getenv("INK_SPEC_KVX") ? std::atof(std::getenv("INK_SPEC_KVX")) : 3.85e-6;
            long kchose[8] = {};
            // INK_SPEC_LOOKUP (default 1 with the drafter): also guess by prompt lookup (the tokens after the most recent
            // earlier occurrence of the last 4, 3 or 2 tokens) and check whichever of the drafter's guesses, lookup's,
            // or the drafter's agreeing prefix continued by lookup's promises the most tokens per ms (the count rule
            // above). Lookup's keep chance per match length is learned from every round whether or not its guesses were
            // checked: the round's tokens y[0..a] are the model's, so lookup's guesses are scored against them (kept up
            // to the first difference); counts decay by INK_SPEC_LK_DECAY (default 0.9) a round, from 1 kept of 4.
            // Without the drafter (INK_SPEC alone) lookup's guesses are checked by the same rule against a plain step
            // (INK_SPEC_LOOKUP=0 there: every lookup match checked, as before).
            const bool lk = (!dr || adapt) && (!std::getenv("INK_SPEC_LOOKUP") || std::atoi(std::getenv("INK_SPEC_LOOKUP")));
            const double lk_decay = std::getenv("INK_SPEC_LK_DECAY") ? std::atof(std::getenv("INK_SPEC_LK_DECAY")) : 0.9;
            double lk_n[5] = {4, 4, 4, 4, 4}, lk_k[5] = {1, 1, 1, 1, 1};
            std::vector<int32_t> gl_round; int lnn_round = 0; // this round's lookup guesses (scored after the check)
            const float lk_skip = std::getenv("INK_SPEC_LK_SKIP") ? (float)std::atof(std::getenv("INK_SPEC_LK_SKIP")) : 0.8f;
            long lk_skipped = 0;
            long lk_rounds[3] = {}; // rounds that checked the drafter's guesses, lookup's, a merge
            long lk_used = 0, lk_kept = 0;
            long pb_n[10] = {}, pb_k[10] = {}; // guesses and kept guesses by the drafter's probability (tenths), first rejection ends a check
            double tdraft = 0;
            // INK_DRAFT_LOG=<file> with INK_ORACLE=<ids of the plain run>: draft 7 guesses each round and log their
            // probabilities and how many lead the plain text, then check as usual (study of longer checks)
            std::vector<int> oracle;
            FILE *dlog = nullptr, *dlog2 = nullptr;
            if (dr && std::getenv("INK_DRAFT_LOG") && std::getenv("INK_ORACLE")) {
                std::ifstream of(std::getenv("INK_ORACLE"));
                std::string w;
                of >> w; // "ids:"
                for (int v; of >> v;) oracle.push_back(v);
                dlog = std::fopen(std::getenv("INK_DRAFT_LOG"), "w");
                if (const char *l2 = std::getenv("INK_DRAFT_LOG2")) dlog2 = std::fopen(l2, "w");
                dr->stop_thr = 0.0f; // every guess computed for the study
            }
            while (x != e.m.hp.eos && (int)out.size() < n_gen && !(serve && poll_stop())) {
                if (shard_serve && (int)out.size() >= shard_after) shard_try();
                std::vector<int32_t> g;
                const int H = (int)hist.size();
                const int room = n_gen - (int)out.size() - 1; // guesses past the end would never be shown
                if (adapt || lk) {
                    for (int k = 0; k < 8; ++k) // (a check of more rows than the engine's dec_rows reads the cache again)
                        cost[k] = cost0[k] + e.n_past * (kv1 * ((k + e.dec_rows) / e.dec_rows) + kvx * k);
                }
                if (adapt) {
                    // the drafter's slots 4-7 are worth reading only if a 4th guess could be checked: with r the 5-token
                    // step's extra cost over 4 tokens, that needs the chain c of guesses 1-3 above r / (0.93 - 3 r)
                    // (0.93 c > (1 + 3 c) r: the 4th guess adds at most 0.93 c expected tokens, the 3 before at least c each)
                    const double r = cost[4] / cost[3] - 1.0, den = 0.93 - 3.0 * r;
                    if (!dlog) dr->stop_hi = den > 0.0 ? (float)(r / den) : 1.0f;
                }
                // this round's lookup guesses (INK_SPEC_LOOKUP), before drafting: with a 4-token match, at least 4 guesses
                // and a learned keep chance of INK_SPEC_LK_SKIP (default 0.8) or more, the drafter is not run this round
                // (its context rows come from every step, not from draft(), so a round without it changes nothing)
                std::vector<int32_t> gl;
                int lnn = 0;
                float ql = 0.0f;
                bool skipd = false;
                if (lk) {
                    for (int nn = 4; nn >= 2 && gl.empty(); --nn) {
                        const int st = ngi.find(hist, H, nn);
                        if (st < 0) continue;
                        lnn = nn;
                        for (int j = st + nn; j < H && (int)gl.size() < std::min(spec, room); ++j) gl.push_back(hist[j]);
                    }
                    ql = lnn ? (float)(lk_k[lnn] / lk_n[lnn]) : 0.0f;
                    gl_round = gl; lnn_round = lnn;
                    skipd = dr && !dlog && lnn == 4 && (int)gl.size() >= 4 && ql >= lk_skip;
                    if (skipd) ++lk_skipped;
                }
                if (dr) {
                    if (room > 0 && !skipd) {
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
                                if (dlog2) { // INK_DRAFT_LOG2: output index, lead count, the guesses, their probabilities
                                    std::fprintf(dlog2, "%d %d |", o0, m);
                                    for (int j = 0; j < nd; ++j) std::fprintf(dlog2, " %d", g[j]);
                                    std::fprintf(dlog2, " |");
                                    for (int j = 0; j < nd; ++j) std::fprintf(dlog2, " %.4f", dr->probs[j]);
                                    std::fprintf(dlog2, "\n");
                                }
                                g.resize(std::min(spec, (int)g.size()));
                            }
                        } else
                            g = dr->draft(e.n_past, xdev, std::min(spec, room), x);
                        tdraft += now_s() - td;
                    }
                } else if (!lk)
                    for (int nn = std::min(maxn, H - 1); nn >= minn && g.empty(); --nn)
                        for (int st = H - nn - 1; st >= 0; --st) {
                            if (!std::equal(hist.begin() + st, hist.begin() + st + nn, hist.end() - nn)) continue;
                            for (int j = st + nn; j < H && (int)g.size() < spec; ++j) g.push_back(hist[j]);
                            break;
                        }
                if ((int)g.size() > room) g.resize(std::max(0, room));
                int lsrc = 0; // guesses from lookup start at index lsrc of g (lsrc = g.size(): none)
                std::vector<float> gch; // the chosen guesses' keep chances
                if (lk) {
                    lsrc = (int)g.size();
                    // a candidate's best count and its tokens per ms (the rule above)
                    auto rate = [&](const std::vector<float> &ch, int &bk) {
                        double best = 1.0 / cost[0], ex = 1.0, pr = 1.0;
                        bk = 0;
                        for (int j = 0; j < (int)ch.size(); ++j) {
                            pr *= ch[j]; ex += pr;
                            if (ex / cost[j + 1] > best) { best = ex / cost[j + 1]; bk = j + 1; }
                        }
                        return best;
                    };
                    std::vector<float> cd(g.size());
                    for (size_t j = 0; j < g.size(); ++j) cd[j] = qk[std::min(9, (int)(dr->probs[j] * 10.0f))];
                    int bd = 0, bl = 0;
                    const double rd = rate(cd, bd);
                    double rl = -1;
                    std::vector<float> cl;
                    int L = 0; // the drafter's guesses that lookup's agree with
                    if (!gl.empty()) {
                        while (L < (int)g.size() && L < (int)gl.size() && g[L] == gl[L]) ++L;
                        // lookup's keep chances: where both guess the same token, the better of the two; at the first
                        // difference at most 1 - the drafter's chance (the two cannot both be kept); after it, ql
                        cl.resize(gl.size());
                        for (int j = 0; j < (int)gl.size(); ++j)
                            cl[j] = j < L ? std::max(cd[j], ql) : j == L && L < (int)g.size() ? std::min(ql, 1.0f - cd[j]) : ql;
                        rl = rate(cl, bl);
                    }
                    if (rl > rd) { // lookup's guesses (the drafter's first L among them)
                        g = gl; g.resize(bl); gch.assign(cl.begin(), cl.begin() + bl); lsrc = std::min(L, bl);
                        ++lk_rounds[L > 0 ? 2 : 1];
                    } else {
                        g.resize(bd); gch.assign(cd.begin(), cd.begin() + bd); lsrc = bd; ++lk_rounds[0];
                    }
                    ++kchose[g.size()];
                } else if (adapt && !g.empty()) {
                    double best = 1.0 / cost[0], ex = 1.0, pr = 1.0;
                    int bk = 0;
                    for (int j = 0; j < (int)g.size(); ++j) {
                        pr *= qk[std::min(9, (int)(dr->probs[j] * 10.0f))];
                        ex += pr;
                        if (ex / cost[j + 1] > best) { best = ex / cost[j + 1]; bk = j + 1; }
                    }
                    g.resize(bk);
                    ++kchose[bk];
                    lsrc = bk;
                }
                if (g.empty()) {
                    e.step(&x, 1);
                    if (gen_out.is_open()) { d.q.wait(); save_rows(1); }
                    x = e.next_token();
                    if (lk && lnn_round && !gl_round.empty()) { // lookup's first guess against the model's token
                        for (int n = 2; n <= 4; ++n) { lk_n[n] *= lk_decay; lk_k[n] *= lk_decay; }
                        lk_n[lnn_round] += 1;
                        if (gl_round[0] == x) lk_k[lnn_round] += 1;
                    }
                    xdev = e.ids;
                    out.push_back(x); hist.push_back(x);
                    pend_row = e.n_logit_rows - 1;
                    emit(out, out.size() - 1);
                    ++plain;
                    continue;
                }
                std::vector<int32_t> tk(1, x);
                tk.insert(tk.end(), g.begin(), g.end());
                const std::vector<int32_t> y = e.check(tk.data(), (int)tk.size());
                int a = 0; // guesses that match the model's choices
                while (a < (int)g.size() && g[a] == y[a] && y[a] != e.m.hp.eos) ++a;
                if (!dr && lk)
                    for (int j = 0; j <= a && j < (int)g.size(); ++j) { ++lk_used; if (j < a) ++lk_kept; }
                if (dr)
                    for (int j = 0; j <= a && j < (int)g.size(); ++j) { // guesses the check decided (up to the first rejection)
                        if (lk && j >= lsrc) { // a lookup guess
                            ++lk_used;
                            if (j < a) ++lk_kept;
                            continue;
                        }
                        const int b = std::min(9, (int)(dr->probs[j] * 10.0f));
                        ++pb_n[b];
                        if (j < a) ++pb_k[b];
                        if (qlearn && e.n_past >= 131072) qk[b] = (float)((pb_k[b] + 4.0 * Drafter::QK.v[b]) / (pb_n[b] + 4.0));
                    }
                e.accept(a + 1);
                if (lk && lnn_round) { // lookup's guesses of this round against the model's tokens y[0..a]
                    for (int n = 2; n <= 4; ++n) { lk_n[n] *= lk_decay; lk_k[n] *= lk_decay; }
                    for (int j = 0; j < (int)gl_round.size() && j <= a; ++j) {
                        lk_n[lnn_round] += 1;
                        if (gl_round[j] != y[j]) break;
                        lk_k[lnn_round] += 1;
                    }
                }
                if (dr) dr->r_last = a; // r(P0') = the row of the last kept token
                xdev = e.cids + a;
                if (gen_out.is_open()) save_rows(a + 1);
                const size_t o0 = out.size();
                for (int r = 0; r <= a && (int)out.size() < n_gen; ++r) { out.push_back(y[r]); hist.push_back(y[r]); }
                pend_row = a;
                emit(out, o0);
                x = out.back();
                ++checks; guessed += (long)g.size(); kept += a;
                e.prof.collect(); // one profile step per round (INK_PROF)
            }
            std::fprintf(stderr, "[spec] %ld checks (%ld guesses, %ld kept: %.1f %%), %ld plain steps; %.2f tokens per check; drafting %.3f s\n",
                         checks, guessed, kept, guessed ? 100.0 * kept / guessed : 0.0, plain, checks ? 1.0 + (double)kept / checks : 0.0, tdraft);
            if (lk)
                std::fprintf(stderr, "[spec] lookup: rounds checking the drafter's (or no) / lookup's / merged guesses %ld / %ld / %ld (%ld without drafting); lookup guesses kept %ld of %ld\n",
                             lk_rounds[0], lk_rounds[1], lk_rounds[2], lk_skipped, lk_kept, lk_used);
            if (dr) {
                if (adapt) {
                    std::fprintf(stderr, "[spec] guesses checked per round:");
                    for (int k = 0; k <= std::min(7, spec); ++k) std::fprintf(stderr, " %d x%ld", k, kchose[k]);
                    std::fprintf(stderr, "\n");
                }
                std::fprintf(stderr, "[spec] kept by the drafter's probability:");
                for (int b = 0; b < 10; ++b) if (pb_n[b]) std::fprintf(stderr, " 0.%d+ %ld/%ld", b, pb_k[b], pb_n[b]);
                std::fprintf(stderr, "\n");
                if (qlearn && e.n_past >= 131072) {
                    std::fprintf(stderr, "[spec] calibrated keep chances:");
                    for (int b = 0; b < 10; ++b) if (pb_n[b]) std::fprintf(stderr, " 0.%d+ %.3f", b, qk[b]);
                    std::fprintf(stderr, "\n");
                }
            }
            if (dlog) std::fclose(dlog);
            if (dlog2) std::fclose(dlog2);
            req_rounds = checks + plain; req_guessed = guessed; req_kept = kept;
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
            pend_row = e.n_logit_rows - 1;
            emit(out, out.size() - 1);
            req_rounds = (long)out.size();
            if (b == e.m.hp.eos) break;
            if (i + 1 == n_gen) break;
            if (serve && poll_stop()) break;
            // INK_SHARD_END=<k>: the shared caches back as they were after k tokens (Engine::shard_end; a test of the reverse)
            static const int shard_end_at = std::getenv("INK_SHARD_END") ? std::atoi(std::getenv("INK_SHARD_END")) : -1;
            if (shard_end_at == i + 1 && e.shard_S) {
                const double ts = now_s();
                e.shard_end();
                std::fprintf(stderr, "[ink] shard: %d tokens written in %.3f s (%.2f tok/s) with the caches shared; back on their own engines in %.3f s\n",
                             i + 1, ts - t1, (i + 1) / (ts - t1), now_s() - ts);
            }
            if (shard_serve && i + 1 >= shard_after) shard_try();
            e.all_logits = false;
            if (host_argmax) e.feed({b});
            else e.step_next();
            e.prof.collect();
        }
        double t2 = now_s();
        if (serve) {
            const char *why = !out.empty() && out.back() == e.m.hp.eos ? "eos" : stop_req ? "stop" : "max";
            char b[256];
            std::snprintf(b, sizeof b, "@@D %s %s %zu %zu %.3f %.3f %ld %ld %ld %d", rid.c_str(), why, fed_n, out.size(), t1 - t0, t2 - t1,
                          req_rounds, req_guessed, req_kept, e.n_past + 1);
            sout(b);
            std::fprintf(stderr, "[serve] %s: read %zu tokens in %.3f s, answered %zu in %.3f s (%.2f tok/s), %s, context %d\n", rid.c_str(),
                         fed_n, t1 - t0, out.size(), t2 - t1, out.size() > 1 ? (out.size() - 1) / (t2 - t1) : 0.0, why, e.n_past + 1);
            conv.insert(conv.end(), out.begin(), out.end());
            req_rounds = req_guessed = req_kept = 0;
            e.prof.rows.clear(); e.prof.busy_ms = e.prof.span_ms = 0; e.prof.steps = 0;
            continue;
        }
        std::printf("ids:");
        for (int t : out) std::printf(" %d", t);
        std::printf("\n");
        std::fflush(stdout);
        if (turn > 0) std::fprintf(stderr, "[ink] turn %d (from position %zu): ", turn, conv.size() - turns[turn - 1].size() - 1);
        else std::fprintf(stderr, "[ink] ");
        std::fprintf(stderr, "prompt %zu tokens %.3f s (%.1f tok/s); generated %zu in %.3f s (%.2f tok/s)\n", fed_n,
                     t1 - t0, fed_n ? fed_n / (t1 - t0) : 0.0, out.size(), t2 - t1, out.size() > 1 ? (out.size() - 1) / (t2 - t1) : 0.0);
        e.prof.report(stderr);
        conv.insert(conv.end(), out.begin(), out.end());
        if (turn >= (int)turns.size() || out.empty()) break;
        e.prof.rows.clear(); e.prof.busy_ms = e.prof.span_ms = 0; e.prof.steps = 0;
        } // turns
        std::fprintf(stderr, "[ink] at the end: driver reports %.2f GiB free (card memory in use %.2f GiB)\n", d.free_mem() / 1073741824.0,
                     d.allocated / 1073741824.0);
    } catch (std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
