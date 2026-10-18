# Packet146 — within-request prompt lookup: policy closeout

<!-- campaign-closeout -->

## Question and identity

On October 18, 2026, can the two-card speculative pipeline use the current
request's prompt and already generated tokens as a second guess source for
headline results? The proposed lookup matches suffixes of length 2–6, resets
all lookup state between requests, and lets the unchanged target verify every
proposed token. No warm-up, cross-request state or benchmark-derived table is
allowed. The brief credits the idea to standard prompt-lookup / n-gram
speculative decoding literature; no external code was adopted.

Scope: the own-runtime Qwen3.8 Flash-Next UD-IQ3_XXS quantized compressed
version, two B70 cards, bundle8 reference of 58.798 tok/s and approximately
0.787 MTP acceptance supplied in the brief. These are context, not new
measurements. This review ran on `steve-b70s`, on main, starting at repository
commit `10aff58c871968c4750c56dbc3cf75862d0bf1f5`.

## Outcome

**Closed at policy gate: not headline-eligible under the current written
rules; the narrower within-request interpretation is at least ambiguous.**
Decision recorded at 2026-10-18 21:27:44 UTC, within the first ten minutes.
The brief explicitly requires stopping on either exclusion or ambiguity.

| Evidence | Meaning for this proposal |
| --- | --- |
| [AGENTS.md](../../../../AGENTS.md), lines 269–273 | Requires disabling “n-gram/history acceleration” and separately requires target verification of speculative tokens. It gives no within-request exception to the former. |
| [AGENTS.md](../../../../AGENTS.md), lines 284–301 | The cold-response explanation names repeated-prompt n-grams; performance and quality remain independent promotion gates. This narrower explanation does not expressly repeal the blanket requirement. |
| [LocalMaxxing rules](../../../../docs/localmaxxing.md), lines 107–113 | Again requires n-gram/history acceleration disabled, alongside unchanged target and verified speculation. Request isolation alone does not satisfy that written requirement. |
| [LocalMaxxing rules](../../../../docs/localmaxxing.md), lines 179–186 | `--allow-non-headline` is local dry-run only; the prohibition mentions prior generated continuation history and n-gram history without defining a request boundary. |
| [Submission helper](../../../../scripts/submit_localmaxxing_results.py), lines 177–196 | Rejects history markers and rejects n-gram markers unless `freshResponseNgramValidated` is truthy. That boolean suppresses one diagnostic; it does not define or authorize within-request lookup. |
| [Submission helper](../../../../scripts/submit_localmaxxing_results.py), lines 528–535 and 571–577 | Explicitly restricts `--allow-non-headline` to dry-run inspection and fails closed for a real submission using it. |
| [Optimization guide](../../../../docs/model-optimization-guide.md), lines 427–431 | The narrower warning concerns history that learned a repeated benchmark answer. The proposed mechanism avoids that particular problem, but this wording does not override the stricter submission rules. |
| [CURRENT.md](../../../../CURRENT.md), Known Issues And Next Actions, item 3 | Keeps record identity and quality gates binding. No packet146 or within-request lookup exception was found in the reviewed current-state policy. |

The favorable interpretation is technically meaningful: fresh per-request
lookup does not need a warmed answer, and exact target verification can
preserve greedy output. It is therefore not sound to call this proposal
cross-request caching or to claim it necessarily changes outputs. However,
neither property establishes permission under the blanket n-gram rule.
The flag and narrower explanatory text create ambiguity, not an authorization.
Changing labels, asserting the flag, or using the dry-run override would not
resolve it. No policy or submission tool was changed or executed.

## What worked

Source review separated two questions that must not be conflated: exact
target output and eligibility of the acceleration mechanism. It found the
validator's conditional exception as well as the stricter prose, rather than
inferring a blanket code rejection from the CLI help alone.

## What failed or remains uncertain

Headline eligibility was not established. This is a policy closeout, not an
empirical rejection of prompt lookup. No calibration or benchmark token
streams were opened for replay or tuning. Packet55 held-out text and packet138
capture streams were not used. No model run, implementation or design note
was produced.

| Requested acceptance result | Disposition |
| --- | --- |
| MTP wrong / lookup right, suffix lengths 2–6 | Not measured: policy gate stopped the study. |
| MTP right / lookup wrong | Not measured. |
| Best arbitration rule | Not selected or tuned. |
| Net acceptance change in percentage points | Unknown, not zero. |
| Packet135 projected tok/s | Not calculated: no admissible measured acceptance delta. |
| At least +1.5 points on held-out text | Not evaluated; does not admit a design note. |

## Evidence and patches

- [Policy source receipt](policy-evidence.json): exact working-file hashes,
  line-numbered excerpts and their Git HEAD blob identities. This preserves
  the decision's evidence if the shared documents later change.
- [Work note](../../../../notes/2026-10-18-own-runtime-packet146.md).
- [DO-NOT-REPEAT entry](DO-NOT-REPEAT.md), linking this closeout.
- [Packet135 context](../../../../notes/2026-10-18-own-runtime-packet135.md)
  and [packet144 closeout](../packet144-miss-path/CLOSEOUT.md) remain unchanged.

Only new packet146 documentation and its evidence receipt were written.
Existing packet trees, `stage2/screen/*`, `ops/*` and live queues were left
untouched. No runtime patch, benchmark payload, proposed GPU window, service,
sudo operation or setting change exists for this packet. No live state changed;
CURRENT.md remains with its current owners. The evidence/validation process
uses nice 19, CPUs 8–15/24–31, Python `-B`, stdin `/dev/null`, and a 4 GiB
address-space cap. No full-model reads or replays were needed.

## When to revisit

Only after an explicit policy revision or owner ruling covers request-local
prompt/generated-token lookup and reconciles the prose with the submission
validator. That would reopen the policy question, not establish a speed or
quality win. A subsequent authorized study would still need independent
held-out calibration, no benchmark tuning, the +1.5-point acceptance gate,
and all unchanged-target quality and performance gates. This packet requests
no ruling and queues no work; it closes this lever under the supplied brief.
