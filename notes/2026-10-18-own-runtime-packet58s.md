# Packet58s — one-card packet58g submission tooling

CPU-only preparation for the coordinator. No GPU work, service, sudo, settings,
model read, server dry-run or submission was performed. No frozen packet, screen,
ops tree or running evidence was edited. Initial `git pull --rebase` refused
because the shared worktree contains active experiment changes; `git fetch
origin main` then showed `HEAD...origin/main = 0 0`. Those changes were preserved.

The new [packet58s preparer](../experiments/own-xpu-runtime/stage2/packet58s-onecard-submission/README.md)
collects only the completed `card0-58g-a` queue. It pins the exact 58g build receipt
`61dd354dcf422774166a631911c939458b1fecf7c6215fdc505b908a689bf61d`, verifies
receipts and hashes, replays exactness and computes the one-card payload. It
follows the current packet91 submission path; packet84 and packet58g are frozen.

The one-card native requests say `decode_mode=plain`: **no MTP/draft**. They use
host-pinned expert weights, an 18 GB device expert cache with copy-on-miss fills,
full BF16 KV at 4096 and no prompt/KV/response reuse. K1a/K1b selected the
`zero-copy` fallback miss path. The payload discloses that choice separately
from the cache fills. All twelve prompts must match the packet49 CPU oracle
exactly under `iq3-p49-split32-v1`; no tolerance or substitute oracle is allowed.

Oracle equivalence is direct path identity: the repository path
`experiments/own-xpu-runtime/stage2/packet49-integrate/oracle/results` resolves
to `/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results`.
The preparer verifies this, then the pinned build/arithmetic/checker, frozen
input manifest, completion, each input/result/validation receipt and CPU repeat.
The real authority and completed KD/W2m/WS requests passed read-only review.

WS128 alone supplies `tokSOut`: the median of six class medians, using 99
intervals between generated-token events 1 and 100 after TTFT. `tokSTotal`
matches the two-card convention: median of output tokens divided by time from
request start to the last token. The result retains all-prompt median/mean/p10,
TTFT, class medians, timestamps, token hashes and exact accounting endpoints.

The 128-token owner scope is carried explicitly; the strict 512-token gate
remains false. **WS128x is exactness under possible shared load, not a second
timing run.** Fresh exactness repeats and fresh timing repeats are separate
fields. The latter stays false. A second whole-host timing run remains necessary
for a speed verdict; preparing this single-run scoped measurement does not claim
that gate passed. Standard 512-token prefill and natural completion are unmeasured.

## Public one-GPU record check

At **2026-10-18 02:34:37 UTC**, a read-only helper loaded the key from the local
file named by `docs/localmaxxing.md` without printing it. Authenticated
`GET https://www.localmaxxing.com/api/speed-tests` returned HTTP **403**,
Cloudflare **1010 / browser_signature_banned**, ray `a4c4251e3e1155b7`.
The same preplanned GET-only check of `/api`, `/api/docs` and `/api/openapi.json`
also returned 403. No follow-up requests were made after the denial was observed.
No records or pagination were returned. No write endpoint was called.

The local documentation identifies `/api/speed-tests` as the submission endpoint
but supplies no read-listing contract. We cannot establish whether a readable
listing is offered, whether a public matching one-GPU run exists, or its best
tok/s. **Public best is unknown; absence is not established.** There is no
matching one-card Flash-Next IQ3 entry in the local submission ledger. The new
threshold ledger preserves that distinction with an empty local history and
an explicit failed public-read audit, never a fabricated zero or a two-card floor.
The payload notes include the failed public lookup.

## Validation

Sixteen CPU tests cover a passing synthetic seven-window chain, failed window,
inexact prompt with rehashed receipt, missing WS128, incomplete queue, excessive
notes, changed hashes, unbound receipts, wrong oracle, layer-byte mismatch,
shared-host timing, reused native owner, empty/nonmonotonic timestamps, production
rejection of the synthetic seal, shared CLI `--dry-run`/API projection, payload
tampering and threshold advancement/stale-result rejection. The synthetic CLI
test patches network access to raise if used and exercises the actual shared
`main()` with `--dry-run`. Test receipts stay in the new packet only.

The production prepare command was also tried while WS128 was incomplete. It
refused with `queue incomplete; wait for finished WS128`, before creating an
output directory. No partial payload was emitted. Full finished-chain preparation
is the coordinator's next action below.

## Coordinator commands after WS128

Run from the repository root. These commands do not launch a GPU job. The output
directory must be new; do not overwrite a previous preparation. The server
dry-run and submission commands below are **for the coordinator**, and were not
executed by this CPU-only task. Keep the single-run limitation above when
reviewing the prepared result; never describe WS128x as timing confirmation.

```bash
cd /home/steve/llm-optimizations
set -euo pipefail
P=experiments/own-xpu-runtime/stage2/packet58s-onecard-submission
C=experiments/own-xpu-runtime/stage2/packet58g-onecard/evidence/card0-58g-a
O="$P/submission/card0-58g-a"
L=qwen38-flash-next-unsloth-iq3xxs-ownrt-tp1-packet58g-realistic-20261018
run58s() { nice -n 19 taskset -c 8-15,24-31 python3 -B "$@" < /dev/null; }

# 1. Prepare: all seven windows, exactness, receipts, hashes, whole-host WS128.
run58s "$P/packet58_submission.py" --chain "$C" \
  --oracle /home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results \
  --output "$O"

# 2. Local shared CLI preflight and schema projection (no network/key needed).
run58s "$P/submission_cli.py" --payloads "$O/payload-queue.json" \
  --label "$L" --dry-run > "$O/local-dry-run.json"

# 3. Coordinator only: authenticated API validation, no result write.
run58s "$P/submission_cli.py" --payloads "$O/payload-queue.json" \
  --label "$L" --server-dry-run | tee "$O/server-dry-run.txt"

# 4. Coordinator only: one submission, no retry option.
run58s "$P/submission_cli.py" --payloads "$O/payload-queue.json" \
  --label "$L" | tee "$O/submission-response.txt"

# 5. Extract the actual success ID locally, then append the one-card threshold.
SUBMISSION_ID=$(run58s -c 'import json,sys; from pathlib import Path; lines=Path(sys.argv[1]).read_text().splitlines(); assert len(lines)==2 and lines[0].endswith("HTTP 201"); r=json.loads(lines[1]); assert r.get("id") and r.get("status"); print(r["id"])' "$O/submission-response.txt")
run58s "$P/packet58_submission.py" --update-record "$O/result.json" \
  --submission-id "$SUBMISSION_ID"
```

If either API step is rejected, stop there; never update the threshold without
the successful submission ID. The offline updater trusts the coordinator's ID,
as packet49's does; it does not call a public endpoint to verify the transaction.
Commit the prepared evidence, actual receipt, threshold update and matching
`results/localmaxxing-submissions.md` entry together, then push. No local ledger
or public result was updated by packet58s preparation itself.

Generated evidence bundles intentionally retain original small source/receipt
bytes for portable replay. Large native binaries, BF16 fixture payloads and logs
are retained by their verified hashes and byte counts in the bundle, with source
paths for restoration. If a generated bundle exceeds the 1 MiB hygiene threshold,
retain it as the hash-bound quality/performance replay dependency and record its
size; never discard the original frozen run evidence to reduce bundle size.
