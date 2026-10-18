# Submission preparation and resume

`packet56_submission.py` is the packet70-local submission helper. Preparation
writes a reviewable payload and hash-bound evidence; it does not submit.
The coordinator supplies completed device receipts. CPU preparation alone is
not a submission or model-quality pass.

The default path comes from `storage.B / chain-registration.json:output`.
A different directory is admitted only by `resume_chain.validate(prepared=True)`,
following packet61x commit `05d39a699`. A registered destination carrying a
resume manifest must also pass that validation, so changing the registration
cannot bypass import checks. The source, destination, current boot, original
and current seals, identical binaries/selection/dispatch, every imported early
receipt and its lane sidecar remain pinned. An optional `destination` in
`resume-pins.json` registers a specific sibling resume directory; arbitrary
repeat directories are refused. There are no resume pins yet: packet70 has
not run. Never import packet64 early receipts into packet70: binaries differ.

Only K0/K1a/K1b/K2/W0p may be imported. KD/W2m/WS/WSs/WS128x/WS128 always run
fresh. Resume manifests and pins are bundled and disclosed in the derived
result, payload flags and notes. Every payload names draft-head prefix,
controller spin, packet60 HC fusion, packet59 draft-HC fusion, batch miss path,
24/24 placement and the selected expert kernel. Short notes stay below the
2,000-character API limit; structured flags retain the details. Full BF16 KV,
unchanged target verification and the packet49 oracle remain required.

```bash
P=experiments/own-xpu-runtime/stage2/packet70-record-bundle
nice -n 19 taskset -c 8-15,24-31 /home/steve/.venvs/deepseek-v4-xpu/bin/python3 -B \
  -m pytest -p no:cacheprovider "$P/test_submission56.py" -q </dev/null
```

All 22 synthetic submission tests pass, including all expert choices,
registered/resumed admission, disclosure hashes, changed-pin refusals and the
current record floor. No real submission is prepared without completed
quality/performance receipts. The strict 512-token gate remains false under
the inherited explicitly disclosed 128-token authorization.
