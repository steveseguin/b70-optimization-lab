#include <pti/pti_view.h>
#include <llama.h>

#include <cerrno>
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <dlfcn.h>

namespace {

constexpr size_t kBufferBytes = 64u * 1024u * 1024u;
std::mutex output_mutex;
FILE * output_file = nullptr;
bool enabled = false;
bool stopped = false;
uint64_t decode_calls = 0;
uint64_t decode_limit = 0;

void json_string(FILE * file, const char * value) {
    std::fputc('"', file);
    if (value != nullptr) {
        for (const unsigned char * p = reinterpret_cast<const unsigned char *>(value); *p; ++p) {
            switch (*p) {
                case '"': std::fputs("\\\"", file); break;
                case '\\': std::fputs("\\\\", file); break;
                case '\n': std::fputs("\\n", file); break;
                case '\r': std::fputs("\\r", file); break;
                case '\t': std::fputs("\\t", file); break;
                default:
                    if (*p < 0x20) {
                        std::fprintf(file, "\\u%04x", unsigned(*p));
                    } else {
                        std::fputc(*p, file);
                    }
            }
        }
    }
    std::fputc('"', file);
}

void buffer_requested(unsigned char ** buffer, size_t * size) {
    void * storage = nullptr;
    if (posix_memalign(&storage, 64, kBufferBytes) != 0) {
        *buffer = nullptr;
        *size = 0;
        return;
    }
    *buffer = static_cast<unsigned char *>(storage);
    *size = kBufferBytes;
}

void write_kernel(const pti_view_record_kernel * record) {
    std::fputs("{\"kind\":\"kernel\",\"pci\":", output_file);
    json_string(output_file, record->_pci_address);
    std::fprintf(output_file,
        ",\"queue\":\"%p\",\"name\":", record->_queue_handle);
    json_string(output_file, record->_name);
    std::fprintf(output_file,
        ",\"append_ns\":%" PRIu64 ",\"submit_ns\":%" PRIu64
        ",\"start_ns\":%" PRIu64 ",\"end_ns\":%" PRIu64 "}\n",
        record->_append_timestamp, record->_submit_timestamp,
        record->_start_timestamp, record->_end_timestamp);
}

void write_copy(const pti_view_record_memory_copy * record, const char * kind) {
    std::fputs("{\"kind\":", output_file);
    json_string(output_file, kind);
    std::fputs(",\"pci\":", output_file);
    json_string(output_file, record->_pci_address);
    std::fprintf(output_file,
        ",\"queue\":\"%p\",\"name\":", record->_queue_handle);
    json_string(output_file, record->_name);
    std::fprintf(output_file,
        ",\"bytes\":%" PRIu64 ",\"append_ns\":%" PRIu64
        ",\"submit_ns\":%" PRIu64 ",\"start_ns\":%" PRIu64
        ",\"end_ns\":%" PRIu64 "}\n",
        record->_bytes, record->_append_timestamp, record->_submit_timestamp,
        record->_start_timestamp, record->_end_timestamp);
}

void write_p2p(const pti_view_record_memory_copy_p2p * record) {
    std::fputs("{\"kind\":\"p2p\",\"src_pci\":", output_file);
    json_string(output_file, record->_src_pci_address);
    std::fputs(",\"dst_pci\":", output_file);
    json_string(output_file, record->_dst_pci_address);
    std::fprintf(output_file,
        ",\"queue\":\"%p\",\"name\":", record->_queue_handle);
    json_string(output_file, record->_name);
    std::fprintf(output_file,
        ",\"bytes\":%" PRIu64 ",\"append_ns\":%" PRIu64
        ",\"submit_ns\":%" PRIu64 ",\"start_ns\":%" PRIu64
        ",\"end_ns\":%" PRIu64 "}\n",
        record->_bytes, record->_append_timestamp, record->_submit_timestamp,
        record->_start_timestamp, record->_end_timestamp);
}

void write_fill(const pti_view_record_memory_fill * record) {
    std::fputs("{\"kind\":\"fill\",\"pci\":", output_file);
    json_string(output_file, record->_pci_address);
    std::fprintf(output_file,
        ",\"queue\":\"%p\",\"name\":", record->_queue_handle);
    json_string(output_file, record->_name);
    std::fprintf(output_file,
        ",\"bytes\":%" PRIu64 ",\"append_ns\":%" PRIu64
        ",\"submit_ns\":%" PRIu64 ",\"start_ns\":%" PRIu64
        ",\"end_ns\":%" PRIu64 "}\n",
        record->_bytes, record->_append_timestamp, record->_submit_timestamp,
        record->_start_timestamp, record->_end_timestamp);
}

void write_sync(const pti_view_record_synchronization * record) {
    std::fprintf(output_file,
        "{\"kind\":\"sync\",\"queue\":\"%p\",\"sync_type\":%u"
        ",\"start_ns\":%" PRIu64 ",\"end_ns\":%" PRIu64 "}\n",
        record->_queue_handle, unsigned(record->_synch_type),
        record->_start_timestamp, record->_end_timestamp);
}

void buffer_completed(unsigned char * buffer, size_t, size_t used) {
    if (buffer == nullptr) {
        return;
    }
    if (used != 0 && output_file != nullptr) {
        std::lock_guard<std::mutex> lock(output_mutex);
        pti_view_record_base * record = nullptr;
        while (ptiViewGetNextRecord(buffer, used, &record) == PTI_SUCCESS) {
            switch (record->_view_kind) {
                case PTI_VIEW_DEVICE_GPU_KERNEL:
                    write_kernel(reinterpret_cast<pti_view_record_kernel *>(record));
                    break;
                case PTI_VIEW_DEVICE_GPU_MEM_COPY:
                    write_copy(reinterpret_cast<pti_view_record_memory_copy *>(record), "copy");
                    break;
                case PTI_VIEW_DEVICE_GPU_MEM_COPY_P2P:
                    write_p2p(reinterpret_cast<pti_view_record_memory_copy_p2p *>(record));
                    break;
                case PTI_VIEW_DEVICE_GPU_MEM_FILL:
                    write_fill(reinterpret_cast<pti_view_record_memory_fill *>(record));
                    break;
                case PTI_VIEW_DEVICE_SYNCHRONIZATION:
                    write_sync(reinterpret_cast<pti_view_record_synchronization *>(record));
                    break;
                default:
                    break;
            }
        }
        std::fflush(output_file);
    }
    std::free(buffer);
}

pti_result enable(pti_view_kind kind) {
    const pti_result result = ptiViewEnable(kind);
    if (result != PTI_SUCCESS) {
        std::fprintf(stderr, "[muse-pti] enable kind=%u failed: %s\n",
            unsigned(kind), ptiResultTypeToString(result));
    }
    return result;
}

void start_views() {
    if (enabled || stopped || output_file == nullptr) {
        return;
    }
    enabled = enable(PTI_VIEW_DEVICE_GPU_KERNEL) == PTI_SUCCESS;
    enable(PTI_VIEW_DEVICE_GPU_MEM_COPY);
    enable(PTI_VIEW_DEVICE_GPU_MEM_COPY_P2P);
    enable(PTI_VIEW_DEVICE_GPU_MEM_FILL);
    enable(PTI_VIEW_DEVICE_SYNCHRONIZATION);
    std::fprintf(stderr, "[muse-pti] device views started\n");
}

void stop_views() {
    if (!enabled || stopped) {
        return;
    }
    const pti_result result = ptiFlushAllViews();
    if (result != PTI_SUCCESS) {
        std::fprintf(stderr, "[muse-pti] flush failed: %s\n", ptiResultTypeToString(result));
    }
    ptiViewDisable(PTI_VIEW_DEVICE_SYNCHRONIZATION);
    ptiViewDisable(PTI_VIEW_DEVICE_GPU_MEM_FILL);
    ptiViewDisable(PTI_VIEW_DEVICE_GPU_MEM_COPY_P2P);
    ptiViewDisable(PTI_VIEW_DEVICE_GPU_MEM_COPY);
    ptiViewDisable(PTI_VIEW_DEVICE_GPU_KERNEL);
    stopped = true;
    enabled = false;
    std::fprintf(stderr, "[muse-pti] device views stopped calls=%" PRIu64 "\n", decode_calls);
}

__attribute__((constructor)) void initialize() {
    const char * path = std::getenv("MUSE_PTI_OUTPUT");
    if (path == nullptr || path[0] == '\0') {
        return;
    }
    output_file = std::fopen(path, "w");
    if (output_file == nullptr) {
        std::fprintf(stderr, "[muse-pti] cannot open %s: %s\n", path, std::strerror(errno));
        return;
    }
    const pti_result callbacks = ptiViewSetCallbacks(buffer_requested, buffer_completed);
    if (callbacks != PTI_SUCCESS) {
        std::fprintf(stderr, "[muse-pti] callbacks failed: %s\n", ptiResultTypeToString(callbacks));
        std::fclose(output_file);
        output_file = nullptr;
        return;
    }
    const char * calls = std::getenv("MUSE_PTI_DECODE_CALLS");
    if (calls != nullptr && calls[0] != '\0') {
        decode_limit = std::strtoull(calls, nullptr, 10);
    }
    if (decode_limit != 0) {
        // Do not enable any view here. Even a brief enable/disable activates
        // the Level Zero collector for model-loading copies on this runtime.
        // The interposer starts all views on the first decode instead.
        std::fprintf(stderr, "[muse-pti] armed output=%s decode_calls=%" PRIu64 "\n",
            path, decode_limit);
    } else {
        enabled = enable(PTI_VIEW_DEVICE_GPU_KERNEL) == PTI_SUCCESS;
        enable(PTI_VIEW_DEVICE_GPU_MEM_COPY);
        enable(PTI_VIEW_DEVICE_GPU_MEM_COPY_P2P);
        enable(PTI_VIEW_DEVICE_GPU_MEM_FILL);
        enable(PTI_VIEW_DEVICE_SYNCHRONIZATION);
        std::fprintf(stderr, "[muse-pti] enabled output=%s\n", path);
    }
}

__attribute__((destructor)) void finalize() {
    if (output_file == nullptr) {
        return;
    }
    stop_views();
    std::lock_guard<std::mutex> lock(output_mutex);
    std::fflush(output_file);
    std::fclose(output_file);
    output_file = nullptr;
}

} // namespace

extern "C" int32_t llama_decode(struct llama_context * ctx, struct llama_batch batch) {
    using decode_fn = int32_t (*)(struct llama_context *, struct llama_batch);
    using synchronize_fn = void (*)(struct llama_context *);
    static auto real_decode = reinterpret_cast<decode_fn>(dlsym(RTLD_NEXT, "llama_decode"));
    static auto real_synchronize = reinterpret_cast<synchronize_fn>(dlsym(RTLD_NEXT, "llama_synchronize"));
    if (real_decode == nullptr || real_synchronize == nullptr) {
        std::fprintf(stderr, "[muse-pti] failed to resolve llama decode/synchronize\n");
        std::abort();
    }
    if (decode_limit != 0 && decode_calls < decode_limit) {
        start_views();
    }
    const int32_t result = real_decode(ctx, batch);
    if (decode_limit != 0 && decode_calls < decode_limit) {
        real_synchronize(ctx);
        ++decode_calls;
        if (decode_calls == decode_limit) {
            stop_views();
        }
    }
    return result;
}
