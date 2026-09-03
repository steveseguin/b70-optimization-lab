# A87 observation and A88 preregistration: the serial-attention gate did not fire

Date: 2026-09-03

A87 (A85 plus overlay `d3a61403`, `VLLM_XPU_FA_SERIAL_SPEC_DECODE=1`
exported and present in the server environment) came up, captured its
graph, passed the exact canary and ran the battery, but the port's
"reached" marker never printed: none of graph capture, the canary, or the
requests entered the serial branch, so A87 measures the A85 identity again
(its rows are recorded as an A85 repeat in the A87 data file).

A88 is the A87 packet at attempt 88 / port 19760 on overlay `53d6594b`,
which adds one warning per process just before the gate printing every
clause the gate tests (`max_seqlen_q`, dynamic causal, mask mods,
`num_actual_tokens`, `cu_seqlens_q`, `seqused_k`, FA version) whenever the
flag is set and a multi-row batch arrives, and a second one-time line when
only single-row batches are seen. Its battery is the same; the point is the
diagnostic line. Generator `tools/rewrite-q38-a87-to-a88-fa-diag.py`.

## A88 answer and A89

A88 came up and passed its canary with no diagnostic line at all, not even
the single-row one: the flag was in the API server's environment but not
in the engine core's or the workers' (`/proc/<pid>/environ`). vLLM forwards
only registered `VLLM_*` variables to those processes (the mkldnn flag
works because 805cde59 registered it in `envs.py`). Overlay `0a03a84c`
registers `VLLM_XPU_FA_SERIAL_SPEC_DECODE` in `envs.py` and reads it
through `envs` in the attention gate; A88 was stopped after its canary.
A89 is the A88 packet at attempt 89 / port 19761 on that head
(`tools/rewrite-q38-a88-to-a89-registered-flag.py`); same battery and
pins. The "reached" marker is the first thing to look for.

## A89 and where this stands (13:00)

A89 (flag registered in `envs.py`, read through `envs`) also produced no
diagnostic line and repeated A85's outputs (short `31.06 / 32.09 / 37.96
tok/s`, exact-2K `29a2947a...`; stopped after that row). Three
corrections to the reasoning above:

- The engine core's and workers' `/proc/<pid>/environ` are not evidence:
  vLLM rewrites the process title (`VLLM::EngineCore`, `VLLM::Worker_TP0`),
  which overwrites the block `/proc` reads, so "the flag is missing there"
  was an artifact. The workers are forks of the API server, whose
  environment does carry the flag, and `envs.VLLM_XPU_MKLDNN_DETERMINISTIC`
  reaches `xpu_worker.init_device` the same way.
- Registering the flag was still right (it silences the "unknown vLLM
  environment variable" warning and is how every other lane flag is
  declared), but it was not the blocker.
- Since neither the multi-row nor the single-row diagnostic line ever
  printed in A88/A89, the gate's code is not executed with the flag true in
  the worker: either `FlashAttentionImpl.forward` takes a path that returns
  before that block for this model's full-attention layers (cascade, an
  encoder path, a fused kv-update variant, or a compiled/captured op that
  bypasses the Python forward after the first capture and the capture
  itself uses a different metadata shape), or `envs` evaluates false inside
  the worker for a reason the launch chain hides. The next step is an
  in-process check, not another 16-minute launch: a one-line unconditional
  `warning_once` at the top of `FlashAttentionImpl.forward` printing
  `max_seqlen_q`, `use_cascade`, `num_actual_tokens` and the `envs` value on
  the first call, run once on the A85 identity.

A87, A88 and A89 are three more fresh servers of the A85 identity: short
rows `30.7-38.0 tok/s`, exact-2K `29a2947a...` on all of them.

## A90 answer (13:07): the port was on the wrong class

A90 (overlay `a6356d5d`, an unconditional one-time warning at the top of
`FlashAttentionImpl.forward`) came up, captured, passed the exact canary
and served its first rows without printing that line once: on this model
`FlashAttentionImpl.forward` is never entered. The 12 full-attention layers
are `Qwen4ExpQSAAttention` (`vllm/models/qwen4_exp/amd/qsa.py`), whose
`Qwen4ExpQSAFlashAttentionImpl.forward_qsa` runs the model's own
query-sparse paged attention: the indexer's per-token top-k block
selection followed by the Triton `qsa_sparse_paged_attention` kernel,
through the `qwen4_exp_qsa_with_output` custom op. The 27B lane's serial
verifier-row flash-attention idea therefore does not apply as ported; the
R38 port (`d3a61403`, registered flag `0a03a84c`) stays in the overlay,
off by default and inert for this model, and the two diagnostics were
removed in `c23ad8e1f`.

What is left for the two-row verification step, after the exact recurrent
path (A85) and the M-invariant dense GEMMs (offline gate): the QSA indexer
and top-k selection with two query rows, the QSA sparse kernel itself, the
Triton block-FP8 MoE at M=2, and the rejection sampler. The next
diagnostic is offline and per component, in the A1 gate style: feed the
same hidden state as one row and as row two of a two-row batch through
each of those and compare bit for bit. A87-A90 add four fresh servers of
the A85 identity (short `30.7-38.0 tok/s`, exact-2K `29a2947a...` on every
one).
