# Incremental build plan — NOT RUN

Only `entry.o` is rebuilt; reuse the other 39 objects. The receipt compiles
`entry.cpp`, which includes main, which includes rank, which includes RESET and
the two native controllers. Sources: executed `entry.cpp:2`, `main.cpp:1841`,
`rank.hpp:267-269`, `v3_boundary.hpp:30`; original `entry.d:2-3,118,121,123`.
Full source aliases and links are in [DESIGN.md](DESIGN.md). Dependency scan and
object existence are recorded in [source-check.json](source-check.json) and
[build-plan.json](build-plan.json). These are source/stat checks, not build proof.

The original receipt is `L/recurrent-f32/evidence/native-build.json`:
`commands[0]` at lines4-26 is the exact compile command; `commands[-1]` at
lines507-556 is the link command. The compiler is
`/opt/intel/oneapi/compiler/2026.0/bin/icpx`. Preserve every compile flag, including
`-O2`, `-g0`, `-DP56X_SLEEP20=0` and the precision flags below.

**Precision trap:** the recorded link command omits the compile precision flags.
The proposed link explicitly adds `-fno-fast-math -ffp-contract=off
-fdenormal-fp-math=ieee -foffload-fp32-prec-div -foffload-fp32-prec-sqrt`, as required
by this brief. This is a deliberate link-command difference; do not silently
call it a bit-identical rebuild. First link an unchanged-source control using
the same new link flags and the original `entry.o` in a separate new output,
then require exact emitted tokens and full target state versus the unchanged
5926 binary. Candidate defaults must pass that comparison too. Any mismatch
blocks adoption; no tolerance or compiler-flag relaxation is allowed.
(Receipt:5-18,507-556; verification plan: DESIGN.md.)

Absolute include paths were rebound only between the seven copied files.
Unchanged includes still resolve to the executed source tree. `-I` alone cannot
override the original absolute includes. All original `#line` directives remain;
main's physical line2 pins `__FILE__` to the historical packet136 main.cpp, so its
`mtp-manifest.tsv` and `rope.bf16` lookups remain there (original main:151,1180).
Do not copy different assets beside this packet or remove those directives.
Original/copy hashes are in [source-manifest.json](source-manifest.json).

## Object inventory

Every object listed below existed at this packet's stat check. Expected hashes
come from the receipt's `objects` mapping (lines1182-1221), not a new object hash
pass. Rehash and compare all reused objects before a separately authorized build;
missing/mismatched dependencies stop the build. Do not regenerate or overwrite
old objects. The exact order is preserved in build-plan.json and the link below.

| Location | Existing objects | Action |
|---|---|---|
| `/mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/` | `entry.o` | Recompile to this packet's future-build directory |
| Same directory | `11,13,15,16,20,22,23,24,25,26,28,29,30,31,32,33,34,35,36,38.o` | Reuse 20 |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/` | `1,2,3,4,5,6,7,8,9,10,12,14,17,18,19,21,27,37,39.o` | Reuse 19 |

Total existing object bytes: 23,608,712; original entry.o: 4,657,696.
([build-plan.json](build-plan.json), `objects` entries.)

## Exact commands for a future authorized build

**Do not run these during Task A.** No compiler or native executable was invoked.
The current hard host rules prohibit this build. A future operator must obtain
build authorization and check current memory/disk capacity; the old receipt's
floors at lines561-564 are historical, not current admission. Build sequentially:
one compile, then one link, no parallel compiler processes. Keep the same flags
on both stages; reducing precision is not a memory workaround. Use only a fresh
output directory and preserve the original binary and objects.

From repository root, create the NEW output/TMPDIR, then compile and link:

```bash
mkdir -p /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/a-reset-stream/future-build/tmp
export TMPDIR=/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/a-reset-stream/future-build/tmp
/opt/intel/oneapi/compiler/2026.0/bin/icpx \
  -std=gnu++20 \
  -O2 \
  -g0 \
  -DP56X_SLEEP20=0 \
  -Werror=return-type \
  -fno-fast-math \
  -ffp-contract=off \
  -ffunction-sections \
  -fdata-sections \
  -fsycl \
  -fdenormal-fp-math=ieee \
  -foffload-fp32-prec-div \
  -foffload-fp32-prec-sqrt \
  -Werror=deprecated-this-capture \
  -MMD \
  -MF \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/a-reset-stream/future-build/entry.d \
  -c \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/a-reset-stream/source/experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/build/source-v2/experiments/own-xpu-runtime/gsq-rco-iq3s/dense-packed-block/engine/build/source/entry.cpp \
  -o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/a-reset-stream/future-build/entry.o
/opt/intel/oneapi/compiler/2026.0/bin/icpx \
  -fno-fast-math \
  -ffp-contract=off \
  -fdenormal-fp-math=ieee \
  -foffload-fp32-prec-div \
  -foffload-fp32-prec-sqrt \
  -fsycl \
  -Wl,--gc-sections \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/a-reset-stream/future-build/entry.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/11.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/13.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/15.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/16.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/20.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/22.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/23.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/24.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/25.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/26.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/28.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/29.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/30.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/31.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/32.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/33.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/34.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/35.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/36.o \
  /mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-native-a/38.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/1.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/2.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/3.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/4.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/5.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/6.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/7.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/8.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/9.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/10.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/12.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/14.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/17.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/18.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/19.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/21.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/27.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/37.o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/full-native-1792819219994861899/39.o \
  -lcrypto \
  -lze_loader \
  -Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib:/usr/lib/x86_64-linux-gnu \
  -o \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/a-reset-stream/future-build/sc117-reset-stream
```

Do not launch the resulting binary from these instructions. Device verification
is a separate authorized operation described in DESIGN.md. Record compiler/source/
object/binary hashes and exact commands, and confirm the new dependency file
resolves all seven changed files to this packet, not their frozen originals.
The current live service continues to use its existing binary and imports.
