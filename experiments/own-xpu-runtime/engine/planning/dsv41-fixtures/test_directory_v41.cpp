// Directory gate: geometry_v41_from_directory on the REAL dsv41 backbone
// directory (dumped from the sha256-verified GGUF shard headers by
// dump_directory.py) must derive exactly the admitted DeepSeek V4.1 Flash
// geometry; a tampered directory must be rejected.
#include <cstdio>
#include <iostream>
#include "stage2/packet3/model/directory_v41.hpp"

int main() {
    flash::Directory d = flash::read_directory(std::cin);
    std::fprintf(stderr, "directory: %zu tensors\n", d.size());
    flash41::GeometryV41 g = flash41::geometry_v41_from_directory(d);
    std::printf("h=%d vocab=%d layers=%d experts=%d mid=%d qrank=%d qh=%d hd=%d "
                "krank=%d ototal=%d oin=%d hcs=%d hcw=%d engram=%llux%d\n",
                g.h, g.vocab, g.layers, g.experts, g.mid, g.qrank, g.qh, g.hd,
                g.krank, g.ototal, g.oin, g.hcs, g.hcw,
                (unsigned long long)g.engram_rows, g.engram_dim);
    // tamper: a wrong vocab must fail the gate
    flash::Directory bad = d;
    flash::Tensor t = bad["token_embd.weight"];
    t.shape[0] += 1;
    bad.erase("token_embd.weight");
    bad.emplace(t.name, t);
    try {
        (void)flash41::geometry_v41_from_directory(bad);
        std::fprintf(stderr, "FAIL: tampered directory accepted\n");
        return 1;
    } catch (const std::invalid_argument &) {
    }
    std::printf("FIXTURE_PASS directory_v41\n");
    return 0;
}
