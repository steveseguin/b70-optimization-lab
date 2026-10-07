# Packet 98: choose the output size per server (build, 2026-10-06)

## In plain words

Packet 98 is built and sealed offline. **It has not run on the cards.** It keeps
packet 97's server and adds a picture-size setting. The normal 256×256 setting
still uses the same graphs and reference checks. The larger settings, 512×320
and 640×384, measure speed without claiming that their pictures match saved
references. No new references are made.

The larger runs still check graph replay, every sampler worker, native versus
replica decoding, the freeze and the full pipeline. These checks establish
consistency inside the run; they do not establish model-output parity at a
new size. Their summaries say **`none (speed only)`** in the references column.

Why: the [resolution probe](2026-10-06-resolution-cost-probe.md) measured a
3.2× decoder cost at 640×384, but could only estimate transformer cost. This
packet permits the full server measurement. It does not crop 640×384 to 640×360.

The live packet 97 campaign and its helpers are untouched. No GPU, checkpoint
load, server launch, sudo, host setting change or Git mutation was used to build
this packet. Existing prepared packets were read only.

## Build and seal

- Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-size-98`.
- Manifest SHA256: **`918b47a5530b4dc97fe8fc8f4ec77fd64521ec6846217c54f5fba589e0e8377f`**.
- Builder: [prepare-output-size-98.py](../scripts/prepare-output-size-98.py).
  It invokes the unchanged `prepare-graph-capture-runtime.py` with the new output
  path, requires its entire file inventory to reproduce packet 97's hashes, then
  applies the size overlay and seals it. It refuses an existing output directory.
- The base reproduced packet 97 manifest
  `6e232f72a9835727323c383bc9baaa167844b58dc6400a5de43a3b9eb4e44b9f` exactly.
- All existing graph files remain byte-identical. Added: 45 size-specific graphs
  and `source/scripts/ltx_output_size_98.py`. Updated only in the new packet:
  text, sampler and decode nodes (including their custom-node copies), graph
  capture adapter, checker and launcher. No numerical model source changes.
- The generator's checked string replacements fail on unexpected source changes.
  The gate retains packet 97's file hashes, inventory, source identity and graph
  checks. It additionally reconstructs every size graph from its original graph
  and permits only dimensions and the explicit size/speed admission inputs.
- Default manifest sections are unchanged except file/source hashes. Receipts
  add `output_size`; their source hashes necessarily change with the overlay.
  Timestamps, IDs and timings are run-specific as before.

To rebuild on a host where this output does not already exist:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/scripts/prepare-output-size-98.py
```

## Design and shape census

[ltx_output_size_98.py](../scripts/ltx_output_size_98.py) reads `LTX_OUTPUT_SIZE`
once at import. Only `256x256` (unset default), `512x320` and `640x384` are
accepted; empty strings, alternate spellings and 640×360 refuse.

| Output | Stage-1 pixels | Stage-1 latent | Stage-2 latent | Video tokens, stages 1 / 2 |
| --- | --- | --- | --- | --- |
| 256×256 | 128×128 | `[1,128,4,4,4]` | `[1,128,4,8,8]` | 64 / 256 |
| 512×320 | 256×160 | `[1,128,4,5,8]` | `[1,128,4,10,16]` | 160 / 640 |
| 640×384 | 320×192 | `[1,128,4,6,10]` | `[1,128,4,12,20]` | 240 / 960 |

- Graph node 356 (`EmptyLTXVLatentVideo`) is the only graph dimension literal.
  Its width and height become half the selected output dimensions; 25 frames
  remain four latent frames. Node 428 carries the unchanged two-stage sampler
  and native latent upsampler, which doubles spatial dimensions. Batch stacking
  happens after the batch-1 latent input is checked; outputs split back into
  batch-1 clips before decode.
- Every size has batch-1, batch-2 and batch-4 speed graphs, for workers 1–4,
  plus serial capture graphs. Names append `-speed-s<size>` to their base arm.
  The `256x256` runner deliberately uses the original unsuffixed graphs as the
  control; explicitly named 256×256 speed graphs are also available to clients.
- Text, sampler and decode nodes require a matching graph `output_size` and
  `speed_only=True` on larger servers. Original non-speed arms refuse. Maintenance
  probes, coverage, pinning and freeze remain available.
- The sampler checks the incoming stage-1 latent; actual native/replica decode
  helpers check the stage-2 latent. The probe checks `[25,H,W,3]` frames and
  `[1,2,48480]` waveform output. Dummy fill values never enter these decode helpers.
- Graph-capture `Slot` mirrors the actual argument tensors, including strides,
  shapes and dtype. Larger-size Slots additionally require the selected stage's
  video token count. The signature cap remains **8**: one fixed size and batch
  per server still needs two stage signatures, not more signatures per pixel.
- The upsampler and VAE allocation paths already derive shapes from their inputs.
  The context/output sentries hash actual tensors and have no fixed spatial
  dimensions. Their implementations are preserved. The chain check already
  counts actual Slot storage; its eager transient allowance now scales by the
  video-token ratio. The 2 GiB freeze floor is unchanged.
- At default size the decode probe is packet 97's reference-based probe. At larger
  sizes it decodes ten independently seeded CPU random latent pairs natively and
  on every selected replica. It requires finite, correctly shaped, byte-identical
  images and waveform across cards. It saves hashes and `_matches_native`, never
  `_matches_reference`. No saved latent tensor or reference output is loaded by
  that path. The helper requires ten passing rows and the selected size/cards.
- The timed client requires `--no-oracle` for every speed graph, rejecting an
  oracle request before writing output or contacting the endpoint. All timing,
  clip-emission, batch provenance and busy-engine definitions remain packet 97's.

## Memory: estimates, not measurements at the new sizes

The [bound snapshot](../data/size-98-memory-basis.json) pins the exact packet 97
freeze and pool-calibration receipts used. It includes batch 1, 2 and 4 on
`two-way-w2-b<B>-p1-dxpu2`; [all planned estimates](../data/size-98-offline/memory-plans.json)
are retained separately from measurements.

Measured pooled worker cost on cards 0 / 1: B1 **0.2664 / 0.2281 GiB**;
B2 **0.4207 / 0.3062 GiB**; B4 **0.7136 / 0.5269 GiB**. The larger-size plan
charges that entire cost × token ratio × **1.5**, plus **0.25 GiB** on each card
with sampler blocks. Scaling even its fixed portion is conservative. Zero-worker
free memory is the matching batch's freeze reading plus two measured workers.
For decoder growth it reserves `0.5 × (pixel ratio − 1) × 1.5 GiB` on each
selected replica card and card 3: **2.063 GiB** extra at 640×384. The measured
one-card decoder peak grew by about 0.9 GiB; this allowance is deliberately larger.
Card 2's existing replica allocation is never credited back for another placement.

| Two-way, pooled, replica card 2 | Size | Predicted free at freeze, GiB: cards 0 / 1 / 2 / 3 | Plan |
| --- | --- | --- | --- |
| W1 B1 | 640×384 | 6.318 / 11.243 / 7.679 / 12.502 | admit |
| W2 B1 | 640×384 | 4.570 / 9.710 / 7.679 / 12.502 | admit |
| W1 B2 | 640×384 | 5.285 / 10.776 / 7.679 / 12.677 | admit |
| W2 B2 | 640×384 | 2.669 / 8.804 / 7.679 / 12.677 | admit, closest to floor |
| W2 B4 | 640×384 | −0.559 / 6.289 / 7.679 / 12.678 | refuse, exit 18 |
| W1 B1 | 512×320 | 6.818 / 11.670 / 8.616 / 13.439 | admit |
| W2 B2 | 512×320 | 4.246 / 9.952 / 8.616 / 13.615 | admit |

Two-way with one or two workers is the first target. `shard4-a` and `shard3-c`
with the replica on card 2 refuse at 640×384 for B1/B2, even W1: no matching pooled
measurement exists for those layouts, and the scaled private-pool estimate does
not leave enough room. This is a conservative refusal, not proof they cannot fit.

[worker-headroom-98.py](../scripts/worker-headroom-98.py) keeps default-size
planning arithmetic and the 2 GiB floor. For larger sizes it checks **all**
planned workers and replica-probe room before capture. Live checks charge future
decode growth; missing/nonfinite memory refuses. New calibrations must match
manifest, size and layout. Before/after readings must name the same server, size
and batch in time order. Packet 97 is used only through the explicitly pinned
estimate above, never silently admitted as a current-packet calibration.
Same-size live measurements and calibrations retain the existing 25% + 0.25 GiB
margin. The freeze rechecks actual room after the whole-chain check.

## Runner and index allocation

[run-campaign-98.sh](../scripts/run-campaign-98.sh):

```text
<layout> <W> <B> <pool> <replica-spec> <size> [repeat 1-5] [timed prompts 120-9000]
```

Run name: `encoder-server-size-98-<layout>-w<W>-b<B>[-p1]-d<spec>-s<size>[-rN]`.
Output: `data/size-98/<mode>`. The runner explicitly requires and records the
server's `LTX_OUTPUT_SIZE`, alongside placement, workers, batch, pool and replica
settings. `NEOReadDebugKeys=1 EnableDeferBacking=0`, busy timers off, a health
admission receipt and a working SIGINT handler are required.

Sequence: window probe → memory plan → pinned serial capture per worker →
coverage → pool calibration → decode-replica probe → whole-chain check and freeze
→ full timed-path self-check → speed probe → timed arm → decode-placement check
→ summary → proven-quiescence SIGINT stop. The stop, failed-job files, monitor
failure handling and explicit-path receipt commits are inherited from packet 97.
The builder and CPU tests never execute campaign actions or Git mutations.

At 256×256, the original reference and proof branches run: batch 1 against w93c,
batches 2/4 against their existing preregistered references. At larger sizes all
capture/self/probe/timed clients use `--no-oracle`; reference and batch-oracle
proof arms are not attempted. Whole-chain replay, replica equality and context
sentry comparisons remain enforced. The speed probe emits ten clips before the
timed arm; only the timed arm supplies the speed result.

The brief's “40,000,000+” is interpreted as a lower bound: packet 97 permits
indices up to 45,919,000. Starting at 40 million would collide. Packet 98 starts
at **46 million**, caps repeat IDs at five and preserves the full 9,000-prompt
arm allowance:

```text
IDX = 12*layout + 3*(W-1) + batch_index
layout: two-way=0, shard4-a=1, shard3-c=2; batch_index: 1=0, 2=1, 4=2
spec: xpu:1=0, xpu:2=1, xpu:1,xpu:2=2, xpu:2,xpu:1=3
size_index: 256x256=0, 512x320=1, 640x384=2
C = IDX + 36*(pool + 2*(spec + 4*(size_index + 3*(repeat-1))))
short base = 46,000,000 + 1,000*C
timed base = 51,000,000 + 10,000*C
```

All 4,320 combinations are disjoint. Short blocks finish below 50,320,000;
timed blocks below 94,200,000, under the unchanged 100,000,000 node ceiling.
Short offsets remain capture `+10*k`, self `+100`, probe `+200`, neighbour proof
`+300`, slot proof `+400`. There is no automatic retry or relaunch.

| Planned order | Size | Short base | Timed base |
| --- | --- | ---: | ---: |
| 1. two-way W2 B1 p1 xpu:2, control against w93c | 256×256 | 46,111,000 | 52,110,000 |
| 2. two-way W1 B1 p1 xpu:2 | 640×384 | 46,684,000 | 57,840,000 |
| 3. two-way W2 B2 p1 xpu:2 | 640×384 | 46,688,000 | 57,880,000 |
| 4a. two-way W1 B1 p1 xpu:2 | 512×320 | 46,396,000 | 54,960,000 |
| 4b. two-way W2 B2 p1 xpu:2 | 512×320 | 46,400,000 | 55,000,000 |

## Checks and launch commands

All five planned names pass `--check-only` both without a receipt and with
`data/health/four-card-health-20261006T1405Z.json`: **10/10**. Results and exact
arguments are represented in [gates.json](../data/size-98-offline/gates.json).
The check-only path does not open devices, create a server run or contact the
live endpoint. A launch later still needs a then-current healthy machine.

[CPU tests](../scripts/test-packet98-size-cpu.py): **17/17**, including the real
size-probe function with CPU decoder stand-ins and corruption, actual Slot
constructor, admission refusal before work, all generated size graphs and
all 4,320 runner configurations. Packet **90c–97: 13/13 scripts, 112 check groups
pass**, including packet 96's 17 and packet 97's 9.

Full guarded lane sweep: **117 files: 47 pass, 66 fail, 1 timeout, 3 skipped**.
The skipped tests are the three packet-copying negative tests; the timeout is
`test-na-axis-host-read-equivalence.py` at 180 seconds. Of the 66 failures,
32 require test-specific CLI inputs; 27 other legacy fixture/import/contract failures; 6 explicit guard refusals; 1 unavailable CUDA import. These counts are **not comparable** to packet 97's
older sweep: this run blocks real XPU discovery, accelerator allocation, real
checkpoint reads, endpoint access and writes outside temporary directories.
The existing lane sources and tests were not edited to make them pass. The
first sweep exposed test-guard issues (Torch registry aliases and CPU seeding's
implicit accelerator broadcast); those guards were corrected and the full sweep
was rerun. Only the final counts above are the result.

Full results: [sweep.json](../data/size-98-offline/sweep.json), with one log per
executed test. Reproduce the guarded sweep with:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/scripts/sweep-size-98-cpu.py
```

These are **future launch commands, not executed in this build**. Wait for the
packet 97 campaign to finish and use a fresh health receipt. Each server and
runner lives in its own user unit. Wait for the runner's successful stop before
moving to the next planned row.

```bash
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-size-98
M=918b47a5530b4dc97fe8fc8f4ec77fd64521ec6846217c54f5fba589e0e8377f
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
L=two-way W=2 B=1 SP=1 D=xpu:2 SIZE=256x256
MODE=$L-w$W-b$B-p1-dxpu2-s$SIZE
HEALTH=$LANE/data/health/<fresh-receipt>.json
systemd-run --user --collect --unit=ltx98-server-$MODE \
  --property=StandardOutput=append:$R/encoder-server-size-98-$MODE.log \
  --property=StandardError=inherit \
  env --default-signal=INT NEOReadDebugKeys=1 EnableDeferBacking=0 LTX_BUSY_WINDOWS=0 \
  LTX_SAMPLER_PLACEMENT=$L LTX_SAMPLER_WORKERS=$W LTX_SAMPLER_BATCH=$B \
  LTX_SAMPLER_SHARED_POOL=$SP LTX_DECODE_REPLICA_DEVICE=$D LTX_DECODE_REPLICAS=1 \
  LTX_OUTPUT_SIZE=$SIZE /home/steve/.venvs/ltx25-baseline/bin/python -B \
  $P/launch/serve-encoder.py --packet $P --manifest-sha256 $M \
  --run-name encoder-server-size-98-$MODE --health-receipt "$HEALTH"
systemd-run --user --collect --unit=ltx98-campaign-$MODE \
  --property=StandardOutput=append:$R/campaign-98-$MODE.log --property=StandardError=inherit \
  bash $LANE/scripts/run-campaign-98.sh $L $W $B $SP $D $SIZE
```

## Unverified offline

- Real larger-shape graph captures and their eager/replay bit equality, including
  both stage signatures on every worker. Attention scratch may grow faster than
  the linear memory estimate; the planner's margin is an assumption, not a bound.
- Native and replica decode equality at these sizes on the real cards, correct
  waveform length, and interference with text encoding on card 2. CPU stand-ins
  test the checker, not the VAE kernels.
- W2 B2 640×384 memory, particularly the whole-chain check's transient peak and
  any ComfyUI eviction before freeze. Admission, freeze and failed-job receipts
  decide; nothing bypasses them.
- Full runner execution, timing, throughput, busy seconds, sustained operation
  and output quality. No new-size reference parity, batch-neighbour independence
  or higher-resolution quality claim is made. Packet 97's batch-baseline ruling
  remains open; speed-only arms cannot settle it.

## Files and live-work isolation

All implementation files are new 98 helpers; all existing lane source files,
97/96 helpers, prepared packets and preregistrations remain unchanged by this
build. The builder's overlay edits only its new packet. The live helper import
census found `ltx_sampler_batch.py` as the shared lane runtime import; it is
untouched. Evidence lives in `data/size-98-offline/` and
`data/size-98-memory-basis.json`. Test-only device/IO guards are in
`cpu-guard-98.py`; the sequential sweep driver is `sweep-size-98-cpu.py`.
