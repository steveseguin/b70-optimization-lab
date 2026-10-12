# Long-context arithmetic-v2 CPU oracles

Completed and verified: 0/2. Arithmetic `iq3-p17-detmath-v2` for the separate
Unsloth UD-IQ3_XXS quantized compressed model; context capacity 4,096, 32 generated tokens.
EOG 248044 or 248046 is retained and then stops generation. No device was accessed.

| Prompt | Prompt tokens | Generated | End | First 8 IDs | Last 8 IDs | Seconds/position | CPU hours |
| --- | ---: | ---: | --- | --- | --- | ---: | ---: |

Numerical-process wall time including resume segments: 0.000 seconds.
Measured user + system time: 0.000000 CPU hours.
These are CPU oracle costs, not serving speeds. Per-position times include the original
streaming weight loader and per-site logging; selected capture positions also include
the selection audit. Checkpoint write/verification is outside those position timings.
Token 1 includes initialization and prefill. `positions.jsonl`, `tokens.jsonl`, and
`result.json` retain timings, every token, top-five logits, logit hashes and decoded text.

| Prompt | Zero-based positions | Mean seconds/position |
| --- | --- | ---: |

QSA recomputes all complete four-token pools and scores them at every position.
Attention reduces the selected positions in score order, at most 2,048 plus up to
three trailing positions. Its cost grows through the budget edge; pool scoring
continues to grow after it. The frozen CPU allocator also scans its growing allocation
history, so wall-time growth cannot be attributed solely to QSA. The retained site
logs allow that distinction to be examined; no faster arithmetic was substituted.

One host allocation adaptation was required: the sealed adapter's 256 MiB temporary
pool would overflow near 1,225 admitted positions. `scratch-capacity.patch` enlarges
both its backing allocation and its pool bound to 512 MiB, without changing any
arithmetic. The initial short replay was stopped cleanly before the long runs; its
partial evidence is retained in `preparation-stopped-capacity/`. Both equality gates
use the final enlarged-pool build. The original numerical sources remain read-only;
`build-receipt.json` binds the two-constant overlay and generated include relocation.

Capacity proof: **PENDING**. Capacity changes allocated cache extents and bounds only;
valid-position arithmetic and the frozen 4,096-position RoPE table stay unchanged.
See `capacity-analysis.md` and the 4,096-capacity `capacity-incident/equality-proof.json`:
64 sealed tokens, all logit hashes/top-five records, 384 BF16 fixtures and eight layer
ledgers must match before LONG-A starts. LONG-A must be sealed before LONG-B starts.
Both gates compare against the unchanged sealed arithmetic, with no tolerance.

Resume proof: **PENDING**. The original suite wrapper could not resume; `oracle_long.cpp`
adds a checkpoint of **all** plan buffers, position, token history, generated IDs,
logit records and log offsets every 100 completed positions. Each buffer is hashed,
the temporary checkpoint is fully reread, then atomically renamed. Resume validates
input/plan/admission/capacity binding and every buffer, truncates output logs to the
checkpoint, and discards only this attempt's fixtures beyond that point. No weights
are checkpointed. The six-token diagnostic compares uninterrupted output with a
run interrupted in both prefill (after four positions) and generation (after eight):
eight tokens, 384 fixtures, eight ledgers, logit records and all mid-prompt records.
See `resume-equality-proof.json`. Failed runs never retry automatically; use `--resume`
explicitly. Completed runs are verified and skipped. Status updates after every position.

Prompts use distinct source files, once each, from the tracked corpus's **prose** class:
LONG-A is 598 rendered tokens from `docs/current-reproducibility-map.md`; LONG-B is
2,271 from `docs/model-effort-index.md`. Exact historical source bytes were recovered
by the corpus's hashes and matched back to its concatenated text; current files have
changed. The prompts are document prefixes, cut at a word boundary without padding or
repetition, preceded by “Summarize the following document in about 200 words.”
`prompts.json` in the input directory records source commits, hashes, offsets and
counts. The frozen publisher Jinja template, thinking disabled, no system message,
and packet2 tokenizer are identical to the suite; all twelve old renderings replay.

`prepare_long.py` calls the unchanged packet29 `prepare(out,prompt)` for the five-file
runtime bundles: `tokens.txt`, `input.json`, `identity.tsv`, `plan.tsv`, `vocab.bin`.
Those files have no short-prompt or context 256/1024 limit. Old runtime **CLI wrappers**
do have bounds; packet44 owns extending them. Python window `--input` takes the bundle
directory; the native runtime takes `tokens.txt`. `suite-manifest.json` uses the suite
schema with token_cap 32 and context 4096, plus explicit mid-prompt positions.

Positions in `midprompt/<position>/` are **zero-based**, including the five requested
indices 2040, 2048, 2049, 2100 and the last prompt index. Extra 2047, 2050 and 2051
records make the exact boundary clear. `prompt_ordinal` is the one-based consumed
count. Each directory retains the twelve QSA layers' full 2,051-slot int32 little-endian
selection buffers (unused slots are -1), ordered admitted IDs, full FP32 pool-score bits,
stable-tie counts and the 20,480-byte layer-47 BF16 stream. Scores are audited using
unchanged Core::dot and detmath::sqrt, without altering model buffers.

| Prompt | Position (zero-based) | Consumed tokens | Admitted | Dropped | Layers with score ties | Cutoff tie layers |
| --- | ---: | ---: | ---: | ---: | ---: | --- |

The budget is 512 complete pools × 4 tokens, plus an incomplete trailing pool. Thus
zero-based 2048 and 2049 may still admit every token; first dropped positions appear
at zero-based 2051 (2,052 consumed tokens). Ties keep the lower pool index first.
`cutoff_tie_layers` identifies ties affecting which complete pools are admitted.

Generation fixture layout is unchanged: step1 is the final prompt position;
steps 1–8 each contain 48 `[1,4,2560]` BF16 little-endian streams and a hash ledger.
The suite checker is reused and extended to compare all tokens, those fixtures,
and every mid-prompt selection/stream byte. Device outputs must provide the same
midprompt directory and binary names; pool-score audit JSON is oracle evidence, not
a required device output. Self-comparison and corrupted token, fixture, selection,
stream, truncated-list and missing-position copies are tested in `checker-tests.json`.
This is long-context arithmetic coverage, not a performance or full quality claim.

All commands use nice 19 and idle I/O. Two OpenMP threads per numerical process;
sequential campaign, no more than two oracle processes and eight compute threads.
Original affinity 4–15,20–31 is preserved. Combined oracle anonymous memory is
checked below 11.5 GB; no device access, sudo, mlock or host setting changes.
`df -B1 /` runs before builds/checkpoints/compression and every ten seconds; below
8 GB stops work. Scratch stays below 2 GB. Site logs rotate at checkpoints, compress
losslessly with restored-hash verification, and retain raw/compressed hashes in
`log-retention.json`. Large log and teardown artifacts are necessary execution
receipts; restore `.gz` with gzip and verify that manifest's raw SHA256. Checkpoints
are removed only after complete validation, with their hash and regeneration recipe
retained. No executable, weights or generated cache is committed.

Reproduction, from repository root (all writes stay in the two new directories):

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-long/prepare_long.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-long/build_cpu.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-long/long_run.py --stage capacity
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-long/long_run.py --stage resume-test
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-long/long_run.py --stage long --publish
nice -n 19 ionice -c 3 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-long/suite_check.py experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-long
```

Long runs use private systemd user units with the same affinity, nice/IO settings,
SIGTERM forwarding and SendSIGKILL=no. Each verified run is atomically renamed,
committed with explicit paths and the requested coauthor, fetched/merged if needed,
and pushed to main. No branch, stash, rebase or unrelated file edits.
