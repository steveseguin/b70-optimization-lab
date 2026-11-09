// CPU bring-up runner for DeepSeek V4.1 Flash on the real UD-IQ2_XXS
// weights + engram Q5_K table, all mmap'd read-only from NVMe.
// Reference semantics in f32 (equations mirror the gated ops_v41.hpp /
// attn_ops.hpp fixtures term for term). Weight-stationary prefill: each
// quantized weight row is decoded once and dotted with every prompt
// position; decode steps run per token. Gate: greedy token parity with
// the llama.cpp oracle pack on identical quantized bytes.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <map>
#include <numeric>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
#include "stage2/packet2/kernels/math.hpp"

static void die(const char *m) { std::fprintf(stderr, "fatal: %s\n", m); exit(1); }

// Decode-step trace for device bring-up (OWN_TRACE=path): tagged f32 records
// [u32 step][u32 layer][u32 tag][u32 n][n x f32]. Tags are shared with
// own_run_v41 (trace_tags_v41.hpp); compare with tools/dsv41_trace_diff.py.
#include "stage2/packet3/backend/trace_tags_v41.hpp"
static struct Trace {
    FILE *f = nullptr;
    bool on = false;
    int step = 0;
    void rec(int layer, int tag, const float *v, size_t n) {
        if (!f || !on) return;
        uint32_t h[4] = {(uint32_t)step, (uint32_t)layer, (uint32_t)tag, (uint32_t)n};
        fwrite(h, 4, 4, f);
        fwrite(v, 4, n, f);
    }
} TR;
// Prefill dump for the llama.cpp cross-check (OWN_PDUMP=path): same record
// format and tensor names as the out-of-tree llama_dump tool
// (u32 name_len, "name-L", i64 ne[4], u64 n, n x f32); compare with
// tools/dsv41_llama_diff.py.
static struct PDump {
    FILE *f = nullptr;
    bool on = false;
    void rec(const char *name, int layer, const float *v, size_t n) {
        if (!f || !on) return;
        char nm[96];
        if (layer >= 0) snprintf(nm, sizeof nm, "%s-%d", name, layer);
        else snprintf(nm, sizeof nm, "%s", name);
        uint32_t nl = (uint32_t)strlen(nm);
        fwrite(&nl, 4, 1, f);
        fwrite(nm, 1, nl, f);
        int64_t ne[4] = {(int64_t)n, 1, 1, 1};
        fwrite(ne, 8, 4, f);
        uint64_t n64 = n;
        fwrite(&n64, 8, 1, f);
        fwrite(v, 4, n, f);
    }
} PD;
// OWN_HC_LEGACY=1 restores the pre-2026-11-09 threading (FFN collapsed with
// its own pre-mix). Official model.py and llama.cpp deepseek41.cpp both use
// the ATTENTION's pre-mix for the FFN input; that is the default here.
static bool g_hc_legacy = false;

// ---------------------------------------------------------------- weights
struct Weight {
    const uint8_t *ptr = nullptr;
    iq3::Type type = iq3::Type::F32;
    int rows = 0, cols = 0, experts = 0;
};
static struct Store {
    std::map<std::string, Weight> w;
    std::vector<std::pair<const uint8_t *, size_t>> maps;
    std::vector<int> fds;
    const Weight &at(const std::string &n) const {
        auto it = w.find(n);
        if (it == w.end()) { std::fprintf(stderr, "weight missing: %s\n", n.c_str()); exit(1); }
        return it->second;
    }
    ~Store() { for (auto &[p, s] : maps) munmap((void *)p, s); for (int fd : fds) close(fd); }
} S;

static void load_store(const std::string &placement,
                       const std::map<std::string, std::pair<std::string, long>> &shards) {
    std::map<std::string, const uint8_t *> base;
    for (auto &[name, pd] : shards) {
        int fd = open(pd.first.c_str(), O_RDONLY);
        if (fd < 0) { perror("open shard"); exit(1); }
        struct stat st; fstat(fd, &st);
        auto *p = (const uint8_t *)mmap(nullptr, st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
        if (p == MAP_FAILED) { perror("mmap"); exit(1); }
        S.maps.push_back({p, (size_t)st.st_size});
        S.fds.push_back(fd);
        base[name] = p + pd.second;
    }
    std::ifstream f(placement);
    if (!f) die("placement unreadable");
    std::string shard, name, comp;
    long kind, offset, size, layer, mask, rank;
    while (f >> shard >> name >> comp >> kind >> offset >> size >> layer >> mask >> rank) {
        std::vector<long> dims(rank);
        for (auto &d : dims) f >> d;
        Weight w;
        w.type = (iq3::Type)kind;
        w.ptr = base.at(shard) + offset;
        w.cols = (int)dims[0];
        if (rank == 3) { w.experts = (int)dims[2]; w.rows = (int)dims[1]; }
        else w.rows = rank > 1 ? (int)dims[1] : 1;
        S.w[name] = w;
    }
}
static inline size_t row_bytes(const Weight &w) {
    auto l = iq3::layout(w.type);
    return (size_t)(w.cols / l.elements) * l.bytes;
}
static void dequant_row(const Weight &w, int r, float *out) {
    auto l = iq3::layout(w.type);
    const uint8_t *row = w.ptr + (size_t)r * row_bytes(w);
    for (int c = 0; c < w.cols; ++c)
        out[c] = iq3::decode(w.type, row + (size_t)(c / l.elements) * l.bytes, c % l.elements);
}
static std::vector<float> w_all(const Weight &w) {
    std::vector<float> v((size_t)w.rows * w.cols);
    for (int r = 0; r < w.rows; ++r) dequant_row(w, r, v.data() + (size_t)r * w.cols);
    return v;
}
static void gemv(const Weight &w, const float *x, float *y) {
    auto l = iq3::layout(w.type);
    size_t rb = row_bytes(w);
#pragma omp parallel for schedule(static)
    for (int r = 0; r < w.rows; ++r) {
        const uint8_t *row = w.ptr + (size_t)r * rb;
        float acc = 0;
        for (int c = 0; c < w.cols; ++c)
            acc += iq3::decode(w.type, row + (size_t)(c / l.elements) * l.bytes, c % l.elements) * x[c];
        y[r] = acc;
    }
}
static void gemv_expert(const Weight &w, int expert, const float *x, float *y) {
    Weight e = w;
    e.ptr = w.ptr + (size_t)expert * w.rows * row_bytes(w);
    gemv(e, x, y);
}
static void gemm(const Weight &w, const float *x, int npos, float *out) {
    size_t rb = row_bytes(w);
#pragma omp parallel for schedule(static)
    for (int r = 0; r < w.rows; ++r) {
        std::vector<float> row(w.cols);
        dequant_row(w, r, row.data());
        for (int p = 0; p < npos; ++p) {
            float acc = 0;
            const float *xp = x + (size_t)p * w.cols;
            for (int c = 0; c < w.cols; ++c) acc += row[c] * xp[c];
            out[(size_t)p * w.rows + r] = acc;
        }
    }
}
static void gemm_expert(const Weight &w, int expert, const float *x, int npos, float *out) {
    Weight e = w;
    e.ptr = w.ptr + (size_t)expert * w.rows * row_bytes(w);
    gemm(e, x, npos, out);
}

// ---------------------------------------------------------------- helpers
static void rmsnorm(const float *x, const float *w, int n, float *out) {
    double sq = 0;
    for (int i = 0; i < n; ++i) sq += double(x[i]) * x[i];
    float rs = float(1.0 / std::sqrt(sq / n + 1e-20));
    for (int i = 0; i < n; ++i) out[i] = w[i] * (x[i] * rs);
}
static inline float sigmoidf(float v) { return 1.0f / (1.0f + std::exp(-v)); }
static inline float siluf(float g) { return g / (1.0f + std::exp(-g)); }

static void rope_table(int yarn, int npos, std::vector<float> &cosb, std::vector<float> &sinb) {
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
    cosb.resize((size_t)npos * 32);
    sinb.resize((size_t)npos * 32);
    for (int p = 0; p < npos; ++p)
        for (int i = 0; i < 32; ++i) {
            cosb[(size_t)p * 32 + i] = (float)std::cos(p * f[i]);
            sinb[(size_t)p * 32 + i] = (float)std::sin(p * f[i]);
        }
}
static void rope_at(float *row, int d, const float *cosb, const float *sinb, bool inverse) {
    float *t = row + (d - 64);
    for (int i = 0; i < 32; ++i) {
        float re = t[2 * i], im = t[2 * i + 1];
        float c = cosb[i], s = inverse ? -sinb[i] : sinb[i];
        t[2 * i] = re * c - im * s;
        t[2 * i + 1] = re * s + im * c;
    }
}

static void hc_mixes(const float *streams, const float *fn, const float *scale,
                     const float *base, float *pre, float *post, float *comb) {
    const int N = 4 * 5120;
    double sq = 0;
    for (int i = 0; i < N; ++i) sq += double(streams[i]) * streams[i];
    float rsqrt = float(1.0 / std::sqrt(sq / N + 1e-20));
    float m[24];
    for (int j = 0; j < 24; ++j) {
        double acc = 0;
        for (int i = 0; i < N; ++i) acc += double(fn[(size_t)j * N + i]) * streams[i];
        m[j] = float(acc) * rsqrt;
    }
    const float eps = 1e-6f;
    for (int j = 0; j < 4; ++j) pre[j] = sigmoidf(m[j] * scale[0] + base[j]) + eps;
    for (int j = 0; j < 4; ++j) post[j] = 2.0f * sigmoidf(m[4 + j] * scale[1] + base[4 + j]);
    for (int j = 0; j < 16; ++j) comb[j] = m[8 + j] * scale[2] + base[8 + j];
    for (int j = 0; j < 4; ++j) {
        float mx = comb[j * 4];
        for (int k = 1; k < 4; ++k) mx = std::max(mx, comb[j * 4 + k]);
        float s = 0;
        for (int k = 0; k < 4; ++k) { comb[j * 4 + k] = std::exp(comb[j * 4 + k] - mx); s += comb[j * 4 + k]; }
        for (int k = 0; k < 4; ++k) comb[j * 4 + k] = comb[j * 4 + k] / s + eps;
    }
    for (int it = 0; it < 20; ++it) {
        if (it > 0)
            for (int j = 0; j < 4; ++j) {
                float s = 0;
                for (int k = 0; k < 4; ++k) s += comb[j * 4 + k];
                for (int k = 0; k < 4; ++k) comb[j * 4 + k] /= (s + eps);
            }
        for (int k = 0; k < 4; ++k) {
            float s = 0;
            for (int j = 0; j < 4; ++j) s += comb[j * 4 + k];
            for (int j = 0; j < 4; ++j) comb[j * 4 + k] /= (s + eps);
        }
    }
}
// OWN_COMB_LEGACY=1 restores the pre-2026-11-09 transposed comb (A/B only).
static bool g_comb_legacy = false;
static void hc_pre(const float *streams, const float *mix, float *out) {
    for (int i = 0; i < 5120; ++i) {
        float acc = 0;
        for (int j = 0; j < 4; ++j) acc += mix[j] * streams[(size_t)j * 5120 + i];
        out[i] = acc;
    }
}
static void hc_post(float *streams, const float *x, const float *post, const float *comb) {
    std::vector<float> old(streams, streams + 4 * 5120);
    for (int j = 0; j < 4; ++j)
        for (int i = 0; i < 5120; ++i) {
            // official: y[dst] = post[dst]*x + sum_src comb[src][dst]*residual[src]
            float acc = post[j] * x[i];
            for (int k = 0; k < 4; ++k)
                acc += (g_comb_legacy ? comb[j * 4 + k] : comb[k * 4 + j]) * old[(size_t)k * 5120 + i];
            streams[(size_t)j * 5120 + i] = acc;
        }
}
static void route(const float *logits, const float *bias, uint32_t *ids, float *prob) {
    const int E = 384, k = 6;
    std::vector<float> s(E);
    for (int i = 0; i < E; ++i) s[i] = std::sqrt(std::log1p(std::exp(logits[i])));
    std::vector<int> ord(E);
    for (int i = 0; i < E; ++i) ord[i] = i;
    std::partial_sort(ord.begin(), ord.begin() + k, ord.end(), [&](int a, int b) {
        return s[a] + bias[a] > s[b] + bias[b];
    });
    float sum = 0;
    for (int i = 0; i < k; ++i) { ids[i] = ord[i]; prob[i] = s[ord[i]]; sum += prob[i]; }
    for (int i = 0; i < k; ++i) prob[i] = prob[i] / (sum + 1e-20f) * 1.5f;
}

// ---------------------------------------------------------------- state
static const int N_LAYER = 40, D = 5120, H = 64, HD = 512, QL = 1280;
static const int WIN = 128, TOPK = 512, MOE_D = 2304;
// config.json compress_ratios has 43 entries: 40 main layers (0,0, 2 x18, 1 x20)
// followed by three zeros for the DSpark blocks. Layers 37-39 are ratio 1
// (YaRN rope, compressed reads); an earlier table took the trailing zeros
// for them (caught against llama.cpp per-layer dumps, 2026-11-09).
static const int compress_ratio[40] = {0,0,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1};
static const int kv_source[4] = {2, 8, 14, 20};
static const int index_source[8] = {2, 8, 14, 20, 24, 28, 32, 36};
static bool is_in(int v, const int *a, int n) { for (int i = 0; i < n; ++i) if (a[i] == v) return true; return false; }
static int kv_src_for(int L) {
    int s = -1;
    for (int i = 0; i < 4; ++i) if (kv_source[i] <= L) s = kv_source[i];
    return s;
}

struct Src {
    std::vector<float> ckv, ik;
    int len = 0;
    std::vector<float> kv_state, score_state;
};
struct Model {
    std::vector<int> toks;
    std::vector<long long> comp_ids;
    std::vector<std::vector<float>> ring;
    Src src[4];
    std::vector<std::vector<float>> cosb, sinb;
    std::vector<std::vector<int32_t>> topk;
    std::vector<std::vector<uint8_t>> cand_mask;
    const uint8_t *eng[2] = {nullptr, nullptr};
    std::vector<int32_t> token_map;
    int64_t primes[2][3][8], eng_off[2][24], eng_mult[2][4];
    int64_t eng_pad = 0;
    std::map<std::string, std::vector<float>> lw; // small-weight cache (norms, hc)
} M;
// Called from inside OpenMP regions (engram_apply_at during prefill): the
// cache must be locked. An unlocked insert corrupted the map once and left
// the main thread spinning in it forever (2026-11-09). Map nodes are stable,
// so the returned reference outlives the lock.
static const std::vector<float> &lw(const std::string &n) {
    const std::vector<float> *r;
#pragma omp critical(lw_cache)
    {
        auto it = M.lw.find(n);
        if (it == M.lw.end()) it = M.lw.emplace(n, w_all(S.at(n))).first;
        r = &it->second;
    }
    return *r;
}

static void engram_lookup(int li, const int64_t *ids24, float *out) {
    auto l = iq3::layout(iq3::Type::Q5_K);
    for (int c = 0; c < 24; ++c) {
        const uint8_t *row = M.eng[li] + (size_t)ids24[c] * l.bytes;
        for (int i = 0; i < 256; ++i)
            out[c * 256 + i] = iq3::decode(iq3::Type::Q5_K, row, i);
    }
}
static void engram_hash(int p, int li, int64_t *ids24) {
    for (int i = 1; i <= 3; ++i) {
        uint64_t rolling = 0;
        for (int sh = 0; sh <= i; ++sh) {
            long long t = (p - sh < 0) ? M.eng_pad : M.comp_ids[p - sh];
            if (t == -1) t = M.eng_pad;
            rolling ^= (uint64_t)(t * M.eng_mult[li][sh]);
        }
        int64_t r = (int64_t)rolling;
        for (int h = 0; h < 8; ++h) {
            int64_t pr = M.primes[li][i - 1][h];
            int64_t v = r % pr; if (v < 0) v += pr;
            ids24[(i - 1) * 8 + h] = v + M.eng_off[li][(i - 1) * 8 + h];
        }
    }
}
static void engram_apply_at(int L, float *streams, int abs_pos) {
    int li = L == 1 ? 0 : 1;
    std::string p = "blk." + std::to_string(L) + ".";
    int64_t ids[24];
    engram_hash(abs_pos, li, ids);
    std::vector<float> lut(6144), kv(25600);
    engram_lookup(li, ids, lut.data());
    gemv(S.at(p + "engram_kv.weight"), lut.data(), kv.data());
    const float *key = kv.data();
    const float *val = kv.data() + 4 * 5120;
    const auto &qw = lw(p + "engram_gate.weight");
    for (int j = 0; j < 4; ++j) {
        float *h = streams + (size_t)j * 5120;
        double hs = 0, ks = 0, dot = 0;
        for (int i = 0; i < 5120; ++i) {
            hs += double(h[i]) * h[i];
            ks += double(key[(size_t)j * 5120 + i]) * key[(size_t)j * 5120 + i];
        }
        double rstd = (1.0 / std::sqrt(hs / 5120 + 1e-20)) * (1.0 / std::sqrt(ks / 5120 + 1e-20));
        for (int i = 0; i < 5120; ++i)
            dot += double(h[i]) * qw[(size_t)j * 5120 + i] * key[(size_t)j * 5120 + i];
        double d = dot * rstd * (1.0 / std::sqrt(5120.0));
        float g = sigmoidf((float)std::copysign(std::sqrt(std::max(std::fabs(d), 1e-6)), d));
        for (int i = 0; i < 5120; ++i) h[i] += g * val[i];
    }
}

// ---------------------------------------------------------------- forward
static void attention(int L, const float *x, int P, int start, float *out) {
    std::string p = "blk." + std::to_string(L) + ".";
    const int r = compress_ratio[L];
    const auto &cosb = M.cosb[L], &sinb = M.sinb[L];

    std::vector<float> qr((size_t)P * QL), q((size_t)P * H * HD);
    gemm(S.at(p + "attn_q_a.weight"), x, P, qr.data());
    for (int t = 0; t < P; ++t)
        rmsnorm(qr.data() + (size_t)t * QL, lw(p + "attn_q_a_norm.weight").data(), QL, qr.data() + (size_t)t * QL);
    PD.rec("qr_norm", L, qr.data(), (size_t)P * QL);
    gemm(S.at(p + "attn_q_b.weight"), qr.data(), P, q.data());
    for (int t = 0; t < P; ++t)
        for (int hh = 0; hh < H; ++hh)
            rope_at(q.data() + ((size_t)t * H + hh) * HD, HD,
                    cosb.data() + (size_t)(start + t) * 32, sinb.data() + (size_t)(start + t) * 32, false);

    std::vector<float> kv((size_t)P * HD);
    gemm(S.at(p + "attn_kv.weight"), x, P, kv.data());
    for (int t = 0; t < P; ++t)
        rmsnorm(kv.data() + (size_t)t * HD, lw(p + "attn_kv_a_norm.weight").data(), HD, kv.data() + (size_t)t * HD);
    for (int t = 0; t < P; ++t)
        rope_at(kv.data() + (size_t)t * HD, HD,
                cosb.data() + (size_t)(start + t) * 32, sinb.data() + (size_t)(start + t) * 32, false);
    TR.rec(L, TT_Q, q.data(), (size_t)H * HD);
    TR.rec(L, TT_KV, kv.data(), HD);
    PD.rec("q", L, q.data(), (size_t)P * H * HD);
    PD.rec("kv", L, kv.data(), (size_t)P * HD);
    auto &ring = M.ring[L];
    if (start == 0) {
        if (P <= WIN) {
            for (int t = 0; t < P; ++t)
                memcpy(ring.data() + (size_t)t * HD, kv.data() + (size_t)t * HD, HD * 4);
        } else {
            int cutoff = P % WIN;
            for (int t = 0; t < WIN - cutoff; ++t)
                memcpy(ring.data() + (size_t)(cutoff + t) * HD, kv.data() + (size_t)(P - WIN + t) * HD, HD * 4);
            for (int t = 0; t < cutoff; ++t)
                memcpy(ring.data() + (size_t)t * HD, kv.data() + (size_t)(P - cutoff + t) * HD, HD * 4);
        }
    } else {
        memcpy(ring.data() + (size_t)(start % WIN) * HD, kv.data(), HD * 4);
    }
    int win_rows = start == 0 ? P : WIN;
    std::vector<const float *> win_ptr(win_rows);
    if (start == 0) for (int i = 0; i < win_rows; ++i) win_ptr[i] = kv.data() + (size_t)i * HD;
    else for (int i = 0; i < WIN; ++i) win_ptr[i] = ring.data() + (size_t)i * HD;

    int compress_len = r ? (start + P) / r : 0;
    std::vector<const float *> comp_ptr;
    std::vector<std::vector<int32_t>> cidx(P);
    if (r) {
        int src = kv_src_for(L);
        int src_idx = 0;
        for (int i = 0; i < 4; ++i) if (kv_source[i] == src) src_idx = i;
        Src &CS = M.src[src_idx];
        std::vector<float> latent_pre;
        if (is_in(L, kv_source, 4)) {
            std::vector<float> cw((size_t)P * HD);
            gemm(S.at(p + "attn_compressor_kv.weight"), x, P, cw.data());
            if (r == 1) {
                latent_pre.resize((size_t)P * HD);
                for (int t = 0; t < P; ++t)
                    rmsnorm(cw.data() + (size_t)t * HD, lw(p + "attn_compressor_norm.weight").data(), HD,
                            latent_pre.data() + (size_t)t * HD);
            } else {
                std::vector<float> score((size_t)P * HD);
                gemm(S.at(p + "attn_compressor_gate.weight"), x, P, score.data());
                if (start == 0) {
                    int full = P - P % 2;
                    latent_pre.resize((size_t)(full / 2) * HD);
                    for (int j = 0; j < full / 2; ++j) {
                        const float *k0 = cw.data() + (size_t)(2 * j) * HD, *k1 = k0 + HD;
                        const float *s0 = score.data() + (size_t)(2 * j) * HD, *s1 = s0 + HD;
                        // official: softmax JOINTLY over the slot axis per channel
                        // (model.py score.softmax(dim=1); llama.cpp ggml_soft_max
                        // over the ratio dim). An earlier per-slot denominator
                        // version diverged at token 4.
                        for (int i = 0; i < HD; ++i) {
                            float mx = std::max(s0[i], s1[i]);
                            double e0 = std::exp(double(s0[i]) - mx), e1 = std::exp(double(s1[i]) - mx);
                            latent_pre[(size_t)j * HD + i] =
                                k0[i] * (float)(e0 / (e0 + e1)) + k1[i] * (float)(e1 / (e0 + e1));
                        }
                        rmsnorm(latent_pre.data() + (size_t)j * HD, lw(p + "attn_compressor_norm.weight").data(),
                                HD, latent_pre.data() + (size_t)j * HD);
                    }
                    if (P % 2) {
                        memcpy(CS.kv_state.data(), cw.data() + (size_t)(P - 1) * HD, HD * 4);
                        memcpy(CS.score_state.data(), score.data() + (size_t)(P - 1) * HD, HD * 4);
                    }
                } else {
                    memcpy(CS.kv_state.data() + (size_t)(start % 2) * HD, cw.data(), HD * 4);
                    memcpy(CS.score_state.data() + (size_t)(start % 2) * HD, score.data(), HD * 4);
                    if ((start + 1) % 2 == 0) {
                        latent_pre.resize(HD);
                        for (int i = 0; i < HD; ++i) {
                            float mx = std::max(CS.score_state[i], CS.score_state[HD + i]);
                            double e0 = std::exp(double(CS.score_state[i]) - mx);
                            double e1 = std::exp(double(CS.score_state[HD + i]) - mx);
                            latent_pre[i] =
                                CS.kv_state[i] * (float)(e0 / (e0 + e1)) +
                                CS.kv_state[HD + i] * (float)(e1 / (e0 + e1));
                        }
                        rmsnorm(latent_pre.data(), lw(p + "attn_compressor_norm.weight").data(), HD, latent_pre.data());
                    }
                }
            }
        }
        if (!latent_pre.empty()) PD.rec("comp_latent", L, latent_pre.data(), latent_pre.size());
        if (is_in(L, index_source, 8)) {
            int T_ = compress_len;
            if (T_ > 0) {
                std::vector<float> qi((size_t)P * 32 * 128);
                gemm(S.at(p + "indexer.attn_q_b.weight"), qr.data(), P, qi.data());
                for (int t = 0; t < P; ++t)
                    for (int hh = 0; hh < 32; ++hh)
                        rope_at(qi.data() + ((size_t)t * 32 + hh) * 128, 128,
                                cosb.data() + (size_t)(start + t) * 32, sinb.data() + (size_t)(start + t) * 32, false);
                int krows = CS.len;
                if (is_in(L, kv_source, 4) && !latent_pre.empty()) {
                    int nl = (int)(latent_pre.size() / HD);
                    std::vector<float> kk((size_t)nl * 128);
                    gemm(S.at(p + "indexer.attn_k.weight"), latent_pre.data(), nl, kk.data());
                    for (int j = 0; j < nl; ++j) {
                        rmsnorm(kk.data() + (size_t)j * 128, lw(p + "indexer.k_norm.weight").data(), 128,
                                kk.data() + (size_t)j * 128);
                        int gpos = (start == 0 ? j : (start + 1 - r) / r + j) * r;
                        rope_at(kk.data() + (size_t)j * 128, 128,
                                cosb.data() + (size_t)gpos * 32, sinb.data() + (size_t)gpos * 32, false);
                        memcpy(CS.ik.data() + (size_t)(CS.len + j) * 128, kk.data() + (size_t)j * 128, 128 * 4);
                    }
                    krows = CS.len + nl;
                }
                std::vector<float> wv((size_t)P * 32);
                gemm(S.at(p + "indexer.proj.weight"), x, P, wv.data());
                std::vector<std::vector<float>> score(P, std::vector<float>(T_));
                for (int t = 0; t < P; ++t) {
                    int len = (int)std::min<int64_t>(T_, (int64_t)(start + t + 1) / r);
                    for (int j = 0; j < T_; ++j) {
                        if (j >= len || j >= krows) { score[t][j] = -INFINITY; continue; }
                        float s = 0;
                        for (int hh = 0; hh < 32; ++hh) {
                            float d = 0;
                            for (int i = 0; i < 128; ++i)
                                d += qi[((size_t)t * 32 + hh) * 128 + i] * CS.ik[(size_t)j * 128 + i];
                            if (d > 0) s += d * wv[(size_t)t * 32 + hh];
                        }
                        score[t][j] = s;
                    }
                }
                if (L == 20) {
                    const int bs = 8, tb = 2048;
                    int nb = (T_ + bs - 1) / bs;
                    M.cand_mask.assign(P, std::vector<uint8_t>(T_, 0));
                    for (int t = 0; t < P; ++t) {
                        int len = (int)std::min<int64_t>(T_, (int64_t)(start + t + 1) / r);
                        std::vector<float> bsc(nb, -INFINITY);
                        for (int j = 0; j < len; ++j) bsc[j / bs] = std::max(bsc[j / bs], score[t][j]);
                        int last = (len - 1) / bs;
                        bsc[last] = INFINITY; // official: pinned inside the top-k budget
                        std::vector<int> ord(nb);
                        std::iota(ord.begin(), ord.end(), 0);
                        int tk = std::min(tb, nb);
                        std::partial_sort(ord.begin(), ord.begin() + tk, ord.end(), [&](int a, int b) {
                            return bsc[a] > bsc[b] || (bsc[a] == bsc[b] && a < b);
                        });
                        for (int i = 0; i < tk; ++i)
                            if (bsc[ord[i]] > -INFINITY)
                                for (int j = ord[i] * bs; j < std::min((ord[i] + 1) * bs, T_); ++j)
                                    M.cand_mask[t][j] = 1;
                    }
                }
                if (L > 20 && !M.cand_mask.empty()) {
                    for (int t = 0; t < P; ++t) {
                        int T20 = (int)M.cand_mask[t].size();
                        for (int j = 0; j < T_ && j < T20; ++j)
                            if (!M.cand_mask[t][j]) score[t][j] = -INFINITY;
                    }
                }
                for (int t = 0; t < P; ++t) {
                    int len = (int)std::min<int64_t>(T_, (int64_t)(start + t + 1) / r);
                    int k = std::min(TOPK, len);
                    std::vector<int> ord(T_);
                    std::iota(ord.begin(), ord.end(), 0);
                    std::partial_sort(ord.begin(), ord.begin() + k, ord.end(), [&](int a, int b) {
                        return score[t][a] > score[t][b] || (score[t][a] == score[t][b] && a < b);
                    });
                    std::vector<int> sel(ord.begin(), ord.begin() + k);
                    std::sort(sel.begin(), sel.end());
                    cidx[t].resize(TOPK);
                    for (int i = 0; i < TOPK; ++i)
                        cidx[t][i] = i < k ? sel[i] + win_rows : -1;
                }
                M.topk = cidx;
            } else {
                for (int t = 0; t < P; ++t) cidx[t].assign(TOPK, -1);
                M.topk = cidx;
            }
        } else {
            cidx = M.topk;
        }
        if (is_in(L, kv_source, 4) && !latent_pre.empty()) {
            int nl = (int)(latent_pre.size() / HD);
            for (int j = 0; j < nl; ++j) {
                int gpos = (start == 0 ? j : (start + 1 - r) / r + j) * r;
                rope_at(latent_pre.data() + (size_t)j * HD, HD,
                        cosb.data() + (size_t)gpos * 32, sinb.data() + (size_t)gpos * 32, false);
                memcpy(CS.ckv.data() + (size_t)(CS.len + j) * HD, latent_pre.data() + (size_t)j * HD, HD * 4);
            }
            if (P == 1) {
                TR.rec(L, TT_PUB_CKV, CS.ckv.data() + (size_t)CS.len * HD, HD);
                TR.rec(L, TT_PUB_IK, CS.ik.data() + (size_t)CS.len * 128, 128);
            }
            CS.len += nl;
        }
        comp_ptr.resize(compress_len);
        for (int j = 0; j < compress_len; ++j) comp_ptr[j] = M.src[src_idx].ckv.data() + (size_t)j * HD;
    }

    std::vector<float> sinks = lw(p + "attn_sinks.weight");
    const float scale = float(1.0 / std::sqrt((double)HD));
    std::vector<float> o((size_t)P * H * HD, 0);
#pragma omp parallel for schedule(static)
    for (int t = 0; t < P; ++t) {
        std::vector<int32_t> idxs;
        if (start == 0) {
            int n = std::min(P, WIN);
            for (int i = 0; i < n; ++i) {
                int v = std::max(0, t - WIN + 1) + i;
                idxs.push_back(v > t ? -1 : v);
            }
        } else {
            int oldest = start % WIN + 1;
            for (int i = oldest; i < WIN; ++i) idxs.push_back(i > start ? -1 : i);
            for (int i = 0; i < oldest; ++i) idxs.push_back(i);
        }
        if (r) idxs.insert(idxs.end(), cidx[t].begin(), cidx[t].end());
        for (int hh = 0; hh < H; ++hh) {
            const float *qh = q.data() + ((size_t)t * H + hh) * HD;
            float mx = sinks[hh];
            std::vector<float> sc(idxs.size());
            for (size_t i = 0; i < idxs.size(); ++i) {
                if (idxs[i] < 0) { sc[i] = -INFINITY; continue; }
                const float *kvp = idxs[i] < win_rows ? win_ptr[idxs[i]] : comp_ptr[idxs[i] - win_rows];
                float d = 0;
                for (int c = 0; c < HD; ++c) d += qh[c] * kvp[c];
                sc[i] = d * scale;
                mx = std::max(mx, sc[i]);
            }
            double se = std::exp(double(sinks[hh]) - mx);
            for (size_t i = 0; i < idxs.size(); ++i)
                if (sc[i] > -INFINITY) se += std::exp(double(sc[i]) - mx);
            float *oh = o.data() + ((size_t)t * H + hh) * HD;
            for (size_t i = 0; i < idxs.size(); ++i) {
                if (sc[i] <= -INFINITY) continue;
                float wgt = (float)(std::exp(double(sc[i]) - mx) / se);
                const float *kvp = idxs[i] < win_rows ? win_ptr[idxs[i]] : comp_ptr[idxs[i] - win_rows];
                for (int c = 0; c < HD; ++c) oh[c] += wgt * kvp[c];
            }
        }
    }
    if (TR.on && TR.f && r) {
        std::vector<float> ci(TOPK);
        for (int i = 0; i < TOPK; ++i) ci[i] = (float)cidx[0][i];
        TR.rec(L, TT_CIDX, ci.data(), TOPK);
    }
    TR.rec(L, TT_ATTN_O, o.data(), (size_t)H * HD);
    for (int t = 0; t < P; ++t)
        for (int hh = 0; hh < H; ++hh)
            rope_at(o.data() + ((size_t)t * H + hh) * HD, HD,
                    cosb.data() + (size_t)(start + t) * 32, sinb.data() + (size_t)(start + t) * 32, true);
    const Weight &wa = S.at(p + "attn_output_a.weight");
    std::vector<float> oa((size_t)P * 8192);
    {
        size_t rb = row_bytes(wa);
        auto lay = iq3::layout(wa.type);
#pragma omp parallel for schedule(static)
        for (int rr = 0; rr < 8192; ++rr) {
            int g = rr / 1024;
            std::vector<float> row(4096);
            const uint8_t *rp = wa.ptr + (size_t)rr * rb;
            for (int c = 0; c < 4096; ++c)
                row[c] = iq3::decode(wa.type, rp + (size_t)(c / lay.elements) * lay.bytes, c % lay.elements);
            for (int t = 0; t < P; ++t) {
                const float *xp = o.data() + (size_t)t * H * HD + (size_t)g * 4096;
                float acc = 0;
                for (int c = 0; c < 4096; ++c) acc += row[c] * xp[c];
                oa[(size_t)t * 8192 + rr] = acc;
            }
        }
    }
    TR.rec(L, TT_ATTN_OA, oa.data(), 8192);
    PD.rec("attn_derope", L, o.data(), (size_t)P * H * HD);
    PD.rec("attn_wo_a", L, oa.data(), (size_t)P * 8192);
    gemm(S.at(p + "attn_output_b.weight"), oa.data(), P, out);
}

static void moe(int L, const float *x, int P, float *out) {
    std::string p = "blk." + std::to_string(L) + ".";
    std::vector<float> logits((size_t)P * 384);
    gemm(S.at(p + "ffn_gate_inp.weight"), x, P, logits.data());
    const auto &bias = lw(p + "exp_probs_b.bias");
    std::vector<float> sg((size_t)P * MOE_D), su((size_t)P * MOE_D), sd((size_t)P * D);
    gemm(S.at(p + "ffn_gate_shexp.weight"), x, P, sg.data());
    gemm(S.at(p + "ffn_up_shexp.weight"), x, P, su.data());
    for (size_t i = 0; i < (size_t)P * MOE_D; ++i) {
        float g = std::min(sg[i], 10.0f), u = std::clamp(su[i], -10.0f, 10.0f);
        sg[i] = siluf(g) * u;
    }
    gemm(S.at(p + "ffn_down_shexp.weight"), sg.data(), P, sd.data());
    std::vector<std::vector<int>> by_exp(384);
    std::vector<std::array<float, 6>> probs(P);
    std::vector<std::array<uint32_t, 6>> eids(P);
    for (int t = 0; t < P; ++t) {
        route(logits.data() + (size_t)t * 384, bias.data(), eids[t].data(), probs[t].data());
        for (int i = 0; i < 6; ++i) by_exp[eids[t][i]].push_back(t);
    }
    if (TR.on && TR.f) {
        float idf[6];
        for (int i = 0; i < 6; ++i) idf[i] = (float)eids[0][i];
        TR.rec(L, TT_ROUTE_LOGITS, logits.data(), 384);
        TR.rec(L, TT_ROUTE_IDS, idf, 6);
        TR.rec(L, TT_ROUTE_PROB, probs[0].data(), 6);
        TR.rec(L, TT_SHARED_DOWN, sd.data(), D);
    }
    std::vector<float> acc((size_t)P * D, 0);
    const Weight &gE = S.at(p + "ffn_gate_exps.weight");
    const Weight &uE = S.at(p + "ffn_up_exps.weight");
    const Weight &dE = S.at(p + "ffn_down_exps.weight");
    for (int e = 0; e < 384; ++e) {
        if (by_exp[e].empty()) continue;
        int n = (int)by_exp[e].size();
        std::vector<float> xs((size_t)n * D);
        for (int i = 0; i < n; ++i)
            memcpy(xs.data() + (size_t)i * D, x + (size_t)by_exp[e][i] * D, D * 4);
        std::vector<float> g((size_t)n * MOE_D), u((size_t)n * MOE_D);
        gemm_expert(gE, e, xs.data(), n, g.data());
        gemm_expert(uE, e, xs.data(), n, u.data());
        for (int i = 0; i < n; ++i) {
            float pr = 0;
            for (int k = 0; k < 6; ++k) if (eids[by_exp[e][i]][k] == (uint32_t)e) pr = probs[by_exp[e][i]][k];
            for (int c = 0; c < MOE_D; ++c) {
                float gv = std::min(g[(size_t)i * MOE_D + c], 10.0f);
                float uv = std::clamp(u[(size_t)i * MOE_D + c], -10.0f, 10.0f);
                g[(size_t)i * MOE_D + c] = pr * siluf(gv) * uv;
            }
        }
        std::vector<float> dn((size_t)n * D);
        gemm_expert(dE, e, g.data(), n, dn.data());
        for (int i = 0; i < n; ++i)
            for (int c = 0; c < D; ++c) acc[(size_t)by_exp[e][i] * D + c] += dn[(size_t)i * D + c];
    }
    for (size_t i = 0; i < (size_t)P * D; ++i) out[i] = acc[i] + sd[i];
    PD.rec("ffn_moe_logits", L, logits.data(), (size_t)P * 384);
    PD.rec("ffn_moe_out", L, acc.data(), (size_t)P * D);
    PD.rec("ffn_shexp", L, sd.data(), (size_t)P * D);
}

static void block(int L, float *streams, const std::vector<float> &pre_mix, int P, int start,
                  std::vector<float> &ffn_pre) {
    std::string p = "blk." + std::to_string(L) + ".";
    const auto &fn_a = lw(p + "hc_attn_fn.weight"), &fb_a = lw(p + "hc_attn_base.weight"), &fs_a = lw(p + "hc_attn_scale.weight");
    const auto &fn_f = lw(p + "hc_ffn_fn.weight"), &fb_f = lw(p + "hc_ffn_base.weight"), &fs_f = lw(p + "hc_ffn_scale.weight");
    const auto &an = lw(p + "attn_norm.weight"), &fnn = lw(p + "ffn_norm.weight");
    std::vector<float> x1((size_t)P * D), attn_out((size_t)P * D);
    std::vector<std::array<float, 4>> a_post(P), a_pre(P);
    std::vector<std::array<float, 16>> a_comb(P);
    for (int t = 0; t < P; ++t) {
        float *st = streams + (size_t)t * 4 * D;
        hc_mixes(st, fn_a.data(), fs_a.data(), fb_a.data(), a_pre[t].data(), a_post[t].data(), a_comb[t].data());
        hc_pre(st, pre_mix.data() + (size_t)t * 4, x1.data() + (size_t)t * D);
    }
    PD.rec("hc_attn_pre", L, x1.data(), (size_t)P * D);
    PD.rec("hc_pre_a", L, a_pre[0].data(), (size_t)P * 4);
    PD.rec("hc_post_a", L, a_post[0].data(), (size_t)P * 4);
    PD.rec("hc_comb_a", L, a_comb[0].data(), (size_t)P * 16);
    for (int t = 0; t < P; ++t)
        rmsnorm(x1.data() + (size_t)t * D, an.data(), D, x1.data() + (size_t)t * D);
    PD.rec("attn_norm", L, x1.data(), (size_t)P * D);
    TR.rec(L, TT_ATTN_MIX_PRE, a_pre[0].data(), 4);
    TR.rec(L, TT_ATTN_MIX_POST, a_post[0].data(), 4);
    TR.rec(L, TT_ATTN_MIX_COMB, a_comb[0].data(), 16);
    TR.rec(L, TT_ATTN_IN, x1.data(), D);
    attention(L, x1.data(), P, start, attn_out.data());
    TR.rec(L, TT_ATTN_OUT, attn_out.data(), D);
    PD.rec("attn_out", L, attn_out.data(), (size_t)P * D);
    for (int t = 0; t < P; ++t)
        hc_post(streams + (size_t)t * 4 * D, attn_out.data() + (size_t)t * D, a_post[t].data(), a_comb[t].data());
    TR.rec(L, TT_STREAMS_ATTN, streams, 4 * D);
    PD.rec("hc_attn_post", L, streams, (size_t)P * 4 * D);
    std::vector<float> ffn_in((size_t)P * D), ffn_out((size_t)P * D);
    std::vector<std::array<float, 4>> f_post(P);
    std::vector<std::array<float, 16>> f_comb(P);
    ffn_pre.resize((size_t)P * 4);
    for (int t = 0; t < P; ++t) {
        float *st = streams + (size_t)t * 4 * D;
        float pre[4];
        hc_mixes(st, fn_f.data(), fs_f.data(), fb_f.data(), pre, f_post[t].data(), f_comb[t].data());
        memcpy(ffn_pre.data() + (size_t)t * 4, pre, 16);
        // official Block.forward: "attention uses what the previous layer's FFN
        // produced and the FFN uses what this attention produced".
        hc_pre(st, g_hc_legacy ? pre : a_pre[t].data(), ffn_in.data() + (size_t)t * D);
    }
    PD.rec("hc_ffn_pre", L, ffn_in.data(), (size_t)P * D);
    PD.rec("hc_pre_f", L, ffn_pre.data(), (size_t)P * 4);
    PD.rec("hc_post_f", L, f_post[0].data(), (size_t)P * 4);
    PD.rec("hc_comb_f", L, f_comb[0].data(), (size_t)P * 16);
    for (int t = 0; t < P; ++t)
        rmsnorm(ffn_in.data() + (size_t)t * D, fnn.data(), D, ffn_in.data() + (size_t)t * D);
    PD.rec("ffn_norm", L, ffn_in.data(), (size_t)P * D);
    TR.rec(L, TT_FFN_MIX_PRE, ffn_pre.data(), 4);
    TR.rec(L, TT_FFN_IN, ffn_in.data(), D);
    moe(L, ffn_in.data(), P, ffn_out.data());
    TR.rec(L, TT_FFN_OUT, ffn_out.data(), D);
    PD.rec("ffn_out", L, ffn_out.data(), (size_t)P * D);
    for (int t = 0; t < P; ++t)
        hc_post(streams + (size_t)t * 4 * D, ffn_out.data() + (size_t)t * D, f_post[t].data(), f_comb[t].data());
    TR.rec(L, TT_STREAMS_FFN, streams, 4 * D);
    PD.rec("l_out", L, streams, (size_t)P * 4 * D);
}

// ---------------------------------------------------------------- engram file
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
        uint32_t type; uint64_t off;
        rd(&type, 4); rd(&off, 8);
        (void)type;
        offs[name] = off;
    }
    off_t ds = (lseek(fd, 0, SEEK_CUR) + 31) / 32 * 32;
    const uint8_t *m = (const uint8_t *)mmap(nullptr, st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (m == MAP_FAILED) { perror("mmap engram"); exit(1); }
    close(fd);
    // single stacked tensor per_layer_token_embd.weight [256, 768022850]:
    // layer-1 table rows [0, 384006168), layer-14 rows from 384006168.
    auto it = offs.find("per_layer_token_embd.weight");
    if (it == offs.end()) {
        std::fprintf(stderr, "engram tensors:"); for (auto &[k, v] : offs) std::fprintf(stderr, " %s", k.c_str());
        std::fprintf(stderr, "\n");
        die("engram table name");
    }
    const uint8_t *base = m + ds + it->second;
    return li == 0 ? base : base + (size_t)384006168 * 176; // Q5_K row = 176B / 256 elems
}

// ---------------------------------------------------------------- main
int main(int argc, char **argv) {
    if (argc < 4) {
        std::fprintf(stderr, "usage: %s ids.txt ndecode out_ids.txt [max_ctx] [engram.gguf]\n", argv[0]);
        return 2;
    }
    g_hc_legacy = getenv("OWN_HC_LEGACY") != nullptr;
    g_comb_legacy = getenv("OWN_COMB_LEGACY") != nullptr;
    if (const char *tp = getenv("OWN_TRACE")) TR.f = fopen(tp, "wb");
    const int trace_steps = getenv("OWN_TRACE_STEPS") ? atoi(getenv("OWN_TRACE_STEPS")) : 2;
    std::vector<int> forced;
    if (argc > 6) { std::ifstream ff(argv[6]); long long v; while (ff >> v) forced.push_back((int)v); }
    std::ifstream idf(argv[1]);
    std::vector<int> ids;
    long long v;
    while (idf >> v) ids.push_back((int)v);
    int ndecode = atoi(argv[2]);
    int max_ctx = argc > 4 ? atoi(argv[4]) : 4096;
    int P = (int)ids.size();
    std::fprintf(stderr, "prompt %d tokens, decode %d\n", P, ndecode);

    std::string root = "/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine";
    std::map<std::string, std::pair<std::string, long>> shards;
    {
        std::ifstream sj(root + "/planning/dsv41-fixtures/data/shards.tsv");
        if (!sj) die("shards.tsv missing");
        std::string name, path;
        long ds2;
        while (sj >> name >> path >> ds2) shards[name] = {path, ds2};
    }
    load_store(root + "/profiles/dsv41-iq2xxs/placement.tsv", shards);
    std::fprintf(stderr, "store: %zu tensors\n", S.w.size());

    const char *eng_path = argc > 5 ? argv[5]
        : "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-00006-of-00006.gguf";
    for (int li = 0; li < 2; ++li) M.eng[li] = map_engram(eng_path, li);

    {
        std::ifstream pf(root + "/../data/dsv41-reference/engram_prep.bin", std::ios::binary);
        if (!pf) die("engram_prep.bin missing");
        M.token_map.resize(129280);
        pf.read((char *)M.token_map.data(), 129280 * 4);
        pf.read((char *)M.primes, sizeof(M.primes));
        pf.read((char *)M.eng_off, sizeof(M.eng_off));
        pf.read((char *)M.eng_mult, sizeof(M.eng_mult));
        int64_t tail[2];
        pf.read((char *)tail, 16);
        M.eng_pad = tail[0];
    }

    M.ring.resize(N_LAYER);
    for (int L = 0; L < N_LAYER; ++L) M.ring[L].assign((size_t)WIN * HD, 0);
    for (int i = 0; i < 4; ++i) {
        int r = compress_ratio[kv_source[i]];
        int rows = max_ctx / r + 2;
        M.src[i].ckv.assign((size_t)rows * HD, 0);
        M.src[i].ik.assign((size_t)rows * 128, 0);
        M.src[i].kv_state.assign(2 * HD, 0);
        M.src[i].score_state.assign(2 * HD, -INFINITY);
    }
    M.cosb.resize(N_LAYER); M.sinb.resize(N_LAYER);
#pragma omp parallel for schedule(static)
    for (int L = 0; L < N_LAYER; ++L)
        rope_table(compress_ratio[L] > 0, max_ctx + 8, M.cosb[L], M.sinb[L]);

    M.toks = ids;
    M.comp_ids.resize(P);
    for (int t = 0; t < P; ++t) M.comp_ids[t] = M.token_map[ids[t]];
    std::vector<float> streams((size_t)P * 4 * D);
    {
        const Weight &te = S.at("token_embd.weight");
#pragma omp parallel for schedule(static)
        for (int t = 0; t < P; ++t) {
            std::vector<float> row(D);
            dequant_row(te, ids[t], row.data());
            for (int j = 0; j < 4; ++j)
                memcpy(streams.data() + ((size_t)t * 4 + j) * D, row.data(), D * 4);
        }
    }
    std::vector<float> pre_mix((size_t)P * 4, 0);
    for (int t = 0; t < P; ++t) pre_mix[(size_t)t * 4] = 1.0f;

    if (const char *pp = getenv("OWN_PDUMP")) PD.f = fopen(pp, "wb");
    PD.on = true;
    PD.rec("hc_init", -1, streams.data(), (size_t)P * 4 * D);
    // OWN_LLAMA_INJECT: teacher-force every layer's input from llama.cpp's own
    // l_out / FFN pre-mix (tools/dsv41_llama_inject.py), so each layer is
    // checked in isolation and reference noise cannot accumulate.
    FILE *inj = nullptr;
    if (const char *ip = getenv("OWN_LLAMA_INJECT"))
        if (!(inj = fopen(ip, "rb"))) die("OWN_LLAMA_INJECT unreadable");
    auto run_layers = [&](int P_, int start) {
        for (int L = 0; L < N_LAYER; ++L) {
            if (inj && start == 0 && L > 0) {
                uint64_t n[2];
                if (fread(n, 8, 2, inj) != 2 || n[0] != (uint64_t)P_ * 4 * D || n[1] != (uint64_t)P_ * 4)
                    die("inject file does not match this prompt");
                if (fread(streams.data(), 4, n[0], inj) != n[0]) die("inject short");
                if (fread(pre_mix.data(), 4, n[1], inj) != n[1]) die("inject short");
            }
            if (L == 1 || L == 14) {
#pragma omp parallel for schedule(static)
                for (int t = 0; t < P_; ++t)
                    engram_apply_at(L, streams.data() + (size_t)t * 4 * D, start + t);
                PD.rec("engram_out", L, streams.data(), (size_t)P_ * 4 * D);
            }
            std::vector<float> ffn_pre;
            block(L, streams.data(), pre_mix, P_, start, ffn_pre);
            pre_mix = ffn_pre;
        }
    };

    run_layers(P, 0);
    std::vector<float> hx(D), logits(129280);
    hc_pre(streams.data() + (size_t)(P - 1) * 4 * D, pre_mix.data() + (size_t)(P - 1) * 4, hx.data());
    PD.rec("hc_out", -1, hx.data(), D);
    rmsnorm(hx.data(), lw("output_norm.weight").data(), D, hx.data());
    PD.rec("result_norm", -1, hx.data(), D);
    gemv(S.at("output.weight"), hx.data(), logits.data());
    PD.rec("result_output", -1, logits.data(), 129280);
    PD.on = false;
    if (PD.f) { fclose(PD.f); PD.f = nullptr; }
    int next = (int)(std::max_element(logits.begin(), logits.end()) - logits.begin());
    {
        std::vector<int> ord(129280);
        std::iota(ord.begin(), ord.end(), 0);
        std::partial_sort(ord.begin(), ord.begin() + 5, ord.end(),
                          [&](int a, int b) { return logits[a] > logits[b]; });
        std::fprintf(stderr, "tok 0 -> %d | top5:", next);
        for (int i = 0; i < 5; ++i) std::fprintf(stderr, " %d:%.4f", ord[i], logits[ord[i]]);
        std::fprintf(stderr, "\n");
    }
    std::vector<int> out_ids{next};
    std::fprintf(stderr, "prefill done; first token %d\n", next);
    if (argc > 7) { // dump device-handoff state (post-prefill, incl first token)
        std::ofstream df(argv[7], std::ios::binary);
        long posd = P;
        df.write((char *)&posd, 8);
        long lens[4];
        for (int i = 0; i < 4; ++i) lens[i] = M.src[i].len;
        df.write((char *)lens, 32);
        for (int L = 0; L < N_LAYER; ++L)
            df.write((char *)M.ring[L].data(), (size_t)WIN * HD * 4);
        for (int i = 0; i < 4; ++i) {
            df.write((char *)M.src[i].ckv.data(), (size_t)lens[i] * HD * 4);
            df.write((char *)M.src[i].ik.data(), (size_t)lens[i] * 128 * 4);
        }
        for (int i = 0; i < 4; ++i) {
            df.write((char *)M.src[i].kv_state.data(), 2 * HD * 4);
            df.write((char *)M.src[i].score_state.data(), 2 * HD * 4);
        }
        long nt = (long)M.toks.size();
        df.write((char *)&nt, 8);
        df.write((char *)M.toks.data(), nt * 4);
        df.write((char *)M.comp_ids.data(), nt * 8);
        df.write((char *)&next, 4);
        std::fprintf(stderr, "state dumped: pos=%ld lens=%ld,%ld,%ld,%ld next=%d\n",
                     posd, lens[0], lens[1], lens[2], lens[3], next);
    }

    for (int d = 1; d < ndecode; ++d) {
        int feed = (d - 1 < (int)forced.size()) ? forced[d - 1] : next;
        M.toks.push_back(feed);
        M.comp_ids.push_back(M.token_map[feed]);
        int pos = P + d - 1;
        std::vector<float> s1(4 * D);
        {
            std::vector<float> row(D);
            dequant_row(S.at("token_embd.weight"), feed, row.data());
            for (int j = 0; j < 4; ++j) memcpy(s1.data() + (size_t)j * D, row.data(), D * 4);
        }
        std::vector<float> pm(4, 0);
        pm[0] = 1;
        TR.step = d;
        TR.on = d <= trace_steps;
        TR.rec(0, TT_EMBED, s1.data(), 4 * D);
        for (int L = 0; L < N_LAYER; ++L) {
            if (L == 1 || L == 14) {
                engram_apply_at(L, s1.data(), pos);
                TR.rec(L, TT_ENGRAM, s1.data(), 4 * D);
            }
            std::vector<float> ffn_pre;
            block(L, s1.data(), pm, 1, pos, ffn_pre);
            pm = ffn_pre;
        }
        hc_pre(s1.data(), pm.data(), hx.data());
        rmsnorm(hx.data(), lw("output_norm.weight").data(), D, hx.data());
        gemv(S.at("output.weight"), hx.data(), logits.data());
        TR.rec(40, TT_FINAL_N, hx.data(), D);
        TR.rec(40, TT_LOGITS, logits.data(), 129280);
        TR.on = false;
        if (TR.f) fflush(TR.f);
        next = (int)(std::max_element(logits.begin(), logits.end()) - logits.begin());
        out_ids.push_back(next);
        {
            std::vector<int> ord(129280);
            std::iota(ord.begin(), ord.end(), 0);
            std::partial_sort(ord.begin(), ord.begin() + 5, ord.end(),
                              [&](int a, int b) { return logits[a] > logits[b]; });
            std::fprintf(stderr, "tok %d -> %d | top5:", d, next);
            for (int i = 0; i < 5; ++i) std::fprintf(stderr, " %d:%.4f", ord[i], logits[ord[i]]);
            std::fprintf(stderr, "\n");
        }
    }
    std::ofstream of(argv[3]);
    for (int t : out_ids) of << t << "\n";
    return 0;
}
