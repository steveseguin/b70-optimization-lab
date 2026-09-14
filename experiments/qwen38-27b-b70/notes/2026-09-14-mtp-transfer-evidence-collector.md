# MTP transfer evidence packing and replay

[Collector/verifier](../scripts/collect-mtp-transfer-evidence.py) follows the prior
AMD-transfer packet convention: deterministic gzip/tar, individually hashed
members, a manifest and a summary reconstructed from retained measurements.
It uses local files and CPU only. Collection and independent archive replay
passed after closure of the faulted campaign: one archive, 310 members.
[Summary](../data/2026-09-14-mtp-lossless-transfer/summary.json).
The model client was not run; the replay pass validates retained evidence,
not optimization quality or speed.

The parent must first create `campaign-completion.json` under the raw campaign
root. Each explicitly selected operator stage must have a finished state and
confirmed stop. A present client campaign must have its completed or aborted
receipt. If no client was launched, the closure receipt must explicitly include
`client_not_run_reason`; absence never becomes a passing result. Failed setup
stages `communication-native-01` and `communication-native-02` are mandatory.
Add every later completed operator stage explicitly.

The completed collection used these stages (do not overwrite the frozen packet):

```bash
python3 experiments/qwen38-27b-b70/scripts/collect-mtp-transfer-evidence.py \
  --operator-stage communication-native-01 \
  --operator-stage communication-native-02 \
  --operator-stage communication-native-03 \
  --operator-stage communication-native-04

python3 experiments/qwen38-27b-b70/scripts/collect-mtp-transfer-evidence.py --verify
```

Defaults select `client-campaign`, `research-server` and
`campaign-completion.json` beneath
`/mnt/fast-ai/bench-results/mtp-lossless-transfer-20260914`. These names can be
provided explicitly. Omit the running-log option if a service log snapshot is
unnecessary. With it, logs live under a labeled `running-log-snapshot/` archive
prefix and are described as point-in-time captures. Cache/model/native-library
files and unrelated journals are excluded.

The bundle retains full strict numeric outputs, canaries, raw context SSE and
histogram snapshots, all RPC/native metadata responses, exact launch/source
identities and the frozen reference evidence. The verifier reconstructs strict
99-interval class-balanced rates and every available context sample/aggregate.
A completed client claim additionally requires all five exact strict attempts,
all four complete context profiles and both native metadata ranks. Aborted
attempts preserve available results and report their failure separately.

Native operator output files are admitted only under their registered rank,
shape, fixture and arm filenames. Identical output bytes are stored once under
a content hash; a path map preserves every original file association. The
collector streams binary bytes and splits archives at 64 MiB uncompressed
payload per part, rather than loading gigabytes into memory. Each compressed
part must remain below 95 MiB. Replay hashes every raw output byte, checks the
recorded XCCL/candidate equality, and recomputes present paired rank timings.
Completed operator quality claims additionally require the entire registered
shape/fixture/repeat coverage and matching outputs on both ranks.

Existing packets are frozen: collection refuses an existing manifest. The
`--verify` path reads only archived files and matching repository parser source;
it does not reopen the raw campaign paths. Source drift is an explicit replay
failure rather than silently substituting a newer parser.

Nine [CPU tests](../scripts/test_collect_mtp_transfer_evidence.py) pass. They cover
streamed binary roundtrips, deterministic archives, path/symlink refusal,
archive/member tampering, interval recomputation and honest retention of output
mismatches. Tests use temporary synthetic bytes; they neither collect active
receipts nor perform network/GPU actions.
