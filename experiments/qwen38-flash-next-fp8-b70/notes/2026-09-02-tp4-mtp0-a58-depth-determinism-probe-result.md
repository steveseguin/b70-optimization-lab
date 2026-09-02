# Qwen3.8 Flash-Next FP8 A58 same-server depth-determinism probe result

Date: 2026-09-02 14:03--14:29 EDT, boot `95bac684-eaa0-4157-bc13-78359c238700`
(BIOS 2.4a, Gen4 root SSD with zero corrected events, upstream GuC 70.72.1
loaded in place on all four B70s)
Status: diagnostic complete; the full-graph line is run-to-run
nondeterministic at every prompt depth tested, including 256 tokens

## Run

Byte-identical A56/A57 server at attempt 58 / port 19730: tuned M1 W13-N32
map, `twoshots`, full decode graph `[1]`, external checkpoint, PLE-only UVA
placement, 2304 max model length, host guards. Load `542.75 s`, graph
captured, healthy at 14:23. All four workers initialized normally on the
new GuC (the exact point where A57 froze on 70.44.1). The probe then sent
three identical greedy `/v1/completions` requests (`temperature=0`,
`seed=1`, `ignore_eos`, `max_tokens=128`, `return_token_ids`) at each depth,
prompts being the first N token ids of the frozen 2048-token fixture case.
It wrote the stop file; the supervisor recorded the expected invalid stop
(rc 143), the host wrapper restored swap and ASPM, and the GPUs came back
idle. No link event, no freeze.

## Result

| depth | distinct outputs in 3 repeats | first divergence vs repeat 1 (token index) | cached tokens |
|---|---|---|---|
| 256 | 3 | 9, 15 | 0 |
| 512 | 3 | 16, 16 | 0 |
| 1024 | 3 | 104, 104 | 0 |
| 1536 | 3 | 29, 27 | 0 |
| 2048 | 2 (repeat 3 = repeat 1) | 12, none | 0 |

`largest_deterministic_depth = null`, `smallest_nondeterministic_depth = 256`.
Summary: `.../attempt58/a58-depth-determinism.json`.

## Interpretation

There is no depth boundary. Identical greedy requests to one healthy server
disagree within 9--16 output tokens even at 256 prompt tokens, so the
forward pass of this line is not bitwise reproducible; the A56 exact-2K
failure was one instance of a general property. The frozen short battery
(146-token chat prompt, 256 outputs, 16 repeats with one hash) passes
because its argmax margins are wide enough to hide the jitter, not because
the computation is exact. Under the lab's standard, the full-graph line
therefore cannot carry a "lossless, deterministic" promotion at any context
until the source is found and removed; the `23.626811 tok/s` A56 short
result stands as a speed observation with an exact-hash gate that this
finding shows to be insufficient on its own.

The 2026-08-28 eager line reproduced the 2K and 4K authorities across fresh
servers, so the jitter entered with one or more of: full decode graph
capture/replay, the public oneCCL build with `twoshots`, the PLE-only UVA
placement, the current vLLM head, or the chunked 64-token prefill. The
probe's outputs diverge during decode, but prefill-only determinism has
not been isolated yet.

## Next discriminator (A59)

Same server identity, probe v2: at depths 256 and 2048, eight repeats with
`max_tokens=1` and `logprobs=5` to test whether the first decode step's
logits are identical after prefill (prefill/first-decode determinism), then
three 128-token repeats with `logprobs=2` to measure the per-position
logprob jitter before the first divergence and the top-1/top-2 gap at the
divergence. If first-step logits already differ, prefill or the collective
path is implicated; if they agree bit-for-bit and jitter appears only in
later graph-replayed steps, the graph replay path is implicated and an eager
control server follows.
