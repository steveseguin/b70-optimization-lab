// Cold-weight GEMV streaming bench for the TP1 z-row anomaly (rung 3 of the
// 2026-08-21 decode profile). Rotates NUM_COPIES distinct weight tensors per
// graph so every mul_mat reads cold weights (working set >> B70 L2),
// removing the L2 contamination that made small/mid standalone rows report
// 938-1483 apparent GB/s. Diagnostic timing only; never promotable.
//
// Shapes: the anomalous z row [m=6144, k=5120] q8_0 (381.7 GB/s in-graph)
// and its healthy sibling [m=10240, k=5120] q8_0 (543 GB/s in-graph) as the
// in-harness control, plus [m=5120, k=5120] for scale reference.
//
// Build (lane tree, oneAPI 2026.0):
//   icpx -fsycl -O2 -std=c++17 qwen38_tp1_cold_gemv_bench.cpp \
//     -I<lane>/ggml/include -I<lane>/include \
//     -L<lane>/build-sycl-aot-bmg-g31/bin -lggml -lggml-base \
//     -Wl,-rpath,<lane>/build-sycl-aot-bmg-g31/bin -o cold-gemv-bench

#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <vector>

#include "ggml.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"

static constexpr int NUM_COPIES = 10;
static constexpr int WARMUP_REPS = 5;
static constexpr int TIMED_REPS = 60;

struct shape_spec {
    const char * name;
    int64_t m;
    int64_t k;
};

int main() {
    const shape_spec shapes[] = {
        {"z-row      ", 6144, 5120},
        {"sibling    ", 10240, 5120},
        {"square-ref ", 5120, 5120},
        {"ffn-out-ref", 5120, 17408},
    };

    ggml_backend_t backend = nullptr;
    for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
        ggml_backend_dev_t dev = ggml_backend_dev_get(i);
        if (ggml_backend_dev_type(dev) == GGML_BACKEND_DEVICE_TYPE_GPU) {
            backend = ggml_backend_dev_init(dev, nullptr);
            std::printf("device: %s\n", ggml_backend_dev_name(dev));
            break;
        }
    }
    if (backend == nullptr) {
        std::fprintf(stderr, "no GPU backend found\n");
        return 1;
    }

    for (const auto & spec : shapes) {
        const int64_t m = spec.m;
        const int64_t k = spec.k;

        ggml_init_params ip = {};
        ip.mem_size = ggml_tensor_overhead() * (size_t)(NUM_COPIES * 4 + 16) +
                      ggml_graph_overhead();
        ip.no_alloc = true;
        ggml_context * ctx = ggml_init(ip);

        std::vector<ggml_tensor *> weights(NUM_COPIES);
        for (int c = 0; c < NUM_COPIES; ++c) {
            weights[c] = ggml_new_tensor_2d(ctx, GGML_TYPE_Q8_0, k, m);
        }
        ggml_tensor * act = ggml_new_tensor_2d(ctx, GGML_TYPE_F32, k, 1);

        // One mul_mat per weight copy; outputs chained through adds so the
        // graph has a single root. Add traffic (m floats per add) is <0.1%
        // of the weight traffic and is excluded from the reported model.
        ggml_tensor * acc = ggml_mul_mat(ctx, weights[0], act);
        for (int c = 1; c < NUM_COPIES; ++c) {
            acc = ggml_add(ctx, acc, ggml_mul_mat(ctx, weights[c], act));
        }

        ggml_cgraph * gf = ggml_new_graph(ctx);
        ggml_build_forward_expand(gf, acc);

        ggml_backend_buffer_t buf =
            ggml_backend_alloc_ctx_tensors(ctx, backend);
        if (buf == nullptr) {
            std::fprintf(stderr, "alloc failed for m=%" PRId64 "\n", m);
            return 1;
        }

        // Deterministic fill: weights from a fixed byte pattern (valid q8_0
        // blocks: scale half = 1.0, int8 quants cycling), activation ramp.
        {
            const size_t row_bytes = ggml_row_size(GGML_TYPE_Q8_0, k);
            std::vector<uint8_t> host(row_bytes * (size_t)m);
            const uint16_t one_h = 0x3C00; // fp16 1.0
            const size_t block_bytes = sizeof(uint16_t) + 32; // q8_0 block
            for (size_t off = 0; off + block_bytes <= host.size();
                 off += block_bytes) {
                std::memcpy(host.data() + off, &one_h, sizeof(one_h));
                for (size_t j = 0; j < 32; ++j) {
                    host[off + sizeof(one_h) + j] =
                        (uint8_t)((off / block_bytes + j) % 251);
                }
            }
            for (int c = 0; c < NUM_COPIES; ++c) {
                ggml_backend_tensor_set(
                    weights[c], host.data(), 0, host.size());
            }
            std::vector<float> a((size_t)k);
            for (int64_t j = 0; j < k; ++j) {
                a[(size_t)j] = 0.001f * (float)(j % 97);
            }
            ggml_backend_tensor_set(act, a.data(), 0, a.size() * sizeof(float));
        }

        for (int r = 0; r < WARMUP_REPS; ++r) {
            ggml_backend_graph_compute(backend, gf);
        }
        ggml_backend_synchronize(backend);

        const auto t0 = std::chrono::steady_clock::now();
        for (int r = 0; r < TIMED_REPS; ++r) {
            ggml_backend_graph_compute(backend, gf);
        }
        ggml_backend_synchronize(backend);
        const auto t1 = std::chrono::steady_clock::now();

        const double sec =
            std::chrono::duration<double>(t1 - t0).count();
        const double calls = (double)TIMED_REPS * NUM_COPIES;
        const double us_per_call = sec * 1e6 / calls;
        const double weight_bytes =
            (double)ggml_row_size(GGML_TYPE_Q8_0, k) * (double)m;
        const double act_out_bytes =
            (double)k * sizeof(float) + (double)m * sizeof(float);
        const double gbps =
            (weight_bytes + act_out_bytes) / (us_per_call * 1e-6) / 1e9;

        std::printf(
            "%s m=%5" PRId64 " k=%5" PRId64 "  copies=%d  working-set=%.0f MiB"
            "  %8.2f us/call  %6.1f GB/s\n",
            spec.name, m, k, NUM_COPIES,
            weight_bytes * NUM_COPIES / (1024.0 * 1024.0),
            us_per_call, gbps);

        ggml_backend_buffer_free(buf);
        ggml_free(ctx);
    }

    ggml_backend_free(backend);
    return 0;
}
