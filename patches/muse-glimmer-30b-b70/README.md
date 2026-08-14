# Muse-Glimmer-30B B70 source snapshots

These artifacts reconstruct the exact llama.cpp source used for the 2026-08-13
Muse Q8/WOQ record. The measured source was not a public commit: it was a
75-commit local branch plus a three-file working-tree delta.

## Recommended restore

Clone public llama.cpp, check out
`030ebb558a5820b444a8f836ed5cdd46c9b4bd7a`, then apply
[`llama.cpp-030ebb558-to-q8-woq-century-20260813.patch`](llama.cpp-030ebb558-to-q8-woq-century-20260813.patch).
That single patch is the authoritative record source and includes both the
private committed stack and final working-tree changes.

For audit/history, [`muse-100-private-history.bundle`](muse-100-private-history.bundle)
contains branch `muse-100-campaign` at
`1ff6bcb6c1d9c175145bd4c212c24bb2fb13f539` and declares the public base as a
prerequisite. The final uncommitted changes are also split into:

- [`q8-woq-final-kernel.patch`](q8-woq-final-kernel.patch): fixed-N16 direct
  oneDNN Q8_0 WOQ kernel and scale sidecars;
- [`prompt-cache-measurement.patch`](prompt-cache-measurement.patch): one
  additive response field used to prove prompt-cache reuse was zero.

Do not apply both the combined patch and the split patches.

To inspect the private history after cloning the public repository/base:

```bash
git bundle verify /path/to/muse-100-private-history.bundle
git fetch /path/to/muse-100-private-history.bundle \
  muse-100-campaign:refs/heads/muse-100-campaign
git log --oneline 030ebb558..muse-100-campaign
```

## Checksums

| Artifact | SHA-256 |
| --- | --- |
| complete base-to-record patch | `3965702b96fe18e2dc9110c7593fd33fbd68312e8321094b8b61b4656b380f19` |
| private-history bundle | `21cb212747b32c74661943811d3f4c2c6550340a5e70b763428fdd5a45954308` |
| final WOQ kernel delta | `a22ab25960898c5b5d2aec2154f69b2e0269548e2d87e474eff86f36e87b5196` |
| prompt-cache measurement delta | `6c3f7c2028f72ae65e9a5b3a67049a121392061b53291960b3a42b9a34f009d4` |

Run `sha256sum -c SHA256SUMS` before use and see the
[standalone reproduction recipe](../../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md).
