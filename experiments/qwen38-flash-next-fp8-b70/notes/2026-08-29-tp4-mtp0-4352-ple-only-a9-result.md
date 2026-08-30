# Flash-Next TP4 MTP0 4K PLE-only A9 result

## Decision

A9 passed every preregistered lossless, capacity, and B70 lifecycle gate and
is now the preferred current-runtime MTP0 placement **candidate**. It improves
the protected short median by 4.55% and the protected exact-4K median by
10.82%, while returning the exact protected outputs on every timing row.

This is additive Grade-C evidence, not deployment qualification. A fresh-server
repeat is still required, and corrected local-NVMe link events prevent
clean-host wording. No prior result, patch, or speed is replaced or lowered.

## Measured result

The PLE-only placement was exact in both its mechanism and static capacity
prediction:

- all four ranks reported 11.92 GiB offloaded;
- 51,200,245,760 PLE bytes were host-resident across TP4;
- the input embedding was device-resident;
- model load reported 31.57 GiB/card;
- the 128-MiB/rank cache exposed 4,747 tokens, exactly the preregistered
  linear estimate and above the 4,352-token ceiling.

The recovery canary passed. The direct battery retained the established 6/7
semantic boundary, with only `code_execution=30` instead of `14`. The fixed
repeat returned one hash 16/16 times, and the exact 4K needle passed with zero
cached and created-cache tokens.

Three p146/o256/c1 rows returned the protected output hash at:

- 5.466103633400652 tok/s;
- 5.402373303540544 tok/s;
- 5.46135622547447 tok/s.

The median is **5.46135622547447 tok/s**, 4.5478% above the protected
5.223788770075911 current-runtime anchor. The row span is 1.1669% of the
median.

Two exact p4096/o128 rows returned the protected token-array hash at
5.258322965451046 and 5.286666537537832 tok/s under conventional 99-interval
accounting. Their median is **5.272494751494439 tok/s**, 10.8175% above the
protected 4.7578181021380175 anchor. TTFT was 110.0617 and 100.7527 seconds,
median 105.4072 seconds, about 28.52% below the prior 147.4683-second median.

## Lifecycle and caveats

Client and supervisor both returned zero. Shutdown was orderly, no listener,
owned process, compile path, or RPC path remained, and all four exact B70s
returned below 43 MiB. No journal event named a B70 address. The known
shutdown-time output-handler notice and one shared-memory cleanup warning were
retained; they did not prevent clean owned teardown.

The broader run window contains six corrected APEI sections and nine NVMe AER
status records for local storage endpoint `0000:01:00.0`. They were reported
as corrected and did not alter model, output, or B70 gates, but they block
clean-host and deployment-ready wording. This is the same continuing local
storage-link caveat seen in recent NVMe-loaded arms.

The compact receipt is
`data/20260829-tp4-mtp0-4352-ple-only-a9-result.json`. Raw evidence remains at
the paths recorded there. The next GPU arm should be a fresh-server repeat of
this exact placement, not another memory selector. If it passes, promote this
as the reliable MTP0 base and then optimize from it before transferring the
winner to MTP1-4.
