// Persistent-layer study (2026-10-30), question 1: device-wide barrier cost on one B70 against the plain
// kernel-to-kernel boundary for the same tiny work.
//
//  A. device facts and the driver's co-residency answer (max_num_work_groups) per work-group size;
//  B. empirical co-residency scan: N groups arrive at one bounded barrier; it passes only if all N are resident;
//  C. barrier cost: R phases of "touch" work, each followed by a bounded barrier, in one kernel (4 barrier variants);
//     us per barrier = (t(R) - t(0)) / R from profiling events; per-barrier distribution from the sub-group clock;
//     the touch data proves cross-group visibility (every value must equal R);
//  D. launch boundary: the same touch work as one kernel per phase, K launches queued behind a busy kernel so the
//     host cannot starve the card; period from profiling events and, separately, from host wall time without
//     profiling; also an empty kernel.
// Output: one JSON object on stdout. Every spin is bounded (gbar.hpp).
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/experimental/clock.hpp>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <string>
#include <vector>
#include "gbar.hpp"

namespace X = sycl::ext::oneapi::experimental;
using namespace pl;

static double ev_ns(const sycl::event& e) {
  return double(e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                e.get_profiling_info<sycl::info::event_profiling::command_start>());
}
static double pct(std::vector<double> v, double p) {
  if (v.empty()) return 0;
  std::sort(v.begin(), v.end());
  size_t i = std::min(v.size() - 1, size_t(p * double(v.size() - 1) + 0.5));
  return v[i];
}

template <int K, int F, int S> class BarName;
class TouchName;
class EmptyName;
class BusyName;

constexpr u32 LIMIT = 1u << 16;  // max polls per barrier (about 6-12 ms at 95-190 ns per poll)

struct Run {
  double ns = 0;
  u32 err = 0, maxpolls = 0, bad = 0;
};

// One persistent launch: R phases of touch work + barrier. buf has 2*nwg floats; stamps 2*(R+1) u64 or null.
template <Kind KK, Fence FF, int S>
static sycl::event launch_bar(sycl::queue& q, u32* ctl, u32 nwg, u32 wg, u32& base, u32 R, float* buf, u64* stamps) {
  Bar b0{ctl, nwg, base, LIMIT};
  auto e = q.parallel_for<BarName<int(KK), int(FF), S>>(
      sycl::nd_range<1>(size_t(nwg) * wg, wg), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
        Bar b = b0;
        const u32 g = u32(it.get_group_linear_id()), last = u32(it.get_local_range(0) - 1);
        const bool stamper = S && it.get_local_linear_id() == 0 && (g == 0 || g == b.nwg - 1);
        const u32 slot = g == 0 ? 0u : 1u;
        if (stamper) stamps[slot * (R + 1)] = X::clock<X::clock_scope::sub_group>();
        for (u32 r = 0; r < R; ++r) {
          if (it.get_local_linear_id() == last) {
            const float* src = buf + (r & 1u) * b.nwg;
            float* dst = buf + ((r + 1u) & 1u) * b.nwg;
            dst[g] = src[(g + 1u) % b.nwg] + 1.f;
          }
          if (!gbar<KK, FF>(it, b)) break;
          if (stamper) stamps[slot * (R + 1) + r + 1] = X::clock<X::clock_scope::sub_group>();
        }
        publish_polls(it, b);
      });
  base = next_base<KK>(base, R, nwg);
  return e;
}

static sycl::event launch_touch(sycl::queue& q, u32 nwg, u32 wg, u32 r, float* buf) {
  return q.parallel_for<TouchName>(sycl::nd_range<1>(size_t(nwg) * wg, wg),
                                   [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                                     const u32 g = u32(it.get_group_linear_id());
                                     if (it.get_local_linear_id() == it.get_local_range(0) - 1) {
                                       const float* src = buf + (r & 1u) * nwg;
                                       float* dst = buf + ((r + 1u) & 1u) * nwg;
                                       dst[g] = src[(g + 1u) % nwg] + 1.f;
                                     }
                                   });
}
static sycl::event launch_empty(sycl::queue& q, u32 nwg, u32 wg) {
  return q.parallel_for<EmptyName>(sycl::nd_range<1>(size_t(nwg) * wg, wg),
                                   [=](sycl::nd_item<1>) [[sycl::reqd_sub_group_size(32)]] {});
}
// Bounded ALU loop on one work-item (no waiting on anything): keeps the card busy while the host queues work.
static sycl::event launch_busy(sycl::queue& q, float* sink, u32 iters) {
  return q.single_task<BusyName>([=] {
    float x = sink[1];  // runtime value: the loop cannot be folded
    for (u32 i = 0; i < iters; ++i) x = x * 1.0000001f + float(i & 7u) * 1e-7f;
    sink[0] = x;
  });
}

struct Ctx {
  sycl::queue& q;
  u32* ctl;
  float* buf;
  u64* stamps;
  std::vector<u32> h;
  u32 base[6] = {0, 0, 0, 0, 0, 0};
};

static u32 read_ctl(Ctx& c, u32 word) {
  u32 v = 0;
  c.q.memcpy(&v, c.ctl + word, 4).wait();
  return v;
}
static void reset_all(Ctx& c) {
  c.q.memset(c.ctl, 0, CTL_WORDS * 4).wait();
  for (auto& b : c.base) b = 0;
}

template <Kind KK, Fence FF, int S>
static Run run_bar(Ctx& c, u32 nwg, u32 wg, u32 R, bool check) {
  Run out;
  c.q.memset(c.buf, 0, 2 * nwg * 4).wait();
  c.q.memset(c.ctl + MAXPOLL, 0, 4).wait();
  u32& base = c.base[int(KK) * 2 + int(FF)];
  auto e = launch_bar<KK, FF, S>(c.q, c.ctl, nwg, wg, base, R, c.buf, c.stamps);
  e.wait();
  out.ns = ev_ns(e);
  out.err = read_ctl(c, ERR);
  out.maxpolls = read_ctl(c, MAXPOLL);
  if (check && R) {
    std::vector<float> hb(nwg);
    c.q.memcpy(hb.data(), c.buf + (R & 1u) * nwg, nwg * 4).wait();
    for (u32 i = 0; i < nwg; ++i)
      if (hb[i] != float(R)) ++out.bad;
  }
  return out;
}

template <Kind KK, Fence FF>
static void barrier_series(Ctx& c, u32 wg, const std::vector<u32>& Ns, u32 R, const char* name, bool& first,
                           bool& halt) {
  for (u32 n : Ns) {
    if (halt) return;
    reset_all(c);  // variants share the control words; tree sub-counter targets assume one N since the reset
    std::vector<double> t0, t1;
    u32 bad = 0, maxp = 0;
    for (int rep = 0; rep < 7; ++rep) {
      Run a = run_bar<KK, FF, 0>(c, n, wg, 0, false);
      Run b = run_bar<KK, FF, 0>(c, n, wg, R, true);
      if (a.err || b.err) {
        std::printf("%s{\"variant\":\"%s\",\"wg\":%u,\"nwg\":%u,\"error\":%u}", first ? "" : ",", name, wg, n,
                    a.err | b.err);
        first = false;
        halt = true;
        return;
      }
      t0.push_back(a.ns);
      t1.push_back(b.ns);
      bad += b.bad;
      maxp = std::max(maxp, b.maxpolls);
    }
    // stamped run for the per-barrier distribution
    Run s = run_bar<KK, FF, 1>(c, n, wg, R, true);
    if (s.err) {
      halt = true;
      return;
    }
    std::vector<u64> st(2 * (R + 1));
    c.q.memcpy(st.data(), c.stamps, st.size() * 8).wait();
    const double ticks = double(st[R] - st[0]);
    const double rate = ticks / s.ns;  // ticks per ns (kernel includes launch: slight underestimate of rate)
    std::vector<double> d0, d1;
    for (u32 r = 0; r < R; ++r) {
      d0.push_back(double(st[r + 1] - st[r]) / 2.80);
      if (n > 1) d1.push_back(double(st[R + 1 + r + 1] - st[R + 1 + r]) / 2.80);
    }
    const double m0 = pct(t0, 0.5), m1 = pct(t1, 0.5);
    std::printf(
        "%s{\"variant\":\"%s\",\"wg\":%u,\"nwg\":%u,\"R\":%u,\"t0_us\":%.3f,\"tR_us\":%.3f,\"us_per_barrier\":%.4f,"
        "\"tR_p10_us\":%.3f,\"tR_p90_us\":%.3f,\"touch_bad\":%u,\"maxpolls\":%u,\"clock_ticks_per_ns\":%.4f,"
        "\"g0_ns\":{\"p10\":%.1f,\"p50\":%.1f,\"p90\":%.1f,\"p99\":%.1f,\"max\":%.1f},"
        "\"glast_ns\":{\"p10\":%.1f,\"p50\":%.1f,\"p90\":%.1f,\"p99\":%.1f,\"max\":%.1f},\"stamped_touch_bad\":%u}",
        first ? "" : ",", name, wg, n, R, m0 / 1e3, m1 / 1e3, (m1 - m0) / 1e3 / R, pct(t1, 0.1) / 1e3,
        pct(t1, 0.9) / 1e3, bad, maxp, rate, pct(d0, 0.1), pct(d0, 0.5), pct(d0, 0.9), pct(d0, 0.99), pct(d0, 1.0),
        pct(d1, 0.1), pct(d1, 0.5), pct(d1, 0.9), pct(d1, 0.99), pct(d1, 1.0), s.bad);
    first = false;
    std::fflush(stdout);
  }
}

int main(int argc, char** argv) {
  const bool quick = argc > 1 && std::string(argv[1]) == "quick";
  auto devs = sycl::device::get_devices(sycl::info::device_type::gpu);
  if (devs.size() != 1) {
    std::printf("{\"error\":\"expected one visible GPU, got %zu\"}\n", devs.size());
    return 2;
  }
  sycl::device d = devs[0];
  sycl::queue q(d, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
  sycl::queue qn(q.get_context(), d, {sycl::property::queue::in_order{}});  // no profiling
  std::printf("{\"device\":\"%s\",\"driver\":\"%s\",\"max_compute_units\":%u,\"max_wg\":%zu,\"local_mem\":%zu",
              d.get_info<sycl::info::device::name>().c_str(), d.get_info<sycl::info::device::driver_version>().c_str(),
              d.get_info<sycl::info::device::max_compute_units>(),
              d.get_info<sycl::info::device::max_work_group_size>(),
              size_t(d.get_info<sycl::info::device::local_mem_size>()));
  if (d.has(sycl::aspect::ext_intel_gpu_eu_count))
    std::printf(",\"eu_count\":%u", d.get_info<sycl::ext::intel::info::device::gpu_eu_count>());
  if (d.has(sycl::aspect::ext_intel_gpu_slices))
    std::printf(",\"slices\":%u", d.get_info<sycl::ext::intel::info::device::gpu_slices>());
  if (d.has(sycl::aspect::ext_intel_gpu_subslices_per_slice))
    std::printf(",\"subslices_per_slice\":%u", d.get_info<sycl::ext::intel::info::device::gpu_subslices_per_slice>());
  if (d.has(sycl::aspect::ext_intel_gpu_eu_count_per_subslice))
    std::printf(",\"eu_per_subslice\":%u", d.get_info<sycl::ext::intel::info::device::gpu_eu_count_per_subslice>());
  if (d.has(sycl::aspect::ext_intel_gpu_hw_threads_per_eu))
    std::printf(",\"hw_threads_per_eu\":%u", d.get_info<sycl::ext::intel::info::device::gpu_hw_threads_per_eu>());
  std::fflush(stdout);

  u32* ctl = sycl::malloc_device<u32>(CTL_WORDS, q);  // tree sub-counters need nwg <= 16 * SUBS
  const u32 MAXN = 4096;
  float* buf = sycl::malloc_device<float>(2 * MAXN, q);
  u64* stamps = sycl::malloc_device<u64>(2 * 1001 + 64, q);
  float* sink = sycl::malloc_device<float>(16, q);
  q.fill(sink, 1.f, 16).wait();
  Ctx c{q, ctl, buf, stamps, {}};
  reset_all(c);

  // A. driver co-residency answer for the counter/wg barrier kernel and the touch kernel
  {
    auto kb = sycl::get_kernel_bundle<sycl::bundle_state::executable>(q.get_context());
    auto kbar = kb.get_kernel<BarName<0, 0, 0>>();
    auto kbar_dev = kb.get_kernel<BarName<0, 1, 0>>();
    std::printf(",\"max_num_work_groups\":[");
    const u32 wgs[] = {32, 64, 128, 256, 512, 1024};
    for (int i = 0; i < 6; ++i) {
      size_t m = 0, md = 0;
      try {
        m = kbar.ext_oneapi_get_info<X::info::kernel_queue_specific::max_num_work_groups>(q, sycl::range<1>(wgs[i]),
                                                                                         0);
        md = kbar_dev.ext_oneapi_get_info<X::info::kernel_queue_specific::max_num_work_groups>(
            q, sycl::range<1>(wgs[i]), 0);
      } catch (const sycl::exception& e) {
        m = md = 0;
      }
      std::printf("%s{\"wg\":%u,\"bar_counter_wg\":%zu,\"bar_counter_device\":%zu}", i ? "," : "", wgs[i], m, md);
    }
    std::printf("]");
    std::fflush(stdout);
  }

  // warm-up (~1 s of work, no settings touched)
  {
    auto t0 = std::chrono::steady_clock::now();
    while (std::chrono::steady_clock::now() - t0 < std::chrono::milliseconds(quick ? 200 : 1000)) {
      launch_busy(q, sink, 200000).wait();
      run_bar<Kind::counter, Fence::wg, 0>(c, 64, 256, 50, false);
    }
    if (read_ctl(c, ERR)) {
      std::printf(",\"error\":\"barrier error during warm-up\"}\n");
      return 3;
    }
  }

  bool halt = false;
  // B. empirical co-residency: one barrier, R = 1, scan N for each work-group size
  std::printf(",\"coresidency\":[");
  {
    bool first = true;
    struct Scan { u32 wg; std::vector<u32> ns; };
    std::vector<Scan> scans = quick ? std::vector<Scan>{{256, {16, 64, 128}}}
                                    : std::vector<Scan>{{128, {64, 128, 256, 384, 448, 512, 513, 576, 640, 1024}},
                                                        {256, {32, 64, 128, 192, 224, 256, 257, 288, 320, 512}},
                                                        {512, {32, 64, 96, 112, 128, 129, 160, 256}},
                                                        {1024, {16, 32, 48, 56, 64, 65, 80, 128}}};
    for (auto& s : scans)
      for (u32 n : s.ns) {
        reset_all(c);
        Run r = run_bar<Kind::counter, Fence::wg, 0>(c, n, s.wg, 1, true);
        std::printf("%s{\"wg\":%u,\"nwg\":%u,\"pass\":%d,\"us\":%.2f,\"maxpolls\":%u,\"touch_bad\":%u}",
                    first ? "" : ",", s.wg, n, r.err == 0, r.ns / 1e3, r.maxpolls, r.bad);
        first = false;
        std::fflush(stdout);
      }
    reset_all(c);
  }
  std::printf("]");

  // C. barrier cost
  const u32 R = quick ? 100 : 1000;
  std::vector<u32> Ns = quick ? std::vector<u32>{1, 16, 64} : std::vector<u32>{1, 2, 8, 32, 64, 128, 192, 256};
  const u32 WG = 256;
  std::printf(",\"barrier\":[");
  {
    bool first = true;
    barrier_series<Kind::counter, Fence::wg>(c, WG, Ns, R, "counter/wg-fence", first, halt);
    barrier_series<Kind::flag, Fence::wg>(c, WG, Ns, R, "flag/wg-fence", first, halt);
    barrier_series<Kind::tree, Fence::wg>(c, WG, Ns, R, "tree16/wg-fence", first, halt);
    barrier_series<Kind::counter, Fence::device>(c, WG, Ns, R, "counter/device-fence", first, halt);
    barrier_series<Kind::tree, Fence::device>(c, WG, Ns, R, "tree16/device-fence", first, halt);
    barrier_series<Kind::flag, Fence::device>(c, WG, Ns, R, "flag/device-fence", first, halt);
    if (!quick) {
      std::vector<u32> n128 = {64, 128, 256, 512};
      barrier_series<Kind::counter, Fence::wg>(c, 128, n128, R, "counter/wg-fence", first, halt);
      barrier_series<Kind::tree, Fence::wg>(c, 128, n128, R, "tree16/wg-fence", first, halt);
      barrier_series<Kind::tree, Fence::device>(c, 128, n128, R, "tree16/device-fence", first, halt);
      // the wide-group layouts that fill the card with fewer arrivals (the chain's best persistent layout is 1024 x 64)
      barrier_series<Kind::counter, Fence::wg>(c, 512, {16, 32, 64, 128}, R, "counter/wg-fence", first, halt);
      barrier_series<Kind::counter, Fence::wg>(c, 1024, {8, 16, 32, 41, 64}, R, "counter/wg-fence", first, halt);
      barrier_series<Kind::tree, Fence::wg>(c, 1024, {32, 64}, R, "tree16/wg-fence", first, halt);
      barrier_series<Kind::counter, Fence::device>(c, 1024, {32, 64}, R, "counter/device-fence", first, halt);
    }
  }
  std::printf("]");
  if (halt) {
    std::printf(",\"halt\":\"barrier error\"}\n");
    return 4;
  }

  // D. launch boundary: K launches queued behind a busy kernel
  const u32 Kn = quick ? 100 : 400;
  std::printf(",\"boundary\":[");
  {
    bool first = true;
    // calibrate busy iterations to about 6 ms
    auto eb = launch_busy(q, sink, 1000000);
    eb.wait();
    const double per_iter = ev_ns(eb) / 1e6;
    const u32 iters = u32(std::min(2.0e7, 6.0e6 / per_iter));
    std::vector<u32> bn = quick ? std::vector<u32>{1, 64} : std::vector<u32>{1, 8, 32, 64, 128, 256};
    for (int kind = 0; kind < 2; ++kind)
      for (u32 n : bn) {
        std::vector<double> periods, durs, enq, gaps, walls, lag, ahead;
        u32 bad = 0;
        for (int rep = 0; rep < 5; ++rep) {
          q.memset(buf, 0, 2 * n * 4).wait();
          auto busy = launch_busy(q, sink, iters);
          std::vector<sycl::event> ev;
          ev.reserve(Kn);
          auto h0 = std::chrono::steady_clock::now();
          for (u32 k = 0; k < Kn; ++k) ev.push_back(kind ? launch_empty(q, n, WG) : launch_touch(q, n, WG, k, buf));
          auto h1 = std::chrono::steady_clock::now();
          q.wait();
          const double busy_end = double(busy.get_profiling_info<sycl::info::event_profiling::command_end>());
          const double first_start = double(ev[0].get_profiling_info<sycl::info::event_profiling::command_start>());
          lag.push_back((first_start - busy_end) / 1e3);
          ahead.push_back(std::chrono::duration<double, std::nano>(h1 - h0).count() / 1e3 < ev_ns(busy) / 1e3 ? 1 : 0);
          const u32 k0 = 8;  // skip the first few
          const double e0 = double(ev[k0].get_profiling_info<sycl::info::event_profiling::command_end>());
          const double e1 = double(ev[Kn - 1].get_profiling_info<sycl::info::event_profiling::command_end>());
          periods.push_back((e1 - e0) / double(Kn - 1 - k0));
          for (u32 k = k0; k < Kn; ++k) {
            durs.push_back(ev_ns(ev[k]));
            if (k > k0)
              gaps.push_back(double(ev[k].get_profiling_info<sycl::info::event_profiling::command_start>()) -
                             double(ev[k - 1].get_profiling_info<sycl::info::event_profiling::command_end>()));
          }
          enq.push_back(std::chrono::duration<double, std::nano>(h1 - h0).count() / Kn);
          if (!kind) {
            std::vector<float> hb(n);
            q.memcpy(hb.data(), buf + (Kn & 1u) * n, n * 4).wait();
            for (u32 i = 0; i < n; ++i)
              if (hb[i] != float(Kn)) ++bad;
            q.memset(buf, 0, 2 * n * 4).wait();
          }
          // host wall without profiling: busy + K launches vs busy alone
          auto w0 = std::chrono::steady_clock::now();
          launch_busy(qn, sink, iters);
          for (u32 k = 0; k < Kn; ++k) {
            if (kind) launch_empty(qn, n, WG);
            else launch_touch(qn, n, WG, k, buf);
          }
          qn.wait();
          auto w1 = std::chrono::steady_clock::now();
          launch_busy(qn, sink, iters);
          qn.wait();
          auto w2 = std::chrono::steady_clock::now();
          walls.push_back((std::chrono::duration<double, std::nano>(w1 - w0).count() -
                           std::chrono::duration<double, std::nano>(w2 - w1).count()) /
                          Kn);
        }
        std::printf(
            "%s{\"kernel\":\"%s\",\"wg\":%u,\"nwg\":%u,\"K\":%u,\"period_us\":%.4f,\"period_p10\":%.4f,"
            "\"period_p90\":%.4f,\"duration_us\":{\"p10\":%.3f,\"p50\":%.3f,\"p90\":%.3f,\"p99\":%.3f},"
            "\"gap_us\":{\"p50\":%.3f,\"p90\":%.3f},\"host_enqueue_us\":%.3f,\"wall_noprof_us_per_launch\":%.4f,"
            "\"wall_noprof_p10\":%.4f,\"wall_noprof_p90\":%.4f,\"busy_ms\":%.2f,\"host_ahead_reps\":%.0f,\"touch_bad\":%u}",
            first ? "" : ",", kind ? "empty" : "touch", WG, n, Kn, pct(periods, 0.5) / 1e3, pct(periods, 0.1) / 1e3,
            pct(periods, 0.9) / 1e3, pct(durs, 0.1) / 1e3, pct(durs, 0.5) / 1e3, pct(durs, 0.9) / 1e3,
            pct(durs, 0.99) / 1e3, pct(gaps, 0.5) / 1e3, pct(gaps, 0.9) / 1e3, pct(enq, 0.5) / 1e3,
            pct(walls, 0.5) / 1e3, pct(walls, 0.1) / 1e3, pct(walls, 0.9) / 1e3, iters * per_iter / 1e6,
            [&] { double a = 0; for (double v : ahead) a += v; return a; }(), bad);
        first = false;
        std::fflush(stdout);
      }
  }
  std::printf("],\"final_err\":%u}\n", read_ctl(c, ERR));
  sycl::free(ctl, q);
  sycl::free(buf, q);
  sycl::free(stamps, q);
  sycl::free(sink, q);
  return 0;
}
