# Packet49c storage and retention

All new builds and chain outputs live under
`/home/steve/own-xpu-runtime-results/packet49c-round2/` on root. This is not
additional disk capacity. No predecessor, oracle or queued-chain file is removed.

| Item | Bytes |
| --- | ---: |
| Root free-space floor | 8,000,000,000 |
| Packet49b pending model windows | 5,818,804,480 |
| Additional shared-oracle growth | 500,000,000 |
| Packet49c retained build cap | 650,000,000 |
| Packet49c early retained evidence cap | 128,000,000 |
| Packet49c model windows, no compression credit | 5,818,804,480 |
| Required before an empty packet49c build | 20,915,608,960 |

The original 2.5 GB retained-build envelope would require 22,765,608,960
bytes, more than the roughly 20.97 GB initially available. The new packet
therefore requires a lean retained build, with sanitizer debug information
and unreachable duplicate entrypoints omitted and its own regenerable objects
removed after their identities are recorded. The 650 MB figure is an admission
limit, not an estimate or a promise that an unfinished build fits.
`storage_precheck.py` must pass against the completed build before any early
or model window. The final receipt records actual free space and build bytes.

CPU compilation has a separate strict 2.5 GB peak limit via
`cpu_build_admit`. It still preserves the root floor, every pending packet49b
model write and the oracle allowance. No packet49c device chain can start
while its build is unfinished. Compile one file at a time and remove only
this packet's recorded regenerable scratch. A final retained build above
650 MB fails admission, even if the aggregate build-plus-chain cap has space.

`storage-parent-binding.json` binds the untouched packet49b build receipt.
Only a passing qualifying device receipt, with that seal and the exact
cards/context/draft/split identity, plus its canonical queue completion state,
releases that window's pending allowance. Missing, changed or malformed
evidence retains the entire allowance. **STOP, an exited queue, or the choice
to use packet49c does not release packet49b's reserve.**

Each chain's model allowance is 5,818,804,480 bytes. K2's 2.5 GB scratch peak
is smaller than that envelope. Early oversized fixture output is discarded
only after inherited verified hash/provenance retention; compact early
evidence and root logs must stay within 128 MB. Overflow preserves evidence
and refuses further launches. The policy applies to one registered chain,
`build/device-cards01-a`, not multiple retries.

Packet49b's sealed policy also reserves the older packet49 model chain.
That policy is unchanged: preparing packet49c may make a later packet49b
admission fail even when the two requested chains' physical storage fits.
The planned switch stops its waiting queue before any model window starts;
this packet does not claim to make all three historical queues runnable.

Keep source, gates, seals, build receipts and compact evidence in Git.
Keep all sealed executable artifacts in the external result tree. Objects
are reproducible from retained compiler/link commands and source identities;
removing them must not remove an artifact enumerated by the seal. Inherited
input fixtures and RoPE are read-only links. Shared-oracle outputs are neither
copied nor edited. A failed storage check is a coordinator review item,
never permission to delete another packet's evidence or weaken the floor.

## Tracked large input

`rope.bf16` is the4,194,304-byte frozen rotary-position fixture copied
byte-for-byte from packet49b (also the admitted packet45 fixture). The local
copy is required by the inherited build/input seal and kernel fixture paths;
it is not a generated cache or model weight. Restore it from
`../packet49b-gemv/rope.bf16` and require its SHA256 to equal the entry in the
compiled-source map before rebuilding. It is retained explicitly despite
exceeding the1MiB repository hygiene review threshold.
