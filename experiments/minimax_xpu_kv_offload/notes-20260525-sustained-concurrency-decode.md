# 2026-05-25 Sustained C4/C8 Decode Rate

Goal: measure warmed sustained decode rate for concurrent session-cache shapes,
not just one-token or short fact-word correctness canaries.

These runs used `prompt-mode=checklist`, `max_tokens=128`, two passes, and the
second pass as the warmed RAM-reload measurement. The production endpoint was
restored afterward.

## Important Interpretation

The rate to compare is the warmed second pass:

- `wall tok/s`: total generated tokens divided by the slowest request elapsed
  time.
- `first-token-to-last-finish tok/s`: total generated tokens divided by the
  time from the first streamed token across the batch to the last finished
  request.

The second metric removes the first reload/TTFT moment but still includes
staggered scheduling. It is not the sum of per-request token rates.

## C4 At 4 x 9.2K

Result:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-c4-sustained-checklist-400lines-n128-20260525T213301Z.json`

Shape:

- c4, `--kv-offloading-size 32`
- `prompt-lines=400`
- prompt tokens per session: `9234`
- requested output: `128` tokens per session
- second-pass output: `512` total tokens

Warmed second pass:

| Metric | Value |
| --- | ---: |
| Wall elapsed | `4.665 s` |
| Wall output rate | `109.76 tok/s` |
| First-token-to-last-finish rate | `120.01 tok/s` |
| TTFT range | `0.398-3.051 s` |
| Per-request after-TTFT range | `51.29-79.34 tok/s` |

Rows:

| Label | Output tokens | Elapsed | TTFT | After-TTFT tok/s |
| --- | ---: | ---: | ---: | ---: |
| A | `128` | `2.895 s` | `0.399 s` | `51.29` |
| B | `128` | `2.894 s` | `0.399 s` | `51.29` |
| C | `128` | `2.894 s` | `0.398 s` | `51.29` |
| D | `128` | `4.665 s` | `3.051 s` | `79.34` |

## C8 At 8 x 9.2K

Result:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-c8-sustained-checklist-400lines-n128-20260525T213825Z.json`

Shape:

- c8, `--kv-offloading-size 64`
- `prompt-lines=400`
- prompt tokens per session: `9234`
- requested output: `128` tokens per session
- second-pass output: `952` total tokens

Warmed second pass:

| Metric | Value |
| --- | ---: |
| Wall elapsed | `8.628 s` |
| Wall output rate | `110.34 tok/s` |
| First-token-to-last-finish rate | `112.71 tok/s` |
| TTFT range | `0.181-6.786 s` |
| Per-request after-TTFT range | `37.54-69.51 tok/s` |

Rows:

| Label | Output tokens | Elapsed | TTFT | After-TTFT tok/s |
| --- | ---: | ---: | ---: | ---: |
| A | `128` | `3.331 s` | `0.181 s` | `40.63` |
| B | `127` | `3.415 s` | `0.906 s` | `50.61` |
| C | `128` | `6.886 s` | `4.046 s` | `45.07` |
| D | `78` | `5.600 s` | `3.522 s` | `37.54` |
| E | `128` | `3.521 s` | `0.904 s` | `48.90` |
| F | `118` | `6.591 s` | `4.146 s` | `48.26` |
| G | `117` | `7.920 s` | `5.798 s` | `55.14` |
| H | `128` | `8.628 s` | `6.786 s` | `69.51` |

Some c8 requests stopped before `128` tokens, so the wall rate uses the actual
`952` generated tokens, not the requested `1024`.

## Larger Context Sustained Decode Attempts

The earlier correctness canaries passed at larger contexts, but sustained
`n128` decode hit scheduler stalls:

- c4 at four `22459`-token checklist prompts stalled after one request
  completed.
- c4 at four `16134`-token checklist prompts also stalled after one request
  completed.

Observed pattern: the server kept one or more requests running/waiting with no
progress and reported shared-memory broadcast wait messages. Restarting the
server was required to clear the orphaned work. Treat this as an experimental
session-cache scheduler limit, not a model throughput result.

## Takeaway

At the stable `9234`-token prompt size, c4 and c8 both deliver about
`110 tok/s` total warmed wall output. c8 does not double total throughput; it
spreads similar total decode bandwidth across more active sessions and suffers
more staggered TTFT/reload scheduling.

The next useful optimization target is not raw decode math. It is scheduler/KV
block behavior under larger sustained contexts, because correctness canaries can
pass at larger contexts while sustained `n128` decode still stalls.
