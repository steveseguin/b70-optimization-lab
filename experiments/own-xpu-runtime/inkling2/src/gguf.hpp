// gguf.hpp: a minimal GGUF v3 reader for the Inkling-2 engine. Reads the header (metadata and tensor table) with
// pread; tensor data is read later by the uploader at data_off + tensor offset. No mmap: the model is about the size
// of host memory, and a mapping would compete with the page cache for it.
#pragma once
#include <climits>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <map>
#include <stdexcept>
#include <string>
#include <unistd.h>
#include <variant>
#include <vector>

namespace ink {

// ggml type ids used by the Inkling-2 GGUFs (ggml/include/ggml.h of the reference tree)
enum GType : uint32_t {
    G_F32 = 0, G_F16 = 1, G_Q4_0 = 2, G_Q4_1 = 3, G_Q5_0 = 6, G_Q5_1 = 7, G_Q8_0 = 8, G_Q8_1 = 9,
    G_Q2_K = 10, G_Q3_K = 11, G_Q4_K = 12, G_Q5_K = 13, G_Q6_K = 14, G_Q8_K = 15,
    G_IQ2_XXS = 16, G_IQ2_XS = 17, G_IQ3_XXS = 18, G_IQ1_S = 19, G_IQ4_NL = 20, G_IQ3_S = 21, G_IQ2_S = 22,
    G_IQ4_XS = 23, G_I8 = 24, G_I16 = 25, G_I32 = 26, G_I64 = 27, G_F64 = 28, G_IQ1_M = 29, G_BF16 = 30,
    G_MXFP4 = 39, G_NVFP4 = 40,
};

// elements per block and bytes per block, for the types we read
inline void type_block(uint32_t t, int &blk, int &bytes) {
    switch (t) {
    case G_F32: blk = 1; bytes = 4; return;
    case G_F16: case G_BF16: blk = 1; bytes = 2; return;
    case G_I32: blk = 1; bytes = 4; return;
    case G_Q8_0: blk = 32; bytes = 34; return;
    case G_Q5_0: blk = 32; bytes = 22; return;
    case G_Q4_0: blk = 32; bytes = 18; return;
    case G_IQ4_NL: blk = 32; bytes = 18; return;
    case G_Q4_K: blk = 256; bytes = 144; return;
    case G_Q5_K: blk = 256; bytes = 176; return;
    case G_Q6_K: blk = 256; bytes = 210; return;
    case G_IQ4_XS: blk = 256; bytes = 136; return;
    case G_NVFP4: blk = 64; bytes = 36; return; // checked against ggml-common.h at load (see check_nvfp4_block)
    default: throw std::runtime_error("gguf: unsupported tensor type " + std::to_string(t));
    }
}
inline const char *type_name(uint32_t t) {
    switch (t) {
    case G_F32: return "F32"; case G_F16: return "F16"; case G_BF16: return "BF16"; case G_I32: return "I32";
    case G_Q8_0: return "Q8_0"; case G_Q5_0: return "Q5_0"; case G_Q4_0: return "Q4_0"; case G_IQ4_NL: return "IQ4_NL";
    case G_Q4_K: return "Q4_K"; case G_Q5_K: return "Q5_K"; case G_Q6_K: return "Q6_K"; case G_IQ4_XS: return "IQ4_XS";
    case G_NVFP4: return "NVFP4"; default: return "?";
    }
}

struct Tensor {
    std::string name;
    uint32_t type = 0;
    std::vector<int64_t> ne; // ggml order, always 4 entries (unused = 1): ne[0] is the contiguous (row) dimension
    int n_dims = 0;
    uint64_t off = 0;        // from the start of the data section
    uint64_t bytes = 0;
    int64_t nel() const { int64_t n = 1; for (auto d : ne) n *= d; return n; }
    int64_t rows() const { return ne[0] ? nel() / ne[0] : 0; } // (parse() checks that nel() is representable)
    uint64_t row_bytes() const { int b, s; type_block(type, b, s); return (uint64_t)(ne[0] / b) * s; }
};

using Value = std::variant<int64_t, uint64_t, double, bool, std::string, std::vector<int64_t>, std::vector<double>,
                           std::vector<std::string>>;

struct GGUF {
    std::string path;
    int fd = -1;
    uint64_t data_off = 0, file_size = 0;
    uint32_t alignment = 32;
    std::map<std::string, Value> kv;
    std::vector<Tensor> tensors;
    std::map<std::string, size_t> index;

    explicit GGUF(const std::string &p) : path(p) {
        fd = ::open(p.c_str(), O_RDONLY);
        if (fd < 0) throw std::runtime_error("gguf: cannot open " + p);
        file_size = (uint64_t)lseek(fd, 0, SEEK_END);
        parse();
    }
    ~GGUF() { if (fd >= 0) ::close(fd); }
    GGUF(const GGUF &) = delete;
    GGUF &operator=(const GGUF &) = delete;

    const Tensor *find(const std::string &n) const {
        auto it = index.find(n);
        return it == index.end() ? nullptr : &tensors[it->second];
    }
    const Tensor &at(const std::string &n) const {
        auto *t = find(n);
        if (!t) throw std::runtime_error("gguf: missing tensor " + n);
        return *t;
    }
    bool has(const std::string &k) const { return kv.count(k) != 0; }
    int64_t i(const std::string &k) const {
        auto it = kv.find(k);
        if (it == kv.end()) throw std::runtime_error("gguf: missing key " + k);
        if (auto *v = std::get_if<int64_t>(&it->second)) return *v;
        if (auto *v = std::get_if<uint64_t>(&it->second)) return (int64_t)*v;
        if (auto *v = std::get_if<bool>(&it->second)) return *v;
        throw std::runtime_error("gguf: key is not an integer: " + k);
    }
    double f(const std::string &k) const {
        auto it = kv.find(k);
        if (it == kv.end()) throw std::runtime_error("gguf: missing key " + k);
        if (auto *v = std::get_if<double>(&it->second)) return *v;
        return (double)i(k);
    }
    std::string s(const std::string &k) const {
        auto it = kv.find(k);
        if (it == kv.end()) throw std::runtime_error("gguf: missing key " + k);
        return std::get<std::string>(it->second);
    }
    template <class T> const T &arr(const std::string &k) const {
        auto it = kv.find(k);
        if (it == kv.end()) throw std::runtime_error("gguf: missing key " + k);
        return std::get<T>(it->second);
    }

    void read_at(void *dst, size_t n, uint64_t off) const {
        uint8_t *d = (uint8_t *)dst;
        while (n) {
            ssize_t g = ::pread(fd, d, n, (off_t)off);
            if (g <= 0) throw std::runtime_error("gguf: read failed in " + path);
            d += g; n -= (size_t)g; off += (uint64_t)g;
        }
    }

  private:
    std::vector<uint8_t> hdr;
    size_t p = 0;
    void need(size_t n) {
        while (p + n > hdr.size()) { // grow the header buffer in 8 MiB steps
            size_t old = hdr.size(), add = (size_t)8 << 20;
            if (old >= file_size) throw std::runtime_error("gguf: truncated header");
            add = std::min<size_t>(add, file_size - old);
            hdr.resize(old + add);
            read_at(hdr.data() + old, add, old);
        }
    }
    template <class T> T rd() { need(sizeof(T)); T v; std::memcpy(&v, hdr.data() + p, sizeof(T)); p += sizeof(T); return v; }
    std::string rs() { uint64_t n = rd<uint64_t>(); need(n); std::string s((const char *)hdr.data() + p, n); p += n; return s; }
    int64_t rint(uint32_t t) {
        switch (t) {
        case 0: return rd<uint8_t>(); case 1: return rd<int8_t>(); case 2: return rd<uint16_t>(); case 3: return rd<int16_t>();
        case 4: return rd<uint32_t>(); case 5: return rd<int32_t>(); case 7: return rd<uint8_t>(); case 10: return (int64_t)rd<uint64_t>();
        case 11: return rd<int64_t>(); default: throw std::runtime_error("gguf: not an int type");
        }
    }
    Value rv(uint32_t t) {
        switch (t) {
        case 6: return (double)rd<float>();
        case 12: return rd<double>();
        case 7: return (bool)rd<uint8_t>();
        case 8: return rs();
        case 10: return rd<uint64_t>();
        case 9: {
            uint32_t at = rd<uint32_t>();
            uint64_t n = rd<uint64_t>();
            if (at == 8) { std::vector<std::string> v; v.reserve(n); for (uint64_t k = 0; k < n; ++k) v.push_back(rs()); return v; }
            if (at == 6 || at == 12) { std::vector<double> v; v.reserve(n); for (uint64_t k = 0; k < n; ++k) v.push_back(at == 6 ? rd<float>() : rd<double>()); return v; }
            std::vector<int64_t> v; v.reserve(n); for (uint64_t k = 0; k < n; ++k) v.push_back(rint(at)); return v;
        }
        default: return rint(t);
        }
    }
    void parse() {
        need(24);
        if (std::memcmp(hdr.data(), "GGUF", 4)) throw std::runtime_error("gguf: bad magic in " + path);
        p = 4;
        uint32_t ver = rd<uint32_t>();
        if (ver != 3) throw std::runtime_error("gguf: version " + std::to_string(ver) + " (need 3)");
        uint64_t nt = rd<uint64_t>(), nkv = rd<uint64_t>();
        for (uint64_t k = 0; k < nkv; ++k) { std::string key = rs(); uint32_t t = rd<uint32_t>(); kv[key] = rv(t); }
        if (has("general.alignment")) alignment = (uint32_t)i("general.alignment");
        tensors.resize(nt);
        for (uint64_t k = 0; k < nt; ++k) {
            Tensor &t = tensors[k];
            t.name = rs();
            uint32_t nd = rd<uint32_t>();
            if (nd < 1 || nd > 4) throw std::runtime_error("gguf: tensor with " + std::to_string(nd) + " dimensions");
            t.n_dims = (int)nd;
            t.ne.assign(4, 1); // always four entries, ggml style: unused dimensions are 1
            // dimensions and the element count checked before nel() / rows() / bytes use them: each dimension fits
            // int64_t, their product does too (no wrap), and so does the byte size
            int64_t nel = 1;
            for (uint32_t d = 0; d < nd; ++d) {
                const uint64_t v = rd<uint64_t>();
                if (v > (uint64_t)INT64_MAX) throw std::runtime_error("gguf: dimension does not fit int64: " + t.name);
                t.ne[d] = (int64_t)v;
                if (t.ne[d] != 0 && nel > INT64_MAX / t.ne[d]) throw std::runtime_error("gguf: element count overflows: " + t.name);
                nel *= t.ne[d];
            }
            t.type = rd<uint32_t>();
            t.off = rd<uint64_t>();
            int b, s; type_block(t.type, b, s);
            if (t.ne[0] % b) throw std::runtime_error("gguf: row not a whole number of blocks: " + t.name);
            if ((uint64_t)(nel / b) > UINT64_MAX / (uint64_t)s) throw std::runtime_error("gguf: byte size overflows: " + t.name);
            t.bytes = (uint64_t)(nel / b) * s;
            // one descriptor per name: lookups (find / at, the upload's slots, certify_half) go by name
            if (!index.emplace(t.name, k).second) throw std::runtime_error("gguf: duplicate tensor name " + t.name);
        }
        data_off = (p + alignment - 1) / alignment * alignment;
        for (auto &t : tensors) // (no wrap: each term checked against what is left of the file)
            if (data_off > file_size || t.off > file_size - data_off || t.bytes > file_size - data_off - t.off)
                throw std::runtime_error("gguf: tensor past end of file: " + t.name);
        hdr.clear(); hdr.shrink_to_fit();
    }
};

} // namespace ink
