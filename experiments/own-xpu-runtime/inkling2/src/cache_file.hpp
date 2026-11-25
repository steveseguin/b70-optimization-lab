#pragma once
// A read prompt saved to a file and loaded back (ink_run INK_SAVE_CACHE / INK_LOAD_CACHE): the engine's state after a
// prompt (every full layer's keys and values, the windowed layers' last positions, the convolution states, the last
// logits row) and the drafter's (its three layers' cached positions and the last head-context row), so a later run
// over the same prompt, or one that continues it, starts where the first stopped. Every value is copied as it is, by
// position: a run with another context size (another step size, ring size or V row length) loads the same file.
// The file is written and read with O_DIRECT in 64 MiB pieces (no page cache; host memory 64 MiB), card copies of at
// most a piece each.
#include "dspark.hpp"
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#include <cstdlib>
#include <cstring>

namespace ink {

struct CacheHdr {
    char magic[8];
    uint64_t n_tok, n_app, kd, E, conv_n, vocab_padded, model_id;
    uint64_t eng_cnt[64]; // positions saved per application (windowed: the last ring's worth)
    uint64_t has_dr, dr_nl, dr_kd, dr_E;
    uint64_t dr_cnt[8];
};

class CacheIO {
    static constexpr size_t PIECE = 64u << 20, ALIGN = 4096;
    int fd = -1;
    bool wr;
    char *buf = nullptr;
    size_t used = 0, have = 0; // writer: bytes in buf; reader: bytes read into buf (used = consumed)
    bool eof = false;
    sycl::queue *q;
    void flush() { // writer: buf full (or the end, padded)
        q->wait();
        size_t n = (used + ALIGN - 1) / ALIGN * ALIGN;
        if (n > used) std::memset(buf + used, 0, n - used);
        for (size_t o = 0; o < n;) {
            const ssize_t r = ::write(fd, buf + o, n - o);
            if (r <= 0) throw std::runtime_error(std::string("cache file: write failed: ") + std::strerror(errno));
            o += (size_t)r;
        }
        bytes += used;
        used = 0;
    }
    void refill() { // reader: everything in buf consumed
        q->wait(); // (copies from buf to the card done)
        have = used = 0;
        while (have < PIECE && !eof) {
            const ssize_t r = ::read(fd, buf + have, PIECE - have);
            if (r < 0) throw std::runtime_error(std::string("cache file: read failed: ") + std::strerror(errno));
            if (r == 0) eof = true;
            have += (size_t)r;
            bytes += (size_t)r;
        }
        if (have == 0) throw std::runtime_error("cache file: shorter than its header says");
    }

  public:
    size_t bytes = 0;
    CacheIO(const std::string &path, bool write, sycl::queue &queue) : wr(write), q(&queue) {
        const int fl = write ? (O_WRONLY | O_CREAT | O_TRUNC) : O_RDONLY;
        fd = ::open(path.c_str(), fl | O_DIRECT, 0644);
        if (fd < 0 && errno == EINVAL) fd = ::open(path.c_str(), fl, 0644); // (a file system without O_DIRECT)
        if (fd < 0) throw std::runtime_error("cache file " + path + ": " + std::strerror(errno));
        buf = (char *)std::aligned_alloc(ALIGN, PIECE);
        if (!buf) throw std::runtime_error("cache file: no host buffer");
    }
    ~CacheIO() {
        if (buf) { q->wait(); std::free(buf); }
        if (fd >= 0) ::close(fd);
    }
    void finish() {
        if (wr && used) flush();
        if (wr && ::fsync(fd) != 0) throw std::runtime_error(std::string("cache file: fsync failed: ") + std::strerror(errno));
    }
    // host bytes
    void put(const void *p, size_t n) {
        const char *c = (const char *)p;
        while (n) {
            const size_t k = std::min(n, PIECE - used);
            q->wait();
            std::memcpy(buf + used, c, k);
            used += k; c += k; n -= k;
            if (used == PIECE) flush();
        }
    }
    void get(void *p, size_t n) {
        char *c = (char *)p;
        while (n) {
            if (used == have) refill();
            const size_t k = std::min(n, have - used);
            std::memcpy(c, buf + used, k);
            used += k; c += k; n -= k;
        }
    }
    // card bytes: copied straight between the card and the piece buffer (the copies finish before the buffer is reused)
    void put_dev(const void *dev, size_t n) {
        const char *c = (const char *)dev;
        while (n) {
            const size_t k = std::min(n, PIECE - used);
            q->memcpy(buf + used, c, k);
            used += k; c += k; n -= k;
            if (used == PIECE) flush();
        }
    }
    void get_dev(void *dev, size_t n) {
        char *c = (char *)dev;
        while (n) {
            if (used == have) refill();
            const size_t k = std::min(n, have - used);
            q->memcpy(c, buf + used, k);
            used += k; c += k; n -= k;
        }
    }
    void skip(size_t n) {
        while (n) {
            if (used == have) refill();
            const size_t k = std::min(n, have - used);
            used += k; n -= k;
        }
    }
};

namespace cache_detail {
// positions [p0, p1) of a cache whose slot is position & mask, as runs of consecutive slots
template <class F> void runs(int64_t p0, int64_t p1, int64_t mask, F f) {
    for (int64_t p = p0; p < p1;) {
        const int64_t s = p & mask, n = std::min(p1 - p, mask - s + 1);
        f(s, n);
        p += n;
    }
}
// rows of w halfs per slot ([slot][w]), positions [p1 - cnt, p1)
inline void save_rows(CacheIO &io, const sycl::half *c, int64_t w, int64_t mask, int64_t cnt, int64_t p1) {
    runs(p1 - cnt, p1, mask, [&](int64_t s, int64_t n) { io.put_dev(c + s * w, sizeof(sycl::half) * (size_t)(n * w)); });
}
// the file holds cnt positions ending at p1; the cache takes the last min(cnt, room) of them
inline void load_rows(CacheIO &io, sycl::half *c, int64_t w, int64_t mask, int64_t cnt, int64_t room, int64_t p1) {
    const int64_t k = std::min(cnt, room);
    io.skip(sizeof(sycl::half) * (size_t)((cnt - k) * w));
    runs(p1 - k, p1, mask, [&](int64_t s, int64_t n) { io.get_dev(c + s * w, sizeof(sycl::half) * (size_t)(n * w)); });
}
// a transposed cache ([w][ld]): row by row, positions [p1 - cnt, p1)
inline void save_t(CacheIO &io, const sycl::half *c, int64_t w, int64_t ld, int64_t mask, int64_t cnt, int64_t p1) {
    for (int64_t r = 0; r < w; ++r)
        runs(p1 - cnt, p1, mask, [&](int64_t s, int64_t n) { io.put_dev(c + r * ld + s, sizeof(sycl::half) * (size_t)n); });
}
inline void load_t(CacheIO &io, sycl::half *c, int64_t w, int64_t ld, int64_t mask, int64_t cnt, int64_t room, int64_t p1) {
    const int64_t k = std::min(cnt, room);
    for (int64_t r = 0; r < w; ++r) {
        io.skip(sizeof(sycl::half) * (size_t)(cnt - k));
        runs(p1 - k, p1, mask, [&](int64_t s, int64_t n) { io.get_dev(c + r * ld + s, sizeof(sycl::half) * (size_t)n); });
    }
}
inline int64_t room_of(int mask, int64_t n) { return mask == 0x7fffffff ? n : std::min<int64_t>(n, (int64_t)mask + 1); }
} // namespace cache_detail

// the state after the prompt tok (n_past == tok.size(), its logits row last)
inline size_t save_cache(const std::string &path, Engine &e, Drafter *dr, const std::vector<int32_t> &tok, uint64_t model_id) {
    using namespace cache_detail;
    const HParams &h = e.m.hp;
    if ((size_t)e.n_past != tok.size()) throw std::runtime_error("save_cache: the cache does not hold exactly the prompt");
    if (h.n_app > 64 || (dr && Drafter::NL > 8)) throw std::runtime_error("save_cache: too many layers for the header");
    e.d.q.wait();
    CacheHdr hd{};
    std::memcpy(hd.magic, "INKC0001", 8);
    const int64_t n = e.n_past, kd = (int64_t)h.n_head_kv * h.head_dim;
    hd.n_tok = (uint64_t)n; hd.n_app = h.n_app; hd.kd = kd; hd.E = h.n_embd; hd.conv_n = e.conv_n;
    hd.vocab_padded = h.vocab_padded; hd.model_id = model_id;
    for (int a = 0; a < h.n_app; ++a) hd.eng_cnt[a] = (uint64_t)room_of(e.kmask[a], n);
    if (dr) {
        hd.has_dr = 1; hd.dr_nl = Drafter::NL; hd.dr_kd = dr->kd; hd.dr_E = dr->E;
        for (int l = 0; l < Drafter::NL; ++l) hd.dr_cnt[l] = (uint64_t)room_of(dr->kmask[l], n);
        if (dr->r_last < 0) throw std::runtime_error("save_cache: the drafter has no context row");
    }
    CacheIO io(path, true, e.d.q);
    io.put(&hd, sizeof(hd));
    io.put(tok.data(), sizeof(int32_t) * tok.size());
    io.put_dev(e.lg + (size_t)(e.n_logit_rows - 1) * h.vocab_padded, sizeof(float) * h.vocab_padded);
    io.put_dev(e.conv + (size_t)e.cpar * h.n_app * e.conv_n, sizeof(float) * (size_t)h.n_app * e.conv_n);
    for (int a = 0; a < h.n_app; ++a) {
        const int64_t cnt = (int64_t)hd.eng_cnt[a];
        save_rows(io, e.Kc[a], kd, e.kmask[a], cnt, n);
        if (e.vld) save_t(io, e.Vc[a], kd, e.kvl[a], e.kmask[a], cnt, n);
        else save_rows(io, e.Vc[a], kd, e.kmask[a], cnt, n);
    }
    if (dr) {
        for (int l = 0; l < Drafter::NL; ++l) {
            save_rows(io, dr->Kc[l], dr->kd, dr->kmask[l], (int64_t)hd.dr_cnt[l], n);
            save_rows(io, dr->Vc[l], dr->kd, dr->kmask[l], (int64_t)hd.dr_cnt[l], n);
        }
        io.put_dev(dr->rrows + (size_t)dr->r_last * dr->E, sizeof(float) * dr->E);
    }
    io.finish();
    return io.bytes;
}

// loads a file whose prompt is tok or a prefix of it into a fresh engine (and drafter); returns the positions loaded.
// With the whole prompt loaded, its logits row is restored (next_token() works); else the caller feeds the rest
inline size_t load_cache(const std::string &path, Engine &e, Drafter *dr, const std::vector<int32_t> &tok, uint64_t model_id,
                         size_t *file_bytes = nullptr) {
    using namespace cache_detail;
    const HParams &h = e.m.hp;
    if (e.n_past != 0) throw std::runtime_error("load_cache: the engine has read something already");
    CacheIO io(path, false, e.d.q);
    CacheHdr hd{};
    io.get(&hd, sizeof(hd));
    const int64_t kd = (int64_t)h.n_head_kv * h.head_dim;
    if (std::memcmp(hd.magic, "INKC0001", 8) || hd.n_app != (uint64_t)h.n_app || hd.kd != (uint64_t)kd || hd.E != (uint64_t)h.n_embd ||
        hd.conv_n != (uint64_t)e.conv_n || hd.vocab_padded != (uint64_t)h.vocab_padded || hd.model_id != model_id)
        throw std::runtime_error("load_cache: " + path + " was saved by another model or engine");
    const int64_t n = (int64_t)hd.n_tok;
    if (n > (int64_t)tok.size()) throw std::runtime_error("load_cache: the file's prompt is longer than this run's");
    if (n + 1 > e.cap) throw std::runtime_error("load_cache: the context is too small for the file");
    std::vector<int32_t> ft(n);
    io.get(ft.data(), sizeof(int32_t) * (size_t)n);
    if (!std::equal(ft.begin(), ft.end(), tok.begin())) throw std::runtime_error("load_cache: this run's prompt does not start with the file's");
    if (dr && !hd.has_dr) throw std::runtime_error("load_cache: the file has no drafter state (save it with INK_DRAFT, or load without)");
    if (dr && (hd.dr_nl != (uint64_t)Drafter::NL || hd.dr_kd != (uint64_t)dr->kd || hd.dr_E != (uint64_t)dr->E))
        throw std::runtime_error("load_cache: the file's drafter is another one");
    io.get_dev(e.lg, sizeof(float) * h.vocab_padded); // row 0
    io.get_dev(e.conv, sizeof(float) * (size_t)h.n_app * e.conv_n); // copy 0
    for (int a = 0; a < h.n_app; ++a) {
        const int64_t cnt = (int64_t)hd.eng_cnt[a], room = room_of(e.kmask[a], n);
        load_rows(io, e.Kc[a], kd, e.kmask[a], cnt, room, n);
        if (e.vld) load_t(io, e.Vc[a], kd, e.kvl[a], e.kmask[a], cnt, room, n);
        else load_rows(io, e.Vc[a], kd, e.kmask[a], cnt, room, n);
    }
    if (dr) {
        for (int l = 0; l < Drafter::NL; ++l) {
            const int64_t cnt = (int64_t)hd.dr_cnt[l], room = room_of(dr->kmask[l], n);
            load_rows(io, dr->Kc[l], dr->kd, dr->kmask[l], cnt, room, n);
            load_rows(io, dr->Vc[l], dr->kd, dr->kmask[l], cnt, room, n);
        }
        io.get_dev(dr->rrows, sizeof(float) * dr->E);
        dr->r_last = 0;
    }
    e.d.q.wait();
    e.n_past = (int)n;
    e.cpar = 0;
    e.n_logit_rows = 1;
    if (file_bytes) *file_bytes = io.bytes;
    return (size_t)n;
}

} // namespace ink
