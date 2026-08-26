# DeepSeek V4 vLLM bundle portability repair

Status: **repair prepared and verified; historical archive preserved; exact
public recovery tags verified**.

This incident affects source portability, not the measured DeepSeek V4 Flash
performance or quality evidence. The original vLLM record bundle is a valid
thin archive when its prerequisite
`61c87db645c256651b5a366f538898485077ad32` is already present, but it is not
a self-contained restoration artifact. At audit time that prerequisite was not
public; it was subsequently published under an exact recovery tag.

## Audit evidence

- historical bundle SHA-256:
  `cebc81bedc22496dc82836b9419428e0377a3eb4e7ac213014a7306c7b30e825`;
- historical bundle size: `110741` bytes;
- advertised tip:
  `264c7f2f7df21ddeeab32ecca0353133344f1ac9`;
- header prerequisite:
  `61c87db645c256651b5a366f538898485077ad32`;
- empty-repository `git bundle verify` and `git bundle unbundle`: rejected
  because the prerequisite is absent;
- direct empty-object-store `git index-pack --fix-thin`: rejected with
  `443 unresolved deltas`;
- at audit time, the prerequisite and record commit were found together only in the scanned
  `/home/steve/src/vllm/.git` object store;
- no remote-tracking ref then contained `61c87d...`; it was a local
  experimental commit, not the public base described by the old table.

After the report, exact lightweight recovery tags were published on
`steveseguin/vllm`:

- base: [`deepseek-v4-k160-vllm-base-20260714`](https://github.com/steveseguin/vllm/releases/tag/deepseek-v4-k160-vllm-base-20260714)
  -> `61c87db645c256651b5a366f538898485077ad32`;
- record: [`deepseek-v4-k160-vllm-record-20260718`](https://github.com/steveseguin/vllm/releases/tag/deepseek-v4-k160-vllm-record-20260718)
  -> `264c7f2f7df21ddeeab32ecca0353133344f1ac9`.

The maintainer response and immediate historical-bundle recovery commands are
in [issue #38](https://github.com/steveseguin/b70-optimization-lab/issues/38).
This remediation makes the preserved thin archive recoverable, but does not
retroactively make it self-contained or erase the original packaging defect.

The adjacent review patch still has value: applied to `61c87d...`, it
produces exact record tree
`98d21ed3a502a04eb8d9c57f185a7486c15286c1`. It cannot supply the missing
private base by itself.

## Additive repair

The corrected archive is
`patches/deepseek-v4-flash-reap-xpu-b70/vllm-deepseek-v4-k160-dspark7-80tps-record-20260718-public-anchor.bundle`.
It is intentionally thin against genuinely upstream commit
`382bbd51448b2f58c73b3e51d051bc352166ba91`, which is reachable from the
declared official vLLM `origin/main` remote-tracking ref. It includes the 23
commits from that public anchor through the old private base and all 98 later
commits through the record.

- corrected bundle SHA-256:
  `bdb02267d5a128665fa46ca0119e218df8596a43ccbbe41767d5543acc9a7096`;
- corrected bundle size: `152050` bytes;
- restored commit:
  `264c7f2f7df21ddeeab32ecca0353133344f1ac9`;
- restored tree:
  `98d21ed3a502a04eb8d9c57f185a7486c15286c1`;
- provenance manifest:
  `patches/deepseek-v4-flash-reap-xpu-b70/vllm-deepseek-v4-k160-dspark7-80tps-record-20260718-public-anchor.provenance.json`.

The restore proof used a brand-new disposable bare repository. It fetched only
the exact public prerequisite at depth one, proved the record tip was
absent, verified and fetched the corrected bundle, matched the exact commit and
tree, and passed Git connectivity checking. A separate empty repository fetched
the exact base and record tags directly from the public fork and verified both
commit and tree identities. The corrected bundle remains preferred because its
only prerequisite is an official upstream commit, independent of the
incident-specific fork tags.

## Permanent gate

`tools/validate-git-bundle-provenance.py` now recognizes only two acceptable
contracts:

1. zero-prerequisite bundles that restore in a brand-new empty repository; or
2. thin bundles whose complete prerequisite set is declared and proven
   reachable from an explicit public remote-tracking ref.

In both cases it performs a disposable exact restore. Focused synthetic tests
cover a valid public-anchor restore, a valid self-contained restore, undeclared
thinness, a private prerequisite mislabeled as public, a mismatched remote, and
the byte-identical historical/corrected DeepSeek headers. Optional declared
recovery refs are checked with `git ls-remote`, fetched by exact ref into a
second empty repository, and matched by commit and tree; a wrong advertised
commit is rejected.

This repair is deliberately scoped to the vLLM archive. It does not silently
reclassify the separate XPU-kernel or oneCCL bundles, local model/draft weights,
compiled runtime, or raw benchmark evidence as self-contained.
