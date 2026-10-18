# Packet104 retention

Keep copied source files, deterministic derivation scripts, the compressed
packet100b route manifest, its 46,080-byte route payload, build receipts,
protocol logs, proposed queue plan and pending integration views. No tracked
file added by this packet is 1 MiB or larger.

`build/` is ignored and bounded below 300 MB. Recreate the native micro with
`build_microbench.py` under the documented CPU affinity, priority and 8 GiB
limit. It compiles only the actual micro include closure plus the required
prepared-submission wrapper; no parent engine build or orchestration output
is needed. `derive.py` and `derive_small.py` regenerate candidate headers from this packet's
copied sources. A full model build, if the micro qualifies, still needs the
frozen packet100 runtime build inputs and its 12,582,900-byte generated RoPE
header identified in `source-origin.json`; that header is not a micro input.

`first-build-before-dispatch-audit.json` is a superseded preparation receipt.
Its binary remains `build/microbench-first` locally; it was never executed.
Its source version is preserved by commit `88cbff92c`. Later build receipts
describe the corrected selected draft baseline. No compiled binary is a
portable public release or a model result.
