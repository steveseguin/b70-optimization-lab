// cert_layout.hpp: per-tensor lossless-layout certificates (host and card; no engine or SYCL dependency on the host).
// A certificate names a source tensor (name, element count, FNV-1a of its bytes), the bit-pattern predicate every
// element was checked against, the packed layout it got, and the exact inverse its consumers apply. A tensor whose
// check fails anywhere keeps its source layout untouched (the fallback), so a certificate never changes a value.
//
// The one layout so far, F32_HI16: FP32 values whose low 16 bits are all zero, stored as their upper 16 bits in the
// same element order (row r, element i at r * cols + i, as the file). Inverse: bits = (uint32_t)h << 16, the value is
// bit_cast<float>(bits): the original FP32 bit pattern for every element (signs, zeros, subnormals, Inf, NaN payloads in
// the upper half included). Consumers decode with f32_from_hi16 at the point they loaded the float before, so the
// products, accumulation order and every rounding stay as they were; only the bytes read halve.
// Reusable for other lanes (DeepSeek V4.1, Qwen): certify at load or repack time, select the consumer's decoder at
// compile time from the layout, keep the source layout when the check fails. Tested by tools/test_cert_layout.cpp.
//
// The host helpers take byte pointers and read / write every element with memcpy, so a buffer of any alignment is
// fine (no typed access through a possibly misaligned pointer); counts are checked before any byte extent is formed.
#pragma once
#include <climits>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>
#if defined(SYCL_LANGUAGE_VERSION)
#include <sycl/sycl.hpp>
#else
#include <bit>
#endif

namespace ink::cert {

enum class Layout : uint8_t { SOURCE = 0, F32_HI16 = 1 };
inline const char *layout_name(Layout l) { return l == Layout::F32_HI16 ? "F32_HI16" : "SOURCE"; }

// ---- the exact inverse (card and host) ------------------------------------------------------------------------
inline float f32_from_bits(uint32_t u) {
#if defined(SYCL_LANGUAGE_VERSION)
    return sycl::bit_cast<float>(u);
#else
    return std::bit_cast<float>(u);
#endif
}
inline float f32_from_hi16(uint16_t h) { return f32_from_bits((uint32_t)h << 16); }
// two packed elements in one little-endian 32-bit word: element 2k in bits 0-15, element 2k + 1 in bits 16-31
inline float f32_even_from_pair(uint32_t w) { return f32_from_bits(w << 16); }
inline float f32_odd_from_pair(uint32_t w) { return f32_from_bits(w & 0xFFFF0000u); }

// ---- the predicate and the packing (host) ---------------------------------------------------------------------
// the largest element count whose FP32 byte extent (4 n) is representable
constexpr size_t MAX_F32_ELEMS = SIZE_MAX / 4;
inline void check_count(size_t n, const char *who) {
    if (n > MAX_F32_ELEMS) throw std::invalid_argument(std::string(who) + ": element count's byte extent overflows");
}
struct Check {
    bool ok = false;
    size_t n = 0, n_bad = 0;
    size_t first_bad = (size_t)-1; // index of the first failing element ((size_t)-1: none)
};
// every element, not only until the first failure (the count goes into the certificate). w: n FP32 words, any alignment
inline Check check_low16_zero(const void *w, size_t n) {
    check_count(n, "check_low16_zero");
    if (n && !w) throw std::invalid_argument("check_low16_zero: null source");
    const unsigned char *b = static_cast<const unsigned char *>(w);
    Check c;
    c.n = n;
    for (size_t i = 0; i < n; ++i) {
        uint32_t u;
        std::memcpy(&u, b + 4 * i, 4);
        if (u & 0xFFFFu) {
            if (c.n_bad == 0) c.first_bad = i;
            ++c.n_bad;
        }
    }
    c.ok = n > 0 && c.n_bad == 0;
    return c;
}
// src: n FP32 words, dst: room for dst_n halfwords (both any alignment)
inline void pack_hi16(const void *src, size_t n, void *dst, size_t dst_n) {
    check_count(n, "pack_hi16");
    if (dst_n < n) throw std::invalid_argument("pack_hi16: destination smaller than the source");
    if (n && (!src || !dst)) throw std::invalid_argument("pack_hi16: null buffer");
    const unsigned char *s = static_cast<const unsigned char *>(src);
    unsigned char *d = static_cast<unsigned char *>(dst);
    for (size_t i = 0; i < n; ++i) {
        uint32_t u;
        std::memcpy(&u, s + 4 * i, 4);
        const uint16_t h = (uint16_t)(u >> 16);
        std::memcpy(d + 2 * i, &h, 2);
    }
}
// FNV-1a, 64 bits (offset basis 14695981039346656037, prime 1099511628211; "foobar" -> 0x85944171f73967e8)
constexpr uint64_t FNV1A64_OFFSET = 14695981039346656037ULL, FNV1A64_PRIME = 1099511628211ULL;
inline uint64_t fnv1a64(const void *p, size_t n) {
    if (n && !p) throw std::invalid_argument("fnv1a64: null buffer");
    const unsigned char *b = static_cast<const unsigned char *>(p);
    uint64_t h = FNV1A64_OFFSET;
    for (size_t i = 0; i < n; ++i) { h ^= b[i]; h *= FNV1A64_PRIME; }
    return h;
}

struct Certificate {
    std::string name;           // source tensor identity: name, elements, hash of its bytes
    size_t elems = 0;
    uint64_t src_fnv = 0;
    Layout layout = Layout::SOURCE;
    Check check;
    size_t src_bytes() const { return 4 * elems; }
    size_t dst_bytes() const { return layout == Layout::F32_HI16 ? 2 * elems : 4 * elems; }
};
// certify one FP32 tensor (src: n words) and, when it passes and allow is set, pack it into dst (room for dst_n
// halfwords). On a failure (or allow = false) dst is not written and the certificate says SOURCE: the caller keeps the
// source bytes. An n whose byte extent overflows, or a destination smaller than n, throws before anything is read.
inline Certificate certify_f32_hi16(const std::string &name, const void *src, size_t n, void *dst, size_t dst_n, bool allow = true) {
    check_count(n, "certify_f32_hi16");
    if (allow && (dst_n < n || (n && !dst))) throw std::invalid_argument("certify_f32_hi16: destination smaller than the source: " + name);
    Certificate c;
    c.name = name;
    c.elems = n;
    c.src_fnv = fnv1a64(src, 4 * n);
    c.check = check_low16_zero(src, n);
    if (c.check.ok && allow) {
        pack_hi16(src, n, dst, dst_n);
        c.layout = Layout::F32_HI16;
    }
    return c;
}
// tensors whose consumers need one layout for all of them (e.g. a gain / forget pair read by one kernel with one row
// stride): all packed or none. srcs[k] / ns[k] / dsts[k] / dst_ns[k] per member (the five vectors of one length, else
// it throws before reading); returns the members' certificates
inline std::vector<Certificate> certify_group_f32_hi16(const std::vector<std::string> &names, const std::vector<const void *> &srcs,
                                                       const std::vector<size_t> &ns, const std::vector<void *> &dsts,
                                                       const std::vector<size_t> &dst_ns, bool allow = true) {
    const size_t m = names.size();
    if (srcs.size() != m || ns.size() != m || dsts.size() != m || dst_ns.size() != m)
        throw std::invalid_argument("certify_group_f32_hi16: member vectors of different lengths");
    for (size_t k = 0; k < m; ++k) {
        check_count(ns[k], "certify_group_f32_hi16");
        if (allow && (dst_ns[k] < ns[k] || (ns[k] && !dsts[k])))
            throw std::invalid_argument("certify_group_f32_hi16: destination smaller than the source: " + names[k]);
    }
    std::vector<Certificate> cs(m);
    bool all = allow && m > 0;
    for (size_t k = 0; k < m; ++k) {
        cs[k] = certify_f32_hi16(names[k], srcs[k], ns[k], nullptr, 0, false);
        all = all && cs[k].check.ok;
    }
    if (all)
        for (size_t k = 0; k < m; ++k) {
            pack_hi16(srcs[k], ns[k], dsts[k], dst_ns[k]);
            cs[k].layout = Layout::F32_HI16;
        }
    return cs;
}

// INK_CERT_HALF: unset or exactly "1" packs certified tensors, exactly "0" keeps every tensor in its source layout;
// anything else ("", "2", "-1", "1junk", " 1", "true") is refused with a warning and keeps the source layout (FP32)
inline bool half_from_env(const char *v, FILE *log = stderr) {
    if (!v) return true;
    if (std::strcmp(v, "1") == 0) return true;
    if (std::strcmp(v, "0") == 0) return false;
    if (log) std::fprintf(log, "[cert] warning: INK_CERT_HALF=\"%s\" is not 0 or 1; every tensor kept FP32\n", v);
    return false;
}
inline bool half_enabled() {
    static const bool v = half_from_env(std::getenv("INK_CERT_HALF"));
    return v;
}
inline bool verbose() {
    static const bool v = std::getenv("INK_CERT_VERBOSE") && std::strcmp(std::getenv("INK_CERT_VERBOSE"), "1") == 0;
    return v;
}

// ---- the extent of a dense FP32 tensor, checked before anything divides or multiplies by its dimensions ----------
// ne: nne ggml dimensions (ne[0] the contiguous one; missing ones are 1). ok only if every dimension is positive, the
// element count and its byte extent are representable, bytes == 4 x elements, and the row length and row count fit the
// kernels' int parameters.
struct Extent {
    bool ok = false;
    const char *why = "";
    int64_t ne[4] = {0, 0, 0, 0};
    size_t elems = 0;
    int cols = 0, rows = 0;
};
inline Extent f32_extent(const int64_t *ne, size_t nne, uint64_t bytes) {
    Extent e;
    if (!ne || nne < 1 || nne > 4) { e.why = "not 1 to 4 dimensions"; return e; }
    for (size_t i = 0; i < 4; ++i) e.ne[i] = i < nne ? ne[i] : 1;
    size_t n = 1;
    for (size_t i = 0; i < 4; ++i) {
        if (e.ne[i] <= 0) { e.why = "a dimension is not positive"; return e; }
        if ((uint64_t)e.ne[i] > MAX_F32_ELEMS / n) { e.why = "element count overflows"; return e; }
        n *= (size_t)e.ne[i];
    }
    if (n > MAX_F32_ELEMS) { e.why = "byte extent overflows"; return e; }
    if (bytes != 4 * (uint64_t)n) { e.why = "byte size is not 4 x elements"; return e; }
    const size_t rows = n / (size_t)e.ne[0];
    if (e.ne[0] > INT_MAX || rows > (size_t)INT_MAX) { e.why = "row length or row count does not fit int"; return e; }
    e.elems = n;
    e.cols = (int)e.ne[0];
    e.rows = (int)rows;
    e.ok = true;
    return e;
}

// ---- the Inkling-2 targets (from the tensor's name and shape only, so the host test applies the engine's rule) ----
// The F32 matrices read every one-token step: the expert routers (blk.N.ffn_gate_inp.weight, 2304 x 128) and the loop
// controls' products (blk.N.loop_<attn|k|v|mlp>_down.weight 4608 x 64, _gain / _forget.weight 64 x 2304): 168 tensors,
// 141.6 MB of FP32, 283.1 MB read per one-token step (48 router and 96 control applications). The other FP32 tensors
// that would certify (norms, convolution taps, relative bias: ~5 MB, a few us per step) are read by fused kernels
// through plain float pointers and stay FP32.
namespace inkling2 {
inline bool ends_with(const std::string &s, const char *x) {
    const size_t n = std::strlen(x);
    return s.size() > n && s.compare(s.size() - n, n, x) == 0;
}
inline bool is_pair_member(const std::string &name) {
    return name.compare(0, 4, "blk.") == 0 && name.find(".loop_") != std::string::npos &&
           (ends_with(name, "_gain.weight") || ends_with(name, "_forget.weight"));
}
// by name only: a tensor of the selection whatever its type or shape
inline bool half_candidate(const std::string &name) {
    if (name.compare(0, 4, "blk.") != 0) return false;
    if (ends_with(name, ".ffn_gate_inp.weight")) return true;
    if (name.find(".loop_") == std::string::npos) return false;
    return ends_with(name, "_down.weight") || ends_with(name, "_gain.weight") || ends_with(name, "_forget.weight");
}
// a candidate that may be packed: F32, a valid extent (f32_extent: no division before the dimensions are checked),
// rows of whole 32-value chunks, at least two rows
inline bool half_target(const std::string &name, bool is_f32, const int64_t *ne, size_t nne, uint64_t bytes) {
    if (!is_f32 || !half_candidate(name)) return false;
    const Extent e = f32_extent(ne, nne, bytes);
    return e.ok && e.cols % 32 == 0 && e.rows >= 2;
}
// tensors that take one layout together: a module's gain and forget (one kernel reads both with one row stride)
inline std::string half_group(const std::string &n) {
    for (const char *x : {"_gain.weight", "_forget.weight"})
        if (ends_with(n, x)) return n.substr(0, n.size() - std::strlen(x)) + "_gain|forget";
    return n;
}
// a gain / forget pair as the control kernels read it (CtlRows takes the gain's rows for both, ctl_out_r64 n_embd
// rows of gate_rank): both F32, both valid 2-D extents of gate_rank values x n_embd rows, the same dimensions.
// "" when compatible, else the reason
inline std::string pair_check(bool g_f32, const int64_t *g_ne, size_t g_nne, uint64_t g_bytes, bool f_f32, const int64_t *f_ne,
                              size_t f_nne, uint64_t f_bytes, int64_t gate_rank, int64_t n_embd) {
    if (!g_f32 || !f_f32) return "not both F32";
    const Extent a = f32_extent(g_ne, g_nne, g_bytes), b = f32_extent(f_ne, f_nne, f_bytes);
    if (!a.ok) return std::string("gain: ") + a.why;
    if (!b.ok) return std::string("forget: ") + b.why;
    for (int i = 0; i < 4; ++i)
        if (a.ne[i] != b.ne[i]) return "gain and forget dimensions differ";
    if (a.ne[2] != 1 || a.ne[3] != 1) return "not a 2-D matrix";
    if (gate_rank <= 0 || a.ne[0] != gate_rank) return "row length is not loop.gate_rank";
    if (n_embd <= 0 || a.ne[1] != n_embd) return "row count is not embedding_length";
    return "";
}
// one tensor as the planner sees it (the GGUF descriptor's fields)
struct TDesc {
    std::string name;
    bool is_f32 = false;
    int64_t ne[4] = {1, 1, 1, 1};
    size_t nne = 4;
    uint64_t bytes = 0;
};
// the groups to certify, in name order (indices into ts). Pairs are formed by name before any eligibility filter:
// a pair group must hold exactly one gain and one forget of compatible shape (pair_check) or the model is refused
// (throws std::runtime_error); a compatible pair whose members are not both half_target stays FP32 together. A
// router or down product is its own group when it is a half_target. Duplicate names throw.
inline std::vector<std::vector<size_t>> plan_groups(const std::vector<TDesc> &ts, int64_t gate_rank, int64_t n_embd) {
    std::map<std::string, std::vector<size_t>> by;
    for (size_t i = 0; i < ts.size(); ++i)
        if (half_candidate(ts[i].name)) by[half_group(ts[i].name)].push_back(i);
    std::vector<std::vector<size_t>> out;
    for (auto &kv : by) {
        const std::vector<size_t> &ix = kv.second;
        if (!is_pair_member(ts[ix[0]].name)) {
            if (ix.size() != 1) throw std::runtime_error("cert: duplicate tensor " + ts[ix[0]].name);
            const TDesc &t = ts[ix[0]];
            if (half_target(t.name, t.is_f32, t.ne, t.nne, t.bytes)) out.push_back(ix);
            continue;
        }
        const TDesc *g = nullptr, *f = nullptr;
        size_t gi = 0, fi = 0;
        for (size_t i : ix) {
            const bool isg = ends_with(ts[i].name, "_gain.weight");
            const TDesc *&slot = isg ? g : f;
            if (slot) throw std::runtime_error("cert: duplicate tensor " + ts[i].name);
            slot = &ts[i];
            (isg ? gi : fi) = i;
        }
        if (!g || !f) throw std::runtime_error("cert: loop gain / forget pair " + kv.first + " is missing a member");
        const std::string why = pair_check(g->is_f32, g->ne, g->nne, g->bytes, f->is_f32, f->ne, f->nne, f->bytes, gate_rank, n_embd);
        if (!why.empty()) throw std::runtime_error("cert: loop gain / forget pair " + kv.first + " incompatible: " + why);
        if (half_target(g->name, g->is_f32, g->ne, g->nne, g->bytes) && half_target(f->name, f->is_f32, f->ne, f->nne, f->bytes))
            out.push_back({gi, fi});
    }
    return out;
}
} // namespace inkling2

struct Census {
    std::vector<Certificate> certs;
    size_t n_packed = 0, n_kept = 0, src_packed = 0, dst_packed = 0, src_kept = 0;
    void add(const Certificate &c) {
        certs.push_back(c);
        if (c.layout == Layout::F32_HI16) { ++n_packed; src_packed += c.src_bytes(); dst_packed += c.dst_bytes(); }
        else { ++n_kept; src_kept += c.src_bytes(); }
    }
    std::string summary() const {
        char b[256];
        std::snprintf(b, sizeof b, "%zu FP32 tensors certified lossless as F32_HI16 (%.1f -> %.1f MB), %zu kept FP32 (%.1f MB)",
                      n_packed, src_packed / 1e6, dst_packed / 1e6, n_kept, src_kept / 1e6);
        return b;
    }
    void print(FILE *f, const char *tag = "[cert]") const {
        std::fprintf(f, "%s %s\n", tag, summary().c_str());
        if (!verbose()) return;
        for (const Certificate &c : certs)
            std::fprintf(f, "%s   %-40s %9zu elems fnv=%016llx %-8s bad=%zu first_bad=%lld\n", tag, c.name.c_str(), c.elems,
                         (unsigned long long)c.src_fnv, layout_name(c.layout), c.check.n_bad,
                         c.check.n_bad ? (long long)c.check.first_bad : -1LL);
    }
};

} // namespace ink::cert
