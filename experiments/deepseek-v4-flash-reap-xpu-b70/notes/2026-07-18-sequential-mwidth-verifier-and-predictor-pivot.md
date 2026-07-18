# Sequential M=4/M=8 Verifier Gate and Predictor Pivot

Date: **2026-07-18**

Status: **fixed verifier promoted to guarded infrastructure; repeated-MTP
predictor rejected**

## Result

The fixed M=4 and M=8 MHC kernels now pass genuine sequential target-verifier
data, not only duplicated M=2 rows. Each corpus contains the complete target
component geometry on all four B70s: 87 reductions, 85 linked MHC boundaries,
consecutive token positions, one verifier-forward record, and one logits
record. All target token IDs and logits agree across ranks.

With the known-safe segmented M=2 collectives retained:

| Width | Segmented M2 MHC | Fixed-width MHC | Saving |
| --- | ---: | ---: | ---: |
| M=4 | 6.948199 ms | 5.506829 ms | 1.441370 ms (20.74%) |
| M=8 | 12.357660 ms | 8.043340 ms | 4.314321 ms (34.91%) |

Both candidates pass 16 changed eager schedules and 70 fixed-address graph
replays with zero mismatches on every card. The traceable vLLM wrapper also
proves that compiled M=4/M=8 execution contains the segmented custom operation
and never emits the corrupt wide collective.

Primary evidence is indexed in
`../data/mwidth-sequential-verifier-20260718.json`.

## Why this matters

The earlier row-tiled gate established kernel economics but could not prove
that independent verifier rows, changing positions, recurrent storage aliases,
and real target outputs were safe. These captures close that gap. Fixed M=4
and M=8 target verification is now a reusable exact primitive for a real
multi-position predictor.

## Endpoint screen and rejection

The checkpoint-attached one-layer MTP was then repeated three times to generate
an M=4 verifier cycle. The compiled endpoint loaded and captured successfully,
but the cold unpredictable workload exposed the predictor limit:

- mean accepted length stayed between 1.81 and 2.17 tokens;
- second-draft acceptance was 5.0-22.6%;
- third-draft acceptance was 0.0-3.2%;
- eight eligible cold rows measured only 46.247281 tok/s median, versus the
  qualified MTP1 record at 63.851301 tok/s.

The suite itself is classified incomplete because two prompts ended before the
100-token timing window. That does not rescue the candidate: the eight valid
timing rows and request-scoped acceptance counters independently show that the
extra two serial draft passes cost more than they save. An M=8 endpoint run is
therefore rejected before launch; proposals four through seven cannot help
when proposal three is almost never accepted.

## Next action

Use the official `deepseek-ai/DeepSeek-V4-Flash-DSpark` predictor. It has three
trained draft stages, a Markov head, block size five, and target features from
layers 40-42. The 4,705 `mtp.*` tensors occupy only shards 46-48 (about 10.9
GB), so a draft-only pack can be used beside K160 without downloading or
loading the full official target. The XPU port must first pass eager output,
target-verification, memory, and frozen held-out gates; only then enable graph
capture and report endpoint throughput.
