// dump.hpp: INK_DUMP=<dir> saves named intermediate tensors in the layout of tools/ref_dump.cpp (float32, ggml
// order, index.tsv) so tools/compare_dumps.py can line them up with the reference. INK_DUMP_ONLY=<p1,p2,...> limits
// it to names starting with one of the prefixes. Dumping waits for the queue: never on for speed runs.
#pragma once
#include "device.hpp"
#include <cstdio>
#include <fstream>

namespace ink {

struct Dumper {
    std::string dir;
    std::vector<std::string> only;
    FILE *index = nullptr;
    explicit Dumper() {
        if (const char *e = std::getenv("INK_DUMP")) {
            dir = e;
            index = std::fopen((dir + "/index.tsv").c_str(), "w");
            if (!index) throw std::runtime_error("dump: cannot write " + dir);
            if (const char *o = std::getenv("INK_DUMP_ONLY")) {
                std::string s = o;
                for (size_t a = 0, b; a <= s.size(); a = b + 1) {
                    b = s.find(',', a);
                    if (b == std::string::npos) b = s.size();
                    if (b > a) only.push_back(s.substr(a, b - a));
                }
            }
        }
    }
    ~Dumper() { if (index) std::fclose(index); }
    bool on() const { return index != nullptr; }
    bool want(const std::string &name) const {
        if (!index) return false;
        if (only.empty()) return true;
        for (auto &p : only) if (name.compare(0, p.size(), p) == 0) return true;
        return false;
    }
    // ne: ggml order, ne0 contiguous
    void put(Device &d, const std::string &name, const float *dev, int64_t ne0, int64_t ne1 = 1, int64_t ne2 = 1, int64_t ne3 = 1) {
        if (!want(name)) return;
        size_t n = (size_t)(ne0 * ne1 * ne2 * ne3);
        std::vector<float> h(n);
        d.q.wait();
        d.get(h.data(), dev, n);
        std::ofstream o(dir + "/" + name + ".f32", std::ios::binary);
        o.write((const char *)h.data(), n * 4);
        std::fprintf(index, "%s\tf32\t%lld\t%lld\t%lld\t%lld\n", name.c_str(), (long long)ne0, (long long)ne1, (long long)ne2, (long long)ne3);
        std::fflush(index);
    }
};

} // namespace ink
