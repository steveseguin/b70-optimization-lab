// Backend41: 12-tile SYCL executor for the v41 decode plan (Plan41).
//
// Placement (UD-IQ2_XXS, ~4.0GB/layer, head ~5.1GB on the head tile):
//   t0: token_embd + layers 0-2      t1: 3-6    t2: 7-9    t3: 10-12
//   t4: 13-16   t5: 17-19   t6: 20-22   t7: 23-26   t8: 27-29
//   t9: 30-32   t10: 33-36  t11: layers 37-39 + output_norm/output + argmax
//
// Design:
// * One SYCL context over the 12 Level-Zero tiles; one queue per tile.
// * Activations ("streams", 40KB) migrate tile-to-tile as layers advance;
//   all other cross-tile reads are served by mirrored state.
// * compress_kv caches (4 publishers) and index-key caches (8 publishers)
//   are mirrored on every tile; publishes broadcast the appended row to the
//   other 11 tiles. Window rings stay local to the layer's tile.
// * Scalars (token, position, active, error, next_token) live host-side and
//   enter kernels as arguments; argmax does a 4-byte D2H per decode step.
// * Weights are uploaded raw (GGUF row bytes) once at init; device gemv
//   decodes via iq3::layout/decode (proven in the device probe + gates).
//
// Decode-only v1: prefill runs in the validated CPU runner; its state
// (rings, compress caches, index keys, histories) is handed off through
// state_v41.bin, then decode steps run here.
#pragma once
#ifndef OWN_RT_HOST_ONLY
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <cmath>
#include <map>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <unordered_map>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/step/plan_v41.hpp"

namespace own41 {

// ---- weight store: placement.tsv + shards.tsv (runner format) -------------
struct WeightTab {
    struct E {
        iq3::Type type;
        const uint8_t *ptr;
        long rows = 1, cols = 1, experts = 0;
    };
    std::unordered_map<std::string, E> w;
    std::vector<std::pair<const uint8_t *, size_t>> maps;
    std::vector<int> fds;
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

inline WeightTab load_weights(const std::string &placement,
                              const std::map<std::string, std::pair<std::string, long>> &shards) {
    WeightTab S;
    std::map<std::string, const uint8_t *> base;
    for (auto &[name, pd] : shards) {
        int fd = open(pd.first.c_str(), O_RDONLY);
        if (fd < 0) throw std::runtime_error("open shard " + pd.first);
        struct stat st;
        fstat(fd, &st);
        auto *p = (const uint8_t *)mmap(nullptr, st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
        if (p == MAP_FAILED) throw std::runtime_error("mmap " + pd.first);
        S.maps.push_back({p, (size_t)st.st_size});
        S.fds.push_back(fd);
        base[name] = p + pd.second;
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
        e.ptr = base.at(shard) + offset;
        e.cols = dims[0];
        if (rank == 3) { e.experts = dims[2]; e.rows = dims[1]; }
        else e.rows = rank > 1 ? dims[1] : 1;
        S.w[name] = e;
    }
    return S;
}

// ---- placement -------------------------------------------------------------
inline int tile_of_layer(int L) {
    static const int map[40] = {0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4,
                                4, 4, 4, 5, 5, 5, 6, 6, 6, 7, 7, 7, 7, 8,
                                8, 8, 9, 9, 9, 10, 10, 10, 10, 11, 11, 11};
    return map[L];
}
inline int tile_of(const std::string &buf) {
    if (buf.rfind("blk.", 0) == 0) {
        int L = std::stoi(buf.substr(4, buf.find('.', 4) - 4));
        return tile_of_layer(L);
    }
    if (buf == "token_embd.weight" || buf == "embedding") return 0;
    if (buf.rfind("output", 0) == 0 || buf == "logits" || buf == "final" ||
        buf == "final.n")
        return 11;
    return 0; // scalars/plumbing default; streams handled by migration
}

// ---- backend ---------------------------------------------------------------
class Backend41 {
public:
    static constexpr int TILES = 12;
    struct DevPtr {
        void *p = nullptr;
        size_t bytes = 0;
        int tile = -1;
    };

    Backend41(const flash41::Plan41 &plan, const WeightTab &wt, int max_seq)
        : g(plan.g), max_seq(max_seq) {
        std::vector<sycl::device> all;
        for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
            all.push_back(d);
        if ((int)all.size() < TILES)
            throw std::runtime_error("need 12 tiles, found " + std::to_string(all.size()));
        devs.assign(all.begin(), all.begin() + TILES);
        ctx = sycl::context(devs);
        for (auto &d : devs) qs.emplace_back(ctx, d, sycl::property::queue::in_order{});

        // buffers: allocate on their placement tile
        for (const auto &b : plan.buffers) {
            std::string n = b.name;
            if (n == "token" || n == "position" || n == "active" ||
                n == "error" || n == "next_token" || n == "token_history" ||
                n == "pre_mix")
                continue; // host-side scalars
            if (n == "streams") continue; // replicated per tile (streams_ptr)
            size_t bytes = flash::scalar_bytes(b.type);
            for (int d : b.shape) bytes *= d;
            if (buf.count(n)) continue; // shared-cache references
            alloc(n, bytes, tile_of(n));
        }
        // streams replicated on all tiles
        for (int t = 0; t < TILES; ++t)
            streams_ptr[t] = sycl::malloc_device<uint16_t>(4 * g.h, qs[t]);
        // cache mirrors on all tiles: compress_kv per publisher + index keys
        int rows_c2 = max_seq / 2, rows_c1 = max_seq;
        for (int t = 0; t < TILES; ++t) {
            for (int s = 0; s < 4; ++s) {
                int rows = s == 3 ? rows_c1 : rows_c2; // layer 20 publishes ratio 1
                ckv_mirror[t][s] = sycl::malloc_device<uint16_t>((size_t)rows * g.hd, qs[t]);
                // index keys: 128-dim projections of the source compress latent;
                // index sources 24-36 reuse these (their attn_k is residue)
                ik_mirror[t][s] = sycl::malloc_device<uint16_t>((size_t)rows * 128, qs[t]);
            }
        }
        // rope tables (host-computed per position; uploaded once)
        build_rope_tables();
    }

    ~Backend41() {
        for (auto &[n, d] : buf) sycl::free(d.p, ctx);
        for (int t = 0; t < TILES; ++t) {
            sycl::free(streams_ptr[t], ctx);
            for (int s = 0; s < 4; ++s) {
                sycl::free(ckv_mirror[t][s], ctx);
                sycl::free(ik_mirror[t][s], ctx);
            }
        }
        for (auto &[n, d] : wgt) sycl::free(d.p, ctx);
        sycl::free(cos_yarn, ctx); sycl::free(sin_yarn, ctx);
        sycl::free(cos_base, ctx); sycl::free(sin_base, ctx);
    }

    // Upload all weights (raw GGUF bytes) to their placement tiles.
    void upload(const WeightTab &wt) {
        for (const auto &[n, e] : wt.w) {
            if (n == "per_layer_token_embd.weight") continue; // NVMe engram store
            int tile = tile_of(n);
            size_t bytes = wt.bytes(e);
            void *dp = sycl::malloc_device<uint8_t>(bytes, qs[tile]);
            qs[tile].memcpy(dp, e.ptr, bytes);
            wgt[n] = {dp, bytes, tile};
        }
        for (auto &q : qs) q.wait();
    }

private:
    flash41::GeometryV41 g;
    int max_seq;
    sycl::context ctx;
    std::vector<sycl::device> devs;
    std::vector<sycl::queue> qs;
    std::unordered_map<std::string, DevPtr> buf, wgt;
    uint16_t *streams_ptr[TILES] = {};
    uint16_t *ckv_mirror[TILES][4] = {};
    uint16_t *ik_mirror[TILES][4] = {};
    float *cos_yarn = nullptr, *sin_yarn = nullptr, *cos_base = nullptr, *sin_base = nullptr;

    void alloc(const std::string &n, size_t bytes, int tile) {
        if (!bytes) return;
        void *p = sycl::malloc_device<uint8_t>(bytes, qs[tile]);
        qs[tile].memset(p, 0, bytes);
        buf[n] = {p, bytes, tile};
    }

    void build_rope_tables() {
        // cos/sin for 32 pair slots per position; yarn (theta 160000, factor
        // 16, beta 32/1, orig 65536) and base (theta 0 -> disabled path uses
        // factor 1). Matches the CPU runner's precompute exactly.
        int P = max_seq;
        std::vector<float> cy(P * 32), sy(P * 32), cb(P * 32), sb(P * 32);
        auto fill = [&](std::vector<float> &c, std::vector<float> &s, int yarn) {
            // exact copy of the validated CPU runner's rope_table
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
        cos_yarn = sycl::malloc_device<float>(P * 32, qs[0]);
        sin_yarn = sycl::malloc_device<float>(P * 32, qs[0]);
        cos_base = sycl::malloc_device<float>(P * 32, qs[0]);
        sin_base = sycl::malloc_device<float>(P * 32, qs[0]);
        qs[0].memcpy(cos_yarn, cy.data(), cy.size() * 4);
        qs[0].memcpy(sin_yarn, sy.data(), sy.size() * 4);
        qs[0].memcpy(cos_base, cb.data(), cb.size() * 4);
        qs[0].memcpy(sin_base, sb.data(), sb.size() * 4);
        qs[0].wait();
    }
};

} // namespace own41
#endif
