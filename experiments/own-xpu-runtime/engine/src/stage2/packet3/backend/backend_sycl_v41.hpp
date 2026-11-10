// Backend41: SYCL executor for the DeepSeek V4.1 Flash decode step on B70s.
//
// Placement for 6 cards of 31.9 GiB, packed by exact placement.tsv bytes
// (layers are 3.1-4.8 GB, growing with depth):
//   t0: embed+L0-7 (26.7)  t1: L8-14 (26.6)  t2: L15-21 (28.4)
//   t3: L22-27 (27.2)      t4: L28-33 (28.7) t5: L34-39+head (27.8+0.5)
//
// Host-memory rules (measured 2026-11-09 on the 15 GiB six-card host; the
// earlier design froze the machine four times, see
// notes/2026-11-09-dsv41-device-load-host-memory.md):
// * ONE SYCL CONTEXT PER CARD. In a context that holds several cards every
//   device-USM byte is also populated in host RAM (1:1; 6 GiB on the card
//   cost 6 GiB of MemAvailable). In a one-card context 28 GiB on the card
//   cost 56 MiB. A shared context can never hold this 154 GiB model.
// * NEVER OVERCOMMIT A CARD. xe does not fail an allocation that does not
//   fit: it evicts other buffers (ours or another process's) from VRAM into
//   host RAM. We read each card's free memory first and refuse to start.
// * Bounded upload: weights go disk -> 32 MiB staging buffer -> card, one
//   thread per card, with a MemAvailable floor that aborts the load.
// * No device-to-device copies; inter-card traffic is staged through host.
//
// Design:
// * Activations ("streams", 4 x 5120 bf16 = 40 KB) migrate card-to-card as
//   layers advance; all other cross-card reads are served by mirrored state.
// * compress_kv rows (4 publishers) and index keys are mirrored on every
//   active card; a publish appends one row everywhere. Window rings are per
//   layer and live on the layer's card.
// * Weights are uploaded raw (GGUF row bytes); device gemv decodes with
//   iq3::element.
//
// Decode-only v1: prefill runs in the CPU reference runner; its state is
// handed off through a state dump, then decode steps run here.
//
// Options select a layer range so a subset of cards can be validated against
// the CPU reference trace (prefix: layers 0..N with no head; segment: streams
// injected from the reference at the first layer).
#pragma once
#ifndef OWN_RT_HOST_ONLY
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <condition_variable>
#include <cxxabi.h>
#include <fcntl.h>
#include <fstream>
#include <map>
#include <mutex>
#include <pthread.h>
#include <sched.h>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <thread>
#include <unistd.h>
#include <unordered_map>
#include <vector>
#include "stage2/packet3/backend/trace_tags_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/sycl_v41_draft.hpp"
#include "stage2/packet3/step/plan_v41.hpp"
#include <level_zero/ze_api.h>
#include <sycl/ext/oneapi/backend/level_zero.hpp>

namespace own41 {

inline long meminfo_kb(const char *key) {
    std::ifstream f("/proc/meminfo");
    std::string k, rest;
    long v;
    while (f >> k >> v) {
        std::getline(f, rest);
        if (k == std::string(key) + ":") return v;
    }
    return -1;
}

// ---- weight store: placement.tsv + shards.tsv (runner format) -------------
struct WeightTab {
    struct E {
        iq3::Type type;
        const uint8_t *ptr;
        long rows = 1, cols = 1, experts = 0;
        int shard = -1; // index into paths
        off_t off = 0;  // absolute file offset of the tensor bytes
    };
    std::unordered_map<std::string, E> w;
    std::vector<std::pair<const uint8_t *, size_t>> maps;
    std::vector<int> fds;
    std::vector<std::string> paths;
    ~WeightTab() {
        for (auto &[p, s] : maps) munmap((void *)p, s);
        for (int fd : fds) close(fd);
    }
    const E &at(const std::string &n) const {
        auto it = w.find(n);
        if (it == w.end()) throw std::invalid_argument("weight missing " + n);
        return it->second;
    }
    size_t row_bytes(const E &e) const {
        auto l = iq3::layout(e.type);
        return (size_t)(e.cols / l.elements) * l.bytes;
    }
    size_t bytes(const E &e) const {
        return row_bytes(e) * e.rows * (e.experts ? e.experts : 1);
    }
};

inline void load_weights(WeightTab &S, const std::string &placement,
                         const std::map<std::string, std::pair<std::string, long>> &shards) {
    std::map<std::string, std::pair<int, long>> base; // shard name -> (index, data start)
    for (auto &[name, pd] : shards) {
        int fd = open(pd.first.c_str(), O_RDONLY);
        if (fd < 0) throw std::runtime_error("open shard " + pd.first);
        struct stat st;
        fstat(fd, &st);
        auto *p = (const uint8_t *)mmap(nullptr, st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
        if (p == MAP_FAILED) throw std::runtime_error("mmap " + pd.first);
        base[name] = {(int)S.maps.size(), pd.second};
        S.maps.push_back({p, (size_t)st.st_size});
        S.fds.push_back(fd);
        S.paths.push_back(pd.first);
    }
    std::ifstream f(placement);
    if (!f) throw std::runtime_error("placement unreadable");
    std::string shard, name, comp;
    long kind, offset, size, layer, mask, rank;
    while (f >> shard >> name >> comp >> kind >> offset >> size >> layer >> mask >> rank) {
        std::vector<long> dims(rank);
        for (auto &d : dims) f >> d;
        WeightTab::E e;
        e.type = (iq3::Type)kind;
        auto [si, ds] = base.at(shard);
        e.shard = si;
        e.off = (off_t)(ds + offset);
        e.ptr = S.maps[si].first + e.off;
        e.cols = dims[0];
        if (rank == 3) { e.experts = dims[2]; e.rows = dims[1]; }
        else e.rows = rank > 1 ? dims[1] : 1;
        if ((size_t)e.off + S.bytes(e) > S.maps[si].second)
            throw std::runtime_error("tensor past end of shard: " + name);
        S.w[name] = e;
    }
}

// ---- placement -------------------------------------------------------------
inline int tile_of_layer(int L) {
    static const int map[40] = {0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1,
                                1, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3,
                                4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5};
    return map[L]; // 8,7,7,6,6,6 layers -> 26.6..28.7GB per card (tsv bytes)
}
inline int layer_of_name(const std::string &n) { // -1: not a block tensor
    if (n.rfind("blk.", 0) != 0) return -1;
    return std::stoi(n.substr(4, n.find('.', 4) - 4));
}

// ---- backend ---------------------------------------------------------------
class Backend41 {
public:
    // Activation storage between operators: F32 by default; -DOWN41_ACT_BF16
    // builds the original BF16-activation executor (see ops41sycl::ActBF16).
#ifdef OWN41_ACT_BF16
    using Act = ops41sycl::ActBF16;
    static constexpr const char *act_name = "bf16";
#else
    using Act = ops41sycl::ActF32;
    static constexpr const char *act_name = "f32";
#endif
    using act_t = Act::T;
    static constexpr int TILES = 6;
    static constexpr int HEAD_TILE = 5;
    static constexpr int HC_SEG = 8; // hc_mix column segments (part of the arithmetic contract)
    struct Options {
        int layer_begin = 0, layer_end = 40; // layers executed on device
        bool head = true;                    // output norm + logits + argmax
        std::vector<int> devices;            // SYCL gpu indices for the ACTIVE tiles, ascending tile order
        long host_floor_mib = 3072;          // abort the load below this MemAvailable
        bool hc_legacy = false;              // pre-2026-11-09 FFN pre-mix (A/B only)
        bool generic_kernels = false;        // runtime-type gemv kernels (A/B against the specialized ones)
        bool packed = true;                  // packed device rows + packed kernels where available (pack_v41.hpp)
        bool gprof = false;                  // profiling queues: GPU time between profile marks, no waits (OWN_GPROF)
        bool kprof = false;                  // with gprof: also kernel time per kernel type (OWN_GPROF=2)
        bool small_fast = true;              // latency-bound forms of norm / hc mix / sparse attention (OWN_SMALL=0: old)
        bool debug = false;
        // tensor parallel (OWN_TP): every layer runs on all `tp` active cards at
        // once, each with a row slice of the big matrices; the cards swap slices
        // card to card (XchgP). 1 = the layer pipeline above. Needs the f32 build.
        int tp = 1;
        bool tp_threads = true; // one host thread per card (OWN_TP_THREADS; trace runs force 0)
        int tp_pin[7] = {-1, -1, -1, -1, -1, -1, -1}; // OWN_TP_PIN="c0,..,c5[,m]": card c's host thread on CPU c_c,
                                // the main thread on CPU m (-1 = left to the scheduler). On this host the six
                                // threads otherwise float and can share a physical core (CPU n and n + 8).
        int tp_w[6] = {};       // tp: relative shares per card of the expert / shared-expert / output-b / engram rows
                                // (OWN_TP_WEIGHTS="w0,..,w5", all 0 = equal): the cards holding two of the eight
                                // attention groups can take fewer. Every row's sums are the same on any card.
        int tp_vw[6] = {};      // ... of the vocabulary rows: head, draft Markov rows (OWN_TP_VWEIGHTS)
        int prof_card = 0;      // tp: the card whose marks and kernels OWN_GPROF records (OWN_GPROF_CARD)
        bool hc_ride = true;    // tp: stream mix inside the next matrix launches (OWN_HC_RIDE=0: own launches)
        bool router16 = true;   // router rows (F32, every value exact in 16 bits) stored halved (OWN_ROUTER16=0: F32)
        bool diet = true;       // tp: neighbouring launches merged (OWN_DIET=0: one launch per operator as before)
        bool down_ex = false;   // tp: shared expert down rows inside the expert down launch (OWN_DOWN_EX=1; no gain)
        int pair_wg = 128;      // tp: work-groups of the expert gate+up launch (OWN_PAIR_WG)
        int down_wg = 128;      // work-groups of the expert down launch (OWN_DOWN_WG)
        int pair_wg_iq1 = 0;    // gate+up work-groups for IQ1_S experts, 0 = pair_wg (OWN_PAIR_WG_IQ1)
        bool dr_fc_split = true; // the draft's dsp.fc rows split across the cards + an exchange (OWN_DR_FC_SPLIT)
        bool dr_mxp = true; // the draft's MXFP4 experts packed (pk41 MXFP4) and run grouped by expert (OWN_DR_MXP)
        bool q2k_fast = true;    // layer 0's unpacked Q2_K expert rows through RoutedQ2KF (bitwise; OWN_Q2K_FAST)
        bool bf16_rows = true;   // BF16 rows (indexer, compressor) by block reads through GemvH16P (OWN_BF16_ROWS)
        bool rope_out = true;   // tp: inverse rope in the attention output's store (OWN_ROPE_OUT=0: own launch)
        bool xtail = false;     // tp: each exchange runs in its producer launch's last work-group (OWN_XTAIL=1; slower)
        bool xpull = true;      // tp: exchanges whose largest slice is >= xpull_min bytes copy by loads from the peers
                                // (ops41sycl::XchgPull; stores into a peer run at ~1 GB/s here) (OWN_XPULL=0: stores)
        unsigned xpull_min = 8192; // (OWN_XPULL_MIN)
        bool dspark = false; // the DSpark draft's weights ("dsp." names) are loaded: draft buffers, feature capture
        bool norm_dots = true;  // tp: stream-mix dot rows ride in the pre-norm's launch (OWN_NORM_DOTS=0: in q_a / router)
        bool pf = false;        // tp: attention launches prefetch output-a/b rows into the cache (OWN_PF=1; slower: the
                                // launch ends only when its prefetch work-groups do)
        bool fin_move = false;  // tp: stream mix finishes ride in output-b / expert gate+up launches (OWN_FIN_MOVE=1; slower)
        bool exp_pair = true;   // tp: expert gate + up rows in one launch (OWN_EXP_PAIR=0: two launches)
        bool eng_split = true;  // tp: engram_kv rows split across the cards, pushed at step start (OWN_ENG_SPLIT=0: every card all rows)
        bool eng_dev = true;    // tp: the 24 hashed engram rows go to each card as raw Q5_K bytes (copied from ordinary
                                // host memory) and the card decodes them (EngRowsA: EmbedRowA's decode), not six host
                                // decodes (OWN_ENG_DEV=0: host decode)
        bool eng_early = true;  // tp: the engram rows' disk reads start sooner: the anchor's rows while the draft runs,
                                // a block's other rows split over the card threads (each its share, then reads),
                                // not 240 serial requests on the main thread; no read-around on the table (OWN_ENG_EARLY=0: off)
        long tp_spin_us = 0;    // tp: the main thread and the card threads poll for each other's hand-off for up to this
                                // many us before sleeping on the condition variable (OWN_TP_SPIN_US; 0 = sleep at once)
        bool eng_late = true;   // tp: the engram rows are fetched and pushed after layer 0's launches (the card runs the
                                // embed and layer 0 meanwhile; layers 1 and 14 need them), not before the embed (OWN_ENG_LATE=0: before)
        bool dev_index = true;  // tp: past 512 rows every card picks its own top-512 on the card (TopKSelP), no host
                                // round trip (OWN_DEV_INDEX=0: the lead's host top-k, the others wait)
        bool dev_index_check = false; // dev_index lists checked against the host selection (OWN_DEV_INDEX_CHECK=1)
        bool score_b = true;    // dev_index: IndexerScoreB, keys read once, same sums (OWN_SCORE_B=0: IndexerScoreA)
    };
    struct DevPtr {
        void *p = nullptr;
        size_t bytes = 0;
        int tile = -1;
        bool packed = false; // rows are in the pack_v41.hpp layout
        unsigned r0 = 0, nrows = 0; // rows [r0, r0 + nrows) of each expert / of the matrix are on this card
    };

    Backend41(const flash41::Plan41 &plan, int max_seq, Options opt)
        : g(plan.g), max_seq(max_seq), o(std::move(opt)) {
        if (o.layer_begin < 0 || o.layer_end > g.layers || o.layer_begin > o.layer_end)
            throw std::invalid_argument("layer range");
        if (o.tp > 1) { // the first tp cards hold every layer of the range (and the head)
#ifdef OWN41_ACT_BF16
            throw std::invalid_argument("tensor parallel (OWN_TP) needs the f32-activation build");
#endif
            if (o.tp > TILES) throw std::invalid_argument("tp > 6");
            for (int t = 0; t < o.tp; ++t) active[t] = true;
        } else {
            for (int L = o.layer_begin; L < o.layer_end; ++L) active[tile_of_layer(L)] = true;
            if (o.head) active[HEAD_TILE] = true;
        }
        int n_active = 0;
        for (bool a : active) n_active += a;
        if (!n_active) throw std::invalid_argument("nothing to run");

        auto all = sycl::device::get_devices(sycl::info::device_type::gpu);
        if (o.devices.empty())
            for (int i = 0; i < n_active; ++i) o.devices.push_back(i);
        if ((int)o.devices.size() != n_active)
            throw std::runtime_error("need " + std::to_string(n_active) + " cards for this layer range, got " +
                                     std::to_string(o.devices.size()));
        // Inactive tiles alias the first active card's context/queue objects so
        // no context is ever created on a card this run does not use.
        int k = 0, first = -1;
        std::vector<int> di_of(TILES, -1);
        for (int t = 0; t < TILES; ++t) {
            if (!active[t]) continue;
            int di = o.devices[k++];
            if (di < 0 || di >= (int)all.size())
                throw std::runtime_error("card index " + std::to_string(di) + " not present (" +
                                         std::to_string(all.size()) + " cards visible)");
            di_of[t] = di;
            if (first < 0) first = t;
        }
        for (int t = 0; t < TILES; ++t) devs.push_back(all[di_of[active[t] ? t : first]]);
        std::map<int, sycl::context> cm;
        for (int t = 0; t < TILES; ++t)
            if (active[t]) cm.emplace(t, sycl::context(devs[t])); // one context per card: see header
        for (int t = 0; t < TILES; ++t) {
            int a = active[t] ? t : first;
            ctxs.push_back(cm.at(a));
            if (opt.gprof)
                qs.emplace_back(cm.at(a), devs[a],
                                sycl::property_list{sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
            else
                qs.emplace_back(cm.at(a), devs[a], sycl::property::queue::in_order{});
        }
        if (o.tp > 1) {
            // every kernel built for every card before the first step: a card still compiling a kernel at its
            // first launch while a peer already waits in an exchange times that exchange out (a new binary
            // with a cold compiler cache). One card at a time: the first fills the driver's cache.
            const double t0 = now_s();
            for (int t = 0; t < o.tp; ++t)
                (void)sycl::get_kernel_bundle<sycl::bundle_state::executable>(ctxs[t], {devs[t]});
            std::printf("kernels built for %d cards in %.1fs\n", o.tp, now_s() - t0);
        }
        for (int t = 0; t < TILES; ++t) {
            if (!active[t]) continue;
            int di = di_of[t];
            pci[t] = devs[t].has(sycl::aspect::ext_intel_pci_address)
                         ? devs[t].get_info<sycl::ext::intel::info::device::pci_address>()
                         : std::string("card") + std::to_string(di);
            // early refusal: a card someone else filled would be evicted into host RAM
            size_t fr = free_bytes(t);
            if (fr != SIZE_MAX && fr < ((size_t)4 << 30))
                throw std::runtime_error("card " + pci[t] + " has only " + gib(fr) +
                                         " GiB free: another process is using it. Refusing to load "
                                         "(overcommitted card memory spills into host RAM).");
        }

        const size_t rows_c2 = (size_t)max_seq / 2 + 2, rows_c1 = (size_t)max_seq + 2;
        for (int t = 0; t < TILES; ++t) {
            if (!active[t]) continue;
            streams[t] = dalloc<act_t>(t, 4 * (size_t)g.h);
            for (int s = 0; s < 4; ++s) {
                size_t rows = s == 3 ? rows_c1 : rows_c2; // layer 20 publishes at ratio 1
                ckv_mirror[t][s] = dalloc<uint16_t>(t, rows * g.hd);
                ik_mirror[t][s] = dalloc<uint16_t>(t, rows * 128);
            }
            for (int s = 0; s < 8; ++s) {
                cidx_mirror[t][s] = dalloc<int32_t>(t, 512);
                std::vector<int32_t> neg(512, -1);
                qs[t].memcpy(cidx_mirror[t][s], neg.data(), 512 * 4).wait();
            }
            scratch_alloc(t);
        }
        for (int L = o.layer_begin; L < o.layer_end; ++L) {
            if (o.tp > 1)
                for (int t = 0; t < o.tp; ++t) // + a block area of MTX rows (multi-token steps)
                    ring[t][L] = dalloc<uint16_t>(t, (size_t)(128 + MTX) * g.hd);
            else
                ring[tile_of_layer(L)][L] = dalloc<uint16_t>(tile_of_layer(L), (size_t)128 * g.hd);
        }
        if (o.head && o.tp <= 1) {
            logits_ = dalloc<float>(HEAD_TILE, g.vocab);
            tok_out_ = dalloc<int32_t>(HEAD_TILE, 1);
            am_v_ = dalloc<float>(HEAD_TILE, (size_t)g.vocab / AM_CH + 1);
            am_i_ = dalloc<int32_t>(HEAD_TILE, (size_t)g.vocab / AM_CH + 1);
        }
        h_streams.resize(4 * (size_t)g.h);
        for (int s = 0; s < 4; ++s) {
            size_t rows = s == 3 ? rows_c1 : rows_c2;
            h_ckv[s].reserve(rows * g.hd);
            h_ik[s].reserve(rows * 128);
        }
        for (auto &slot : h_cidx)
            for (auto &v : slot) v.assign(512, -1);
        for (auto &card : h_eng)
            for (auto &layer : card)
                for (auto &v : layer) v.resize((size_t)24 * g.engram_dim);
        build_rope_tables();
        for (int t = 0; t < TILES; ++t)
            if (active[t]) qs[t].wait();
        cur = o.layer_begin < g.layers ? tile_of_layer(o.layer_begin) : HEAD_TILE;
        if (o.tp > 1) {
            cur = 0;
            tp_setup();
        }
    }

    ~Backend41() {
        if (!tp_th.empty()) {
            {
                std::lock_guard<std::mutex> lk(tp_mu);
                tp_quit = true;
            }
            tp_cv.notify_all();
            // (a spinning worker sees tp_quit too)
            for (auto &x : tp_th) x.join();
        }
        for (int t = 0; t < TILES; ++t) {
            if (!active[t]) continue;
            try { qs[t].wait(); } catch (...) {}
        }
        for (int c = 0; c < TILES; ++c) // peers' arenas opened in this card's context
            for (int d = 0; d < TILES; ++d)
                if (c != d && xpeer[c][d])
                    zeMemCloseIpcHandle(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctxs[c]), xpeer[c][d]);
        for (int t = 0; t < TILES; ++t) {
            if (!active[t]) continue;
            if (xerr[t]) sycl::free(xerr[t], ctxs[t]);
            for (void *p : owned[t]) sycl::free(p, ctxs[t]);
        }
        if (trace_f) fclose(trace_f);
    }
    Backend41(const Backend41 &) = delete;
    Backend41 &operator=(const Backend41 &) = delete;

    bool tile_active(int t) const { return active[t]; }
    const std::string &tile_pci(int t) const { return pci[t]; }

    // Free VRAM on the tile's card as the driver reports it (needs
    // ZES_ENABLE_SYSMAN=1 before SYCL starts). SIZE_MAX if unavailable.
    size_t free_bytes(int t) const {
        if (!devs[t].has(sycl::aspect::ext_intel_free_memory)) return SIZE_MAX;
        return devs[t].get_info<sycl::ext::intel::info::device::free_memory>();
    }

    // ---- weight upload ------------------------------------------------------
    bool wanted(const std::string &n) const {
        if (n == "per_layer_token_embd.weight") return false; // NVMe engram store
        if (n.find("exp_probs_b_vl") != std::string::npos) return false; // vision router bias
        int L = layer_of_name(n);
        if (L >= 0) return L >= o.layer_begin && L < o.layer_end;
        if (n == "token_embd.weight") return o.layer_begin == 0;
        return o.head; // output.weight, output_norm.weight
    }
    int tile_of(const std::string &n) const {
        int L = layer_of_name(n);
        if (L >= 0) return tile_of_layer(L);
        return n == "token_embd.weight" ? 0 : HEAD_TILE;
    }

    // Upload the selected weights (raw GGUF bytes) to their cards.
    void upload(const WeightTab &wt) {
        W = &wt;
        static constexpr size_t CHUNK = (size_t)2 << 30, PIECE = (size_t)32 << 20;
        struct Item {
            const std::string *name;
            const WeightTab::E *e;
            size_t bytes, chunk, off;
            bool packed;
            size_t rb, prb;   // raw / packed row bytes
            unsigned sr0, sr1; // rows of each expert (of the matrix) on this card: all unless tp splits it
            size_t fbytes;     // bytes read from the file
        };
        std::vector<Item> items[TILES];
        std::vector<size_t> chunk_sz[TILES];
        size_t need[TILES] = {}, total = 0;
        for (const auto &kv : wt.w) {
            if (!wanted(kv.first)) continue;
            const auto &e = kv.second;
            auto add = [&](int t) {
                const auto [a, b] = tp_rows(kv.first, e, t);
                Item it{&kv.first, &e, wt.bytes(e), 0, 0, false, wt.row_bytes(e), 0, a, b, wt.bytes(e)};
                const size_t nr = (size_t)(b - a) * (size_t)(e.experts ? e.experts : 1);
                if ((long)(b - a) != e.rows) it.bytes = it.fbytes = it.rb * nr;
                if (pack_wanted(kv.first, e)) {
                    it.packed = true;
                    it.prb = pk41::packed_row_bytes(e.type, (size_t)e.cols);
                    it.bytes = it.prb * nr;
                }
                items[t].push_back(it);
            };
            if (o.tp > 1)
                for (int t = 0; t < o.tp; ++t) add(t);
            else
                add(tile_of(kv.first));
        }
        for (int t = 0; t < TILES; ++t) {
            auto &v = items[t];
            std::sort(v.begin(), v.end(), [](const Item &a, const Item &b) {
                return a.e->shard != b.e->shard ? a.e->shard < b.e->shard : a.e->off < b.e->off;
            });
            for (auto &it : v) {
                size_t padded = (it.bytes + 255) & ~(size_t)255; // device bytes (packed size if packed)
                if (chunk_sz[t].empty() || chunk_sz[t].back() + padded > CHUNK) chunk_sz[t].push_back(0);
                it.chunk = chunk_sz[t].size() - 1;
                it.off = chunk_sz[t].back();
                chunk_sz[t].back() += padded;
                need[t] += padded;
                total += it.fbytes; // file bytes (progress counter)
            }
        }
        // preflight: every card must already have room (see header: no overcommit)
        const size_t margin = (size_t)384 << 20;
        std::string refuse;
        for (int t = 0; t < TILES; ++t) {
            if (!active[t]) continue;
            size_t fr = free_bytes(t);
            if (o.debug)
                std::fprintf(stderr, "  card %s (tile %d): need %s GiB, free %s GiB\n", pci[t].c_str(), t,
                             gib(need[t]).c_str(), fr == SIZE_MAX ? "?" : gib(fr).c_str());
            if (fr != SIZE_MAX && need[t] + margin > fr)
                refuse += " " + pci[t] + " needs " + gib(need[t] + margin) + " GiB, has " + gib(fr) + ";";
        }
        if (!refuse.empty())
            throw std::runtime_error("not enough free card memory:" + refuse +
                                     " refusing to load (overcommit would spill into host RAM)");
        const long floor_kb = o.host_floor_mib * 1024;
        auto host_low = [&] { return meminfo_kb("MemAvailable") < floor_kb; };
        if (host_low())
            throw std::runtime_error("host MemAvailable is already below the " +
                                     std::to_string(o.host_floor_mib) + " MiB floor");
        // allocate the arenas (exact sizes), checking host memory between chunks
        std::vector<uint8_t *> chunks[TILES];
        for (int t = 0; t < TILES; ++t)
            for (size_t sz : chunk_sz[t]) {
                chunks[t].push_back(dalloc<uint8_t>(t, sz, false));
                if (host_low())
                    throw std::runtime_error("host memory fell below the floor while allocating on card " +
                                             pci[t] + " (card memory is spilling into host RAM)");
            }
        // copy: one thread per card, disk -> bounded staging -> card
        std::vector<int> dfd(wt.paths.size(), -1), bfd(wt.paths.size(), -1);
        for (size_t i = 0; i < wt.paths.size(); ++i) {
            dfd[i] = open(wt.paths[i].c_str(), O_RDONLY | O_DIRECT);
            bfd[i] = open(wt.paths[i].c_str(), O_RDONLY);
            if (bfd[i] < 0) throw std::runtime_error("open " + wt.paths[i]);
        }
        std::atomic<size_t> done{0};
        std::atomic<bool> stop{false};
        std::mutex err_mu;
        std::string err;
        auto fail = [&](const std::string &m) {
            std::lock_guard<std::mutex> lk(err_mu);
            if (err.empty()) err = m;
            stop = true;
        };
        auto worker = [&](int t) {
            uint8_t *stage = (uint8_t *)aligned_alloc(4096, PIECE + 8192);
            uint8_t *pstage = (uint8_t *)aligned_alloc(4096, PIECE + PIECE / 8 + 65536); // packed rows
            if (!stage || !pstage) { free(stage); free(pstage); return fail("staging alloc"); }
            try {
                for (const auto &it : items[t]) {
                  // a row slice (tp) is one file segment per expert: rows [sr0, sr1) of each
                  const bool whole = (long)(it.sr1 - it.sr0) == it.e->rows;
                  const size_t nseg = whole ? 1 : (size_t)(it.e->experts ? it.e->experts : 1);
                  const size_t raw = whole ? wt.bytes(*it.e) : (size_t)(it.sr1 - it.sr0) * it.rb; // file bytes per segment
                  const size_t seg_dev = it.packed ? raw / it.rb * it.prb : raw;
                  for (size_t sg = 0; sg < nseg && !stop; ++sg) {
                    uint8_t *dst = chunks[t][it.chunk] + it.off + sg * seg_dev;
                    const off_t fbase =
                        it.e->off + (off_t)(whole ? 0 : (sg * (size_t)it.e->rows + it.sr0) * it.rb);
                    for (size_t d = 0; d < raw && !stop;) {
                        // packed tensors move whole rows per piece
                        size_t n = it.packed ? std::min(PIECE / it.rb * it.rb, raw - d) : std::min(PIECE, raw - d);
                        off_t fo = fbase + (off_t)d, a0 = fo & ~(off_t)4095;
                        size_t lead = (size_t)(fo - a0), want = (lead + n + 4095) & ~(size_t)4095;
                        ssize_t got = dfd[it.e->shard] >= 0 ? pread(dfd[it.e->shard], stage, want, a0) : -1;
                        if (got < (ssize_t)(lead + n)) { // no O_DIRECT here: plain read
                            lead = 0;
                            for (size_t r = 0; r < n;) {
                                ssize_t k = pread(bfd[it.e->shard], stage + r, n - r, fo + (off_t)r);
                                if (k <= 0) throw std::runtime_error("short read " + *it.name);
                                r += (size_t)k;
                            }
                        }
                        if (it.packed) {
                            const size_t nr = n / it.rb;
                            for (size_t r = 0; r < nr; ++r)
                                pk41::pack_row(it.e->type, stage + lead + r * it.rb, pstage + r * it.prb,
                                               (size_t)it.e->cols);
                            qs[t].memcpy(dst + d / it.rb * it.prb, pstage, nr * it.prb).wait();
                        } else {
                            qs[t].memcpy(dst + d, stage + lead, n).wait();
                        }
                        d += n;
                        done += n;
                        if (host_low()) fail("host MemAvailable fell below the floor during upload");
                    }
                  }
                  if (stop) break;
                }
            } catch (const std::exception &ex) {
                fail(std::string("upload tile ") + std::to_string(t) + ": " + ex.what());
            }
            free(stage);
            free(pstage);
        };
        std::vector<std::thread> th;
        auto t0 = std::chrono::steady_clock::now();
        for (int t = 0; t < TILES; ++t)
            if (active[t] && !items[t].empty()) th.emplace_back(worker, t);
        size_t last_print = 0;
        while (done < total && !stop) {
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
            if (o.debug && done - last_print >= ((size_t)8 << 30)) {
                last_print = done;
                double s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
                std::fprintf(stderr, "  upload %.1f/%.1f GB  %.2f GB/s  host avail %ld MiB\n", done / 1e9,
                             total / 1e9, done / 1e9 / s, meminfo_kb("MemAvailable") / 1024);
            }
        }
        for (auto &x : th) x.join();
        for (int fd : dfd) if (fd >= 0) close(fd);
        for (int fd : bfd) if (fd >= 0) close(fd);
        if (!err.empty()) throw std::runtime_error(err);
        for (int t = 0; t < TILES; ++t)
            for (const auto &it : items[t]) {
                wgt[t][*it.name] = {chunks[t][it.chunk] + it.off, it.bytes, t, it.packed, it.sr0, it.sr1 - it.sr0};
                if (it.packed) { ++packed_tensors; packed_bytes += it.bytes; }
            }
        uploaded_bytes = total;
    }
    size_t uploaded_bytes = 0;
    size_t packed_tensors = 0, packed_bytes = 0;
    // Weights read only by gemv / gemv_grouped / routed_gemv may be packed;
    // the token embedding is read row-by-row by EmbedRow and stays raw.
    bool pack_wanted(const std::string &n, const WeightTab::E &e) const {
#ifdef OWN41_ACT_BF16
        (void)n; (void)e;
        return false; // packed kernels take f32 activations
#else
        if (!o.packed || n == "token_embd.weight") return false;
        if (e.type == iq3::Type::F32 && n.rfind("dsp.", 0) == 0) return false; // the draft's router stays F32
        if (e.type == iq3::Type::MXFP4) // only the draft's routed experts (dr_routed reads the packed form)
            return o.dr_mxp && n.rfind("dsp.", 0) == 0 && e.experts > 0 && (e.cols == 5120 || e.cols == 2304);
        if (e.type == iq3::Type::F32) { // the router: upload refuses (pack_row) if a value is not exact in 16 bits
            static const std::string rn = "ffn_gate_inp.weight";
            return o.router16 && e.cols == 5120 && e.experts == 0 && n.size() > rn.size() &&
                   n.compare(n.size() - rn.size(), rn.size(), rn) == 0;
        }
        return pk41::packable(e.type, (size_t)e.cols, e.experts > 0);
#endif
    }

    // ---- public decode state -----------------------------------------------
    long pos = 0;
    long src_len[4] = {0, 0, 0, 0};
    std::vector<int64_t> comp_ids; // mapped ids history (driver-maintained)
    const uint8_t *eng_base[2] = {}; // Q5_K tables for layers 1/14
    int64_t eng_primes[2][3][8];
    int64_t eng_off[2][24];
    int64_t eng_mult[2][4];
    int64_t eng_pad = 0;

    // profile (OWN_PROF): wall time per op group, with a queue wait at every
    // mark. The waits change the totals; use it for shares, not for tok/s.
    bool prof_on = false;
    std::map<std::string, double> prof_t;
    double prof_last = 0;
    static double now_s() {
        return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
    }
    void prof_begin(int t) {
        if (o.tp > 1 && !o.gprof) return;
        if (o.gprof) {
            gmarks.clear();
            kevs.clear(); // steps without a collect (prompt reading) leave theirs behind
            gmark("begin", t);
            return;
        }
        if (!prof_on) return;
        qs[t].wait();
        prof_last = now_s();
    }
    // GPU-time profile (Options::gprof): a barrier at every mark; per card, the
    // device time between consecutive marks of one step goes to the later
    // mark's name. Includes idle time on the card while the host had not yet
    // submitted (host-bound gaps), excludes everything before a card's first
    // mark in the step (hand-over from the previous card).
    struct GMark { const char *name; int t; sycl::event e; };
    std::vector<GMark> gmarks;
    std::map<std::string, double> gprof_t; // seconds, summed over steps
    std::map<std::string, long> gprof_n;
    void gmark(const char *name, int t) { gmarks.push_back({name, t, qs[t].ext_oneapi_submit_barrier()}); }
    // kernel-type profile (Options::kprof): start-to-end time of every launch
    struct KEv { const char *name; sycl::event e; };
    std::vector<KEv> kevs;
    std::map<std::string, double> kprof_t;
    std::map<std::string, long> kprof_n;
    template <typename K> static const char *kname() {
        static const std::string n = [] {
            int st = 0;
            char *d = abi::__cxa_demangle(typeid(K).name(), nullptr, nullptr, &st);
            std::string r = st == 0 && d ? d : typeid(K).name();
            std::free(d);
            for (const char *pre : {"ops41sycl::", "own41::"})
                for (size_t q; (q = r.find(pre)) != std::string::npos;) r.erase(q, std::strlen(pre));
            return r;
        }();
        return n.c_str();
    }
    void kev(int tile, const char *name, const sycl::event &e) {
        if (o.kprof && (o.tp <= 1 || tile == o.prof_card)) kevs.push_back({name, e}); // tp: one card's kernels
    }
    void gprof_collect() {
        if (!o.gprof) return;
        for (auto &k : kevs) {
            k.e.wait();
            const long long a = (long long)k.e.get_profiling_info<sycl::info::event_profiling::command_start>();
            const long long b = (long long)k.e.get_profiling_info<sycl::info::event_profiling::command_end>();
            kprof_t[k.name] += (b - a) * 1e-9;
            kprof_n[k.name] += 1;
        }
        kevs.clear();
        std::vector<long long> last(TILES, -1);
        for (auto &m : gmarks) {
            m.e.wait();
            const long long e = (long long)m.e.get_profiling_info<sycl::info::event_profiling::command_end>();
            if (last[m.t] >= 0) { gprof_t[m.name] += (e - last[m.t]) * 1e-9; gprof_n[m.name] += 1; }
            last[m.t] = e;
        }
        gmarks.clear();
    }
    // pace: 0 = never wait between operators, 1 = wait at the end of each
    // layer, 2 = wait at every operator-group mark (OWN_PACE)
    int pace = 0;
    // keep_warm (OWN_KEEP_WARM): 0 off; 1 = after each layer, run a tiny kernel
    // on every OTHER active card and wait for it; 2 = only on the next card in
    // line. An idle card clocks down within a fraction of a second and then
    // runs its whole slice of layers ~40 % slower. No power setting is changed.
    int keep_warm = 1;
    void warm(int t) {
        if (!keep_warm) return;
        int next = -1;
        for (int k = 1; k <= TILES; ++k) {
            int t2 = (t + k) % TILES;
            if (active[t2] && t2 != t) { next = t2; break; }
        }
        for (int t2 = 0; t2 < TILES; ++t2) {
            if (!active[t2] || t2 == t) continue;
            if (keep_warm == 2 && t2 != next) continue;
            float *p = sc[t2].warm;
            qs[t2].submit([&](sycl::handler &hh) {
                hh.parallel_for(sycl::nd_range<1>(warm_items, 32), [=](sycl::nd_item<1> it) {
                    size_t g = it.get_global_linear_id();
                    p[g & 1023] = float(g);
                });
            });
        }
        for (int t2 = 0; t2 < TILES; ++t2) {
            if (!active[t2] || t2 == t) continue;
            if (keep_warm == 2 && t2 != next) continue;
            qs[t2].wait();
        }
    }
    size_t warm_items = 32;
    // wait right after every host->card copy (OWN_H2D_WAIT, default on): on this
    // stack a host-pointer copy left pending slows every launch behind it
    int hc_fin_form = 0; // OWN_HC_FIN=1: the stream mix's finish by constant-lane broadcasts (HcMixFinishSG::run_bc)
    bool h2d_wait = true;
    // tp: the step's head (final norm, output rows, argmax) is skipped; a prompt token whose
    // next word nobody reads (every prompt token but the last). decode_step returns -1 then.
    bool skip_head = false;
    // tp: token index inside a multi-token step (0 in one-token steps); the card's position is pos + tokoff
    static constexpr int MTX = 16; // tokens per multi-token step, at most
    long tokoff[TILES] = {};
    long cpos(int c) const { return pos + tokoff[c]; }
    void prof(const char *name, int t) {
        if (o.tp > 1) { // card 0's marks only; never a host wait (a card may be waiting for a peer not yet submitted)
            if (o.gprof && t == o.prof_card) gmark(name, t);
            return;
        }
        if (o.gprof) {
            gmark(name, t);
            return;
        }
        if (!prof_on) {
            if (pace >= 2) qs[t].wait();
            return;
        }
        qs[t].wait();
        double n = now_s();
        prof_t[name] += n - prof_last;
        prof_last = n;
    }

    // trace (same record format and tags as cpu_run_v41; OWN_TRACE)
    FILE *trace_f = nullptr;
    bool trace_on = false;
    int trace_step = 0;

    // segment mode: reference streams + pre-mix enter at the first layer
    void set_streams(const float *s4h, const float *pre4) {
        int t = o.layer_begin < o.layer_end ? tile_of_layer(o.layer_begin) : HEAD_TILE;
        for (size_t i = 0; i < 4 * (size_t)g.h; ++i) h_streams[i] = Act::wr(s4h[i]);
        if (o.tp > 1) {
            for (int c = 0; c < o.tp; ++c) {
                qs[c].memcpy(streams[c], h_streams.data(), sizeof(act_t) * 4 * (size_t)g.h);
                qs[c].memcpy(sc[c].cur_pre, pre4, 16);
                qs[c].wait();
            }
            return;
        }
        qs[t].memcpy(streams[t], h_streams.data(), sizeof(act_t) * 4 * (size_t)g.h);
        qs[t].memcpy(sc[t].cur_pre, pre4, 16);
        qs[t].wait();
        cur = t;
    }
    // segment mode: a row published by a source layer outside the range
    void append_published(int si, const float *ckv_row, const float *ik_row) {
        std::vector<uint16_t> kvr(g.hd), ikr(128);
        for (int i = 0; i < g.hd; ++i) kvr[i] = ops41::bf16b(ckv_row[i]);
        for (int i = 0; i < 128; ++i) ikr[i] = ops41::bf16b(ik_row[i]);
        append_row_host(si, kvr.data(), ikr.data());
        if (o.tp > 1) // host rows reach the cards through sync_rows; the cards' row counts follow
            for (int c = 0; c < o.tp; ++c) ++tlen[c][si];
    }

    // The 24 hashed engram rows per engram layer are cold 4 KiB reads from the
    // 135 GB table (about 2 ms per layer when taken inline). Their ids depend
    // only on the token history, so ask the kernel for them at step start.
    void engram_prefetch() {
        static const long page = sysconf(_SC_PAGESIZE);
        auto l = iq3::layout(iq3::Type::Q5_K);
        for (int li = 0; li < 2; ++li) {
            int L = li == 0 ? 1 : 14;
            if (L < o.layer_begin || L >= o.layer_end || !eng_base[li]) continue;
            if ((long)comp_ids.size() <= pos) continue;
            int64_t ids[24];
            engram_hash((int)pos, li, ids);
            for (int c = 0; c < 24; ++c) {
                uintptr_t a = (uintptr_t)(eng_base[li] + (size_t)ids[c] * l.bytes);
                uintptr_t a0 = a & ~(uintptr_t)(page - 1);
                madvise((void *)a0, (size_t)(a + l.bytes - a0), MADV_WILLNEED);
            }
        }
    }

    // decode one token; returns the next token id (-1 when the head is not loaded)
    int32_t decode_step(int32_t token) {
        if (o.tp > 1) return decode_step_tp(token);
        const int H_ = g.h;
        engram_prefetch();
        if (o.layer_begin == 0) {
            const auto &te = we("token_embd.weight");
            const uint8_t *row = (const uint8_t *)wgt[0].at("token_embd.weight").p + (size_t)token * wrb(te);
            launch(0, H_, 32, ops41sycl::EmbedRowA<Act>{te.type, H_}, row, sc[0].x);
            launch(0, H_, 32, ops41sycl::Broadcast4A<Act>{H_}, (const act_t *)sc[0].x, streams[0]);
            float pm[4] = {1, 0, 0, 0};
            qs[0].memcpy(sc[0].cur_pre, pm, 16);
            qs[0].wait();
            cur = 0;
            tra(0, TT_EMBED, 0, streams[0], 4 * (size_t)H_);
        }
        prof_begin(cur);
        for (int L = o.layer_begin; L < o.layer_end; ++L) {
            int t = tile_of_layer(L);
            if (t != cur) { migrate(t); prof("migrate", t); }
            layer(L, t);
        }
        int32_t next = -1;
        if (o.head) {
            if (cur != HEAD_TILE) migrate(HEAD_TILE);
            auto &s = sc[HEAD_TILE];
            launch(HEAD_TILE, H_, 32, ops41sycl::HcPreA<Act>{H_}, (const act_t *)streams[HEAD_TILE],
                   (const float *)s.cur_pre, s.x);
            rmsnorm(HEAD_TILE, s.x, "output_norm.weight", H_, s.xn);
            gemv(HEAD_TILE, "output.weight", s.xn, logits_, true);
            if (o.small_fast) { // same result as Argmax (order-free definition), test_small_v41_device.cpp
                const int G = (g.vocab + AM_CH - 1) / AM_CH;
                launch_sg(HEAD_TILE, G, ops41sycl::ArgmaxP1{g.vocab, AM_CH}, (const float *)logits_, am_v_, am_i_);
                launch_sg(HEAD_TILE, 1, ops41sycl::ArgmaxP2{G}, (const float *)am_v_, (const int32_t *)am_i_, tok_out_);
            } else {
                launch_sg(HEAD_TILE, 1, ops41sycl::Argmax{g.vocab}, (const float *)logits_, tok_out_,
                          (float *)nullptr);
            }
            qs[HEAD_TILE].memcpy(&next, tok_out_, 4).wait();
            prof("head", HEAD_TILE);
            tra(40, TT_FINAL_N, HEAD_TILE, s.xn, H_);
            trf(40, TT_LOGITS, HEAD_TILE, logits_, g.vocab);
        } else {
            qs[cur].wait();
        }
        ++pos;
        return next;
    }

    // top-5 of the last logits (debug print; D2H of the whole vector)
    std::vector<std::pair<int, float>> top5() {
        std::vector<float> lg(g.vocab);
        if (o.tp > 1)
            for (int c = 0; c < o.tp; ++c)
                qs[c].memcpy(lg.data() + tv0[c], tlog[c], (size_t)(tv1[c] - tv0[c]) * 4).wait();
        else
            qs[HEAD_TILE].memcpy(lg.data(), logits_, (size_t)g.vocab * 4).wait();
        std::vector<int> ord(g.vocab);
        for (int i = 0; i < g.vocab; ++i) ord[i] = i;
        std::partial_sort(ord.begin(), ord.begin() + 5, ord.end(),
                          [&](int a, int b) { return lg[a] > lg[b]; });
        std::vector<std::pair<int, float>> r;
        for (int i = 0; i < 5; ++i) r.push_back({ord[i], lg[ord[i]]});
        return r;
    }

    // state handoff: upload rings + caches from the CPU runner's dump.
    void load_state(long pos_, const long lens[4],
                    const std::vector<std::vector<float>> &rings, // [40][128*512]
                    const std::vector<std::vector<float>> &ckv,   // [4][rows*512]
                    const std::vector<std::vector<float>> &ik,    // [4][rows*128]
                    const float kv_state[4][1024], const float score_state[4][1024]) {
        pos = pos_;
        std::vector<uint16_t> tmp;
        auto up16 = [&](void *dst, const float *src, size_t n, int t) {
            if (!n) return;
            tmp.resize(n);
            for (size_t i = 0; i < n; ++i) tmp[i] = ops41::bf16b(src[i]);
            qs[t].memcpy(dst, tmp.data(), n * 2).wait(); // tmp is reused: wait
        };
        for (int L = o.layer_begin; L < o.layer_end; ++L) {
            if (o.tp > 1)
                for (int c = 0; c < o.tp; ++c) up16(ring[c][L], rings[L].data(), rings[L].size(), c);
            else
                up16(ring[tile_of_layer(L)][L], rings[L].data(), rings[L].size(), tile_of_layer(L));
        }
        static const int srcs[4] = {2, 8, 14, 20};
        for (int i = 0; i < 4; ++i) {
            src_len[i] = lens[i];
            size_t cap = (i == 3 ? (size_t)max_seq + 2 : (size_t)max_seq / 2 + 2);
            if ((size_t)lens[i] > cap) throw std::runtime_error("state exceeds max_seq");
            h_ckv[i].resize(ckv[i].size());
            h_ik[i].resize(ik[i].size());
            for (size_t k = 0; k < ckv[i].size(); ++k) h_ckv[i][k] = ops41::bf16b(ckv[i][k]);
            for (size_t k = 0; k < ik[i].size(); ++k) h_ik[i][k] = ops41::bf16b(ik[i][k]);
            for (int t = 0; t < TILES; ++t) synced[t][i] = 0; // cards catch up on first use
            int st = o.tp > 1 ? 0 : tile_of_layer(srcs[i]); // tp: kv_state goes to every card below
            if (o.tp > 1) {
                for (int c = 0; c < o.tp; ++c) {
                    tlen[c][i] = lens[i];
                    if (srcs[i] >= o.layer_begin && srcs[i] < o.layer_end) {
                        qs[c].memcpy(sc[c].kv_state + (size_t)i * 2 * g.hd, kv_state[i], 1024 * 4);
                        qs[c].memcpy(sc[c].score_state + (size_t)i * 2 * g.hd, score_state[i], 1024 * 4);
                        qs[c].wait();
                    }
                }
                continue;
            }
            if (srcs[i] >= o.layer_begin && srcs[i] < o.layer_end) {
                qs[st].memcpy(sc[st].kv_state + (size_t)i * 2 * g.hd, kv_state[i], 1024 * 4);
                qs[st].memcpy(sc[st].score_state + (size_t)i * 2 * g.hd, score_state[i], 1024 * 4);
                qs[st].wait();
            }
        }
    }

    flash41::GeometryV41 g;
    int max_seq;
    Options o;

private:
    // ---- device resources ----------------------------------------------------
    bool active[TILES] = {};
    std::string pci[TILES];
    std::vector<sycl::context> ctxs;
    std::vector<sycl::device> devs;
    std::vector<sycl::queue> qs;
    std::vector<void *> owned[TILES];
    std::unordered_map<std::string, DevPtr> wgt[TILES]; // per card (tp: every card holds its slice)
    const WeightTab *W = nullptr;
    act_t *streams[TILES] = {};
    uint16_t *ckv_mirror[TILES][4] = {};
    uint16_t *ik_mirror[TILES][4] = {};
    int32_t *cidx_mirror[TILES][8] = {};
    uint16_t *ring[TILES][40] = {}; // window ring per card per layer
    float *cos_yarn[TILES] = {}, *sin_yarn[TILES] = {}, *cos_base[TILES] = {}, *sin_base[TILES] = {};
    float *logits_ = nullptr;
    int32_t *tok_out_ = nullptr;
    static constexpr int AM_CH = 512; // argmax pass-1 span per sub-group
    float *am_v_ = nullptr;
    int32_t *am_i_ = nullptr;
    int cur = 0;
    std::vector<act_t> h_streams;
    // Host copies of the state every card mirrors (KV rows are BF16 in both
    // activation modes). A card is brought up to date only when a layer on
    // it is about to read the state, with non-blocking uploads: the old
    // design copied every new row and index list to all six cards and waited
    // on each queue, about 80 blocking round trips per token.
    std::vector<uint16_t> h_ckv[4], h_ik[4]; // append-only; capacity reserved, so pointers stay valid
    long synced[TILES][4] = {};              // rows already on each card
    std::vector<int32_t> h_cidx[8][4];       // 4-deep ring per slot: a pending upload never sees a rewrite
    unsigned cidx_ver[8] = {}, tile_cidx_ver[TILES][8] = {};
    std::vector<act_t> h_eng[TILES][2][2];   // engram rows per card, two alternating buffers per engram layer
    unsigned eng_flip[TILES][2] = {};
    std::vector<uint8_t> h_engr[TILES][2][2]; // eng_dev: the raw rows (ordinary host memory, copied like h_eng;
                                              // pinned host buffers were in the run that faulted, e72), same alternation
    uint8_t *tengr[TILES][2] = {};           // eng_dev: the raw rows on the card
  public:
    double eng_t[TILES] = {};                // host time in the engram row upload per card (seconds; the caller resets)
    long eng_n[TILES] = {};
    double eng_tq[TILES] = {};               // of which OWN_ENG_DEV's copy + decode launch calls
  private:
    std::vector<uint8_t> cand_host; // layer-20 candidate mask of the current step
    bool cand_valid = false;

    static std::string gib(size_t b) {
        char s[32];
        std::snprintf(s, sizeof s, "%.2f", b / 1073741824.0);
        return s;
    }
    template <typename T> T *dalloc(int t, size_t count, bool zero = true) {
        T *p = sycl::malloc_device<T>(count, qs[t]);
        if (!p)
            throw std::runtime_error("device allocation of " + gib(count * sizeof(T)) + " GiB failed on card " +
                                     pci[t]);
        owned[t].push_back(p);
        if (zero) qs[t].memset(p, 0, count * sizeof(T));
        touch(t, p);
        return p;
    }
    // One launch with p as a direct pointer argument, so the driver makes p's allocation resident on
    // card t. own_run sets DisableIndirectAccess=1: the driver then stops re-registering every
    // allocation on each launch of a kernel its compiler marks "indirect" (any data-dependent
    // address, a pointer in a by-value struct, a program-scope table). That bookkeeping ran under a
    // lock shared by all cards' host threads (six threads: ~52 -> ~60 tok/s without it). Every
    // allocation the engine owns or opens (dalloc, the error words, the peers' arenas) passes
    // through here once, so none depends on some later kernel taking it as a direct argument.
    int touch_zero = 0;
    void touch(int t, void *p) {
        uint8_t *b = (uint8_t *)p;
        const int z = touch_zero; // 0 at run time; the device compiler cannot drop the argument
        qs[t].single_task([=] {
            if (z) b[0] = 0;
        });
    }

    struct Scratch {
        act_t *x, *xn;               // sublayer input, normalized
        act_t *qa, *qn, *q;          // q LoRA
        act_t *kv, *kvn;             // latent kv row
        act_t *qi, *wv;              // indexer query / head weights
        float *score;
        int64_t *lens;
        float *router;                  // f32 router logits
        uint32_t *ids;
        float *prob;
        act_t *expg, *expu, *act, *expd;
        act_t *shg, *shu, *sha, *shd;
        float *of;                      // attention output, f32
        float *attn_w;                  // [heads][640] attention scores -> weights
        act_t *obuf, *oa, *ob;       // bf16 attn out, o_a out, sublayer output
        act_t *cw, *scg, *latent, *kk;
        float *kv_state, *score_state;  // [4 sources][2 slots][hd]
        float *pre_a, *post_a, *comb_a, *pre_f, *post_f, *comb_f, *cur_pre;
        double *d25;                    // hc_mix: (24 dots + sum of squares) x HC_SEG segments
        float *rs, *rsb;                // router scores, scores + bias
        float *warm;                    // keep-warm scribble buffer
        int32_t *idxs_cat, *widx;
        act_t *old, *eng_rows, *kvbuf;
        uint8_t *cand;                  // dev_index: layer-20 candidate mask of the current step
    };
    Scratch sc[TILES] = {};

    void scratch_alloc(int t) {
        auto &s = sc[t];
        auto md = [&](size_t n) { return dalloc<act_t>(t, n); };
        auto mf = [&](size_t n) { return dalloc<float>(t, n); };
        s.x = md(g.h); s.xn = md(g.h);
        s.qa = md(g.qrank); s.qn = md(g.qrank);
        s.q = md((size_t)g.qh * g.hd);
        s.kv = md(g.hd); s.kvn = md(g.hd);
        s.qi = md(32 * 128); s.wv = md(32);
        s.score = mf((size_t)max_seq + 64);
        s.lens = dalloc<int64_t>(t, 1);
        s.router = mf(g.experts);
        s.ids = dalloc<uint32_t>(t, 6);
        s.prob = mf(6);
        s.expg = md((size_t)6 * g.mid); s.expu = md((size_t)6 * g.mid);
        s.act = md((size_t)6 * g.mid); s.expd = md((size_t)6 * g.h);
        s.shg = md(g.mid); s.shu = md(g.mid); s.sha = md(g.mid); s.shd = md(g.h);
        s.of = mf((size_t)g.qh * g.hd);
        s.attn_w = mf((size_t)g.qh * 640);
        s.obuf = md((size_t)g.qh * g.hd);
        s.oa = md(g.ototal); s.ob = md(g.h);
        s.cw = md(g.hd); s.scg = md(g.hd); s.latent = md(g.hd); s.kk = md(128);
        s.kv_state = mf((size_t)4 * 2 * g.hd); s.score_state = mf((size_t)4 * 2 * g.hd);
        s.pre_a = mf(4); s.post_a = mf(4); s.comb_a = mf(16);
        s.pre_f = mf(4); s.post_f = mf(4); s.comb_f = mf(16);
        s.d25 = dalloc<double>(t, 25 * HC_SEG); s.cur_pre = mf(4);
        s.rs = mf(g.experts); s.rsb = mf(g.experts);
        s.warm = mf(1024);
        s.idxs_cat = dalloc<int32_t>(t, 640); s.widx = dalloc<int32_t>(t, 128);
        s.old = md((size_t)4 * g.h);
        s.eng_rows = md((size_t)24 * g.engram_dim); s.kvbuf = md((size_t)5 * g.h);
        s.cand = dalloc<uint8_t>(t, (size_t)max_seq + 64);
    }

    const WeightTab::E &we(const std::string &n) const { return W->at(n); }
    size_t wrb(const WeightTab::E &e) const { return W->row_bytes(e); }
    template <typename T = uint8_t> const T *wp(int t, const std::string &n) const {
        auto it = wgt[t].find(n);
        if (it == wgt[t].end()) throw std::invalid_argument("weight not uploaded " + n);
        return (const T *)it->second.p;
    }

    // ---- launch helpers -----------------------------------------------------
    // arm_xtail(exchange) before the producer's launch, end_xtail() after it: with xtail the producer's launch
    // (launch / launch_rows without local memory) ends with the exchange (ops41sycl::xchg_tail); otherwise, or
    // when no such launch took it, end_xtail() runs it as its own launch after the producer
    struct XTail {
        bool on = false;      // the next launch takes the exchange
        bool pending = false; // armed and not yet run
        unsigned off = 0, stride = 0, nslot = 0, r0 = 0, r1 = 0;
        int part = -1;
    };
    XTail xt[TILES];
    uint32_t *xcnt[TILES] = {};
    void arm_xtail(int c, unsigned off, unsigned stride, unsigned nslot, unsigned r0, unsigned r1, int part) {
        xt[c] = {o.xtail && !use_pull(part, nslot), true, off, stride, nslot, r0, r1, part};
    }
    void end_xtail(int c) {
        const XTail t = xt[c];
        xt[c].on = xt[c].pending = false;
        if (t.pending) xchg(c, t.off, t.stride, t.nslot, t.r0, t.r1, 0, 0, t.part);
    }
    template <bool SG32, typename K, typename... A> void launch_xt(int c, sycl::nd_range<1> nr, K k, A... args) {
        const XTail t = xt[c];
        xt[c].on = xt[c].pending = false;
        float *P[6] = {};
        for (int d = 0; d < o.tp; ++d) P[d] = (float *)xpeer[c][d];
        float *p0 = P[0], *p1 = P[1], *p2 = P[2], *p3 = P[3], *p4 = P[4], *p5 = P[5];
        const uint32_t seq = ++xseq[c];
        const ops41sycl::XchgP x{o.tp, c, t.off, t.stride, t.nslot, t.r0, t.r1, seq, XSPIN, 0};
        uint32_t *cnt = xcnt[c], *err = xerr[c];
        auto e = qs[c].submit([&](sycl::handler &hh) {
            if constexpr (SG32)
                hh.parallel_for(nr, [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                    k(it, args...);
                    ops41sycl::xchg_tail(it, x, cnt, p0, p1, p2, p3, p4, p5, err);
                });
            else
                hh.parallel_for(nr, [=](sycl::nd_item<1> it) {
                    k(it, args...);
                    ops41sycl::xchg_tail(it, x, cnt, p0, p1, p2, p3, p4, p5, err);
                });
        });
        kev(c, kname<K>(), e);
    }
    template <typename K, typename... A>
    void launch(int tile, size_t nwork, size_t lwork, K k, A... args) {
        size_t n = (nwork + lwork - 1) / lwork * lwork; // B70 rejects non-uniform groups
        if (xt[tile].on) return launch_xt<false>(tile, sycl::nd_range<1>(n, lwork), k, args...);
        auto e = qs[tile].submit([&](sycl::handler &hh) {
            hh.parallel_for(sycl::nd_range<1>(n, lwork), [=](sycl::nd_item<1> it) { k(it, args...); });
        });
        kev(tile, kname<K>(), e);
    }
    // kernels built on 32-lane sub-group reductions: one work-group == one sub-group
    template <typename K, typename... A> void launch_sg(int tile, size_t groups, K k, A... args) {
        auto e = qs[tile].submit([&](sycl::handler &hh) {
            hh.parallel_for(sycl::nd_range<1>(groups * 32, 32),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, args...); });
        });
        kev(tile, kname<K>(), e);
    }
    // launch_sg plus work-groups that prefetch [p, p + bytes) into the card's cache (WithPf); plain launch_sg
    // when there is nothing to prefetch
    struct Pf {
        const void *p = nullptr;
        size_t bytes = 0;
    };
    Pf pf_of(int tile, const std::string &wn) {
        if (!o.pf) return {};
        const auto &dp = wgt[tile].at(wn);
        return {dp.p, dp.bytes};
    }
    template <typename K, typename... A> void launch_sg_pf(int tile, size_t groups, Pf pf, K k, A... args) {
        if (!pf.p || !pf.bytes) return launch_sg(tile, groups, k, args...);
        const uintptr_t a = (uintptr_t)pf.p & ~(uintptr_t)63;
        const unsigned lines = (unsigned)(((uintptr_t)pf.p + pf.bytes - a + 63) / 64);
        const size_t npg = std::min<size_t>(1024, (lines + 127) / 128);
        launch_sg(tile, groups + npg, ops41sycl::WithPf<K>{k, (unsigned)groups, (const uint8_t *)a, lines}, args...);
    }
    // one work-group of `items` (a multiple of 32), 32-lane sub-groups, no local memory
    template <typename K, typename... A> void launch_wg(int tile, size_t items, K k, A... args) {
        auto e = qs[tile].submit([&](sycl::handler &hh) {
            hh.parallel_for(sycl::nd_range<1>(items, items),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, args...); });
        });
        kev(tile, kname<K>(), e);
    }
    // one work-group of `items` (a multiple of 32) with SLM floats of local
    // memory passed as the last argument
    template <size_t SLM, typename K, typename... A> void launch_local(int tile, size_t items, K k, A... args) {
        auto e = qs[tile].submit([&](sycl::handler &hh) {
            sycl::local_accessor<float, 1> lt(SLM, hh);
            hh.parallel_for(sycl::nd_range<1>(items, items), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k(it, args..., &lt[0]);
            });
        });
        kev(tile, kname<K>(), e);
    }
    // packed-row kernels: 16 sub-groups (rows) per work-group, optional local
    // table; max_wg > 0 caps the work-groups (the routed kernels loop over rows)
    template <size_t SLM, size_t WG = 512, typename K, typename... A>
    void launch_rows(int tile, size_t rows, size_t max_wg, K k, A... args) {
        constexpr size_t PER = WG / 32;
        size_t nwg = (rows + PER - 1) / PER;
        if (max_wg && nwg > max_wg) nwg = max_wg;
        const size_t n = nwg * WG;
        if constexpr (SLM == 0)
            if (xt[tile].on) return launch_xt<true>(tile, sycl::nd_range<1>(n, WG), k, args...);
        auto e = qs[tile].submit([&](sycl::handler &hh) {
            if constexpr (SLM > 0) {
                sycl::local_accessor<float, 1> lt(SLM, hh);
                hh.parallel_for(sycl::nd_range<1>(n, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                    k(it, args..., &lt[0]);
                });
            } else {
                hh.parallel_for(sycl::nd_range<1>(n, WG),
                                [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, args...); });
            }
        });
        kev(tile, kname<K>(), e);
    }
#ifndef OWN41_ACT_BF16
    // dense Q8_0 over packed rows; xn > 0 = grouped (row r reads x + (r / xn) * cols)
    void gemv_q8p(int tile, const WeightTab::E &e, const void *w, const act_t *x, act_t *y, unsigned rows,
                  unsigned xn, unsigned cols) {
        switch (cols) {
#define X(COLS) \
    case COLS: launch_rows<0>(tile, rows, 0, ops41sycl::GemvQ8P<COLS / 32, Act>{rows, xn}, (const uint8_t *)w, x, y); break;
            X(1280) X(2304) X(4096) X(5120) X(8192)
#undef X
        default: throw std::runtime_error("no packed Q8_0 kernel for cols " + std::to_string(cols));
        }
        (void)e;
    }
    // any packed dense format (pk41::packable); xn as gemv_q8p
    void gemv_kp(int tile, const WeightTab::E &e, const void *w, const act_t *x, act_t *y, unsigned rows, unsigned xn,
                 unsigned cols, const std::string &wn) {
        const auto *wb = (const uint8_t *)w;
#define X(KERN, NB)                                                                                        \
    if (cols == NB * 256) {                                                                                \
        launch_rows<0>(tile, rows, 0, ops41sycl::KERN<NB, Act>{rows, xn}, wb, x, y);                       \
        return;                                                                                            \
    }
        if (e.type == iq3::Type::Q8_0) return gemv_q8p(tile, e, w, x, y, rows, xn, cols);
        if (e.type == iq3::Type::Q6_K) { X(GemvQ6KP, 5) X(GemvQ6KP, 16) X(GemvQ6KP, 20) X(GemvQ6KP, 24) X(GemvQ6KP, 32) }
        if (e.type == iq3::Type::Q5_K) { X(GemvQ5KP, 9) X(GemvQ5KP, 20) }
        if (e.type == iq3::Type::F32 && cols == 5120 && !xn) {
            launch_rows<0>(tile, rows, 0, ops41sycl::GemvH16P<160, Act>{rows}, wb, x, y);
            return;
        }
#undef X
        throw std::runtime_error("packed dense kernel missing: " + wn);
    }
    // gemv_kp plus the extra rows EX (sub-group rows, see HcDotsRows) in the same launch; the extra rows
    // come first so a long one starts at once. Every row runs the same per-row code as alone.
    template <typename DK, typename EX>
    void launch_dense_ex(int tile, DK dk, const uint8_t *w, const act_t *x, act_t *y, EX ex) {
        using R = ops41sycl::RowsPair<EX, ops41sycl::DenseRows<DK>>;
        launch_rows<0>(tile, ex.n() + dk.rows, 0, ops41sycl::RowsP<R>{R{ex, ops41sycl::DenseRows<DK>{dk, w, x, y}}});
    }
    template <typename EX>
    void gemv_kp_ex(int tile, const WeightTab::E &e, const void *w, const act_t *x, act_t *y, unsigned rows,
                    unsigned xn, unsigned cols, const std::string &wn, EX ex) {
        const auto *wb = (const uint8_t *)w;
#define X(KERN, NB)                                                                                        \
    if (cols == NB * 256) return launch_dense_ex(tile, ops41sycl::KERN<NB, Act>{rows, xn}, wb, x, y, ex);
#define XQ(COLS)                                                                                           \
    if (cols == COLS) return launch_dense_ex(tile, ops41sycl::GemvQ8P<COLS / 32, Act>{rows, xn}, wb, x, y, ex);
        if (e.type == iq3::Type::Q8_0) { XQ(1280) XQ(2304) XQ(4096) XQ(5120) XQ(8192) }
        if (e.type == iq3::Type::Q6_K) { X(GemvQ6KP, 5) X(GemvQ6KP, 16) X(GemvQ6KP, 20) X(GemvQ6KP, 24) X(GemvQ6KP, 32) }
        if (e.type == iq3::Type::Q5_K) { X(GemvQ5KP, 9) X(GemvQ5KP, 20) }
        if (e.type == iq3::Type::F32 && cols == 5120 && !xn)
            return launch_dense_ex(tile, ops41sycl::GemvH16P<160, Act>{rows}, wb, x, y, ex);
#undef XQ
#undef X
        throw std::runtime_error("packed dense kernel missing: " + wn);
    }
    // gemv() / gemv_part() with extra rows (packed weights, or the F32 router rows)
    template <typename EX> void gemv_ex(int tile, const std::string &wn, const act_t *x, act_t *y, EX ex) {
        const auto &e = we(wn);
        const auto &dp = wgt[tile].at(wn);
        if (dp.packed) return gemv_kp_ex(tile, e, dp.p, x, y, (unsigned)e.rows, 0, (unsigned)e.cols, wn, ex);
        if (o.packed && e.type == iq3::Type::F32 && e.cols == 5120)
            return launch_dense_ex(tile, ops41sycl::GemvF32P<160, Act>{(unsigned)e.rows}, (const uint8_t *)dp.p, x, y, ex);
        throw std::runtime_error("no fused-row kernel for " + wn);
    }
    template <typename EX> void gemv_part_ex(int t, const std::string &wn, const act_t *x, act_t *y, EX ex) {
        const auto &e = we(wn);
        const auto &dp = wgt[t].at(wn);
        if (!dp.packed) throw std::runtime_error("tensor-parallel slice needs packed rows: " + wn);
        gemv_kp_ex(t, e, dp.p, x, y, dp.nrows, 0, (unsigned)e.cols, wn, ex);
    }
    // stream mix riding in later launches (see HcDotsRows); false: the mix runs as its own two launches
    bool hc_rides(int t, const std::string &prefix) const {
        return o.hc_ride && o.small_fast && !o.hc_legacy && g.h == 5120 && HC_SEG == 8 && al16(streams[t]) &&
               al16(wp<float>(t, prefix + "fn.weight"));
    }
    // two packed matrices of one format, 5120 wide, reading the same x (query-a and key/value), plus the
    // extra rows EX, in one launch; false (nothing launched) for any other shape
    template <typename EX>
    bool gemv_pair_ex(int t, const std::string &wa, act_t *ya, const std::string &wb, act_t *yb, const act_t *x, EX ex) {
        const auto &ea = we(wa), &eb = we(wb);
        const auto &da = wgt[t].at(wa), &db = wgt[t].at(wb);
        if (!da.packed || !db.packed || ea.type != eb.type || ea.cols != 5120 || eb.cols != 5120) return false;
        auto go = [&](auto dka, auto dkb) {
            using DK = decltype(dka);
            using D = ops41sycl::DenseRows<DK>;
            using R = ops41sycl::RowsPair<EX, ops41sycl::RowsPair<D, D>>;
            const R r{ex, {D{dka, (const uint8_t *)da.p, x, ya}, D{dkb, (const uint8_t *)db.p, x, yb}}};
            launch_rows<0>(t, r.n(), 0, ops41sycl::RowsP<R>{r});
        };
        if (ea.type == iq3::Type::Q8_0)
            go(ops41sycl::GemvQ8P<160, Act>{da.nrows, 0}, ops41sycl::GemvQ8P<160, Act>{db.nrows, 0});
        else if (ea.type == iq3::Type::Q6_K)
            go(ops41sycl::GemvQ6KP<20, Act>{da.nrows, 0}, ops41sycl::GemvQ6KP<20, Act>{db.nrows, 0});
        else if (ea.type == iq3::Type::Q5_K)
            go(ops41sycl::GemvQ5KP<20, Act>{da.nrows, 0}, ops41sycl::GemvQ5KP<20, Act>{db.nrows, 0});
        else
            return false;
        return true;
    }
    // the 5,120-wide norm (four sub-group parts, RmsNormPS) with extra rows EX in one launch: the norm is a
    // serial chain on four sub-groups, so rows that do not need its output fill the card meanwhile
    template <typename EX> bool norm_ex(int c, const act_t *x, const std::string &wn, act_t *y, EX ex) {
        const float *w = wp<float>(c, wn);
        if (g.h != 5120 || !o.small_fast || !al16(x) || !al16(w) || !al16(y) || x == y) return false;
        using R = ops41sycl::RowsPair<ops41sycl::NormRows<5120, 4>, EX>;
        const R r{{x, w, y}, ex};
        launch_rows<0>(c, r.n(), 0, ops41sycl::RowsP<R>{r});
        return true;
    }
    // tp phase 0 in four launches (see tp_phase): shapes the fused forms are written for
    bool attn_in_diet(int c, const std::string &p) const {
        const auto &s = sc[c];
        if (!o.diet || !o.small_fast || g.qrank != 1280 || g.hd != 512) return false;
        const auto &ea = we(p + "attn_q_a.weight"), &eb = we(p + "attn_kv.weight");
        const auto &da = wgt[c].at(p + "attn_q_a.weight"), &db = wgt[c].at(p + "attn_kv.weight");
        if (!da.packed || !db.packed || ea.type != eb.type || ea.cols != 5120 || eb.cols != 5120) return false;
        if (ea.type != iq3::Type::Q8_0 && ea.type != iq3::Type::Q6_K && ea.type != iq3::Type::Q5_K) return false;
        return al16(s.qa) && al16(s.qn) && al16(s.kv) && al16(s.kvn) && s.qa != s.qn && s.kv != s.kvn &&
               al16(wp<float>(c, p + "attn_q_a_norm.weight")) && al16(wp<float>(c, p + "attn_kv_a_norm.weight"));
    }
    // HcPostPreP may stand in for hc_post + the next sublayer's HcPreA
    bool post_pre_ok() const { return o.diet && o.small_fast && !o.hc_legacy; }
    bool x_ready[TILES] = {}; // s.x holds the next pre-norm's input (HcPostPreP ran)
    ops41sycl::HcDotsRows<5120, HC_SEG> hc_dots(int t, const std::string &prefix) {
        return {(const float *)streams[t], wp<float>(t, prefix + "fn.weight"), sc[t].d25};
    }
    ops41sycl::HcMixFinishSG hc_fin_k() const {
        ops41sycl::HcMixFinishSG k{g.h, HC_SEG};
        k.form = hc_fin_form;
        return k;
    }
    ops41sycl::HcFinishRows hc_finish(int t, const std::string &prefix, float *pre, float *post, float *comb) {
        return {hc_fin_k(), (const double *)sc[t].d25, wp<float>(t, prefix + "scale.weight"),
                wp<float>(t, prefix + "base.weight"), pre, post, comb};
    }
#endif
    // One kernel per weight format (OWN_GENERIC_KERNELS=1 selects the
    // runtime-type kernels instead; outputs are bit-identical either way).
    void gemv(int tile, const std::string &wn, const act_t *x, void *y, bool f32out = false) {
        const auto &e = we(wn);
        const unsigned rows = (unsigned)e.rows, cols = (unsigned)e.cols;
#ifndef OWN41_ACT_BF16
        if (const auto &dp = wgt[tile].at(wn); dp.packed) { // f32 activations: f32out is the same store
            gemv_kp(tile, e, dp.p, x, (act_t *)y, rows, 0, cols, wn);
            return;
        }
        // F32 rows need no packing: block-read kernel (the router logits, 5120 columns)
        if (o.packed && e.type == iq3::Type::F32 && cols == 5120) {
            launch_rows<0>(tile, rows, 0, ops41sycl::GemvF32P<160, Act>{rows}, (const uint8_t *)wp(tile, wn), x, (act_t *)y);
            return;
        }
        // BF16 rows are GemvH16P's layout as stored (the upper halves of the floats): block reads, GemvT's lane
        // order and tree, so the same sums bit for bit (a NaN weight would differ in its payload only)
        if (bf16_h16(e, wp(tile, wn))) {
            h16_rows(cols, rows, [&](auto dk) { launch_rows<0>(tile, rows, 0, dk, (const uint8_t *)wp(tile, wn), x, (act_t *)y); });
            return;
        }
#endif
#ifdef OWN41_ACT_BF16
        if (o.generic_kernels) {
            launch_sg(tile, (size_t)rows, ops41sycl::Gemv{e.type, rows, cols, f32out}, wp(tile, wn), wrb(e), x, y);
            return;
        }
#else
        if (o.generic_kernels) throw std::runtime_error("runtime-type kernels exist only in the BF16-activation build");
#endif
        switch (e.type) {
#define X(TY)                                                                                              \
    case iq3::Type::TY:                                                                                    \
        launch_sg(tile, (size_t)rows, ops41sycl::GemvT<iq3::Type::TY, Act>{rows, cols, f32out}, wp(tile, wn), x, y); \
        break;
            OWN41_WEIGHT_TYPES(X)
#undef X
        default: throw std::runtime_error("unsupported weight format: " + wn);
        }
    }
    void gemv_grouped(int tile, const std::string &wn, const act_t *x, act_t *y) {
        const auto &e = we(wn);
        if (e.rows != g.ototal || e.cols != g.oin) throw std::runtime_error("attn_output_a shape");
        const unsigned n = (unsigned)(g.ototal / 8), k = (unsigned)g.oin;
#ifndef OWN41_ACT_BF16
        if (const auto &dp = wgt[tile].at(wn); dp.packed) {
            gemv_kp(tile, e, dp.p, x, y, (unsigned)e.rows, n, k, wn);
            return;
        }
#endif
#ifdef OWN41_ACT_BF16
        if (o.generic_kernels) {
            launch_sg(tile, (size_t)e.rows, ops41sycl::GemvGroupedQ{e.type, n, k}, wp(tile, wn), wrb(e), x, y);
            return;
        }
#else
        if (o.generic_kernels) throw std::runtime_error("runtime-type kernels exist only in the BF16-activation build");
#endif
        switch (e.type) {
#define X(TY)                                                                                              \
    case iq3::Type::TY:                                                                                    \
        launch_sg(tile, (size_t)e.rows, ops41sycl::GemvGroupedQT<iq3::Type::TY, Act>{n, k}, wp(tile, wn), x, y); \
        break;
            OWN41_WEIGHT_TYPES(X)
#undef X
        default: throw std::runtime_error("unsupported weight format: " + wn);
        }
    }
    void routed_gemv(int tile, const std::string &wn, const act_t *x, const uint32_t *ids, act_t *y,
                     bool per_slot) {
        const auto &e = we(wn);
        const unsigned rows = wgt[tile].at(wn).nrows, cols = (unsigned)e.cols; // tp: this card's rows of each expert
#ifndef OWN41_ACT_BF16
        if (const auto &dp = wgt[tile].at(wn); dp.packed) {
            const auto *w = (const uint8_t *)dp.p;
            // 128 work-groups (2,048 sub-groups): best for every format and shape in
            // the 2026-11-09 kernel bench (each fills its local table once); o.down_wg for the down rows
            const size_t MAXWG = per_slot ? o.down_wg : 128;
#define X(TY, KERN, NB)                                                                                    \
    if (e.type == iq3::Type::TY && cols == NB * 256) {                                                     \
        using K = ops41sycl::KERN<NB, Act>;                                                                \
        launch_rows<K::TAB>(tile, (size_t)6 * rows, MAXWG, K{rows, per_slot}, w, x, ids, y);               \
        return;                                                                                            \
    }
            X(IQ2_XXS, RoutedIQ2XXSP, 20) X(IQ2_XXS, RoutedIQ2XXSP, 9)
            X(IQ2_S, RoutedIQ2SP, 20) X(IQ2_S, RoutedIQ2SP, 9)
            X(IQ3_XXS, RoutedIQ3XXSP, 20) X(IQ3_XXS, RoutedIQ3XXSP, 9)
            X(IQ2_XS, RoutedIQ2XSP, 20) X(IQ2_XS, RoutedIQ2XSP, 9)
            X(IQ1_S, RoutedIQ1SP, 20) X(IQ1_S, RoutedIQ1SP, 9)
#undef X
            throw std::runtime_error("packed routed kernel missing: " + wn);
        }
#endif
#ifdef OWN41_ACT_BF16
        if (o.generic_kernels) {
            launch_sg(tile, (size_t)6 * rows, ops41sycl::RoutedGemv{e.type, rows, cols, per_slot}, wp(tile, wn), x, ids, y);
            return;
        }
#else
        if (o.generic_kernels) throw std::runtime_error("runtime-type kernels exist only in the BF16-activation build");
#endif
#ifndef OWN41_ACT_BF16
        // block-loaded form of RoutedGemvT<Q2_K> (same sums bit for bit; tools/bench/bench_routed_m1.cpp)
        if (o.q2k_fast && e.type == iq3::Type::Q2_K && (cols == 9 * 256 || cols == 20 * 256)) {
            if (cols == 9 * 256)
                launch_sg(tile, (size_t)6 * rows, ops41sycl::RoutedQ2KF<9>{rows, cols, per_slot}, wp(tile, wn), x, ids, y);
            else
                launch_sg(tile, (size_t)6 * rows, ops41sycl::RoutedQ2KF<20>{rows, cols, per_slot}, wp(tile, wn), x, ids, y);
            return;
        }
#endif
        switch (e.type) {
#define X(TY)                                                                                              \
    case iq3::Type::TY:                                                                                    \
        launch_sg(tile, (size_t)6 * rows, ops41sycl::RoutedGemvT<iq3::Type::TY, Act>{rows, cols, per_slot}, \
                  wp(tile, wn), x, ids, y);                                                                      \
        break;
            OWN41_WEIGHT_TYPES(X)
#undef X
        default: throw std::runtime_error("unsupported weight format: " + wn);
        }
    }
#ifndef OWN41_ACT_BF16
    // two routed matrices of the same format and shape on the same x (expert gate + up) in one launch: rows
    // 6 * rows .. 12 * rows - 1 of the launch are the second matrix's (same per-row code); false when unfit
    bool routed_pair_fits(int tile, const std::string &wa, const std::string &wb) {
        const auto &ea = we(wa), &eb = we(wb);
        const auto &da = wgt[tile].at(wa), &db = wgt[tile].at(wb);
        if (!da.packed || !db.packed || ea.type != eb.type || ea.cols != eb.cols || da.nrows != db.nrows) return false;
        if (ea.cols != 20 * 256) return false;
        const auto t = ea.type;
        return t == iq3::Type::IQ2_XXS || t == iq3::Type::IQ2_S || t == iq3::Type::IQ3_XXS || t == iq3::Type::IQ2_XS ||
               t == iq3::Type::IQ1_S;
    }
    // ... plus extra rows EX (placed first: a long one starts at once)
    template <typename EX = ops41sycl::NoRows>
    bool routed_pair(int tile, const std::string &wa, const std::string &wb, const act_t *x, const uint32_t *ids,
                     act_t *ya, act_t *yb, EX ex = {}) {
        if (!routed_pair_fits(tile, wa, wb)) return false;
        const auto &ea = we(wa);
        const auto &da = wgt[tile].at(wa), &db = wgt[tile].at(wb);
        const unsigned rows = da.nrows;
        const auto *w = (const uint8_t *)da.p;
        const size_t MAXWG = ea.type == iq3::Type::IQ1_S && o.pair_wg_iq1 > 0 ? o.pair_wg_iq1 : o.pair_wg;
        auto go = [&](auto kt) {
            using K = typename decltype(kt)::type;
            K k{rows, false, ex};
            k.w2 = (const uint8_t *)db.p;
            k.out2 = yb;
            launch_rows<K::TAB>(tile, (size_t)12 * rows + ex.n(), MAXWG, k, w, x, ids, ya);
            return true;
        };
        using namespace ops41sycl;
        switch (ea.type) {
        case iq3::Type::IQ2_XXS: return go(std::type_identity<RoutedIQ2XXSP<20, Act, EX>>{});
        case iq3::Type::IQ2_S: return go(std::type_identity<RoutedIQ2SP<20, Act, EX>>{});
        case iq3::Type::IQ3_XXS: return go(std::type_identity<RoutedIQ3XXSP<20, Act, EX>>{});
        case iq3::Type::IQ2_XS: return go(std::type_identity<RoutedIQ2XSP<20, Act, EX>>{});
        case iq3::Type::IQ1_S: return go(std::type_identity<RoutedIQ1SP<20, Act, true, EX>>{});
        default: return false;
        }
    }
    // routed_gemv (packed rows) with extra rows EX spread through the same launch; false when unfit
    template <typename EX>
    bool routed_gemv_ex(int tile, const std::string &wn, const act_t *x, const uint32_t *ids, act_t *y, bool per_slot,
                        EX ex) {
        const auto &e = we(wn);
        const auto &dp = wgt[tile].at(wn);
        if (!dp.packed) return false;
        const unsigned rows = dp.nrows, cols = (unsigned)e.cols;
        const auto *w = (const uint8_t *)dp.p;
        constexpr size_t MAXWG = 128;
        if (cols != 9 * 256) return false;
        auto go = [&](auto kt) {
            using K = typename decltype(kt)::type;
            launch_rows<K::TAB>(tile, (size_t)6 * rows + ex.n(), MAXWG, K{rows, per_slot, ex}, w, x, ids, y);
            return true;
        };
        using namespace ops41sycl;
        if (e.type == iq3::Type::IQ2_XXS) return go(std::type_identity<RoutedIQ2XXSP<9, Act, EX>>{});
        if (e.type == iq3::Type::IQ2_S) return go(std::type_identity<RoutedIQ2SP<9, Act, EX>>{});
        if (e.type == iq3::Type::IQ3_XXS) return go(std::type_identity<RoutedIQ3XXSP<9, Act, EX>>{});
        if (e.type == iq3::Type::IQ2_XS) return go(std::type_identity<RoutedIQ2XSP<9, Act, EX>>{});
        if (e.type == iq3::Type::IQ1_S) return go(std::type_identity<RoutedIQ1SP<9, Act, true, EX>>{});
        return false;
    }
    // expert down rows with the shared expert's down rows in the same launch
    bool down_with_shared(int c, const std::string &p) {
        auto &s = sc[c];
        const std::string wn = p + "ffn_down_shexp.weight";
        const auto &es = we(wn);
        const auto &ds = wgt[c].at(wn);
        if (!ds.packed || es.cols != 2304) return false;
        const act_t *xs = s.act + (size_t)6 * g.mid;
        if (es.type == iq3::Type::Q8_0)
            return routed_gemv_ex(c, p + "ffn_down_exps.weight", s.act, s.ids, s.expd, true,
                                  ops41sycl::DenseRows<ops41sycl::GemvQ8P<72, Act>>{{ds.nrows, 0}, (const uint8_t *)ds.p, xs, s.shd});
        if (es.type == iq3::Type::Q5_K)
            return routed_gemv_ex(c, p + "ffn_down_exps.weight", s.act, s.ids, s.expd, true,
                                  ops41sycl::DenseRows<ops41sycl::GemvQ5KP<9, Act>>{{ds.nrows, 0}, (const uint8_t *)ds.p, xs, s.shd});
        return false;
    }
#endif
    static bool al16(const void *p) { return ((uintptr_t)p & 15u) == 0; }
    // BF16 rows of these widths through GemvH16P<cols / 32> (OWN_BF16_ROWS)
    static bool h16_width(long cols) { return cols == 256 || cols == 512 || cols == 1280 || cols == 5120; }
    bool bf16_h16(const WeightTab::E &e, const void *w) const {
#ifdef OWN41_ACT_BF16
        (void)e; (void)w;
        return false;
#else
        return o.bf16_rows && e.type == iq3::Type::BF16 && e.experts == 0 && h16_width(e.cols) && al16(w);
#endif
    }
    template <typename F> static void h16_rows(unsigned cols, unsigned rows, F &&f) {
        switch (cols) {
        case 256: return f(ops41sycl::GemvH16P<8, Act>{rows});
        case 512: return f(ops41sycl::GemvH16P<16, Act>{rows});
        case 1280: return f(ops41sycl::GemvH16P<40, Act>{rows});
        case 5120: return f(ops41sycl::GemvH16P<160, Act>{rows});
        default: throw std::runtime_error("h16_rows: width");
        }
    }
    void rmsnorm(int tile, const act_t *x, const std::string &wn, int n, act_t *y) {
        const float *w = wp<float>(tile, wn);
#ifndef OWN41_ACT_BF16
        if (o.small_fast && al16(x) && al16(w) && al16(y) && x != y) { // several sub-groups: not in place
            switch (n) {
            case 512: launch_wg(tile, 64, ops41sycl::RmsNormPS<512, 2>{}, x, w, y); return;
            case 1280: launch_wg(tile, 128, ops41sycl::RmsNormPS<1280, 4>{}, x, w, y); return;
            case 5120: launch_wg(tile, 128, ops41sycl::RmsNormPS<5120, 4>{}, x, w, y); return;
            default: break;
            }
        }
        if (o.small_fast && al16(x) && al16(w)) {
            switch (n) {
            case 512: launch_sg(tile, 1, ops41sycl::RmsNormP<512>{}, x, w, y); return;
            case 1280: launch_sg(tile, 1, ops41sycl::RmsNormP<1280>{}, x, w, y); return;
            case 5120: launch_sg(tile, 1, ops41sycl::RmsNormP<5120>{}, x, w, y); return;
            default: break;
            }
        }
#endif
        launch_sg(tile, 1, ops41sycl::RmsNormA<Act>{n}, x, w, y);
    }
    void rope(int tile, act_t *x, int rows, int d, long p_, bool yarn, bool inv) {
        if (p_ < 0 || p_ >= max_seq) throw std::runtime_error("position beyond max_seq");
        const float *cb = yarn ? cos_yarn[tile] : cos_base[tile];
        const float *sb = yarn ? sin_yarn[tile] : sin_base[tile];
        launch(tile, (size_t)rows * 32, 32, ops41sycl::RopePairsA<Act>{(unsigned)rows, (unsigned)d, 64u, inv}, x,
               cb + (size_t)p_ * 32, sb + (size_t)p_ * 32);
    }

    // ---- trace --------------------------------------------------------------
    void trw(int layer, int tag, const float *v, size_t n) {
        uint32_t h[4] = {(uint32_t)trace_step, (uint32_t)layer, (uint32_t)tag, (uint32_t)n};
        fwrite(h, 4, 4, trace_f);
        fwrite(v, 4, n, trace_f);
    }
    bool tracing() const { return trace_f && trace_on; }
    void tra(int layer, int tag, int t, const act_t *p, size_t n) { // activation buffer
        if (!tracing()) return;
        std::vector<act_t> b(n);
        qs[t].memcpy(b.data(), p, n * sizeof(act_t)).wait();
        std::vector<float> f(n);
        for (size_t i = 0; i < n; ++i) f[i] = Act::rd(b[i]);
        trw(layer, tag, f.data(), n);
    }
    void trf(int layer, int tag, int t, const float *p, size_t n) {
        if (!tracing()) return;
        std::vector<float> f(n);
        qs[t].memcpy(f.data(), p, n * 4).wait();
        trw(layer, tag, f.data(), n);
    }
    template <typename I> void tri(int layer, int tag, int t, const I *p, size_t n) {
        if (!tracing()) return;
        std::vector<I> b(n);
        qs[t].memcpy(b.data(), p, n * sizeof(I)).wait();
        std::vector<float> f(n);
        for (size_t i = 0; i < n; ++i) f[i] = (float)b[i];
        trw(layer, tag, f.data(), n);
    }

    // ---- decode step pieces -------------------------------------------------
    void migrate(int t) {
        const size_t nb = sizeof(act_t) * 4 * (size_t)g.h;
        float pre[4];
        qs[cur].memcpy(h_streams.data(), streams[cur], nb);
        qs[cur].memcpy(pre, sc[cur].cur_pre, 16);
        qs[cur].wait();
        qs[t].memcpy(streams[t], h_streams.data(), nb);
        qs[t].memcpy(sc[t].cur_pre, pre, 16);
        qs[t].wait();
        cur = t;
    }

    void hc_mix(int t, const std::string &prefix, float *pre, float *post, float *comb) {
        auto &s = sc[t];
        // lane/tree reduction (anchor ops41::hc_mix_lanes); the serial-order
        // HcMixDots kernel cost ~3 ms per call
        const float *fn = wp<float>(t, prefix + "fn.weight");
#ifndef OWN41_ACT_BF16
        if (o.small_fast && g.h == 5120 && HC_SEG == 8 && al16(streams[t]) && al16(fn)) {
            launch_sg(t, 25 * HC_SEG, ops41sycl::HcMixDotsP<5120, HC_SEG>{}, (const act_t *)streams[t], fn, s.d25);
            launch_sg(t, 1, hc_fin_k(), (const double *)s.d25,
                      wp<float>(t, prefix + "scale.weight"), wp<float>(t, prefix + "base.weight"), pre, post, comb);
            return;
        }
#endif
        launch_sg(t, 25 * HC_SEG, ops41sycl::HcMixDots32A<Act>{g.h, HC_SEG}, (const act_t *)streams[t], fn, s.d25);
        launch(t, 1, 1, ops41sycl::HcMixFinishSeg{g.h, HC_SEG}, (const double *)s.d25,
               wp<float>(t, prefix + "scale.weight"), wp<float>(t, prefix + "base.weight"), pre, post, comb);
    }

    // collapse the 4 streams with `mix` (HcPreA) and RMS-normalize into s.xn
    void pre_norm(int t, const float *mix, const std::string &wn) {
        auto &s = sc[t];
        const int H_ = g.h;
#ifndef OWN41_ACT_BF16
        const float *w = wp<float>(t, wn);
        // Off: same arithmetic as the two launches below (test_small_v41_device.cpp), faster alone (19 vs 23 us)
        // but 22.1 us per call in the real step against 11.4 for HcPreA + RmsNormPS (p8 profile, 2026-11-09)
        constexpr bool fused_pre_norm = false;
        if (fused_pre_norm && o.small_fast && H_ == 5120 && al16(streams[t]) && al16(w) && al16(s.xn)) {
            launch_wg(t, 128, ops41sycl::HcPreNormPS<5120, 4>{}, (const float *)streams[t], mix, w, s.xn);
            return;
        }
#endif
        launch(t, H_, 32, ops41sycl::HcPreA<Act>{H_}, (const act_t *)streams[t], mix, s.x);
        rmsnorm(t, s.x, wn, H_, s.xn);
    }
    // streams <- post * ob + comb^T * streams; optionally copy 4 pre-mix floats pre_src -> pre_dst after
    void hc_post(int t, const float *post, const float *comb, const float *pre_src, float *pre_dst) {
        auto &s = sc[t];
        const int H_ = g.h;
        if (o.small_fast) { // one launch, no stream copy (test_small_v41_device.cpp)
            launch(t, (size_t)H_, 64, ops41sycl::HcPostP<Act>{H_}, streams[t], (const act_t *)s.ob, post, comb, pre_src,
                   pre_dst);
            return;
        }
        qs[t].memcpy(s.old, streams[t], sizeof(act_t) * 4 * (size_t)H_);
        launch(t, (size_t)4 * H_, 32, ops41sycl::HcPostA<Act>{H_}, streams[t], (const act_t *)s.old,
               (const act_t *)s.ob, post, comb);
        if (pre_dst) qs[t].memcpy(pre_dst, pre_src, 16);
    }

    // Official Block.forward threading: the attention collapses the streams
    // with the previous layer's FFN pre-mix; the FFN collapses them with the
    // pre-mix THIS attention computed (from the pre-attention streams).
    void layer(int L, int t) {
        auto &s = sc[t];
        const int H_ = g.h;
        const std::string p = "blk." + std::to_string(L) + ".";
        const size_t sb = sizeof(act_t) * 4 * (size_t)H_;
        if (L == 1 || L == 14) {
            engram_host(L, t);
            prof("engram", t);
            tra(L, TT_ENGRAM, t, streams[t], 4 * (size_t)H_);
        }
        hc_mix(t, p + "hc_attn_", s.pre_a, s.post_a, s.comb_a);
        prof("hc_mix", t);
        pre_norm(t, (const float *)s.cur_pre, p + "attn_norm.weight");
        prof("hc_pre_norm", t);
        trf(L, TT_ATTN_MIX_PRE, t, s.pre_a, 4);
        trf(L, TT_ATTN_MIX_POST, t, s.post_a, 4);
        trf(L, TT_ATTN_MIX_COMB, t, s.comb_a, 16);
        tra(L, TT_ATTN_IN, t, s.xn, H_);
        attention(L, t);
        tra(L, TT_ATTN_OUT, t, s.ob, H_);
        hc_post(t, s.post_a, s.comb_a, nullptr, nullptr);
        prof("hc_post", t);
        tra(L, TT_STREAMS_ATTN, t, streams[t], 4 * (size_t)H_);

        hc_mix(t, p + "hc_ffn_", s.pre_f, s.post_f, s.comb_f);
        prof("hc_mix", t);
        pre_norm(t, (const float *)(o.hc_legacy ? s.pre_f : s.pre_a), p + "ffn_norm.weight");
        prof("hc_pre_norm", t);
        trf(L, TT_FFN_MIX_PRE, t, s.pre_f, 4);
        tra(L, TT_FFN_IN, t, s.xn, H_);
        moe(L, t);
        tra(L, TT_FFN_OUT, t, s.ob, H_);
        hc_post(t, s.post_f, s.comb_f, s.pre_f, s.cur_pre);
        prof("hc_post", t);
        if (pace == 1) qs[t].wait();
        warm(t);
        if (prof_on) prof("keep_warm", t);
        tra(L, TT_STREAMS_FFN, t, streams[t], 4 * (size_t)H_);
    }

    static int src_index(int layer) { // latest kv source at or below layer
        static const int srcs[4] = {2, 8, 14, 20};
        int si = -1;
        for (int i = 0; i < 4; ++i) if (srcs[i] <= layer) si = i;
        return si;
    }
    static bool is_kv_source(int L) { return L == 2 || L == 8 || L == 14 || L == 20; }
    static int index_slot(int L) { // position among the 8 index sources, -1 if none
        static const int idx[8] = {2, 8, 14, 20, 24, 28, 32, 36};
        for (int i = 0; i < 8; ++i) if (idx[i] == L) return i;
        return -1;
    }
    static int isrc_for(int layer) { // latest index source at or below layer
        static const int idx[8] = {2, 8, 14, 20, 24, 28, 32, 36};
        int si = -1;
        for (int i = 0; i < 8; ++i) if (idx[i] <= layer) si = i;
        return si;
    }
    // config.json compress_ratios, main layers: 0,0, 2 x18, 1 x20 (37-39 are ratio 1)
    int cr_of(int L) const { return L < 2 ? 0 : (L < 20 ? 2 : 1); }

    void attention(int L, int t) {
        auto &s = sc[t];
        const std::string p = "blk." + std::to_string(L) + ".";
        const int cr = cr_of(L);
        const bool yarn = cr > 0;
        gemv(t, p + "attn_q_a.weight", s.xn, s.qa);
        rmsnorm(t, s.qa, p + "attn_q_a_norm.weight", g.qrank, s.qn);
        prof("attn_q_a", t);
        gemv(t, p + "attn_q_b.weight", s.qn, s.q);
        rope(t, s.q, g.qh, g.hd, pos, yarn, false);
        prof("attn_q_b", t);
        gemv(t, p + "attn_kv.weight", s.xn, s.kv);
        rmsnorm(t, s.kv, p + "attn_kv_a_norm.weight", g.hd, s.kvn);
        rope(t, s.kvn, 1, g.hd, pos, yarn, false);
        prof("attn_kv", t);
        tra(L, TT_Q, t, s.q, (size_t)g.qh * g.hd);
        tra(L, TT_KV, t, s.kvn, g.hd);
        // small_fast: the window append moves below, fused with building the index list
        // (nothing between reads the ring or the window indices)
        const bool fast_win = o.small_fast && g.hd <= 1024;
        if (!fast_win)
            launch(t, 1, 1, ops41sycl::WindowAppendA<Act>{128, g.hd, (int)pos}, ring[t][L], (const act_t *)s.kvn, s.widx);
        int si = src_index(L);
        int n_idx = 128;
        if (cr) {
            if (is_kv_source(L)) { publish(L, t, si, yarn); prof("publish", t); }
            if (index_slot(L) >= 0) { index(L, t, si, yarn); prof("index", t); }
            sync_rows(t, si);
            sync_cidx(t, isrc_for(L));
            if (fast_win) {
                launch(t, (size_t)std::max(g.hd, 512), 64, ops41sycl::WindowAppendP<Act>{128, g.hd, (int)pos, 512}, ring[t][L],
                       (const act_t *)s.kvn, s.widx, s.idxs_cat, (const int32_t *)cidx_mirror[t][isrc_for(L)]);
            } else {
                qs[t].memcpy(s.idxs_cat, s.widx, 128 * 4);
                qs[t].memcpy(s.idxs_cat + 128, cidx_mirror[t][isrc_for(L)], 512 * 4);
            }
            n_idx += 512;
            tri(L, TT_CIDX, t, s.idxs_cat + 128, 512);
        } else if (fast_win) {
            launch(t, (size_t)std::max(g.hd, 128), 64, ops41sycl::WindowAppendP<Act>{128, g.hd, (int)pos, 0}, ring[t][L],
                   (const act_t *)s.kvn, s.widx, s.idxs_cat, (const int32_t *)nullptr);
        } else {
            qs[t].memcpy(s.idxs_cat, s.widx, 128 * 4);
        }
#ifndef OWN41_ACT_BF16
        if (o.small_fast && g.hd == 512 && (n_idx == 128 || n_idx == 640) && g.qh % 4 == 0) {
            // same per-output arithmetic as the three launches below (test_small_v41_device.cpp)
            const uint16_t *kvw = ring[t][L], *kvc = cr ? ckv_mirror[t][si] : ring[t][L];
            const float *sinks = wp<float>(t, p + "attn_sinks.weight");
            const int32_t *ix = (const int32_t *)s.idxs_cat;
            if (n_idx == 128) {
                launch_sg(t, (size_t)g.qh * n_idx / 32, ops41sycl::SparseScoreP<512>{n_idx, g.qh, 128, g.hd},
                          (const act_t *)s.q, kvw, kvc, ix, s.attn_w);
                launch_sg(t, g.qh, ops41sycl::SparseSoftmaxP<128>{g.qh}, sinks, ix, s.attn_w);
            } else {
                launch_sg(t, (size_t)(g.qh / 4) * (n_idx / 32), ops41sycl::SparseScoreHG<512, 4>{n_idx, g.qh, 128, g.hd},
                          (const act_t *)s.q, kvw, kvc, ix, s.attn_w);
                launch_sg(t, g.qh, ops41sycl::SparseSoftmaxP<640>{g.qh}, sinks, ix, s.attn_w);
            }
            if (al16(kvw) && al16(kvc)) // block reads: uniform row address per index (2026-11-09: 39 -> 23 us at 640)
                launch_sg(t, (size_t)g.qh * g.hd / 64, ops41sycl::SparseOutJB<512, 1, 16>{n_idx, g.qh, 128}, kvw, kvc,
                          ix, (const float *)s.attn_w, s.of);
            else
                launch_sg(t, (size_t)g.qh * g.hd / 64, ops41sycl::SparseOutJ<512, 2>{n_idx, g.qh, 128}, kvw, kvc, ix,
                          (const float *)s.attn_w, s.of);
        } else
#endif
        { // three launches, same arithmetic order as the one-launch SparseAttn kernel
            const uint16_t *kvw = ring[t][L], *kvc = cr ? ckv_mirror[t][si] : ring[t][L];
            launch(t, (size_t)g.qh * n_idx, 32, ops41sycl::SparseScoreA<Act>{n_idx, g.qh, g.hd, 128},
                   (const act_t *)s.q, kvw, kvc, (const int32_t *)s.idxs_cat, s.attn_w);
            launch(t, g.qh, 8, ops41sycl::SparseSoftmax{n_idx, g.qh}, wp<float>(t, p + "attn_sinks.weight"),
                   (const int32_t *)s.idxs_cat, s.attn_w);
            launch(t, (size_t)g.qh * g.hd, 32, ops41sycl::SparseOut{n_idx, g.qh, g.hd, 128}, kvw, kvc,
                   (const int32_t *)s.idxs_cat, (const float *)s.attn_w, s.of);
        }
        prof("sparse_attn", t);
        trf(L, TT_ATTN_O, t, s.of, (size_t)g.qh * g.hd);
        if (o.small_fast) { // one launch (test_small_v41_device.cpp)
            if (pos < 0 || pos >= max_seq) throw std::runtime_error("position beyond max_seq");
            const float *cb = (yarn ? cos_yarn[t] : cos_base[t]) + (size_t)pos * 32;
            const float *sbp = (yarn ? sin_yarn[t] : sin_base[t]) + (size_t)pos * 32;
            launch(t, (size_t)g.qh * g.hd, 64, ops41sycl::ToActRopeA<Act>{(unsigned)g.qh, (unsigned)g.hd, 64u, true},
                   (const float *)s.of, s.obuf, cb, sbp);
        } else {
            launch(t, (size_t)g.qh * g.hd, 32, ops41sycl::ToActA<Act>{g.qh * g.hd}, (const float *)s.of, s.obuf);
            rope(t, s.obuf, g.qh, g.hd, pos, yarn, true);
        }
        // grouped output LoRA: 8 groups of 1024 rows, each reads its 4096-slice
        gemv_grouped(t, p + "attn_output_a.weight", s.obuf, s.oa);
        prof("attn_o_a", t);
        tra(L, TT_ATTN_OA, t, s.oa, g.ototal);
        gemv(t, p + "attn_output_b.weight", s.oa, s.ob);
        prof("attn_o_b", t);
    }

    // append one published row to the host mirrors (cards sync lazily)
    void append_row_host(int si, const uint16_t *kv_row, const uint16_t *ik_row) {
        if (h_ckv[si].size() + g.hd > h_ckv[si].capacity() || h_ik[si].size() + 128 > h_ik[si].capacity())
            throw std::runtime_error("compressed cache full (max_seq)");
        h_ckv[si].insert(h_ckv[si].end(), kv_row, kv_row + g.hd); // within capacity: no reallocation
        h_ik[si].insert(h_ik[si].end(), ik_row, ik_row + 128);
        src_len[si]++;
    }
    // bring card t's copy of source si up to date; non-blocking (the host rows
    // are append-only and never move). Pieces stay under 64 MiB.
    void sync_rows(int t, int si) {
        long have = synced[t][si];
        const long want = src_len[si];
        const bool copies = have < want;
        const long step = ((long)64 << 20) / ((long)g.hd * 2);
        while (have < want) {
            const long n = std::min(step, want - have);
            qs[t].memcpy(ckv_mirror[t][si] + (size_t)have * g.hd, h_ckv[si].data() + (size_t)have * g.hd,
                         (size_t)n * g.hd * 2);
            qs[t].memcpy(ik_mirror[t][si] + (size_t)have * 128, h_ik[si].data() + (size_t)have * 128,
                         (size_t)n * 128 * 2);
            have += n;
        }
        if (h2d_wait && (o.tp <= 1 || copies)) twait(t); // tp: no drain when nothing was copied
        synced[t][si] = want;
    }
    void set_cidx(int slot, const std::vector<int32_t> &sel) {
        ++cidx_ver[slot];
        std::copy(sel.begin(), sel.end(), h_cidx[slot][cidx_ver[slot] % 4].begin());
    }
    void sync_cidx(int t, int slot) {
        if (tile_cidx_ver[t][slot] == cidx_ver[slot]) return;
        auto ev = qs[t].memcpy(cidx_mirror[t][slot], h_cidx[slot][cidx_ver[slot] % 4].data(), 512 * 4);
        if (h2d_wait) ev.wait();
        tile_cidx_ver[t][slot] = cidx_ver[slot];
    }

    // compressor publish + index-key append (kv source layers 2/8/14/20)
    void publish(int L, int t, int si, bool yarn) {
        auto &s = sc[t];
        const std::string p = "blk." + std::to_string(L) + ".";
        const int cr = cr_of(L);
        long gpos;
        if (cr == 1) {
            gemv(t, p + "attn_compressor_kv.weight", s.xn, s.cw);
            rmsnorm(t, s.cw, p + "attn_compressor_norm.weight", g.hd, s.latent);
            gpos = pos;
        } else {
            gemv(t, p + "attn_compressor_kv.weight", s.xn, s.cw);
            gemv(t, p + "attn_compressor_gate.weight", s.xn, s.scg);
            const int slot = (int)(pos % 2);
            launch(t, g.hd, 32, ops41sycl::ToF32A<Act>{g.hd}, (const act_t *)s.cw,
                   s.kv_state + (size_t)si * 2 * g.hd + (size_t)slot * g.hd);
            launch(t, g.hd, 32, ops41sycl::ToF32A<Act>{g.hd}, (const act_t *)s.scg,
                   s.score_state + (size_t)si * 2 * g.hd + (size_t)slot * g.hd);
            if (pos % 2 == 0) return; // group not complete yet
            gpos = pos - 1;           // a latent stands for the first token of its group
            if (o.small_fast && g.hd <= 1024)
                launch_local<1024>(t, 32, ops41sycl::CompressPoolP<Act>{2, g.hd},
                                   (const float *)(s.kv_state + (size_t)si * 2 * g.hd),
                                   (const float *)(s.score_state + (size_t)si * 2 * g.hd),
                                   wp<float>(t, p + "attn_compressor_norm.weight"), s.latent);
            else
                launch(t, 1, 1, ops41sycl::CompressPoolA<Act>{2, g.hd},
                       (const float *)(s.kv_state + (size_t)si * 2 * g.hd),
                       (const float *)(s.score_state + (size_t)si * 2 * g.hd),
                       wp<float>(t, p + "attn_compressor_norm.weight"), s.latent);
        }
        // reference order: ik = rope(k_norm(wk * latent)); ckv = rope(latent)
        gemv(t, p + "indexer.attn_k.weight", s.latent, s.kk);
        rmsnorm(t, s.kk, p + "indexer.k_norm.weight", 128, s.kk);
        rope(t, s.kk, 1, 128, gpos, yarn, false);
        rope(t, s.latent, 1, g.hd, gpos, yarn, false);
        // the published rows leave the activation domain here: KV is BF16
        std::vector<act_t> ha(g.hd), hk(128);
        qs[t].memcpy(ha.data(), s.latent, sizeof(act_t) * (size_t)g.hd);
        qs[t].memcpy(hk.data(), s.kk, sizeof(act_t) * 128);
        qs[t].wait();
        std::vector<uint16_t> kvr(g.hd), ikr(128);
        for (int i = 0; i < g.hd; ++i) kvr[i] = ops41::bf16b(Act::rd(ha[i]));
        for (int i = 0; i < 128; ++i) ikr[i] = ops41::bf16b(Act::rd(hk[i]));
        append_row_host(si, kvr.data(), ikr.data());
    }

    // indexer: score every visible compressed row, keep the best 512 (host
    // selection: long serial device kernels trip the driver's hang check)
    void index(int L, int t, int si, bool yarn, long len = -1) { // len: rows of source si (default: src_len)
        auto &s = sc[t];
        const std::string p = "blk." + std::to_string(L) + ".";
        if (len < 0) len = src_len[si];
        std::vector<int32_t> sel(512, -1);
        if (len > 0 && len <= 512) {
            // top-512 of at most 512 visible rows is all of them, whatever the
            // scores (official: topk = min(index_topk, rows), then sorted by
            // position), and with at most 2048 blocks the candidate mask keeps
            // every block. Nothing to compute.
            for (long j = 0; j < len; ++j) sel[j] = (int32_t)j + 128;
            if (L == 20) {
                cand_host.assign(len, 1);
                cand_valid = true;
            }
        } else if (len > 0) {
            sync_rows(t, si); // the scores read this card's index keys
            gemv(t, p + "indexer.attn_q_b.weight", s.qn, s.qi);
            rope(t, s.qi, 32, 128, pos, yarn, false);
            gemv(t, p + "indexer.proj.weight", s.xn, s.wv);
            int64_t l64 = len;
            qs[t].memcpy(s.lens, &l64, 8);
            const int T_ = (int)((len + 31) / 32 * 32);
            launch(t, (size_t)T_, 32, ops41sycl::IndexerScoreA<Act>{32, 128, T_, 1}, (const act_t *)s.qi,
                   (const uint16_t *)ik_mirror[t][si], (const act_t *)s.wv, (const int64_t *)s.lens,
                   s.score);
            std::vector<float> hs(len);
            qs[t].memcpy(hs.data(), s.score, (size_t)len * 4).wait();
            if (L == 20) { // official select_candidate_blocks (block 8, top 2048, newest pinned)
                const int bs = 8, tb = 2048;
                const int nb = (int)((len + bs - 1) / bs);
                std::vector<float> bsc(nb, -INFINITY);
                for (long j = 0; j < len; ++j) bsc[j / bs] = std::max(bsc[j / bs], hs[j]);
                bsc[(len - 1) / bs] = INFINITY;
                std::vector<int> ord(nb);
                for (int i = 0; i < nb; ++i) ord[i] = i;
                const int tk = std::min(tb, nb);
                std::partial_sort(ord.begin(), ord.begin() + tk, ord.end(), [&](int a, int b) {
                    return bsc[a] > bsc[b] || (bsc[a] == bsc[b] && a < b);
                });
                cand_host.assign(len, 0);
                for (int i = 0; i < tk; ++i)
                    if (bsc[ord[i]] > -INFINITY)
                        for (long j = (long)ord[i] * bs; j < std::min<long>((long)(ord[i] + 1) * bs, len); ++j)
                            cand_host[j] = 1;
                cand_valid = true;
            } else if (L > 20) {
                if (cand_valid) {
                    for (long j = 0; j < len && j < (long)cand_host.size(); ++j)
                        if (!cand_host[j]) hs[j] = -INFINITY;
                } else if (len > 2048 * 8) {
                    throw std::runtime_error("candidate mask missing (layer 20 not in range) beyond 16384 rows");
                }
            }
            const int nk = (int)std::min<long>(512, len);
            std::vector<int32_t> ord(len);
            for (long j = 0; j < len; ++j) ord[j] = (int32_t)j;
            std::partial_sort(ord.begin(), ord.begin() + nk, ord.end(), [&](int32_t a, int32_t b) {
                return hs[a] > hs[b] || (hs[a] == hs[b] && a < b);
            });
            std::sort(ord.begin(), ord.begin() + nk);
            for (int i = 0; i < nk; ++i) sel[i] = ord[i] + 128;
        }
        set_cidx(index_slot(L), sel);
    }

    // index() for len > 512 on card t alone (tp, o.dev_index): the same scores, then the
    // candidate blocks (layer 20) and the top-512 by TopKSelP straight into this card's list.
    // Every card holds the indexer weights and its own keys, so each picks for itself.
    long dcand_n[TILES] = {};
    bool dcand_ok[TILES] = {};
    // out: the list's destination (multi-token steps: one list per token; the token's own layer-20 mask in
    // s.cand, same length, so layers past 20 always mask); default this card's list for the slot
    void dev_index(int L, int t, int si, bool yarn, long len, int32_t *out = nullptr) {
        auto &s = sc[t];
        const std::string p = "blk." + std::to_string(L) + ".";
        const int slot = index_slot(L);
        sync_rows(t, si);
        gemv(t, p + "indexer.attn_q_b.weight", s.qn, s.qi);
        rope(t, s.qi, 32, 128, cpos(t), yarn, false);
        gemv(t, p + "indexer.proj.weight", s.xn, s.wv);
        const int T_ = (int)((len + 31) / 32 * 32);
        if (o.score_b) { // the same sums, keys read once (IndexerScoreB)
            using KS = ops41sycl::IndexerScoreB<Act>;
            constexpr size_t WG = 128;
            const size_t n = ((size_t)T_ + WG - 1) / WG * WG;
            const KS k{(int)len, T_};
            const act_t *qi = s.qi, *wv = s.wv;
            const uint16_t *ik = ik_mirror[t][si];
            float *sco = s.score;
            auto e = qs[t].submit([&](sycl::handler &hh) {
                sycl::local_accessor<float, 1> lt(32 * 128 + 32, hh);
                hh.parallel_for(sycl::nd_range<1>(n, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                    k(it, qi, ik, wv, sco, &lt[0]);
                });
            });
            kev(t, kname<KS>(), e);
        } else {
            qs[t].fill(s.lens, (int64_t)len, 1);
            launch(t, (size_t)T_, 32, ops41sycl::IndexerScoreA<Act>{32, 128, T_, 1}, (const act_t *)s.qi,
                   (const uint16_t *)ik_mirror[t][si], (const act_t *)s.wv, (const int64_t *)s.lens, s.score);
        }
        using KR = ops41sycl::TopKSelP<false>;
        using KB = ops41sycl::TopKSelP<true>;
        constexpr size_t SLM = (size_t)KR::NSG * 256 + 8;
        if (L == 20) { // official select_candidate_blocks (block 8, top 2048, newest pinned)
            const int nb = (int)((len + 7) / 8);
            launch_local<SLM>(t, KB::WG, KB{nb, 2048, 0, 0, 0, 8, (int)len}, (const float *)s.score,
                              (const uint8_t *)nullptr, (int32_t *)nullptr, s.cand);
            dcand_n[t] = len;
            dcand_ok[t] = true;
        }
        const bool mask = L > 20 && (out || dcand_ok[t]);
        if (L > 20 && !out && !dcand_ok[t] && len > 2048 * 8)
            throw std::runtime_error("candidate mask missing (layer 20 not in range) beyond 16384 rows");
        int32_t *dst = out ? out : cidx_mirror[t][slot];
        launch_local<SLM>(t, KR::WG, KR{(int)len, 512, 128, 512, mask ? (int)(out ? len : dcand_n[t]) : 0, 0, 0},
                          (const float *)s.score, mask ? (const uint8_t *)s.cand : (const uint8_t *)nullptr, dst,
                          (uint8_t *)nullptr);
        if (!out) tile_cidx_ver[t][slot] = cidx_ver[slot]; // the list is on the card: nothing for sync_cidx to copy
        if (o.dev_index_check) dev_index_check(L, t, len, mask, dst);
    }
    // OWN_DEV_INDEX_CHECK=1: every dev_index list (and layer-20 mask) against index()'s host selection
    std::vector<uint8_t> chk_cand[TILES][MTX]; // per card and token of the step
    std::atomic<long> chk_calls{0}, chk_bad{0};
    void dev_index_check(int L, int t, long len, bool mask, const int32_t *dst) {
        auto &s = sc[t];
        std::vector<float> hs(len);
        std::vector<int32_t> dl(512);
        qs[t].memcpy(hs.data(), s.score, (size_t)len * 4);
        qs[t].memcpy(dl.data(), dst, 512 * 4).wait();
        bool bad = false;
        if (L == 20) {
            const int bs = 8, tb = 2048;
            const int nb = (int)((len + bs - 1) / bs);
            std::vector<float> bsc(nb, -INFINITY);
            for (long j = 0; j < len; ++j) bsc[j / bs] = std::max(bsc[j / bs], hs[j]);
            bsc[(len - 1) / bs] = INFINITY;
            std::vector<int> ord(nb);
            for (int i = 0; i < nb; ++i) ord[i] = i;
            const int tk = std::min(tb, nb);
            std::partial_sort(ord.begin(), ord.begin() + tk, ord.end(),
                              [&](int a, int b) { return bsc[a] > bsc[b] || (bsc[a] == bsc[b] && a < b); });
            auto &hc = chk_cand[t][tokoff[t]];
            hc.assign(len, 0);
            for (int i = 0; i < tk; ++i)
                if (bsc[ord[i]] > -INFINITY)
                    for (long j = (long)ord[i] * bs; j < std::min<long>((long)(ord[i] + 1) * bs, len); ++j) hc[j] = 1;
            std::vector<uint8_t> dc(len);
            qs[t].memcpy(dc.data(), s.cand, (size_t)len).wait();
            if (dc != hc) bad = true;
        }
        if (mask)
            for (long j = 0; j < len && j < (long)chk_cand[t][tokoff[t]].size(); ++j)
                if (!chk_cand[t][tokoff[t]][j]) hs[j] = -INFINITY;
        std::vector<int32_t> ord(len), sel(512, -1);
        for (long j = 0; j < len; ++j) ord[j] = (int32_t)j;
        std::partial_sort(ord.begin(), ord.begin() + 512, ord.end(),
                          [&](int32_t a, int32_t b) { return hs[a] > hs[b] || (hs[a] == hs[b] && a < b); });
        std::sort(ord.begin(), ord.begin() + 512);
        for (int i = 0; i < 512; ++i) sel[i] = ord[i] + 128;
        if (sel != dl) bad = true;
        const long n = ++chk_calls, nb_ = bad ? ++chk_bad : chk_bad.load();
        if (bad && nb_ <= 5) fprintf(stderr, "dev_index check: MISMATCH card %d layer %d len %ld pos %ld\n", t, L, len, (long)pos);
        if ((n & (n - 1)) == 0 || n % 4096 == 0)
            fprintf(stderr, "dev_index check: %ld lists, %ld mismatches (last: card %d layer %d len %ld)\n", n, nb_, t, L, len);
    }

#ifndef OWN41_ACT_BF16
    // RouteP in work-group 0 and the shared expert's gate and up rows in the
    // others, one launch (test_packed_v41_device.cpp "fused": 52 -> 28 us)
    // EX: extra sub-group rows in the same launch, before the shared rows (see HcFinishRows)
    template <typename DK, typename EX = ops41sycl::NoRows>
    void route_with_shared(int t, const std::string &p, DK dk, const uint8_t *wg, const uint8_t *wu, EX ex = {}) {
        auto &s = sc[t];
        using R1 = ops41sycl::DenseRows<DK>;
        using RR = ops41sycl::RowsPair<R1, R1>;
        using RX = std::conditional_t<std::is_same_v<EX, ops41sycl::NoRows>, RR, ops41sycl::RowsPair<EX, RR>>;
        using K = ops41sycl::RoutePRows<RX>;
        const RR rr{R1{dk, wg, s.xn, s.shg}, R1{dk, wu, s.xn, s.shu}};
        RX rx;
        if constexpr (std::is_same_v<EX, ops41sycl::NoRows>) rx = rr;
        else rx = RX{ex, rr};
        K k{ops41sycl::RouteP{g.experts, 6}, rx};
        const size_t ng = 1 + (rx.n() + 15) / 16;
        const float *logits = s.router, *bias = wp<float>(t, p + "exp_probs_b.bias");
        uint32_t *ids = s.ids;
        float *prob = s.prob;
        auto e = qs[t].submit([&](sycl::handler &hh) {
            sycl::local_accessor<float, 1> lt(2 * 1024 + 6, hh);
            hh.parallel_for(sycl::nd_range<1>(ng * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k(it, logits, bias, ids, prob, &lt[0]);
            });
        });
        kev(t, kname<K>(), e);
    }
    // true when the router and the shared gate/up rows went out in one launch
    bool route_shared_fused(int t, const std::string &p) {
        if (!o.small_fast || g.experts % 32 != 0 || g.experts > 512) return false;
        const auto &eg = we(p + "ffn_gate_shexp.weight"), &eu = we(p + "ffn_up_shexp.weight");
        const auto &dg = wgt[t].at(p + "ffn_gate_shexp.weight"), &du = wgt[t].at(p + "ffn_up_shexp.weight");
        if (!dg.packed || !du.packed || eg.type != eu.type || eg.rows != eu.rows || eg.cols != eu.cols ||
            eg.cols != 5120)
            return false;
        const unsigned rows = (unsigned)eg.rows;
        auto sh = wgt[t].at(p + "ffn_gate_shexp.weight").p, su = wgt[t].at(p + "ffn_up_shexp.weight").p;
        if (eg.type == iq3::Type::Q8_0)
            route_with_shared(t, p, ops41sycl::GemvQ8P<160, Act>{rows, 0}, (const uint8_t *)sh, (const uint8_t *)su);
        else if (eg.type == iq3::Type::Q5_K)
            route_with_shared(t, p, ops41sycl::GemvQ5KP<20, Act>{rows, 0}, (const uint8_t *)sh, (const uint8_t *)su);
        else
            return false;
        return true;
    }
#endif
    void moe(int L, int t) {
        auto &s = sc[t];
        const std::string p = "blk." + std::to_string(L) + ".";
        gemv(t, p + "ffn_gate_inp.weight", s.xn, s.router, true); // router logits stay f32
#ifndef OWN41_ACT_BF16
        if (route_shared_fused(t, p)) {
            prof("router", t);
            routed_gemv(t, p + "ffn_gate_exps.weight", s.xn, s.ids, s.expg, false);
            prof("exp_gate", t);
            routed_gemv(t, p + "ffn_up_exps.weight", s.xn, s.ids, s.expu, false);
            prof("exp_up", t);
            // routed SwiGLU + router weight and the shared SwiGLU, one launch
            launch(t, (size_t)7 * g.mid, 64, ops41sycl::SwigluBothA<Act>{6, g.mid, 10.0f}, (const act_t *)s.expg,
                   (const act_t *)s.expu, s.act, (const float *)s.prob, (const act_t *)s.shg, (const act_t *)s.shu,
                   s.sha);
            routed_gemv(t, p + "ffn_down_exps.weight", s.act, s.ids, s.expd, true);
            prof("exp_down", t);
            gemv(t, p + "ffn_down_shexp.weight", s.sha, s.shd);
            launch(t, g.h, 32, ops41sycl::MoeCombineA<Act>{6, g.h}, (const act_t *)s.expd, (const act_t *)s.shd,
                   s.ob);
            prof("shared", t);
            if (tracing()) {
                trf(L, TT_ROUTE_LOGITS, t, s.router, g.experts);
                tri(L, TT_ROUTE_IDS, t, s.ids, 6);
                trf(L, TT_ROUTE_PROB, t, s.prob, 6);
                tra(L, TT_SHARED_DOWN, t, s.shd, g.h);
            }
            return;
        }
#endif
        if (o.small_fast && g.experts % 32 == 0 && g.experts <= 1024) {
            // one work-group, same picks and arithmetic (test_small_v41_device.cpp)
            launch_local<2 * 1024 + 6>(t, (size_t)g.experts, ops41sycl::RouteP{g.experts, 6}, (const float *)s.router,
                                       wp<float>(t, p + "exp_probs_b.bias"), s.ids, s.prob);
        } else {
            // three launches, same picks and arithmetic as the one-work-item RouteF32
            launch(t, g.experts, 32, ops41sycl::RouteScore{g.experts}, (const float *)s.router,
                   wp<float>(t, p + "exp_probs_b.bias"), s.rs, s.rsb);
            launch(t, g.experts, 32, ops41sycl::RouteRank{g.experts, 6}, (const float *)s.rs, (const float *)s.rsb,
                   s.ids, s.prob);
            launch(t, 1, 1, ops41sycl::RouteNorm{6}, s.prob);
        }
        prof("router", t);
        routed_gemv(t, p + "ffn_gate_exps.weight", s.xn, s.ids, s.expg, false);
        prof("exp_gate", t);
        routed_gemv(t, p + "ffn_up_exps.weight", s.xn, s.ids, s.expu, false);
        prof("exp_up", t);
        if (o.small_fast) { // one launch (test_small_v41_device.cpp)
            launch(t, (size_t)6 * g.mid, 64, ops41sycl::SwigluProbA<Act>{6, g.mid, 10.0f}, (const act_t *)s.expg,
                   (const act_t *)s.expu, s.act, (const float *)s.prob);
        } else {
            launch(t, (size_t)6 * g.mid, 32, ops41sycl::SwigluA<Act>{(long long)6 * g.mid, 10.0f},
                   (const act_t *)s.expg, (const act_t *)s.expu, s.act);
            launch(t, (size_t)6 * g.mid, 32, ops41sycl::ProbScaleA<Act>{6, g.mid}, s.act, (const float *)s.prob);
        }
        routed_gemv(t, p + "ffn_down_exps.weight", s.act, s.ids, s.expd, true);
        prof("exp_down", t);
        gemv(t, p + "ffn_gate_shexp.weight", s.xn, s.shg);
        gemv(t, p + "ffn_up_shexp.weight", s.xn, s.shu);
        launch(t, g.mid, 32, ops41sycl::SwigluA<Act>{(long long)g.mid, 10.0f}, (const act_t *)s.shg,
               (const act_t *)s.shu, s.sha);
        gemv(t, p + "ffn_down_shexp.weight", s.sha, s.shd);
        launch(t, g.h, 32, ops41sycl::MoeCombineA<Act>{6, g.h}, (const act_t *)s.expd, (const act_t *)s.shd,
               s.ob);
        prof("shared", t);
        if (tracing()) {
            trf(L, TT_ROUTE_LOGITS, t, s.router, g.experts);
            tri(L, TT_ROUTE_IDS, t, s.ids, 6);
            trf(L, TT_ROUTE_PROB, t, s.prob, 6);
            tra(L, TT_SHARED_DOWN, t, s.shd, g.h);
        }
    }

    // ---- tensor-parallel decode (Options::tp > 1) ---------------------------
    // Every layer runs on all tp cards at once. Card c holds a row slice of
    // q_b (whole heads, following its o_a groups), attn_output_a (whole groups
    // of 1024 rows), attn_output_b, the expert and shared gate/up (rows of mid)
    // and down (rows of h) matrices and the head; everything else is
    // replicated and computed on every card. Per layer the cards swap four
    // slices card to card (XchgP): o_a out, o_b out, the SwiGLU outputs (6
    // routed + shared, one exchange), the MoE out. A slice is computed by the
    // same kernel over the same rows as on one card, so every value is
    // bit-identical. Card 0 ("lead") alone does the host-side work (publish,
    // index); the others wait for it (tp_mark) before they read the mirrors.
    // An exchange buffer is rewritten no earlier than two exchanges later and
    // every reader consumes it before its own next push, so one buffer each is
    // enough (no double buffering).
    int tog0[TILES] = {}, tog1[TILES] = {}, thq0[TILES] = {}, thq1[TILES] = {};
    int tm0[TILES] = {}, tm1[TILES] = {}, td0[TILES] = {}, td1[TILES] = {}, tv0[TILES] = {}, tv1[TILES] = {};
    unsigned xoa = 0, xob = 0, xact = 0, xeng = 0;
    int te0[TILES] = {}, te1[TILES] = {}; // engram_kv rows per card (eng_split)
    uint32_t eng_seq[TILES] = {};         // the engram push's exchange number
    bool fin_attn[TILES] = {};            // fin_move: this layer's attention mix finish waits for output-b's launch
    float *xarena[TILES] = {};
    void *xpeer[TILES][TILES] = {};
    uint32_t *xerr[TILES] = {};
    uint32_t xseq[TILES] = {};
    float *tlog[TILES] = {}, *tam_v[TILES] = {};
    int32_t *tam_i[TILES] = {};
    std::vector<float> h_amv[TILES];
    std::vector<int32_t> h_ami[TILES];
    static constexpr long XSPIN = 5000000; // ~0.9 s of flag polls, under the driver's hang check
    std::vector<std::thread> tp_th;
    std::mutex tp_mu;
    std::condition_variable tp_cv, tp_done_cv;
    std::atomic<long> tp_gen{0};
    std::atomic<int> tp_left{0};
    std::atomic<bool> tp_quit{false};
    // hand-offs: the caller sets the step up, tp_go starts every card thread on it, tp_join waits for all of them
    // (OWN_TP_SPIN_US: both sides poll first; the generation and the count change under tp_mu or are read under it
    // before sleeping, so a wake-up is never lost)
    void tp_go() {
        {
            std::lock_guard<std::mutex> lk(tp_mu);
            tp_err.clear();
            tp_left.store(o.tp);
            tp_gen.fetch_add(1);
        }
        tp_cv.notify_all();
    }
    template <typename F> static bool tp_poll(long us, F &&done) {
        if (us <= 0) return done();
        const auto t0 = std::chrono::steady_clock::now();
        for (unsigned k = 0;; ++k) {
            if (done()) return true;
            __builtin_ia32_pause();
            if ((k & 255) == 255 && std::chrono::steady_clock::now() - t0 > std::chrono::microseconds(us)) return done();
        }
    }
    void tp_join() {
        if (tp_poll(o.tp_spin_us, [&] { return tp_left.load() == 0; })) {
            std::lock_guard<std::mutex> lk(tp_mu); // tp_err was written under it
            return;
        }
        std::unique_lock<std::mutex> lk(tp_mu);
        tp_done_cv.wait(lk, [&] { return tp_left.load() == 0; });
    }
    std::string tp_err;
    std::atomic<bool> tp_abort{false};
    std::atomic<long> tp_mark{0};
    long tp_stepn = 0;
    int32_t tp_tok = 0;
    bool tp_hostprof = getenv("OWN_TP_HOSTPROF") != nullptr; // host time per card thread: busy vs blocked
    double tph_step[TILES] = {}, tph_wait[TILES] = {};
    long tph_n = 0;
    void twait(int c) {
        if (!tp_hostprof || o.tp <= 1) { qs[c].wait(); return; }
        const double t0 = now_s();
        qs[c].wait();
        tph_wait[c] += now_s() - t0;
    }
    long tlen[TILES][4] = {};         // rows of each kv source on card c (tp: every card publishes for itself)
    act_t *teng[TILES][2] = {};       // engram rows of layers 1 / 14, uploaded at step start

    // rows of tensor n held by card c (all rows unless tp splits it)
    std::pair<unsigned, unsigned> tp_rows(const std::string &n, const WeightTab::E &e, int c) const {
        const unsigned R = (unsigned)e.rows;
        if (o.tp <= 1) return {0, R};
        auto need = [&](long want) {
            if (e.rows != want) throw std::runtime_error("tensor parallel: unexpected rows in " + n);
        };
        if (n == "output.weight") { need(g.vocab); return {(unsigned)tv0[c], (unsigned)tv1[c]}; }
        // the DSpark draft ("dsp." names, same layer geometry as the target): split as the target's layers;
        // its input projection by model rows, its Markov output rows by vocabulary
        const bool dsp = n.rfind("dsp.", 0) == 0;
        // (dsp.fc.weight, 15360 columns, is not packable: the generic rows read the whole matrix, so every
        // card holds all of it and projects the features alone, without an exchange)
        if (dsp && n == "dsp.markov_w2.weight") { need(g.vocab); return {(unsigned)tv0[c], (unsigned)tv1[c]}; }
        // OWN_DR_FC_SPLIT (default): dsp.fc by model rows like attn_output_b, its rows all-gathered in dr_inject
        if (dsp && n == "dsp.fc.weight" && o.dr_fc_split) { need(g.h); return {(unsigned)td0[c], (unsigned)td1[c]}; }
        const std::string nl = dsp ? n.substr(4) : n;
        if (layer_of_name(nl) < 0) return {0, R};
        const std::string suf = nl.substr(nl.find('.', 4) + 1);
        if (suf == "attn_q_b.weight") { need((long)g.qh * g.hd); return {(unsigned)(thq0[c] * g.hd), (unsigned)(thq1[c] * g.hd)}; }
        if (suf == "attn_output_a.weight") {
            need(g.ototal);
            const unsigned per = (unsigned)g.ototal / 8;
            return {tog0[c] * per, tog1[c] * per};
        }
        if (suf == "attn_output_b.weight" || suf == "ffn_down_exps.weight" || suf == "ffn_down_shexp.weight") {
            need(g.h);
            return {(unsigned)td0[c], (unsigned)td1[c]};
        }
        if (suf == "engram_kv.weight" && o.eng_split) {
            need(5L * g.h);
            return {(unsigned)te0[c], (unsigned)te1[c]};
        }
        if (suf == "ffn_gate_exps.weight" || suf == "ffn_up_exps.weight" || suf == "ffn_gate_shexp.weight" ||
            suf == "ffn_up_shexp.weight") {
            need(g.mid);
            return {(unsigned)tm0[c], (unsigned)tm1[c]};
        }
        return {0, R};
    }

    void tp_setup() {
        const int N = o.tp;
        if (g.ototal % 8 || g.qh % 8 || g.h % 16 || g.mid % 16 || g.ototal / 8 * 8 != g.ototal || g.oin != g.qh / 8 * g.hd)
            throw std::runtime_error("tensor parallel: geometry");
        // rows [a, b) of n for card c in units of al, shares by weight w (all 0: equal, u * c / N as before)
        for (const int *w : {o.tp_w, o.tp_vw}) {
            int nz = 0;
            for (int d = 0; d < N; ++d) nz += w[d] > 0;
            if (nz != 0 && nz != N) throw std::runtime_error("tensor parallel: OWN_TP_WEIGHTS needs a weight per card");
        }
        auto split = [&](int n, int c, int al, const int *w) {
            long W = 0, Wc = 0;
            for (int d = 0; d < N; ++d) {
                const long wd = w[d] > 0 ? w[d] : 1;
                if (d < c) Wc += wd;
                W += wd;
            }
            const long u = n / al, wc = w[c] > 0 ? w[c] : 1;
            const int a = (int)(u * Wc / W) * al, b = c + 1 == N ? n : (int)(u * (Wc + wc) / W) * al;
            return std::pair<int, int>{a, b};
        };
        for (int c = 0; c < N; ++c) {
            tog0[c] = 8 * c / N;
            tog1[c] = 8 * (c + 1) / N;
            if (tog1[c] <= tog0[c]) throw std::runtime_error("tensor parallel: more cards than output groups");
            thq0[c] = tog0[c] * g.qh / 8;
            thq1[c] = tog1[c] * g.qh / 8;
            std::tie(tm0[c], tm1[c]) = split(g.mid, c, 16, o.tp_w);
            std::tie(td0[c], td1[c]) = split(g.h, c, 16, o.tp_w);
            std::tie(tv0[c], tv1[c]) = split(g.vocab, c, 16, o.tp_vw);
            std::tie(te0[c], te1[c]) = split(5 * g.h, c, 16, o.tp_w);
            if ((thq1[c] - thq0[c]) % 4) throw std::runtime_error("tensor parallel: heads per card % 4");
            if (tm1[c] <= tm0[c] || td1[c] <= td0[c] || tv1[c] <= tv0[c] || te1[c] <= te0[c])
                throw std::runtime_error("tensor parallel: a card without rows (OWN_TP_WEIGHTS)");
        }
        if (o.tp_w[0] > 0 || o.tp_vw[0] > 0) {
            std::fprintf(stderr, "tensor parallel rows per card (mid / model / vocab):");
            for (int c = 0; c < N; ++c)
                std::fprintf(stderr, " %d/%d/%d", tm1[c] - tm0[c], td1[c] - td0[c], tv1[c] - tv0[c]);
            std::fprintf(stderr, "\n");
        }
        xoa = 1024; // [0, 1024): flags, uint32 16 * card
        xob = xoa + (unsigned)g.ototal;
        xact = xob + (unsigned)g.h;
        xeng = xact + 7 * (unsigned)g.mid; // two engram layers' kv rows, 5 * h each
#ifndef OWN41_ACT_BF16
        mt_offsets(xeng + 10 * (size_t)g.h); // the multi-token step's regions follow
        const size_t nf = xeng + 10 * (size_t)g.h + mt_arena_floats();
#else
        const size_t nf = xeng + 10 * (size_t)g.h;
#endif
        for (int c = 0; c < N; ++c) {
            xarena[c] = dalloc<float>(c, nf);
            xcnt[c] = dalloc<uint32_t>(c, 16);
            qs[c].memset(xcnt[c], 0, 64);
            xerr[c] = sycl::malloc_host<uint32_t>(4, ctxs[c]);
            if (!xerr[c]) throw std::runtime_error("host error word");
            std::memset(xerr[c], 0, 16);
            touch(c, xerr[c]);
            auto &s = sc[c];
            s.oa = xarena[c] + xoa;
            s.ob = xarena[c] + xob;
            s.act = xarena[c] + xact;
            s.sha = s.act + (size_t)6 * g.mid;
            teng[c][0] = dalloc<act_t>(c, (size_t)24 * g.engram_dim);
            teng[c][1] = dalloc<act_t>(c, (size_t)24 * g.engram_dim);
            if (o.eng_dev) {
                if (g.engram_dim != 256) throw std::runtime_error("OWN_ENG_DEV: engram rows of one Q5_K block expected");
                for (int li = 0; li < 2; ++li) {
                    tengr[c][li] = dalloc<uint8_t>(c, (size_t)24 * 176);
                    for (int f = 0; f < 2; ++f) h_engr[c][li][f].resize((size_t)24 * 176);
                }
            }
#ifndef OWN41_ACT_BF16
            mt_alloc(c);
#endif
            if (o.head) {
                const int nl = tv1[c] - tv0[c], G = (nl + AM_CH - 1) / AM_CH;
                tlog[c] = dalloc<float>(c, nl);
                tam_v[c] = dalloc<float>(c, G);
                tam_i[c] = dalloc<int32_t>(c, G);
            }
            qs[c].wait();
        }
        for (int d = 0; d < N; ++d) {
            auto zxd = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctxs[d]);
            auto zdd = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(devs[d]);
            ze_ipc_mem_handle_t h;
            if (zeMemGetIpcHandle(zxd, xarena[d], &h) != ZE_RESULT_SUCCESS)
                throw std::runtime_error("zeMemGetIpcHandle failed on card " + pci[d]);
            for (int c = 0; c < N; ++c) {
                if (c == d) { xpeer[c][d] = xarena[d]; continue; }
                auto zxc = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(ctxs[c]);
                auto zdc = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(devs[c]);
                ze_bool_t can = 0;
                if (zeDeviceCanAccessPeer(zdc, zdd, &can) != ZE_RESULT_SUCCESS || !can)
                    throw std::runtime_error("card " + pci[c] + " cannot access card " + pci[d]);
                void *ptr = nullptr;
                if (zeMemOpenIpcHandle(zxc, zdc, h, 0, &ptr) != ZE_RESULT_SUCCESS || !ptr)
                    throw std::runtime_error("zeMemOpenIpcHandle failed: card " + pci[c] + " <- " + pci[d]);
                xpeer[c][d] = ptr;
                touch(c, ptr);
            }
        }
        for (int c = 0; c < N; ++c) qs[c].wait();
        if (o.tp_threads)
            for (int c = 0; c < N; ++c) tp_th.emplace_back([this, c] { tp_worker(c); });
        auto pin = [&](pthread_t t, int cpu, const char *who) {
            if (cpu < 0) return;
            cpu_set_t cs;
            CPU_ZERO(&cs);
            CPU_SET(cpu, &cs);
            if (pthread_setaffinity_np(t, sizeof cs, &cs) != 0)
                throw std::runtime_error(std::string("OWN_TP_PIN: cannot pin the ") + who + " thread to CPU " +
                                         std::to_string(cpu));
        };
        for (int c = 0; c < (int)tp_th.size() && c < 6; ++c) pin(tp_th[c].native_handle(), o.tp_pin[c], "card");
        // (the main thread's CPU, OWN_TP_PIN's seventh entry, is set by the runner after the upload: the upload's
        // threads would otherwise inherit it)
    }

#ifndef OWN41_ACT_BF16
    // all-gather of rows [r0, r1) of nslot slots (stride floats) at arena offset off
    // mode 0: push this card's rows and wait for every peer's; 1: push only (the wait is a later exchange's,
    // whose flags come after this one's in every peer's queue); 2: wait only for exchange number seq
    // part (XP_*) names whose rows every card owns (xbounds); the exchanges of one part and slot count take the
    // same form on every card (use_pull decides from all cards' rows), stores (XchgP) or loads (XchgPull)
    uint32_t xchg(int c, unsigned off, unsigned stride, unsigned nslot, unsigned r0, unsigned r1, int mode = 0,
                  uint32_t seq = 0, int part = -1) {
        float *P[6] = {};
        for (int d = 0; d < o.tp; ++d) P[d] = (float *)xpeer[c][d];
        if (mode != 2) seq = ++xseq[c];
        if (use_pull(part, nslot)) {
            ops41sycl::XchgPull x{o.tp, c, off, stride, nslot, {}, {}, seq, XSPIN, mode};
            xbounds(part, x.b0, x.b1);
            if (x.b0[c] != r0 || x.b1[c] != r1) throw std::runtime_error("exchange: rows do not match the part");
            size_t nv = 0;
            for (int d = 0; d < o.tp; ++d)
                if (d != c) nv += (size_t)nslot * ((x.b1[d] - x.b0[d]) / 4);
            const size_t nwg = mode == 1 ? 1 : std::clamp<size_t>((nv + 511) / 512, 4, 64);
            float *p0 = P[0], *p1 = P[1], *p2 = P[2], *p3 = P[3], *p4 = P[4], *p5 = P[5];
            uint32_t *err = xerr[c];
            auto e = qs[c].submit([&](sycl::handler &hh) {
                hh.parallel_for(sycl::nd_range<1>(nwg * 256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                    x(it, p0, p1, p2, p3, p4, p5, err);
                });
            });
            kev(c, kname<ops41sycl::XchgPull>(), e);
            return seq;
        }
        launch_wg(c, 256, ops41sycl::XchgP{o.tp, c, off, stride, nslot, r0, r1, seq, XSPIN, mode}, P[0], P[1], P[2],
                  P[3], P[4], P[5], xerr[c]);
        return seq;
    }
    enum { XP_OA = 0, XP_H = 1, XP_ACT = 2, XP_ENG = 3 };
    void xbounds(int part, unsigned *b0, unsigned *b1) const {
        const unsigned per = (unsigned)g.ototal / 8;
        for (int d = 0; d < 6; ++d) {
            b0[d] = b1[d] = 0;
            if (d >= o.tp) continue;
            switch (part) {
            case XP_OA: b0[d] = tog0[d] * per, b1[d] = tog1[d] * per; break;
            case XP_H: b0[d] = td0[d], b1[d] = td1[d]; break;
            case XP_ACT: b0[d] = tm0[d], b1[d] = tm1[d]; break;
            case XP_ENG: b0[d] = te0[d], b1[d] = te1[d]; break;
            default: throw std::runtime_error("exchange part");
            }
            if ((b1[d] - b0[d]) % 4 || b0[d] % 4) throw std::runtime_error("exchange rows not multiples of 4");
        }
    }
    bool use_pull(int part, unsigned nslot) const {
        if (!o.xpull || part < 0 || o.tp > 6) return false;
        unsigned b0[6], b1[6];
        xbounds(part, b0, b1);
        size_t mx = 0;
        for (int d = 0; d < o.tp; ++d) mx = std::max<size_t>(mx, (size_t)(b1[d] - b0[d]) * nslot * 4);
        return mx >= o.xpull_min;
    }
    // this card's rows of a dense matrix -> y[0, nrows) (packed rows); xn as gemv_kp
    void gemv_part(int t, const std::string &wn, const act_t *x, act_t *y, unsigned xn = 0) {
        const auto &e = we(wn);
        const auto &dp = wgt[t].at(wn);
        if (!dp.packed) throw std::runtime_error("tensor-parallel slice needs packed rows: " + wn);
        gemv_kp(t, e, dp.p, x, y, dp.nrows, xn, (unsigned)e.cols, wn);
    }
    template <typename EX = ops41sycl::NoRows> void route_shared_tp(int c, const std::string &p, EX ex = {}) {
        const auto &eg = we(p + "ffn_gate_shexp.weight"), &eu = we(p + "ffn_up_shexp.weight");
        const auto &dg = wgt[c].at(p + "ffn_gate_shexp.weight"), &du = wgt[c].at(p + "ffn_up_shexp.weight");
        if (!o.small_fast || g.experts % 32 != 0 || g.experts > 512 || !dg.packed || !du.packed || eg.type != eu.type ||
            eg.cols != eu.cols || eg.cols != 5120 || dg.nrows != du.nrows)
            throw std::runtime_error("tensor parallel needs the fused router + shared gate/up launch: " + p);
        const unsigned rows = dg.nrows;
        if (eg.type == iq3::Type::Q8_0)
            route_with_shared(c, p, ops41sycl::GemvQ8P<160, Act>{rows, 0}, (const uint8_t *)dg.p, (const uint8_t *)du.p, ex);
        else if (eg.type == iq3::Type::Q5_K)
            route_with_shared(c, p, ops41sycl::GemvQ5KP<20, Act>{rows, 0}, (const uint8_t *)dg.p, (const uint8_t *)du.p, ex);
        else
            throw std::runtime_error("tensor parallel: shared expert format " + p);
    }
    void tp_wait_mark(long v) {
        for (long i = 0; tp_mark.load(std::memory_order_acquire) < v; ++i) {
            if (tp_abort.load()) throw std::runtime_error("lead card failed");
            if (i > 256) std::this_thread::yield();
        }
    }
    // one layer = phases 0..5; a phase ends where the cards exchange (1-4)
    void tp_phase(int L, int c, int ph) {
        auto &s = sc[c];
        const std::string p = "blk." + std::to_string(L) + ".";
        const int cr = cr_of(L);
        const bool yarn = cr > 0;
        const int si = src_index(L);
        const bool lead = c == 0;
        const bool host_work = cr && index_slot(L) >= 0 && tlen[c][si] > 512 && !o.dev_index; // the lead's host top-k
        const int nh = thq1[c] - thq0[c];
        const size_t qo = (size_t)thq0[c] * g.hd;
        switch (ph) {
        case 0: {
            if (L == 1 || L == 14) {
                engram_tp(L, c);
                prof("engram", c);
            }
            // the attention's pre-norm takes the previous FFN's pre-mix (cur_pre), so this sublayer's stream
            // mix is first read at hc_post: its dot rows ride in q_a's launch, its finish in q_b's
            const bool ride = hc_rides(c, p + "hc_attn_") && wgt[c].at(p + "attn_q_a.weight").packed;
            if (!ride) {
                hc_mix(c, p + "hc_attn_", s.pre_a, s.post_a, s.comb_a);
                prof("hc_mix", c);
            }
            bool dots_done = false; // the mix's dot rows already ran (in the norm's launch)
            if (x_ready[c]) { // the previous FFN's hc_post already collapsed the streams into s.x (HcPostPreP)
                if (ride && o.norm_dots && attn_in_diet(c, p))
                    dots_done = norm_ex(c, s.x, p + "attn_norm.weight", s.xn, hc_dots(c, p + "hc_attn_"));
                if (!dots_done) rmsnorm(c, s.x, p + "attn_norm.weight", g.h, s.xn);
                x_ready[c] = false;
            } else {
                pre_norm(c, (const float *)s.cur_pre, p + "attn_norm.weight");
            }
            prof("hc_pre_norm", c);
            if (ride && attn_in_diet(c, p)) {
                // four launches: query-a + key/value rows (+ the mix's dot rows); both norms; query-b rows
                // (+ the mix's finish + the key's rope); the query's rope
                if (cpos(c) < 0 || cpos(c) >= max_seq) throw std::runtime_error("position beyond max_seq");
                const float *cb = (yarn ? cos_yarn[c] : cos_base[c]) + (size_t)cpos(c) * 32;
                const float *sbp = (yarn ? sin_yarn[c] : sin_base[c]) + (size_t)cpos(c) * 32;
                const bool pair_ok = dots_done ? gemv_pair_ex(c, p + "attn_q_a.weight", s.qa, p + "attn_kv.weight",
                                                              s.kv, s.xn, ops41sycl::NoRows{})
                                               : gemv_pair_ex(c, p + "attn_q_a.weight", s.qa, p + "attn_kv.weight",
                                                              s.kv, s.xn, hc_dots(c, p + "hc_attn_"));
                if (!pair_ok) throw std::runtime_error("query-a / key-value pair launch: " + p);
                using NR = ops41sycl::RowsPair<ops41sycl::NormRows<1280, 4>, ops41sycl::NormRows<512, 2>>;
                const NR nr{{s.qa, wp<float>(c, p + "attn_q_a_norm.weight"), s.qn},
                            {s.kv, wp<float>(c, p + "attn_kv_a_norm.weight"), s.kvn}};
                launch_rows<0>(c, nr.n(), 0, ops41sycl::RowsP<NR>{nr});
                prof("attn_q_a", c);
                if (o.fin_move) { // the mix's finish rides in output-b's launch instead (case 2)
                    gemv_part_ex(c, p + "attn_q_b.weight", s.qn, s.q + qo,
                                 ops41sycl::RopeRows<Act>{s.kvn, cb, sbp, 1u, (unsigned)g.hd, false});
                    fin_attn[c] = true;
                } else {
                    gemv_part_ex(c, p + "attn_q_b.weight", s.qn, s.q + qo,
                                 ops41sycl::RowsPair<ops41sycl::HcFinishRows, ops41sycl::RopeRows<Act>>{
                                     hc_finish(c, p + "hc_attn_", s.pre_a, s.post_a, s.comb_a),
                                     ops41sycl::RopeRows<Act>{s.kvn, cb, sbp, 1u, (unsigned)g.hd, false}});
                }
                launch_rows<0>(c, (size_t)nh, 0,
                               ops41sycl::RowsP<ops41sycl::RopeRows<Act>>{
                                   {s.q + qo, cb, sbp, (unsigned)nh, (unsigned)g.hd, false}});
                prof("attn_q_b", c);
            } else {
                if (ride) gemv_ex(c, p + "attn_q_a.weight", s.xn, s.qa, hc_dots(c, p + "hc_attn_"));
                else gemv(c, p + "attn_q_a.weight", s.xn, s.qa);
                rmsnorm(c, s.qa, p + "attn_q_a_norm.weight", g.qrank, s.qn);
                prof("attn_q_a", c);
                if (ride)
                    gemv_part_ex(c, p + "attn_q_b.weight", s.qn, s.q + qo,
                                 hc_finish(c, p + "hc_attn_", s.pre_a, s.post_a, s.comb_a));
                else gemv_part(c, p + "attn_q_b.weight", s.qn, s.q + qo);
                rope(c, s.q + qo, nh, g.hd, cpos(c), yarn, false);
                prof("attn_q_b", c);
                gemv(c, p + "attn_kv.weight", s.xn, s.kv);
                rmsnorm(c, s.kv, p + "attn_kv_a_norm.weight", g.hd, s.kvn);
                rope(c, s.kvn, 1, g.hd, cpos(c), yarn, false);
                prof("attn_kv", c);
            }
            if (cr && is_kv_source(L)) { // every card publishes for itself: no host round trip
                publish_tp(L, c, si, yarn);
                prof("publish", c);
            }
            if (cr && index_slot(L) >= 0) {
                const long len = tlen[c][si];
                if (len <= 512) { // all rows in order (index()'s short path), filled on every card
                    launch(c, 512, 64, ops41sycl::CidxFill{(int)len, 512}, cidx_mirror[c][index_slot(L)]);
                    if (lead && L == 20) {
                        cand_host.assign(len, 1);
                        cand_valid = true;
                    }
                    if (L == 20) dcand_ok[c] = false; // every row a candidate: layers 24-36 are short too
                } else if (o.dev_index) {
                    dev_index(L, c, si, yarn, len);
                } else if (lead) { // scores + top-k on the host; the others copy the list (tp_mark)
                    index(L, c, si, yarn, len);
                    tp_mark.store(tp_stepn * 64 + L + 1, std::memory_order_release);
                }
                prof("index", c);
            }
            break;
        }
        case 1: {
            if (g.hd != 512) throw std::runtime_error("tensor parallel: head dim");
            int n_idx = 128;
            if (cr) {
                if (!lead && host_work && !tp_th.empty()) tp_wait_mark(tp_stepn * 64 + L + 1);
                sync_rows(c, si);
                sync_cidx(c, isrc_for(L));
                launch(c, (size_t)std::max(g.hd, 512), 64, ops41sycl::WindowAppendP<Act>{128, g.hd, (int)cpos(c), 512},
                       ring[c][L], (const act_t *)s.kvn, s.widx, s.idxs_cat,
                       (const int32_t *)cidx_mirror[c][isrc_for(L)]);
                n_idx += 512;
            } else {
                launch(c, (size_t)std::max(g.hd, 128), 64, ops41sycl::WindowAppendP<Act>{128, g.hd, (int)cpos(c), 0},
                       ring[c][L], (const act_t *)s.kvn, s.widx, s.idxs_cat, (const int32_t *)nullptr);
            }
            const uint16_t *kvw = ring[c][L], *kvc = cr ? ckv_mirror[c][si] : ring[c][L];
            if (!al16(kvw) || !al16(kvc)) throw std::runtime_error("tensor parallel: kv alignment");
            const float *sinks = wp<float>(c, p + "attn_sinks.weight") + thq0[c];
            const int32_t *ix = (const int32_t *)s.idxs_cat;
            // the attention reads little: output-a's and output-b's rows are pulled into the cache meanwhile
            const Pf pfa = pf_of(c, p + "attn_output_a.weight"), pfb = pf_of(c, p + "attn_output_b.weight");
            if (n_idx == 128) {
                launch_sg_pf(c, (size_t)nh * n_idx / 32, pfa, ops41sycl::SparseScoreP<512>{n_idx, nh, 128, g.hd},
                             (const act_t *)(s.q + qo), kvw, kvc, ix, s.attn_w);
                launch_sg(c, nh, ops41sycl::SparseSoftmaxP<128>{nh}, sinks, ix, s.attn_w);
            } else {
                launch_sg_pf(c, (size_t)(nh / 4) * (n_idx / 32), pfa,
                             ops41sycl::SparseScoreHG<512, 4>{n_idx, nh, 128, g.hd}, (const act_t *)(s.q + qo), kvw,
                             kvc, ix, s.attn_w);
                launch_sg(c, nh, ops41sycl::SparseSoftmaxP<640>{nh}, sinks, ix, s.attn_w);
            }
            if (cpos(c) < 0 || cpos(c) >= max_seq) throw std::runtime_error("position beyond max_seq");
            const float *cb = (yarn ? cos_yarn[c] : cos_base[c]) + (size_t)cpos(c) * 32;
            const float *sbp = (yarn ? sin_yarn[c] : sin_base[c]) + (size_t)cpos(c) * 32;
            ops41sycl::SparseOutJB<512, 1, 16> so{n_idx, nh, 128};
            if (o.rope_out) { // the inverse rope in the output's store (f32 activations: obuf is f32 too)
                so.ry = (float *)(s.obuf + qo);
                so.cosb = cb;
                so.sinb = sbp;
            }
            launch_sg_pf(c, (size_t)nh * g.hd / 64, pfb, so, kvw, kvc, ix, (const float *)s.attn_w, s.of + qo);
            prof("sparse_attn", c);
            if (!o.rope_out)
                launch(c, (size_t)nh * g.hd, 64, ops41sycl::ToActRopeA<Act>{(unsigned)nh, (unsigned)g.hd, 64u, true},
                       (const float *)(s.of + qo), s.obuf + qo, cb, sbp);
            const unsigned per = (unsigned)g.ototal / 8;
            arm_xtail(c, xoa, (unsigned)g.ototal, 1, tog0[c] * per, tog1[c] * per, XP_OA);
            gemv_part(c, p + "attn_output_a.weight", s.obuf + (size_t)tog0[c] * g.oin, s.oa + (size_t)tog0[c] * per, per);
            prof("attn_o_a", c);
            end_xtail(c);
            prof("xchg", c);
            break;
        }
        case 2:
            arm_xtail(c, xob, (unsigned)g.h, 1, td0[c], td1[c], XP_H);
            if (fin_attn[c]) {
                gemv_part_ex(c, p + "attn_output_b.weight", s.oa, s.ob + td0[c],
                             hc_finish(c, p + "hc_attn_", s.pre_a, s.post_a, s.comb_a));
                fin_attn[c] = false;
            } else {
                gemv_part(c, p + "attn_output_b.weight", s.oa, s.ob + td0[c]);
            }
            prof("attn_o_b", c);
            end_xtail(c);
            prof("xchg", c);
            break;
        case 3: {
            // the FFN's pre-norm takes the attention's pre-mix (pre_a): the FFN mix is first read at the
            // next hc_post, so its dot rows ride in the router launch, its finish with the shared rows
            const bool ride = hc_rides(c, p + "hc_ffn_");
            bool ffn_dots_done = false; // the FFN mix's dot rows already ran (in the norm's launch)
            if (ride && post_pre_ok()) { // hc_post and the FFN's stream collapse in one launch
                launch(c, (size_t)g.h, 64, ops41sycl::HcPostPreP<Act>{g.h}, streams[c], (const act_t *)s.ob,
                       (const float *)s.post_a, (const float *)s.comb_a, (const float *)nullptr, (float *)nullptr,
                       (const float *)s.pre_a, s.x);
                prof("hc_post", c);
                if (o.norm_dots) ffn_dots_done = norm_ex(c, s.x, p + "ffn_norm.weight", s.xn, hc_dots(c, p + "hc_ffn_"));
                if (!ffn_dots_done) rmsnorm(c, s.x, p + "ffn_norm.weight", g.h, s.xn);
            } else {
                hc_post(c, s.post_a, s.comb_a, nullptr, nullptr);
                prof("hc_post", c);
                if (!ride) {
                    hc_mix(c, p + "hc_ffn_", s.pre_f, s.post_f, s.comb_f);
                    prof("hc_mix", c);
                }
                pre_norm(c, (const float *)(o.hc_legacy ? s.pre_f : s.pre_a), p + "ffn_norm.weight");
            }
            prof("hc_pre_norm", c);
            // with the expert gate + up launch the FFN mix's finish rides there (a long launch, finish first)
            const bool fin_pair = ride && o.fin_move && o.exp_pair &&
                                  routed_pair_fits(c, p + "ffn_gate_exps.weight", p + "ffn_up_exps.weight");
            if (ride) {
                if (ffn_dots_done) gemv(c, p + "ffn_gate_inp.weight", s.xn, s.router, true);
                else gemv_ex(c, p + "ffn_gate_inp.weight", s.xn, s.router, hc_dots(c, p + "hc_ffn_"));
                if (fin_pair) route_shared_tp(c, p);
                else route_shared_tp(c, p, hc_finish(c, p + "hc_ffn_", s.pre_f, s.post_f, s.comb_f));
            } else {
                gemv(c, p + "ffn_gate_inp.weight", s.xn, s.router, true);
                route_shared_tp(c, p);
            }
            prof("router", c);
            if (fin_pair) {
                routed_pair(c, p + "ffn_gate_exps.weight", p + "ffn_up_exps.weight", s.xn, s.ids, s.expg, s.expu,
                            hc_finish(c, p + "hc_ffn_", s.pre_f, s.post_f, s.comb_f));
            } else if (!o.exp_pair ||
                       !routed_pair(c, p + "ffn_gate_exps.weight", p + "ffn_up_exps.weight", s.xn, s.ids, s.expg, s.expu)) {
                routed_gemv(c, p + "ffn_gate_exps.weight", s.xn, s.ids, s.expg, false);
                prof("exp_gate", c);
                routed_gemv(c, p + "ffn_up_exps.weight", s.xn, s.ids, s.expu, false);
            }
            prof("exp_up", c);
            const int nm = tm1[c] - tm0[c];
            arm_xtail(c, xact, (unsigned)g.mid, 7, tm0[c], tm1[c], XP_ACT);
            launch(c, (size_t)7 * nm, 64, ops41sycl::SwigluBothS<Act>{6, nm, 10.0f, g.mid}, (const act_t *)s.expg,
                   (const act_t *)s.expu, s.act + tm0[c], (const float *)s.prob, (const act_t *)s.shg,
                   (const act_t *)s.shu, s.act + (size_t)6 * g.mid + tm0[c]);
            end_xtail(c);
            prof("xchg", c);
            break;
        }
        case 4: {
            const int nd = td1[c] - td0[c];
            if (!o.down_ex || !down_with_shared(c, p)) {
                routed_gemv(c, p + "ffn_down_exps.weight", s.act, s.ids, s.expd, true);
                prof("exp_down", c);
                gemv_part(c, p + "ffn_down_shexp.weight", s.act + (size_t)6 * g.mid, s.shd);
            }
            arm_xtail(c, xob, (unsigned)g.h, 1, td0[c], td1[c], XP_H);
            launch(c, nd, 32, ops41sycl::MoeCombineA<Act>{6, nd}, (const act_t *)s.expd, (const act_t *)s.shd,
                   s.ob + td0[c]);
            prof("shared", c);
            end_xtail(c);
            prof("xchg", c);
            break;
        }
        case 5: {
            // with the next attention's stream collapse (its mix = this FFN's pre-mix, copied to cur_pre here)
            // unless the next layer adds its engram row first, or nothing follows
            const int Ln = L + 1;
            if (post_pre_ok() && Ln != 1 && Ln != 14 && (Ln < o.layer_end || o.head)) {
                launch(c, (size_t)g.h, 64, ops41sycl::HcPostPreP<Act>{g.h}, streams[c], (const act_t *)s.ob,
                       (const float *)s.post_f, (const float *)s.comb_f, (const float *)s.pre_f, s.cur_pre,
                       (const float *)s.pre_f, s.x);
                x_ready[c] = true;
            } else {
                hc_post(c, s.post_f, s.comb_f, s.pre_f, s.cur_pre);
            }
            prof("hc_post", c);
            break;
        }
        }
    }
    // publish() on card c, appending to its own mirrors (same kernels, same BF16 rounding)
    void publish_tp(int L, int c, int si, bool yarn) {
        auto &s = sc[c];
        const std::string p = "blk." + std::to_string(L) + ".";
        long gpos;
        if (cr_of(L) == 1) {
            gemv(c, p + "attn_compressor_kv.weight", s.xn, s.cw);
            rmsnorm(c, s.cw, p + "attn_compressor_norm.weight", g.hd, s.latent);
            gpos = cpos(c);
        } else {
            gemv(c, p + "attn_compressor_kv.weight", s.xn, s.cw);
            gemv(c, p + "attn_compressor_gate.weight", s.xn, s.scg);
            const int slot = (int)(cpos(c) % 2);
            launch(c, g.hd, 32, ops41sycl::ToF32A<Act>{g.hd}, (const act_t *)s.cw,
                   s.kv_state + (size_t)si * 2 * g.hd + (size_t)slot * g.hd);
            launch(c, g.hd, 32, ops41sycl::ToF32A<Act>{g.hd}, (const act_t *)s.scg,
                   s.score_state + (size_t)si * 2 * g.hd + (size_t)slot * g.hd);
            if (cpos(c) % 2 == 0) return;
            gpos = cpos(c) - 1;
            if (!o.small_fast || g.hd > 1024) throw std::runtime_error("tensor parallel: compressor pool form");
            launch_local<1024>(c, 32, ops41sycl::CompressPoolP<Act>{2, g.hd},
                               (const float *)(s.kv_state + (size_t)si * 2 * g.hd),
                               (const float *)(s.score_state + (size_t)si * 2 * g.hd),
                               wp<float>(c, p + "attn_compressor_norm.weight"), s.latent);
        }
        gemv(c, p + "indexer.attn_k.weight", s.latent, s.kk);
        rmsnorm(c, s.kk, p + "indexer.k_norm.weight", 128, s.kk);
        rope(c, s.kk, 1, 128, gpos, yarn, false);
        rope(c, s.latent, 1, g.hd, gpos, yarn, false);
        const size_t cap = si == 3 ? (size_t)max_seq + 2 : (size_t)max_seq / 2 + 2;
        if ((size_t)tlen[c][si] + 1 > cap) throw std::runtime_error("compressed cache full (max_seq)");
        launch(c, (size_t)std::max(g.hd, 128), 64, ops41sycl::PubAppendA<Act>{g.hd, 128, (int)tlen[c][si]},
               (const act_t *)s.latent, (const act_t *)s.kk, ckv_mirror[c][si], ik_mirror[c][si]);
        ++tlen[c][si];
    }
    // engram rows for this step's two engram layers: decoded and uploaded at step start
    // (the queue is empty then), so layers 1 and 14 do not drain it
    void tp_engram_upload(int c) {
        auto l = iq3::layout(iq3::Type::Q5_K);
        for (int li = 0; li < 2; ++li) {
            const int L = li == 0 ? 1 : 14;
            if (L < o.layer_begin || L >= o.layer_end || !eng_base[li]) continue;
            if ((long)comp_ids.size() <= cpos(c)) throw std::runtime_error("comp_ids behind position");
            int64_t ids[24];
            engram_hash((int)cpos(c), li, ids);
            const unsigned fl = eng_flip[c][li]++ & 1;
            if (o.eng_dev) {
                uint8_t *raw = h_engr[c][li][fl].data();
                for (int k = 0; k < 24; ++k)
                    std::memcpy(raw + (size_t)k * l.bytes, eng_base[li] + (size_t)ids[k] * l.bytes, l.bytes);
                const auto q0 = std::chrono::steady_clock::now();
                qs[c].memcpy(tengr[c][li], raw, (size_t)24 * l.bytes);
                launch(c, (size_t)24 * 256, 256, ops41sycl::EngRowsA<Act>{24u}, (const uint8_t *)tengr[c][li], teng[c][li]);
                eng_tq[c] += std::chrono::duration<double>(std::chrono::steady_clock::now() - q0).count();
                continue;
            }
            std::vector<act_t> &rows = h_eng[c][li][fl];
            for (int k = 0; k < 24; ++k) {
                const uint8_t *row = eng_base[li] + (size_t)ids[k] * l.bytes;
                for (int i = 0; i < 256; ++i) rows[k * 256 + i] = Act::wr(iq3::decode(iq3::Type::Q5_K, row, i));
            }
            qs[c].memcpy(teng[c][li], rows.data(), rows.size() * sizeof(act_t));
        }
    }
    // eng_split: engram_kv depends on the token only, so at step start each card computes its rows of both
    // engram layers and pushes them to every peer (no wait); a later exchange's wait covers them (the
    // peers' flags for it come after this push in their queues), else engram_tp waits for this one
    void tp_engram_kv(int c) {
        if (!o.eng_split) return;
        bool any = false;
        for (int li = 0; li < 2; ++li) {
            const int L = li == 0 ? 1 : 14;
            if (L < o.layer_begin || L >= o.layer_end || !eng_base[li]) continue;
            gemv_part(c, "blk." + std::to_string(L) + ".engram_kv.weight", teng[c][li],
                      xarena[c] + xeng + (size_t)li * 5 * g.h + te0[c]);
            any = true;
        }
        if (any) eng_seq[c] = xchg(c, xeng, 5u * (unsigned)g.h, 2, te0[c], te1[c], 1, 0, XP_ENG);
    }
    void engram_tp(int L, int c) {
        const int li = L == 1 ? 0 : 1;
        const std::string p = "blk." + std::to_string(L) + ".";
        const float *kv = sc[c].kvbuf;
        if (o.eng_split) {
            // loads: the rows arrive only by this copy; stores: a later exchange's wait already covers them
            if (use_pull(XP_ENG, 2) || xseq[c] == eng_seq[c])
                xchg(c, xeng, 5u * (unsigned)g.h, 2, te0[c], te1[c], 2, eng_seq[c], XP_ENG);
            kv = xarena[c] + xeng + (size_t)li * 5 * g.h;
        } else {
            gemv(c, p + "engram_kv.weight", teng[c][li], sc[c].kvbuf);
        }
        if (!o.small_fast || g.h % 32) throw std::runtime_error("tensor parallel: engram gate form");
        launch_sg(c, 4, ops41sycl::EngramGateP{g.h}, streams[c], kv, wp<float>(c, p + "engram_gate.weight"));
    }
    void tp_embed(int c, int32_t token, bool wait = true) {
        const auto &te = we("token_embd.weight");
        const uint8_t *row = (const uint8_t *)wgt[c].at("token_embd.weight").p + (size_t)token * wrb(te);
        launch(c, g.h, 32, ops41sycl::EmbedRowA<Act>{te.type, g.h}, row, sc[c].x);
        launch(c, g.h, 32, ops41sycl::Broadcast4A<Act>{g.h}, (const act_t *)sc[c].x, streams[c]);
        float pm[4] = {1, 0, 0, 0};
        qs[c].memcpy(sc[c].cur_pre, pm, 16);
        if (wait) twait(c);
    }
    // final norm + this card's logits rows + its argmax candidates (to the host)
    void tp_head(int c) {
        auto &s = sc[c];
        const int H_ = g.h;
        if (!x_ready[c]) // else the last FFN's HcPostPreP already collapsed the streams into s.x
            launch(c, H_, 32, ops41sycl::HcPreA<Act>{H_}, (const act_t *)streams[c], (const float *)s.cur_pre, s.x);
        x_ready[c] = false;
        rmsnorm(c, s.x, "output_norm.weight", H_, s.xn);
        gemv_part(c, "output.weight", s.xn, tlog[c]);
        const int nl = tv1[c] - tv0[c], G = (nl + AM_CH - 1) / AM_CH;
        launch_sg(c, G, ops41sycl::ArgmaxP1O{nl, AM_CH, tv0[c], g.vocab}, (const float *)tlog[c], tam_v[c], tam_i[c]);
        h_amv[c].resize(G);
        h_ami[c].resize(G);
        qs[c].memcpy(h_amv[c].data(), tam_v[c], (size_t)G * 4);
        qs[c].memcpy(h_ami[c].data(), tam_i[c], (size_t)G * 4);
        twait(c);
        prof("head", c);
    }
    // ArgmaxP2's comparison over every card's candidates: the order-free
    // definition (largest non-NaN value, lowest index among equals)
    int32_t tp_argmax() const {
        float bv = -INFINITY;
        int bi = 0x7fffffff;
        for (int c = 0; c < o.tp; ++c)
            for (size_t k = 0; k < h_amv[c].size(); ++k) {
                const float ov = h_amv[c][k];
                const int oi = h_ami[c][k];
                if (ov > bv || (ov == bv && oi < bi)) { bv = ov; bi = oi; }
            }
        return bi;
    }
    void tp_card_step(int c) {
        const double t0 = now_s();
        commit_pending(c);
        x_ready[c] = false; // a step that failed part-way must not leave it set
        fin_attn[c] = false;
        xt[c].on = xt[c].pending = false;
        auto eng = [&] {
            const auto e0 = std::chrono::steady_clock::now();
            tp_engram_upload(c);
            eng_t[c] += std::chrono::duration<double>(std::chrono::steady_clock::now() - e0).count();
            ++eng_n[c];
        };
        if (!o.eng_late) eng();
        if (o.layer_begin == 0) tp_embed(c, tp_tok, !o.eng_late); // late: the rows' copy is later, nothing to wait for
        else twait(c);
        if (c == o.prof_card) prof_begin(c);
        if (!o.eng_late) {
            tp_engram_kv(c);
            prof("engram", c);
        }
        bool eng_done = !o.eng_late;
        for (int L = o.layer_begin; L < o.layer_end; ++L) {
            if (!eng_done && L >= 1) { // after layer 0's launches: the host reads the rows while the card runs them
                eng();
                tp_engram_kv(c);
                prof("engram", c);
                eng_done = true;
            }
            for (int ph = 0; ph < 6; ++ph) tp_phase(L, c, ph);
        }
        if (o.head && !skip_head) tp_head(c);
        else twait(c);
        tph_step[c] += now_s() - t0;
    }
    void tp_worker(int c) {
        long seen = 0;
        for (;;) {
            if (!tp_poll(o.tp_spin_us, [&] { return tp_quit.load() || tp_gen.load() != seen; })) {
                std::unique_lock<std::mutex> lk(tp_mu);
                tp_cv.wait(lk, [&] { return tp_quit.load() || tp_gen.load() != seen; });
            }
            if (tp_quit) return;
            seen = tp_gen.load();
            try {
                if (dr_step) dr_card_step(c);
                else if (mt_n > 0) tpm_card_step(c);
                else tp_card_step(c);
            } catch (const std::exception &e) {
                tp_abort = true;
                std::lock_guard<std::mutex> lk(tp_mu);
                if (tp_err.empty()) tp_err = "card " + pci[c] + ": " + e.what();
            }
            if (tp_left.fetch_sub(1) == 1) {
                std::lock_guard<std::mutex> lk(tp_mu);
                tp_done_cv.notify_all();
            }
        }
    }
    // trace a vector whose row slices live on different cards: card c's
    // [a_c, b_c) x mult floats, read at src_c + a_c * mult (or at src_c when local)
    void tr_gather(int L, int tag, const int *a, const int *b, size_t mult, size_t n, bool local,
                   const float *const *src) {
        if (!tracing()) return;
        std::vector<float> f(n);
        for (int c = 0; c < o.tp; ++c) {
            const size_t k = (size_t)(b[c] - a[c]) * mult;
            qs[c].memcpy(f.data() + (size_t)a[c] * mult, src[c] + (local ? 0 : (size_t)a[c] * mult), k * 4).wait();
        }
        trw(L, tag, f.data(), n);
    }
    // the tp=1 trace records in the same order (serial mode only)
    void tp_trace(int L, int ph) {
        if (!tracing()) return;
        const int H_ = g.h;
        auto &s = sc[0];
        const float *src[TILES] = {};
        switch (ph) {
        case 0:
            if (L == 1 || L == 14) tra(L, TT_ENGRAM, 0, streams[0], 4 * (size_t)H_);
            trf(L, TT_ATTN_MIX_PRE, 0, s.pre_a, 4);
            trf(L, TT_ATTN_MIX_POST, 0, s.post_a, 4);
            trf(L, TT_ATTN_MIX_COMB, 0, s.comb_a, 16);
            tra(L, TT_ATTN_IN, 0, s.xn, H_);
            for (int c = 0; c < o.tp; ++c) src[c] = sc[c].q;
            tr_gather(L, TT_Q, thq0, thq1, g.hd, (size_t)g.qh * g.hd, false, src);
            tra(L, TT_KV, 0, s.kvn, g.hd);
            break;
        case 1:
            if (cr_of(L)) tri(L, TT_CIDX, 0, s.idxs_cat + 128, 512);
            for (int c = 0; c < o.tp; ++c) src[c] = sc[c].of;
            tr_gather(L, TT_ATTN_O, thq0, thq1, g.hd, (size_t)g.qh * g.hd, false, src);
            tra(L, TT_ATTN_OA, 0, s.oa, g.ototal);
            break;
        case 2:
            tra(L, TT_ATTN_OUT, 0, s.ob, H_);
            break;
        case 3:
            tra(L, TT_STREAMS_ATTN, 0, streams[0], 4 * (size_t)H_);
            trf(L, TT_FFN_MIX_PRE, 0, s.pre_f, 4);
            tra(L, TT_FFN_IN, 0, s.xn, H_);
            break;
        case 4:
            trf(L, TT_ROUTE_LOGITS, 0, s.router, g.experts);
            tri(L, TT_ROUTE_IDS, 0, s.ids, 6);
            trf(L, TT_ROUTE_PROB, 0, s.prob, 6);
            for (int c = 0; c < o.tp; ++c) src[c] = sc[c].shd;
            tr_gather(L, TT_SHARED_DOWN, td0, td1, 1, H_, true, src);
            tra(L, TT_FFN_OUT, 0, s.ob, H_);
            break;
        case 5:
            tra(L, TT_STREAMS_FFN, 0, streams[0], 4 * (size_t)H_);
            break;
        }
    }
    // one host thread for every card in phase order (trace runs): every card's
    // kernels of a phase, exchanges included, are queued before any host wait
    void tp_step_serial(int32_t token) {
        for (int c = 0; c < o.tp; ++c) {
            commit_pending(c);
            x_ready[c] = fin_attn[c] = false;
            xt[c].on = xt[c].pending = false;
        }
        for (int c = 0; c < o.tp; ++c) tp_engram_upload(c);
        if (o.layer_begin == 0) {
            for (int c = 0; c < o.tp; ++c) tp_embed(c, token);
            tra(0, TT_EMBED, 0, streams[0], 4 * (size_t)g.h);
        }
        prof_begin(o.prof_card);
        for (int c = 0; c < o.tp; ++c) {
            tp_engram_kv(c);
            prof("engram", c);
        }
        for (int L = o.layer_begin; L < o.layer_end; ++L)
            for (int ph = 0; ph < 6; ++ph) {
                for (int c = 0; c < o.tp; ++c) tp_phase(L, c, ph);
                // fin_move: the attention mix is final only after phase 2; the records of phases 0-1 are
                // read then (in the same order; nothing they read changes before phase 3)
                if (o.fin_move && ph < 2) continue;
                if (o.fin_move && ph == 2) {
                    tp_trace(L, 0);
                    tp_trace(L, 1);
                }
                tp_trace(L, ph);
            }
        if (o.head && !skip_head) {
            for (int c = 0; c < o.tp; ++c) tp_head(c);
            tra(40, TT_FINAL_N, 0, sc[0].xn, g.h);
            const float *src[TILES] = {};
            for (int c = 0; c < o.tp; ++c) src[c] = tlog[c];
            tr_gather(40, TT_LOGITS, tv0, tv1, 1, g.vocab, true, src);
        } else {
            for (int c = 0; c < o.tp; ++c) qs[c].wait();
        }
    }
#include "backend_sycl_v41_mt.inc"
#include "backend_sycl_v41_draft.inc"
    int32_t decode_step_tp(int32_t token) {
        engram_prefetch();
        ++tp_stepn;
        tp_tok = token;
        if (!tp_th.empty() && !tracing()) { // traced steps run phase by phase from this thread (workers parked)
            tp_abort = false;
            tp_go();
            tp_join();
            if (!tp_err.empty()) throw std::runtime_error("tensor-parallel step: " + tp_err);
        } else {
            tp_step_serial(token);
        }
        for (int c = 0; c < o.tp; ++c)
            if (xerr[c][0])
                throw std::runtime_error("card " + pci[c] + ": card-to-card exchange timed out waiting for card " +
                                         std::to_string((int)xerr[c][0] - 1));
        const int32_t next = o.head && !skip_head ? tp_argmax() : -1;
        ++pos;
        if (tp_hostprof && !tp_th.empty() && ++tph_n % 32 == 0) {
            std::fprintf(stderr, "host per step (ms), %ld steps: ", tph_n);
            for (int c = 0; c < o.tp; ++c)
                std::fprintf(stderr, " card%d %.2f (blocked %.2f, busy %.2f)", c, tph_step[c] / 32 * 1e3,
                             tph_wait[c] / 32 * 1e3, (tph_step[c] - tph_wait[c]) / 32 * 1e3);
            std::fprintf(stderr, "\n");
            for (int c = 0; c < o.tp; ++c) tph_step[c] = tph_wait[c] = 0;
        }
        return next;
    }
#else
    int32_t decode_step_tp(int32_t) { throw std::runtime_error("tensor parallel needs the f32-activation build"); }
  public:
    int32_t decode_block_tp(const int32_t *, int) { throw std::runtime_error("tensor parallel needs the f32-activation build"); }
  private:
    void tp_worker(int) {}
#endif

    // tok_p >= 0: the token at position p (not yet in comp_ids); ahead: the tokens after comp_ids' end (the
    // prompt's next block, read ahead of its step: engram_ask_ahead)
    void engram_hash(int p, int li, int64_t *ids24, long long tok_p = -2,
                     const std::vector<int64_t> *ahead = nullptr) const {
        const long nc = (long)comp_ids.size();
        for (int i = 1; i <= 3; ++i) {
            uint64_t rolling = 0;
            for (int sh = 0; sh <= i; ++sh) {
                const long q = p - sh;
                long long tk = sh == 0 && tok_p >= 0 ? tok_p
                               : q < 0 ? eng_pad
                               : q < nc ? comp_ids[q]
                               : ahead && q - nc < (long)ahead->size() ? (*ahead)[q - nc] : eng_pad;
                if (tk == -1) tk = eng_pad;
                rolling ^= (uint64_t)(tk * eng_mult[li][sh]);
            }
            int64_t r = (int64_t)rolling;
            for (int h = 0; h < 8; ++h) {
                int64_t pr = eng_primes[li][i - 1][h];
                int64_t v = r % pr;
                if (v < 0) v += pr;
                ids24[(i - 1) * 8 + h] = v + eng_off[li][(i - 1) * 8 + h];
            }
        }
    }
    // engram (layers 1/14): 24 hashed rows from the NVMe Q5_K table, decoded
    // on host, projected and gated on the layer's card.
    void engram_host(int L, int t) {
        auto &s = sc[t];
        int li = L == 1 ? 0 : 1;
        if ((long)comp_ids.size() <= pos) throw std::runtime_error("comp_ids behind position");
        int64_t ids[24];
        engram_hash((int)pos, li, ids);
        auto l = iq3::layout(iq3::Type::Q5_K);
        std::vector<act_t> &rows = h_eng[t][li][eng_flip[t][li]++ & 1]; // persistent: the upload below does not wait
        for (int c = 0; c < 24; ++c) {
            const uint8_t *row = eng_base[li] + (size_t)ids[c] * l.bytes;
            for (int i = 0; i < 256; ++i)
                rows[c * 256 + i] = Act::wr(iq3::decode(iq3::Type::Q5_K, row, i));
        }
        const std::string p = "blk." + std::to_string(L) + ".";
        auto ev = qs[t].memcpy(s.eng_rows, rows.data(), rows.size() * sizeof(act_t));
        if (h2d_wait) ev.wait();
        gemv(t, p + "engram_kv.weight", s.eng_rows, s.kvbuf);
#ifndef OWN41_ACT_BF16
        if (o.small_fast && g.h % 32 == 0) {
            launch_sg(t, 4, ops41sycl::EngramGateP{g.h}, streams[t], (const act_t *)s.kvbuf,
                      wp<float>(t, p + "engram_gate.weight"));
            return;
        }
#endif
        launch(t, 4, 4, ops41sycl::EngramGateA<Act>{g.h}, streams[t], (const act_t *)s.kvbuf,
               wp<float>(t, p + "engram_gate.weight"));
    }

    void build_rope_tables() {
        // cos/sin for 32 pair slots per position; yarn (theta 160000, factor
        // 16, beta 32/1, orig 65536) and base. Exact copy of the CPU runner.
        int P = max_seq;
        std::vector<float> cy((size_t)P * 32), sy((size_t)P * 32), cb((size_t)P * 32), sb((size_t)P * 32);
        auto fill = [&](std::vector<float> &c, std::vector<float> &s, int yarn) {
            const int dim = 64;
            double base = yarn ? 160000.0 : 10000.0;
            std::vector<double> f(dim / 2);
            for (int i = 0; i < dim / 2; ++i) f[i] = 1.0 / std::pow(base, (2.0 * i) / dim);
            if (yarn) {
                double orig = 65536.0, factor = 16.0, beta_fast = 32.0, beta_slow = 1.0;
                auto corrected = [&](double rot) {
                    return dim * std::log(orig / (rot * 2 * M_PI)) / (2 * std::log(base));
                };
                double low = std::max(std::floor(corrected(beta_fast)), 0.0);
                double high = std::min(std::ceil(corrected(beta_slow)), (double)dim - 1);
                for (int i = 0; i < dim / 2; ++i) {
                    double ramp = std::clamp((i - low) / std::max(high - low, 1e-3), 0.0, 1.0);
                    double smooth = 1 - ramp;
                    f[i] = f[i] / factor * (1 - smooth) + f[i] * smooth;
                }
            }
            for (int p = 0; p < P; ++p)
                for (int i = 0; i < 32; ++i) {
                    c[(size_t)p * 32 + i] = (float)std::cos(p * f[i]);
                    s[(size_t)p * 32 + i] = (float)std::sin(p * f[i]);
                }
        };
        fill(cy, sy, 1);
        fill(cb, sb, 0);
        for (int t = 0; t < TILES; ++t) {
            if (!active[t]) continue;
            cos_yarn[t] = dalloc<float>(t, (size_t)P * 32, false);
            sin_yarn[t] = dalloc<float>(t, (size_t)P * 32, false);
            cos_base[t] = dalloc<float>(t, (size_t)P * 32, false);
            sin_base[t] = dalloc<float>(t, (size_t)P * 32, false);
            qs[t].memcpy(cos_yarn[t], cy.data(), cy.size() * 4);
            qs[t].memcpy(sin_yarn[t], sy.data(), sy.size() * 4);
            qs[t].memcpy(cos_base[t], cb.data(), cb.size() * 4);
            qs[t].memcpy(sin_base[t], sb.data(), sb.size() * 4);
            qs[t].wait(); // host vectors are locals
        }
    }
};

} // namespace own41
#endif
