#include "q27_xe2_module.h"
#include "q5k_gdn_out_m6_module.h"

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
#include <fstream>
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

constexpr int m = q27_q5k_gdn_out_m6_workspace::rows;
constexpr int k = q27_q5k_gdn_out_m6_workspace::k;
constexpr int n = q27_q5k_gdn_out_m6_workspace::n;
constexpr int kb = k / 32;
constexpr int sb = k / 256;
constexpr int nt = n / 16;
constexpr size_t source_offset = 1963459456;
constexpr size_t source_bytes = 21626880;
constexpr size_t candidate_bytes = q27_q5k_gdn_out_m6_workspace::pack_bytes;
constexpr size_t reordered_bytes = source_bytes;
constexpr size_t payload_bytes = candidate_bytes + reordered_bytes;

struct q5_block_file {
    uint16_t d;
    uint16_t dmin;
    uint8_t scales[12];
    uint8_t qh[32];
    uint8_t qs[128];
};
static_assert(sizeof(q5_block_file) == 176);

struct pack_cache_header {
    char magic[8];
    uint32_t version;
    uint32_t k;
    uint32_t n;
    uint32_t reserved;
    uint64_t source_offset;
    uint64_t source_bytes;
    uint64_t candidate_bytes;
    uint64_t reordered_bytes;
    uint64_t layout_id;
    uint64_t model_tag;
};
static_assert(sizeof(pack_cache_header) == 72);

class mapped_file {
public:
    explicit mapped_file(const std::string &path) {
        fd_ = open(path.c_str(), O_RDONLY);
        if (fd_ < 0) throw std::runtime_error("open failed: " + path);
        struct stat st {};
        if (fstat(fd_, &st) != 0 || st.st_size <= 0) {
            throw std::runtime_error("fstat failed: " + path);
        }
        size_ = size_t(st.st_size);
        void *mapping = mmap(nullptr, size_, PROT_READ, MAP_PRIVATE, fd_, 0);
        if (mapping == MAP_FAILED) throw std::runtime_error("mmap failed: " + path);
        data_ = static_cast<const uint8_t *>(mapping);
    }
    ~mapped_file() {
        if (data_) munmap(const_cast<uint8_t *>(data_), size_);
        if (fd_ >= 0) close(fd_);
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
    while (bytes != 0) {
        const ssize_t count = write(fd, cursor, bytes);
        if (count <= 0) throw std::runtime_error("pack-cache write failed");
        cursor += count;
        bytes -= size_t(count);
    }
}

void get_scale_min(int group, const uint8_t *q, uint8_t *scale, uint8_t *min) {
    if (group < 4) {
        *scale = q[group] & 63;
        *min = q[group + 4] & 63;
    } else {
        *scale = (q[group + 4] & 15) | ((q[group - 4] >> 6) << 4);
        *min = (q[group + 4] >> 4) | ((q[group] >> 6) << 4);
    }
}

uint8_t get_quant(const q5_block_file &block, int index) {
    const int il = index / 64;
    const int in = index % 64;
    const int ir = (in & 31) / 2;
    const int iq = in & 1;
    const uint8_t q = block.qs[32 * il + 2 * ir + iq];
    const uint8_t h = block.qh[2 * ir + iq];
    const uint8_t low = in >= 32 ? q >> 4 : q & 15;
    const uint8_t mask = uint8_t(1 << (2 * il + (in >= 32 ? 1 : 0)));
    return uint8_t(low + ((h & mask) ? 16 : 0));
}

void pack_q5(const q5_block_file *source, uint8_t *candidate, uint8_t *reordered) {
    uint8_t *quants = candidate;
    auto *scale_min = reinterpret_cast<uint16_t *>(candidate + size_t(k) * n);
    auto *dm = reinterpret_cast<uint16_t *>(candidate + size_t(k) * n + size_t(kb) * n * 2);
    const size_t total_blocks = size_t(n) * sb;
    uint8_t *r_qs = reordered;
    uint8_t *r_qh = r_qs + total_blocks * 128;
    uint8_t *r_scales = r_qh + total_blocks * 32;
    uint16_t *r_dm = reinterpret_cast<uint16_t *>(r_scales + total_blocks * 12);

    for (int output = 0; output < n; ++output) {
        const int tile = output / 16;
        const int lane = output % 16;
        for (int super = 0; super < sb; ++super) {
            const size_t source_block = size_t(output) * sb + super;
            const q5_block_file &block = source[source_block];
            std::memcpy(r_qs + source_block * 128, block.qs, 128);
            std::memcpy(r_qh + source_block * 32, block.qh, 32);
            std::memcpy(r_scales + source_block * 12, block.scales, 12);
            r_dm[source_block * 2] = block.d;
            r_dm[source_block * 2 + 1] = block.dmin;
            dm[(size_t(super) * n + output) * 2] = block.d;
            dm[(size_t(super) * n + output) * 2 + 1] = block.dmin;
            for (int group = 0; group < 8; ++group) {
                uint8_t scale = 0, min = 0;
                get_scale_min(group, block.scales, &scale, &min);
                const int qblock = super * 8 + group;
                scale_min[size_t(qblock) * n + output] = uint16_t(scale | (uint16_t(min) << 8));
                for (int ki = 0; ki < 32; ++ki) {
                    quants[((size_t(qblock) * nt + tile) * 32 + ki) * 16 + lane] =
                        int8_t(get_quant(block, group * 32 + ki));
                }
            }
        }
    }
}

bool valid_cache(const mapped_file &cache) {
    if (cache.size() != sizeof(pack_cache_header) + payload_bytes) return false;
    const auto *h = reinterpret_cast<const pack_cache_header *>(cache.data());
    return std::memcmp(h->magic, "Q5GDOM61", 8) == 0 && h->version == 1 &&
        h->k == k && h->n == n && h->source_offset == source_offset &&
        h->source_bytes == source_bytes && h->candidate_bytes == candidate_bytes &&
        h->reordered_bytes == reordered_bytes &&
        h->layout_id == Q27_XE2_LAYOUT_Q5K_GDN_OUT_M6_V1 &&
        h->model_tag == Q27_XE2_QWEN36_27B_Q4_MODEL_TAG;
}

std::unique_ptr<mapped_file> open_or_build_pack(
        const std::string &model_path, const std::string &cache_path,
        bool *cache_hit, double *prepare_s) {
    const auto begin = std::chrono::steady_clock::now();
    if (std::filesystem::exists(cache_path)) {
        auto cache = std::make_unique<mapped_file>(cache_path);
        if (!valid_cache(*cache)) throw std::runtime_error("pack-cache identity mismatch");
        *cache_hit = true;
        *prepare_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - begin).count();
        return cache;
    }
    mapped_file model(model_path);
    if (model.size() < source_offset + source_bytes) throw std::runtime_error("model too small");
    std::vector<uint8_t> payload(payload_bytes);
    pack_q5(reinterpret_cast<const q5_block_file *>(model.data() + source_offset),
        payload.data(), payload.data() + candidate_bytes);
    std::filesystem::create_directories(std::filesystem::path(cache_path).parent_path());
    const std::string temporary = cache_path + ".tmp." + std::to_string(getpid());
    int fd = open(temporary.c_str(), O_CREAT | O_EXCL | O_WRONLY, 0644);
    if (fd < 0) throw std::runtime_error("could not create pack cache");
    const pack_cache_header header = {
        {'Q','5','G','D','O','M','6','1'}, 1, k, n, 0, source_offset, source_bytes,
        candidate_bytes, reordered_bytes, Q27_XE2_LAYOUT_Q5K_GDN_OUT_M6_V1,
        Q27_XE2_QWEN36_27B_Q4_MODEL_TAG,
    };
    try {
        write_all(fd, &header, sizeof(header));
        write_all(fd, payload.data(), payload.size());
        if (fsync(fd) != 0 || close(fd) != 0) throw std::runtime_error("cache finalize failed");
        fd = -1;
        if (rename(temporary.c_str(), cache_path.c_str()) != 0) {
            throw std::runtime_error("cache rename failed");
        }
    } catch (...) {
        if (fd >= 0) close(fd);
        unlink(temporary.c_str());
        throw;
    }
    *cache_hit = false;
    auto cache = std::make_unique<mapped_file>(cache_path);
    if (!valid_cache(*cache)) throw std::runtime_error("new pack cache validation failed");
    *prepare_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - begin).count();
    return cache;
}

template <int M> class production_quant_kernel;
template <int M>
void quantize_production(sycl::queue &queue, const float *src, int8_t *dst) {
    constexpr int lanes = 16;
    queue.submit([&](sycl::handler &handler) {
        handler.parallel_for<production_quant_kernel<M>>(
            sycl::nd_range<1>(M * kb * lanes, lanes),
            [=](sycl::nd_item<1> item) [[sycl::reqd_sub_group_size(lanes)]] {
                const int linear = int(item.get_group(0));
                const int row = linear / kb;
                const int block = linear % kb;
                const int lane = int(item.get_local_id(0));
                float values[2];
                float sum = 0.0f, amax = 0.0f;
#pragma unroll
                for (int j = 0; j < 2; ++j) {
                    values[j] = src[size_t(row) * k + block * 32 + lane * 2 + j];
                    sum += values[j];
                    amax = sycl::fmax(amax, sycl::fabs(values[j]));
                }
                const auto subgroup = item.get_sub_group();
                sum = sycl::reduce_over_group(subgroup, sum, sycl::plus<float>());
                amax = sycl::reduce_over_group(subgroup, amax, sycl::maximum<float>());
                const float d = amax == 0.0f ? 1.0f : amax / 127.0f;
#pragma unroll
                for (int j = 0; j < 2; ++j) {
                    dst[size_t(row) * (k + kb * 4) + block * 32 + lane * 2 + j] =
                        int8_t(sycl::round(values[j] / d));
                }
                if (lane == 0) {
                    *reinterpret_cast<sycl::half2 *>(dst + size_t(row) * (k + kb * 4) +
                        k + block * 4) = sycl::half2(
                            sycl::half(amax == 0.0f ? 0.0f : d), sycl::half(sum));
                }
            });
    });
}

double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

struct delta_result { float max_abs = 0; float max_rel = 0; double rms = 0; size_t bit_diff = 0; };
delta_result compare(const std::vector<float> &a, const std::vector<float> &b) {
    delta_result result;
    double squared = 0.0;
    for (size_t i = 0; i < a.size(); ++i) {
        const float delta = std::fabs(a[i] - b[i]);
        result.max_abs = std::max(result.max_abs, delta);
        result.max_rel = std::max(result.max_rel, delta / std::max(1.0f, std::fabs(a[i])));
        squared += double(delta) * delta;
        uint32_t ai = 0, bi = 0;
        std::memcpy(&ai, &a[i], 4); std::memcpy(&bi, &b[i], 4);
        result.bit_diff += ai != bi;
    }
    result.rms = std::sqrt(squared / a.size());
    return result;
}

} // namespace

int main(int argc, char **argv) try {
    if (argc < 6 || argc > 7) {
        std::cerr << "usage: " << argv[0]
                  << " MODULE MODEL INPUT_F32 ORACLE_F32 PACK_CACHE [ITERS]\n";
        return 64;
    }
    const int iterations = argc == 7 ? std::stoi(argv[6]) : 100;
    mapped_file input_file(argv[3]);
    mapped_file oracle_file(argv[4]);
    if (input_file.size() != size_t(m) * k * sizeof(float) ||
            oracle_file.size() != size_t(m) * n * sizeof(float)) {
        throw std::runtime_error("fixture sizes do not match M=6 GDN output projection");
    }
    const float *host_input = reinterpret_cast<const float *>(input_file.data());
    const float *host_oracle = reinterpret_cast<const float *>(oracle_file.data());

    void *handle = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!handle) throw std::runtime_error(std::string("dlopen failed: ") + dlerror());
    auto getter = reinterpret_cast<q27_xe2_get_module_v1_fn>(
        dlsym(handle, Q27_XE2_GETTER_SYMBOL));
    const q27_xe2_module_v1 *module = getter ? getter() : nullptr;
    if (!module || module->abi_magic != Q27_XE2_ABI_MAGIC ||
            module->abi_version != Q27_XE2_ABI_VERSION ||
            std::strcmp(module->toolchain_abi, Q27_XE2_TOOLCHAIN_ABI) != 0) {
        throw std::runtime_error("module ABI mismatch");
    }

    bool cache_hit = false;
    double prepare_s = 0.0;
    auto cache = open_or_build_pack(argv[2], argv[5], &cache_hit, &prepare_s);
    const uint8_t *payload = cache->data() + sizeof(pack_cache_header);

    ggml_backend_sycl_context context(0);
    sycl::queue &queue = *context.stream();
    const auto device = queue.get_device();
    const uint64_t free_before = device.has(sycl::aspect::ext_intel_free_memory) ?
        device.get_info<sycl::ext::intel::info::device::free_memory>() : 0;
    auto alloc = [&](size_t bytes) {
        void *pointer = sycl::malloc_device(bytes, queue);
        if (!pointer) throw std::bad_alloc();
        return pointer;
    };
    void *d_candidate = alloc(candidate_bytes);
    void *d_reordered = alloc(reordered_bytes);
    auto *d_input = static_cast<float *>(alloc(size_t(m) * k * sizeof(float)));
    auto *d_q8 = static_cast<int8_t *>(alloc(size_t(m) * (k + kb * 4)));
    auto *d_integrated = static_cast<float *>(alloc(size_t(m) * n * sizeof(float)));
    auto *d_candidate_out = static_cast<float *>(alloc(size_t(m) * n * sizeof(float)));
    void *d_workspace = alloc(q27_q5k_gdn_out_m6_workspace::bytes);
    queue.memcpy(d_candidate, payload, candidate_bytes);
    queue.memcpy(d_reordered, payload + candidate_bytes, reordered_bytes);
    queue.memcpy(d_input, host_input, size_t(m) * k * sizeof(float)).wait();
    const uint64_t free_after = device.has(sycl::aspect::ext_intel_free_memory) ?
        device.get_info<sycl::ext::intel::info::device::free_memory>() : 0;

    ggml_tensor src0{};
    ggml_tensor src1{};
    ggml_tensor dst{};
    ggml_tensor_extra_gpu extra{};
    src0.type = GGML_TYPE_Q5_K;
    src0.ne[0] = k; src0.ne[1] = n; src0.ne[2] = src0.ne[3] = 1;
    extra.optimized_feature.reorder = true;
    src0.extra = &extra;
    src1.type = GGML_TYPE_F32;
    src1.ne[0] = k; src1.ne[1] = m; src1.ne[2] = src1.ne[3] = 1;
    dst.type = GGML_TYPE_F32;
    dst.ne[0] = n; dst.ne[1] = m; dst.ne[2] = dst.ne[3] = 1;

    q27_xe2_pack_v1 pack = {d_candidate, candidate_bytes,
        Q27_XE2_LAYOUT_Q5K_GDN_OUT_M6_V1, Q27_XE2_QWEN36_27B_Q4_MODEL_TAG,
        Q27_XE2_PACK_GDN_OUTPUT, 0};
    q27_xe2_launch_v1 launch{};
    launch.struct_size = sizeof(launch);
    launch.op = Q27_XE2_OP_Q5K_GDN_OUT_M6;
    launch.flags = Q27_XE2_QUEUE_IS_IN_ORDER;
    launch.queue = &queue;
    launch.input0 = d_input;
    launch.output0 = d_candidate_out;
    launch.scratch = d_workspace;
    launch.scratch_bytes = q27_q5k_gdn_out_m6_workspace::bytes;
    launch.packs = &pack;
    launch.pack_count = 1;
    launch.rows = m;
    launch.cols = n;
    launch.stride = k;

    auto integrated = [&] {
        quantize_production<m>(queue, d_input, d_q8);
        ggml_sycl_op_mul_mat_vec_q(context, &src0, &src1, &dst,
            static_cast<const char *>(d_reordered), d_input,
            reinterpret_cast<const char *>(d_q8), d_integrated,
            0, n, m, k, &queue);
    };
    auto candidate = [&] {
        const int32_t status = module->launch(&launch);
        if (status != Q27_XE2_OK) {
            throw std::runtime_error("candidate module status " + std::to_string(status));
        }
    };

    integrated(); candidate(); queue.wait_and_throw();
    std::vector<float> integrated_host(size_t(m) * n), candidate_host(size_t(m) * n),
        oracle(host_oracle, host_oracle + size_t(m) * n);
    queue.memcpy(integrated_host.data(), d_integrated, integrated_host.size() * 4);
    queue.memcpy(candidate_host.data(), d_candidate_out, candidate_host.size() * 4).wait();
    const auto candidate_delta = compare(integrated_host, candidate_host);
    const auto integrated_oracle_delta = compare(oracle, integrated_host);
    const auto candidate_oracle_delta = compare(oracle, candidate_host);

    // Invalid layout is fallback-safe: validation happens before submission.
    q27_xe2_pack_v1 invalid_pack = pack;
    invalid_pack.layout_id ^= 1;
    q27_xe2_launch_v1 invalid_launch = launch;
    invalid_launch.packs = &invalid_pack;
    const int32_t invalid_status = module->launch(&invalid_launch);

    std::vector<double> integrated_us, candidate_us;
    for (int i = 0; i < iterations; ++i) {
        auto begin = std::chrono::steady_clock::now();
        if ((i & 1) == 0) {
            integrated(); queue.wait_and_throw();
        } else {
            candidate(); queue.wait_and_throw();
        }
        auto end = std::chrono::steady_clock::now();
        ((i & 1) == 0 ? integrated_us : candidate_us).push_back(
            std::chrono::duration<double, std::micro>(end - begin).count());
        begin = std::chrono::steady_clock::now();
        if ((i & 1) == 0) {
            candidate(); queue.wait_and_throw();
        } else {
            integrated(); queue.wait_and_throw();
        }
        end = std::chrono::steady_clock::now();
        ((i & 1) == 0 ? candidate_us : integrated_us).push_back(
            std::chrono::duration<double, std::micro>(end - begin).count());
    }
    const double control_median = median(integrated_us);
    const double candidate_median = median(candidate_us);
    const double saving_us = control_median - candidate_median;
    const double projected_ms = saving_us * 48.0 / 1000.0;
    const double all48_gib = candidate_bytes * 48.0 / double(UINT64_C(1) << 30);

    std::cout << std::fixed << std::setprecision(6)
        << "{\n"
        << "  \"device\": \"" << device.get_info<sycl::info::device::name>() << "\",\n"
        << "  \"iterations_per_path\": " << integrated_us.size() << ",\n"
        << "  \"pack_cache_hit\": " << (cache_hit ? "true" : "false") << ",\n"
        << "  \"pack_prepare_s\": " << prepare_s << ",\n"
        << "  \"source_bytes_per_layer\": " << source_bytes << ",\n"
        << "  \"candidate_pack_bytes_per_layer\": " << candidate_bytes << ",\n"
        << "  \"candidate_pack_all48_gib\": " << all48_gib << ",\n"
        << "  \"device_allocated_bytes\": " << (free_before >= free_after ? free_before-free_after : 0) << ",\n"
        << "  \"invalid_layout_status\": " << invalid_status << ",\n"
        << "  \"integrated_us\": " << control_median << ",\n"
        << "  \"candidate_us\": " << candidate_median << ",\n"
        << "  \"speedup\": " << control_median / candidate_median << ",\n"
        << "  \"saving_us_per_layer\": " << saving_us << ",\n"
        << "  \"projected_saving_ms_48_layers\": " << projected_ms << ",\n"
        << "  \"projected_ms_per_gib\": " << projected_ms / all48_gib << ",\n"
        << "  \"candidate_vs_integrated_max_abs\": " << candidate_delta.max_abs << ",\n"
        << "  \"candidate_vs_integrated_max_rel\": " << candidate_delta.max_rel << ",\n"
        << "  \"candidate_vs_integrated_rms\": " << candidate_delta.rms << ",\n"
        << "  \"candidate_vs_integrated_bit_differences\": " << candidate_delta.bit_diff << ",\n"
        << "  \"integrated_vs_capture_max_abs\": " << integrated_oracle_delta.max_abs << ",\n"
        << "  \"candidate_vs_capture_max_abs\": " << candidate_oracle_delta.max_abs << "\n"
        << "}\n";

    for (void *pointer : {d_candidate, d_reordered, static_cast<void *>(d_input),
            static_cast<void *>(d_q8), static_cast<void *>(d_integrated),
            static_cast<void *>(d_candidate_out), d_workspace}) {
        sycl::free(pointer, queue);
    }
    dlclose(handle);
    const bool correctness_ok = candidate_delta.max_rel <= 2.0e-4f &&
        candidate_delta.rms <= 2.0e-4 && integrated_oracle_delta.max_rel <= 2.0e-4f;
    const bool contract_ok = invalid_status == Q27_XE2_BAD_LAYOUT;
    return correctness_ok && contract_ok ? 0 : 3;
} catch (const std::exception &error) {
    std::cerr << "error: " << error.what() << '\n';
    return 2;
}
