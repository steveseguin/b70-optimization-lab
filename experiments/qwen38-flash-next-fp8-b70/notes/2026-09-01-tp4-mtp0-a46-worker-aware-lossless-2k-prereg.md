# Qwen3.8 Flash-Next FP8 A46 worker-aware lossless-2K preregistration

Date: 2026-09-01
Status: frozen before GPU launch

A46 is a fresh attempt-46/port-19718 successor to A45. Model, official FP8
revision, source/runtime/kernel heads, TP4/EP4 MTP0, 2,304-token cap,
synchronous PLE-only placement, public oneCCL, size-1 full-decode graph,
compilation mode NONE, KV cache, prompts, 2K authorities, quality battery,
and supervisor teardown are unchanged. The only behavioral change is the
hash-bound A46 runtime verifier described in the A45 result.

The A46 verifier first requires exactly one nonempty rank trace log for each
rank 0–3. Only then may the Linux-truncated EngineCore or worker process name
omit the consumed selector; any declared value must equal the exact isolated
trace path. The inherited verifier still validates process ancestry, mapped
public oneCCL/kernel identities, graph selectors, allowed compile targets,
server receipts, runtime size-1 full dispatch after requests, and cache/trace
manifests.

Frozen hashes:

- verifier: `724528810e5316e1a32c013ecc6a2d0419f7063a7cedf6c5cb7d05d4ea672310`;
- verifier tests: `94d62fb3cec624d0d0a962d8f1efbf4bed351262b49423210ca601ff0a38b8cf`;
- rewriter: `189fd1c595be06c8545f5828d2a3c621f0bf24ddc019429b21a5c2a19387051a`;
- launcher: `31fdb1c92ffe29b5be03a5485340f13e556d2b0ba132c235b33ace3006af562c`;
- generated inner launcher: `6fc3f7b87c85138247be89e86eb1602d6911b98be022d3fa752a9e327bec1d4f`;
- client: `0b3e14850ca17b3b5c2148a3e300a4c83f91d45e14adb0f4a277df00e02aba41`;
- supervisor: `0621e67b4c8ff7f16302cfae3887c87e6bdb76a7b4f927ec09184336adaceb35`.

Promotion remains all-or-nothing: recovery, accepted semantics, 16-repeat,
three protected short hashes, two cache-zero exact 2K rows matching the eager
authority and one another, before/after runtime proof, and clean teardown. No
reboot or per-boot model-load rule applies.
