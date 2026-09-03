# Recipe Publication Standard

A recipe is **published** only when a third party can obtain every required
input from public locations and verify the same identities that the build and
result evidence name. Working on the lab host, being committed to Git, and
having a README are necessary but not sufficient.

This policy applies to every promoted `repro/` recipe and package. Existing
recipes may remain honestly classified as `lab-replay`, `record-capsule`, or
`candidate-portable-repro` while their closure is incomplete. They must not
claim public source closure.

## Required publication packet

Each published recipe must include a tracked `publication-manifest.json` using
`neural.download.recipe-publication.v2`. The manifest binds:

- the public guide and every build entrypoint;
- the exact public-repository source commit and SHA-256 of every build
  entrypoint at that commit;
- every immutable in-repository build input and its SHA-256 digest;
- every upstream source repository at a full commit;
- a public release URL and the name, byte size, SHA-256 digest, type, and direct
  download URL of every release asset;
- the successful build-log asset and hash-bound clean-build, runtime-smoke,
  and quality evidence;
- the UTC time at which the public assets were downloaded and reverified;
- for every later published image in the same recipe (a chain that ships its
  own release, such as the FP8 R139 W8A16 image), the same asset binding under
  a top-level `chain_releases` object keyed by chain id. It lives outside
  `chains` because the source-closure verifier treats every digest under
  `chains` as a repository-file binding; `--check-remote` re-verifies these
  assets too.

Binary-bearing recipes must publish the complete rebuilt wheel or equivalent
package, the result-critical shared libraries separately, the complete build
log, runtime/toolchain inventories, and a checksum manifest covering every
other release asset. ELF/SYCL binaries must record
whole-file hashes, portable RUNPATH, and hashes for `.text`, `.rodata`, `.data`,
and `OFFLOAD_DEVICE_CODE` where present. This binary path is a recovery and
audit aid; the source build remains authoritative. Remote validation also
checks that the wheel embeds the same result-critical libraries published as
standalone assets.

## Gates before `publication_status: published`

1. Start from a pristine clone of the public repository commit. Do not use a
   dirty source tree, an unpublished patch, or an originating-host checkout.
2. Resolve every build-script input. A declared `*_sha256` must match the exact
   referenced file; a second hand-maintained allow-list cannot override it.
3. Confirm every repository dependency is tracked. Reject `/home/<user>`,
   `/mnt/fast-ai`, `/media/<user>`, `file://`, and other originating-host-only
   dependencies. Normal platform paths such as `/opt/intel/oneapi` are allowed
   only when the required version and installation source are documented.
4. Obtain the base image by immutable registry digest, or rebuild its entire
   publicly closed parent chain. A local image tag or image ID alone is not a
   public dependency.
5. Build using only the declared public sources. Record the full log and exact
   compiler/runtime package inventory.
6. Verify artifact sizes and SHA-256 digests, binary sections, RUNPATHs, image
   labels/contracts, and a runtime import/operator smoke test.
7. Run the recipe's fixed quality and determinism gates. Publication closure
   does not promote a benchmark that failed output or realistic-workload rules.
8. Upload the release assets, then download every public URL and re-hash it.
   Re-extract the declared ELF sections, verify RUNPATH, verify the wheel's
   embedded binaries, and reconcile the checksum manifest. Record
   `remote_verified_at` only after this succeeds.
9. Run both validators from the clean clone:

   ```bash
   python3 tools/validate-recipe-publication.py
   python3 tools/validate-recipe-publication.py --check-remote
   python3 tools/validate-repro-guides.py
   ```

10. A second machine or clean supported OS replay is still required for
    `starter-guide` certification. Public source closure alone earns no
    beginner-ready label.

## Status rules

- `draft`: assets or a gate may still be missing. Direct URLs can be planned,
  but the website and README must say the packet is incomplete.
- `published`: all required asset types exist, all three validation gates pass,
  and every public asset has been downloaded and verified.
- If a public asset is removed, a digest changes, or a clean-clone build fails,
  immediately return the manifest to `draft` or publish a corrected immutable
  release. Never silently replace an asset under an existing release identity.

CI validates manifest structure, source-commit and tracked dependency closure,
build-script digest contracts, and hash-bound evidence. A dedicated publication
workflow runs the full `--check-remote` audit whenever a publication manifest
or validator changes, on manual dispatch, and on a daily schedule. Thus a
missing or silently replaced public asset fails both at publication time and on
the next scheduled integrity check; `remote_verified_at` is an attestation, not
a substitute for CI verification.
