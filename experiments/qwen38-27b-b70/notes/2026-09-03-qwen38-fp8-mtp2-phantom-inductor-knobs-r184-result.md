# R184: Inductor knobs on the published R156 image, depth 2, async on

Date: 2026-09-03 19:08-19:3x EDT, boot 88f0984f (clean). Prereg
`data/2026-09-03-qwen38-fp8-r156-mtp2-phantom-inductor-knobs-r184-prereg.json`. XPU graphs are disabled on this
lane by default (`XPU Graph is disabled by environment variable`; resolved `cudagraph_mode` NONE), so graph
capture was not an arm. Each arm's override was confirmed in the server's resolved `inductor_compile_config`.

| arm | knob | 64-pass (async on) |
|---|---|---|
| b | `allow_buffer_reuse=false` | phantom on cache-c032 (`[60, 271, 3833]`), 63/64, no other row moved |
| c | `max_fusion_size=1` | phantom on cache-c032, 63/64, no other row moved |
| d | `pattern_matcher=false` | phantom on cache-c032, 63/64, no other row moved (19:26) |

Reading: none of Inductor buffer planning, kernel fusion (at the `max_fusion_size` level) or the pattern matcher
is the mechanism, and none of the three knobs changed a single token elsewhere, so they are numerically inert on
this graph. The
phantom needs the full VLLM_COMPILE pipeline (R183: absent under eager) but not these two Inductor choices.
R185 bisects the compile stack instead (backend=eager under VLLM_COMPILE; DYNAMO_TRACE_ONCE; STOCK_TORCH_COMPILE).

## R185 (19:27-19:39): compile-stack bisection on R156, depth 2, async on

| arm | config | result |
|---|---|---|
| e | mode 3 + `backend=eager` | void: Dynamo traces vLLM's Triton RMSNorm path and fails on `torch.xpu.get_device_properties` (server never healthy) |
| f | mode 2 `DYNAMO_TRACE_ONCE` (no Inductor, no piecewise) | **no phantom**; 11 tie-class rows differ mid-sequence (cache-c032 @35 with a normal first token) |
| g | mode 1 `STOCK_TORCH_COMPILE` | void: `aot_autograd() does not yet handle input mutations on views with different dtypes` in the warm-up |

Standing picture: phantom present only under the full VLLM_COMPILE pipeline with an unsplit graph; absent under
eager (R183), Dynamo-only (R185f) and with a mutating custom op per layer (R182). The three Inductor knobs of
R184 are numerically inert, while removing Inductor or splitting the graph flips the same tie-class rows, so the
compiled kernels' numerics come from Inductor codegen and the phantom rides on something the piecewise
VLLM_COMPILE pipeline does that plain Inductor knobs do not touch: vLLM's post-grad passes or the splitting itself.

## R186 (19:43-19:5x): vLLM passes, piecewise splitting, final-op probe

| arm | config | result |
|---|---|---|
| h | mode 3, every `pass_config` pass false (noop elimination and all fusions) | phantom on cache-c032, 63/64, no other row moved |
| j | mode 3, `splitting_ops=[]` (one Inductor graph, 41 s compile) | **no phantom**; 11 tie rows differ, token-identical to R185f (Dynamo-only) on all 64 rows |
| n | R176 probe image + the custom op after the final norm only | (below) |

Reading: the vLLM post-grad passes are not involved (h, inert). The piecewise pipeline is: with one whole graph
(j) the outputs equal the FX-eager run token for token and the phantom is gone; with the default attention/GDN
split points the tie rows move and the phantom appears; with extra split points at every layer (R182) the
phantom is gone again. So it is not "splitting" as such but the specific default piece structure, or what the
piecewise runner does at piece boundaries for the mutating attention/GDN ops (their `output` buffers) under async
scheduling.

### R186n (19:55-20:01): the phantom persists with a single graph-end op, as the 220 variant

`phantom_first_token_rows: []` is a detector artifact: cache-c032 diverges at index 0 with first token 220 (a
space) followed by `001]`, i.e. the same "the model's view of the prompt ends early" defect with a different
corrupted value (the R170-era note already recorded 60 vs 220 varying with the graph). So a mutating op after the
final norm alone does not remove the phantom; R182's per-layer split did. The final-norm probe line for request
33 is now recorded in situ under the phantom (128 `final_norm` lines); R186n-b (same image, async off) is queued
before R187 to give the exact clean-vs-phantom comparison of that row. Detector rule from now on: judge the
phantom by divergence at index 0 vs the oracle, not by token 60.

Process note (20:02): killing a queued wrapper after its wait loop has passed does not kill the campaign it
already spawned; the R187 runner had launched `run-...-r152.sh` (pid 47866) seconds before it was killed, and
that campaign is the valid R187 (clean preflight 20:02:11). The R186n-b launch then lost the port race to R187's
MTP0 server (`docker run` failed on the published port) and was re-queued behind R187. Before killing a queued
runner, check for its r152 child with `pgrep -af r152.sh`.

### R186n vs R186n-b (20:43-20:49): the phantom measured in situ at the final norm

R186n-b (same final-op probe image, `--no-async-scheduling`) is 64/64. Comparing the `final_norm` probe lines
(abs-sums of the last two real rows after the final RMSNorm) of the 64 prefills, phantom run vs control:

| | TP0 last row | TP1 last row | TP0 row before last | TP1 row before last |
|---|---|---|---|---|
| request 33 (cache-c032), phantom run | 5982.85 | 6022.08 | 6518.65 | 6518.65 |
| request 33, clean control | 7167.73 | 7167.73 | 6510.96 | 6510.96 |
| every other request | equal | equal | equal | equal |

So in the phantom run the last **two** rows of request 33's final hidden state are wrong (not only the sampled
last row), and the two TP ranks **disagree** on the last row while they agree on everything else and agree with
each other in the control. Rank-local disagreement after the model's last all-reduce means the corruption enters
the rank-replicated residual stream (not the all-reduced hidden path) from rank-local data that differs between
ranks: stale or uninitialised memory, deterministic per graph because the previous step's contents are
deterministic (hence token 60 on one graph and 220 on another). The model-level row count is 31 in both runs
(`n=31 rows=31`), so it is not padding at the model boundary. Together with R186j (one graph: clean) and R182
(split at every layer: clean), the reading is a tail-of-sequence read past the written rows inside a default
piecewise piece, whose stale content under async scheduling is the discarded extra step's rows.
