// ink_load: list the GPUs, or upload a whole GGUF to one card and report time and card memory.
//   ink_load --list
//   ink_load <model.gguf> <card>
#include "../src/device.hpp"
#include <cstdio>

int main(int argc, char **argv) {
    using namespace ink;
    if (argc >= 2 && std::string(argv[1]) == "--list") {
        auto all = cards();
        for (size_t i = 0; i < all.size(); ++i) {
            std::string pci = all[i].has(sycl::aspect::ext_intel_pci_address)
                                  ? all[i].get_info<sycl::ext::intel::info::device::pci_address>() : "?";
            size_t fr = all[i].has(sycl::aspect::ext_intel_free_memory)
                            ? all[i].get_info<sycl::ext::intel::info::device::free_memory>() : 0;
            std::printf("card %zu  %s  %s  total %.2f GB  free %.2f GB\n", i, pci.c_str(),
                        all[i].get_info<sycl::info::device::name>().c_str(),
                        all[i].get_info<sycl::info::device::global_mem_size>() / 1e9, fr / 1e9);
        }
        return 0;
    }
    if (argc < 3) { std::fprintf(stderr, "usage: ink_load --list | ink_load <model.gguf> <card>\n"); return 2; }
    try {
        GGUF g(argv[1]);
        Device d(std::atoi(argv[2]));
        std::printf("card %d %s %s: %zu tensors, data at %llu, free before %.2f GB\n", d.index, d.pci.c_str(),
                    d.name().c_str(), g.tensors.size(), (unsigned long long)g.data_off, d.free_mem() / 1e9);
        Weights w;
        w.upload(d, g);
        std::printf("uploaded %.2f GB in %.1f s; free after %.2f GB\n", w.bytes / 1e9, w.seconds, d.free_mem() / 1e9);
        // spot check: the first 64 bytes of the last tensor read back equal the file
        const Tensor &t = g.tensors.back();
        uint8_t a[64], b[64];
        size_t n = std::min<size_t>(64, t.bytes);
        d.get(a, w[t.name], n);
        g.read_at(b, n, g.data_off + t.off);
        std::printf("read-back of %s: %s\n", t.name.c_str(), std::memcmp(a, b, n) ? "DIFFERENT" : "same");
    } catch (std::exception &e) {
        std::fprintf(stderr, "error: %s\n", e.what());
        return 1;
    }
    return 0;
}
