// own_run_v41: decode DeepSeek-V4.1-Flash on B70 cards from a CPU reference
// state dump (cpu_run_v41 argv[7]: post-prefill rings, compress/index caches,
// group states, token history, first token).
//
//   own_run_v41 state.bin ndecode out_ids.txt [max_ctx]
//   OWN_PROMPT=ids.txt own_run_v41 - ndecode out_ids.txt [max_ctx]
//
// With OWN_PROMPT the cards read the prompt themselves, one token per decode
// step from an empty state (causal model: identical to a batched prompt
// pass), and no CPU reference state is needed. Prompt reading then runs at
// the decode rate.
//
// Environment:
//   OWN_LAYERS=a:b     run only layers [a,b) (default 0:40)
//   OWN_HEAD=0|1       output norm + logits + argmax (default: 1 iff b == 40)
//   OWN_DEVS=i,j,...   SYCL gpu indices for the cards this range needs
//   OWN_PROMPT=ids.txt read this prompt on the cards instead of loading a state dump
//   OWN_EOS=id         stop when this token is generated (default 1; -1 = never)
//   OWN_FORCED=ids.txt teacher-force these tokens (required without the head)
//   OWN_INJECT=cpu.trc reference trace: streams/pre-mix (and rows published by
//                      sources outside the range) enter at layer a
//   OWN_TRACE=dev.trc  write the device trace (OWN_TRACE_STEPS, default 2)
//   OWN_HOST_FLOOR_MIB abort the load below this MemAvailable (default 3072)
//   OWN_HC_LEGACY=1    old FFN pre-mix threading (A/B only)
//   OWN_LOAD_ONLY=1    stop after the upload (load/memory test)
//   OWN_GENERIC_KERNELS=1 runtime-type gemv kernels instead of one kernel per weight format
//   OWN_PACKED=0|1     packed device rows + packed kernels where available (default 1; f32 build)
//   OWN_KEEP_WARM=0|1|2 after each layer, ping the other cards with a tiny kernel so they stay at
//                      full clock (default 1; 2 = next card only; 0 = off, about 40 % slower)
//   OWN_PACE=0|1|2     extra queue waits (per layer / per operator group); no measured benefit
//   OWN_H2D_WAIT=0|1   wait after host->card state uploads (default 1; no measured difference)
//   OWN_PROF=1         per-op-group time shares (adds a queue wait at every mark)
//   OWN_DEBUG=1        progress output
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <map>
#include <sstream>
#include <sys/mman.h>
#include <sys/stat.h>
#include <tuple>
#include <unistd.h>
#include <vector>
#include "stage2/packet3/backend/backend_sycl_v41.hpp"

static void die(const std::string &m) { std::fprintf(stderr, "fatal: %s\n", m.c_str()); exit(1); }
static double now() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

// GGUF single-tensor table locator (from the validated CPU runner).
static const uint8_t *map_engram(const char *path, int li) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) { perror("open engram"); exit(1); }
    struct stat st; fstat(fd, &st);
    auto rd = [&](void *dst, size_t n) { if (read(fd, dst, n) != (ssize_t)n) die("engram hdr"); };
    uint32_t magic, ver; uint64_t nt, nkv;
    rd(&magic, 4); rd(&ver, 4); rd(&nt, 8); rd(&nkv, 8);
    if (magic != 0x46554747) die("engram magic");
    auto skip_str = [&] { uint64_t n; rd(&n, 8); lseek(fd, n, SEEK_CUR); };
    for (uint64_t i = 0; i < nkv; ++i) {
        skip_str();
        uint32_t vt; rd(&vt, 4);
        switch (vt) {
        case 0: case 1: case 7: lseek(fd, 1, SEEK_CUR); break;
        case 2: case 3: lseek(fd, 2, SEEK_CUR); break;
        case 4: case 5: case 6: lseek(fd, 4, SEEK_CUR); break;
        case 8: skip_str(); break;
        case 10: case 11: case 12: lseek(fd, 8, SEEK_CUR); break;
        case 9: {
            uint32_t et; uint64_t n; rd(&et, 4); rd(&n, 8);
            if (et == 8) for (uint64_t j = 0; j < n; ++j) skip_str();
            else lseek(fd, n * (et <= 1 || et == 7 ? 1 : (et <= 3 ? 2 : (et >= 10 ? 8 : 4))), SEEK_CUR);
            break;
        }
        default: die("engram kv type");
        }
    }
    std::map<std::string, uint64_t> offs;
    for (uint64_t i = 0; i < nt; ++i) {
        uint64_t nl; rd(&nl, 8);
        std::string name(nl, 0);
        rd(name.data(), nl);
        uint32_t nd; rd(&nd, 4);
        lseek(fd, 8 * nd, SEEK_CUR);
        uint32_t type; uint64_t toff;
        rd(&type, 4); rd(&toff, 8);
        (void)type;
        offs[name] = toff;
    }
    off_t ds = (lseek(fd, 0, SEEK_CUR) + 31) / 32 * 32;
    const uint8_t *m = (const uint8_t *)mmap(nullptr, st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (m == MAP_FAILED) { perror("mmap engram"); exit(1); }
    close(fd);
    auto it = offs.find("per_layer_token_embd.weight");
    if (it == offs.end()) die("engram table name");
    const uint8_t *base = m + ds + it->second;
    return li == 0 ? base : base + (size_t)384006168 * 176; // Q5_K row = 176B
}

using TraceKey = std::tuple<int, int, int>; // step, layer, tag
static std::map<TraceKey, std::vector<float>> read_trace(const char *path) {
    std::map<TraceKey, std::vector<float>> m;
    FILE *f = fopen(path, "rb");
    if (!f) die(std::string("trace unreadable: ") + path);
    uint32_t h[4];
    while (fread(h, 4, 4, f) == 4) {
        std::vector<float> v(h[3]);
        if (fread(v.data(), 4, h[3], f) != h[3]) break;
        if (h[2] == TT_LOGITS) continue; // large, not needed for injection
        m[{(int)h[0], (int)h[1], (int)h[2]}] = std::move(v);
    }
    fclose(f);
    return m;
}

int main(int argc, char **argv) {
    if (argc < 4) {
        std::fprintf(stderr, "usage: %s state.bin ndecode out_ids.txt [max_ctx]\n", argv[0]);
        return 2;
    }
    setenv("ZES_ENABLE_SYSMAN", "1", 0); // free-memory query; must precede SYCL startup
    // Driver switch (read at SYCL startup): no per-launch re-registration of all allocations for
    // kernels the compiler marks "indirect access". That work runs under a lock shared by every
    // card's host thread and cost the six-card path ~15 % (see Backend41::touch, which registers
    // each allocation once instead). OWN_INDIRECT_ACCESS=1 keeps the driver default.
    if (!(getenv("OWN_INDIRECT_ACCESS") && atoi(getenv("OWN_INDIRECT_ACCESS")) == 1)) {
        setenv("NEOReadDebugKeys", "1", 0);
        setenv("DisableIndirectAccess", "1", 0);
    }
    const char *state_path = argv[1];
    int ndecode = atoi(argv[2]);
    int max_ctx = argc > 4 ? atoi(argv[4]) : 16384;
    std::string root = "/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine";

    own41::Backend41::Options opt;
    opt.debug = getenv("OWN_DEBUG") != nullptr;
    opt.hc_legacy = getenv("OWN_HC_LEGACY") != nullptr;
    opt.generic_kernels = getenv("OWN_GENERIC_KERNELS") != nullptr;
    if (const char *e = getenv("OWN_PACKED")) opt.packed = atoi(e) != 0;
    opt.gprof = getenv("OWN_GPROF") != nullptr;
    opt.kprof = opt.gprof && atoi(getenv("OWN_GPROF")) >= 2;
    if (const char *e = getenv("OWN_SMALL")) opt.small_fast = atoi(e) != 0;
    if (const char *e = getenv("OWN_HOST_FLOOR_MIB")) opt.host_floor_mib = atol(e);
    if (const char *e = getenv("OWN_LAYERS"))
        if (sscanf(e, "%d:%d", &opt.layer_begin, &opt.layer_end) != 2) die("OWN_LAYERS=a:b");
    opt.head = opt.layer_end == 40;
    if (const char *e = getenv("OWN_HEAD")) opt.head = atoi(e) != 0;
    if (const char *e = getenv("OWN_DEVS")) {
        std::stringstream ss(e);
        std::string tok;
        while (std::getline(ss, tok, ',')) opt.devices.push_back(atoi(tok.c_str()));
    }
    if (const char *e = getenv("OWN_TP")) opt.tp = atoi(e); // every layer split across this many cards
    if (const char *e = getenv("OWN_GPROF_CARD")) opt.prof_card = atoi(e);
    if (const char *e = getenv("OWN_HC_RIDE")) opt.hc_ride = atoi(e) != 0;
    if (const char *e = getenv("OWN_ROUTER16")) opt.router16 = atoi(e) != 0;
    if (const char *e = getenv("OWN_DIET")) opt.diet = atoi(e) != 0;
    // one host thread per card; trace runs submit phase by phase from one thread
    opt.tp_threads = !getenv("OWN_TRACE") && !(getenv("OWN_TP_THREADS") && atoi(getenv("OWN_TP_THREADS")) == 0);
    std::vector<int> forced;
    if (const char *e = getenv("OWN_FORCED")) {
        std::ifstream ff(e);
        long long v;
        while (ff >> v) forced.push_back((int)v);
        if (forced.empty()) die("OWN_FORCED file empty");
    }
    std::map<TraceKey, std::vector<float>> inject;
    if (const char *e = getenv("OWN_INJECT")) inject = read_trace(e);
    if (opt.layer_begin > 0 && inject.empty()) die("a range that starts above layer 0 needs OWN_INJECT");
    if (!opt.head && forced.empty()) die("without the head the tokens must come from OWN_FORCED");
    const int trace_steps = getenv("OWN_TRACE_STEPS") ? atoi(getenv("OWN_TRACE_STEPS")) : 2;

    try {
        // ---- weights ----
        std::map<std::string, std::pair<std::string, long>> shards;
        {
            std::ifstream sj(root + "/planning/dsv41-fixtures/data/shards.tsv");
            if (!sj) die("shards.tsv missing");
            std::string name, path;
            long ds2;
            while (sj >> name >> path >> ds2) shards[name] = {path, ds2};
        }
        own41::WeightTab wt;
        own41::load_weights(wt, root + "/profiles/dsv41-iq2xxs/placement.tsv", shards);
        std::fprintf(stderr, "store: %zu tensors\n", wt.w.size());

        flash::Directory d;
        {
            std::ifstream df(root + "/planning/dsv41-fixtures/data/dsv41-directory.tsv");
            if (!df) die("directory tsv missing");
            d = flash::read_directory(df);
        }
        flash41::Plan41 plan = flash41::model_plan_v41(d, max_ctx);

        std::fprintf(stderr, "host MemAvailable %ld MiB (floor %ld MiB)\n",
                     own41::meminfo_kb("MemAvailable") / 1024, opt.host_floor_mib);
        own41::Backend41 be(plan, max_ctx, opt);
        for (int t = 0; t < own41::Backend41::TILES; ++t)
            if (be.tile_active(t))
                std::fprintf(stderr, "tile %d -> card %s, %.2f GiB free\n", t, be.tile_pci(t).c_str(),
                             be.free_bytes(t) / 1073741824.0);
        double t0 = now();
        be.upload(wt);
        std::fprintf(stderr, "upload: %.1f GB in %.1fs (%.2f GB/s); host MemAvailable %ld MiB\n",
                     be.uploaded_bytes / 1e9, now() - t0, be.uploaded_bytes / 1e9 / (now() - t0),
                     own41::meminfo_kb("MemAvailable") / 1024);
        std::fprintf(stderr, "packed rows: %zu tensors, %.2f GB on the cards\n", be.packed_tensors, be.packed_bytes / 1e9);
        for (int t = 0; t < own41::Backend41::TILES; ++t)
            if (be.tile_active(t))
                std::fprintf(stderr, "tile %d card %s: %.2f GiB free after load\n", t, be.tile_pci(t).c_str(),
                             be.free_bytes(t) / 1073741824.0);
        if (getenv("OWN_LOAD_ONLY")) return 0;

        // ---- engram tables + prep ----
        const char *eng_path = "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-00006-of-00006.gguf";
        be.eng_base[0] = map_engram(eng_path, 0);
        be.eng_base[1] = map_engram(eng_path, 1);
        std::vector<int32_t> token_map(129280);
        {
            std::ifstream pf(root + "/../data/dsv41-reference/engram_prep.bin", std::ios::binary);
            if (!pf) die("engram_prep.bin missing");
            pf.read((char *)token_map.data(), 129280 * 4);
            pf.read((char *)be.eng_primes, sizeof(be.eng_primes));
            pf.read((char *)be.eng_off, sizeof(be.eng_off));
            pf.read((char *)be.eng_mult, sizeof(be.eng_mult));
            int64_t tail[2];
            pf.read((char *)tail, 16);
            be.eng_pad = tail[0];
        }

        // ---- state dump ----
        long pos;
        long lens[4];
        std::vector<std::vector<float>> rings(40), ckv(4), ik(4);
        float kv_state[4][1024], score_state[4][1024];
        int first = -1;
        std::vector<int> prompt;
        if (const char *pp = getenv("OWN_PROMPT")) {
            std::ifstream pf2(pp);
            long long v;
            while (pf2 >> v) prompt.push_back((int)v);
            if (prompt.empty()) die("OWN_PROMPT file empty");
            if (opt.layer_begin != 0 || !opt.head) die("OWN_PROMPT needs the whole model (no OWN_LAYERS)");
            if ((int)prompt.size() + ndecode > max_ctx) die("prompt + ndecode exceeds max_ctx");
        } else {
            std::ifstream sf(state_path, std::ios::binary);
            if (!sf) die("state unreadable");
            sf.read((char *)&pos, 8);
            sf.read((char *)lens, 32);
            for (int L = 0; L < 40; ++L) {
                rings[L].resize((size_t)128 * 512);
                sf.read((char *)rings[L].data(), (size_t)128 * 512 * 4);
            }
            for (int i = 0; i < 4; ++i) {
                ckv[i].resize((size_t)lens[i] * 512);
                ik[i].resize((size_t)lens[i] * 128);
                sf.read((char *)ckv[i].data(), (size_t)lens[i] * 512 * 4);
                sf.read((char *)ik[i].data(), (size_t)lens[i] * 128 * 4);
            }
            for (int i = 0; i < 4; ++i) {
                sf.read((char *)kv_state[i], 1024 * 4);
                sf.read((char *)score_state[i], 1024 * 4);
            }
            long nt;
            sf.read((char *)&nt, 8);
            std::vector<int32_t> toks(nt);
            std::vector<int64_t> cids(nt);
            sf.read((char *)toks.data(), nt * 4);
            sf.read((char *)cids.data(), nt * 8);
            sf.read((char *)&first, 4);
            if (!sf) die("state file truncated");
            be.comp_ids.assign(cids.begin(), cids.end());
            be.load_state(pos, lens, rings, ckv, ik, kv_state, score_state);
            std::fprintf(stderr, "state loaded: pos=%ld lens=%ld,%ld,%ld,%ld first=%d\n", pos, lens[0], lens[1],
                         lens[2], lens[3], first);
        }
        if (const char *tp = getenv("OWN_TRACE")) be.trace_f = fopen(tp, "wb");
        be.prof_on = getenv("OWN_PROF") != nullptr;
        if (const char *e = getenv("OWN_PACE")) be.pace = atoi(e);
        if (const char *e = getenv("OWN_H2D_WAIT")) be.h2d_wait = atoi(e) != 0;
        if (const char *e = getenv("OWN_KEEP_WARM")) be.keep_warm = atoi(e);
        if (const char *e = getenv("OWN_WARM_ITEMS")) be.warm_items = (size_t)atol(e) / 32 * 32;

        // ---- prompt on the cards (OWN_PROMPT): one decode step per prompt token ----
        const int eos = getenv("OWN_EOS") ? atoi(getenv("OWN_EOS")) : 1;
        if (!prompt.empty()) {
            double tp0 = now(), t_first = 0;
            for (size_t i = 0; i < prompt.size(); ++i) {
                be.comp_ids.push_back(token_map[prompt[i]]);
                be.trace_on = false;
                double t1 = now();
                first = be.decode_step(prompt[i]);
                if (i == 0) t_first = now() - t1;
            }
            double dtp = now() - tp0;
            std::fprintf(stderr, "prompt: %zu tokens read on the cards in %.2fs (%.1f tok/s; first step %.2fs incl. kernel build), first token %d\n",
                         prompt.size(), dtp, prompt.size() > 1 ? (prompt.size() - 1) / (dtp - t_first) : 0.0, t_first,
                         first);
        }

        // ---- decode ----
        static const int srcs[4] = {2, 8, 14, 20};
        std::vector<int> out_ids{forced.empty() ? first : forced[0]};
        int cur = out_ids[0];
        double t_dec = 0;
        int n_timed = 0;
        for (int step = 1; step < ndecode; ++step) {
            if (!forced.empty()) {
                if (step - 1 >= (int)forced.size()) break;
                cur = forced[step - 1];
            }
            be.comp_ids.push_back(token_map[cur]);
            be.trace_step = step;
            be.trace_on = step <= trace_steps;
            if (opt.layer_begin > 0) {
                auto s = inject.find({step, opt.layer_begin - 1, TT_STREAMS_FFN});
                auto p = inject.find({step, opt.layer_begin - 1, TT_FFN_MIX_PRE});
                if (s == inject.end() || p == inject.end()) {
                    std::fprintf(stderr, "reference trace ends at step %d\n", step - 1);
                    break;
                }
                be.set_streams(s->second.data(), p->second.data());
                for (int i = 0; i < 4; ++i) {
                    if (srcs[i] >= opt.layer_begin) continue;
                    auto a = inject.find({step, srcs[i], TT_PUB_CKV});
                    auto b = inject.find({step, srcs[i], TT_PUB_IK});
                    if (a != inject.end() && b != inject.end())
                        be.append_published(i, a->second.data(), b->second.data());
                }
            }
            double t1 = now();
            int next = be.decode_step(cur);
            double dt = now() - t1;
            if (step > 1 || !prompt.empty()) { t_dec += dt; ++n_timed; } // a cold first step carries kernel compilation
            else be.prof_t.clear();
            be.gprof_collect();
            if (!(step > 1 || !prompt.empty())) { be.gprof_t.clear(); be.gprof_n.clear(); be.kprof_t.clear(); be.kprof_n.clear(); }
            if (opt.head) {
                std::fprintf(stderr, "tok %d -> %d (%.3fs)", step, next, dt);
                if (opt.debug || step <= trace_steps) {
                    std::fprintf(stderr, " | top5:");
                    for (auto &[id, v] : be.top5()) std::fprintf(stderr, " %d:%.4f", id, v);
                }
                std::fprintf(stderr, "\n");
                out_ids.push_back(next);
                cur = next;
                if (forced.empty() && next == eos) {
                    std::fprintf(stderr, "end of sentence after %d generated tokens\n", (int)out_ids.size());
                    break;
                }
            } else {
                std::fprintf(stderr, "step %d layers %d:%d (%.3fs)\n", step, opt.layer_begin, opt.layer_end, dt);
            }
            if (be.trace_f) fflush(be.trace_f);
        }
        if (n_timed)
            std::fprintf(stderr, "decode: %d steps after the first, %.3f s/step, %.2f tok/s\n", n_timed,
                         t_dec / n_timed, n_timed / t_dec);
        if (be.prof_on && n_timed) {
            std::vector<std::pair<double, std::string>> v;
            double tot = 0;
            for (auto &[k, t] : be.prof_t) { v.push_back({t / n_timed, k}); tot += t / n_timed; }
            std::sort(v.rbegin(), v.rend());
            std::fprintf(stderr, "profile (ms per step, queue wait at every mark):\n");
            for (auto &[t, k] : v) std::fprintf(stderr, "  %-14s %8.2f  %5.1f%%\n", k.c_str(), t * 1e3, 100 * t / tot);
            std::fprintf(stderr, "  %-14s %8.2f\n", "total", tot * 1e3);
        }
        if (opt.gprof && n_timed) {
            std::vector<std::pair<double, std::string>> v;
            double tot = 0;
            for (auto &[k, t] : be.gprof_t) { v.push_back({t / n_timed, k}); tot += t / n_timed; }
            std::sort(v.rbegin(), v.rend());
            std::fprintf(stderr, "GPU-time profile (ms per step; card time between marks, no waits):\n");
            for (auto &[t, k] : v)
                std::fprintf(stderr, "  %-14s %8.3f  %5.1f%%  (%ld marks/step)\n", k.c_str(), t * 1e3, 100 * t / tot,
                             be.gprof_n[k] / n_timed);
            std::fprintf(stderr, "  %-14s %8.3f   (wall %.3f)\n", "total", tot * 1e3, t_dec / n_timed * 1e3);
            if (opt.kprof) {
                std::vector<std::pair<double, std::string>> kv;
                double ktot = 0;
                for (auto &[k, t] : be.kprof_t) { kv.push_back({t / n_timed, k}); ktot += t / n_timed; }
                std::sort(kv.rbegin(), kv.rend());
                std::fprintf(stderr, "kernel time per type (ms per step, start to end; launches per step):\n");
                for (auto &[t, k] : kv)
                    std::fprintf(stderr, "  %8.3f  %5.1f%%  %5ld  %8.2f us  %s\n", t * 1e3, 100 * t / tot,
                                 be.kprof_n[k] / n_timed, t * 1e6 * n_timed / std::max(1L, be.kprof_n[k]), k.c_str());
                std::fprintf(stderr, "  kernels %8.3f ms, launches %ld per step; marks total %.3f -> gaps/copies %.3f ms\n",
                             ktot * 1e3, [&] { long n = 0; for (auto &[k, c] : be.kprof_n) n += c; return n / n_timed; }(),
                             tot * 1e3, (tot - ktot) * 1e3);
            }
        }
        std::ofstream of(argv[3]);
        for (int t : out_ids) of << t << "\n";
    } catch (const std::exception &ex) {
        std::fprintf(stderr, "fatal: %s\n", ex.what());
        return 1;
    }
    return 0;
}
