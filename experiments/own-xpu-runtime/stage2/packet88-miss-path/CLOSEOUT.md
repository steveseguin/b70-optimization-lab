# Packet88 miss path — attribution closeout

<!-- campaign-closeout -->

## Question and identity

Can the corrected rank0 half or rollback save enough lossless work to justify
a new packet84-derived candidate? Analysis on October 18 UTC / October 17
Toronto, 2026, CPU only on steve-b70s. Evidence is packet77's lane-B paired
screen, packet70 wide64, draft-HC, batch rollback, 24/24, rank1 draft,
Unsloth Flash-Next UD-IQ3_XXS quantized compressed model, packet49 oracle and
`iq3-p49-split32-v1` arithmetic, full BF16 KV. Packet84 is only the prospective
implementation parent.

## Outcome

Closed with attribution within the requested 40-minute attribution budget;
the 2.5-hour candidate phase was not entered. No supported new mechanism was
found. No candidate, screen or queue proposal was manufactured to test an
unsupported saving. This does not close the model's optimization lane.

Raw receipts reproduce the first-99 means exactly: A 13.688277 ms,
C 12.655226 ms, R 0.569390 ms, 252 misses among 1,188 intervals. The restore
payload is 19,025,640 bytes, after the already implemented 29,601,792-byte
spare-bank omission. No new device measurement or speed claim is made.

## What worked

Joining raw command identities with host timings separates snapshot/setup
accounting from corrected work. Independent device spans and sampled site
costs locate the target work while retaining instrumentation and sampling
limits. Cumulative copy counters establish exact payloads and two submissions
per restore without double-counting requests. R/D already overlap for almost
the whole R command. The unchanged source supplies the input-dependence and
terminal-state constraints.

## What failed or remains uncertain

There was no failed device run or build. The BCS overlap argument adds no new
overlap; wrong-token target activations are not reusable; setup-only savings
are too small or not independently exposed. Copy-engine transport speed and
the flat restore's actual device duration remain unknown. The 60 recorded
rollback transfer events have zero-width timestamps and do not time that
kernel. Existing scratch/metadata omission boundaries remain binding.

CPU byte identity, mock state identity, full-shape device-startup rehearsal,
seals and pinned-v4 grids/confirmations apply if a runtime candidate is built.
They were not run here and are not marked passed. In particular, no miniature
test is substituted for the full-shape startup gate.

## Evidence and patches

- [Attribution and mechanism decisions](MISS.md)
- [Raw-receipt recomputation](attribute.py) and [structured result/input hashes](attribution.json)
- [Final verification and resource receipt](final-check.log): 0.22 seconds, 27,208 KiB peak RSS, exit 0
- [Initial extraction log](attribution.log); the final script prints a smaller summary and additionally checks miss token IDs
- [Existing packet77 raw screen](../screen/v4-lanes/evidence/packet77-attribution-B-a/run/)
- [Existing packet85 model](../packet85-critical-path/MODEL.md)
- [Do not repeat](DO-NOT-REPEAT.md)
- [Task note](../../../../notes/2026-10-18-own-runtime-packet88.md)

`attribute.py --check` passes against the frozen raw receipts and source pins.
Only the standard library is used, under nice19, cores 8–15 and 24–31,
Python `-B`, stdin `/dev/null`, and a 4 GiB address-space ceiling. There was no
compile, model payload access, GPU initialization, service, sudo, settings
change, queue modification, reboot or process termination. All pre-existing
packet/screen/ops edits were left alone. The packet is below 1 MiB.

## When to revisit

Require one of: separately timed restore kernel/upload/host phases identifying
a material transport or setup saving; an exact scratch write-range and tail
preservation proof covering both abandoned redo and terminal state; or a
measured exposed corrected-half launch gap large enough to matter. Any new
candidate must copy frozen packet84 sources, keep production selectable, pass
byte/state/full-shape/seal gates, then use the unchanged pinned shared v4 with
both-lane grids and opposite-lane best-of confirmation. None is authorized for
device execution by this CPU-only packet.
