# Laguna S 2.1 102.971 tok/s source snapshots

These files preserve the exact local vLLM and vLLM XPU-kernel source used by
the approved four-B70 Laguna record. The original experiment branches point at
upstream project remotes and are not assumed to be publicly pushable.

| Component | Public upstream base | Record commit | Bundle SHA-256 | Combined patch SHA-256 |
| --- | --- | --- | --- | --- |
| vLLM | `1d354c694eedf241b836319dba497345a5aa1167` | `e596ef1543466ae1a05e5bb8091f58872e2b18ba` | `56bb463925cf53ba20db81c980264fd2a993d1e76f15731ac5676674fa0b9126` | `23fc7766c1985c6237fcab12dae62096f759511dbc7c5dc7f9828fe93d4c6d6d` |
| vLLM XPU kernels | `11f42aa47ff51924b3d9527cfc2bfef5fd2d98e5` | `6f9dd3c3a7b1b677a992ca4f431a968408f9c816` | `7aeec0b55e7b40f26d993ddf6dfb978ec267da1ae1e89d9f54c6db4d80022ed3` | `0eb4337547160394ff4ebaa66782dd936fbad3fffeceb85af08832f6d99dbd69` |

The `.bundle` files preserve the original commit graph after the listed public
prerequisite. The `.patch` files are review-friendly binary-safe combined tree
diffs from that base to the record commit. Both bundle prerequisites are
contained in the corresponding upstream `origin/main`.

Restore vLLM from an upstream clone:

```bash
git fetch origin
git fetch /path/to/b70-optimization-lab/patches/laguna-s-2.1-xpu-b70/vllm-laguna-width12-dflash-fp8-102tps-record-20260726.bundle \
  experiment/laguna-width12-stack-clean-20260726:refs/heads/laguna-record
git checkout e596ef1543466ae1a05e5bb8091f58872e2b18ba
```

Restore the XPU kernels from an upstream clone:

```bash
git fetch origin
git fetch /path/to/b70-optimization-lab/patches/laguna-s-2.1-xpu-b70/vllm-xpu-kernels-laguna-width12-102tps-record-20260726.bundle \
  experiment/laguna-width12-router-clean-20260726:refs/heads/laguna-record
git checkout 6f9dd3c3a7b1b677a992ca4f431a968408f9c816
```

Validation performed before promotion:

- both bundles pass `git bundle verify` in repositories containing their
  public prerequisites;
- both combined patches pass `git apply --check --reverse` at their exact
  record commits;
- bundle heads equal the record commits in the table;
- all four file SHA-256 values were recomputed from the tracked snapshots.

The result packet is
[`../../data/laguna-s-2.1-width12-dflash-fp8-record-20260726.json`](../../data/laguna-s-2.1-width12-dflash-fp8-record-20260726.json).
