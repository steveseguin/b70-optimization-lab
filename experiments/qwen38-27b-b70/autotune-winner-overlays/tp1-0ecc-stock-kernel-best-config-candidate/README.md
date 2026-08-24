# TP1 0ecc stock-kernel decision overlay candidate

Status: stale before launch. vLLM `main` advanced to `e239947777` before the
post-reboot hardware gate or any arm used this packet. Keep these exact files
as 0ecc historical evidence; do not relabel or silently carry them into e239.
A separately versioned e239 packet requires a fresh compatibility map.

This bundle contains the 38 `.best_config` decision records from the fully
qualified vLLM-0ecc/stock-base-kernel TP1 cache. It is a candidate for the
literal-current vLLM-0ecc/kernel-`baaa05bb4e` lane, whose correctness and
quality passed but whose two strict medians missed the protected speed floor.

This is not a source rollback and not a compiled-cache transfer. The bundle
contains no generated kernel, binary, AOT model, outer cache, or model data.
The target runner seeds these decision JSON files into an otherwise empty ext4
cache and must perform a fresh current-kernel compilation.

Compatibility was checked against both fresh campaign caches:

- identical outer and AOT namespaces;
- byte-identical computation graph;
- identical code, compiler, config, and environment hashes;
- all 38 relative paths present in both lanes;
- all 38 embedded `configs_hash` values match;
- 17 normalized selected configurations differ, while 21 agree.

The source campaign ran on host kernel `7.0.0-28-generic`. Before this packet
was committed or executed, the host hard-rebooted and selected
`7.0.0-30-generic`. The candidate is therefore a cross-boot qualification, not
a same-boot causal attribution. Its three arms must all remain on one boot of
the exact new kernel.

The new boot first requires a four-card compute/peer/XCCL hardware gate and a
fresh three-arm untreated current-code control. If that control passes the
protected diagnostic and both strict floors, the packet is not run or credited.
The packet is eligible only after a speed-only control miss with every model,
canary, quality, cache, source, repository, and host gate still passing.

The candidate remains unqualified until its fresh diagnostic and two sealed
natural-EOS replays pass the frozen TP1 speed, quality, model, cache, host,
repository, image, and source-recency gates. A miss is preserved as evidence
and never lowers the historical floor.

Verify the bundle with:

```bash
cd source
sha256sum -c ../manifest.sha256
```

See [`metadata.json`](metadata.json) for exact source/target identities and
the frozen qualification contract.
