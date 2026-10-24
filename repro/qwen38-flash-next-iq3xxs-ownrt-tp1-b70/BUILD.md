# Build the packet165 native programs from source

This is a CPU-only build recipe for the one-card 58aj and two-card bundle8/136
packet165 programs. It compiles every translation unit and links a new binary.
It never copies inherited object files, launches a GPU program, changes device
admission rules, or overwrites the sealed benchmark binaries.

The source snapshot and complete command lists are in
[manifests/native-build.json](manifests/native-build.json) and the
[hash-pinned source archive](manifests/native-sources.tar.gz). The archive
contains 962 compiler inputs and readonly constants, including generated
headers that previously lived only under originating-host build directories.
Every source has a SHA-256 and size. Compiler commands were recovered by
matching the inherited object hashes; packet56 objects additionally use the
packet60 hash-bound source/command snapshots and its exact rebuild mapping.
The historical object hashes are provenance, not build inputs.

## Prerequisites

Use Linux x86-64, Python 3.12+, the Intel oneAPI DPC++/C++ compiler at
`/opt/intel/oneapi/compiler/2026.0/bin/icpx`, GNU C++ and its C++20 development
headers, OpenSSL development headers/libraries, and Level Zero development
headers/libraries (`libze_loader`). The manifest records the exact per-file
flags, including strict floating-point options. This is not a driver installer.
No model weights are required to compile.

Choose a fresh output directory outside the checkout with at least 2 GiB free.
The build runs one compiler command at a time, at nice 19, with affinity limited
to two CPUs and a 4 GiB per-command address-space limit. Each command has a
15-minute timeout. Keep the CPU build separate from timed benchmarks.

```bash
# Check and unpack sources only; no compiler or GPU program is invoked.
python3 repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/scripts/build-native.py \
  --cards 1 --out /absolute/new-ownrt-source-check --prepare-only

# Compile the one-card program, using another fresh directory.
python3 repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/scripts/build-native.py \
  --cards 1 --out /absolute/new-ownrt-tp1-build

# Compile the two-card program from its own recorded source/flags.
python3 repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/scripts/build-native.py \
  --cards 2 --out /absolute/new-ownrt-tp2-build
```

Each output directory contains `source/`, `objects/`, per-command `logs/`,
`build-plan.json`, `build-receipt.json`, and, on success, `own-rt-iq3`.
The receipt records source and binary hashes, compiler versions, commands,
return codes, timing and compiler peak memory. Keep the relocated source tree:
the binary's readonly rotary and manifest paths point into that tree.

The only source rewrite replaces the original checkout root with the new
source directory, including readonly constant paths. The parser guards,
math code, compiler flags and kernel definitions remain unchanged. Paths,
compiler metadata and generated SYCL images can change executable hashes.
The new binary must **not** replace a sealed packet165 executable based on a
successful compile alone. The historical target hashes are:

| Program | Historical SHA-256 |
| --- | --- |
| One card | `1364bb3de0e0742ea3c5419a3f6850cea3646466c19732ad5cf3fe9be2b1b7cf` |
| Two cards | `cb2cef7125f8c20356e83f2a1fdd07c5318ce1518aecff659bdd76e2983c4e3a` |

## Qualification boundary

A successful build closes the compiler-input dependency chain. It does not
qualify a portable device launch or transfer the historical speed result to
this new binary. Fresh oracle-prefix comparisons, complete-output
fresh-process determinism, quality review and the unchanged host/device
admission checks remain required before promotion. The current independent
oracle covers only the first 128 output tokens; full-512 output parity is not
established by that prefix oracle.

The separate guarded replay entrypoint still selects the original sealed
lab binaries. This builder never weakens those guards or silently points the
replay at its new output. Raw archival commands and local build paths remain
provenance; the source archive is the portable build input.

## CPU build verification (2026-10-20)

Both clean-source builds completed: 42 translation units plus link for one
card, and 45 translation units plus link for two cards. All compiler-generated
dependency files passed the source-closure check. No inherited object was
reused, and neither new executable was launched.

[Build validation](manifests/build-validation.json) records output hashes,
compiler versions, timing, dependency checks and the exact qualification
boundary. The [compressed evidence](manifests/build-validation-evidence.tar.gz)
contains input manifests, executed commands, compiler logs, dependency lists
and receipts; it contains no binaries or model weights. The one-card build
started with the initial helper: its commands and source inputs match the
final manifest, and the strengthened dependency checks were rerun on all
42 compiler dependency files afterward. The two-card build and source-only
preparation used the final helper directly.

This section records the October 20 compile-only validation. The later
[October 22 one-card rebuild qualification](../../results/qwen38-flash-next-ud-iq3xxs-b70/ownrt-measurements-20261022.json)
passed two device runs at 31.827 / 31.813 tok/s with complete outputs identical
to the sealed line. That qualifies the tested rebuilt artifact, not every new
build or a clean-host installation. The two-card rebuild remains unqualified
on device. This archive does not build the newer diet/max23 record or streaming
engine; see [current identity boundaries](LATEST.md).
