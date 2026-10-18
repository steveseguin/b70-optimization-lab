# CPU analysis

Only a clean, released capture passing every token comparison can enter replay.
`capture_inputs.py` checks the original oracle binding, source seal, input hashes,
device isolation, drain, rank metadata, all route rows and raw-byte hashes.
No synthetic fallback supplies prediction or speed evidence.

Run from this directory, with each command prefixed by
`nice -n 19 taskset -c 8-15,24-31 python3 -B` and stdin from `/dev/null`:

1. `build_replay.py` builds two CPU-only shared libraries through the shared
   compile turn. Intel platform/compiler dependencies are ordinary dependencies.
2. `replay_gate.py` checks GNU/Intel fresh-process equality, real router weights,
   ties and nonfinite refusal. It reads only 251.7 MB of router tensors from GGUF,
   checks tensor directories against the pinned native plan, and records hashes.
3. `prepare_prefill.py` extracts the same prompts' historical packet55 target
   prefill routes. These 912 positions initialize both simulated caches equally.
   They are not one-card measurements or newly captured packet138 states.
4. `timing_inputs.py` pins the 58p token/cache spans and 58g/58i remote-cost proxies.
5. `analysis_gate.py` validates preparation and runs the simulator and full-layout
   tests without touching device preparation or any capture evidence.
6. After capture release, `router_replay.py` checks every same-layer BF16 router
   logit and top-ten route against the captured values. Any mismatch stops
   analysis. Then it replays next-layer weights on each available predictor input.
7. `simulate.py` reports all 15 predictor/width combinations in three scenarios.

Every CPU-only main process caps virtual address space at 4 GiB. OpenMP uses four
threads; no numpy package is required. Raw captures are mmap-read, not copied into
a second persistent artifact. Builds are about 67 MB; the raw capture is 801 MB.

## Arithmetic and prediction

Read F32 `ffn_gate_inp.weight` from GGUF at the validated absolute tensor offset.
Use the unchanged split-four constant router reduction, round logits to BF16,
then use the production probability arithmetic and expert-ID tie break. Ranking
raw logits instead would mishandle probability ties. Same-layer equality is a
separate necessary gate, even after CPU compiler-repeat tests pass.

For target layer L+1, evaluate its unchanged router on L's router input and each
of L's four BF16 output residual streams. Keep the five predictors separate.
Widths 10, 12 and 16 all score against the actual ten experts. Per-prompt/layer
rows retain category, counts and recall. The first target layer has no prediction.
Output residual predictions are available at layer end and receive a shorter
transfer window than router-input predictions. No weights or thresholds are fit.

## Cache and timing assumptions

Capacity is 18,000,000,000 bytes, globally shared across layers with the original
LRU order and 256-byte slot alignment. Actual GGUF expert sizes are used, including
the larger layer 2. Both arms start empty, preserve cache across requests, include
prefill, and drain pending copies at request boundaries. Decode evidence is
48 accepted tokens per prompt, not the benchmark's 99-interval speed measure.

The control models 58v's delayed plans and single copy transaction. Current misses
remain zero-copy. Victims are revoked before DMA; new slots are invisible until
completion and a safe publication boundary. Prefetch cannot run beside an
outstanding transaction or evict current-layer readers. All submitted bytes count,
including wrong predictions, late transfers and replaced cache contents. Candidate
demand planning moves after layer prefetches; an extra planning cost is charged.
This is an event model, not a new device implementation.

No measured per-layer clock is available in 58g/58p. The 0.645465 ms equal share of
58p's token span minus cache span is a timing proxy, with 25/50/100% causal-window
fractions. Effective copy bandwidth is 9.5/12.5/18.75 GB/s. Predictor plus publication
cost is 0.060/0.030/0.012 ms per eligible layer; planning adds 0.25/0.10/0.05 ms per
token. Per-fill submission costs are 0.006/0.003/0.001 ms. These are sensitivity
assumptions. The model also charges overflow bytes serially; late zero-copy reads
still count. Layer-2 and ordinary expert remote penalties remain distinct.

The modeled 58v control period is 58p's reciprocal rate minus half its measured
cache span; 58v's actual rate is still pending. Candidate deltas use matched
calibration cache misses and the historical K1 remote-cost proxies. They do not
claim that calibration text has the benchmark's measured rate. All outputs say
projected, not measured. Sources and exact assumptions are machine-readable in
`evidence/timing-inputs.json`.

Preregistered before real capture: recommend phase-2 design only when at least
one predictor/width clears +3% in all three scenarios and every submitted
prefetch fits its assumed causal window. Otherwise close this phase-1 arm with
the failure and revisit conditions. With no capture, the decision stays pending.
A positive recommendation is conditional on the timing model; device correctness
and actual causal windows remain phase-2 work. No phase-2 code is part of this task.

## Idea credit

The idea family is credited to Ranggi Hwang et al.,
[Pre-gated MoE](https://arxiv.org/abs/2308.12066), and the adjacent-layer gate-input
prediction idea to Zhiyuan Fang et al.,
[Accurate Expert Predictions in MoE Inference via Cross-Layer Gate](https://arxiv.org/abs/2502.12224).
Only those ideas motivate this experiment. The lab writes its own implementation
and retains its unchanged router, exact target route, model bytes, cache precision
and quality gates. Neither paper's performance or broader techniques are claimed
as lab results or adopted here.
