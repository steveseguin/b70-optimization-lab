# Proposed lossless state evidence bundles

Status: source-only proposal, 2026-10-24. No implementation, build, payload read
or device action. Wait for the running combined candidate measurement before
changing capture code.

Use one uncompressed target-state bytebundle per rank/request, with an explicit
index of original relative buffer filenames, offsets, lengths and SHA256 hashes.
Retain byte-identical `state.json`. Initially leave the five draft `.bin` files
and other JSON/log evidence unchanged. This replaces roughly 2,108 target `.bin`
files per request with two bundles and two indexes. Existing GPU computation,
allocation/state lifetime, protocol, RESET semantics and oracle remain unchanged.

The two implementation seams would be:

1. Private `rank.hpp::pipeline::state_dump` (lines250–257): stream the same
   per-buffer readback bytes into a checked exclusive temporary bundle, keeping
   the current buffer names, iteration order, sizes and `state.json` bytes.
   Check every write/close, fsync payload/index and parent, and publish a final
   completion marker only after both are durable. Preserve failed partial files;
   no fallback, retry or request continuation after failure.
2. [serving/adapter.py](../serving/adapter.py), `state_hashes` (lines183–191):
   independently stream every indexed payload range, verify its size/hash and
   reconstruct exactly the old relative-filename→SHA256 map, including the
   unchanged `state.json`. Compare this map with the existing independently
   audited baseline. Reject duplicate/unknown/missing names, overlaps, gaps,
   out-of-bounds ranges, trailing bytes, symlinks or incomplete capture. An index
   hash alone is insufficient evidence of the actual buffer bytes.

RESET is a material hazard: `request_reset` dumps the **old** request again
before zeroing allocations and changing `e.a.output`. The first `state_hashes`
return therefore does not establish final file closure. For an already sealed
bundle, the proposed repeated dump must recompute current logical inventory,
buffer hashes and `state.json`, require exact agreement, and retain the original
sealed bytes rather than overwrite them. A mismatch or existing incomplete
capture must fail. After both RESET acknowledgements, the previous request's
target and draft output is closed; the last request closes after normal FINISH
and positive owner teardown. Archival/recovery must use this closed proof, not
merely the existence of a completion marker. Startup's blank dump and excluded
warmups remain accounted for.

This is an evidence-format change outside the request token timing interval:
the [suite](../baseline/suite.py) calls `state_hashes` after `NativeController.run`,
and RESET maintenance resets the next request's counters. It does not remove
readback, hashing or durable-write costs, and no speedup is claimed. A small
qualification must establish format equivalence before adopting it in a suite.

Bundles remove NTFS MFT fanout and per-file archive/prune overhead, **not raw
byte capacity**. The full27-dump suite still contains 6,248,947,500 raw `.bin`
bytes, plus metadata. If USB space after the current run is about5.6GB, another
full suite still requires capacity recovery. Compressing closed bundles with
complete member/range verification should involve far fewer files, but its time
and compression ratio are unmeasured. Preserve the existing verified-copy-before-
deletion discipline of [closed_baseline_bins.py](../storage/closed_baseline_bins.py).

Direct USB bundles need no additional NVMe payload staging and retain the
existing bounded per-buffer readback allocation. In contrast, conservative local
staging256MiB + root cache128MiB + reserve64MiB needs469,762,048 bytes above the
27GB floor, exceeding the observed429MB margin. Local staging plus a second local
archive would require more. These are admission estimates, not fresh host checks.

Minimal tests before any native qualification: synthetic byte-for-byte old-files
versus bundle oracle parity (including alternate banks and `state.json`), all
index/extent/truncation errors, failed write/fsync/close with no success marker,
repeated DUMP/RESET agreement and mismatch, and preservation of incomplete or
sealed evidence. Then one bounded native same-state comparison must demonstrate
the unchanged full oracle map and normal closure. No checkpoint/session redesign,
compression in the native arithmetic path or new optimization campaign is needed.

Source identities below are relative to this lane. The private generated files
are bound by the original [full native build receipt](../integration/evidence/full-native-build.json);
they are source inputs, not portable standalone reproduction entrypoints.

| Source | SHA256 |
| --- | --- |
| `serving/adapter.py` | `68538b214b7bda9c2fa5cd87534bad2243745b8a1af0dc82b43f01da48b06a01` |
| `baseline/suite.py` | `301347fe701eaaaa1e16e7a3891da2808a956147ae67b9b918dd451b7fe010d4` |
| `integration/build/private/source/diet-native/native-src/rank.hpp` | `bdd2955e31eddb821565c8a7b59e49dfa837986715d5469b2765297cf0588a7c` |
| `integration/build/private/source/diet-native/native-src/mtp.hpp` | `deaa729573f2bb0304a9882ccede5267f6d272b5736a45a9dd6057eb0f0df542` |
| `integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/request_reset.hpp` | `0e718893e0bae5434b37fc9d329c9480d7ea5fb823cb9511b4a4e73ea1d79ab8` |
| `storage/closed_baseline_bins.py` | `6a86c61fe46b453f7f9516d7b41169f0314cfc2b2716f82aab54b05c8df566ab` |
| `integration/evidence/full-native-build.json` | `5d4643615ad94c0805de75ac7a01806dbb784c7fc09052f90ee04deafc5abd6d` |
