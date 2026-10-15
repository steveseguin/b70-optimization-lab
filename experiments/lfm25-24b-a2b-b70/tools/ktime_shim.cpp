// Per-kernel GPU time via Intel PTI (LD_PRELOAD shim). Aggregates device time per kernel name and the idle gap
// between consecutive kernels on the same queue (gaps over KT_MAX_GAP_US, default 200 us, are host-side idle and
// skipped). Writes KT_OUT (TSV: name, count, total_ns, gap_before_ns) after every completed buffer and at exit.
// Tracing starts when the program first calls llama_init_from_model (after the model upload, which PTI slows to a
// crawl), so llama-bench's warm-up and timed runs are covered and the load is not.
//   g++ -O2 -shared -fPIC ktime_shim.cpp -I$PTI/include -I$LLAMA/include -I$LLAMA/ggml/include -L$PTI/lib -lpti_view -ldl -o libktime.so
//   ZE_ENABLE_TRACING_LAYER=1 KT_OUT=out.tsv LD_PRELOAD=./libktime.so llama-bench ...
#include <dlfcn.h>
#include <llama.h>
#include <pti/pti_view.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <mutex>
#include <string>

namespace {
struct agg { uint64_t n = 0, ns = 0, gap_ns = 0; };
std::mutex mu;
std::map<std::string, agg> totals;
std::map<const void *, uint64_t> last_end;  // per queue
uint64_t max_gap_ns = 200000;
const char * out_path = nullptr;
const size_t kbuf = 4 << 20;

void write_out() {
    if (out_path == nullptr) return;
    std::string tmp = std::string(out_path) + ".tmp";
    FILE * f = std::fopen(tmp.c_str(), "w");
    if (!f) return;
    for (const auto & kv : totals) {
        std::fprintf(f, "%s\t%llu\t%llu\t%llu\n", kv.first.c_str(), (unsigned long long) kv.second.n,
                (unsigned long long) kv.second.ns, (unsigned long long) kv.second.gap_ns);
    }
    std::fclose(f);
    std::rename(tmp.c_str(), out_path);
}

void requested(unsigned char ** buf, size_t * size) {
    *buf = static_cast<unsigned char *>(std::aligned_alloc(8, kbuf));
    *size = kbuf;
}

void completed(unsigned char * buf, size_t size, size_t used) {
    (void) size;
    std::lock_guard<std::mutex> lock(mu);
    pti_view_record_base * rec = nullptr;
    while (used > 0) {
        if (ptiViewGetNextRecord(buf, used, &rec) != PTI_SUCCESS || rec == nullptr) break;
        if (rec->_view_kind == PTI_VIEW_DEVICE_GPU_KERNEL) {
            auto * k = reinterpret_cast<pti_view_record_kernel *>(rec);
            agg & a = totals[k->_name ? k->_name : "?"];
            a.n++;
            a.ns += k->_end_timestamp - k->_start_timestamp;
            auto it = last_end.find(k->_queue_handle);
            if (it != last_end.end() && k->_start_timestamp > it->second &&
                    k->_start_timestamp - it->second < max_gap_ns) {
                a.gap_ns += k->_start_timestamp - it->second;
            }
            last_end[k->_queue_handle] = k->_end_timestamp;
        }
    }
    std::free(buf);
    write_out();
}

bool enabled = false;

void kt_enable() {
    if (enabled) return;
    enabled = true;
    out_path = std::getenv("KT_OUT");
    if (const char * g = std::getenv("KT_MAX_GAP_US")) max_gap_ns = std::strtoull(g, nullptr, 10) * 1000;
    if (ptiViewSetCallbacks(requested, completed) != PTI_SUCCESS ||
            ptiViewEnable(PTI_VIEW_DEVICE_GPU_KERNEL) != PTI_SUCCESS) {
        std::fprintf(stderr, "ktime: PTI init failed\n");
    } else {
        std::fprintf(stderr, "ktime: tracing on\n");
    }
}

__attribute__((destructor)) void kt_fini() {
    if (!enabled) return;
    ptiViewDisable(PTI_VIEW_DEVICE_GPU_KERNEL);
    ptiFlushAllViews();
    std::lock_guard<std::mutex> lock(mu);
    write_out();
}
}  // namespace

// interposed (LD_PRELOAD): switch tracing on, then call the real function
extern "C" llama_context * llama_init_from_model(llama_model * model, llama_context_params params) {
    kt_enable();
    using fn_t = llama_context * (*)(llama_model *, llama_context_params);
    static fn_t real = reinterpret_cast<fn_t>(dlsym(RTLD_NEXT, "llama_init_from_model"));
    return real(model, params);
}
