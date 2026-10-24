# Same-pair Host qualification

The first designated run passed: **one two-rank HOST_ONLY pair**, target-only generation, RESET on both ranks, then MTP generation through the actual inherited NativeController. Both requests returned `[0,0,0,0]` and identical complete target plan-buffer/alternate-bank/state-JSON bytes. This is synthetic miniature geometry, not a real-model quality result.

MTP did real work: three guesses, two accepted and one rejected/redone. Both native owners reported safe closure, zero in-flight work and zero live allocation bytes. Their processes exited 0; the coordinator sent no signals, requested no incident stop and retained no owner. RESET reported preserved allocation IDs on both ranks. The unchanged adapter was run once; there was no retry or new build.

- [Run result](evidence/host-pair.json), [exact runner](evidence/host-pair-run.py), [log](evidence/host-pair-run.log).
- [Closeout verification](evidence/host-pair-closeout.json) rehashed the actual state files and verified the two RESET/teardown records.
- [Complete raw proof](evidence/host-pair-raw.tar.gz) retains all 512 files (790,847 uncompressed bytes), including exact executed adapter/test snapshots, plan, launches, native requests/results, states and owner receipts. The [per-file index](evidence/host-pair-index.json) records size/SHA; every archive member was read back and matched. Original files remain under the indexed ignored build directory.

The CPU process used nice 19, cores 8–15/24–31, two threads and a 4 GiB address-space cap. The successful historical Host build and its exact retained-source map were checked before launching. No GPU executable, model payload, service or device enumeration was used. Host event/queue completion is the inherited MockDevice model; this proof does not establish native DMA behavior or physical GPU drain. Current full native build and real-model admission are separate gates.
