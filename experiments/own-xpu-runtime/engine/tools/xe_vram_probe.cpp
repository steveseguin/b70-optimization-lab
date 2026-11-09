// icpx -fsycl -O2 -std=c++20 tools/xe_vram_probe.cpp -o xe_vram_probe
// LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
//   ./xe_vram_probe list
//   ./xe_vram_probe alloc <pci e.g. 0000:43:00.0> <single|shared> <step MiB> <total MiB> <MemAvailable floor MiB> [touch]
// Results that shaped the loader: notes/2026-11-09-dsv41-device-load-host-memory.md.
//
// Safe device-memory probe: allocates in steps on ONE card, watches host
// MemAvailable and this process's per-card fdinfo, and stops itself before
// the host gets low. Never "allocate until failure" (xe spills VRAM overflow
// into host RAM instead of failing).
#include <sycl/sycl.hpp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <fstream>
#include <map>
#include <string>
#include <vector>
#include <chrono>

static long meminfo_kb(const char *key) {
    std::ifstream f("/proc/meminfo");
    std::string k; long v; std::string unit;
    while (f >> k >> v) { std::getline(f, unit); if (k == std::string(key) + ":") return v; }
    return -1;
}
struct CardUse { long vram_kb = 0, sys_kb = 0; };
static std::map<std::string, CardUse> fdinfo_self() {
    std::map<std::string, CardUse> out;
    std::map<std::string, bool> seen_client;
    DIR *d = opendir("/proc/self/fdinfo");
    if (!d) return out;
    while (auto *e = readdir(d)) {
        if (e->d_name[0] == '.') continue;
        std::ifstream f(std::string("/proc/self/fdinfo/") + e->d_name);
        std::string line, pdev, client; long vram = 0, sys = 0; bool drm = false;
        while (std::getline(f, line)) {
            if (line.rfind("drm-driver:", 0) == 0) drm = true;
            else if (line.rfind("drm-pdev:", 0) == 0) pdev = line.substr(line.find('\t') + 1);
            else if (line.rfind("drm-client-id:", 0) == 0) client = line.substr(line.find('\t') + 1);
            else if (line.rfind("drm-total-vram0:", 0) == 0) vram = atol(line.c_str() + line.find('\t') + 1);
            else if (line.rfind("drm-total-system:", 0) == 0) sys = atol(line.c_str() + line.find('\t') + 1);
        }
        if (!drm || seen_client[pdev + "/" + client]) continue;
        seen_client[pdev + "/" + client] = true;
        out[pdev].vram_kb += vram; out[pdev].sys_kb += sys;
    }
    closedir(d);
    return out;
}
static std::string pci_of(const sycl::device &d) {
    if (!d.has(sycl::aspect::ext_intel_pci_address)) return "?";
    return d.get_info<sycl::ext::intel::info::device::pci_address>();
}

int main(int argc, char **argv) {
    // usage: vram_probe list | alloc <pci> <single|shared> <step_mib> <total_mib> <floor_avail_mib> [touch]
    auto devs = sycl::device::get_devices(sycl::info::device_type::gpu);
    std::string cmd = argc > 1 ? argv[1] : "list";
    if (cmd == "list") {
        for (size_t i = 0; i < devs.size(); ++i) {
            auto &d = devs[i];
            std::printf("dev %zu pci=%s name=%s global=%.2fGiB max_alloc=%.2fGiB", i, pci_of(d).c_str(),
                        d.get_info<sycl::info::device::name>().c_str(),
                        d.get_info<sycl::info::device::global_mem_size>() / 1073741824.0,
                        d.get_info<sycl::info::device::max_mem_alloc_size>() / 1073741824.0);
            if (d.has(sycl::aspect::ext_intel_free_memory))
                std::printf(" free=%.2fGiB", d.get_info<sycl::ext::intel::info::device::free_memory>() / 1073741824.0);
            std::printf("\n");
        }
        return 0;
    }
    if (argc < 7) { std::fprintf(stderr, "usage\n"); return 2; }
    std::string pci = argv[2], mode = argv[3];
    size_t step = (size_t)atol(argv[4]) << 20, total = (size_t)atol(argv[5]) << 20;
    long floor_kb = atol(argv[6]) * 1024;
    bool touch = argc > 7;
    int idx = -1;
    for (size_t i = 0; i < devs.size(); ++i) if (pci_of(devs[i]) == pci) idx = (int)i;
    if (idx < 0) { std::fprintf(stderr, "pci %s not visible\n", pci.c_str()); return 2; }
    sycl::context ctx = mode == "shared" ? sycl::context(devs) : sycl::context(devs[idx]);
    sycl::queue q(ctx, devs[idx], sycl::property::queue::in_order{});
    std::fprintf(stderr, "mode=%s devices_in_ctx=%zu target=%s step=%zuMiB total=%zuMiB floor=%ldMiB touch=%d\n",
                 mode.c_str(), ctx.get_devices().size(), pci.c_str(), step >> 20, total >> 20, floor_kb / 1024, touch);
    long avail0 = meminfo_kb("MemAvailable");
    std::vector<void *> ps;
    size_t done = 0;
    auto report = [&](const char *tag) {
        auto u = fdinfo_self();
        std::fprintf(stderr, "%s alloc=%.2fGiB avail=%ldMiB (d%+ldMiB) card_vram=%.2fGiB card_sys=%ldMiB\n", tag,
                     done / 1073741824.0, meminfo_kb("MemAvailable") / 1024,
                     (meminfo_kb("MemAvailable") - avail0) / 1024, u[pci].vram_kb / 1048576.0, u[pci].sys_kb / 1024);
        std::fflush(stderr);
    };
    report("start");
    int rc = 0;
    while (done < total) {
        if (meminfo_kb("MemAvailable") < floor_kb) { std::fprintf(stderr, "STOP: host MemAvailable below floor\n"); rc = 3; break; }
        auto t0 = std::chrono::steady_clock::now();
        void *p = sycl::malloc_device(step, q);
        double dt = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        if (!p) { std::fprintf(stderr, "malloc_device returned null at %.2fGiB (%.2fs)\n", done / 1073741824.0, dt); rc = 4; break; }
        ps.push_back(p); done += step;
        if (touch) q.memset(p, 0, step).wait();
        if (dt > 1.0) std::fprintf(stderr, "  slow alloc %.2fs\n", dt);
        report("  step");
    }
    report("end");
    for (void *p : ps) sycl::free(p, ctx);
    done = 0;
    report("freed");
    return rc;
}
