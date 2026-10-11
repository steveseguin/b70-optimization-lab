# Preregistered one- or two-B70 reference screens

## October 11 selectable plans

Owner direction (2026-10-11): "this model is probably going to be used by folks
with just 1 or 2 B70 GPUs; i figure 2 GPUs is a good target for us, but 1 is also
reasonable to target. either way, we have lots of ram and lots of gpus so we
can do multiple runs at a time".

`--plan twocard` retains the original two-card argv below. `--plan onecard`
uses the same frozen twelve prompts, sampling, seed, context, full FP16 KV,
64-token cap and two complete repeats (24 fresh processes), with these changes:

- One selector-visible device; `--fit on --load-mode mmap --verbose`.
- Omit `--gpu-layers`, `--tensor-split` and `--override-tensor` entirely.
  The pinned `common/fit.cpp:463-485` refuses fitting when these placements
  are set by the user. The fitter therefore chooses device/CPU placement,
  including expert offload. Explicit context remains 4096; no compressed KV.
- Default gap **60 seconds**, rather than twocard's 305 seconds. These are
  short bounded completion processes, naturally drained before each gap;
  the owner requested shorter waits on October 11. This is a preregistered
  pacing choice, not a claim that a particular gap prevents faults. Every
  second is still watched, including the final gap. `--gap-seconds` records
  an explicit coordinator override for either plan; no automatic retry.

The pinned source uses `--load-mode mmap`, **not `--mmap`**
(`common/arg.cpp:2693-2711`). `--verbose` sets logging to all levels
(`common/arg.cpp:3944-3949`); the equivalent verbosity environment variable is
`LLAMA_ARG_LOG_VERBOSITY`, not `LLAMA_LOG_VERBOSITY`. Fit decisions are TRACE
messages in `common/fit.cpp`; debug fit probing is enabled by
`common/common.cpp:1272`. Final offloaded layers and named CPU/device model
buffers are INFO messages in `src/llama-model.cpp:1982-1990`, KV buffers in
`src/llama-kv-cache.cpp:291`, and compute/output buffers in
`src/llama-context.cpp`. All go to each child's stderr; log colours stay off,
`--perf` stays on, and the timing parser accepts log prefixes. No native binary
was run to discover these flags. Source identity is the frozen commit below.

### Cards and concurrent instances

`--device-selector` sets the child's `ONEAPI_DEVICE_SELECTOR` and accepts whole
Level Zero card indices 0–3, exactly one or two according to plan. The default
is `level_zero:0` or `level_zero:0,1`. `--device-list` passes llama's `--device`;
these names are local to the filtered enumeration: physical card 2 alone is
`SYCL0`, and physical cards 2,3 are `SYCL0,SYCL1`, not `SYCL2,SYCL3`.
The pinned `ggml/src/ggml-sycl/ggml-sycl.cpp:7539-7542` numbers visible devices.
The coordinator still verifies the actual selector-to-PCI mapping from the
current health receipt and runtime logs before accepting a result.

Admission replaces a blanket "no other llama/vLLM process" rule with passive
`/proc` checks: a known disjoint selector is allowed, overlap is refused, and
an absent, ambiguous or unreadable selector is refused. Each selected card
also gets a nonblocking advisory lock held for the entire screen, including
hashing and gaps, so two cooperating screens cannot race into the same card.
Lock files under `/tmp/iq3-screen-cards-<uid>/` are stable coordination files,
not scratch; never unlink a live lock. Nonparticipating launchers still require
coordinator exclusion; this is not a host-wide scheduler. Separate output/cache
directories are required. Combined RAM and I/O admission belongs to the
coordinator, and concurrent runs share CPU/RAM/I/O, so record them separately
from isolated measurements. `device-admission.json`, every command/row and
`environment.json` retain the selector, cards and device list; each row also
records other observed disjoint runtimes. Each screen keeps its own journal
watch and evidence; a fault anywhere on this host still stops new launches in
both screens. Device-aware admission does not filter out another card's faults.

CPU-only preview (the existing prepared inputs serve either plan):

```bash
OMP_NUM_THREADS=2 nice -n 19 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/run-screen.py --plan onecard --device-selector level_zero:2 --device-list SYCL0
```

Coordinator-only window commands, after all admission gates below, with a fresh
`HEALTH_RECEIPT` and a new `WINDOW_OUT` for each instance:

```bash
# One card: physical card 2, default 60-second gaps.
OMP_NUM_THREADS=2 nice -n 19 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/run-screen.py \
  --plan onecard --device-selector level_zero:2 --device-list SYCL0 \
  --execute-after-admission --health-receipt "$HEALTH_RECEIPT" --out "$WINDOW_OUT"

# Two cards: physical cards 2,3; record the previously authorized short-run gap.
OMP_NUM_THREADS=2 nice -n 19 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/run-screen.py \
  --plan twocard --device-selector level_zero:2,3 --device-list SYCL0,SYCL1 --gap-seconds 60 \
  --execute-after-admission --health-receipt "$HEALTH_RECEIPT" --out "$WINDOW_OUT"
```

These two examples overlap on card 2 and must **not** run together. Either can
run beside a separately admitted twocard instance on cards 0,1. The one-card
exploratory 21.64 tok/s probe is only feasibility evidence; its split was not
logged and its text differs from the two-card probe. Neither is a CPU-oracle
parity result. The existing two-card screen has a fault marker and only nine
first-repeat rows; see the [results ledger](../../../results/qwen38-flash-next-ud-iq3xxs-b70/README.md).

### Retained October 11 fixes and summaries

The child `LD_LIBRARY_PATH` retains the versioned paths obtained from
`setvars.sh`, including UMF (`libumf.so.1`), rather than inheriting the caller's
environment. Zero-generation natural EOS retains prompt timing, records
`decode=null` and `generated_tokens=0`, and does not abort the suite merely
because the reported decode rate is `inf`. The gap remains selectable and
recorded. No frozen receipt is rewritten to pretend these changes existed at
build time.

`summarise.py RUN_DIR [RUN_DIR ...] --out SUMMARY.md` writes separate per-window
tables with both repeats' decode/prompt rates, generated tokens, byte equality
and observed medians. Missing repeats, failed rows and zero-generation rows
remain visible; unavailable decode rates are excluded with denominators shown.
Run CPU tests with `OMP_NUM_THREADS=2 nice -n 19 python3 -B -m unittest discover
-s experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp -p 'test*.py'`.

**CPU preparation only. Do not execute the native command until the owner opens
the window and resolves the current fault halt.** This is a target-only loading,
fit, one-user timing and repeated-output screen of the Unsloth quantized
compressed version. It is not a Flash-Next FP8 result or a final quality gate.

## Frozen identity

- Upstream llama.cpp: `23b0202a189c44a54625aadcb37a946dd1d6278d`, no patches;
  [build receipt](build-receipt.json). Use the receipted binaries and libraries.
- Model: `unsloth/Qwen3.8-Flash-Next-GGUF` revision
  `766911a6b7369840a91dbcd95f9f997acaab6cd6`, `UD-IQ3_XXS`.
  All three files and SHA256s are in the
  [publisher file manifest](../../own-xpu-runtime/data/unsloth-flash-next-stage2-files.json).
  The model directory is
  `/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS/`.
  Pass `Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf`; llama.cpp discovers
  shards 2 and 3. The first shard contains metadata and zero tensors.
- Original twocard host: `steve-b70s` (128 GB nominal), using exactly two B70s, not the 15 GiB
  host. `ONEAPI_DEVICE_SELECTOR=level_zero:0,1` and `--device SYCL0,SYCL1`.
  The authorized coordinator must verify and record the current selector-to-PCI
  mapping before the screen; expected cards are `0000:23:00.0` and
  `0000:27:00.0`. Refuse rather than substitute devices if the mapping differs.
- `--split-mode layer --tensor-split 1,1 --gpu-layers all --fit off`.
  All target layers/expert banks requested on the two cards; input embedding
  and the 28.8 GB PLE table explicitly on CPU. Record actual per-card allocation
  and layer assignment from stderr, including any unsupported-operation CPU
  fallback. Do not call layer splitting TP2. Automatic reduced-context or
  layer-offload fitting is disabled. Fit remains an empirical question;
  packet 1c's 53.3 GB device arithmetic is not a runtime peak measurement.
- F32 SYCL arithmetic reference (`GGML_SYCL_F16=OFF`, dynamic precision F32),
  **FP16 K and V cache**, context 4096, batch 512, microbatch 128, flash
  attention off, one user, two CPU threads. No model/draft substitution,
  MTP, speculative decoder, prompt cache, session file, response reuse or
  runtime warmup. This conservative arithmetic identity must be held fixed
  when our runtime is compared; no CPU dequantization parity is yet certified.
- Fixed suite: [all 12 realistic prompts](../../../repro/rapid-model-snapshots-b70/realistic-suite-v1.json),
  in file order, covering prose, code, analysis, operations, documentation
  and structured writing. One user message, no system message, publisher
  GGUF chat template, thinking disabled. [Prompt receipt](prompt-receipt.json)
  pins both original and rendered UTF-8 bytes. Do not substitute a short or
  easy subset. Raw completion mode receives the pre-rendered chat because
  this upstream completion chat path omits the thinking template input.
- Greedy (`temperature=0`, top-k 1, top-p 1, min-p 0, repeat penalty 1), seed
  `20260609`, **at most 64 new tokens**; natural EOS may stop earlier and is
  recorded, never padded/forced away. Repeat the whole suite twice in the
  same order: **24 fresh processes**, one request per process. The first
  incident-retrospective process is also the load/fit probe; no extra warmup
  or startup retry. A failed process closes this screen.

## Admission, health and fault prerequisites

The owner/coordinator, outside this CPU preparation, must:

1. Resolve the current halt explicitly and record the owner decision, boot ID,
   host, exact build/model identity and the selected-card window. No agent clears
   or archives a FAULT file to make admission pass. Keep the LTX work protected;
   this screen neither contacts port 8188 nor stops/starts any ltx unit.
2. Verify `CURRENT.md`, passive process/ownership facts, exclusive host/device
   locks and the registered quiet gap since the previous native owner's completed
   teardown (60 seconds onecard; 305 twocard unless explicitly overridden).
   Selected cards must be free of other work; disjoint cards may host separately
   admitted runs of this lane. Do not run this in an agent
   shell subject to forced termination; the coordinator supplies the approved
   long-job owner. No systemd operation is performed by these scripts.
3. Confirm the download has finished and admit host RAM/storage for mapped PLE,
   staging, driver allocations, state and scratch. Keep existing swap/page-cache,
   power, clock and driver settings unchanged. The runner verifies all three
   payload SHA256s read-only; allow time for the 82 GB read. No writes to the
   model directory. There is no claimed safe memory floor from this CPU work.
4. Supply a fresh passing **four-card** `ltx.four-card-health.v1` receipt from
   the existing bounded host probe. The probe itself is GPU work and **was not
   run here**. It must match the boot/kernel, contain four passing card rows,
   `passed=true`, no fault lines during the probe, and be no more than 15 minutes
   old both before and after payload verification. Earlier faults still require
   the owner's documented halt resolution; a passing probe alone does not grant
   permission. If hashing exceeds freshness, no GPU process starts; the coordinator must
   arrange a fresh receipt and review the admission sequence before another attempt.
5. Verify absence of `FAULT.json` at the LTX results root
   `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/`, the FP8 lane's
   `reopen-20261008/`, own-runtime `stage1/packet4-prep/`, and this IQ3 lane.
   These are checked again throughout execution; any additional current
   coordinator fault latch also blocks admission. Journal readability is required.

The explicit execution switch below attests that these **manual admission
steps are complete**. The runner validates receipt freshness and core identities,
but does not resolve the halt, exclude noncooperating launchers, prove the PCI mapping or
admit host memory on the owner's behalf. Missing any manual step means no launch.

## Window command

The CPU preparation command is safe now (use a new output directory on repeat):

```bash
OMP_NUM_THREADS=2 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/prepare-prompts.py \
  --out /home/steve/build/flash-next-iq3-baseline-20261010/window-inputs
```

It has already been run at that path. Inspect the complete 24-command plan
without launching any binary:

```bash
OMP_NUM_THREADS=2 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/run-screen.py
```

**Only in the admitted window**, with `HEALTH_RECEIPT` set to the coordinator's
fresh receipt and a new `WINDOW_OUT` under an evidence/build directory:

```bash
OMP_NUM_THREADS=2 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/run-screen.py \
  --execute-after-admission --health-receipt "$HEALTH_RECEIPT" --out "$WINDOW_OUT"
```

Every child gets a clean environment: `OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`,
`ONEAPI_DEVICE_SELECTOR=level_zero:0,1`, both GGML SYCL dynamic precision
variables set to `F32`, and versioned oneAPI compiler/MKL/TBB library paths.
Its HOME/cache paths are private to the new output directory. No inherited
`LLAMA_ARG_*`, draft, device or precision overrides survive. For example, the
first child's exact command is:

```bash
/home/steve/build/flash-next-iq3-baseline-20261010/build/bin/llama-completion \
  --model /mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf \
  --device SYCL0,SYCL1 --split-mode layer --tensor-split 1,1 --gpu-layers all --fit off \
  --override-tensor '^token_embd\.weight$=CPU,^per_layer_token_embd\.weight$=CPU' \
  --ctx-size 4096 --batch-size 512 --ubatch-size 128 --cache-type-k f16 --cache-type-v f16 \
  --flash-attn off --threads 2 --threads-batch 2 --parallel 1 \
  --temp 0 --seed 20260609 --top-k 1 --top-p 1 --min-p 0 --repeat-penalty 1 --predict 64 \
  --no-conversation --no-display-prompt --simple-io --color off --log-colors off \
  --no-warmup --no-context-shift --perf \
  --file /home/steve/build/flash-next-iq3-baseline-20261010/window-inputs/incident-retrospective.txt
```

Run via the supervisor, not this isolated child command: it captures stdout
and stderr separately, records the child PID/argv and never retries. Before
any GPU process it authenticates binaries/libraries, full model payloads,
fixed prompts and regenerated argv. Empty output, absent timings or a failed
exit cannot count as success.

## Measurements, stop and time budget

Keep all 24 outputs and stderr logs, exit status, wall time, build/model/prompt
hashes, environment, per-card allocations, prefill/decode counts and timing
lines. Decode is llama.cpp's `eval time` count/rate, excluding prefill/load;
prefill is its `prompt eval time`, with actual input length. These are runtime
aggregate timings, **not timestamped 99-interval headline rates**. Report each
repeat separately and class medians across the full suite; never select the
faster repeat. stdout is compared byte-for-byte per prompt, with SHA256s retained.
Timing/diagnostic stderr is not part of the output comparison. Nonempty equal
text alone is not proof of token-ID, logit or CPU-reference parity.

The supervisor polls the kernel journal about once per second, starting at the
health receipt's end (including the payload-hash interval). First fault, journal
failure, FAULT file, STOP file, nonzero child exit or missing timing closes the
campaign without retry. Fault lines are retained in the run and lane-level
`FAULT.json`; nothing removes device coredumps or recovery evidence.

**Graceful stop means natural exit after EOS/64 tokens**, followed by resource
destruction and a clean journal throughout the registered idle postflight. Upstream
`tools/completion/completion.cpp`'s SIGINT handler calls `_exit(130)`, so do not
send Ctrl+C/SIGTERM to the child or use `timeout`, a group kill or SIGKILL.
To cancel, create `STOP` under `WINDOW_OUT` or signal only the captured
supervisor PID; it drains the current bounded request and starts no next one.
If a child stalls, it is marked DRAINING after 10 minutes, with no forced kill;
the coordinator preserves evidence and handles recovery. This is a limit on
new work, not a guaranteed termination time for a wedged driver.

Reserve **four hours**: up to 30 minutes for admission/payload checks and
postflight, and 3.5 hours for the 24-process screen, including 305-second gaps.
The runner starts no next process after 3.5 hours and records incomplete work
honestly. No further optimization arm follows a failed process. After the final
exit, the coordinator performs the authorized bounded host health postflight,
records its receipt and leaves the cards empty. A timing/output result is not
valid until that postflight passes. This does not authorize a recovery probe
or any native action during the present CPU-only task.

`realistic_final_gate.passed=false` regardless of speed or repeat equality:
this is a 64-token screen, not the 512-token promotion suite, and CPU arithmetic
parity is still pending. It must never replace the FP8 record or be submitted
as a headline.
