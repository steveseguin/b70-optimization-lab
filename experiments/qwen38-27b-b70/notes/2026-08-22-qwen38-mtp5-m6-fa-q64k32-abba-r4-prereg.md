# Qwen3.8 MTP5/M6 Q64xK32 integration-DSO requalification (r4) preregistration

Date: 2026-08-22

Status: **preregistered; single launch authorized after commit/push and hash
recheck; not yet run.**

## Basis

The [endpoint2 campaign](2026-08-21-qwen38-mtp5-q64k32-endpoint2-result.md)
proved the r2 operator DSO undeployable: its exact-coverage kernel-config
lists lacked the memory-profiler tuple `96,false,false,false,false,false`.
The [r3 integration build](../scripts/build-qwen38-m6-head256-q64k32-attn-override-r3-20260821.sh)
rebuilt the candidate from the identical frozen source commit
(`2dd55f38…`) and identical frozen candidate patch (`93864320…`), changing
only the config lists to the upstream full presets (literal `all`, frozen as
lane confs `6091d2b7…`/`2c46aea6…`). Coverage is proven two ways: the
`-Wl,-z,defs` link against the stock farm resolved every dispatch-referenced
kernel symbol, and the r3 DSO contains **zero** compiled-in
"not compiled" error branches versus two in r2. New candidate DSO identity:
`979e91c1f11d9e6ede77c494803889e9f47dd881c2d02e1c290c5246c0dbb616`
(runtime and stage sealed by the builder at
`/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r3`).

Because the r3 operator qualification binds the exact DSO bytes, the new
artifact requires **requalification** before any endpoint use.

## Contract

Full adoption of the
[frozen operator contract](2026-08-21-qwen38-mtp5-m6-fa-q64k32-operator-prereg.md)
— identical fixtures, oracles, correctness/mutation/marker/mapping gates,
fresh-process A-B-B-A order on GPU2 then GPU3 with stop-on-first-failure,
40x100 captured-replay timing, and the conjunctive decision gates including
the `21.844 us/call` KV1300 hurdle and `+2.0 us/call` KV128 cap — with two
recorded identity updates:

- qualifier `scripts/qwen38_mtp5_m6_fa_q64k32_operator.py` at
  `4ad6fd360b1969f3e56a6658a61436bec5bf9d580e88602ea1583cebb3bde557`
  (schema, builder-name, build-inputs, and graph-manifest basename pins
  updated from r2 to r3 stage identities; no gate logic changed);
- driver `scripts/run-20260821-qwen38-mtp5-m6-fa-q64k32-operator-abba.sh` at
  `b257e650fbc4230d229c33235e7e8a4b4389ed637b8c830d7c0ed3e4ee159288`
  (embedded qualifier identity refreshed; fails closed on byte drift).

Fresh immutable result root (must not exist before launch; never reused):

```text
/home/steve/qwen38-mtp5-m6-fa-q64k32-abba-20260822-r4
```

The r3 result root remains terminal-valid for the r2 DSO's qualification and
is not compared against r4. A pass qualifies the **integration DSO** for the
already-designed endpoint campaign (endpoint3, reusing the endpoint2 driver
with the r3 stage identities); any gate failure rejects this artifact with
no same-root retry.
