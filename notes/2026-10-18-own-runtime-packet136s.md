# Packet136s: submission preparation after the finished bundle8 chain

The copied tools prepared the bundle8 result and both dry runs passed on
October 18. **Nothing was submitted.** The prepared rate is
**58.798108759182306 tok/s**, the median of six prompt-class medians over
99 intervals between events 1 and 100. This is replay of the finished
packet136 chain, not a new GPU measurement.

The unchanged threshold receipt identifies `cmvdx8urg0068rf01vvb32bcs` at
58.2238342935355 tok/s, giving an observed increase of 0.9863219635305898%.
The public record and threshold are unchanged. This is the existing
owner-authorized 128-token scope; the raw realistic final gate and strict
512-token gate both remain false. No claim of a new 512-token gate, new speed
repeat, or clean boot is made.

## Defect and bounded fix

The original preparation indexed a missing packet-local `oracle/suite_check.py`
source entry and raised `KeyError`. Packet136's source gate deliberately omits
oracle symlink paths. The new
[packet136s tools](../experiments/own-xpu-runtime/ops/packet136s-submission/README.md)
copy both entry points, the evidence validator, adapter and needed local
dependencies. Only the checker-binding block changes; all other checks remain
byte-for-byte unchanged. The tests enforce that boundary.

The fallback verifies packet136's source-pinned `oracle-binding.json` equals
its sealed `shared_oracle`; verifies the packet49 oracle build/arithmetic
bytes through that binding and the existing `oracle_inputs_sha256` checks;
requires the binding's checker hash to equal packet49's own sealed oracle
build's checker hash; and compares the actual bundled checker bytes. The
unchanged adapter also verifies the oracle symlink and live authority.
The checker hash is
`f33fd0d4a28943df90137b19a47c3ef2d176e3b352526f1037ec4757ef10ae93`.

The brief's suggested parent relationship did not match disk:
`parent_seal_sha256=0adf2fe9e0ed236f35c58f456cc45c395e90406bed9b790faec2532acdcc7406`
pins `lineage-inputs/packet56-chain-input.json`, as `chain_seal.py` specifies.
Packet124c's current build receipt hashes to
`b75bc5db9a21020b97685edf68d679d974fe1429ca1a5618dc7735f2344ffc69`.
The fix uses the allowed packet49 own-seal route, not an assumed parent pin.
[Inspected hashes and fault counts](../experiments/own-xpu-runtime/ops/packet136s-submission/audit.json).

## What ran

Host: `steve-b70s`. `git pull --rebase` refused existing unrelated dirty
files; `git fetch origin` confirmed HEAD and origin/main both at
`cd01675c05893d8288a26be04b9ad9990aa76396` before work. Existing dirty files
were preserved. No GPU, service, sudo, queue, host setting or runtime changes
were made. `CURRENT.md` and all sealed trees stayed untouched; the sole new
packet-tree write is the explicitly authorized `submission/prepared-a/`.

Each test/preparation/dry-run command below ran from the repository root with
`ulimit -v 4194304`, prefixed by
`nice -n 19 taskset -c 8-15,24-31 /usr/bin/time -v`, and stdin from `/dev/null`.
The cap limits only these child processes' address space, not host settings.

```bash
python3 -B experiments/own-xpu-runtime/ops/packet136s-submission/test_oracle_binding.py
python3 -B experiments/own-xpu-runtime/ops/packet136s-submission/prepare_submission.py \
  --packet packet136-record-bundle \
  --chain experiments/own-xpu-runtime/stage2/packet136-record-bundle/build/device-cards01-a \
  --output experiments/own-xpu-runtime/stage2/packet136-record-bundle/submission/prepared-a
python3 -B experiments/own-xpu-runtime/ops/packet136s-submission/submission.py \
  --payloads experiments/own-xpu-runtime/stage2/packet136-record-bundle/submission/prepared-a/payload-queue.json \
  --dry-run
env -u LMX_API_KEY python3 -B experiments/own-xpu-runtime/ops/packet136s-submission/submission.py \
  --payloads experiments/own-xpu-runtime/stage2/packet136-record-bundle/submission/prepared-a/payload-queue.json \
  --server-dry-run
```

An initial six-test run passed; adding an independent authority-build tamper
case produced the final **seven passing tests**. The original validator is
loaded unchanged and raises the exact missing-key exception on the real chain.
The copy passes the same chain. Rehashed tampered checker and binding members
refuse, and even a correspondingly changed shared binding cannot bypass the
oracle build's own checker pin. Direct pins retain priority. A separate
`prepare_submission.py --help` invocation also passed. Preparation ran once;
`prepared-a` did not exist beforehand.

Peak RSS: final tests 113,360 KiB; preparation 187,144 KiB; local dry run
126,764 KiB; server dry run 126,712 KiB. All exit statuses were zero.
[Test log](../experiments/own-xpu-runtime/ops/packet136s-submission/tests-final.log),
[preparation log](../experiments/own-xpu-runtime/ops/packet136s-submission/prepare.log),
[local dry-run output](../experiments/own-xpu-runtime/ops/packet136s-submission/dry-run.json),
[server dry-run response](../experiments/own-xpu-runtime/ops/packet136s-submission/server-dry-run.log).
The server helper read its configured key file itself; the key was never printed.

## Dry-run summaries

Both runs used this same exact payload:

| Run | Label | tokSOut | Notes characters | Outcome |
| --- | --- | ---: | ---: | --- |
| Local dry run | qwen38-flash-next-unsloth-iq3xxs-ownrt-tp2-packet136-record-bundle-realistic-20261017 | 58.798108759182306 | 875 / 2000 | Exit 0 |
| Server dry run | qwen38-flash-next-unsloth-iq3xxs-ownrt-tp2-packet136-record-bundle-realistic-20261017 | 58.798108759182306 | 875 / 2000 | HTTP 200; `{"valid": true}`; exit 0 |

The inherited label date is preserved. The actual preparation and both dry runs
ran October 18. No submission ID was created or claimed.

The retained queue-completion receipt passes all eleven windows K0 through
WS128. Each of the six collected model-window preflight logs contains two
historical fault-signature lines; the unchanged replay gate found no new
window fault signatures. This is not a fault-free-host claim or a new health
probe. The actual prepared evidence documents one preregistered timed WS128
and independent exactness windows, not multiple new timed server repeats.

## Packet139 and retained output

Read-only inspection shows packet139 **does not have this exact defect**:
its copied validator selects `seal.shared_oracle.files_sha256` at the canonical
packet49 checker path for its current packet, rather than indexing a missing
packet-local source. No packet139 code or preparation was run or edited;
this is a static finding, not a full packet139 qualification.

[Prepared result](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/submission/prepared-a/result.json),
[attestation](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/submission/prepared-a/promotion-attestation.json),
[payload queue](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/submission/prepared-a/payload-queue.json),
[result packet](../experiments/own-xpu-runtime/stage2/packet136-record-bundle/submission/prepared-a/result-packet.md).

Retain the 5,555,101-byte `evidence.json.gz` with those files. It contains
original receipts and is consumed by result replay, attestation and payload
validation. It is required evidence, not a cache; its SHA-256 is pinned by
`result.json`. Restore the exact blob from this commit if needed. Re-running
collection against mutable live files is not a byte-preserving restoration.
No original evidence or large KD fixture was removed.

Final `git diff --cached --check` passed. The repository hygiene checker
reviewed 29 changed paths with zero errors and one expected large-artifact
warning for the retained evidence bundle; its consumers and restoration are
documented above. The focused diff contains only the new tool copy, the new
prepared output and this note.

The coordinator can review this prepared output for a later real submission.
This task ends with preparation, dry runs, and the focused commit/push only.
