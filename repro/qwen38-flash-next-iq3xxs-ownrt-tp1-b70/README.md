# Flash-Next UD-IQ3_XXS: our Xe runtime on one B70

**Updated October 23:** the separate capped record is now **37.595605 tok/s**,
and a bounded streaming/checkpoint pilot has passed. See [current recipes,
verification commands and limits](LATEST.md). The source build and full-512
replay below retain their measured identity.

**Candidate · expert lab replay · full BF16 KV · one user.** These are Unsloth's
quantized compressed weights, a separate model from official Flash-Next FP8.
The measured full-512 profile uses packet58aj through packet165c, target-only
greedy decoding, with all 48 layers on the card and experts held in host memory
and a device cache. There is no draft model or CPU layer offload.

| Two fresh loads, same profile | Load a | Load b |
| --- | ---: | ---: |
| Writing, class-balanced first 99 intervals | 31.782 tok/s | 31.510 tok/s |
| Reading a new 512-token prompt, 512 / native TTFT | 32.752 tok/s | 32.595 tok/s |
| That prompt's TTFT | 15.633 s | 15.708 s |

Each load ran twelve varied prompts once with a 512-token response cap, plus
one different 512-input-token document. Each request started with cleared
state and zero reused prompt tokens. The first suite prompt warmed the runtime
before the reading test; it remains in the suite results. Reading includes
the request reset and first-token work. It is not isolated device prefill or
HTTP TTFT. Both loads emitted identical complete outputs; the independent
CPU oracle verifies only the first **128 output tokens** of the twelve suite
prompts. The reading prompt has repeat agreement but no independent oracle.

**The performance workload passed; full-output quality promotion remains
pending.** The records explicitly keep `submission_eligible=false` and
`no_quality_loss_decision=false`. The separate packet196 diet/max23 profile
has an approved **37.595605 tok/s** result under the older 128-token cap;
its speed is not substituted into this full-512 profile. The completed record,
exact configuration and read-only verifier are in [LATEST.md](LATEST.md). No actual
prompt-length curve or multi-user measurement exists for either one-card
identity. The native controller handles one request at a time; simultaneous
users are not a supported measured mode.

[Exact measurements and hashes](../../results/qwen38-flash-next-ud-iq3xxs-b70/ownrt-measurements-20261019.json),
[result history](../../results/qwen38-flash-next-ud-iq3xxs-b70/README.md),
[two-card profile](../qwen38-flash-next-iq3xxs-ownrt-tp2-b70/README.md),
[package manifest](../../packages/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/package.json).

## Requirements and exact inputs

One Intel Arc Pro B70 with 32 GiB, Linux, Intel oneAPI compiler **2026.0**,
Level Zero, OpenSSL development libraries, Python 3.12, and a 128 GiB host.
The sealed admission requires **98,990,252,032 bytes available host RAM** and
the whole host's cards idle. It plans 57,141,252 output bytes and requires
**25 GB free on the packet filesystem after those writes**. It does not change
swap, page-cache, power settings or memory limits to meet admission.

Download the three target shards in [models.json](manifests/models.json),
revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`:

```bash
hf download unsloth/Qwen3.8-Flash-Next-GGUF \
  --revision 766911a6b7369840a91dbcd95f9f997acaab6cd6 \
  --local-dir "$TARGET_DOWNLOAD" 'UD-IQ3_XXS/*'
```

Verify all three SHA-256 values and lengths from the manifest before loading.
The target occupies 81,961,823,936 bytes on disk. Model download space is in
addition to runtime and evidence space. The published target hashes are shared
with the two-card profile; this one-card profile does not need draft shards.

## Build and CPU checks

The retained measured identity is pinned by
[identity.json](../../experiments/own-xpu-runtime/stage2/packet165-warm-prefill/one-card/identity.json),
[source seal](../../experiments/own-xpu-runtime/stage2/packet165-warm-prefill/one-card/seal.json)
and [publication manifest](publication-manifest.json). Its source snapshot is
commit `ac37d1027b55567c92c4be8e63acfb5691dc87c6` of
`https://github.com/steveseguin/b70-optimization-lab`.

The measured build's entry compilation and link arguments are retained in
[packet165-build.json](../../experiments/own-xpu-runtime/stage2/packet165-warm-prefill/one-card/lineage/packet165-build.json).
The original [build helper](../../experiments/own-xpu-runtime/stage2/packet165-warm-prefill/localize_native.py)
reuses packet163's kernel object files and remains historical evidence. The
new [clean-source build recipe](BUILD.md) compiles all translation units from
a hash-pinned source archive, without inherited object files. Its commands
require no model weights or GPU execution. A relocated or newly compiled
binary needs new arithmetic, repeat and device gates; never replace its hash
in old receipts. The one-card portable rebuild passed two device runs on October 22, with
complete outputs equal to this sealed line; see the [rebuild evidence](../../results/qwen38-flash-next-ud-iq3xxs-b70/ownrt-measurements-20261022.json).
Portable model admission and clean-host replay remain pending.

The October 23 publication closeout performed CPU verification only. No new
native device benchmark was run for that closeout. The replay below is for an explicitly admitted compatible host and does
not authorize automatic benchmark execution on the current host.

From the repository root, these commands only check retained files and plan
one load; they do not run a GPU job:

```bash
python3 -B repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/scripts/replay.py health --cards 1
python3 -B repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/scripts/replay.py preflight --cards 1 --name replay-first
```

Health hashes the sealed packet and checks the extracted measurements.
Preflight uses the real entry point's `--plan`; it does not establish device
health, ownership, current free memory, or permission to run a benchmark.

## One bounded replay on the admitted lab host

The sealed runner binds local model inode metadata, card BDF `0000:23:00.0`,
CPU placement and a reviewed boot with exactly two historical fault lines.
**It is not a portable serving endpoint.** A different host or clean boot needs
a reviewed admission implementation and freshly qualified identity; do not
manufacture historical faults, rewrite seals or weaken the fault checks.
Keep the supplied runtime source and evidence intact.

After the coordinator has reserved the host and produced a genuine current
fault-review receipt, use a new output name and unit. `launch` and `benchmark`
both run the complete bounded 13-request experiment once and finish; neither
starts an HTTP service. The existing engine still checks ownership, topology,
model identity, memory, disk space, full reset, faults and graceful teardown.

```bash
python3 -B repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/scripts/replay.py benchmark \
  --cards 1 --name replay-first --unit screen-ownrt-replay-one-first \
  --fault-review "$FAULT_REVIEW" --authorized-device-window
```

The helper creates one systemd user unit with `Restart=no`, `KillMode=process`,
`ExitType=cgroup`, `SendSIGKILL=no` and no stop timeout. SSH loss does not own
the job. For early cooperative shutdown, signal that exact unit:

```bash
python3 -B repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/scripts/replay.py stop \
  --cards 1 --unit screen-ownrt-replay-one-first
```

Inspect teardown and kernel evidence before releasing the reservation. A
failed run is retained and receives no automatic retry or restart. A second
fresh validation, when authorized, uses a distinct name/unit and `--reference`
pointing to the completed first output directory. Historical outputs are never
overwritten. The CPU source/evidence checks passed during package preparation;
no new GPU replay or clean-host validation was performed.
