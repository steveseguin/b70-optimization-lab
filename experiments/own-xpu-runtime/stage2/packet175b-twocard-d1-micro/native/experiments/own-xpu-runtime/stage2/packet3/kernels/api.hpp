#pragma once
#include "../../packet2/kernels/math.hpp"
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

// Host-only declarations: no SYCL runtime, discovery, allocation or readback.
// iq3::Type, bf16_bits, element, gemv_row and Route are packet 2's names.
namespace flash {
using Type = iq3::Type;
using Event = std::uint64_t;
struct Geometry {
  int h = 2560, low = 320, experts = 512, top = 10, mid = 640;
  int kh = 16, vh = 48, d = 128, qh = 24, kvh = 2, ad = 256, ih = 4, id = 128;
  int rotary = 64, budget = 2048, context = 32768, vocab = 248320, eos = 248044;
  static Geometry tiny() {
    return {16, 4, 16, 10, 8, 1, 3, 4, 4, 1, 4, 4, 4, 2, 8, 8, 16, 15};
  }
};
// All dimensions are row-major (reverse of GGUF's fastest-first dimensions).
// This is a loader descriptor, never a pointer to a materialized FP32 shadow.
struct Tensor {
  std::string name, grid, component;
  std::vector<int> shape;
  std::uint64_t bytes = 0;
};
enum class Scalar { bf16, f32, i32, u32, i64 };
inline unsigned scalar_bytes(Scalar t) {
  return t == Scalar::bf16 ? 2 : t == Scalar::i64 ? 8 : 4;
}
// card=-1 means TWO distinct allocations, one per card, never a shared pointer.
// handoff explicitly copies replicated logical buffers between their owners.
struct Buffer {
  std::string name;
  std::vector<int> shape;
  Scalar type = Scalar::bf16;
  int card = 0;
};
struct Launch {
  std::string op, label;
  std::vector<std::string> inputs, outputs, weights;
  std::vector<int> shape; // op-specific logical output/batch geometry
  int card = 0, parameter = 0, source_card = -1;
  std::uint64_t weight_bytes = 0, read_bytes = 0, write_bytes = 0;
};
// CONTRACT v1:
// ENTRY PRECONDITION: inputs_ready covers uploads to BOTH owners. Replicated
// active/position/token controls must already agree before begin.0/begin.1;
// a request reset may not update only card0. The later handoff transports the
// same controls with streams and sticky errors; it is not initial admission.
// * Every dynamic input (token, position, active flag, IDs, lengths, histories,
//   errors, sampler output) is device-resident. enqueue NEVER returns data.
// * Bindings and scratch are prepared before execute; enqueue cannot allocate,
//   perform file IO, JIT, host routing, synchronize or read back. Host lookup
//   tables require a separately admitted stable device-addressable mapping.
// * One logical launch per Launch; a backend that expands one must report the
//   physical launch count. This packet reports planned launch sites, not
//   measured driver dispatches. Native lowering/capture is not implemented
//   here.
// * IDs/lengths/routes are I32/U32, token history and PLE IDs are I64.
//   Packet2 Route is three U32 fields. No float-encoded native IDs.
// * Every launch depends on the preceding event, including cross-card handoff.
//   The final event covers commit. No independent compute queues/atomic sums.
// * packed GEMV: packet2 iq3::gemv_row 32 logical strided lanes, FP32 multiply
//   then add, tree32, BF16 RNE output; no extra BF16 weight rounding. Expert
//   GEMVs consume device Route/ID arrays, NEVER IDs copied to the controller.
// * norm: FP32 adjacent tree with odd zero padding, mean+1e-6, reciprocal sqrt,
//   stored GGUF gain directly (export already applied unit offsets). Conv:
//   chronological taps 0..3, no FMA; GDN history3, PLE dilation3/history9. PLE
//   conv accumulator rounds BF16 before SiLU (GDN does not); BF16 SiLU outputs
//   and stored history.
// * GDN: Q/K normalized FP32; dot128 has 32 contiguous groups of4 then tree;
//   stored ssm_a=-exp(A_log) multiplies softplus before decay exp (no second
//   exp(A_log) or inverse log). Then decay -> prediction -> beta correction ->
//   outer add -> output dot -> BF16 output and inter-row state. Never commit
//   state before output dot. Output RMS uses ordinary stored gain then
//   SIGMOID(z), per corrected packet1b/gate-evidence.json; conv/FFN/HC retain
//   SiLU.
// * route: FP32 softmax -> stable top10 (lower ID on ties) -> renormalize;
//   sum experts in selected order FP32, weight AFTER BF16 down, round BF16;
//   shared down*sigmoid(shared gate) rounds BF16 before routed+shared BF16.
// * QSA: pool4 chronological raw keys FP32 then BF16; norm/rotary; index score
//   ReLU dots summed in head order; lower block on ties; expand blocks in
//   selected order, append tail, -1-pad. KV is BF16, never compressed. Selected
//   order tree softmax/PV; sigmoid gate BF16 before output projection.
// * HC: per-stream stored-gain norm BF16, down BF16 /4 -> SiLU BF16 -> up BF16;
//   sum sigmoid(gate)*normalized stream in order0..3, /4 BF16; combine BF16.
// * argmax: finite FP32/BF16 logits, greatest value, lowest vocabulary ID ties,
//   +0/-0 tie. Nonfinite/error sets device failure flag and forbids commit.
// * scratch state is transactional: begin snapshots recurrent/conv state and
//   committed KV/index lengths; KV appends beyond the committed length. Ops
//   modify working state only; commit advances all histories/length/position
//   iff no error and active. Cancellation/failed submission never commits.
// * Two-card begin/commit execute on each owner. handoff copies streams and
//   controls 0->1; handoff_result returns error/token 1->0 before either
//   commit. All begin/commit kernels operate on that card's state/transaction
//   arena. commit.parameter marks the final host submission for the unified
//   CPU mock only; BOTH native commit sites advance their distinct local
//   positions once. It must never suppress card0's commit/position advance.
// * Device/Arena owner adapter must track these events/buffer leases through
//   ownrt::Device::compute and orderly Shutdown. UVA and peer operations need
//   additional admission; stage1's current compute accepts device buffers only.
class Backend {
public:
  virtual ~Backend() = default;
  virtual Event enqueue(const Launch &, Event dependency) = 0;
  // Submission failure poisons native execution until tracked work drains and
  // checkpoint restoration is proven; never free or restore busy GPU buffers.
  virtual void submission_failed() noexcept = 0;
};
struct Plan {
  Geometry g;
  std::vector<Launch> launches;
  std::vector<Buffer> buffers;
  Event execute(Backend &b, Event inputs_ready) const {
    auto e = inputs_ready;
    try {
      for (const auto &launch : launches)
        e = b.enqueue(launch, e);
    } catch (...) {
      b.submission_failed();
      throw;
    }
    return e;
  }
};
} // namespace flash
