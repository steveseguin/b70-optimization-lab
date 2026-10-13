# Flash-Next UD-IQ3_XXS: our Xe runtime on two B70 cards

**Lab replay · expert audience · candidate package.** This is the Unsloth
**quantized compressed version**, a separate model from official Flash-Next FP8.
Packet 44 uses two rank processes, full BF16 caches, the native controller and
one official MTP draft token verified by the unchanged quantized target.
The draft head alone uses the recorded 8-bit requantization.

LocalMaxxing approved **37.85626413203107 tokens/s** at 4,096-position capacity,
submission `cmv6pugme0020oa01fjrho6nx`: the median of six prompt-class medians,
each timed across 99 intervals between generated-token completions 1 and 100.
All twelve 128-token outputs equal the arithmetic-v2 CPU oracles exactly.
This is an approved capped lab result. The repository's 512-token natural-
completion final gate and two fresh full-suite runs remain pending; the
library's strict headline remains unset.

[Result and receipt chains](../../results/qwen38-flash-next-ud-iq3xxs-b70/README.md),
[expected token IDs and hashes](expected-outputs.md),
[package contract](../../packages/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/package.json),
[publication manifest](publication-manifest.json).

## Requirements and certification

Two Intel Arc Pro B70 cards with 32 GiB each, Ubuntu 24.04, and Intel oneAPI.
The requested oneAPI 2026.1 platform is **not a qualified rebuild**: the sealed
`build.py` pins `/opt/intel/oneapi/compiler/2026.0/bin/icpx`. Retain that compiler
for the exact lab replay; a 2026.1 port needs new build, arithmetic and device
gates. Obtain the compiler from Intel's official oneAPI distribution. There
is no Docker image. CMake, GNU C++, LLVM 22 for sanitizer gates, and the packet's
Python/tokenizer environment are also required. Exact local paths are in
[CPU-REPRO.md](../../experiments/own-xpu-runtime/stage2/packet44-context/CPU-REPRO.md).

The measured host had 128 GiB RAM. The window requires **97 GiB available**
before loading ranks; the 15 GiB two-card host cannot replay it as-is. Download
space is 81,961,823,936 bytes for the GGUF and 30,047,461,616 bytes for 28 draft
shards, plus build/evidence space. Keep at least 8 GB free on root and follow
the packet's 4 GB preparation / 6 GB window build-tree limits. Do not change
power, memory, swap or page-cache settings to gain admission.

At 4,096 positions, modeled allocation is 27,311,728,188 / 31,267,162,826 bytes
for ranks 0/1; admission ceilings including reserves are
27,358,228,736 / 31,268,391,626 bytes, with another 1.5 GB free per card required.
These are plan values; live owner census must pass. See the
[memory plan](../../experiments/own-xpu-runtime/stage2/packet44-context/memory-plan.json).

Certification is `lab-replay`, `clean_host_tested=false`; publication status is
`draft`. A pristine independent build, portable model admission, released
binary/log assets with remotely verified hashes, and independent supported-
host device replay remain missing. The CPU audit does not certify those gates.

## Download exact model and draft files

[models.json](manifests/models.json) lists every filename, byte size and SHA256.
The target is `unsloth/Qwen3.8-Flash-Next-GGUF`, revision
`766911a6b7369840a91dbcd95f9f997acaab6cd6`, with these three files:

- `UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf`
- `UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00002-of-00003.gguf`
- `UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00003-of-00003.gguf`

The companion source is `Qwen/Qwen3.8-Flash-Next-FP8`, revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`. The 28 complete shards in the
manifest supply official MTP tensors at their recorded offsets; they do not
replace the target. Use Hugging Face's `hf` client on an admitted disk:

```bash
export TARGET_DOWNLOAD=/path/to/target-download
export DRAFT_DOWNLOAD=/path/to/official-draft-shards
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B - <<'DOWNLOAD'
import json, os, subprocess
from pathlib import Path
m = json.loads(Path('repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/manifests/models.json').read_text())
for key, destination in [('target', os.environ['TARGET_DOWNLOAD']), ('draft', os.environ['DRAFT_DOWNLOAD'])]:
    part = m[key]
    subprocess.run(['hf', 'download', part['repository'], '--revision', part['revision'],
                    '--local-dir', destination, *[r['path'] for r in part['files']]], check=True)
DOWNLOAD
```

Preflight hashes all 31 files in bounded chunks.
[prepare_mtp.py](../../experiments/own-xpu-runtime/stage2/packet44-context/prepare_mtp.py)
authenticates the draft against the tracked
[tensor contract](../../experiments/own-xpu-runtime/stage2/packet1/tensor-contract.json).

## Restore and build the source

Repository: `https://github.com/steveseguin/b70-optimization-lab`.
Source pin: **421a4ab5029680c2f88c78c7c7fdb4a05d6fc6c4**.
Remain on `main`; the publication manifest verifies these source bytes. For a
historical export into an empty directory on a sufficiently large disk (not
a branch or Git worktree), use the already-fetched commit:

```bash
export PUBLICATION_REPO="$PWD"
export SOURCE_EXPORT=/path/to/empty-source-export
nice -n 19 ionice -c 3 bash -c 'git archive 421a4ab5029680c2f88c78c7c7fdb4a05d6fc6c4 | tar -x -C "$SOURCE_EXPORT"'
```

[build.py](../../experiments/own-xpu-runtime/stage2/packet44-context/build.py)
is the source builder, using `-j1`. It has no portable model/compiler-path
flags. On the admitted lab layout, its real stage arguments are:

```bash
cd "$SOURCE_EXPORT"
packet=experiments/own-xpu-runtime/stage2/packet44-context
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet/build.py" prepare
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet/build.py" gnu-host
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet/build.py" icpx-host
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet/build.py" asan
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet/build.py" device
```

The export is an independent historical build. Run its native coordinator chain
from that export. The package helpers below operate on the current publication
checkout and its own build directory; to use them, run this same build/qualification
sequence there after CPU health confirms its source bytes match the pin. Do not
copy a seal between build directories.

Compilation alone does not admit a window. Follow the complete ordered
[CPU reproduction and seal sequence](../../experiments/own-xpu-runtime/stage2/packet44-context/CPU-REPRO.md),
including native-controller builds, fixture gates and final seal. The
[gate ledger](../../experiments/own-xpu-runtime/stage2/packet44-context/CPU-GATES.md)
and [build receipt](../../experiments/own-xpu-runtime/stage2/packet44-context/build-receipt.json)
record completed and waived arms. No build or device run was done during this
publication task.

A different host must regenerate target admission and dependent input bundles
after verifying identical weights: inode/device/mtime/ctime are bound in
`identity.tsv`, `input.json`, suite manifests and the seal. Adapt compiler and
Python paths, official draft location, captured draft-reference inputs and
library paths, then regenerate dependent receipts and rerun every required
gate. The locally captured development inputs named in CPU-REPRO are not
portable release assets. Never copy old inode identities or rewrite old hashes
to force a new host through admission. This adaptation is pending work.

## CPU health and coordinator preflight

Return to the current publication checkout for the package commands; the
historical source export predates these helpers. Health needs no weights or
device APIs:

```bash
cd "$PUBLICATION_REPO"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/scripts/verify.py
```

It verifies evidence hashes, sealed source hashes, both capacity suites and
all twelve oracle token arrays; it recomputes the 99-interval metrics.
`--build-artifacts` additionally hashes restored binaries without executing them.
This checks build/receipt integrity, not live GPU health.

Before a device window, the coordinator reserves the adjacent pair and supplies
a measured `ownrt.coordinator-vram.v1` JSON report with `boot_id`, Unix
`captured_unix`, measurement `source`, `raw_evidence`, and `cards` containing
exactly two objects with `card`, `pci` and measured `free_bytes`. This must be
from the current boot and at most ten minutes old after model hashing; refresh
it during hashing if needed. Preflight requires each ceiling plus 1.5 GB free.
The report is not a reservation; packet44 still performs live guarded checks.
No discovery or device binary is hidden in this preflight.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/scripts/preflight.py --model-dir "$TARGET_DOWNLOAD/UD-IQ3_XXS" --draft-dir "$DRAFT_DOWNLOAD" --vram-report /path/to/current-coordinator-vram.json --card 0 --context 4096
```

A new download deliberately fails stale lab file admission even when all
hashes match. Complete the adaptation and qualification described above first.

## Coordinator window chain, launch and stop

Run device work only in an admitted systemd user unit with a **nice-0 parent**.
W windows require this; K windows lower themselves to nice 19. Preserve CPU
affinity and existing qualified `LD_LIBRARY_PATH`; add no device selectors,
precision changes or cache reuse. No other GPU lane may run. Stop on the first
fault, save evidence, and follow coordinator recovery; never retry in a loop.
The existing complete chain commands are:

```bash
bash experiments/own-xpu-runtime/stage2/packet44-context/coordinator_windows.sh 0 4096
# A second independent chain, only when separately admitted:
bash experiments/own-xpu-runtime/stage2/packet44-context/coordinator_windows.sh 0 32768
```

[coordinator_windows.sh](../../experiments/own-xpu-runtime/stage2/packet44-context/coordinator_windows.sh)
runs K0 → K1a → K1b → K2 → W0p → KD → W2m → WS → WSs with fresh output paths.
Its WS default is two repeats. To replay the sealed one-repeat 128-token
benchmark, run the six prerequisites from
[WINDOW.md](../../experiments/own-xpu-runtime/stage2/packet44-context/WINDOW.md),
then the package command below. Archived receipts cannot admit a new boot:
source, build, boot, card pair, capacity and dispatch must all match.

```bash
export CHAIN_DIR=experiments/own-xpu-runtime/stage2/packet44-context/build/c4096
export CARD=0 CONTEXT=4096
export UNIT=ownrt-p44-benchmark-unique
export OUT_DIR="$CHAIN_DIR/WS128-new"
bash repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/scripts/window.sh benchmark --authorized-device-window
```

This runs one two-rank WS window in its own unit with native controller,
`--repeat 1`, and the committed 128-token manifest; it waits and then compares
all twelve outputs to their CPU oracles. A distinct warmup is excluded;
measured prompts start from cleared request state. No second attempt is run.

For one bounded prompt, `launch` starts W2m: the committed incident-retrospective
prompt, 64 generated tokens and matching oracle. This is not an HTTP service;
there is no arbitrary free-text `--prompt` flag. It finishes naturally:

```bash
export UNIT=ownrt-p44-prompt-unique
export OUT_DIR="$CHAIN_DIR/W2m-new"
bash repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/scripts/window.sh launch --authorized-device-window
# From another shell with the same UNIT, for early graceful stop:
bash repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/scripts/window.sh stop
```

Stop signals only the wrapper; it owns the cooperative rank stop pipe. There
is no automatic SIGKILL, restart or reboot. Inspect window/rank teardown and
kernel postflight before releasing the cards. A retained owner needs recovery,
not a forced kill. The launcher preserves the coordinator's affinity in its unit.

## Expected results and limits

| Allocation capacity | Output cap / requests | Decode median, 63 intervals | All-prompt median, 99 intervals |
| ---: | --- | ---: | ---: |
| 256, packet 38 predecessor | 64 / 24 | 38.25 tok/s | not available |
| 4,096, packet 44 | 128 / 12 | 37.59 tok/s | 37.77 tok/s |
| 32,768, packet 44, other card pair | 128 / 12 | 37.71 tok/s | 37.70 tok/s |

Observed per-prompt decode ranges: 34.45–40.71 at 4,096; 34.27–40.46 at 32,768.
These are observations, not speed guarantees or output tolerances. The separate
class-balanced 4,096 figure is **37.85626413203107**. Sequential target-only
128-token decode at 4,096 was 25.00 tok/s. Token IDs must match exactly.

Capacity reserves storage. Actual suite inputs are 60–90 tokens; this is not
a 256-to-32K prompt-length curve. WL additionally checked 598- and 2,271-token
prompts, each with 32 exact output tokens; midprompt states were not retained.
No 32K real-prompt speed is claimed. The 64-token repeated suite was 24/24 exact
at each packet44 capacity, which is not two fresh 128-token suite launches.

**Reading speed (prefill): not measured at the standard 512-token input.**
The 4,096 suite's median TTFT is 1,422.011 ms and wall throughput 26.634 tok/s,
at median input length 68. Neither is a standard prefill rate. No prompt/KV/
response reuse, compressed KV or changed target precision is used. Exactness
is relative to this model's arithmetic-v2 CPU oracle, not official FP8 or
llama.cpp arithmetic. The reference screening record remains separate.
