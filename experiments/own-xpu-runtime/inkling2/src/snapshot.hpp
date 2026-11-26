// A copy, on the card, of the state that later positions overwrite: the windowed applications' rings, the short
// convolutions' state and, with the drafter, its rings and its context row. The full-context caches need no copy: a
// conversation that continues from the copy's position writes only positions at or past it. Restoring the copy puts
// the engine back at that position exactly as it was, so a request that starts with the same tokens (a regenerated
// answer, an edited last message, another question after the same document) reads only what follows them.
#pragma once
#include <cstdlib>
#include <vector>

#include "dspark.hpp"
#include "engine.hpp"

namespace ink {

struct Snapshot {
    struct Part { sycl::half *live, *copy; size_t n; };
    // one engine's share (a split: each engine of the chain holds its own applications' state, on its own card)
    struct Eng { Engine *x; std::vector<Part> parts; float *conv = nullptr; size_t conv_floats = 0; int cpar = 0; };
    std::vector<Eng> es;
    float *row = nullptr;
    int E = 0;
    int64_t pos = -1;          // n_past at the copy; -1: no copy
    std::vector<int32_t> tok;  // the tokens read up to pos
    size_t bytes = 0;
    bool ok = false;

    // allocates the copy when it fits with INK_SNAP_ROOM_MB (default 256) to spare on every card; INK_SNAP=0: never
    void init(Engine &e, Drafter *dr) {
        if (const char *s = std::getenv("INK_SNAP"); s && !std::atoi(s)) return;
        const size_t spare = (size_t)(std::getenv("INK_SNAP_ROOM_MB") ? std::atol(std::getenv("INK_SNAP_ROOM_MB")) : 256) << 20;
        struct Plan { Engine *x; std::vector<std::pair<sycl::half *, size_t>> live; size_t conv_floats, bytes; };
        std::vector<Plan> plan;
        for (Engine *x = &e; x; x = x->prev) {
            const HParams &h = x->m.hp;
            const size_t kd = (size_t)h.n_head_kv * h.head_dim;
            Plan p{x, {}, (size_t)2 * x->conv_n * h.n_app, 0};
            for (int a = x->a0; a < x->a1; ++a) {
                if (x->kmask[a] == 0x7fffffff) continue; // (by position: never overwritten below the copy's position)
                const size_t n = (size_t)(x->kmask[a] + 1) * kd;
                p.live.push_back({x->Kc[a], n});
                p.live.push_back({x->Vc[a], n});
            }
            if (x == &e && dr)
                for (int l = 0; l < Drafter::NL; ++l) {
                    if (dr->kmask[l] == 0x7fffffff) continue;
                    const size_t n = (size_t)(dr->kmask[l] + 1) * dr->kd;
                    p.live.push_back({dr->Kc[l], n});
                    p.live.push_back({dr->Vc[l], n});
                }
            p.bytes = p.conv_floats * sizeof(float) + (x == &e && dr ? (size_t)dr->E * sizeof(float) : 0);
            for (auto &l : p.live) p.bytes += l.second * sizeof(sycl::half);
            // (engines sharing a card: the copies of all of them on it)
            size_t on_card = 0;
            for (auto &q : plan) if (&q.x->d == &x->d) on_card += q.bytes;
            if (x->d.allocated + x->d.hold + on_card + p.bytes + spare > x->d.limit()) {
                std::fprintf(stderr, "[snap] no room on card %d for the %.0f MiB copy (requests that do not extend the held "
                                     "conversation start over)\n", x->d.index, p.bytes / 1048576.0);
                return;
            }
            bytes += p.bytes;
            plan.push_back(std::move(p));
        }
        for (auto &p : plan) {
            Eng g{p.x, {}, nullptr, p.conv_floats, 0};
            for (auto &l : p.live) g.parts.push_back({l.first, p.x->d.alloc<sycl::half>(l.second), l.second});
            g.conv = p.x->d.alloc<float>(p.conv_floats);
            es.push_back(std::move(g));
        }
        E = dr ? dr->E : 0;
        if (E) row = e.d.alloc<float>(E);
        ok = true;
        size_t nb = 0;
        for (auto &g : es) nb += g.parts.size();
        std::fprintf(stderr, "[snap] %.0f MiB copy on the card%s (%zu buffers)\n", bytes / 1048576.0, es.size() > 1 ? "s" : "", nb);
    }

    // the state now (position e.n_past; ids starts with the tokens read)
    void take(Engine &e, Drafter *dr, const std::vector<int32_t> &ids) {
        pos = -1;
        if (!ok || e.n_past <= 0 || (size_t)e.n_past > ids.size() || (dr && dr->r_last < 0)) return;
        for (auto &g : es) {
            sycl::queue &q = g.x->d.q;
            for (auto &p : g.parts) q.memcpy(p.copy, p.live, p.n * sizeof(sycl::half));
            q.memcpy(g.conv, g.x->conv, g.conv_floats * sizeof(float));
            g.cpar = g.x->cpar;
        }
        if (dr) e.d.q.memcpy(row, dr->rrows + (size_t)dr->r_last * E, (size_t)E * sizeof(float));
        pos = e.n_past;
        tok.assign(ids.begin(), ids.begin() + pos);
    }

    // true when ids continues from the copy (starts with its tokens and goes past them)
    bool fits(const std::vector<int32_t> &ids) const {
        return pos > 0 && ids.size() > (size_t)pos && std::equal(tok.begin(), tok.end(), ids.begin());
    }

    void restore(Engine &e, Drafter *dr) {
        for (auto &g : es) {
            sycl::queue &q = g.x->d.q;
            for (auto &p : g.parts) q.memcpy(p.live, p.copy, p.n * sizeof(sycl::half));
            q.memcpy(g.x->conv, g.conv, g.conv_floats * sizeof(float));
            g.x->cpar = g.cpar;
            g.x->n_past = (int)pos;
        }
        if (dr) {
            e.d.q.memcpy(dr->rrows, row, (size_t)E * sizeof(float));
            dr->r_last = 0;
        }
    }
};

} // namespace ink
