# Authenticated two-shard loader preparation

The GNU CPU proof passes ten tests through the actual packet2 `iq3::read_plan`,
`Shard`, `Model` and `Model::census` implementations. Tiny synthetic two-shard
GGUFs cover all thirteen types in the new SC117 release. No real model header,
tensor payload, numeric decoder, `Slice`, reservation, Device or native runtime
was executed. The real files were checked with `lstat` against the frozen
[census](../metadata/new-census.json), which supplies the existing header hashes.
This is loader preparation; native dispatch and inference remain unadmitted.

[placement.tsv](placement.tsv) is the full native-format 1,224-tensor plan:
`shard name component type_id offset bytes layer mask rank dimensions...`.
The per-name component, layer and HC replica flags come from the original
[authoritative placement census](../../../qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json),
not name inference. Both cards retain all 194 mask3 HC replicas, now BF16.
There are two host tensors, 516 card0-only and 512 card1-only tensors.

| Placement | Raw logical weight bytes |
|---|---:|
| Card0, including HC replicas | 26,381,702,400 |
| Card1, including HC replicas | 29,604,404,480 |
| Host file backing | 29,137,853,440 |

These are actual loader mask totals, distinct from the earlier graph's logical
use accounting. They exclude expanded weights, caches, driver resources,
activation/scratch peaks and allocator overhead. They establish no device fit.

[shard-auth.tsv](shard-auth.tsv) uses the existing native six-column format:
`basename bytes dev ino mtime_ns ctime_ns`. [inputs.json](inputs.json) binds this
file, the placement plan, both retained header hashes and all parent sources.
The existing Engine's three-shard `Weights` entry must be updated separately;
these files do not change it or grant native admission.

## Constructor and trust boundary

The private overlay adds these types and overload while retaining the original
constructor:

```cpp
struct iq3::ShardIdentity {
  std::string basename;
  uint64_t bytes, dev, ino, mtime_ns, ctime_ns;
};
struct iq3::Admission {
  std::vector<ShardIdentity> shards;
  std::vector<Planned> expected;
};
iq3::Model(paths, candidate_plan, const Admission& trusted_admission);
```

The coordinator must independently authenticate the complete expected plan and
stat file, for example by fixed canonical paths and externally pinned file
hashes, **before** constructing `Admission`. Reading an unchecked candidate plan
into both arguments would defeat this boundary. The test executable accepts
separate trusted fixture inputs solely to exercise the API; it is not an
untrusted-input admission service or a model launcher.

The overload requires exactly two distinct admitted basenames and the same
candidate basename set, independent of path order. It checks every candidate
name, component, type, dimension, offset, byte extent, layer and mask against the
complete trusted descriptors. Only the thirteen target types are allowed.
Each file is opened read-only with `O_NOFOLLOW`; the held descriptor's regular
file status, size, device, inode, mtime and ctime match before and after its
header parse, and again after all `Model` validation. Existing split, block-row,
alignment, overlap, in-file extent and placement checks still run. BF16 mask3
HC replicas are accepted only by this bound overload. The default overload
still requires Q8 HC replicas. This is local coordinator trust, not protection
against a hostile same-user actor capable of mutating admitted files or code.
No long-term immutable-file guarantee is claimed after construction.

[overlay.patch](overlay.patch) records private packet2 changes, including the
previously reviewed layout-only math extension. Its new-format numeric decode
paths throw explicitly. [p195-loader.patch](p195-loader.patch) carries the same
loader constructor/header change onto the authoritative P195 native-base files,
preserving their generated guards, line directives and absolute includes.
The generator proves their bodies and patched bodies identical after only
normalizing those directives. The native integrator separately owns new-format
numeric dispatch and math-header placement; this patch does not supply them.

## Proof and retained attempts

[cpu-proof.json](cpu-proof.json) binds the successful GNU build, six compiler
inputs, two objects, binary, ten tests and generated loader inputs. Tests cover
all thirteen types and replica byte accounting; default Q8-only behavior;
every descriptor field; independently exercised original directory/placement
refusals; unsupported types; each stat field; duplicate/missing shard identities;
replaced inode and symlink; malformed split, overlap, truncation and plan text.
Source checks bind the before/after held-FD verification points; these are not a
concurrent attacker or filesystem race stress test.

The first attempt stopped before compiler execution because the shared compile
coordinator expects the `build_engine.limits` module callback. Its exact source
and failure are retained under `evidence/cpu-*/`. The corrected helper supplies
that alias with its own resource checks; one compile and all ten tests passed.
There was no parser/arithmetic test failure and no fixture replay. Exact
successful and failed receipts remain in their attempt directories; ignored
build artifacts preserve the successful executable and objects locally.

The executed command was:

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  taskset -c 8-15,24-31 nice -n 19 python3 -B \
  experiments/own-xpu-runtime/gsq-rco-iq3s/loader/build_cpu.py
```

The helper refuses an existing promoted proof, applies a 4 GiB address-space
cap and two-thread environment, acquires the repository compile lock, and
requires a 25 GB root floor plus 40 MiB write allowance. Total retained files
are below 2 MiB. [summary.json](summary.json) binds final documents and evidence.
The separate [control-upload review](evidence/controls-review.json) verifies the
root's primitive conversion evidence without replaying its executable.
