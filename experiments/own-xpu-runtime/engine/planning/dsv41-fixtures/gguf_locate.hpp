// Shared GGUF tensor locator for the dsv41 dequant fixtures.
// Walks the header, returns a pointer to the first tensor of `type_id`
// (data section aligned to 32, GGUF default) plus its element count.
// Read-only; caller owns the mapping.
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

namespace dsv41fix {

inline const uint8_t *find_first_of_type(const uint8_t *base, size_t len,
                                         uint32_t type_id, uint32_t block_elems,
                                         uint32_t block_bytes, long long *out_blocks) {
    auto rd = [&](auto &v, const uint8_t *&p) { std::memcpy(&v, p, sizeof v); p += sizeof v; };
    const uint8_t *p = base + 4;  // magic checked by caller
    uint32_t ver; rd(ver, p);
    uint64_t nt, nkv; rd(nt, p); rd(nkv, p);
    static const int tsz[13] = {1,1,2,2,4,4,4,1,-1,-1,8,8,8};
    for (uint64_t i = 0; i < nkv; ++i) {
        uint64_t kl; rd(kl, p); p += kl;
        uint32_t t; rd(t, p);
        if (t == 8) { uint64_t n; rd(n, p); p += n; }
        else if (t == 9) {
            uint32_t et; rd(et, p); uint64_t n; rd(n, p);
            if (et == 8) for (uint64_t j = 0; j < n; ++j) { uint64_t m; rd(m, p); p += m; }
            else p += n * tsz[et];
        } else p += tsz[t];
    }
    // Pass 1: walk ALL tensor infos; the data section starts (align 32) only
    // after the last info. Record the match's relative offset, keep walking.
    uint64_t match_off = 0, match_elems = 0;
    bool found = false;
    for (uint64_t i = 0; i < nt; ++i) {
        uint64_t nl; rd(nl, p);
        std::string name((const char *)p, nl); p += nl;
        uint32_t nd; rd(nd, p);
        uint64_t elems = 1;
        for (uint32_t d = 0; d < nd; ++d) { uint64_t v; rd(v, p); elems *= v; }
        uint32_t type; rd(type, p);
        uint64_t off; rd(off, p);
        if (!found && type == type_id) {
            if (elems % block_elems) { std::fprintf(stderr, "odd elems\n"); return nullptr; }
            std::printf("real tensor: %s (%llu elems)\n", name.c_str(), (unsigned long long)elems);
            match_off = off; match_elems = elems; found = true;
        }
    }
    if (!found) return nullptr;
    size_t data = ((size_t)(p - base) + 31) & ~31ull;
    size_t bytes = match_elems / block_elems * block_bytes;
    if (data + match_off + bytes > len) { std::fprintf(stderr, "bounds\n"); return nullptr; }
    *out_blocks = (long long)(match_elems / block_elems);
    return base + data + match_off;
}

} // namespace dsv41fix
