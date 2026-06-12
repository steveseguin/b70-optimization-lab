#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <sstream>
#include <unordered_map>
#include <vector>

#include "example_utils.hpp"
#include "oneapi/dnnl/dnnl.hpp"
#include "oneapi/dnnl/dnnl_sycl.hpp"
#include <sycl/sycl.hpp>

using namespace dnnl;

namespace {

struct Meta {
    std::string name;
    int64_t num_experts = 0;
    int64_t total_tokens = 0;
    int64_t k = 0;
    int64_t n = 0;
    std::string dst_dtype = "bf16";
    std::string weight_format = "abc";
    std::unordered_map<std::string, std::string> paths;
};

struct Stats {
    double mean_us = 0.0;
    double min_us = 0.0;
    double p50_us = 0.0;
    double p90_us = 0.0;
    double max_us = 0.0;
};

struct ManifestPair {
    std::filesystem::path gemm1_meta;
    std::filesystem::path gemm2_meta;
};

struct GatherWindow {
    std::filesystem::path base;
    std::vector<uint8_t> expected_output;
    std::vector<uint8_t> output;
    int64_t rows = 0;
    int64_t topk = 0;
    int64_t hidden_size = 0;
    memory topk_weights_mem;
    memory unpermuted_mem;
    memory output_mem;
};

std::string env_string(const char *name, const std::string &fallback = "") {
    const char *value = std::getenv(name);
    if (!value || !*value) return fallback;
    return std::string(value);
}

int env_int(const char *name, int fallback) {
    const char *value = std::getenv(name);
    if (!value || !*value) return fallback;
    return std::stoi(value);
}

std::string json_escape(const std::string &value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (char c : value) {
        if (c == '\\' || c == '"') out.push_back('\\');
        out.push_back(c);
    }
    return out;
}

std::string trim_copy(const std::string &value) {
    const auto begin = value.find_first_not_of(" \t\r\n");
    if (begin == std::string::npos) return "";
    const auto end = value.find_last_not_of(" \t\r\n");
    return value.substr(begin, end - begin + 1);
}

std::vector<ManifestPair> read_manifest(const std::filesystem::path &path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("failed to open manifest: " + path.string());
    std::vector<ManifestPair> pairs;
    const auto base = path.parent_path();
    std::string line;
    int line_no = 0;
    while (std::getline(in, line)) {
        ++line_no;
        line = trim_copy(line);
        if (line.empty() || line[0] == '#') continue;
        const auto comma = line.find(',');
        if (comma == std::string::npos) {
            throw std::runtime_error("manifest line " + std::to_string(line_no)
                    + " missing comma separator");
        }
        std::filesystem::path gemm1 = trim_copy(line.substr(0, comma));
        std::filesystem::path gemm2 = trim_copy(line.substr(comma + 1));
        if (gemm1.is_relative()) gemm1 = base / gemm1;
        if (gemm2.is_relative()) gemm2 = base / gemm2;
        pairs.push_back({gemm1, gemm2});
    }
    if (pairs.empty()) {
        throw std::runtime_error("manifest has no window pairs: " + path.string());
    }
    return pairs;
}

memory::data_type parse_dst_dtype(const std::string &value) {
    if (value == "bf16") return memory::data_type::bf16;
    if (value == "fp16" || value == "f16") return memory::data_type::f16;
    if (value == "f32") return memory::data_type::f32;
    throw std::runtime_error("unsupported dst_dtype: " + value);
}

memory::format_tag parse_weight_format(const std::string &value) {
    if (value == "abc") return memory::format_tag::abc;
    if (value == "acb") return memory::format_tag::acb;
    throw std::runtime_error("unsupported weight_format: " + value);
}

size_t dtype_size(memory::data_type dt) {
    switch (dt) {
    case memory::data_type::f32: return 4;
    case memory::data_type::bf16:
    case memory::data_type::f16: return 2;
    case memory::data_type::s8: return 1;
    default: throw std::runtime_error("unsupported dtype size");
    }
}

std::vector<uint8_t> read_file(const std::filesystem::path &path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("failed to open " + path.string());
    in.seekg(0, std::ios::end);
    const auto size = in.tellg();
    if (size < 0) throw std::runtime_error("failed to size " + path.string());
    in.seekg(0, std::ios::beg);
    std::vector<uint8_t> data(static_cast<size_t>(size));
    if (!data.empty()) {
        in.read(reinterpret_cast<char *>(data.data()), size);
        if (!in) throw std::runtime_error("failed to read " + path.string());
    }
    return data;
}

void expect_size(const std::string &name, const std::vector<uint8_t> &data,
        size_t expected) {
    if (data.size() != expected) {
        throw std::runtime_error(name + " size " + std::to_string(data.size())
                + " expected " + std::to_string(expected));
    }
}

Meta read_meta(const std::filesystem::path &path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("failed to open meta: " + path.string());
    Meta meta;
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        const auto pos = line.find('=');
        if (pos == std::string::npos) continue;
        const std::string key = line.substr(0, pos);
        const std::string value = line.substr(pos + 1);
        if (key == "name") meta.name = value;
        else if (key == "num_experts") meta.num_experts = std::stoll(value);
        else if (key == "total_tokens") meta.total_tokens = std::stoll(value);
        else if (key == "k") meta.k = std::stoll(value);
        else if (key == "n") meta.n = std::stoll(value);
        else if (key == "dst_dtype") meta.dst_dtype = value;
        else if (key == "weight_format") meta.weight_format = value;
        else meta.paths[key] = value;
    }
    if (meta.name.empty() || meta.num_experts <= 0 || meta.total_tokens <= 0
            || meta.k <= 0 || meta.n <= 0) {
        throw std::runtime_error("incomplete meta: " + path.string());
    }
    return meta;
}

std::vector<int32_t> cumulative_offsets(const std::vector<uint8_t> &rows_data,
        int64_t num_experts, int64_t expected_total) {
    expect_size("rows", rows_data, static_cast<size_t>(num_experts) * sizeof(int32_t));
    const auto *rows = reinterpret_cast<const int32_t *>(rows_data.data());
    std::vector<int32_t> offsets(static_cast<size_t>(num_experts), 0);
    int64_t total = 0;
    for (int64_t i = 0; i < num_experts; ++i) {
        total += rows[i];
        offsets[static_cast<size_t>(i)] = static_cast<int32_t>(total);
    }
    if (total != expected_total) {
        throw std::runtime_error("rows total " + std::to_string(total)
                + " expected " + std::to_string(expected_total));
    }
    return offsets;
}

std::vector<std::vector<int32_t>> load_count_windows(
        const std::string &path, int64_t expected_experts, int64_t expected_total) {
    std::vector<std::vector<int32_t>> windows;
    if (path.empty()) return windows;

    std::ifstream in(path);
    if (!in) throw std::runtime_error("failed to open route counts: " + path);

    std::string line;
    int line_no = 0;
    while (std::getline(in, line)) {
        ++line_no;
        if (line.empty()) continue;
        std::vector<int32_t> counts;
        std::stringstream ss(line);
        std::string item;
        while (std::getline(ss, item, ',')) {
            if (!item.empty()) counts.push_back(std::stoi(item));
        }
        if (static_cast<int64_t>(counts.size()) != expected_experts) {
            throw std::runtime_error("route-count line " + std::to_string(line_no)
                    + " has " + std::to_string(counts.size()) + " experts, expected "
                    + std::to_string(expected_experts));
        }
        const int total = std::accumulate(counts.begin(), counts.end(), 0);
        if (total != expected_total) {
            throw std::runtime_error("route-count line " + std::to_string(line_no)
                    + " total " + std::to_string(total) + ", expected "
                    + std::to_string(expected_total));
        }
        windows.push_back(std::move(counts));
    }
    if (windows.empty()) {
        throw std::runtime_error("route-count file had no windows: " + path);
    }
    return windows;
}

double raw_checksum(const std::vector<uint8_t> &data, memory::data_type dt) {
    const size_t elements = data.size() / dtype_size(dt);
    double sum = 0.0;
    if (dt == memory::data_type::f32) {
        const auto *ptr = reinterpret_cast<const float *>(data.data());
        for (size_t i = 0; i < elements; ++i) sum += double(ptr[i]);
    } else if (dt == memory::data_type::bf16 || dt == memory::data_type::f16) {
        const auto *ptr = reinterpret_cast<const uint16_t *>(data.data());
        for (size_t i = 0; i < elements; ++i) sum += double(ptr[i]);
    } else {
        const auto *ptr = reinterpret_cast<const int8_t *>(data.data());
        for (size_t i = 0; i < elements; ++i) sum += double(ptr[i]);
    }
    return sum;
}

uint64_t raw_diff_count(const std::vector<uint8_t> &a, const std::vector<uint8_t> &b) {
    if (a.size() != b.size()) {
        throw std::runtime_error("raw diff size mismatch");
    }
    uint64_t diff = 0;
    for (size_t i = 0; i < a.size(); ++i) {
        if (a[i] != b[i]) ++diff;
    }
    return diff;
}

void launch_exact_silu_quant_bf16_to_int8(sycl::queue &queue,
        memory &gemm1_dst_mem, memory &gemm2_src_mem,
        memory &gemm2_src_scales_mem, int64_t rows, int64_t input_cols) {
    if (input_cols % 2 != 0) {
        throw std::runtime_error("silu quant input cols must be even");
    }
    const int64_t cols = input_cols / 2;
    if (rows <= 0 || cols <= 0) return;

    using bf16 = sycl::ext::oneapi::bfloat16;
    const auto *input = reinterpret_cast<const bf16 *>(
            gemm1_dst_mem.get_data_handle(0));
    auto *q = reinterpret_cast<int8_t *>(gemm2_src_mem.get_data_handle(0));
    auto *scales = reinterpret_cast<float *>(
            gemm2_src_scales_mem.get_data_handle());
    if (!input || !q || !scales) {
        throw std::runtime_error("oneDNN memory handle for silu quant was null");
    }

    constexpr int kBlockSize = 256;
    const sycl::range<1> local(kBlockSize);
    const sycl::range<1> global(rows * kBlockSize);
    queue.submit([&](sycl::handler &cgh) {
        sycl::local_accessor<float, 1> local_max(local, cgh);
        cgh.parallel_for(sycl::nd_range<1>(global, local),
                [=](sycl::nd_item<1> item)
                        [[sycl::reqd_sub_group_size(16)]] {
                    const int64_t row = item.get_group(0);
                    const int local_id = item.get_local_id(0);
                    const int local_range = item.get_local_range(0);
                    const int64_t input_row_offset = row * cols * 2;
                    const int64_t output_row_offset = row * cols;

                    float thread_max = 0.0f;
                    for (int64_t col = local_id; col < cols;
                            col += local_range) {
                        const bf16 gate_b = input[input_row_offset + col];
                        const bf16 up_b = input[input_row_offset + cols + col];
                        const float gate_f = static_cast<float>(gate_b);
                        const bf16 silu_b = static_cast<bf16>(
                                gate_f / (1.0f + sycl::exp(-gate_f)));
                        const bf16 value_b = static_cast<bf16>(silu_b * up_b);
                        const float value = static_cast<float>(value_b);
                        thread_max = sycl::fmax(thread_max, sycl::fabs(value));
                    }

                    local_max[local_id] = thread_max;
                    item.barrier(sycl::access::fence_space::local_space);

                    for (int stride = local_range / 2; stride > 0;
                            stride >>= 1) {
                        if (local_id < stride) {
                            local_max[local_id] = sycl::fmax(
                                    local_max[local_id],
                                    local_max[local_id + stride]);
                        }
                        item.barrier(sycl::access::fence_space::local_space);
                    }

                    const float absmax = sycl::fmax(local_max[0], 1.0e-10f);
                    if (local_id == 0) {
                        scales[row] = absmax / 127.0f;
                    }
                    const float inv_scale = 127.0f / absmax;

                    for (int64_t col = local_id; col < cols;
                            col += local_range) {
                        const bf16 gate_b = input[input_row_offset + col];
                        const bf16 up_b = input[input_row_offset + cols + col];
                        const float gate_f = static_cast<float>(gate_b);
                        const bf16 silu_b = static_cast<bf16>(
                                gate_f / (1.0f + sycl::exp(-gate_f)));
                        const bf16 value_b = static_cast<bf16>(silu_b * up_b);
                        float quantized =
                                sycl::round(static_cast<float>(value_b)
                                        * inv_scale);
                        quantized = sycl::fmin(
                                127.0f, sycl::fmax(-127.0f, quantized));
                        q[output_row_offset + col] =
                                static_cast<int8_t>(quantized);
                    }
                });
    });
}

void launch_moe_gather_bf16(sycl::queue &queue, memory &gemm2_dst_mem,
        GatherWindow &gather) {
    using bf16 = sycl::ext::oneapi::bfloat16;
    if (gather.hidden_size % 8 != 0) {
        throw std::runtime_error("gather hidden_size must be divisible by 8");
    }
    const auto *moe_output = reinterpret_cast<const bf16 *>(
            gemm2_dst_mem.get_data_handle(0));
    const auto *topk_weights = reinterpret_cast<const float *>(
            gather.topk_weights_mem.get_data_handle());
    const auto *unpermuted = reinterpret_cast<const int32_t *>(
            gather.unpermuted_mem.get_data_handle());
    auto *output = reinterpret_cast<bf16 *>(
            gather.output_mem.get_data_handle());
    if (!moe_output || !topk_weights || !unpermuted || !output) {
        throw std::runtime_error("oneDNN memory handle for gather was null");
    }

    constexpr int kGroupWorkItem = 256;
    constexpr int kElemsPerItem = 8;
    constexpr int kStride = kGroupWorkItem * kElemsPerItem;
    const int64_t rows = gather.rows;
    const int64_t topk = gather.topk;
    const int64_t hidden_size = gather.hidden_size;

    queue.submit([&](sycl::handler &cgh) {
        cgh.parallel_for(sycl::nd_range<1>(
                sycl::range<1>(rows * kGroupWorkItem),
                sycl::range<1>(kGroupWorkItem)),
                [=](sycl::nd_item<1> item)
                        [[sycl::reqd_sub_group_size(32)]] {
                    const int64_t token_idx = item.get_group(0);
                    const int local_id = item.get_local_id(0);
                    const int64_t loop_count =
                            (hidden_size + kStride - 1) / kStride;
                    for (int64_t i = 0; i < loop_count; ++i) {
                        const int64_t hidden_idx =
                                i * kStride + local_id * kElemsPerItem;
                        if (hidden_idx >= hidden_size) continue;
                        float accum[kElemsPerItem];
#pragma unroll
                        for (int e = 0; e < kElemsPerItem; ++e) {
                            accum[e] = 0.0f;
                        }
                        for (int64_t k = 0; k < topk; ++k) {
                            const int32_t moe_id =
                                    unpermuted[token_idx * topk + k];
                            if (moe_id == -1) continue;
                            const float score =
                                    topk_weights[token_idx * topk + k];
#pragma unroll
                            for (int e = 0; e < kElemsPerItem; ++e) {
                                accum[e] += static_cast<float>(
                                        moe_output[static_cast<int64_t>(moe_id)
                                                        * hidden_size
                                                + hidden_idx + e])
                                        * score;
                            }
                        }
#pragma unroll
                        for (int e = 0; e < kElemsPerItem; ++e) {
                            output[token_idx * hidden_size + hidden_idx + e] =
                                    accum[e];
                        }
                    }
                });
    });
}

Stats summarize(const std::vector<double> &samples) {
    if (samples.empty()) throw std::runtime_error("no samples");
    std::vector<double> sorted = samples;
    std::sort(sorted.begin(), sorted.end());
    const double sum = std::accumulate(samples.begin(), samples.end(), 0.0);
    auto pct = [&](double p) {
        const size_t idx = std::min(sorted.size() - 1,
                static_cast<size_t>((sorted.size() - 1) * p + 0.5));
        return sorted[idx];
    };
    return {
        sum / double(samples.size()),
        sorted.front(),
        pct(0.50),
        pct(0.90),
        sorted.back(),
    };
}

class ResidentCase {
  public:
    ResidentCase(engine &eng, const std::filesystem::path &meta_path,
            const std::string &weight_format_name)
        : meta_path_(meta_path),
          meta_(read_meta(meta_path)),
          base_(meta_path.parent_path()),
          dst_dt_(parse_dst_dtype(meta_.dst_dtype)),
          weight_format_name_(weight_format_name.empty() ? meta_.weight_format
                                                         : weight_format_name),
          weight_format_(parse_weight_format(weight_format_name_)) {
        auto path_for = [&](const std::string &key) {
            auto it = meta_.paths.find(key);
            if (it == meta_.paths.end()) {
                throw std::runtime_error("missing path key: " + key);
            }
            return base_ / it->second;
        };

        a_data_ = read_file(path_for("a_path"));
        a_scales_data_ = read_file(path_for("a_scales_path"));
        std::string b_path_key = env_string("ONEDNN_B_PATH_KEY");
        if (b_path_key.empty()) {
            b_path_key = (weight_format_name_ == "acb"
                            && meta_.paths.find("b_acb_path") != meta_.paths.end())
                    ? "b_acb_path"
                    : "b_path";
        }
        b_path_key_ = b_path_key;
        b_data_ = read_file(path_for(b_path_key_));
        b_scales_data_ = read_file(path_for("b_scales_path"));
        rows_data_ = read_file(path_for("rows_path"));
        expected_output_ = read_file(path_for("xpu_out_path"));
        offsets_ = cumulative_offsets(rows_data_, meta_.num_experts, meta_.total_tokens);

        expect_size("A", a_data_, static_cast<size_t>(meta_.total_tokens * meta_.k));
        expect_size("A scales", a_scales_data_,
                static_cast<size_t>(meta_.total_tokens) * sizeof(float));
        expect_size("B", b_data_,
                static_cast<size_t>(meta_.num_experts * meta_.k * meta_.n));
        expect_size("B scales", b_scales_data_,
                static_cast<size_t>(meta_.num_experts * meta_.n) * sizeof(float));
        expect_size("expected output", expected_output_,
                static_cast<size_t>(meta_.total_tokens * meta_.n) * dtype_size(dst_dt_));

        const memory::dims src_dims = {meta_.total_tokens, meta_.k};
        const memory::dims weights_dims = {meta_.num_experts, meta_.k, meta_.n};
        const memory::dims dst_dims = {meta_.total_tokens, meta_.n};

        src_md_ = memory::desc::grouped(
                src_dims, memory::data_type::s8, 0, meta_.num_experts);
        dst_md_ = memory::desc::grouped(dst_dims, dst_dt_, 0, meta_.num_experts);
        weights_md_ = memory::desc(weights_dims, memory::data_type::s8,
                weight_format_);

        primitive_attr attr;
        attr.set_scales_mask(DNNL_ARG_SRC, 1 << 0);
        attr.set_scales_mask(DNNL_ARG_WEIGHTS, (1 << 0) | (1 << 2));

        const auto start = std::chrono::steady_clock::now();
        pd_ = matmul::primitive_desc(eng, src_md_, weights_md_, dst_md_, attr);
        prim_ = matmul(pd_);
        src_mem_ = memory(src_md_, eng);
        dst_mem_ = memory(dst_md_, eng);
        weights_mem_ = memory(weights_md_, eng);
        src_scales_mem_ = memory(
                memory::desc({meta_.total_tokens}, memory::data_type::f32,
                        memory::format_tag::a),
                eng);
        weights_scales_mem_ = memory(
                memory::desc({meta_.num_experts, meta_.n}, memory::data_type::f32,
                        memory::format_tag::ab),
                eng);
        const auto end = std::chrono::steady_clock::now();
        construct_us_ = std::chrono::duration_cast<std::chrono::microseconds>(
                end - start).count();

        output_.assign(
                static_cast<size_t>(meta_.total_tokens * meta_.n) * dtype_size(dst_dt_),
                0);
        write_to_dnnl_memory(a_data_.data(), src_mem_);
        write_to_dnnl_memory(b_data_.data(), weights_mem_);
        write_to_dnnl_memory(output_.data(), dst_mem_);
        write_to_dnnl_memory(offsets_.data(), src_mem_, 1);
        write_to_dnnl_memory(offsets_.data(), dst_mem_, 1);
        write_to_dnnl_memory(a_scales_data_.data(), src_scales_mem_);
        write_to_dnnl_memory(b_scales_data_.data(), weights_scales_mem_);

        args_ = {
                {DNNL_ARG_SRC, src_mem_},
                {DNNL_ARG_WEIGHTS, weights_mem_},
                {DNNL_ARG_DST, dst_mem_},
                {DNNL_ARG_ATTR_SCALES | DNNL_ARG_SRC, src_scales_mem_},
                {DNNL_ARG_ATTR_SCALES | DNNL_ARG_WEIGHTS, weights_scales_mem_},
        };
    }

    void execute(stream &engine_stream) { prim_.execute(engine_stream, args_); }

    void read_output() { read_from_dnnl_memory(output_.data(), dst_mem_); }

    void update_counts(const std::vector<int32_t> &tokens_per_expert) {
        if (static_cast<int64_t>(tokens_per_expert.size()) != meta_.num_experts) {
            throw std::runtime_error(meta_.name + " count window expert mismatch");
        }
        const int total = std::accumulate(
                tokens_per_expert.begin(), tokens_per_expert.end(), 0);
        if (total != meta_.total_tokens) {
            throw std::runtime_error(meta_.name + " count window token total mismatch");
        }
        int64_t cumulative = 0;
        for (int64_t i = 0; i < meta_.num_experts; ++i) {
            cumulative += tokens_per_expert[static_cast<size_t>(i)];
            offsets_[static_cast<size_t>(i)] = static_cast<int32_t>(cumulative);
        }
        write_to_dnnl_memory(offsets_.data(), src_mem_, 1);
        write_to_dnnl_memory(offsets_.data(), dst_mem_, 1);
    }

    const Meta &meta() const { return meta_; }
    const std::string &b_path_key() const { return b_path_key_; }
    const std::string &weight_format_name() const { return weight_format_name_; }
    int64_t construct_us() const { return construct_us_; }
    memory::data_type dst_dtype() const { return dst_dt_; }
    const std::vector<uint8_t> &output() const { return output_; }
    const std::vector<uint8_t> &expected_output() const { return expected_output_; }

  private:
    std::filesystem::path meta_path_;
    Meta meta_;
    std::filesystem::path base_;
    memory::data_type dst_dt_;
    std::string weight_format_name_;
    memory::format_tag weight_format_;
    std::string b_path_key_;
    int64_t construct_us_ = 0;

    std::vector<uint8_t> a_data_;
    std::vector<uint8_t> a_scales_data_;
    std::vector<uint8_t> b_data_;
    std::vector<uint8_t> b_scales_data_;
    std::vector<uint8_t> rows_data_;
    std::vector<uint8_t> expected_output_;
    std::vector<uint8_t> output_;
    std::vector<int32_t> offsets_;

    memory::desc src_md_;
    memory::desc dst_md_;
    memory::desc weights_md_;
    matmul::primitive_desc pd_;
    matmul prim_;
    memory src_mem_;
    memory dst_mem_;
    memory weights_mem_;
    memory src_scales_mem_;
    memory weights_scales_mem_;
    std::unordered_map<int, memory> args_;
};

class WindowedResidentCase {
  public:
    struct Window {
        std::filesystem::path meta_path;
        Meta meta;
        std::vector<uint8_t> expected_output;
        std::vector<uint8_t> output;
        std::vector<int32_t> offsets;
        memory src_mem;
        memory dst_mem;
        memory src_scales_mem;
        std::unordered_map<int, memory> args;
    };

    WindowedResidentCase(engine &eng,
            const std::vector<std::filesystem::path> &meta_paths,
            const std::string &weight_format_name)
        : dst_dt_(memory::data_type::undef) {
        if (meta_paths.empty()) {
            throw std::runtime_error("WindowedResidentCase requires meta paths");
        }
        base_meta_path_ = meta_paths.front();
        base_meta_ = read_meta(base_meta_path_);
        base_ = base_meta_path_.parent_path();
        dst_dt_ = parse_dst_dtype(base_meta_.dst_dtype);
        weight_format_name_ = weight_format_name.empty()
                ? base_meta_.weight_format
                : weight_format_name;
        weight_format_ = parse_weight_format(weight_format_name_);

        auto path_for_base = [&](const std::string &key) {
            auto it = base_meta_.paths.find(key);
            if (it == base_meta_.paths.end()) {
                throw std::runtime_error("missing path key: " + key);
            }
            return base_ / it->second;
        };

        std::string b_path_key = env_string("ONEDNN_B_PATH_KEY");
        if (b_path_key.empty()) {
            b_path_key = (weight_format_name_ == "acb"
                            && base_meta_.paths.find("b_acb_path")
                                    != base_meta_.paths.end())
                    ? "b_acb_path"
                    : "b_path";
        }
        b_path_key_ = b_path_key;
        b_data_ = read_file(path_for_base(b_path_key_));
        b_scales_data_ = read_file(path_for_base("b_scales_path"));
        expect_size("B", b_data_,
                static_cast<size_t>(
                        base_meta_.num_experts * base_meta_.k * base_meta_.n));
        expect_size("B scales", b_scales_data_,
                static_cast<size_t>(base_meta_.num_experts * base_meta_.n)
                        * sizeof(float));

        const memory::dims src_dims = {base_meta_.total_tokens, base_meta_.k};
        const memory::dims weights_dims = {
                base_meta_.num_experts, base_meta_.k, base_meta_.n};
        const memory::dims dst_dims = {base_meta_.total_tokens, base_meta_.n};

        src_md_ = memory::desc::grouped(
                src_dims, memory::data_type::s8, 0, base_meta_.num_experts);
        dst_md_ = memory::desc::grouped(
                dst_dims, dst_dt_, 0, base_meta_.num_experts);
        weights_md_ = memory::desc(weights_dims, memory::data_type::s8,
                weight_format_);

        primitive_attr attr;
        attr.set_scales_mask(DNNL_ARG_SRC, 1 << 0);
        attr.set_scales_mask(DNNL_ARG_WEIGHTS, (1 << 0) | (1 << 2));

        const auto start = std::chrono::steady_clock::now();
        pd_ = matmul::primitive_desc(eng, src_md_, weights_md_, dst_md_, attr);
        prim_ = matmul(pd_);
        weights_mem_ = memory(weights_md_, eng);
        weights_scales_mem_ = memory(
                memory::desc({base_meta_.num_experts, base_meta_.n},
                        memory::data_type::f32, memory::format_tag::ab),
                eng);
        const auto end = std::chrono::steady_clock::now();
        construct_us_ = std::chrono::duration_cast<std::chrono::microseconds>(
                end - start).count();

        write_to_dnnl_memory(b_data_.data(), weights_mem_);
        write_to_dnnl_memory(b_scales_data_.data(), weights_scales_mem_);

        windows_.reserve(meta_paths.size());
        for (const auto &meta_path : meta_paths) {
            windows_.push_back(load_window(eng, meta_path));
        }
    }

    void execute_window(stream &engine_stream, size_t index) {
        prim_.execute(engine_stream, windows_.at(index).args);
    }

    void read_window_output(size_t index) {
        auto &window = windows_.at(index);
        read_from_dnnl_memory(window.output.data(), window.dst_mem);
    }

    uint64_t window_diff_count(size_t index) const {
        const auto &window = windows_.at(index);
        return raw_diff_count(window.output, window.expected_output);
    }

    double window_checksum(size_t index) const {
        return raw_checksum(windows_.at(index).output, dst_dt_);
    }

    double window_expected_checksum(size_t index) const {
        return raw_checksum(windows_.at(index).expected_output, dst_dt_);
    }

    size_t window_count() const { return windows_.size(); }
    const Meta &base_meta() const { return base_meta_; }
    const Window &window(size_t index) const { return windows_.at(index); }
    memory &src_memory(size_t index) { return windows_.at(index).src_mem; }
    memory &dst_memory(size_t index) { return windows_.at(index).dst_mem; }
    memory &src_scales_memory(size_t index) {
        return windows_.at(index).src_scales_mem;
    }
    const std::string &b_path_key() const { return b_path_key_; }
    const std::string &weight_format_name() const { return weight_format_name_; }
    int64_t construct_us() const { return construct_us_; }

  private:
    Window load_window(engine &eng, const std::filesystem::path &meta_path) {
        Window window;
        window.meta_path = meta_path;
        window.meta = read_meta(meta_path);
        validate_window_meta(window.meta, meta_path);
        const auto base = meta_path.parent_path();
        auto path_for = [&](const std::string &key) {
            auto it = window.meta.paths.find(key);
            if (it == window.meta.paths.end()) {
                throw std::runtime_error("missing path key: " + key);
            }
            return base / it->second;
        };

        auto a_data = read_file(path_for("a_path"));
        auto a_scales_data = read_file(path_for("a_scales_path"));
        const auto rows_data = read_file(path_for("rows_path"));
        window.expected_output = read_file(path_for("xpu_out_path"));
        window.offsets = cumulative_offsets(
                rows_data, window.meta.num_experts, window.meta.total_tokens);
        expect_size("A", a_data,
                static_cast<size_t>(window.meta.total_tokens * window.meta.k));
        expect_size("A scales", a_scales_data,
                static_cast<size_t>(window.meta.total_tokens) * sizeof(float));
        expect_size("expected output", window.expected_output,
                static_cast<size_t>(window.meta.total_tokens * window.meta.n)
                        * dtype_size(dst_dt_));

        window.output.assign(window.expected_output.size(), 0);
        window.src_mem = memory(src_md_, eng);
        window.dst_mem = memory(dst_md_, eng);
        window.src_scales_mem = memory(
                memory::desc({window.meta.total_tokens}, memory::data_type::f32,
                        memory::format_tag::a),
                eng);

        write_to_dnnl_memory(a_data.data(), window.src_mem);
        write_to_dnnl_memory(window.output.data(), window.dst_mem);
        write_to_dnnl_memory(window.offsets.data(), window.src_mem, 1);
        write_to_dnnl_memory(window.offsets.data(), window.dst_mem, 1);
        write_to_dnnl_memory(a_scales_data.data(), window.src_scales_mem);

        window.args = {
                {DNNL_ARG_SRC, window.src_mem},
                {DNNL_ARG_WEIGHTS, weights_mem_},
                {DNNL_ARG_DST, window.dst_mem},
                {DNNL_ARG_ATTR_SCALES | DNNL_ARG_SRC,
                        window.src_scales_mem},
                {DNNL_ARG_ATTR_SCALES | DNNL_ARG_WEIGHTS,
                        weights_scales_mem_},
        };
        return window;
    }

    void validate_window_meta(
            const Meta &meta, const std::filesystem::path &meta_path) const {
        if (meta.num_experts != base_meta_.num_experts
                || meta.total_tokens != base_meta_.total_tokens
                || meta.k != base_meta_.k || meta.n != base_meta_.n
                || meta.dst_dtype != base_meta_.dst_dtype) {
            throw std::runtime_error("window meta shape mismatch: "
                    + meta_path.string());
        }
    }

    std::filesystem::path base_meta_path_;
    Meta base_meta_;
    std::filesystem::path base_;
    memory::data_type dst_dt_;
    std::string weight_format_name_;
    memory::format_tag weight_format_;
    std::string b_path_key_;
    int64_t construct_us_ = 0;

    std::vector<uint8_t> b_data_;
    std::vector<uint8_t> b_scales_data_;
    std::vector<Window> windows_;

    memory::desc src_md_;
    memory::desc dst_md_;
    memory::desc weights_md_;
    matmul::primitive_desc pd_;
    matmul prim_;
    memory weights_mem_;
    memory weights_scales_mem_;
};

GatherWindow load_gather_window(engine &eng,
        const WindowedResidentCase::Window &gemm2_window) {
    GatherWindow gather;
    gather.base = gemm2_window.meta_path.parent_path();
    const auto topk_weights_path = gather.base / "moe_topk_weights.f32.bin";
    const auto unpermuted_path = gather.base / "moe_unpermuted.i32.bin";
    const auto ref_output_path = gather.base / "moe_ref_output.bf16.bin";
    auto topk_weights_data = read_file(topk_weights_path);
    auto unpermuted_data = read_file(unpermuted_path);
    gather.expected_output = read_file(ref_output_path);
    gather.hidden_size = gemm2_window.meta.n;
    const size_t ref_element_size = dtype_size(memory::data_type::bf16);
    if (gather.expected_output.size()
            % (static_cast<size_t>(gather.hidden_size) * ref_element_size)
            != 0) {
        throw std::runtime_error("bad gather ref output size: "
                + ref_output_path.string());
    }
    gather.rows = static_cast<int64_t>(gather.expected_output.size()
            / (static_cast<size_t>(gather.hidden_size) * ref_element_size));
    if (gather.rows <= 0
            || gemm2_window.meta.total_tokens % gather.rows != 0) {
        throw std::runtime_error("bad gather rows/topk for "
                + gemm2_window.meta_path.string());
    }
    gather.topk = gemm2_window.meta.total_tokens / gather.rows;
    expect_size("gather topk weights", topk_weights_data,
            static_cast<size_t>(gather.rows * gather.topk) * sizeof(float));
    expect_size("gather unpermuted", unpermuted_data,
            static_cast<size_t>(gather.rows * gather.topk) * sizeof(int32_t));
    gather.output.assign(gather.expected_output.size(), 0);

    gather.topk_weights_mem = memory(
            memory::desc({gather.rows, gather.topk}, memory::data_type::f32,
                    memory::format_tag::ab),
            eng);
    gather.unpermuted_mem = memory(
            memory::desc({gather.rows, gather.topk}, memory::data_type::s32,
                    memory::format_tag::ab),
            eng);
    gather.output_mem = memory(
            memory::desc({gather.rows, gather.hidden_size},
                    memory::data_type::bf16, memory::format_tag::ab),
            eng);
    write_to_dnnl_memory(topk_weights_data.data(), gather.topk_weights_mem);
    write_to_dnnl_memory(unpermuted_data.data(), gather.unpermuted_mem);
    write_to_dnnl_memory(gather.output.data(), gather.output_mem);
    return gather;
}

void read_gather_output(GatherWindow &gather) {
    read_from_dnnl_memory(gather.output.data(), gather.output_mem);
}

void write_case_json(std::ofstream &json, const char *prefix,
        const ResidentCase &item, const std::vector<uint8_t> &output) {
    const uint64_t diff_count = raw_diff_count(output, item.expected_output());
    json << "  \"" << prefix << "\": {\n";
    json << "    \"name\": \"" << json_escape(item.meta().name) << "\",\n";
    json << "    \"num_experts\": " << item.meta().num_experts << ",\n";
    json << "    \"total_tokens\": " << item.meta().total_tokens << ",\n";
    json << "    \"k\": " << item.meta().k << ",\n";
    json << "    \"n\": " << item.meta().n << ",\n";
    json << "    \"dst_dtype\": \"" << json_escape(item.meta().dst_dtype) << "\",\n";
    json << "    \"weight_format\": \"" << json_escape(item.weight_format_name()) << "\",\n";
    json << "    \"b_path_key\": \"" << json_escape(item.b_path_key()) << "\",\n";
    json << "    \"construct_us\": " << item.construct_us() << ",\n";
    json << "    \"raw_checksum\": " << raw_checksum(output, item.dst_dtype()) << ",\n";
    json << "    \"expected_raw_checksum\": "
         << raw_checksum(item.expected_output(), item.dst_dtype()) << ",\n";
    json << "    \"raw_equal\": " << (diff_count == 0 ? "true" : "false") << ",\n";
    json << "    \"raw_diff_count\": " << diff_count << "\n";
    json << "  }";
}

void write_stats_json(std::ofstream &json, const char *prefix, const Stats &stats) {
    json << "  \"" << prefix << "\": {\n";
    json << "    \"mean_us\": " << stats.mean_us << ",\n";
    json << "    \"min_us\": " << stats.min_us << ",\n";
    json << "    \"p50_us\": " << stats.p50_us << ",\n";
    json << "    \"p90_us\": " << stats.p90_us << ",\n";
    json << "    \"max_us\": " << stats.max_us << "\n";
    json << "  }";
}

void run_manifest_pair(engine::kind engine_kind,
        const std::filesystem::path &manifest_path) {
    const auto manifest = read_manifest(manifest_path);
    const int warmup = env_int("ONEDNN_PAIR_WARMUP", 20);
    const int iterations = env_int("ONEDNN_PAIR_ITERATIONS", 200);
    const std::string weight_format = env_string("ONEDNN_WEIGHT_FORMAT", "acb");
    const bool include_activation_quant =
            env_int("ONEDNN_PAIR_INCLUDE_ACTIVATION_QUANT", 0) != 0;
    const bool include_gather =
            env_int("ONEDNN_PAIR_INCLUDE_GATHER", 0) != 0;
    const std::filesystem::path json_path = env_string(
            "ONEDNN_PAIR_JSON",
            (manifest_path.parent_path()
                    / "resident_multiwindow_pair_result.json")
                    .string());

    std::vector<std::filesystem::path> gemm1_paths;
    std::vector<std::filesystem::path> gemm2_paths;
    gemm1_paths.reserve(manifest.size());
    gemm2_paths.reserve(manifest.size());
    for (const auto &pair : manifest) {
        gemm1_paths.push_back(pair.gemm1_meta);
        gemm2_paths.push_back(pair.gemm2_meta);
    }

    engine eng(engine_kind, 0);
    stream engine_stream(eng);
    sycl::queue sycl_queue = sycl_interop::get_queue(engine_stream);

    WindowedResidentCase gemm1(eng, gemm1_paths, weight_format);
    WindowedResidentCase gemm2(eng, gemm2_paths, weight_format);
    if (gemm1.window_count() != gemm2.window_count()) {
        throw std::runtime_error("manifest GEMM window count mismatch");
    }
    const size_t window_count = gemm1.window_count();
    std::vector<GatherWindow> gather_windows;
    if (include_gather) {
        gather_windows.reserve(window_count);
        for (size_t i = 0; i < window_count; ++i) {
            gather_windows.push_back(load_gather_window(eng, gemm2.window(i)));
        }
    }

    for (int i = 0; i < warmup; ++i) {
        const size_t index = static_cast<size_t>(i) % window_count;
        gemm1.execute_window(engine_stream, index);
        if (include_activation_quant) {
            launch_exact_silu_quant_bf16_to_int8(sycl_queue,
                    gemm1.dst_memory(index), gemm2.src_memory(index),
                    gemm2.src_scales_memory(index), gemm1.window(index).meta.total_tokens,
                    gemm1.window(index).meta.n);
        }
        gemm2.execute_window(engine_stream, index);
        if (include_gather) {
            launch_moe_gather_bf16(sycl_queue, gemm2.dst_memory(index),
                    gather_windows.at(index));
        }
        engine_stream.wait();
    }

    std::vector<double> pair_samples;
    pair_samples.reserve(iterations);
    for (int i = 0; i < iterations; ++i) {
        const size_t index = static_cast<size_t>(i) % window_count;
        const auto start = std::chrono::steady_clock::now();
        gemm1.execute_window(engine_stream, index);
        if (include_activation_quant) {
            launch_exact_silu_quant_bf16_to_int8(sycl_queue,
                    gemm1.dst_memory(index), gemm2.src_memory(index),
                    gemm2.src_scales_memory(index), gemm1.window(index).meta.total_tokens,
                    gemm1.window(index).meta.n);
        }
        gemm2.execute_window(engine_stream, index);
        if (include_gather) {
            launch_moe_gather_bf16(sycl_queue, gemm2.dst_memory(index),
                    gather_windows.at(index));
        }
        engine_stream.wait();
        const auto end = std::chrono::steady_clock::now();
        pair_samples.push_back(std::chrono::duration<double, std::micro>(
                end - start).count());
    }
    const Stats pair_stats = summarize(pair_samples);

    uint64_t gemm1_total_diff = 0;
    uint64_t gemm2_total_diff = 0;
    uint64_t gather_total_diff = 0;
    uint64_t exact_windows = 0;
    uint64_t exact_full_windows = 0;
    for (size_t i = 0; i < window_count; ++i) {
        gemm1.read_window_output(i);
        gemm2.read_window_output(i);
        if (include_gather) {
            read_gather_output(gather_windows.at(i));
        }
        const uint64_t d1 = gemm1.window_diff_count(i);
        const uint64_t d2 = gemm2.window_diff_count(i);
        const uint64_t dg = include_gather
                ? raw_diff_count(gather_windows.at(i).output,
                        gather_windows.at(i).expected_output)
                : 0;
        gemm1_total_diff += d1;
        gemm2_total_diff += d2;
        gather_total_diff += dg;
        if (d1 == 0 && d2 == 0) ++exact_windows;
        if (d1 == 0 && d2 == 0 && (!include_gather || dg == 0)) {
            ++exact_full_windows;
        }
    }

    std::ofstream json(json_path);
    if (!json) throw std::runtime_error("failed to open json: " + json_path.string());
    json << std::fixed << std::setprecision(6);
    json << "{\n";
    json << "  \"kind\": \""
         << (include_activation_quant && include_gather
                    ? "resident_onednn_multiwindow_gemm1_silu_quant_gemm2_gather"
                    : include_activation_quant
                    ? "resident_onednn_multiwindow_gemm1_silu_quant_gemm2"
                    : include_gather
                    ? "resident_onednn_multiwindow_two_gemm_pair_gather"
                    : "resident_onednn_multiwindow_two_gemm_pair")
         << "\",\n";
    json << "  \"note\": \"Cycles real per-window A/scales/offsets from "
            "resident device memory with one resident primitive/weight set per "
            "GEMM. ";
    if (include_activation_quant) {
        json << "GEMM2 input/scales are generated from GEMM1 output by the "
                "runner's exact BF16 SiLU+INT8 quant bridge";
    } else {
        json << "GEMM2 input is the captured post-activation quantized input; "
                "activation is not included";
    }
    if (include_gather) {
        json << "; final top-k gather is included and compared against the "
                "exported xpu_fused_moe reference output.";
    } else {
        json << "; final gather is not included.";
    }
    json << "\",\n";
    json << "  \"manifest\": \"" << json_escape(manifest_path.string()) << "\",\n";
    json << "  \"warmup\": " << warmup << ",\n";
    json << "  \"iterations\": " << iterations << ",\n";
    json << "  \"include_activation_quant\": "
         << (include_activation_quant ? "true" : "false") << ",\n";
    json << "  \"include_gather\": "
         << (include_gather ? "true" : "false") << ",\n";
    json << "  \"window_count\": " << window_count << ",\n";
    json << "  \"exact_window_count\": " << exact_windows << ",\n";
    json << "  \"exact_full_window_count\": " << exact_full_windows << ",\n";
    json << "  \"all_gemm_windows_exact\": "
         << (exact_windows == window_count ? "true" : "false") << ",\n";
    json << "  \"all_full_windows_exact\": "
         << (exact_full_windows == window_count ? "true" : "false") << ",\n";
    json << "  \"gemm1_total_raw_diff_count\": " << gemm1_total_diff << ",\n";
    json << "  \"gemm2_total_raw_diff_count\": " << gemm2_total_diff << ",\n";
    json << "  \"gather_total_raw_diff_count\": " << gather_total_diff << ",\n";
    json << "  \"pair_mean_us\": " << pair_stats.mean_us << ",\n";
    json << "  \"pair_min_us\": " << pair_stats.min_us << ",\n";
    json << "  \"pair_p50_us\": " << pair_stats.p50_us << ",\n";
    json << "  \"pair_p90_us\": " << pair_stats.p90_us << ",\n";
    json << "  \"pair_max_us\": " << pair_stats.max_us << ",\n";
    json << "  \"pair_construct_us\": "
         << (gemm1.construct_us() + gemm2.construct_us()) << ",\n";
    json << "  \"gemm1\": {\n";
    json << "    \"name\": \"" << json_escape(gemm1.base_meta().name) << "\",\n";
    json << "    \"num_experts\": " << gemm1.base_meta().num_experts << ",\n";
    json << "    \"total_tokens\": " << gemm1.base_meta().total_tokens << ",\n";
    json << "    \"k\": " << gemm1.base_meta().k << ",\n";
    json << "    \"n\": " << gemm1.base_meta().n << ",\n";
    json << "    \"dst_dtype\": \""
         << json_escape(gemm1.base_meta().dst_dtype) << "\",\n";
    json << "    \"weight_format\": \""
         << json_escape(gemm1.weight_format_name()) << "\",\n";
    json << "    \"b_path_key\": \"" << json_escape(gemm1.b_path_key())
         << "\",\n";
    json << "    \"construct_us\": " << gemm1.construct_us() << "\n";
    json << "  },\n";
    json << "  \"gemm2\": {\n";
    json << "    \"name\": \"" << json_escape(gemm2.base_meta().name) << "\",\n";
    json << "    \"num_experts\": " << gemm2.base_meta().num_experts << ",\n";
    json << "    \"total_tokens\": " << gemm2.base_meta().total_tokens << ",\n";
    json << "    \"k\": " << gemm2.base_meta().k << ",\n";
    json << "    \"n\": " << gemm2.base_meta().n << ",\n";
    json << "    \"dst_dtype\": \""
         << json_escape(gemm2.base_meta().dst_dtype) << "\",\n";
    json << "    \"weight_format\": \""
         << json_escape(gemm2.weight_format_name()) << "\",\n";
    json << "    \"b_path_key\": \"" << json_escape(gemm2.b_path_key())
         << "\",\n";
    json << "    \"construct_us\": " << gemm2.construct_us() << "\n";
    json << "  },\n";
    json << "  \"windows\": [\n";
    for (size_t i = 0; i < window_count; ++i) {
        const uint64_t d1 = gemm1.window_diff_count(i);
        const uint64_t d2 = gemm2.window_diff_count(i);
        const uint64_t dg = include_gather
                ? raw_diff_count(gather_windows.at(i).output,
                        gather_windows.at(i).expected_output)
                : 0;
        json << "    {\n";
        json << "      \"index\": " << i << ",\n";
        json << "      \"gemm1_meta\": \""
             << json_escape(gemm1.window(i).meta_path.string()) << "\",\n";
        json << "      \"gemm2_meta\": \""
             << json_escape(gemm2.window(i).meta_path.string()) << "\",\n";
        json << "      \"gemm1_raw_equal\": " << (d1 == 0 ? "true" : "false")
             << ",\n";
        json << "      \"gemm1_raw_diff_count\": " << d1 << ",\n";
        json << "      \"gemm1_raw_checksum\": " << gemm1.window_checksum(i)
             << ",\n";
        json << "      \"gemm1_expected_raw_checksum\": "
             << gemm1.window_expected_checksum(i) << ",\n";
        json << "      \"gemm2_raw_equal\": " << (d2 == 0 ? "true" : "false")
             << ",\n";
        json << "      \"gemm2_raw_diff_count\": " << d2 << ",\n";
        json << "      \"gemm2_raw_checksum\": " << gemm2.window_checksum(i)
             << ",\n";
        json << "      \"gemm2_expected_raw_checksum\": "
             << gemm2.window_expected_checksum(i);
        if (include_gather) {
            json << ",\n";
            json << "      \"gather_rows\": "
                 << gather_windows.at(i).rows << ",\n";
            json << "      \"gather_topk\": "
                 << gather_windows.at(i).topk << ",\n";
            json << "      \"gather_raw_equal\": "
                 << (dg == 0 ? "true" : "false") << ",\n";
            json << "      \"gather_raw_diff_count\": " << dg << ",\n";
            json << "      \"gather_raw_checksum\": "
                 << raw_checksum(gather_windows.at(i).output,
                         memory::data_type::bf16)
                 << ",\n";
            json << "      \"gather_expected_raw_checksum\": "
                 << raw_checksum(gather_windows.at(i).expected_output,
                         memory::data_type::bf16) << "\n";
        } else {
            json << "\n";
        }
        json << "    }" << (i + 1 == window_count ? "\n" : ",\n");
    }
    json << "  ]\n";
    json << "}\n";

    std::cout << "ONEDNN_RESIDENT_MULTIWINDOW_PAIR p50_us="
              << pair_stats.p50_us
              << " mean_us=" << pair_stats.mean_us
              << " include_activation_quant=" << include_activation_quant
              << " include_gather=" << include_gather
              << " exact_windows=" << exact_windows << "/" << window_count
              << " exact_full_windows=" << exact_full_windows << "/" << window_count
              << " gemm1_total_diff=" << gemm1_total_diff
              << " gemm2_total_diff=" << gemm2_total_diff
              << " gather_total_diff=" << gather_total_diff
              << " json=" << json_path << std::endl;
}

void run_pair(engine::kind engine_kind) {
    const std::filesystem::path manifest_path = env_string("ONEDNN_WINDOW_MANIFEST");
    if (!manifest_path.empty()) {
        run_manifest_pair(engine_kind, manifest_path);
        return;
    }

    const std::filesystem::path gemm1_meta = env_string("ONEDNN_GEMM1_META");
    const std::filesystem::path gemm2_meta = env_string("ONEDNN_GEMM2_META");
    if (gemm1_meta.empty() || gemm2_meta.empty()) {
        throw std::runtime_error("ONEDNN_GEMM1_META and ONEDNN_GEMM2_META are required");
    }
    const int warmup = env_int("ONEDNN_PAIR_WARMUP", 20);
    const int iterations = env_int("ONEDNN_PAIR_ITERATIONS", 200);
    const std::string weight_format = env_string("ONEDNN_WEIGHT_FORMAT", "acb");
    const std::filesystem::path json_path = env_string(
            "ONEDNN_PAIR_JSON",
            (gemm1_meta.parent_path() / "resident_pair_result.json").string());
    const std::string route_counts_csv = env_string("ONEDNN_ROUTE_COUNTS_CSV");

    engine eng(engine_kind, 0);
    stream engine_stream(eng);

    ResidentCase gemm1(eng, gemm1_meta, weight_format);
    ResidentCase gemm2(eng, gemm2_meta, weight_format);

    for (int i = 0; i < warmup; ++i) {
        gemm1.execute(engine_stream);
        gemm2.execute(engine_stream);
        engine_stream.wait();
    }

    std::vector<double> pair_samples;
    pair_samples.reserve(iterations);
    for (int i = 0; i < iterations; ++i) {
        const auto start = std::chrono::steady_clock::now();
        gemm1.execute(engine_stream);
        gemm2.execute(engine_stream);
        engine_stream.wait();
        const auto end = std::chrono::steady_clock::now();
        pair_samples.push_back(std::chrono::duration<double, std::micro>(
                end - start).count());
    }

    gemm1.read_output();
    gemm2.read_output();
    const std::vector<uint8_t> base_gemm1_output = gemm1.output();
    const std::vector<uint8_t> base_gemm2_output = gemm2.output();
    const bool base_gemm1_equal =
            raw_diff_count(base_gemm1_output, gemm1.expected_output()) == 0;
    const bool base_gemm2_equal =
            raw_diff_count(base_gemm2_output, gemm2.expected_output()) == 0;
    const Stats pair_stats = summarize(pair_samples);

    std::vector<std::vector<int32_t>> route_windows;
    if (!route_counts_csv.empty()) {
        if (gemm1.meta().num_experts != gemm2.meta().num_experts
                || gemm1.meta().total_tokens != gemm2.meta().total_tokens) {
            throw std::runtime_error(
                    "route-window mode requires matching expert/token counts");
        }
        route_windows = load_count_windows(route_counts_csv, gemm1.meta().num_experts,
                gemm1.meta().total_tokens);
    }

    Stats route_pair_stats;
    double route_gemm1_checksum = 0.0;
    double route_gemm2_checksum = 0.0;
    uint64_t route_gemm1_diff_count = 0;
    uint64_t route_gemm2_diff_count = 0;
    bool have_route_stats = false;
    if (!route_windows.empty()) {
        for (int i = 0; i < warmup; ++i) {
            const auto &counts = route_windows[static_cast<size_t>(i) % route_windows.size()];
            gemm1.update_counts(counts);
            gemm2.update_counts(counts);
            gemm1.execute(engine_stream);
            gemm2.execute(engine_stream);
            engine_stream.wait();
        }

        std::vector<double> route_pair_samples;
        route_pair_samples.reserve(iterations);
        for (int i = 0; i < iterations; ++i) {
            const auto &counts = route_windows[static_cast<size_t>(i) % route_windows.size()];
            const auto start = std::chrono::steady_clock::now();
            gemm1.update_counts(counts);
            gemm2.update_counts(counts);
            gemm1.execute(engine_stream);
            gemm2.execute(engine_stream);
            engine_stream.wait();
            const auto end = std::chrono::steady_clock::now();
            route_pair_samples.push_back(std::chrono::duration<double, std::micro>(
                    end - start).count());
        }
        gemm1.read_output();
        gemm2.read_output();
        route_pair_stats = summarize(route_pair_samples);
        route_gemm1_checksum = raw_checksum(gemm1.output(), gemm1.dst_dtype());
        route_gemm2_checksum = raw_checksum(gemm2.output(), gemm2.dst_dtype());
        route_gemm1_diff_count = raw_diff_count(gemm1.output(), gemm1.expected_output());
        route_gemm2_diff_count = raw_diff_count(gemm2.output(), gemm2.expected_output());
        have_route_stats = true;
    }

    std::ofstream json(json_path);
    if (!json) throw std::runtime_error("failed to open json: " + json_path.string());
    json << std::fixed << std::setprecision(6);
    json << "{\n";
    json << "  \"kind\": \"resident_onednn_two_gemm_pair\",\n";
    json << "  \"warmup\": " << warmup << ",\n";
    json << "  \"iterations\": " << iterations << ",\n";
    json << "  \"pair_mean_us\": " << pair_stats.mean_us << ",\n";
    json << "  \"pair_min_us\": " << pair_stats.min_us << ",\n";
    json << "  \"pair_p50_us\": " << pair_stats.p50_us << ",\n";
    json << "  \"pair_p90_us\": " << pair_stats.p90_us << ",\n";
    json << "  \"pair_max_us\": " << pair_stats.max_us << ",\n";
    json << "  \"pair_construct_us\": "
         << (gemm1.construct_us() + gemm2.construct_us()) << ",\n";
    json << "  \"route_counts_csv\": \"" << json_escape(route_counts_csv) << "\",\n";
    json << "  \"route_window_count\": " << route_windows.size() << ",\n";
    write_case_json(json, "gemm1", gemm1, base_gemm1_output);
    json << ",\n";
    write_case_json(json, "gemm2", gemm2, base_gemm2_output);
    if (have_route_stats) {
        json << ",\n";
        write_stats_json(json, "route_pair", route_pair_stats);
        json << ",\n";
        json << "  \"route_outputs\": {\n";
        json << "    \"gemm1_raw_checksum\": " << route_gemm1_checksum << ",\n";
        json << "    \"gemm2_raw_checksum\": " << route_gemm2_checksum << ",\n";
        json << "    \"gemm1_diff_vs_base_expected_count\": "
             << route_gemm1_diff_count << ",\n";
        json << "    \"gemm2_diff_vs_base_expected_count\": "
             << route_gemm2_diff_count << "\n";
        json << "  }";
    }
    json << "\n}\n";

    std::cout << "ONEDNN_RESIDENT_PAIR p50_us=" << pair_stats.p50_us
              << " mean_us=" << pair_stats.mean_us
              << " gemm1_equal=" << base_gemm1_equal
              << " gemm2_equal=" << base_gemm2_equal
              << " route_windows=" << route_windows.size();
    if (have_route_stats) {
        std::cout << " route_pair_p50_us=" << route_pair_stats.p50_us
                  << " route_pair_mean_us=" << route_pair_stats.mean_us;
    }
    std::cout << " json=" << json_path << std::endl;
}

} // namespace

int main(int argc, char **argv) {
    engine::kind engine_kind = parse_engine_kind(argc, argv);
    return handle_example_errors(run_pair, engine_kind);
}
