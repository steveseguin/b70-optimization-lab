# Two-stage and four-stage F32 execution agree exactly

On October 25, the target-only engine produced the same 32 tokens on two and
four B70 cards. All **2,065 canonical state buffers** match in bytes, hashes,
types and shapes after the same 87-token prompt and 32 outputs. That includes
**121 persistent layer buffers**, 1,929 layer intermediates, first-stage PLE
history, replicated status, and the final head/output state. Both runs also
match the first 32 output IDs of the retained `297b388764e9` GPU baseline.

This establishes the new stage partition on this bounded request. It is not a
full-suite qualification, a four-card speculative result, or a resolution of
the independent CPU-reference disagreements.

The [summary](summary.json) binds the result and diagnostic timings. The complete
[comparison report](comparison.json.gz) records every compared source key,
metadata identity and exclusion. Its compression was round-trip verified;
the expanded hash is in the summary. Plans, launch records, state indexes,
state hashes, seals, process logs and final results are retained under
[pp2](pp2/) and [pp4](pp4/).

| Setup | Layer boundaries | Mean complete target step | Median complete target step |
|---|---|---:|---:|
| Two cards | 0 / 23 / 48 | 31.894 ms | 31.668 ms |
| Four cards | 0 / 13 / 25 / 37 / 48 | 39.707 ms | 39.651 ms |

These are 32 serial target-only steps, including the first output. Four stages
take **24.50% more time** in this diagnostic. There is no overlapping speculative
schedule here, and these are not first-99 inter-token rates or a certified
benchmark. Startup and JIT are included only in the separately labeled whole-run
wall time. Further four-card work must earn a gain through measured scheduling
and overlap; adding stages alone did not make this request faster.

## Identity and exactness scope

Both runs use binary
`51ebe749679333ba235e036e6dbe39d44ead4675a37ff42431a774a1e8574af8`,
the same model identity and F32 arithmetic, and terminate at input position 118.
All two PP2 and four PP4 rank processes exited with status zero; both controller
results report `passed=true`, no error, and no surviving child process.
The [post-PP4 host receipt](../host-after-pp4.json) records the final host check.

The comparator enforces contiguous stage ranges, unique absolute-layer
ownership, complete canonical buffer inventories, identical layouts, and sealed
raw payload hashes. It records rather than silently removes exclusions:

- intermediate boundary streams, whose layer endpoints intentionally differ;
- nonfinal output-token slots, which have no head writer;
- physical alternate banks explicitly declared inactive by the target-only
  engine with speculation disabled. Each must have a unique read/write
  `conv` or `gdn` producer in its actual plan. Canonical committed history and
  recurrent buffers always compare.

The initial comparator's inactive-bank registry named GDN state/history only.
Actual PP2 metadata exposed the existing `blk.1.ple.history` spare, produced by
`blk.1.ple.conv`. That legitimate temporal-bank category was registered with
the same producer check; no mismatching canonical state was omitted. Eleven
CPU tests pass, including refusal of speculative state, fabricated inactive
banks, missing persistent buffers, changed shapes, overlapping partitions and
corrupted payloads.

The historical service oracle was captured after MTP and lacks dtype/shape
metadata. This comparison uses matched target-only dumps instead of treating
either speculative bank's hash as an acceptable answer.

## Raw-state preservation and replay

The six raw state bundles total **860,665,704 bytes**. Their source paths,
byte counts and verified seal hashes are in [PP2 retention](pp2/retention.json)
and [PP4 retention](pp4/retention.json). They are now durably archived at
`/home/steve/own-xpu-runtime-results/review-2026-10-25/sc117-pp-proof-20261025.tar.gz`.
An independent streaming read verified all six archived raw members against
their retained engine seal hashes and sizes, and verified every byte of the
375,778,869-byte compressed archive against its recorded SHA256. The verifier
enumerated 229 archive entries and rejected duplicate names. The separate
durable source archive's compressed identity was also rechecked.

[Archive locations and hashes](../durable-archives.json) and the
[independent verification](archive-verification.json) retain those receipts.
This is durable local preservation, not a publicly downloadable release.
The summary's numeric identities were also checked against the actual plans,
results and token timing rows. Its initial prose-only PP4 boundary transcription
was corrected to **0 / 13 / 25 / 37 / 48**; the state-set manifests and strict
comparator always used the correct emitted ranges.

[retain_pipeline_proof.py](../retain_pipeline_proof.py) created these manifests
and copied metadata only after successful process closure. Re-run the comparator
while original bundles are present, or after restoring the archived state
directories to their recorded source paths using the member mappings in the
retention files:

```bash
python3 -B experiments/own-xpu-runtime/engine/tools/compare_pipeline_state.py \
  --reference experiments/own-xpu-runtime/research/review-2026-10-25/pp-proof/pp2/state-set.json \
  --candidate experiments/own-xpu-runtime/research/review-2026-10-25/pp-proof/pp4/state-set.json
```
