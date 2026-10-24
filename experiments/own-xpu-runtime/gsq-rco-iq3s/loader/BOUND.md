# Compiled exact-model authority

[bound.hpp](bound.hpp) adds immutable expected descriptors and identities to the
[loader API](README.md). Its generated C++ contains all 1,224 placement entries,
the two exact shard stat identities, fixed plan/auth/model paths, complete
plan/auth SHA256 values, and both raw GGUF header prefix lengths and SHA256s.
[bound-authority.json](bound-authority.json) binds the generator, template and
frozen census/input sources. No model file was read to generate it.

The Engine must include its admitted private `iq3` loader definitions first,
then this header. Its expected integration is:

```cpp
auto checked = gsq::bound::authenticate(
    a.plan, a.auth, a.model,
    [](const std::vector<uint8_t>& bytes) { return hash(bytes); });
model = std::make_unique<iq3::Model>(
    checked.paths, std::move(checked.candidate), checked.admission);
```

`hash` must be the independently admitted SHA256 implementation. The helper
checks plan and auth paths exactly, opens each read-only/no-follow, limits each
to 2 MiB, hashes the same held-file bytes and checks stable size/inode/device/
mtime/ctime. It then verifies each compiled shard identity and raw header hash
using a held no-follow descriptor. Prefixes are exactly 11,024,355 and 173
bytes; the first includes the complete architecture/tokenizer metadata and
tensor directory. Alignment padding and tensor payload are excluded. Each
prefix is capped at 16 MiB. The file identity is checked again after hashing.

After both text hashes match independently compiled constants, `candidate` is
the compiled expected descriptor list. There is no unchecked second pathname
read and no expected identity derived from candidate GGUF fields. The unchanged
admitted `Model` constructor subsequently parses and validates actual tensor,
split and extent fields and checks the reopened held descriptors against the
same compiled stats. These checks assume the repository coordinator and local
user are trusted; they do not promise immutable storage after constructor exit.

The helper performs header reads only when a future admitted preflight calls
`authenticate` with the real fixed root. **That call has not been executed.**
Native inference remains unadmitted. The numeric dispatch and Engine integration
are separate work; this header changes neither.

[bound-proof.json](bound-proof.json) records one GNU compile/run of a pure CPU
fixture: 24 checks pass, with no Device or real model accesses. It checks all
compiled descriptors against the already pinned placement bytes, exact stat
text, 194 BF16 replicas, bounded prefix reads, each stat field, changed files,
symlinks, directories, text mismatch, wrong fixed paths, post-hash mutation,
size limits and refusal of an alternate model root. Temporary synthetic files
exercise the read helper. The fixture's injected string-identity callback tests
the comparison/control seam; it does not qualify a SHA implementation. The
actual SHA implementation/call site must remain pinned by the native integration
receipt. Existing loader proof and its source snapshots are unchanged.

The earlier loader summary describes its original under-2-MiB core batch. With
this later compiled authority and its source snapshots, the complete loader
folder is approximately 2.23 MB, still below the 40 MiB budget.
