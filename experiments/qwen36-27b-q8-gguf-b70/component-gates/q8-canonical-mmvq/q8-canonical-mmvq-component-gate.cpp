#include "ggml.h"
#include "ggml-backend.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <unistd.h>

namespace {

constexpr int64_t K = 6144;
constexpr int64_t M = 5120;
constexpr size_t OUTPUT_BYTES_PER_VECTOR = static_cast<size_t>(M) * sizeof(float);

struct ggml_context_deleter {
    void operator()(ggml_context * ptr) const {
        if (ptr != nullptr) {
            ggml_free(ptr);
        }
    }
};

struct ggml_backend_deleter {
    void operator()(ggml_backend_t ptr) const {
        if (ptr != nullptr) {
            ggml_backend_free(ptr);
        }
    }
};

struct ggml_buffer_deleter {
    void operator()(ggml_backend_buffer_t ptr) const {
        if (ptr != nullptr) {
            ggml_backend_buffer_free(ptr);
        }
    }
};

using context_ptr = std::unique_ptr<ggml_context, ggml_context_deleter>;
using backend_ptr = std::unique_ptr<ggml_backend, ggml_backend_deleter>;
using buffer_ptr = std::unique_ptr<ggml_backend_buffer, ggml_buffer_deleter>;

struct options {
    std::string bootstrap_order;
    std::filesystem::path output_dir;
    size_t gpu_ordinal = 0;
};

struct case_output {
    std::string name;
    std::vector<uint8_t> bytes;
};

[[noreturn]] void fail(const std::string & message) {
    throw std::runtime_error(message);
}

std::string json_escape(std::string_view value) {
    std::string escaped;
    escaped.reserve(value.size());
    for (const unsigned char ch : value) {
        switch (ch) {
            case '\\': escaped += "\\\\"; break;
            case '"':  escaped += "\\\""; break;
            case '\n': escaped += "\\n";  break;
            case '\r': escaped += "\\r";  break;
            case '\t': escaped += "\\t";  break;
            default:
                if (ch < 0x20) {
                    char encoded[7] = {};
                    std::snprintf(encoded, sizeof(encoded), "\\u%04x", static_cast<unsigned int>(ch));
                    escaped += encoded;
                } else {
                    escaped.push_back(static_cast<char>(ch));
                }
        }
    }
    return escaped;
}

options parse_options(int argc, char ** argv) {
    options parsed;
    for (int i = 1; i < argc; ++i) {
        const std::string_view arg(argv[i]);
        auto next_value = [&]() -> std::string {
            if (++i >= argc) {
                fail("missing value after " + std::string(arg));
            }
            return argv[i];
        };

        if (arg == "--bootstrap-order") {
            parsed.bootstrap_order = next_value();
        } else if (arg == "--output-dir") {
            parsed.output_dir = next_value();
        } else if (arg == "--gpu-ordinal") {
            const std::string value = next_value();
            size_t consumed = 0;
            parsed.gpu_ordinal = std::stoull(value, &consumed);
            if (consumed != value.size()) {
                fail("invalid --gpu-ordinal: " + value);
            }
        } else {
            fail("unknown argument: " + std::string(arg));
        }
    }

    if (parsed.bootstrap_order != "selector-off-m1-ab" &&
        parsed.bootstrap_order != "m1-first-ab" &&
        parsed.bootstrap_order != "batched-first-ba") {
        fail("--bootstrap-order must be selector-off-m1-ab, m1-first-ab, or batched-first-ba");
    }
    if (parsed.output_dir.empty()) {
        fail("--output-dir is required");
    }
    return parsed;
}

uint32_t mix32(uint32_t value) {
    value ^= value >> 16;
    value *= UINT32_C(0x7feb352d);
    value ^= value >> 15;
    value *= UINT32_C(0x846ca68b);
    value ^= value >> 16;
    return value;
}

float deterministic_value(uint64_t index, uint32_t seed) {
    const uint32_t folded = static_cast<uint32_t>(index) ^ static_cast<uint32_t>(index >> 32) ^ seed;
    const int32_t centered = static_cast<int32_t>(mix32(folded) & UINT32_C(0xffff)) - 32768;
    return static_cast<float>(centered) * (1.0f / 32768.0f);
}

std::vector<float> make_input(uint32_t seed) {
    std::vector<float> result(static_cast<size_t>(K));
    for (int64_t column = 0; column < K; ++column) {
        result[static_cast<size_t>(column)] = deterministic_value(static_cast<uint64_t>(column), seed);
    }
    return result;
}

std::vector<uint8_t> make_quantized_weights() {
    const size_t row_bytes = ggml_row_size(GGML_TYPE_Q8_0, K);
    std::vector<uint8_t> quantized(row_bytes * static_cast<size_t>(M));
    std::vector<float> row(static_cast<size_t>(K));

    for (int64_t output_row = 0; output_row < M; ++output_row) {
        for (int64_t column = 0; column < K; ++column) {
            const uint64_t index = static_cast<uint64_t>(output_row) * static_cast<uint64_t>(K) +
                                   static_cast<uint64_t>(column);
            row[static_cast<size_t>(column)] = deterministic_value(index, UINT32_C(0x31415926));
        }
        const size_t written = ggml_quantize_chunk(
            GGML_TYPE_Q8_0,
            row.data(),
            quantized.data() + static_cast<size_t>(output_row) * row_bytes,
            0,
            1,
            K,
            nullptr);
        if (written != row_bytes) {
            fail("Q8_0 row quantization returned an unexpected byte count");
        }
    }
    return quantized;
}

context_ptr make_context(size_t tensor_count) {
    ggml_init_params params = {
        /* .mem_size = */ ggml_tensor_overhead() * tensor_count + ggml_graph_overhead(),
        /* .mem_buffer = */ nullptr,
        /* .no_alloc = */ true,
    };
    context_ptr context(ggml_init(params));
    if (!context) {
        fail("ggml_init failed");
    }
    return context;
}

ggml_backend_dev_t select_gpu(size_t ordinal) {
    size_t seen = 0;
    for (size_t index = 0; index < ggml_backend_dev_count(); ++index) {
        ggml_backend_dev_t device = ggml_backend_dev_get(index);
        const enum ggml_backend_dev_type type = ggml_backend_dev_type(device);
        if (type != GGML_BACKEND_DEVICE_TYPE_GPU && type != GGML_BACKEND_DEVICE_TYPE_IGPU) {
            continue;
        }
        if (seen++ == ordinal) {
            return device;
        }
    }
    fail("requested GPU ordinal is not visible to GGML");
}

case_output run_case(
        ggml_backend_t backend,
        ggml_tensor * weights,
        std::string name,
        int64_t ne1,
        int64_t ne2,
        const std::vector<float> & first,
        const std::vector<float> * second) {
    if ((ne1 * ne2 == 1) != (second == nullptr)) {
        fail("internal input-vector count mismatch for " + name);
    }
    if (ne1 * ne2 != 1 && ne1 * ne2 != 2) {
        fail("internal unsupported vector count for " + name);
    }

    context_ptr context = make_context(8);
    ggml_tensor * input = ggml_new_tensor_4d(context.get(), GGML_TYPE_F32, K, ne1, ne2, 1);
    ggml_set_name(input, (name + "-input").c_str());
    ggml_tensor * output = ggml_mul_mat(context.get(), weights, input);
    ggml_set_name(output, (name + "-output").c_str());
    ggml_cgraph * graph = ggml_new_graph(context.get());
    ggml_build_forward_expand(graph, output);

    if (!ggml_backend_supports_op(backend, output)) {
        fail("candidate backend does not support MUL_MAT for " + name);
    }

    buffer_ptr buffer(ggml_backend_alloc_ctx_tensors(context.get(), backend));
    if (!buffer) {
        fail("candidate backend tensor allocation failed for " + name);
    }

    std::vector<float> packed;
    packed.reserve(static_cast<size_t>(K * ne1 * ne2));
    packed.insert(packed.end(), first.begin(), first.end());
    if (second != nullptr) {
        packed.insert(packed.end(), second->begin(), second->end());
    }
    if (packed.size() * sizeof(float) != ggml_nbytes(input)) {
        fail("packed input size does not match GGML tensor for " + name);
    }
    ggml_backend_tensor_set(input, packed.data(), 0, packed.size() * sizeof(float));

    const ggml_status status = ggml_backend_graph_compute(backend, graph);
    if (status != GGML_STATUS_SUCCESS) {
        fail("candidate backend graph compute failed for " + name + ": " + ggml_status_to_string(status));
    }
    ggml_backend_synchronize(backend);

    case_output result = {std::move(name), std::vector<uint8_t>(ggml_nbytes(output))};
    ggml_backend_tensor_get(output, result.bytes.data(), 0, result.bytes.size());
    if (result.bytes.size() != static_cast<size_t>(ne1 * ne2) * OUTPUT_BYTES_PER_VECTOR) {
        fail("output byte count does not match the declared shape for " + result.name);
    }
    return result;
}

void require_slice_equal(
        const case_output & batched,
        size_t slice,
        const case_output & reference,
        const std::string & comparison) {
    if (reference.bytes.size() != OUTPUT_BYTES_PER_VECTOR) {
        fail("M=1 reference has an unexpected size: " + reference.name);
    }
    const size_t offset = slice * OUTPUT_BYTES_PER_VECTOR;
    if (offset + OUTPUT_BYTES_PER_VECTOR > batched.bytes.size()) {
        fail("batched slice is out of range: " + comparison);
    }
    if (std::memcmp(batched.bytes.data() + offset, reference.bytes.data(), OUTPUT_BYTES_PER_VECTOR) != 0) {
        size_t first_difference = 0;
        while (first_difference < OUTPUT_BYTES_PER_VECTOR &&
               batched.bytes[offset + first_difference] == reference.bytes[first_difference]) {
            ++first_difference;
        }
        fail("bitwise output mismatch for " + comparison + " at byte " + std::to_string(first_difference));
    }
}

void write_bytes(const std::filesystem::path & path, const void * data, size_t size) {
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    if (!stream) {
        fail("cannot open output file: " + path.string());
    }
    stream.write(static_cast<const char *>(data), static_cast<std::streamsize>(size));
    stream.close();
    if (!stream) {
        fail("cannot finish output file: " + path.string());
    }
}

void retain_outputs(
        const std::filesystem::path & output_dir,
        const std::vector<float> & input_a,
        const std::vector<float> & input_b,
        const std::vector<case_output> & outputs) {
    write_bytes(output_dir / "input-a.f32", input_a.data(), input_a.size() * sizeof(float));
    write_bytes(output_dir / "input-b.f32", input_b.data(), input_b.size() * sizeof(float));
    for (const case_output & output : outputs) {
        write_bytes(output_dir / (output.name + ".f32"), output.bytes.data(), output.bytes.size());
    }
}

} // namespace

int main(int argc, char ** argv) {
    try {
        const options opts = parse_options(argc, argv);
        if (!std::filesystem::is_directory(opts.output_dir) ||
            !std::filesystem::is_empty(opts.output_dir)) {
            fail("--output-dir must be an existing empty directory");
        }

        const std::vector<float> input_a = make_input(UINT32_C(0xa5a5a5a5));
        const std::vector<float> input_b = make_input(UINT32_C(0x5a5a5a5a));
        if (std::memcmp(input_a.data(), input_b.data(), input_a.size() * sizeof(float)) == 0) {
            fail("the two deterministic F32 input vectors are not distinct");
        }

        ggml_backend_load_all();
        ggml_backend_dev_t device = select_gpu(opts.gpu_ordinal);
        const std::string device_name = ggml_backend_dev_name(device);
        const std::string device_description = ggml_backend_dev_description(device);
        backend_ptr backend(ggml_backend_dev_init(device, nullptr));
        if (!backend) {
            fail("candidate GPU backend initialization failed");
        }

        context_ptr weight_context = make_context(4);
        ggml_tensor * weights = ggml_new_tensor_4d(weight_context.get(), GGML_TYPE_Q8_0, K, M, 1, 1);
        ggml_set_name(weights, "qwen36-q8-control-weight-6144x5120");
        buffer_ptr weight_buffer(ggml_backend_alloc_ctx_tensors(weight_context.get(), backend.get()));
        if (!weight_buffer) {
            fail("candidate GPU weight allocation failed");
        }
        ggml_backend_buffer_set_usage(weight_buffer.get(), GGML_BACKEND_BUFFER_USAGE_WEIGHTS);

        const std::vector<uint8_t> quantized_weights = make_quantized_weights();
        if (quantized_weights.size() != ggml_nbytes(weights)) {
            fail("host Q8_0 weight bytes do not match GGML tensor bytes");
        }
        ggml_backend_tensor_set(weights, quantized_weights.data(), 0, quantized_weights.size());

        std::vector<case_output> outputs;
        outputs.reserve(4);
        size_t bitwise_comparisons = 0;
        if (opts.bootstrap_order == "selector-off-m1-ab") {
            outputs.push_back(run_case(backend.get(), weights, "m1-a", 1, 1, input_a, nullptr));
            outputs.push_back(run_case(backend.get(), weights, "m1-b", 1, 1, input_b, nullptr));
        } else if (opts.bootstrap_order == "m1-first-ab") {
            outputs.push_back(run_case(backend.get(), weights, "m1-a", 1, 1, input_a, nullptr));
            outputs.push_back(run_case(backend.get(), weights, "m1-b", 1, 1, input_b, nullptr));
            outputs.push_back(run_case(backend.get(), weights, "flat-ab", 2, 1, input_a, &input_b));
            outputs.push_back(run_case(backend.get(), weights, "recurrent-ab", 1, 2, input_a, &input_b));

            require_slice_equal(outputs[2], 0, outputs[0], "flat AB column 0 versus M1 A");
            require_slice_equal(outputs[2], 1, outputs[1], "flat AB column 1 versus M1 B");
            require_slice_equal(outputs[3], 0, outputs[0], "recurrent AB sequence 0 versus M1 A");
            require_slice_equal(outputs[3], 1, outputs[1], "recurrent AB sequence 1 versus M1 B");
            bitwise_comparisons = 4;
        } else {
            outputs.push_back(run_case(backend.get(), weights, "recurrent-ba", 1, 2, input_b, &input_a));
            outputs.push_back(run_case(backend.get(), weights, "flat-ba", 2, 1, input_b, &input_a));
            outputs.push_back(run_case(backend.get(), weights, "m1-b", 1, 1, input_b, nullptr));
            outputs.push_back(run_case(backend.get(), weights, "m1-a", 1, 1, input_a, nullptr));

            require_slice_equal(outputs[0], 0, outputs[2], "recurrent BA sequence 0 versus M1 B");
            require_slice_equal(outputs[0], 1, outputs[3], "recurrent BA sequence 1 versus M1 A");
            require_slice_equal(outputs[1], 0, outputs[2], "flat BA column 0 versus M1 B");
            require_slice_equal(outputs[1], 1, outputs[3], "flat BA column 1 versus M1 A");
            bitwise_comparisons = 4;
        }

        retain_outputs(opts.output_dir, input_a, input_b, outputs);
        std::printf(
            "{\"schema_version\":1,\"pid\":%ld,\"bootstrap_order\":\"%s\","
            "\"device_name\":\"%s\",\"device_description\":\"%s\","
            "\"weight_type\":\"Q8_0\",\"weight_shape\":[6144,5120,1,1],"
            "\"flat_input_shape\":[6144,2,1,1],\"recurrent_input_shape\":[6144,1,2,1],"
            "\"inputs_distinct\":true,\"bitwise_comparisons\":%zu,\"bitwise_equal\":true}\n",
            static_cast<long>(getpid()),
            json_escape(opts.bootstrap_order).c_str(),
            json_escape(device_name).c_str(),
            json_escape(device_description).c_str(),
            bitwise_comparisons);
        std::fflush(stdout);

        // Force backend and weight teardown before returning so candidate route
        // summaries emitted during destruction are captured by the parent.
        weight_buffer.reset();
        weight_context.reset();
        backend.reset();
        ggml_quantize_free();
        return 0;
    } catch (const std::exception & error) {
        std::fprintf(stderr, "q8-canonical-mmvq-component-gate: %s\n", error.what());
        ggml_quantize_free();
        return 1;
    }
}
