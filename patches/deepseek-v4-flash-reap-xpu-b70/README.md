# DeepSeek V4 Flash K160 source archive

This folder preserves the exact source history and reviewable combined deltas
for the 80.820052 tok/s record, plus later EAGLE experiment snapshots. The
vLLM archive now has an additive public-anchor repair after an audit found that
the original historical bundle was thin against a then-unpublished local
commit. Exact base and record recovery tags have since been published.

## Promoted record source

| Component | Declared prerequisite | Record commit | Preferred bundle SHA-256 | Combined patch SHA-256 |
| --- | --- | --- | --- | --- |
| vLLM | public upstream `382bbd51448b2f58c73b3e51d051bc352166ba91` | `264c7f2f7df21ddeeab32ecca0353133344f1ac9` | `bdb02267d5a128665fa46ca0119e218df8596a43ccbbe41767d5543acc9a7096` | `9228bccd3e690a9ca06366a21e6c2506fd088176f580eb8355d83a5c6fa71aff` |
| vLLM XPU kernels | `dda91d171fbc3f51d1d65a7f8839714b1efffd42` | `31315673737d95da0f79179c8f755260ef02c1d6` | `4c04c7f501c780dc13f5db69d551e3da52f5cf1103c83cf10f64e57afffdb9d9` | `8be7f7c397258921928c6cf013c54b24866594b03afe908946dd10669ef92981` |
| oneCCL | `66499938b7a8b615e26361c52900e7aec306ce50` | `48fda4f0e074db005596d6899d5227d3f0316c12` | `100d9c7f03e648501e174498a72e9da88751b42acc3a94828ff95db7c1d5849c` | `21a60677051d61da8bf16bb51ac277fb18c678ef008a6db18a6b1f2d723e27cc` |

Use
`vllm-deepseek-v4-k160-dspark7-80tps-record-20260718-public-anchor.bundle`
for vLLM restoration. It contains all 121 commits after the verified upstream
anchor, including experimental base `61c87db645c256651b5a366f538898485077ad32`,
and restores exact record commit `264c7f2f7df21ddeeab32ecca0353133344f1ac9`
and tree `98d21ed3a502a04eb8d9c57f185a7486c15286c1`.

The original
`vllm-deepseek-v4-k160-dspark7-80tps-record-20260718.bundle` remains
byte-identical at SHA-256
`cebc81bedc22496dc82836b9419428e0377a3eb4e7ac213014a7306c7b30e825`
for historical custody. It remains a thin artifact and cannot restore directly
into an empty repository. Its exact prerequisite is now public as tag
[`deepseek-v4-k160-vllm-base-20260714`](https://github.com/steveseguin/vllm/releases/tag/deepseek-v4-k160-vllm-base-20260714),
and the exact record is independently public as tag
[`deepseek-v4-k160-vllm-record-20260718`](https://github.com/steveseguin/vllm/releases/tag/deepseek-v4-k160-vllm-record-20260718).
The corrected official-upstream-anchored bundle remains the preferred archive;
the old bundle is recoverable only after explicitly fetching its base tag.

The corrected bundle's provenance contract is
`vllm-deepseek-v4-k160-dspark7-80tps-record-20260718-public-anchor.provenance.json`.
Validate it against an official-upstream clone before use:

```bash
python3 tools/validate-git-bundle-provenance.py \
  --manifest patches/deepseek-v4-flash-reap-xpu-b70/vllm-deepseek-v4-k160-dspark7-80tps-record-20260718-public-anchor.provenance.json \
  --provenance-repo /home/steve/src/vllm
```

The validator rejects undeclared thin bundles, requires each thin prerequisite
to be reachable from the declared public remote-tracking ref, seeds a new
disposable repository with only that prerequisite, and proves the exact record
commit and tree after restoration. It also resolves and fetches both recovery
tags by exact ref into a second empty repository. The `.patch` file remains the
reviewable delta from experimental base `61c87d...`; it is not a portable
substitute for the corrected bundle. Historical-bundle recovery commands and
the corrected fetch/worktree commands are in the
[standalone repro](../../repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md).
The incident evidence and exact repair classification are recorded in
[the portability repair note](../../notes/2026-08-26-deepseek-v4-vllm-bundle-portability-repair.md).
The original report and maintainer response are preserved in
[issue #38](https://github.com/steveseguin/b70-optimization-lab/issues/38).

The `0001-xpu-add-guarded-K160-EAGLE-*` and
`0002-xpu-stabilize-EAGLE-*` files are later training experiments. Their
filenames and linked notes distinguish retained candidates from rejected
variants; they are not part of the 80.820052 record identity.
