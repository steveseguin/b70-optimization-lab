# Broader SC117 coverage — October 24, 10:06 UTC

The corrected coverage-b run passes all six requests and all three target/MTP
pairs. Independent closed readback verifies14 bundles,14,756 ranges and
1,552,202,176 target-state bytes; all299 retained artifacts total1,722,928,763 bytes.
Both registered GPU contacts are positive, both owners exited and drained safely,
and the fault baseline/protected vision owner are unchanged. Runtime445.670993s.
The qualified native binary973489… and its exact device-memory ledger are unchanged.

| Case | Input tokens | Output per mode | Consumed positions | Evidence and quality limit |
| --- | ---: | ---: | ---: | --- |
| Extended original chat |87|512, cap|598|All512 tokens/full target state equal across modes; first128 match original baseline. Coherent but only273 words and truncated mid sentence, so requested450–550-word complete retrospective is not satisfied.|
| Historical raw continuation |512|512, cap|1023|Exact pair tokens/state. Coherent continuation of the input cutoff; truncated mid list. This is untemplated continuation, not reading-question accuracy.|
| Fixed document facts |2084|84, EOS|2167|Exact pair tokens/state; all six facts correct in complete valid JSON, including facts near input positions60,1048,2037.|

Consumed positions exclude the final emitted token pending consumption. Maximum
observed consumed position is2166 (2167 positions), within unchangedcontext4096.
This is not a262,144-context claim. Both capped cases and natural EOS are retained.
No prompt editing, output repair, discarded samples or precision changes occurred.

[Full-text review](launch-b/evidence/device-b/manual-output-review.json) records
Codex's complete readback of all three unique outputs. It is not an external human
evaluation. The document task passes its preregistered rubric; the extended chat's
missing ending is explicitly attributed to the requested cap, not silently counted
as complete. Overallquality_qualified remains false. A complete answer beyond512
and a compatible independent same-weight model reference remain useful future work.

MTP verifies the same target normally. Extended chat has398 accepted/113 rejected
proposals; raw continuation423/88. The EOS task records82 accepted/one rejected and
one unscored proposal at termination; the independent event audit retains that
boundary rather than inventing a denominator. No aggregate speed comparison is
made: there are no excluded warmups and the order is2target-first/1MTP-first.
Raw timing remains available in the result. The previous15.73/23.30 resident screen
has its own separate identity and is not recomputed from these coverage cases.

## Failed first launch and explicit correction

[Coverage-a](evidence/device-a/incident-review.json) remains failed. Both native
parsers refused startup max-new512 before model/device initialization; no requests
ran. [Consumer diagnosis](evidence/independent-startup-bound-diagnosis.json) checked
all122 actual compiled dependencies: the startup field is limited to128 and used
only in the standalone generation path, while rank-mode requests have an independent
context-bounded count. The additive [launch-b wrapper](launch-b/README.md) sets
startup128 and retains actual requestcaps512/512/128. Five focused command/request
serialization tests and independent review passed. No native guard was relaxed,
no output count reduced, no binary rebuilt and no restart/retry loop added.

## Durable identity

- [Admission plan](launch-b/evidence/device-b/plan.json):
  `9d80a1d2fc29cef4444a555ca2f033952adf8250f8a052bb2d1eadc08b7429ac`.
- [Actual independent review](launch-b/evidence/device-b/review.json):
  `9ab6bfce305ecb82816bc36b50092a434a1faa4cd2b24eb3f99bbffbb031d2ed`.
- [Artifact index](launch-b/evidence/device-b/artifact-index.jsonl.gz):
  `ce564bfc70a5f8400c7602d94d96a97a416fe684195b3ffbbd251596876e7ba9`.
- Full result SHA256:
  `8036f66a7382861fb029fa009d2a185a97bf44e942e625a18147e5ae76c78dd2`.
- Raw/control roots: `/mnt/usb-models/own-xpu-runtime-results/gsq-coverage-b`
  and `/home/steve/own-xpu-runtime-results/gsq-coverage-b.control`.

The original SC117 revision/shards, official full-vocabulary draft, split24/24,
BF16 state/KV, tokenizer/template and fixed prompts are bound in the admission.
This establishes exact same-target speculative behavior on these longer cases,
not an independent full-model oracle or a public speed record.
