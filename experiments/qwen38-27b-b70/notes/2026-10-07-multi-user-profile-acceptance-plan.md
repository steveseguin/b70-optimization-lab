# Multi-user profile: acceptance plan (2026-10-07)

**What this is for.** Commit `db98ba0d4` added a third profile to the two-card FP8 package launcher,
`multi-user` (64 users at once, no speculation, overlays `b70_exclusive_prefill` +
`b70_fa_decode_per_seq`, prefix cache off). Its numbers come from the research launcher
([2026-10-04 multi-user result](2026-10-04-fp8-multiuser-result.md)); the package's own acceptance is
pending. This plan gets that acceptance from **one GPU session** that also re-accepts the recommended
profile, through the package launcher, from a public download of a pushed commit.

## What changed in the repository (CPU only, no GPU yet)

* `scripts/run-fp8-tp2-acceptance-session.py` gains `--multi-user`. After the single-user gates and the
  graceful stop of the recommended-profile server, it waits (bounded, 5 min) until the port, the
  render devices and the launchers' stage lock are free, then starts **one** server with
  `serve.py start --profile multi-user` from the downloaded package. On it, the research campaign's
  own client (`scripts/bench-openai-concurrency-oracle.py`, same flags: completions, 128 tokens,
  seed 42, token ids) runs the short ladder suite and the long-prompt suite, each as one sequential
  pass plus **two passes at 16, 32 and 64 users at once**. Every answer is compared token for token
  (`compare-ladder-oracles.py`'s `compare_rows`) with the frozen single-user no-MTP answers the
  campaign used, then the server is stopped through `serve.py stop` (in a `finally`, so a client
  timeout still stops it). Results: `<out>/multi-user/summary.json`; `session-rcs.json` gets
  `multi_user`. The new overlays, their `entry_points.txt`, the client, the comparator and both suites
  are in `PINNED`, so the public download is checked against the working tree.
* `scripts/collect-fp8-tp2-acceptance-evidence.py` pins the same files in `SOURCE_PATHS`, freezes the
  two reference files into the packet (`reference/multi-user/`), and, only when the raw session has
  `multi-user/`, adds the gate `multi_user_exact_16_32_64_both_passes` and a `multi_user` summary
  section (exact counts and tok/s together per level and pass), recomputed from token ids with the
  packet's own frozen runner, comparator and launcher. The twelve existing gates are unchanged.
* Both scripts are pinned by the current packet (`data/2026-10-04-fp8-two-card-chunked-upload/`);
  their drift is declared there in `source-drift.json` with an `additive` proof (inserted lines only).

### The frozen references

| Suite | Reference (one request at a time, no speculation) | sha256 |
| --- | --- | --- |
| short (`data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json`, 64 prompts) | `/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp0-ladder.json` (campaign `REF_LADDER`) | `843ef0c2…cc1878` |
| long (`data/2026-10-04-fp8-multiuser/long-prompt-suite.json`, 2K-8K tokens) | `/mnt/fast-ai/bench-results/fp8-multiuser-three-s64-20261004/tp2-pure-faseq-head4-mtp0-s64-long-concurrency.json`, its sequential pass (campaign `LONG_REF`) | `68016724…5e31dc` |

Neither file is in `data/2026-10-04-fp8-multiuser/` (that folder holds only comparisons); the session
refuses to start the second server if either is missing or its digest changed, and the collector
copies both into the packet. **Caveat on the long reference:** it is the sequential pass of the
three-overlay research server (with the 4-row LM-head overlay that was later found unnecessary), and
the research gate for long prompts was "equal to the same server's solo answers", not this file. If
the long sequential pass differs from it while every batch still equals the server's own solo
answers (`exact_vs_own_solo`), that is a reference question for the owner, not a multi-user failure.

## Command sequence (GPU session)

Before the session, on the CPU:

1. Run every `run:` line of `.github/workflows/guides.yml` locally (it now includes
   `tools/test_fp8_tp2_acceptance_session.py`). Commit and push to `main`; note the sha.
2. Check `CURRENT.md` and `docker ps`: cards empty, nothing else on this host's GPUs, about 3 GB of
   host RAM is not enough to run beside anything else.

The session (its own systemd user unit, so the agent harness cannot kill it; **`QUALIFIED_CONTAINER`
is required**, the default points at a container that predates the allgather overlay):

```
systemd-run --user --unit fp8-tp2-acceptance-mu --same-dir \
  --setenv=QUALIFIED_CONTAINER=/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp5/container-final.json \
  python3 experiments/qwen38-27b-b70/scripts/run-fp8-tp2-acceptance-session.py \
    --commit <pushed sha> --out /mnt/fast-ai/bench-results/fp8-tp2-acceptance-multiuser-<date> --multi-user
```

After it ends (`journalctl --user -u fp8-tp2-acceptance-mu -o cat`; confirm `docker ps` is empty):

3. **Repoint `DEFAULT`** in `collect-fp8-tp2-acceptance-evidence.py` at
   `experiments/qwen38-27b-b70/data/<date>-fp8-two-card-multi-user` **before** collecting (the packet
   pins the collector's own bytes), and delete `source-drift.json` from the 2026-10-04 packet (it keeps
   its frozen truth; it is just no longer current).
4. Collect, with the same `QUALIFIED_CONTAINER`:
   ```
   QUALIFIED_CONTAINER=/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp5/container-final.json \
   python3 experiments/qwen38-27b-b70/scripts/collect-fp8-tp2-acceptance-evidence.py \
     --raw /mnt/fast-ai/bench-results/fp8-tp2-acceptance-multiuser-<date> \
     --out experiments/qwen38-27b-b70/data/<date>-fp8-two-card-multi-user
   ```
   It refuses to write a packet whose summary does not pass.
5. Publish (owner's call): `python3 experiments/qwen38-27b-b70/scripts/publish-fp8-tp2-allgather-package.py
   --acceptance experiments/qwen38-27b-b70/data/<date>-fp8-two-card-multi-user/summary.json` for the
   recommended profile; the `multi_user_profile` block of `packages/qwen38-27b-fp8-tp2-b70/package.json`
   has no publish script yet, so set `acceptance_status`, `evidence` and the measured totals there by
   hand from the packet's `multi_user` section.
6. `python3 tools/validate-repro-guides.py --write-package-catalog`, `python3 tools/build-model-pages.py`,
   `python3 tools/validate-repro-guides.py`, `python3 tools/check-doc-links.py`,
   `python3 tools/check-manifest-paths.py`, `python3 tools/check-pinned-hashes.py`, then every `run:`
   line of `guides.yml` again; update `CURRENT.md`; commit and push.

## Expected GPU time

About **65-80 minutes**: the existing session is 35-45 minutes (download, model verify, image pull,
one server, strict suite, six practical requests, stop, two health probes); the multi-user stage adds
one server start (~2.5 min), the short suite (~5 min: 64 sequential answers plus six batches) and the
long suite (~13 min: on 2026-10-04 the sequential pass plus two 64-user passes took 9 min), and one
stop. Each server is started once; nothing is retried.

## Pass criteria

* All twelve existing gates, unchanged.
* `multi_user_exact_16_32_64_both_passes`: on **both** suites, the multi-user server's sequential pass
  and **both** passes at 16, 32 and 64 users are token-for-token equal to the frozen single-user
  answers (16/16, 32/32 and 64/64, twice), cached tokens zero, the launched argv is exactly
  `serve.py`'s `multi-user` argv (64 sequences, no speculative config, prefix cache off, the overlay
  environment), clean owned stop, the downloaded overlay bytes equal the working tree's.
* Totals (generated tok/s with all users at once) are **reported, not gated**: no speed threshold.
* Health before and after clean, zero GPU fault lines over the whole session (the journal window covers
  both servers).
