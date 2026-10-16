# Proposed wording fixes after the prefix-cache hand-over defect (2026-10-16, for the owner)

> **Proposal only, not applied.** Public pages change only with the owner's yes. Background:
> `2026-10-16-pc-handover-impact-audit.md` (what is touched) and `2026-10-04-fp8-multiuser-prereg.md`, addenda of
> 2026-10-16 (the defect, the 0.5.0 fix, parts A-D).

What the evidence supports now: the 99/99 test and every published exactness check ran **one request at a time**,
and that case was exact (also re-shown today: 0.1-0.2 ms gaps, 98 hits, 64/64 twice). Requests **waiting in the
queue** behind another one could start from a wrong saved state on the unfixed server (40/64 equal back to back);
with overlay `b70-spec-resume-accepted` 0.5.0 they are exact (256/256 over four orders, part B). No published score is
known to be affected: the logs show almost no queued requests in those runs.

## skindeep.ai

| Page, line | Now | Proposed |
| --- | --- | --- |
| `context-reuse.html:163` | "Everything it reuses is exactly what a fresh read computes, so a cached answer is identical to an uncached one." | "Everything it reuses is exactly what a fresh read computes, so a cached answer is identical to an uncached one. (Tested one request at a time. Requests that wait in a queue needed one more fix, added on 16 October; with it, 256 of 256 answers matched.)" |
| `context-reuse.html:184` | "Exactness: 99 of 99 cases gave identical output tokens with drafting on, including edits and later turns." | add: "All 99 were sent one at a time." |
| `context-prefix-cache.html:25` | "The matching cache test produced the same output tokens in 99/99 cases." | "The matching cache test, one request at a time, produced the same output tokens in 99/99 cases." |
| `context-cache.html:28` | "The exact-cache test returned the same output tokens in 99/99 cases, including repeat questions, edits and later turns." | "... in 99/99 cases sent one at a time, including repeat questions, edits and later turns." |
| `context-cache.html:31` | "... Matching output tokens is narrower than a scores-level or every-input guarantee." | add: "With drafting on and requests waiting in a queue, an older server copy could start from the wrong saved state; the 16 October fix (overlay b70-spec-resume-accepted 0.5.0) made 256 of 256 queued answers match." |
| `context-results.html:80` | "With drafting on, the matched cache experiment produced identical output token sequences in 99/99 cases ..." | "With drafting on and one request at a time, the matched cache experiment ..." (the L84 limit stays) |
| `context-reproduce.html:38` | "Add-on: b70-prefix-cache-exact." | "Add-ons: b70-prefix-cache-exact, and b70-spec-resume-accepted 0.5.0 or later (needed with drafting whenever a request can wait in the queue)." |
| `docs/claims.md:84`, `docs/context-prefix-cache.md:7`, `results/long-context/result.json:184` | 99/99 | same "one at a time" limit; `result.json` gets `"requests": "one at a time"` beside `users_tested`. |

The search copies (`content/pages.json`, `content/context-*.html`, `content/search-answers.json`, `search/answers.json`)
follow the pages.

## ctxkeeper README (`tools/ctxkeeper/README.md:225-226`)

Now: "(Our first try with MTP returned corrupted replies; that was a bug in our vLLM build with prefix caching, since
fixed there, not in ctxkeeper.)"

Proposed: "(Our first try with MTP returned corrupted replies. That was a vLLM bug with prefix caching and
speculative decoding, not a ctxkeeper bug; our server overlay fixes it. A related one, found on 16 October, could
change an answer when a request waited in the server's queue; ctxkeeper's default settings never queue a request,
and the overlay fixes that too.)"

## neural.download

No change needed: the #long-tasks rows are task scores and make no exactness claim; the packages run with the cache
off.
