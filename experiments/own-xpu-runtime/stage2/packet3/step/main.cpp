#include "../kernels/mock.hpp"
#include "plan.hpp"
#include <iomanip>
#include <iostream>
using namespace flash;
static void strings(const std::vector<std::string> &v) {
  std::cout << '[';
  bool first = true;
  for (auto &s : v) {
    if (!first)
      std::cout << ',';
    first = false;
    std::cout << std::quoted(s);
  }
  std::cout << ']';
}
static void record(const Plan &p) {
  std::uint64_t bytes = 0, reads = 0, writes = 0;
  std::cout << "{\"launches\":[";
  bool first = true;
  for (auto &l : p.launches) {
    if (!first)
      std::cout << ',';
    first = false;
    std::cout << "{\"op\":" << std::quoted(l.op)
              << ",\"label\":" << std::quoted(l.label) << ",\"card\":" << l.card
              << ",\"parameter\":" << l.parameter
              << ",\"source_card\":" << l.source_card << ",\"shape\":[";
    for (size_t i = 0; i < l.shape.size(); ++i) {
      if (i)
        std::cout << ',';
      std::cout << l.shape[i];
    }
    std::cout << "],\"inputs\":";
    strings(l.inputs);
    std::cout << ",\"outputs\":";
    strings(l.outputs);
    std::cout << ",\"weights\":";
    strings(l.weights);
    std::cout << ",\"weight_bytes\":" << l.weight_bytes
              << ",\"read_bytes\":" << l.read_bytes
              << ",\"write_bytes\":" << l.write_bytes << '}';
    bytes += l.weight_bytes;
    reads += l.read_bytes;
    writes += l.write_bytes;
  }
  std::cout << "],\"launch_count\":" << p.launches.size()
            << ",\"weight_bytes\":" << bytes
            << ",\"buffer_read_extent_bytes\":" << reads
            << ",\"buffer_write_extent_bytes\":" << writes << ",\"buffers\":[";
  first = true;
  for (const auto &b : p.buffers) {
    if (!first)
      std::cout << ',';
    first = false;
    std::cout << "{\"name\":" << std::quoted(b.name) << ",\"card\":" << b.card
              << ",\"scalar\":" << int(b.type)
              << ",\"element_bytes\":" << scalar_bytes(b.type)
              << ",\"shape\":[";
    for (size_t i = 0; i < b.shape.size(); ++i) {
      if (i)
        std::cout << ',';
      std::cout << b.shape[i];
    }
    std::cout << "]}";
  }
  std::cout << "]}\n";
}
int main(int argc, char **argv) {
  try {
    if (argc == 3 && std::string(argv[1]) == "record") {
      std::ifstream f(argv[2]);
      auto d = read_directory(f);
      record(model_plan(d));
      return 0;
    }
    bool real = argc > 1 && std::string(argv[1]) == "real";
    auto g = real ? Geometry{} : Geometry::tiny();
    if (real)
      g.context = 8;
    auto p = Builder(g).build(
        real ? std::vector<bool>{false} : std::vector<bool>{false, true}, real);
    if (argc > 1 && std::string(argv[1]) == "tiny-record") {
      record(p);
      return 0;
    }
    mock::Cpu cpu(p);
    for (int token : {2, 5, 3, 7, 1}) {
      cpu.data["token"] = {float(token)};
      p.execute(cpu, cpu.last());
    }
    std::cout << '{';
    bool first = true;
    for (auto &[name, values] : cpu.data) {
      if (!first)
        std::cout << ',';
      first = false;
      std::cout << std::quoted(name) << ":[";
      for (size_t i = 0; i < values.size(); ++i) {
        if (i)
          std::cout << ',';
        std::cout << std::bit_cast<std::uint32_t>(values[i]);
      }
      std::cout << ']';
    }
    std::cout << "}\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
