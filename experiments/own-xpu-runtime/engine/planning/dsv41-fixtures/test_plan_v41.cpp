// Plan gate: build the v41 decode plan from the REAL backbone directory
// (data/dsv41-directory.tsv). Verifies: geometry derives, every directory
// tensor is consumed by the plan, buffer/op structure is sane, and the
// shared-cache references (compress_kv/topk_idxs) point at their
// publisher layers. Prints an op census.
#include <cstdio>
#include <iostream>
#include <map>
#include "stage2/packet3/step/plan_v41.hpp"

int main() {
    flash::Directory d = flash::read_directory(std::cin);
    flash41::Plan41 p = flash41::model_plan_v41(d);
    std::map<std::string, int> ops;
    for (const auto &l : p.launches) ops[l.op]++;
    std::fprintf(stderr, "launches=%zu buffers=%zu\n", p.launches.size(),
                 p.buffers.size());
    for (const auto &[op, n] : ops)
        std::fprintf(stderr, "  %-16s %d\n", op.c_str(), n);
    // structural assertions
    if (ops["hc_mix41"] != 80) return 1;          // attn+ffn per layer
    if (ops["sparse_attn41"] != 40) return 1;
    if (ops["route41"] != 40) return 1;
    if (ops["compress41"] != 4) return 1;         // kv sources 2,8,14,20
    if (ops["index41"] != 8) return 1;            // index sources
    if (ops["engram_gate"] != 2) return 1;        // layers 1,14
    if (ops["hc_mean"] != 3) return 1;            // MTP captures 37,38,39
    // shared-cache reference check: blk.3 sparse_attn must read blk.2's
    for (const auto &l : p.launches)
        if (l.op == "sparse_attn41" && l.label == "blk.3.attention") {
            bool ok = false;
            for (const auto &i : l.inputs)
                ok |= i == "blk.2.attn.compress_kv";
            if (!ok) { std::fprintf(stderr, "blk.3 not reading blk.2 cache\n"); return 1; }
        }
    std::printf("FIXTURE_PASS plan_v41\n");
    return 0;
}
