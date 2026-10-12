# Arithmetic-v2 128-token CPU suite

Verified prompts: 9/12. Complete: False.
Arithmetic `iq3-p17-detmath-v2`, quantized Unsloth UD-IQ3_XXS; context 256; cap 128.
EOS 248044 or 248046 is included and then stops generation; no forced continuation.

| Prompt | Prompt tokens | Generated | Early end | First 8 token IDs | Last 8 token IDs | Seconds/position | 64-prefix equal |
| --- | ---: | ---: | --- | --- | --- | ---: | --- |
| incident-retrospective | 87 | 128 | False | 332, 37947, 1653, 10082, 3508, 8812, 25, 23288 | 11164, 6297, 6679, 13, 271, 332, 69075, 35059 | 20.3990 | True |
| code-review | 90 | 128 | False | 1919, 369, 264, 4927, 41052, 6206, 494, 63723 | 1558, 494, 10270, 887, 310, 40357, 27224, 440 | 18.1398 | True |
| customer-email | 77 | 128 | False | 12646, 25, 5376, 383, 21503, 19389, 16870, 25 | 1452, 279, 4884, 364, 411, 4125, 13, 1165 | 21.3985 | True |
| sql-debugging | 83 | 128 | False | 2, 10768, 3072, 264, 36885, 45132, 11033, 303 | 5574, 12585, 11, 198, 262, 29732, 1889, 24474 | 21.3659 | True |
| release-plan | 68 | 128 | False | 2, 16107, 16870, 9392, 25, 7134, 21753, 343 | 5839, 5614, 369, 310, 17833, 4610, 45702, 1973 | 20.8130 | True |
| benchmark-analysis | 65 | 128 | False | 1919, 369, 264, 11088, 46931, 314, 2972, 66 | 318, 68, 1257, 2487, 343, 3950, 44, 11 | 16.5751 | True |
| architecture-tradeoff | 67 | 128 | False | 1919, 369, 264, 11088, 41052, 6355, 12105, 303 | 11, 28121, 28, 19, 369, 279, 1132, 2904 | 17.1900 | True |
| bug-report-synthesis | 71 | 128 | False | 2, 29505, 8001, 25, 769, 1519, 5764, 25375 | 52369, 92217, 52738, 1420, 1510, 31826, 27896, 835 | 17.0556 | True |
| technical-guide | 69 | 128 | False | 2, 25816, 12347, 25, 29381, 264, 1478, 59542 | 1665, 26157, 15087, 14, 22054, 88004, 625, 27650 | 17.4586 | True |

Numerical-process wall time (sum): 34554.049 seconds.
Measured user + system CPU time: 15.860062 CPU hours.
Per-position wall times are in `positions.jsonl`; per-generated-token times and IDs are
in `tokens.jsonl`; decoded text is in `result.json`. Token 1 includes prefill time.
These are CPU oracle costs, not serving speeds.

Capacity changes only allocated cache extents and guards, not valid-position arithmetic.
See `capacity-analysis.md` in the oracle directory for source evidence. Before token 65,
the incident run must reproduce the sealed 64 tokens, all 64 logit/top-five records,
384 BF16 layer fixtures and 8 ledgers byte for byte at context 256. Other prompts cannot
start until this incident result is sealed. Each prompt's `suite64-equality-proof.json`
compares the finished 64-token suite when available; any difference stops the campaign.
The source analysis predicts comparable prefixes; measured confirmation is PASS.

The sealed program hard-codes cap 64/context 192: `oracle128.patch` changes only those
limits, captures steps 97–104 as well as 1–8, and adds the prefix checkpoint wait.
All numerical sources and compiler flags are unchanged and hash-bound in
`build-receipt.json`; the rebuilt binary has its own hash. No device code is run.

Input bundles do not depend on generation cap or context. Packet29 `prepare.py` takes
only the prompt, so each new input directory holds `bundle-reference.json`, binding
all five existing bundle files by SHA256 without duplicating them. Use the manifest's
`input_bundle` for window.py `--input`; the native runtime takes its `tokens.txt`.

Two OpenMP threads per oracle. While the existing suite runs, only one new oracle runs;
after it exits, at most three run, within the 12-thread ceiling. CPU affinity is inherited,
nice 19 and idle I/O are required. Combined oracle anonymous memory is guarded below
11 GB; each new worker below 3 GB. No sudo, devices, host settings, or model writes.
`df -B1 /` guards large writes and runs every ten seconds; below 8 GB stops work.
Scratch stays below 2 GB. Retain raw 20,480-byte BF16 fixtures only for steps 1–8 and
97–104 (through EOG). Compress progress/timing logs with deterministic gzip, verify
restored hashes before deleting raw logs; original hashes/sizes are in receipts.
Large teardown and compressed evidence files are necessary receipts, not disposable dumps.
No models or executable build files are committed; `build_cpu.py` recreates the CPU binary.

Each prompt runs under a private temporary name, is verified, then renamed. Finished
prompts are reverified and skipped on restart; completed partial results are recovered.
An interrupted unfinished prompt alone needs recomputation. `status.json` and each
attempt's status update after each position. Failed runs are not retried automatically.
The coordinator was corrected after the first two prompts: its old-suite process check
matched the new suite128 directory as a text prefix. It now compares path components.
Both finished prompts were pushed before the supervisor was stopped; neither was rerun.
See `coordination-fix.json`; this changed process admission only, not oracle arithmetic.

Each finished prompt gets a separate explicit-path commit and push, with the requested
coauthor. Fetch/merge main on remote movement; no stash, branches or rebase.

Run from repository root:

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/build_cpu.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/suite_run.py --all --jobs 3 --publish
nice -n 19 ionice -c 3 python3 -B experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128/suite_check.py experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128
```

The checker accepts prompt directories or prompt/run directories and verifies both
fixture ranges and the complete 128-token sequence (or recorded EOG). Unit tests use
oracle files and corrupted copies, including tail corruption. This extends exactness
coverage past token 100; it is not a 512-token final performance gate or a speed result.
