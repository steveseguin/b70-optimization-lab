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
#include <cxxabi.h>
#include <fcntl.h>
#include <fstream>
#include <map>
#include <mutex>
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
#include "stage2/packet3/step/plan_v41.hpp"

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
    };
    struct DevPtr {
        void *p = nullptr;
        size_t bytes = 0;
        int tile = -1;
        bool packed = false; // rows are in the pack_v41.hpp layout
    };

    Backend41(const flash41::Plan41 &plan, int max_seq, Options opt)
        : g(plan.g), max_seq(max_seq), o(std::move(opt)) {
        if (o.layer_begin < 0 || o.layer_end > g.layers || o.layer_begin > o.layer_end)
            throw std::invalid_argument("layer range");
        for (int L = o.layer_begin; L < o.layer_end; ++L) active[tile_of_layer(L)] = true;
        if (o.head) active[HEAD_TILE] = true;
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
        for (int L = o.layer_begin; L < o.layer_end; ++L)
            ring[L] = dalloc<uint16_t>(tile_of_layer(L), (size_t)128 * g.hd);
        if (o.head) {
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
        for (auto &layer : h_eng)
            for (auto &v : layer) v.resize((size_t)24 * g.engram_dim);
        build_rope_tables();
        for (int t = 0; t < TILES; ++t)
            if (active[t]) qs[t].wait();
        cur = o.layer_begin < g.layers ? tile_of_layer(o.layer_begin) : HEAD_TILE;
    }

    ~Backend41() {
        for (int t = 0; t < TILES; ++t) {
            if (!active[t]) continue;
            try { qs[t].wait(); } catch (...) {}
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
            size_t rb, prb; // raw / packed row bytes (packed items)
        };
        std::vector<Item> items[TILES];
        std::vector<size_t> chunk_sz[TILES];
        size_t need[TILES] = {}, total = 0;
        for (const auto &kv : wt.w) {
            if (!wanted(kv.first)) continue;
            int t = tile_of(kv.first);
            const auto &e = kv.second;
            Item it{&kv.first, &e, wt.bytes(e), 0, 0, false, 0, 0};
            if (pack_wanted(kv.first, e)) {
                it.packed = true;
                it.rb = wt.row_bytes(e);
                it.prb = pk41::packed_row_bytes(e.type, (size_t)e.cols);
                it.bytes = it.prb * (size_t)e.rows * (size_t)(e.experts ? e.experts : 1);
            }
            items[t].push_back(it);
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
                total += wt.bytes(*it.e); // file bytes (progress counter)
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
                    uint8_t *dst = chunks[t][it.chunk] + it.off;
                    const size_t raw = wt.bytes(*it.e); // bytes in the file
                    for (size_t d = 0; d < raw && !stop;) {
                        // packed tensors move whole rows per piece
                        size_t n = it.packed ? std::min(PIECE / it.rb * it.rb, raw - d) : std::min(PIECE, raw - d);
                        off_t fo = it.e->off + (off_t)d, a0 = fo & ~(off_t)4095;
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
                wgt[*it.name] = {chunks[t][it.chunk] + it.off, it.bytes, t, it.packed};
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
    void kev(const char *name, const sycl::event &e) {
        if (o.kprof) kevs.push_back({name, e});
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
    bool h2d_wait = true;
    void prof(const char *name, int t) {
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
        const int H_ = g.h;
        engram_prefetch();
        if (o.layer_begin == 0) {
            const auto &te = we("token_embd.weight");
            const uint8_t *row = (const uint8_t *)wgt.at("token_embd.weight").p + (size_t)token * wrb(te);
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
        for (int L = o.layer_begin; L < o.layer_end; ++L)
            up16(ring[L], rings[L].data(), rings[L].size(), tile_of_layer(L));
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
            int st = tile_of_layer(srcs[i]);
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
    std::unordered_map<std::string, DevPtr> wgt;
    const WeightTab *W = nullptr;
    act_t *streams[TILES] = {};
    uint16_t *ckv_mirror[TILES][4] = {};
    uint16_t *ik_mirror[TILES][4] = {};
    int32_t *cidx_mirror[TILES][8] = {};
    uint16_t *ring[40] = {};
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
    std::vector<act_t> h_eng[2][2];          // engram rows, two alternating buffers per engram layer
    unsigned eng_flip[2] = {};
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
        return p;
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
    }

    const WeightTab::E &we(const std::string &n) const { return W->at(n); }
    size_t wrb(const WeightTab::E &e) const { return W->row_bytes(e); }
    template <typename T = uint8_t> const T *wp(const std::string &n) const {
        auto it = wgt.find(n);
        if (it == wgt.end()) throw std::invalid_argument("weight not uploaded " + n);
        return (const T *)it->second.p;
    }

    // ---- launch helpers -----------------------------------------------------
    template <typename K, typename... A>
    void launch(int tile, size_t nwork, size_t lwork, K k, A... args) {
        size_t n = (nwork + lwork - 1) / lwork * lwork; // B70 rejects non-uniform groups
        auto e = qs[tile].submit([&](sycl::handler &hh) {
            hh.parallel_for(sycl::nd_range<1>(n, lwork), [=](sycl::nd_item<1> it) { k(it, args...); });
        });
        kev(kname<K>(), e);
    }
    // kernels built on 32-lane sub-group reductions: one work-group == one sub-group
    template <typename K, typename... A> void launch_sg(int tile, size_t groups, K k, A... args) {
        auto e = qs[tile].submit([&](sycl::handler &hh) {
            hh.parallel_for(sycl::nd_range<1>(groups * 32, 32),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, args...); });
        });
        kev(kname<K>(), e);
    }
    // one work-group of `items` (a multiple of 32), 32-lane sub-groups, no local memory
    template <typename K, typename... A> void launch_wg(int tile, size_t items, K k, A... args) {
        auto e = qs[tile].submit([&](sycl::handler &hh) {
            hh.parallel_for(sycl::nd_range<1>(items, items),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, args...); });
        });
        kev(kname<K>(), e);
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
        kev(kname<K>(), e);
    }
    // packed-row kernels: 16 sub-groups (rows) per work-group, optional local
    // table; max_wg > 0 caps the work-groups (the routed kernels loop over rows)
    template <size_t SLM, typename K, typename... A>
    void launch_rows(int tile, size_t rows, size_t max_wg, K k, A... args) {
        constexpr size_t WG = 512, PER = WG / 32;
        size_t nwg = (rows + PER - 1) / PER;
        if (max_wg && nwg > max_wg) nwg = max_wg;
        const size_t n = nwg * WG;
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
        kev(kname<K>(), e);
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
#undef X
        throw std::runtime_error("packed dense kernel missing: " + wn);
    }
#endif
    // One kernel per weight format (OWN_GENERIC_KERNELS=1 selects the
    // runtime-type kernels instead; outputs are bit-identical either way).
    void gemv(int tile, const std::string &wn, const act_t *x, void *y, bool f32out = false) {
        const auto &e = we(wn);
        const unsigned rows = (unsigned)e.rows, cols = (unsigned)e.cols;
#ifndef OWN41_ACT_BF16
        if (const auto &dp = wgt.at(wn); dp.packed) { // f32 activations: f32out is the same store
            gemv_kp(tile, e, dp.p, x, (act_t *)y, rows, 0, cols, wn);
            return;
        }
        // F32 rows need no packing: block-read kernel (the router logits, 5120 columns)
        if (o.packed && e.type == iq3::Type::F32 && cols == 5120) {
            launch_rows<0>(tile, rows, 0, ops41sycl::GemvF32P<160, Act>{rows}, (const uint8_t *)wp(wn), x, (act_t *)y);
            return;
        }
#endif
#ifdef OWN41_ACT_BF16
        if (o.generic_kernels) {
            launch_sg(tile, (size_t)rows, ops41sycl::Gemv{e.type, rows, cols, f32out}, wp(wn), wrb(e), x, y);
            return;
        }
#else
        if (o.generic_kernels) throw std::runtime_error("runtime-type kernels exist only in the BF16-activation build");
#endif
        switch (e.type) {
#define X(TY)                                                                                              \
    case iq3::Type::TY:                                                                                    \
        launch_sg(tile, (size_t)rows, ops41sycl::GemvT<iq3::Type::TY, Act>{rows, cols, f32out}, wp(wn), x, y); \
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
        if (const auto &dp = wgt.at(wn); dp.packed) {
            gemv_kp(tile, e, dp.p, x, y, (unsigned)e.rows, n, k, wn);
            return;
        }
#endif
#ifdef OWN41_ACT_BF16
        if (o.generic_kernels) {
            launch_sg(tile, (size_t)e.rows, ops41sycl::GemvGroupedQ{e.type, n, k}, wp(wn), wrb(e), x, y);
            return;
        }
#else
        if (o.generic_kernels) throw std::runtime_error("runtime-type kernels exist only in the BF16-activation build");
#endif
        switch (e.type) {
#define X(TY)                                                                                              \
    case iq3::Type::TY:                                                                                    \
        launch_sg(tile, (size_t)e.rows, ops41sycl::GemvGroupedQT<iq3::Type::TY, Act>{n, k}, wp(wn), x, y); \
        break;
            OWN41_WEIGHT_TYPES(X)
#undef X
        default: throw std::runtime_error("unsupported weight format: " + wn);
        }
    }
    void routed_gemv(int tile, const std::string &wn, const act_t *x, const uint32_t *ids, act_t *y,
                     bool per_slot) {
        const auto &e = we(wn);
        const unsigned rows = (unsigned)e.rows, cols = (unsigned)e.cols;
#ifndef OWN41_ACT_BF16
        if (const auto &dp = wgt.at(wn); dp.packed) {
            const auto *w = (const uint8_t *)dp.p;
            // 128 work-groups (2,048 sub-groups): best for every format and shape in
            // the 2026-11-09 kernel bench (each fills its local table once)
            constexpr size_t MAXWG = 128;
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
            launch_sg(tile, (size_t)6 * rows, ops41sycl::RoutedGemv{e.type, rows, cols, per_slot}, wp(wn), x, ids, y);
            return;
        }
#else
        if (o.generic_kernels) throw std::runtime_error("runtime-type kernels exist only in the BF16-activation build");
#endif
        switch (e.type) {
#define X(TY)                                                                                              \
    case iq3::Type::TY:                                                                                    \
        launch_sg(tile, (size_t)6 * rows, ops41sycl::RoutedGemvT<iq3::Type::TY, Act>{rows, cols, per_slot}, \
                  wp(wn), x, ids, y);                                                                      \
        break;
            OWN41_WEIGHT_TYPES(X)
#undef X
        default: throw std::runtime_error("unsupported weight format: " + wn);
        }
    }
    static bool al16(const void *p) { return ((uintptr_t)p & 15u) == 0; }
    void rmsnorm(int tile, const act_t *x, const std::string &wn, int n, act_t *y) {
        const float *w = wp<float>(wn);
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
        const float *fn = wp<float>(prefix + "fn.weight");
#ifndef OWN41_ACT_BF16
        if (o.small_fast && g.h == 5120 && HC_SEG == 8 && al16(streams[t]) && al16(fn)) {
            launch_sg(t, 25 * HC_SEG, ops41sycl::HcMixDotsP<5120, HC_SEG>{}, (const act_t *)streams[t], fn, s.d25);
            launch_sg(t, 1, ops41sycl::HcMixFinishSG{g.h, HC_SEG}, (const double *)s.d25,
                      wp<float>(prefix + "scale.weight"), wp<float>(prefix + "base.weight"), pre, post, comb);
            return;
        }
#endif
        launch_sg(t, 25 * HC_SEG, ops41sycl::HcMixDots32A<Act>{g.h, HC_SEG}, (const act_t *)streams[t], fn, s.d25);
        launch(t, 1, 1, ops41sycl::HcMixFinishSeg{g.h, HC_SEG}, (const double *)s.d25,
               wp<float>(prefix + "scale.weight"), wp<float>(prefix + "base.weight"), pre, post, comb);
    }

    // collapse the 4 streams with `mix` (HcPreA) and RMS-normalize into s.xn
    void pre_norm(int t, const float *mix, const std::string &wn) {
        auto &s = sc[t];
        const int H_ = g.h;
#ifndef OWN41_ACT_BF16
        const float *w = wp<float>(wn);
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
            launch(t, 1, 1, ops41sycl::WindowAppendA<Act>{128, g.hd, (int)pos}, ring[L], (const act_t *)s.kvn, s.widx);
        int si = src_index(L);
        int n_idx = 128;
        if (cr) {
            if (is_kv_source(L)) { publish(L, t, si, yarn); prof("publish", t); }
            if (index_slot(L) >= 0) { index(L, t, si, yarn); prof("index", t); }
            sync_rows(t, si);
            sync_cidx(t, isrc_for(L));
            if (fast_win) {
                launch(t, (size_t)std::max(g.hd, 512), 64, ops41sycl::WindowAppendP<Act>{128, g.hd, (int)pos, 512}, ring[L],
                       (const act_t *)s.kvn, s.widx, s.idxs_cat, (const int32_t *)cidx_mirror[t][isrc_for(L)]);
            } else {
                qs[t].memcpy(s.idxs_cat, s.widx, 128 * 4);
                qs[t].memcpy(s.idxs_cat + 128, cidx_mirror[t][isrc_for(L)], 512 * 4);
            }
            n_idx += 512;
            tri(L, TT_CIDX, t, s.idxs_cat + 128, 512);
        } else if (fast_win) {
            launch(t, (size_t)std::max(g.hd, 128), 64, ops41sycl::WindowAppendP<Act>{128, g.hd, (int)pos, 0}, ring[L],
                   (const act_t *)s.kvn, s.widx, s.idxs_cat, (const int32_t *)nullptr);
        } else {
            qs[t].memcpy(s.idxs_cat, s.widx, 128 * 4);
        }
#ifndef OWN41_ACT_BF16
        if (o.small_fast && g.hd == 512 && (n_idx == 128 || n_idx == 640) && g.qh % 4 == 0) {
            // same per-output arithmetic as the three launches below (test_small_v41_device.cpp)
            const uint16_t *kvw = ring[L], *kvc = cr ? ckv_mirror[t][si] : ring[L];
            const float *sinks = wp<float>(p + "attn_sinks.weight");
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
            const uint16_t *kvw = ring[L], *kvc = cr ? ckv_mirror[t][si] : ring[L];
            launch(t, (size_t)g.qh * n_idx, 32, ops41sycl::SparseScoreA<Act>{n_idx, g.qh, g.hd, 128},
                   (const act_t *)s.q, kvw, kvc, (const int32_t *)s.idxs_cat, s.attn_w);
            launch(t, g.qh, 8, ops41sycl::SparseSoftmax{n_idx, g.qh}, wp<float>(p + "attn_sinks.weight"),
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
        const long step = ((long)64 << 20) / ((long)g.hd * 2);
        while (have < want) {
            const long n = std::min(step, want - have);
            qs[t].memcpy(ckv_mirror[t][si] + (size_t)have * g.hd, h_ckv[si].data() + (size_t)have * g.hd,
                         (size_t)n * g.hd * 2);
            qs[t].memcpy(ik_mirror[t][si] + (size_t)have * 128, h_ik[si].data() + (size_t)have * 128,
                         (size_t)n * 128 * 2);
            have += n;
        }
        if (h2d_wait) qs[t].wait();
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
                                   wp<float>(p + "attn_compressor_norm.weight"), s.latent);
            else
                launch(t, 1, 1, ops41sycl::CompressPoolA<Act>{2, g.hd},
                       (const float *)(s.kv_state + (size_t)si * 2 * g.hd),
                       (const float *)(s.score_state + (size_t)si * 2 * g.hd),
                       wp<float>(p + "attn_compressor_norm.weight"), s.latent);
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
    void index(int L, int t, int si, bool yarn) {
        auto &s = sc[t];
        const std::string p = "blk." + std::to_string(L) + ".";
        const long len = src_len[si];
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

    void moe(int L, int t) {
        auto &s = sc[t];
        const std::string p = "blk." + std::to_string(L) + ".";
        gemv(t, p + "ffn_gate_inp.weight", s.xn, s.router, true); // router logits stay f32
        if (o.small_fast && g.experts % 32 == 0 && g.experts <= 1024) {
            // one work-group, same picks and arithmetic (test_small_v41_device.cpp)
            launch_local<2 * 1024 + 6>(t, (size_t)g.experts, ops41sycl::RouteP{g.experts, 6}, (const float *)s.router,
                                       wp<float>(p + "exp_probs_b.bias"), s.ids, s.prob);
        } else {
            // three launches, same picks and arithmetic as the one-work-item RouteF32
            launch(t, g.experts, 32, ops41sycl::RouteScore{g.experts}, (const float *)s.router,
                   wp<float>(p + "exp_probs_b.bias"), s.rs, s.rsb);
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

    void engram_hash(int p, int li, int64_t *ids24) const {
        for (int i = 1; i <= 3; ++i) {
            uint64_t rolling = 0;
            for (int sh = 0; sh <= i; ++sh) {
                long long tk = (p - sh < 0 || p - sh >= (long)comp_ids.size()) ? eng_pad : comp_ids[p - sh];
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
        std::vector<act_t> &rows = h_eng[li][eng_flip[li]++ & 1]; // persistent: the upload below does not wait
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
                      wp<float>(p + "engram_gate.weight"));
            return;
        }
#endif
        launch(t, 4, 4, ops41sycl::EngramGateA<Act>{g.h}, streams[t], (const act_t *)s.kvbuf,
               wp<float>(p + "engram_gate.weight"));
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
