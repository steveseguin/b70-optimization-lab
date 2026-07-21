// Default-off standalone B70 device-memory bandwidth probe.
//
// This file is not linked into vLLM or the XPU extension.  It measures logical
// read bytes from a data set much larger than cache, with a small checksum
// write so the compiler cannot remove the loads.

#include <sycl/sycl.hpp>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

using u32x4 = sycl::vec<std::uint32_t, 4>;

static inline std::uint64_t splitmix64(std::uint64_t x) {
  x += 0x9e3779b97f4a7c15ULL;
  x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
  x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
  return x ^ (x >> 31);
}

struct Options {
  std::size_t bytes = 1ULL << 30;
  int seconds = 2;
  int warmups = 4;
  int device = 0;
  int work_group = 256;
  int waves_per_cu = 16;
};

static Options parse(int argc, char **argv) {
  Options o;
  for (int i = 1; i < argc; ++i) {
    const std::string a(argv[i]);
    auto take = [&]() -> std::string {
      if (++i == argc) throw std::runtime_error("missing value after " + a);
      return argv[i];
    };
    if (a == "--bytes") o.bytes = std::stoull(take());
    else if (a == "--seconds") o.seconds = std::stoi(take());
    else if (a == "--warmups") o.warmups = std::stoi(take());
    else if (a == "--device") o.device = std::stoi(take());
    else if (a == "--work-group") o.work_group = std::stoi(take());
    else if (a == "--waves-per-cu") o.waves_per_cu = std::stoi(take());
    else throw std::runtime_error("unknown argument: " + a);
  }
  if (o.bytes < (1ULL << 20) || o.bytes % sizeof(u32x4))
    throw std::runtime_error("--bytes must be >=1 MiB and divisible by 16");
  if (o.work_group <= 0 || o.waves_per_cu <= 0)
    throw std::runtime_error("invalid launch geometry");
  return o;
}

int main(int argc, char **argv) {
  try {
    const Options o = parse(argc, argv);
    const auto devices = sycl::device::get_devices(sycl::info::device_type::gpu);
    if (o.device < 0 || static_cast<std::size_t>(o.device) >= devices.size())
      throw std::runtime_error("GPU ordinal is out of range");
    const sycl::device dev = devices[o.device];
    sycl::queue q(dev, sycl::property_list{sycl::property::queue::enable_profiling{}});
    const std::size_t cu = dev.get_info<sycl::info::device::max_compute_units>();
    const std::size_t global = cu * static_cast<std::size_t>(o.waves_per_cu) *
                               static_cast<std::size_t>(o.work_group);
    const std::size_t vectors = o.bytes / sizeof(u32x4);

    auto *src = sycl::malloc_device<u32x4>(vectors, q);
    auto *sink = sycl::malloc_device<u32x4>(global, q);
    if (!src || !sink) throw std::runtime_error("device allocation failed");
    // Per-address pseudo-random contents prevent the device's transparent
    // memory compression from turning this into a cache/compression probe.
    q.parallel_for(sycl::range<1>(vectors), [=](sycl::id<1> id) {
       const std::uint64_t i = id[0];
       const std::uint64_t lo = splitmix64(2 * i);
       const std::uint64_t hi = splitmix64(2 * i + 1);
       src[i] = u32x4(static_cast<std::uint32_t>(lo),
                      static_cast<std::uint32_t>(lo >> 32),
                      static_cast<std::uint32_t>(hi),
                      static_cast<std::uint32_t>(hi >> 32));
     }).wait();
    q.memset(sink, 0, global * sizeof(u32x4)).wait();

    auto launch = [&]() {
      return q.submit([&](sycl::handler &h) {
        h.parallel_for(
            sycl::nd_range<1>(global, static_cast<std::size_t>(o.work_group)),
            [=](sycl::nd_item<1> item) {
              const std::size_t gid = item.get_global_linear_id();
              const std::size_t stride = item.get_global_range(0);
              u32x4 a0(0), a1(0), a2(0), a3(0);
              std::size_t i = gid;
              for (; i + 3 * stride < vectors; i += 4 * stride) {
                a0 ^= src[i];
                a1 ^= src[i + stride];
                a2 ^= src[i + 2 * stride];
                a3 ^= src[i + 3 * stride];
              }
              for (; i < vectors; i += stride) a0 ^= src[i];
              sink[gid] = a0 ^ a1 ^ a2 ^ a3;
            });
      });
    };

    for (int i = 0; i < o.warmups; ++i) launch().wait();
    std::vector<double> durations;
    std::uint64_t launches = 0;
    const auto wall_start = std::chrono::steady_clock::now();
    do {
      sycl::event e = launch();
      e.wait();
      const auto start = e.get_profiling_info<sycl::info::event_profiling::command_start>();
      const auto end = e.get_profiling_info<sycl::info::event_profiling::command_end>();
      durations.push_back(static_cast<double>(end - start) * 1e-9);
      ++launches;
    } while (std::chrono::duration<double>(std::chrono::steady_clock::now() - wall_start).count() <
             o.seconds);

    std::sort(durations.begin(), durations.end());
    const double median_s = durations[durations.size() / 2];
    const double best_s = durations.front();
    const double wall_s = std::chrono::duration<double>(
                              std::chrono::steady_clock::now() - wall_start)
                              .count();
    const double logical_gb = static_cast<double>(o.bytes) / 1e9;
    std::cout << std::fixed << std::setprecision(3)
              << "{\"device\":\"" << dev.get_info<sycl::info::device::name>()
              << "\",\"device_ordinal\":" << o.device
              << ",\"compute_units\":" << cu
              << ",\"bytes\":" << o.bytes
              << ",\"work_group\":" << o.work_group
              << ",\"waves_per_cu\":" << o.waves_per_cu
              << ",\"global_items\":" << global
              << ",\"launches\":" << launches
              << ",\"median_ms\":" << median_s * 1e3
              << ",\"best_ms\":" << best_s * 1e3
              << ",\"median_GBps\":" << logical_gb / median_s
              << ",\"best_GBps\":" << logical_gb / best_s
              << ",\"wall_GBps\":" << logical_gb * launches / wall_s
              << "}\n";

    sycl::free(src, q);
    sycl::free(sink, q);
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "b70-stream-bandwidth: " << e.what() << '\n';
    return 2;
  }
}
