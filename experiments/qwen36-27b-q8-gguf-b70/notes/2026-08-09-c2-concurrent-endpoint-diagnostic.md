# c2 forced-tail column divergence

Date: 2026-08-09

## Outcome

F16-KV c2/32K fits, and the synchronized forced streams contain the complete
correct answer prefixes, but the strict cross-mode full-512 gate is blocked.
The apparent missing timestamp was not a transport problem: one synchronized
M=2 stream generated a different post-EOS continuation from its later M=1
replay. Reversing the prompts moved the divergence to the other prompt while it
stayed on slot 1, localizing it to the second batch column or a column-sensitive
M=2 numerical path. Later natural-stop probes passed, but those probes were
sequential; a synchronized `ignore_eos=false` pair remains unmeasured.

Initial endpoint-only failure packet:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-formal-c2-gpu0-short-fixed-20260809T165506.933484829Z`

The packet sealed `FAIL`. Both fresh servers fully offloaded `65/65` layers,
passed the corrected two-slot/4-GiB-KV attestation, and returned the card to
43 MiB without a fault, forced kill, listener, or survivor.

Two diagnostic reruns retained the decisive evidence:

- forward order:
  `/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-formal-c2-gpu0-short-diag-20260809T171516.435188879Z`;
- reverse order:
  `/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-formal-c2-gpu0-short-reverse-20260809T173515.954289991Z`.

## What passed

The sequential phase passed:

- both 512-token streams and deterministic replays;
- both selected-band 128-token slot canaries;
- both natural-stop semantic retrieval checks and their forced-row links;
- the fixed external DNN-off canary on slots 0 and 1;
- cache-zero, exact prompt counts, and clean slot turnover.

The concurrent server log shows the synchronized pair completed and both slots
then passed all later requests through the final external canary. The log also
shows the useful performance shape: prompts were prefetched serially, then the
two occupied slots decoded together at roughly 12.7--12.9 tok/s each in steady
state. These live log rates are diagnostic, not the client metric.

## What the retained rows prove

Forward order assigned A to slot 0 and B to slot 1:

- A was stream/replay exact for all 512 tokens;
- B was exact for 70 tokens and diverged at generated token 71: M=2 selected
  token `332` (`**`) while the M=1 replay selected token `71093` (a Markdown
  code fence);
- the synchronized forced stream already contained B's complete correct JSON;
  its separate sequential natural-stop probe emitted EOS at token 70.

Reverse order assigned B to slot 0 and A to slot 1:

- B became stream/replay exact for all 512 tokens;
- A was exact for 95 tokens and diverged at generated token 96: M=2 continued
  with a bare repeated JSON object while M=1 opened a fenced JSON block;
- the synchronized forced stream already contained A's complete correct JSON;
  its separate sequential natural-stop probe emitted EOS at token 95.

In both runs the forced identity used `ignore_eos=true`. The split therefore
occurs only after the answer boundary established by the later sequential
natural-stop probes. Those probes, all expected fields, cache-zero checks,
selected-slot canaries, and the fixed external DNN-off canaries passed. This is
a strict numerical or kernel-invariance failure with no observed corruption in
the synchronized answer prefixes. It is not direct proof that a synchronized
natural-stop pair would select EOS identically.

The synchronized rows were genuinely batched: each diagnostic recorded 1,024
predicted tokens across 520 `llama_decode` calls (`1.9692` predicted tokens per
call) and an average `1.9923` busy slots per decode. Send skew was below
`0.14 ms`. The missing timing fields are correct fail-closed behavior because
the streamed sequence was not a subsequence of the replay sequence.

The c2 allocation itself is now measured rather than modeled. It used
`30,570 MiB`, left `1,814 MiB` free, allocated `4,096 MiB` of F16 KV plus
`299.25 MiB` of recurrent state, and fully offloaded `65/65` layers.

## Diagnostic-only harness change

The capture now treats a missing concurrent endpoint as a normal failed result:

- the row, stream/replay alignment, token IDs, canaries, semantic checks, and
  occupancy counters are retained;
- `timing_endpoints_present=false` and the exact missing endpoint/case/slot are
  recorded;
- aggregate timing, throughput, and fairness fields that cannot be computed
  remain `null`;
- overlap and intrinsic gates remain false, and the process still exits 1.

No correctness or performance gate was relaxed. The new regression test removes
one row's `t512` value and requires a retained failed packet with no aggregate
rate. The complete offline suite is now 17 c1 plus 25 c2 tests, all passing;
Python compilation, Ruff, and `git diff --check` also pass.

The change worked as intended: both later failures retained complete 512-token
streams, replay IDs, missing endpoint identity, semantic rows, occupancy, and
clean teardown evidence while still exiting nonzero and sealing `FAIL`.

## Likely boundary and next action

The pinned SYCL backend changes more than one Q8 path at c2:

- flattened Q8 projections use the dedicated reordered multi-column
  `MMVQ<2>` kernel instead of the M=1 kernel; this specialization arrived in
  [llama.cpp PR #21845](https://github.com/ggml-org/llama.cpp/pull/21845),
  whose backend gate is tolerance-based rather than M=1/M=2 token identity;
- the 48 recurrent `ssm_out` projections retain shape `[K,1,2]` and select
  reordered DMMV per sequence, while c1 selects reordered MMVQ.

The prompt reversal makes HTTP routing, prompt-specific sensitivity, and gross
GDN/KV state mixing unlikely. The next bounded diagnostic is a synchronized
128-token B+B pair. If slot 0 remains c1-exact and slot 1 takes the alternate
tail, the second-column numerical path is reproduced directly. Only then build
a combined per-vector canonical-Q8 control, followed by separate controls for
multi-column MMVQ and recurrent-output DMMV. Broad `OPT=0` is not a causal
test because it changes several dispatches.

This general class is not unique to this host: upstream
[issue #7052](https://github.com/ggml-org/llama.cpp/issues/7052) tracks greedy
multi-slot output differences across backends. That does not excuse this
result or prove the exact SYCL cause; it supports treating bitwise cross-batch
invariance as a separate property from ordinary semantic correctness.

Do not weaken the existing forced-tail exactness gate or invent a c2 rate from
the incomplete endpoint mapping. Also do not describe the post-EOS failure as
natural answer corruption. A later promotable serving scorecard should add a
held-out prompt that naturally sustains at least 512 tokens, so the main long-
decode result is not based only on forcing short JSON answers past EOS.

## Evidence hashes

- forward `concurrent/result.json`:
  `39416de77fb20d88523dc83c15f629dec7d7a9e341e98d8104368dcd02778763`;
- forward `artifacts.sha256`:
  `5d9de5da683174a3fe097d8eb4ffcbf1f21f486b45633c4ad5a78f49cfe66226`;
- reverse `concurrent/result.json`:
  `55fd86dc97087689d24dcf0e546296a01bfe82f4748b0e1a1b71ebdc80645618`;
- reverse `artifacts.sha256`:
  `a05aec67deedbb6dcd3cc1a0d7ef1a75f60ab6a1f172b5aeb9bb489e0f7413af`.
