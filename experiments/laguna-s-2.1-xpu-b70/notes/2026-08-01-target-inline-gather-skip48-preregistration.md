# Laguna target inline gathers with slot 48 eager

Date: 2026-08-01 America/Toronto

Status: **preregistered non-scored diagnostic; no score is authorized.**

## Evidence and treatment

The completed prefix bisection proved that capturing slots 0–47 passes two
changing 400-token requests, while adding only slot 48 causes a canonical-q1
token mismatch. Slot 48 is layer 24's attention O-projection gather.

Add a diagnostic-only single skip index to the validated prefix machinery.
The treatment uses limit 96, keeps slot 48 on the protected eager callback,
and captures the other 95 gathers through V2's fixed input/output path. The
embedding all-reduce and all 48 attention calls remain eager. Required target
topology is therefore `51/50`; draft topology remains `14/13`.

Source must use one capture predicate for buffer allocation, capture dispatch,
replay eager-count validation, topology derivation, and activation evidence.
The skip is invalid unless inline gathers are enabled, must be `-1` or an
integer in `[0,95]`, and must lie below the configured prefix limit when set.
Selector-off behavior and the default `-1` full-prefix behavior remain
unchanged.

## Gate

1. Add focused tests for the 95-captured/one-eager capture and replay counts,
   fixed-input ownership, `51/50` topology, and invalid skip combinations.
   Pass Ruff, compileall, whitespace, and the existing focused suites.
2. Run one non-scored changing-request smoke. Persist raw responses before
   assertions. Require two exact 400-token q=1 prefixes, `cached_tokens=0`,
   normal DFlash acceptance, target `51/50`, draft `14/13`, exact four-rank
   activation evidence, and clean teardown.
3. Any token/cache/topology mismatch, hang, collective/device error, contract
   drift, or dirty teardown closes this treatment. Do not retry unchanged code
   or perform recovery.
4. A smoke pass authorizes a separate full 13-prompt exactness gate, not a
   score. A full exactness pass would then require a separate score
   preregistration whose first valid result is reported whether it wins or
   loses.

No model, weight, BF16 KV, width/depth, verification, sampler, teacher, prompt,
cache, acceptance, metric, or scoring-window change is authorized.
