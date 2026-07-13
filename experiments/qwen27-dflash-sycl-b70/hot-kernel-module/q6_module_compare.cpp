#include "q27_xe2_module.h"
#include "q6_m6_top1_module.h"

#include "ggml-sycl/common.hpp"
#include "ggml-sycl/mmvq.hpp"

#include <sycl/sycl.hpp>

#include <dlfcn.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef Q27_XE2_TOOLCHAIN_ABI
#define Q27_XE2_TOOLCHAIN_ABI "oneapi-2026.0-sycl-cxx17"
#endif

namespace {

constexpr int k = q27_q6_m6_top1_workspace::k;
constexpr int n = q27_q6_m6_top1_workspace::n;
constexpr int useful_rows = q27_q6_m6_top1_workspace::rows;
constexpr int fixture_rows = 6;
constexpr int qk = 256;
constexpr size_t model_data_offset = 10994816;
constexpr size_t quant_bytes = size_t(k) * n;
constexpr size_t scale_bytes = size_t(k / 16) * n;
constexpr size_t d_bytes = size_t(k / qk) * n * sizeof(uint16_t);
constexpr size_t packed_bytes = quant_bytes + scale_bytes + d_bytes;

struct top1_pair {
    float value;
    int32_t id;
};

struct fixture_header {
    char magic[8];
    uint32_t version;
    uint32_t k;
    uint32_t n;
    uint32_t m;
    top1_pair reference[useful_rows];
    int32_t sampled[useful_rows];
};

static_assert(sizeof(fixture_header) == 84);

struct q6_block_file {
    uint8_t ql[qk / 2];
    uint8_t qh[qk / 4];
    int8_t scales[qk / 16];
    uint16_t d;
};

static_assert(sizeof(q6_block_file) == 210);

struct pack_cache_header {
    char magic[8];
    uint32_t version;
    uint32_t k;
    uint32_t n;
    uint32_t reserved0;
    uint64_t data_bytes;
    uint64_t layout_id;
    uint64_t content_tag;
    uint64_t model_offset;
    uint64_t source_bytes;
};

static_assert(sizeof(pack_cache_header) == 64);

class mapped_file {
public:
    explicit mapped_file(const std::string &path) {
        fd_ = open(path.c_str(), O_RDONLY);
        if (fd_ < 0) {
            throw std::runtime_error("open failed: " + path);
        }
        struct stat stat_buffer {};
        if (fstat(fd_, &stat_buffer) != 0 || stat_buffer.st_size <= 0) {
            throw std::runtime_error("fstat failed: " + path);
        }
        size_ = size_t(stat_buffer.st_size);
        void *mapping = mmap(nullptr, size_, PROT_READ, MAP_PRIVATE, fd_, 0);
        if (mapping == MAP_FAILED) {
            throw std::runtime_error("mmap failed: " + path);
        }
        data_ = static_cast<const uint8_t *>(mapping);
    }

    ~mapped_file() {
        if (data_ != nullptr) {
            munmap(const_cast<uint8_t *>(data_), size_);
        }
        if (fd_ >= 0) {
            close(fd_);
        }
    }

    const uint8_t *data() const { return data_; }
    size_t size() const { return size_; }

private:
    int fd_ = -1;
    size_t size_ = 0;
    const uint8_t *data_ = nullptr;
};

void write_all(int fd, const void *data, size_t bytes) {
    const auto *cursor = static_cast<const uint8_t *>(data);
    while (bytes > 0) {
        const ssize_t written = write(fd, cursor, std::min<size_t>(bytes, 64 * 1024 * 1024));
        if (written <= 0) {
            throw std::runtime_error("pack cache write failed");
        }
        cursor += written;
        bytes -= size_t(written);
    }
}

void expand_q6k(const q6_block_file *source, uint8_t *packed) {
    auto *quants = reinterpret_cast<int8_t *>(packed);
    auto *scales = reinterpret_cast<int8_t *>(packed + quant_bytes);
    auto *ds = reinterpret_cast<uint16_t *>(packed + quant_bytes + scale_bytes);
    constexpr int blocks_per_row = k / qk;
    for (int row = 0; row < n; ++row) {
        for (int ib = 0; ib < blocks_per_row; ++ib) {
            const q6_block_file &block = source[size_t(row) * blocks_per_row + ib];
            std::memcpy(scales + size_t(row) * (k / 16) + ib * 16, block.scales, 16);
            std::memcpy(ds + size_t(row) * blocks_per_row + ib, &block.d, sizeof(uint16_t));
            int8_t *dst = quants + size_t(row) * k + ib * qk;
            for (int half = 0; half < 2; ++half) {
                for (int lane = 0; lane < 32; ++lane) {
                    dst[half * 128 + lane] = int8_t(
                        (block.ql[half * 64 + lane] & 15) |
                        (((block.qh[half * 32 + lane] >> 0) & 3) << 4)) - 32;
                    dst[half * 128 + lane + 32] = int8_t(
                        (block.ql[half * 64 + lane + 32] & 15) |
                        (((block.qh[half * 32 + lane] >> 2) & 3) << 4)) - 32;
                    dst[half * 128 + lane + 64] = int8_t(
                        (block.ql[half * 64 + lane] >> 4) |
                        (((block.qh[half * 32 + lane] >> 4) & 3) << 4)) - 32;
                    dst[half * 128 + lane + 96] = int8_t(
                        (block.ql[half * 64 + lane + 32] >> 4) |
                        (((block.qh[half * 32 + lane] >> 6) & 3) << 4)) - 32;
                }
            }
        }
    }
}

bool valid_cache(const mapped_file &cache) {
    if (cache.size() != sizeof(pack_cache_header) + packed_bytes) {
        return false;
    }
    const auto *header = reinterpret_cast<const pack_cache_header *>(cache.data());
    return std::memcmp(header->magic, "Q6M6PK1", 8) == 0 && header->version == 1 &&
        header->k == k && header->n == n && header->data_bytes == packed_bytes &&
        header->layout_id == Q27_XE2_LAYOUT_Q6K_M6_TOP1_V1 &&
        header->content_tag == Q27_XE2_QWEN36_27B_Q4_MODEL_TAG &&
        header->model_offset == model_data_offset &&
        header->source_bytes == size_t(n) * (k / qk) * sizeof(q6_block_file);
}

std::unique_ptr<mapped_file> open_or_build_pack(
        const std::string &model_path,
        const std::string &cache_path,
        bool *cache_hit,
        double *prepare_s) {
    const auto begin = std::chrono::steady_clock::now();
    if (std::filesystem::exists(cache_path)) {
        auto cache = std::make_unique<mapped_file>(cache_path);
        if (!valid_cache(*cache)) {
            throw std::runtime_error("existing pack cache has wrong identity: " + cache_path);
        }
        *cache_hit = true;
        *prepare_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - begin).count();
        return cache;
    }

    mapped_file model(model_path);
    const size_t source_bytes = size_t(n) * (k / qk) * sizeof(q6_block_file);
    if (model.size() < model_data_offset + source_bytes) {
        throw std::runtime_error("model file is too small for output.weight");
    }
    std::vector<uint8_t> packed(packed_bytes);
    expand_q6k(reinterpret_cast<const q6_block_file *>(model.data() + model_data_offset), packed.data());

    std::filesystem::create_directories(std::filesystem::path(cache_path).parent_path());
    const std::string temporary = cache_path + ".tmp." + std::to_string(getpid());
    const int fd = open(temporary.c_str(), O_CREAT | O_EXCL | O_WRONLY, 0644);
    if (fd < 0) {
        throw std::runtime_error("could not create pack cache temporary file");
    }
    try {
        const pack_cache_header header = {
            {'Q', '6', 'M', '6', 'P', 'K', '1', '\0'},
            1, k, n, 0, packed_bytes, Q27_XE2_LAYOUT_Q6K_M6_TOP1_V1,
            Q27_XE2_QWEN36_27B_Q4_MODEL_TAG, model_data_offset, source_bytes,
        };
        write_all(fd, &header, sizeof(header));
        write_all(fd, packed.data(), packed.size());
        if (fsync(fd) != 0 || close(fd) != 0) {
            throw std::runtime_error("could not finalize pack cache");
        }
        if (rename(temporary.c_str(), cache_path.c_str()) != 0) {
            throw std::runtime_error("could not publish pack cache");
        }
    } catch (...) {
        close(fd);
        unlink(temporary.c_str());
        throw;
    }

    auto cache = std::make_unique<mapped_file>(cache_path);
    if (!valid_cache(*cache)) {
        throw std::runtime_error("new pack cache failed identity validation");
    }
    *cache_hit = false;
    *prepare_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - begin).count();
    return cache;
}

double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

template <typename Function>
double timed_call_us(sycl::queue &queue, Function &&function) {
    queue.wait_and_throw();
    const auto begin = std::chrono::steady_clock::now();
    function();
    queue.wait_and_throw();
    return std::chrono::duration<double, std::micro>(
        std::chrono::steady_clock::now() - begin).count();
}

template <typename Function>
double host_dispatch_us(sycl::queue &queue, Function &&function) {
    queue.wait_and_throw();
    const auto begin = std::chrono::steady_clock::now();
    function();
    const auto end = std::chrono::steady_clock::now();
    queue.wait_and_throw();
    return std::chrono::duration<double, std::micro>(end - begin).count();
}

} // namespace

int main(int argc, char **argv) try {
    if (argc < 5 || argc > 6) {
        std::cerr << "usage: " << argv[0] << " MODULE.so MODEL.gguf FIXTURE.bin PACK.cache [ITERS]\n";
        return 2;
    }
    const int iterations = argc == 6 ? std::stoi(argv[5]) : 9;

    void *module_handle = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (module_handle == nullptr) {
        throw std::runtime_error(dlerror());
    }
    auto getter = reinterpret_cast<q27_xe2_get_module_v1_fn>(
        dlsym(module_handle, Q27_XE2_GETTER_SYMBOL));
    if (getter == nullptr) {
        throw std::runtime_error(dlerror());
    }
    const q27_xe2_module_v1 *module = getter();
    if (module == nullptr || module->abi_magic != Q27_XE2_ABI_MAGIC ||
            module->abi_version != Q27_XE2_ABI_VERSION ||
            module->struct_size < sizeof(q27_xe2_module_v1) ||
            std::strcmp(module->toolchain_abi, Q27_XE2_TOOLCHAIN_ABI) != 0 ||
            (module->supported_ops & (UINT64_C(1) << Q27_XE2_OP_Q6K_M6_TOP1)) == 0) {
        throw std::runtime_error("Q6 module ABI validation failed");
    }

    mapped_file fixture_file(argv[3]);
    if (fixture_file.size() != sizeof(fixture_header) + size_t(fixture_rows) * k * sizeof(float)) {
        throw std::runtime_error("fixture size mismatch");
    }
    const auto *fixture = reinterpret_cast<const fixture_header *>(fixture_file.data());
    if (std::memcmp(fixture->magic, "DFLM6V1", 8) != 0 || fixture->version != 1 ||
            fixture->k != k || fixture->n != n || fixture->m != fixture_rows) {
        throw std::runtime_error("fixture identity mismatch");
    }
    const auto *host_activations = reinterpret_cast<const float *>(
        fixture_file.data() + sizeof(fixture_header));

    bool cache_hit = false;
    double pack_prepare_s = 0.0;
    auto pack_cache = open_or_build_pack(argv[2], argv[4], &cache_hit, &pack_prepare_s);
    const void *host_pack = pack_cache->data() + sizeof(pack_cache_header);

    ggml_backend_sycl_context context(0);
    sycl::queue &queue = *context.stream();
    auto allocate = [&](size_t bytes) {
        void *pointer = sycl::malloc_device(bytes, queue);
        if (pointer == nullptr) {
            throw std::bad_alloc();
        }
        return pointer;
    };

    void *device_pack = allocate(packed_bytes);
    auto *device_activations = static_cast<float *>(allocate(size_t(fixture_rows) * k * sizeof(float)));
    auto *integrated_ids = static_cast<int32_t *>(allocate(useful_rows * sizeof(int32_t)));
    auto *module_ids = static_cast<int32_t *>(allocate(useful_rows * sizeof(int32_t)));

    q27_xe2_workspace_v1 workspace_info{};
    const int32_t workspace_status = module->query_workspace(
        Q27_XE2_OP_Q6K_M6_TOP1, useful_rows, n, &workspace_info);
    if (workspace_status != Q27_XE2_OK ||
            workspace_info.bytes != q27_q6_m6_top1_workspace::bytes ||
            workspace_info.alignment != q27_q6_m6_top1_workspace::alignment) {
        throw std::runtime_error("Q6 module workspace contract mismatch");
    }
    void *module_workspace = allocate(workspace_info.bytes);

    const auto copy_begin = std::chrono::steady_clock::now();
    queue.memcpy(device_pack, host_pack, packed_bytes);
    queue.memcpy(device_activations, host_activations, size_t(fixture_rows) * k * sizeof(float));
    queue.wait_and_throw();
    const double device_copy_s = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - copy_begin).count();

    q27_xe2_pack_v1 pack{};
    pack.device_ptr = device_pack;
    pack.bytes = packed_bytes;
    pack.layout_id = Q27_XE2_LAYOUT_Q6K_M6_TOP1_V1;
    pack.content_tag = Q27_XE2_QWEN36_27B_Q4_MODEL_TAG;
    pack.role = Q27_XE2_PACK_TARGET_LM_HEAD;

    q27_xe2_launch_v1 launch{};
    launch.struct_size = sizeof(launch);
    launch.op = Q27_XE2_OP_Q6K_M6_TOP1;
    launch.flags = Q27_XE2_QUEUE_IS_IN_ORDER;
    launch.queue = &queue;
    launch.input0 = device_activations + k;
    launch.output0 = module_ids;
    launch.scratch = module_workspace;
    launch.scratch_bytes = workspace_info.bytes;
    launch.packs = &pack;
    launch.pack_count = 1;
    launch.rows = useful_rows;
    launch.cols = n;
    launch.stride = k;

    auto integrated_call = [&] {
        if (!ggml_sycl_mul_mat_q6_k_xe2_m6_top1(
                context, device_pack, packed_bytes, device_activations + k,
                integrated_ids, k, n, &queue)) {
            throw std::runtime_error("integrated Q6 dispatch declined");
        }
    };
    auto module_call = [&] {
        const int32_t status = module->launch(&launch);
        if (status != Q27_XE2_OK) {
            throw std::runtime_error("module Q6 dispatch status " + std::to_string(status));
        }
    };

    integrated_call();
    module_call();
    queue.wait_and_throw();

    std::vector<int32_t> host_integrated(useful_rows);
    std::vector<int32_t> host_module(useful_rows);
    queue.memcpy(host_integrated.data(), integrated_ids, useful_rows * sizeof(int32_t));
    queue.memcpy(host_module.data(), module_ids, useful_rows * sizeof(int32_t));
    queue.wait_and_throw();
    bool exact = true;
    for (int row = 0; row < useful_rows; ++row) {
        exact = exact && host_integrated[row] == host_module[row] &&
            host_module[row] == fixture->reference[row].id &&
            host_module[row] == fixture->sampled[row];
    }
    const std::vector<int32_t> fixture_integrated_ids = host_integrated;
    const std::vector<int32_t> fixture_module_ids = host_module;

    std::vector<float> zero_activations(size_t(useful_rows) * k, 0.0f);
    queue.memcpy(device_activations + k, zero_activations.data(),
                 zero_activations.size() * sizeof(float)).wait();
    integrated_call();
    module_call();
    queue.wait_and_throw();
    queue.memcpy(host_integrated.data(), integrated_ids, useful_rows * sizeof(int32_t));
    queue.memcpy(host_module.data(), module_ids, useful_rows * sizeof(int32_t));
    queue.wait_and_throw();
    bool tie_exact = true;
    for (int row = 0; row < useful_rows; ++row) {
        tie_exact = tie_exact && host_integrated[row] == 0 && host_module[row] == 0;
    }

    q27_xe2_pack_v1 invalid_pack = pack;
    invalid_pack.layout_id ^= 1;
    q27_xe2_launch_v1 invalid_launch = launch;
    invalid_launch.packs = &invalid_pack;
    const int32_t invalid_status = module->launch(&invalid_launch);
    const bool fallback_safe = invalid_status == Q27_XE2_BAD_LAYOUT;

    queue.memcpy(device_activations, host_activations, size_t(fixture_rows) * k * sizeof(float)).wait();
    integrated_call();
    module_call();
    queue.wait_and_throw();

    std::vector<double> integrated_wall_us;
    std::vector<double> module_wall_us;
    std::vector<double> integrated_host_us;
    std::vector<double> module_host_us;
    for (int iteration = 0; iteration < iterations; ++iteration) {
        if ((iteration & 1) == 0) {
            integrated_wall_us.push_back(timed_call_us(queue, integrated_call));
            module_wall_us.push_back(timed_call_us(queue, module_call));
        } else {
            module_wall_us.push_back(timed_call_us(queue, module_call));
            integrated_wall_us.push_back(timed_call_us(queue, integrated_call));
        }
        integrated_host_us.push_back(host_dispatch_us(queue, integrated_call));
        module_host_us.push_back(host_dispatch_us(queue, module_call));
    }

    const double integrated_median_us = median(integrated_wall_us);
    const double module_median_us = median(module_wall_us);
    const double integrated_dispatch_us = median(integrated_host_us);
    const double module_dispatch_us = median(module_host_us);
    const bool dispatch_gate = module_dispatch_us - integrated_dispatch_us < 100.0;

    std::cout << std::fixed << std::setprecision(6)
              << "{\n"
              << "  \"module\": \"" << module->module_name << "\",\n"
              << "  \"build_id\": \"" << module->module_build_id << "\",\n"
              << "  \"device\": \"" << queue.get_device().get_info<sycl::info::device::name>() << "\",\n"
              << "  \"pack_cache_hit\": " << (cache_hit ? "true" : "false") << ",\n"
              << "  \"pack_prepare_s\": " << pack_prepare_s << ",\n"
              << "  \"device_pack_copy_s\": " << device_copy_s << ",\n"
              << "  \"workspace_bytes\": " << workspace_info.bytes << ",\n"
              << "  \"integrated_ids\": [";
    for (int row = 0; row < useful_rows; ++row) {
        std::cout << (row == 0 ? "" : ", ") << fixture_integrated_ids[row];
    }
    std::cout << "],\n  \"module_ids\": [";
    for (int row = 0; row < useful_rows; ++row) {
        std::cout << (row == 0 ? "" : ", ") << fixture_module_ids[row];
    }
    std::cout << "],\n"
              << "  \"fixture_exact\": " << (exact ? "true" : "false") << ",\n"
              << "  \"zero_tie_exact\": " << (tie_exact ? "true" : "false") << ",\n"
              << "  \"invalid_layout_fallback_safe\": " << (fallback_safe ? "true" : "false") << ",\n"
              << "  \"iterations\": " << iterations << ",\n"
              << "  \"integrated_wall_median_us\": " << integrated_median_us << ",\n"
              << "  \"module_wall_median_us\": " << module_median_us << ",\n"
              << "  \"wall_ratio_module_over_integrated\": " << module_median_us / integrated_median_us << ",\n"
              << "  \"integrated_host_dispatch_median_us\": " << integrated_dispatch_us << ",\n"
              << "  \"module_host_dispatch_median_us\": " << module_dispatch_us << ",\n"
              << "  \"dispatch_delta_us\": " << module_dispatch_us - integrated_dispatch_us << ",\n"
              << "  \"dispatch_overhead_lt_100us\": " << (dispatch_gate ? "true" : "false") << "\n"
              << "}\n";

    queue.wait_and_throw();
    for (void *pointer : {device_pack, static_cast<void *>(device_activations),
                          static_cast<void *>(integrated_ids), static_cast<void *>(module_ids),
                          module_workspace}) {
        sycl::free(pointer, queue);
    }
    dlclose(module_handle);
    return exact && tie_exact && fallback_safe && dispatch_gate ? 0 : 1;
} catch (const std::exception &error) {
    std::cerr << "q6-module-compare error: " << error.what() << '\n';
    return 1;
}
