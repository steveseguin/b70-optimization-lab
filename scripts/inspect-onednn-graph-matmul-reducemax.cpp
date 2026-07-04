// Diagnostic-only oneDNN Graph partition inspector for the Qwen3.6 27B
// LM-head route.
//
// This does not execute a model or claim benchmark throughput. It answers a
// narrower question: does oneDNN Graph expose a fused MatMul -> ReduceMax
// partition for rows<=4, hidden=5120, vocab=248320? Even a successful
// ReduceMax fusion would still lack token IDs, so it is not sufficient for
// exact greedy decoding by itself.
//
// Example build on this host:
//
//   source /opt/intel/oneapi/setvars.sh >/tmp/oneapi-setvars.log 2>&1 || true
//   /opt/intel/oneapi/compiler/2026.0/bin/icpx -std=c++17 -fsycl \
//     -I/opt/intel/oneapi/dnnl/2026.0/include \
//     scripts/inspect-onednn-graph-matmul-reducemax.cpp \
//     -L/opt/intel/oneapi/dnnl/2026.0/lib -ldnnl \
//     -Wl,-rpath,/opt/intel/oneapi/dnnl/2026.0/lib \
//     -o /tmp/inspect-onednn-graph-matmul-reducemax

#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

#include "oneapi/dnnl/dnnl_graph.hpp"

namespace graph = dnnl::graph;
using dims = graph::logical_tensor::dims;
using dtype = graph::logical_tensor::data_type;
using layout_type = graph::logical_tensor::layout_type;

static const char* yes_no(bool value) {
  return value ? "yes" : "no";
}

static void inspect_case(const std::string& name,
                         dtype src_dtype,
                         dtype weight_dtype,
                         dtype logits_dtype,
                         int64_t rows,
                         int64_t hidden,
                         int64_t vocab) {
  std::cout << "case=" << name << " rows=" << rows
            << " hidden=" << hidden << " vocab=" << vocab << "\n";
  try {
    size_t id = 0;
    auto src = graph::logical_tensor(
        id++, src_dtype, dims{rows, hidden}, layout_type::strided);
    auto weight = graph::logical_tensor(
        id++, weight_dtype, dims{hidden, vocab}, layout_type::strided);
    auto logits = graph::logical_tensor(
        id++, logits_dtype, dims{rows, vocab}, layout_type::strided);
    auto max_values = graph::logical_tensor(
        id++, logits_dtype, dims{rows, 1}, layout_type::strided);

    auto matmul = graph::op(0, graph::op::kind::MatMul, "lm_head_matmul");
    matmul.add_inputs({src, weight});
    matmul.add_outputs({logits});

    auto reduce = graph::op(1, graph::op::kind::ReduceMax, "vocab_reducemax");
    reduce.set_attr<std::vector<int64_t>>(graph::op::attr::axes, {1});
    reduce.set_attr<bool>(graph::op::attr::keep_dims, true);
    reduce.add_inputs({logits});
    reduce.add_outputs({max_values});

    graph::graph g(dnnl::engine::kind::gpu);
    auto matmul_status = g.add_op(matmul, false);
    auto reduce_status = g.add_op(reduce, false);
    std::cout << "  add_matmul_status=" << static_cast<int>(matmul_status)
              << " add_reduce_status=" << static_cast<int>(reduce_status)
              << "\n";
    if (matmul_status != graph::status::success ||
        reduce_status != graph::status::success) {
      return;
    }

    g.finalize();
    for (auto policy : {graph::partition::policy::fusion,
                       graph::partition::policy::debug}) {
      auto partitions = g.get_partitions(policy);
      std::cout << "  policy="
                << (policy == graph::partition::policy::fusion ? "fusion"
                                                               : "debug")
                << " partitions=" << partitions.size() << "\n";
      for (size_t i = 0; i < partitions.size(); ++i) {
        auto ops = partitions[i].get_ops();
        std::cout << "    partition[" << i << "] supported="
                  << yes_no(partitions[i].is_supported())
                  << " ops_num=" << partitions[i].get_ops_num()
                  << " ops=";
        for (size_t j = 0; j < ops.size(); ++j) {
          std::cout << (j ? "," : "") << ops[j];
        }
        std::cout << " inputs=" << partitions[i].get_input_ports().size()
                  << " outputs=" << partitions[i].get_output_ports().size()
                  << "\n";
      }
    }
  } catch (const dnnl::error& e) {
    std::cout << "  dnnl_error status=" << static_cast<int>(e.status)
              << " message=" << e.what() << "\n";
  } catch (const std::exception& e) {
    std::cout << "  std_error message=" << e.what() << "\n";
  }
}

int main() {
  constexpr int64_t hidden = 5120;
  constexpr int64_t vocab = 248320;
  for (int64_t rows : {1, 2, 3, 4}) {
    inspect_case("bf16_matmul_reducemax",
                 dtype::bf16,
                 dtype::bf16,
                 dtype::bf16,
                 rows,
                 hidden,
                 vocab);
    inspect_case("s8_s8_bf16_matmul_reducemax",
                 dtype::s8,
                 dtype::s8,
                 dtype::bf16,
                 rows,
                 hidden,
                 vocab);
  }
  return 0;
}
