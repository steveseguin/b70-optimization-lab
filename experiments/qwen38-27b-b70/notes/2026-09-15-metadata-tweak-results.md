# MTP metadata tweak: exact, but no measurable speed gain

Tested on September 15, 2026 on the two-B70 host, newest-base image
`sha256:506fcc26…` (upstream vLLM `dc36fcce9`), official Qwen3.8 27B FP8 with
native MTP1, one user, prompt caching off. The tweak moves one unused GPU
subtraction in the GDN attention metadata builder into the branch that uses it
([candidate and gates](../probes/mtp-metadata-20260914/README.md)).

**Result: every answer stayed exactly the same, and speed did not change beyond
normal run-to-run wobble. The tweak stays off by default.**

## What passed

- The unchanged newest base matched all 12 complete reference answers from the
  qualified R304 service (first time this base loaded on this host; it needed the
  five qualified environment variables, see the
  [OOM incident note](2026-09-15-research-load-host-oom.md)).
- The low-level check passed all 36 metadata cases on both GPUs.
- Four alternating rounds (normal, tweak, normal, tweak) each passed the full
  12-question test and 18 long-prompt continuations with exactly the reference
  outputs and zero cached tokens. Both GPUs ran the selected path 15,594 times per
  round and never the other path.

## Speeds

Writing speed is the class-balanced median over tokens 1-100 of the 12-question
test. Reading speed is server prefill in input tokens per second.

| Round | Writing, tok/s | Reading 512, tok/s | Reading 2,048, tok/s | Reading 16,384, tok/s | First-token wait 16,384, s |
| --- | ---: | ---: | ---: | ---: | ---: |
| normal 1 | 54.245 | 2,855.5 | 3,667.7 | 3,293.2 | 4.988 |
| tweak 1 | 54.392 | 2,866.2 | 3,662.8 | 3,291.1 | 4.990 |
| normal 2 | 54.450 | 2,869.2 | 3,668.8 | 3,291.8 | 4.987 |
| tweak 2 | 54.543 | 2,869.6 | 3,668.3 | 3,292.9 | 4.985 |

The two normal rounds differ from each other by 0.38% in writing speed, more
than the tweak's 0.17-0.27% difference from its neighbours, and reading speeds
drift up across rounds regardless of mode. This is one server process, so it is
a screen, not a promotion; there is no speed claim to confirm.

## Also fixed along the way

- The first campaign attempt stopped after the base check because the native
  gate returned a PyTorch version object that the newer vLLM cannot serialize;
  the extension now returns plain JSON.
- The research launcher now adds the five qualified variables and starts a
  root host-memory guard. Peak driver-held host memory during these loads was
  1.7 GiB, well under the guard limit.

Evidence: `/mnt/fast-ai/bench-results/optimization-validation-20260915/client-campaign-02`
and [summary copy](../data/2026-09-15-metadata-tweak-screen/summary.json).
