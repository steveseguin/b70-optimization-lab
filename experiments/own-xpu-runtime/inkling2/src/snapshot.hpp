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
    std::vector<Part> parts;
    float *conv = nullptr, *row = nullptr;
    size_t conv_floats = 0;
    int cpar = 0, E = 0;
    int64_t pos = -1;          // n_past at the copy; -1: no copy
    std::vector<int32_t> tok;  // the tokens read up to pos
    size_t bytes = 0;
    bool ok = false;

    // allocates the copy when it fits with INK_SNAP_ROOM_MB (default 256) to spare; INK_SNAP=0: never
    void init(Engine &e, Drafter *dr) {
        if (const char *s = std::getenv("INK_SNAP"); s && !std::atoi(s)) return;
        Device &d = e.d;
        const HParams &h = e.m.hp;
        const size_t kd = (size_t)h.n_head_kv * h.head_dim;
        std::vector<std::pair<sycl::half *, size_t>> live;
        for (int a = 0; a < h.n_app; ++a) {
            if (e.kmask[a] == 0x7fffffff) continue; // (by position: never overwritten below the copy's position)
            const size_t n = (size_t)(e.kmask[a] + 1) * kd;
            live.push_back({e.Kc[a], n});
            live.push_back({e.Vc[a], n});
        }
        if (dr)
            for (int l = 0; l < Drafter::NL; ++l) {
                if (dr->kmask[l] == 0x7fffffff) continue;
                const size_t n = (size_t)(dr->kmask[l] + 1) * dr->kd;
                live.push_back({dr->Kc[l], n});
                live.push_back({dr->Vc[l], n});
            }
        conv_floats = (size_t)2 * e.conv_n * h.n_app;
        E = dr ? dr->E : 0;
        bytes = conv_floats * sizeof(float) + (size_t)E * sizeof(float);
        for (auto &p : live) bytes += p.second * sizeof(sycl::half);
        const size_t spare = (size_t)(std::getenv("INK_SNAP_ROOM_MB") ? std::atol(std::getenv("INK_SNAP_ROOM_MB")) : 256) << 20;
        if (d.allocated + d.hold + bytes + spare > d.limit()) {
            std::fprintf(stderr, "[snap] no room on the card for the %.0f MiB copy (requests that do not extend the held "
                                 "conversation start over)\n", bytes / 1048576.0);
            return;
        }
        for (auto &p : live) parts.push_back({p.first, d.alloc<sycl::half>(p.second), p.second});
        conv = d.alloc<float>(conv_floats);
        if (E) row = d.alloc<float>(E);
        ok = true;
        std::fprintf(stderr, "[snap] %.0f MiB copy on the card (%zu buffers)\n", bytes / 1048576.0, parts.size());
    }

    // the state now (position e.n_past; ids starts with the tokens read)
    void take(Engine &e, Drafter *dr, const std::vector<int32_t> &ids) {
        pos = -1;
        if (!ok || e.n_past <= 0 || (size_t)e.n_past > ids.size() || (dr && dr->r_last < 0)) return;
        sycl::queue &q = e.d.q;
        for (auto &p : parts) q.memcpy(p.copy, p.live, p.n * sizeof(sycl::half));
        q.memcpy(conv, e.conv, conv_floats * sizeof(float));
        if (dr) q.memcpy(row, dr->rrows + (size_t)dr->r_last * E, (size_t)E * sizeof(float));
        cpar = e.cpar;
        pos = e.n_past;
        tok.assign(ids.begin(), ids.begin() + pos);
    }

    // true when ids continues from the copy (starts with its tokens and goes past them)
    bool fits(const std::vector<int32_t> &ids) const {
        return pos > 0 && ids.size() > (size_t)pos && std::equal(tok.begin(), tok.end(), ids.begin());
    }

    void restore(Engine &e, Drafter *dr) {
        sycl::queue &q = e.d.q;
        for (auto &p : parts) q.memcpy(p.live, p.copy, p.n * sizeof(sycl::half));
        q.memcpy(e.conv, conv, conv_floats * sizeof(float));
        if (dr) {
            q.memcpy(dr->rrows, row, (size_t)E * sizeof(float));
            dr->r_last = 0;
        }
        e.cpar = cpar;
        e.n_past = (int)pos;
    }
};

} // namespace ink
