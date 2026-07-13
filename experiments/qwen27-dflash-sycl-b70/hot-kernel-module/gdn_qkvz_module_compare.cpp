#include "gdn_qkvz_m6_module.h"
#include "q27_xe2_module.h"

#include "ggml-sycl/common.hpp"
#include "ggml-sycl/mmvq.hpp"

#include <sycl/sycl.hpp>
#include <oneapi/mkl.hpp>

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

constexpr int m = q27_gdn_qkvz_m6_workspace::rows;
constexpr int k = q27_gdn_qkvz_m6_workspace::k;
constexpr int n_qkv = q27_gdn_qkvz_m6_workspace::n_qkv;
constexpr int n_z = q27_gdn_qkvz_m6_workspace::n_z;
constexpr int n_alpha = q27_gdn_qkvz_m6_workspace::n_alpha;
constexpr int n_beta = q27_gdn_qkvz_m6_workspace::n_beta;
constexpr int kb = k / 32;
constexpr size_t z_source_offset = 1769120896;
constexpr size_t qkv_source_offset = 1786836096;
constexpr size_t alpha_source_offset = 1972323648;
constexpr size_t beta_source_offset = 1973306688;
constexpr size_t ssm_a_source_offset = 1972323456;
constexpr size_t ssm_dt_source_offset = 1974453568;
constexpr size_t qkv_source_bytes = size_t(n_qkv) * kb * 18;
constexpr size_t z_source_bytes = size_t(n_z) * kb * 18;
constexpr size_t qkv_dpas_bytes = q27_gdn_qkvz_m6_workspace::qkv_pack_bytes;
constexpr size_t z_dpas_bytes = q27_gdn_qkvz_m6_workspace::z_pack_bytes;
constexpr size_t qkv_prod_bytes = qkv_dpas_bytes;
constexpr size_t z_prod_bytes = z_dpas_bytes;
constexpr size_t payload_bytes = qkv_dpas_bytes + z_dpas_bytes + qkv_prod_bytes + z_prod_bytes;
constexpr size_t alpha_bytes = size_t(k) * n_alpha * sizeof(float);
constexpr size_t beta_bytes = size_t(k) * n_beta * sizeof(float);
constexpr size_t alpha_beta_bytes = alpha_bytes + beta_bytes;
constexpr size_t production_pack_per_layer_bytes = qkv_dpas_bytes + z_dpas_bytes + alpha_beta_bytes;
constexpr size_t production_pack_48_layers_bytes = production_pack_per_layer_bytes * 48;
constexpr size_t gate_vector_bytes = size_t(n_alpha) * sizeof(float);
constexpr size_t folded_pack_per_layer_bytes = production_pack_per_layer_bytes + 2 * gate_vector_bytes;
constexpr size_t folded_pack_48_layers_bytes = folded_pack_per_layer_bytes * 48;

struct q4_block_file {
    uint16_t d;
    uint8_t qs[16];
};
static_assert(sizeof(q4_block_file) == 18);

struct pack_cache_header {
    char magic[8];
    uint32_t version;
    uint32_t k;
    uint32_t n_qkv;
    uint32_t n_z;
    uint64_t payload_bytes;
    uint64_t layout_id;
    uint64_t model_tag;
    uint64_t qkv_source_offset;
    uint64_t z_source_offset;
    uint64_t qkv_source_bytes;
    uint64_t z_source_bytes;
};
static_assert(sizeof(pack_cache_header) == 80);

class mapped_file {
public:
    explicit mapped_file(const std::string &path) {
        fd_ = open(path.c_str(), O_RDONLY);
        if (fd_ < 0) throw std::runtime_error("open failed: " + path);
        struct stat st {};
        if (fstat(fd_, &st) != 0 || st.st_size <= 0) throw std::runtime_error("fstat failed: " + path);
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
    auto *cursor = static_cast<const uint8_t *>(data);
    while (bytes) {
        const ssize_t count = write(fd, cursor, std::min<size_t>(bytes, 64 * 1024 * 1024));
        if (count <= 0) throw std::runtime_error("pack cache write failed");
        cursor += count;
        bytes -= size_t(count);
    }
}

void pack_q4(const q4_block_file *raw, int n, uint8_t *dpas, uint8_t *prod) {
    const int nt = n / 16;
    const size_t quant_bytes = size_t(k) * n / 2;
    auto *dpas_scales = reinterpret_cast<uint16_t *>(dpas + quant_bytes);
    auto *prod_scales = reinterpret_cast<uint16_t *>(prod + quant_bytes);
    std::memset(dpas, 0, quant_bytes);
    for (int row = 0; row < n; ++row) {
        for (int block = 0; block < kb; ++block) {
            const q4_block_file &source = raw[size_t(row) * kb + block];
            std::memcpy(prod + (size_t(row) * kb + block) * 16, source.qs, 16);
            prod_scales[size_t(row) * kb + block] = source.d;
            dpas_scales[size_t(block) * n + row] = source.d;
            const int tile = row / 16;
            const int lane = row % 16;
            for (int ki = 0; ki < 32; ++ki) {
                const uint8_t biased = (source.qs[ki & 15] >> (4 * (ki / 16))) & 15;
                const uint8_t signed_nibble = biased ^ 8;
                const size_t nibble =
                    ((((size_t(block) * nt + tile) * 4 + ki / 8) * 16 + lane) * 8 + ki % 8);
                dpas[nibble / 2] |= signed_nibble << (4 * (nibble & 1));
            }
        }
    }
}

bool valid_cache(const mapped_file &cache) {
    if (cache.size() != sizeof(pack_cache_header) + payload_bytes) return false;
    const auto *h = reinterpret_cast<const pack_cache_header *>(cache.data());
    return std::memcmp(h->magic, "Q4GDNM61", 8) == 0 && h->version == 1 && h->k == k &&
        h->n_qkv == n_qkv && h->n_z == n_z && h->payload_bytes == payload_bytes &&
        h->layout_id == Q27_XE2_LAYOUT_Q4_0_Q8_1_V1 &&
        h->model_tag == Q27_XE2_QWEN36_27B_Q4_MODEL_TAG &&
        h->qkv_source_offset == qkv_source_offset && h->z_source_offset == z_source_offset &&
        h->qkv_source_bytes == qkv_source_bytes && h->z_source_bytes == z_source_bytes;
}

std::unique_ptr<mapped_file> open_or_build_pack(
        const std::string &model_path, const std::string &cache_path,
        bool *cache_hit, double *prepare_s) {
    const auto begin = std::chrono::steady_clock::now();
    if (std::filesystem::exists(cache_path)) {
        auto cache = std::make_unique<mapped_file>(cache_path);
        if (!valid_cache(*cache)) throw std::runtime_error("pack cache identity mismatch: " + cache_path);
        *cache_hit = true;
        *prepare_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - begin).count();
        return cache;
    }
    mapped_file model(model_path);
    if (model.size() < qkv_source_offset + qkv_source_bytes) {
        throw std::runtime_error("model file is too small for layer-0 GDN tensors");
    }
    std::vector<uint8_t> payload(payload_bytes);
    uint8_t *qkv_dpas = payload.data();
    uint8_t *z_dpas = qkv_dpas + qkv_dpas_bytes;
    uint8_t *qkv_prod = z_dpas + z_dpas_bytes;
    uint8_t *z_prod = qkv_prod + qkv_prod_bytes;
    pack_q4(reinterpret_cast<const q4_block_file *>(model.data() + qkv_source_offset),
            n_qkv, qkv_dpas, qkv_prod);
    pack_q4(reinterpret_cast<const q4_block_file *>(model.data() + z_source_offset),
            n_z, z_dpas, z_prod);
    std::filesystem::create_directories(std::filesystem::path(cache_path).parent_path());
    const std::string temporary = cache_path + ".tmp." + std::to_string(getpid());
    int fd = open(temporary.c_str(), O_CREAT | O_EXCL | O_WRONLY, 0644);
    if (fd < 0) throw std::runtime_error("could not create pack cache");
    const pack_cache_header header = {
        {'Q','4','G','D','N','M','6','1'}, 1, k, n_qkv, n_z, payload_bytes,
        Q27_XE2_LAYOUT_Q4_0_Q8_1_V1, Q27_XE2_QWEN36_27B_Q4_MODEL_TAG,
        qkv_source_offset, z_source_offset, qkv_source_bytes, z_source_bytes,
    };
    try {
        write_all(fd, &header, sizeof(header));
        write_all(fd, payload.data(), payload.size());
        if (fsync(fd) != 0 || close(fd) != 0) throw std::runtime_error("cache finalize failed");
        fd = -1;
        if (rename(temporary.c_str(), cache_path.c_str()) != 0) throw std::runtime_error("cache rename failed");
    } catch (...) {
        if (fd >= 0) close(fd);
        unlink(temporary.c_str());
        throw;
    }
    *cache_hit = false;
    auto cache = std::make_unique<mapped_file>(cache_path);
    if (!valid_cache(*cache)) throw std::runtime_error("new pack cache failed validation");
    *prepare_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - begin).count();
    return cache;
}

template <int M> class production_quant_kernel;

template <int M>
sycl::event quantize_production(sycl::queue &queue, const float *src, int8_t *dst) {
    constexpr int lanes = 16;
    constexpr int values_per_lane = 32 / lanes;
    return queue.submit([&](sycl::handler &handler) {
        handler.parallel_for<production_quant_kernel<M>>(
            sycl::nd_range<1>(M * kb * lanes, lanes),
            [=](sycl::nd_item<1> item) [[sycl::reqd_sub_group_size(lanes)]] {
                const int group = int(item.get_group(0));
                const int row = group / kb;
                const int block = group % kb;
                const int lane = int(item.get_local_id(0));
                float values[values_per_lane];
                float sum = 0.0f, amax = 0.0f;
#pragma unroll
                for (int j = 0; j < values_per_lane; ++j) {
                    const int element = lane * values_per_lane + j;
                    values[j] = src[size_t(row) * k + block * 32 + element];
                    sum += values[j];
                    amax = sycl::fmax(amax, sycl::fabs(values[j]));
                }
                const auto subgroup = item.get_sub_group();
                amax = sycl::reduce_over_group(subgroup, amax, sycl::maximum<float>());
                sum = sycl::reduce_over_group(subgroup, sum, sycl::plus<float>());
                const float d = amax ? amax / 127.0f : 1.0f;
#pragma unroll
                for (int j = 0; j < values_per_lane; ++j) {
                    const int element = lane * values_per_lane + j;
                    dst[size_t(row) * (k + kb * 4) + block * 32 + element] =
                        int8_t(sycl::round(values[j] / d));
                }
                if (lane == 0) {
                    *reinterpret_cast<sycl::half2 *>(
                        dst + size_t(row) * (k + kb * 4) + k + block * 4) =
                        sycl::half2(sycl::half(amax ? d : 0.0f), sycl::half(sum));
                }
            });
    });
}

double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

template <typename Function>
double time_us(sycl::queue &queue, Function &&function) {
    queue.wait_and_throw();
    const auto begin = std::chrono::steady_clock::now();
    function();
    queue.wait_and_throw();
    return std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - begin).count();
}

struct delta_result { float max_abs; float max_rel; double rms; };

delta_result compare(const std::vector<float> &a, const std::vector<float> &b) {
    delta_result result{};
    double squared = 0.0;
    for (size_t i = 0; i < a.size(); ++i) {
        const float delta = std::fabs(a[i] - b[i]);
        result.max_abs = std::max(result.max_abs, delta);
        result.max_rel = std::max(result.max_rel, delta / std::max(1.0f, std::fabs(a[i])));
        squared += double(delta) * delta;
    }
    result.rms = std::sqrt(squared / a.size());
    return result;
}

class alpha_add_kernel;
class alpha_softplus_kernel;
class alpha_mul_kernel;

void alpha_separate_epilogue(
        sycl::queue &queue, const float *alpha, const float *dt, const float *a,
        float *temporary, float *output) {
    constexpr size_t count = size_t(m) * n_alpha;
    constexpr size_t local = 256;
    constexpr size_t global = ((count + local - 1) / local) * local;
    queue.submit([&](sycl::handler &handler) {
        handler.parallel_for<alpha_add_kernel>(
            sycl::nd_range<1>(global, local), [=](sycl::nd_item<1> item) {
                const size_t index = item.get_global_id(0);
                if (index < count) temporary[index] = alpha[index] + dt[index % n_alpha];
            });
    });
    queue.submit([&](sycl::handler &handler) {
        handler.parallel_for<alpha_softplus_kernel>(
            sycl::nd_range<1>(global, local), [=](sycl::nd_item<1> item) {
                const size_t index = item.get_global_id(0);
                if (index < count) {
                    const float x = temporary[index];
                    temporary[index] = sycl::fmax(x, 0.0f) +
                        sycl::log1p(sycl::exp(-sycl::fabs(x)));
                }
            });
    });
    queue.submit([&](sycl::handler &handler) {
        handler.parallel_for<alpha_mul_kernel>(
            sycl::nd_range<1>(global, local), [=](sycl::nd_item<1> item) {
                const size_t index = item.get_global_id(0);
                if (index < count) output[index] = temporary[index] * a[index % n_alpha];
            });
    });
}

} // namespace

int main(int argc, char **argv) try {
    if (argc < 5 || argc > 6) {
        std::cerr << "usage: " << argv[0] << " MODULE MODEL FIXTURE PACK_CACHE [ITERS]\n";
        return 64;
    }
    const int iterations = argc == 6 ? std::stoi(argv[5]) : 30;
    void *module_handle = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!module_handle) throw std::runtime_error(std::string("dlopen failed: ") + dlerror());
    auto getter = reinterpret_cast<q27_xe2_get_module_v1_fn>(dlsym(module_handle, Q27_XE2_GETTER_SYMBOL));
    if (!getter) throw std::runtime_error("module getter missing");
    const q27_xe2_module_v1 *module = getter();
    if (!module || module->abi_magic != Q27_XE2_ABI_MAGIC ||
            module->abi_version != Q27_XE2_ABI_VERSION ||
            module->struct_size < sizeof(q27_xe2_module_v1) ||
            std::strcmp(module->toolchain_abi, Q27_XE2_TOOLCHAIN_ABI) != 0) {
        throw std::runtime_error("module ABI mismatch");
    }

    mapped_file fixture(argv[3]);
    constexpr size_t fixture_header_bytes = 84;
    if (fixture.size() < fixture_header_bytes + size_t(m) * k * sizeof(float)) {
        throw std::runtime_error("fixture is not the expected real M=6 activation capture");
    }
    const float *host_input = reinterpret_cast<const float *>(fixture.data() + fixture_header_bytes);
    bool cache_hit = false;
    double pack_prepare_s = 0.0;
    auto cache = open_or_build_pack(argv[2], argv[4], &cache_hit, &pack_prepare_s);
    const uint8_t *payload = cache->data() + sizeof(pack_cache_header);
    const uint8_t *host_qkv_dpas = payload;
    const uint8_t *host_z_dpas = host_qkv_dpas + qkv_dpas_bytes;
    const uint8_t *host_qkv_prod = host_z_dpas + z_dpas_bytes;
    const uint8_t *host_z_prod = host_qkv_prod + qkv_prod_bytes;
    mapped_file model(argv[2]);
    if (model.size() < ssm_dt_source_offset + gate_vector_bytes) {
        throw std::runtime_error("model file is too small for layer-0 GDN gate tensors");
    }
    const void *host_alpha = model.data() + alpha_source_offset;
    const void *host_beta = model.data() + beta_source_offset;
    const void *host_ssm_a = model.data() + ssm_a_source_offset;
    const void *host_ssm_dt = model.data() + ssm_dt_source_offset;

    ggml_backend_sycl_context context(0);
    sycl::queue &queue = *context.stream();
    const auto device = queue.get_device();
    const uint64_t global_mem_bytes = device.get_info<sycl::info::device::global_mem_size>();
    const uint64_t free_mem_before = device.has(sycl::aspect::ext_intel_free_memory) ?
        device.get_info<sycl::ext::intel::info::device::free_memory>() : 0;
    auto alloc = [&](size_t bytes) {
        void *pointer = sycl::malloc_device(bytes, queue);
        if (!pointer) throw std::bad_alloc();
        return pointer;
    };
    void *d_qkv_dpas = alloc(qkv_dpas_bytes);
    void *d_z_dpas = alloc(z_dpas_bytes);
    void *d_qkv_prod = alloc(qkv_prod_bytes);
    void *d_z_prod = alloc(z_prod_bytes);
    auto *d_alpha_beta = static_cast<float *>(alloc(alpha_beta_bytes));
    auto *d_ssm_a = static_cast<float *>(alloc(gate_vector_bytes));
    auto *d_ssm_dt = static_cast<float *>(alloc(gate_vector_bytes));
    auto *d_input = static_cast<float *>(alloc(size_t(m) * k * sizeof(float)));
    auto *d_prod_q8 = static_cast<int8_t *>(alloc(size_t(m) * (k + kb * 4)));
    auto *d_int_qkv = static_cast<float *>(alloc(size_t(m) * n_qkv * sizeof(float)));
    auto *d_int_z = static_cast<float *>(alloc(size_t(m) * n_z * sizeof(float)));
    auto *d_int_alpha = static_cast<float *>(alloc(size_t(m) * n_alpha * sizeof(float)));
    auto *d_int_beta = static_cast<float *>(alloc(size_t(m) * n_beta * sizeof(float)));
    auto *d_int_gate = static_cast<float *>(alloc(size_t(m) * n_alpha * sizeof(float)));
    auto *d_gate_temporary = static_cast<float *>(alloc(size_t(m) * n_alpha * sizeof(float)));
    auto *d_mod_qkv = static_cast<float *>(alloc(size_t(m) * n_qkv * sizeof(float)));
    auto *d_mod_z = static_cast<float *>(alloc(size_t(m) * n_z * sizeof(float)));
    auto *d_mod_alpha = static_cast<float *>(alloc(size_t(m) * n_alpha * sizeof(float)));
    auto *d_mod_beta = static_cast<float *>(alloc(size_t(m) * n_beta * sizeof(float)));
    auto *d_mod_gate = static_cast<float *>(alloc(size_t(m) * n_alpha * sizeof(float)));
    auto *d_prod_qkv_out = static_cast<float *>(alloc(size_t(m) * n_qkv * sizeof(float)));
    auto *d_prod_z_out = static_cast<float *>(alloc(size_t(m) * n_z * sizeof(float)));

    q27_xe2_workspace_v1 workspace_info{};
    if (module->query_workspace(Q27_XE2_OP_GDN_QKVZAB_M6, m, n_qkv, &workspace_info) != Q27_XE2_OK ||
            workspace_info.bytes != q27_gdn_qkvz_m6_workspace::bytes) {
        throw std::runtime_error("GDN workspace contract mismatch");
    }
    void *workspace = alloc(workspace_info.bytes);
    queue.memcpy(d_qkv_dpas, host_qkv_dpas, qkv_dpas_bytes);
    queue.memcpy(d_z_dpas, host_z_dpas, z_dpas_bytes);
    queue.memcpy(d_qkv_prod, host_qkv_prod, qkv_prod_bytes);
    queue.memcpy(d_z_prod, host_z_prod, z_prod_bytes);
    queue.memcpy(d_alpha_beta, host_alpha, alpha_bytes);
    queue.memcpy(reinterpret_cast<uint8_t *>(d_alpha_beta) + alpha_bytes, host_beta, beta_bytes);
    queue.memcpy(d_ssm_a, host_ssm_a, gate_vector_bytes);
    queue.memcpy(d_ssm_dt, host_ssm_dt, gate_vector_bytes);
    queue.memcpy(d_input, host_input, size_t(m) * k * sizeof(float)).wait();
    const uint64_t free_mem_after_one_layer = device.has(sycl::aspect::ext_intel_free_memory) ?
        device.get_info<sycl::ext::intel::info::device::free_memory>() : 0;

    q27_xe2_pack_v1 packs[3]{};
    packs[0] = {d_qkv_dpas, qkv_dpas_bytes, Q27_XE2_LAYOUT_Q4_0_Q8_1_V1,
                Q27_XE2_QWEN36_27B_Q4_MODEL_TAG, Q27_XE2_PACK_GDN_QKV, 0};
    packs[1] = {d_z_dpas, z_dpas_bytes, Q27_XE2_LAYOUT_Q4_0_Q8_1_V1,
                Q27_XE2_QWEN36_27B_Q4_MODEL_TAG, Q27_XE2_PACK_GDN_Z, 0};
    packs[2] = {d_alpha_beta, alpha_beta_bytes, Q27_XE2_LAYOUT_F32_GDN_BA_V1,
                Q27_XE2_QWEN36_27B_Q4_MODEL_TAG, Q27_XE2_PACK_GDN_ALPHA_BETA, 0};
    q27_xe2_launch_v1 launch{};
    launch.struct_size = sizeof(launch);
    launch.op = Q27_XE2_OP_GDN_QKVZAB_M6;
    launch.flags = Q27_XE2_QUEUE_IS_IN_ORDER;
    launch.queue = &queue;
    launch.input0 = d_input;
    launch.output0 = d_mod_qkv;
    launch.output1 = d_mod_z;
    launch.output2 = d_mod_alpha;
    launch.output3 = d_mod_beta;
    launch.scratch = workspace;
    launch.scratch_bytes = workspace_info.bytes;
    launch.packs = packs;
    launch.pack_count = 3;
    launch.rows = m;
    launch.cols = n_qkv;
    launch.stride = k;

    q27_xe2_pack_v1 gate_packs[5] = {packs[0], packs[1], packs[2], {}, {}};
    gate_packs[3] = {d_ssm_dt, gate_vector_bytes, Q27_XE2_LAYOUT_F32_GDN_VECTOR_V1,
                     Q27_XE2_QWEN36_27B_Q4_MODEL_TAG, Q27_XE2_PACK_GDN_DT, 0};
    gate_packs[4] = {d_ssm_a, gate_vector_bytes, Q27_XE2_LAYOUT_F32_GDN_VECTOR_V1,
                     Q27_XE2_QWEN36_27B_Q4_MODEL_TAG, Q27_XE2_PACK_GDN_A, 0};
    q27_xe2_launch_v1 gate_launch = launch;
    gate_launch.op = Q27_XE2_OP_GDN_QKVZAB_GATE_M6;
    gate_launch.output2 = d_mod_gate;
    gate_launch.packs = gate_packs;
    gate_launch.pack_count = 5;

    auto f32_projection = [&](const float *weights, float *output) {
        constexpr float alpha = 1.0f;
        constexpr float beta = 0.0f;
        oneapi::mkl::blas::column_major::gemm(
            queue, oneapi::mkl::transpose::trans, oneapi::mkl::transpose::nontrans,
            int64_t(n_alpha), int64_t(m), int64_t(k), alpha, weights, int64_t(k),
            d_input, int64_t(k), beta, output, int64_t(n_alpha));
    };
    const float *d_alpha = d_alpha_beta;
    const float *d_beta = reinterpret_cast<const float *>(
        reinterpret_cast<const uint8_t *>(d_alpha_beta) + alpha_bytes);
    auto integrated = [&] {
        if (!ggml_sycl_mul_mat_q4_0_xe2_m6(context, d_qkv_dpas, qkv_dpas_bytes,
                d_input, d_int_qkv, k, n_qkv, &queue) ||
            !ggml_sycl_mul_mat_q4_0_xe2_m6(context, d_z_dpas, z_dpas_bytes,
                d_input, d_int_z, k, n_z, &queue)) {
            throw std::runtime_error("active integrated Q4_0 M6 pair declined");
        }
        // Match the graph's beta-then-alpha F32 oneMKL operation order.
        f32_projection(d_beta, d_int_beta);
        f32_projection(d_alpha, d_int_alpha);
    };
    auto generic_q4_oracle = [&] {
        quantize_production<m>(queue, d_input, d_prod_q8);
        ggml_sycl_bench_reorder_q4_0_ncols(
            d_qkv_prod, d_prod_q8, d_prod_qkv_out, k, n_qkv, m, k + kb * 4, n_qkv, &queue);
        quantize_production<m>(queue, d_input, d_prod_q8);
        ggml_sycl_bench_reorder_q4_0_ncols(
            d_z_prod, d_prod_q8, d_prod_z_out, k, n_z, m, k + kb * 4, n_z, &queue);
    };
    auto candidate = [&] {
        const int32_t status = module->launch(&launch);
        if (status != Q27_XE2_OK) throw std::runtime_error("module launch status " + std::to_string(status));
    };
    auto active_full_gate = [&] {
        integrated();
        alpha_separate_epilogue(
            queue, d_int_alpha, d_ssm_dt, d_ssm_a, d_gate_temporary, d_int_gate);
    };
    auto candidate_full_gate = [&] {
        const int32_t status = module->launch(&gate_launch);
        if (status != Q27_XE2_OK) {
            throw std::runtime_error("module gate launch status " + std::to_string(status));
        }
    };

    integrated(); generic_q4_oracle(); candidate(); active_full_gate(); candidate_full_gate();
    queue.wait_and_throw();
    auto copy_output = [&](float *device, size_t count) {
        std::vector<float> host(count);
        queue.memcpy(host.data(), device, count * sizeof(float)).wait();
        return host;
    };
    const auto int_qkv = copy_output(d_int_qkv, size_t(m) * n_qkv);
    const auto int_z = copy_output(d_int_z, size_t(m) * n_z);
    const auto int_alpha = copy_output(d_int_alpha, size_t(m) * n_alpha);
    const auto int_beta = copy_output(d_int_beta, size_t(m) * n_beta);
    const auto int_gate = copy_output(d_int_gate, size_t(m) * n_alpha);
    const auto mod_qkv = copy_output(d_mod_qkv, size_t(m) * n_qkv);
    const auto mod_z = copy_output(d_mod_z, size_t(m) * n_z);
    const auto mod_alpha = copy_output(d_mod_alpha, size_t(m) * n_alpha);
    const auto mod_beta = copy_output(d_mod_beta, size_t(m) * n_beta);
    const auto mod_gate = copy_output(d_mod_gate, size_t(m) * n_alpha);
    const auto prod_qkv = copy_output(d_prod_qkv_out, size_t(m) * n_qkv);
    const auto prod_z = copy_output(d_prod_z_out, size_t(m) * n_z);
    const auto qkv_integrated_delta = compare(int_qkv, mod_qkv);
    const auto z_integrated_delta = compare(int_z, mod_z);
    const auto qkv_production_delta = compare(prod_qkv, mod_qkv);
    const auto z_production_delta = compare(prod_z, mod_z);
    const auto alpha_integrated_delta = compare(int_alpha, mod_alpha);
    const auto beta_integrated_delta = compare(int_beta, mod_beta);
    const auto gate_integrated_delta = compare(int_gate, mod_gate);

    q27_xe2_pack_v1 bad_packs[5] = {
        gate_packs[0], gate_packs[1], gate_packs[2], gate_packs[3], gate_packs[4]};
    bad_packs[3].layout_id ^= 1;
    q27_xe2_launch_v1 bad_launch = gate_launch;
    bad_launch.packs = bad_packs;
    const bool fallback_safe = module->launch(&bad_launch) == Q27_XE2_BAD_LAYOUT;

    // Bring the card to a stable operating point before collecting interleaved
    // wall medians. This also removes one-time module/kernel initialization.
    constexpr int warmup_rounds = 20;
    for (int i = 0; i < warmup_rounds; ++i) {
        integrated();
        candidate();
        active_full_gate();
        candidate_full_gate();
    }
    queue.wait_and_throw();

    std::vector<double> integrated_us, candidate_us, active_gate_us, candidate_gate_us;
    for (int i = 0; i < iterations; ++i) {
        if ((i & 1) == 0) {
            integrated_us.push_back(time_us(queue, integrated));
            candidate_us.push_back(time_us(queue, candidate));
            active_gate_us.push_back(time_us(queue, active_full_gate));
            candidate_gate_us.push_back(time_us(queue, candidate_full_gate));
        } else {
            candidate_gate_us.push_back(time_us(queue, candidate_full_gate));
            active_gate_us.push_back(time_us(queue, active_full_gate));
            candidate_us.push_back(time_us(queue, candidate));
            integrated_us.push_back(time_us(queue, integrated));
        }
    }
    const double integrated_median = median(integrated_us);
    const double candidate_median = median(candidate_us);
    const double active_gate_median = median(active_gate_us);
    const double candidate_gate_median = median(candidate_gate_us);
    const double active_speedup = integrated_median / candidate_median;
    const double saving_per_layer_us = integrated_median - candidate_median;
    const double projected_cycle_saving_ms = saving_per_layer_us * 48.0 / 1000.0;
    const double gate_saving_per_layer_us = active_gate_median - candidate_gate_median;
    const double gate_projected_cycle_saving_ms = gate_saving_per_layer_us * 48.0 / 1000.0;
    const bool q4_exact = qkv_integrated_delta.max_abs == 0.0f && z_integrated_delta.max_abs == 0.0f;
    const bool f32_tight = alpha_integrated_delta.max_abs <= 0.002f &&
        beta_integrated_delta.max_abs <= 0.002f && alpha_integrated_delta.max_rel <= 0.0001f &&
        beta_integrated_delta.max_rel <= 0.0001f;
    const bool speed_gate = projected_cycle_saving_ms >= 2.0;
    const bool gate_semantics_tight = gate_integrated_delta.max_abs <= 0.0001f &&
        gate_integrated_delta.max_rel <= 0.0001f;
    const bool folded_speed_gate = gate_projected_cycle_saving_ms >= 2.0;
    const bool gate = q4_exact && f32_tight && gate_semantics_tight && fallback_safe &&
        speed_gate && folded_speed_gate;

    std::cout << std::fixed << std::setprecision(6)
        << "{\n"
        << "  \"module\": \"" << module->module_name << "\",\n"
        << "  \"build_id\": \"" << module->module_build_id << "\",\n"
        << "  \"device\": \"" << queue.get_device().get_info<sycl::info::device::name>() << "\",\n"
        << "  \"fixture_scope\": \"real model-generated final-norm M=6 activations; not a GDN-layer input capture\",\n"
        << "  \"weights\": \"real blk.0 Q4_0 QKV/z plus exact F32 alpha/beta\",\n"
        << "  \"pack_cache_hit\": " << (cache_hit ? "true" : "false") << ",\n"
        << "  \"pack_prepare_s\": " << pack_prepare_s << ",\n"
        << "  \"pack_payload_bytes\": " << payload_bytes << ",\n"
        << "  \"candidate_pack_per_layer_bytes\": " << production_pack_per_layer_bytes << ",\n"
        << "  \"candidate_pack_48_layers_bytes\": " << production_pack_48_layers_bytes << ",\n"
        << "  \"folded_gate_pack_per_layer_bytes\": " << folded_pack_per_layer_bytes << ",\n"
        << "  \"folded_gate_pack_48_layers_bytes\": " << folded_pack_48_layers_bytes << ",\n"
        << "  \"device_global_mem_bytes\": " << global_mem_bytes << ",\n"
        << "  \"device_free_mem_before_bytes\": " << free_mem_before << ",\n"
        << "  \"device_free_mem_after_one_layer_bytes\": " << free_mem_after_one_layer << ",\n"
        << "  \"workspace_bytes\": " << workspace_info.bytes << ",\n"
        << "  \"qkv_module_vs_integrated_max_abs\": " << qkv_integrated_delta.max_abs << ",\n"
        << "  \"z_module_vs_integrated_max_abs\": " << z_integrated_delta.max_abs << ",\n"
        << "  \"qkv_module_vs_generic_max_abs\": " << qkv_production_delta.max_abs << ",\n"
        << "  \"z_module_vs_generic_max_abs\": " << z_production_delta.max_abs << ",\n"
        << "  \"alpha_module_vs_integrated_max_abs\": " << alpha_integrated_delta.max_abs << ",\n"
        << "  \"alpha_module_vs_integrated_max_rel\": " << alpha_integrated_delta.max_rel << ",\n"
        << "  \"alpha_module_vs_integrated_rms\": " << alpha_integrated_delta.rms << ",\n"
        << "  \"beta_module_vs_integrated_max_abs\": " << beta_integrated_delta.max_abs << ",\n"
        << "  \"beta_module_vs_integrated_max_rel\": " << beta_integrated_delta.max_rel << ",\n"
        << "  \"beta_module_vs_integrated_rms\": " << beta_integrated_delta.rms << ",\n"
        << "  \"folded_gate_module_vs_active_max_abs\": " << gate_integrated_delta.max_abs << ",\n"
        << "  \"folded_gate_module_vs_active_max_rel\": " << gate_integrated_delta.max_rel << ",\n"
        << "  \"folded_gate_module_vs_active_rms\": " << gate_integrated_delta.rms << ",\n"
        << "  \"invalid_layout_fallback_safe\": " << (fallback_safe ? "true" : "false") << ",\n"
        << "  \"warmup_rounds\": " << warmup_rounds << ",\n"
        << "  \"iterations\": " << iterations << ",\n"
        << "  \"active_integrated_four_op_median_us\": " << integrated_median << ",\n"
        << "  \"joint_qkvzab_candidate_median_us\": " << candidate_median << ",\n"
        << "  \"speedup_vs_active_four_op\": " << active_speedup << ",\n"
        << "  \"saving_per_layer_us\": " << saving_per_layer_us << ",\n"
        << "  \"projected_cycle_saving_ms\": " << projected_cycle_saving_ms << ",\n"
        << "  \"active_full_gate_sequence_median_us\": " << active_gate_median << ",\n"
        << "  \"folded_gate_candidate_median_us\": " << candidate_gate_median << ",\n"
        << "  \"folded_gate_saving_per_layer_us\": " << gate_saving_per_layer_us << ",\n"
        << "  \"folded_gate_projected_cycle_saving_ms\": " << gate_projected_cycle_saving_ms << ",\n"
        << "  \"q4_numerical_exact_vs_active\": " << (q4_exact ? "true" : "false") << ",\n"
        << "  \"f32_semantics_tight\": " << (f32_tight ? "true" : "false") << ",\n"
        << "  \"folded_gate_semantics_tight\": " << (gate_semantics_tight ? "true" : "false") << ",\n"
        << "  \"projected_cycle_gate_ge_2ms\": " << (speed_gate ? "true" : "false") << ",\n"
        << "  \"folded_gate_projected_cycle_gate_ge_2ms\": " << (folded_speed_gate ? "true" : "false") << ",\n"
        << "  \"qkvzab_folded_gate\": \"" << (gate ? "PASS" : "FAIL") << "\"\n"
        << "}\n";

    for (void *pointer : {d_qkv_dpas, d_z_dpas, d_qkv_prod, d_z_prod,
            static_cast<void *>(d_alpha_beta),
            static_cast<void *>(d_ssm_a), static_cast<void *>(d_ssm_dt),
            static_cast<void *>(d_input), static_cast<void *>(d_prod_q8),
            static_cast<void *>(d_int_qkv), static_cast<void *>(d_int_z),
            static_cast<void *>(d_int_alpha), static_cast<void *>(d_int_beta),
            static_cast<void *>(d_int_gate), static_cast<void *>(d_gate_temporary),
            static_cast<void *>(d_mod_qkv), static_cast<void *>(d_mod_z),
            static_cast<void *>(d_mod_alpha), static_cast<void *>(d_mod_beta),
            static_cast<void *>(d_mod_gate),
            static_cast<void *>(d_prod_qkv_out), static_cast<void *>(d_prod_z_out), workspace}) {
        sycl::free(pointer, queue);
    }
    dlclose(module_handle);
    return gate ? 0 : 3;
} catch (const std::exception &error) {
    std::cerr << "gdn-qkvzab-module-compare error: " << error.what() << '\n';
    return 1;
}
