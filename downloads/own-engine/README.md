# Own Xe developer source

Use [the developer guide](../../experiments/own-xpu-runtime/engine/DEVELOPING.md)
for Git checkout, prerequisites, CPU tests and build commands. Start the next
AI with [the project charter](../../experiments/own-xpu-runtime/engine/PROJECT.md)
and [DeepSeek GGUF onboarding](../../experiments/own-xpu-runtime/engine/planning/deepseek-v41-onboarding.md).
DeepSeek support is planned, not implemented.

## November 8, 2026 source snapshot

- [Source archive](ownrt-source-1acf8352d.tar.gz): 549 files, including the
  canonical native sources/assets, build script, developer guides, license,
  model profiles and CPU planning/deployment tests.
- Source commit: `1acf8352da192148ddd04a616945f221119733c3`.
- SHA-256: `879b480fae613be128ebb8c31d72939936a9442ea621a969c92d6bca7b737ed1`.
- [Source manifest](ownrt-source-1acf8352d.tar.gz.manifest.json) and
  [extracted CPU checks](ownrt-source-1acf8352d.cpu-checks.json): all 548 listed
  payloads verified and all 64 selected CPU tests passed. The archive's additional
  file is its own embedded manifest.
- [Native build validation](ownrt-source-1acf8352d.validation.json),
  [build receipt](ownrt-source-1acf8352d.build-receipt.json) and
  [build log](ownrt-source-1acf8352d.build.log): fresh extracted-source
  compilation/link passed for all 40 translation units with oneAPI 2026.0.0.
  All 267 compiled dependencies match this archive. This was a CPU-only build
  on the originating Ubuntu host, not a clean-host or GPU qualification.

This includes the November 4 persistent-serving native changes. The full Git
repository also carries Pi integration, research patches and results outside
the engine archive. The faster fixed-cost-2/HC-split research patches remain
separate; this snapshot does not silently merge them into the canonical engine.

The archive is a development source distribution, not a ready-to-run model
package. It contains no model weights, compiled binaries or installed toolchain.
New-host execution, model quality and performance require their own gates.
The older snapshots below remain available under their original identities.

## Download and inspect

```bash
curl -fL https://raw.githubusercontent.com/steveseguin/b70-optimization-lab/main/downloads/own-engine/ownrt-source-1acf8352d.tar.gz -o ownrt-source-1acf8352d.tar.gz
echo '879b480fae613be128ebb8c31d72939936a9442ea621a969c92d6bca7b737ed1  ownrt-source-1acf8352d.tar.gz' | sha256sum -c -
mkdir ownrt-developer
tar -xzf ownrt-source-1acf8352d.tar.gz -C ownrt-developer
```

Read `ownrt-developer/own-xpu-runtime-source/PROJECT.md`, then `DEVELOPING.md`.
Keep the source at its build location; native code reads included RoPE assets
relative to that path. For ongoing development and contribution, use the Git
checkout instead of editing an archive without history.

## Historical source archives

Checksums for every retained archive are in [SHA256SUMS](SHA256SUMS).

- [e6f89fbce](ownrt-source-e6f89fbce.tar.gz): October 25 research source.
- [9d6320c1b](ownrt-source-9d6320c1b.tar.gz)
- [f6079c380](ownrt-source-f6079c380.tar.gz)
- [1cab4a1e5](ownrt-source-1cab4a1e5.tar.gz)
