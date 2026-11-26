// ink_pipe: Inkling-2-Mini split over two engines: applications 0 .. S - 1 and S .. 47 (INK_SPLIT=S, default 24: four of
// the eight full-attention caches on each), on one card or two. Each engine holds only the weights of the physical
// layers it runs (Engine::unused_tensor); after each step the first engine's rows that the second reads (the current
// rows, the blocks, the previous pass's bank and their saved mix scores: Engine::carry_slots) go through host memory
// (Engine::carry_out / carry_in; no card-to-card reads). Every application computes what it computes in one engine, so
// the logits are ink_run's bits.
//   Greedy text like ink_run's plain loop: "ids: ..." on stdout. INK_SAVE_GEN=<file>: every step's last logits row (the
// prompt's, then each generated token's) as ink_run writes it, so the gate's baselines compare as they are.
//   Two cards: the prompt's steps run in a pipeline (the first card reads step s + 1 while the second reads step s), a
// host thread per card; INK_PIPE=0: one after the other. INK_UBATCH: the step size (default as ink_run's).
//   ink_pipe <model.gguf> <cardA> <cardB> <tokens.txt> [n_gen] [ctx]
#include "../src/engine.hpp"
#include <condition_variable>
#include <cstring>
#include <exception>
#include <fstream>
#include <memory>
#include <mutex>
#include <thread>

using namespace ink;

int main(int argc, char **argv) {
    if (argc < 5) { std::fprintf(stderr, "usage: ink_pipe <model.gguf> <cardA> <cardB> <tokens.txt> [n_gen] [ctx]\n"); return 2; }
    try {
        GGUF g(argv[1]);
        const int ca = std::atoi(argv[2]), cb = std::atoi(argv[3]);
        std::vector<int32_t> tok;
        {
            std::ifstream f(argv[4]);
            long v;
            while (f >> v) tok.push_back((int32_t)v);
            if (tok.empty()) throw std::runtime_error(std::string("no token ids in ") + argv[4]);
        }
        const int n_gen = argc > 5 ? std::atoi(argv[5]) : 0;
        const int ctx = argc > 6 ? std::atoi(argv[6]) : (int)tok.size() + n_gen + 16;
        const bool ub_fixed = std::getenv("INK_UBATCH") != nullptr;
        int ub = ub_fixed ? std::atoi(std::getenv("INK_UBATCH"))
                          : ctx <= 65536 ? 8192 : ctx <= 131072 ? 4096 : ctx <= 300000 ? 1024 : 512;
        if (!ub_fixed) {
            int need = 512;
            while (need < ctx && need < ub) need *= 2;
            ub = std::min(ub, need);
        }
        HParams hp;
        hp.load(g);
        const int S = std::getenv("INK_SPLIT") ? std::atoi(std::getenv("INK_SPLIT")) : 24;
        if (S < 1 || S >= hp.n_app) throw std::runtime_error("INK_SPLIT: 1 to " + std::to_string(hp.n_app - 1));
        if (!dec_on()) throw std::runtime_error("ink_pipe: INK_DEC=0 is not supported");

        std::unique_ptr<Device> da = std::make_unique<Device>(ca), dbo;
        if (cb != ca) dbo = std::make_unique<Device>(cb);
        Device &db = cb != ca ? *dbo : *da;
        const auto host_t = [](const Tensor &t) { return t.name == "token_embd.weight"; }; // (the host table, Engine::embed)
        Weights wa, wb;
        std::map<std::string, WView> va, vb;
        const auto load = [&](Device &d, Weights &w, std::map<std::string, WView> &v, int lo, int hi) {
            const auto own = [&, lo, hi](const Tensor &t) { return host_t(t) || Engine::unused_tensor(hp, lo, hi, t); };
            w.upload(d, g, true, [&](const Tensor &t) { return dec_target(t) || q6k_target(t) || own(t); });
            v = planarize(d, g, w, true, own);
        };
        // INK_PIPE_ONLY=A or B: that engine alone on cardA (card memory beside the context, the time of its steps; B's
        // input rows are zeros, so only its time means anything)
        const char *only = std::getenv("INK_PIPE_ONLY");
        const bool onlyA = only && only[0] == 'A', onlyB = only && only[0] == 'B';
        const double t0 = now_s();
        std::unique_ptr<Engine> pa, pb;
        if (!onlyB) {
            load(*da, wa, va, 0, S);
            pa = std::make_unique<Engine>(*da, g, wa, ctx, ub, false, &va, 0, S);
            std::fprintf(stderr, "[pipe] card %d: applications 0-%d, card memory in use %.2f GiB (driver: %.2f GiB free)\n", ca, S - 1,
                         da->allocated / 1073741824.0, da->free_mem() / 1073741824.0);
        }
        if (!onlyA) {
            Device &d2 = onlyB ? *da : db;
            load(d2, wb, vb, S, hp.n_app);
            pb = std::make_unique<Engine>(d2, g, wb, ctx, ub, false, &vb, S, hp.n_app);
            std::fprintf(stderr, "[pipe] card %d: applications %d-%d, card memory in use %.2f GiB (driver: %.2f GiB free)\n", onlyB ? ca : cb, S,
                         hp.n_app - 1, d2.allocated / 1073741824.0, d2.free_mem() / 1073741824.0);
        }
        std::fprintf(stderr, "[pipe] loaded in %.1f s; context %d, steps of %d\n", now_s() - t0, ctx, ub);
        for (Device *d : {da.get(), dbo.get()}) {
            if (!d) continue;
            auto kb = sycl::get_kernel_bundle<sycl::bundle_state::executable>(d->ctx, {d->dev});
            (void)kb;
        }

        // the prompt's steps as Engine::feed takes them (a short rest spread over steps of one size)
        std::vector<std::pair<size_t, int>> steps;
        {
            const size_t N = tok.size(), T = (size_t)ub, ns = (N + T - 1) / T;
            size_t s = T;
            if (ns > 1 && N - (ns - 1) * T < 512) s = std::min(T, ((N + ns - 1) / ns + 15) / 16 * 16);
            for (size_t p = 0; p < N; p += s) steps.push_back({p, (int)std::min(s, N - p)});
        }
        std::vector<float> hb[2];
        for (auto &b : hb) b.resize((pa ? *pa : *pb).carry_floats(ub));
        if (only) { // one engine's steps alone, each timed on the card
            Engine &e = pa ? *pa : *pb;
            const double ts = now_s();
            for (auto [p, n] : steps) {
                const double t1 = now_s();
                if (pa) e.step(tok.data() + p, n);
                else { e.carry_in(hb[0].data(), n); e.step(nullptr, n); }
                e.d.q.wait();
                if (std::getenv("INK_PIPE_STEPS")) std::fprintf(stderr, "[pipe] step at %zu, %d tokens: %.3f s\n", p, n, now_s() - t1);
            }
            const double te = now_s() - ts;
            std::fprintf(stderr, "[pipe] %s alone: prompt %zu tokens %.3f s (%.1f tok/s) in %zu steps\n", pa ? "A" : "B", tok.size(), te,
                         tok.size() / te, steps.size());
            return 0;
        }
        Engine &A = *pa, &B = *pb;
        const double tp = now_s();
        const bool pipe = cb != ca && (!std::getenv("INK_PIPE") || std::atoi(std::getenv("INK_PIPE")));
        if (!pipe) {
            for (auto [p, n] : steps) {
                A.step(tok.data() + p, n);
                A.carry_out(hb[0].data(), n);
                B.carry_in(hb[0].data(), n);
                B.step(nullptr, n);
            }
        } else { // the first card runs up to two steps ahead (two host buffers)
            std::mutex mu;
            std::condition_variable cv;
            size_t made = 0, taken = 0;
            std::exception_ptr err;
            std::thread th([&] {
                try {
                    for (size_t s = 0; s < steps.size(); ++s) {
                        {
                            std::unique_lock<std::mutex> lk(mu);
                            cv.wait(lk, [&] { return s < taken + 2 || err; });
                            if (err) return;
                        }
                        A.step(tok.data() + steps[s].first, steps[s].second);
                        A.carry_out(hb[s % 2].data(), steps[s].second);
                        std::lock_guard<std::mutex> lk(mu);
                        made = s + 1;
                        cv.notify_all();
                    }
                } catch (...) {
                    std::lock_guard<std::mutex> lk(mu);
                    err = std::current_exception();
                    cv.notify_all();
                }
            });
            try {
                for (size_t s = 0; s < steps.size(); ++s) {
                    {
                        std::unique_lock<std::mutex> lk(mu);
                        cv.wait(lk, [&] { return made > s || err; });
                        if (err) break;
                    }
                    B.carry_in(hb[s % 2].data(), steps[s].second);
                    {
                        std::lock_guard<std::mutex> lk(mu);
                        taken = s + 1;
                        cv.notify_all();
                    }
                    B.step(nullptr, steps[s].second);
                }
            } catch (...) {
                std::lock_guard<std::mutex> lk(mu);
                if (!err) err = std::current_exception();
                cv.notify_all();
            }
            th.join();
            if (err) std::rethrow_exception(err);
        }
        db.q.wait();
        const double tpe = now_s() - tp;
        std::fprintf(stderr, "[pipe] prompt %zu tokens %.3f s (%.1f tok/s) in %zu steps%s\n", tok.size(), tpe, tok.size() / tpe, steps.size(),
                     pipe ? ", pipelined" : "");

        std::ofstream gen_out;
        std::vector<float> row(hp.vocab);
        if (const char *gp = std::getenv("INK_SAVE_GEN")) gen_out.open(gp, std::ios::binary);
        std::vector<int> out;
        const double tg = now_s();
        for (int i = 0; i < n_gen; ++i) {
            if (gen_out.is_open()) {
                db.q.wait();
                db.get(row.data(), B.lg + (size_t)(B.n_logit_rows - 1) * hp.vocab_padded, row.size());
                gen_out.write((const char *)row.data(), (std::streamsize)row.size() * 4);
            }
            int32_t b = B.next_token();
            out.push_back(b);
            if (b == hp.eos || i + 1 == n_gen) break;
            A.step(&b, 1);
            A.carry_out(hb[0].data(), 1);
            B.carry_in(hb[0].data(), 1);
            B.step(nullptr, 1);
        }
        const double tge = now_s() - tg;
        if (!out.empty())
            std::fprintf(stderr, "[pipe] generated %zu in %.3f s (%.2f tok/s)\n", out.size(), tge, out.size() > 1 ? (out.size() - 1) / tge : 0.0);
        std::printf("ids:");
        for (int x : out) std::printf(" %d", x);
        std::printf("\n");
    } catch (const std::exception &ex) {
        std::fprintf(stderr, "ink_pipe: %s\n", ex.what());
        return 1;
    }
    return 0;
}
