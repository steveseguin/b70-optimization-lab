# Packet137 fixed device proposals

Status: CPU preparation only; no device execution is authorized in this task.
The coordinator may later admit the new proposed files. No live queue is edited.

Question: does exact immutable draft embedding projection plus bounded rank0
token preparation improve the fixed packet136 banked runtime?

Identity: packet136 bundle8 at `3dfcff0ca`, unchanged `iq3-p49-split32-v1`
arithmetic, target/draft weight pins, BF16 KV, 80,128-row draft head prefix,
route/recurrence/head/expert choices and dispatch. All five views keep
`miss=banks-batch`. The only selection difference is `token_input`: original
or both. Attribution selections draft_table and target_buffers are implemented
and CPU-startup checked, but are not additional queued experimental arms.
The final binary and source closure are in `v5/evidence/build.json`; exact
selections and table SHA-256 are in `v5/lineage/`. The parent136 binding and
original oracle binding are independently verified.

1. Lane B smoke: one load, both, twelve 64-token prompts plus the separate
   incident64 check. Require the original target oracle for every response
   and the pre-ready 32-row device table byte check. Store proposal sequences.
2. Lane B bracket: one load, original/both/original/both/original. Each view
   performs a full reset and runs twelve 128-token prompts plus incident64.
   Require exact target tokens, per-prompt draft proposals and acceptance
   across all five views. All allocation/weight descriptors must be unchanged,
   with zero weight uploads after load.
3. The same lane A bracket is proposed separately and remains unqueued.
   It is conditioned on the exact lane B smoke as well as live admission.

All views allocate the same complete table, pinned row and target buffers
before the first control. Table file hash and read-only mapping are fixed
for the load. The table is over the entire vocabulary, independent of suite
inputs. No prompt, KV, history or response reuse is allowed across requests.
Each response reports cached_tokens=0; the existing request-reset inventory
and all six bank captures are checked. No lower precision or alternative
draft proposal is substituted.

Measure conventional 99 timestamp intervals over tokens 1–100, then median
within each prompt class and median across classes. Retain per-request timing,
TTFT, tokens, proposals, acceptance, identity and reset/teardown evidence.
Both candidate rates must exceed every control by at least 0.5%; A/A control
drift must not exceed 3%. Failed quality, proposal, memory, seal, oracle, drain
or control-drift gates refuse qualification. There is no retry or next-arm
search after a fault. Existing cooperative drain and coordinator recovery
remain authoritative.

This one-load, 128-token result is a diagnostic screen. It does not establish
fresh-load device determinism, a 512-token realistic final gate, a public
record or a submission. Packet136's own separate promotion gates remain
pending independently. No bank speedup is attributed to token-input work.

Expected smoke: 240–360 seconds; bracket: 720–1,200 seconds. Each watchdog is
4,800 seconds (at least 4× the upper estimate). Host admission requires
97 GiB + 1,271,398,400 table bytes + 5,120 pinned bytes + 32,768 reserved target
buffer bytes. Banked state adds zero net device arena bytes relative to copy.
Disk must retain 25 GB free. CPU compilation is serialized by the shared
compile-turn gate; CPU-only preparation stays within 4 GiB.
