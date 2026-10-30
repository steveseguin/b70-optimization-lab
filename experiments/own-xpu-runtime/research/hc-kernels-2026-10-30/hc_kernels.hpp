// Candidate exact HC kernels (hc-kernels study, 2026-10-30). Each keeps the engine kernel's per-output arithmetic bit for
// bit; only which work-item does which (unchanged) operation sequence, the load scheduling and prefetches change.
//
// Engine arithmetic being preserved (stage2/packet6-kopt/dense_v2.hpp bf16_rows<R,U>, the kopt Multiply value):
//   one output row = 32 logical lanes; logical lane l owns the 8-element chunks starting at 8l, 8l+256, 8l+512, ...;
//   per lane: acc = 0.f; for each chunk in order, for j = 0..7: acc = acc + bf16(w)*x  (product rounded, then added;
//   -ffp-contract=off); then the 32 lane sums by the adjacent-pair tree (strides 1..16, node = lower + upper).
// Engine HC norm (stage2/packet194-expert-diet-engine/specialised.hpp body<norm,0/1,2560,4>, two launches):
//   stage 0: partial[row][c] = 32-leaf adjacent subtree of x^2 over elements c*32..c*32+31 (c = 0..79);
//   stage 1: inv = detmath::rsqrt(upper(partial[row], 80) / 2560 + 1e-6f); y = (x*inv)*(gain[(row%4)*2560+k] + unit).
#pragma once
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/experimental/prefetch.hpp>
#include <cstdint>
#include "stage2/packet6-kopt/dense_v2.hpp"
#include "stage2/packet194-expert-diet-engine/specialised.hpp"

namespace hck {
namespace syclex = sycl::ext::oneapi::experimental;
using iq3::kopt::dense_v2::bf16f;

// The engine's 32-lane tree for one row (bf16_rows<1,U>'s levels 0..4): every lane ends with the same value.
inline float row_tree(const sycl::sub_group& sg, float A, unsigned lane) {
#pragma unroll
  for (unsigned lv = 0; lv < 5; ++lv) {
    const float o = sycl::permute_group_by_xor(sg, A, 1u << lv);
    A = ((lane >> lv) & 1u) ? o + A : A + o;
  }
  return A;
}

template <int HINT>
inline void pf(const void* p, size_t bytes) {
  void* q = const_cast<void*>(p);
  if constexpr (HINT == 1) syclex::prefetch(q, bytes, syclex::properties{syclex::prefetch_hint_L1});
  else if constexpr (HINT == 2) syclex::prefetch(q, bytes, syclex::properties{syclex::prefetch_hint_L2});
  else if constexpr (HINT == 3) syclex::prefetch(q, bytes, syclex::properties{syclex::prefetch_hint_L3});
}

// Low GEMV row (K large): bf16_rows<1,U> with prefetches of the row's weights. PF0 = bytes of the row each lane
// prefetches at entry (spread over the row, lane-interleaved 64-byte lines); D = batches ahead prefetched in the loop.
template <unsigned U, unsigned D, int HINT, bool AHEAD_ALL>
inline void low_row_pf(const uint8_t* W, const float* x, float* y, uint32_t rows, uint32_t k, uint32_t rb,
                       const sycl::sub_group& sg, uint32_t row) {
  const unsigned lane = sg.get_local_linear_id();
  if (row >= rows) return;
  const uint8_t* wr = W + size_t(row) * rb;
  if constexpr (HINT != 0 && AHEAD_ALL) {
    // whole row: rb bytes = rb/64 lines, line i by lane i % 32
    for (uint32_t line = lane; line * 64u < rb; line += 32u) pf<HINT>(wr + size_t(line) * 64u, 64);
  }
  float A = 0.f;
  uint32_t base = lane * 8u;
  for (; base + (U - 1) * 256u + 8u <= k; base += U * 256u) {
    if constexpr (HINT != 0 && !AHEAD_ALL && D > 0) {
      // the batch D ahead: bytes [(base0 + D*U*256)*2, + U*512) of the row, 16*U bytes per lane
      const uint32_t b0 = (base - lane * 8u) + D * U * 256u;
      if (b0 + U * 256u <= k) pf<HINT>(wr + size_t(b0) * 2u + lane * (U * 16u), U * 16u);
    }
    float wide[U][8];
#pragma unroll
    for (unsigned u = 0; u < U; ++u) {
      const sycl::vec<float, 4>* xv = reinterpret_cast<const sycl::vec<float, 4>*>(x + base + u * 256u);
      const auto a0 = xv[0], a1 = xv[1];
#pragma unroll
      for (unsigned j = 0; j < 4; ++j) { wide[u][j] = a0[j]; wide[u][j + 4] = a1[j]; }
    }
    sycl::vec<uint16_t, 8> w[U];
#pragma unroll
    for (unsigned u = 0; u < U; ++u) w[u] = *reinterpret_cast<const sycl::vec<uint16_t, 8>*>(wr + size_t(base + u * 256u) * 2u);
#pragma unroll
    for (unsigned u = 0; u < U; ++u) {
#pragma unroll
      for (unsigned j = 0; j < 8; ++j) { const float product = bf16f(w[u][j]) * wide[u][j]; A = A + product; }
    }
  }
  for (; base + 8u <= k; base += 256u) {
    float wide[8];
    {
      const sycl::vec<float, 4>* xv = reinterpret_cast<const sycl::vec<float, 4>*>(x + base);
      const auto a0 = xv[0], a1 = xv[1];
#pragma unroll
      for (unsigned j = 0; j < 4; ++j) { wide[j] = a0[j]; wide[j + 4] = a1[j]; }
    }
    const auto w = *reinterpret_cast<const sycl::vec<uint16_t, 8>*>(wr + size_t(base) * 2u);
#pragma unroll
    for (unsigned j = 0; j < 8; ++j) { const float product = bf16f(w[j]) * wide[j]; A = A + product; }
  }
  if (base < k) {
    const uint16_t* w16 = reinterpret_cast<const uint16_t*>(wr);
    float values[8], wide[8];
    for (unsigned j = 0; base + j < k; ++j) { values[j] = bf16f(w16[base + j]); wide[j] = x[base + j]; }
    for (unsigned j = 0; base + j < k; ++j) { const float product = values[j] * wide[j]; A = A + product; }
  }
  A = row_tree(sg, A, lane);
  if (lane == 0) y[row] = A;
}

// Up to two dense matrices (low + inject) in one launch; subgroup s < m0.rows -> matrix 0, else matrix 1.
struct Mat { const uint8_t* w; const float* x; float* y; uint32_t rows, k, rb; };
template <unsigned U, unsigned D, int HINT, bool ALL>
inline void low_pair(const Mat& m0, const Mat& m1, unsigned count, sycl::nd_item<1> it) {
  auto sg = it.get_sub_group();
  const uint32_t gsub = uint32_t(it.get_group_linear_id()) * uint32_t(it.get_local_range(0) / 32) +
                        uint32_t(sg.get_group_linear_id());
  if (gsub < m0.rows) low_row_pf<U, D, HINT, ALL>(m0.w, m0.x, m0.y, m0.rows, m0.k, m0.rb, sg, gsub);
  else if (count > 1) low_row_pf<U, D, HINT, ALL>(m1.w, m1.x, m1.y, m1.rows, m1.k, m1.rb, sg, gsub - m0.rows);
}

// Gate GEMV (K <= 512, K % 8 == 0, K > 256): NR consecutive rows per subgroup, every row's loads issued first, then
// each row's unchanged lane chain (chunk 8l, then chunk 256+8l when it fits) and its own 32-lane tree.
template <unsigned NR, int HINT>
inline void gate_rows(const uint8_t* W, const float* x, float* y, uint32_t rows, uint32_t k, uint32_t rb,
                      const sycl::sub_group& sg, uint32_t sgid) {
  const unsigned lane = sg.get_local_linear_id();
  const uint32_t row0 = sgid * NR;
  if (row0 >= rows) return;
  const uint32_t b0 = lane * 8u, b1 = 256u + lane * 8u;
  const bool has1 = b1 + 8u <= k;
  if constexpr (HINT != 0) {
    // prefetch the next subgroup-stride block of rows is not useful here; prefetch this block's rows line by line
#pragma unroll
    for (unsigned r = 0; r < NR; ++r) {
      const uint32_t row = row0 + r < rows ? row0 + r : row0;
      if (lane * 64u < rb) pf<HINT>(W + size_t(row) * rb + lane * 64u, 64);
    }
  }
  float x0[8], x1[8];
  {
    const sycl::vec<float, 4>* xv = reinterpret_cast<const sycl::vec<float, 4>*>(x + b0);
    const auto a0 = xv[0], a1 = xv[1];
#pragma unroll
    for (unsigned j = 0; j < 4; ++j) { x0[j] = a0[j]; x0[j + 4] = a1[j]; }
  }
  if (has1) {
    const sycl::vec<float, 4>* xv = reinterpret_cast<const sycl::vec<float, 4>*>(x + b1);
    const auto a0 = xv[0], a1 = xv[1];
#pragma unroll
    for (unsigned j = 0; j < 4; ++j) { x1[j] = a0[j]; x1[j + 4] = a1[j]; }
  }
  sycl::vec<uint16_t, 8> w0[NR], w1[NR];
#pragma unroll
  for (unsigned r = 0; r < NR; ++r) {
    const uint32_t row = row0 + r < rows ? row0 + r : row0;
    w0[r] = *reinterpret_cast<const sycl::vec<uint16_t, 8>*>(W + size_t(row) * rb + size_t(b0) * 2u);
    if (has1) w1[r] = *reinterpret_cast<const sycl::vec<uint16_t, 8>*>(W + size_t(row) * rb + size_t(b1) * 2u);
  }
  float A[NR];
#pragma unroll
  for (unsigned r = 0; r < NR; ++r) {
    A[r] = 0.f;
#pragma unroll
    for (unsigned j = 0; j < 8; ++j) { const float product = bf16f(w0[r][j]) * x0[j]; A[r] = A[r] + product; }
    if (has1) {
#pragma unroll
      for (unsigned j = 0; j < 8; ++j) { const float product = bf16f(w1[r][j]) * x1[j]; A[r] = A[r] + product; }
    }
  }
#pragma unroll
  for (unsigned r = 0; r < NR; ++r) {
    const float v = row_tree(sg, A[r], lane);
    if (lane == 0 && row0 + r < rows) y[row0 + r] = v;
  }
}

// HC norm in one launch: one work-group per stream row (4 for H = 2560 x 4 streams), WGS items (multiple of 32).
// Same guard semantics as specialised::body (inactive or error: nothing written; position out of range: item 0 of
// row 0 sets the error word), the same stage-0 partials (also written to the engine's scratch row, as stage 0 does),
// the engine's own upper() over them and the same output expression.
struct NormArgs {
  const float* x; const float* gain; float* y; float* scratch;
  int32_t* error; const int32_t* position; const int32_t* active;
  int capacity, tokens, flags;  // flags: bit 0 = unit offset, bit 3 = F32 gain (required here)
};
template <unsigned WGS>
inline void norm_one(const NormArgs a, sycl::nd_item<1> it, float* part /* 80 + 1 floats of local memory */) {
  constexpr int W = 2560, C = 80, HEADS = 4, NSG = WGS / 32;
  static_assert(WGS % 32 == 0 && C % NSG == 0, "chunks split evenly over the subgroups");
  constexpr int CPS = C / NSG;  // chunks per subgroup
  auto g = it.get_group();
  auto sg = it.get_sub_group();
  const int lane = int(sg.get_local_linear_id()), sgi = int(sg.get_group_linear_id());
  const int row = int(g.get_group_linear_id());
  using ref = sycl::atomic_ref<int32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                               sycl::access::address_space::global_space>;
  // guard, read once per subgroup as the engine's CachedGuard path does
  const int act = sycl::group_broadcast(sg, lane == 0 ? a.active[0] : 0, 0);
  const int err = sycl::group_broadcast(sg, lane == 0 ? ref(a.error[0]).load() : 0, 0);
  if (!act || err) return;
  const int pos = a.position[0];
  if (pos < 0 || pos > a.capacity - a.tokens) {
    if (row == 0 && it.get_local_linear_id() == 0) ref(a.error[0]).store(1);
    return;
  }
  float xs[CPS];
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int c = sgi + j * NSG, k = c * 32 + lane;
    const float xv = a.x[row * W + k];
    xs[j] = xv;
    float v = xv * xv;
#pragma unroll
    for (int s = 1; s < 32; s *= 2) {
      const float rhs = sycl::select_from_group(sg, v, (lane + s) % 32);
      if (lane % (2 * s) == 0) v = v + rhs;
    }
    if (lane == 0) { part[c] = v; a.scratch[row * C + c] = v; }
  }
  sycl::group_barrier(g);
  if (it.get_local_linear_id() == 0) part[C] = detmath::rsqrt(specialised::upper(part, C) / float(W) + 1e-6f);
  sycl::group_barrier(g);
  const float inv = part[C];
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int c = sgi + j * NSG, k = c * 32 + lane;
    const float y = (xs[j] * inv) * (a.gain[(row % HEADS) * W + k] + float(a.flags & 1));
    a.y[row * W + k] = y;
  }
}
// The engine's upper(p, 80) (specialised.hpp: adjacent tree with odd-tail +0 nodes) evaluated by one 32-lane subgroup.
// Levels 1..16 of upper() are three adjacent subtrees: leaves 0..31 (a), 32..63 (b) and 64..79 (c, levels 1..8 only).
// The rest of upper(): stride 16: v64 = v64 + 0 (no right child); stride 32: v0 = v0 + v32, v64 = v64 + 0;
// stride 64: v0 = v0 + v64. Valid in lane 0.
inline float upper80_sg(const sycl::sub_group& sg, const float* part, int lane) {
  float a = part[lane], b = part[32 + lane], c = lane < 16 ? part[64 + lane] : 0.f;
#pragma unroll
  for (int s = 1; s < 32; s *= 2) {
    const float ra = sycl::select_from_group(sg, a, (lane + s) % 32);
    const float rb = sycl::select_from_group(sg, b, (lane + s) % 32);
    const float rc = sycl::select_from_group(sg, c, (lane + s) % 32);
    if (lane % (2 * s) == 0) {
      a = a + ra;
      b = b + rb;
      if (s < 16) c = c + rc;
    }
  }
  float v64 = c + 0.f;
  float v0 = a + b;
  v64 = v64 + 0.f;
  v0 = v0 + v64;
  return v0;
}
// norm_one with the gain loaded at entry (independent of x) and upper() by subgroup 0 (upper80_sg).
template <unsigned WGS>
inline void norm_one2(const NormArgs a, sycl::nd_item<1> it, float* part /* 80 + 1 floats of local memory */) {
  constexpr int W = 2560, C = 80, HEADS = 4, NSG = WGS / 32;
  static_assert(WGS % 32 == 0 && C % NSG == 0, "chunks split evenly over the subgroups");
  constexpr int CPS = C / NSG;
  auto g = it.get_group();
  auto sg = it.get_sub_group();
  const int lane = int(sg.get_local_linear_id()), sgi = int(sg.get_group_linear_id());
  const int row = int(g.get_group_linear_id());
  using ref = sycl::atomic_ref<int32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                               sycl::access::address_space::global_space>;
  const int act = sycl::group_broadcast(sg, lane == 0 ? a.active[0] : 0, 0);
  const int err = sycl::group_broadcast(sg, lane == 0 ? ref(a.error[0]).load() : 0, 0);
  if (!act || err) return;
  const int pos = a.position[0];
  if (pos < 0 || pos > a.capacity - a.tokens) {
    if (row == 0 && it.get_local_linear_id() == 0) ref(a.error[0]).store(1);
    return;
  }
  float xs[CPS], gs[CPS];
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int k = (sgi + j * NSG) * 32 + lane;
    xs[j] = a.x[row * W + k];
    gs[j] = a.gain[(row % HEADS) * W + k];
  }
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int c = sgi + j * NSG;
    float v = xs[j] * xs[j];
#pragma unroll
    for (int s = 1; s < 32; s *= 2) {
      const float rhs = sycl::select_from_group(sg, v, (lane + s) % 32);
      if (lane % (2 * s) == 0) v = v + rhs;
    }
    if (lane == 0) { part[c] = v; a.scratch[row * C + c] = v; }
  }
  sycl::group_barrier(g);
  if (sgi == 0) {
    const float total = upper80_sg(sg, part, lane);
    if (lane == 0) part[C] = detmath::rsqrt(total / float(W) + 1e-6f);
  }
  sycl::group_barrier(g);
  const float inv = part[C];
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int k = (sgi + j * NSG) * 32 + lane;
    a.y[row * W + k] = (xs[j] * inv) * (gs[j] + float(a.flags & 1));
  }
}
// bf16_multi with the matrix chosen by static indices only (no runtime index into the captured descriptor array, which
// can force the array into private memory): the same bf16_rows<R,U> call for the same subgroup and row.
template <unsigned R, unsigned U>
inline void bf16_multi_static(const std::array<iq3::kopt::dense_v2::Mat, 4>& m, unsigned count, sycl::nd_item<1> it) {
  const uint32_t gsub = uint32_t(it.get_group_linear_id()) * uint32_t(it.get_local_range(0) / 32) +
                        uint32_t(it.get_sub_group().get_group_linear_id());
  iq3::kopt::dense_v2::Mat d = m[0];
  if (count > 1 && gsub >= m[1].first_sub) d = m[1];
  if (count > 2 && gsub >= m[2].first_sub) d = m[2];
  if (count > 3 && gsub >= m[3].first_sub) d = m[3];
  iq3::kopt::dense_v2::bf16_rows<R, U>(d.w, d.x, d.y, d.rows, d.k, d.rb, it, gsub - d.first_sub);
}
// norm v3: every load issued at entry (guard words, x, gain) before any check; the same checks then decide.
template <unsigned WGS>
inline void norm_one3(const NormArgs a, sycl::nd_item<1> it, float* part) {
  constexpr int W = 2560, C = 80, HEADS = 4, NSG = WGS / 32;
  static_assert(WGS % 32 == 0 && C % NSG == 0, "chunks split evenly over the subgroups");
  constexpr int CPS = C / NSG;
  auto g = it.get_group();
  auto sg = it.get_sub_group();
  const int lane = int(sg.get_local_linear_id()), sgi = int(sg.get_group_linear_id());
  const int row = int(g.get_group_linear_id());
  using ref = sycl::atomic_ref<int32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                               sycl::access::address_space::global_space>;
  float xs[CPS], gs[CPS];
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int k = (sgi + j * NSG) * 32 + lane;
    xs[j] = a.x[row * W + k];
    gs[j] = a.gain[(row % HEADS) * W + k];
  }
  const int act0 = lane == 0 ? a.active[0] : 0, err0 = lane == 0 ? ref(a.error[0]).load() : 0, pos0 = lane == 0 ? a.position[0] : 0;
  const int act = sycl::group_broadcast(sg, act0, 0), err = sycl::group_broadcast(sg, err0, 0), pos = sycl::group_broadcast(sg, pos0, 0);
  if (!act || err) return;
  if (pos < 0 || pos > a.capacity - a.tokens) {
    if (row == 0 && it.get_local_linear_id() == 0) ref(a.error[0]).store(1);
    return;
  }
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int c = sgi + j * NSG;
    float v = xs[j] * xs[j];
#pragma unroll
    for (int s = 1; s < 32; s *= 2) {
      const float rhs = sycl::select_from_group(sg, v, (lane + s) % 32);
      if (lane % (2 * s) == 0) v = v + rhs;
    }
    if (lane == 0) { part[c] = v; a.scratch[row * C + c] = v; }
  }
  sycl::group_barrier(g);
  if (sgi == 0) {
    const float total = upper80_sg(sg, part, lane);
    if (lane == 0) part[C] = detmath::rsqrt(total / float(W) + 1e-6f);
  }
  sycl::group_barrier(g);
  const float inv = part[C];
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int k = (sgi + j * NSG) * 32 + lane;
    a.y[row * W + k] = (xs[j] * inv) * (gs[j] + float(a.flags & 1));
  }
}
// The HC combine (adapter.cpp CombineFast, F32: gate = 2*sigmoid(inject[h]/4); streams[h][k] += branch[k]*gate, with
// the guard "inactive or error: nothing") followed by the HC norm of the same streams, in one launch: work-group h owns
// stream row h, writes its combined row to streams exactly as CombineFast does, then normalizes the values it holds
// (norm_one3). The combine has no position check; the norm's position check runs after the combine's write, as when
// the two kernels run in order.
struct CNArgs {
  float* streams; const float* branch; const float* cinj; const float* gain; float* y; float* scratch;
  int32_t* error; const int32_t* position; const int32_t* active; int capacity, tokens, flags;
};
template <unsigned WGS>
inline void combine_norm_one(const CNArgs a, sycl::nd_item<1> it, float* part) {
  constexpr int W = 2560, C = 80, HEADS = 4, NSG = WGS / 32;
  static_assert(WGS % 32 == 0 && C % NSG == 0, "chunks split evenly over the subgroups");
  constexpr int CPS = C / NSG;
  auto g = it.get_group();
  auto sg = it.get_sub_group();
  const int lane = int(sg.get_local_linear_id()), sgi = int(sg.get_group_linear_id());
  const int row = int(g.get_group_linear_id());
  using ref = sycl::atomic_ref<int32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                               sycl::access::address_space::global_space>;
  float xs[CPS], bs[CPS], gs[CPS];
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int k = (sgi + j * NSG) * 32 + lane;
    xs[j] = a.streams[row * W + k];
    bs[j] = a.branch[k];
    gs[j] = a.gain[(row % HEADS) * W + k];
  }
  const float inj = a.cinj[row];
  const int act0 = lane == 0 ? a.active[0] : 0, err0 = lane == 0 ? ref(a.error[0]).load() : 0, pos0 = lane == 0 ? a.position[0] : 0;
  const int act = sycl::group_broadcast(sg, act0, 0), err = sycl::group_broadcast(sg, err0, 0), pos = sycl::group_broadcast(sg, pos0, 0);
  if (!act || err) return;
  const float gate = 2.f * ng::sigmoid(inj / 4.f);
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int k = (sgi + j * NSG) * 32 + lane;
    xs[j] = xs[j] + bs[j] * gate;
    a.streams[row * W + k] = xs[j];
  }
  if (pos < 0 || pos > a.capacity - a.tokens) {
    if (row == 0 && it.get_local_linear_id() == 0) ref(a.error[0]).store(1);
    return;
  }
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int c = sgi + j * NSG;
    float v = xs[j] * xs[j];
#pragma unroll
    for (int s = 1; s < 32; s *= 2) {
      const float rhs = sycl::select_from_group(sg, v, (lane + s) % 32);
      if (lane % (2 * s) == 0) v = v + rhs;
    }
    if (lane == 0) { part[c] = v; a.scratch[row * C + c] = v; }
  }
  sycl::group_barrier(g);
  if (sgi == 0) {
    const float total = upper80_sg(sg, part, lane);
    if (lane == 0) part[C] = detmath::rsqrt(total / float(W) + 1e-6f);
  }
  sycl::group_barrier(g);
  const float inv = part[C];
#pragma unroll
  for (int j = 0; j < CPS; ++j) {
    const int k = (sgi + j * NSG) * 32 + lane;
    a.y[row * W + k] = (xs[j] * inv) * (gs[j] + float(a.flags & 1));
  }
}
}  // namespace hck
