# Launch B: acknowledged full-suite capture budget

Original launch-A plan11819 and its sources/reviews are retained under lineage/unexecuted-a and remain unchanged. No A owner was launched. This wrapper uses the same binary, all26 requests,24 measured arms,54 target bundles, full original baseline gates and frozen retained-owner cleanup. Only unit/control/evidence names gain `-b`, and remaining payload accounting is corrected.

Initial payload forecast is27×231,442,500 bytes. Successful initial/second/third RESET acknowledgements each account for a whole target+draft capture. Warmups do not issue DUMP. For measured requests, successful DUMP accounts for221,743,168 target bytes once; the next successful RESET accounts only for9,699,332 remaining draft bytes. The explicit final repeated DUMP credits zero. Successful normal FINISH/owner close accounts for the final draft bytes. All failed callbacks leave their associated credit unapplied. A later comparison failure stops the inherited suite; credit does not authorize another request.

The full metadata128MiB reserve, external2GiB floor, root27GB+128MiB reserve,26/27 count bounds, memory forecast, two physical-owner requirements and no-retry handling remain unchanged. Credit never derives from arbitrary files or request-count guesses. The full result includes52 ordered successful capture acknowledgements and remaining payload zero after clean close.

Focused tests simulate payload writes at exact admission thresholds and one byte below, including the actual inherited request loop and callback wrappers. This is not a promise that starting at the mathematical payload threshold suffices physically: metadata/log writes also consume bytes while the full128MiB metadata amount remains conservatively reserved. Root still checks actual space and admits the concrete launch.

Root-only plan command after independent review:

```sh
python3 -B experiments/own-xpu-runtime/gsq-rco-iq3s/dense-packed-block/engine/operating/launch-b/once.py --plan
```

No plan or operational helper is invoked by preparation/tests. Existing native build is reused; no new compile is required.
