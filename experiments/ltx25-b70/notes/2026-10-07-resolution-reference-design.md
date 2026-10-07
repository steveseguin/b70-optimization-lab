# Independent 640×384 reference design — October 7, 2026

Status: **source design only; not implemented, ready, admitted or qualified**.
This is the next useful-resolution question after the20/28 placement decision
and any justified W3 scheduling screen. It does not authorize changing the
active runtime or promote packet98's larger-size speed-only arms.

The question is whether the optimized batch-one pipeline preserves an
independently recomputed640×384 native-sampling reference, and what generates
that output fastest without changing its bytes. Existing decoder probes show
higher spatial cost, but no qualified larger-size full-pipeline throughput
result: [resolution cost evidence](2026-10-06-resolution-cost-probe.md).

## Existing reference skeleton

Use the qualified current-source packet's
[`graphs/host-embedding-control.json`](/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b/graphs/host-embedding-control.json)
as the graph skeleton, with an explicitly reviewed successor identity. Packet99b
is the identified23/25 source/arithmetic control; do not silently substitute
an unqualified placement candidate. The final chosen placement needs its own
qualification before becoming a reference execution configuration.

- Set node356 `EmptyLTXVLatentVideo` to width320, height192, length25,
  batch_size1. The unchanged native two-stage upsampler produces640×384.
- Keep native `SamplerCustomAdvanced` nodes344 and368, the original8+3
  sigma sequences, native `LTXVLatentUpsampler`348, native `VAEDecode`374,
  and native audio decode358. Preserve prompts, seeds, BF16 model identity,
  strict determinism and current qualified RoPE arithmetic.
- Keep the existing sharded host loader420 so model weights need not fit on
  one card. Do not install transformer graph routes, lean-conditioning
  pipeline, decoder replicas or save-behind in the reference execution path.
- Keep `LTXBaselineCapture`414 with images, video latent, audio latent and
  waveform wired to the corresponding native outputs. Its
  [implementation](../scripts/capture_node.py) retains original tensor dtypes,
  records shape/hash/finite checks and refuses an existing output directory.
  Optional preview encoding is outside the raw-tensor reference claim.

Reference stage shapes are video latents `[1,128,4,6,10]` then
`[1,128,4,12,20]`, with240 and960 video tokens. Final images are
`[25,384,640,3]`; the existing25-frame audio workload remains unchanged.
These shapes follow the [size helper](../scripts/ltx_output_size_98.py), not
an instruction to reuse its speed-only admission as a quality gate.

## Accepted encoder, independently executed sampler

The skeleton's original `CLIPTextEncode`364 uses the padded1024-token encode.
Leaving it unchanged would silently replace the accepted short-window
workload. Preserve the accepted encoding branch instead:

1. Add existing node425 `LTXTextEncoderGraphGate`, mode `graph-shard`,
   receiving the CLIP from420.
2. Use existing364 `LTXPipelineTextEncode`, mode `pipeline-window`, with
   current window qualification and its worker/depth contract.
3. Connect node365 conditioning directly to364 and remove421, the placement
   observer whose one-encode accounting is incompatible with this branch.
4. Bind each generated reference to its exact prompt/seed, window bucket,
   conditioning fingerprint and successful same-server window probe.

The current [window implementation](../scripts/ltx_text_window.py) explicitly
requires graph-sharded encoder layers and already-captured worker signatures.
The [text gate](../scripts/graph_text_encoder_node.py) and
[encoding node](../scripts/pipeline_node.py) enforce those requirements. Thus
this is **native eager sampler/decode recomputation with the accepted encoder**,
not an entirely eager end-to-end oracle. Each reference request is submitted
serially with a unique index; no future prompt needs to be queued. The window
node computes the request's conditioning and does not reuse generated clips.
There is no proposed attention-backend or precision substitution.

## Minimum reference and timing sequence

Prepare an explicitly sealed successor and bounded storage/memory admission
before any device execution. On one healthy application, run the references
**before** installing sampler graph routes or freezing optimized workers.
The existing [graph gate](../scripts/graph_capture_node.py) does not allow
`original` mode while graph routes remain installed; do not rely on toggling
an already-frozen optimized runtime back to a reference state.

1. Preregister three distinct fixtures, the exact graph/source/model/runtime
   and window policy, and fresh reference/request names. Preserve the accepted
   256×256 w93c reference set unchanged.
2. Submit every fixture twice as separate serial native-sampling executions.
   The [profile client](../scripts/profile-clip.py) provides the existing
   request/history/identity capture workflow. Bind every node's run name and
   clip index so repeated executions neither cache outputs nor collide with
   earlier receipts. Keep the launcher's `--cache-none` policy.
3. Require distinct successful request identities and exact equality of all
   four tensors between repeats with [compare-clip.py](../scripts/compare-clip.py).
   Pin these independently generated captures as the new same-size references.
   Do not copy the optimized candidate's outputs into its own oracle.
4. Only then prepare the optimized path on that same healthy endpoint, retaining
   existing capture/replay, ownership, freeze, native/replica decode and health
   gates. Require each of the three optimized fixtures to match its native
   reference exactly before timed work.
5. Measure ten **emitted** timed clips cycling those three fixtures. Add the
   actual pipeline-fill prompts required by the selected graph; ten submitted
   prompts are not necessarily ten outputs. Preserve emission sequence and
   compare every output with the corresponding reference.

This small screen covers three fixture identities. Ten distinct timed fixtures
would require ten independently established references; three references cannot
qualify the other seven. Ten emitted clips provide a preliminary throughput
screen, not the full-suite p95/endurance milestone. Report generated frames per
wall second separately from24 playback FPS, full-request latency, initialization
and compilation. These remain independent25-frame clips, not coherent longer
video.

## Explicit harness changes still required

The [packet98 throughput client](../scripts/run-throughput-fixtures-98.py)
currently requires larger-size arms to use `--no-oracle` and records
`all_exact=null`. The [geometry helper](../scripts/ltx_output_size_98.py) forces
larger-size metadata to `none (speed only)` and refuses non-speed admission.
Those semantics are intentional historical limits, not a qualification path.

Implement a narrow, explicit same-size reference mode in a successor, binding
reference manifest, graph, geometry, fixture identities and all four tensor
hashes. Preserve the old speed-only mode and fail closed when reference coverage
or identities are missing. Update affected node admission, receipt labels and
client checks consistently; do not merely remove assertions or turn a
speed-only result into a quality claim. Exact independent comparison itself
is shape-generic, but the current size admission and campaign plumbing are not.
The historical [window-oracle constructor](../scripts/make-window-oracle-93.py)
contains useful distinct-execution and byte-verification checks; its two passes
of the optimized workload are not this independent native-sampler reference.

## Meaning and unresolved budgets

A pass would establish that the tested optimization matches the pinned640×384
native-sampling workload on these fixtures. It would not establish equality
with256×256 pixels, universal image quality, all prompts, longer sequences or
an untested placement. Review selected full-resolution samples as well as raw
parity; determinism alone does not establish attractive output.

Native eager sampler transients at240/960 tokens, coexistence with accepted
encoder graphs, and subsequent optimized capture allocations are not measured
on the current runtime. The [packet98 memory estimates](2026-10-06-packet-98-build.md)
are planning evidence, not transferable live admission. Preserve the2GiB device
floor, host admission and50GiB disk reserve; declare reference, repeat, candidate
and timed-output allowances before execution. One F32 image tensor alone is
73,728,000 bytes (about70.3MiB), before latents, waveform, metadata or previews.
Do not infer current feasibility from decoder-only peak memory.

No graph, harness, server, model, reference or device state was changed to write
this design. Implementation and independent CPU review remain pending.
