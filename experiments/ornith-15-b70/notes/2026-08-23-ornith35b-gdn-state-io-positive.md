# Ornith 1.5 35B-A3B: in-place GDN state I/O

Date: 2026-08-23 EDT

Status: **accepted as the tenth target-only optimization**

## Why this Qwen transfer was tested

Ornith 1.5 retains Qwen-derived Gated Delta Net structure. Our earlier Qwen
lane showed that its one-token recurrent path needlessly gathered persistent
state into a temporary before GDN, then copied the updated state back. The
accepted Ornith stack already fused the output copy into GDN, leaving the
input `GET_ROWS` launch as the missing half of that transfer.

The new default-off `GGML_SYCL_FUSED_ORNITH_GDN_STATE_IO=1` path reads the
persistent state directly and writes its update back in place. Each workgroup
owns one state column and loads that column fully before writing, so no
workgroup reads data written by another. The matcher fails closed unless it
finds Ornith's exact one-row FP32 state, the exact 128x32 GDN value shape,
K=1, identical persistent input/output storage, non-overlap with the GDN
activation output, and no other compute consumer of the gathered temporary.

This removes one `GET_ROWS` launch in each of 30 recurrent layers. The
complete ten-feature stack removes 660 launches per decoded token.

## Matched performance

All runs used one B70, graph off, F16 KV, the same final candidate binary, and
the preceding nine-feature stack in both arms.

| Protocol | Controls | Candidates | Mean change |
| --- | --- | --- | ---: |
| `llama-bench p0/n128/d0/r7`, A/B/B/A | `122.181649`, `121.967034` | `130.451175`, `129.288972` | **+6.39%** |
| fresh 12-prompt server suite, A/B/B/A | `118.397776`, `117.897718` | `126.362074`, `125.996811` | **+6.80%** |

Both candidate runs exceeded both controls in both protocols. Every server
process used 12 unique prompts once, reported `cached_tokens=0` on every row,
and passed the tokens 1-100 and final-response gates. The promoted serving
number is the directly measured candidate mean, **126.179443 tok/s**; it is
not obtained by applying 6.80% to any older result.

Candidate engine runs recorded 26,910 hits each and candidate server runs
recorded 183,960 hits each, confirming that the timed path executed throughout
both arms.

## Correctness and determinism scope

- Same-final-binary forced 128-token control and candidate transcripts were
  byte-identical and both hashed to
  `d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.
- The candidate recorded exactly 3,810 hits: 30 recurrent layers across 127
  decoded graph evaluations.
- The short 8x repeat, arithmetic, exact-copy, and JSON-schema canaries passed.
- The added realistic same-process repeated-prompt probe produced four hashes
  across eight fixed-seed requests, with one hash appearing five times. This
  is consistent with the already documented stock-runtime prose variability.
  It is disclosed rather than mislabeled as candidate determinism; candidate
  exactness uses the same-frozen-binary on/off test and activation counts.
- The complete patch applies cleanly to pinned llama.cpp base
  `9fee29e9435f865ec0b811a783a6471a136d9317` and passes `git diff --check`.

## Artifacts

The incremental patch is
`../patches/llamacpp-ornith15-gdn-state-io-positive-20260823.patch`. The
package's complete ten-feature patch is
`../../../patches/ornith-15-35b-a3b-q4km-b70/llama-cpp-ornith15-ten-feature-stack-gdn-state-io-20260823.patch`.
Structured summary, exactness record, raw engine/server rows, canaries, logs,
and realistic repeat records are under
`../data/2026-08-23-ornith35b-gdn-state-io-*`.
