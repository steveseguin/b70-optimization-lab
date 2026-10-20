# Flash-Next UD-IQ3_XXS: our Xe runtime on two B70 cards

**Candidate · expert lab replay · full BF16 KV · one user.** This is Unsloth's
quantized compressed version, a separate model from official Flash-Next FP8.
The current full-512 profile is bundle 8 (packet136), through packet165's
measurement harness: two rank processes, 24 layers each, the official MTP
head on rank 1, and unchanged-target verification of every draft token.

| Two fresh loads, same profile | Load a | Load b |
| --- | ---: | ---: |
| Writing, class-balanced first 99 intervals | 58.632 tok/s | 58.557 tok/s |
| Reading a new 512-token prompt, 512 / native TTFT | 75.973 tok/s | 75.884 tok/s |
| That prompt's TTFT | 6.739 s | 6.747 s |

Twelve varied suite prompts ran once per load with a 512-token response cap,
plus one distinct 512-input-token document. Request state is fully reset;
there is no prompt, KV or response reuse. The first suite prompt warms the
runtime before the reading request and remains in the suite report. Reading
uses 512 / native request TTFT, includes first-token work and excludes model
loading and reset. It is not HTTP TTFT or isolated device prefill. The
[one-card profile](../qwen38-flash-next-iq3xxs-ownrt-tp1-b70/README.md) includes
reset in its TTFT; do not treat those clocks as identical phase measurements.

Both full outputs match across the fresh loads. The CPU oracle independently
checks only the first **128 output tokens** of the twelve suite prompts;
longer outputs and the reading response have repeat agreement only. These
receipts pass the performance workload but explicitly retain
`no_quality_loss_decision=false` and `submission_eligible=false`. A strict
public headline and full-output oracle qualification remain pending.

The approved **58.798109 tok/s** packet136 record uses the earlier 128-token
cap. It remains in the [submission ledger](../../results/localmaxxing-submissions.md)
as `cmve4dtir007wrf01k57sdf23`; it is not substituted for the full-512 result.
Earlier packet163 full-512 runs measured 58.610 / 58.625 tok/s. Its 512-input
request ran first and measured about 7.8 tok/s including the initial runtime
cost; packet165's different-prompt warm-up measures the steady runtime instead.
Neither the old short-input capacity experiments nor an analytical batching
projection is an actual prompt-length curve. Current-profile context scaling
and multi-user throughput are **not measured**. The native controller handles
one request at a time.

[Exact observations and hashes](../../results/qwen38-flash-next-ud-iq3xxs-b70/ownrt-measurements-20261019.json),
[full result history](../../results/qwen38-flash-next-ud-iq3xxs-b70/README.md),
[package manifest](../../packages/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/package.json),
[publication manifest](publication-manifest.json).

## Requirements and model files

Two Intel Arc Pro B70 cards with 32 GiB each, Linux, Intel oneAPI compiler
**2026.0**, Level Zero, OpenSSL development libraries, Python 3.12 and a
128 GiB host. The sealed admission requires **105,411,248,128 bytes available
host RAM**, an empty host at entry, and the other lane idle throughout.
It plans 1,222,788,768 output bytes and keeps **25 GB free on the packet
filesystem after those writes**. The 15 GiB Turin host cannot run this profile.
Do not change swap, page-cache, power or memory settings to gain admission.

[models.json](manifests/models.json) pins the three target GGUF shards and
28 official draft shards by repository revision, length and SHA-256. Target:
`unsloth/Qwen3.8-Flash-Next-GGUF` at
`766911a6b7369840a91dbcd95f9f997acaab6cd6`. Draft source:
`Qwen/Qwen3.8-Flash-Next-FP8` at
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`. Allow 81,961,823,936 target bytes
and 30,047,461,616 draft bytes, plus build/output space. The official draft
uses the recorded draft-only quantization and 80,128-row prefix; target
weights and full-precision caches remain unchanged.

Download only the pinned files, then compare their SHA-256 values with the
manifest before any model read:

```bash
python3 - <<'DOWNLOAD'
import json, os, subprocess
from pathlib import Path
m = json.loads(Path('repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/manifests/models.json').read_text())
for key, destination in [('target', os.environ['TARGET_DOWNLOAD']), ('draft', os.environ['DRAFT_DOWNLOAD'])]:
    part = m[key]
    subprocess.run(['hf', 'download', part['repository'], '--revision', part['revision'],
                    '--local-dir', destination, *[r['path'] for r in part['files']]], check=True)
DOWNLOAD
```

## Source, build and replay

Measured source snapshot: `ac37d1027b55567c92c4be8e63acfb5691dc87c6` in
`https://github.com/steveseguin/b70-optimization-lab`. The
[identity](../../experiments/own-xpu-runtime/stage2/packet165-warm-prefill/two-card/identity.json),
[source seal](../../experiments/own-xpu-runtime/stage2/packet165-warm-prefill/two-card/seal.json)
and [compile/link record](../../experiments/own-xpu-runtime/stage2/packet165-warm-prefill/two-card/lineage/packet165-build.json)
retain the precise measurement variant. Its parser accepts the full 512 cap;
arithmetic and the parent kernel objects were unchanged.

The original [build helper](../../experiments/own-xpu-runtime/stage2/packet165-warm-prefill/localize_native.py)
relinks inherited packet163 objects and absolute include/constant paths.
The new shared [clean-source build recipe](../qwen38-flash-next-iq3xxs-ownrt-tp1-b70/BUILD.md)
compiles every translation unit from its hash-pinned source archive, including
the exact two-card compiler recipes. It requires no model weights or GPU
execution. Portable model admission and clean-host device requalification
remain unfinished gates. Do not replace old binary hashes with a new build's hashes.

During this closeout, this host's standing stability rules permit only CPU
build and preflight work for this native lane. No native device benchmark was
run. The replay below is for an explicitly admitted compatible host and does
not authorize automatic benchmark execution on the current host.

The shared [replay helper](../qwen38-flash-next-iq3xxs-ownrt-tp1-b70/scripts/replay.py)
preserves the original admission. CPU evidence health and the real entry's
plan are safe offline checks; they do not establish device health or grant a
reservation:

```bash
python3 -B repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/scripts/replay.py health --cards 2
python3 -B repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/scripts/replay.py preflight \
  --cards 2 --lane B --name replay-first
```

The measured run used cards 2+3 (lane B). The runner binds the lab's model
inode metadata, CPU placement and a boot review containing exactly two
historical faults. **A different host or clean boot needs a reviewed portable
admission implementation; never fabricate a review or edit old seals.** This
is a bounded native benchmark, not an HTTP server or arbitrary chat interface.

After a coordinator has reserved the host and supplied a genuine current
fault review, one command runs the complete thirteen-request measurement:

```bash
python3 -B repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/scripts/replay.py benchmark \
  --cards 2 --lane B --name replay-first --unit screen-ownrt-replay-two-first \
  --fault-review "$FAULT_REVIEW" --authorized-device-window
```

`launch` has the same bounded behavior. The job runs in its own systemd user
unit with no restart, no SIGKILL, cooperative stop and no stop timeout. To
stop that exact job early:

```bash
python3 -B repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/scripts/replay.py stop \
  --cards 2 --unit screen-ownrt-replay-two-first
```

Wait for the recorded owner drain and inspect kernel evidence before releasing
the reservation. No failed request triggers a retry or server restart. A
separately authorized second load uses a fresh name/unit and `--reference`
pointing at the first completed output; all original evidence is retained.
The package CPU checks and plan passed; no new GPU replay was run for this
publication update. Independent clean-host execution, full-output quality,
context and concurrency measurements remain pending.

## Preserved earlier recipe

The [packet44 replay guide](packet44-replay.md) and
[its original publication manifest](packet44-publication-manifest.json)
preserve the October 13 capped 37.856264 tok/s recipe, arithmetic-v2 oracle,
capacity experiments and exact historical commands. Its source, kernel,
arithmetic and measurements are not the bundle-8 operating profile above.
