# Device-resident MTP3 phase 1: required runtime boundary

## Objective

Remove the per-draft-step device-to-host-to-device path for the Qwen MTP
token and `h_nextn` row while preserving candidate-0, chained KV, and fixed
MTP3 semantics.

## Measured code path

The current path is structurally host mediated:

1. `llama_context::decode()` builds backend `t_h_nextn` and backend sampler
   candidate tensors.
2. `llama-context.cpp` schedules async copies of both into host-owned output
   buffers.
3. `common_speculative_impl_draft_mtp::draft()` synchronizes through the host
   accessors, selects candidate 0, and copies `h_nextn` into `llama_batch`.
4. `llm_graph_input_embd_h::set_input()` uploads that token and hidden row for
   the next MTP decode.

`LLAMA_MTP_FUSED_TOP1_HOST_BOUNDARY` only combines repeated synchronization
and host accessor work. It still performs D2H for candidate/probability/hidden
and H2D for token/hidden, so it is not a device-resident implementation.

## Why raw backend tensor exposure is unsafe

The tensors in `llm_graph_result` are allocated by the graph scheduler. A
subsequent graph reset or allocation may invalidate or reuse their storage.
Passing `t_h_nextn` or `t_candidates` directly to the next decode therefore
cannot be made correct by adding getters. Exact graph reuse helps but is not a
lifetime contract, and a fallback rebuild would silently consume aliased or
overwritten data.

## Required internal API

The safe phase-1 runtime change has four pieces:

1. Add context-owned, fixed-address backend staging tensors for one token, one
   probability, and one `h_nextn` row per active sequence and MTP step. Their
   buffers must outlive scheduler graph resets.
2. At the end of an MTP decode, copy candidate 0, its probability, and the
   selected hidden row backend-to-backend into that staging area before the
   scheduler can reuse output allocation.
3. Add a device-input variant of `llm_graph_input_embd_h::set_input()` that
   consumes those staging tensors without first performing the ordinary host
   token/hidden uploads. Position, sequence ID, output mask, and memory
   transaction metadata may remain host inputs in phase 1.
4. Submit all three fixed MTP steps before host materialization. Apply `p_min`
   and expose the draft vector only after the unrolled submission. Otherwise
   reading probability/token after each step still synchronizes the queue and
   eliminates most of the intended benefit.

The final item implies speculative over-computation when a step fails `p_min`.
That is required for a fixed MTP3 command sequence and must be evaluated
against the removed synchronization cost.

## Correctness tests required before performance testing

- Backend staging survives an intervening graph reset and forced graph rebuild.
- Device-input and host-input MTP steps produce identical candidate-0 token,
  probability, and `h_nextn` bytes for M=1.
- MTP3 draft vectors match at every early-stop position (`p_min` failure at
  step 0, 1, 2, and no failure).
- KV positions and candidate-0 target verification match for full acceptance,
  partial acceptance, and rejection.
- The device path is default off and rejects unsupported backends instead of
  falling back through host copies silently.

## Validation status

The existing host-boundary consolidation compiled through
`common/speculative.cpp`, `src/llama-context.cpp`, and the server target. The
full JIT link was blocked by an unrelated concurrent SYCL MMVQ compile error:
`use_simd4` was captured as a non-constant global in a device kernel. No claim
is made that a D2H/H2D boundary has yet been removed.
