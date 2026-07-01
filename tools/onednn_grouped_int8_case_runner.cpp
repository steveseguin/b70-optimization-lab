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
#include <unordered_map>
#include <vector>

#include "example_utils.hpp"
#include "oneapi/dnnl/dnnl.hpp"

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

void write_file(const std::filesystem::path &path, const std::vector<uint8_t> &data) {
    std::ofstream out(path, std::ios::binary);
    if (!out) throw std::runtime_error("failed to open output " + path.string());
    if (!data.empty()) {
        out.write(reinterpret_cast<const char *>(data.data()), data.size());
        if (!out) throw std::runtime_error("failed to write " + path.string());
    }
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

void run_case(engine::kind engine_kind) {
    const std::filesystem::path meta_path = env_string("ONEDNN_CASE_META");
    if (meta_path.empty()) {
        throw std::runtime_error("ONEDNN_CASE_META is required");
    }
    const Meta meta = read_meta(meta_path);
    const auto base = meta_path.parent_path();
    const auto dst_dt = parse_dst_dtype(meta.dst_dtype);
    const std::string weight_format_name =
            env_string("ONEDNN_WEIGHT_FORMAT", meta.weight_format);
    const auto weight_format = parse_weight_format(weight_format_name);
    const int warmup = env_int("ONEDNN_CASE_WARMUP", 5);
    const int iterations = env_int("ONEDNN_CASE_ITERATIONS", 20);
    const std::filesystem::path output_path = env_string(
            "ONEDNN_CASE_OUTPUT",
            (base / (meta.name + "_onednn_out." + meta.dst_dtype + ".bin")).string());
    const std::filesystem::path json_path = env_string(
            "ONEDNN_CASE_JSON",
            (base / (meta.name + "_onednn_result.json")).string());

    auto path_for = [&](const std::string &key) {
        auto it = meta.paths.find(key);
        if (it == meta.paths.end()) {
            throw std::runtime_error("missing path key: " + key);
        }
        return base / it->second;
    };

    const auto a_data = read_file(path_for("a_path"));
    const auto a_scales_data = read_file(path_for("a_scales_path"));
    std::string b_path_key = env_string("ONEDNN_B_PATH_KEY");
    if (b_path_key.empty()) {
        b_path_key = (weight_format_name == "acb"
                        && meta.paths.find("b_acb_path") != meta.paths.end())
                ? "b_acb_path"
                : "b_path";
    }
    const auto b_data = read_file(path_for(b_path_key));
    const auto b_scales_data = read_file(path_for("b_scales_path"));
    const auto rows_data = read_file(path_for("rows_path"));
    const auto offsets = cumulative_offsets(
            rows_data, meta.num_experts, meta.total_tokens);

    expect_size("A", a_data, static_cast<size_t>(meta.total_tokens * meta.k));
    expect_size("A scales", a_scales_data,
            static_cast<size_t>(meta.total_tokens) * sizeof(float));
    expect_size("B", b_data,
            static_cast<size_t>(meta.num_experts * meta.k * meta.n));
    expect_size("B scales", b_scales_data,
            static_cast<size_t>(meta.num_experts * meta.n) * sizeof(float));

    engine eng(engine_kind, 0);
    stream engine_stream(eng);

    const memory::dims src_dims = {meta.total_tokens, meta.k};
    const memory::dims weights_dims = {meta.num_experts, meta.k, meta.n};
    const memory::dims dst_dims = {meta.total_tokens, meta.n};

    auto src_md = memory::desc::grouped(
            src_dims, memory::data_type::s8, 0, meta.num_experts);
    auto dst_md = memory::desc::grouped(dst_dims, dst_dt, 0, meta.num_experts);
    auto weights_md = memory::desc(weights_dims, memory::data_type::s8,
            weight_format);

    primitive_attr attr;
    attr.set_scales_mask(DNNL_ARG_SRC, 1 << 0);
    attr.set_scales_mask(DNNL_ARG_WEIGHTS, (1 << 0) | (1 << 2));

    const auto construct_start = std::chrono::steady_clock::now();
    auto pd = matmul::primitive_desc(eng, src_md, weights_md, dst_md, attr);
    auto prim = matmul(pd);
    auto src_mem = memory(src_md, eng);
    auto dst_mem = memory(dst_md, eng);
    auto weights_mem = memory(weights_md, eng);
    auto src_scales_mem = memory(
            memory::desc({meta.total_tokens}, memory::data_type::f32,
                    memory::format_tag::a),
            eng);
    auto weights_scales_mem = memory(
            memory::desc({meta.num_experts, meta.n}, memory::data_type::f32,
                    memory::format_tag::ab),
            eng);
    const auto construct_end = std::chrono::steady_clock::now();

    std::vector<uint8_t> dst_data(
            static_cast<size_t>(meta.total_tokens * meta.n) * dtype_size(dst_dt), 0);
    write_to_dnnl_memory(const_cast<uint8_t *>(a_data.data()), src_mem);
    write_to_dnnl_memory(const_cast<uint8_t *>(b_data.data()), weights_mem);
    write_to_dnnl_memory(dst_data.data(), dst_mem);
    write_to_dnnl_memory(const_cast<int32_t *>(offsets.data()), src_mem, 1);
    write_to_dnnl_memory(const_cast<int32_t *>(offsets.data()), dst_mem, 1);
    write_to_dnnl_memory(const_cast<uint8_t *>(a_scales_data.data()), src_scales_mem);
    write_to_dnnl_memory(
            const_cast<uint8_t *>(b_scales_data.data()), weights_scales_mem);

    std::unordered_map<int, memory> args = {
            {DNNL_ARG_SRC, src_mem},
            {DNNL_ARG_WEIGHTS, weights_mem},
            {DNNL_ARG_DST, dst_mem},
            {DNNL_ARG_ATTR_SCALES | DNNL_ARG_SRC, src_scales_mem},
            {DNNL_ARG_ATTR_SCALES | DNNL_ARG_WEIGHTS, weights_scales_mem},
    };

    for (int i = 0; i < warmup; ++i) {
        prim.execute(engine_stream, args);
        engine_stream.wait();
    }

    std::vector<double> samples;
    samples.reserve(iterations);
    for (int i = 0; i < iterations; ++i) {
        const auto start = std::chrono::steady_clock::now();
        prim.execute(engine_stream, args);
        engine_stream.wait();
        const auto end = std::chrono::steady_clock::now();
        samples.push_back(std::chrono::duration<double, std::micro>(
                end - start).count());
    }

    read_from_dnnl_memory(dst_data.data(), dst_mem);
    write_file(output_path, dst_data);

    std::vector<double> sorted = samples;
    std::sort(sorted.begin(), sorted.end());
    const double sum = std::accumulate(samples.begin(), samples.end(), 0.0);
    auto pct = [&](double p) {
        const size_t idx = std::min(sorted.size() - 1,
                static_cast<size_t>((sorted.size() - 1) * p + 0.5));
        return sorted[idx];
    };
    const auto construct_us = std::chrono::duration_cast<std::chrono::microseconds>(
            construct_end - construct_start).count();

    std::ofstream json(json_path);
    if (!json) throw std::runtime_error("failed to open json: " + json_path.string());
    json << std::fixed << std::setprecision(6);
    json << "{\n";
    json << "  \"name\": \"" << json_escape(meta.name) << "\",\n";
    json << "  \"num_experts\": " << meta.num_experts << ",\n";
    json << "  \"total_tokens\": " << meta.total_tokens << ",\n";
    json << "  \"k\": " << meta.k << ",\n";
    json << "  \"n\": " << meta.n << ",\n";
    json << "  \"dst_dtype\": \"" << json_escape(meta.dst_dtype) << "\",\n";
    json << "  \"weight_format\": \"" << json_escape(weight_format_name)
         << "\",\n";
    json << "  \"b_path_key\": \"" << json_escape(b_path_key) << "\",\n";
    json << "  \"warmup\": " << warmup << ",\n";
    json << "  \"iterations\": " << iterations << ",\n";
    json << "  \"construct_us\": " << construct_us << ",\n";
    json << "  \"mean_us\": " << (sum / double(samples.size())) << ",\n";
    json << "  \"min_us\": " << sorted.front() << ",\n";
    json << "  \"p50_us\": " << pct(0.50) << ",\n";
    json << "  \"p90_us\": " << pct(0.90) << ",\n";
    json << "  \"max_us\": " << sorted.back() << ",\n";
    json << "  \"raw_checksum\": " << raw_checksum(dst_data, dst_dt) << ",\n";
    json << "  \"output_path\": \"" << json_escape(output_path.string()) << "\"\n";
    json << "}\n";

    std::cout << "ONEDNN_CASE name=" << meta.name
              << " total_tokens=" << meta.total_tokens
              << " K=" << meta.k << " N=" << meta.n
              << " dst=" << meta.dst_dtype
              << " weight_format=" << weight_format_name
              << " b_path_key=" << b_path_key
              << " mean_us=" << (sum / double(samples.size()))
              << " p50_us=" << pct(0.50)
              << " raw_checksum=" << raw_checksum(dst_data, dst_dt)
              << " output=" << output_path << std::endl;
}

} // namespace

int main(int argc, char **argv) {
    engine::kind engine_kind = parse_engine_kind(argc, argv);
    return handle_example_errors(run_case, engine_kind);
}
