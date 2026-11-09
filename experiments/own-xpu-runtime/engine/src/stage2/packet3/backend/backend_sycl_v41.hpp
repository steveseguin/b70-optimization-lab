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
                ik_mirror[t][s] = sycl::malloc_device<uint16_t>((size_t)rows * 128, qs[t]);
            }
            for (int s = 0; s < 8; ++s)
                cidx_mirror[t][s] = (int32_t *)sycl::malloc_device(512 * 4, qs[t]);
            cand_mirror[t] = (uint8_t *)sycl::malloc_device(max_seq, qs[t]);
            qs[t].memset(cand_mirror[t], 1, max_seq); // no-op mask until L20 publishes
        }
        cand_ = (uint8_t *)sycl::malloc_device(max_seq, qs[6]);
        logits_ = sycl::malloc_device<float>(g.vocab, qs[11]);
        for (auto &q : qs) q.wait();
        // rope tables replicated on every tile (rope kernels run on the
        // layer's tile): yarn + base, [max_seq][32] f32 each.
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
            for (int s = 0; s < 8; ++s) sycl::free(cidx_mirror[t][s], ctx);
            sycl::free(cand_mirror[t], ctx);
            sycl::free(cos_yarn[t], ctx); sycl::free(sin_yarn[t], ctx);
            sycl::free(cos_base[t], ctx); sycl::free(sin_base[t], ctx);
        }
        sycl::free(cand_, ctx);
        sycl::free(logits_, ctx);
        for (auto &[n, d] : wgt) sycl::free(d.p, ctx);
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

    // ---- decode-step executor (runner-shaped; plan.buffers where shapes ----
    // match, per-tile scratch for the rest). Public state: pos, src_len.
    long pos = 0;
    long src_len[4] = {0, 0, 0, 0};

    void bind(const WeightTab &wt) { W = &wt; }

    struct Scratch {
        uint16_t *attn_in, *attn_n, *qa, *qn, *q, *kvn, *qi, *wv;
        float *score;
        int64_t *lens;
        int32_t *cidx_loc;
        uint16_t *router;
        uint32_t *ids;
        float *prob;
        uint16_t *expg, *expu, *act, *expd;
        uint16_t *shg, *shu, *sha, *shd;
        float *of;
        uint16_t *obuf, *oa, *ob;
        uint16_t *cw, *scg, *latent, *kk;
        float *kv_state, *score_state;
        float *pre, *post, *comb, *pre2, *post2, *comb2, *m24, *cur_pre;
        int32_t *idxs_cat;
        uint16_t *old, *eng_rows, *kvbuf;
        int32_t *widx;
        uint16_t *ring;
        int32_t *tok_out;
    };
    Scratch sc[TILES] = {};
    bool sc_init = false;
    const WeightTab *W = nullptr;

    void scratch_alloc(int t) {
        auto &s = sc[t];
        auto md = [&](size_t n) { return (uint16_t *)sycl::malloc_device(n, qs[t]); };
        auto mf = [&](size_t n) { return (float *)sycl::malloc_device(n * 4, qs[t]); };
        s.attn_in = md(2 * g.h); s.attn_n = md(2 * g.h);
        s.qa = md(2 * g.qrank); s.qn = md(2 * g.qrank);
        s.q = md(2 * (size_t)g.qh * g.hd); s.kvn = md(2 * g.hd);
        s.qi = md(2 * 4096); s.wv = md(2 * 32);
        s.score = mf(max_seq); s.lens = (int64_t *)sycl::malloc_device(8, qs[t]);
        s.cidx_loc = (int32_t *)sycl::malloc_device(512 * 4, qs[t]);
        s.router = md(2 * 384);
        s.ids = (uint32_t *)sycl::malloc_device(24, qs[t]);
        s.prob = mf(6);
        s.expg = md(2 * 6 * g.mid); s.expu = md(2 * 6 * g.mid);
        s.act = md(2 * 6 * g.mid); s.expd = md(2 * 6 * g.h);
        s.shg = md(2 * g.mid); s.shu = md(2 * g.mid);
        s.sha = md(2 * g.mid); s.shd = md(2 * g.h);
        s.of = mf((size_t)g.qh * g.hd);
        s.obuf = md(2 * (size_t)g.qh * g.hd);
        s.oa = md(2 * g.ototal); s.ob = md(2 * g.h);
        s.cw = md(2 * g.hd); s.scg = md(2 * g.hd);
        s.latent = md(2 * g.hd); s.kk = md(2 * 128);
        s.kv_state = mf(4 * 2 * g.hd); s.score_state = mf(4 * 2 * g.hd);
        qs[t].memset(s.score_state, 0, 4 * 2 * g.hd * 4);
        s.pre = mf(4); s.post = mf(4); s.comb = mf(16); s.m24 = mf(24);
        s.pre2 = mf(4); s.post2 = mf(4); s.comb2 = mf(16); s.cur_pre = mf(4);
        s.idxs_cat = (int32_t *)sycl::malloc_device(640 * 4, qs[t]);
        s.old = md(2 * 4 * g.h);
        s.eng_rows = md(2 * 24 * g.engram_dim); s.kvbuf = md(2 * 5 * g.h);
        s.widx = (int32_t *)sycl::malloc_device(128 * 4, qs[t]);
        s.ring = md(2 * (size_t)128 * g.hd);
        qs[t].memset(s.ring, 0, 2 * (size_t)128 * g.hd);
        s.tok_out = (int32_t *)sycl::malloc_device(4, qs[t]);
    }

    const WeightTab::E &we(const std::string &n) const { return W->at(n); }
    size_t wrb(const WeightTab::E &e) const { return W->row_bytes(e); }

    template <typename K, typename... A>
    void launch(int tile, size_t nwork, size_t lwork, K k, A... args) {
        qs[tile].submit([&](sycl::handler &hh) {
            hh.parallel_for(sycl::nd_range<1>((nwork + lwork - 1) / lwork * lwork, lwork),
                            [=](sycl::nd_item<1> it) { k(it, args...); });
        });
    }
    void gemv(int tile, const std::string &wn, const uint16_t *x, void *y,
              bool f32out = false) {
        const auto &e = we(wn);
        ops41sycl::Gemv k{e.type, (unsigned)e.rows, (unsigned)e.cols, f32out};
        launch(tile, (size_t)e.rows * 32, 32, k, (const uint8_t *)wgt.at(wn).p, wrb(e), x, y);
    }
    void rmsnorm(int tile, const uint16_t *x, const std::string &wn, int n, uint16_t *y) {
        ops41sycl::RmsNorm k{n};
        launch(tile, 32, 32, k, x, (const float *)wgt.at(wn).p, y);
    }
    void rope(int tile, uint16_t *x, int rows, int d, long p_, bool yarn, bool inv) {
        ops41sycl::RopePairs k{(unsigned)rows, (unsigned)d, 64u, inv};
        const float *cb = yarn ? cos_yarn[tile] : cos_base[tile];
        const float *sb = yarn ? sin_yarn[tile] : sin_base[tile];
        launch(tile, (size_t)rows * 32, 32, k, x, cb + (size_t)p_ * 32, sb + (size_t)p_ * 32);
    }

    // decode one token; returns next token id. cur tracks streams' tile.
    int32_t decode_step(int32_t token) {
        if (!sc_init) {
            for (int t = 0; t < TILES; ++t) scratch_alloc(t);
            sc_init = true;
        }
        const int H_ = g.h;
        // embed on tile 0 into streams_0
        {
            const auto &te = we("token_embd.weight");
            const uint8_t *row = (const uint8_t *)wgt.at("token_embd.weight").p +
                                 (size_t)token * wrb(te);
            launch(0, H_, 32, ops41sycl::EmbedRow{te.type, H_}, row, sc[0].attn_in);
            launch(0, H_, 32, ops41sycl::Broadcast4{H_}, (const uint16_t *)sc[0].attn_in,
                   streams_ptr[0]);
            float pm[4] = {1, 0, 0, 0};
            qs[0].memcpy(sc[0].pre, pm, 16);
            qs[0].wait();
            cur = 0;
        }
        for (int L = 0; L < g.layers; ++L) {
            int t = tile_of_layer(L);
            if (t != cur) migrate(t);
            auto &s = sc[t];
            std::string p = "blk." + std::to_string(L) + ".";
            if (L == 1 || L == 14) engram_host(L, t); // fills s.eng_rows; then kv+gate
            hc_mix(t, p + "hc_attn_", s, s.pre, s.post, s.comb);
            launch(t, H_, 32, ops41sycl::HcPre{H_}, streams_ptr[t], s.cur_pre, s.attn_in);
            rmsnorm(t, s.attn_in, p + "attn_norm.weight", H_, s.attn_n);
            attention(L, t, s);
            qs[t].memcpy(s.old, streams_ptr[t], 2 * 4 * H_);
            launch(t, (size_t)4 * H_, 32, ops41sycl::HcPost{H_}, streams_ptr[t], s.old,
                   s.ob, s.post, s.comb);
            hc_mix(t, p + "hc_ffn_", s, s.pre2, s.post2, s.comb2);
            launch(t, H_, 32, ops41sycl::HcPre{H_}, streams_ptr[t], s.pre2, s.attn_in);
            rmsnorm(t, s.attn_in, p + "ffn_norm.weight", H_, s.attn_n);
            moe(L, t, s);
            qs[t].memcpy(s.old, streams_ptr[t], 2 * 4 * H_);
            launch(t, (size_t)4 * H_, 32, ops41sycl::HcPost{H_}, streams_ptr[t], s.old,
                   s.ob, s.post2, s.comb2);
            qs[t].memcpy(s.cur_pre, s.pre2, 16);
        }
        // head on tile 11
        if (cur != 11) migrate(11);
        auto &s = sc[11];
        launch(11, g.h, 32, ops41sycl::HcPre{g.h}, streams_ptr[11], s.cur_pre, s.attn_in);
        rmsnorm(11, s.attn_in, "output_norm.weight", g.h, s.attn_n);
        gemv(11, "output.weight", s.attn_n, logits_, true);
        launch(11, 32, 32, ops41sycl::Argmax{g.vocab}, logits_, s.tok_out, (float *)nullptr);
        int32_t next;
        qs[11].memcpy(&next, s.tok_out, 4).wait();
        ++pos;
        return next;
    }

private:
    int cur = 0;
    float *logits_ = nullptr;

    void migrate(int t) {
        qs[cur].wait();
        qs[t].memcpy(streams_ptr[t], streams_ptr[cur], 2 * 4 * g.h);
        qs[t].memcpy(sc[t].cur_pre, sc[cur].cur_pre, 16);
        qs[t].wait();
        cur = t;
    }

    void hc_mix(int t, const std::string &prefix, Scratch &s, float *pre, float *post,
                float *comb) {
        launch(t, 24, 8, ops41sycl::HcMixDots{g.h}, streams_ptr[t],
               (const float *)wgt.at(prefix + "fn.weight").p, s.m24);
        launch(t, 1, 1, ops41sycl::HcMixFinish{}, s.m24,
               (const float *)wgt.at(prefix + "scale.weight").p,
               (const float *)wgt.at(prefix + "base.weight").p, pre, post, comb);
    }

    static int src_index(int layer) {
        static const int srcs[4] = {2, 8, 14, 20};
        int si = -1;
        for (int i = 0; i < 4; ++i) if (srcs[i] <= layer) si = i;
        return si;
    }
    static bool is_kv_source(int L) { return L == 2 || L == 8 || L == 14 || L == 20; }
    static bool is_index_source(int L) {
        return L == 2 || L == 8 || L == 14 || L == 20 || L == 24 || L == 28 || L == 32 ||
               L == 36;
    }
    static int index_slot(int L) { // position among the 8 index sources
        static const int idx[8] = {2, 8, 14, 20, 24, 28, 32, 36};
        for (int i = 0; i < 8; ++i) if (idx[i] == L) return i;
        return -1;
    }
    int cr_of(int L) const { return (L < 2 || L > 36) ? 0 : (L < 20 ? 2 : 1); }

    void attention(int L, int t, Scratch &s) {
        std::string p = "blk." + std::to_string(L) + ".";
        const int cr = cr_of(L);
        const bool yarn = cr > 0;
        gemv(t, p + "attn_q_a.weight", s.attn_n, s.qa);
        rmsnorm(t, s.qa, p + "attn_q_a_norm.weight", g.qrank, s.qn);
        gemv(t, p + "attn_q_b.weight", s.qn, s.q);
        rope(t, s.q, g.qh, g.hd, pos, yarn, false);
        gemv(t, p + "attn_kv.weight", s.attn_n, s.qa);     // reuse qa as 512 scratch
        rmsnorm(t, s.qa, p + "attn_kv_a_norm.weight", g.hd, s.kvn);
        rope(t, s.kvn, 1, g.hd, pos, yarn, false);
        launch(t, 1, 1, ops41sycl::WindowAppend{128, g.hd, (int)pos}, s.ring, s.kvn, s.widx);
        int si = src_index(L);
        int n_idx = 128;
        const int32_t *cidx = nullptr;
        if (cr) {
            if (is_kv_source(L)) publish(L, t, s, si, yarn);
            if (is_index_source(L)) index(L, t, s, si, yarn);
            cidx = cidx_mirror[t][isrc_for(L)];
            n_idx += 512;
        }
        // concat window idxs + compress idxs into one array
        qs[t].memcpy(s.idxs_cat, s.widx, 128 * 4);
        if (cr) qs[t].memcpy(s.idxs_cat + 128, cidx, 512 * 4);
        launch(t, g.qh, 8,
               ops41sycl::SparseAttn{n_idx, g.qh, g.hd, 128}, s.q, s.ring,
               cr ? ckv_mirror[t][si] : s.ring,
               (const float *)wgt.at(p + "attn_sinks.weight").p, s.idxs_cat, s.of);
        launch(t, g.qh * g.hd, 32, ops41sycl::ToBf16{g.qh * g.hd}, s.of, s.obuf);
        rope(t, s.obuf, g.qh, g.hd, pos, yarn, true);
        launch(t, (size_t)8 * (g.ototal / 8) * 32, 32,
               ops41sycl::GemvGrouped{8, g.ototal / 8, g.oin}, s.obuf,
               (const uint16_t *)wgt.at(p + "attn_output_a.weight").p, s.oa);
        gemv(t, p + "attn_output_b.weight", s.oa, s.ob);
    }

    // compressor publish + index-key append + mirror broadcasts
    void publish(int L, int t, Scratch &s, int si, bool yarn) {
        std::string p = "blk." + std::to_string(L) + ".";
        const int cr = cr_of(L);
        long gpos;
        bool emit;
        if (cr == 1) {
            gemv(t, p + "attn_compressor_kv.weight", s.attn_n, s.cw);
            rmsnorm(t, s.cw, p + "attn_compressor_norm.weight", g.hd, s.latent);
            gpos = pos;
            emit = true;
        } else {
            gemv(t, p + "attn_compressor_kv.weight", s.attn_n, s.cw);
            gemv(t, p + "attn_compressor_gate.weight", s.attn_n, s.scg);
            int slot = (int)(pos % 2);
            // store raw projections as f32 in the group state
            launch(t, g.hd, 32, ops41sycl::ToF32{g.hd}, s.cw,
                   s.kv_state + (size_t)si * 2 * g.hd + (size_t)slot * g.hd);
            launch(t, g.hd, 32, ops41sycl::ToF32{g.hd}, s.scg,
                   s.score_state + (size_t)si * 2 * g.hd + (size_t)slot * g.hd);
            gpos = pos - 1; // a latent stands for the first token of its group
            emit = (pos % 2) == 1;
            if (emit)
                launch(t, 1, 1, ops41sycl::CompressPool{2, g.hd},
                       s.kv_state + (size_t)si * 2 * g.hd,
                       s.score_state + (size_t)si * 2 * g.hd,
                       (const float *)wgt.at(p + "attn_compressor_norm.weight").p, s.latent);
        }
        if (!emit) return;
        // llama order: ik = rope(norm(wk * latent_pre)); comp = rope(latent_pre)
        gemv(t, p + "indexer.attn_k.weight", s.latent, s.kk);
        rmsnorm(t, s.kk, p + "indexer.k_norm.weight", 128, s.kk);
        rope(t, s.kk, 1, 128, gpos, yarn, false);
        rope(t, s.latent, 1, g.hd, gpos, yarn, false);
        long row = src_len[si];
        qs[t].wait();
        for (int o = 0; o < TILES; ++o) {
            qs[o].memcpy(ckv_mirror[o][si] + (size_t)row * g.hd, s.latent, 2 * g.hd);
            qs[o].memcpy(ik_mirror[o][si] + (size_t)row * 128, s.kk, 2 * 128);
        }
        for (auto &q : qs) q.wait();
        src_len[si]++;
    }

    void index(int L, int t, Scratch &s, int si, bool yarn) {
        std::string p = "blk." + std::to_string(L) + ".";
        gemv(t, p + "indexer.attn_q_b.weight", s.qn, s.qi);
        rope(t, s.qi, 32, 128, pos, yarn, false);
        gemv(t, p + "indexer.proj.weight", s.attn_n, s.wv);
        long len = src_len[si];
        qs[t].memcpy(s.lens, &len, 8);
        launch(t, (size_t)1 * max_seq, 32, ops41sycl::IndexerScore{32, 128, max_seq, 1},
               s.qi, ik_mirror[t][si], s.wv, s.lens, s.score);
        if (L == 20) {
            launch(t, 1, 1, ops41sycl::CandidateBlocks{max_seq, 8, 2048}, s.score, s.lens,
                   cand_);
            for (int o = 0; o < TILES; ++o) qs[o].memcpy(cand_mirror[o], cand_, max_seq);
            for (auto &q : qs) q.wait();
        } else if (L > 20) {
            launch(t, (size_t)max_seq, 32, ops41sycl::MaskApply{max_seq}, s.score,
                   cand_mirror[t]);
        }
        launch(t, 1, 1, ops41sycl::IndexerTopk{max_seq, 512, 128}, s.score, s.lens,
               s.cidx_loc);
        int slot = index_slot(L);
        for (int o = 0; o < TILES; ++o) {
            if (o != t) qs[o].memcpy(cidx_mirror[o][slot], s.cidx_loc, 512 * 4);
        }
        qs[t].memcpy(cidx_mirror[t][slot], s.cidx_loc, 512 * 4);
        for (auto &q : qs) q.wait();
    }

    static int isrc_for(int layer) {
        static const int idx[8] = {2, 8, 14, 20, 24, 28, 32, 36};
        int si = -1;
        for (int i = 0; i < 8; ++i) if (idx[i] <= layer) si = i;
        return si;
    }

    void moe(int L, int t, Scratch &s) {
        std::string p = "blk." + std::to_string(L) + ".";
        gemv(t, p + "ffn_gate_inp.weight", s.attn_n, s.router);
        launch(t, 1, 1, ops41sycl::Route{g.experts, 6}, s.router,
               (const float *)wgt.at(p + "exp_probs_b.bias").p, s.ids, s.prob);
        const auto &ge = we(p + "ffn_gate_exps.weight");
        launch(t, (size_t)6 * ge.rows * 32, 32,
               ops41sycl::RoutedGemv{ge.type, (unsigned)ge.rows, (unsigned)ge.cols},
               (const uint8_t *)wgt.at(p + "ffn_gate_exps.weight").p, s.attn_n, s.ids, s.expg);
        launch(t, (size_t)6 * ge.rows * 32, 32,
               ops41sycl::RoutedGemv{ge.type, (unsigned)ge.rows, (unsigned)ge.cols},
               (const uint8_t *)wgt.at(p + "ffn_up_exps.weight").p, s.attn_n, s.ids, s.expu);
        launch(t, (size_t)6 * g.mid, 32, ops41sycl::Swiglu{6 * g.mid}, s.expg, s.expu, s.act);
        launch(t, (size_t)6 * g.mid, 32, ops41sycl::ProbScale{6, g.mid}, s.act, s.prob);
        const auto &de = we(p + "ffn_down_exps.weight");
        launch(t, (size_t)6 * de.rows * 32, 32,
               ops41sycl::RoutedGemv{de.type, (unsigned)de.rows, (unsigned)de.cols},
               (const uint8_t *)wgt.at(p + "ffn_down_exps.weight").p, s.act, s.ids, s.expd);
        gemv(t, p + "ffn_gate_shexp.weight", s.attn_n, s.shg);
        gemv(t, p + "ffn_up_shexp.weight", s.attn_n, s.shu);
        launch(t, g.mid, 32, ops41sycl::Swiglu{g.mid}, s.shg, s.shu, s.sha);
        gemv(t, p + "ffn_down_shexp.weight", s.sha, s.shd);
        launch(t, g.h, 32, ops41sycl::MoeCombine{6, g.h}, s.expd, s.shd, s.ob);
    }

    // host-side engram hash + row gather; rows uploaded to tile t scratch.
    std::vector<int64_t> comp_ids; // mapped ids history (driver-maintained)
    const uint8_t *eng_base[2] = {}; // Q5_K tables for layers 1/14
    int64_t eng_primes[2][3][8];
    int64_t eng_off[2][24];
    int64_t eng_mult[2][4];
    int64_t eng_pad = 0;

    void engram_hash(int p, int li, int64_t *ids24) const {
        for (int i = 1; i <= 3; ++i) {
            uint64_t rolling = 0;
            for (int sh = 0; sh <= i; ++sh) {
                long long tk = (p - sh < 0 || p - sh >= (long)comp_ids.size())
                                   ? eng_pad
                                   : comp_ids[p - sh];
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

    void engram_host(int L, int t) {
        int li = L == 1 ? 0 : 1;
        int64_t ids[24];
        engram_hash((int)pos, li, ids);
        auto l = iq3::layout(iq3::Type::Q5_K);
        std::vector<uint16_t> rows(24 * 256);
        for (int c = 0; c < 24; ++c) {
            const uint8_t *row = eng_base[li] + (size_t)ids[c] * l.bytes;
            for (int i = 0; i < 256; ++i)
                rows[c * 256 + i] = ops41::bf16b(iq3::decode(iq3::Type::Q5_K, row, i));
        }
        std::string p = "blk." + std::to_string(L) + ".";
        qs[t].memcpy(sc[t].eng_rows, rows.data(), rows.size() * 2);
        gemv(t, p + "engram_kv.weight", sc[t].eng_rows, sc[t].kvbuf);
        launch(t, 4, 4, ops41sycl::EngramGate{g.h}, streams_ptr[t], sc[t].kvbuf,
               (const float *)wgt.at(p + "engram_gate.weight").p);
    }

    // state handoff: upload rings + caches from the CPU runner's dump.
    void load_state(long pos_, const long lens[4],
                    const std::vector<std::vector<float>> &rings,   // [40][128*512]
                    const std::vector<std::vector<float>> &ckv,     // [4][rows*512]
                    const std::vector<std::vector<float>> &ik,      // [4][rows*128]
                    const float kv_state[4][1024], const float score_state[4][1024]) {
        pos = pos_;
        for (int i = 0; i < 4; ++i) src_len[i] = lens[i];
        std::vector<uint16_t> tmp;
        auto up16 = [&](void *dst, const float *src, size_t n, int t) {
            tmp.resize(n);
            for (size_t i = 0; i < n; ++i) tmp[i] = ops41::bf16b(src[i]);
            qs[t].memcpy(dst, tmp.data(), n * 2);
        };
        for (int L = 0; L < 40; ++L) {
            int t = tile_of_layer(L);
            up16(sc[t].ring, rings[L].data(), rings[L].size(), t);
        }
        for (int i = 0; i < 4; ++i) {
            int st = tile_of_layer((int[]){2, 8, 14, 20}[i]);
            qs[st].memcpy(sc[st].kv_state + (size_t)i * 2 * 512, kv_state[i], 1024 * 4);
            qs[st].memcpy(sc[st].score_state + (size_t)i * 2 * 512, score_state[i], 1024 * 4);
            for (int o = 0; o < TILES; ++o) {
                up16(ckv_mirror[o][i], ckv[i].data(), ckv[i].size(), o);
                up16(ik_mirror[o][i], ik[i].data(), ik[i].size(), o);
            }
        }
        for (auto &q : qs) q.wait();
    }

    flash41::GeometryV41 g;
    int max_seq;
    sycl::context ctx;
    std::vector<sycl::device> devs;
    std::vector<sycl::queue> qs;
    std::unordered_map<std::string, DevPtr> buf, wgt;
    uint16_t *streams_ptr[TILES] = {};
    uint16_t *ckv_mirror[TILES][4] = {};
    uint16_t *ik_mirror[TILES][4] = {};
    int32_t *cidx_mirror[TILES][8] = {};
    uint8_t *cand_mirror[TILES] = {};
    uint8_t *cand_ = nullptr;
    float *cos_yarn[TILES] = {}, *sin_yarn[TILES] = {}, *cos_base[TILES] = {}, *sin_base[TILES] = {};

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
        for (int t = 0; t < TILES; ++t) {
            cos_yarn[t] = sycl::malloc_device<float>(P * 32, qs[t]);
            sin_yarn[t] = sycl::malloc_device<float>(P * 32, qs[t]);
            cos_base[t] = sycl::malloc_device<float>(P * 32, qs[t]);
            sin_base[t] = sycl::malloc_device<float>(P * 32, qs[t]);
            qs[t].memcpy(cos_yarn[t], cy.data(), cy.size() * 4);
            qs[t].memcpy(sin_yarn[t], sy.data(), sy.size() * 4);
            qs[t].memcpy(cos_base[t], cb.data(), cb.size() * 4);
            qs[t].memcpy(sin_base[t], sb.data(), sb.size() * 4);
        }
        for (auto &q : qs) q.wait();
    }
};

} // namespace own41
#endif
