# Qwen3.8 TP2 speculative graph-replay-bypass result

Date: 2026-08-20

Classification: **bounded positive for the combined treatment; diagnostic-only**

Preregistration:
[`2026-08-20-detpad-tp2-graph-replay-bypass-prereg.md`](2026-08-20-detpad-tp2-graph-replay-bypass-prereg.md)

Structured result:
[`2026-08-20-int4-detpad-tp2-graph-replay-bypass-result.json`](../data/2026-08-20-int4-detpad-tp2-graph-replay-bypass-result.json)

## Result

R1 and R2 both completed with runner status 0, passed the sealed arm checker,
and matched on all **25/25 complete token arrays**. R1 passed the frozen quality
baseline; R2 skipped quality as preregistered and used immutable R1 as its
mandatory all-25 parity peer. The R2 parity report passed with no differences.

This meets the preregistered positive criterion for one ordered pair under the
combined treatment. It does not establish general TP2 determinism:

- both arms matched target oracle A on only **18/25**, with mismatches at prompt
  indexes `2, 10, 12, 16, 19, 20, 22`;
- both matched the sane B2 reference on **22/25**, with mismatches at `6, 11,
  24`; and
- prompt 24 matched S1 and target A exactly, with 512 nonzero-containing token
  IDs, token-array SHA-256
  `b1ad815bceff49895fedb75552c6f7d8a4650a965f818aeb4c20fb3685c8f20b`,
  and output SHA-256
  `471a54e871126200a286dedbc80c6c689ce83093be06e7350b551a512cf364dd`.

The pair therefore avoided the known 512-zero prompt-24 catastrophe and
replicated one sane existing family. Exact R1/R2 agreement does not make that
full 25-prompt result target-exact or prove that the untreated lane could not
have repeated it.

## Identity, cache, and engagement

Both sealed arm reports recorded status `passed`, no errors, and the same
frozen identity:

- repository HEAD `973eddffbcffd4bdc5ccfe0d7dddf29136a40310`;
- model manifest SHA-256
  `731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8`,
  with all 19 files verified through ordinary cached and O_DIRECT views before
  load;
- TP2 on physical GPUs 2,3, engine seed 0, request seed 1, FP16, AutoRound
  INT4, MTP5, target INT8 head, draft INT4 head, and both fallback margins 0;
- composite graph-stage manifest SHA-256
  `47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da`,
  native extension SHA-256 `4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0`,
  and graph-safe FA SHA-256
  `33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739`;
- sealed outer namespace `b99160ae76`, canonical cache manifest SHA-256
  `f3582440de9b252cc738648aa5b690fd324bec9afeb8d89e4b73d295071cb0ff`,
  tree SHA-256 `723c1599060f5c9c82dc5731cc75b50620c79d202b34ee99b8390d3aec20acbe`,
  3,795 entries, 3,246 files, and 395,855,113 bytes; and
- exactly two outer and four AOT direct loads, no compile/save negatives,
  byte-identical input/output cache manifests, and zero cache-byte delta.

The effective and independently expected replay-bypass flags were both 1.
Each arm contained exactly one Worker_TP0-local/rank-0 target-verifier skip
marker, one Worker_TP0-local/rank-0 drafter graph-key-disable marker, and one
Worker_TP0-local/rank-0 graph-capture-finished event. The only remaining
capture inventory was mixed prefill-decode PIECEWISE, completed 1/1. Each arm
also had exactly one CUDAGraph-metrics-disabled marker, exactly two INT4 pad
markers across ranks 0 and 1, and no checker negative lines.

Speculative decoding remained active: R1 recorded 29 metrics rows totaling
18,380 drafted and 9,158 accepted tokens; R2 recorded 23 rows totaling 17,425
drafted and 8,417 accepted tokens. These startup/source markers prove the
configured topology selection, not per-call replay counts.

The frozen native-GDN main comparison SHA-256
`61b9f0031e153d4841b139263d8a7afbef6004b8a8da3491affcf8688c329d1d`
was a mandatory prerequisite. It remains a separate raw-op bounded negative,
not evidence that the integrated runtime is stable.

## Performance is descriptive only

Preferred medians were `56.1584169814` and `56.5677528324 tok/s`; their
two-arm central value was `56.3630849069 tok/s`. Legacy-inclusive medians were
`56.7256737186` and `57.1391442751 tok/s`, central value
`56.9324089969 tok/s`.

The preferred central value is **44.263% below** B2's
`101.1236430227 tok/s`. This is not a performance A/B: the treatment changes
target-verifier replay selection, drafter graph selection and M6-to-M1
geometry, and startup graph memory/allocation history. These measurements are
not promotable and must not be submitted as a record.

## Interpretation and decision

Within this one preregistered ordered pair, R1 and R2 replicated exactly under
the sealed identity with full-width speculative target-verifier replay and
drafter graph keys disabled. This is a bounded positive only for the combined
verifier-replay plus drafter-graph/geometry plus startup-allocation treatment.

It does **not** localize target replay, drafter replay, drafter M1 geometry, or
startup allocation history; establish target exactness; prove lane-wide
determinism; or provide a safe performance candidate. Ordinary one-token target
decode remained graph-eligible, and the treated speculative paths still used
compiled non-cudagraph runnables rather than an eager model path.

The preregistered campaign is complete. Preserve R1 and R2 by the checksum
manifests below, run no further arm under this preregistration, and do not
resume throughput optimization from this treatment.

## External artifacts

| Arm | Artifact root | Checksum manifest SHA-256 | Bench SHA-256 | Sealed gate SHA-256 |
| --- | --- | --- | --- | --- |
| R1 | `/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-detpad-composite4dd-marginfree-mtp5-25-graph-replay-bypass-r1-20260820` | `e69d5181ecf6228503243ec6e96949ac701d4bdb0204900b8f3cbbb56117981e` | `857f50218528f984e1e1e78e7ded7564f5500940d315d145724b5790fe7813fa` | `41c2d264aa0330a5701ac885d533009333639572c2df4ef14a52c337ba004748` |
| R2 | `/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/qwen38-detpad-composite4dd-marginfree-mtp5-25-graph-replay-bypass-r2-20260820` | `e167381b80c00f7f5de0c177e85ea4d20e7eb1d7ad544e06a5000ce501b9a526` | `ace48af9e567fc6b55c973e517492b87dc8ca823542b0ba2a5d582f872c814ab` | `1557505bfdee3318ba8072c7a9fcff9191ff94613e2a830e7f37a871e706f497` |

R2 token-parity report SHA-256:
`fd6b3da6eb7d3929af207e5aa48a55db3fb65ea96a1d739d6489e0d7b45aa332`.
Both enclosing checksum manifests were independently reverified before this
packet was written. The compact structured result records the references and
derived comparisons; the large raw benchmark artifacts remain at the frozen
external roots.
