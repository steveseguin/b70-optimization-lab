# Native multiblock client ready

September14, 2026. Packet06 client is now implemented and passes offline checks.
Client SHA73f9124c8ad298c5776ca3a9327b0381432d2fdfe0042b593224ea1507380cde;
validator SHA900f7bdc41bf7f7d5ccd85c66619257a34a52c1f3e812e4eb867a5665a1099e9.
The copied application remains packet05 until the controlled transition.

Schedule: at most32 requests, two original boat clips, then single24, boundary4
and all48. Each selection starts with one cold compiled boat qualification;
restored/compiled/restored triples follow for boat42, marble17 and bird123.
Every completed clip must match all four original raw outputs. Candidate and
original ownership, actual graph coverage and every block's11call receipts
are mandatory. Exact byte comparisons, stage graphs, source identities,
strict determinism, failure halt and verified bounded retention are retained.

Cold request timeouts are1200s/2400s/7200s for one/four/48blocks; all other
requests1200s. The outer client adds60s. These are bounds, not duration or
memory estimates. Timeout stops subsequent submissions and preserves the
server job; it does not prove cancellation. No restart or retry action exists
in this client. Initialization/compilation costs are excluded from the small
paired warm timing summaries and retained in per-request results.

Nine client tests and27 receipt tests pass without Torch imports. They cover
the closed schedule, unchanged graph templates, separate candidate identities,
paired timing arithmetic, incomplete/forged receipts, block/device swaps,
source drift and missing stage qualification. Independent source review found
no blocker in client or validator. The venv check-only command passed against
packet06, touching no endpoint or GPU and creating no application run directory.
Evidence: data/multiblock-client-stdlib-01.json,
data/multiblock-receipts-stdlib-01.json and
data/multiblock-client-check-only-01.json. The latter contains exact arguments
and the complete bounded schedule. Native validation and speed are pending.

The already-authorized next action is one controlled LTX application reload:
verify idle PID17769/start identity, send oneSIGINT, confirm exit/render owner
release/listener availability, launch sealed packet06 once and bind its startup
identity/strictness. Then submit this client once and halt on any failure.
No host reboot, driver reset, power/swap/page-cache changes or restart chain.
