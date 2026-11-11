// GPU stall sampling (PTI PC sampling = EU stall sampling) around a region of a bench, printed per kernel as the
// share of samples per stall reason, plus the instructions with the most samples. One session per process:
// pcs::begin() before the first queue (sets ZET_ENABLE_METRICS=1), pcs::start() / pcs::stop_print() once.
// Needs CAP_PERFMON or root while /proc/sys/dev/xe/observation_paranoid is 1 (run the bench with sudo; nothing
// is changed on the host). Link: -I /opt/intel/oneapi/pti/latest/include -L /opt/intel/oneapi/pti/latest/lib -lpti_view
#pragma once
#include <pti/pti_pc_sampling.h>
#include <pti/pti_view.h>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace pcs {
inline pti_pc_sampling_handle_t g_h = nullptr;
inline bool g_on = false;
// PC sampling subscribes to kernel callbacks, which need a GPU view on (PTI_ERROR_NO_GPU_VIEWS_ENABLED otherwise):
// the kernel view runs with throw-away buffers
inline void buf_req(unsigned char **b, size_t *n) {
    *n = (size_t)1 << 20;
    *b = static_cast<unsigned char *>(std::aligned_alloc(8, *n));
}
inline void buf_done(unsigned char *b, size_t, size_t) { std::free(b); }
inline bool begin(uint32_t period_ns = 0) {
    setenv("ZET_ENABLE_METRICS", "1", 1);
    if (ptiViewSetCallbacks(buf_req, buf_done) != PTI_SUCCESS || ptiViewEnable(PTI_VIEW_DEVICE_GPU_KERNEL) != PTI_SUCCESS) {
        std::printf("pcs: kernel view failed\n");
        return false;
    }
    pti_result r = ptiPcSamplingEnable(&g_h);
    if (r != PTI_SUCCESS) { std::printf("pcs: enable failed (%d)\n", (int)r); return false; }
    r = ptiPcSamplingConfigure(g_h, nullptr, 0, period_ns);
    if (r != PTI_SUCCESS) { std::printf("pcs: configure failed (%d)\n", (int)r); return false; }
    g_on = true;
    return true;
}
inline void start() {
    if (!g_on) return;
    pti_result r = ptiPcSamplingStartCollection(g_h);
    if (r != PTI_SUCCESS) { std::printf("pcs: start failed (%d)\n", (int)r); g_on = false; }
}
// kernel names are shortened to the text after `key` (when found) and cut at `width` characters
inline void stop_print(const char *key = nullptr, unsigned width = 110, unsigned top_instr = 12) {
    if (!g_on) return;
    if (ptiPcSamplingStopCollection(g_h) != PTI_SUCCESS) { std::printf("pcs: stop failed\n"); return; }
    ptiViewDisable(PTI_VIEW_DEVICE_GPU_KERNEL);
    ptiFlushAllViews();
    size_t nr = 0;
    ptiPcSamplingGetStallReasons(g_h, nullptr, &nr);
    std::vector<pti_pc_sampling_stall_reason_info_t> rs(nr);
    for (auto &x : rs) x._struct_size = sizeof x;
    ptiPcSamplingGetStallReasons(g_h, rs.data(), &nr);
    size_t nd = 0;
    ptiPcSamplingGetProfiledDevices(g_h, nullptr, &nd);
    std::vector<pti_device_handle_t> ds(nd);
    ptiPcSamplingGetProfiledDevices(g_h, ds.data(), &nd);
    std::printf("pcs: %zu stall reasons:", nr);
    for (auto &x : rs) std::printf(" %s", x._name);
    std::printf("\n");
    for (auto d : ds) {
        pti_pc_sampling_device_status_t st{};
        st._struct_size = sizeof st;
        ptiPcSamplingGetDeviceStatus(g_h, d, &st);
        std::printf("pcs: device samples %llu, pcs %llu, dropped %u\n", (unsigned long long)st._total_sample_count,
                    (unsigned long long)st._total_pc_count, st._samples_dropped);
        size_t nk = 0;
        ptiPcSamplingGetObservedKernelHandles(g_h, d, nullptr, &nk);
        std::vector<uint64_t> ks(nk);
        ptiPcSamplingGetObservedKernelHandles(g_h, d, ks.data(), &nk);
        for (uint64_t k : ks) {
            std::vector<uint64_t> agg(nr, 0);
            pti_pc_sampling_kernel_info_t ki{};
            ki._struct_size = sizeof ki;
            ki._aggregated_samples = agg.data();
            if (ptiPcSamplingGetObservedKernelInfo(g_h, d, k, &ki) != PTI_SUCCESS) continue;
            uint64_t tot = 0;
            for (size_t j = 0; j < nr; ++j) tot += agg[j];
            if (!tot) continue;
            std::string nm = ki._kernel_name ? ki._kernel_name : "?";
            if (key) {
                const size_t p = nm.find(key);
                if (p != std::string::npos) nm = nm.substr(p);
            }
            if (nm.size() > width) nm.resize(width);
            std::printf("\nkernel %s\n  samples %llu:", nm.c_str(), (unsigned long long)tot);
            std::vector<size_t> ord(nr);
            for (size_t j = 0; j < nr; ++j) ord[j] = j;
            std::sort(ord.begin(), ord.end(), [&](size_t a, size_t b) { return agg[a] > agg[b]; });
            for (size_t j : ord)
                if (agg[j]) std::printf(" %s %.1f%%", rs[j]._name, 100.0 * agg[j] / tot);
            std::printf("\n");
            const size_t ni = ki._instructions_with_samples_count;
            if (!ni || !top_instr) continue;
            std::vector<pti_pc_sampling_instruction_t> in(ni);
            std::vector<uint64_t> sm(ni * nr);
            if (ptiPcSamplingGetSamplesPerInstruction(g_h, d, k, in.data(), ni, sm.data(), sm.size()) != PTI_SUCCESS) continue;
            std::vector<size_t> io(ni);
            std::vector<uint64_t> it(ni, 0);
            for (size_t i = 0; i < ni; ++i) {
                io[i] = i;
                for (size_t j = 0; j < nr; ++j) it[i] += sm[i * nr + j];
            }
            std::sort(io.begin(), io.end(), [&](size_t a, size_t b) { return it[a] > it[b]; });
            for (size_t q = 0; q < std::min<size_t>(top_instr, ni); ++q) {
                const size_t i = io[q];
                std::printf("    +0x%05llx %5.1f%% |", (unsigned long long)in[i]._instruction_offset, 100.0 * it[i] / tot);
                for (size_t j : ord)
                    if (sm[i * nr + j]) std::printf(" %s %llu", rs[j]._name, (unsigned long long)sm[i * nr + j]);
                std::printf("\n");
            }
        }
    }
    ptiPcSamplingDisable(g_h);
    g_on = false;
}
} // namespace pcs
