# Flash-Next A367 CPU preparation — October 16, 2026

**Model PASS:** all 144 files / 131 shards match; zero file differences.
**Source PASS:** all 75 patch/bundle members and 2,305 Python files match;
all 18 certified stage files are reusable without a rebuild.
This is preparation, **not launch approval**. The calibration was not started,
queued or resealed. The owner's RAID repair and a filesystem with the required
60 GiB free remain necessary. Existing packet seal drift and the reviewed receipt
replacement below must also be resolved before a launch.

## Scope and retained evidence

Work followed the owner's October 16 authorization for one full read-only USB
payload pass and a new pinned source directory. CPU work used nice 19, ionice
class 3, cores 4–15,20–31 and `python3 -B`; no compilation occurred. No device
binary, model runtime, health probe, server, service, sudo or device interface was
run. Neither protected source/archive nor the failing RAID was inspected or
changed. Existing untracked experiments were preserved. The lab stayed on main.

Evidence is in [data/2026-10-16-flash-next-a367-prep](../data/2026-10-16-flash-next-a367-prep/):

- [Full model receipt](../data/2026-10-16-flash-next-a367-prep/model-payload.json)
  and [historical reconciliation](../data/2026-10-16-flash-next-a367-prep/model-reconciliation.json).
- [All 75 patch/bundle hashes](../data/2026-10-16-flash-next-a367-prep/patch-members.json)
  and [source reconstruction](../data/2026-10-16-flash-next-a367-prep/source-reconstruction.json).
- [18 stage files, collectives and version metadata](../data/2026-10-16-flash-next-a367-prep/stage-and-runtime.json),
  [static ELF evidence](../data/2026-10-16-flash-next-a367-prep/stage-elf.txt)
  and [build flags/provenance](../data/2026-10-16-flash-next-a367-prep/build-provenance.json).
- [Existing seal mismatches](../data/2026-10-16-flash-next-a367-prep/existing-seal-audit.json),
  [CPU checks](../data/2026-10-16-flash-next-a367-prep/cpu-validation.json)
  and [unapplied source-path patch](../data/2026-10-16-flash-next-a367-prep/proposed-source-path.patch).

## Model method and receipt mismatch

The actual launch root is
`/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`.
The [new helper](../scripts/verify-flash-next-a367-launch-payload.py) uses the
existing frozen tree verifier's contract, exact root inventory, regular-file
checks and index validation. It authenticates the USB tree metadata by the
record's `4a3793bd…` SHA256, then requires its entire file map to equal the
independent packet-1 publisher snapshot (`bc69301a…`, revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`).

Each of the 144 publisher root files is read in full. SHA256 is recorded for
every file; the 133 LFS objects are compared with publisher SHA256, and the 11
ordinary files with publisher Git blob SHA1. Config/index additionally retain
their frozen SHA256 checks. All 131 indexed weight shards are covered, totaling
185,563,783,127 bytes with the other root files. `.cache` download bookkeeping
is excluded exactly as in the existing verifier; its tree manifest is checked.
The helper checks file identity, sizes and timestamps across the pass, retains
individual mismatches, rejects receipt overwrites, writes only into this repo,
and enforces the owner's root-free/growth guards. No second bulk pass was run.

The historical gate expects receipt SHA256
`6ae22291119e8c8a01597bda9fe4b1fb5850912655ec188e363a88eb6de58470`.
The file currently at its recorded NVMe receipt path hashes to
`f7a9a494428f022f2943fd50bac984203c9d00749833bb4d8188606473c72e45`;
its exact bytes are [retained here](../data/2026-10-16-flash-next-a367-prep/historical-receipt-observed.json).
It is a successful **September 3** verification of the final NVMe path.
The [August 27 note](2026-08-27-storage-relocation-and-flash-next-localization.md)
explicitly says the original receipt bound the temporary
`.Qwen3.8-Flash-Next-FP8.incoming-20260827` path before rename.
Thus the current file is a later receipt, not the byte-identical original.
The original receipt's bytes were not recovered, so an exhaustive original-JSON
field diff is not claimed. The reconciliation compares all retained per-file
digests, sizes and digest kinds against this fresh USB read and the publisher
manifest: **144/144 equal, no differing files**. A changed receipt hash is not
evidence of changed weights. The full pass took 394.6 seconds. The new source
uses 154.1 MB of file bytes; root free space declined by about 179 MB and remains
24.09 GB, comfortably within the 6 GB growth cap and above the 14 GB floor.

The replacement admission must bind **the USB launch path**, publisher revision,
both expected manifests, all file hashes and sizes, completion time, verifier
identity and a passing full verification. The owner-window binds the SHA256 of
that exact fresh receipt. Preserve the old contract and both historical hashes;
do not simply relabel the September 3 receipt as the August 27 receipt or use an
NVMe receipt to admit USB.

Run this exact command from the repository immediately before a future admitted
launch; it creates a new receipt and never launches a model:

```bash
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B \
  /home/steve/llm-optimizations/scripts/verify-flash-next-a367-launch-payload.py \
  --receipt "/home/steve/llm-optimizations/data/2026-10-16-flash-next-a367-prep/payload-prelaunch-$(date -u +%Y%m%dT%H%M%SZ).json"
```

Require exit 0 and `passed=true`, then hash that receipt into the new owner-window
as `payload_sha256` and pass its absolute name to `--payload-receipt`. The packet
requires `0 <= launch_time - verified_unix <= 3600`; today's receipt is historical
preparation evidence once it expires. Obtain the fresh health receipt after the
long hash/audit work so its shorter 600-second limit can still be satisfied.

## Clean source and reuse decision

New source export:
`/home/steve/src/vllm-flashnext-a367-clean-20261016`.
The certified source is reconstructed from public commit
`76cfe1cd88d30d525eec8be5bff75f8b77471c88`, not current upstream. This is a
historical record reconstruction under the owner's explicit pin, not a new
optimization base.

A new bare object store at `.source-objects` fetched only the public base with
`--depth=1 --no-tags`. The four in-repo bundles were verified and fetched to
FETCH_HEAD without branch refs. Independently, `git read-tree` loaded the base
into a private index; `git apply --cached` applied each series in order, and
`git write-tree` had to equal its bundled tree after each stage:

| Series | Patches | Resulting head |
| --- | ---: | --- |
| Lossless MTP1 | 55 | `1b2a17c1e7c41985d6a5e0eb324ada4775c25e60` |
| Placement | 9 | `005dc57895896f770157ea94f68e473e7447139e` |
| Triton HC | 1 | `622191221475b53cc6f7f4d847860939f4c300ab` |
| Fused QSA | 2 | `6d8724577dabbee5fa0bbc70c4d927c6174c8d8a` |

`git archive` exported the final tree
`3e8dfc5937087d186cd4a99a6bf15213be732462`; the temporary tar was removed.
All 2,305 Python files match the supervisor's hashes and exact file set.
All 75 patch/bundle members match, including the kernel bundle that is retained
for provenance but not rebuilt. This is a standalone source export, not a Git
working tree; the object store has no branch refs or secondary worktrees. The
old `verify-series.sh --apply` helpers were not run because they create worktrees.

**Reused, without copying or rebuilding:** all 18 files in the USB
`runtime-gdn-roundstate-bbae3c5-b70/vllm_xpu_kernels` stage, the pinned oneCCL
`libccl.so.1.0`, the venv's `lib/ccl/kernels/kernels.spv`, and the existing host
venv. The two collective hashes and installed version metadata match. This is
not a complete byte audit of every venv dependency or a runtime import test.
**Rebuilt:** nothing. The Python source was exported, not compiled or installed.

The stage is the certified hybrid: `_xpu_C.abi3.so` is
`6b95dc90c25bb0f9c2503805e4184648ddcac089ec54ec65fe7eeb13ab2b097b`,
from `bbae3c5` over `e421889`; the other 17 members are the served stage bytes.
Static inspection preserves the historical distinction: nine DSOs need
`libsycl.so.8` and report compiler 2025.3.3, while the manifest-pinned
`xpumem_allocator.abi3.so` needs `libsycl.so.9` and reports 2026.0.0. This was
already in the frozen stage; no new build-era mixture was introduced. Its
transitive loader closure still needs review before native work. Never replace
the allocator or rebuild the other 17 files merely to make version labels agree.

Static ELF exports, embedded options, NEEDED and compiler comments were read
without loading the libraries. No complete build-flag accessor was found in the
inspected exports. The retained `_xpu_C` build artifact matches the certified
stage; its separately hashed CMake/Ninja records supply the invocation flags.
They specify Release, `-O3 -DNDEBUG`, `-fsycl`, `spir64_gen`, targets
`pvc,bmg,bmg-g21-a0,bmg-g31-a0`, GDN ON, MoE OFF and XE-default OFF.
The receipt distinguishes embedded strings from build-record evidence rather
than claiming every string is a compile option. The kernel-library flags in
this build directory are not claimed to describe the 17 reused older files.

Any future unavoidable rebuild must first estimate disk and time and remain
under this task's budget. Pin compiler **and**
`SYCL_LIBRARY=/opt/intel/oneapi/compiler/2025.3/lib/libsycl.so` and
`SYCL_LIBRARY_DIR=/opt/intel/oneapi/compiler/2025.3/lib`, never `compiler/latest`.
The historical build script uses `-j8`, and its Ninja file allows 16 parallel
device links: neither may be executed under this task's maximum of two jobs.
A rebuilt binary requires a new, same-binary oracle and fresh determinism and
target-output qualification before any speed claim. Agreement between rebuilds
alone cannot establish agreement with the promoted binary's oracle. No rebuild
estimate or compile was needed for this successful reuse path.

## Proposed packet changes and reseal review

**No changes below were applied to the active packet.** The small source-path
patch passes `git apply --check` only. It overrides `source` in calibration
`paths()` to the new export, leaving the USB model, stage, graph, MTP1 and all
compute selectors unchanged. `build_environment` then supplies the new
`PYTHONPATH` and `PACKET4_SOURCE`; the existing spawn bootstrap already requires
`vllm.__file__` and its selected dependency hashes to resolve to that source.
The shared fixture driver's defaults are deliberately outside this path-only
proposal; if it is later relocated too, update its preregistration and the
hard-coded source path in `driver/test_driver.py` together.

Review and reseal in this order:

1. Review the model reconciliation and explicitly supersede the obsolete
   historical-receipt admission dependency. Keep its failed historical hash
   comparison in the audit. Add a separately pinned reconciliation input to the
   packet, verifying its expected/observed historical hashes, fresh USB receipt
   hash, revision, manifest identity and zero file differences. The later fresh
   payload gate must still run and bind the actual USB path; no unconditional
   bypass, silent model-contract repin or old-receipt freshness waiver.
   `driver/window_driver.py:verify_environment` currently fails before that fresh
   gate and therefore needs this reviewed amendment, beyond the path-only patch.
2. Review the source override, declare it and the receipt-dependency amendment
   in calibration `preregistration.json` and README, and update WINDOW-RUNBOOK.
   Review the venv import mapping and complete transitive shared-library closure
   without substituting a modern wheel. Source hashes and all 75/18 member hashes
   stay unchanged. Keep the no-generation calibration scope and all memory floors.
3. Review existing drift: `MEMORY-ADMISSION-REVISION.md` now hashes to
   `1ab81c32…` but both the calibration and driver seals pin older different
   versions; `driver/preregistration.json` also pins older
   `stage2/packet1b/reference.py` and `test-receipt.json` hashes. The complete
   expected/actual hashes are in the seal audit. The reference changed arithmetic
   in commit `3ebd0d2b1`; do not mechanically bless that as an A367 oracle.
   For the zero-generation calibration, review whether these fixture-only pins
   should remain frozen or be separated into a calibration dependency set.
4. Update the selected dependency pins, driver seal if shared code changes,
   calibration seal, and their documentation after those reviews. Run the CPU
   tests with the reviewed paths and byte checks; require zero seal mismatches.
   Today's unchanged calibration tests give 48 passes and one seal error; the
   new helper's six tests and shared tree verifier's nine tests pass.
5. Reissue every affected owner-window hash, including packet-4 preregistration,
   calibration preregistration/seal, health and fresh payload. A calibration-only
   memory-floor exception, if needed, must use the owner's exact newly hash-bound
   approval. Existing approval text cannot survive a seal change.

Still required for a device window: repaired/admitted output storage with at
least 60 GiB free, current exclusive ownership, current boot/halt/fault admission,
the 305-second stop gap, fresh passing four-card health, fresh payload receipt,
and the start-floor decision if the default 120,000,000 KiB is unmet. The
12,000,000 KiB live reserve stays fixed. This CPU task supplies none of those
device permissions and makes no claim about current card state or speed.
