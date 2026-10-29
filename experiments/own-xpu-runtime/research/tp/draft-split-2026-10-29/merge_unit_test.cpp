// CPU unit test of the exact draft-head vocabulary split (OWNRT_DRAFT_HEAD_SPLIT=1, engine draft_head_split.hpp).
// The merged result of two shards (card 0: rows [0, r0), card 1: rows [r0, R)) must equal the one-card ArgmaxFast
// result over all R rows: the largest value, the lowest index among equal values (+0 == -0), and a sticky failure if
// any logit is non-finite. Three implementations are compared on every case:
//   (1) ref:   a plain sequential definition (first strictly larger value wins);
//   (2) fast:  a verbatim copy of ArgmaxFast's device body (adapter.cpp, one 1024-lane work-group), run as a SYCL kernel;
//   (3) split: the engine's own ShardKernel (on each half) and MergeKernel device functors, run as SYCL kernels, and
//              their host twins draft_split::shard / draft_split::merge.
// The SYCL kernels run on the OpenCL CPU device only (no GPU is opened):
//   source /opt/intel/oneapi/setvars.sh
//   icpx -fsycl -std=gnu++20 -O1 -fno-fast-math -ffp-contract=off -I ../../../engine/src merge_unit_test.cpp -o /dev/shm/merge_unit_test
//   ONEAPI_DEVICE_SELECTOR=opencl:cpu /dev/shm/merge_unit_test
#include "stage2/packet194-expert-diet-engine/draft_head_split.hpp"
#include <cstdio>
#include <random>
#include <string>
#include <vector>

using u16 = uint16_t;
static u16 bf(float f) { uint32_t u = std::bit_cast<uint32_t>(f); return u16(u >> 16); }  // values below are exact BF16
static u16 bf_bits(uint32_t u) { return u16(u >> 16); }
struct Result { int index; bool fail; };

static Result ref(const std::vector<u16>& x) {
  int best = 0; bool finite = true;
  for (size_t j = 0; j < x.size(); ++j) {
    const float v = draft_split::bf16_value(x[j]); finite = finite && std::isfinite(v);
    if (v > draft_split::bf16_value(x[best])) best = int(j);
  }
  return {best, !finite};
}

// ArgmaxFast (adapter.cpp), verbatim body with raw pointers for rb.in(0)/rb.out(0)/rb.fail(): one row, W = 1024.
struct ArgmaxFastCopy {
  const u16* in; int n; int32_t* out; uint32_t* error;
  void operator()(sycl::nd_item<1> it) const {
    const int lane = int(it.get_local_linear_id()); auto g = it.get_group();
    constexpr int W = 1024; auto get = [&](int j) { return draft_split::bf16_value(in[j]); };
    int best = -1; float value = 0.f; bool finite = true;
    for (int j = lane; j < n; j += W) { const float v = get(j); finite = finite && sycl::isfinite(v); if (best < 0 || v > value) { best = j; value = v; } }
    const bool all_finite = sycl::all_of_group(g, finite);
    if (all_finite) {
      const float top = sycl::reduce_over_group(g, best < 0 ? -INFINITY : value, sycl::maximum<float>());
      const int index = sycl::reduce_over_group(g, (best >= 0 && value == top) ? best : INT_MAX, sycl::minimum<int>());
      if (lane == 0) *out = int32_t(float(index));  // View::put(i32) = int32_t(float(index))
    } else if (lane == 0) {
      int fallback = 0;
      for (int l = 0; l < 128; ++l) { int local = l; for (int j = l; j < n; j += 128) if (get(j) > get(local)) local = j;
        if (l < n && (get(local) > get(fallback) || (get(local) == get(fallback) && local < fallback))) fallback = local; }
      *out = int32_t(float(fallback)); *error = 1;
    }
  }
};

struct Device {
  sycl::queue q{sycl::cpu_selector_v, sycl::property::queue::in_order{}};
  Result fast(const std::vector<u16>& x) {
    u16* in = sycl::malloc_shared<u16>(x.size(), q); int32_t* out = sycl::malloc_shared<int32_t>(1, q); uint32_t* err = sycl::malloc_shared<uint32_t>(1, q);
    std::copy(x.begin(), x.end(), in); *out = -7; *err = 0;
    ArgmaxFastCopy k{in, int(x.size()), out, err};
    q.parallel_for(sycl::nd_range<1>(1024, 1024), k).wait();
    Result r{*out, *err != 0}; sycl::free(in, q); sycl::free(out, q); sycl::free(err, q); return r;
  }
  // The engine's kernels: shard on card 0 rows, shard on card 1 rows (its own logits buffer, offset r0), the record
  // exchange (a copy here), then merge on card 0. preset0/preset1 = a sticky error already set on that card.
  Result split(const std::vector<u16>& x, uint32_t r0, bool preset0 = false, bool preset1 = false, uint32_t* host_records = nullptr) {
    const uint32_t r1 = uint32_t(x.size()) - r0;
    u16* l0 = sycl::malloc_shared<u16>(r0, q); u16* l1 = sycl::malloc_shared<u16>(r1, q);
    uint32_t* w0 = sycl::malloc_shared<uint32_t>(draft_split::words, q); uint32_t* w1 = sycl::malloc_shared<uint32_t>(draft_split::words, q);
    uint32_t* ctl = sycl::malloc_shared<uint32_t>(4, q);  // active0, error0, active1, error1
    int32_t* token = sycl::malloc_shared<int32_t>(1, q);
    std::copy(x.begin(), x.begin() + r0, l0); std::copy(x.begin() + r0, x.end(), l1);
    for (unsigned i = 0; i < draft_split::words; ++i) w0[i] = w1[i] = 0xdeadbeefu;  // stale garbage must never be read
    ctl[0] = 1; ctl[1] = preset0; ctl[2] = 1; ctl[3] = preset1; *token = -7;
    draft_split::ShardKernel s0{l0, w0, ctl + 0, ctl + 1, r0, 0, 0}, s1{l1, w1, ctl + 2, ctl + 3, r1, r0, 1};
    q.parallel_for(sycl::nd_range<1>(draft_split::lanes, draft_split::lanes), s0).wait();
    q.parallel_for(sycl::nd_range<1>(draft_split::lanes, draft_split::lanes), s1).wait();
    for (unsigned i = 0; i < 4; ++i) { w1[draft_split::records + i] = w0[draft_split::records + i];   // X2: both records on both cards
      w0[draft_split::records + 4 + i] = w1[draft_split::records + 4 + i]; }
    if (host_records) for (unsigned i = 0; i < 8; ++i) host_records[i] = w0[draft_split::records + i];
    draft_split::MergeKernel m{w0, token, ctl + 0, ctl + 1};
    q.parallel_for(sycl::range<1>(1), m).wait();
    Result r{*token, ctl[1] != 0};
    for (void* p : {(void*)l0, (void*)l1, (void*)w0, (void*)w1, (void*)ctl, (void*)token}) sycl::free(p, q);
    return r;
  }
};

static Result host_split(const std::vector<u16>& x, uint32_t r0, uint32_t* records) {
  draft_split::shard(x.data(), r0, 0, records);
  draft_split::shard(x.data() + r0, uint32_t(x.size()) - r0, r0, records + 4);
  int32_t t = -7; const bool ok = draft_split::merge(records, records + 4, t);
  return {ok ? t : -7, !ok};
}

static int failures = 0, cases = 0, ties_across = 0, negative_detected = 0;
static void check(Device& d, const std::string& name, const std::vector<u16>& x, uint32_t r0, bool expect_fail, int expect_index = -1) {
  ++cases;
  const Result a = ref(x), b = d.fast(x); uint32_t dev_records[8], host_records[8];
  const Result c = d.split(x, r0, false, false, dev_records), h = host_split(x, r0, host_records);
  bool ok = a.fail == expect_fail && b.fail == expect_fail && c.fail == expect_fail && h.fail == expect_fail;
  if (!expect_fail) ok = ok && a.index == b.index && a.index == c.index && a.index == h.index && (expect_index < 0 || a.index == expect_index);
  for (int i = 0; i < 8; ++i) ok = ok && dev_records[i] == host_records[i];  // device records == host twins, bit for bit
  // ties across the split: the maximum occurs on both cards
  if (!expect_fail) { const float m = draft_split::bf16_value(x[a.index]); bool lo = false, hi = false;
    for (size_t j = 0; j < x.size(); ++j) if (draft_split::bf16_value(x[j]) == m) (j < r0 ? lo : hi) = true;
    ties_across += lo && hi;
    // Negative control: a merge that lets card 1 win equal values (>=) must disagree with ArgmaxFast on such ties.
    const int wrong = draft_split::bits_value(host_records[4]) >= draft_split::bits_value(host_records[0]) ? int(host_records[5]) : int(host_records[1]);
    negative_detected += wrong != a.index; }
  if (!ok) { ++failures; std::printf("FAIL %s r0=%u: ref %d/%d fast %d/%d split %d/%d host %d/%d expect %d fail %d\n", name.c_str(), r0,
    a.index, a.fail, b.index, b.fail, c.index, c.fail, h.index, h.fail, expect_index, expect_fail); }
}

int main() {
  Device d;
  std::printf("device: %s\n", d.q.get_device().get_info<sycl::info::device::name>().c_str());
  const uint32_t R = 91392, R0 = 45824;  // the B19 draft prefix and the default card-0 rows
  std::mt19937 rng(20261029);
  auto randoms = [&](size_t n, float scale) { std::normal_distribution<float> nd(0.f, scale); std::vector<u16> v(n); for (auto& e : v) e = bf(nd(rng)); return v; };
  const std::vector<uint32_t> splits{R0, 128, 45696, R - 128, 1024, 46080};
  // 1. Random BF16 logits (coarse BF16 spacing makes equal maxima common), every split point.
  for (int t = 0; t < 24; ++t) for (uint32_t r0 : splits) check(d, "random" + std::to_string(t), randoms(R, t % 2 ? 1.f : 6.f), r0, false);
  // 2. Constructed equal maxima.
  for (uint32_t r0 : splits) {
    auto x = randoms(R, 1.f); const u16 top = bf(64.f);
    const uint32_t r1 = R - r0, a1 = r1 / 3, b1 = 2 * r1 / 3;  // two positions inside card 1's rows (a1 < b1)
    { auto y = x; y[7] = top; y[r0 + a1] = top; check(d, "equal max across split", y, r0, false, 7); }
    { auto y = x; y[r0 - 1] = top; y[r0] = top; check(d, "equal max at the boundary", y, r0, false, int(r0 - 1)); }
    { auto y = x; y[r0 + a1] = top; y[r0 + b1] = top; check(d, "equal max inside card 1", y, r0, false, int(r0 + a1)); }
    { auto y = x; y[r0 + b1] = top; check(d, "max only on card 1", y, r0, false, int(r0 + b1)); }
    { auto y = x; y[3] = top; y[1027] = top; y[r0 + a1] = top; check(d, "equal max in two lanes and card 1", y, r0, false, 3); }
    { std::vector<u16> y(R, bf(1.f)); check(d, "all equal", y, r0, false, 0); }
    // +0 / -0: every other value negative.
    std::vector<u16> neg(R); for (auto& e : neg) e = bf(-std::abs(draft_split::bf16_value(bf(1.f + std::abs(std::normal_distribution<float>(0, 1)(rng))))));
    { auto y = neg; y[11] = bf_bits(0x80000000u); y[r0 + a1] = bf(0.f); check(d, "-0 on card 0, +0 on card 1", y, r0, false, 11); }
    { auto y = neg; y[11] = bf(0.f); y[r0 + a1] = bf_bits(0x80000000u); check(d, "+0 on card 0, -0 on card 1", y, r0, false, 11); }
    { auto y = neg; y[r0 + a1] = bf_bits(0x80000000u); y[r0 + b1] = bf(0.f); check(d, "-0 then +0 on card 1", y, r0, false, int(r0 + a1)); }
    { auto y = neg; y[r0 + a1] = bf(0.f); y[r0 + b1] = bf_bits(0x80000000u); check(d, "+0 then -0 on card 1", y, r0, false, int(r0 + a1)); }
    { auto y = neg; y[2048] = bf_bits(0x80000000u); y[1024] = bf(0.f); check(d, "+0 and -0 in one lane on card 0", y, r0, false, 1024); }
    // Non-finite logits on either card: a sticky failure, as ArgmaxFast.
    const uint32_t nan = 0x7fc00000u, pinf = 0x7f800000u, ninf = 0xff800000u;
    for (uint32_t bits : {nan, pinf, ninf}) {
      { auto y = x; y[5] = bf_bits(bits); check(d, "non-finite on card 0", y, r0, true); }
      { auto y = x; y[r0 + b1] = bf_bits(bits); check(d, "non-finite on card 1", y, r0, true); }
      { auto y = x; y[R - 1] = bf_bits(bits); y[0] = bf_bits(bits); check(d, "non-finite on both cards", y, r0, true); }
    }
  }
  // 3. Small prefixes (fewer rows than lanes on one card).
  for (uint32_t n : {256u, 1280u, 2304u}) for (int t = 0; t < 6; ++t) check(d, "small" + std::to_string(n), randoms(n, 2.f), 128, false);
  // 4. A sticky error already set: on card 0 the merge writes nothing and keeps the error; on card 1 the record carries
  //    it to the merge, which fails the draft (never a stale record).
  int preset_ok = 0;
  { auto x = randoms(R, 1.f); const Result r = d.split(x, R0, true, false); preset_ok += r.fail && r.index == -7; }
  { auto x = randoms(R, 1.f); const Result r = d.split(x, R0, false, true); preset_ok += r.fail && r.index == -7; }
  ++cases; if (preset_ok != 2) { ++failures; std::printf("FAIL preset sticky error cases %d/2\n", preset_ok); }
  std::printf("cases %d, failures %d, cases with the maximum on both cards %d\n", cases, failures, ties_across);
  std::printf("negative control (card 1 wins ties): differs from ArgmaxFast in %d cases (must be > 0)\n", negative_detected);
  if (!negative_detected) ++failures;
  std::printf("%s\n", failures ? "FAIL" : "PASS");
  return failures ? 1 : 0;
}
