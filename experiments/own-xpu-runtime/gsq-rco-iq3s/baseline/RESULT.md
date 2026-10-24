# Resident SC117 target/MTP baseline — October 24, 2026

All twelve original prompt pairs pass exact output tokens and complete target-state comparison. On this one resident run, interval-weighted decode is **12.6346 tokens/s target-only and 17.9772 tokens/s with MTP**, a **42.29% increase**. MTP accepts 1,160 of 1,524 proposals (76.12%) and rejects 364. Rejected-proposal work is included in elapsed decode time. All twelve prompts reach their 128-token cap; no short or EOS cases were discarded, and this run does not exercise early EOS.

The [independent audit](evidence/independent-a/review.json) rehashed 57,675 files totaling 6,338,112,625 bytes, recomputed the timestamps and aggregates, and verified all 26 requests including the two excluded warmups. Its [compressed artifact index](evidence/independent-a/artifact-index.jsonl.gz) binds retained raw artifacts. All 1,536 emitted tokens per mode and every per-prompt full target-state map match. This establishes target/MTP equivalence within this engine and quantization; it is not an independent full-forward quality oracle.

| Metric | Target-only | MTP |
| --- | ---: | ---: |
| Interval-weighted decode tokens/s | 12.6346 | 17.9772 |
| Median per-prompt decode tokens/s | 12.7372 | 17.9529 |
| Total decode intervals | 1,524 | 1,524 |
| Total decode time, seconds | 120.6211 | 84.7741 |
| Mean prompt plus first-token time, seconds | 2.9164 | 3.0307 |

Decode uses N−1 completion intervals after the first output token. Prompt/first-token time is reported separately; initialization, RESET, state dumps and independent hashing are outside these request timing metrics. MTP does not improve every timing component.

| Order group (six prompts each) | Target-only tokens/s | MTP tokens/s |
| --- | ---: | ---: |
| Target-only first | 12.0995 | 19.0584 |
| MTP first | 13.2192 | 17.0121 |

Both groups favor MTP, but their different prompt classes prevent treating the difference between groups as a pure causal order effect. First-use, cache and ordering effects remain visible. No comparison with the old Unsloth target or prior leaderboard record is valid.

| Original prompt | First arm | Output tokens per arm | Target-only tokens/s | MTP tokens/s | Accepted proposals |
| --- | --- | ---: | ---: | ---: | ---: |
| incident-retrospective | none | 128 | 11.922 | 19.272 | 98/127 |
| code-review | mtp | 128 | 13.216 | 16.230 | 92/127 |
| customer-email | none | 128 | 12.026 | 18.191 | 89/127 |
| sql-debugging | mtp | 128 | 13.200 | 17.021 | 99/127 |
| release-plan | none | 128 | 12.050 | 17.766 | 86/127 |
| benchmark-analysis | mtp | 128 | 13.221 | 17.454 | 104/127 |
| architecture-tradeoff | none | 128 | 12.228 | 20.920 | 109/127 |
| bug-report-synthesis | mtp | 128 | 13.206 | 16.124 | 89/127 |
| technical-guide | none | 128 | 12.104 | 19.443 | 99/127 |
| risk-register | mtp | 128 | 13.220 | 18.139 | 102/127 |
| performance-hypotheses | none | 128 | 12.274 | 19.070 | 96/127 |
| decision-memo | mtp | 128 | 13.252 | 17.276 | 97/127 |

The fixed [manifest](manifest.json) includes all original prompts, two disjoint warmups, alternate arm order, context 4,096, full BF16 KV, unchanged target quantization and full-vocabulary draft. Each request starts with complete RESET; no prompt/KV/output state is reused. Both ranks stay loaded for the entire suite. Binary SHA256 is `16ce5bbda43e9d3d39c2446fc3037ea352d345f62161453f1ab0539330046ea2`; target revision is `eec4e10a2c29b440a2ae85591fa11569ce752963`. Split is 24/24, draft rank 0, BDF23/47, low-priority coordinator and unchanged pinned execution environment. The [plan and terminal receipts](evidence/run-a/terminal.json) retain complete identity.

Owners 3581837 and 3581845 exited with zero in-flight work, live bytes, signals or retained PIDs. Logical device allocations exactly match 30,716,803,978 and 29,672,451,988 bytes. Retained physical inventory shows both target cards drained, the vision application unchanged, and no new driver fault. There were no retries, resets, service changes or host-setting changes during the run. Elapsed orchestration was 551.073 seconds.

Raw evidence remains at `/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a`; control receipts remain at `/home/steve/own-xpu-runtime-results/gsq-baseline-a.control`. The successful binary and all baseline source inputs stay frozen as the control. Next is a [short class diagnostic](../profiling/README.md), followed by one measured, lossless optimization candidate. These results cover short prompts and cap128 in one resident run, not cold-start, long-context or broad semantic quality.

The 2.31 MB compressed index is retained research evidence: it contains paths, byte counts and SHA256 values, not model or state payloads. Future reviewers can use it to check the external raw evidence without trusting the summary. Keep it with this result and the raw run; the deterministic gzip index can be reconstructed by the file enumeration/hash logic in `audit.py` against the unchanged external roots. Its expected SHA256 is bound by the independent review.

A [literal decode of all twelve outputs](evidence/decoded-output.json) is retained for inspection using the pinned codec and matching tokenizer metadata. The capped text is readable and responds to the prompt topics, but some outputs introduce example dates/identifiers not supplied in their prompts. No semantic quality score is assigned; all are truncated at128 tokens. Candidate equality must preserve this baseline rather than silently alter responses.
