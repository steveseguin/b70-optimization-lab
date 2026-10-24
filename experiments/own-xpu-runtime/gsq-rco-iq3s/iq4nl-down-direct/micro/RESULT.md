# IQ4_NL direct-global: exact, slower, rejected

The single fixed layer0 down-projection comparison passed all28 full output/status
pairs, including4 preregistered warmups. All24 measured pairs are retained, balanced
12 AB/12 BA. The candidate averaged198.811 microseconds versus118.442 for the
original staged kernel: **1.67855 times the latency**. Both order groups agree.
This candidate is rejected; no full-engine integration or repeat is planned.

| Order | Pairs | Original (microseconds) | Candidate (microseconds) | Candidate/original |
| --- | ---: | ---: | ---: | ---: |
| AB | 12 | 118.429 | 198.932 | 1.67976 |
| BA | 12 | 118.455 | 198.689 | 1.67734 |
| All measured | 24 | 118.442 | 198.811 | 1.67855 |

These are isolated repeated kernel event times for one captured real input and
its ten expert routes. They are not full-model throughput or a cold-workload
claim. Native comparisons checked every51,200 output bytes and40 status bytes;
successful output blobs were not separately retained, but all comparison hashes
and timing rows are preserved. All values remain relative to this quantized model.

The independently reviewed [closed auditor](operating/audit.py) passed actual
readback: [review](evidence/device-a/review.json)
`f3781981d87bd1ad68a91c83780df5ce8d11e3243b1d560c8ff0844b5087a653`.
It indexed509 artifacts, verified binary/source/fixture identities and joined the
actual backend PID/startticks to its physical target descriptor and nonce ACK.
All56 kernel submissions completed; the owner exited safely with zero live bytes
and no in-flight work. Target descriptors drained, protected vision and kernel
fault baseline were unchanged. The coordinator completed in3.243seconds.

The ACK mechanism now has actual qualification: an accepted complete passive
sample was durably recorded before permitting kernel work. It does not repair
the earlier IQ3 micro's unobserved physical contact; that failed qualification
remains recorded separately.

The native binary is
`dcd67040535733a8271191d6fe6feccee4e14eff30f8c13d76e52fd0db9fda5b`,
[build](evidence/native-build.json)
`d1c5e5d02b674c7b2531559b721e35a7fa1322dcb21970e4b86840f239abb95e`;
[plan](evidence/device-a/plan.json)
`46b7823b6f3ce76534f3ab5ce6916a68c19a73c509c6d4bc0f5aecb36d728ca7`.
The bounded extraction retained9,280,160 bytes of fixtures/expert slices outside
Git, with hashes and exact offsets in [its receipt](evidence/extraction.json).
It authenticated the fixed original archive and model header/span; no full-bank
payload hash is claimed. The first extractor's metadata-schema refusal and exact
pre-fix source are preserved under `lineage/` and
[evidence](evidence/extraction-authority-refusal.json).

The qualified [IQ3-block engine](../../expert-iq3xxs-block/engine/operating/RESULT.md)
remains the retained engine. The next candidate extends its existing exact Q6 p33
kernel to19 additional dense sites; this loss does not justify changing precision,
arithmetic order, verification or model quality.
